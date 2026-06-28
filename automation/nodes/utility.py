def register(registry):
    registry.register_node({
        "type": "utility/const_number",
        "category": "utility",
        "display_name": "数字常量",
        "color": "#d8d8d8ff",
        "inputs": [],
        "outputs": [{"name": "value", "type": "number"}],
        "params_schema": {
            "value": {"type": "number", "default": 0, "description": "常量值", "varRef": True},
        },
        "handler": "_handle_const_number",
    })

    registry.register_node({
        "type": "utility/const_string",
        "category": "utility",
        "display_name": "字符串常量",
        "color": "#d8d8d8ff",
        "inputs": [],
        "outputs": [{"name": "value", "type": "string"}],
        "params_schema": {
            "value": {"type": "string", "default": "", "description": "常量字符串", "varRef": True},
        },
        "handler": "_handle_const_string",
    })

    registry.register_node({
        "type": "utility/const_bool",
        "category": "utility",
        "display_name": "布尔常量",
        "color": "#d8d8d8ff",
        "inputs": [],
        "outputs": [{"name": "value", "type": "boolean"}],
        "params_schema": {
            "value": {"type": "boolean", "default": True, "description": "布尔值", "display_names": {"true": "真", "false": "假"}},
        },
        "handler": "_handle_const_bool",
    })

    registry.register_node({
        "type": "utility/math_op",
        "category": "utility",
        "display_name": "数学运算",
        "color": "#d8d8d8ff",
        "inputs": [{"name": "A", "type": "number"}, {"name": "B", "type": "number"}],
        "outputs": [{"name": "result", "type": "number"}],
        "params_schema": {
            "op": {"type": "string", "enum": ["+", "-", "*", "/", "%", "^", "min", "max"], "default": "+", "description": "运算符", "display_names": {"+": "加法(+)", "-": "减法(-)", "*": "乘法(×)", "/": "除法(÷)", "%": "取余(模)", "^": "乘方(幂)", "min": "取最小值", "max": "取最大值"}},
            "a": {"type": "number", "default": 0, "description": "输入A", "varRef": True},
            "b": {"type": "number", "default": 0, "description": "输入B", "varRef": True},
        },
        "handler": "_handle_math_op",
    })

    registry.register_node({
        "type": "utility/math_func",
        "category": "utility",
        "display_name": "数学函数",
        "color": "#d8d8d8ff",
        "inputs": [{"name": "x", "type": "number"}],
        "outputs": [{"name": "result", "type": "number"}],
        "params_schema": {
            "func": {"type": "string", "enum": ["abs", "round", "floor", "ceil", "sqrt", "sin", "cos", "log", "negate"], "default": "abs", "description": "数学函数", "display_names": {"abs": "绝对值(|x|)", "round": "四舍五入", "floor": "向下取整(⌊x⌋)", "ceil": "向上取整(⌈x⌉)", "sqrt": "平方根(√)", "sin": "正弦(sin)", "cos": "余弦(cos)", "log": "自然对数(ln)", "negate": "取负(-x)"}},
            "x": {"type": "number", "default": 0, "description": "输入值(sin/cos为弧度)", "varRef": True},
            "digits": {"type": "number", "default": 0, "description": "小数位数(round专用)", "showWhen": "func=round", "varRef": True},
        },
        "handler": "_handle_math_func",
    })

    registry.register_node({
        "type": "utility/logic_op",
        "category": "utility",
        "display_name": "逻辑运算",
        "color": "#d8d8d8ff",
        "inputs": [{"name": "A", "type": "boolean"}, {"name": "B", "type": "boolean"}],
        "outputs": [{"name": "result", "type": "boolean"}],
        "params_schema": {
            "op": {"type": "string", "enum": ["and", "or", "xor", "not", "nand", "nor"], "default": "and", "description": "逻辑运算", "display_names": {"and": "与(AND, 全真则真)", "or": "或(OR, 有真则真)", "xor": "异或(XOR, 不同为真)", "not": "非(NOT, 取反)", "nand": "与非(NAND)", "nor": "或非(NOR)"}},
            "a": {"type": "bool", "default": True, "description": "输入A", "varRef": True},
            "b": {"type": "bool", "default": True, "description": "输入B", "showWhen": "op=and,op=or,op=xor,op=nand,op=nor", "varRef": True},
        },
        "handler": "_handle_logic_op",
    })

    registry.register_node({
        "type": "utility/compare",
        "category": "utility",
        "display_name": "数值比较",
        "color": "#d8d8d8ff",
        "inputs": [{"name": "A", "type": "number"}, {"name": "B", "type": "number"}],
        "outputs": [{"name": "result", "type": "boolean"}],
        "params_schema": {
            "op": {"type": "string", "enum": ["eq", "ne", "gt", "lt", "ge", "le"], "default": "gt", "description": "比较运算符", "display_names": {"eq": "等于(==)", "ne": "不等于(!=)", "gt": "大于(>)", "lt": "小于(<)", "ge": "大于等于(≥)", "le": "小于等于(≤)"}},
            "a": {"type": "number", "default": 0, "description": "输入A", "varRef": True},
            "b": {"type": "number", "default": 0, "description": "输入B", "varRef": True},
        },
        "handler": "_handle_compare",
    })

    registry.register_node({
        "type": "utility/string_op",
        "category": "utility",
        "display_name": "字符串操作",
        "color": "#d8d8d8ff",
        "inputs": [{"name": "str", "type": "string"}],
        "outputs": [{"name": "result", "type": "string"}],
        "params_schema": {
            "op": {"type": "string", "enum": ["concat", "replace", "upper", "lower", "trim", "substring", "split_index", "regex_extract"], "default": "concat", "description": "操作类型", "display_names": {"concat": "拼接(合并)", "replace": "替换(查找替换)", "upper": "转大写", "lower": "转小写", "trim": "去首尾空格", "substring": "截取子串", "split_index": "分割取段", "regex_extract": "正则提取"}},
            "input_str": {"type": "string", "default": "", "description": "输入字符串", "varRef": True},
            "concat_str": {"type": "string", "default": "", "description": "要拼接的字符串", "showWhen": "op=concat", "varRef": True},
            "search_str": {"type": "string", "default": "", "description": "要查找的文本", "showWhen": "op=replace", "varRef": True},
            "replace_str": {"type": "string", "default": "", "description": "替换为", "showWhen": "op=replace", "varRef": True},
            "start_pos": {"type": "number", "default": 0, "description": "起始位置(从0开始)", "showWhen": "op=substring", "varRef": True},
            "length": {"type": "number", "default": 0, "description": "截取长度(0=到末尾)", "showWhen": "op=substring", "varRef": True},
            "delimiter": {"type": "string", "default": ",", "description": "分隔符", "showWhen": "op=split_index", "varRef": True},
            "index": {"type": "number", "default": 0, "description": "取第几段(从0开始)", "showWhen": "op=split_index", "varRef": True},
            "pattern": {"type": "string", "default": "", "description": "正则表达式", "showWhen": "op=regex_extract", "varRef": True},
            "group": {"type": "number", "default": 0, "description": "捕获组编号(0=整个匹配)", "showWhen": "op=regex_extract", "varRef": True},
        },
        "handler": "_handle_string_op",
    })

    registry.register_node({
        "type": "utility/condition",
        "category": "utility",
        "display_name": "条件选择",
        "color": "#d8d8d8ff",
        "inputs": [{"name": "cond", "type": "boolean"}, {"name": "if_true", "type": "any"}, {"name": "if_false", "type": "any"}],
        "outputs": [{"name": "result", "type": "any"}],
        "params_schema": {
            "cond_var": {"type": "string", "default": "", "description": "条件变量名", "varRef": True},
            "true_val": {"type": "string", "default": "", "description": "为真时的值", "varRef": True},
            "false_val": {"type": "string", "default": "", "description": "为假时的值", "varRef": True},
        },
        "handler": "_handle_condition",
    })

    registry.register_node({
        "type": "utility/delay",
        "category": "utility",
        "display_name": "延迟",
        "color": "#d8d8d8ff",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "ms": {"type": "number", "default": 1000, "description": "延迟时间(ms)", "varRef": True},
        },
        "handler": "_handle_utility_delay",
    })

    registry.register_node({
        "type": "utility/bookmark",
        "category": "utility",
        "display_name": "坐标书签",
        "color": "#d8d8d8ff",
        "inputs": [],
        "outputs": [
            {"name": "x", "type": "number"},
            {"name": "y", "type": "number"},
            {"name": "w", "type": "number"},
            {"name": "h", "type": "number"},
        ],
        "params_schema": {
            "name": {"type": "string", "default": "", "description": "书签名称"},
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式", "display_names": {"screen": "屏幕坐标", "window": "窗口坐标", "relative": "相对坐标(0~1)"}},
            "x": {"type": "number", "default": 0, "description": "X坐标", "varRef": True},
            "y": {"type": "number", "default": 0, "description": "Y坐标", "varRef": True},
            "w": {"type": "number", "default": 0, "description": "宽度", "varRef": True},
            "h": {"type": "number", "default": 0, "description": "高度", "varRef": True},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量", "showWhen": "mode=window,mode=relative", "varRef": True},
            "remark": {"type": "string", "default": "", "description": "备注"},
        },
        "handler": "_handle_bookmark",
    })
