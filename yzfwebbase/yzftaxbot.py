# -*- coding:utf-8 -*-
import sys
import time
import logging
import yzfxml
import collections
import yzfbrowser
from selenium.webdriver.support import select
from PIL import Image, ImageDraw, ImageFont
import datetime
import base64
from functools import wraps
import yzfargv


class YzfSelect:
    def __init__(self, selector_str):
        self.selector = selector_str
        self.frame_id_list = analyze_element_frames(selector_str)[0]

    def select_by_visible_text(self, visible_text_str):
        for frame_id in self.frame_id_list:
            YzfBrowser.switch_to.frame(frame_id)

        select.Select(YzfBrowser.find_element_by_css_selector(self.selector)).select_by_visible_text(visible_text_str)

        for _ in self.frame_id_list:
            YzfBrowser.switch_to.parent_frame()



class YzfFlowRow:
    def __init__(self):
        self.data = collections.OrderedDict()


class YzfFloatRows:
    def __init__(self):
        self.data = collections.OrderedDict()

    def get_cell_list(self, float_attr_str, row_attr_str):
        return self.data[float_attr_str].data[row_attr_str]

    def delete_row(self, float_attr_str, row_attr_str):
        del self.data[float_attr_str].data[row_attr_str]

    def cell_list(self):
        for float_attr_str, row in self.data.items():
            for row_attr_str, cell_list in row.data.items():
                yield (float_attr_str, row_attr_str, cell_list)

    def delete_rows_with_cell_contains_attr_str_equal(self, attr_name_str="", attr_value_str="", text_str=""):
        float_row_tupple_list = []
        for float_attr, v in self.data.items():
            for row_attr, cell_list in v.data.items():
                for cell in cell_list:
                    if cell.get_attr_value(attr_name_str) != attr_value_str:
                        continue

                    if cell.get_text() == text_str:
                        float_row_tupple_list.append((float_attr, row_attr))

                    break

        for (float_attr, row_attr) in float_row_tupple_list:
            print(float_attr, row_attr)
            del self.data[float_attr].data[row_attr]

    def yhs_filter_declarable_rows(self, attr_name_str="", attr_value_str="", text_str=""):
        """
        印花税专用，删除所有"适用税率"非0的行
        :param attr_name_str:
        :param attr_value_str:
        :param text_str:
        :return:
        """
        self.delete_rows_with_cell_contains_attr_float_equal(attr_name_str, attr_value_str, text_str)

    def delete_rows_with_cell_contains_attr_float_equal(self, attr_name_str="", attr_value_str="", text_str="0.0"):
        """
        删除包含单元格的浮动行。单元格满足以下条件：
        1. 单元格的属性attr_name_str的值是attr_value_str
        2. 单元格的文本等于text_str(按照浮点数比较)

        :param attr_name_str: 单元格属性名字符串
        :param attr_value_str:  单元格属性值字符串
        :param text_str:  单元格文本（值）
        :return:
        """
        float_row_tupple_list = []
        for float_attr, v in self.data.items():
            for row_attr, cell_list in v.data.items():
                for cell in cell_list:
                    if cell.get_attr_value(attr_name_str) != attr_value_str:
                        continue

                    if YzfFloat(cell.get_text()).equal(YzfFloat(text_str)):
                        float_row_tupple_list.append((float_attr, row_attr))

                    break

        for (float_attr, row_attr) in float_row_tupple_list:
            print(float_attr, row_attr)
            del self.data[float_attr].data[row_attr]


class YzfFloat:
    def __init__(self, float_str):
        self.data = float_str

    def value(self):
        return float(self.data)

    def is_zero(self):
        f = float(self.data)
        return abs(f) < 1e-6

    def equal(self, yzf_float, precision=1e-6):
        assert isinstance(yzf_float, YzfFloat)
        return abs(self.value() - yzf_float.value()) <= precision


class YzfTableData:
    def __init__(self):
        self.Selector = ""
        self.Text = ""


class YzfTableRow:
    def __init__(self):
        self.Selector = ""
        self.TableDataList = []

    def tds(self):
        for td in self.TableDataList:
            yield td


