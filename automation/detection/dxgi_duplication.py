# -*- coding: utf-8 -*-
"""原生 ctypes 实现的 DXGI Desktop Duplication 截图。

为什么不用 comtypes？
--------------------
comtypes 需要 `comtypes.gen.DXGI` / `comtypes.gen.D3D11` 两个自动生成的模块，
而 DXGI/D3D11 都不是标准 Windows 组件（dxgi.dll / d3d11.dll 内含的 type library
在常规系统上取不到，`comtypes.client.GetModule` 会报 TYPE_E_CANTLOADLIBRARY）。
于是原实现只能在 `_initialize_ctypes()` 里退化成「每帧一次全屏 BitBlt」——
窗口化程序尚可，**独占全屏 / 硬件加速内容只能取到黑屏**。

本模块直接用 ctypes 构造 COM 接口指针、按虚表(vtable)下标调用方法，
完全不需要 type library，因此任何 Python 3.8+ / 任何 Windows 10 1803+ 都能用真 DXGI。

覆盖的能力（最小子集）：
    CreateDXGIFactory1 → EnumAdapters1 → EnumOutputs → QI(IDXGIOutput1) → DuplicateOutput
    D3D11CreateDevice → CreateTexture2D(staging)
    AcquireNextFrame → QI(ID3D11Texture2D) → CopyResource → Map/Unmap → ReleaseFrame

线程要求：同一实例只应被一个线程使用；使用线程需已 CoInitializeEx（MTA 即可）。
"""

from __future__ import annotations

import ctypes
import logging
import threading
from ctypes import (
    POINTER, Structure, byref, c_int, c_long, c_ubyte, c_uint, c_ulong, c_void_p,
    c_wchar, WINFUNCTYPE, cast, sizeof,
)

import numpy as np

_logger = logging.getLogger("dxgi_duplication")

_IS_WINDOWS = hasattr(ctypes, "WinDLL")

# ── 常量 ──────────────────────────────────────────────────────
D3D_DRIVER_TYPE_UNKNOWN = 0
D3D_DRIVER_TYPE_HARDWARE = 1
D3D11_CREATE_DEVICE_BGRA_SUPPORT = 0x00000020
D3D11_SDK_VERSION = 7

# D3D11_USAGE：0=DEFAULT 1=IMMUTABLE 2=DYNAMIC 3=STAGING
# （注意 D3D11 里没有 UNKNOWN，别把 DEFAULT 当成 1——写错会得到 E_INVALIDARG）
D3D11_USAGE_DEFAULT = 0
D3D11_USAGE_IMMUTABLE = 1
D3D11_USAGE_DYNAMIC = 2
D3D11_USAGE_STAGING = 3
D3D11_CPU_ACCESS_WRITE = 0x00010000
D3D11_CPU_ACCESS_READ = 0x00020000
# D3D11_MAP：1=READ 2=WRITE 3=READ_WRITE
D3D11_MAP_READ = 1
D3D11_BIND_SHADER_RESOURCE = 0x00000008
DXGI_FORMAT_B8G8R8A8_UNORM = 87
DXGI_FORMAT_B8G8R8A8_UNORM_SRGB = 91

S_OK = 0
D3DERR_INVALIDCALL = 0x8876086C
DXGI_ERROR_WAIT_TIMEOUT = 0x887A0027
DXGI_ERROR_ACCESS_LOST = 0x887A0026
DXGI_ERROR_NOT_FOUND = 0x887A0002
DXGI_ERROR_UNSUPPORTED = 0x887A0004
DXGI_ERROR_NOT_CURRENTLY_AVAILABLE = 0x887A0022
DXGI_ERROR_SESSION_DISCONNECTED = 0x887A0028
DXGI_ERROR_INVALID_CALL = 0x887A0001
DXGI_ERROR_WAS_STILL_DRAWING = 0x887A000A

# ── COM 接口 IID ──────────────────────────────────────────────
CLSID_IDXGIFactory1 = "{770AAE78-F26F-4DBA-A829-253C83D1B387}"
IID_IDXGIAdapter1 = "{29038F61-3839-4626-91FD-086879011A05}"
IID_IDXGIOutput = "{AE02EEDB-C735-4690-8D52-5A8EDCAE1E7D}"
IID_IDXGIOutput1 = "{00CDDEA8-939B-4B83-A340-A685226666CC}"
IID_IDXGIResource = "{035F3AB4-482E-4E50-B4A8-8F7A8955010B}"
IID_IDXGIOutputDuplication = "{191CFAC3-A341-470D-B26E-A8AD28A6A364}"
IID_ID3D11Texture2D = "{6F15AAF2-D208-4E89-9AB4-489535D34F9C}"
IID_ID3D11Device = "{DB6F6DDB-AC77-4E88-8253-819DF9BBF140}"
IID_ID3D11DeviceContext = "{C0BFA96C-E089-44FB-8EAF-26F8796190DA}"
IID_IDXGIAdapter = "{2411E7E1-12AC-4CCF-BD14-9798E8534DC0}"
IID_IDXGIOutput6 = "{068346E8-AAEC-4B34-ADD7-137F513F77A1}"


