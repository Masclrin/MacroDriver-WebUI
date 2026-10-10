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
            # 尽力应用 ext 钩子（旧引擎未就绪时会在 list_ext_commands 里补做）
            try:
                cls.apply_ext_hooks(plugin_id)
            except Exception:
                pass
        except Exception as e:
            _logger.error("[PluginManager] 插件 %s 加载失败: %s", folder.name, e)

    # ── T2-3：ext 附加指令注册钩子 ──────────────────────────────
    @classmethod
    def apply_ext_hooks(cls, plugin_id=None):
        """让插件参与 ext 附加指令（描述符 + 处理器）。

        约定：
          · manifest.json 可选 ``"ext_commands": [ {描述符}, ... ]``  → 只声明描述符
          · backend.py   可选 ``def register_ext(api):``              → 注册处理器
            api.register_handler(name, handler, spec=None)
            api.register_command(spec)

        可重复调用（注册是幂等的）；旧引擎尚未加载时会静默跳过，
        由 ``list_ext_commands`` 接口在引擎就绪后再次触发。
        """
        try:
            from automation.engine import _get_old_engine
            oe = _get_old_engine()
        except Exception:
            return 0

        applied = 0
        for pid, entry in list(cls._plugins.items()):
            if plugin_id is not None and pid != plugin_id:
                continue
            manifest = entry.get("manifest") or {}
            module = entry.get("module")

            # 1) manifest 只声明描述符
            for spec in (manifest.get("ext_commands") or []):
                try:
                    s = dict(spec)
                    s.setdefault("plugin", pid)
                    oe.register_ext_command(s)
                    applied += 1
                except Exception as e:
                    _logger.error("[PluginManager] ext 描述符注册失败 %s: %s", pid, e)

            # 2) backend 注册处理器（可同时带描述符）
            if module is not None and hasattr(module, "register_ext"):
                class _ExtApi:
                    def __init__(self, plugin_id_):
                        self.plugin_id = plugin_id_

                    def register_handler(self, name, handler, spec=None):
                        s = None
                        if spec is not None:
                            s = dict(spec)
                            s.setdefault("plugin", self.plugin_id)
                        return oe.register_ext_handler(name, handler, spec=s)

                    def register_command(self, spec):
                        s = dict(spec)
                        s.setdefault("plugin", self.plugin_id)
                        return oe.register_ext_command(s)

                try:
                    module.register_ext(_ExtApi(pid))
                    applied += 1
                except Exception as e:
                    _logger.error("[PluginManager] ext 钩子异常 %s: %s", pid, e)

        if applied:
            _logger.info("[PluginManager] ext 钩子已应用 %d 项", applied)
        return applied

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
