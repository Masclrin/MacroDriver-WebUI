# -*- coding: utf-8 -*-
"""防跳秒插件回归测试。

覆盖两处曾导致“插件完全不触发 / 锁帧后不恢复”的缺陷：

1. 坐标退化：hwnd 失效（游戏重启后残留旧句柄）或窗口最小化时，
   `engine.coordinate.resolve_region` 会把 relative 区域解析成 (0,0,0,0)
   或 (-32000,-32000,0,0) —— 零面积区域使黑屏/亮屏检测与点击区域恒不匹配。
   插件必须检测到退化并回退到屏幕绝对坐标。

2. 亮屏超时恢复：无论以“亮屏确认 / 亮屏超时 / 截图不可用 / 流程停止 / 异常”结束，
   只要发过锁帧键，就必须补发一次恢复键（下一次锁帧前不得残留锁帧状态）。

运行：python plugins/anti_jump/test_backend.py
"""
import importlib.util
import os
import sys
import threading
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_spec = importlib.util.spec_from_file_location(
    "anti_jump_backend", os.path.join(_HERE, "backend.py"))
aj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aj)

# 像素区域：给流程测试里的假截图用
BLACK_REGION = [19, 103, 42, 39]
BRIGHT_REGION = [1119, 1002, 5, 8]
# 相对(0~1)区域：给坐标解析用（与 node.js 默认值一致）
BLACK_RECT_REL = [0.01, 0.096, 0.022, 0.037]
BRIGHT_RECT_REL = [0.583, 0.928, 0.003, 0.008]
COMBO_REGION_REL = [0.468, 0.464, 0.064, 0.037]
BOGUS_HWND = 0x0000000000ABCDEF

_failures = []


def check(cond, msg):
    if not cond:
        _failures.append(msg)


# ══════════════════════════════════════════════════════════════
# 1. 坐标退化回退
# ══════════════════════════════════════════════════════════════

def test_region_degeneration():
    check(aj._is_usable_region((19, 103, 42, 39)), "正常区域被判定为不可用")
    check(not aj._is_usable_region((0, 0, 0, 0)), "零面积区域被判定为可用")
    check(not aj._is_usable_region((-32000, -32000, 0, 0)), "最小化窗口区域被判定为可用")
    check(not aj._is_usable_region((10, 10, 0, 5)), "零宽区域被判定为可用")

    for label, rect in (("黑屏", BLACK_RECT_REL), ("亮屏", BRIGHT_RECT_REL)):
        region, status = aj._resolve_region("relative", rect, BOGUS_HWND, label)
        check(aj._is_usable_region(region),
              "%s 区域在失效 hwnd 下未回退，得到 %s" % (label, region))
        check(status == "fallback-screen",
              "%s 区域未标记为回退（status=%s）" % (label, status))

    combos = aj._parse_combos(
        {"combo_count": 1, "combo_0_keys": "esc", "combo_0_region": COMBO_REGION_REL},
        "relative", BOGUS_HWND)
    check(combos and combos[0]["has_region"],
          "失效 hwnd 下点击组合退化为“仅按键触发”：%s" % (combos,))
    rx, ry, rw, rh = combos[0]["region"]
    check(rx <= 960 <= rx + rw and ry <= 540 <= ry + rh,
          "回退后的点击区域未覆盖屏幕中心，无法触发：%s" % (combos[0]["region"],))

    # mode 与框选值不一致（relative 模式里填了像素值）→ 按绝对像素兜底，而不是静默失效
    region, status = aj._resolve_region("relative", BLACK_REGION, None, "黑屏(模式不匹配)")
    check(aj._is_usable_region(region) and status == "fallback-absolute",
          "模式与框选值不一致时未按绝对像素兜底：%s / %s" % (region, status))

    check(not aj._is_valid_hwnd(BOGUS_HWND), "失效句柄被判定为有效")


# ══════════════════════════════════════════════════════════════
# 2. 流程：每一次锁帧都必须有对应恢复
# ══════════════════════════════════════════════════════════════

class _FakeExecCtx:
    def __init__(self):
        self.stop_event = threading.Event()
        self._capture_manager = None


