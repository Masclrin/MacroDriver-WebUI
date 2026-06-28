# -*- coding: utf-8 -*-
import threading
import time
import ctypes
from ctypes import (
    wintypes, Structure, POINTER, byref, c_void_p, c_uint, c_int,
    c_ulong, c_long, c_float, c_ubyte, sizeof, cast, WINFUNCTYPE,
)
import numpy as np

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

IID_ID3D11Device = None
IID_IDXGIOutputDuplication = None

D3D11_CREATE_DEVICE_BGRA_SUPPORT = 0x00000020
D3D11_DRIVER_TYPE_HARDWARE = 1
D3D11_SDK_VERSION = 7
D3D11_USAGE_STAGING = 3
D3D11_CPU_ACCESS_READ = 0x00020000
D3D11_MAP_READ = 1
D3D11_BIND_FLAG = 0
DXGI_FORMAT_B8G8R8A8_UNORM = 87
DXGI_ERROR_WAIT_TIMEOUT = 0x887A0027
DXGI_ERROR_ACCESS_LOST = 0x887A0026
S_OK = 0
E_FAIL = 0x80004005
D3D11_MAP_FLAG_DO_NOT_WAIT = 0x100000
DXGI_ERROR_WAS_STILL_DRAWING = 0x887A000A


class RECT(Structure):
    _fields_ = [("left", c_long), ("top", c_long), ("right", c_long), ("bottom", c_long)]


class DXGI_OUTPUT_DESC(Structure):
    _fields_ = [
        ("DeviceName", wintypes.WCHAR * 32),
        ("DesktopCoordinates", RECT),
        ("AttachedToDesktop", wintypes.BOOL),
        ("Rotation", c_uint),
        ("Monitor", c_void_p),
    ]


class DXGI_OUTDUPL_DESC(Structure):
    _fields_ = [
        ("ModeDesc_Width", c_uint),
        ("ModeDesc_Height", c_uint),
        ("ModeDesc_RefreshRate_Numerator", c_uint),
        ("ModeDesc_RefreshRate_Denominator", c_uint),
        ("ModeDesc_Format", c_uint),
        ("ModeDesc_ScanlineOrdering", c_uint),
        ("ModeDesc_Scaling", c_uint),
        ("Rotation", c_uint),
        ("DesktopDirtyRects", wintypes.BOOL),
    ]


class DXGI_OUTDUPL_FRAME_INFO(Structure):
    _fields_ = [
        ("LastPresentTime", c_ulong * 2),
        ("LastMouseUpdateTime", c_ulong * 2),
        ("AccumulatedFrames", c_uint),
        ("RectsCoalesced", wintypes.BOOL),
        ("ProtectedContentMaskedOut", wintypes.BOOL),
        ("PointerPosition", c_long * 3),
        ("TotalMetadataBufferSize", c_uint),
        ("FrameNumber", c_uint),
    ]


class D3D11_TEXTURE2D_DESC(Structure):
    _fields_ = [
        ("Width", c_uint),
        ("Height", c_uint),
        ("MipLevels", c_uint),
        ("ArraySize", c_uint),
        ("Format", c_uint),
        ("SampleDesc_Count", c_uint),
        ("SampleDesc_Quality", c_uint),
        ("Usage", c_uint),
        ("BindFlags", c_uint),
        ("CPUAccessFlags", c_uint),
        ("MiscFlags", c_uint),
    ]


class D3D11_MAPPED_SUBRESOURCE(Structure):
    _fields_ = [
        ("pData", c_void_p),
        ("RowPitch", c_uint),
        ("DepthPitch", c_uint),
    ]


