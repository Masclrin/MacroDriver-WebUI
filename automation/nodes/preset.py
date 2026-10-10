def register(registry):
    registry.register_node({
        "type": "preset/preset_click",
        "category": "preset",
        "display_name": "点击坐标",
        "color": "#f472b6",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式"},
            "x": {"type": "number", "default": 960, "description": "X坐标"},
            "y": {"type": "number", "default": 540, "description": "Y坐标"},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名"},
            "button": {"type": "string", "enum": ["left", "right"], "default": "left", "description": "鼠标按键"},
            "move_duration": {"type": "number", "default": 150, "description": "移动耗时(ms)"},
        },
        "handler": "_handle_preset_click",
    })

    registry.register_node({
        "type": "preset/preset_find_click",
        "category": "preset",
        "display_name": "找图点击",
        "color": "#f472b6",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "found", "type": "flow"},
            {"name": "not_found", "type": "flow"},
        ],
        "params_schema": {
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式"},
            "rect": {"type": "array", "format": "region", "default": [0, 0, 0, 0], "description": "搜索区域, 0=全屏"},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名"},
            "template_path": {"type": "string", "default": "", "format": "path", "description": "模板图片路径"},
            "threshold": {"type": "number", "default": 0.8, "description": "匹配阈值(0-1)"},
            "button": {"type": "string", "enum": ["left", "right"], "default": "left", "description": "鼠标按键"},
        },
        "handler": "_handle_preset_find_click",
    })

    registry.register_node({
        "type": "preset/preset_read_text",
        "category": "preset",
        "display_name": "读取数字文本",
        "color": "#f472b6",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式"},
            "rect": {"type": "array", "format": "region", "default": [0, 0, 100, 30], "description": "检测区域[x,y,w,h]"},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名"},
            "read_mode": {"type": "string", "enum": ["all", "number", "text"], "default": "all", "description": "读取模式"},
            "engine": {"type": "string", "enum": ["rapidocr"], "default": "rapidocr", "description": "OCR引擎"},
            "store_var": {"type": "string", "default": "", "description": "存入变量名"},
        },
        "handler": "_handle_preset_read_text",
    })