# ── 虚表下标 ──────────────────────────────────────────────────
# IUnknown:            0 QueryInterface / 1 AddRef  / 2 Release
# IDXGIObject:         3 SetPrivateData / 4 SetPrivateDataInterface / 5 GetPrivateData / 6 GetParent
# IDXGIFactory:        7 EnumAdapters / 8 MakeWindowAssociation / 9 GetWindowAssociation
#                     10 CreateSwapChain / 11 CreateSoftwareAdapter
# IDXGIFactory1:      12 EnumAdapters1 / 13 IsCurrent
VT_QUERYINTERFACE = 0
VT_RELEASE = 2
VT_ENUM_ADAPTERS1 = 12

# IDXGIAdapter (IDXGIObject 之后): 7 EnumOutputs / 8 GetDesc / 9 CheckInterfaceSupport
VT_ADAPTER_ENUM_OUTPUTS = 7

# IDXGIOutput (IDXGIObject 之后):
#   7 GetDesc / 8 GetDisplayModeList / 9 FindClosestMatchingMode / 10 WaitForVBlank
#   11 TakeOwnership / 12 ReleaseOwnership / 13 GetGammaControlCapabilities
#   14 SetGammaControl / 15 GetGammaControl / 16 SetDisplaySurface
#   17 GetDisplaySurfaceData / 18 GetFrameStatistics
# IDXGIOutput1: 19 GetDisplayModeList1 / 20 FindClosestMatchingMode1
#              21 GetDisplaySurfaceData1 / 22 DuplicateOutput
VT_OUTPUT_GET_DESC = 7
VT_OUTPUT1_DUPLICATE_OUTPUT = 22

# IDXGIOutputDuplication (IDXGIObject 之后):
#   7 GetDesc / 8 AcquireNextFrame / 9 GetFrameDirtyRects / 10 GetFrameMoveRects
#   11 GetFramePointerShape / 12 MapDesktopSurface / 13 UnMapDesktopSurface / 14 ReleaseFrame
VT_DUPL_GET_DESC = 7
VT_DUPL_ACQUIRE_NEXT_FRAME = 8
VT_DUPL_RELEASE_FRAME = 14

# ID3D11Device (IUnknown 之后):
#   3 CreateBuffer / 4 CreateTexture1D / 5 CreateTexture2D / 6 CreateTexture3D ...
VT_DEVICE_CREATE_TEXTURE2D = 5

# ID3D11DeviceContext —— 注意它继承的是 ID3D11DeviceChild（不是直接 IUnknown），
# 因此 IUnknown(0..2) 之后还有 4 个基类方法：
#   3 GetDevice / 4 GetPrivateData / 5 SetPrivateData / 6 SetPrivateDataInterface
# 之后才是 DeviceContext 自己的方法，从下标 7 开始：
#   7 VSSetConstantBuffers / 8 PSSetShaderResources / 9 PSSetShader / 10 PSSetSamplers
#   11 VSSetShader / 12 DrawIndexed / 13 Draw / 14 Map / 15 Unmap
#   16 PSSetConstantBuffers / 17 IASetInputLayout ... 28 UpdateSubresource / 29 CopyResource
# （漏算那 4 个基类槽位会让 25 落到 GSSetSamplers 上，表现为 Map/Copy 触发访问违例。）
VT_CONTEXT_MAP = 14
VT_CONTEXT_UNMAP = 15
VT_CONTEXT_COPY_RESOURCE = 29

# ID3D11Texture2D（继承 IUnknown→ID3D11DeviceChild→ID3D11Resource）：
#   3 GetDevice / 4 GetPrivateData / 5 SetPrivateData / 6 SetPrivateDataInterface
#   7 GetType / 8 SetEvictionPriority / 9 GetEvictionPriority / 10 GetDesc
VT_TEXTURE2D_GET_DESC = 10