class YzfTbody:
    def __init__(self):
        self.Selector = ""
        self.TableRowList = []

    def set_selector(self, selector_str):
        self.Selector = selector_str

    def get_selector(self):
        return self.Selector

    def rows(self):
        for row in self.TableRowList:
            yield row

    def trim(self):
        """
        把格子数据的前空白符和后空白符删除。例如，如果格子的文本是" 税种 ", 结果是"税种"
        :return:
        """
        for row in self.TableRowList:
            for td in row.TableDataList:
                td.Text = td.Text.strip()

    def query_row_contains(self, text_str=""):
        yzf_tbody = YzfTbody()
        result_rows = []
        for row in self.TableRowList:
            for td in row.TableDataList:
                if td.Text.find(text_str) != -1:
                    result_rows.append(row)
                    break

        yzf_tbody.Selector = self.Selector
        yzf_tbody.TableRowList = result_rows
        return yzf_tbody

    def query_row_contains_in_nth_column(self, text_str, nth_col_int):
        """
        在表中查询第nth_col_int列包含文本text_str的行
        :param text_str: 要查的字符串
        :param nth_col_int: 第几列，从0开始数
        :return: 新的YzfTbody对象
        """
        yzf_tbody = YzfTbody()
        result_rows = []
        for row in self.TableRowList:
            if len(row.TableDataList) <= nth_col_int:
                continue

            if row.TableDataList[nth_col_int].Text.find(text_str) != -1:
                result_rows.append(row)

        yzf_tbody.Selector = self.Selector
        yzf_tbody.TableRowList = result_rows
        return yzf_tbody

    def query_row_equal_in_nth_column(self, text_str, nth_col_int):
        """
        在表中查询第nth_col_int列文本等于text_str的行
        :param text_str: 要查的字符串
        :param nth_col_int: 第几列，从0开始数
        :return: 新的YzfTbody对象
        """
        yzf_tbody = YzfTbody()
        result_rows = []
        for row in self.TableRowList:
            if len(row.TableDataList) <= nth_col_int:
                continue

            if row.TableDataList[nth_col_int].Text == text_str:
                result_rows.append(row)

        yzf_tbody.Selector = self.Selector
        yzf_tbody.TableRowList = result_rows
        return yzf_tbody

class YzfGroupResult:
    def __init__(self, group_result_ordered_dict):
        assert isinstance(group_result_ordered_dict, collections.OrderedDict)
        self.__data = group_result_ordered_dict

    def set_result_code(self, str_code):
        self.set_result_code_text(str_code)

    def set_result_code_text(self, str_code):
        self.__data["ResultCode"] = str_code

    def set_result_desc_type(self, str_type):
        if "ResultDesc" not in self.__data:
            self.__data["ResultDesc"] = collections.OrderedDict()

        if not isinstance(self.__data["ResultDesc"], collections.OrderedDict):
            self.__data["ResultDesc"] = collections.OrderedDict()

        self.__data["ResultDesc"]["@type"] = str_type

    def set_result_desc(self, str_text):
        self.set_result_desc_text(str_text)

    def set_result_desc_text(self, str_text):
        if "ResultDesc" not in self.__data:
            self.__data["ResultDesc"] = collections.OrderedDict()

        if not isinstance(self.__data["ResultDesc"], collections.OrderedDict):
            self.__data["ResultDesc"] = collections.OrderedDict()

        self.__data["ResultDesc"]["#text"] = str_text


class Cell:
    def __init__(self, cell_ordered_dict, str_tag):
        assert isinstance(cell_ordered_dict, collections.OrderedDict)
        self.__data = cell_ordered_dict
        self.Tag = str_tag

    def is_blank_cell(self):
        return self.__is_cell_with_tag("BlankCell")

    def is_verify_cell(self):
        return self.__is_cell_with_tag("VerifyCell")

    def is_edit_cell(self):
        return self.__is_cell_with_tag("EditCell")

    def is_confirm_cell(self):
        return self.__is_cell_with_tag("ConfirmCell")

    def is_write_cell(self):
        return self.__is_cell_with_tag("WriteCell")

    def __is_cell_with_tag(self, tag_str=""):
        return self.Tag.upper() == tag_str.upper()

    def tag(self):
        return self.Tag

    def set_text(self, str_text):
        self.__data["#text"] = str_text

    def get_text(self):
        return self.text()

    def text(self):
        try:
            return self.__data["#text"]
        except Exception as e:
            return ""

    def set_attr_value(self, str_attr_name, str_attr_value):
        self.__data["@" + str_attr_name] = str_attr_value

    def get_attr_value(self, str_attr_value):
        return self.__data["@" + str_attr_value] if self.attr_exists(str_attr_value) else ""

    def attr_exists(self, str_attr_name):
        return ("@" + str_attr_name) in self.__data

    def is_float_cell(self):
        return "@float" in self.__data or "@float_f" in self.__data

    def float_attr(self):
        if "@float" in self.__data:
            return self.__data["@float"]

        if "@float_f" in self.__data:
            return self.__data["@float_f"]

        return ""

    def row_attr(self):
        if "@row" in self.__data:
            return self.__data["@row"]

        return ""

