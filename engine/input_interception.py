# interception_input.py
"""
Interception 驱动高精度输入模块。

说明：
1. 需先安装 Interception 驱动（管理员运行 install-interception.exe /install）。
2. 安装后需重启系统，驱动才会生效。
3. 本文件直接调用官方 interception.dll（无需 pip interception 包）。
"""
import ctypes
import os
import threading
import time

# 左键抗吞策略：
# 左键动作先发首选设备，再额外发给少量候选设备（可配数量）。
INTERCEPTION_MOUSE_LEFT_DOWN_LIMITED = True # 鼠标按下限制 True: 限制冗余数量；False: 按下时广播到所有检测到的鼠标设备
INTERCEPTION_MOUSE_LEFT_REDUNDANT_DOWN_DEVICES = 1
INTERCEPTION_MOUSE_LEFT_UP_LIMITED_RELEASE = True  # 是否启用鼠标抬起的冗余设备限制（True: 限制数量，False: 全设备）
INTERCEPTION_MOUSE_LEFT_REDUNDANT_UP_DEVICES = 2

INTERCEPTION_KEYBOARD_REDUNDANT_DEVICES = 1  #
INTERCEPTION_KEYBOARD_SCAN_INTERVAL = 1.0

# 默认仅做注入，不拦截物理输入，避免外接键鼠失效。
INTERCEPTION_CAPTURE_PHYSICAL_INPUT = False
# -- Interception API 常量（与 interception.h 对齐） --
INTERCEPTION_MAX_KEYBOARD = 10
INTERCEPTION_MAX_MOUSE = 10
INTERCEPTION_MAX_DEVICE = INTERCEPTION_MAX_KEYBOARD + INTERCEPTION_MAX_MOUSE

# 键盘设备编号从 1 开始：INTERCEPTION_KEYBOARD(i) = i + 1
INTERCEPTION_KEYBOARD_START = 1
INTERCEPTION_KEYBOARD_END = INTERCEPTION_MAX_KEYBOARD

# InterceptionKeyState
INTERCEPTION_KEY_DOWN = 0x00
INTERCEPTION_KEY_UP = 0x01
INTERCEPTION_KEY_E0 = 0x02

# InterceptionFilterKeyState
INTERCEPTION_FILTER_KEY_NONE = 0x0000
INTERCEPTION_FILTER_KEY_ALL = 0xFFFF

# InterceptionMouseState / InterceptionFilterMouseState
INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN = 0x001
INTERCEPTION_MOUSE_LEFT_BUTTON_UP = 0x002
INTERCEPTION_MOUSE_RIGHT_BUTTON_DOWN = 0x004
INTERCEPTION_MOUSE_RIGHT_BUTTON_UP = 0x008
INTERCEPTION_FILTER_MOUSE_NONE = 0x0000
INTERCEPTION_FILTER_MOUSE_ALL = 0xFFFF

# 鼠标设备编号：INTERCEPTION_MOUSE(i) = 10 + i + 1 -> 11..20
INTERCEPTION_MOUSE_START = INTERCEPTION_MAX_KEYBOARD + 1
INTERCEPTION_MOUSE_END = INTERCEPTION_MAX_DEVICE



# 键盘扫描码映射（需要用 Scan Code 而非 Virtual Key）
SC_MAP = {
    "a": 0x1E, "b": 0x30, "c": 0x2E, "d": 0x20, "e": 0x12,
    "f": 0x21, "g": 0x22, "h": 0x23, "i": 0x17, "j": 0x24,
    "k": 0x25, "l": 0x26, "m": 0x32, "n": 0x31, "o": 0x18,
    "p": 0x19, "q": 0x10, "r": 0x13, "s": 0x1F, "t": 0x14,
    "u": 0x16, "v": 0x2F, "w": 0x11, "x": 0x2D, "y": 0x15,
    "z": 0x2C,
    "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
    "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B,
    "enter": 0x1C, "esc": 0x01, "space": 0x39, "tab": 0x0F,
    "shift": 0x2A, "ctrl": 0x1D, "alt": 0x38,
    "caps_lock": 0x3A, "back": 0x0E, "delete": 0x53,
    "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f4": 0x3E,
    "f5": 0x3F, "f6": 0x40, "f7": 0x41, "f8": 0x42,
    "f9": 0x43, "f10": 0x44, "f11": 0x57, "f12": 0x58,
    "up_arrow": 0x48, "down_arrow": 0x50,
    "left_arrow": 0x4B, "right_arrow": 0x4D,
}

