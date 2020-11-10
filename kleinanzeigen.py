#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=C0301,bad-whitespace,invalid-name
# pylint: disable=C0111
# pylint: disable=W0141,input-builtin

"""
Created on Tue Oct  6 00:15:14 2015
Updated and improved by x86dev Dec 2017.

@author: Leo; Eduardo; x86dev
"""
from __future__ import absolute_import
from __future__ import division

import json
import getopt
import os
import re
import signal
import sys
import time

from random import randint
import logging
from datetime import datetime
import dateutil.parser
from urllib import parse

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions

# Whether to run in interactive mode or not.
g_fInteractive = True
# Whether to run in headless mode or not.
g_fHeadless    = False

json.JSONEncoder.default = \
    lambda self, obj: \
        (obj.isoformat() if isinstance(obj, datetime) else None)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
fh = logging.FileHandler('kleinanzeigen.log')
fh.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s %(message)s')

log.addHandler(ch)
log.addHandler(fh)

def profile_read(sProfile, oConfig):

    log.info("Loading profile '%s'" % (sProfile,))

    if not os.path.isfile(sProfile):
        return False

    with open(sProfile, encoding="utf-8") as file:
        oConfig.update(json.load(file))

    # Sanitize.
    if oConfig['glob_phone_number'] is None:
        oConfig['glob_phone_number'] = ''

    if oConfig['glob_street'] is None:
        oConfig['glob_street'] = ''

    return True

def profile_write(sProfile, oConfig):

    log.info("Saving profile '%s'" % (sProfile,))

    with open(sProfile, "w+", encoding='utf8') as fh_config:
        text = json.dumps(oConfig, sort_keys=True, indent=4, ensure_ascii=False)
        fh_config.write(text)

def login_has_captcha(driver):
    fRc = False
    try:
        e = WebDriverWait(driver, 5).until(
            expected_conditions.presence_of_element_located((By.ID, "login-recaptcha"))
            )
        if e:
            fRc = True
    except TimeoutException:
        pass
    log.info("Login Captcha: %s", fRc)
    return fRc

def login(driver, config):
    fRc = True
    log.info("Logging in ...")
    driver.set_page_load_timeout(90)
    try:
        driver.get('https://www.ebay-kleinanzeigen.de/m-einloggen.html?targetUrl=/')

        log.info('Waitng for login page ...')

        # Accept (click) GDPR banner
        WebDriverWait(driver, 180).until(
            expected_conditions.element_to_be_clickable((By.ID, 'gdpr-banner-accept'))).click()

        log.info('Sending login credentials ...')

        # Send e-mail
        WebDriverWait(driver, 180).until(
            expected_conditions.presence_of_element_located((By.ID, "login-email"))
        ).send_keys(config['glob_username'])
        fake_wait()

        # Send password
        driver.find_element_by_id('login-password').send_keys(config['glob_password'])
        fake_wait()

        # Check for captcha
        fHasCaptcha = login_has_captcha(driver)
        if fHasCaptcha:
            if g_fInteractive:
                log.info("\t*** Manual login captcha input needed! ***")
                log.info("\tFill out captcha and submit, after that press Enter here to continue ...")
                wait_key()
            else:
                log.info("\tLogin captcha input needed, but running in non-interactive mode! Skipping ...")
                fRc = False
        else:
            driver.find_element_by_id('login-submit').click()

    except TimeoutException:
        log.info("Unable to login -- loading site took too long?")
        fRc = False

    except NoSuchElementException:
        log.info("Unable to login -- login form element(s) not found")
        fRc = False

    return fRc

def fake_wait(msSleep=None):
    if msSleep is None:
        msSleep = randint(777, 3333)
    if msSleep < 100:
        msSleep = 100
    log.debug("Waiting %d ms ...",  msSleep)
    time.sleep(msSleep / 1000)

