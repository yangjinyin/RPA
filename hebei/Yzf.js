function read_tbody(selector,tr,inputtd) {
    var rtnJson = {};
    var info_dict = {};
    var index = 0;
    try {
        var table = document.querySelectorAll(selector)
        if (table.length) {
            for (i = 0; i < table[0].rows.length; i++) {
                for(j = 0; j < table[0].rows[0].cells.length;j++){
                    var jsSelector = selector + " > " +  tr + ":nth-child(" + (i+1) + ") > "
                    jsSelector = jsSelector +  inputtd + ":nth-child(" + (j+1) + ")"
                    value = document.querySelectorAll(jsSelector)[0].children[0].innerHTML
                    info_dict[index++] = new Array(i, j, jsSelector, value)
                    rtnJson.rtnMsg = info_dict;
                }
            }
        }
        else {
            rtnJson.rtnCode = false;
            rtnJson.rtnMsg = "没找到元素";
        }
    } catch (error) {
        rtnJson.rtnCode = false;
        rtnJson.rtnMsg = error.message;
    }
    return JSON.stringify(rtnJson);
}

function testAlert(out) {
    alert(out)

}
function add(input)
{
    var rtnJson = {}
    var info_dict = {}
    info_dict[0] = new Array(1, 1, "test key", "test value")
     rtnJson.rtnMsg = info_dict;
    info_dict[1] = new Array(2, 2, "test key 2", "test value 2")
     rtnJson.rtnMsg = info_dict;

     rtnJson.rtnCode = true;
      return JSON.stringify(rtnJson);
}