# ── 基础结构体 ────────────────────────────────────────────────
class GUID(Structure):
    _fields_ = [
        ("Data1", c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", c_ubyte * 8),
    ]


def _guid(spec: str) -> GUID:
    s = spec.strip().strip("{}")
    p = s.split("-")
    g = GUID()
    g.Data1 = int(p[0], 16)
    g.Data2 = int(p[1], 16)
    g.Data3 = int(p[2], 16)
    tail = p[3] + p[4]
    for i in range(8):
        g.Data4[i] = int(tail[i * 2:i * 2 + 2], 16)
    return g


class RECT(Structure):
    _fields_ = [("left", c_long), ("top", c_long), ("right", c_long), ("bottom", c_long)]


class POINT(Structure):
    _fields_ = [("x", c_long), ("y", c_long)]


class DXGI_RATIONAL(Structure):
    _fields_ = [("Numerator", c_uint), ("Denominator", c_uint)]


class DXGI_MODE_DESC(Structure):
    _fields_ = [
        ("Width", c_uint), ("Height", c_uint), ("RefreshRate", DXGI_RATIONAL),
        ("Format", c_uint), ("ScanlineOrdering", c_uint), ("Scaling", c_uint),
    ]


class DXGI_OUTPUT_DESC(Structure):
    _fields_ = [
        ("DeviceName", c_wchar * 32),
        ("DesktopCoordinates", RECT),
        ("AttachedToDesktop", c_int),
        ("Rotation", c_uint),
        ("Monitor", c_void_p),
    ]


class DXGI_OUTDUPL_DESC(Structure):
    _fields_ = [
        ("ModeDesc", DXGI_MODE_DESC),
        ("Rotation", c_uint),
        ("DesktopImageInSystemMemory", c_int),
    ]


class DXGI_OUTDUPL_POINTER_POSITION(Structure):
    _fields_ = [("Position", POINT), ("Visible", c_int)]


class DXGI_OUTDUPL_FRAME_INFO(Structure):
    _fields_ = [
        ("LastPresentTime", ctypes.c_longlong),
        ("LastMouseUpdateTime", ctypes.c_longlong),
        ("AccumulatedFrames", c_uint),
        ("RectsCoalesced", c_int),
        ("ProtectedContentMaskedOut", c_int),
        ("PointerPosition", DXGI_OUTDUPL_POINTER_POSITION),
        ("TotalMetadataBufferSize", c_uint),
        ("PointerShapeBufferSize", c_uint),
    ]


class DXGI_SAMPLE_DESC(Structure):
    _fields_ = [("Count", c_uint), ("Quality", c_uint)]


class D3D11_TEXTURE2D_DESC(Structure):
    _fields_ = [
        ("Width", c_uint), ("Height", c_uint), ("MipLevels", c_uint),
        ("ArraySize", c_uint), ("Format", c_uint), ("SampleDesc", DXGI_SAMPLE_DESC),
        ("Usage", c_uint), ("BindFlags", c_uint), ("CPUAccessFlags", c_uint),
        ("MiscFlags", c_uint),
    ]


class D3D11_MAPPED_SUBRESOURCE(Structure):
    _fields_ = [("pData", c_void_p), ("RowPitch", c_uint), ("DepthPitch", c_uint)]


class D3D11_SUBRESOURCE_DATA(Structure):
    _fields_ = [("pSysMem", c_void_p), ("SysMemPitch", c_uint), ("SysMemSlicePitch", c_uint)]


# ── 函数原型缓存 ──────────────────────────────────────────────
_proto_cache = {}
_proto_lock = threading.Lock()


def _proto(restype, argtypes):
    key = (restype, argtypes)
    fn = _proto_cache.get(key)
    if fn is None:
        fn = WINFUNCTYPE(restype, c_void_p, *argtypes)
        with _proto_lock:
            _proto_cache[key] = fn
    return fn


class ComPtr:
    """极简 COM 接口指针：按虚表下标直接调用，避免 type library 依赖。"""

    __slots__ = ("ptr", "_name")

    def __init__(self, ptr, name=""):
        self.ptr = int(ptr or 0)
        self._name = name

    def __bool__(self):
        return bool(self.ptr)

    def call(self, index, restype, argtypes, args=()):
        if not self.ptr:
            raise RuntimeError("{}: 空接口指针".format(self._name or "ComPtr"))
        obj = cast(c_void_p(self.ptr), POINTER(POINTER(c_void_p)))
        vtbl = obj.contents                     # 指向虚表首地址
        method_addr = vtbl[index]               # 第 index 个函数指针
        fn = _proto(restype, tuple(argtypes))(method_addr)
        return fn(self.ptr, *args)

    def query_interface(self, iid_str, name=""):
        iid = _guid(iid_str)
        out = c_void_p()
        hr = self.call(VT_QUERYINTERFACE, c_long,
                       [POINTER(GUID), POINTER(c_void_p)],
                       (byref(iid), byref(out)))
        if hr != S_OK or not out.value:
            return None
        return ComPtr(out.value, name or iid_str)

    def release(self):
        ptr, self.ptr = self.ptr, 0
        if not ptr:
            return
        try:
            obj = cast(c_void_p(ptr), POINTER(POINTER(c_void_p)))
            vtbl = obj.contents
            fn = _proto(c_ulong, ())(vtbl[VT_RELEASE])
            fn(ptr)
        except Exception:
            pass


def _hr(hr):
    """把 HRESULT 归一成 Python int（comtypes 返回有符号，ctypes 也是）。"""
    return int(hr) & 0xFFFFFFFF


def _hr_name(hr):
    names = {
        S_OK: "S_OK",
        DXGI_ERROR_WAIT_TIMEOUT: "DXGI_ERROR_WAIT_TIMEOUT",
        DXGI_ERROR_ACCESS_LOST: "DXGI_ERROR_ACCESS_LOST",
        DXGI_ERROR_NOT_FOUND: "DXGI_ERROR_NOT_FOUND",
        DXGI_ERROR_UNSUPPORTED: "DXGI_ERROR_UNSUPPORTED",
        DXGI_ERROR_NOT_CURRENTLY_AVAILABLE: "DXGI_ERROR_NOT_CURRENTLY_AVAILABLE",
        DXGI_ERROR_SESSION_DISCONNECTED: "DXGI_ERROR_SESSION_DISCONNECTED",
        DXGI_ERROR_INVALID_CALL: "DXGI_ERROR_INVALID_CALL",
        DXGI_ERROR_WAS_STILL_DRAWING: "DXGI_ERROR_WAS_STILL_DRAWING",
        D3DERR_INVALIDCALL: "D3DERR_INVALIDCALL",
    }
    return names.get(_hr(hr), "0x{:08X}".format(_hr(hr)))


def is_available() -> bool:
    """本机是否具备原生 Desktop Duplication 的前提（能加载 dxgi.dll / d3d11.dll）。"""
    if not _IS_WINDOWS:
        return False
    try:
        ctypes.WinDLL("dxgi")
        ctypes.WinDLL("d3d11")
        return True
    except Exception:
        return False


def _selftest_pipeline(device, context) -> bool:
    """自检：D3D11 的「建纹理 → CopyResource → Map 读回」通路是否真的可用。

    为什么必须自检：部分机器的 D3D11 运行时/驱动处于受限或异常状态时，
    DuplicateOutput 能成功、AcquireNextFrame 也能返回 S_OK，但复制出来的
    暂存纹理**恒为全零**（表现为画面全黑）。此时若静默启用，所有检测节点都会
    看到"全黑画面"，比回退 BitBlt 更糟。这里用一张已知图案的小纹理实测整条
    通路，只有内容能正确搬回来才认为原生 DXGI 值得启用。
    """
    W, H, FMT = 16, 8, DXGI_FORMAT_B8G8R8A8_UNORM
    try:
        # 图案：左上红、右上绿、左下蓝、右下白（BGR）
        pat = np.zeros((H, W, 4), dtype=np.uint8)
        pat[:H // 2, :W // 2] = (0, 0, 255, 255)
        pat[:H // 2, W // 2:] = (0, 255, 0, 255)
        pat[H // 2:, :W // 2] = (255, 0, 0, 255)
        pat[H // 2:, W // 2:] = (255, 255, 255, 255)
        raw = pat.tobytes()
        buf = (c_ubyte * len(raw))(*raw)          # 必须持有，避免悬空指针

        sub = D3D11_SUBRESOURCE_DATA()
        sub.pSysMem = cast(buf, c_void_p)
        sub.SysMemPitch = W * 4
        sub.SysMemSlicePitch = W * 4 * H

        def _desc(usage, bind, cpu):
            d = D3D11_TEXTURE2D_DESC()
            d.Width, d.Height, d.MipLevels, d.ArraySize = W, H, 1, 1
            d.Format = FMT
            d.SampleDesc.Count, d.SampleDesc.Quality = 1, 0
            d.Usage, d.BindFlags, d.CPUAccessFlags, d.MiscFlags = usage, bind, cpu, 0
            return d

        # 源：DEFAULT(0) + SHADER_RESOURCE(8) + 初始图案
        texA = c_void_p()
        hr = _hr(device.call(VT_DEVICE_CREATE_TEXTURE2D, c_long,
                             [POINTER(D3D11_TEXTURE2D_DESC), POINTER(D3D11_SUBRESOURCE_DATA),
                              POINTER(c_void_p)],
                             (byref(_desc(D3D11_USAGE_DEFAULT, D3D11_BIND_SHADER_RESOURCE, 0)),
                              byref(sub), byref(texA))))
        if hr != S_OK or not texA.value:
            _logger.warning("[DXGI-native] 自检失败: 无法创建基准纹理 (%s)", _hr_name(hr))
            return False

        # 目标：STAGING(3) + CPU_ACCESS_READ
        texB = c_void_p()
        hr = _hr(device.call(VT_DEVICE_CREATE_TEXTURE2D, c_long,
                             [POINTER(D3D11_TEXTURE2D_DESC), c_void_p, POINTER(c_void_p)],
                             (byref(_desc(D3D11_USAGE_STAGING, 0, D3D11_CPU_ACCESS_READ)),
                              None, byref(texB))))
        if hr != S_OK or not texB.value:
            _logger.warning("[DXGI-native] 自检失败: 无法创建暂存纹理 (%s)", _hr_name(hr))
            ComPtr(texA.value).release()
            return False

        ok = False
        try:
            context.call(VT_CONTEXT_COPY_RESOURCE, None, [c_void_p, c_void_p],
                         (texB.value, texA.value))
            mapped = D3D11_MAPPED_SUBRESOURCE()
            hr = _hr(context.call(VT_CONTEXT_MAP, c_long,
                                  [c_void_p, c_uint, c_uint, c_uint,
                                   POINTER(D3D11_MAPPED_SUBRESOURCE)],
                                  (texB.value, 0, D3D11_MAP_READ, 0, byref(mapped))))
            if hr == S_OK and mapped.pData:
                pitch = int(mapped.RowPitch)
                row = (c_ubyte * (pitch * H)).from_address(mapped.pData)
                img = np.frombuffer(row, dtype=np.uint8).reshape((H, pitch))[:, :W * 4]
                img = img.reshape((H, W, 4))
                tl = tuple(int(v) for v in img[1, 1][:3])
                br = tuple(int(v) for v in img[H - 2, W - 2][:3])
                ok = (tl == (0, 0, 255) and br == (255, 255, 255))
                if not ok:
                    _logger.warning(
                        "[DXGI-native] 自检失败: 复制后的内容不正确 "
                        "(左上=%s 右下=%s，期望 (0,0,255)/(255,255,255))", tl, br)
                try:
                    context.call(VT_CONTEXT_UNMAP, None, [c_void_p, c_uint], (texB.value, 0))
                except Exception:
                    pass
            else:
                _logger.warning("[DXGI-native] 自检失败: Map 暂存纹理失败 (%s)", _hr_name(hr))
        finally:
            ComPtr(texB.value).release()
            ComPtr(texA.value).release()
        return ok
    except Exception as e:
        _logger.warning("[DXGI-native] 自检异常: %s", e)
        return False


class DesktopDuplicator:
    """原生 DXGI Desktop Duplication 采集器（全屏帧）。"""

    def __init__(self):
        self._factory = None
        self._adapter = None
        self._output = None
        self._output1 = None
        self._duplication = None
        self._device = None
        self._context = None
        self._staging = None
        self._staging_key = None
        self._width = 0
        self._height = 0
        self._origin_x = 0
        self._origin_y = 0
        self._initialized = False
        self._access_lost = False
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3
        self._lock = threading.Lock()

    # ---------------- 属性 ----------------
    @property
    def initialized(self):
        return self._initialized

    @property
    def needs_reinit(self):
        return self._access_lost

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    def get_output_origin(self):
        return self._origin_x, self._origin_y

    # ---------------- 初始化 ----------------
    def initialize(self, adapter_idx=0, output_idx=0) -> bool:
        self.release()
        if not _IS_WINDOWS:
            return False

        try:
            dxgi = ctypes.WinDLL("dxgi")
            d3d11 = ctypes.WinDLL("d3d11")
        except Exception as e:
            _logger.warning("[DXGI-native] 无法加载 dxgi/d3d11 库: %s", e)
            return False

        try:
            # 1) 工厂 → 适配器 → 输出
            factory = self._create_factory1(dxgi)
            if not factory:
                return False
            adapter = self._enum_adapter1(factory, adapter_idx)
            if not adapter:
                _logger.warning("[DXGI-native] 适配器 %d 不存在", adapter_idx)
                return False
            output = self._enum_output(adapter, output_idx)
            if not output:
                _logger.warning("[DXGI-native] 适配器 %d 上无输出 %d", adapter_idx, output_idx)
                return False

            desc = DXGI_OUTPUT_DESC()
            hr = output.call(VT_OUTPUT_GET_DESC, c_long, [POINTER(DXGI_OUTPUT_DESC)],
                             (byref(desc),))
            if _hr(hr) != S_OK:
                _logger.warning("[DXGI-native] GetDesc 失败: %s", _hr_name(hr))
                return False
            self._origin_x = int(desc.DesktopCoordinates.left)
            self._origin_y = int(desc.DesktopCoordinates.top)
            self._width = int(desc.DesktopCoordinates.right - desc.DesktopCoordinates.left)
            self._height = int(desc.DesktopCoordinates.bottom - desc.DesktopCoordinates.top)
            # DXGI_MODE_ROTATION: 0=UNSPECIFIED, 1=IDENTITY, 2=ROTATE90, 3=ROTATE180, 4=ROTATE270
            if desc.Rotation not in (0, 1):
                _logger.warning("[DXGI-native] 输出旋转 = %d，帧内容不是正向", desc.Rotation)

            # 2) D3D11 设备 —— 必须建在「拥有该输出的同一块适配器」上。
            #    若用 D3D11CreateDevice(pAdapter=NULL, HARDWARE)，Windows 会挑默认适配器，
            #    在混合显卡（核显 + 独显）机器上未必等于枚举到的这块；
            #    DuplicateOutput 仍可能返回成功，但之后 AcquireNextFrame 永远超时（拿不到帧）。
            #    传 pAdapter 时 DriverType 必须为 D3D_DRIVER_TYPE_UNKNOWN。
            device, context = self._create_d3d11_device(d3d11, adapter)
            if not device or not context:
                return False

            # 3) IDXGIOutput1 → DuplicateOutput
            output1 = output.query_interface(IID_IDXGIOutput1, "IDXGIOutput1")
            if not output1:
                _logger.warning("[DXGI-native] QI(IDXGIOutput1) 失败")
                return False
            dup = c_void_p()
            hr = output1.call(VT_OUTPUT1_DUPLICATE_OUTPUT, c_long,
                              [c_void_p, POINTER(c_void_p)],
                              (device.ptr, byref(dup)))
            hr = _hr(hr)
            if hr != S_OK or not dup.value:
                _logger.warning(
                    "[DXGI-native] DuplicateOutput 失败: %s%s",
                    _hr_name(hr),
                    "（同屏已有其它程序占用复制会话）"
                    if hr == DXGI_ERROR_NOT_CURRENTLY_AVAILABLE else "")
                self._release_partial()
                return False
            duplication = ComPtr(dup.value, "IDXGIOutputDuplication")

            self._factory = factory
            self._adapter = adapter
            self._output = output
            self._output1 = output1
            self._duplication = duplication
            self._device = device
            self._context = context
            self._initialized = True
            self._access_lost = False
            self._consecutive_failures = 0

            # 4) 自检 D3D11 的「复制 → Map 读回」通路。
            #    某些机器的运行时/驱动状态下，DuplicateOutput 与 AcquireNextFrame 都返回
            #    S_OK，但复制出来的帧恒为全零（画面全黑）。那种情况下启用原生 DXGI 会让
            #    所有检测节点看到"全黑画面"，比回退 BitBlt 更糟，所以这里实测一次，
            #    不通过就放弃原生路径。
            if not _selftest_pipeline(self._device, self._context):
                _logger.warning("[DXGI-native] 复制/读回通路自检未通过 → 放弃原生 DXGI，改用 BitBlt")
                self.release()
                return False
            _logger.info("[DXGI-native] 自检通过，Desktop Duplication 就绪 output=%d %dx%d @(%d,%d)",
                         output_idx, self._width, self._height, self._origin_x, self._origin_y)
            return True
        except Exception as e:
            _logger.warning("[DXGI-native] 初始化异常: %s", e, exc_info=True)
            self.release()
            return False

    @staticmethod
    def _create_factory1(dxgi):
        try:
            create = dxgi.CreateDXGIFactory1
            create.restype = c_long
            create.argtypes = [POINTER(GUID), POINTER(c_void_p)]
        except Exception as e:
            _logger.warning("[DXGI-native] 取不到 CreateDXGIFactory1: %s", e)
            return None
        iid = _guid(CLSID_IDXGIFactory1)
        out = c_void_p()
        hr = _hr(create(byref(iid), byref(out)))
        if hr != S_OK or not out.value:
            _logger.warning("[DXGI-native] CreateDXGIFactory1 失败: %s", _hr_name(hr))
            return None
        return ComPtr(out.value, "IDXGIFactory1")

    @staticmethod
    def _enum_adapter1(factory, adapter_idx):
        out = c_void_p()
        hr = factory.call(VT_ENUM_ADAPTERS1, c_long,
                          [c_uint, POINTER(c_void_p)],
                          (adapter_idx, byref(out)))
        if _hr(hr) != S_OK or not out.value:
            return None
        return ComPtr(out.value, "IDXGIAdapter1")

    @staticmethod
    def _enum_output(adapter, output_idx):
        out = c_void_p()
        hr = adapter.call(VT_ADAPTER_ENUM_OUTPUTS, c_long,
                          [c_uint, POINTER(c_void_p)],
                          (output_idx, byref(out)))
        if _hr(hr) != S_OK or not out.value:
            return None
        return ComPtr(out.value, "IDXGIOutput")

    @staticmethod
    def _create_d3d11_device(d3d11, adapter=None):
        try:
            fn = d3d11.D3D11CreateDevice
            fn.restype = c_long
            fn.argtypes = [
                c_void_p, c_uint, c_void_p, c_uint,
                POINTER(c_uint), c_uint, c_uint,
                POINTER(c_void_p), POINTER(c_uint), POINTER(c_void_p),
            ]
        except Exception as e:
            _logger.warning("[DXGI-native] 取不到 D3D11CreateDevice: %s", e)
            return None, None

        device = c_void_p()
        context = c_void_p()
        feature_level = c_uint()

        # 指定适配器时必须用 D3D_DRIVER_TYPE_UNKNOWN
        p_adapter = adapter.ptr if adapter else None
        driver_type = D3D_DRIVER_TYPE_UNKNOWN if p_adapter else D3D_DRIVER_TYPE_HARDWARE

        hr = _hr(fn(
            p_adapter,
            driver_type,
            None,
            D3D11_CREATE_DEVICE_BGRA_SUPPORT,
            None, 0,
            D3D11_SDK_VERSION,
            byref(device), byref(feature_level), byref(context),
        ))
        if hr != S_OK or not device.value:
            # 指定适配器失败时退回默认适配器，尽量不放弃
            if p_adapter:
                _logger.info("[DXGI-native] 指定适配器建设备失败(%s)，改用默认适配器重试",
                             _hr_name(hr))
                hr = _hr(fn(
                    None, D3D_DRIVER_TYPE_HARDWARE, None,
                    D3D11_CREATE_DEVICE_BGRA_SUPPORT, None, 0, D3D11_SDK_VERSION,
                    byref(device), byref(feature_level), byref(context),
                ))
        if hr != S_OK or not device.value:
            _logger.warning("[DXGI-native] D3D11CreateDevice 失败: %s", _hr_name(hr))
            return None, None
        return ComPtr(device.value, "ID3D11Device"), ComPtr(context.value, "ID3D11DeviceContext")

    # ---------------- 暂存纹理 ----------------
    def _ensure_staging(self, width, height, fmt):
        key = (width, height, fmt)
        if self._staging is not None and self._staging_key == key:
            return True
        if self._staging is not None:
            self._staging.release()
            self._staging = None
            self._staging_key = None

        desc = D3D11_TEXTURE2D_DESC()
        desc.Width = width
        desc.Height = height
        desc.MipLevels = 1
        desc.ArraySize = 1
        desc.Format = fmt
        desc.SampleDesc.Count = 1
        desc.SampleDesc.Quality = 0
        desc.Usage = D3D11_USAGE_STAGING
        desc.BindFlags = 0
        desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ
        desc.MiscFlags = 0

        tex = c_void_p()
        hr = self._device.call(VT_DEVICE_CREATE_TEXTURE2D, c_long,
                               [POINTER(D3D11_TEXTURE2D_DESC), c_void_p, POINTER(c_void_p)],
                               (byref(desc), None, byref(tex)))
        hr = _hr(hr)
        if hr != S_OK or not tex.value:
            _logger.warning("[DXGI-native] CreateTexture2D(staging) 失败: %s", _hr_name(hr))
            return False
        self._staging = ComPtr(tex.value, "ID3D11Texture2D(staging)")
        self._staging_key = key
        return True

    # ---------------- 取帧 ----------------
    def acquire_frame(self, timeout_ms=100):
        """取一帧全屏 BGR 图；失败返回 None（需重建时 self.needs_reinit 为 True）。"""
        if not self._initialized:
            return None
        with self._lock:
            if not self._initialized:
                return None
            try:
                return self._acquire_locked(timeout_ms)
            except Exception as e:
                _logger.warning("[DXGI-native] 取帧异常: %s", e)
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._max_consecutive_failures:
                    self._access_lost = True
                return None

    def _acquire_locked(self, timeout_ms):
        frame_info = DXGI_OUTDUPL_FRAME_INFO()
        resource = c_void_p()
        hr = self._duplication.call(
            VT_DUPL_ACQUIRE_NEXT_FRAME, c_long,
            [c_uint, POINTER(DXGI_OUTDUPL_FRAME_INFO), POINTER(c_void_p)],
            (c_uint(int(timeout_ms)), byref(frame_info), byref(resource)))
        hr = _hr(hr)
        if hr != S_OK:
            if hr in (DXGI_ERROR_WAIT_TIMEOUT,):
                return None
            if hr in (DXGI_ERROR_ACCESS_LOST, DXGI_ERROR_SESSION_DISCONNECTED,
                      DXGI_ERROR_INVALID_CALL):
                # 分辨率切换 / 全屏独占切换 / 会话断开 → 复制会话失效，必须重建
                self._consecutive_failures += 1
                if hr == DXGI_ERROR_ACCESS_LOST or self._consecutive_failures >= 1:
                    self._access_lost = True
                _logger.info("[DXGI-native] 复制会话失效(%s)，请求重建", _hr_name(hr))
            return None

        self._consecutive_failures = 0
        res_ptr = ComPtr(resource.value, "IDXGIResource")
        surface = None
        try:
            if frame_info.ProtectedContentMaskedOut:
                _logger.debug("[DXGI-native] 当前帧含受保护内容，可能为黑帧")

            surface = res_ptr.query_interface(IID_ID3D11Texture2D, "ID3D11Texture2D")
            if not surface:
                return None

            desc = D3D11_TEXTURE2D_DESC()
            surface.call(VT_TEXTURE2D_GET_DESC, None,
                         [POINTER(D3D11_TEXTURE2D_DESC)], (byref(desc),))
            if desc.Width == 0 or desc.Height == 0:
                return None

            if not self._ensure_staging(desc.Width, desc.Height, desc.Format):
                return None

            self._context.call(VT_CONTEXT_COPY_RESOURCE, None,
                               [c_void_p, c_void_p],
                               (self._staging.ptr, surface.ptr))

            mapped = D3D11_MAPPED_SUBRESOURCE()
            hr = self._context.call(VT_CONTEXT_MAP, c_long,
                                    [c_void_p, c_uint, c_uint, c_uint,
                                     POINTER(D3D11_MAPPED_SUBRESOURCE)],
                                    (self._staging.ptr, 0, D3D11_MAP_READ, 0, byref(mapped)))
            hr = _hr(hr)
            if hr != S_OK or not mapped.pData:
                _logger.debug("[DXGI-native] Map 失败: %s", _hr_name(hr))
                self._consecutive_failures += 1
                return None

            try:
                width = int(desc.Width)
                height = int(desc.Height)
                row_pitch = int(mapped.RowPitch)
                buf = (c_ubyte * (row_pitch * height)).from_address(mapped.pData)
                frame = np.frombuffer(buf, dtype=np.uint8).reshape((height, row_pitch))
                frame = frame[:, :width * 4].copy().reshape((height, width, 4))
                if desc.Format in (DXGI_FORMAT_B8G8R8A8_UNORM,
                                   DXGI_FORMAT_B8G8R8A8_UNORM_SRGB):
                    return frame[:, :, :3].copy()      # BGRA → BGR
                # 其它格式（少见）：按 BGRA 兜底，至少不崩
                return frame[:, :, :3].copy()
            finally:
                self._context.call(VT_CONTEXT_UNMAP, None, [c_void_p, c_uint],
                                   (self._staging.ptr, 0))
        finally:
            if surface:
                surface.release()
            res_ptr.release()
            try:
                self._duplication.call(VT_DUPL_RELEASE_FRAME, c_long, [])
            except Exception:
                pass

    # ---------------- 释放 ----------------
    def _release_partial(self):
        for attr in ("_output1", "_duplication", "_device", "_context",
                     "_staging", "_output", "_adapter", "_factory"):
            obj = getattr(self, attr, None)
            if obj is not None:
                try:
                    obj.release()
                except Exception:
                    pass
                setattr(self, attr, None)
        self._staging_key = None

    def release(self):
        with self._lock:
            self._release_partial()
            self._initialized = False
            self._access_lost = False
            self._consecutive_failures = 0


def _selftest(output_idx=0):
    import time
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("is_available =", is_available())
    d = DesktopDuplicator()
    if not d.initialize(output_idx=output_idx):
        print("初始化失败")
        return 1
    print("输出尺寸 = %dx%d, 原点 = %s" % (d.width, d.height, d.get_output_origin()))
    ok = none = 0
    sigs = set()
    t0 = time.time()
    for _ in range(60):
        f = d.acquire_frame(timeout_ms=100)
        if f is None:
            none += 1
        else:
            ok += 1
            sigs.add((int(f.shape[0]), int(f.shape[1]), round(float(f.mean()), 2)))
            if ok == 1:
                print("首帧 shape =", f.shape, " dtype =", f.dtype)
        time.sleep(0.01)
        if d.needs_reinit:
            print("需要重建")
            break
    print("成功 %d / None %d, 用时 %.2fs, 不同帧签名 %d" % (ok, none, time.time() - t0, len(sigs)))
    d.release()
    print("已释放")
    return 0 if ok else 2


if __name__ == "__main__":
    import sys
    sys.exit(_selftest(int(sys.argv[1]) if len(sys.argv) > 1 else 0))
