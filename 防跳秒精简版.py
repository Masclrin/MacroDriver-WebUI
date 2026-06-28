"""
防跳秒精简版 (DXGI + 高精度定时)
用于原神游戏开局防跳秒，给玩家提供更多战斗时间
────────────
生命周期:
  动作匹配 → 黑屏检测 → 等待 → 锁帧 → 等待 → 亮屏检测 → 恢复帧率 → 循环

交互:
  F9  开关监听 (默认关)

启动参数:
  --debug  启用 Debug 框图窗口

依赖: pip install keyboard opencv-python numpy pillow comtypes
"""

import sys
import os
import time
import argparse
import threading
import ctypes
import ctypes.wintypes

_DPISCALE = 1.0

user32_dpi = ctypes.windll.user32
try:
    user32_dpi.SetProcessDPIAware()
except Exception:
    pass
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

import keyboard
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(SCRIPT_DIR, '存档内容', '旧后端脚本'))

from dxgi_capture import DXGICapture

try:
    from engine.precision import (
        boost_process_priority, boost_thread_priority,
        set_thread_affinity, precise_sleep_v5, auto_warmup,
    )
    _PRECISION_AVAILABLE = True
except ImportError:
    _PRECISION_AVAILABLE = False
    def boost_process_priority(): pass
    def boost_thread_priority(): pass
    def set_thread_affinity(core_index=13): pass
    def auto_warmup(*a, **kw): pass

# ═══════════════════════════════════════════════════════════════
# 配置区 (用户可修改)
# ═══════════════════════════════════════════════════════════════

SW, SH = 1920, 1080
CX, CY = SW // 2, SH // 2
ACTION_COMBOS = [
    (('esc',), (CX - 23, CY - 15, CX + 23, CY + 15)),
]
COMBO_TIME_WINDOW = 2.0

BLACK_REGION   = (19, 105, 30, 30)
BLACK_THRESH   = 60
BLACK_RATIO    = 0.9
BLACK_TIMEOUT  = 2.0

BRIGHT_REGION  = (1118, 1005, 6, 6)
BRIGHT_THRESH  = 80
BRIGHT_RATIO   = 0.5
BRIGHT_TIMEOUT = 8.0

WAIT_BEFORE_LOCK = 0.6
WAIT_AFTER_LOCK  = 1.5
WAIT_AFTER_BRIGHT = 0.3
COOLDOWN_AFTER_CYCLE = 1.0

RTSS_HOTKEY = 'f6'

IDLE_FPS   = 15
ACTIVE_FPS = 90

DETECT_INTERVAL = 0.02

POLL_INTERVAL_ACTIVE  = 0.04
POLL_INTERVAL_IDLE    = 0.2

# ═══════════════════════════════════════════════════════════════
# 高精度定时
# ═══════════════════════════════════════════════════════════════

_stop_event = threading.Event()

def psleep(seconds):
    if seconds <= 0:
        return
    if _PRECISION_AVAILABLE:
        precise_sleep_v5(seconds, _stop_event)
    else:
        time.sleep(seconds)

# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def send_key(k):
    keyboard.send(k)

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

# ═══════════════════════════════════════════════════════════════
# 屏幕检测 (DXGI)
# ═══════════════════════════════════════════════════════════════

