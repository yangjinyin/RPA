# -*- coding:utf-8 -*-
import re
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
import os
import sys
import time
import io
import yzfbase
import yzferrorcode
import logging
import yzflogging
import yzfxmlParse
import atexit
import datetime
import dateutil.relativedelta
from yzfbrowser import MyBrowser
from PIL import Image
import random
import requests
from selenium.webdriver.support.ui import Select

mybrowser = MyBrowser.GetBrowser()
mybrowser.maximize_window()
mybrowser.implicitly_wait(10)


def switch_to_url(strUrl):
    for i in range(len(mybrowser.window_handles)):
        mybrowser.switch_to.window(mybrowser.window_handles[i])
        if strUrl in mybrowser.current_url:
            return True

    return False


def close_browser():
    logging.info("close_browser()")
    mybrowser.quit()


atexit.register(close_browser)

g_strKJZD = ""  # 适用会计制度


def thisisatest():
    for i in range(len(mybrowser.window_handles)):
        try:
            mybrowser.switch_to.window(mybrowser.window_handles[i])
            logging.info(str(i) + " " + str(mybrowser.current_url))
        except Exception as e:
            logging.exception(e)


def GoToIndexPageA():
    logging.info("回首页")
    for i in range(len(mybrowser.window_handles)):
        mybrowser.switch_to.window(mybrowser.window_handles[i])
        try:
            mybrowser.find_element_by_xpath("//span[text()='首页']").click()
        except Exception as e:
            try:
                mybrowser.find_element_by_xpath("//a[text()='首页']").click()
            except Exception as e:
                continue
            break
        break
    else:
        logging.error("跳回首页失败")
        raise Exception("跳回首页失败")

    logging.info("跳回首页成功")
    return True


def GoToIndexPage():
    if switch_to_url("/home/home.html"):
        return True

    mybrowser.implicitly_wait(0)
    logging.info("回首页")
    for i in range(len(mybrowser.window_handles)):
        mybrowser.switch_to.window(mybrowser.window_handles[i])
        try:
            mybrowser.find_element_by_xpath("//*[text()='首页']").click()
        except Exception as e:
            continue
        break
    else:
        logging.error("跳回首页失败")
        mybrowser.implicitly_wait(10)
        raise Exception("跳回首页失败")

    logging.info("跳回首页成功")
    mybrowser.implicitly_wait(10)
    return True