class YzfItem:
    def __init__(self, item_ordered_dict):
        assert isinstance(item_ordered_dict, collections.OrderedDict)
        self.__dict__["__data"] = item_ordered_dict

    def __setattr__(self, key, value):
        self.__dict__["__data"][key] = value

    def __getattr__(self, item):
        try:
            return self.__dict__["__data"][item]
        except Exception as e:
            return None


class YzfTaskParam:
    def __init__(self, task_param_ordered_dict):
        assert isinstance(task_param_ordered_dict, collections.OrderedDict)
        self.__dict__["__data"] = task_param_ordered_dict
        self.BlankCellList = self.parse_cell_list("BlankCell")
        self.VerifyCellList= self.parse_cell_list("VerifyCell")
        self.EditCellList = self.parse_cell_list("EditCell")
        self.ConfirmCellList = self.parse_cell_list("ConfirmCell")
        self.WriteCellList = self.parse_cell_list("WriteCell")
        self.ItemList = self.parse_item_list()
        self.StableCellList = []
        self.FloatRowDict = self.parse_float_row_dict()


    def parse_float_row_dict(self):
        all_cell_list = self.BlankCellList
        all_cell_list.extend(self.VerifyCellList)
        all_cell_list.extend(self.EditCellList)
        all_cell_list.extend(self.ConfirmCellList)
        all_cell_list.extend(self.WriteCellList)
        # yzf_float_rows.data is a dict, key is float_attr
        # yzf_float_rows.data[float_attr] is a dict, key is row_attr
        # yzf_float_rows.data[float_attr].data[row_attr] is a list, element is cell
        yzf_float_rows = YzfFloatRows()

        for cell in all_cell_list:
            if not cell.is_float_cell():
                self.StableCellList.append(cell)

            if cell.float_attr() not in yzf_float_rows.data:
                yzf_float_rows.data[cell.float_attr()] = YzfFlowRow()

            if cell.row_attr() not in yzf_float_rows.data[cell.float_attr()].data:
                yzf_float_rows.data[cell.float_attr()].data[cell.row_attr()] = []

            yzf_float_rows.data[cell.float_attr()].data[cell.row_attr()].append(cell)

        return yzf_float_rows

    def _delete_sub_elements_by_tag(self, str_tag):
        if str_tag in self.__dict__["__data"]:
            del self.__dict__["__data"][str_tag]
        if str_tag + "List" in self.__dict__:
            del self.__dict__[str_tag + "List"]

    def add_sub_element(self, tag="tag", value="value", **attrs):
        if tag == "Item":
            if tag not in self.__dict__["__data"]:
                self.__dict__["__data"][tag] = [collections.OrderedDict()]
            elif isinstance(self.__dict__["__data"][tag], collections.OrderedDict):
                orig_dict = self.__dict__["__data"][tag]
                self.__dict__["__data"][tag] = [orig_dict]
                self.__dict__["__data"][tag].append(collections.OrderedDict())
            elif isinstance(self.__dict__["__data"][tag], list):
                self.__dict__["__data"][tag].append(collections.OrderedDict())
            self.__dict__["__data"][tag][-1]["#text"] = value
            for k, v in attrs.items():
                self.__dict__["__data"][tag][-1]["@" + k] = v

            self.ItemList = self.parse_item_list()
            return self.ItemList[-1]
        else:
            raise Exception("不支持的Tag类型" + tag)

    def delete_sub_elements_by_tag(self, str_tag):
        supported_list = ["BlankCell", "VerifyCell", "EditCell", "ConfirmCell", "WriteCell", "Item"]
        if str_tag not in supported_list:
            raise Exception("不支持的参数" + str_tag + ". 只支持删除" + ",".join(supported_list))
        self._delete_sub_elements_by_tag(str_tag)

    def parse_item_list(self):
        str_tag = "Item"
        if str_tag not in self.__dict__["__data"]:
            return []

        if isinstance(self.__dict__["__data"][str_tag], list):
            return [YzfItem(item) for item in self.__dict__["__data"][str_tag]]
        elif isinstance(self.__dict__["__data"][str_tag], collections.OrderedDict):
            return [YzfItem(self.__dict__["__data"][str_tag])]
        else:
            raise Exception("解析TaskParam中的" + str_tag + "出现类型错误")

    def parse_cell_list(self, str_tag):
        if str_tag not in self.__dict__["__data"]:
            return []

        if isinstance(self.__dict__["__data"][str_tag], list):
            return [Cell(cell, str_tag) for cell in self.__dict__["__data"][str_tag]]
        elif isinstance(self.__dict__["__data"][str_tag], collections.OrderedDict):
            return [Cell(self.__dict__["__data"][str_tag], str_tag)]
        else:
            raise Exception("解析TaskParam中的" + str_tag + "出现类型错误")

    def __setattr__(self, key, value):
        if key in ["BlankCellList", "VerifyCellList", "EditCellList", "ConfirmCellList", "WriteCellList", "ItemList", "FloatRowDict", "StableCellList"]:
            self.__dict__[key] = value
        else:
            self.__dict__["__data"][key] = value

    def __getattr__(self, attr):
        try:
            return self.__dict__["__data"][attr]
        except Exception as e:
            return None


