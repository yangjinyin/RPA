# -*- coding:utf-8 -*-

import sys
import argparse

INPUT_XML_PATH = ""
BROWSER_TYPE = ""
INITIAL_BROWSER_URL = ""


def parse():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input-xml-file", help="输入的XML路径")
    parser.add_argument("-b", "--browser-type", help="浏览器类型, 取值为ie,chrome或firefox")
    parser.add_argument("-l", "--initial-browser-url", help="税局首页")
    args = parser.parse_args()

    global INPUT_XML_PATH
    global BROWSER_TYPE
    global INITIAL_BROWSER_URL
    try:
        INPUT_XML_PATH = args.input_xml_file
    except Exception as e:
        pass

    try:
        BROWSER_TYPE = args.browser_type
    except Exception as e:
        pass

    try:
        INITIAL_BROWSER_URL = args.initial_browser_url
    except Exception as e:
        pass

parse()


if __name__ == '__main__':
    """测试代码"""
    sys.argv.append("--input-xml-file=PutDataTask.xml")
    sys.argv.append("--browser-type=ie")
    print(sys.argv)
    parse()



