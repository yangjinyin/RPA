



def get_js():
    f = open("Yzf.js", "r", encoding="UTF-8")
    line = f.readline()
    htmlstr = ''
    while line:
        htmlstr = htmlstr + line
        line = f.readline()
    return htmlstr