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


def _get_hwnd(params, context):
    hwnd_val = params.get("hwnd_var", "")
    if not hwnd_val:
        return None
    try:
        return int(hwnd_val)
    except (ValueError, TypeError):
        pass
    if isinstance(hwnd_val, str) and hwnd_val.startswith("${") and hwnd_val.endswith("}"):
        var_name = hwnd_val[2:-1]
        val = context.get_variable(var_name, "")
        if val:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
    val = context.get_variable(str(hwnd_val), "")
    if val:
        try:
            return int(val)
        except (ValueError, TypeError):
            pass
    return None


def _resolve_region(mode, rect, hwnd=None):
    try:
        from engine.coordinate import resolve_region
        return resolve_region(mode, rect, hwnd)
    except Exception:
        return tuple(int(v) for v in rect)


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
        phys_region = _resolve_region(mode, region, hwnd) if has_region else None
        combos.append({"keys": keys, "region": phys_region, "has_region": has_region})
    return combos


def _to_gray(frame):
    if len(frame.shape) == 2:
        return frame
    if frame.shape[2] == 3:
        try:
            import cv2
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        except ImportError:
            return np.mean(frame, axis=2)
    if frame.shape[2] == 4:
        try:
            import cv2
            return cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        except ImportError:
            return np.mean(frame[:, :, :3], axis=2)
    return frame[:, :, 0]


def _check_black(context, phys_region, thresh, ratio):
    frame = context.capture_screen(list(phys_region))
    if frame is None:
        return False, 0.0
    gray = _to_gray(frame)
    dark = np.sum(gray < thresh)
    total = gray.size
    r = dark / total if total > 0 else 0
    return r >= ratio, r


def _check_bright(context, phys_region, thresh, ratio):
    frame = context.capture_screen(list(phys_region))
    if frame is None:
        return False, 0.0
    gray = _to_gray(frame)
    bright = np.sum(gray > thresh)
    total = gray.size
    r = bright / total if total > 0 else 0
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
            logger.warning("keyboard 库不可用，无法监听按键组合")

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


def _run_monitor(params, context):
    mode = params.get("mode", "screen")
    hwnd = _get_hwnd(params, context)

    combos = _parse_combos(params, mode, hwnd)
    time_window = float(params.get("combo_time_window", 2.0))

    black_region = _resolve_region(mode, params.get("black_region", [0, 0, 0, 0]), hwnd)
    black_thresh = int(params.get("black_thresh", 60))
    black_ratio = float(params.get("black_ratio", 0.9))
    black_timeout = float(params.get("black_timeout", 2.0))

    bright_region = _resolve_region(mode, params.get("bright_region", [0, 0, 0, 0]), hwnd)
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

    use_precise = hasattr(context, 'precise_sleep')

    context.log("info", "[防跳秒] 开始监听 (模式={}, 组合数={}, 超时={}, 最大次数={}, 高精度等待={})".format(
        mode, len(combos), idle_timeout, max_count, use_precise))
    context.log("info", "[防跳秒] 黑屏区域 物理={}".format(black_region))
    context.log("info", "[防跳秒] 亮屏区域 物理={}".format(bright_region))

    def _sleep(seconds):
        if use_precise:
            return context.precise_sleep(seconds)
        time.sleep(seconds)
        return True

    trigger_count = 0
    last_trigger_time = time.time()
    watcher = None
    is_locked = False  # 追踪当前是否处于 RTSS 锁帧状态，用于异常/超时退出时补发恢复键

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
                ok, ratio = _check_black(context, black_region, black_thresh, black_ratio)
                if not ok:
                    if not _sleep(DETECT_INTERVAL):
                        break
                    continue

            ok, ratio = _check_black(context, black_region, black_thresh, black_ratio)
            if not ok:
                t0 = time.time()
                black_ok = False
                while time.time() - t0 < black_timeout:
                    stop_reason = _should_stop(context, control_var, max_count, trigger_count,
                                               idle_timeout, last_trigger_time)
                    if stop_reason:
                        break
                    ok, ratio = _check_black(context, black_region, black_thresh, black_ratio)
                    if ok:
                        black_ok = True
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

            ok, ratio = _check_bright(context, bright_region, bright_thresh, bright_ratio)
            if not ok:
                t0 = time.time()
                bright_ok = False
                while time.time() - t0 < bright_timeout:
                    stop_reason = _should_stop(context, control_var, max_count, trigger_count,
                                               idle_timeout, last_trigger_time)
                    if stop_reason:
                        break
                    ok, ratio = _check_bright(context, bright_region, bright_thresh, bright_ratio)
                    if ok:
                        bright_ok = True
                        break
                    if not _sleep(DETECT_INTERVAL):
                        break
                if not bright_ok:
                    _send_key(rtss_hotkey)
                    is_locked = False
                    if stop_reason:
                        break
                    continue

            context.log("info", "[防跳秒] 亮屏确认，{:.1f}s后恢复帧率".format(wait_after_bright))
            if not _sleep(wait_after_bright):
                break

            _send_key(rtss_hotkey)
            is_locked = False
            context.log("info", "[防跳秒] 已恢复帧率")

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
        if is_locked:
            _send_key(rtss_hotkey)
            context.log("info", "[防跳秒] 退出时仍处于锁帧状态，补发 RTSS 恢复键: {}".format(rtss_hotkey))

    final_reason = _should_stop(context, control_var, max_count, trigger_count,
                                idle_timeout, last_trigger_time) or "max_count"

    if final_reason == "timeout":
        return {"ok": True, "flow_port": "timeout", "check_results": {"trigger_count": trigger_count}}
    else:
        return {"ok": True, "check_results": {"trigger_count": trigger_count}}
