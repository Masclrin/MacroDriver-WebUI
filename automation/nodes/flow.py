def register(registry):
    registry.register_node({
        "type": "flow/start",
        "category": "flow",
        "display_name": "开始",
        "color": "#99ff00ff",
        "inputs": [],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {},
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
