# -*- coding: utf-8 -*-
import logging
import ctypes
from ctypes import (c_uint, c_long, c_longlong, c_int, c_void_p, byref,
                    sizeof, c_ubyte, c_wchar_p)
import threading
import time
import re
import random
import os

_logger = logging.getLogger("plugin.notify")

_BUILTIN_VARIABLES = {
    "timestamp": lambda: str(int(time.time() * 1000)),
    "timestamp_s": lambda: str(int(time.time())),
    "date": lambda: time.strftime("%Y-%m-%d"),
    "time": lambda: time.strftime("%H:%M:%S"),
    "datetime": lambda: time.strftime("%Y-%m-%d %H:%M:%S"),
    "datetime_compact": lambda: time.strftime("%Y%m%d_%H%M%S"),
    "random": lambda: str(int(time.time() * 1000) % 100000),
    "random_int": lambda: str(random.randint(0, 999999)),
    "year": lambda: time.strftime("%Y"),
    "month": lambda: time.strftime("%m"),
    "day": lambda: time.strftime("%d"),
    "hour": lambda: time.strftime("%H"),
    "minute": lambda: time.strftime("%M"),
    "second": lambda: time.strftime("%S"),
    "weekday": lambda: str(time.localtime().tm_wday),
    "pid": lambda: str(os.getpid()),
}


def _resolve_value(value, context):
    if not isinstance(value, str):
        return value
    pattern = re.compile(r'\$\{([^}]+)\}')
    matches = pattern.findall(value)
    if not matches:
        return value
    if len(matches) == 1 and value == f"${{{matches[0]}}}":
        var_name = matches[0]
        if var_name in _BUILTIN_VARIABLES:
            return _BUILTIN_VARIABLES[var_name]()
        var_val = context.get_variable(var_name)
        if var_val is not None:
            if isinstance(var_val, float) and var_val == int(var_val):
                return int(var_val)
            return var_val
        if '.' in var_name:
            parts = var_name.split('.', 1)
            if len(parts) == 2:
                resolved = _resolve_node_output(parts[0], parts[1], context)
                if resolved is not None:
                    return resolved
        cr_val = context.get_check_result(var_name)
        if cr_val is not None:
            return cr_val
        return ""
    result = value
    for var_name in matches:
        if var_name in _BUILTIN_VARIABLES:
            builtin_val = _BUILTIN_VARIABLES[var_name]()
            result = result.replace(f"${{{var_name}}}", builtin_val)
            continue
        var_val = context.get_variable(var_name)
        if var_val is not None:
            display_val = int(var_val) if isinstance(var_val, float) and var_val == int(var_val) else var_val
            result = result.replace(f"${{{var_name}}}", str(display_val))
        elif '.' in var_name:
            parts = var_name.split('.', 1)
            if len(parts) == 2:
                resolved = _resolve_node_output(parts[0], parts[1], context)
                if resolved is not None:
                    result = result.replace(f"${{{var_name}}}", str(resolved))
                    continue
            cr_val = context.get_check_result(var_name)
            if cr_val is not None:
                result = result.replace(f"${{{var_name}}}", str(cr_val))
            else:
                result = result.replace(f"${{{var_name}}}", "")
        else:
            cr_val = context.get_check_result(var_name)
            if cr_val is not None:
                result = result.replace(f"${{{var_name}}}", str(cr_val))
            else:
                result = result.replace(f"${{{var_name}}}", "")
    return result


def _resolve_node_output(node_id_str, output_name, context):
    graph = context.get_graph()
    if not graph:
        return None
    node = graph.nodes.get(node_id_str)
    if not node:
        return None
    if node.type.startswith("utility/"):
        ctx = context.get_exec_context()
        if ctx:
            try:
                from automation.handlers import NODE_HANDLERS
                from automation.registry import PluginRegistry
                node_def = PluginRegistry.get_node(node.type)
                if node_def and isinstance(node_def, dict):
                    handler_name = node_def.get("handler")
                    handler = NODE_HANDLERS.get(handler_name) if handler_name else None
                    if handler:
                        handler(node, ctx)
            except Exception as e:
                _logger.warning("[notify] 动态执行节点 %s 失败: %s", node_id_str, e)
    cr_key = f"{node_id_str}.{output_name}"
    cr_val = context.get_check_result(cr_key)
    if cr_val is not None:
        return cr_val
    for nid, n in graph.nodes.items():
        if n.type == "utility/bookmark" and n.params.get("name") == node_id_str:
            return n.params.get(output_name, 0)
    return None

