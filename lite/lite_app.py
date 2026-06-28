# -*- coding: utf-8 -*-
from __future__ import annotations

import ctypes
import sys
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

APP_VERSION = "3.1.1-lite"
APP_NAME = "MacroDriver Lite"


def _print_banner():
    print()
    print("=" * 56)
    print(f"  宏驱动精简版 v{APP_VERSION}")
    print("  高精度宏驱动控制台 (Lite)")
    print("=" * 56)
    print(f"  Python:  {sys.version.split()[0]}")
    print(f"  平台:    {sys.platform}")
    print(f"  工作目录: {sys.path[0] if sys.path else '.'}")
    print("=" * 56)
    print()


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

from lite.lite_bridge import LiteBridge
from core.paths import BASE_DIR, MACRO_ROOT, RESOURCE_DIR


def run_ui() -> None:
    _print_banner()

    if not MACRO_ROOT.exists():
        MACRO_ROOT.mkdir(parents=True, exist_ok=True)

    bridge = LiteBridge()

    html_path = (RESOURCE_DIR / "lite" / "webui_lite" / "index.html").resolve()
    if not html_path.exists():
        raise FileNotFoundError("前端页面不存在: lite/webui_lite/index.html")

    window = webview.create_window(
        title="宏驱动精简版",
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

    webview.start(debug=False)


if __name__ == "__main__":
    run_ui()
