def register(registry):
    registry.register_node({
        "type": "variable/var_set",
        "category": "variable",
        "display_name": "设置变量",
        "color": "#f97316",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "vars_json": {"type": "var_list", "default": "[]", "description": "多变量设置（JSON数组格式）"},
            "name": {"type": "string", "default": "", "description": "变量名(单变量模式)"},
            "value": {"type": "string", "default": "", "description": "变量值(支持${var}引用)", "varRef": True},
            "var_type": {"type": "string", "enum": ["number", "string", "boolean"], "default": "string", "description": "变量类型(单变量模式)", "display_names": {"number": "数字", "string": "文本(字符串)", "boolean": "布尔(真假)"}},
        },
        "handler": "_handle_var_set",
    })

    registry.register_node({
        "type": "variable/var_math",
        "category": "variable",
        "display_name": "数学运算",
        "color": "#f97316",
        "inputs": [
            {"name": "in", "type": "flow"},
            {"name": "A", "type": "number"},
            {"name": "B", "type": "number"},
        ],
        "outputs": [
            {"name": "next", "type": "flow"},
            {"name": "result", "type": "number"},
        ],
        "params_schema": {
            "op": {"type": "string", "enum": ["+", "-", "*", "/", "%", "^", "min", "max", "abs", "round"], "default": "+", "description": "运算类型", "display_names": {"+": "加法(+)", "-": "减法(-)", "*": "乘法(×)", "/": "除法(÷)", "%": "取余(模)", "^": "乘方(幂)", "min": "取最小值", "max": "取最大值", "abs": "绝对值", "round": "四舍五入"}},
            "a": {"type": "string", "default": "0", "description": "操作数A(支持${var})", "varRef": True},
            "b": {"type": "string", "default": "0", "description": "操作数B(round时=小数位数)", "showWhen": "op=+,op=-,op=*,op=/,op=%,op=^,op=min,op=max,op=round", "varRef": True},
            "store_var": {"type": "string", "default": "", "description": "存储结果变量名", "varRef": True},
        },
        "handler": "_handle_var_math",
    })

    registry.register_node({
        "type": "variable/var_compare",
        "category": "variable",
        "display_name": "比较",
        "color": "#f97316",
        "inputs": [
            {"name": "in", "type": "flow"},
            {"name": "A", "type": "number"},
            {"name": "B", "type": "number"},
        ],
        "outputs": [
            {"name": "next", "type": "flow"},
            {"name": "result", "type": "data_bool"},
        ],
        "params_schema": {
            "op": {"type": "string", "enum": [">", "<", ">=", "<=", "==", "!="], "default": ">", "description": "比较运算", "display_names": {">": "大于(>)", "<": "小于(<)", ">=": "大于等于(≥)", "<=": "小于等于(≤)", "==": "等于(==)", "!=": "不等于(!=)"}},
            "a": {"type": "string", "default": "0", "description": "操作数A(支持${var})", "varRef": True},
            "b": {"type": "string", "default": "0", "description": "操作数B(支持${var})", "varRef": True},
        },
        "handler": "_handle_var_compare",
    })

    registry.register_node({
        "type": "variable/var_string",
        "category": "variable",
        "display_name": "字符串操作",
        "color": "#f97316",
        "inputs": [
            {"name": "in", "type": "flow"},
            {"name": "str", "type": "string"},
        ],
        "outputs": [
            {"name": "next", "type": "flow"},
            {"name": "result", "type": "string"},
        ],
        "params_schema": {
            "op": {"type": "string", "enum": ["concat", "replace", "upper", "lower", "trim", "substring", "split_index", "regex_extract"], "default": "concat", "description": "操作类型", "display_names": {"concat": "拼接(合并)", "replace": "替换(查找替换)", "upper": "转大写", "lower": "转小写", "trim": "去首尾空格", "substring": "截取子串", "split_index": "分割取段", "regex_extract": "正则提取"}},
            "a": {"type": "string", "default": "", "description": "输入字符串(支持${var})", "varRef": True},
            "concat_str": {"type": "string", "default": "", "description": "要拼接的字符串", "showWhen": "op=concat", "varRef": True},
            "search_str": {"type": "string", "default": "", "description": "要查找的文本", "showWhen": "op=replace", "varRef": True},
            "replace_str": {"type": "string", "default": "", "description": "替换为", "showWhen": "op=replace", "varRef": True},
            "start_pos": {"type": "number", "default": 0, "description": "起始位置(从0开始)", "showWhen": "op=substring", "varRef": True},
            "length": {"type": "number", "default": 0, "description": "截取长度(0=到末尾)", "showWhen": "op=substring", "varRef": True},
            "delimiter": {"type": "string", "default": ",", "description": "分隔符(如逗号、竖线)", "showWhen": "op=split_index", "varRef": True},
            "index": {"type": "number", "default": 0, "description": "取第几段(从0开始)", "showWhen": "op=split_index", "varRef": True},
            "regex_pattern": {"type": "string", "default": "", "description": "正则表达式(如\\d+匹配数字)", "showWhen": "op=regex_extract", "varRef": True},
            "store_var": {"type": "string", "default": "", "description": "存入变量名", "varRef": True},
        },
        "handler": "_handle_var_string",
    })

    registry.register_node({
        "type": "variable/var_convert",
        "category": "variable",
        "display_name": "类型转换",
        "color": "#f97316",
        "inputs": [
            {"name": "in", "type": "flow"},
            {"name": "val", "type": "any"},
        ],
        "outputs": [
            {"name": "next", "type": "flow"},
            {"name": "result", "type": "any"},
        ],
        "params_schema": {
            "to_type": {"type": "string", "enum": ["number", "string", "boolean"], "default": "number", "description": "目标类型", "display_names": {"number": "数字", "string": "文本(字符串)", "boolean": "布尔(真假)"}},
            "input_var": {"type": "string", "default": "", "description": "输入变量名", "varRef": True},
            "store_var": {"type": "string", "default": "", "description": "存储结果变量名", "varRef": True},
        },
        "handler": "_handle_var_convert",
    })

    registry.register_node({
        "type": "variable/var_random",
        "category": "variable",
        "display_name": "随机数生成",
        "color": "#f97316",
        "inputs": [
            {"name": "in", "type": "flow"},
        ],
        "outputs": [
            {"name": "next", "type": "flow"},
            {"name": "result", "type": "any"},
        ],
        "params_schema": {
            "mode": {"type": "string", "enum": ["number", "string"], "default": "number", "description": "随机模式", "display_names": {"number": "随机数字", "string": "随机文本"}},
            "min_val": {"type": "number", "default": 1, "description": "最小值(含)", "showWhen": "mode=number", "varRef": True},
            "max_val": {"type": "number", "default": 100, "description": "最大值(含)", "showWhen": "mode=number", "varRef": True},
            "int_only": {"type": "boolean", "default": True, "description": "仅整数(关闭则生成小数)", "showWhen": "mode=number"},
            "charset": {"type": "string", "enum": ["alpha", "alphanumeric", "numeric", "custom"], "default": "alpha", "description": "字符集", "showWhen": "mode=string", "display_names": {"alpha": "字母(a-zA-Z)", "alphanumeric": "字母+数字(0-9a-zA-Z)", "numeric": "纯数字(0-9)", "custom": "自定义字符池"}},
            "custom_chars": {"type": "string", "default": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", "description": "自定义字符池内容", "showWhen": "mode=string,charset=custom", "varRef": True},
            "length": {"type": "number", "default": 8, "description": "字符串长度", "showWhen": "mode=string", "varRef": True},
            "store_var": {"type": "string", "default": "", "description": "存储结果变量名", "varRef": True},
        },
        "handler": "_handle_var_random",
    })