def delete_ad(driver, ad):

    log.info("\tDeleting ad ...")

    driver.get("https://www.ebay-kleinanzeigen.de/m-meine-anzeigen.html")
    fake_wait()

    adIdElem = None

    if "id" in ad:
        log.info("\tSearching by ID (%s)", ad["id"])
        try:
            adIdElem = driver.find_element_by_xpath("//a[@data-adid='%s']" % ad["id"])
        except NoSuchElementException:
            log.info("\tNot found by ID")

    if adIdElem is None:
        log.info("\tSearching by title (%s)", ad["title"])
        try:
            adIdElem  = driver.find_element_by_xpath("//a[contains(text(), '%s')]/../../../../.." % ad["title"])
            adId      = adIdElem.get_attribute("data-adid")
            log.info("\tAd ID is %s", adId)
        except NoSuchElementException:
            log.info("\tNot found by title")

    if adIdElem is not None:
        try:
            btn_del = adIdElem.find_element_by_class_name("managead-listitem-action-delete")
            btn_del.click()

            fake_wait()

            try:
                driver.find_element_by_id("modal-bulk-delete-ad-sbmt").click()
            except:
                driver.find_element_by_id("modal-bulk-mark-ad-sold-sbmt").click()

            log.info("\tAd deleted")

            fake_wait(randint(2000, 3000))
            webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            return True

        except NoSuchElementException:
            log.info("\tDelete button not found")
    else:
        log.info("\tAd does not exist (anymore)")

    ad.pop("id", None)
    return False

# From: https://stackoverflow.com/questions/983354/how-do-i-make-python-to-wait-for-a-pressed-key
def wait_key():
    """ Wait for a key press on the console and return it. """
    result = None
    if os.name == 'nt':
        result = input("Press Enter to continue ...")
    else:
        import termios
        fd = sys.stdin.fileno()

        oldterm = termios.tcgetattr(fd)
        newattr = termios.tcgetattr(fd)
        newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, newattr)

        try:
            result = sys.stdin.read(1)
        except IOError:
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)

    return result

def post_ad_has_captcha(driver, ad):

    _ = ad
    fRc  = False

    try:
        captcha_field = driver.find_element_by_xpath('//*[@id="postAd-recaptcha"]')
        if captcha_field:
            fRc = True
    except NoSuchElementException:
        pass

    log.info("Captcha: %s", fRc)

    return fRc

def post_ad_is_allowed(driver, ad):

    _ = ad
    fRc  = True

    # Try checking for the monthly limit per account first.
    try:
        icon_insertionfees = driver.find_element_by_class_name('icon-insertionfees')
        if icon_insertionfees:
            log.info("\t*** Monthly limit of free ads per account reached! Skipping ... ***")
            fRc = False
    except NoSuchElementException:
        pass

    log.info("Ad posting allowed: %s", fRc)

    return fRc

def post_ad_mandatory_combobox_select(driver, ad, sName, sValue):
    _ = ad
    for el in driver.find_elements_by_xpath('//*[@class="formgroup-label-mandatory"]'):
        log.info("Detected mandatory field: '%s'", el.text)
        if sName in el.text:
            sForId = el.get_attribute("for")
            Select(driver.find_element_by_id(sForId)).select_by_visible_text(sValue)
            fake_wait()
            return True
    return False

def post_ad_mandatory_fields_set(driver, ad):
    for el in driver.find_elements_by_xpath('//*[@class="formgroup-label-mandatory"]'):
        try:
            sForId = el.get_attribute("for")
            if sForId is not None:
                log.info("Detected mandatory field (Name='%s', ID='%s')", el.text, sForId)
                reMatch = re.search('.*\.(.*)_s.*', sForId, re.IGNORECASE)
                if reMatch is not None:
                    sForIdRaw = reMatch.group(1)
                    fUseDefault = False
                    if "field_" + sForIdRaw in ad:
                        try:
                            Select(driver.find_element_by_id(sForId)).select_by_visible_text(ad["field_" + sForIdRaw])
                        except NoSuchElementException:
                            log.info("*** Warning: Value for combo box '%s' invalid in config, setting to default (first entry)", sForIdRaw)
                            fUseDefault = True
                    else:
                        log.info("*** Warning: No value for combo box '%s' defined, setting to default (first entry)", sForIdRaw)
                        fUseDefault = True
                    if fUseDefault:
                        s = Select(driver.find_element_by_id(sForId))
                        iOpt = 0
                        for o in s.options:
                            # Skip empty options (defaults?)
                            if len(o.get_attribute("value")):
                                break
                            iOpt += 1
                        s.select_by_value(s.options[iOpt].get_attribute("value"))
                    fake_wait()
                else:
                    sForIdRaw = sForId
                    if "field_" + sForIdRaw in ad:
                        sValue = ad["field_" + sForIdRaw]
                    else:
                        log.info("*** Warning: No value for text field '%s' defined, setting to empty value" % (sForIdRaw,))
                        sValue = 'Nicht angegeben'
                    try:
                        driver.find_element_by_id(sForId).send_keys(sValue)
                        fake_wait()
                    except:
                        pass
        except NoSuchElementException:
            pass

