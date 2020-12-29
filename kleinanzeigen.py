#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=C0301,bad-whitespace,invalid-name
# pylint: disable=C0111
# pylint: disable=too-many-lines

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

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.utils import formatdate
from email import encoders

from random import randint
import logging
from datetime import datetime, timedelta
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

# Found on: https://stackoverflow.com/questions/812477/how-many-times-was-logging-error-called
class CallCounted:
    """Decorator to determine number of calls for a method"""
    def __init__(self,method):
        self.method=method
        self.counter=0

    def __call__(self,*args,**kwargs):
        self.counter+=1
        return self.method(*args,**kwargs)

class Kleinanzeigen:
    def __init__(self):
        # Whether debugging mode is active or not.
        self.fDebug       = False
        # Whether to run in interactive mode or not.
        self.fInteractive = True
        # Whether to run in headless mode or not.
        self.fHeadless    = False
        # Output directory, if needed. Set to /tmp/ by default.
        self.sPathOut     = '/tmp/'
        # Whether testing sending E-Mails should be performed or not.
        self.fEmailTest   = False
        # How many E-Mails have been sent already.
        self.cEmailSent   = 0
        # Whether logged into user account or not.
        self.fLoggedIn    = False
        # Absolute file path for log file, if any.
        self.sLogFileAbs  = None
        # Array of absolute path names of taken screenshots, if any.
        self.aScreenshots = []

        json.JSONEncoder.default = \
            lambda self, obj: \
                (obj.isoformat() if isinstance(obj, datetime) else None)

        self.log = logging.getLogger(__name__)
        self.log.error = CallCounted(logging.error)
        self.log.setLevel(logging.INFO)

        self.log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        self.log_stream = logging.StreamHandler()
        self.log_stream.setLevel(logging.INFO)
        self.log_stream.setFormatter(self.log_formatter)

        # Logging to file gets initialized in init_logfile().
        self.log_fh = None

        self.log.addHandler(self.log_stream)

    def cleanup(self):
        """
        Does cleaning up work by removing intermediate files.
        """
        if self.fInteractive \
        or self.fDebug:
            return

        self.log.info("Cleaning up ...")
        for file_screenshot in self.aScreenshots:
            self.log.debug("Removing screenshot '%s'", file_screenshot)
            try:
                os.remove(file_screenshot)
            except:
                pass
        if self.sLogFileAbs:
            self.log.debug("Removing logfile '%s'", self.sLogFileAbs)
            try:
                if self.log_fh:
                    self.log.removeHandler(self.log_fh)
                os.remove(self.sLogFileAbs)
            except:
                pass

    def reset(self):
        """
        Resets internal variables for handling the next ad.
        """
        self.aScreenshots = []

    def init_logfile(self, path_abs):
        """
        Initializes the logfile.
        """
        sFileName = "kleinanzeigen_" + time.strftime("%Y%m%d-%H%M%S") + ".log"

        self.sLogFileAbs = os.path.join(path_abs, sFileName)
        self.log.debug("Log file is '%s'", self.sLogFileAbs)

        self.log_fh = logging.FileHandler(self.sLogFileAbs)
        if self.fDebug:
            self.log_fh.setLevel(logging.DEBUG)
        else:
            self.log_fh.setLevel(logging.INFO)
        self.log_fh.setFormatter(self.log_formatter)

        self.log.addHandler(self.log_fh)

    def send_email(self, email_server_addr, email_server_port, \
                   email_user, email_pw, \
                   to_addr, from_addr, sub, body, files = None):
        """
        Sends an E-Mail.
        """
        msg = MIMEMultipart()
        msg['From'] = from_addr
        msg['To'] = to_addr
        msg['Subject'] = sub
        msg['Date'] = formatdate(localtime = True)
        msg.attach(MIMEText(body, 'plain'))

        self.log.info("Sending e-mail with SMTP %s:%d", email_server_addr, email_server_port)

        if files is not None:
            for cur_file in files:
                try:
                    self.log.info("Attaching file '%s'", cur_file)
                    part = MIMEBase('application', "octet-stream")
                    fh = open(cur_file, "rb")
                    part.set_payload(fh.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(cur_file))
                    msg.attach(part)
                    fh.close()
                except:
                    self.log.error("Attaching file '%s' failed", cur_file)

        server = smtplib.SMTP(email_server_addr, email_server_port)
        server.ehlo_or_helo_if_needed()
        server.starttls()
        server.login(email_user, email_pw)
        server.sendmail(from_addr, to_addr, msg.as_string())
        server.quit()

        return True

    def send_email_profile(self, config, sub, msg, files = None):
        """
        Sends an E-Mail with the provided configuration.
        """
        if config['glob_email_enabled'] == "1":
            self.log.info("Sending mail with subject '%s' ...", sub)
            return self.send_email(config['glob_email_server_addr'], int(config['glob_email_server_port']), \
                                   config['glob_email_user'], config['glob_email_pw'], \
                                   config['glob_email_to_addr'], config['glob_email_from_addr'], sub, msg, files)
        return False

    def send_email_error(self, config, ad = None):
        """
        Sends an E-Mail
        """
        if self.cEmailSent > 0:
            return

        if ad:
            sub = "eBay Kleinanzeigen: %d error(s) handling ad '%s' (profile '%s')" \
                  % (self.log.error.counter, ad['title'], config['glob_username'])
        else:
            sub = "eBay Kleinanzeigen: %d error(s) handling profile '%s'" \
                  % (self.log.error.counter, config['glob_username'])

        files = []

        if self.sLogFileAbs:
            self.log.debug("Appending log '%s'", self.sLogFileAbs)
            files.append(self.sLogFileAbs)

        for file_screenshot in self.aScreenshots:
            self.log.debug("Appending screenshot '%s'", file_screenshot)
            files.append(file_screenshot)

        if self.send_email_profile(config, sub, "See attached log file / screenshots.", files):
            self.cEmailSent += 1

    def profile_read(self, profile, config):
        """
        Reads a profile from a file.
        """
        self.log.debug("Loading profile '%s'", profile)

        if not os.path.isfile(profile):
            return False

        with open(profile, encoding="utf-8") as file:
            config.update(json.load(file))

        # Sanitize.
        if config['glob_phone_number'] is None:
            config['glob_phone_number'] = ''

        if config['glob_street'] is None:
            config['glob_street'] = ''

        return True

    def profile_write(self, profile, config):
        """
        Saves (serializes) a profile to a file.
        """
        self.log.info("Saving profile '%s'", profile)

        with open(profile, "w+", encoding='utf8') as fh_config:
            text = json.dumps(config, sort_keys=True, indent=4, ensure_ascii=False)
            fh_config.write(text)

    def profile_can_run(self, config):
        """
        Returns whether the profile is able to run or not.
        """
        if config.get('date_next_run') is not None:
            date_now = datetime.utcnow()
            date_nextrun = dateutil.parser.parse(config['date_next_run'])
            if date_now < date_nextrun:
                self.log.info("Next run for this profile scheduled for %d/%d/%d, skipping", \
                                date_nextrun.year, date_nextrun.month, date_nextrun.day)
                return False
        return True

    def login_has_captcha(self, driver):
        """
        Returns if the login page has a Captcha or not.
        """
        rc = False
        try:
            e = WebDriverWait(driver, 5).until(
                expected_conditions.presence_of_element_located((By.ID, "login-recaptcha"))
                )
            if e:
                rc = True
        except TimeoutException:
            pass
        self.log.debug("Login Captcha: %s", rc)
        return rc

    def login(self, driver, config):
        """
        Logs into Kleinanzeigen.
        """
        rc = True
        self.log.info("Logging in ...")
        driver.set_page_load_timeout(90)
        try:
            driver.get('https://www.ebay-kleinanzeigen.de/m-einloggen.html?targetUrl=/')

            self.log.debug('Waitng for login page ...')

            # Accept (click) GDPR banner
            WebDriverWait(driver, 180).until(
                expected_conditions.element_to_be_clickable((By.ID, 'gdpr-banner-accept'))).click()

            self.log.debug('Sending login credentials ...')

            # Send e-mail
            WebDriverWait(driver, 180).until(
                expected_conditions.presence_of_element_located((By.ID, "login-email"))
            ).send_keys(config['glob_username'])
            self.fake_wait()

            # Send password
            driver.find_element_by_id('login-password').send_keys(config['glob_password'])
            self.fake_wait()

            # Check for captcha
            has_captcha = self.login_has_captcha(driver)
            if has_captcha:
                if self.fInteractive:
                    self.log.warning("*** Manual login captcha input needed! ***")
                    self.log.warning("Fill out captcha and submit, after that press Enter here to continue ...")
                    self.wait_key()
                else:
                    self.log.warning("Login captcha input needed, but running in non-interactive mode! Skipping ...")
                    rc = False
            else:
                driver.find_element_by_id('login-submit').click()

        except TimeoutException:
            self.log.error("Unable to login -- Loading site took too long?")
            rc = False

        except NoSuchElementException:
            self.log.error("Unable to login -- Login form element(s) not found")
            rc = False

        if rc:
            self.log.info("Login successful")
        else:
            self.add_screenshot(driver)
            self.log.error("Login failed")

        self.fLoggedIn = rc

        return rc

    def logout(self, driver):
        """ Logs out from the current session. """
        if driver is None:
            return
        if not self.fLoggedIn:
            return
        self.log.info("Logging out ...")
        driver.get('https://www.ebay-kleinanzeigen.de/m-abmelden.html')
        self.fLoggedIn = False

    def relogin(self, driver, config):
        """
        Performs a re-login.
        """
        self.log.info("Performing re-login ...")
        self.logout(driver)
        self.fake_wait(7777)
        return self.login(driver, config)

    def fake_wait(self, ms_sleep=None):
        """
        Waits for a certain amount of time.
        """
        if ms_sleep is None:
            ms_sleep = randint(777, 3333)
        if ms_sleep < 100:
            ms_sleep = 100
        self.log.debug("Waiting %d ms ...", ms_sleep)
        time.sleep(ms_sleep / 1000)

    def make_screenshot(self, driver, path_abs):
        """
        Makes a screenshot of the current page.
        Returns the absolute path to the screenshot file on success.
        """
        file_name = 'kleinanzeigen_' + time.strftime("%Y%m%d-%H%M%S") + ".png"
        file_path = os.path.join(path_abs, file_name)

        self.log.info("Saving screenshot of %s to '%s'", driver.current_url, file_path)

        # Taken from: https://pythonbasics.org/selenium-screenshot/
        S = lambda X: driver.execute_script('return document.body.parentNode.scroll'+X)
        driver.set_window_size(S('Width'),S('Height')) # May need manual adjustment
        driver.find_element_by_tag_name('body').screenshot(file_path)

        return file_path

    def add_screenshot(self, driver):
        """
        Makes a screenshot and adds it to the list of screenshots
        for this session.
        """
        file_screenshot = self.make_screenshot(driver, self.sPathOut)
        self.aScreenshots.append(file_screenshot)

    def delete_ad(self, driver, ad):
        """
        Deletes an ad.
        """
        self.log.info("Deleting ad '%s' ...", ad["title"])

        rc = True

        while rc:

            driver.get("https://www.ebay-kleinanzeigen.de/m-meine-anzeigen.html")
            self.fake_wait()

            ad_id_elem = None

            if "id" in ad:
                self.log.info("Searching by ID (%s)", ad["id"])
                try:
                    ad_id_elem = driver.find_element_by_xpath("//a[@data-adid='%s']" % ad["id"])
                except NoSuchElementException:
                    self.log.debug("Not found by ID")

            if ad_id_elem is None:
                self.log.info("Searching by title (%s)", ad["title"])
                try:
                    ad_id_elem  = driver.find_element_by_xpath("//a[contains(text(), '%s')]/../../../../.." % ad["title"])
                    adId      = ad_id_elem.get_attribute("data-adid")
                    self.log.info("Ad ID is %s", adId)
                except NoSuchElementException:
                    self.log.debug("Not found by title")

            if ad_id_elem is not None:
                try:
                    btn_del = ad_id_elem.find_element_by_class_name("managead-listitem-action-delete")
                    btn_del.click()

                    self.fake_wait()

                    try:
                        driver.find_element_by_id("modal-bulk-delete-ad-sbmt").click()
                    except:
                        driver.find_element_by_id("modal-bulk-mark-ad-sold-sbmt").click()

                    self.log.info("Ad deleted")

                    self.fake_wait(randint(2000, 3000))
                    webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()

                except NoSuchElementException:
                    self.log.error("Delete button not found")
                    rc = False
                    break
            else:
                self.log.info("Ad does not exist (anymore)")
                break

        if not rc:
            self.log.error("Deleting ad failed")

        ad.pop("id", None)

        return rc

    # From: https://stackoverflow.com/questions/983354/how-do-i-make-python-to-wait-for-a-pressed-key
    def wait_key(self):
        """
        Wait for a key press on the console and return it.
        """
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
        """
        Checks and returns if posting an ad needs to handle a Captcha first.
        """
        _   = ad
        rc  = False

        try:
            captcha_field = driver.find_element_by_xpath('//*[@id="postAd-recaptcha"]')
            if captcha_field:
                rc = True
        except NoSuchElementException:
            pass

        self.log.info("Captcha: %s", rc)

        return rc

    def post_ad_is_allowed(self, driver):
        """
        Checks and returns if posting an ad currently is allowed.
        """
        rc  = True

        # Try checking for the monthly limit per account first.
        try:
            icon_insertionfees = driver.find_element_by_class_name('icon-insertionfees')
            if icon_insertionfees:
                self.log.warning("Monthly limit of free ads per account reached! Skipping ...")
                rc = False
        except NoSuchElementException:
            pass

        self.log.debug("Ad posting allowed: %s", rc)

        return rc

    def post_ad_mandatory_combobox_select(self, driver, ad, name, value):
        """
        Selects a value from a specific combo box.
        """
        _ = ad
        for el in driver.find_elements_by_xpath('//*[@class="formgroup-label-mandatory"]'):
            self.log.debug("Detected mandatory field: '%s'", el.text)
            if name in el.text:
                for_id = el.get_attribute("for")
                Select(driver.find_element_by_id(for_id)).select_by_visible_text(value)
                self.fake_wait()
                return True
        return False

    def post_ad_mandatory_fields_set(self, driver, ad):
        """
        Tries to detect and (pre-)select all mandatory fields of an ad.
        This is necessary in order to getting the ad posted.
        """
        for el in driver.find_elements_by_xpath('//*[@class="formgroup-label-mandatory"]'):
            try:
                for_id = el.get_attribute("for")
                if for_id is not None:
                    self.log.debug("Detected mandatory field (Name='%s', ID='%s')", el.text, for_id)
                    re_match = re.search(r'.*\.(.*)_s.*', for_id, re.IGNORECASE)
                    if re_match is not None:
                        for_id_raw = re_match.group(1)
                        use_default = False
                        if "field_" + for_id_raw in ad:
                            try:
                                Select(driver.find_element_by_id(for_id)).select_by_visible_text(ad["field_" + for_id_raw])
                            except NoSuchElementException:
                                self.log.warning("Value for combo box '%s' invalid in config, setting to default (first entry)", for_id_raw)
                                use_default = True
                        else:
                            self.log.warning("No value for combo box '%s' defined, setting to default (first entry)", for_id_raw)
                            use_default = True
                        if use_default:
                            s = Select(driver.find_element_by_id(for_id))
                            idx_opt = 0
                            value = ""
                            for o in s.options:
                                value = o.get_attribute("value")
                                # Skip empty options (defaults?)
                                if not value:
                                    continue
                                self.log.debug("Value at index %d: %s", idx_opt, value)
                                if value == u"Bitte wählen":
                                    continue
                                idx_opt += 1
                            self.log.info("Setting combo box '%s' to '%s'", for_id_raw, value)
                            s.select_by_value(value)
                        self.fake_wait()
                    else:
                        for_id_raw = for_id
                        if "field_" + for_id_raw in ad:
                            value = ad["field_" + for_id_raw]
                        else:
                            self.log.warning("No value for text field '%s' defined, setting to empty value", for_id_raw)
                            value = 'Nicht angegeben'
                        try:
                            driver.find_element_by_id(for_id).send_keys(value)
                            self.fake_wait()
                        except:
                            pass
            except NoSuchElementException:
                pass

    def post_field_set_text(self, driver, ad, field_id, value):
        """
        Sets text of specific text field.
        """
        _ = ad
        if value:
            e = driver.find_element_by_id(field_id)
            e.clear()
            lstLines = [x.strip('\\n') for x in value.split('\\n')]
            for sLine in lstLines:
                e.send_keys(sLine)
                if len(lstLines) > 1:
                    e.send_keys(Keys.RETURN)

            self.fake_wait()

    def post_field_select(self, driver, ad, field_id, value):
        """
        Selects (sets) a specific ad field.
        """
        _ = ad
        driver.find_element_by_xpath("//input[@name='%s' and @value='%s']" % (field_id, value)).click()
        self.fake_wait()

    def post_upload_image(self, driver, ad, file_path_abs):
        """
        Uploads a single image (picture) of an ad.
        """
        _ = ad
        try:
            fileup = driver.find_element_by_xpath("//input[@type='file']")
            uploaded_count = len(driver.find_elements_by_class_name("imagebox-thumbnail"))
            self.log.info("Uploading image: %s", file_path_abs)
            fileup.send_keys(os.path.abspath(file_path_abs))
            total_upload_time = 0
            while uploaded_count == len(driver.find_elements_by_class_name("imagebox-thumbnail")) and \
                    total_upload_time < 30:
                self.fake_wait(1000)
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
        self.log.info("Uploading images from folder '%s' ...", path_abs)
        files.sort(reverse=False)
        for filename in files:
            if not filename.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
                continue
            self.post_upload_image(driver, ad, path_abs + filename)

    def post_submit(self, driver, config, ad):
        """
        Submits a (pre-filled) ad
        """
        _ = config

        self.log.debug("Current URL before posting is: %s", driver.current_url)

        #
        # Find the (right) submit button.
        # Start with the most obvious one.
        #
        submit_btn_found = False
        self.log.info("Submitting ad ...")
        try:
            driver.find_element_by_id('pstad-submit').click()
            submit_btn_found = True
        except:
            self.log.debug("pstad-submit not found")

        if not submit_btn_found:
            try:
                driver.find_element_by_id('pstad-frmprview').click()
                submit_btn_found = True
            except:
                self.log.debug("pstad-frmprview not found")

        if not submit_btn_found:
            try:
                driver.find_element_by_id('prview-btn-post').click()
                submit_btn_found = True
            except:
                self.log.debug("prview-btn-post not found")

        if not submit_btn_found:
            self.log.error("Submit button not found!")
            return False

        self.fake_wait()

        #
        # Check if there is a Captcha we need to handle.
        #
        has_captcha = self.post_ad_has_captcha(driver, ad)
        if has_captcha:
            if self.fInteractive:
                self.log.warning("*** Manual captcha input needed! ***")
                self.log.warning("Fill out captcha and submit, after that press Enter here to continue ...")
                self.wait_key()
            else:
                self.log.warning("Captcha input needed, but running in non-interactive mode! Skipping ...")
                return False

        self.log.debug("Current URL after posting is: %s", driver.current_url)

        if "#anker" in driver.current_url:
            self.log.error("Site reported an error while posting. Might be due to missing (mandatory) information.")
            return False

        #
        # Get ad ID from URL.
        #
        try:
            parsed_q = parse.parse_qs(parse.urlparse(driver.current_url).query)
            adId = parsed_q.get('adId', None)[0]
            self.log.info("Ad ID is: %s", adId)
            if "id" not in ad:
                self.log.info("Set ID: %s", adId)
                ad["date_published"] = str(datetime.utcnow())

            if adId is not None:
                ad["id"] = adId
        except:
            self.log.warning("Unable to parse posted ad ID")

        # Make sure to update the updated timestamp, even if we weren't able
        # to find the (new) ad ID.
        ad["date_updated"] = str(datetime.utcnow())

        self.log.info("Ad successfully submitted")
        return True

    def post_ad_sanitize(self, ad):
        """
        Sanitizes ad config values if necessary.
        """

        if ad["price_type"] not in ['FIXED', 'NEGOTIABLE', 'GIVE_AWAY']:
            ad["price_type"] = 'NEGOTIABLE'

        date_now = datetime.utcnow()
        if "date_published" in ad:
            date_pub = dateutil.parser.parse(ad["date_published"])
            if date_pub > date_now:
                date_pub = date_now
            ad["date_published"] = str(date_pub)
        if "date_updated" in ad:
            date_updated = dateutil.parser.parse(ad["date_updated"])
            if date_updated > date_now:
                date_updated = date_now
            if date_pub is None:
                date_pub = date_updated
            if date_updated > date_pub:
                date_updated = date_pub
            ad["date_updated"] = str(date_updated)

    def post_ad(self, driver, config, ad):
        """
        Main function to post an ad to Kleinanzeigen.
        """
        self.log.info("Publishing ad '%s' ...", ad["title"])

        driver.get('https://www.ebay-kleinanzeigen.de/m-meine-anzeigen.html')

        # Click to post a new ad.
        try:
            driver.find_element_by_id('site-mainnav-postad-link').click()
            self.fake_wait(randint(4000, 8000))
        except:
            self.log.error("Post ad button not found!")
            return False

        # Find out where we are; might be some A/B testing the site does ...
        try:
            driver.find_element_by_id('pstad-lnk-chngeCtgry').click()
        except:
            pass

        # Whether to skip this ad or not.
        # Don't handle this as a fatal error, to continue posting the other ads.
        skip = False

        # Change category
        cat_url = parse.parse_qs(ad["caturl"])
        if cat_url:
            if 'https://www.ebay-kleinanzeigen.de/p-kategorie-aendern.html#?path' in cat_url:
                path_cat = cat_url.get('https://www.ebay-kleinanzeigen.de/p-kategorie-aendern.html#?path')
            elif 'https://www.ebay-kleinanzeigen.de/p-anzeige-aufgeben.html#?path' in cat_url:
                path_cat = cat_url.get('https://www.ebay-kleinanzeigen.de/p-anzeige-aufgeben.html#?path')

            if path_cat:
                for cur_cat in path_cat[0].split('/'):
                    self.log.debug('Category: %s', cur_cat)
                    try:
                        driver.find_element_by_id('cat_' + cur_cat).click()
                        self.fake_wait()
                    except:
                        self.log.error("Category not existing (anymore); skipping")
                        skip = True
                try:
                    driver.find_element_by_id('postad-step1-sbmt').submit()
                    self.fake_wait(randint(1000, 2000))
                except:
                    self.log.error("Category submit button not found")
                    return False # This is fatal though.
            else:
                self.log.error("Invalid category URL specified; skipping")
                skip = True
        else:
            self.log.error("No category URL specified for this ad; skipping")
            skip = True

        # Skipping an ad is not fatal to other ads.
        if skip:
            self.log.error("Skipping ad due to configuration / page errors before")
            return True

        # Check if posting an ad is allowed / possible.
        if not self.post_ad_is_allowed(driver):
            # Try again in 2 days (48h).
            config['date_next_run'] = str(datetime.now() + timedelta(hours=48))
            return True # Skipping this profile is not a fatal error, so return True here.

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

        path_photo_root = config["glob_photo_path"]
        if path_photo_root:
            # Upload images from photofiles
            if "photofiles" in ad:
                for cur_photo_path in ad["photofiles"]:
                    self.post_upload_image(driver, ad, os.path.join(path_photo_root, cur_photo_path))

            # Upload images from directories
            path_photo_dir = ''
            if 'photo_dir' in ad:
                path_photo_dir = ad["photo_dir"]
            elif 'photodir' in ad:
                path_photo_dir = ad["photodir"]

            if path_photo_dir:
                self.post_upload_path(driver, ad, os.path.join(path_photo_root, path_photo_dir))
        else:
            self.log.warning("No global photo path specified, skipping photo uploads")

        self.fake_wait()

        if not self.post_submit(driver, config, ad):
            return False

        return True

    def handle_ads(self, profile_file, config):
        """
        Main function to handle the ads of a profile.
        """
        driver = None

        rc = True

        date_now = datetime.utcnow()

        needs_login = True

        for cur_ad in config["ads"]:

            needs_update = False

            self.log.info("Handling '%s'", cur_ad["title"])

            self.post_ad_sanitize(cur_ad)

            if "date_updated" in cur_ad:
                date_lastupdated = cur_ad["date_updated"]
            else:
                date_lastupdated = date_now
            date_diff            = date_now - date_lastupdated

            if  "enabled" in cur_ad \
            and cur_ad["enabled"] == "1":
                if "date_published" in cur_ad:
                    self.log.info("Already published (%d days ago)", date_diff.days)
                    glob_update_after_days = int(config.get('glob_update_after_days'))
                    if date_diff.days > glob_update_after_days:
                        self.log.info("Custom global update interval (%d days) set and needs to be updated", \
                                glob_update_after_days)
                        needs_update = True

                    ad_update_after_days = 0
                    if "update_after_days" in cur_ad:
                        ad_update_after_days = int(cur_ad["update_after_days"])

                    if  ad_update_after_days != 0 \
                    and date_diff.days > ad_update_after_days:
                        self.log.info("Ad has a specific update interval (%d days) and needs to be updated", \
                                ad_update_after_days)
                        needs_update = True
                else:
                    self.log.info("Not published yet")
                    needs_update = True
            else:
                self.log.info("Disabled, skipping")

            if needs_update:

                if driver is None:
                    driver = self.session_create(config)
                    if driver is None:
                        rc = False
                        break

                self.profile_write(profile_file, config)

                if needs_login:
                    rc = self.login(driver, config)
                    if not rc:
                        break
                    needs_login = False
                    self.fake_wait(randint(12222, 17777))

                self.delete_ad(driver, cur_ad)
                self.fake_wait(randint(12222, 17777))

                rc = self.post_ad(driver, config, cur_ad)
                if not rc:
                    self.add_screenshot(driver)
                    if not self.fInteractive:
                        if self.session_expired(driver):
                            rc = self.relogin(driver, config)
                            if rc:
                                rc = self.post_ad(driver, config, cur_ad)

                if not rc:
                    self.add_screenshot(driver)
                if not rc:
                    break

                # Was the profile postponed from a former run?
                if not self.profile_can_run(config):
                    break

                self.log.info("Waiting for handling next ad ...")
                self.reset()
                self.fake_wait(randint(12222, 17777))

        if not rc:
            self.send_email_error(config)

        return rc

    def session_create(self, config):
        """
        Creates a new browser / webdriver session.
        """
        self.log.info("Creating session")

        # For now use the Chrome driver, as Firefox doesn't work (empy page)
        driver      = None
        use_firefox = False

        try:

            if use_firefox:
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

            self.log.info("New driver session is: %s %s", driver.session_id, driver.command_executor._url)

            config['session_id'] = driver.session_id
            config['session_url'] = driver.command_executor._url

        except:
            self.log.error("Creating driver session failed!")

        return driver

    def session_attach(self, config):
        """
        Tries to attach to a former (existing) webdriver session, if any.
        """
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

    def session_expired(self, driver):
        """
        Checks if the Kleinanzeigen session is expired or not.
        """
        if driver is None:
            return True

        # Simply check the GET URL here for now
        if "sessionExpired" in driver.current_url:
            return True

        return False

    def main(self):
        """
        Main function for this class.
        """
        signal.signal(signal.SIGINT, signal_handler)

        try:
            opts, _ = getopt.gnu_getopt(sys.argv[1:], "ph", [ "profile=", "debug", "email-test", "headless", "outdir=", "non-interactive", "help" ])
        except getopt.GetoptError as msg:
            print(msg)
            print('For help use --help')
            sys.exit(2)

        profile_file = ""

        for o, a in opts:
            if o in '--profile':
                profile_file = a
            elif o in '--headless':
                self.fHeadless = True
            elif o in '--non-interactive':
                self.fInteractive = False
            elif o in '--debug':
                self.fDebug = True
                self.log_stream.setLevel(logging.DEBUG)
                self.log.setLevel(logging.DEBUG)
            elif o in '--outdir':
                self.sPathOut = a
            elif o in '--email-test':
                self.fEmailTest = True

        if not profile_file:
            print('No profile specified')
            sys.exit(2)

        self.init_logfile(self.sPathOut)

        self.log.info('Script started')
        self.log.info("Using profile: %s", profile_file)
        self.log.info("Output path is '%s'", self.sPathOut)

        if self.fHeadless:
            self.log.info("Running in headless mode")
        if not self.fInteractive:
            self.log.info("Running in non-interactive mode")

        config = {}

        if not self.profile_read(profile_file, config):
            self.log.error("Profile file not found / accessible!")
            sys.exit(1)

        if self.fEmailTest:
            self.log.info("Sending test E-Mail ...")
            self.send_email_profile(config, \
                                    "This is a test mail", \
                                    "If you can read this, sending was successful!")
            sys.exit(0)

        driver = None

        if config.get('session_id') is not None:
            driver = self.session_attach(config)

        # Is this profile postponed to run at some later point in time?
        if self.profile_can_run(config):
            self.handle_ads(profile_file, config)

        if self.log.error.counter:
            self.send_email_error(config)

        # Make sure to update the profile's data before terminating.
        self.profile_write(profile_file, config)

        self.logout(driver)

        self.log.info("Script done")
        self.cleanup()

if __name__ == '__main__':
    Kleinanzeigen().main()