class YzfTaskItem:
    def __init__(self, task_item_ordered_dict):
        assert isinstance(task_item_ordered_dict, collections.OrderedDict)
        self.__data = task_item_ordered_dict
        if self.__data["TaskParam"] is None:
            self.__data["TaskParam"] = collections.OrderedDict()
        self.TaskParam = YzfTaskParam(self.__data["TaskParam"])

    def id(self):
        return self.get_attr("id")

    def nsqxdm(self):
        return self.get_attr("nsqxdm")

    def get_attr(self, attr_str):
        return self.__data["@" + attr_str]

    def get_attr_value(self, attr_str):
        return self.get_attr(attr_str)


class YzfTaskGroup:
    def __init__(self, task_group_ordered_dict):
        """
        :param task_group_ordered_dict: 类型是collections.OrderedDict的对象
        """
        self.__data = None
        self.GroupResult = None
        self.TaskItemList = None
        assert isinstance(task_group_ordered_dict, collections.OrderedDict)
        if len(task_group_ordered_dict) == 0:
            return
        self.__data = task_group_ordered_dict
        self.GroupResult = YzfGroupResult(self.__data["GroupResult"])
        self.TaskItemList = self.parse_taskitem_list()

    def get_task_item_by_attrs(self, **args):
        for task_item in self.TaskItemList:
            for k, v in args.items():
                if task_item.get_attr_value(k) != v:
                    break
            else:
                return task_item

    def get_task_item_by_id(self, id_str=""):
        return self.get_task_item_by_attrs(id=id_str)

    def parse_taskitem_list(self):
        if isinstance(self.__data["TaskItem"], list):
            return [YzfTaskItem(item) for item in self.__data["TaskItem"]]
        elif isinstance(self.__data["TaskItem"], collections.OrderedDict):
            return [YzfTaskItem(self.__data["TaskItem"])]
        else:
            raise Exception("解析TaskList中的TaskItem出现类型错误")

    def id(self):
        return self.get_attr_value("id")

    def get_id(self):
        return self.id()

    def type(self):
        return self.get_attr_value("type")

    def get_type(self):
        return self.type()

    def ssqs(self):
        return self.get_attr_value("ssqs")

    def get_ssqs(self):
        return self.ssqs()

    def ssqz(self):
        return self.get_attr_value("ssqz")

    def get_ssqz(self):
        return self.ssqz()

    def get_attr_value(self, str_attr_name):
        return self.__data["@" + str_attr_name]

    def set_attr_value(self, str_attr_name, str_attr_value):
        self.__data["@" + str_attr_name] = str_attr_value

    def notify_done_with_screen_shot(self, error_code="", error_msg="测试"):
        self.GroupResult.set_result_code(error_code)
        self.GroupResult.set_result_desc_type("PNG")
        self.GroupResult.set_result_desc_text(get_window_png_as_base64(error_msg))

    def notify_done(self, error_code="", error_msg=""):
        self.GroupResult.set_result_code(error_code)
        self.GroupResult.set_result_desc_type("STRING")
        self.GroupResult.set_result_desc_text(error_msg)


class YzfCompanyInfo:
    def __init__(self, company_info_ordered_dict):
        assert isinstance(company_info_ordered_dict, collections.OrderedDict)
        self.__data = company_info_ordered_dict

    def __getattr__(self, item):
        try:
            return self.__data[item]
        except Exception as e:
            raise Exception("在CompanyInfo中没有找到tag为"+item+"的子结点")

    def get_text_by_tag(self, str_tag):
        return self.__data[str_tag]


class YzfBaseInfo:
    def __init__(self, base_info_ordered_dict):
        assert isinstance(base_info_ordered_dict, collections.OrderedDict)
        self.__dict__["__data"] = base_info_ordered_dict

    # TODO 重复代码，考虑提取形成基类
    def __getattr__(self, item):
        try:
            return self.__dict__["__data"][item]
        except Exception as e:
            raise Exception("此BaseInfo中没有找到tag为"+item+"的子结点")

    def __setattr__(self, key, value):
        self.__dict__["__data"][key] = value


