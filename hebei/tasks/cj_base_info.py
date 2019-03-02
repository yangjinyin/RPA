# -*- coding:utf-8 -*-

import yzflogging
import logging
import time
import yzftaxbot
from yzftaxbot import MyBot, YzfBrowser, switch_to_url, switch_to_last_window, save_page_source_to, TaskGroup, analyze_element_frames, click_selector, click_xpath, read_tbody


def get_js():
    f = open("Yzf.js", "r", encoding="UTF-8")
    line = f.readline()
    htmlstr = ''
    while line:
        htmlstr = htmlstr + line
        line = f.readline()
    return htmlstr

def main():
    YzfBrowser.find_element_by_xpath("//*[@id='mine-ul']/li[2]").click()
    time.sleep(1)
    YzfBrowser.find_element_by_class_name("txt-c").click()
    switch_to_last_window()

    js = get_js() + "read_tbody(arguments[0],arguments[1],arguments[2])"
    driver.execute_script(js, "#app > div > div > section > div > section > div > div > div.ant-tabs-content > span > div:nth-child(2) > div > div > div > div > table > tbody", "tr", "td")

