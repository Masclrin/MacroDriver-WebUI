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

    @classmethod
    def unregister_plugin_nodes(cls):
        to_remove = [k for k in cls._node_types if k.startswith("plugin/")]
        for k in to_remove:
            del cls._node_types[k]


def register_builtin_nodes():
    from automation.nodes import (
        register_action_nodes,
        register_control_nodes,
        register_detection_nodes,
        register_variable_nodes,
        register_preset_nodes,
        register_utility_nodes,
        register_monitor_nodes,
        register_flow_nodes,
    )
    register_action_nodes(PluginRegistry)
    register_control_nodes(PluginRegistry)
    register_detection_nodes(PluginRegistry)
    register_variable_nodes(PluginRegistry)
    register_preset_nodes(PluginRegistry)
    register_utility_nodes(PluginRegistry)
    register_monitor_nodes(PluginRegistry)
    register_flow_nodes(PluginRegistry)
    register_plugin_nodes()


def register_plugin_nodes():
    try:
        from core.plugin_manager import PluginManager
        import json
        plugins = PluginManager.list_all()
        for plugin_info in plugins:
            plugin_id = plugin_info["id"]
            manifest = PluginManager.get_manifest(plugin_id)
            if not manifest:
                continue
            node_ids = manifest.get("nodes", [])
            color = manifest.get("color", "#a855f7")
            icon = manifest.get("icon", "fa-solid fa-puzzle-piece")
            node_display_names = manifest.get("node_display_names", {})
            for node_id in node_ids:
                type_key = f"plugin/{node_id}"
                if PluginRegistry.get_node(type_key):
                    continue
                display_name = node_display_names.get(node_id, node_id.replace("_", " ").title())
                node_params = manifest.get("node_params", {}).get(node_id, {})
                if not node_params:
                    node_params = {"__placeholder": {"type": "string", "default": "", "description": "此节点无可配置参数"}}
                node_inputs = manifest.get("node_inputs", {}).get(node_id, [{"name": "in", "type": "flow"}])
                node_outputs = manifest.get("node_outputs", {}).get(node_id, [{"name": "next", "type": "flow"}])
                PluginRegistry.register_node({
                    "type": type_key,
                    "category": "plugin",
                    "display_name": display_name,
                    "color": color,
                    "icon": icon,
                    "inputs": node_inputs,
                    "outputs": node_outputs,
                    "params_schema": node_params,
                    "handler": f"_plugin_{plugin_id}",
                    "_plugin_id": plugin_id,
                })
    except Exception as e:
        print(f"[Registry] 注册插件节点失败: {e}")
