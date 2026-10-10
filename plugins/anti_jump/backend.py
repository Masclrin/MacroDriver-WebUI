# -*- coding: utf-8 -*-
"""防跳秒 插件后端

生命周期:
  动作匹配/黑屏触发 → 黑屏确认 → 等待 → 锁帧(RTSS) → 等待 → 亮屏确认 → 恢复帧率 → 循环

本次修复要点（对应反馈）:
1. 亮屏(白屏)检测超时 —— 确认并强化“超时补发恢复快捷键”:
   超时、截图通道失效、流程停止/异常 四条路径都会补发 RTSS 恢复键，
   不再出现“锁了帧却不会恢复”的情况。
2. 相对位置方案“常见不触发” —— 根因是坐标退化:
   hwnd 失效（游戏重启后残留的旧句柄）或窗口最小化时，
   GetClientRect/ClientToScreen 返回 (0,0,0,0) / (-32000,-32000,0,0)，
   经 relative 模式换算后区域退化为零面积 —— 黑屏/亮屏检测与点击区域恒不匹配，
   表现为“插件完全不触发且无任何日志”。现在会检测退化并自动回退到屏幕绝对坐标
   （等价外置脚本的绝对/全屏方案），并打印明确的警告日志。
3. 截图源依赖 —— 无“截图源”节点时，独占全屏游戏用 BitBlt 只能取到黑屏/旧帧。
   现在插件在上下文没有 DXGI 时自建 DXGI 全屏后台采集（与外置脚本一致），
   再按绝对坐标切片；若流程图里已有“截图源”节点，则优先复用其 DXGI，不重复复制。
"""

import time
import ctypes
import ctypes.wintypes
import threading
import logging
import numpy as np

logger = logging.getLogger("plugin.anti_jump")

VK_LBUTTON = 0x01

POLL_INTERVAL_ACTIVE = 0.04
POLL_INTERVAL_IDLE = 0.2
DETECT_INTERVAL = 0.02

# 截图通道连续失败多少次后判定为“不可用”（约 0.5s）
_MAX_CAPTURE_FAILS = 25

# 插件自建采集的帧率。
# 注意：本机实测「全屏 BitBlt」约 19ms/帧（当 comtypes 的 DXGI 类型库不可用时，
# 所谓 DXGI 就是全屏 BitBlt）。60fps 会吃掉一个以上的核心，因此这里取 15fps
# （与外置脚本 IDLE_FPS 一致）：约 19ms/66ms ≈ 29% 单核，且 66ms 的检测延迟
# 对持续 0.5s 以上的黑屏过场完全够用。
_SELF_DXGI_FPS = 15

# 合理的区域上限，超过则视为解析异常
_MAX_REGION_SIDE = 16384
_MIN_REGION_POS = -16000


def register():
    return [{"action": "anti_jump", "name": "防跳秒"}]


def execute(action, params, context):
    if action != "anti_jump":
        return {"ok": False, "error": "未知动作: {}".format(action)}

    if params.get("stop_mode"):
        return _stop_signal(params, context)

    return _run_monitor(params, context)


def _stop_signal(params, context):
    control_var = params.get("control_var_stop") or params.get("control_var") or "anti_jump_control"
    context.set_variable(control_var, "stop")
    context.log("info", "[防跳秒] 停止信号已发送: {}".format(control_var))
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
# 窗口句柄
# ══════════════════════════════════════════════════════════════

def _is_valid_hwnd(hwnd):
    """句柄必须既是有效窗口，又未最小化。

    最小化窗口的客户区原点会变成 -32000，直接把区域算到屏幕外。
    """
    if not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        h = int(hwnd)
        if not user32.IsWindow(h):
            return False
        if user32.IsIconic(h):
            return False
        return True
    except Exception:
        return False