class ScreenDetector:
    """黑屏 / 亮屏检测 (DXGI 后台采集)"""

    def __init__(self):
        self._dxgi = DXGICapture()
        self._initialized = False

    def initialize(self):
        if not self._dxgi.initialize():
            print("[DXGI] 初始化失败")
            return False
        if not self._dxgi.start_background(fps=IDLE_FPS):
            print("[DXGI] 后台采集启动失败")
            return False
        for i in range(30):
            frame = self._dxgi.get_latest_frame()
            if frame is not None:
                h, w = frame.shape[:2]
                print(f"[DXGI] 预热完成 ({i + 1} 帧, {w}x{h})")
                break
            psleep(0.05)
        else:
            print("[DXGI] 预热超时，未获取到有效帧")
        self._initialized = True
        return True

    def set_fps(self, fps):
        self._dxgi.set_fps(fps)

    def pause_capture(self):
        self._dxgi.pause()

    def resume_capture(self, fps=IDLE_FPS):
        self._dxgi.set_fps(fps)
        self._dxgi.resume()

    def _capture_region(self, x, y, w, h):
        frame = self._dxgi.get_region_frame(x, y, w, h)
        if frame is None:
            return None
        if len(frame.shape) == 3:
            if frame.shape[2] == 3:
                return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            elif frame.shape[2] == 4:
                return cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        return None

    def is_black(self, x, y, w, h, thresh=BLACK_THRESH, ratio=BLACK_RATIO):
        gray = self._capture_region(x, y, w, h)
        if gray is None:
            return False, 0.0
        dark = np.sum(gray < thresh)
        total = gray.size
        return (dark / total) >= ratio, dark / total

    def is_bright(self, x, y, w, h, thresh=BRIGHT_THRESH, ratio=BRIGHT_RATIO):
        gray = self._capture_region(x, y, w, h)
        if gray is None:
            return False, 0.0
        bright = np.sum(gray > thresh)
        total = gray.size
        return (bright / total) >= ratio, bright / total

    def capture_full(self):
        return self._dxgi.get_latest_frame()

    def stop(self):
        self._dxgi.stop_background()

# ═══════════════════════════════════════════════════════════════
# Debug 框图
# ═══════════════════════════════════════════════════════════════

class DebugOverlay:
    """OpenCV 窗口显示检测区域框图"""

    def __init__(self, detector):
        self._detector = detector
        self._running = False
        self._thread = None
        self._font = None
        self._init_font()

    def _init_font(self):
        for name in ["simhei.ttf", "msyh.ttc", "msyhbd.ttc"]:
            try:
                self._font = ImageFont.truetype(name, 18)
                return
            except Exception:
                continue
        self._font = ImageFont.load_default()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[Debug] 框图窗口已开启 (ESC 或关闭窗口退出)")

    def stop(self):
        self._running = False
        cv2.destroyAllWindows()
        print("[Debug] 框图窗口已关闭")

    def _draw_text(self, frame, text, pos, color):
        img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        draw.text(pos, text, font=self._font, fill=color)
        return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

    def _loop(self):
        cv2.namedWindow("Debug", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Debug", 960, 540)
        while self._running:
            try:
                if cv2.getWindowProperty("Debug", cv2.WND_PROP_VISIBLE) < 1:
                    self._running = False
                    break

                frame = self._detector.capture_full()
                if frame is None:
                    time.sleep(0.03)
                    continue
                if len(frame.shape) == 3 and frame.shape[2] == 4:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                bx, by, bw, bh = BLACK_REGION
                cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (255, 0, 0), 2)
                frame = self._draw_text(frame, "黑屏", (bx + 2, by + 2), (255, 0, 0))

                lx, ly, lw, lh = BRIGHT_REGION
                cv2.rectangle(frame, (lx, ly), (lx + lw, ly + lh), (0, 255, 0), 2)
                frame = self._draw_text(frame, "亮屏", (lx + 2, ly + 2), (0, 255, 0))

                for i, (keys, rect) in enumerate(ACTION_COMBOS):
                    rx1, ry1, rx2, ry2 = rect
                    cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (0, 0, 255), 2)
                    label = f"点击{i}: {'+'.join(keys)}"
                    frame = self._draw_text(frame, label, (rx1 + 2, ry1 + 2), (0, 0, 255))

                cv2.imshow("Debug", frame)
                key = cv2.waitKey(33)
                if key == 27:
                    self._running = False
                    break
            except Exception as e:
                print(f"[Debug] 错误: {e}")
                time.sleep(0.5)
        cv2.destroyAllWindows()

# ═══════════════════════════════════════════════════════════════
# 动作匹配监听
# ═══════════════════════════════════════════════════════════════

VK_ESC = 0x1B
VK_LBUTTON = 0x01

