# -*- coding:utf-8 -*-

import subprocess
import logging


class YzfPdfTable:
    def __init__(self, text_list_list):
        self.data = text_list_list

    def get_text_by_row_col(self, row_int, col_int):
        return self.data[row_int][col_int]

    def log(self):
        for row_index in range(len(self.data)):
            for col_idnex in range(len(self.data[row_index])):
                logging.info("table[" + str(row_index) + "][" + str(col_idnex) + "] = " + self.get_text_by_row_col(row_index, col_idnex))
                print("table[" + str(row_index) + "][" + str(col_idnex) + "] = " + self.get_text_by_row_col(row_index, col_idnex))


def analyze_pdf(pdf_file_full_path_str, ghost_script_exe_full_path_str):
    gsexe = ghost_script_exe_full_path_str
    pdf_file = pdf_file_full_path_str
    args = gsexe + " -dNOPAUSE -dBATCH -q -sDEVICE=txtwrite -sOutputFile=- " + pdf_file
    output = subprocess.run(args.split(), stdout=subprocess.PIPE, timeout=60)
    output = output.stdout.decode("utf-8")
    output_lines = output.split("\r\n")
    ret_lines = []
    for line in output_lines:
        ret_lines.append(line.split())

    return YzfPdfTable(ret_lines)


if __name__ == '__main__':
    """
    测试代码
    """
    table = analyze_pdf("E:\\tmp\\pdf\\downloaded20181207_121110.pdf", "E:\\oldInterfaceSystem\\InterfaceSystem_\\Xiamen\\XiamenGds\\res\\gswin32c.exe")
    print(table.get_text_by_row_col(0, 0))
    table.log()