def ProcessBaseInfoCJ(taskgroup):
    logging.info("Entering ProcessBaseInfoCJ:" + str(taskgroup.attrib))
    time.sleep(5)
    mybrowser.find_element_by_xpath("//*[@id='panel-22010']/ul/li[1]/a").click()
    time.sleep(5)
    mybrowser.switch_to.window(mybrowser.window_handles[-1])  # 切换到新弹出来的窗口
    info = dict()
    # 基础信息
    info["nsrmc"] = mybrowser.find_element_by_xpath("//*[@id='nsrmc']").text
    info["nsrsbh"] = mybrowser.find_element_by_xpath("//*[@id='nsrsbh']").text
    info["hy"] = mybrowser.find_element_by_id("hyxl").text
    info["djzclx"] = mybrowser.find_element_by_id("djzclxmc").text
    info["swdjrq"] = mybrowser.find_element_by_id("djrq").text

    # 注册经营信息
    mybrowser.find_element_by_xpath("//div[text()='注册经营信息']").click()
    time.sleep(1)
    info["zcdz"] = mybrowser.find_element_by_id("zcdz").text
    info["scjydz"] = mybrowser.find_element_by_id("scjydz").text

    # 企业经营信息
    mybrowser.find_element_by_xpath("//div[text()='企业经营信息']").click()
    time.sleep(1)
    info["jyfw"] = mybrowser.find_element_by_id("jyfw").text
    info["zczb"] = mybrowser.find_element_by_id("zczb").text

    # 税务信息
    mybrowser.find_element_by_xpath("//div[text()='税务信息']").click()
    time.sleep(1)
    info["zgswjg"] = info["ZGSWJG"] = mybrowser.find_element_by_id("zgswjg").text
    global g_strKJZD
    g_strKJZD = mybrowser.find_element_by_id("sykjzd").text

    # 业主信息
    mybrowser.find_element_by_xpath("//div[text()='业主信息']").click()
    time.sleep(1)
    info["bslxr"] = mybrowser.find_element_by_id("bsrxm").text  # 办税人姓名
    info["bslxr_mobile"] = mybrowser.find_element_by_id("bsryddh").text  # 办税人手机, 办税人移动电话
    info["bsrysfzhm"] = mybrowser.find_element_by_id("bsrsfzjhm").text  # 办税人证件号码
    info["bsrysfzlx"] = mybrowser.find_element_by_id("bsrsfzjzlDm").text  # 办税人证件名称
    info["cwfzr"] = mybrowser.find_element_by_id("cwfzrxm").text  # 财务负责人
    info["cwfzr_mobile"] = mybrowser.find_element_by_id("cwfzryddh").text  # 财务负责人移动电话
    info["cwfzrzjhm"] = mybrowser.find_element_by_id("cwfzrsfzjhm").text  # 财务负责人证件号码print(str(info))
    info["cwfzrzjlx"] = mybrowser.find_element_by_id("cwfzrsfzjzlDm").text  # 财务负责人证件名称
    info["fddbr"] = mybrowser.find_element_by_id("fddbrxm").text  # 法人
    info["fddbr_mobile"] = mybrowser.find_element_by_id("fddbryddh").text  # 法人移动电话
    info["fd_zjhm"] = mybrowser.find_element_by_id("fddbrsfzjhm").text  # 法人证件号码
    info["fd_sfzjmc"] = mybrowser.find_element_by_id("fddbrsfzjlxDm").text  # 法人证件名称
    logging.info(str(info))

    yzfbase.RemoveAllTaskParam(taskgroup)
    yzfbase.AddTaskParam(taskgroup)
    for k, v in info.items():
        yzfbase.AddTagValueItemToTaskParam(taskgroup, k, v)

    # for taskitem in taskgroup.iter("TaskItem"):
    #    for taskparam in taskitem.iter():
    #        for param in taskparam.iter():
    #            if param.tag in info:
    #                param.text = info[param.tag]

    # strMsg = "截图测试"
    # yzfbase.NotifyDone(taskgroup,
    #                   yzferrorcode.eErrorCode.ExcuteSuccess.value,
    #                   yzfbase.SaveOwnWndPngToBase64(mybrowser, strMsg),
    #                   True)

    yzfbase.NotifySuccess(taskgroup)

    logging.info("回首页")
    mybrowser.find_element_by_xpath("//span[text()='首页']").click()
    time.sleep(5)
    logging.info("采集基本信息完成")
    return True


