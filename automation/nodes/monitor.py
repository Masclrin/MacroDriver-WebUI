def register(registry):
    registry.register_node({
        "type": "monitor/monitor_color",
        "category": "monitor",
        "display_name": "颜色监视",
        "color": "#06b6d4",
        "inputs": [],
        "outputs": [
            {"name": "trigger", "type": "flow"},
            {"name": "timeout", "type": "flow"},
        ],
        "params_schema": {
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式"},
            "rect": {"type": "array", "format": "region", "default": [0, 0, 10, 10], "description": "检测区域[x,y,w,h]"},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名"},
            "target_color": {"type": "string", "default": "#FF0000", "format": "color", "description": "目标颜色"},
            "tolerance": {"type": "number", "default": 10, "description": "容差(0-255)"},
            "interval": {"type": "number", "default": 100, "description": "检测间隔(ms)"},
            "timeout": {"type": "number", "default": 0, "description": "超时(ms, 0=无限)"},
            "trigger_mode": {"type": "string", "enum": ["appear", "disappear", "change"], "default": "appear", "description": "触发模式"},
            "on_trigger": {"type": "string", "enum": ["branch", "stop_all", "stop_task", "pause_task"], "default": "branch", "description": "触发行为"},
            "target_task": {"type": "string", "default": "", "description": "目标任务ID", "showWhen": "on_trigger=stop_task,pause_task"},
            "auto_stop": {"type": "boolean", "default": True, "description": "触发后是否自动停止此监视器"},
        },
        "handler": "_handle_monitor_node",
    })

    registry.register_node({
        "type": "monitor/monitor_ocr",
        "category": "monitor",
        "display_name": "OCR监视",
        "color": "#06b6d4",
        "inputs": [],
        "outputs": [
            {"name": "trigger", "type": "flow"},
            {"name": "timeout", "type": "flow"},
        ],
        "params_schema": {
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式"},
            "rect": {"type": "array", "format": "region", "default": [0, 0, 100, 30], "description": "检测区域[x,y,w,h]"},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名"},
            "match_text": {"type": "string", "default": "", "description": "匹配文本"},
            "match_mode": {"type": "string", "enum": ["contain", "exact", "regex", "number_gt", "number_lt", "number_eq"], "default": "contain", "description": "匹配模式"},
            "match_number": {"type": "number", "default": 0, "description": "比较数值", "showWhen": "match_mode=number_gt,number_lt,number_eq"},
            "engine": {"type": "string", "enum": ["rapidocr"], "default": "rapidocr", "description": "OCR引擎"},
            "interval": {"type": "number", "default": 200, "description": "检测间隔(ms)"},
            "timeout": {"type": "number", "default": 0, "description": "超时(ms, 0=无限)"},
            "on_trigger": {"type": "string", "enum": ["branch", "stop_all", "stop_task", "pause_task"], "default": "branch", "description": "触发行为"},
            "target_task": {"type": "string", "default": "", "description": "目标任务ID", "showWhen": "on_trigger=stop_task,pause_task"},
            "auto_stop": {"type": "boolean", "default": True, "description": "触发后是否自动停止此监视器"},
            "store_var": {"type": "string", "default": "", "description": "存储识别到的原始文本"},
            "store_number": {"type": "string", "default": "", "description": "存储提取的数字值"},
        },
        "handler": "_handle_monitor_node",
    })

    registry.register_node({
        "type": "monitor/monitor_timer",
        "category": "monitor",
        "display_name": "定时器",
        "color": "#06b6d4",
        "inputs": [],
        "outputs": [
            {"name": "trigger", "type": "flow"},
        ],
        "params_schema": {
            "interval": {"type": "number", "default": 1000, "description": "触发间隔(ms)"},
            "repeat_count": {"type": "number", "default": 0, "description": "重复次数(0=无限)"},
            "on_trigger": {"type": "string", "enum": ["branch", "stop_all", "stop_task", "pause_task"], "default": "branch", "description": "触发行为"},
        },
        "handler": "_handle_monitor_node",
    })