class _FakeCtx:
    def __init__(self, never_bright=False, never_black=False, bright_after=0.25):
        self.vars = {}
        self.exec = _FakeExecCtx()
        self.t0 = time.time()
        self.never_bright = never_bright
        self.never_black = never_black
        self.bright_after = bright_after

    def log(self, level, msg):
        pass

    def emit(self, name, data):
        pass

    def get_variable(self, name, default=None):
        return self.vars.get(name, default)

    def set_variable(self, name, value):
        self.vars[name] = value

    def get_exec_context(self):
        return self.exec

    def capture_screen(self, region):
        if region is None:
            return None
        x, y, w, h = (int(v) for v in region)
        if [x, y, w, h] == BLACK_REGION:
            if self.never_black:
                return np.full((h, w, 3), 200, dtype=np.uint8)
            return np.zeros((h, w, 3), dtype=np.uint8)
        if [x, y, w, h] == BRIGHT_REGION:
            if self.never_bright:
                return np.zeros((h, w, 3), dtype=np.uint8)
            if time.time() - self.t0 >= self.bright_after:
                return np.full((h, w, 3), 255, dtype=np.uint8)
            return np.zeros((h, w, 3), dtype=np.uint8)
        return None


BASE = {
    "mode": "screen",
    "combo_count": 0,
    "black_region": BLACK_REGION, "black_thresh": 60, "black_ratio": 0.9, "black_timeout": 0.5,
    "bright_region": BRIGHT_REGION, "bright_thresh": 80, "bright_ratio": 0.5, "bright_timeout": 0.6,
    "wait_before_lock": 0.05, "wait_after_lock": 0.05, "wait_after_bright": 0.02,
    "cooldown_after_cycle": 0.05, "rtss_hotkey": "f6",
    "idle_timeout": 0, "max_count": 1, "self_dxgi": False,
}

_sent = []
_orig_send_key = aj._send_key


def _run(ctx, params, expect_lock=True, label=""):
    _sent.clear()
    aj._send_key = lambda k: _sent.append(k)
    res = aj.execute("anti_jump", params, ctx)
    n = len(_sent)
    if expect_lock:
        check(n > 0, "%s：从未发送锁帧键" % label)
        check(n % 2 == 0, "%s：锁帧/恢复数量不配对（%d 次发送）——存在锁帧后不恢复" % (label, n))
    else:
        check(n == 0, "%s：不应发送按键，实际 %d 次" % (label, n))
    return res


def test_flow_invariants():
    # A. 正常：黑屏 → 锁帧 → 亮屏 → 恢复
    res = _run(_FakeCtx(bright_after=0.25), dict(BASE, bright_timeout=0.6), True, "A 正常周期")
    check(res.get("check_results", {}).get("trigger_count") == 1, "A：触发计数应为 1")

    # B. 亮屏永不出现 → 超时也必须恢复
    _run(_FakeCtx(never_bright=True), dict(BASE, bright_timeout=0.3, idle_timeout=0.9),
         True, "B 亮屏超时")

    # C. 黑屏永不出现 → 不应锁帧
    _run(_FakeCtx(never_black=True), dict(BASE, black_timeout=0.4, idle_timeout=0.7),
         False, "C 黑屏超时")

    # D. 执行前已停止
    ctx_d = _FakeCtx(never_bright=True)
    ctx_d.exec.stop_event.set()
    _run(ctx_d, dict(BASE), False, "D 执行前已停止")

    # E. 等待亮屏期间被停止 → 仍须恢复
    ctx_e = _FakeCtx(never_bright=True)
    threading.Timer(0.25, ctx_e.exec.stop_event.set).start()
    _run(ctx_e, dict(BASE, bright_timeout=3.0), True, "E 等待时被停止")

    # F. 控制变量停止信号
    ctx_f = _FakeCtx(never_bright=True)
    ctx_f.vars["anti_jump_control"] = "stop"
    _run(ctx_f, dict(BASE, bright_timeout=3.0), False, "F 停止信号")


def main():
    t0 = time.time()
    test_region_degeneration()
    test_flow_invariants()
    aj._send_key = _orig_send_key
    print("-" * 56)
    if _failures:
        print("失败 %d 项:" % len(_failures))
        for f in _failures:
            print("  ✗", f)
        return 1
    print("防跳秒插件回归测试通过 ✔ (%.1fs)" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