class YzfTaskList:
    def __init__(self, task_list_ordered_dict):
        assert isinstance(task_list_ordered_dict, collections.OrderedDict)
        self.__data = task_list_ordered_dict
        self.BaseInfo = self.get_base_info()
        self.TaskGroupList = self.parse_taskgroup_list()

    def get_base_info(self):
        return YzfBaseInfo(self.__data["BaseInfo"])

    def get_task_group(self, str_type, str_id):
        return YzfTaskGroup(self.__data)

    def task_groups(self):
        for task_group in self.TaskGroupList:
            yield task_group

    def parse_taskgroup_list(self):
        if isinstance(self.__data["TaskGroup"], list):
            return [YzfTaskGroup(tg) for tg in self.__data["TaskGroup"]]
        elif isinstance(self.__data["TaskGroup"], collections.OrderedDict):
            return [YzfTaskGroup(self.__data["TaskGroup"])]
        else:
            raise Exception("解析TaskList中的TaskGroup出现类型错误")


class YzfCompanyTask:
    def __init__(self, company_task_ordered_dict):
        assert isinstance(company_task_ordered_dict, collections.OrderedDict)
        self.__data = company_task_ordered_dict
        self.CompanyInfo = self.get_company_info()
        self.TaskList = self.get_task_list()

    def get_company_info(self):
        return YzfCompanyInfo(self.__data["CompanyInfo"])

    def get_task_list(self):
        return YzfTaskList(self.__data["TaskList"])


class YzfTaxBot:
    def __init__(self):
        self.GoToMainPageFunc = YzfTaxBot.go_to_main_page
        self.TaskFuncMap = dict() # TaskGroup处理函数字典:TaskFuncMap[type][Id]
        self.TaskFuncMaxTryMap = dict()
        self.LoginTaskFunc = None
        self.LoginTaskMaxTry = 1
        self.Xml = yzfxml.YzfXml(yzfargv.INPUT_XML_PATH)  # 基于xmltodict生成的对象的封装
        self.XmlDoc = self.Xml.xmldoc  # xmltodict生成的对象
        self.CompanyTask = YzfCompanyTask(self.Xml.xmldoc["ExchangeData"]["CompanyTask"])  # 客户端收到的XML里有且只有一个CompanyTask
        self.CompanyInfo = self.CompanyTask.CompanyInfo
        self.TaskList = self.CompanyTask.TaskList # 客户端收到的XML里有且只有一个TaskList
        self.BaseInfo = self.TaskList.BaseInfo
        self.TaskGroupList = self.TaskList.TaskGroupList

    def get_task_group_by_id(self, group_id_str):
        for task_group in self.TaskGroupList:
            if task_group.id() == group_id_str:
                return task_group
        return None

    def get_task_group_by_id_type(self, group_id_str, group_type_str):
        for task_group in self.TaskGroupList:
            if task_group.id() == group_id_str and task_group.type() == group_type_str:
                return task_group

        return None

    @staticmethod
    def go_to_main_page(self):
        """
        默认的返回首页函数，什么都不做
        :param self: YzfTaxBot类型的对象
        :return:
        """
        pass

    def register_login_task(self, func_name, max_try=1):
        """
        :param func_name: 登录函数。此函数必须接受一个参数，参数类型是YzfTaxBot
        :param max_try: 试几次，默认值是1，即出错就返回
        :return: 正常不返回值，异常时抛异常
        """
        logging.info("")
        self.LoginTaskFunc = func_name
        self.LoginTaskMaxTry = max_try

    def register_go_to_main_page(self, func_name):
        """
        :param func_name: 返回首页函数。此函数必须接受一个参数，参数类型是YzfTaxBot
        :return: 正常不返回值，异常时抛异常
        """
        self.GoToMainPageFunc = func_name

    def register_task_group(self, str_type, str_id, func_name, max_try=1):
        """
        :param str_type: 任务类型
        :param str_id: 任务ID
        :param func_name: 函数。此函数必须接受两个参数，第一个是YzfTaxBot的对象，第二个是YzfTaskGroup类型的对象
        :param max_try: 最大重试次数，默认值为1，即出错就返回
        :return: 正常不返回值，异常时抛异常
        """
        if str_type not in self.TaskFuncMap:
            self.TaskFuncMap[str_type] = dict()
            self.TaskFuncMaxTryMap[str_type] = dict()

        self.TaskFuncMap[str_type][str_id] = func_name
        self.TaskFuncMaxTryMap[str_type][str_id] = max_try

    def run(self):
        """
        1. 执行登录任务函数
        2. 执行其他任务函数
        :return:
        """
        if self.LoginTaskFunc is None:
            logging.error("没有注册登录任务处理函数")
            raise Exception("没有注册登录任务处理函数")

        login_try_times = 0
        while self.LoginTaskMaxTry:
            self.LoginTaskMaxTry = self.LoginTaskMaxTry - 1
            login_try_times += 1
            logging.info("第" + str(login_try_times) + "次运行登录函数")
            try:
                self.LoginTaskFunc()
                break  # 登录函数正常退出，break跳出while循环
            except Exception as e:
                debug_str = str(e)
                logging.exception(e)
                if self.LoginTaskMaxTry == 0:
                    raise e  # 重试次数用完，向外层抛异常
                else:
                    pass

        for task_group in self.TaskGroupList:
            if task_group.type() not in self.TaskFuncMap:
                raise Exception("不支持任务type:" + task_group.type())

            if task_group.id() not in self.TaskFuncMap[task_group.type()]:
                raise Exception("任务type" + task_group.type() + "不支持任务ID:" + task_group.id())

            task_func_try_times = 0
            while self.TaskFuncMaxTryMap[task_group.type()][task_group.id()]:
                self.TaskFuncMaxTryMap[task_group.type()][task_group.id()] = self.TaskFuncMaxTryMap[task_group.type()][task_group.id()] - 1
                try:
                    task_func_try_times += 1
                    logging.info("第" + str(task_func_try_times) + "次执行任务（任务type=" + task_group.type() + ", 任务id=" + task_group.id() + "）")
                    global TaskGroup
                    TaskGroup = task_group
                    self.TaskFuncMap[task_group.type()][task_group.id()]()
                    break  # 任务函数正常退出，break跳出while循环
                except Exception as e:
                    logging.exception(e)
                    if self.TaskFuncMaxTryMap[task_group.type()][task_group.id()] == 0:
                        raise e  # TODO 重试次数用完，设置Task
                    else:
                        self.GoToMainPageFunc(self)
                        pass

        self.Xml.save()


