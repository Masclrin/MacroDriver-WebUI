# -*- coding: utf-8 -*-
from core.paths import BASE_DIR


def _ok(data=None):
    return {"ok": True, "data": data, "error": None}


def _err(msg):
    return {"ok": False, "data": None, "error": str(msg)}


class PluginApiMixin:
    def _init_plugins(self):
        from core.plugin_manager import PluginManager
        plugins_dir = BASE_DIR / "plugins"
        PluginManager.scan(plugins_dir)

    def list_plugins(self):
        from core.plugin_manager import PluginManager
        try:
            items = PluginManager.list_all()
            return _ok(items)
        except Exception as e:
            return _err(f"列出插件失败: {e}")

    def get_plugin_node_js(self, plugin_id):
        from core.plugin_manager import PluginManager
        try:
            content = PluginManager.get_node_js(plugin_id)
            if content is None:
                return _err(f"插件 {plugin_id} 的 node.js 不存在")
            return _ok({"content": content})
        except Exception as e:
            return _err(f"获取插件节点定义失败: {e}")

    def call_plugin(self, plugin_id, action, params=None):
        from core.plugin_manager import PluginManager
        try:
            result = PluginManager.execute(plugin_id, action, params or {})
            return result
        except Exception as e:
            return _err(f"调用插件失败: {e}")

    def reload_plugin(self, plugin_id):
        from core.plugin_manager import PluginManager
        try:
            success = PluginManager.reload(plugin_id)
            if success:
                return _ok({"reloaded": plugin_id})
            return _err(f"重载插件 {plugin_id} 失败")
        except Exception as e:
            return _err(f"重载插件失败: {e}")

    def unregister_plugin_nodes(self):
        from automation.registry import PluginRegistry
        try:
            PluginRegistry.unregister_plugin_nodes()
            return _ok({"unregistered": True})
        except Exception as e:
            return _err(f"注销插件节点失败: {e}")