# 扩展键标志（右Shift、右Ctrl、右Alt、Enter、方向键等）
EXTENDED_KEYS = {
    "right_arrow", "down_arrow", "left_arrow", "up_arrow",
    "right_ctrl", "right_alt", "right_shift",
    "insert", "delete", "home", "end", "page_up", "page_down",
    "numpad_enter",
}


class InterceptionKeyStroke(ctypes.Structure):
    """与 interception.h 的 InterceptionKeyStroke 对齐。"""

    _fields_ = [
        ("code", ctypes.c_ushort),
        ("state", ctypes.c_ushort),
        ("information", ctypes.c_uint),
    ]


class InterceptionMouseStroke(ctypes.Structure):
    """用于计算 InterceptionStroke 的最小缓冲区大小。"""

    _fields_ = [
        ("state", ctypes.c_ushort),
        ("flags", ctypes.c_ushort),
        ("rolling", ctypes.c_short),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("information", ctypes.c_uint),
    ]


InterceptionStroke = ctypes.c_ubyte * ctypes.sizeof(InterceptionMouseStroke)


def _resolve_dll_path():
    """优先从工作区自带目录解析 interception.dll。"""
    module_dir = os.path.dirname(os.path.abspath(__file__))
    arch_dir = "x64" if ctypes.sizeof(ctypes.c_void_p) == 8 else "x86"

    candidates = [
        os.environ.get("INTERCEPTION_DLL"),
        os.path.join(module_dir, "interception.dll"),
        os.path.join(module_dir, "Interception", "library", arch_dir, "interception.dll"),
    ]

    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def _load_interception_dll():
    """加载 DLL：优先绝对路径，最后尝试系统 PATH。"""
    dll_path = _resolve_dll_path()
    if dll_path:
        return ctypes.WinDLL(dll_path)

    # 最后回退系统路径（若用户手动放到了 System32/PATH）
    return ctypes.WinDLL("interception.dll")


