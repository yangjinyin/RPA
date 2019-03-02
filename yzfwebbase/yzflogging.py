# -*- coding:utf-8 -*-

import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(filename)s:%(lineno)d[%(funcName)s()] %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S',
                    filename='InterfaceClientSelenium.log')