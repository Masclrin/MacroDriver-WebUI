# -*- coding: utf-8 -*-
"""
插件/节点/引擎注册中心
所有节点类型、检测引擎均通过注册制管理，前端UI完全由后端下发的 params_schema 驱动渲染。
"""
import json


class PluginRegistry:
    _node_types = {}
    _detect_engines = {}

    @classmethod
    def register_node(cls, def_dict):
        required_keys = {"type", "category", "display_name", "color", "inputs", "outputs", "params_schema"}
        missing = required_keys - set(def_dict.keys())
        if missing:
            raise ValueError(f"节点定义缺少必需字段: {missing}")
        cls._node_types[def_dict["type"]] = def_dict

    @classmethod
    def register_detect_engine(cls, def_dict):
        required_keys = {"id", "name", "params_schema", "detect_func"}
        missing = required_keys - set(def_dict.keys())
        if missing:
            raise ValueError(f"检测引擎定义缺少必需字段: {missing}")
        cls._detect_engines[def_dict["id"]] = def_dict

    @classmethod
    def get_node(cls, node_type):
        return cls._node_types.get(node_type)

    @classmethod
    def get_all_nodes(cls):
        return dict(cls._node_types)

    @classmethod
    def get_detect_engine(cls, engine_id):
        return cls._detect_engines.get(engine_id)

    @classmethod
    def get_frontend_payload(cls):
        nodes = {}
        for k, v in cls._node_types.items():
            node_copy = {kk: vv for kk, vv in v.items() if kk != "handler"}
            nodes[k] = node_copy
        engines = []
        for val in cls._detect_engines.values():
            engine_copy = {k: v for k, v in val.items() if k != "detect_func"}
            engines.append(engine_copy)
        return {"nodes": nodes, "engines": engines}

    @classmethod
    def clear(cls):
        cls._node_types.clear()
        cls._detect_engines.clear()


