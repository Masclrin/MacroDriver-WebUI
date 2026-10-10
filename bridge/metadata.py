# -*- coding: utf-8 -*-
"""MacroBridge 参数元数据，拆分自 webui_app.py。"""

SECTION_META = {
    "executor": {"title": "执行框架 3.2", "source": "executor"},
    "recorder": {"title": "录制框架 V2.1", "source": "recorder"},
    "simplify_tool": {"title": "轨迹化简参数", "source": "simplify_tool"},
    "interception": {"title": "Interception 注入", "source": "interception"},
    "webui": {"title": "WebUI 行为", "source": "bridge"},
    "automation_editor": {"title": "自动化编辑器", "source": "bridge"},
}

PARAM_DOCS = {
    "executor.TIMELINE_EXECUTION_MODE": {
        "desc": "宏执行策略，absolute 绝对时间线，低延迟宏如wait=0时可能出现后发先至；relative_compensated 相对补偿时间线。",
        "recommend": "使用高精度引擎可启用absolute，常规低精度不推荐；relative_compensated在非高精度场景下有优势。",
    },
    "executor.ABSOLUTE_TIMELINE_ALLOW_EARLY_MS": {
        "desc": "绝对时间线允许提前执行的窗口，用于抵消python循环延迟。",
        "recommend": "根据实际测试结果进行调整。",
    },
    "executor.ABSOLUTE_TIMELINE_WAIT_CHUNK_MS": {
        "desc": "绝对时间线等待切片长度，过长会增加延迟波动，过短可能增加 CPU 占用。",
        "recommend": "5~15ms，根据实际测试结果微调。",
    },
    "executor.ABSOLUTE_TIMELINE_USE_DELAY_ADJUST": {
        "desc": "绝对时间线是否继续应用动作分档随机修正。",
        "recommend": "如果想减少脚本特征可开启；追求绝对稳定可关闭。",
    },
    "executor.ENABLE_RANDOM_DELAY_ADJUST": {
        "desc": "根据动作原始延迟分档修正，可让宏节奏更接近真人波动。",
        "recommend": "需要拟人化时开启；压测或精确复现时关闭。",
    },
    "executor.RANDOM_DELAY_ADJUST_RULES_BY_DELAY_MS": {
        "desc": "分档规则按原始延迟命中，支持固定值与百分比混合修正。",
        "recommend": "先用默认推荐档位，再按游戏容忍度微调 fixed_ms。",
        "example": "[{\"min\":0,\"max\":199,\"fixed_ms\":3},{\"min\":200,\"max\":800,\"fixed_ms\":6}]",
    },
    "executor.ENABLE_RUNTIME_RANDOM_OFFSET": {
        "desc": "在最终动作延迟上附加随机扰动。",
        "recommend": "建议与最小/最大值成对配置，且范围尽量小（例如 0~6ms）。",
    },
    "executor.LAG_COMPENSATION_ENABLED": {
        "desc": "累计误差补偿总开关，仅在补偿执行流里生效。",
        "recommend": "长序列动作建议开启，短宏可关闭以简化行为。",
    },

    "executor.MACRO_RELOAD_KEY": {   
        "desc": "为空时仅在宏触发时重新加载宏文件，非空时则启动时直接加载或由按键触发加载。",
        #"recommend": "建议设置一个方便触及且不易误触的键位，例如 F6；不需要时可留空关闭。",
    },
    "executor.ENABLE_THREAD_CORE_BINDING": {
        "desc": "是否启用宏执行线程绑核。启用后会按倒序核心分配，优先使用倒数第一个核心。",
        "recommend": "追求多宏并发精度时开启，普通场景可关闭。",
    },
    "executor.CORE_BINDING_MAX_CORES": {
        "desc": "绑核可使用的核心数量上限（从倒数第一个核心向前取）。",
        "recommend": "建议 1~4，根据CPU核心数与并发量调整。",
    },
    "executor.CORE_BINDING_MAX_THREADS_PER_CORE": {
        "desc": "单个核心允许的线程上限。超出后将回落到占用最少核心共享。",
        "recommend": "高精度场景建议 1；负载高时可调高。",
    },
    "executor.ENABLE_LOW_CPU_EXECUTION": {
        "desc": "启用低占用执行模式。等待阶段改为普通 sleep 分片，显著降低 CPU 占用。",
        "recommend": "长时间挂机或多开场景建议开启；极限精度场景建议关闭。",
    },
    "executor.LOW_CPU_ENABLE_TIME_PERIOD": {
        "desc": "低占用模式下是否启用 timeBeginPeriod(1) 以改善普通 sleep 的粒度。",
        "recommend": "默认建议开启；若系统功耗敏感可关闭测试。",
    },
    "executor.LOW_CPU_FORCE_RELATIVE_MODE": {
        "desc": "低占用模式下是否强制切换到 relative_compensated，避免绝对时间线高占用。",
        "recommend": "建议开启，并配合补偿器减少长宏漂移。",
    },
    "executor.USE_INTERCEPTION": {
        "desc": "输入注入总开关，影响键盘与鼠标注入路径。",
        "recommend": "普通场景建议开启；若遇到输入异常可先关闭排查。",
    },
    "executor.ENABLE_BATCH_SEND": {
        "desc": "批量动作提交总开关。将连续低延迟动作合并为一次系统调用，减少开销。",
        "recommend": "默认开启。低延迟密集宏（如连发键）受益最大；若出现时序异常可关闭。",
    },
    "executor.BATCH_DELAY_THRESHOLD_MS": {
        "desc": "延迟 <= 此值的连续动作可合并提交。0.0 表示仅合并严格0延迟动作，最安全无时序偏移。",
        "recommend": "建议 2.0~5.0ms。值越大合并越多但时序偏移风险增加；追求安全可设为 0.0。",
    },
    "executor.BATCH_MAX_SIZE": {
        "desc": "单批最大合并动作数。批量过大会增加单次提交延迟。",
        "recommend": "建议 8~32。常规场景 16 即可；极高密度动作可适当提高。",
    },
    "executor.BATCH_INCLUDE_MOUSE_CLICK": {
        "desc": "是否将鼠标点击(md/mu)动作纳入批量合并。关闭后仅合并键盘动作。",
        "recommend": "默认开启。若鼠标点击出现丢失或错位可关闭。",
    },
    "recorder.START_MODE": {
        "desc": "delayed 为按键后延时启动，first_event 为首个有效事件触发启动。",
        "recommend": "战斗场景建议 first_event+延迟启动秒；流程脚本建议 delayed。",
    },
    "recorder.MAX_RECORD_SECONDS": {
        "desc": "录制缓存的时间窗口长度，超过后旧事件将被丢弃!",
        "recommend": "根据预期录制时长调整。",
    },
    "recorder.ENABLE_TRACK_SIMPLIFY": {
        "desc": "录制阶段是否直接执行轨迹化简。",
        "recommend": "首次录制建议关闭，确认轨迹后再开启。",
    },
    "recorder.ENABLE_KEY_WHITELIST": {
        "desc": "是否启用按键白名单，在高级参数中调整白名单。",
        "recommend": "建议在部分游戏场景时开启。",
    },
    "recorder.MIN_SPEED_PX_PER_SEC": {
        "desc": "低于阈值的轨迹将被视作抖动噪声。",
        "recommend": "高 DPI 鼠标可适当提高；精细微调动作可降低。",
    },
    "recorder.RECORD_TOGGLE_LISTENER_HOTKEY": {
        "desc": "切换录制监听服务的快捷键。",
        "recommend": "建议使用 F6~F10 区间，留空可关闭。",
    },
    "recorder.RECORD_ARM_HOTKEY": {
        "desc": "布防开始录制的快捷键。",
        "recommend": "建议与监听切换键错开，避免误触。",
    },
    "recorder.RECORD_STOP_HOTKEY": {
        "desc": "停止录制的快捷键。",
        "recommend": "建议使用就近按键，紧急停止更方便。",
    },
    "recorder.RECORD_SAVE_HOTKEY": {
        "desc": "保存录制结果的快捷键。",
        "recommend": "建议与停止键配对，例如 F8 停止、F9 保存。",
    },
    "recorder.RECORD_CLEAR_HOTKEY": {
        "desc": "清空录制缓存的快捷键。",
        "recommend": "建议设置为不常误触的键位。",
    },
    "interception.INTERCEPTION_MOUSE_LEFT_DOWN_LIMITED": {
        "desc": "左键按下采用限制设备模式，可降低误触发。",
        "recommend": "只有出现左键冲突时再开启。",
    },
    "webui.ALLOW_MULTI_MACRO_BIND_PER_KEY": {
        "desc": "是否允许同一个触发键绑定多个宏并发运行。",
        "recommend": "默认关闭。仅在明确需要同键并发时开启。",
    },
    "automation_editor.HOTKEY_RUN": {
        "desc": "自动化编辑器中运行当前脚本的快捷键。",
        "recommend": "建议与暂停/停止键错开，避免误触。",
    },
    "automation_editor.HOTKEY_PAUSE": {
        "desc": "自动化编辑器中暂停/继续执行当前脚本的快捷键。",
        "recommend": "建议与运行/停止键错开。",
    },
    "automation_editor.HOTKEY_STOP": {
        "desc": "自动化编辑器中停止执行当前脚本的快捷键。",
        "recommend": "建议设置为容易触及的键位，紧急停止更方便。",
    },
    "automation_editor.HOTKEY_FULLSCREEN": {
        "desc": "自动化编辑器中切换全屏预览的快捷键。",
        "recommend": "建议设置为不常误触的键位。",
    },
    "automation_editor.HOTKEY_ENABLED": {
        "desc": "是否启用自动化编辑器的全局快捷键。",
        "recommend": "默认开启。若与其他软件快捷键冲突可关闭。",
    },
}

