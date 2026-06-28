# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib

import webview

from bridge.base import MacroBridgeBase
from bridge.params_api import ParamsApiMixin
from bridge.listener_api import ListenerApiMixin
from bridge.extra_api import ExtraApiMixin
from bridge.macro_binding_api import MacroBindingApiMixin
from bridge.editor_record_api import EditorRecordApiMixin

try:
    from macro_io.parser import MacroFileApiMixin
    _has_macro_io = True
except ImportError:
    _has_macro_io = False
    class MacroFileApiMixin:
        pass

from lite.lite_metadata import LITE_PARAM_DOCS, LITE_PARAM_SCHEMA, LITE_SECTION_META


class LiteBridge(
    MacroBridgeBase,
    ParamsApiMixin,
    MacroFileApiMixin,
    MacroBindingApiMixin,
    ListenerApiMixin,
    ExtraApiMixin,
    EditorRecordApiMixin,
):
    webview = webview

    SECTION_META = LITE_SECTION_META
    PARAM_DOCS = LITE_PARAM_DOCS
    PARAM_SCHEMA = LITE_PARAM_SCHEMA

    def __init__(self):
        self.recorder = None
        self.simplify_tool = None

        MacroBridgeBase.__init__(self)

        self.recorder = None
        self.simplify_tool = None

    def shutdown(self):
        try:
            self.stop_all_macros()
        except Exception:
            pass
        try:
            self.stop_global_listeners()
        except Exception:
            pass
        try:
            if getattr(self, '_ed_rec_active', False):
                self.editor_record_stop()
        except Exception:
            pass

    def get_dashboard_snapshot(self):
        if self.executor is None:
            return self._ok(active_macros=0, global_paused=False, cache_loading=False, recording={})
        with self.executor.active_macros_lock:
            active_count = 0
            for info in self.executor.active_macros.values():
                stop_event = info.get("stop_event")
                thread = info.get("thread")
                if stop_event is not None and stop_event.is_set():
                    continue
                if thread is not None and not thread.is_alive():
                    continue
                active_count += 1
            paused = self.executor.global_trigger_paused
            loading = self.executor.macro_loading_in_progress
        return self._ok(
            active_macros=active_count,
            global_paused=paused,
            cache_loading=loading,
            recording={},
        )

    def _check_dxgi(self):
        return {"ok": True, "available": False, "warning": "精简版不包含 DXGI 模块"}

    def _check_packages(self):
        results = {"ok": True, "installed": [], "missing": []}
        required = {"pynput": "pynput", "pywebview": "webview"}
        for pkg, import_name in required.items():
            try:
                importlib.import_module(import_name)
                results["installed"].append(pkg)
            except ImportError:
                results["missing"].append(pkg)
                results["ok"] = False
        return results

    def get_feature_list(self):
        features = [
            {"name": "宏执行绑定", "icon": "fa-solid fa-play", "desc": "绑定热键触发宏执行，支持多宏并行、重复执行、按键模式"},
            {"name": "宏编辑保存", "icon": "fa-solid fa-pen-to-square", "desc": "可视化查看和修改宏序列，支持插入、删除、拖拽排序、批量注释"},
            {"name": "简单录制", "icon": "fa-solid fa-circle-dot", "desc": "编辑器内录制键鼠动作序列，录制结果直接插入当前宏"},
            {"name": "全局参数", "icon": "fa-solid fa-sliders", "desc": "配置执行引擎和 Interception 参数，支持导入导出"},
            {"name": "全局控制台", "icon": "fa-solid fa-terminal", "desc": "实时查看系统运行日志"},
            {"name": "额外功能", "icon": "fa-solid fa-toolbox", "desc": "环境检查、驱动管理、系统信息等工具"},
        ]
        return self._ok(features=features)

    def open_console_popout(self):
        try:
            from core.paths import RESOURCE_DIR
            html_path = (RESOURCE_DIR / "lite" / "webui_lite" / "console_popout.html").resolve()
            if not html_path.exists():
                return self._fail("弹出窗口页面不存在")
            popout_window = webview.create_window(
                title="控制台日志 - 宏驱动精简版",
                url=html_path.as_uri(),
                js_api=self,
                width=720,
                height=480,
                min_size=(400, 300),
                text_select=True,
            )
            return self._ok(opened=True)
        except Exception as e:
            return self._fail(f"打开弹出窗口失败: {e}")
