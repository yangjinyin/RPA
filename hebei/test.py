import execjs
from selenium import webdriver
import json
#river = webdriver.Chrome()
#driver.get('http://www.baidu.com')

key = "key1"
value = "value1"
dic = {key, value}
list = []
list.append(dic)

key = "key2"
value = "value2"
dic = {key, value}
list.append(dic)

print(dic)



def get_js():
    f = open("Yzf.js", "r", encoding="UTF-8")
    line = f.readline()
    htmlstr = ''
    while line:
        htmlstr = htmlstr + line
        line = f.readline()
    return htmlstr


js = get_js() + "return add(arguments[0])"
ts = driver.execute_script(js, "123")
dict = json.loads(ts)
dict1 = dict["rtnMsg"]
list = dict1["1"]
print(list[1])
print(dict1[1])