class ActionWatcher:
    """监听键序列 + 鼠标点击组合 (GetAsyncKeyState 轮询)

    优化策略:
      - 键盘事件后 COMBO_TIME_WINDOW 内: 精细轮询 (0.04s)
      - 窗口期外: 粗轮询 (0.2s)，降低 CPU 占用
      - 全部使用 time.sleep (无需高精度)
    """

    def __init__(self):
        self._matched = threading.Event()
        self._active = False
        self._key_time = 0.0
        self._matched_combo_idx = -1
        self._poll_thread = None
        self._hotkey_hooks = []

    @property
    def matched(self):
        return self._matched.is_set()

    @property
    def matched_idx(self):
        return self._matched_combo_idx

    def clear(self):
        self._matched.clear()
        self._matched_combo_idx = -1
        self._key_time = 0.0

    def start(self):
        if self._active:
            return
        self._active = True
        self._key_time = 0.0
        self._matched.clear()
        self._matched_combo_idx = -1
        self._hotkey_hooks = []

        all_keys = set()
        for keys, _ in ACTION_COMBOS:
            for k in keys:
                all_keys.add(k)

        for k in all_keys:
            try:
                hook = keyboard.add_hotkey(k, lambda kk=k: self._on_key(kk))
                self._hotkey_hooks.append(hook)
            except Exception:
                pass

        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

        print("[监听] 动作匹配已启动")

    def stop(self):
        self._active = False
        for hook in self._hotkey_hooks:
            try:
                keyboard.remove_hotkey(hook)
            except Exception:
                pass
        self._hotkey_hooks = []
        self._matched.clear()

    def _on_key(self, key):
        if not self._active:
            return
        self._key_time = time.time()
        for idx, (keys, rect) in enumerate(ACTION_COMBOS):
            if key in keys and rect is None:
                self._matched_combo_idx = idx
                self._matched.set()
                print(f"[匹配] 按键触发: {key} (combo #{idx})")

    def _poll_loop(self):
        user32 = ctypes.windll.user32
        prev_lbtn = False
        while self._active:
            now = time.time()
            in_window = (now - self._key_time) <= COMBO_TIME_WINDOW and self._key_time > 0

            curr_lbtn = bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)

            if curr_lbtn and not prev_lbtn and in_window and not self._matched.is_set():
                pt = ctypes.wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                mx, my = pt.x, pt.y
                for idx, (keys, rect) in enumerate(ACTION_COMBOS):
                    if rect is None:
                        continue
                    rx1, ry1, rx2, ry2 = rect
                    if rx1 <= mx <= rx2 and ry1 <= my <= ry2:
                        self._matched_combo_idx = idx
                        self._matched.set()
                        ks = '+'.join(keys)
                        print(f"[匹配] {ks} + 点击({mx},{my}) → combo #{idx}")
                        break

            prev_lbtn = curr_lbtn

            if in_window:
                time.sleep(POLL_INTERVAL_ACTIVE)
            else:
                time.sleep(POLL_INTERVAL_IDLE)

