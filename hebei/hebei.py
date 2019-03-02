# -*- coding:utf-8 -*-

import sys
sys.argv.append("--input-xml-file=PutDataTask.xml")
sys.argv.append("--browser-type=chrome")
import yzfargv
import LibDirMgr
import logging
import login
import cj_base_info
import cj_szrd
#import cj_szrd
from yzftaxbot import MyBot, YzfBrowser


def main():

    MyBot.register_login_task(login.main)
    MyBot.register_task_group("CJ", "HB_BASE_INFO", cj_base_info.main)
    MyBot.register_task_group("CJ", "HBGS_SZRD", cj_szrd.main)
    MyBot.run()


if __name__ == '__main__':
    try:
        logging.info("Hebei starts")
        print("Hebei starts")
        main()
        logging.info("Hebei exits normally")
        print("Hebei exits normally")
    except Exception as e:
        logging.exception(e)
        MyBot.Xml.save()
        sys.exit(128)

