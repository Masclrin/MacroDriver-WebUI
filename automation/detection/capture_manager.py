# -*- coding: utf-8 -*-
import time
import logging
import numpy as np

from automation.detection.dxgi_capture import DXGICapture

_logger = logging.getLogger("capture_manager")


class CaptureManager:
    def __init__(self, ctx=None):
        self._ctx = ctx
        self._dxgi_instances = {}
        self._dxgi_running_keys = set()
        self._dxgi_fps = {}
        self._dxgi_init_fail_times = {}
        self._init_retry_interval = 5.0

    def _get_dxgi(self, output_idx=0) -> DXGICapture:
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

        if dxgi.is_running():
            if self._dxgi_fps.get(output_idx) == fps:
                return True
            dxgi.stop_background()

        success = dxgi.initialize(adapter_idx=0, output_idx=output_idx)
        if not success:
            self._dxgi_init_fail_times[output_idx] = now
            return False

        is_ctypes = getattr(dxgi._impl, '_ctypes_mode', False)
        if is_ctypes:
            _logger.warning("[截图] DXGI comtypes不可用，使用BitBlt回退模式 (output_idx=%d)", output_idx)

        success = dxgi.start_background(fps=fps)
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
        self._dxgi_instances.clear()

    def _find_best_dxgi(self, region):
        if not self._dxgi_running_keys:
            return None
        if region is None:
            return next(iter(self._dxgi_running_keys))
        abs_x = int(region[0])
        abs_y = int(region[1])
        for output_idx in self._dxgi_running_keys:
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
        method = "BitBlt/MSS"

        if prefer_dxgi and self._dxgi_running_keys:
            best_idx = self._find_best_dxgi(region)
            if best_idx is not None:
                dxgi = self._dxgi_instances[best_idx]
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
                        return frame, method
                else:
                    frame = dxgi.get_latest_frame()
                    if frame is not None:
                        method = f"{dxgi_label} 全帧 (output={best_idx})"
                        return frame, method

                _logger.warning("[截图] %s无帧(output=%d)→回退BitBlt", dxgi_label, best_idx)
                method = f"{dxgi_label}无帧→BitBlt"

        img = self._capture_bitblt(region)
        if img is not None:
            if "→" not in method:
                method = "BitBlt"
            return img, method

        img = self._capture_mss(region)
        method = method.replace("BitBlt", "BitBlt失败→MSS") if "→" in method else "MSS"
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
