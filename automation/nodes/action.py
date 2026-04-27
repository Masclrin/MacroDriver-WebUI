def register(registry):
    registry.register_node({
        "type": "action/mouse_click",
        "category": "action",
        "display_name": "鼠标点击",
        "color": "#22c55e",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式"},
            "x": {"type": "number", "default": 0, "description": "X坐标"},
            "y": {"type": "number", "default": 0, "description": "Y坐标"},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名"},
            "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left", "description": "鼠标按键"},
            "click_type": {"type": "string", "enum": ["click", "dblclick", "press", "release", "long_press"], "default": "click", "description": "点击类型"},
            "hold_time": {"type": "number", "default": 0, "description": "长按持续时间(ms)"},
            "move_duration": {"type": "number", "default": 0, "description": "移动到目标坐标的耗时(ms)"},
            "before_delay": {"type": "number", "default": 0, "description": "点击前额外等待(ms)"},
            "after_delay": {"type": "number", "default": 0, "description": "点击后额外等待(ms)"},
        },
        "handler": "_handle_mouse_click",
    })

    registry.register_node({
        "type": "action/key_action",
        "category": "action",
        "display_name": "按键动作",
        "color": "#22c55e",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "action": {"type": "string", "enum": ["press", "release", "type"], "default": "press", "description": "动作类型"},
            "key": {"type": "string", "default": "", "description": "按键名"},
            "delay": {"type": "number", "default": 0, "description": "动作后延迟(ms)"},
        },
        "handler": "_handle_key_action",
    })

    registry.register_node({
        "type": "action/mouse_scroll",
        "category": "action",
        "display_name": "鼠标滚轮",
        "color": "#22c55e",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "delta": {"type": "number", "default": 120, "description": "滚动量(正值向上)"},
            "delay": {"type": "number", "default": 0, "description": "动作后延迟(ms)"},
        },
        "handler": "_handle_mouse_scroll",
    })

    registry.register_node({
        "type": "action/text_input",
        "category": "action",
        "display_name": "文本输入",
        "color": "#22c55e",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "text": {"type": "string", "default": "", "description": "要输入的文本"},
            "interval": {"type": "number", "default": 50, "description": "字符间间隔(ms)"},
            "before_delay": {"type": "number", "default": 0, "description": "输入前等待(ms)"},
        },
        "handler": "_handle_text_input",
    })

    registry.register_node({
        "type": "action/wait",
        "category": "action",
        "display_name": "等待",
        "color": "#22c55e",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "duration": {"type": "number", "default": 1000, "description": "等待时长(ms)"},
        },
        "handler": "_handle_wait",
    })

    registry.register_node({
        "type": "action/mouse_move",
        "category": "action",
        "display_name": "鼠标移动",
        "color": "#22c55e",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式"},
            "x": {"type": "number", "default": 0, "description": "目标X坐标"},
            "y": {"type": "number", "default": 0, "description": "目标Y坐标"},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名"},
            "duration": {"type": "number", "default": 200, "description": "移动耗时(ms)"},
            "easing": {"type": "string", "enum": ["linear", "ease_in_out", "ease_in", "ease_out"], "default": "ease_in_out", "description": "缓动函数"},
        },
        "handler": "_handle_mouse_move",
    })

    registry.register_node({
        "type": "action/mouse_move_rel",
        "category": "action",
        "display_name": "相对位移",
        "color": "#22c55e",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "dx": {"type": "number", "default": 100, "description": "水平偏移(像素)"},
            "dy": {"type": "number", "default": 0, "description": "垂直偏移(像素)"},
            "duration": {"type": "number", "default": 200, "description": "移动耗时(ms)"},
        },
        "handler": "_handle_mouse_move_rel",
    })
