# -*- coding:utf-8 -*-

import base64

f = open("tmp1.png", "rb")
pngContent = f.read()
print(str(base64.b64encode(pngContent)))