PARAM_SCHEMA = {
    "executor": {
        "GLOBAL_PAUSE_TOGGLE_KEY": {"type": "str", "label": "全局暂停切换键", "tier": "basic"},
        "STOP_MACRO_KEY": {"type": "str", "label": "全局终止键", "tier": "basic"},
        "MACRO_RELOAD_KEY": {"type": "str", "label": "宏重载键", "tier": "advanced", "hint": "为空表示关闭"},
        "ENABLE_THREAD_CORE_BINDING": {"type": "bool", "label": "启用执行线程绑核", "tier": "advanced"},
        "CORE_BINDING_MAX_CORES": {
            "type": "int",
            "label": "绑核可用核心数",
            "tier": "advanced",
            "depends_on": [{"section": "executor", "key": "ENABLE_THREAD_CORE_BINDING", "value": True}],
        },
        "CORE_BINDING_MAX_THREADS_PER_CORE": {
            "type": "int",
            "label": "单核心最大并发线程",
            "tier": "advanced",
            "depends_on": [{"section": "executor", "key": "ENABLE_THREAD_CORE_BINDING", "value": True}],
        },
        "ENABLE_LOW_CPU_EXECUTION": {"type": "bool", "label": "启用低占用CPU执行", "tier": "basic"},
        "LOW_CPU_ENABLE_TIME_PERIOD": {
            "type": "bool",
            "label": "低占用时启用timeBeginPeriod(1)",
            "tier": "basic",
            "depends_on": [{"section": "executor", "key": "ENABLE_LOW_CPU_EXECUTION", "value": True}],
        },
        "LOW_CPU_FORCE_RELATIVE_MODE": {
            "type": "bool",
            "label": "低占用强制补偿模式",
            "tier": "advanced",
            "depends_on": [{"section": "executor", "key": "ENABLE_LOW_CPU_EXECUTION", "value": True}],
        },
        "EXEC_SPEED_FACTOR": {"type": "float", "label": "倍速执行", "tier": "basic", "hint": "2.0=两倍速"},
        "ENABLE_RUNTIME_RANDOM_OFFSET": {"type": "bool", "label": "启用运行时随机延迟", "tier": "basic"},
        "RUNTIME_RANDOM_OFFSET_MIN_MS": {
            "type": "float",
            "label": "随机延迟最小值(ms)",
            "tier": "basic",
            "depends_on": [{"section": "executor", "key": "ENABLE_RUNTIME_RANDOM_OFFSET", "value": True}],
        },
        "RUNTIME_RANDOM_OFFSET_MAX_MS": {
            "type": "float",
            "label": "随机延迟最大值(ms)",
            "tier": "basic",
            "depends_on": [{"section": "executor", "key": "ENABLE_RUNTIME_RANDOM_OFFSET", "value": True}],
        },
        "USE_INTERCEPTION": {"type": "bool", "label": "启用 Interception 总开关", "tier": "basic"},
        "USE_INTERCEPTION_KEYBOARD": {
            "type": "bool",
            "label": "键盘使用 Interception",
            "tier": "advanced",
            "depends_on": [{"section": "executor", "key": "USE_INTERCEPTION", "value": True}],
        },
        "USE_INTERCEPTION_MOUSE": {
            "type": "bool",
            "label": "鼠标使用 Interception",
            "tier": "advanced",
            "depends_on": [{"section": "executor", "key": "USE_INTERCEPTION", "value": True}],
        },
        "TIMELINE_EXECUTION_MODE": {
            "type": "str",
            "label": "时间线模式",
            "tier": "basic",
            "options": ["absolute", "relative_compensated"],
        },
        "ABSOLUTE_TIMELINE_ALLOW_EARLY_MS": {
            "type": "float",
            "label": "绝对时间线提前窗口(ms)",
            "tier": "advanced",
            "depends_on": [{"section": "executor", "key": "TIMELINE_EXECUTION_MODE", "value": "absolute"}],
        },
        "ABSOLUTE_TIMELINE_WAIT_CHUNK_MS": {
            "type": "float",
            "label": "绝对时间线等待切片(ms)",
            "tier": "advanced",
            "depends_on": [{"section": "executor", "key": "TIMELINE_EXECUTION_MODE", "value": "absolute"}],
        },
        "ENABLE_RANDOM_DELAY_ADJUST": {"type": "bool", "label": "启用动作分档随机延迟", "tier": "advanced"},
        "ABSOLUTE_TIMELINE_USE_DELAY_ADJUST": {
            "type": "bool",
            "label": "绝对模式启用延迟修正",
            "tier": "advanced",
            "depends_on": [{"section": "executor", "key": "TIMELINE_EXECUTION_MODE", "value": "absolute"}],
        },
        "RANDOM_DELAY_ADJUST_RULES_BY_DELAY_MS": {
            "type": "list",
            "label": "动作分档规则",
            "tier": "advanced",
            "hint": "支持 JSON 数组",
            "depends_on": [{"section": "executor", "key": "ENABLE_RANDOM_DELAY_ADJUST", "value": True}],
        },
        "LAG_COMPENSATION_ENABLED": {"type": "bool", "label": "启用误差补偿", "tier": "basic"},
        "LAG_USE_PI_CONTROLLER": {
            "type": "bool",
            "label": "启用 PI 控制器",
            "tier": "advanced",
            "depends_on": [{"section": "executor", "key": "LAG_COMPENSATION_ENABLED", "value": True}],
        },
        "LAG_USE_FEEDFORWARD": {
            "type": "bool",
            "label": "启用前馈控制",
            "tier": "advanced",
            "depends_on": [{"section": "executor", "key": "LAG_COMPENSATION_ENABLED", "value": True}],
        },
        "LAG_KP": {
            "type": "float",
            "label": "PI 比例增益 LAG_KP",
            "tier": "advanced",
            "depends_on": [
                {"section": "executor", "key": "LAG_COMPENSATION_ENABLED", "value": True},
                {"section": "executor", "key": "LAG_USE_PI_CONTROLLER", "value": True},
            ],
        },
        "LAG_KI": {
            "type": "float",
            "label": "PI 积分增益 LAG_KI",
            "tier": "advanced",
            "depends_on": [
                {"section": "executor", "key": "LAG_COMPENSATION_ENABLED", "value": True},
                {"section": "executor", "key": "LAG_USE_PI_CONTROLLER", "value": True},
            ],
        },
        "LAG_ERROR_TRIGGER_MS": {
            "type": "float",
            "label": "误差触发阈值(ms)",
            "tier": "advanced",
            "depends_on": [
                {"section": "executor", "key": "LAG_COMPENSATION_ENABLED", "value": True},
                {"section": "executor", "key": "LAG_USE_PI_CONTROLLER", "value": True},
            ],
        },
        "LAG_ERROR_TARGET_MS": {
            "type": "float",
            "label": "误差目标(ms)",
            "tier": "advanced",
            "depends_on": [
                {"section": "executor", "key": "LAG_COMPENSATION_ENABLED", "value": True},
                {"section": "executor", "key": "LAG_USE_PI_CONTROLLER", "value": True},
            ],
        },
        "LAG_MAX_STEP_COMP_PCT": {
            "type": "float",
            "label": "单步最大补偿比例",
            "tier": "advanced",
            "depends_on": [{"section": "executor", "key": "LAG_COMPENSATION_ENABLED", "value": True}],
        },
        "LAG_MIN_STEP_DELAY_MS": {
            "type": "float",
            "label": "最小步延迟(ms)",
            "tier": "advanced",
            "depends_on": [{"section": "executor", "key": "LAG_COMPENSATION_ENABLED", "value": True}],
        },
        "FF_SCALE": {
            "type": "float",
            "label": "前馈缩放 FF_SCALE",
            "tier": "advanced",
            "depends_on": [
                {"section": "executor", "key": "LAG_COMPENSATION_ENABLED", "value": True},
                {"section": "executor", "key": "LAG_USE_FEEDFORWARD", "value": True},
            ],
        },
        "FF_KP": {
            "type": "float",
            "label": "前馈比例 FF_KP",
            "tier": "advanced",
            "depends_on": [
                {"section": "executor", "key": "LAG_COMPENSATION_ENABLED", "value": True},
                {"section": "executor", "key": "LAG_USE_FEEDFORWARD", "value": True},
            ],
        },
        "FF_WINDOW_SIZE": {
            "type": "int",
            "label": "前馈窗口大小",
            "tier": "advanced",
            "depends_on": [
                {"section": "executor", "key": "LAG_COMPENSATION_ENABLED", "value": True},
                {"section": "executor", "key": "LAG_USE_FEEDFORWARD", "value": True},
            ],
        },
        "FF_MAX_COMP_PCT": {
            "type": "float",
            "label": "前馈单步最大补偿",
            "tier": "advanced",
            "depends_on": [
                {"section": "executor", "key": "LAG_COMPENSATION_ENABLED", "value": True},
                {"section": "executor", "key": "LAG_USE_FEEDFORWARD", "value": True},
            ],
        },
        "MAX_MACRO_EXEC_TIME": {"type": "float", "label": "宏最大执行时长(秒)", "tier": "advanced"},
        "MAX_COMPILED_ACTIONS": {"type": "int", "label": "宏编译动作上限", "tier": "advanced"},
        "ENABLE_REALTIME_PRIORITY": {"type": "bool", "label": "启用实时进程优先级", "tier": "advanced"},
        "ENABLE_BATCH_SEND": {"type": "bool", "label": "启用批量动作提交", "tier": "basic"},
        "BATCH_DELAY_THRESHOLD_MS": {
            "type": "float",
            "label": "批量合并延迟阈值(ms)",
            "tier": "advanced",
            "depends_on": [{"section": "executor", "key": "ENABLE_BATCH_SEND", "value": True}],
        },
        "BATCH_MAX_SIZE": {
            "type": "int",
            "label": "单批最大动作数",
            "tier": "advanced",
            "depends_on": [{"section": "executor", "key": "ENABLE_BATCH_SEND", "value": True}],
        },
        "BATCH_INCLUDE_MOUSE_CLICK": {
            "type": "bool",
            "label": "鼠标点击纳入批量合并",
            "tier": "advanced",
            "depends_on": [{"section": "executor", "key": "ENABLE_BATCH_SEND", "value": True}],
        },
        "ENABLE_PRO_AUDIO": {"type": "bool", "label": "启用 Pro Audio 调度", "tier": "advanced"},
        "ENABLE_TEST_TRACE": {"type": "bool", "label": "未开放: 步进测试追踪", "tier": "debug"},
        "TEST_TRACE_OUTPUT_MODE": {
            "type": "str",
            "label": "未开放: 测试输出模式",
            "tier": "debug",
            "options": ["final", "realtime"],
            "depends_on": [{"section": "executor", "key": "ENABLE_TEST_TRACE", "value": True}],
        },
        "ALLOW_LOCK_STYLE_KEY_LONG_PRESS": {"type": "bool", "label": "未开放: 锁定键长按模式", "tier": "debug"},
        "MACRO_BINDINGS": {"type": "json", "label": "未开放: 触发键绑定配置", "tier": "debug"},
        "MACRO_RUNTIME_SETTINGS": {"type": "json", "label": "未开放: 触发键运行时配置", "tier": "debug"},
    },
    "recorder": {
        "ENABLE_RECORD_HOTKEY_ACTIONS": {"type": "bool", "label": "启用录制快捷键动作", "tier": "basic"},
        "ENABLE_RECORD_ACTIONS": {"type": "bool", "label": "录制键鼠动作", "tier": "basic"},
        "ENABLE_RECORD_TRACK": {"type": "bool", "label": "录制鼠标轨迹", "tier": "basic"},
        "START_MODE": {"type": "str", "label": "录制启动模式", "tier": "basic", "options": ["delayed", "first_event"]},
        "START_DELAY_SECONDS": {
            "type": "float",
            "label": "延时启动秒数",
            "tier": "basic",
            #"depends_on": [{"section": "recorder", "key": "START_MODE", "value": "delayed"}],
        },
        # "RECORD_TOGGLE_LISTENER_HOTKEY": {
        #     "type": "str",
        #     "label": "录制监听切换快捷键",
        #     "tier": "basic",
        #     "hint": "留空则关闭",
        # },
        "RECORD_ARM_HOTKEY": {
            "type": "str",
            "label": "开始录制快捷键",
            "tier": "basic",
            "hint": "留空则关闭",
        },
        "RECORD_STOP_HOTKEY": {
            "type": "str",
            "label": "停止录制快捷键",
            "tier": "basic",
            "hint": "留空则关闭",
        },
        "RECORD_SAVE_HOTKEY": {
            "type": "str",
            "label": "保存录制快捷键",
            "tier": "basic",
            "hint": "留空则关闭",
        },
        "RECORD_CLEAR_HOTKEY": {
            "type": "str",
            "label": "清空录制缓存快捷键",
            "tier": "basic",
            "hint": "留空则关闭",
        },
        "MAX_RECORD_SECONDS": {"type": "float", "label": "缓存窗口时长(秒)", "tier": "basic"},
        "ENABLE_KEY_WHITELIST": {"type": "bool", "label": "启用按键白名单", "tier": "basic"},
        "ALLOWED_KEYS": {
            "type": "set",
            "label": "白名单按键集合",
            "tier": "advanced",
            "depends_on": [{"section": "recorder", "key": "ENABLE_KEY_WHITELIST", "value": True}],
        },
        "MOUSE_SAMPLE_INTERVAL_MS": {"type": "float", "label": "鼠标采样间隔(ms)", "tier": "basic"},
        "MOUSE_MOVE_SCALE": {"type": "float", "label": "鼠标位移缩放", "tier": "advanced"},
        "ENABLE_TRACK_SIMPLIFY": {"type": "bool", "label": "录制阶段轨迹化简", "tier": "basic"},
        "TRACK_SIMPLIFY_PIPELINE": {
            "type": "list",
            "label": "轨迹化简流水线",
            "tier": "advanced",
            "depends_on": [{"section": "recorder", "key": "ENABLE_TRACK_SIMPLIFY", "value": True}],
        },
        "SIMPLIFY_ANGLE_THRESHOLD_DEG": {
            "type": "float",
            "label": "意图角度阈值",
            "tier": "advanced",
            "depends_on": [{"section": "recorder", "key": "ENABLE_TRACK_SIMPLIFY", "value": True}],
        },
        "SIMPLIFY_SPEED_RATIO_THRESHOLD": {
            "type": "float",
            "label": "速度变化阈值",
            "tier": "advanced",
            "depends_on": [{"section": "recorder", "key": "ENABLE_TRACK_SIMPLIFY", "value": True}],
        },
        "SIMPLIFY_SLIDING_WINDOW_SIZE": {
            "type": "int",
            "label": "滑动窗口大小",
            "tier": "advanced",
            "depends_on": [{"section": "recorder", "key": "ENABLE_TRACK_SIMPLIFY", "value": True}],
        },
        "SIMPLIFY_RDP_EPSILON": {
            "type": "float",
            "label": "RDP Epsilon",
            "tier": "advanced",
            "depends_on": [{"section": "recorder", "key": "ENABLE_TRACK_SIMPLIFY", "value": True}],
        },
        "SIMPLIFY_MERGE_GAP_MS": {
            "type": "float",
            "label": "轨迹合并间隔(ms)",
            "tier": "advanced",
            "depends_on": [{"section": "recorder", "key": "ENABLE_TRACK_SIMPLIFY", "value": True}],
        },
        "SIMPLIFY_MIN_MANHATTAN": {
            "type": "float",
            "label": "轨迹最小曼哈顿阈值",
            "tier": "advanced",
            "depends_on": [{"section": "recorder", "key": "ENABLE_TRACK_SIMPLIFY", "value": True}],
        },
        "SIMPLIFY_ALLOW_CROSS_ACTION_MERGE": {
            "type": "bool",
            "label": "允许跨动作边界合并",
            "tier": "advanced",
            "depends_on": [{"section": "recorder", "key": "ENABLE_TRACK_SIMPLIFY", "value": True}],
        },
        "ENABLE_ACTION_DELAY_EMBEDDING": {
            "type": "bool",
            "label": "启用动作延迟嵌入",
            "tier": "advanced",
            "depends_on": [{"section": "recorder", "key": "ENABLE_TRACK_SIMPLIFY", "value": True}],
        },
        "ACTION_EMBED_DELAY_MS": {
            "type": "float",
            "label": "动作嵌入延迟(ms)",
            "tier": "advanced",
            "depends_on": [
                {"section": "recorder", "key": "ENABLE_TRACK_SIMPLIFY", "value": True},
                {"section": "recorder", "key": "ENABLE_ACTION_DELAY_EMBEDDING", "value": True},
            ],
        },
        "ACTION_EMBED_MAX_RATIO_TO_NEXT_PRESS": {
            "type": "float",
            "label": "嵌入延迟最大比例",
            "tier": "advanced",
            "depends_on": [
                {"section": "recorder", "key": "ENABLE_TRACK_SIMPLIFY", "value": True},
                {"section": "recorder", "key": "ENABLE_ACTION_DELAY_EMBEDDING", "value": True},
            ],
        },
        "MIN_SPEED_PX_PER_SEC": {"type": "float", "label": "低速滤噪阈值(px/s)", "tier": "advanced"},
        "ENABLE_ULTRA_LOW_JITTER_RECORD": {"type": "bool", "label": "未开放: 超低抖动录制", "tier": "debug"},
        "ULTRA_LOW_JITTER_MOUSE_SAMPLE_INTERVAL_MS": {
            "type": "float",
            "label": "未开放: 超低抖动采样间隔",
            "tier": "debug",
            "depends_on": [{"section": "recorder", "key": "ENABLE_ULTRA_LOW_JITTER_RECORD", "value": True}],
        },
        "ULTRA_LOW_JITTER_DISABLE_LOW_SPEED_FILTER": {
            "type": "bool",
            "label": "未开放: 关闭低速滤波",
            "tier": "debug",
            "depends_on": [{"section": "recorder", "key": "ENABLE_ULTRA_LOW_JITTER_RECORD", "value": True}],
        },
        "BOOST_PROCESS_PRIORITY": {"type": "bool", "label": "提升录制进程优先级", "tier": "advanced"},
        "BIND_CPU_CORE": {"type": "int", "label": "绑定 CPU 核心(-1 关闭)", "tier": "advanced"},
        "OUTPUT_DIR": {"type": "str", "label": "录制输出目录", "tier": "basic"},
        "OUTPUT_BASE_NAME": {"type": "str", "label": "录制输出基础名", "tier": "basic"},
    },
    "simplify_tool": {
        "SCENE_PRESET": {"type": "str", "label": "离线预设", "tier": "basic", "options": ["fps", "desktop", "rpg3d", "custom"]},
        "CUSTOM_CFG.pipeline": {"type": "list", "label": "自定义化简流水线", "tier": "advanced"},
        "CUSTOM_CFG.rdp_epsilon": {"type": "float", "label": "自定义 RDP Epsilon", "tier": "advanced"},
        "CUSTOM_CFG.intent_angle_threshold_deg": {"type": "float", "label": "自定义意图角度阈值", "tier": "advanced"},
        "CUSTOM_CFG.intent_speed_ratio_threshold": {"type": "float", "label": "自定义速度阈值", "tier": "advanced"},
        "CUSTOM_CFG.intent_min_dt_ms": {"type": "float", "label": "自定义最小段时长(ms)", "tier": "advanced"},
        "CUSTOM_CFG.sliding_window_size": {"type": "int", "label": "自定义滑动窗口", "tier": "advanced"},
        "CUSTOM_CFG.merge_gap_ms": {"type": "float", "label": "自定义轨迹合并间隔(ms)", "tier": "advanced"},
        "CUSTOM_CFG.min_manhattan_after_simplify": {"type": "float", "label": "自定义最小曼哈顿阈值", "tier": "advanced"},
        "CUSTOM_CFG.allow_cross_action_merge": {"type": "bool", "label": "自定义跨动作合并", "tier": "advanced"},
        "CUSTOM_CFG.enable_action_delay_embedding": {"type": "bool", "label": "自定义动作延迟嵌入", "tier": "advanced"},
        "CUSTOM_CFG.action_embed_delay_ms": {
            "type": "float",
            "label": "自定义动作嵌入延迟(ms)",
            "tier": "advanced",
            "depends_on": [{"section": "simplify_tool", "key": "CUSTOM_CFG.enable_action_delay_embedding", "value": True}],
        },
        "CUSTOM_CFG.action_embed_max_ratio_to_next_press": {
            "type": "float",
            "label": "自定义动作嵌入比例",
            "tier": "advanced",
            "depends_on": [{"section": "simplify_tool", "key": "CUSTOM_CFG.enable_action_delay_embedding", "value": True}],
        },
    },
    "interception": {
        "INTERCEPTION_CAPTURE_PHYSICAL_INPUT": {"type": "bool", "label": "未开放: 捕获物理输入", "tier": "debug"},
        "INTERCEPTION_KEYBOARD_REDUNDANT_DEVICES": {"type": "int", "label": "键盘冗余设备数", "tier": "advanced"},
        "INTERCEPTION_KEYBOARD_SCAN_INTERVAL": {"type": "float", "label": "键盘设备扫描间隔(s)", "tier": "advanced"},
        "INTERCEPTION_MOUSE_LEFT_DOWN_LIMITED": {"type": "bool", "label": "左键按下限制模式", "tier": "advanced"},
        "INTERCEPTION_MOUSE_LEFT_REDUNDANT_DOWN_DEVICES": {
            "type": "int",
            "label": "左键按下冗余设备数",
            "tier": "advanced",
            "depends_on": [{"section": "interception", "key": "INTERCEPTION_MOUSE_LEFT_DOWN_LIMITED", "value": True}],
        },
        "INTERCEPTION_MOUSE_LEFT_UP_LIMITED_RELEASE": {"type": "bool", "label": "左键抬起限制模式", "tier": "advanced"},
        "INTERCEPTION_MOUSE_LEFT_REDUNDANT_UP_DEVICES": {
            "type": "int",
            "label": "左键抬起冗余设备数",
            "tier": "advanced",
            "depends_on": [{"section": "interception", "key": "INTERCEPTION_MOUSE_LEFT_UP_LIMITED_RELEASE", "value": True}],
        },
    },
    "webui": {
        "ALLOW_MULTI_MACRO_BIND_PER_KEY": {
            "type": "bool",
            "label": "允许单按键绑定多宏并发",
            "tier": "advanced",
        },
    },
    "automation_editor": {
        "HOTKEY_RUN": {"type": "str", "label": "运行快捷键", "tier": "basic", "hint": "留空则关闭", "options": ["", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"]},
        "HOTKEY_PAUSE": {"type": "str", "label": "暂停/继续快捷键", "tier": "basic", "hint": "留空则关闭", "options": ["", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"]},
        "HOTKEY_STOP": {"type": "str", "label": "停止快捷键", "tier": "basic", "hint": "留空则关闭", "options": ["", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"]},
        "HOTKEY_FULLSCREEN": {"type": "str", "label": "全屏快捷键", "tier": "basic", "hint": "留空则关闭", "options": ["", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"]},
        "HOTKEY_ENABLED": {"type": "bool", "label": "启用编辑器快捷键", "tier": "basic"},
    },
}

