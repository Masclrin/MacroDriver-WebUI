def register(registry):
    registry.register_node({
        "type": "detection/check_color",
        "category": "detection",
        "display_name": "颜色检测",
        "color": "#eab308",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "match", "type": "flow"},
            {"name": "no", "type": "flow"},
            {"name": "result", "type": "data_bool"},
            {"name": "color", "type": "string"},
        ],
        "params_schema": {
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式"},
            "rect": {"type": "array", "format": "region", "default": [0, 0, 10, 10], "description": "检测区域[x,y,w,h]"},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名"},
            "target_color": {"type": "string", "default": "#FF0000", "format": "color", "description": "目标颜色"},
            "tolerance": {"type": "number", "default": 10, "description": "容差(0-255)"},
            "check_mode": {"type": "string", "enum": ["exact", "contain", "change"], "default": "contain", "description": "检测模式"},
            "sample_mode": {"type": "string", "enum": ["center", "mean", "max_diff"], "default": "center", "description": "采样模式"},
            "change_threshold": {"type": "number", "default": 10, "description": "变化检测阈值", "showWhen": "check_mode=change"},
            "store_var": {"type": "string", "default": "", "description": "存储检测到的实际颜色值"},
        },
        "handler": "_handle_check_color",
    })

    registry.register_node({
        "type": "detection/check_ocr",
        "category": "detection",
        "display_name": "OCR识别",
        "color": "#eab308",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "match", "type": "flow"},
            {"name": "no", "type": "flow"},
            {"name": "result", "type": "data_bool"},
            {"name": "text", "type": "string"},
            {"name": "number", "type": "number"},
        ],
        "params_schema": {
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式"},
            "rect": {"type": "array", "format": "region", "default": [0, 0, 100, 30], "description": "检测区域[x,y,w,h]"},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名"},
            "match_text": {"type": "string", "default": "", "description": "匹配文本"},
            "match_mode": {"type": "string", "enum": ["contain", "exact", "regex", "number_gt", "number_lt", "number_eq"], "default": "contain", "description": "匹配模式"},
            "match_number": {"type": "number", "default": 0, "description": "比较数值", "showWhen": "match_mode=number_gt,number_lt,number_eq"},
            "engine": {"type": "string", "enum": ["rapidocr"], "default": "rapidocr", "description": "OCR引擎"},
            "cache_strategy": {"type": "string", "enum": ["frame_diff", "time_interval", "disabled"], "default": "time_interval", "description": "缓存策略"},
            "cache_interval_ms": {"type": "number", "default": 100, "description": "缓存间隔(ms)", "showWhen": "cache_strategy=time_interval"},
            "store_var": {"type": "string", "default": "", "description": "存储识别到的原始文本"},
            "store_number": {"type": "string", "default": "", "description": "存储提取的数字值"},
        },
        "handler": "_handle_check_ocr",
    })

    registry.register_node({
        "type": "detection/check_image",
        "category": "detection",
        "display_name": "图像匹配",
        "color": "#eab308",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "match", "type": "flow"},
            {"name": "no", "type": "flow"},
            {"name": "result", "type": "data_bool"},
            {"name": "match_x", "type": "number"},
            {"name": "match_y", "type": "number"},
        ],
        "params_schema": {
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式"},
            "rect": {"type": "array", "format": "region", "default": [0, 0, 0, 0], "description": "搜索区域[x,y,w,h], 0=全屏"},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名"},
            "template_path": {"type": "string", "default": "", "format": "path", "description": "模板图片路径"},
            "threshold": {"type": "number", "default": 0.8, "description": "匹配阈值(0-1)"},
            "method": {"type": "string", "enum": ["tm_ccoeff_normed", "tm_ccorr_normed", "tm_sqdiff_normed"], "default": "tm_ccoeff_normed", "description": "匹配方法"},
            "multi_match": {"type": "boolean", "default": False, "description": "是否匹配多个结果"},
            "store_var": {"type": "string", "default": "", "description": "存储匹配位置变量名"},
        },
        "handler": "_handle_check_image",
    })

    registry.register_node({
        "type": "detection/check_screen",
        "category": "detection",
        "display_name": "屏幕状态",
        "color": "#eab308",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "match", "type": "flow"},
            {"name": "no", "type": "flow"},
            {"name": "result", "type": "data_bool"},
        ],
        "params_schema": {
            "state": {"type": "string", "enum": ["black", "bright", "frozen"], "default": "black", "description": "检测状态"},
            "threshold": {"type": "number", "default": 30, "description": "亮度阈值(0-255)"},
            "region": {"type": "array", "format": "region", "default": [0, 0, 0, 0], "description": "检测区域, 0=全屏"},
        },
        "handler": "_handle_check_screen",
    })
