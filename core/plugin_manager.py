# -*- coding: utf-8 -*-
import importlib
import importlib.util
import json
import logging
import sys
from pathlib import Path

from core.plugin_context import PluginContext

_logger = logging.getLogger("plugin")


class PluginManager:
    _plugins = {}
    _context = None
    _plugins_dir = None
    _global_vars = {}

    @classmethod
    def scan(cls, plugins_dir):
        plugins_dir = Path(plugins_dir)
        cls._plugins_dir = plugins_dir
        if not plugins_dir.exists():
            _logger.info("[PluginManager] 插件目录不存在: %s", plugins_dir)
            return

        cls._context = PluginContext(
            emit_fn=cls._emit_to_window,
            var_get_fn=cls._var_get,
            var_set_fn=cls._var_set,
        )

        for folder in sorted(plugins_dir.iterdir()):
            if not folder.is_dir():
                continue
            cls._load_single(folder)

    @classmethod
    def _load_single(cls, folder):
        manifest_path = folder / "manifest.json"
        if not manifest_path.exists():
            return
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            plugin_id = manifest.get("id", folder.name)
            if not manifest.get("id"):
                manifest["id"] = plugin_id

            entry = {
                "manifest": manifest,
                "module": None,
                "actions": [],
                "folder": str(folder),
            }

            backend_file = manifest.get("backend", "backend.py")
            backend_path = folder / backend_file
            if backend_path.exists():
                module = cls._load_backend(plugin_id, backend_path)
                if module and hasattr(module, "register"):
                    actions = module.register()
                    entry["module"] = module
                    entry["actions"] = actions if actions else []

            cls._plugins[plugin_id] = entry
            _logger.info("[PluginManager] 插件已加载: %s", plugin_id)
        except Exception as e:
            _logger.error("[PluginManager] 插件 %s 加载失败: %s", folder.name, e)

    @classmethod
    def _load_backend(cls, plugin_id, path):
        module_name = f"_plugin_{plugin_id}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, str(path))
            if spec is None or spec.loader is None:
                _logger.error("[PluginManager] 无法加载后端模块: %s", path)
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            return module
        except Exception as e:
            _logger.error("[PluginManager] 后端模块加载异常 %s: %s", plugin_id, e)
            return None

    @classmethod
    def list_all(cls):
        items = []
        for plugin_id, entry in cls._plugins.items():
            manifest = entry["manifest"]
            items.append({
                "id": plugin_id,
                "name": manifest.get("name", plugin_id),
                "version": manifest.get("version", "0.0.0"),
                "description": manifest.get("description", ""),
                "icon": manifest.get("icon", "fa-solid fa-puzzle-piece"),
                "color": manifest.get("color", "#a855f7"),
                "nodes": manifest.get("nodes", []),
                "has_backend": entry["module"] is not None,
                "actions": [a.get("action", "") for a in entry["actions"]],
            })
        return items

    @classmethod
    def get_node_js(cls, plugin_id):
        entry = cls._plugins.get(plugin_id)
        if not entry:
            return None
        folder = Path(entry["folder"])
        node_path = folder / "node.js"
        if not node_path.exists():
            return None
        try:
            return node_path.read_text(encoding="utf-8")
        except Exception as e:
            _logger.error("[PluginManager] 读取 node.js 失败 %s: %s", plugin_id, e)
            return None

    @classmethod
    def execute(cls, plugin_id, action, params=None, context=None):
        entry = cls._plugins.get(plugin_id)
        if not entry:
            _logger.error("[PluginManager] 插件 %s 未加载", plugin_id)
            return {"ok": False, "error": f"插件 {plugin_id} 未加载"}
        if not entry["module"]:
            _logger.error("[PluginManager] 插件 %s 无后端", plugin_id)
            return {"ok": False, "error": f"插件 {plugin_id} 无后端"}
        try:
            # 使用传入的context（含执行期能力），或回退到全局context
            ctx = context or cls._context
            return entry["module"].execute(action, params or {}, ctx)
        except Exception as e:
            _logger.error("[PluginManager] 插件执行错误 %s: %s", plugin_id, e)
            return {"ok": False, "error": f"插件 {plugin_id} 执行错误: {e}"}

    @classmethod
    def reload(cls, plugin_id):
        entry = cls._plugins.get(plugin_id)
        if not entry:
            return False
        folder = Path(entry["folder"])
        old_module_name = f"_plugin_{plugin_id}"
        if old_module_name in sys.modules:
            del sys.modules[old_module_name]
        cls._plugins.pop(plugin_id, None)
        cls._load_single(folder)
        if plugin_id in cls._plugins:
            try:
                from automation.registry import PluginRegistry, register_plugin_nodes
                PluginRegistry.unregister_plugin_nodes()
                register_plugin_nodes()
            except Exception as e:
                _logger.warning("[PluginManager] 重载后更新节点注册表失败: %s", e)
            cls._emit_to_window("plugin_reloaded", {"plugin_id": plugin_id})
        return plugin_id in cls._plugins

    @classmethod
    def get_manifest(cls, plugin_id):
        entry = cls._plugins.get(plugin_id)
        if not entry:
            return None
        return entry["manifest"]

    @classmethod
    def _emit_to_window(cls, event_name, data):
        try:
            import json as _json
            import webview
            window = webview.windows[0] if webview.windows else None
            if window:
                payload = _json.dumps({"event_name": event_name, "data": data}, ensure_ascii=False)
                js_code = (
                    "if(window._automationEvents&&window._automationEvents.onPluginEvent)"
                    "{window._automationEvents.onPluginEvent(" + payload + ");}"
                )
                try:
                    window.evaluate_js(js_code)
                except Exception as eval_err:
                    _logger.warning("[PluginManager] evaluate_js 直接调用失败，尝试延迟重试: %s", eval_err)
                    import threading
                    def _retry():
                        try:
                            window.evaluate_js(js_code)
                        except Exception as retry_err:
                            _logger.error("[PluginManager] evaluate_js 延迟重试也失败: %s", retry_err)
                    threading.Timer(0.1, _retry).start()
        except Exception as e:
            _logger.error("[PluginManager] emit_to_window 失败: %s", e)

    @classmethod
    def _var_get(cls, name, default=None):
        return cls._global_vars.get(name, default)

    @classmethod
    def _var_set(cls, name, value):
        cls._global_vars[name] = value
