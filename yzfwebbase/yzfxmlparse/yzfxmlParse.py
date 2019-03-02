# -*- coding:utf-8 -*-
from bs4 import BeautifulSoup
import os
from ctypes import *
import xmltodict
import sys
import re

def GetLoginInfo(filename):
    contents = open(filename, encoding='utf-8').read()
    soup = BeautifulSoup(contents, 'xml')
    dict = {}
    dict['loginName'] = soup.find('LoginName').get_text()
    dict['loginPassword'] = soup.find('LoginPassword').get_text()
    dict['companyName'] = soup.find('CompanyName').get_text()
    return dict

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


