def register(registry):
    registry.register_node({
        "type": "action/mouse_click",
        "category": "action",
        "display_name": "鼠标点击",
        "color": "#22c55e",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "mode": {"type": "string", "enum": ["screen", "window", "relative", "current"], "default": "screen", "description": "坐标模式", "display_names": {"screen": "屏幕坐标", "window": "窗口坐标", "relative": "相对坐标(0~1)", "current": "当前位置"}},
            "x": {"type": "number", "default": 0, "description": "X坐标", "showWhen": "mode=screen,mode=window,mode=relative", "varRef": True},
            "y": {"type": "number", "default": 0, "description": "Y坐标", "showWhen": "mode=screen,mode=window,mode=relative", "varRef": True},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名", "showWhen": "mode=window,mode=relative", "varRef": True},
            "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left", "description": "鼠标按键", "display_names": {"left": "左键", "right": "右键", "middle": "中键"}},
            "click_type": {"type": "string", "enum": ["click", "dblclick", "press", "release", "long_press"], "default": "click", "description": "点击类型", "display_names": {"click": "单击", "dblclick": "双击", "press": "按下不放", "release": "松开", "long_press": "长按"}},
            "hold_time": {"type": "number", "default": 0, "description": "长按持续时间(ms)", "varRef": True},
            "move_duration": {"type": "number", "default": 0, "description": "移动到目标坐标的耗时(ms)", "showWhen": "mode=screen,mode=window,mode=relative", "varRef": True},
            "before_delay": {"type": "number", "default": 0, "description": "点击前额外等待(ms)", "varRef": True},
            "after_delay": {"type": "number", "default": 0, "description": "点击后额外等待(ms)", "varRef": True},
            "store_hwnd_var": {"type": "string", "default": "", "description": "存储窗口句柄到变量", "showWhen": "mode=window,mode=relative", "varRef": True},
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
            "action": {"type": "string", "enum": ["click", "press", "release", "type"], "default": "click", "description": "动作类型", "display_names": {"click": "点击(按下+松开)", "press": "按下不放", "release": "松开按键", "type": "打字输入"}},
            "key": {"type": "string", "default": "", "description": "按键名(如A、F1、Space、Enter)", "varRef": True},
            "delay": {"type": "number", "default": 0, "description": "动作后延迟(ms)", "varRef": True},
            "text_input_delay": {"type": "number", "default": 10, "description": "打字模式字符间隔(ms)", "showWhen": "action=type", "varRef": True},
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
            "delta": {"type": "number", "default": 120, "description": "滚动量(正值向上, 120=1格Windows)", "varRef": True},
            "delay": {"type": "number", "default": 0, "description": "动作后延迟(ms)", "varRef": True},
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
            "text": {"type": "string", "default": "", "description": "要输入的文本", "varRef": True},
            "interval": {"type": "number", "default": 50, "description": "字符间间隔(ms)", "varRef": True},
            "before_delay": {"type": "number", "default": 0, "description": "输入前等待(ms)", "varRef": True},
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
            "mode": {"type": "string", "enum": ["duration", "until_time"], "default": "duration", "description": "等待模式", "display_names": {"duration": "固定时长", "until_time": "等到指定时间"}},
            "duration": {"type": "number", "default": 0, "description": "等待时长", "showWhen": "mode=duration", "varRef": True},
            "unit": {"type": "string", "enum": ["ms", "s", "min"], "default": "ms", "description": "时间单位", "showWhen": "mode=duration", "display_names": {"ms": "毫秒(ms)", "s": "秒(s)", "min": "分钟(min)"}},
            "hour": {"type": "number", "default": 8, "description": "目标小时(0-23)", "showWhen": "mode=until_time", "varRef": True},
            "minute": {"type": "number", "default": 0, "description": "目标分钟(0-59)", "showWhen": "mode=until_time", "varRef": True},
            "second": {"type": "number", "default": 0, "description": "目标秒(0-59)", "showWhen": "mode=until_time", "varRef": True},
            "next_day": {"type": "boolean", "default": False, "description": "若已过目标时间则等到次日", "showWhen": "mode=until_time"},
        },
        "handler": "_handle_wait",
    })

    registry.register_node({
        "type": "action/window_manage",
        "category": "action",
        "display_name": "窗口管理",
        "color": "#22c55e",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "find_mode": {"type": "string", "enum": ["title", "hwnd", "hwnd_var"], "default": "title", "description": "查找方式", "display_names": {"title": "窗口标题(模糊匹配)", "hwnd": "句柄值(十进制)", "hwnd_var": "句柄变量"}},
            "title": {"type": "string", "default": "", "description": "窗口标题(支持部分匹配)", "showWhen": "find_mode=title", "windowPicker": True, "varRef": True},
            "hwnd_value": {"type": "string", "default": "", "description": "窗口句柄(十进制)", "showWhen": "find_mode=hwnd", "varRef": True},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名", "showWhen": "find_mode=hwnd_var", "varRef": True},
            "action": {"type": "string", "enum": ["activate", "maximize", "minimize", "restore", "close", "move_to_monitor"], "default": "activate", "description": "窗口操作", "display_names": {"activate": "激活(置前)", "maximize": "最大化", "minimize": "最小化", "restore": "还原(恢复)", "close": "关闭窗口", "move_to_monitor": "移至指定显示器"}},
            "monitor_index": {"type": "number", "default": 0, "description": "目标显示器序号(0=主显示器)", "showWhen": "action=move_to_monitor", "varRef": True},
            "store_hwnd_var": {"type": "string", "default": "", "description": "存储窗口句柄到变量", "varRef": True},
        },
        "handler": "_handle_window_manage",
    })

    registry.register_node({
        "type": "action/program_open",
        "category": "action",
        "display_name": "打开程序",
        "color": "#22c55e",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "path": {"type": "string", "default": "", "description": "程序路径", "browseType": "program", "varRef": True},
            "args": {"type": "string", "default": "", "description": "启动参数", "varRef": True},
            "work_dir": {"type": "string", "default": "", "description": "工作目录", "varRef": True},
            "wait_start": {"type": "number", "default": 0, "description": "启动后等待(ms)", "varRef": True},
            "store_hwnd_var": {"type": "string", "default": "", "description": "存储主窗口句柄到变量", "varRef": True},
        },
        "handler": "_handle_program_open",
    })

    registry.register_node({
        "type": "action/program_close",
        "category": "action",
        "display_name": "关闭程序",
        "color": "#22c55e",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "close_mode": {"type": "string", "enum": ["name", "pid", "hwnd", "hwnd_var"], "default": "name", "description": "关闭方式", "display_names": {"name": "按进程名(如notepad.exe)", "pid": "按进程PID", "hwnd": "按窗口句柄", "hwnd_var": "按句柄变量"}},
            "process_name": {"type": "string", "default": "", "description": "进程名(如notepad.exe)", "showWhen": "close_mode=name", "processPicker": True, "varRef": True},
            "pid_value": {"type": "string", "default": "", "description": "进程PID", "showWhen": "close_mode=pid", "varRef": True},
            "hwnd_value": {"type": "string", "default": "", "description": "窗口句柄(十进制)", "showWhen": "close_mode=hwnd", "varRef": True},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名", "showWhen": "close_mode=hwnd_var", "varRef": True},
            "force": {"type": "boolean", "default": False, "description": "强制结束进程(不等待程序响应)"},
        },
        "handler": "_handle_program_close",
    })

    registry.register_node({
        "type": "action/mouse_move",
        "category": "action",
        "display_name": "鼠标移动",
        "color": "#22c55e",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式", "display_names": {"screen": "屏幕坐标", "window": "窗口坐标", "relative": "相对坐标(0~1)"}},
            "x": {"type": "number", "default": 0, "description": "目标X坐标", "showWhen": "mode=screen,mode=window,mode=relative", "varRef": True},
            "y": {"type": "number", "default": 0, "description": "目标Y坐标", "showWhen": "mode=screen,mode=window,mode=relative", "varRef": True},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名", "showWhen": "mode=window,mode=relative", "varRef": True},
            "duration": {"type": "number", "default": 200, "description": "移动耗时(ms)", "varRef": True},
            "easing": {"type": "string", "enum": ["linear", "ease_in_out", "ease_in", "ease_out"], "default": "ease_in_out", "description": "缓动函数(移动曲线)", "display_names": {"linear": "匀速(直线)", "ease_in_out": "先慢-快-慢(自然)", "ease_in": "渐入(越来越快)", "ease_out": "渐出(越来越慢)"}},
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
            "dx": {"type": "number", "default": 0, "description": "水平偏移(像素)", "varRef": True},
            "dy": {"type": "number", "default": 0, "description": "垂直偏移(像素)", "varRef": True},
            "duration": {"type": "number", "default": 200, "description": "移动耗时(ms)", "varRef": True},
        },
        "handler": "_handle_mouse_move_rel",
    })

    registry.register_node({
        "type": "script_block/flow_control",
        "category": "script_block",
        "display_name": "动作控制",
        "color": "#3b82f6",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "action": {"type": "string", "enum": ["stop_all", "stop_task", "pause_task", "resume_task", "stop_self", "nothing"], "default": "stop_all", "description": "控制动作", "display_names": {"stop_all": "停止所有任务", "stop_task": "停止指定任务", "pause_task": "暂停指定任务", "resume_task": "恢复指定任务", "stop_self": "停止自身(当前脚本)", "nothing": "无操作(占位)"}},
            "target_task": {"type": "string", "default": "", "description": "目标任务ID", "showWhen": "action=stop_task,action=pause_task,action=resume_task", "nodeRef": "script_block/call_script_async,script_block/exec_sub_script", "varRef": True},
        },
        "handler": "_handle_flow_control",
    })

    registry.register_node({
        "type": "script_block/exec_sub_script",
        "category": "script_block",
        "display_name": "执行子脚本",
        "color": "#3b82f6",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "next", "type": "flow"},
            {"name": "fail", "type": "flow"},
        ],
        "params_schema": {
            "script_path": {"type": "string", "default": "", "description": "子脚本文件路径", "varRef": True},
        },
        "handler": "_handle_preset_sub_script",
    })
