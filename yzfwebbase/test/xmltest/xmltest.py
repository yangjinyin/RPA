import xml.etree.ElementTree as ET

class YzfItem:
    def __init__(self, tag="Item", attrib={}):
        self.item = ET.Element(tag, attrib)

    def SetAttr(self, strAttrName, strAttrValue):
        self.item.set(strAttrName, strAttrValue)

    def SetAttrs(self, attrib = {}):
        for key, value in attrib.items():
            self.SetAttr(key, value)

    def AddChildElement(self, tag, text, attrib={}):
        subElem = ET.SubElement(self.item, tag, attrib)
        subElem.text = text

    def AddChildElements(self, dictKV):
        for key, value in dictKV.items():
            self.AddChildElement(key, value)

xmlfile_path = "1.xml"
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

def AddItem(taskgroup, dictKV, dictAttr):
	for taskitem in taskgroup.findall("TaskItem"):
		for taskparam in taskitem.iter("TaskParam"):
			yzfitem = YzfItem()
			yzfitem.SetAttrs(dictAttr)
			yzfitem.AddChildElements(dictKV)
			taskparam.append(yzfitem.item)
			return True
	return False


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

		
root = ET.fromstring(xml_text)
TaskXMLTree = ET.ElementTree(element=root)
taskgroups = root.findall("CompanyTask/TaskList/TaskGroup")
for taskgroup in taskgroups:
	if taskgroup.attrib["id"] != "HB_BASE_INFO":
		continue

	RemoveAllTaskParam(taskgroup)
	AddTaskParam(taskgroup)
	'''
	for taskitem in taskgroup.findall("TaskItem"):
		for taskparam in taskitem.findall("TaskParam"):
			for item in taskparam.iter("Item"):
				taskparam.remove(item)
	'''

		
TaskXMLTree.write("2.xml", encoding="UTF-8", xml_declaration=True)
	
	
