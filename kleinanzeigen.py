#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=C0301
# pylint: disable=C0111

"""
Created on Tue Oct  6 00:15:14 2015
Updated and improved by x86dev Dec 2017.

@author: Leo; Eduardo; x86dev
"""
import json
import getopt
import os
import re
import signal
import sys
import time
import urlparse

from urlparse import parse_qs
from random import randint
import logging
from datetime import datetime
import dateutil.parser

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions

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
    if os.path.isfile(sProfile):
        with open(sProfile) as data:
            oConfig.update(json.load(data))

        # Sanitize.
        if oConfig.get('headless') is None:
            oConfig['headless'] = False

        if oConfig['glob_phone_number'] is None:
            oConfig['glob_phone_number'] = ''

        if oConfig['glob_street'] is None:
            oConfig['glob_street'] = ''

def profile_write(sProfile, oConfig):
    fhConfig = open(sProfile, "w+")
    fhConfig.write(json.dumps(oConfig, sort_keys=True, indent=4))
    fhConfig.close()

def login_has_captcha(driver, fInteractive):
    fRc = False
    try:
        e = WebDriverWait(driver, 5).until(
            expected_conditions.presence_of_element_located((By.ID, "login-recaptcha"))
            )
        if e:
            fRc = True
    except TimeoutException:
        pass
    log.info("Login Captcha: %s" % fRc)
    return fRc

def login(driver, config, fInteractive):
    fRc = True
    log.info("Logging in ...")
    driver.set_page_load_timeout(90)
    try:
        driver.get('https://www.ebay-kleinanzeigen.de/m-einloggen.html?targetUrl=/')

        log.info('Waitng for login page ...')

        # Accept (click) GDPR banner
        WebDriverWait(driver, 180).until(
            expected_conditions.element_to_be_clickable((By.ID, 'gdpr-banner-accept'))).click()

        # Send e-mail
        text_area = WebDriverWait(driver, 180).until(
           expected_conditions.presence_of_element_located((By.ID, "login-email"))
        ).send_keys(config['glob_username'])
        fake_wait()

        # Send password
        driver.find_element_by_id('login-password').send_keys(config['glob_password'])
        fake_wait()

        # Check for captcha
        fHasCaptcha = login_has_captcha(driver, fInteractive)
        if fHasCaptcha:
            if fInteractive:
                log.info("\t*** Manual login captcha input needed! ***")
                log.info("\tFill out captcha and submit, after that press Enter here to continue ...")
                wait_key()
            else:
                log.info("\tLogin captcha input needed, but running in non-interactive mode! Skipping ...")
                fRc = False
        else:
            driver.find_element_by_id('login-submit').click()

    except TimeoutException as e:
        log.info("Unable to login -- loading site took too long?")
        fRc = False

    except NoSuchElementException as e:
        log.info("Unable to login -- login form element(s) not found")
        fRc = False

    return fRc

def fake_wait(msSleep=None):
    if msSleep is None:
        msSleep = randint(777, 3333)
    if msSleep < 100:
        msSleep = 100
    log.debug("Waiting %d ms ..." % msSleep)
    time.sleep(msSleep / 1000)

def delete_ad(driver, ad):

    log.info("\tDeleting ad ...")

    driver.get("https://www.ebay-kleinanzeigen.de/m-meine-anzeigen.html")
    fake_wait()

    adIdElem = None

    if "id" in ad:
        log.info("\tSearching by ID (%s)" % (ad["id"],))
        try:
            adIdElem = driver.find_element_by_xpath("//a[@data-adid='%s']" % ad["id"])
        except NoSuchElementException as e:
            log.info("\tNot found by ID")

    if adIdElem is None:
        log.info("\tSearching by title (%s)" % (ad["title"],))
        try:
            adIdElem = driver.find_element_by_xpath("//a[contains(text(), '%s')]/../../../../.." % ad["title"])
            adId     = adIdElem.get_attribute("data-adid")
            log.info("\tAd ID is %s" % adId)
        except NoSuchElementException as e:
            log.info("\tNot found by title")

    if adIdElem is not None:
        try:
            btn_del = adIdElem.find_element_by_class_name("managead-listitem-action-delete")
            btn_del.click()

            fake_wait()

            btn_confirm_del = driver.find_element_by_id("modal-bulk-delete-ad-sbmt")
            btn_confirm_del.click()

            log.info("\tAd deleted")

            fake_wait(randint(2000, 3000))
            webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            return True

        except NoSuchElementException as e:
            log.info("\tDelete button not found")
    else:
        log.info("\tAd does not exist (anymore)")

    ad.pop("id", None)
    return False

