# -*- coding: utf-8 -*-
import time
import logging
import threading
import numpy as np

from automation.detection.dxgi_capture import DXGICapture

_logger = logging.getLogger("capture_manager")

# 共享帧缓存的硬性上限(ms)。
# 帧缓存只在「同一个 epoch（同一次循环迭代）」内复用，但若脚本里没有循环节点，
# epoch 将永不递增，仅靠 epoch 判断会退化成"永久冻结帧"。
# 因此无论用户如何配置，都额外施加上限：默认 4ms 远小于 60fps 的 16.7ms 帧周期，
# 最多带来 4ms 的陈旧度，却可省掉一次 13.7ms 的全屏 BitBlt。
_FRAME_CACHE_HARD_TTL_MS = 4.0


class CaptureManager:
    def __init__(self, ctx=None):
        self._ctx = ctx
        self._dxgi_instances = {}
        self._dxgi_running_keys = set()
        self._dxgi_fps = {}
        self._dxgi_init_fail_times = {}
        self._init_retry_interval = 5.0
        # 所有可变状态（含 DXGI 实例集合）由同一把锁保护。
        # 监视器轮询线程与主执行线程会并发调用 capture()，
        # 而 _handle_capture_source 可能在另一线程 stop_dxgi() 修改 _dxgi_running_keys，
        # 无锁迭代会抛 "Set changed size during iteration"。
        self._lock = threading.RLock()
        # --- 共享帧缓存 ---
        # 一次循环迭代里若有 N 个检测节点，修复前会做 N 次独立截图（全屏各 13.7ms）。
        # 这里让它们复用同一帧：entry = (frame, timestamp, epoch)
        self._frame_cache = {}
        self._frame_epoch = 0
        # 由精度档位下发（core.precision_profile）：
        # 延迟优先=2ms / 均衡=4ms / 低占用=8ms。0 表示用内置安全默认值。
        try:
            from core.precision_profile import get_default_frame_cache_ttl
            self._frame_ttl_ms = get_default_frame_cache_ttl()
        except Exception:
            self._frame_ttl_ms = 0.0

    # ------------------------------------------------------------------
    # 共享帧缓存
    # ------------------------------------------------------------------
    def set_frame_ttl_ms(self, ttl_ms: float):
        """设置共享帧缓存的时间上限(ms)。0 表示使用内置安全默认值。"""
        with self._lock:
            self._frame_ttl_ms = max(0.0, float(ttl_ms or 0.0))

    def invalidate_frame_cache(self):
        """开启新的帧世代。

        由执行引擎在每次循环迭代开始时调用（_reset_body_nodes），
        从而使「一次循环迭代 = 一次截图」成立。
        """
        with self._lock:
            self._frame_epoch += 1
            if self._frame_epoch > 1 << 62:
                self._frame_epoch = 0
                self._frame_cache.clear()
            else:
                self._frame_cache.clear()

    def _frame_cache_get(self, cache_key):
        with self._lock:
            entry = self._frame_cache.get(cache_key)
            if entry is None:
                return None
            frame, ts, epoch = entry
            if epoch != self._frame_epoch:
                return None
            ttl = self._frame_ttl_ms if self._frame_ttl_ms > 0 else _FRAME_CACHE_HARD_TTL_MS
            if (time.perf_counter() - ts) * 1000.0 >= ttl:
                return None
            return frame

    def _frame_cache_put(self, cache_key, frame):
        with self._lock:
            self._frame_cache[cache_key] = (frame, time.perf_counter(), self._frame_epoch)

    def get_frame_cache_stats(self):
        with self._lock:
            return {
                "epoch": self._frame_epoch,
                "entries": len(self._frame_cache),
                "ttl_ms": self._frame_ttl_ms or _FRAME_CACHE_HARD_TTL_MS,
            }

    def _get_dxgi(self, output_idx=0) -> DXGICapture:
        with self._lock:
            if output_idx not in self._dxgi_instances:
                self._dxgi_instances[output_idx] = DXGICapture()
            return self._dxgi_instances[output_idx]

    def start_dxgi(self, fps=60, output_idx=0) -> bool:
        now = time.perf_counter()
        last_fail = self._dxgi_init_fail_times.get(output_idx, 0.0)
        if now - last_fail < self._init_retry_interval:
            _logger.info("[截图] DXGI output=%d 初始化冷却中(%.1fs后重试)", output_idx, self._init_retry_interval - (now - last_fail))
            return False

        dxgi = self._get_dxgi(output_idx)

        with self._lock:
            if dxgi.is_running():
                if self._dxgi_fps.get(output_idx) == fps:
                    return True
                dxgi.stop_background()

        success = dxgi.initialize(adapter_idx=0, output_idx=output_idx)
        if not success:
            self._dxgi_init_fail_times[output_idx] = now
            return False

        # 用户请求的帧率用于配置比对（避免被限速后每轮都被判定为“配置已变”而反复重启）；
        # 实际运行帧率是 run_fps。
        run_fps = fps

        is_ctypes = getattr(dxgi._impl, '_ctypes_mode', False)
        if is_ctypes:
            # 说明：comtypes 拿不到 DXGI/D3D11 类型库时（comtypes.gen 里没有对应模块、
            # 且 comtypes.client.GetModule 报 TYPE_E_CANTLOADLIBRARY），这里并不是真正的
            # Desktop Duplication，而是「每帧做一次全屏 BitBlt」。本机实测全屏 BitBlt
            # 约 19ms/帧，若仍按用户配置的 60fps 跑，会占用一个以上 CPU 核心，
            # 与「不抢占游戏 CPU」的约束冲突。因此回退模式下把运行帧率限制在上限内。
            _BITBLT_FALLBACK_MAX_FPS = 20
            if run_fps > _BITBLT_FALLBACK_MAX_FPS:
                run_fps = _BITBLT_FALLBACK_MAX_FPS
                _logger.warning(
                    "[截图] DXGI 实为 BitBlt 回退模式（真 Desktop Duplication 不可用，"
                    "全屏 BitBlt 约19ms/帧）：运行帧率 %d → %d 以避免占满 CPU (output_idx=%d)",
                    fps, run_fps, output_idx)
            else:
                _logger.warning(
                    "[截图] DXGI comtypes不可用，使用BitBlt回退模式 "
                    "(非 Desktop Duplication，独占全屏可能取到黑屏) (output_idx=%d)", output_idx)

        success = dxgi.start_background(fps=run_fps)
        with self._lock:
            if success:
                self._dxgi_running_keys.add(output_idx)
                self._dxgi_fps[output_idx] = fps
            else:
                self._dxgi_init_fail_times[output_idx] = time.perf_counter()
        return success

    def config_changed(self, fps, output_idx) -> bool:
        if output_idx not in self._dxgi_running_keys:
            return True
        if self._dxgi_fps.get(output_idx) != fps:
            return True
        return False

    def stop_dxgi(self, output_idx=None):
        with self._lock:
            self._frame_cache.clear()
        if output_idx is not None:
            dxgi = self._dxgi_instances.get(output_idx)
            if dxgi is not None and dxgi.is_running():
                dxgi.stop_background()
            self._dxgi_running_keys.discard(output_idx)
            self._dxgi_fps.pop(output_idx, None)
            self._dxgi_init_fail_times.pop(output_idx, None)
        else:
            for idx, dxgi in self._dxgi_instances.items():
                if dxgi.is_running():
                    dxgi.stop_background()
            self._dxgi_running_keys.clear()
            self._dxgi_fps.clear()
            self._dxgi_init_fail_times.clear()

    def stop_all(self):
        self.stop_dxgi()
        with self._lock:
            self._dxgi_instances.clear()

    def _find_best_dxgi(self, region):
        with self._lock:
            running = tuple(self._dxgi_running_keys)
        if not running:
            return None
        if region is None:
            return running[0]
        abs_x = int(region[0])
        abs_y = int(region[1])
        for output_idx in running:
            with self._lock:
                dxgi = self._dxgi_instances.get(output_idx)
            if dxgi is None or not dxgi.is_running():
                continue
            origin_x, origin_y = dxgi.get_output_origin()
            w = dxgi._impl._screen_width
            h = dxgi._impl._screen_height
            if origin_x <= abs_x < origin_x + w and origin_y <= abs_y < origin_y + h:
                return output_idx
        return None

    def capture(self, region=None, prefer_dxgi=True):
        # 共享帧缓存：同一循环迭代内的多个检测节点复用一次截图。
        cache_key = None
        if region is not None:
            try:
                cache_key = (int(region[0]), int(region[1]), int(region[2]), int(region[3]))
            except Exception:
                cache_key = None
        else:
            cache_key = "__full__"

        if cache_key is not None:
            cached = self._frame_cache_get(cache_key)
            if cached is not None:
                return cached, "共享帧缓存"

        method = "BitBlt/MSS"

        with self._lock:
            has_dxgi = bool(self._dxgi_running_keys)
        if prefer_dxgi and has_dxgi:
            best_idx = self._find_best_dxgi(region)
            if best_idx is not None:
                with self._lock:
                    dxgi = self._dxgi_instances.get(best_idx)
                if dxgi is not None:
                    is_ctypes = getattr(dxgi._impl, '_ctypes_mode', False)
                    dxgi_label = "DXGI(BitBlt回退)" if is_ctypes else "DXGI"

                    if region is not None:
                        origin_x, origin_y = dxgi.get_output_origin()
                        local_left = int(region[0]) - origin_x
                        local_top = int(region[1]) - origin_y
                        local_w = int(region[2])
                        local_h = int(region[3])
                        frame = dxgi.get_region_frame(local_left, local_top, local_w, local_h)
                        if frame is not None:
                            method = f"{dxgi_label} (output={best_idx})"
                            self._frame_cache_put(cache_key, frame)
                            return frame, method
                    else:
                        frame = dxgi.get_latest_frame()
                        if frame is not None:
                            method = f"{dxgi_label} 全帧 (output={best_idx})"
                            self._frame_cache_put(cache_key, frame)
                            return frame, method

                    _logger.warning("[截图] %s无帧(output=%d)→回退BitBlt", dxgi_label, best_idx)
                    method = f"{dxgi_label}无帧→BitBlt"

        img = self._capture_bitblt(region)
        if img is not None:
            if "→" not in method:
                method = "BitBlt"
            self._frame_cache_put(cache_key, img)
            return img, method

        img = self._capture_mss(region)
        method = method.replace("BitBlt", "BitBlt失败→MSS") if "→" in method else "MSS"
        if img is not None:
            self._frame_cache_put(cache_key, img)
        return img, method

    def _capture_bitblt(self, region=None) -> np.ndarray:
        from automation.detection.capture import _capture_bitblt
        return _capture_bitblt(region)

    def _capture_mss(self, region=None) -> np.ndarray:
        from automation.detection.capture import _capture_mss
        return _capture_mss(region)

    def is_dxgi_running(self, output_idx=None) -> bool:
        if output_idx is not None:
            return output_idx in self._dxgi_running_keys
        return len(self._dxgi_running_keys) > 0

    def get_running_output_indices(self):
        return set(self._dxgi_running_keys)
