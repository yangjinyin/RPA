# -*- coding:utf-8 -*-
import yzflogging
import logging
import time
import yzftaxbot
import cj_base_info
from yzftaxbot import MyBot, YzfBrowser, switch_to_url, switch_to_last_window, save_page_source_to, TaskGroup, analyze_element_frames, click_selector, click_xpath, read_tbody


def main():
    task_group = yzftaxbot.TaskGroup
    print(cj_base_info.test)

    task_group.TaskItemList[0].TaskParam.delete_sub_elements_by_tag("Item")
    item = task_group.TaskItemList[0].TaskParam.add_sub_element("Item", "", type="JDXX")
    item.zspm = "zspm test 2"

    item = task_group.TaskItemList[0].TaskParam.add_sub_element("Item", "", type="CWBB")
    item.zspm = "zspm test cwbb"
    print(task_group.id())
    print(task_group.type())