def ProcessSZRDCJ(taskgroup):
    logging.info("Entering:" + str(taskgroup.attrib))
    yzfbase.RemoveAllItems(taskgroup)
    time.sleep(5)
    mybrowser.find_element_by_xpath("//*[@id='panel-22010']/ul/li[1]/a").click()
    time.sleep(5)
    mybrowser.switch_to.window(mybrowser.window_handles[-1])  # 切换到新弹出来的窗口
    WebDriverWait(mybrowser, 30).until(EC.element_to_be_clickable((By.XPATH, "//div[text()='税费种认定信息']")))
    mybrowser.find_element_by_xpath("//div[text()='税费种认定信息']").click()
    time.sleep(5)

    info = {}
    row_text = []
    resultTbody = mybrowser.find_element_by_xpath("//tbody[@class='ant-table-tbody']")
    for row in resultTbody.find_elements_by_xpath(".//tr"):
        logging.info(str([td.text for td in row.find_elements_by_xpath(".//span")]))
        row_text = [td.text for td in row.find_elements_by_xpath(".//span")]
        info["zsxm"] = row_text[2]  # 税种
        info["zspm"] = row_text[3]  # 税目
        info["nsqx"] = row_text[4]  # 纳税期限
        info["sl"] = row_text[7]  # 税率
        info["rdyxqq"] = row_text[8]  # 认定有效期起
        info["rdyxqz"] = row_text[9]  # 认定有效期止
        yzfbase.AddItem(taskgroup, info, {"type": "GS_JDXX"})

    mybrowser.find_element_by_xpath("//span[text()='首页']").click()
    time.sleep(5)

    # CWBB 我要办税->税费申报及缴纳->申报结果查询/作废 选择企业所得税/财务报表 日期往前推三个月
    mybrowser.find_element_by_xpath("//li[text()='我要办税']").click()
    time.sleep(3)
    mybrowser.find_element_by_xpath("//div[text()='税费申报及缴纳']").click()
    time.sleep(3)
    mybrowser.switch_to.window(mybrowser.window_handles[-1])
    WebDriverWait(mybrowser, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[text()='申报结果查询/作废']")))

    mybrowser.find_element_by_xpath("//a[text()='申报结果查询/作废']").click()
    time.sleep(3)
    mybrowser.switch_to.window(mybrowser.window_handles[-1])
    WebDriverWait(mybrowser, 10).until(EC.element_to_be_clickable((By.XPATH, "//*[@id='zsxmDm$text']")))

    mybrowser.find_element_by_xpath("//*[@id='zsxmDm$text']").send_keys(u"财务报表\n")
    strSbrqz = mybrowser.find_element_by_xpath("//*[@id='sbrqz$value']").get_attribute("value")
    logging.info("申报日期止" + strSbrqz)
    datetimeSbrqz = datetime.datetime.strptime(strSbrqz, "%Y-%m-%d")
    datetimeSbrqq = datetimeSbrqz - dateutil.relativedelta.relativedelta(months=3)
    strSbrqq = datetimeSbrqq.strftime("%Y-%m-%d")
    logging.info("三个月前" + strSbrqq)
    mybrowser.find_element_by_xpath("//*[@id='sbrqq$text']").clear()
    mybrowser.find_element_by_xpath("//*[@id='sbrqq$text']").send_keys(strSbrqq)
    time.sleep(1)
    mybrowser.find_element_by_xpath("//*[@id='search-btn']").click()

    resultTbody = mybrowser.find_element_by_xpath("//*[@id='mini-grid-table-bodysbjgcx_grid']/tbody")
    for row in resultTbody.find_elements_by_xpath(".//tr"):
        row_text = [td.text for td in row.find_elements_by_xpath(".//td")]
        logging.info("一行:" + str(row_text))
        if row_text[0] == "1":
            info = {}
            info["cwzd"] = row_text[1].split("-")[0]
            info["nsqx"] = row_text[1].split("-")[1][0]
            info["ssqq"] = row_text[4]
            info["ssqz"] = row_text[5]
            yzfbase.AddItem(taskgroup, info, {"type": "GS_CWBB"})
            break
    else:
        global g_strKJZD
        yzfbase.AddItem(taskgroup, {"cwzd": g_strKJZD}, {"type": "GS_CWBB"})

    time.sleep(15)  # 网站说10秒后可以查第2次

    mybrowser.find_element_by_xpath("//*[@id='zsxmDm$text']").clear()
    mybrowser.find_element_by_xpath("//*[@id='zsxmDm$text']").send_keys(u"企业所得税\n")
    time.sleep(1)
    mybrowser.find_element_by_xpath("//*[@id='search-btn']").click()
    resultTbody = mybrowser.find_element_by_xpath("//*[@id='mini-grid-table-bodysbjgcx_grid']/tbody")
    for row in resultTbody.find_elements_by_xpath(".//tr"):
        row_text = [td.text for td in row.find_elements_by_xpath(".//td")]
        if row_text[0] == "1":
            info = {}
            info["sbbmc"] = row_text[1][:-2]
            yzfbase.AddItem(taskgroup, info, {"type": "GS_QYSDS"})
            break
    else:
        yzfbase.AddItem(taskgroup, {"sbbmc": "企业所得税A类"}, {"type": "GS_QYSDS"})

    yzfbase.NotifySuccess(taskgroup)
    thisisatest()
    GoToIndexPage()
    time.sleep(5)


def ProcessWHSYJBSB(taskgroup):
    logging.info("Entering ProcessWHSYJBSB:" + str(taskgroup.attrib))
    time.sleep(5)
    # 我要办税->税费申报及缴纳->其他申报 文化事业建设费申报
    mybrowser.find_element_by_xpath("//li[text()='我要办税']").click()
    time.sleep(3)
    mybrowser.find_element_by_xpath("//div[text()='税费申报及缴纳']").click()
    time.sleep(3)
    mybrowser.switch_to.window(mybrowser.window_handles[-1])
    WebDriverWait(mybrowser, 10).until(EC.element_to_be_clickable((By.ID, "menu-220203040")))
    mybrowser.find_element_by_xpath("//*[@id='menu-220203040']").click()
    mybrowser.find_element_by_xpath("//a[text()='文化事业建设费申报']").click()
    WebDriverWait(mybrowser, 30).until(EC.element_to_be_clickable((By.XPATH, "//*[@id='table_001']/tbody")))
    for taskparm in taskgroup.findall("TaskParam"):
        for info in taskparm:
            row = int(''.join(re.findall(r"\d+\d*", (info.attrib["tax"])))) + 1
            # print(info.tag, info.attrib, info.text)
            if (info.tag == "BlankCell"):
                # info_BlankCell.append(info.text)
                SBCell(info.text, str(row), "5")
            else:
                SBCell(info.text, str(row), "6")


def SBCell(cell, row, col):
    resultTbody = mybrowser.find_element_by_xpath("//*[@id='table_001']/tbody")
    for row in resultTbody.find_elements_by_xpath(".//tr[" + row + "]"):
        for td in row.find_elements_by_xpath(".//td[" + col + "]/input"):
            try:
                td.click()
                td.clear()
                time.sleep(0.5)
                td.send_keys(str(cell))
            except Exception as e:
                print("该值不可选")


def ProcessWHSYFWSB(taskgroup):
    # 我要办税->税费申报及缴纳->其他申报 文化事业建设费申报 ->文化事业建设费应税服务扣除项目清单
    logging.info("Entering ProcessWHSYFWSB:" + str(taskgroup.attrib))
    WebDriverWait(mybrowser, 10).until(EC.element_to_be_clickable((By.XPATH, "//*[@id='mini-1$2']/span")))
    mybrowser.find_element_by_xpath("//*[@id='mini-1$2']/span").click()
    WebDriverWait(mybrowser, 30).until(EC.element_to_be_clickable((By.XPATH, "//*[@id='table_002']/tbody")))
    info_BlankCellVal = []
    for taskparm in taskgroup.findall("TaskParam"):
        for info in taskparm:
            if (info.tag == "BlankCell"):
                if (info.attrib['col'] == "4"):
                    # print(info.attrib['row'] + info.attrib['col'] + info.text)
                    SBCell2(str(int(info.attrib['row']) + 1), info.attrib['col'], info.text)
                else:
                    row = info.attrib['row']
                    col = info.attrib['col']
                    text = info.text
                    val = row + "_" + col + "_" + text
                    info_BlankCellVal.append(val)

    for val in info_BlankCellVal:
        val = val.split("_")
        SBCell1(str(int(val[0]) + 1), val[1], val[2])

    # # 提交
    # time.sleep(0.5)
    # mybrowser.find_element_by_id("sb_save").click()
    # time.sleep(0.5)
    # suspondWindowHandler(mybrowser, "//div[contains(@id, 'mini-2')]/div//*[contains(@id, 'mini-3')]")
    # # 等待12秒
    # time.sleep(12)
    #
    # WebDriverWait(mybrowser, 30).until(EC.element_to_be_clickable((By.XPATH, "//*[@id='breadcrumb-Nav']/span[3]")))
    # time.sleep(1)
    # mybrowser.find_element_by_xpath("//*[@id='search-btn']").click()
    # time.sleep(3)
    #
    # resultTbody = mybrowser.find_element_by_xpath("//*[@id='mini-grid-table-bodysbjgcx_grid']/tbody")
    # for row in resultTbody.find_elements_by_xpath(".//tr"):
    #     row_text = [td.text for td in row.find_elements_by_xpath(".//td")]
    #     logging.info("一行:" + str(row_text))
    #     # 一行:['', '', '', '', '', '', '', '', '']
    #     # 一行:['1', '文化事业建设费季报', '正常申报', '2019-01-11', '2018-10-01', '2018-12-31', '申报失败', '0', '查看错误原因重新申报']
    #     if row_text[0] == "1":
    #         info = {}
    #         # 申报类型
    #         info["sblx"] = row_text[1] + row_text[1]
    #         # 纳税期限
    #         info["nsqx"] = row_text[1]
    #         # 所属时期起
    #         info["ssqq"] = row_text[4]
    #         # 所属时期止
    #         info["ssqz"] = row_text[5]
    #         # 申报状态
    #         info["sbzt"] = row_text[6]
    #         # yzfbase.AddItem(taskgroup, info, {"type": "GS_CWBB"})
    #         break
    # else:
    #     global g_strKJZD
    #     # yzfbase.AddItem(taskgroup, {"cwzd": g_strKJZD}, {"type": "GS_CWBB"})


# 选择凭证种类
def SBCell2(row, col, text):
    resultTbody = mybrowser.find_element_by_xpath("//*[@id='table_002']/tbody")
    for row in resultTbody.find_elements_by_xpath(".//tr[" + row + "]"):
        for td in row.find_elements_by_xpath(".//td[" + col + "]/select"):
            try:
                time.sleep(0.5)
                # td.click()
                Select(td).select_by_visible_text(text)
            except Exception as e:
                print("没有这个选项")


# 文化事业建设费应税服务扣除项目清单 ->输入各种值
def SBCell1(row, i, cell):
    resultTbody = mybrowser.find_element_by_xpath("//*[@id='table_002']/tbody")
    for row in resultTbody.find_elements_by_xpath(".//tr[" + row + "]"):
        for td in row.find_elements_by_xpath(".//td[" + i + "]/input"):
            try:
                td.click()
                td.clear()
                time.sleep(0.5)
                td.send_keys(str(cell))
            except Exception as e:
                print("该值不可选")


def ProcessCJTaskGroup(taskgroup):
    CJTaskGroupHandler = dict()
    CJTaskGroupHandler["HB_BASE_INFO"] = ProcessBaseInfoCJ
    CJTaskGroupHandler["HBGS_SZRD"] = ProcessSZRDCJ
    if taskgroup.attrib["id"] not in CJTaskGroupHandler:
        raise "不支持的采集任务" + taskgroup.attrib["id"]

    logging.info(taskgroup.attrib["id"])
    return CJTaskGroupHandler[taskgroup.attrib["id"]](taskgroup)


def DummyTaskGroup(taskgroup):
    pass


def ProccessTaskItem(taskItem):
    AllTaskItemHandler = dict()
    AllTaskItemHandler["文化事业建设费申报表"] = ProcessWHSYJBSB
    AllTaskItemHandler["文化事业建设费应税服务扣除项目清单"] = ProcessWHSYFWSB

    if taskItem.attrib["id"] not in AllTaskItemHandler:
        raise "不支持的申报任务" + taskItem.attrib["id"]

    logging.info(taskItem.attrib["id"])
    return AllTaskItemHandler[taskItem.attrib["id"]](taskItem)


def ProcessSBTaskGroup(taskgroup):
    AlltaskItem = taskgroup.findall("TaskItem")
    for taskItem in AlltaskItem:
        ProccessTaskItem(taskItem)
    yzfbase.NotifySuccess(taskgroup)


def ProccessTaskGroup(taskgroup):
    logging.info(u"处理" + taskgroup.attrib["type"] + " " + taskgroup.attrib["id"])

    AllTaskGroupHandler = dict()
    AllTaskGroupHandler["CJ"] = ProcessCJTaskGroup
    AllTaskGroupHandler["SWCSH"] = DummyTaskGroup
    AllTaskGroupHandler["SB"] = ProcessSBTaskGroup

    if taskgroup.attrib["type"] not in AllTaskGroupHandler:
        raise "不支持的TaskGroup类型" + taskgroup.attrib["type"]

    return AllTaskGroupHandler[taskgroup.attrib["type"]](taskgroup)


def CheckImg(captcha):
    # 请求验证码
    CheckImg = mybrowser.find_element_by_id("yzmImg")
    captchaUrl = CheckImg.get_attribute("src")
    response = mybrowser.request("Get", captchaUrl)
    open("test.png", "w+b").write(response.content)
    # 获取验证码识别数字
    captcharesult = yzfxmlParse.GetCaptcha()
    captcha.send_keys(captcharesult.decode('utf-8'))
    mybrowser.find_element_by_css_selector("#login").click()


# 弹窗处理
def suspondWindowHandler(browser, xpath1):
    try:
        WebDriverWait(mybrowser, 30).until(EC.element_to_be_clickable((By.XPATH, xpath1)))  # 等待窗口出现
        suspondWindow = browser.find_element_by_xpath(xpath1)
        suspondWindow.click()
        print(f"searchKey: Suspond Page1 had been closed.")
    except Exception as e:
        print(f"searchKey: there is no suspond Page1. e = {e}")


def ProcessLogin(dict):
    logging.info(u"登录任务")
    username = mybrowser.find_element_by_id("userName")
    password = mybrowser.find_element_by_id("passWord")
    username.send_keys(dict['loginName'])
    password.send_keys(dict['loginPassword'])
    captcha = mybrowser.find_element_by_id("captchCode")
    CheckImg(captcha)
    # 登录并选择企业
    WebDriverWait(mybrowser, 30).until(EC.element_to_be_clickable((By.ID, "companyEnter")))
    company_xpath = r"//*[@id='choiceCompany']/li[contains(text(),'" + dict['companyName'] + "')]"
    mybrowser.find_element_by_xpath(company_xpath).click()
    mybrowser.find_element_by_id("companyEnter").click()
    WebDriverWait(mybrowser, 30).until(EC.element_to_be_clickable((By.XPATH, "//*[@id='panel-22010']/ul/li[1]/a")))  # 纳税人信息
    suspondWindowHandler(mybrowser, "//div[contains(@id, 'mini-1')]//*[contains(@class, 'mini-button')]")


def ProcessXMGItem(taskitem):
    blanks = taskitem['TaskParam']['BlankCell']
    index = 0
    print(len(blanks))
    try:
        while index < len(blanks):
            xpath = '// *[ @ id = "printView"] / table[3] / tbody / tr[%s] / td[%s]' % (str(int(blanks[index]['@row_col'].split('_')[0]) + 2), str(int(blanks[index]['@row_col'].split('_')[1]) + 2))
            print(mybrowser.find_element_by_xpath(xpath).text)
            blanks[index]['#text'] = mybrowser.find_element_by_xpath(xpath).text
            index = index + 1
            print(index)
    except Exception as e:
        logging.exception(e)


def ProcessFLItem(taskitem):
    blanks = taskitem['TaskParam']['BlankCell']
    index = 0
    print(len(blanks))
    try:
        while index < len(blanks):
            print(blanks[index]['@row_col'])
            xpath = '// *[ @ id = "printView"] / table[3] / tbody / tr[%s] / td[%s]' % (str((blanks[index]['@row_col'].split('_')[0])), str((blanks[index]['@row_col'].split('_')[1])))
            print(mybrowser.find_element_by_xpath(xpath).text)
            blanks[index]['#text'] = mybrowser.find_element_by_xpath(xpath).text
            index = index + 1
            print(index)
    except Exception as e:
        logging.exception(e)


def ProcessXGMCSH(taskgroup):
    mybrowser.get("https://ybs.he-n-tax.gov.cn:8888/yhs-web/cxzx/index.html?&code=sbxxcx&id=90003&_lot=1543213208429#/sbxxcx")
    WebDriverWait(mybrowser, 10).until(EC.element_to_be_clickable((By.ID, "app")))
    mybrowser.find_element_by_xpath('//*[@id="app"]/div/div/div[2]/form/div[1]/div[2]/div/div/div/span[1]/span/span[1]').click()
    mybrowser.find_element_by_xpath('/html/body/div[2]/div/div/ul/li[2]').click()

    # 申报日期起选择
    mybrowser.find_element_by_xpath('//*[@id="app"]/div/div/div[2]/form/div[1]/div[3]/div/div/div/span[1]/span/input').click()
    time.sleep(1)
    mybrowser.find_element_by_xpath('/html/body/div[3]/div/div/div[2]/div[1]/div/a[2]').click()
    mybrowser.find_element_by_xpath('/html/body/div[3]/div/div/div[2]/div[1]/div/a[2]').click()
    mybrowser.find_element_by_xpath('/html/body/div[3]/div/div/div[2]/div[2]/table/tbody/tr[1]/td[1]/span').click()
    # 点击查询
    mybrowser.find_element_by_xpath('//*[@id="app"]/div/div/div[2]/form/div[2]/div[4]/button').click()
    mybrowser.find_element_by_link_text('查看申报表').click()
    mybrowser.find_element_by_xpath('/html/body/div[4]/div/div[2]/div[1]/div[2]/div/div/div/div/div/table/tbody/tr[1]/td[2]/div/a[1]').click()
    mybrowser.switch_to_window(mybrowser.window_handles[1])
    # 小规模纳税申报表
    taskitems = taskgroup['TaskItem']

    iter = 0
    while iter < len(taskitems):
        if taskitems[iter]['@id'] == "增值税纳税申报表":
            taskitem = taskitems[iter]
            ProcessXMGItem(taskitem)
            break
        else:
            iter = iter + 1

    mybrowser.switch_to_window(mybrowser.window_handles[0])
    mybrowser.find_element_by_xpath('/html/body/div[4]/div/div[2]/div[1]/div[2]/div/div/div/div/div/table/tbody/tr[2]/td[2]/div/a[1]').click()
    mybrowser.switch_to_window(mybrowser.window_handles[2])
    iter = 0
    while iter < len(taskitems):
        if taskitems[iter]['@id'] == "增值税纳税申报表（小规模纳税人适用）附列资料":
            ProcessFLItem(taskitems[iter])
            break
        else:
            iter = iter + 1


def main():
    logging.info("Entering main()")
    global mybrowser
    global resultcode

    dict = yzfxmlParse.GetLoginInfo(sys.argv[1])
    login_url = "https://ybs.he-n-tax.gov.cn:8888/login-web/login"
    mybrowser.get(login_url)
    WebDriverWait(mybrowser, 10).until(EC.element_to_be_clickable((By.ID, "userName")))
    WebDriverWait(mybrowser, 10).until(EC.element_to_be_clickable((By.ID, "passWord")))
    # 登陆模块
    ProcessLogin(dict)
    # 任务模块
    yzfbase.parse(sys.argv[1])
    for taskgroup in yzfbase.AllTaskGroup:
        ProccessTaskGroup(taskgroup)

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        logging.exception(e)
        sys.exit(128)