# ═══════════════════════════════════════════════════════════════
# 主循环
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="防跳秒精简版")
    parser.add_argument('--debug', action='store_true', help='启用 Debug 框图窗口')
    args = parser.parse_args()

    print("=" * 50)
    print("  防跳秒精简版 (DXGI + 高精度定时)")
    print("  F9 开关监听 | Ctrl+C 退出")
    if args.debug:
        print("  [Debug] 框图窗口已启用")
    print("=" * 50)

    if not is_admin():
        print("[警告] 未以管理员身份运行, 全局热键可能失效")

    boost_process_priority()
    boost_thread_priority()
    set_thread_affinity(core_index=13)
    print("[系统] 进程优先级已提升, 线程已绑定核心14")

    if _PRECISION_AVAILABLE:
        auto_warmup(target_s=0.030, iterations=30)
        print("[定时] 高精度定时引擎已预热")
    else:
        print("[定时] 高精度定时引擎不可用, 使用 time.sleep 回退")

    detector = ScreenDetector()
    if not detector.initialize():
        print("[错误] DXGI 初始化失败, 退出")
        sys.exit(1)
    detector.pause_capture()
    print(f"[DXGI] 截图引擎已就绪 (空闲不捕获 / 检测 {ACTIVE_FPS}fps)")

    debug = None
    if args.debug:
        debug = DebugOverlay(detector)
        debug.start()

    watcher = ActionWatcher()

    running = [False]

    def toggle_running():
        if running[0]:
            running[0] = False
            watcher.stop()
            detector.pause_capture()
            print("[状态] 监听已关闭")
        else:
            running[0] = True
            watcher.start()
            print("[状态] 监听已开启")

    try:
        keyboard.add_hotkey('f9', toggle_running)
    except Exception as e:
        print(f"[错误] 热键注册失败: {e}")
        sys.exit(1)

    print("[就绪] 按 F9 开始监听")

    try:
        while True:
            if not running[0]:
                time.sleep(0.1)
                continue

            if not watcher.matched:
                time.sleep(0.05)
                continue

            idx = watcher.matched_idx
            keys, rect = ACTION_COMBOS[idx]
            ks = '+'.join(keys)
            print(f"\n{'─'*40}")
            print(f"[触发] combo #{idx}: {ks} + 点击区域 {rect}")
            watcher.clear()

            detector.resume_capture(ACTIVE_FPS)

            bx, by, bw, bh = BLACK_REGION
            print(f"[黑屏检测] 等待黑屏... (超时 {BLACK_TIMEOUT}s)")
            t0 = time.time()
            black_ok = False
            while time.time() - t0 < BLACK_TIMEOUT:
                ok, ratio = detector.is_black(bx, by, bw, bh)
                if ok:
                    black_ok = True
                    print(f"[黑屏检测] ✓ 黑屏确认 (暗像素 {ratio:.0%})")
                    break
                psleep(DETECT_INTERVAL)
            if not black_ok:
                print(f"[黑屏检测] ✗ 超时, 放弃本轮")
                detector.pause_capture()
                continue

            print(f"[等待] {WAIT_BEFORE_LOCK}s 后锁帧...")
            psleep(WAIT_BEFORE_LOCK)
            print(f"[锁帧] 发送 RTSS {RTSS_HOTKEY}")
            send_key(RTSS_HOTKEY)

            print(f"[等待] {WAIT_AFTER_LOCK}s 后检测亮屏...")
            psleep(WAIT_AFTER_LOCK)

            lx, ly, lw, lh = BRIGHT_REGION
            print(f"[亮屏检测] 等待亮屏... (超时 {BRIGHT_TIMEOUT}s)")
            t0 = time.time()
            bright_ok = False
            while time.time() - t0 < BRIGHT_TIMEOUT:
                ok, ratio = detector.is_bright(lx, ly, lw, lh)
                if ok:
                    bright_ok = True
                    print(f"[亮屏检测] ✓ 亮屏确认 (亮像素 {ratio:.0%})，{WAIT_AFTER_BRIGHT}s 后恢复帧率...")
                    psleep(WAIT_AFTER_BRIGHT)
                    break
                psleep(DETECT_INTERVAL)
            if not bright_ok:
                print(f"[亮屏检测] ✗ 超时")
                detector.pause_capture()
                continue

            print(f"[恢复] 发送 RTSS {RTSS_HOTKEY}")
            send_key(RTSS_HOTKEY)

            detector.pause_capture()

            print(f"[冷却] {COOLDOWN_AFTER_CYCLE}s 内忽略新的触发")
            psleep(COOLDOWN_AFTER_CYCLE)
            watcher.clear()

            print(f"[完成] 回到监听状态")
            print(f"{'─'*40}\n")

    except KeyboardInterrupt:
        print("\n[退出]")
    finally:
        running[0] = False
        _stop_event.set()
        watcher.stop()
        if debug:
            debug.stop()
        detector.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
