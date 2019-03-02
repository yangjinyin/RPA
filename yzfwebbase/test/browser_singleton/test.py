# -*- coding:utf-8 -*-

import sys
import time
from yzfbrowser import MyBrowser

b  = MyBrowser.GetBrowser()
b2 = MyBrowser.GetBrowser()

print("b is b2 : " + str(b is b2))

b.get("https://www.baidu.com/")
time.sleep(10)
b2.get("https://cn.bing.com/")
time.sleep(10)
sys.exit(1)