# From: https://stackoverflow.com/questions/983354/how-do-i-make-python-to-wait-for-a-pressed-key
def wait_key():
    ''' Wait for a key press on the console and return it. '''
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

def post_ad_has_captcha(driver, ad, fInteractive):

    fRc = False

    try:
        captcha_field = driver.find_element_by_xpath('//*[@id="postAd-recaptcha"]')
        if captcha_field:
            fRc = True
    except NoSuchElementException:
        pass

    log.info("Captcha: %s" % fRc)

    return fRc

def post_ad_is_allowed(driver, ad, fInteractive):

    fRc = True

    # Try checking for the monthly limit per account first.
    try:
        icon_insertionfees = driver.find_element_by_class_name('icon-insertionfees')
        if icon_insertionfees:
            log.info("\t*** Monthly limit of free ads per account reached! Skipping ... ***")
            fRc = False
    except:
        pass

    log.info("Ad posting allowed: %s" % fRc)

    return fRc

def post_ad_mandatory_combobox_select(driver, ad, sName, sValue):
    for el in driver.find_elements_by_xpath('//*[@class="formgroup-label-mandatory"]'):
        log.info("Detected mandatory field: '%s'" % (el.text,))
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
                log.info("Detected mandatory field (Name='%s', ID='%s')" % (el.text, sForId))
                reMatch = re.search('.*\.(.*)_s.*', sForId, re.IGNORECASE)
                if reMatch is not None:
                    sForIdRaw = reMatch.group(1)
                    fUseDefault = False
                    if "field_" + sForIdRaw in ad:
                        try:
                            Select(driver.find_element_by_id(sForId)).select_by_visible_text(ad["field_" + sForIdRaw])
                        except:
                            log.info("*** Warning: Value for combo box '%s' invalid in config, setting to default (first entry)" % (sForIdRaw,))
                            fUseDefault = True
                    else:
                        log.info("*** Warning: No value for combo box '%s' defined, setting to default (first entry)" % (sForIdRaw,))
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
        except:
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
            fake_wait(500)
            total_upload_time += 0.5

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
    """
    if not path_abs.endswith("/"):
        path_abs += "/"
    for filename in os.listdir(path_abs):
        if not filename.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
            continue
        post_upload_image(driver, ad, path_abs + filename)

def post_ad(driver, ad, fInteractive):

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
    dQuery = parse_qs(ad["caturl"])
    if dQuery:
        if ('https://www.ebay-kleinanzeigen.de/p-kategorie-aendern.html#?path') in dQuery:
            sPathCat = dQuery.get('https://www.ebay-kleinanzeigen.de/p-kategorie-aendern.html#?path')
        elif ('https://www.ebay-kleinanzeigen.de/p-anzeige-aufgeben.html#?path') in dQuery:
            sPathCat = dQuery.get('https://www.ebay-kleinanzeigen.de/p-anzeige-aufgeben.html#?path')

        if sPathCat:
            for sCat in sPathCat[0].split('/'):
                log.debug('Category: %s' % (sCat,))
                driver.find_element_by_id('cat_' + sCat).click()
                fake_wait()
            driver.find_element_by_id('postad-step1-sbmt').submit()
            fake_wait(randint(1000, 2000))
        else:
            log.warning("Invalid category URL specified; skipping")
            return False    
    else:
        log.warning("No category specified; skipping")
        return False

    # Check if posting an ad is allowed / possible
    fRc = post_ad_is_allowed(driver, ad, fInteractive)
    if fRc is False:
        return fRc

    # Some categories needs this
    post_ad_mandatory_fields_set(driver, ad)

    # Fill form
    post_field_set_text(driver, ad, 'postad-title',       ad["title"])
    post_field_set_text(driver, ad, 'pstad-descrptn',     config['glob_ad_prefix'] + ad["desc"] + config['glob_ad_suffix'])
    post_field_set_text(driver, ad, 'pstad-price',        ad["price"])

    post_field_select  (driver, ad, 'priceType',          ad["price_type"]);

    post_field_set_text(driver, ad, 'pstad-zip',          config["glob_zip"])
    post_field_set_text(driver, ad, 'postad-phonenumber', config["glob_phone_number"])
    post_field_set_text(driver, ad, 'postad-contactname', config["glob_contact_name"])
    post_field_set_text(driver, ad, 'pstad-street',       config["glob_street"])

    # Upload images from photofiles
    if "photofiles" in ad:
        for path in ad["photofiles"]:
            post_upload_image(driver, ad, config["glob_photo_path"] + path)

    # Upload images from directories
    if ("photo_dir") in ad:
        post_upload_path(driver, ad, config["glob_photo_path"] + ad["photo_dir"])
    elif ("photodir") in ad:
        post_upload_path(driver, ad, config["glob_photo_path"] + ad["photodir"])

    fake_wait()

    submit_button = driver.find_element_by_id('pstad-frmprview')
    if submit_button:
        submit_button.click()

    fake_wait()

    fHasCaptcha = post_ad_has_captcha(driver, ad, fInteractive)
    if fHasCaptcha:
        if fInteractive:
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
            parsed_q = urlparse.parse_qs(urlparse.urlparse(driver.current_url).query)
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
        if config.get('headless', False) is True:
            log.info("Headless mode")
            ff_options.add_argument("--headless")
        ff_profile = webdriver.FirefoxProfile()
        ff_profile.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 5.1; rv:7.0.1) Gecko/20100101 Firefox/7.0.1")
        driver = webdriver.Firefox(firefox_profile=ff_profile, firefox_options=ff_options)
    else:
        cr_options = ChromeOptions()
        cr_options.add_argument("--no-sandbox")
        cr_options.add_argument("--disable-blink-features");
        cr_options.add_argument("--disable-blink-features=AutomationControlled")
        if config.get('headless', False) is True:
            log.info("Headless mode")
            cr_options.add_argument("--headless")
        cr_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.50 Safari/537.36")
        cr_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        cr_options.add_experimental_option('useAutomationExtension', False)

        driver = webdriver.Chrome(chrome_options=cr_options)

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
        aOpts, aArgs = getopt.gnu_getopt(sys.argv[1:], "ph", ["profile=", "help" ])
    except getopt.error, msg:
        print msg
        print "For help use --help"
        sys.exit(2)

    sProfile = ""

    for o, a in aOpts:
        if o in ("--profile"):
            sProfile = a

    if not sProfile:
        print "No profile specified"
        sys.exit(2)

    log.info('Script started')
    log.info("Using profile: %s" % sProfile)

    config = {}

    profile_read(sProfile, config)

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
                fR = login(driver, config, True)
                if fRc:
                    fake_wait(randint(12222, 17777))
                    fNeedsUpdate = False
                else:
                    log.info('Login failed')
                    break

            delete_ad(driver, ad)
            fake_wait(randint(12222, 17777))

            fPosted = post_ad(driver, ad, True)
            if not fPosted:
                break

            log.info("Waiting for handling next ad ...")
            fake_wait(randint(12222, 17777))

        profile_write(sProfile, config)

    log.info("Script done")