def post_field_set_text(driver, ad, field_id, sValue):
    if sValue:
        e = driver.find_element_by_id(field_id)
        e.clear()
        lstLines = [x.strip('\\n') for x in sValue.split('\\n')]
        for sLine in lstLines:
            e.send_keys(sLine)
            if len(lstLines) > 1:
                e.send_keys(Keys.RETURN)

        fake_wait()

def post_field_select(driver, ad, field_id, sValue):
    driver.find_element_by_xpath("//input[@name='%s' and @value='%s']" % (field_id, sValue)).click()
    fake_wait()

def post_upload_image(driver, ad, file_path_abs):
    try:
        fileup = driver.find_element_by_xpath("//input[@type='file']")
        uploaded_count = len(driver.find_elements_by_class_name("imagebox-thumbnail"))
        log.debug("\tUploading image: %s" % file_path_abs)
        fileup.send_keys(os.path.abspath(file_path_abs))
        total_upload_time = 0
        while uploaded_count == len(driver.find_elements_by_class_name("imagebox-thumbnail")) and \
                total_upload_time < 30:
            fake_wait(1000)
            total_upload_time += 1

        if uploaded_count == len(driver.find_elements_by_class_name("imagebox-thumbnail")):
            log.warning("\tCould not upload image: %s within %s seconds" % (file_path_abs, total_upload_time))
        else:
            log.debug("\tUploaded file in %s seconds" % total_upload_time)
    except NoSuchElementException:
        log.warning("Unable to find elements required for uploading images; skipping")
        pass

def post_upload_path(driver, ad, path_abs):
    """
    Uploads all images of a given absolute path.
    Note: Oldest images will be uploaded last, so that the oldest image will be the main (gallery) picture.
    """
    if not path_abs.endswith("/"):
        path_abs += "/"
    files = os.listdir(path_abs)
    files.sort(reverse=False)
    for filename in files:
        if not filename.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
            continue
        post_upload_image(driver, ad, path_abs + filename)