# ============== Win32 结构体（64 位安全） ==============

class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", c_void_p), ("message", c_uint),
        ("wParam", c_void_p), ("lParam", c_void_p),
        ("time", c_uint), ("pt_x", c_long), ("pt_y", c_long),
    ]

class _RECT(ctypes.Structure):
    _fields_ = [("left", c_long), ("top", c_long),
                ("right", c_long), ("bottom", c_long)]

class _PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", c_void_p), ("fErase", c_int),
        ("rcPaint", _RECT), ("fRestore", c_int),
        ("fIncUpdate", c_int), ("rgbReserved", c_ubyte * 32),
    ]

class _LOGFONTA(ctypes.Structure):
    _fields_ = [
        ("lfHeight", c_long), ("lfWidth", c_long),
        ("lfEscapement", c_long), ("lfOrientation", c_long),
        ("lfWeight", c_long),
        ("lfItalic", c_ubyte), ("lfUnderline", c_ubyte), ("lfStrikeOut", c_ubyte),
        ("lfCharSet", c_ubyte), ("lfOutPrecision", c_ubyte),
        ("lfClipPrecision", c_ubyte), ("lfQuality", c_ubyte),
        ("lfPitchAndFamily", c_ubyte),
        ("lfFaceName", ctypes.c_char * 32),
    ]

class _WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", c_uint), ("lpfnWndProc", c_void_p),
        ("cbClsExtra", c_int), ("cbWndExtra", c_int),
        ("hInstance", c_void_p), ("hIcon", c_void_p),
        ("hCursor", c_void_p), ("hbrBackground", c_void_p),
        ("lpszMenuName", c_wchar_p), ("lpszClassName", c_wchar_p),
    ]