MyBot = YzfTaxBot()
TaskGroup = YzfTaskGroup(collections.OrderedDict())
YzfBrowser = yzfbrowser.MyBrowser.GetBrowser()
ImplicitWaitTimeout = 10


def __analyze_element_frames(element_css_selector, tmp_frame_id_list, frame_id_list_list):
    ele_sel = element_css_selector
    frames = YzfBrowser.find_elements_by_tag_name("iframe")

    elements = YzfBrowser.find_elements_by_css_selector(ele_sel)
    if len(elements) > 1:
        raise Exception("找到" + str(len(elements)) + "个" + element_css_selector)

    if len(elements) == 1:
        frame_id_list_list.append(tmp_frame_id_list[:])
        print("找到1个" + ele_sel + ", " + ",".join(tmp_frame_id_list))

    for frame in frames:
        frame_id = frame.get_attribute("id")
        tmp_frame_id_list.append(frame_id)
        YzfBrowser.switch_to.frame(frame_id)
        __analyze_element_frames(element_css_selector, tmp_frame_id_list, frame_id_list_list)
        YzfBrowser.switch_to.parent_frame()
        tmp_frame_id_list.pop()


def _analyze_element_frames(element_css_selector, frame_id_list_list):
    tmp_frame_id_list = []
    __analyze_element_frames(element_css_selector, tmp_frame_id_list, frame_id_list_list)


def analyze_element_frames(element_css_selector):
    YzfBrowser.implicitly_wait(0)
    frame_id_list_list = []
    _analyze_element_frames(element_css_selector, frame_id_list_list)
    YzfBrowser.implicitly_wait(ImplicitWaitTimeout)
    return frame_id_list_list


def find_elements_by_selector(selector_str):
    frame_id_list_list = analyze_element_frames(selector_str)
    elements = []
    for frame_id_list in frame_id_list_list:
        for frame_id in frame_id_list:
            YzfBrowser.switch_to.frame(frame_id)
        elements.extend(YzfBrowser.find_elements_by_css_selector(selector_str))
        for _ in frame_id_list:
            YzfBrowser.switch_to.parent_frame()

    return elements


def find_element_by_selector(selector_str, index_int=-1, exception_str=""):
    element_list = find_elements_by_selector(selector_str)
    if index_int == -1:
        if len(element_list) == 1:
            return element_list[0]
        elif len(element_list) == 0:
            raise Exception("没有找到" + selector_str)
        elif len(element_list) > 1:
            raise Exception("找到多个" + selector_str)
    else:
        if index_int >= len(element_list):
            raise Exception("下标越界。找到" + str(len(element_list)) + "个" + selector_str + "。下标必须小于" + str(len(element_list)))

        return element_list[index_int]


def auto_switch_frame(func):
    def wrapper(selector_str):
        frame_id_list_list = analyze_element_frames(selector_str)

        if len(frame_id_list_list) != 1:
            raise Exception("找到" +str(len(frame_id_list_list)) + "个" + selector_str)

        for frame_id in frame_id_list_list[0]:
            YzfBrowser.switch_to.frame(frame_id)

        ret = None
        try:
            ret = func(selector_str)
        except Exception as e:
            logging.exception(e)
            raise e
        finally:
            for _ in frame_id_list_list[0]:
                YzfBrowser.switch_to.parent_frame()

        return ret
    return wrapper