class _DXGICaptureImpl:
    _init_warned_comtypes = False

    def __init__(self):
        self._device = None
        self._context = None
        self._duplication = None
        self._frame_buffer = None
        self._frame_lock = threading.Lock()
        self._thread = None
        self._running = False
        self._initialized = False
        self._screen_width = 0
        self._screen_height = 0
        self._consecutive_timeouts = 0
        self._max_consecutive_timeouts = 3
        self._com_initialized = False
        self._reinit_requested = False
        self._staging_pool = [None, None]
        self._pool_write_idx = 0
        self._pool_copied = [False, False]
        self._pool_desc_key = None
        self._pool_width = 0
        self._pool_height = 0

    @staticmethod
    def _enum_monitor_rect(target_index):
        try:
            monitors = []
            def _callback(hmon, hdc, lprect, lparam):
                rect = lprect.contents
                monitors.append((rect.left, rect.top, rect.right, rect.bottom))
                return True
            MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(RECT), ctypes.c_long)
            user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_callback), 0)
            if 0 <= target_index < len(monitors):
                return monitors[target_index]
        except Exception:
            pass
        return None

    def get_output_origin(self):
        if getattr(self, '_ctypes_mode', False):
            return getattr(self, '_ctypes_origin_x', 0), getattr(self, '_ctypes_origin_y', 0)
        return getattr(self, '_output_origin_x', 0), getattr(self, '_output_origin_y', 0)

    def _ensure_pool(self, desc):
        try:
            from comtypes.gen import D3D11
        except ImportError:
            return False

        desc_key = (desc.Width, desc.Height, desc.Format,
                    desc.SampleDesc_Count, desc.SampleDesc_Quality)

        if self._staging_desc_key == desc_key and self._staging_pool[0] is not None:
            return True

        for i in range(2):
            if self._staging_pool[i] is not None:
                try:
                    self._staging_pool[i].Release()
                except Exception:
                    pass
                self._staging_pool[i] = None
            self._pool_copied[i] = False

        try:
            staging_desc = D3D11.D3D11_TEXTURE2D_DESC()
            staging_desc.Width = desc.Width
            staging_desc.Height = desc.Height
            staging_desc.MipLevels = 1
            staging_desc.ArraySize = 1
            staging_desc.Format = desc.Format
            staging_desc.SampleDesc_Count = desc.SampleDesc_Count
            staging_desc.SampleDesc_Quality = desc.SampleDesc_Quality
            staging_desc.Usage = D3D11_USAGE_STAGING
            staging_desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ
            staging_desc.BindFlags = 0
            staging_desc.MiscFlags = 0

            for i in range(2):
                self._staging_pool[i] = self._device.CreateTexture2D(staging_desc, None)

            self._staging_desc_key = desc_key
            self._pool_width = desc.Width
            self._pool_height = desc.Height
            self._pool_write_idx = 0
            return True
        except Exception as e:
            print(f"[DXGI] 双缓冲池创建失败: {e}")
            for i in range(2):
                if self._staging_pool[i] is not None:
                    try:
                        self._staging_pool[i].Release()
                    except Exception:
                        pass
                    self._staging_pool[i] = None
            self._staging_desc_key = None
            return False

    def initialize(self, adapter_idx=0, output_idx=0) -> bool:
        try:
            ctypes.windll.ole32.CoInitializeEx(None, 0x2)
            self._com_initialized = True
        except Exception:
            pass

        try:
            import comtypes
            from comtypes import GUID
            from comtypes.gen import DXGI as _DXGI
            from comtypes.gen import D3D11 as _D3D11
        except (ImportError, OSError):
            try:
                import comtypes.client
                comtypes.client.GetModule("dxgi.dll")
                comtypes.client.GetModule("d3d11.dll")
                from comtypes.gen import DXGI as _DXGI
                from comtypes.gen import D3D11 as _D3D11
            except Exception as e:
                if not _DXGICaptureImpl._init_warned_comtypes:
                    print(f"[DXGI] comtypes DXGI/D3D11 模块不可用: {e}")
                    _DXGICaptureImpl._init_warned_comtypes = True
                return self._initialize_ctypes(adapter_idx, output_idx)

        try:
            return self._initialize_comtypes(adapter_idx, output_idx, _DXGI, _D3D11)
        except Exception as e:
            print(f"[DXGI] comtypes 初始化失败，回退 ctypes: {e}")
            return self._initialize_ctypes(adapter_idx, output_idx)

    def _initialize_ctypes(self, adapter_idx=0, output_idx=0) -> bool:
        if not _DXGICaptureImpl._init_warned_comtypes:
            print("[DXGI] comtypes 不可用，ctypes 模式仅支持 BitBlt 回退截图，不支持真正的 DXGI Desktop Duplication")
            _DXGICaptureImpl._init_warned_comtypes = True
        try:
            target_rect = self._enum_monitor_rect(output_idx)
            if target_rect:
                self._screen_width = target_rect[2] - target_rect[0]
                self._screen_height = target_rect[3] - target_rect[1]
                self._ctypes_origin_x = target_rect[0]
                self._ctypes_origin_y = target_rect[1]
            else:
                sw = user32.GetSystemMetrics(0)
                sh = user32.GetSystemMetrics(1)
                if sw <= 0 or sh <= 0:
                    return False
                self._screen_width = sw
                self._screen_height = sh
                self._ctypes_origin_x = 0
                self._ctypes_origin_y = 0

            self._ctypes_mode = True
            self._initialized = True
            return True
        except Exception as e:
            print(f"[DXGI] ctypes 初始化失败: {e}")
            return False

    def _initialize_comtypes(self, adapter_idx, output_idx, _DXGI, _D3D11):
        factory = comtypes.CoCreateInstance(
            _DXGI.IDXGIFactory1._reg_clsid_,
            interface=_DXGI.IDXGIFactory1,
        )
        adapter = factory.EnumAdapters1(adapter_idx)
        output = adapter.EnumOutputs(output_idx)
        desc = output.GetDesc()
        self._screen_width = desc.DesktopCoordinates.right - desc.DesktopCoordinates.left
        self._screen_height = desc.DesktopCoordinates.bottom - desc.DesktopCoordinates.top
        self._output_origin_x = desc.DesktopCoordinates.left
        self._output_origin_y = desc.DesktopCoordinates.top

        feature_level = c_uint()
        device_ptr = POINTER(_D3D11.ID3D11Device)()
        context_ptr = POINTER(_D3D11.ID3D11DeviceContext)()

        _D3D11_lib = ctypes.windll.d3d11
        _D3D11_lib.D3D11CreateDevice.argtypes = [
            c_void_p, c_uint, c_void_p, c_uint,
            POINTER(c_uint), c_uint, c_uint,
            POINTER(POINTER(_D3D11.ID3D11Device)),
            POINTER(c_uint),
            POINTER(POINTER(_D3D11.ID3D11DeviceContext)),
        ]
        _D3D11_lib.D3D11CreateDevice.restype = ctypes.c_long

        hr = _D3D11_lib.D3D11CreateDevice(
            None,
            D3D11_DRIVER_TYPE_HARDWARE,
            None,
            D3D11_CREATE_DEVICE_BGRA_SUPPORT,
            None,
            0,
            D3D11_SDK_VERSION,
            byref(device_ptr),
            byref(feature_level),
            byref(context_ptr),
        )

        if hr != S_OK or not device_ptr:
            raise RuntimeError(f"D3D11CreateDevice failed with hr=0x{hr & 0xFFFFFFFF:08X}")

        self._device = device_ptr.QueryInterface(_D3D11.ID3D11Device)
        self._context = context_ptr.QueryInterface(_D3D11.ID3D11DeviceContext)

        output1 = output.QueryInterface(_DXGI.IDXGIOutput1)
        self._duplication = output1.DuplicateOutput(self._device)
        self._ctypes_mode = False
        self._initialized = True
        return True

    def acquire_frame(self, timeout_ms=100) -> np.ndarray | None:
        if not self._initialized:
            return None
        if getattr(self, '_ctypes_mode', False):
            return self._acquire_frame_fallback()
        return self._acquire_frame_comtypes(timeout_ms)

    def _acquire_frame_comtypes(self, timeout_ms=100) -> np.ndarray | None:
        try:
            from comtypes.gen import DXGI, D3D11
        except ImportError:
            return None

        try:
            frame_info = DXGI.DXGI_OUTDUPL_FRAME_INFO()
            resource = POINTER(DXGI.IDXGIResource)()
            hr = self._duplication.AcquireNextFrame(timeout_ms, byref(frame_info), byref(resource))
            if hr != S_OK:
                if hr == DXGI_ERROR_WAIT_TIMEOUT or hr == DXGI_ERROR_ACCESS_LOST:
                    self._consecutive_timeouts += 1
                    if self._consecutive_timeouts >= self._max_consecutive_timeouts:
                        self._request_reinit()
                return None
            self._consecutive_timeouts = 0

            try:
                surface = resource.QueryInterface(D3D11.ID3D11Texture2D)
                desc = D3D11.D3D11_TEXTURE2D_DESC()
                surface.GetDesc(byref(desc))

                if not self._ensure_pool(desc):
                    return None

                w = self._pool_write_idx
                r = 1 - w

                self._context.CopyResource(self._staging_pool[w], surface)
                self._pool_copied[w] = True

                frame_bgr = None
                if self._pool_copied[r]:
                    mapped = D3D11.D3D11_MAPPED_SUBRESOURCE()
                    try:
                        self._context.Map(
                            self._staging_pool[r], 0, D3D11_MAP_READ,
                            D3D11_MAP_FLAG_DO_NOT_WAIT, byref(mapped)
                        )
                        width = self._pool_width
                        height = self._pool_height
                        row_pitch = mapped.RowPitch
                        data_ptr = mapped.pData

                        buf = (c_ubyte * (row_pitch * height)).from_address(data_ptr)
                        frame = np.frombuffer(buf, dtype=np.uint8).reshape((height, row_pitch))
                        frame = frame[:, :width * 4].copy()
                        frame = frame.reshape((height, width, 4))
                        frame_bgr = frame[:, :, :3].copy()

                        self._context.Unmap(self._staging_pool[r], 0)
                        self._pool_copied[r] = False
                    except Exception:
                        pass

                self._pool_write_idx = r
                return frame_bgr
            finally:
                self._duplication.ReleaseFrame()
        except Exception as e:
            print(f"[DXGI] comtypes 帧获取失败: {e}")
            return None

    def _acquire_frame_fallback(self) -> np.ndarray | None:
        hdc = None
        hdc_mem = None
        hbitmap = None
        old_bmp = None
        try:
            sw = self._screen_width
            sh = self._screen_height
            if sw <= 0 or sh <= 0:
                return None
            origin_x = getattr(self, '_ctypes_origin_x', 0)
            origin_y = getattr(self, '_ctypes_origin_y', 0)

            hdc = user32.GetDC(0)
            if not hdc:
                return None

            hdc_mem = ctypes.windll.gdi32.CreateCompatibleDC(hdc)
            if not hdc_mem:
                user32.ReleaseDC(0, hdc)
                hdc = None
                hdc_mem = None
                return None

            hbitmap = ctypes.windll.gdi32.CreateCompatibleBitmap(hdc, sw, sh)
            if not hbitmap:
                ctypes.windll.gdi32.DeleteDC(hdc_mem)
                user32.ReleaseDC(0, hdc)
                hdc_mem = None
                hdc = None
                return None

            old_bmp = ctypes.windll.gdi32.SelectObject(hdc_mem, hbitmap)

            ctypes.windll.gdi32.BitBlt(hdc_mem, 0, 0, sw, sh, hdc, origin_x, origin_y, 0x00CC0020)

            class BITMAPINFOHEADER(Structure):
                _fields_ = [
                    ("biSize", c_uint),
                    ("biWidth", c_long),
                    ("biHeight", c_long),
                    ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD),
                    ("biCompression", c_uint),
                    ("biSizeImage", c_uint),
                    ("biXPelsPerMeter", c_long),
                    ("biYPelsPerMeter", c_long),
                    ("biClrUsed", c_uint),
                    ("biClrImportant", c_uint),
                ]

            bi = BITMAPINFOHEADER()
            bi.biSize = sizeof(BITMAPINFOHEADER)
            bi.biWidth = sw
            bi.biHeight = -sh
            bi.biPlanes = 1
            bi.biBitCount = 32
            bi.biCompression = 0

            buf_size = sw * sh * 4
            pixel_buf = (c_ubyte * buf_size)()
            ctypes.windll.gdi32.GetDIBits(
                hdc_mem, hbitmap, 0, sh, pixel_buf, byref(bi), 0
            )

            frame = np.frombuffer(pixel_buf, dtype=np.uint8).reshape((sh, sw, 4))
            frame_bgr = frame[:, :, :3].copy()
            return frame_bgr
        except Exception as e:
            print(f"[DXGI] BitBlt 回退截图失败: {e}")
            return None
        finally:
            if hdc_mem is not None and old_bmp is not None:
                try:
                    ctypes.windll.gdi32.SelectObject(hdc_mem, old_bmp)
                except Exception:
                    pass
            if hbitmap is not None:
                try:
                    ctypes.windll.gdi32.DeleteObject(hbitmap)
                except Exception:
                    pass
            if hdc_mem is not None:
                try:
                    ctypes.windll.gdi32.DeleteDC(hdc_mem)
                except Exception:
                    pass
            if hdc is not None:
                try:
                    user32.ReleaseDC(0, hdc)
                except Exception:
                    pass

    def start_background(self, fps=60) -> bool:
        if self._running:
            return True
        if not self._initialized:
            if not self.initialize():
                return False
        self._running = True
        self._reinit_requested = False
        interval = 1.0 / max(1, min(fps, 144))
        self._thread = threading.Thread(target=self._capture_loop, args=(interval,), daemon=True)
        self._thread.start()
        return True

    def stop_background(self):
        self._running = False
        self._reinit_requested = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        self._release_resources()

    def get_latest_frame(self) -> np.ndarray | None:
        with self._frame_lock:
            if self._frame_buffer is not None:
                return self._frame_buffer.copy()
            return None

    def get_region_frame(self, left, top, width, height) -> np.ndarray | None:
        with self._frame_lock:
            if self._frame_buffer is None:
                return None
            fh, fw = self._frame_buffer.shape[:2]
            x1 = max(0, int(left))
            y1 = max(0, int(top))
            x2 = min(fw, int(left + width))
            y2 = min(fh, int(top + height))
            if x2 <= x1 or y2 <= y1:
                return None
            return self._frame_buffer[y1:y2, x1:x2].copy()

    def is_running(self) -> bool:
        return self._running

    def _capture_loop(self, interval):
        com_initialized = False
        try:
            try:
                ctypes.windll.ole32.CoInitializeEx(None, 0x2)
                com_initialized = True
            except Exception:
                pass

            while self._running:
                if self._reinit_requested:
                    self._do_reinit_in_thread()
                    if not self._running:
                        break
                    continue

                frame = self.acquire_frame(timeout_ms=100)
                if frame is not None:
                    with self._frame_lock:
                        self._frame_buffer = frame
                time.sleep(interval)
        finally:
            if com_initialized:
                try:
                    ctypes.windll.ole32.CoUninitialize()
                except Exception:
                    pass

    def _request_reinit(self):
        self._reinit_requested = True

    def _do_reinit_in_thread(self):
        self._release_resources()
        try:
            if self.initialize():
                self._consecutive_timeouts = 0
                self._reinit_requested = False
                print("[DXGI] 重新初始化成功")
            else:
                print("[DXGI] 重新初始化失败，停止后台采集")
                self._running = False
                self._reinit_requested = False
        except Exception as e:
            print(f"[DXGI] 重新初始化异常: {e}")
            self._running = False
            self._reinit_requested = False

    def _try_reinitialize(self):
        self._request_reinit()

    def _release_resources(self):
        for i in range(2):
            if self._staging_pool[i] is not None:
                try:
                    self._staging_pool[i].Release()
                except Exception:
                    pass
                self._staging_pool[i] = None
            self._pool_copied[i] = False
        self._staging_desc_key = None
        self._pool_width = 0
        self._pool_height = 0
        self._pool_write_idx = 0
        for attr_name in ('_duplication', '_context', '_device'):
            obj = getattr(self, attr_name, None)
            if obj is not None:
                try:
                    obj.Release()
                except Exception:
                    pass
                setattr(self, attr_name, None)
        with self._frame_lock:
            self._frame_buffer = None
        self._initialized = False


class DXGICapture:
    def __init__(self):
        self._impl = _DXGICaptureImpl()

    def initialize(self, adapter_idx=0, output_idx=0) -> bool:
        return self._impl.initialize(adapter_idx, output_idx)

    def acquire_frame(self, timeout_ms=100) -> np.ndarray | None:
        return self._impl.acquire_frame(timeout_ms)

    def start_background(self, fps=60) -> bool:
        return self._impl.start_background(fps)

    def stop_background(self):
        self._impl.stop_background()

    def get_latest_frame(self) -> np.ndarray | None:
        return self._impl.get_latest_frame()

    def get_region_frame(self, left, top, width, height) -> np.ndarray | None:
        return self._impl.get_region_frame(left, top, width, height)

    def get_output_origin(self):
        return self._impl.get_output_origin()

    def is_running(self) -> bool:
        return self._impl.is_running()
