def register(registry):
    registry.register_node({
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

    registry.register_node({
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

    registry.register_node({
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

    registry.register_node({
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

    registry.register_node({
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

    registry.register_node({
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
            "steps": {"type": "string", "default": "", "description": "步骤描述"},
            "retry": {"type": "boolean", "default": True, "description": "失败后重试"},
            "max_retries": {"type": "number", "default": 100, "description": "最大重试次数"},
        },
        "handler": "_handle_seq_check",
    })

    registry.register_node({
        "type": "control/state_machine",
        "category": "control",
        "display_name": "状态机",
        "color": "#a855f7",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "done", "type": "flow"}],
        "params_schema": {
            "states": {"type": "string", "default": "", "description": "状态列表"},
            "fail_state": {"type": "string", "default": "", "description": "失败回退状态名"},
        },
        "handler": "_handle_state_machine",
    })

    registry.register_node({
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

    registry.register_node({
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