@auto_switch_frame
def get_text_by_selector(selector_str):
    return YzfBrowser.find_element_by_css_selector(selector_str).text


def js_click_selector(selector_str, index_int=-1, exception_str=""):
    """
    :param selector_str:
    :param index_int:
        如果是-1：
            如果找到1个，OK，正常操作
            如果找到多个，异常
        如果不是-1：
            如果越界，异常
            否则OK，正常操作

    :param exception_str:
    :return:
    """
    frame_id_list_list = analyze_element_frames(selector_str)
    if index_int == -1:
        if len(frame_id_list_list) != 1:
            raise Exception("找到" +str(len(frame_id_list_list)) + "个" + selector_str)

        for frame_id in frame_id_list_list[0]:
            YzfBrowser.switch_to.frame(frame_id)
        YzfBrowser.execute_script("document.querySelector(\"" + selector_str + "\").click()")
        for _ in frame_id_list_list[0]:
            YzfBrowser.switch_to.parent_frame()
    else:
        if index_int >= len(frame_id_list_list):
            raise Exception("越界。查找"+selector_str+"时，共找到" + str(len(frame_id_list_list)) + "个")

        for frame_id in frame_id_list_list[index_int]:
            YzfBrowser.switch_to.frame(frame_id)
        YzfBrowser.execute_script("document.querySelector(\"" + selector_str + "\").click()")
        for _ in frame_id_list_list[index_int]:
            YzfBrowser.switch_to.parent_frame()


def click_selector(selector_str, index_int=-1, exception_str=""):
    """
    :param selector_str:
    :param index_int:
        如果是-1：
            如果找到1个，OK，正常操作
            如果找到多个，异常
        如果不是-1：
            如果越界，异常
            否则OK，正常操作

    :param exception_str:
    :return:
    """
    frame_id_list_list = analyze_element_frames(selector_str)
    if index_int == -1:
        if len(frame_id_list_list) != 1:
            raise Exception("找到" +str(len(frame_id_list_list)) + "个" + selector_str)

        for frame_id in frame_id_list_list[0]:
            YzfBrowser.switch_to.frame(frame_id)
        YzfBrowser.find_element_by_css_selector(selector_str).click()
        for _ in frame_id_list_list[0]:
            YzfBrowser.switch_to.parent_frame()
    else:
        if index_int >= len(frame_id_list_list):
            raise Exception("越界。查找"+selector_str+"时，共找到" + str(len(frame_id_list_list)) + "个")

        for frame_id in frame_id_list_list[index_int]:
            YzfBrowser.switch_to.frame(frame_id)
        YzfBrowser.find_element_by_css_selector(selector_str).click()
        for _ in frame_id_list_list[index_int]:
            YzfBrowser.switch_to.parent_frame()


def click_xpath(xpath_str, index_int=-1, exception_str=""):
    pass

def read_tbody_by_xpath(tbody_selector, tr="tr"):
    table = YzfBrowser.find_element_by_xpath(tbody_selector)
    time.sleep(1)
    table_rows = table.find_elements_by_tag_name(tr)
    time.sleep(1)
    arr = []
    list = []
    for i in table_rows:
        list = i.text.split(" ")
        arr.append(list)

    return arr

def read_tbody(tbody_selector_str, tr="tr", td="td"):
    yzf_tbody = YzfTbody()
    frame_id_list_list = analyze_element_frames(tbody_selector_str)

    if len(frame_id_list_list) == 0:
        raise Exception("没有找到元素" + tbody_selector_str)

    if len(frame_id_list_list) > 1:
        raise Exception("找到" + str(len(frame_id_list_list)) + "个表" + tbody_selector_str)

    frame_id_list = frame_id_list_list[0]

    for frame_id in frame_id_list:
        YzfBrowser.switch_to.frame(frame_id)

    tr_list = YzfBrowser.find_elements_by_css_selector(tbody_selector_str + " > " + tr)
    tr_index = 1
    tr_index_list = []

    while len(tr_index_list) != len(tr_list):
        tr_selector = tbody_selector_str + " > " + tr + ":nth-child(" + str(tr_index) + ")"
        #print(tr_selector)
        if YzfBrowser.find_elements_by_css_selector(tr_selector):
            tr_index_list.append(tr_index)
        tr_index = tr_index + 1

    for tr_index in tr_index_list:
        tr_selector = tbody_selector_str + " > " + tr + ":nth-child(" + str(tr_index) + ")"
        td_list = YzfBrowser.find_elements_by_css_selector(tr_selector + " > " + td)
        td_index_list = []
        td_index = 1
        while len(td_index_list) != len(td_list):
            td_selector = tr_selector + " > " + td + ":nth-child(" + str(td_index) + ")"
            #print(td_selector)
            if YzfBrowser.find_elements_by_css_selector(td_selector):
                td_index_list.append(td_index)

            td_index = td_index + 1

        yzf_tr = YzfTableRow()
        yzf_tr.Selector = tr_selector
        for td_index in td_index_list:
            td_selector = tr_selector + " > " + td + ":nth-child(" + str(td_index) + ")"
            yzf_td = YzfTableData()
            yzf_td.Selector = td_selector
            yzf_td.Text = YzfBrowser.find_element_by_css_selector(td_selector).text
            yzf_tr.TableDataList.append(yzf_td)

        yzf_tbody.TableRowList.append(yzf_tr)

    for _ in frame_id_list:
        YzfBrowser.switch_to.parent_frame()

    return yzf_tbody