class _PopupWindow:
    """使用 Win32 API 自绘现代风格桌面弹窗"""

    # 主题色（正确 BGR 格式：0x00BBGGRR）
    _ACCENT = {
        "default": 0xF6823B,  # #3b82f6 蓝
        "info":    0xD4B606,  # #06b6d4 青
        "success": 0x5EC522,  # #22c55e 绿
        "warning": 0x08B3EA,  # #eab308 黄
        "error":   0x4444EF,  # #ef4444 红
    }
    # 背景色（修复 BGR 转换）
    _BG        = 0x2E1E1E   # #1E1E2E 深色背景
    _BORDER    = 0x442D2D   # #2D2D44 边框
    _SEP       = 0x402A2A   # #2A2A40 分隔线
    _TITLE_CLR = 0xF2EAEA   # #EAEAF2 标题文字
    _TEXT_CLR  = 0xAC9898   # #9898AC 内容文字
    _CLOSE_CLR = 0x725C5C   # #5C5C72 关闭按钮
    _PROG_BG   = 0x3A2424   # #24243A 进度条背景
    _RADIUS    = 10
    _BAR_W     = 4
    _PAD       = 14

    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32
        self.kernel32 = ctypes.windll.kernel32
        self._proc_refs = []

    def _calc_text_height(self, text, width, font_size):
        """用 DrawTextW DT_CALCRECT 计算文本在指定宽度下换行后的高度(px)。
        失败返回 None。"""
        if not text:
            return 0
        hdc = self.user32.GetDC(0)
        if not hdc:
            return None
        try:
            lf = _LOGFONTA()
            lf.lfHeight = -font_size if font_size else -12
            lf.lfWeight = 400
            lf.lfFaceName = b"Microsoft YaHei\x00"
            hf = self.gdi32.CreateFontIndirectA(byref(lf))
            if not hf:
                return None
            of = self.gdi32.SelectObject(hdc, hf)
            try:
                rc = _RECT(0, 0, width, 0)
                # DT_WORDBREAK | DT_EDITCONTROL | DT_CALCRECT
                flags = 0x04 | 0x40 | 0x400
                self.user32.DrawTextW(hdc, text, -1, byref(rc), flags)
                return rc.bottom - rc.top
            finally:
                self.gdi32.SelectObject(hdc, of)
                self.gdi32.DeleteObject(hf)
        except Exception:
            return None
        finally:
            self.user32.ReleaseDC(0, hdc)

    def show(self, title, message, sound="default", duration_ms=3000,
             position="bottom-right", width=380, height=140, font_size=12):
        # 根据消息内容动态扩展窗口高度，防止文字过多被截断
        try:
            avail_w = width - (self._PAD + self._BAR_W + 10) - self._PAD
            text_h = self._calc_text_height(message, avail_w, font_size)
            if text_h is not None:
                sep_y = self._PAD + 26
                calc_height = sep_y + 10 + text_h + 18 + 10
                height = max(height, calc_height)
        except Exception:
            pass
        screen = self._get_screen_size()
        x, y = self._calc_position(position, screen["width"], screen["height"], width, height)
        result = {"hwnd": None, "closed": False}
        t = threading.Thread(
            target=self._window_thread,
            args=(title, message, sound, duration_ms, x, y, width, height, font_size, result),
            daemon=True,
        )
        t.start()
        return result

    def _get_screen_size(self):
        return {"width": self.user32.GetSystemMetrics(0), "height": self.user32.GetSystemMetrics(1)}

    def _calc_position(self, pos, sw, sh, w, h):
        m, tb = 20, 40
        if pos == "top-right":    return sw - w - m, m
        if pos == "top-left":     return m, m
        if pos == "bottom-left":  return m, sh - h - m - tb
        if pos == "center":       return (sw - w) // 2, (sh - h) // 2
        return sw - w - m, sh - h - m - tb

    def _window_thread(self, title, message, sound, duration_ms,
                       x, y, width, height, font_size, result):
        accent = self._ACCENT.get(sound, self._ACCENT["default"])
        is64 = ctypes.sizeof(c_void_p) == 8
        _LR = c_longlong if is64 else c_long
        _WP = c_void_p if is64 else c_uint
        _LP = c_void_p if is64 else c_long
        WNDPROC = ctypes.WINFUNCTYPE(_LR, c_void_p, c_uint, _WP, _LP)

        self.user32.DefWindowProcW.argtypes = [c_void_p, c_uint, _WP, _LP]
        self.user32.DefWindowProcW.restype = _LR

        wd = {
            "w": width, "h": height,
            "title": title, "message": message,
            "accent": accent, "fs": font_size,
            "t0": time.time(), "dur": duration_ms / 1000.0,
            "_cb": None,
        }

        def _proc(hwnd, msg, wp, lp):
            if msg == 0x0002:
                cb = wd["_cb"]
                if cb in self._proc_refs:
                    self._proc_refs.remove(cb)
                self.user32.PostQuitMessage(0)
                return 0
            if msg == 0x0010:
                self.user32.DestroyWindow(hwnd)
                return 0
            if msg == 0x0113:
                if wp == 1:
                    self.user32.KillTimer(hwnd, 2)
                    self.user32.DestroyWindow(hwnd)
                elif wp == 2:
                    self.user32.InvalidateRect(hwnd, None, False)
                return 0
            if msg == 0x0201:
                px, py = lp & 0xFFFF, (lp >> 16) & 0xFFFF
                if wd["w"] - 40 <= px <= wd["w"] - self._PAD and 8 <= py <= 34:
                    self.user32.DestroyWindow(hwnd)
                    return 0
            if msg == 0x0084:
                return 2
            if msg == 0x000F:
                self._draw(hwnd, wd)
                return 0
            return self.user32.DefWindowProcW(hwnd, msg, wp, lp)

        callback = WNDPROC(_proc)
        wd["_cb"] = callback
        self._proc_refs.append(callback)

        hinst = self.kernel32.GetModuleHandleW(None)
        cls_name = "MacroNotify_" + str(int(time.time() * 1000))

        wc = _WNDCLASSW()
        wc.lpfnWndProc = ctypes.cast(callback, c_void_p).value
        wc.hInstance = hinst
        wc.hCursor = self.user32.LoadCursorW(0, 32512)
        wc.lpszClassName = cls_name

        if not self.user32.RegisterClassW(byref(wc)):
            _logger.error("[notify] RegisterClassW 失败")
            return

        hwnd = self.user32.CreateWindowExW(
            0x00000080 | 0x08000000 | 0x00000008,
            cls_name, title,
            0x80000000 | 0x10000000,
            x, y, width, height, 0, 0, hinst, 0)

        if not hwnd:
            _logger.error("[notify] CreateWindowExW 失败")
            return

        result["hwnd"] = hwnd

        try:
            dwm = ctypes.windll.dwmapi
            v = c_int(2)
            dwm.DwmSetWindowAttribute(hwnd, 2, byref(v), sizeof(c_int))
        except Exception:
            pass

        self.user32.InvalidateRect(hwnd, None, True)
        if duration_ms > 0:
            self.user32.SetTimer(hwnd, 1, duration_ms, 0)
        self.user32.SetTimer(hwnd, 2, 50, 0)

        m = _MSG()
        while self.user32.GetMessageW(byref(m), None, 0, 0) > 0:
            self.user32.TranslateMessage(byref(m))
            self.user32.DispatchMessageW(byref(m))

        result["closed"] = True

    def _fill_rrect(self, dc, x1, y1, x2, y2, rw, rh, color):
        rgn = self.gdi32.CreateRoundRectRgn(x1, y1, x2, y2, rw, rh)
        if not rgn:
            return
        brush = self.gdi32.CreateSolidBrush(color)
        self.gdi32.FillRgn(dc, rgn, brush)
        self.gdi32.DeleteObject(brush)
        self.gdi32.DeleteObject(rgn)

    def _draw(self, hwnd, wd):
        W, H = wd["w"], wd["h"]
        accent = wd["accent"]
        R = self._RADIUS
        P = self._PAD

        ps = _PAINTSTRUCT()
        hdc = self.user32.BeginPaint(hwnd, byref(ps))
        if not hdc:
            return

        mem = self.gdi32.CreateCompatibleDC(hdc)
        bmp = self.gdi32.CreateCompatibleBitmap(hdc, W, H)
        self.gdi32.SelectObject(mem, bmp)

        self._fill_rrect(mem, 0, 0, W - 1, H - 1, R * 2, R * 2, self._BORDER)
        ri = max(R - 1, 2)
        self._fill_rrect(mem, 1, 1, W - 2, H - 2, ri * 2, ri * 2, self._BG)

        bar_l, bar_t, bar_b, bw = P, P + 2, H - P - 14, self._BAR_W
        self._fill_rrect(mem, bar_l, bar_t, bar_l + bw, bar_b, bw * 2, bw * 2, accent)

        tx = bar_l + bw + 10
        self._text(mem, wd["title"], tx, P - 2, W - tx - 42, 26,
                   self._TITLE_CLR, wd["fs"] + 2, bold=True)
        self._text(mem, "\u00D7", W - 36, P - 4, 24, 24, self._CLOSE_CLR, 20, bold=True)

        sep_y = P + 26
        rc = _RECT(tx, sep_y, W - P, sep_y + 1)
        sb = self.gdi32.CreateSolidBrush(self._SEP)
        self.user32.FillRect(mem, byref(rc), sb)
        self.gdi32.DeleteObject(sb)

        ct, ch = sep_y + 10, H - sep_y - 10 - 18
        self._text(mem, wd["message"], tx, ct, W - tx - P, ch,
                   self._TEXT_CLR, wd["fs"], wrap=True)

        elapsed = time.time() - wd["t0"]
        prog = max(0.0, 1.0 - elapsed / wd["dur"]) if wd["dur"] > 0 else 0.0
        pb_h, pb_y, pb_total = 3, H - 10, W - P * 2

        bg_rc = _RECT(P, pb_y, P + pb_total, pb_y + pb_h)
        bg_br = self.gdi32.CreateSolidBrush(self._PROG_BG)
        self.user32.FillRect(mem, byref(bg_rc), bg_br)
        self.gdi32.DeleteObject(bg_br)

        if prog > 0.005:
            pw = int(pb_total * prog)
            fg_rc = _RECT(P, pb_y, P + pw, pb_y + pb_h)
            fg_br = self.gdi32.CreateSolidBrush(accent)
            self.user32.FillRect(mem, byref(fg_rc), fg_br)
            self.gdi32.DeleteObject(fg_br)

        self.gdi32.BitBlt(hdc, 0, 0, W, H, mem, 0, 0, 0x00CC0020)
        self.gdi32.DeleteObject(bmp)
        self.gdi32.DeleteDC(mem)
        self.user32.EndPaint(hwnd, byref(ps))

    def _text(self, hdc, text, x, y, w, h, color, size, bold=False, wrap=False):
        lf = _LOGFONTA()
        lf.lfHeight = -size if size else -12
        lf.lfWeight = 700 if bold else 400
        lf.lfFaceName = b"Microsoft YaHei\x00"
        hf = self.gdi32.CreateFontIndirectA(byref(lf))
        of = self.gdi32.SelectObject(hdc, hf)
        ob = self.gdi32.SetBkMode(hdc, 1)
        rv = color & 0xFF
        gv = (color >> 8) & 0xFF
        bv = (color >> 16) & 0xFF
        oc = self.gdi32.SetTextColor(hdc, rv | (gv << 8) | (bv << 16))
        rc = _RECT(x, y, x + w, y + h)
        flags = (0x04 | 0x40) if wrap else (0x20 | 0x04)
        self.user32.DrawTextW(hdc, text, -1, byref(rc), flags)
        self.gdi32.SetTextColor(hdc, oc)
        self.gdi32.SetBkMode(hdc, ob)
        self.gdi32.SelectObject(hdc, of)
        self.gdi32.DeleteObject(hf)


