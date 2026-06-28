def register(registry):
    registry.register_node({
        "type": "flow/start",
        "category": "flow",
        "display_name": "开始",
        "color": "#99ff00ff",
        "inputs": [],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "boost_priority": {"type": "boolean", "default": True, "description": "提升优先级", "display_names": {"true": "是(推荐)", "false": "否"}},
            "affinity_enabled": {"type": "boolean", "default": False, "description": "绑核执行", "display_names": {"true": "启用绑核", "false": "不绑核"}},
            "affinity_core": {"type": "number", "default": -1, "minimum": -1, "maximum": 63, "description": "主线程绑核核心(-1=自动选最后核心, 0-N=指定核心)", "showWhen": "affinity_enabled=true"},
        },
        "handler": "_handle_flow_start",
    })

    registry.register_node({
        "type": "flow/end",
        "category": "flow",
        "display_name": "结束",
        "color": "#ef4444",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [],
        "params_schema": {},
        "handler": "_handle_flow_end",
    })