def switch_to_url(str_url):
    for i in range(len(YzfBrowser.window_handles)):
        YzfBrowser.switch_to.window(YzfBrowser.window_handles[i])
        if str_url in YzfBrowser.current_url:
            return True

    raise Exception("切换URL失败：" + str_url)


def switch_to_last_window():
    YzfBrowser.switch_to.window(YzfBrowser.window_handles[-1])


def save_page_source_to(file_name):
    content = YzfBrowser.page_source
    open(file_name, "w", encoding="utf-8").write(content)


def notify_done(error_code="", error_msg_str=""):
    TaskGroup.notify_done(error_code, error_msg_str)


def notify_done_with_screen_shot(error_code="", error_msg_str="测试"):
    TaskGroup.notify_done_with_screen_shot(error_code, error_msg_str)


def get_window_png_as_base64(message_str=""):
    YzfBrowser.get_screenshot_as_file("tmp.png")
    img = Image.open("tmp.png")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("STFANGSO.TTF", 36)
    draw.text((0, 0), message_str, (255, 0, 0), font=font)
    timestamp = str(datetime.datetime.now())
    font = ImageFont.truetype("STFANGSO.TTF", 26)
    draw.text((img.width / 2, img.height - 50), timestamp, (255, 0, 0), font=font)
    img.save('tmp1.png')
    with open('tmp1.png', 'rb') as pngfile:
        return base64.b64encode(pngfile.read()).decode()


def float_row_cell_list():
    for task_item in TaskGroup.TaskItemList:
        for (float_attr_str, row_attr_str, cell_list) in task_item.TaskParam.FloatRowDict.cell_list():
            yield (float_attr_str, row_attr_str, cell_list)


def blank_cell_lists():
    return cell_lists("BlankCell")


def edit_cell_lists():
    return cell_lists("EditCell")


def verify_cell_lists():
    return cell_lists("VerifyCell")


def confirm_cell_lists():
    return cell_lists("ConfirmCell")


def write_cell_lists():
    return cell_lists("WriteCell")


def cell_lists(cell_tag_str="BlankCell"):
    cell_tag_upper = cell_tag_str.upper()
    for task_item in TaskGroup.TaskItemList:
        if cell_tag_upper == "BLANKCELL":
            yield task_item.TaskParam.BlankCellList
        elif cell_tag_upper == "EDITCELL":
            yield task_item.TaskParam.EditCellList
        elif cell_tag_upper == "VERIFYCELL":
            yield task_item.TaskParam.VerifyCellList
        elif cell_tag_upper == "CONFIRMCELL":
            yield task_item.TaskParam.ConfirmCellList
        elif cell_tag_upper == "WRITECELL":
            yield task_item.TaskParam.WriteCellList
        else:
            raise Exception("不支持的单元格类型" + cell_tag_str)


def all_cell_lists():
    for task_item in TaskGroup.TaskItemList:
        yield (task_item.TaskParam.BlankCellList, task_item.TaskParam.VerifyCellList, task_item.TaskParam.ConfirmCellList, task_item.TaskParam.EditCellList, task_item.TaskParam.WriteCellList)


def max_try(tries=5):
    """
    :param tries: 最多重试的次数。默认5次
    :return:
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            max_try_times = tries
            while max_try_times:
                max_try_times = max_try_times - 1
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    if max_try_times == 0:
                        raise e
                    logging.info("忽略一次调用异常" + str(e))
                    time.sleep(1)
        return wrapper
    return decorator


@max_try(5)
def maximize_browser_window():
    YzfBrowser.maximize_window()


if __name__ == '__main__':
    """测试代码"""
    import sys
    sys.argv.append("E:\\InterfaceSystem3\\Jsgds\\bin\\Debug\\PutDataTask2.xml")
    mybot = YzfTaxBot()
    mybot.run()

