# -*- coding:utf-8 -*-

import time
from selenium.common.exceptions import NoSuchElementException
from yzfwebbase.yzftaxbot import MyBot, YzfBrowser, switch_to_url
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import os
from ctypes import *
import xmltodict
import sys
import re

def GetCaptcha():
    i = c_int(128)
    pi = pointer(i)  # the pointer point to int
    input = create_string_buffer(b'test.png')  # create a buffer containing a NULL terminated string; remember add 'b';
    output = create_string_buffer(128)  # create a 128 byte buffer initialized to NULL bytes
    testdll = CDLL(r'ChongqingGsCaptcha.dll')
    testdll.InitCaptcha()
    testdll.VerifyCaptchaHeBei(input, output, pi)
    testdll.Clear()

    return output.value


def main():
    MyBot.get_task_group_by_id("s")

    YzfBrowser.get("https://ybs.he-n-tax.gov.cn:8888/login-web/login")

    time.sleep(2)
    YzfBrowser.find_element_by_id("userName").send_keys(MyBot.BaseInfo.LoginName)
    YzfBrowser.find_element_by_id("passWord").send_keys(MyBot.BaseInfo.LoginPassword)

    captcha = YzfBrowser.find_element_by_id("captchCode")
    # 请求验证码
    CheckImg = YzfBrowser.find_element_by_id("yzmImg")
    captchaUrl = CheckImg.get_attribute("src")
    response = YzfBrowser.request("Get", captchaUrl)
    open("test.png", "w+b").write(response.content)
    # 获取验证码识别数字
    captcharesult = GetCaptcha()
    captcha.send_keys(captcharesult.decode('utf-8'))
    YzfBrowser.find_element_by_css_selector("#login").click()
    #登录并选择企业
    WebDriverWait(YzfBrowser, 30).until(EC.element_to_be_clickable((By.ID, "companyEnter")))

    company_xpath = r"//*[@id='choiceCompany']/li[contains(text(),'" + MyBot.CompanyInfo.CompanyName + "')]"
    YzfBrowser.find_element_by_xpath(company_xpath).click()
    YzfBrowser.find_element_by_id("companyEnter").click()