def post_ad(driver, ad):

    log.info("\tPublishing ad '...")

    # Sanitize ad values if not set
    if ad["price_type"] not in ['FIXED', 'NEGOTIABLE', 'GIVE_AWAY']:
        ad["price_type"] = 'NEGOTIABLE'

    driver.get('https://www.ebay-kleinanzeigen.de/m-meine-anzeigen.html')

    # Click to post a new ad
    driver.find_element_by_id('site-mainnav-postad-link').click()
    fake_wait(randint(4000, 8000))

    # Find out where we are; might be some A/B testing the site does ...
    try:
        e = driver.find_element_by_id('pstad-lnk-chngeCtgry')
        if e:
            e.click()
    except:
        pass

    # Change category
    dQuery = parse.parse_qs(ad["caturl"])
    if dQuery:
        if 'https://www.ebay-kleinanzeigen.de/p-kategorie-aendern.html#?path' in dQuery:
            sPathCat = dQuery.get('https://www.ebay-kleinanzeigen.de/p-kategorie-aendern.html#?path')
        elif 'https://www.ebay-kleinanzeigen.de/p-anzeige-aufgeben.html#?path' in dQuery:
            sPathCat = dQuery.get('https://www.ebay-kleinanzeigen.de/p-anzeige-aufgeben.html#?path')

        if sPathCat:
            for sCat in sPathCat[0].split('/'):
                log.debug('Category: %s' % (sCat,))
                try:
                    driver.find_element_by_id('cat_' + sCat).click()
                    fake_wait()
                except:
                    log.warning("Category not existing (anymore); skipping")
                    return False
            try:
                driver.find_element_by_id('postad-step1-sbmt').submit()
                fake_wait(randint(1000, 2000))
            except:
                log.error("Category submit button not found, skipping")
                return False
        else:
            log.warning("Invalid category URL specified; skipping")
            return False
    else:
        log.warning("No category specified; skipping")
        return False

    # Check if posting an ad is allowed / possible
    fRc = post_ad_is_allowed(driver, ad)
    if fRc is False:
        return fRc

    # Some categories needs this
    post_ad_mandatory_fields_set(driver, ad)

    # Fill form
    post_field_set_text(driver, ad, 'postad-title',       ad["title"])
    post_field_set_text(driver, ad, 'pstad-descrptn',     config['glob_ad_prefix'] + ad["desc"] + config['glob_ad_suffix'])
    post_field_set_text(driver, ad, 'pstad-price',        ad["price"])

    post_field_select  (driver, ad, 'priceType',          ad["price_type"])

    post_field_set_text(driver, ad, 'pstad-zip',          config["glob_zip"])
    post_field_set_text(driver, ad, 'postad-phonenumber', config["glob_phone_number"])
    post_field_set_text(driver, ad, 'postad-contactname', config["glob_contact_name"])
    post_field_set_text(driver, ad, 'pstad-street',       config["glob_street"])

    sPhotoPathRoot = config["glob_photo_path"]
    if sPhotoPathRoot:
        # Upload images from photofiles
        if "photofiles" in ad:
            for sPath in ad["photofiles"]:
                post_upload_image(driver, ad, os.path.join(sPhotoPathRoot, sPath))

        # Upload images from directories
        sPhotoPathDir = ''
        if 'photo_dir' in ad:
            sPhotoPathDir = ad["photo_dir"]
        elif 'photodir' in ad:
            sPhotoPathDir = ad["photodir"]

        if sPhotoPathDir:
            post_upload_path(driver, ad, os.path.join(sPhotoPathRoot, sPhotoPathDir))
    else:
        log.info("No global photo path specified, skipping photo uploads")

    fake_wait()

    submit_button = driver.find_element_by_id('pstad-frmprview')
    if submit_button:
        submit_button.click()

    fake_wait()

    fHasCaptcha = post_ad_has_captcha(driver, ad)
    if fHasCaptcha:
        if g_fInteractive:
            log.info("\t*** Manual captcha input needed! ***")
            log.info("\tFill out captcha and submit, after that press Enter here to continue ...")
            wait_key()
        else:
            log.info("\tCaptcha input needed, but running in non-interactive mode! Skipping ...")
            fRc = False

    if fRc:
        try:
            submit_button = driver.find_element_by_id('prview-btn-post')
            if submit_button:
                submit_button.click()
        except NoSuchElementException:
            pass

        try:
            parsed_q = parse.parse_qs(urllib.parse.urlparse(driver.current_url).query)
            addId = parsed_q.get('adId', None)[0]
            log.info("\tPosted as: %s" % driver.current_url)
            if "id" not in ad:
                log.info("\tNew ad ID: %s" % addId)
                ad["date_published"] = datetime.utcnow()

            ad["id"]           = addId
            ad["date_updated"] = datetime.utcnow()
        except:
            pass

    if fRc is False:
        log.info("\tError publishing ad")

    return fRc

def session_create(config):

    log.info("Creating session")

    # For now use the Chrome driver, as Firefox doesn't work (empy page)
    fUseFirefox = False

    if fUseFirefox:
        ff_options = FirefoxOptions()
        if g_fInteractive:
            ff_options.add_argument("--headless")
        if config.get('webdriver_enabled', False) is False:
            ff_options.set_preference("dom.webdriver.enabled", False)
        ff_profile = webdriver.FirefoxProfile()
        ff_profile.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 5.1; rv:7.0.1) Gecko/20100101 Firefox/7.0.1")
        driver = webdriver.Firefox(firefox_profile=ff_profile, firefox_options=ff_options)
    else:
        # See: https://chromium.googlesource.com/chromium/src/+/master/chrome/common/chrome_switches.cc
        #      https://chromium.googlesource.com/chromium/src/+/master/chrome/common/pref_names.cc
        cr_options = ChromeOptions()
        cr_options.add_argument("--no-sandbox")
        cr_options.add_argument("--disable-setuid-sandbox")
        cr_options.add_argument("--disable-blink-features")
        cr_options.add_argument("--disable-blink-features=AutomationControlled")
        if g_fHeadless:
            cr_options.add_argument("--headless")
            cr_options.add_argument("--disable-extensions")
            cr_options.add_argument("--disable-gpu")
            cr_options.add_argument("--disable-dev-shm-usage")
            cr_options.add_argument("--start-maximized")
        cr_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.50 Safari/537.36")
        cr_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        cr_options.add_experimental_option('useAutomationExtension', False)

        driver = webdriver.Chrome(options=cr_options)

    log.info("New session is: %s %s" % (driver.session_id, driver.command_executor._url))

    config['session_id'] = driver.session_id
    config['session_url'] = driver.command_executor._url

    return driver

