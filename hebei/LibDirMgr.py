# -*- coding:utf-8 -*-
# Library Directory Manager

import sys
import os


def RegisterLibDir(new_lib_path):
	'''注册new_lib_path为库目录'''
	absolute_path = os.path.abspath(new_lib_path)
	if not os.path.isdir(absolute_path):
		raise Exception(new_lib_path + "不是目录。当前路径是" + os.getcwd() + ", 路径" + absolute_path + "不是目录。")

	if absolute_path not in sys.path:
		sys.path.append(absolute_path)


RegisterLibDir("tasks")
RegisterLibDir("../yzfwebbase")
RegisterLibDir("../yzfwebbase/ocr")
RegisterLibDir("../yzfwebbase/yzfxmlparse")
