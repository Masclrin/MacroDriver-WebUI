# -*- coding: utf-8 -*-
from __future__ import annotations

import ctypes
import sys

def _init_per_monitor_dpi():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        print("[DPI] SetProcessDpiAwareness(2) - PerMonitorV2")
        return True
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
        print("[DPI] SetProcessDPIAware() - System DPI Aware")
        return True
    except Exception:
        pass
    print("[DPI] WARNING: Could not set DPI awareness")
    return False

_init_per_monitor_dpi()

import webview

from bridge.base import MacroBridgeBase
from bridge.metadata import PARAM_DOCS, PARAM_SCHEMA, SECTION_META
from bridge.params_api import ParamsApiMixin
from bridge.recorder_api import RecorderApiMixin
from bridge.macro_binding_api import MacroBindingApiMixin
from bridge.listener_api import ListenerApiMixin
from bridge.macro_simplify_api import MacroSimplifyApiMixin

try:
    from bridge.automation_api import AutomationApiMixin
    _has_automation = True
except ImportError:
    _has_automation = False
    class AutomationApiMixin:
        pass

try:
    from macro_io.parser import MacroFileApiMixin, MACRO_ROOT
    _has_macro_io = True
except ImportError:
    _has_macro_io = False
    class MacroFileApiMixin:
        pass
    from core.paths import MACRO_ROOT

from core.paths import BASE_DIR


class MacroBridge(
    MacroBridgeBase,
    ParamsApiMixin,
    RecorderApiMixin,
    MacroFileApiMixin,
    MacroBindingApiMixin,
    ListenerApiMixin,
    MacroSimplifyApiMixin,
    AutomationApiMixin,
):
    webview = webview

    def __init__(self):
        super().__init__()
        if _has_automation:
            self._init_automation()


def run_ui() -> None:
    if not MACRO_ROOT.exists():
        MACRO_ROOT.mkdir(parents=True, exist_ok=True)

    bridge = MacroBridge()

    html_path = (BASE_DIR / "webui" / "index.html").resolve()
    if not html_path.exists():
        raise FileNotFoundError("前端页面不存在: webui/index.html")

    window = webview.create_window(
        title="宏驱动控制台",
        url=html_path.as_uri(),
        js_api=bridge,
        width=1200,
        height=900,
        min_size=(800, 600),
        text_select=True,
    )

    bridge.set_window(window)

    def _on_closing(*_args):
        bridge.shutdown()

    window.events.closing += _on_closing

    webview.start(debug=True)


if __name__ == "__main__":
    run_ui()