def session_attach(config):

    log.info("Trying to attach to session %s %s" % (config['session_id'], config['session_url']))

    # Save the original function, so we can revert our patch
    org_command_execute = webdriver.Remote.execute

    def new_command_execute(self, command, params=None):
        if command == "newSession":
            # Mock the response
            return {'success': 0, 'value': None, 'sessionId': config['session_id']}
        else:
            return org_command_execute(self, command, params)

    # Patch the function before creating the driver object
    webdriver.Remote.execute = new_command_execute

    driver = webdriver.Remote(command_executor=config['session_url'], desired_capabilities={})
    driver.session_id = config['session_id']

    try:
        log.info("Current URL is: %s" % driver.current_url)
    except:
        log.info("Session does not exist anymore")
        config['session_id'] = None
        config['session_url'] = None
        driver = None

        # Make sure to put the original executor back in charge.
        webdriver.Remote.execute = org_command_execute

    return driver

def signal_handler(sig, frame):
    print('Exiting script')
    sys.exit(0)

if __name__ == '__main__':

    signal.signal(signal.SIGINT, signal_handler)

    try:
        aOpts, aArgs = getopt.gnu_getopt(sys.argv[1:], "ph", [ "profile=", "headless", "non-interactive", "help" ])
    except getopt.GetoptError as msg:
        print(msg)
        print('For help use --help')
        sys.exit(2)

    sProfile = ""

    for o, a in aOpts:
        if o in '--profile':
            sProfile = a
        elif o in '--headless':
            g_fHeadless = True
        elif o in '--non-interactive':
            g_fInteractive = False

    if not sProfile:
        print('No profile specified')
        sys.exit(2)

    log.info('Script started')
    log.info("Using profile: %s" % sProfile)

    if g_fHeadless:
        log.info("Running in headless mode")
    if not g_fInteractive:
        log.info("Running in non-interactive mode")

    config = {}

    if not profile_read(sProfile, config):
        log.error("Profile file not found / accessible!")
        sys.exit(1)

    fRc          = True
    fNeedsLogin  = True
    fForceUpdate = False

    dtNow = datetime.utcnow()

    driver = None

    if config.get('session_id') is not None:
        driver = session_attach(config)

    for ad in config["ads"]:

        fNeedsUpdate = False

        log.info("Handling '%s'" % ad["title"])

        if "date_updated" in ad:
            dtLastUpdated = dateutil.parser.parse(ad["date_updated"])
        else:
            dtLastUpdated = dtNow
        dtDiff            = dtNow - dtLastUpdated

        if  "enabled" in ad \
        and ad["enabled"] == "1":
            if "date_published" in ad:
                log.info("\tAlready published (%d days ago)" % dtDiff.days)
                glob_update_after_days = int(config.get('glob_update_after_days'))
                if dtDiff.days > glob_update_after_days:
                    log.info("\tCustom global update interval (%d days) set and needs to be updated" % \
                             glob_update_after_days)
                    fNeedsUpdate = True

                ad_update_after_days = 0
                if "update_after_days" in ad:
                    ad_update_after_days = int(ad["update_after_days"])

                if  ad_update_after_days != 0 \
                and dtDiff.days > ad_update_after_days:
                    log.info("\tAd has a specific update interval (%d days) and needs to be updated" % \
                             ad_update_after_days)
                    fNeedsUpdate = True
            else:
                log.info("\tNot published yet")
                fNeedsUpdate = True
        else:
            log.info("\tDisabled, skipping")

        if fNeedsUpdate \
        or fForceUpdate:

            if driver is None \
            and fNeedsLogin:
                driver = session_create(config)
                profile_write(sProfile, config)
                fR = login(driver, config)
                if fRc:
                    fake_wait(randint(12222, 17777))
                    fNeedsUpdate = False
                else:
                    log.info('Login failed')
                    break

            delete_ad(driver, ad)
            fake_wait(randint(12222, 17777))

            fPosted = post_ad(driver, ad)
            if not fPosted:
                break

            log.info("Waiting for handling next ad ...")
            fake_wait(randint(12222, 17777))

    # Make sure to update the profile's data before terminating.
    profile_write(sProfile, config)

    log.info("Script done")
