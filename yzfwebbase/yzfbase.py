# -*- coding:utf-8 -*-
import sys
import os
import xml.etree.ElementTree as ET
import yzferrorcode
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
import datetime
import base64
import logging
import yzflogging
from yzfxml import YzfElement

dictCompanyInfo = dict()
dictBaseInfo = dict()
TaskXMLTree = ET.ElementTree()
AllTaskGroup = list()
XmlFilePath = ""


def SetGroupResultCode(taskgroup, strCode):
    resultCode = taskgroup.find("GroupResult/ResultCode")
    resultCode.text = strCode


def SetGroupResultDesc(taskgroup, strDesc):
    resultDesc = taskgroup.find("GroupResult/ResultDesc")
    resultDesc.text = strDesc


def NotifySuccess(taskgroup):
    return NotifyDone(taskgroup, yzferrorcode.eErrorCode.ExcuteSuccess.value, "")


def SaveOwnWndPngToBase64(browserDriver, strMsg=""):
    browserDriver.get_screenshot_as_file("tmp.png")
    img = Image.open("tmp.png")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("STFANGSO.TTF", 36)
    draw.text((0, 0), strMsg, (255, 0, 0), font=font)
    timestamp = str(datetime.datetime.now())
    font = ImageFont.truetype("STFANGSO.TTF", 26)
    draw.text((img.width / 2, img.height - 50), timestamp, (255, 0, 0), font=font)
    img.save('tmp1.png')
    with open('tmp1.png', 'rb') as pngfile:
        return str(base64.b64encode(pngfile.read()))


def NotifyDone(taskgroup, icode, strDesc, bImage=False, bNeedRetry=False):
    resultCode = taskgroup.find("GroupResult/ResultCode")
    resultCode.text = str(icode)
    resultDesc = taskgroup.find("GroupResult/ResultDesc")
    resultDesc.text = strDesc
    if bImage:
        resultDesc.set("bImage", "TRUE")
    if bNeedRetry:
        resultDesc.set("bNeedRetry", "TRUE")

    strResultXmlFile = os.path.splitext(XmlFilePath)[0] + "_updated" + os.path.splitext(XmlFilePath)[1]
    logging.info("Result XML:" + strResultXmlFile)
    SaveXMLTreeToFile(strResultXmlFile, 'UTF-8')


def CJ_HB_BASE_INFO(taskgroup):
    for taskitem in taskgroup.iter("TaskItem"):
        print("  " + taskitem.tag, taskitem.attrib)
        for taskparam in taskitem.iter("TaskParam"):
            print("    " + taskparam.tag, taskparam.attrib)
            for param in taskparam.iter():
                print("      " + param.tag, param.attrib, param.text)


def processCJTaskGroup(taskgroup):
    if taskgroup["id"] == "HB_BASE_INFO":
        CJ_HB_BASE_INFO(taskgroup)
    else:
        print("Error")
        return False


def SaveXMLTreeToFile(filename, strEncoding):
    global TaskXMLTree
    TaskXMLTree.write(filename, encoding=strEncoding, xml_declaration=True)


def parse(xmlfile_path):
    global dictCompanyInfo
    global dictBaseInfo
    global TaskXMLTree
    global AllTaskGroup
    global XmlFilePath

    XmlFilePath = xmlfile_path
    xml_text = ""

    try:
        xml_text = open(xmlfile_path, encoding="gbk").read()
    except:
        pass

    if xml_text == "":
        try:
            xml_text = open(xmlfile_path, encoding="utf-8").read()
        except:
            pass

    if xml_text == "":
        print("读取XML失败")
        sys.exit(1)

    # print(xml_text)
    root = ET.fromstring(xml_text)

    TaskXMLTree = ET.ElementTree(element=root)

    companyInfo = root.find("CompanyTask/CompanyInfo")
    for info in companyInfo.iter():
        dictCompanyInfo[info.tag] = info.text

    tasklist = root.find("TaskList")
    baseinfo = root.findall("CompanyTask/TaskList/BaseInfo/*")
    for info in baseinfo:
        # print(info.tag, info.attrib, info.text)
        dictBaseInfo[info.tag] = info.text

    AllTaskGroup = root.findall("CompanyTask/TaskList/TaskGroup")

    return True


def RemoveFirstTaskParam(taskgroup):
    for taskitem in taskgroup.findall("TaskItem"):
        for taskparm in taskitem.iter("TaskParam"):
            taskitem.remove(taskparm)
            return True
    return False


def RemoveAllTaskParam(taskgroup):
    while RemoveFirstTaskParam(taskgroup):
        pass


def RemoveFirstItem(taskgroup):
    for taskitem in taskgroup.findall("TaskItem"):
        for taskparam in taskitem.iter("TaskParam"):
            for item in taskparam.iter("Item"):
                taskparam.remove(item)
                return True
    return False


def RemoveAllItems(taskgroup):
    while RemoveFirstItem(taskgroup):
        pass


def AddItem(taskgroup, dictKV, dictAttr):
    for taskitem in taskgroup.findall("TaskItem"):
        for taskparam in taskitem.iter("TaskParam"):
            yzfitem = YzfElement()
            yzfitem.SetAttrs(dictAttr)
            yzfitem.AddChildElements(dictKV)
            taskparam.append(yzfitem.ele)
            return True
    return False


def AddTagValueItemToTaskParam(taskgroup, itemtag, itemvalue):
    for taskitem in taskgroup.findall("TaskItem"):
        for taskparam in taskitem.iter("TaskParam"):
            item = ET.SubElement(taskparam, itemtag)
            item.text = itemvalue
            return True
    return False


def RemoveFirstTaskParam(taskgroup):
    for taskitem in taskgroup.findall("TaskItem"):
        for taskparam in taskitem.iter("TaskParam"):
            taskitem.remove(taskparam)
            return True
    return False


def AddTaskParam(taskgroup):
    for taskitem in taskgroup.findall("TaskItem"):
        taskparam = ET.SubElement(taskitem, "TaskParam")
        return True
    return False


def RemoveAllTaskParam(taskgroup):
    while RemoveFirstTaskParam(taskgroup):
        pass


def RemoveTaskParamChildren(taskgroup):
    while RemoveFirstTaskParam(taskgroup):
        pass
    AddTaskParam(taskgroup)

def main():
    parse()
    return 0

if __name__ == '__main__':
    sys.exit(main())