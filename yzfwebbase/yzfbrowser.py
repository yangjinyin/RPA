# -*- coding:utf-8 -*-

import atexit
import logging
import yzfargv
from seleniumrequests import Chrome, Ie, Firefox
from selenium.webdriver import IeOptions


# Chrome singleton
class MyBrowser:
	instance = None

	def __init__(self):
		pass

	@classmethod
	def Quit(cls):
		logging.info("Quit() exit browser")
		MyBrowser.instance.quit()
		MyBrowser.instance = None

	@classmethod
	def GetBrowser(cls):
		if not MyBrowser.instance:
			if yzfargv.BROWSER_TYPE.upper() == "IE":
				if yzfargv.INITIAL_BROWSER_URL:
					ie_options = IeOptions()
					ie_options.initial_browser_url = yzfargv.INITIAL_BROWSER_URL
					MyBrowser.instance = Ie(ie_options=ie_options)
				else:
					MyBrowser.instance = Ie()
			elif yzfargv.BROWSER_TYPE.upper() == "CHROME":
				MyBrowser.instance = Chrome()
			elif yzfargv.BROWSER_TYPE.upper() == "FIREFOX":
				MyBrowser.instance = Firefox()
			else:
				raise Exception("暂不支持的浏览器类型" + yzfargv.BROWSER_TYPE)

			MyBrowser.instance.implicitly_wait(10)
			atexit.register(MyBrowser.Quit)
		return MyBrowser.instance