def _parse_hwnd_value(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _get_hwnd(params, context):
    hwnd_val = params.get("hwnd_var", "")
    if not hwnd_val:
        return None

    hwnd = _parse_hwnd_value(hwnd_val)
    if hwnd is not None:
        if _is_valid_hwnd(hwnd):
            return hwnd
        logger.warning("[防跳秒] 窗口句柄 %s 已失效(窗口不存在或已最小化)，改用屏幕绝对坐标", hwnd)
        return None

    if isinstance(hwnd_val, str) and hwnd_val.startswith("${") and hwnd_val.endswith("}"):
        val = context.get_variable(hwnd_val[2:-1], "")
        hwnd = _parse_hwnd_value(val)
        if hwnd is not None:
            if _is_valid_hwnd(hwnd):
                return hwnd
            logger.warning("[防跳秒] 窗口句柄变量 %s 的值 %s 已失效，改用屏幕绝对坐标",
                           hwnd_val, hwnd)
            return None

    val = context.get_variable(str(hwnd_val), "")
    hwnd = _parse_hwnd_value(val)
    if hwnd is not None:
        if _is_valid_hwnd(hwnd):
            return hwnd
        logger.warning("[防跳秒] 窗口句柄变量 %s 的值 %s 已失效，改用屏幕绝对坐标",
                       hwnd_val, hwnd)
    return None


# ══════════════════════════════════════════════════════════════
# 区域解析（带退化检测与回退）
# ══════════════════════════════════════════════════════════════

def _is_usable_region(region):
    """区域必须是非零面积、且不落在屏幕外。"""
    if region is None:
        return False
    try:
        x, y, w, h = (int(v) for v in region)
    except (ValueError, TypeError):
        return False
    if w <= 0 or h <= 0:
        return False
    if x < _MIN_REGION_POS or y < _MIN_REGION_POS:
        return False
    if w > _MAX_REGION_SIDE or h > _MAX_REGION_SIDE:
        return False
    return True


def _resolve_region(mode, rect, hwnd, label=""):
    """稳健的区域解析。

    返回 (region, status)，status ∈ {"resolved", "fallback-screen", "invalid"}。

    退化场景（会静默不触发）：
      - hwnd 失效（游戏重启后残留旧句柄） → GetClientRect 失败 → (0,0,0,0)
      - 窗口最小化                        → ClientToScreen → (-32000,-32000,0,0)
    两者经 relative 换算后都是零面积区域。这里检测到退化就回退到屏幕尺寸解析，
    等价外置脚本使用的绝对/全屏坐标方案。
    """
    region = None
    try:
        from engine.coordinate import resolve_region
        region = resolve_region(mode, rect, hwnd)
    except Exception as exc:
        logger.warning("[防跳秒] %s 区域解析异常(mode=%s): %s", label, mode, exc)

    if _is_usable_region(region):
        return tuple(int(v) for v in region), "resolved"

    # 回退：relative 按屏幕尺寸换算；window 的像素偏移按屏幕绝对坐标处理
    fb_mode = "relative" if mode in ("relative", "window") else "screen"
    fallback = None
    try:
        from engine.coordinate import resolve_region
        fallback = resolve_region(fb_mode, rect, None)
    except Exception:
        try:
            fallback = tuple(int(v) for v in rect)
        except Exception:
            fallback = None

    if _is_usable_region(fallback):
        logger.warning(
            "[防跳秒] %s 解析结果不可用 %s (mode=%s, hwnd=%s) → 回退屏幕绝对坐标 %s",
            label, region, mode, hwnd, fallback)
        return tuple(int(v) for v in fallback), "fallback-screen"

    # 再退一步：把 rect 当作屏幕绝对像素。
    # 典型场景：参数里 mode 仍是 relative，但区域是用像素值框选的
    # （切换坐标模式后没有重新框选）。此时按 relative 换算会得到天文数字，
    # 旧实现会静默变成“永远不触发”，现在按绝对像素兜底。
    try:
        abs_region = tuple(int(v) for v in rect)
    except (ValueError, TypeError):
        abs_region = None
    if _is_usable_region(abs_region):
        logger.warning(
            "[防跳秒] %s 按 %s 解析均不可用(原值 %s)，已按屏幕绝对像素兜底 %s"
            "（请确认坐标模式与框选值一致）", label, mode, region, abs_region)
        return abs_region, "fallback-absolute"

    logger.error("[防跳秒] %s 区域无法解析: rect=%s mode=%s hwnd=%s → %s",
                 label, rect, mode, hwnd, region)
    return tuple(int(v) for v in (region or rect or (0, 0, 0, 0))), "invalid"


def _parse_combos(params, mode, hwnd):
    combo_count = int(params.get("combo_count", 1))
    combos = []
    for i in range(min(combo_count, 5)):
        keys_str = params.get("combo_{}_keys".format(i), "")
        if not keys_str:
            continue
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        region = params.get("combo_{}_region".format(i), [0, 0, 0, 0])
        has_region = bool(region) and region != [0, 0, 0, 0]
        phys_region = None
        if has_region:
            phys_region, status = _resolve_region(mode, region, hwnd,
                                                  label="组合{}点击区域".format(i + 1))
            if status == "invalid":
                logger.warning("[防跳秒] 组合%d 点击区域无效，已降级为“仅按键触发”", i + 1)
                has_region = False
        combos.append({"keys": keys, "region": phys_region, "has_region": has_region})
    return combos


# ══════════════════════════════════════════════════════════════
# 截图通道
# ══════════════════════════════════════════════════════════════

def _to_gray(frame):
    if frame is None:
        return None
    try:
        if len(frame.shape) == 2:
            return frame
        if frame.shape[2] == 3:
            try:
                import cv2
                return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            except ImportError:
                return np.mean(frame, axis=2).astype(np.uint8)
        if frame.shape[2] == 4:
            try:
                import cv2
                return cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
            except ImportError:
                return np.mean(frame[:, :, :3], axis=2).astype(np.uint8)
        return frame[:, :, 0]
    except Exception:
        return None


def _frame_ok(frame):
    return frame is not None and getattr(frame, "size", 0) > 0


def _crop(frame, x, y, w, h):
    """从整屏帧里按绝对物理坐标切出区域。"""
    if not _frame_ok(frame):
        return None
    try:
        fh, fw = frame.shape[:2]
        x1 = max(0, int(x))
        y1 = max(0, int(y))
        x2 = min(fw, int(x) + int(w))
        y2 = min(fh, int(y) + int(h))
        if x2 <= x1 or y2 <= y1:
            return None
        return frame[y1:y2, x1:x2]
    except Exception:
        return None


class CaptureChannel:
    """统一的截图通道。

    优先级：
      0) 若上下文没有 DXGI（即流程图里没有启用“截图源”节点）→ 自建 DXGI 全屏采集，
         等价外置脚本的“全屏截图 + 区域切片”，独占全屏游戏也能正确取帧。
      1) 上下文区域截图（有 DXGI 时即后台帧切片，最省）
      2) 上下文全屏截图 + 本地切片
    任一通道连续失败即计入 fail_count，供上层判定“截图不可用”。
    """

    def __init__(self, context, enable_self_dxgi=True):
        self._ctx = context
        self._enable_self_dxgi = enable_self_dxgi
        self._self_dxgi = None
        self._self_dxgi_failed = False
        self._fail_count = 0
        self._reported_method = None
        self._warned_out_of_screen = False

    # ---------- 上下文探测 ----------

    def _ctx_capture_manager(self):
        try:
            ref = self._ctx.get_exec_context()
            return getattr(ref, "_capture_manager", None)
        except Exception:
            return None

    def ctx_has_dxgi(self):
        cm = self._ctx_capture_manager()
        if cm is None:
            return False
        try:
            return bool(cm.is_dxgi_running())
        except Exception:
            return False

    def _context_capture(self, region):
        try:
            return self._ctx.capture_screen(region)
        except Exception as exc:
            logger.debug("[防跳秒] 上下文截图异常: %s", exc)
            return None

    # ---------- 自建 DXGI ----------

    def _ensure_self_dxgi(self):
        if self._self_dxgi is not None or self._self_dxgi_failed:
            return self._self_dxgi
        try:
            from automation.detection.dxgi_capture import DXGICapture
            cap = DXGICapture()
            if not cap.initialize(adapter_idx=0, output_idx=0):
                raise RuntimeError("initialize 失败")
            if not cap.start_background(fps=_SELF_DXGI_FPS):
                raise RuntimeError("start_background 失败")
            for _ in range(25):
                if cap.get_latest_frame() is not None:
                    break
                time.sleep(0.02)
            self._self_dxgi = cap
            logger.info("[防跳秒] 已启用插件自建 DXGI 全屏采集 (%dfps)", _SELF_DXGI_FPS)
        except Exception as exc:
            self._self_dxgi_failed = True
            logger.warning("[防跳秒] 自建 DXGI 不可用，回退上下文截图: %s", exc)
        return self._self_dxgi

    def prepare(self):
        """执行前预热：没有上下文 DXGI 时主动建立自己的 DXGI。"""
        if self._enable_self_dxgi and not self.ctx_has_dxgi():
            self._ensure_self_dxgi()

    def _self_dxgi_frame(self):
        cap = self._self_dxgi
        if cap is None:
            return None
        # 上下文后来启动了 DXGI（例如流程里跑了“截图源”节点）→ 让路，避免重复复制
        if self.ctx_has_dxgi():
            self.close()
            return None
        try:
            return cap.get_latest_frame()
        except Exception:
            return None

    # ---------- 取帧 ----------

    def _report(self, method):
        if self._reported_method != method:
            logger.info("[防跳秒] 截图通道: %s", method)
            self._reported_method = method

    def get_gray(self, region):
        x, y, w, h = (int(v) for v in region)

        # 0) 自建 DXGI 全屏切片（独占全屏可用）
        sub = _crop(self._self_dxgi_frame(), x, y, w, h)
        if _frame_ok(sub):
            self._report("自建DXGI全屏切片")
            self._fail_count = 0
            return _to_gray(sub)

        # 1) 上下文区域截图
        frame = self._context_capture([x, y, w, h])
        if _frame_ok(frame):
            self._report("区域截图")
            self._fail_count = 0
            return _to_gray(frame)

        # 2) 上下文全屏截图 + 本地切片（等价外置脚本方案）
        sub = _crop(self._context_capture(None), x, y, w, h)
        if _frame_ok(sub):
            self._report("全屏截图切片")
            self._fail_count = 0
            return _to_gray(sub)

        self._fail_count += 1
        if self._fail_count == 1 and not self._warned_out_of_screen:
            self._warned_out_of_screen = True
            logger.warning("[防跳秒] 区域 %s 在整屏帧内无效（可能位于副屏或坐标为负）", region)
        return None

    @property
    def fail_count(self):
        return self._fail_count

    def capture_broken(self):
        return self._fail_count >= _MAX_CAPTURE_FAILS

    def close(self):
        cap = self._self_dxgi
        self._self_dxgi = None
        if cap is not None:
            try:
                cap.stop_background()
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════
# 检测
# ══════════════════════════════════════════════════════════════

def _check_black(channel, phys_region, thresh, ratio):
    gray = channel.get_gray(phys_region)
    if gray is None:
        return False, 0.0
    dark = np.sum(gray < thresh)
    total = gray.size
    r = dark / total if total > 0 else 0.0
    return r >= ratio, r


def _check_bright(channel, phys_region, thresh, ratio):
    gray = channel.get_gray(phys_region)
    if gray is None:
        return False, 0.0
    bright = np.sum(gray > thresh)
    total = gray.size
    r = bright / total if total > 0 else 0.0
    return r >= ratio, r


def _send_key(k):
    try:
        import keyboard
        keyboard.send(k)
    except Exception as e:
        logger.warning("发送按键失败 %s: %s", k, e)


def _should_stop(context, control_var, max_count, trigger_count, idle_timeout, last_trigger_time):
    try:
        exec_ctx = context.get_exec_context()
        if exec_ctx and hasattr(exec_ctx, 'stop_event') and exec_ctx.stop_event.is_set():
            return "stopped"
    except Exception:
        pass

    ctrl_val = context.get_variable(control_var, "")
    if ctrl_val == "stop":
        return "stopped"

    if max_count > 0 and trigger_count >= max_count:
        return "max_count"

    if idle_timeout > 0 and (time.time() - last_trigger_time) > idle_timeout:
        return "timeout"

    return None


class ComboWatcher:
    def __init__(self, combos, time_window):
        self._combos = combos
        self._time_window = time_window
        self._matched = threading.Event()
        self._matched_idx = -1
        self._key_times = {}
        self._active = False
        self._hotkey_hooks = []
        self._poll_thread = None
        self._has_region_combos = any(c["has_region"] for c in combos)

    @property
    def matched(self):
        return self._matched.is_set()

    @property
    def matched_idx(self):
        return self._matched_idx

    def clear(self):
        self._matched.clear()
        self._matched_idx = -1
        self._key_times.clear()

    def start(self):
        if self._active:
            return
        self._active = True
        self._matched.clear()
        self._hotkey_hooks = []

        try:
            import keyboard
            all_keys = set()
            for combo in self._combos:
                for k in combo["keys"]:
                    all_keys.add(k)
            for k in all_keys:
                try:
                    hook = keyboard.add_hotkey(k, lambda kk=k: self._on_key(kk))
                    self._hotkey_hooks.append(hook)
                except Exception:
                    pass
        except ImportError:
            # keyboard 不可用时，带点击区域的组合将永远等不到“按键时间窗口”，
            # 这本身就是“不触发”的常见原因，必须显式报错而非静默。
            logger.error("[防跳秒] keyboard 库不可用：按键+点击组合无法触发，"
                         "请安装 keyboard 或改用「纯黑屏监听」模式(动作组合数=0)")

        if self._has_region_combos:
            self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._poll_thread.start()

    def stop(self):
        self._active = False
        try:
            import keyboard
            for hook in self._hotkey_hooks:
                try:
                    keyboard.remove_hotkey(hook)
                except Exception:
                    pass
        except Exception:
            pass
        self._hotkey_hooks = []
        self._matched.clear()

    def _on_key(self, key):
        if not self._active:
            return
        self._key_times[key] = time.time()
        for idx, combo in enumerate(self._combos):
            if key in combo["keys"] and not combo["has_region"]:
                self._matched_combo(idx)

    def _matched_combo(self, idx):
        self._matched_idx = idx
        self._matched.set()

    def _poll_loop(self):
        user32 = ctypes.windll.user32
        prev_lbtn = False
        while self._active:
            try:
                now = time.time()
                in_window = any(
                    now - self._key_times.get(k, 0) <= self._time_window
                    for combo in self._combos if combo["has_region"]
                    for k in combo["keys"]
                )

                curr_lbtn = bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)

                if curr_lbtn and not prev_lbtn and in_window and not self._matched.is_set():
                    pt = ctypes.wintypes.POINT()
                    user32.GetCursorPos(ctypes.byref(pt))
                    mx, my = pt.x, pt.y
                    for idx, combo in enumerate(self._combos):
                        if not combo["has_region"]:
                            continue
                        all_in_window = all(
                            now - self._key_times.get(k, 0) <= self._time_window
                            for k in combo["keys"]
                        )
                        if not all_in_window:
                            continue
                        rx, ry, rw, rh = combo["region"]
                        if rx <= mx <= rx + rw and ry <= my <= ry + rh:
                            self._matched_combo(idx)
                            break

                prev_lbtn = curr_lbtn
            except Exception:
                pass

            if in_window:
                time.sleep(POLL_INTERVAL_ACTIVE)
            else:
                time.sleep(POLL_INTERVAL_IDLE)


