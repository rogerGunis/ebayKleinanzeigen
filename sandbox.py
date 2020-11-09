#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint: disable=C0301
# pylint: disable=C0111
import os
import re
import sys
import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys

from urlparse import parse_qs

def post_ad_mandatory_fields_set(driver, ad):
    for el in driver.find_elements_by_xpath('//*[@class="formgroup-label-mandatory"]'):
        sForId = el.get_attribute("for")
        if sForId is not None:
            print("Detected mandatory field (Name='%s', ID='%s')" % (el.text, sForId))
            reMatch = re.search('.*\.(.*)_s.*', sForId, re.IGNORECASE)
            if reMatch is not None:
                sForIdRaw = reMatch.group(1)
                if sForIdRaw in ad:
                    Select(driver.find_element_by_id(sForId)).select_by_visible_text(ad[sForIdRaw])
                else:
                    print("*** Warning: No value for combo box '%s' defined, setting to default (first entry)" % (sForIdRaw,))
                    s = Select(driver.find_element_by_id(sForId))
                    iOpt = 0
                    for o in s.options:
                        if len(o.get_attribute("value")):
                            break
                        iOpt += 1
                    s.select_by_value(s.options[iOpt].get_attribute("value"))
            else:
                sForIdRaw = sForId
                if "field_" + sForIdRaw in ad:
                    sValue = ad["field_" + sForIdRaw]
                else:
                    print("*** Warning: No value for text field '%s' defined, setting to empty value" % (sForIdRaw,))
                    sValue = 'Nicht angegeben'
                try:
                    driver.find_element_by_id(sForId).send_keys(sValue)
                except:
                    pass


dQuery = parse_qs('https://www.ebay-kleinanzeigen.de/p-kategorie-aendern.html#?path=161/225/netzwerk_modem&isParent=false')
for sPathCat in dQuery.get('https://www.ebay-kleinanzeigen.de/p-kategorie-aendern.html#?path')[0].split('/'):
    sPathCat = 'cat_' + sPathCat


ad = {
    'field_postad-title' : 'foobar',
    'field_groesse' : '110'
}

#
#driver = webdriver.Firefox()
#driver.get("file:///home/jiinx/Downloads/kleinanzeigen_test/fields.html")
#post_ad_mandatory_fields_set(driver, ad)
#driver.close()
#