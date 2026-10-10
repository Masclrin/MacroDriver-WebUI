def register(registry):
    registry.register_node({
        "type": "utility/const_number",
        "category": "utility",
        "display_name": "数字常量",
        "color": "#d8d8d8ff",
        "inputs": [],
        "outputs": [{"name": "value", "type": "number"}],
        "params_schema": {
            "value": {"type": "number", "default": 0, "description": "常量值"},
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
            "value": {"type": "string", "default": "", "description": "常量字符串"},
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
            "value": {"type": "bool", "default": True, "description": "布尔值"},
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
            "op": {"type": "string", "enum": ["add", "sub", "mul", "div", "mod", "pow", "min", "max"], "default": "add", "description": "运算符"},
            "a": {"type": "number", "default": 0, "description": "输入A"},
            "b": {"type": "number", "default": 0, "description": "输入B"},
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
            "func": {"type": "string", "enum": ["abs", "round", "floor", "ceil", "sqrt", "sin", "cos", "log", "negate"], "default": "abs", "description": "函数"},
            "x": {"type": "number", "default": 0, "description": "输入值"},
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
            "op": {"type": "string", "enum": ["and", "or", "xor", "not", "nand", "nor"], "default": "and", "description": "逻辑运算"},
            "a": {"type": "bool", "default": True, "description": "输入A"},
            "b": {"type": "bool", "default": True, "description": "输入B"},
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
            "op": {"type": "string", "enum": ["eq", "ne", "gt", "lt", "ge", "le"], "default": "gt", "description": "比较运算符"},
            "a": {"type": "number", "default": 0, "description": "输入A"},
            "b": {"type": "number", "default": 0, "description": "输入B"},
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
            "op": {"type": "string", "enum": ["concat", "replace", "upper", "lower", "trim", "substring", "split_index"], "default": "concat", "description": "操作类型"},
            "input_str": {"type": "string", "default": "", "description": "输入字符串"},
            "param_a": {"type": "string", "default": "", "description": "参数A"},
            "param_b": {"type": "string", "default": "", "description": "参数B"},
            "param_c": {"type": "string", "default": "", "description": "参数C"},
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
            "cond_var": {"type": "string", "default": "", "description": "条件变量名"},
            "true_val": {"type": "string", "default": "", "description": "为真时的值"},
            "false_val": {"type": "string", "default": "", "description": "为假时的值"},
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
            "ms": {"type": "number", "default": 1000, "description": "延迟时间(ms)"},
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
            "mode": {"type": "enum", "default": "screen", "options": ["screen", "window", "relative"], "description": "坐标模式"},
            "x": {"type": "number", "default": 0, "description": "X坐标"},
            "y": {"type": "number", "default": 0, "description": "Y坐标"},
            "w": {"type": "number", "default": 0, "description": "宽度"},
            "h": {"type": "number", "default": 0, "description": "高度"},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量"},
            "remark": {"type": "string", "default": "", "description": "备注"},
        },
        "handler": "_handle_bookmark",
    })
