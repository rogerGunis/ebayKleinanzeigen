#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=C0301,bad-whitespace,invalid-name
# pylint: disable=C0111

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
if os.name == 'posix':
    import termios
import time

from random import randint
import logging
from datetime import datetime
from urllib import parse
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


def signal_handler(sig, frame):
    _, _ = sig, frame
    print('Exiting script')
    sys.exit(0)

class Kleinanzeigen:
    def __init__(self):
        # Whether to run in interactive mode or not.
        self.fInteractive = True
        # Whether to run in headless mode or not.
        self.fHeadless    = False

        json.JSONEncoder.default = \
            lambda self, obj: \
                (obj.isoformat() if isinstance(obj, datetime) else None)

        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.INFO)

        self.log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        self.log_fh = logging.FileHandler('kleinanzeigen.self.log')
        self.log_fh.setLevel(logging.INFO)
        self.log_fh.setFormatter(self.log_formatter)

        self.log_stream = logging.StreamHandler()
        self.log_stream.setLevel(logging.INFO)
        self.log_stream.setFormatter(self.log_formatter)

        self.log.addHandler(self.log_stream)
        self.log.addHandler(self.log_fh)

    def profile_read(self, sProfile, oConfig):

        self.log.info("Loading profile '%s'", (sProfile,))

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

    def profile_write(self, sProfile, oConfig):

        self.log.info("Saving profile '%s'", sProfile)

        with open(sProfile, "w+", encoding='utf8') as fh_config:
            text = json.dumps(oConfig, sort_keys=True, indent=4, ensure_ascii=False)
            fh_config.write(text)

    def login_has_captcha(self, driver):
        fRc = False
        try:
            e = WebDriverWait(driver, 5).until(
                expected_conditions.presence_of_element_located((By.ID, "login-recaptcha"))
                )
            if e:
                fRc = True
        except TimeoutException:
            pass
        self.log.info("Login Captcha: %s", fRc)
        return fRc

    def login(self, driver, config):
        fRc = True
        self.log.info("Logging in ...")
        driver.set_page_load_timeout(90)
        try:
            driver.get('https://www.ebay-kleinanzeigen.de/m-einloggen.html?targetUrl=/')

            self.log.info('Waitng for login page ...')

            # Accept (click) GDPR banner
            WebDriverWait(driver, 180).until(
                expected_conditions.element_to_be_clickable((By.ID, 'gdpr-banner-accept'))).click()

            self.log.info('Sending login credentials ...')

            # Send e-mail
            WebDriverWait(driver, 180).until(
                expected_conditions.presence_of_element_located((By.ID, "login-email"))
            ).send_keys(config['glob_username'])
            self.fake_waitt()

            # Send password
            driver.find_element_by_id('login-password').send_keys(config['glob_password'])
            self.fake_waitt()

            # Check for captcha
            fHasCaptcha = self.login_has_captcha(driver)
            if fHasCaptcha:
                if self.fInteractive:
                    self.log.info("*** Manual login captcha input needed! ***")
                    self.log.info("Fill out captcha and submit, after that press Enter here to continue ...")
                    self.wait_key()
                else:
                    self.log.info("Login captcha input needed, but running in non-interactive mode! Skipping ...")
                    fRc = False
            else:
                driver.find_element_by_id('login-submit').click()

        except TimeoutException:
            self.log.info("Unable to login -- loading site took too long?")
            fRc = False

        except NoSuchElementException:
            self.log.info("Unable to login -- Login form element(s) not found")
            fRc = False

        return fRc

    def fake_waitt(self, msSleep=None):
        if msSleep is None:
            msSleep = randint(777, 3333)
        if msSleep < 100:
            msSleep = 100
        self.log.debug("Waiting %d ms ...", msSleep)
        time.sleep(msSleep / 1000)

    def delete_ad(self, driver, ad):

        self.log.info("Deleting ad '%s' ...", ad["title"])

        fRc = True

        while fRc:

            driver.get("https://www.ebay-kleinanzeigen.de/m-meine-anzeigen.html")
            self.fake_waitt()

            adIdElem = None

            if "id" in ad:
                self.log.info("Searching by ID (%s)", ad["id"])
                try:
                    adIdElem = driver.find_element_by_xpath("//a[@data-adid='%s']" % ad["id"])
                except NoSuchElementException:
                    self.log.warning("Not found by ID")

            if adIdElem is None:
                self.log.info("Searching by title (%s)", ad["title"])
                try:
                    adIdElem  = driver.find_element_by_xpath("//a[contains(text(), '%s')]/../../../../.." % ad["title"])
                    adId      = adIdElem.get_attribute("data-adid")
                    self.log.info("Ad ID is %s", adId)
                except NoSuchElementException:
                    self.log.warning("Not found by title")

            if adIdElem is not None:
                try:
                    btn_del = adIdElem.find_element_by_class_name("managead-listitem-action-delete")
                    btn_del.click()

                    self.fake_waitt()

                    try:
                        driver.find_element_by_id("modal-bulk-delete-ad-sbmt").click()
                    except:
                        driver.find_element_by_id("modal-bulk-mark-ad-sold-sbmt").click()

                    self.log.info("Ad deleted")

                    self.fake_waitt(randint(2000, 3000))
                    webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()

                except NoSuchElementException:
                    self.log.error("Delete button not found")
                    fRc = False
                    break
            else:
                self.log.info("Ad does not exist (anymore)")
                break

        if not fRc:
            self.log.error("Deleting ad failed")

        ad.pop("id", None)

        return fRc

    # From: https://stackoverflow.com/questions/983354/how-do-i-make-python-to-wait-for-a-pressed-key
    def wait_key(self):
        """ Wait for a key press on the console and return it. """
        result = None
        if os.name == 'nt':
            result = input("Press Enter to continue ...")
        else:
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

    def post_ad_has_captcha(self, driver, ad):

        _ = ad
        fRc  = False

        try:
            captcha_field = driver.find_element_by_xpath('//*[@id="postAd-recaptcha"]')
            if captcha_field:
                fRc = True
        except NoSuchElementException:
            pass

        self.log.info("Captcha: %s", fRc)

        return fRc

    def post_ad_is_allowed(self, driver, ad):

        _ = ad
        fRc  = True

        # Try checking for the monthly limit per account first.
        try:
            icon_insertionfees = driver.find_element_by_class_name('icon-insertionfees')
            if icon_insertionfees:
                self.log.info("*** Monthly limit of free ads per account reached! Skipping ... ***")
                fRc = False
        except NoSuchElementException:
            pass

        self.log.info("Ad posting allowed: %s", fRc)

        return fRc

    def post_ad_mandatory_combobox_select(self, driver, ad, sName, sValue):
        _ = ad
        for el in driver.find_elements_by_xpath('//*[@class="formgroup-label-mandatory"]'):
            self.log.debug("Detected mandatory field: '%s'", el.text)
            if sName in el.text:
                sForId = el.get_attribute("for")
                Select(driver.find_element_by_id(sForId)).select_by_visible_text(sValue)
                self.fake_waitt()
                return True
        return False

    def post_ad_mandatory_fields_set(self, driver, ad):
        for el in driver.find_elements_by_xpath('//*[@class="formgroup-label-mandatory"]'):
            try:
                sForId = el.get_attribute("for")
                if sForId is not None:
                    self.log.debug("Detected mandatory field (Name='%s', ID='%s')", el.text, sForId)
                    reMatch = re.search(r'.*\.(.*)_s.*', sForId, re.IGNORECASE)
                    if reMatch is not None:
                        sForIdRaw = reMatch.group(1)
                        fUseDefault = False
                        if "field_" + sForIdRaw in ad:
                            try:
                                Select(driver.find_element_by_id(sForId)).select_by_visible_text(ad["field_" + sForIdRaw])
                            except NoSuchElementException:
                                self.log.warning("Value for combo box '%s' invalid in config, setting to default (first entry)", sForIdRaw)
                                fUseDefault = True
                        else:
                            self.log.warning("No value for combo box '%s' defined, setting to default (first entry)", sForIdRaw)
                            fUseDefault = True
                        if fUseDefault:
                            s = Select(driver.find_element_by_id(sForId))
                            iOpt = 0
                            for o in s.options:
                                # Skip empty options (defaults?)
                                if not o.get_attribute("value"):
                                    break
                                iOpt += 1
                            s.select_by_value(s.options[iOpt].get_attribute("value"))
                        self.fake_waitt()
                    else:
                        sForIdRaw = sForId
                        if "field_" + sForIdRaw in ad:
                            sValue = ad["field_" + sForIdRaw]
                        else:
                            self.log.warning("No value for text field '%s' defined, setting to empty value", sForIdRaw)
                            sValue = 'Nicht angegeben'
                        try:
                            driver.find_element_by_id(sForId).send_keys(sValue)
                            self.fake_waitt()
                        except:
                            pass
            except NoSuchElementException:
                pass

    def post_field_set_text(self, driver, ad, field_id, sValue):
        _ = ad
        if sValue:
            e = driver.find_element_by_id(field_id)
            e.clear()
            lstLines = [x.strip('\\n') for x in sValue.split('\\n')]
            for sLine in lstLines:
                e.send_keys(sLine)
                if len(lstLines) > 1:
                    e.send_keys(Keys.RETURN)

            self.fake_waitt()

    def post_field_select(self, driver, ad, field_id, sValue):
        _ = ad
        driver.find_element_by_xpath("//input[@name='%s' and @value='%s']" % (field_id, sValue)).click()
        self.fake_waitt()

    def post_upload_image(self, driver, ad, file_path_abs):
        _ = ad
        try:
            fileup = driver.find_element_by_xpath("//input[@type='file']")
            uploaded_count = len(driver.find_elements_by_class_name("imagebox-thumbnail"))
            self.log.debug("Uploading image: %s", file_path_abs)
            fileup.send_keys(os.path.abspath(file_path_abs))
            total_upload_time = 0
            while uploaded_count == len(driver.find_elements_by_class_name("imagebox-thumbnail")) and \
                    total_upload_time < 30:
                self.fake_waitt(1000)
                total_upload_time += 1

            if uploaded_count == len(driver.find_elements_by_class_name("imagebox-thumbnail")):
                self.log.warning("Could not upload image: %s within %s seconds", file_path_abs, total_upload_time)
            else:
                self.log.debug("Uploaded file in %s seconds", total_upload_time)
        except NoSuchElementException:
            self.log.warning("Unable to find elements required for uploading images; skipping")

    def post_upload_path(self, driver, ad, path_abs):
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
            self.post_upload_image(driver, ad, path_abs + filename)

    def post_ad(self, driver, config, ad):

        self.log.info("Publishing ad '%s' ...", ad["title"])

        # Sanitize ad values if not set
        if ad["price_type"] not in ['FIXED', 'NEGOTIABLE', 'GIVE_AWAY']:
            ad["price_type"] = 'NEGOTIABLE'

        driver.get('https://www.ebay-kleinanzeigen.de/m-meine-anzeigen.html')

        # Click to post a new ad.
        try:
            driver.find_element_by_id('site-mainnav-postad-link').click()
            self.fake_waitt(randint(4000, 8000))
        except:
            self.log.error("Post ad button not found!")
            return False

        # Find out where we are; might be some A/B testing the site does ...
        try:
            driver.find_element_by_id('pstad-lnk-chngeCtgry').click()
        except:
            pass

        # Whether to skip this ad or not.
        # Don't handle this as a fatal error (fRc = False), to continue posting the other ads.
        fSkip = False

        # Change category
        dQuery = parse.parse_qs(ad["caturl"])
        if dQuery:
            if 'https://www.ebay-kleinanzeigen.de/p-kategorie-aendern.html#?path' in dQuery:
                sPathCat = dQuery.get('https://www.ebay-kleinanzeigen.de/p-kategorie-aendern.html#?path')
            elif 'https://www.ebay-kleinanzeigen.de/p-anzeige-aufgeben.html#?path' in dQuery:
                sPathCat = dQuery.get('https://www.ebay-kleinanzeigen.de/p-anzeige-aufgeben.html#?path')

            if sPathCat:
                for sCat in sPathCat[0].split('/'):
                    self.log.debug('Category: %s', sCat)
                    try:
                        driver.find_element_by_id('cat_' + sCat).click()
                        self.fake_waitt()
                    except:
                        self.log.warning("Category not existing (anymore); skipping")
                        fSkip = True
                try:
                    driver.find_element_by_id('postad-step1-sbmt').submit()
                    self.fake_waitt(randint(1000, 2000))
                except:
                    self.log.error("Category submit button not found, skipping")
                    return False # This is fatal though.
            else:
                self.log.warning("Invalid category URL specified; skipping")
                fSkip = True
        else:
            self.log.warning("No category specified; skipping")
            fSkip = True

        # Skipping an ad is not fatal to other ads.
        if fSkip:
            return True

        # Check if posting an ad is allowed / possible
        if not self.post_ad_is_allowed(driver, ad):
            return False

        # Some categories needs this
        self.post_ad_mandatory_fields_set(driver, ad)

        # Fill form
        self.post_field_set_text(driver, ad, 'postad-title',       ad["title"])
        self.post_field_set_text(driver, ad, 'pstad-descrptn',     config['glob_ad_prefix'] + ad["desc"] + config['glob_ad_suffix'])
        self.post_field_set_text(driver, ad, 'pstad-price',        ad["price"])

        self.post_field_select  (driver, ad, 'priceType',          ad["price_type"])

        self.post_field_set_text(driver, ad, 'pstad-zip',          config["glob_zip"])
        self.post_field_set_text(driver, ad, 'postad-phonenumber', config["glob_phone_number"])
        self.post_field_set_text(driver, ad, 'postad-contactname', config["glob_contact_name"])
        self.post_field_set_text(driver, ad, 'pstad-street',       config["glob_street"])

        sPhotoPathRoot = config["glob_photo_path"]
        if sPhotoPathRoot:
            # Upload images from photofiles
            if "photofiles" in ad:
                for sPath in ad["photofiles"]:
                    self.post_upload_image(driver, ad, os.path.join(sPhotoPathRoot, sPath))

            # Upload images from directories
            sPhotoPathDir = ''
            if 'photo_dir' in ad:
                sPhotoPathDir = ad["photo_dir"]
            elif 'photodir' in ad:
                sPhotoPathDir = ad["photodir"]

            if sPhotoPathDir:
                self.post_upload_path(driver, ad, os.path.join(sPhotoPathRoot, sPhotoPathDir))
        else:
            self.log.warning("No global photo path specified, skipping photo uploads")

        self.fake_waitt()

        #
        # Submit ad
        #
        fSubmitted = False
        self.log.info("Submitting ad ...")
        try:
            driver.find_element_by_id('pstad-frmprview').click()
            fSubmitted = True
        except:
            pass

        if not fSubmitted:
            try:
                driver.find_element_by_id('pstad-submit').click()
                fSubmitted = True
            except:
                pass

        if not fSubmitted:
            self.log.error("Submit button not found!")
            return False

        self.fake_waitt()

        fHasCaptcha = self.post_ad_has_captcha(driver, ad)
        if fHasCaptcha:
            if self.fInteractive:
                self.log.warning("*** Manual captcha input needed! ***")
                self.log.warning("Fill out captcha and submit, after that press Enter here to continue ...")
                self.wait_key()
            else:
                self.log.warning("Captcha input needed, but running in non-interactive mode! Skipping ...")
                return False

        # Somes there is a preview button shown. Handle this if necessary.
        try:
            driver.find_element_by_id('prview-btn-post').click()
        except NoSuchElementException:
            self.log.debug("Preview button not found / available, continuing ...")

        try:
            self.log.info("Posted as: %s", driver.current_url)
            parsed_q = parse.parse_qs(parse.urlparse(driver.current_url).query)
            adId = parsed_q.get('adId', None)[0]
            self.log.info("Ad ID is: %s", adId)
            if "id" not in ad:
                self.log.info("Set ID: %s", adId)
                ad["date_published"] = datetime.utcnow()

            if adId is not None:
                ad["id"] = adId
        except:
            self.log.warning("Unable to parse posted ad ID")

            # Make sure to update the updated timestamp, even if we weren't able
            # to find the (new) ad ID.
            ad["date_updated"] = datetime.utcnow()

        return True

    def session_create(self, config):

        self.log.info("Creating session")

        # For now use the Chrome driver, as Firefox doesn't work (empy page)
        fUseFirefox = False

        if fUseFirefox:
            ff_options = FirefoxOptions()
            if self.fInteractive:
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
            if self.fHeadless:
                cr_options.add_argument("--headless")
                cr_options.add_argument("--disable-extensions")
                cr_options.add_argument("--disable-gpu")
                cr_options.add_argument("--disable-dev-shm-usage")
                cr_options.add_argument("--start-maximized")
            cr_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.50 Safari/537.36")
            cr_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            cr_options.add_experimental_option('useAutomationExtension', False)

            driver = webdriver.Chrome(options=cr_options)

        self.log.info("New session is: %s %s", driver.session_id, driver.command_executor._url)

        config['session_id'] = driver.session_id
        config['session_url'] = driver.command_executor._url

        return driver

    def session_attach(self, config):

        self.log.info("Trying to attach to session %s %s", config['session_id'], config['session_url'])

        # Save the original function, so we can revert our patch
        org_command_execute = webdriver.Remote.execute

        def new_command_execute(self, command, params=None):
            if command == "newSession":
                # Mock the response
                return {'success': 0, 'value': None, 'sessionId': config['session_id']}
            return org_command_execute(self, command, params)

        # Patch the function before creating the driver object
        webdriver.Remote.execute = new_command_execute

        driver = webdriver.Remote(command_executor=config['session_url'], desired_capabilities={})
        driver.session_id = config['session_id']

        try:
            self.log.info("Current URL is: %s", driver.current_url)
        except:
            self.log.info("Session does not exist anymore")
            config['session_id'] = None
            config['session_url'] = None
            driver = None

            # Make sure to put the original executor back in charge.
            webdriver.Remote.execute = org_command_execute

        return driver

    def main(self):
        signal.signal(signal.SIGINT, signal_handler)

        try:
            aOpts, _ = getopt.gnu_getopt(sys.argv[1:], "ph", [ "profile=", "headless", "non-interactive", "help" ])
        except getopt.GetoptError as msg:
            print(msg)
            print('For help use --help')
            sys.exit(2)

        sCurProfile = ""

        for o, a in aOpts:
            if o in '--profile':
                sCurProfile = a
            elif o in '--headless':
                self.fHeadless = True
            elif o in '--non-interactive':
                self.fInteractive = False
            elif o in '--debug':
                self.log_stream.setLevel(logging.DEBUG)
                self.log_fh.setLevel(logging.DEBUG)
                self.log.setLevel(logging.DEBUG)

        if not sCurProfile:
            print('No profile specified')
            sys.exit(2)

        self.log.info('Script started')
        self.log.info("Using profile: %s", sCurProfile)

        if self.fHeadless:
            self.log.info("Running in headless mode")
        if not self.fInteractive:
            self.log.info("Running in non-interactive mode")

        oCurConfig = {}

        if not self.profile_read(sCurProfile, oCurConfig):
            self.log.error("Profile file not found / accessible!")
            sys.exit(1)

        fRc          = True
        fNeedsLogin  = True
        fForceUpdate = False

        dtNow = datetime.utcnow()

        oDriver = None

        if oCurConfig.get('session_id') is not None:
            oDriver = self.session_attach(oCurConfig)

        for oCurAd in oCurConfig["ads"]:

            fNeedsUpdate = False

            self.log.info("Handling '%s'", oCurAd["title"])

            if "date_updated" in oCurAd:
                dtLastUpdated = dateutil.parser.parse(oCurAd["date_updated"])
            else:
                dtLastUpdated = dtNow
            dtDiff            = dtNow - dtLastUpdated

            if  "enabled" in oCurAd \
            and oCurAd["enabled"] == "1":
                if "date_published" in oCurAd:
                    self.log.info("Already published (%d days ago)", dtDiff.days)
                    glob_update_after_days = int(oCurConfig.get('glob_update_after_days'))
                    if dtDiff.days > glob_update_after_days:
                        self.log.info("Custom global update interval (%d days) set and needs to be updated", \
                                glob_update_after_days)
                        fNeedsUpdate = True

                    ad_update_after_days = 0
                    if "update_after_days" in oCurAd:
                        ad_update_after_days = int(oCurAd["update_after_days"])

                    if  ad_update_after_days != 0 \
                    and dtDiff.days > ad_update_after_days:
                        self.log.info("Ad has a specific update interval (%d days) and needs to be updated", \
                                ad_update_after_days)
                        fNeedsUpdate = True
                else:
                    self.log.info("Not published yet")
                    fNeedsUpdate = True
            else:
                self.log.info("Disabled, skipping")

            if fNeedsUpdate \
            or fForceUpdate:

                if oDriver is None \
                and fNeedsLogin:
                    oDriver = self.session_create(oCurConfig)
                    self.profile_write(sCurProfile, oCurConfig)
                    fRc = self.login(oDriver, oCurConfig)
                    if fRc:
                        self.fake_waitt(randint(12222, 17777))
                        fNeedsUpdate = False
                    else:
                        self.log.info('Login failed')
                        break

                self.delete_ad(oDriver, oCurAd)
                self.fake_waitt(randint(12222, 17777))

                fPosted = self.post_ad(oDriver, oCurConfig, oCurAd)
                if not fPosted:
                    break

                self.log.info("Waiting for handling next ad ...")
                self.fake_waitt(randint(12222, 17777))

        # Make sure to update the profile's data before terminating.
        self.profile_write(sCurProfile, oCurConfig)

        self.log.info("Script done")


if __name__ == '__main__':
    Kleinanzeigen().main()