class InterceptionContext:
    """Interception 驱动上下文管理器"""

    def __init__(self):
        try:
            self._lib = _load_interception_dll()
        except OSError:
            raise RuntimeError(
                "无法加载 interception.dll。\n"
                "请确认以下路径存在并与 Python 位数匹配：\n"
                "Interception/library/x64/interception.dll（64位）或 x86（32位）"
            )

        # 绑定官方导出函数（interception_ 前缀）
        self._lib.interception_create_context.restype = ctypes.c_void_p
        self._lib.interception_create_context.argtypes = []

        self._lib.interception_destroy_context.argtypes = [ctypes.c_void_p]

        self._lib.interception_set_filter.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_ushort,
        ]

        self._lib.interception_send.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.POINTER(InterceptionStroke),
            ctypes.c_uint,
        ]
        self._lib.interception_send.restype = ctypes.c_int

        self._lib.interception_is_keyboard.argtypes = [ctypes.c_int]
        self._lib.interception_is_keyboard.restype = ctypes.c_int

        self._lib.interception_is_mouse.argtypes = [ctypes.c_int]
        self._lib.interception_is_mouse.restype = ctypes.c_int

        self._context = self._lib.interception_create_context()
        if not self._context:
            raise RuntimeError("无法创建 Interception 上下文")

        # 绑定谓词回调：int predicate(int device)
        self._predicate_keyboard = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int)(
            self._lib.interception_is_keyboard
        )

        keyboard_filter = (
            INTERCEPTION_FILTER_KEY_ALL
            if INTERCEPTION_CAPTURE_PHYSICAL_INPUT
            else INTERCEPTION_FILTER_KEY_NONE
        )
        self._lib.interception_set_filter(
            self._context,
            self._predicate_keyboard,
            keyboard_filter,
        )

        self._predicate_mouse = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int)(
            self._lib.interception_is_mouse
        )
        mouse_filter = (
            INTERCEPTION_FILTER_MOUSE_ALL
            if INTERCEPTION_CAPTURE_PHYSICAL_INPUT
            else INTERCEPTION_FILTER_MOUSE_NONE
        )
        self._lib.interception_set_filter(
            self._context,
            self._predicate_mouse,
            mouse_filter,
        )

        self._keyboard_devices = []
        for dev in range(INTERCEPTION_KEYBOARD_START, INTERCEPTION_KEYBOARD_END + 1):
            if self._lib.interception_is_keyboard(dev):
                self._keyboard_devices.append(dev)

        self._device = self._keyboard_devices[0] if self._keyboard_devices else -1
        if self._device < 0:
            raise RuntimeError("没有可用的 Interception 键盘设备")
        self._preferred_keyboard_device = self._device
        self._keyboard_lock = threading.Lock()
        self._last_keyboard_scan_time = time.perf_counter()
        self._keyboard_scan_interval = INTERCEPTION_KEYBOARD_SCAN_INTERVAL

        self._mouse_devices = []
        for dev in range(INTERCEPTION_MOUSE_START, INTERCEPTION_MOUSE_END + 1):
            if self._lib.interception_is_mouse(dev):
                self._mouse_devices.append(dev)

        self._mouse_device = self._mouse_devices[0] if self._mouse_devices else -1
        self._preferred_mouse_device = self._mouse_device
        self._mouse_lock = threading.Lock()
        self._last_mouse_scan_time = time.perf_counter()
        self._mouse_scan_interval = 1.0
        self._last_left_down_devices = []

    @property
    def device(self):
        return self._device

    @property
    def mouse_device(self):
        return self._mouse_device

    def _refresh_mouse_devices(self, force=False):
        """重扫可用鼠标设备，支持动态换机/换鼠标场景。"""
        now = time.perf_counter()
        if (not force) and (now - self._last_mouse_scan_time < self._mouse_scan_interval):
            return

        devices = []
        for dev in range(INTERCEPTION_MOUSE_START, INTERCEPTION_MOUSE_END + 1):
            if self._lib.interception_is_mouse(dev):
                devices.append(dev)

        self._mouse_devices = devices
        self._mouse_device = devices[0] if devices else -1
        if self._preferred_mouse_device not in devices:
            self._preferred_mouse_device = self._mouse_device
        self._last_mouse_scan_time = now

    def _refresh_keyboard_devices(self, force=False):
        """重扫可用键盘设备，支持动态换机/换键盘场景。"""
        now = time.perf_counter()
        if (not force) and (now - self._last_keyboard_scan_time < self._keyboard_scan_interval):
            return

        devices = []
        for dev in range(INTERCEPTION_KEYBOARD_START, INTERCEPTION_KEYBOARD_END + 1):
            if self._lib.interception_is_keyboard(dev):
                devices.append(dev)

        self._keyboard_devices = devices
        self._device = devices[0] if devices else -1
        if self._preferred_keyboard_device not in devices:
            self._preferred_keyboard_device = self._device
        self._last_keyboard_scan_time = now

    def _send_key_stroke_to_device(self, device, raw_stroke):
        """向指定设备发送键盘事件，返回是否成功。"""
        sent = self._lib.interception_send(
            self._context,
            device,
            ctypes.byref(raw_stroke),
            1,
        )
        return sent > 0

    def _send_key_stroke_to_devices(self, devices, raw_stroke):
        """向设备集合发送键盘事件，返回成功设备列表。"""
        ok = []
        for dev in devices:
            if self._send_key_stroke_to_device(dev, raw_stroke):
                ok.append(dev)
        return ok

    def _select_keyboard_fallback_order(self):
        """键盘设备回退顺序（从首选设备后一个开始轮转）。"""
        devices = list(self._keyboard_devices)
        if not devices:
            return []
        pref = self._preferred_keyboard_device
        if pref not in devices:
            return devices
        idx = devices.index(pref)
        return devices[idx + 1:] + devices[:idx]

    def _build_keyboard_targets_with_redundancy(self, primary_device, redundant_count):
        """生成键盘目标设备：主设备 + 冗余设备。"""
        targets = []
        seen = set()

        def _push(dev):
            if dev in self._keyboard_devices and dev not in seen:
                seen.add(dev)
                targets.append(dev)

        _push(primary_device)
        need = max(0, int(redundant_count))
        if need == 0:
            return targets

        for dev in self._select_keyboard_fallback_order():
            if len(targets) >= 1 + need:
                break
            _push(dev)

        return targets

    def _send_mouse_stroke_to_device(self, device, raw_stroke):
        """向指定设备发送鼠标事件，返回是否成功。"""
        sent = self._lib.interception_send(
            self._context,
            device,
            ctypes.byref(raw_stroke),
            1,
        )
        return sent > 0

    def _send_mouse_stroke_to_devices(self, devices, raw_stroke):
        """向设备集合发送鼠标事件，返回成功设备列表。"""
        ok = []
        for dev in devices:
            if self._send_mouse_stroke_to_device(dev, raw_stroke):
                ok.append(dev)
        return ok

    def _append_left_down_device(self, device):
        if device not in self._last_left_down_devices:
            self._last_left_down_devices.append(device)

    def _select_fallback_order(self):
        """构造回退顺序：从首选后一个设备开始轮转，避免总是从头广播。"""
        devices = list(self._mouse_devices)
        if not devices:
            return []
        pref = self._preferred_mouse_device
        if pref not in devices:
            return devices
        idx = devices.index(pref)
        return devices[idx + 1:] + devices[:idx]

    def _build_targets_with_redundancy(self, primary_device, redundant_count, prefer_devices=None):
        """生成目标设备列表：主设备 + 冗余设备（数量可控）。"""
        targets = []
        seen = set()

        def _push(dev):
            if dev in self._mouse_devices and dev not in seen:
                seen.add(dev)
                targets.append(dev)

        _push(primary_device)

        if prefer_devices:
            for dev in prefer_devices:
                _push(dev)

        need = max(0, int(redundant_count))
        if need == 0:
            return targets

        for dev in self._select_fallback_order():
            if len(targets) >= 1 + need:
                break
            _push(dev)

        return targets

    def send_key(self, scan_code, key_state, flags=0):
        """
        发送按键事件到内核输入栈。

        参数:
            scan_code: 键盘扫描码
            key_state: INTERCEPTION_KEY_DOWN(0x00) 或 INTERCEPTION_KEY_UP(0x01)
            flags: 附加状态位（如 INTERCEPTION_KEY_E0）
        """
        key_stroke = InterceptionKeyStroke(
            code=ctypes.c_ushort(scan_code),
            state=ctypes.c_ushort(key_state | flags),
            information=ctypes.c_uint(0),
        )

        raw_stroke = InterceptionStroke()
        ctypes.memmove(
            ctypes.byref(raw_stroke),
            ctypes.byref(key_stroke),
            ctypes.sizeof(InterceptionKeyStroke),
        )

        with self._keyboard_lock:
            self._refresh_keyboard_devices(force=False)
            if not self._keyboard_devices:
                self._refresh_keyboard_devices(force=True)
            if not self._keyboard_devices:
                raise RuntimeError("没有可用的 Interception 键盘设备")

            pref = self._preferred_keyboard_device
            if pref in self._keyboard_devices and self._send_key_stroke_to_device(pref, raw_stroke):
                self._device = pref
                targets = self._build_keyboard_targets_with_redundancy(
                    pref,
                    INTERCEPTION_KEYBOARD_REDUNDANT_DEVICES,
                )
                if len(targets) > 1:
                    self._send_key_stroke_to_devices(targets[1:], raw_stroke)
                return

            for dev in self._select_keyboard_fallback_order():
                if self._send_key_stroke_to_device(dev, raw_stroke):
                    self._preferred_keyboard_device = dev
                    self._device = dev
                    targets = self._build_keyboard_targets_with_redundancy(
                        dev,
                        INTERCEPTION_KEYBOARD_REDUNDANT_DEVICES,
                    )
                    if len(targets) > 1:
                        self._send_key_stroke_to_devices(targets[1:], raw_stroke)
                    return

            self._refresh_keyboard_devices(force=True)
            for dev in self._keyboard_devices:
                if self._send_key_stroke_to_device(dev, raw_stroke):
                    self._preferred_keyboard_device = dev
                    self._device = dev
                    return

            raise RuntimeError("interception_send 键盘发送失败，请确认驱动状态")

    def send_mouse_click(self, left=True, up=False):
        """发送鼠标左右键点击（按下/抬起）。"""
        with self._mouse_lock:
            self._refresh_mouse_devices(force=False)
            if not self._mouse_devices:
                self._refresh_mouse_devices(force=True)
            if not self._mouse_devices:
                raise RuntimeError("没有可用的 Interception 鼠标设备")

            if left:
                state = INTERCEPTION_MOUSE_LEFT_BUTTON_UP if up else INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN
            else:
                state = INTERCEPTION_MOUSE_RIGHT_BUTTON_UP if up else INTERCEPTION_MOUSE_RIGHT_BUTTON_DOWN

            mouse_stroke = InterceptionMouseStroke(
                state=ctypes.c_ushort(state),
                flags=ctypes.c_ushort(0),
                rolling=ctypes.c_short(0),
                x=ctypes.c_int(0),
                y=ctypes.c_int(0),
                information=ctypes.c_uint(0),
            )

            raw_stroke = InterceptionStroke()
            ctypes.memmove(
                ctypes.byref(raw_stroke),
                ctypes.byref(mouse_stroke),
                ctypes.sizeof(InterceptionMouseStroke),
            )

            # 左键抬起：可按独立冗余数量释放，也可切换到全设备释放。
            if left and up:
                if INTERCEPTION_MOUSE_LEFT_UP_LIMITED_RELEASE:
                    up_targets = self._build_targets_with_redundancy(
                        self._preferred_mouse_device,
                        INTERCEPTION_MOUSE_LEFT_REDUNDANT_UP_DEVICES,
                        prefer_devices=self._last_left_down_devices,
                    )
                else:
                    up_targets = list(self._mouse_devices)

                success_devices = self._send_mouse_stroke_to_devices(up_targets, raw_stroke)
                self._last_left_down_devices.clear()
                if success_devices:
                    if self._preferred_mouse_device not in success_devices:
                        self._preferred_mouse_device = success_devices[0]
                    self._mouse_device = self._preferred_mouse_device
                    return

                # 兜底：重扫后再重试
                self._refresh_mouse_devices(force=True)
                retry_targets = list(self._mouse_devices)
                success_devices = self._send_mouse_stroke_to_devices(retry_targets, raw_stroke)
                if success_devices:
                    self._preferred_mouse_device = success_devices[0]
                    self._mouse_device = self._preferred_mouse_device
                    return
                raise RuntimeError("interception_send 鼠标发送失败，请确认驱动已安装并已重启")

            # 快路径：优先命中最近成功设备。
            pref = self._preferred_mouse_device
            if pref in self._mouse_devices and self._send_mouse_stroke_to_device(pref, raw_stroke):
                if left and (not up):
                    self._last_left_down_devices.clear()
                    self._append_left_down_device(pref)
                    if INTERCEPTION_MOUSE_LEFT_DOWN_LIMITED:
                        down_targets = self._build_targets_with_redundancy(
                            pref,
                            INTERCEPTION_MOUSE_LEFT_REDUNDANT_DOWN_DEVICES,
                        )
                    else:
                        down_targets = list(self._mouse_devices)
                    sent_extra = self._send_mouse_stroke_to_devices(down_targets[1:], raw_stroke)
                    for dev in sent_extra:
                        self._append_left_down_device(dev)
                return

            # 回退路径：轮转尝试其余设备，命中即更新首选设备。
            for dev in self._select_fallback_order():
                if self._send_mouse_stroke_to_device(dev, raw_stroke):
                    self._preferred_mouse_device = dev
                    self._mouse_device = dev
                    if left and (not up):
                        self._last_left_down_devices.clear()
                        self._append_left_down_device(dev)
                        if INTERCEPTION_MOUSE_LEFT_DOWN_LIMITED:
                            down_targets = self._build_targets_with_redundancy(
                                dev,
                                INTERCEPTION_MOUSE_LEFT_REDUNDANT_DOWN_DEVICES,
                            )
                        else:
                            down_targets = list(self._mouse_devices)
                        sent_extra = self._send_mouse_stroke_to_devices(down_targets[1:], raw_stroke)
                        for extra_dev in sent_extra:
                            self._append_left_down_device(extra_dev)
                    return

            # 兜底：强制重扫后再尝试一次，处理设备热插拔。
            self._refresh_mouse_devices(force=True)
            for dev in self._mouse_devices:
                if self._send_mouse_stroke_to_device(dev, raw_stroke):
                    self._preferred_mouse_device = dev
                    self._mouse_device = dev
                    if left and (not up):
                        self._last_left_down_devices.clear()
                        self._append_left_down_device(dev)
                        if INTERCEPTION_MOUSE_LEFT_DOWN_LIMITED:
                            down_targets = self._build_targets_with_redundancy(
                                dev,
                                INTERCEPTION_MOUSE_LEFT_REDUNDANT_DOWN_DEVICES,
                            )
                        else:
                            down_targets = list(self._mouse_devices)
                        sent_extra = self._send_mouse_stroke_to_devices(down_targets[1:], raw_stroke)
                        for extra_dev in sent_extra:
                            self._append_left_down_device(extra_dev)
                    return

            raise RuntimeError("interception_send 鼠标发送失败，请确认驱动已安装并已重启")

    def __del__(self):
        if hasattr(self, "_context") and self._context:
            try:
                self._lib.interception_destroy_context(self._context)
            except Exception:
                pass


# -- 全局单例 --
_ctx = None


def get_interception_context():
    """获取全局 Interception 上下文（懒加载）"""
    global _ctx
    if _ctx is None:
        _ctx = InterceptionContext()
        print("[Interception] 驱动已连接，输入精度模式：内核级")
    return _ctx


# -- 兼容原框架的接口 --
def send_key_interception(key_name, up=False):
    """通过 Interception 驱动发送按键（替代 SendInput）"""
    ctx = get_interception_context()

    scan_code = SC_MAP.get(key_name.lower())
    if scan_code is None:
        # 回退到 SendInput
        return False

    state = INTERCEPTION_KEY_UP if up else INTERCEPTION_KEY_DOWN
    flags = INTERCEPTION_KEY_E0 if key_name.lower() in EXTENDED_KEYS else 0

    ctx.send_key(scan_code, state, flags)
    return True


def send_mouse_interception(left=True, up=False):
    """通过 Interception 驱动发送鼠标点击。"""
    ctx = get_interception_context()
    ctx.send_mouse_click(left=left, up=up)
    return True
