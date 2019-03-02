# -*- coding:utf-8 -*-
import sys
import os
import xmltodict


class YzfXml:
    def __init__(self, xml_file_path):
        self.xml_file_path = xml_file_path
        self.xmldoc_fd = open(xml_file_path, encoding='utf-8')
        self.xmldoc = xmltodict.parse(self.xmldoc_fd.read())

    def save(self):
        out = xmltodict.unparse(self.xmldoc, pretty=True)
        with open(self.xml_file_path, 'wb') as file:
            file.write(out.encode('utf-8'))

    def get_task_group(self, str_type, str_id):
        pass





def GetTaskGroupDict(taskgroupid):
    global doc
    global taskGroup
    with open("PutDataTask.xml", encoding='utf-8') as fd:
        doc = xmltodict.parse(fd.read())
        taskGroups = doc["ExchangeData"]["CompanyTask"]["TaskList"]["TaskGroup"]

        index = 0
        try:
            if '@id' in taskGroups.keys():
                if taskGroups['@id'] == taskgroupid:
                    taskGroup = taskGroups
        except Exception as e:
            while index < len(taskGroups):
                if taskGroups[index]['@id'] == taskgroupid:
                    taskGroup = taskGroups[index]
                break
            else:
                index = index + 1
        return taskGroup

def GetSaveXML():
    out = xmltodict.unparse(doc, pretty=True)

    with open("PutDataTask.xml", 'wb') as file:
        file.write(out.encode('utf-8'))

    return



