def register(registry):
    registry.register_node({
        "type": "preset/preset_click",
        "category": "preset",
        "display_name": "点击坐标",
        "color": "#f472b6",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "next", "type": "flow"},
        ],
        "params_schema": {
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式", "coordMode": True, "display_names": {"screen": "屏幕坐标", "window": "窗口坐标", "relative": "相对坐标(0~1)"}},
            "x": {"type": "number", "default": 960, "description": "X坐标(像素)", "varRef": True, "coordRef": True},
            "y": {"type": "number", "default": 540, "description": "Y坐标(像素)", "varRef": True, "coordRef": True},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名", "showWhen": "mode=window,mode=relative", "varRef": True},
            "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left", "description": "鼠标按键", "display_names": {"left": "左键", "right": "右键", "middle": "中键"}},
            "move_duration": {"type": "number", "default": 150, "description": "移动耗时(ms)", "varRef": True},
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
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式", "coordMode": True, "display_names": {"screen": "屏幕坐标", "window": "窗口坐标", "relative": "相对坐标(0~1)"}},
            "rect": {"type": "array", "format": "region", "default": [0, 0, 0, 0], "description": "搜索区域(全零=全屏)", "coordMode": True, "varRef": True},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名", "showWhen": "mode=window,mode=relative", "varRef": True},
            "template_path": {"type": "string", "default": "", "format": "path", "description": "模板图片路径(.png/.jpg)", "varRef": True},
            "threshold": {"type": "number", "default": 0.8, "description": "匹配阈值(0.5~1.0，越高越严格)", "varRef": True},
            "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left", "description": "鼠标按键", "display_names": {"left": "左键", "right": "右键", "middle": "中键"}},
            "store_var": {"type": "string", "default": "", "description": "存入变量名(是否找到,布尔值)", "varRef": True},
        },
        "handler": "_handle_preset_find_click",
    })

    registry.register_node({
        "type": "preset/preset_read_text",
        "category": "preset",
        "display_name": "读取数字文本",
        "color": "#f472b6",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "next", "type": "flow"},
            {"name": "text", "type": "data_string"},
        ],
        "params_schema": {
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式", "coordMode": True, "display_names": {"screen": "屏幕坐标", "window": "窗口坐标", "relative": "相对坐标(0~1)"}},
            "rect": {"type": "array", "format": "region", "default": [0, 0, 100, 30], "description": "检测区域[x,y,w,h]", "coordMode": True, "varRef": True},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名", "showWhen": "mode=window,mode=relative", "varRef": True},
            "read_mode": {"type": "string", "enum": ["all", "number", "text"], "default": "all", "description": "读取模式", "display_names": {"all": "全部识别", "number": "仅提取数字", "text": "仅提取文本"}},
            "store_var": {"type": "string", "default": "", "description": "存入变量名", "varRef": True},
            "store_number": {"type": "string", "default": "", "description": "存储数字值变量名", "showWhen": "read_mode=number", "varRef": True},
        },
        "handler": "_handle_preset_read_text",
    })
