def register(registry):
    registry.register_node({
        "type": "variable/var_set",
        "category": "variable",
        "display_name": "设置变量",
        "color": "#f97316",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "vars_json": {"type": "string", "default": "[]", "description": "变量列表JSON"},
            "name": {"type": "string", "default": "", "description": "变量名(单变量模式)"},
            "value": {"type": "string", "default": "", "description": "变量值(支持${var}引用)"},
            "var_type": {"type": "string", "enum": ["number", "string", "boolean"], "default": "string", "description": "变量类型(单变量模式)"},
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
            "op": {"type": "string", "enum": ["add", "sub", "mul", "div", "mod", "min", "max", "abs", "round"], "default": "add", "description": "运算类型"},
            "a": {"type": "string", "default": "0", "description": "操作数A(支持${var})"},
            "b": {"type": "string", "default": "0", "description": "操作数B(支持${var})"},
            "store_var": {"type": "string", "default": "", "description": "存储结果变量名"},
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
            "op": {"type": "string", "enum": ["eq", "ne", "gt", "lt", "ge", "le"], "default": "gt", "description": "比较运算"},
            "a": {"type": "string", "default": "0", "description": "操作数A(支持${var})"},
            "b": {"type": "string", "default": "0", "description": "操作数B(支持${var})"},
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
            "op": {"type": "string", "enum": ["concat", "substr", "replace", "split", "regex_extract"], "default": "concat", "description": "操作类型"},
            "a": {"type": "string", "default": "", "description": "字符串A(支持${var})"},
            "b": {"type": "string", "default": "", "description": "字符串B(支持${var})"},
            "store_var": {"type": "string", "default": "", "description": "存储结果变量名"},
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
            "to_type": {"type": "string", "enum": ["number", "string", "boolean"], "default": "number", "description": "目标类型"},
            "input_var": {"type": "string", "default": "", "description": "输入变量名"},
            "store_var": {"type": "string", "default": "", "description": "存储结果变量名"},
        },
        "handler": "_handle_var_convert",
    })