# ══════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════

def _run_monitor(params, context):
    mode = params.get("mode", "screen")
    hwnd = _get_hwnd(params, context)
    if mode in ("relative", "window") and hwnd is None:
        logger.warning("[防跳秒] %s 模式未取得有效窗口句柄，将按屏幕绝对坐标解析", mode)

    combos = _parse_combos(params, mode, hwnd)
    time_window = float(params.get("combo_time_window", 2.0))

    black_region, black_status = _resolve_region(mode, params.get("black_region", [0, 0, 0, 0]), hwnd,
                                                label="黑屏检测区域")
    black_thresh = int(params.get("black_thresh", 60))
    black_ratio = float(params.get("black_ratio", 0.9))
    black_timeout = float(params.get("black_timeout", 2.0))

    bright_region, bright_status = _resolve_region(mode, params.get("bright_region", [0, 0, 0, 0]), hwnd,
                                                  label="亮屏检测区域")
    bright_thresh = int(params.get("bright_thresh", 80))
    bright_ratio = float(params.get("bright_ratio", 0.5))
    bright_timeout = float(params.get("bright_timeout", 8.0))

    wait_before_lock = float(params.get("wait_before_lock", 0.6))
    wait_after_lock = float(params.get("wait_after_lock", 1.5))
    wait_after_bright = float(params.get("wait_after_bright", 0.3))
    cooldown_after_cycle = float(params.get("cooldown_after_cycle", 1.0))

    rtss_hotkey = params.get("rtss_hotkey", "f6")
    idle_timeout = float(params.get("idle_timeout", 0))
    max_count = int(params.get("max_count", 0))
    control_var = params.get("control_var") or params.get("control_var_stop") or "anti_jump_control"
    enable_self_dxgi = bool(params.get("self_dxgi", True))

    use_precise = hasattr(context, 'precise_sleep')

    context.log("info", "[防跳秒] 开始监听 (模式={}, 组合数={}, 超时={}, 最大次数={}, 高精度等待={})".format(
        mode, len(combos), idle_timeout, max_count, use_precise))
    context.log("info", "[防跳秒] 黑屏区域 物理={} ({}), 阈值={} 比例={} 超时={}s".format(
        black_region, black_status, black_thresh, black_ratio, black_timeout))
    context.log("info", "[防跳秒] 亮屏区域 物理={} ({}), 阈值={} 比例={} 超时={}s".format(
        bright_region, bright_status, bright_thresh, bright_ratio, bright_timeout))

    if black_status == "invalid" or bright_status == "invalid":
        msg = ("[防跳秒] 检测区域无法解析为有效区域 "
               "(黑屏={} / 亮屏={})，请检查坐标模式与窗口句柄变量".format(black_status, bright_status))
        context.log("error", msg)
        return {"ok": False, "error": msg, "check_results": {"trigger_count": 0}}

    def _sleep(seconds):
        if use_precise:
            return context.precise_sleep(seconds)
        time.sleep(seconds)
        return True

    channel = CaptureChannel(context, enable_self_dxgi=enable_self_dxgi)
    channel.prepare()
    if not channel.ctx_has_dxgi() and enable_self_dxgi:
        context.log("info", "[防跳秒] 未检测到“截图源”节点，已启用插件自带 DXGI 全屏采集")

    trigger_count = 0
    last_trigger_time = time.time()
    watcher = None
    is_locked = False  # 追踪当前是否处于 RTSS 锁帧状态，用于异常/超时退出时补发恢复键

    def _restore(reason):
        """补发 RTSS 恢复键（幂等：仅当认为处于锁帧状态时发送）。"""
        nonlocal is_locked
        if not is_locked:
            return
        _send_key(rtss_hotkey)
        is_locked = False
        context.log("info", "[防跳秒] 已恢复帧率 ({}): {}".format(reason, rtss_hotkey))

    try:
        if combos:
            watcher = ComboWatcher(combos, time_window)
            watcher.start()

        while True:
            stop_reason = _should_stop(context, control_var, max_count, trigger_count,
                                       idle_timeout, last_trigger_time)
            if stop_reason:
                context.log("info", "[防跳秒] 退出: {}".format(stop_reason))
                break

            if combos:
                if not watcher.matched:
                    if not _sleep(0.05):
                        break
                    continue
                watcher.clear()
                context.log("info", "[防跳秒] 动作组合触发")
            else:
                ok, ratio = _check_black(channel, black_region, black_thresh, black_ratio)
                if not ok:
                    if not _sleep(DETECT_INTERVAL):
                        break
                    continue

            ok, ratio = _check_black(channel, black_region, black_thresh, black_ratio)
            if not ok:
                t0 = time.time()
                black_ok = False
                while time.time() - t0 < black_timeout:
                    stop_reason = _should_stop(context, control_var, max_count, trigger_count,
                                               idle_timeout, last_trigger_time)
                    if stop_reason:
                        break
                    ok, ratio = _check_black(channel, black_region, black_thresh, black_ratio)
                    if ok:
                        black_ok = True
                        break
                    if channel.capture_broken():
                        context.log("error", "[防跳秒] 截图通道连续失败，放弃本轮黑屏检测")
                        break
                    if not _sleep(DETECT_INTERVAL):
                        break
                if not black_ok:
                    if stop_reason:
                        break
                    continue

            context.log("info", "[防跳秒] 黑屏确认，{:.1f}s后锁帧".format(wait_before_lock))
            if not _sleep(wait_before_lock):
                break

            _send_key(rtss_hotkey)
            is_locked = True
            context.log("info", "[防跳秒] 已发送锁帧键: {}".format(rtss_hotkey))

            if not _sleep(wait_after_lock):
                break

            ok, ratio = _check_bright(channel, bright_region, bright_thresh, bright_ratio)
            if not ok:
                t0 = time.time()
                bright_ok = False
                capture_broken = False
                while time.time() - t0 < bright_timeout:
                    stop_reason = _should_stop(context, control_var, max_count, trigger_count,
                                               idle_timeout, last_trigger_time)
                    if stop_reason:
                        break
                    ok, ratio = _check_bright(channel, bright_region, bright_thresh, bright_ratio)
                    if ok:
                        bright_ok = True
                        break
                    if channel.capture_broken():
                        # 截图通道失效时不能继续等满 bright_timeout，
                        # 否则会一直停在锁帧状态。立即按超时处理并恢复帧率。
                        capture_broken = True
                        context.log("error", "[防跳秒] 截图通道连续失败，按超时处理并恢复帧率")
                        break
                    if not _sleep(DETECT_INTERVAL):
                        break
                if not bright_ok:
                    if capture_broken:
                        context.log("warning", "[防跳秒] 亮屏检测中断(截图不可用)，恢复帧率")
                    else:
                        context.log("warning", "[防跳秒] 亮屏检测超时({}s)，恢复帧率".format(bright_timeout))
                    _restore("亮屏检测超时")
                    if stop_reason:
                        break
                    continue

            context.log("info", "[防跳秒] 亮屏确认，{:.1f}s后恢复帧率".format(wait_after_bright))
            if not _sleep(wait_after_bright):
                break

            _restore("亮屏确认")

            if cooldown_after_cycle > 0:
                context.log("info", "[防跳秒] 冷却 {:.1f}s".format(cooldown_after_cycle))
                if not _sleep(cooldown_after_cycle):
                    break

            if watcher:
                watcher.clear()

            trigger_count += 1
            last_trigger_time = time.time()
            context.emit("anti_jump_triggered", {"count": trigger_count})

    except Exception as e:
        logger.error("防跳秒异常: %s", e, exc_info=True)
        return {"ok": False, "error": str(e), "check_results": {"trigger_count": trigger_count}}
    finally:
        if watcher:
            watcher.stop()
        # 任何退出路径（停止/异常/暂停中断）都补发恢复键，避免残留在锁帧状态
        if is_locked:
            _send_key(rtss_hotkey)
            is_locked = False
            context.log("info", "[防跳秒] 退出时仍处于锁帧状态，补发 RTSS 恢复键: {}".format(rtss_hotkey))
        channel.close()

    final_reason = _should_stop(context, control_var, max_count, trigger_count,
                                idle_timeout, last_trigger_time) or "max_count"

    if final_reason == "timeout":
        return {"ok": True, "flow_port": "timeout", "check_results": {"trigger_count": trigger_count}}
    else:
        return {"ok": True, "check_results": {"trigger_count": trigger_count}}