def register_builtin_nodes():
    from webui_backend.input_primitives import get_vk, set_cursor_pos, send_click_sendinput, send_key_sendinput, send_scroll_sendinput

    PluginRegistry.register_node({
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

    PluginRegistry.register_node({
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

    PluginRegistry.register_node({
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

    PluginRegistry.register_node({
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

    PluginRegistry.register_node({
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

    PluginRegistry.register_node({
        "type": "control/if_else",
        "category": "control",
        "display_name": "条件分支",
        "color": "#a855f7",
        "inputs": [
            {"name": "in", "type": "flow"},
            {"name": "cond", "type": "data_bool"},
        ],
        "outputs": [
            {"name": "true", "type": "flow"},
            {"name": "false", "type": "flow"},
        ],
        "params_schema": {
            "logic": {"type": "string", "enum": ["AND", "OR", "NOT"], "default": "AND", "description": "逻辑组合"},
            "fallback": {"type": "string", "enum": ["true", "false"], "default": "false", "description": "无data连接时默认走向"},
        },
        "handler": "_handle_if_else",
    })

    PluginRegistry.register_node({
        "type": "control/loop_count",
        "category": "control",
        "display_name": "计数循环",
        "color": "#a855f7",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "body", "type": "flow"},
            {"name": "next", "type": "flow"},
        ],
        "params_schema": {
            "count": {"type": "number", "default": 1, "description": "循环次数"},
            "counter_var": {"type": "string", "default": "", "description": "循环计数器变量名"},
        },
        "handler": "_handle_loop_count",
    })

    PluginRegistry.register_node({
        "type": "control/loop_while",
        "category": "control",
        "display_name": "条件循环",
        "color": "#a855f7",
        "inputs": [
            {"name": "in", "type": "flow"},
            {"name": "cond", "type": "data_bool"},
        ],
        "outputs": [
            {"name": "body", "type": "flow"},
            {"name": "next", "type": "flow"},
        ],
        "params_schema": {
            "max_iterations": {"type": "number", "default": 10000, "description": "最大迭代次数"},
            "check_at": {"type": "string", "enum": ["start", "end"], "default": "start", "description": "检查时机"},
        },
        "handler": "_handle_loop_while",
    })

    PluginRegistry.register_node({
        "type": "script_block/call_script_sync",
        "category": "script_block",
        "display_name": "调用宏(同步)",
        "color": "#3b82f6",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "path": {"type": "string", "default": "", "format": "path", "description": "旧JSON宏文件路径"},
            "speed_factor": {"type": "number", "default": 1.0, "description": "倍速"},
            "timeline_mode": {"type": "string", "enum": ["absolute", "relative_compensated"], "default": "absolute", "description": "时间线模式"},
            "random_delay": {"type": "boolean", "default": False, "description": "是否启用随机延迟修正"},
        },
        "handler": "_handle_call_script_sync",
    })

    PluginRegistry.register_node({
        "type": "script_block/call_script_async",
        "category": "script_block",
        "display_name": "调用宏(异步)",
        "color": "#3b82f6",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "next", "type": "flow"},
            {"name": "completed", "type": "flow"},
            {"name": "interrupted", "type": "flow"},
        ],
        "params_schema": {
            "path": {"type": "string", "default": "", "format": "path", "description": "旧JSON宏文件路径"},
            "speed_factor": {"type": "number", "default": 1.0, "description": "倍速"},
            "timeline_mode": {"type": "string", "enum": ["absolute", "relative_compensated"], "default": "absolute", "description": "时间线模式"},
            "random_delay": {"type": "boolean", "default": False, "description": "是否启用随机延迟修正"},
        },
        "handler": "_handle_call_script_async",
    })

    PluginRegistry.register_node({
        "type": "detection/check_color",
        "category": "detection",
        "display_name": "颜色检测",
        "color": "#eab308",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "match", "type": "flow"},
            {"name": "no", "type": "flow"},
            {"name": "result", "type": "data_bool"},
        ],
        "params_schema": {
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式"},
            "rect": {"type": "array", "format": "region", "default": [0, 0, 10, 10], "description": "检测区域[x,y,w,h]"},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名"},
            "target_color": {"type": "string", "default": "#FF0000", "format": "color", "description": "目标颜色"},
            "tolerance": {"type": "number", "default": 10, "description": "容差(0-255)"},
            "check_mode": {"type": "string", "enum": ["exact", "contain", "change"], "default": "contain", "description": "检测模式"},
            "sample_mode": {"type": "string", "enum": ["center", "mean", "max_diff"], "default": "center", "description": "采样模式"},
            "change_threshold": {"type": "number", "default": 10, "description": "变化检测阈值(check_mode=change时)", "showWhen": "check_mode=change"},
            "store_var": {"type": "string", "default": "", "description": "存储检测到的实际颜色值"},
        },
        "handler": "_handle_check_color",
    })

    PluginRegistry.register_node({
        "type": "detection/check_ocr",
        "category": "detection",
        "display_name": "OCR识别",
        "color": "#eab308",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "match", "type": "flow"},
            {"name": "no", "type": "flow"},
            {"name": "result", "type": "data_bool"},
        ],
        "params_schema": {
            "mode": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "坐标模式"},
            "rect": {"type": "array", "format": "region", "default": [0, 0, 100, 30], "description": "检测区域[x,y,w,h]"},
            "hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名"},
            "match_text": {"type": "string", "default": "", "description": "匹配文本"},
            "match_mode": {"type": "string", "enum": ["contain", "exact", "regex", "number_gt", "number_lt", "number_eq"], "default": "contain", "description": "匹配模式"},
            "match_number": {"type": "number", "default": 0, "description": "比较数值(number_*模式)", "showWhen": "match_mode=number_gt,number_lt,number_eq"},
            "engine": {"type": "string", "enum": ["rapidocr"], "default": "rapidocr", "description": "OCR引擎"},
            "cache_strategy": {"type": "string", "enum": ["frame_diff", "time_interval", "disabled"], "default": "time_interval", "description": "缓存策略"},
            "cache_interval_ms": {"type": "number", "default": 100, "description": "缓存间隔(ms)", "showWhen": "cache_strategy=time_interval"},
            "store_var": {"type": "string", "default": "", "description": "存储识别到的原始文本"},
            "store_number": {"type": "string", "default": "", "description": "存储提取的数字值"},
        },
        "handler": "_handle_check_ocr",
    })

    PluginRegistry.register_node({
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

    PluginRegistry.register_node({
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

    PluginRegistry.register_node({
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

    PluginRegistry.register_node({
        "type": "variable/var_set",
        "category": "variable",
        "display_name": "设置变量",
        "color": "#f97316",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "name": {"type": "string", "default": "", "description": "变量名"},
            "value": {"type": "string", "default": "", "description": "变量值(支持${var}引用)"},
            "var_type": {"type": "string", "enum": ["number", "string", "boolean"], "default": "string", "description": "变量类型"},
        },
        "handler": "_handle_var_set",
    })

    PluginRegistry.register_node({
        "type": "variable/var_math",
        "category": "variable",
        "display_name": "数学运算",
        "color": "#f97316",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "op": {"type": "string", "enum": ["add", "sub", "mul", "div", "mod", "min", "max", "abs", "round"], "default": "add", "description": "运算类型"},
            "a": {"type": "string", "default": "0", "description": "操作数A(支持${var})"},
            "b": {"type": "string", "default": "0", "description": "操作数B(支持${var})"},
            "store_var": {"type": "string", "default": "", "description": "存储结果变量名"},
        },
        "handler": "_handle_var_math",
    })

    PluginRegistry.register_node({
        "type": "variable/var_compare",
        "category": "variable",
        "display_name": "比较",
        "color": "#f97316",
        "inputs": [{"name": "in", "type": "flow"}],
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

    PluginRegistry.register_node({
        "type": "variable/var_string",
        "category": "variable",
        "display_name": "字符串操作",
        "color": "#f97316",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "op": {"type": "string", "enum": ["concat", "substr", "replace", "split", "regex_extract"], "default": "concat", "description": "操作类型"},
            "a": {"type": "string", "default": "", "description": "字符串A(支持${var})"},
            "b": {"type": "string", "default": "", "description": "字符串B(支持${var})"},
            "store_var": {"type": "string", "default": "", "description": "存储结果变量名"},
        },
        "handler": "_handle_var_string",
    })

    PluginRegistry.register_node({
        "type": "variable/var_convert",
        "category": "variable",
        "display_name": "类型转换",
        "color": "#f97316",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "to_type": {"type": "string", "enum": ["number", "string", "boolean"], "default": "number", "description": "目标类型"},
            "input_var": {"type": "string", "default": "", "description": "输入变量名"},
            "store_var": {"type": "string", "default": "", "description": "存储结果变量名"},
        },
        "handler": "_handle_var_convert",
    })

    PluginRegistry.register_node({
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

    PluginRegistry.register_node({
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

    PluginRegistry.register_node({
        "type": "detection/check_image",
        "category": "detection",
        "display_name": "图像匹配",
        "color": "#eab308",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "match", "type": "flow"},
            {"name": "no", "type": "flow"},
            {"name": "result", "type": "data_bool"},
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

    PluginRegistry.register_node({
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

    PluginRegistry.register_node({
        "type": "control/wait_cond",
        "category": "control",
        "display_name": "等待条件",
        "color": "#a855f7",
        "inputs": [
            {"name": "in", "type": "flow"},
            {"name": "cond", "type": "data_bool"},
        ],
        "outputs": [
            {"name": "met", "type": "flow"},
            {"name": "timeout", "type": "flow"},
        ],
        "params_schema": {
            "timeout": {"type": "number", "default": 10000, "description": "超时(ms)"},
            "interval": {"type": "number", "default": 100, "description": "检查间隔(ms)"},
        },
        "handler": "_handle_wait_cond",
    })

    PluginRegistry.register_node({
        "type": "control/goto",
        "category": "control",
        "display_name": "跳转",
        "color": "#a855f7",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [],
        "params_schema": {
            "target_node_id": {"type": "string", "default": "", "description": "目标节点ID"},
        },
        "handler": "_handle_goto",
    })

    PluginRegistry.register_node({
        "type": "control/seq_check",
        "category": "control",
        "display_name": "序列检测",
        "color": "#a855f7",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "pass", "type": "flow"},
            {"name": "fail", "type": "flow"},
        ],
        "params_schema": {
            "steps": {"type": "string", "default": "", "description": "步骤描述(如: 颜色变绿 → OCR弹窗 → 点击确认)"},
            "retry": {"type": "boolean", "default": True, "description": "失败后重试"},
            "max_retries": {"type": "number", "default": 100, "description": "最大重试次数"},
        },
        "handler": "_handle_seq_check",
    })

    PluginRegistry.register_node({
        "type": "control/state_machine",
        "category": "control",
        "display_name": "状态机",
        "color": "#a855f7",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "done", "type": "flow"}],
        "params_schema": {
            "states": {"type": "string", "default": "", "description": "状态列表(如: wait_color → check_popup → done)"},
            "fail_state": {"type": "string", "default": "", "description": "失败回退状态名"},
        },
        "handler": "_handle_state_machine",
    })

    PluginRegistry.register_node({
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

    PluginRegistry.register_node({
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

    PluginRegistry.register_node({
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
            "read_mode": {"type": "string", "enum": ["all", "number", "text"], "default": "all", "description": "读取模式(全部/纯数字/中英文文本)"},
            "engine": {"type": "string", "enum": ["rapidocr"], "default": "rapidocr", "description": "OCR引擎"},
            "store_var": {"type": "string", "default": "", "description": "存入变量名"},
        },
        "handler": "_handle_preset_read_text",
    })

    PluginRegistry.register_node({
        "type": "utility/const_number",
        "category": "utility",
        "display_name": "数字常量",
        "color": "#64748b",
        "inputs": [],
        "outputs": [{"name": "value", "type": "number"}],
        "params_schema": {
            "value": {"type": "number", "default": 0, "description": "常量值"},
        },
        "handler": "_handle_const_number",
    })

    PluginRegistry.register_node({
        "type": "utility/const_string",
        "category": "utility",
        "display_name": "字符串常量",
        "color": "#64748b",
        "inputs": [],
        "outputs": [{"name": "value", "type": "string"}],
        "params_schema": {
            "value": {"type": "string", "default": "", "description": "常量字符串"},
        },
        "handler": "_handle_const_string",
    })

    PluginRegistry.register_node({
        "type": "utility/const_bool",
        "category": "utility",
        "display_name": "布尔常量",
        "color": "#64748b",
        "inputs": [],
        "outputs": [{"name": "value", "type": "boolean"}],
        "params_schema": {
            "value": {"type": "bool", "default": True, "description": "布尔值"},
        },
        "handler": "_handle_const_bool",
    })

    PluginRegistry.register_node({
        "type": "utility/math_op",
        "category": "utility",
        "display_name": "数学运算",
        "color": "#64748b",
        "inputs": [{"name": "A", "type": "number"}, {"name": "B", "type": "number"}],
        "outputs": [{"name": "result", "type": "number"}],
        "params_schema": {
            "op": {"type": "string", "enum": ["add", "sub", "mul", "div", "mod", "pow", "min", "max"], "default": "add", "description": "运算符"},
            "a": {"type": "number", "default": 0, "description": "输入A(可由连线覆盖)"},
            "b": {"type": "number", "default": 0, "description": "输入B(可由连线覆盖)"},
        },
        "handler": "_handle_math_op",
    })

    PluginRegistry.register_node({
        "type": "utility/math_func",
        "category": "utility",
        "display_name": "数学函数",
        "color": "#64748b",
        "inputs": [{"name": "x", "type": "number"}],
        "outputs": [{"name": "result", "type": "number"}],
        "params_schema": {
            "func": {"type": "string", "enum": ["abs", "round", "floor", "ceil", "sqrt", "sin", "cos", "log", "negate"], "default": "abs", "description": "函数"},
            "x": {"type": "number", "default": 0, "description": "输入值(可由连线覆盖)"},
        },
        "handler": "_handle_math_func",
    })

    PluginRegistry.register_node({
        "type": "utility/logic_op",
        "category": "utility",
        "display_name": "逻辑运算",
        "color": "#64748b",
        "inputs": [{"name": "A", "type": "boolean"}, {"name": "B", "type": "boolean"}],
        "outputs": [{"name": "result", "type": "boolean"}],
        "params_schema": {
            "op": {"type": "string", "enum": ["and", "or", "xor", "not", "nand", "nor"], "default": "and", "description": "逻辑运算"},
            "a": {"type": "bool", "default": True, "description": "输入A"},
            "b": {"type": "bool", "default": True, "description": "输入B"},
        },
        "handler": "_handle_logic_op",
    })

    PluginRegistry.register_node({
        "type": "utility/compare",
        "category": "utility",
        "display_name": "数值比较",
        "color": "#64748b",
        "inputs": [{"name": "A", "type": "number"}, {"name": "B", "type": "number"}],
        "outputs": [{"name": "result", "type": "boolean"}],
        "params_schema": {
            "op": {"type": "string", "enum": ["eq", "ne", "gt", "lt", "ge", "le"], "default": "gt", "description": "比较运算符"},
            "a": {"type": "number", "default": 0, "description": "输入A"},
            "b": {"type": "number", "default": 0, "description": "输入B"},
        },
        "handler": "_handle_compare",
    })

    PluginRegistry.register_node({
        "type": "utility/string_op",
        "category": "utility",
        "display_name": "字符串操作",
        "color": "#64748b",
        "inputs": [{"name": "str", "type": "string"}],
        "outputs": [{"name": "result", "type": "string"}],
        "params_schema": {
            "op": {"type": "string", "enum": ["concat", "replace", "upper", "lower", "trim", "substring", "split_index"], "default": "concat", "description": "操作类型"},
            "input_str": {"type": "string", "default": "", "description": "输入字符串(可由连线覆盖)"},
            "param_a": {"type": "string", "default": "", "description": "参数A(拼接串/替换源/分隔符)"},
            "param_b": {"type": "string", "default": "", "description": "参数B(替换目标/起始索引)"},
            "param_c": {"type": "string", "default": "", "description": "参数C(结束索引/取第N段)"},
        },
        "handler": "_handle_string_op",
    })

    PluginRegistry.register_node({
        "type": "utility/condition",
        "category": "utility",
        "display_name": "条件选择",
        "color": "#64748b",
        "inputs": [{"name": "cond", "type": "boolean"}, {"name": "if_true", "type": "any"}, {"name": "if_false", "type": "any"}],
        "outputs": [{"name": "result", "type": "any"}],
        "params_schema": {
            "cond_var": {"type": "string", "default": "", "description": "条件变量名(优先于连线)"},
            "true_val": {"type": "string", "default": "", "description": "为真时的值"},
            "false_val": {"type": "string", "default": "", "description": "为假时的值"},
        },
        "handler": "_handle_condition",
    })

    PluginRegistry.register_node({
        "type": "utility/delay",
        "category": "utility",
        "display_name": "延迟",
        "color": "#64748b",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "ms": {"type": "number", "default": 1000, "description": "延迟时间(ms)"},
        },
        "handler": "_handle_utility_delay",
    })

    PluginRegistry.register_node({
        "type": "utility/comment",
        "category": "utility",
        "display_name": "注释",
        "color": "#64748b",
        "inputs": [],
        "outputs": [],
        "params_schema": {
            "text": {"type": "string", "default": "", "description": "注释内容"},
            "bg_color": {"type": "string", "default": "#1e293b", "description": "背景色"},
        },
        "handler": None,
    })

    PluginRegistry.register_node({
        "type": "utility/group",
        "category": "utility",
        "display_name": "分组框",
        "color": "#64748b",
        "inputs": [],
        "outputs": [],
        "params_schema": {
            "title": {"type": "string", "default": "分组", "description": "分组标题"},
            "bg_color": {"type": "string", "default": "rgba(30,41,59,0.3)", "description": "背景色"},
        },
        "handler": None,
    })