# ============== 插件接口 ==============

def register():
    return [
        {"action": "notify_popup", "name": "消息弹窗"},
        {"action": "notify_sound", "name": "语音提示"},
    ]

def execute(action, params, context):
    if action == "notify_popup":
        return _notify_popup(params, context)
    elif action == "notify_sound":
        return _notify_sound(params, context)
    return {"ok": False, "error": f"未知动作: {action}"}

def _notify_popup(params, context):
    title = str(_resolve_value(params.get("title", "提示"), context))
    message = str(_resolve_value(params.get("message", ""), context))
    sound = params.get("sound", "default")
    custom_sound = str(_resolve_value(params.get("custom_sound", ""), context))
    duration = int(_resolve_value(params.get("duration", 3000), context) or 3000)
    position = params.get("position", "bottom-right")
    desktop_popup = params.get("desktop_popup", False)
    font_size = int(_resolve_value(params.get("font_size", 12), context) or 12)

    if desktop_popup:
        popup = _PopupWindow()
        res = popup.show(
            title=title, message=message, sound=sound,
            duration_ms=duration, position=position, font_size=font_size,
        )
        context.log("info", f"桌面弹窗(自绘): {title} - {message}")
        if sound and sound != "none":
            context.emit("notify_play_sound", {"sound": sound, "custom_sound": custom_sound})
        return {"ok": True, "data": res}

    context.emit("notify_popup", {
        "title": title, "message": message, "sound": sound,
        "custom_sound": custom_sound, "duration": duration,
        "position": position, "font_size": font_size,
    })
    context.log("info", f"消息弹窗: {title} - {message}")
    return {"ok": True}

def _notify_sound(params, context):
    text = str(_resolve_value(params.get("text", ""), context))
    volume = float(_resolve_value(params.get("volume", 0.8), context) or 0.8)
    rate = float(_resolve_value(params.get("rate", 1.0), context) or 1.0)
    sound = params.get("sound", "none")
    custom_sound = str(_resolve_value(params.get("custom_sound", ""), context))
    voice_name = params.get("voice_name", "")
    context.emit("notify_sound", {
        "text": text, "volume": volume, "rate": rate,
        "sound": sound, "custom_sound": custom_sound,
        "voice_name": voice_name,
    })
    context.log("info", f"语音提示: {text}")
    return {"ok": True}
