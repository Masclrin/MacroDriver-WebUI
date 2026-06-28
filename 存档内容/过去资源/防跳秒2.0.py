#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔═══════════════════════════════════════════════════════════════════╗
║           原神挑战计时优化器  v1.0                                ║
║           Genshin Challenge Timer Optimizer                       ║
║                                                                   ║
║  基于Unity底层分析，利用以下原理优化挑战时间:                        ║
║    - 帧率锁定: 消除高刷显示器导致的帧级时间窃取                      ║
║    - 后台切换: 利用Unity失焦降频延迟客户端初始化                     ║
║    - CPU压力: 缓慢异步场景加载，拉平硬件差异                        ║
║    - 黑屏检测: 精确定位操作时机                                    ║
║                                                                   ║
║  用法:                                                            ║
║    pip install keyboard mss                                       ║
║    以管理员身份运行: python genshin_timer.py                      ║
║    在游戏中点击"开始挑战" → 立即按 F9 触发                        ║
║                                                                   ║
║  前置: RTSS 已安装并配置好帧率限制热键                             ║
╚═══════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import time
import ctypes
import ctypes.wintypes
import threading
import signal
import subprocess
import re
import numpy as np
from dataclasses import dataclass
from multiprocessing import Process, Event as MpEvent
from typing import Optional, List

# ═══════════════════════════════════════════════════════════════
# 0. 环境与工具函数
# ═══════════════════════════════════════════════════════════════

_shutdown = threading.Event()          # 全局取消标志

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
SW_MINIMIZE, SW_RESTORE = 6, 9


def is_admin():
    """检查是否以管理员权限运行 (keyboard全局钩子需要)"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def get_fg_hwnd():
    """获取当前前台窗口句柄"""
    return user32.GetForegroundWindow()


def win_minimize(hwnd):
    """最小化窗口 → Unity 收到 OnApplicationPause(true) + OnApplicationFocus(false)"""
    user32.ShowWindow(hwnd, SW_MINIMIZE)


def win_restore(hwnd):
    """恢复窗口并强制设为前台 (绕过 Windows SetForegroundWindow 限制)"""
    user32.ShowWindow(hwnd, SW_RESTORE)
    _force_fg(hwnd)


def _force_fg(hwnd):
    """
    Windows 安全机制限制: 只有前台进程才能 SetForegroundWindow.
    绕过方法: 用 AttachThreadInput 将当前线程附加到前台窗口线程.
    """
    if user32.SetForegroundWindow(hwnd):
        return True
    try:
        fhwnd = user32.GetForegroundWindow()
        ftid = user32.GetWindowThreadProcessId(fhwnd, None)
        ctid = kernel32.GetCurrentThreadId()
        if ftid != ctid:
            user32.AttachThreadInput(ftid, ctid, True)
            user32.ShowWindow(hwnd, SW_RESTORE)
            time.sleep(0.05)
            r = user32.SetForegroundWindow(hwnd)
            user32.AttachThreadInput(ftid, ctid, False)
            return bool(r)
    except Exception:
        pass
    return False


def beep(freq=1000, ms=100):
    """异步蜂鸣 (不阻塞主流程, 用作阶段提示音)"""
    def _b():
        try:
            import winsound
            winsound.Beep(freq, ms)
        except Exception:
            pass
    threading.Thread(target=_b, daemon=True).start()


def set_priority(level):
    if os.name != "nt":
        return
    try:
        pid = os.getpid()
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if level == "realtime":
            val = 0x00000100
        elif level == "high":
            val = 0x00000080
        elif level == "below_normal":
            val = 0x00004000
        else:
            val = 0x00000020
        ctypes.windll.kernel32.SetPriorityClass(handle, val)
    except:
        pass


def set_cpu_affinity(core_list):
    if not core_list:
        return
    try:
        if os.name == "nt":
            mask = 0
            for core in core_list:
                mask |= 1 << int(core)
            pid = os.getpid()
            handle = ctypes.windll.kernel32.OpenProcess(0x001F0FFF, False, pid)
            success = ctypes.windll.kernel32.SetProcessAffinityMask(handle, mask)
            ctypes.windll.kernel32.CloseHandle(handle)
            if not success:
                print(f"[警告] PID {pid} 绑核失败")
        elif hasattr(os, "sched_setaffinity"):
            os.sched_setaffinity(0, core_list)
    except Exception as e:
        print(f"[错误] 绑核操作异常: {e}")


def get_l3_cache_mb():
    try:
        if os.name != "nt":
            return None
        try:
            cmd = 'wmic path Win32_CacheMemory where "Level=3" get InstalledSize'
            result = subprocess.check_output(cmd, shell=True).decode()
            numbers = re.findall(r"\d+", result)
            valid_sizes = [int(n) for n in numbers if int(n) > 2048]
            if valid_sizes:
                return max(valid_sizes) / 1024
        except:
            pass
        cmd = "wmic cpu get L3CacheSize"
        result = subprocess.check_output(cmd, shell=True).decode()
        numbers = re.findall(r"\d+", result)
        if numbers:
            int_values = [int(n) for n in numbers]
            max_val_kb = max(int_values)
            if max_val_kb < 2048:
                return None
            return max_val_kb / 1024
    except Exception:
        pass
    return None


# ANSI 控制台颜色
class C:
    R   = "\033[0m"
    RED = "\033[91m"
    GRN = "\033[92m"
    YLW = "\033[93m"
    BLU = "\033[94m"
    CYN = "\033[96m"
    B   = "\033[1m"
    D   = "\033[2m"


# ═══════════════════════════════════════════════════════════════
# 1. Config — 全局配置数据类
# ═══════════════════════════════════════════════════════════════

@dataclass
class Config:
    trigger_key: str = "f9"

    # ── Module A: RTSS 帧率锁定 ──
    rtss_on:       bool   = False
    rtss_hotkey:   str    = "f6"    # RTSS 设置中的切换热键
    rtss_restore:  bool   = True             # 挑战开始后恢复帧率

    # ── Module B: 后台切换 ──
    focus_on:      bool   = False
    focus_method:  str    = "minimize"       # "minimize" | "win_d" | "alt_tab" | "none"
    focus_delay:   float  = 0.1              # 检测到黑屏后, 延迟多久切走
    focus_dur:     float  = 1.2              # 后台停留时长 (核心参数)

    # ── Module C: CPU 压力 ──
    cpu_on:        bool   = True
    cpu_cores:     int    = 0                # 0 = 自动 (取一半核心数)

    # ── Module D: 黑屏检测 ──
    sd_on:         bool   = True
    sd_thresh:     int    = 70               # 像素亮度阈值 (<此值视为黑)
    sd_ratio:      float  = 0.70             # 黑色像素占比阈值
    sd_interval:   float  = 0.005             # 采样间隔
    sd_monitor:    int    = 1                # 检测的显示器编号 (1=主屏, 2=副屏...)
    sd_region_x:   int    = 25               # 检测区域左上角X (-1=自动居中)
    sd_region_y:   int    = 140               # 检测区域左上角Y (-1=自动居中)
    sd_region_w:   int    = 50              # 检测区域宽度
    sd_region_h:   int    = 50              # 检测区域高度

    # ── 固定延迟后备 (黑屏检测不可用时) ──
    fb_black:      float  = 0.4              # 触发后到黑屏的估计延迟
    fb_post:       float  = 1.5              # 切回后等321结束的估计时间
    beep_on:       bool   = True             # 蜂鸣提示音开关

    # ── Module E: 自动监听 (自定义模式) ──
    aw_on:         bool   = True             # 自定义模式默认开启
    aw_click_x:    int    = -1               # 点击位置X (-1=屏幕居中)
    aw_click_y:    int    = -1               # 点击位置Y (-1=屏幕居中)
    aw_tolerance:  int    = 20              # 位置允许误差 (像素)
    aw_esc_delay:  float  = 3.0              # ESC到点击的最大间隔 (s)
    aw_retry_timeout: float = 0.5            # 检测黑屏超时后重试等待 (s)

    # ── Module F: L3 缓存污染 ──
    cache_on:      bool   = True             # 缓存污染开关
    cache_workers: int    = 3                # 污染进程数
    cache_block_mb: int   = 32               # 单次搬运数据大小 (MB)

    # ── Module G: CPU 绑核 ──
    affinity_on:   bool   = True             # 绑核开关
    affinity_cores: str  = "0,3,5,7"                # 核心列表, 如 "4,5,6,7" (空=不绑)


# ═══════════════════════════════════════════════════════════════
# 2. Module Base — 模块基类 (6个生命周期钩子)
# ═══════════════════════════════════════════════════════════════

class Mod:
    """
    所有模块的基类.
    定义了编排器在每个阶段会调用的钩子方法,
    子类只需覆盖自己关心的阶段即可.
    """
    name = "base"
    on   = False

    def __init__(self, on=False):
        self.on = on

    def log(self, s):
        ts = time.strftime("%H:%M:%S")
        print(f"  [{ts}] {C.CYN}{self.name.upper()}{C.R} {s}")

    # ── 生命周期钩子 (子类按需覆盖) ──
    def pre(self):            pass    # Phase 0:  挑战前预处理
    def trigger(self, hw):    pass    # 触发瞬间 (传入游戏窗口句柄)
    def black(self):          pass    # 检测到黑屏
    def bg_enter(self):       pass    # 进入后台
    def bg_exit(self):        pass    # 离开后台
    def post(self):           pass    # Phase 5:  挑战后处理
    def clean(self):          pass    # 始终最后调用 (清理资源)


# ═══════════════════════════════════════════════════════════════
# 3. Module A — RTSS Frame Lock
# ═══════════════════════════════════════════════════════════════

class RTSSMod(Mod):
    """
    RTSS 帧率锁定模块
    ─────────────────
    原理:
      高刷显示器(144/240Hz)下, Unity Time.deltaTime 每帧更小,
      加载期间的 Update() 调用频率更高 → 底层计时器每帧消耗的时间更少
      → 看起来"加载没花时间", 但 60s 的 UI 动画是固定步长的 → 产生跳秒.
      锁定 60fps 后, 每帧步进一致, 加载期间不额外"偷步".

    操作:
      模拟按下用户在 RTSS 中配置的全局切换热键 (如 Scroll Lock).
    """
    name = "rtss_lock"

    def __init__(self, on, hotkey, restore):
        super().__init__(on)
        self.hk  = hotkey
        self.rst = restore
        self._lk = False            # 当前是否处于锁定状态

    def pre(self):
        """Phase 0: 锁定帧率"""
        if not self.on:
            return
        self.log(f"发送 RTSS 切换键 [{self.hk}] → 锁定帧率")
        try:
            import keyboard
            keyboard.send(self.hk)
            self._lk = True
            time.sleep(0.15)       # 等待 RTSS 响应
            self.log(f"{C.GRN}✓ 帧率已锁定{C.R}")
        except Exception as e:
            self.log(f"{C.RED}✗ RTSS 控制失败: {e}{C.R}")

    def post(self):
        """Phase 5: 恢复帧率"""
        if not self.on or not self.rst or not self._lk:
            return
        self.log(f"发送 RTSS 切换键 [{self.hk}] → 恢复帧率")
        try:
            import keyboard
            keyboard.send(self.hk)
            self._lk = False
            self.log(f"{C.GRN}✓ 帧率已恢复{C.R}")
        except Exception as e:
            self.log(f"{C.RED}✗ RTSS 恢复失败: {e}{C.R}")


# ═══════════════════════════════════════════════════════════════
# 4. Module B — Screen Detection
# ═══════════════════════════════════════════════════════════════

class ScreenMod(Mod):
    """
    黑屏检测模块
    ─────────────
    用 mss 库截取屏幕中心 200×200 区域,
    统计暗像素占比, 判断是否处于黑屏加载状态.
    
    为后续的"后台切换"提供精确的时机信号,
    避免过早切换 (挑战还没开始) 或过晚切换 (已经321了).
    """
    name = "screen"

    def __init__(self, on, thresh, ratio, interval,
                 monitor=1, region_x=-1, region_y=-1,
                 region_w=100, region_h=100):
        super().__init__(on)
        self.th   = thresh           # 像素亮度阈值
        self.ratio = ratio           # 黑色占比阈值
        self.itv   = interval        # 采样间隔
        self.mon   = monitor         # 显示器编号
        self.rx    = region_x        # 区域X (-1=居中)
        self.ry    = region_y        # 区域Y (-1=居中)
        self.rw    = region_w        # 区域宽度
        self.rh    = region_h        # 区域高度
        self._ok   = False           # mss 是否可用

    def _chk(self):
        """延迟检查 mss 是否已安装"""
        if not self._ok:
            try:
                import mss
                self._ok = True
            except ImportError:
                self.on = False
                self.log(f"{C.YLW}mss 未安装, 将使用固定延迟{C.R}")
        return self._ok

    def _analyze(self):
        """
        截取指定显示器的指定区域, 返回黑色像素占比.
        原始数据格式: BGRA (4 bytes/pixel)
        采样策略: 每4个像素取1个 (stride=16字节), 只检查B通道.
        """
        import mss
        with mss.mss() as sct:
            monitors = sct.monitors
            mi = min(self.mon, len(monitors) - 1)
            mi = max(mi, 1)
            m = monitors[mi]
            if self.rx == -1:
                left = m["left"] + (m["width"] - self.rw) // 2
            else:
                left = m["left"] + self.rx
            if self.ry == -1:
                top = m["top"] + (m["height"] - self.rh) // 2
            else:
                top = m["top"] + self.ry
            raw = sct.grab({
                "left": left, "top": top,
                "width": self.rw, "height": self.rh
            }).raw
            bc = tot = 0
            for i in range(0, len(raw), 16):
                if raw[i] < self.th:
                    bc += 1
                tot += 1
            return bc / max(tot, 1)

    def get_ratio(self):
        """获取当前黑色像素占比 (用于校准)"""
        if not self._chk():
            return 0.0
        try:
            return self._analyze()
        except Exception:
            return 0.0

    def wait_black(self, timeout=1.0):
        """
        阻塞等待黑屏出现.
        返回 True=检测到黑屏, False=超时 (编排器将使用固定延迟后备).
        """
        if not self.on or not self._chk():
            return False
        self.log("监控屏幕, 等待黑屏...")
        t0 = time.time()
        while time.time() - t0 < timeout and not _shutdown.is_set():
            r = self._analyze()
            bl = int(r * 30)
            bar = "\u2588" * bl + "\u2591" * (30 - bl)
            sys.stdout.write(f"\r  [{bar}] {r:.0%}  ")
            sys.stdout.flush()
            if r >= self.ratio:
                print()
                self.log(f"{C.GRN}✓ 检测到黑屏 (占比 {r:.0%}){C.R}")
                return True
            time.sleep(self.itv)
        print()
        self.log(f"{C.YLW}等待黑屏超时{C.R}")
        return False

    def calibrate(self):
        """校准模式: 实时显示黑色像素占比, 帮助用户调整阈值"""
        if not self._chk():
            print("  mss 未安装, 无法校准")
            return
        try:
            import keyboard
        except ImportError:
            return
        mon_label = f"显示器 {self.mon}"
        if self.rx == -1:
            pos_label = "居中"
        else:
            pos_label = f"X={self.rx} Y={self.ry}"
        print(f"\n  {C.B}黑屏校准模式{C.R}")
        print(f"  {C.D}检测区域: {self.rw}×{self.rh} @ {mon_label} ({pos_label}){C.R}")
        print(f"  {C.D}将游戏画面切到需要检测的状态, 按任意键退出{C.R}\n")
        done = threading.Event()
        kb = None
        try:
            kb = keyboard.hook(lambda e: done.set())
            while not done.is_set():
                r = self.get_ratio()
                bl = int(r * 40)
                bar = "\u2588" * bl + "\u2591" * (40 - bl)
                if r >= self.ratio:
                    st = f"{C.GRN}← 判定为黑屏 (阈值 {self.ratio:.0%}){C.R}"
                else:
                    st = f"{C.RED}← 判定为非黑屏{C.R}"
                sys.stdout.write(f"\r  [{bar}] {r:.1%} {st}     ")
                sys.stdout.flush()
                time.sleep(0.1)
        finally:
            if kb:
                try:
                    keyboard.unhook(kb)
                except Exception:
                    pass
        print("\n")


# ═══════════════════════════════════════════════════════════════
# 5. Module C — Focus Switch
# ═══════════════════════════════════════════════════════════════

class FocusMod(Mod):
    """
    后台切换模块
    ─────────────
    原理:
      Windows 在窗口失焦时, 会大幅节流该窗口进程的 CPU 调度.
      Unity 的主线程 Update() 频率从 240fps 骤降到个位数.
      这推迟了 "场景加载完成 → 客户端发送 Ready 包" 的时间点.
      服务端在收到 Ready 后才开始计时, 所以最终:
        EndTimeStamp = ServerTime(received_later) + 60s
        → 客户端显示的初始剩余时间 = EndTimeStamp - ServerNow > 60s
        → 出现 61s / 62s 的"红利时间".

    方法:
      minimize: 仅最小化游戏窗口 (不影响其他屏幕显示)
      win_d:    Win+D 显示桌面 (全局最小化, 切回时再Win+D+激活游戏)
      alt_tab:  模拟 Alt+Tab 切换窗口
      none:     不切屏, 仅靠缓存污染+CPU压力拖慢加载
    """
    name = "focus"

    def __init__(self, on, method, delay, dur):
        super().__init__(on)
        self.meth  = method
        self.delay = delay
        self.dur   = dur
        self._hw   = 0              # 游戏窗口句柄

    def trigger(self, hw):
        """记录游戏窗口句柄 (触发时游戏应该在前台)"""
        self._hw = hw

    def black(self):
        """黑屏后延迟一小段再切走 (让黑屏完全建立)"""
        if not self.on:
            return
        self.log(f"延迟 {self.delay}s 后切到后台...")
        time.sleep(self.delay)

    def bg_enter(self):
        """执行后台切换"""
        if not self.on:
            return
        if self.meth == "none":
            self.log("不切屏, 游戏保持前台")
            return
        if self.meth == "minimize" and self._hw:
            self.log(f"最小化游戏窗口 (hwnd={self._hw:#x})")
            win_minimize(self._hw)
            time.sleep(0.1)
        elif self.meth == "win_d":
            self.log("Win+D 显示桌面")
            try:
                import keyboard
                keyboard.send("windows+d")
                time.sleep(0.3)
            except Exception as e:
                self.log(f"{C.RED}Win+D 失败: {e}{C.R}")
        elif self.meth == "alt_tab":
            self.log("Alt+Tab 切换窗口")
            try:
                import keyboard
                keyboard.press("alt")
                time.sleep(0.05)
                keyboard.press("tab")
                time.sleep(0.05)
                keyboard.release("tab")
                time.sleep(0.05)
                keyboard.release("alt")
                time.sleep(0.2)
            except Exception as e:
                self.log(f"{C.RED}Alt+Tab 失败: {e}{C.R}")
        self.log(f"{C.YLW}→ 游戏已切到后台{C.R}")

    def bg_exit(self):
        """切回游戏"""
        if not self.on:
            return
        if self.meth == "none":
            return
        if self.meth == "minimize" and self._hw:
            self.log("恢复游戏窗口")
            win_restore(self._hw)
        elif self.meth == "win_d":
            self.log("Win+D 恢复窗口 + 激活游戏")
            try:
                import keyboard
                keyboard.send("windows+d")
                time.sleep(1.3)
                if self._hw:
                    win_restore(self._hw)
            except Exception:
                pass
        elif self.meth == "alt_tab":
            self.log("Alt+Tab 切回游戏")
            try:
                import keyboard
                keyboard.press("alt")
                time.sleep(0.05)
                keyboard.press("tab")
                time.sleep(0.05)
                keyboard.release("tab")
                time.sleep(0.05)
                keyboard.release("alt")
                time.sleep(0.3)
            except Exception:
                pass
        self.log(f"{C.GRN}→ 游戏已切回前台{C.R}")


# ═══════════════════════════════════════════════════════════════
# 6. Module D — CPU Pressure
# ═══════════════════════════════════════════════════════════════

def _burn(ev):
    """
    CPU 密集空循环 (在独立进程中运行).
    每个进程占满一个物理核心.
    """
    while not ev.is_set():
        pass


class CPUMod(Mod):
    """
    CPU 压力模块
    ─────────────
    原理:
      Unity 的 SceneManager.LoadSceneAsync() 使用后台线程加载 AB 包.
      当 CPU 核心被密集占用时, OS 调度器会降低加载线程的优先级,
      LoadSceneAsync 的 allowSceneActivation 进展变慢.
      配合后台切换, 进一步放大 "客户端 Ready 延迟" 的效果.

    实现:
      用 multiprocessing.Process 创建独立进程 (绕过 GIL),
      每个进程一个空循环占满一个核心.
      后台切换结束时, 通过 Event 信号立即释放所有进程.
    """
    name = "cpu"

    def __init__(self, on, cores):
        super().__init__(on)
        self.cores = cores
        self._ev   = None
        self._ps   = []

    @property
    def _n(self):
        """实际使用的核心数"""
        if self.cores > 0:
            return min(self.cores, os.cpu_count() or 4)
        return max(1, (os.cpu_count() or 4) // 2)

    def bg_enter(self):
        """进后台时启动 CPU 压力"""
        if not self.on:
            return
        n = self._n
        self.log(f"启动 CPU 压力 ({n} 核心)...")
        self._ev = MpEvent()
        for _ in range(n):
            p = Process(target=_burn, args=(self._ev,), daemon=True)
            p.start()
            self._ps.append(p)
        time.sleep(0.1)
        active = sum(1 for p in self._ps if p.is_alive())
        self.log(f"{C.YLW}→ {active}/{n} 进程运行中{C.R}")

    def bg_exit(self):
        """出后台时释放 CPU 压力"""
        if not self.on:
            return
        self._kill()

    def _kill(self):
        if self._ev:
            self._ev.set()
        for p in self._ps:
            if p.is_alive():
                p.join(timeout=1.0)
                if p.is_alive():
                    p.terminate()
        self.log(f"{C.GRN}→ CPU 压力已释放{C.R}")
        self._ps.clear()
        self._ev = None

    def clean(self):
        self._kill()


# ═══════════════════════════════════════════════════════════════
# 7. Module F — CPU Affinity (绑核)
# ═══════════════════════════════════════════════════════════════

class AffinityMod(Mod):
    """
    CPU 绑核模块
    ─────────────
    将压力进程绑定到指定核心, 避免与游戏主线程争抢同一核心.
    在启动时一次性绑定, 之后不再变动.
    """
    name = "affinity"

    def __init__(self, on, cores_str):
        super().__init__(on)
        self.cores_str = cores_str
        self._cores = self._parse(cores_str)

    def _parse(self, s):
        if not s or not s.strip():
            return None
        try:
            return [int(x.strip()) for x in s.split(",") if x.strip()]
        except ValueError:
            return None

    @property
    def cores(self):
        return self._cores

    def pre(self):
        if not self.on or not self._cores:
            return
        self.log(f"绑核至 {self._cores}")
        set_cpu_affinity(self._cores)


# ═══════════════════════════════════════════════════════════════
# 8. Module G — L3 Cache Pollution (缓存污染)
# ═══════════════════════════════════════════════════════════════

def _cache_worker(flag, block_size_mb, core_list):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    if core_list:
        set_cpu_affinity(core_list)
    set_priority("below_normal")
    total_bytes = int(block_size_mb * 1024 * 1024)
    num_elements = int(total_bytes / 8)
    try:
        source_data = np.ones(num_elements, dtype=np.float64)
    except Exception:
        return
    while True:
        if flag.is_set():
            try:
                _ = np.sum(source_data)
            except:
                pass
        else:
            time.sleep(0.1)


class CacheMod(Mod):
    """
    L3 缓存污染模块
    ────────────────
    使用 numpy 大数组运算持续刷新 L3 缓存,
    迫使游戏加载时的内存访问产生大量 Cache Miss,
    从而拖慢场景加载速度, 延迟服务端计时起点.
    """
    name = "cache"

    def __init__(self, on, workers, block_mb, core_list=None):
        super().__init__(on)
        self.workers = max(1, workers)
        self.block_mb = max(8, block_mb)
        self.core_list = core_list
        self._flag = None
        self._ps = []

    def bg_enter(self):
        if not self.on:
            return
        self.log(f"启动缓存污染 ({self.workers}进程 x {self.block_mb}MB)")
        self._flag = MpEvent()
        self._flag.set()
        for _ in range(self.workers):
            p = Process(target=_cache_worker,
                        args=(self._flag, self.block_mb, self.core_list),
                        daemon=True)
            p.start()
            self._ps.append(p)
        time.sleep(0.1)
        active = sum(1 for p in self._ps if p.is_alive())
        self.log(f"{C.YLW}→ {active}/{self.workers} 缓存污染进程运行中{C.R}")

    def bg_exit(self):
        if not self.on:
            return
        self._kill()

    def _kill(self):
        if self._flag:
            self._flag.clear()
        for p in self._ps:
            if p.is_alive():
                p.join(timeout=1.0)
                if p.is_alive():
                    p.terminate()
        if self._ps:
            self.log(f"{C.GRN}→ 缓存污染已停止{C.R}")
        self._ps.clear()
        self._flag = None

    def clean(self):
        self._kill()


# ═══════════════════════════════════════════════════════════════
# 9. Module E — Auto Watch (自动监听)
# ═══════════════════════════════════════════════════════════════

class AutoWatchMod(Mod):
    """
    自动监听模块
    ─────────────
    按 F9 进入自动监听模式后, 监听用户的 ESC+鼠标左键点击序列.
    检测到该序列后, 自动触发优化流程.
    鼠标点击位置在配置中指定 (默认屏幕中心), 允许误差范围.

    原理:
      使用 Windows GetAsyncKeyState 轮询检测 ESC 按键,
      配合 GetCursorPos 检测鼠标左键点击位置.
      不依赖额外库, 纯 ctypes 实现.
    """
    name = "autowatch"

    def __init__(self, on, click_x, click_y, tolerance,
                 esc_delay, retry_timeout):
        super().__init__(on)
        self.cx = click_x
        self.cy = click_y
        self.tol = tolerance
        self.max_esc_delay = esc_delay
        self.retry_to = retry_timeout
        self._thread = None
        self._trigger_cb = None
        self._watching = False
        self._cx_abs = click_x
        self._cy_abs = click_y

    def set_trigger_cb(self, cb):
        """设置触发回调 (当检测到 ESC+点击时调用)"""
        self._trigger_cb = cb

    def start(self):
        """开始后台轮询监听"""
        if not self.on or self._watching:
            return
        # 解析坐标: -1 表示屏幕居中
        if self.cx == -1 or self.cy == -1:
            try:
                import mss
                with mss.mss() as sct:
                    m = sct.monitors[1]
                    self._cx_abs = m["left"] + m["width"] // 2
                    self._cy_abs = m["top"] + m["height"] // 2
            except Exception:
                self._cx_abs = 960
                self._cy_abs = 540
        else:
            self._cx_abs = self.cx
            self._cy_abs = self.cy

        self._watching = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        self.log(f"{C.GRN}自动监听已启动, 等待 ESC+点击 ({self._cx_abs},{self._cy_abs})...{C.R}")

    def stop(self):
        """停止监听"""
        self._watching = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _poll_loop(self):
        """轮询线程: 检测 ESC → 左键点击 序列"""
        VK_ESC = 0x1B
        VK_LBUTTON = 0x01
        prev_esc = False

        while self._watching and not _shutdown.is_set():
            curr_esc = bool(user32.GetAsyncKeyState(VK_ESC) & 0x8000)

            # ESC 按下瞬间 (上升沿检测)
            if curr_esc and not prev_esc:
                esc_t = time.time()
                # 在时间窗口内等待左键点击
                while time.time() - esc_t < self.max_esc_delay:
                    if user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000:
                        pt = ctypes.wintypes.POINT()
                        user32.GetCursorPos(ctypes.byref(pt))
                        dx = abs(pt.x - self._cx_abs)
                        dy = abs(pt.y - self._cy_abs)
                        if dx <= self.tol and dy <= self.tol:
                            self.log(
                                f"{C.GRN}检测到 ESC+点击 ({pt.x},{pt.y}), "
                                f"触发优化{C.R}"
                            )
                            if self._trigger_cb:
                                self._trigger_cb()
                            # 防抖后继续监听下一轮
                            time.sleep(0.3)
                            break
                    time.sleep(0.01)

            prev_esc = curr_esc
            time.sleep(0.01)

    def clean(self):
        self.stop()


# ═══════════════════════════════════════════════════════════════
# 8. Orchestrator — 编排器 (核心6阶段时序流水线)
# ═══════════════════════════════════════════════════════════════

class Orch:
    """
    挑战计时优化编排器.
    ────────────────────
    将7个模块按精确时序编排为6阶段流水线:

      Phase 0   预处理        → [A]RTSS 锁帧 + [G]绑核
      Phase 1   等待黑屏      → [B]屏幕检测 (超时→放弃本轮)
      Phase 1.5 黑屏后延迟    → [C]focus.black() (延迟切走)
      Phase 2   进入后台      → [C]切屏 + [D]CPU压力 + [F]缓存污染
      Phase 3   后台等待      → 倒计时 (focus_dur 秒)
      Phase 4   返回游戏      → [D]释放CPU + [F]停止污染 + [C]恢复窗口
      Phase 5   后处理        → 等待321结束 + [A]RTSS恢复
      → 自动回到监听状态
    """

    def __init__(self, cfg: Config):
        self.c    = cfg
        self._run = False
        self._hw  = 0
        self._loop = True

        parsed_cores = self._parse_cores(cfg.affinity_cores)

        self.A = RTSSMod(cfg.rtss_on, cfg.rtss_hotkey, cfg.rtss_restore)
        self.B = ScreenMod(cfg.sd_on, cfg.sd_thresh, cfg.sd_ratio, cfg.sd_interval,
                           cfg.sd_monitor, cfg.sd_region_x, cfg.sd_region_y,
                           cfg.sd_region_w, cfg.sd_region_h)
        self.C = FocusMod(cfg.focus_on, cfg.focus_method, cfg.focus_delay, cfg.focus_dur)
        self.D = CPUMod(cfg.cpu_on, cfg.cpu_cores)
        self.E = AutoWatchMod(cfg.aw_on, cfg.aw_click_x, cfg.aw_click_y,
                              cfg.aw_tolerance, cfg.aw_esc_delay, cfg.aw_retry_timeout)
        self.F = CacheMod(cfg.cache_on, cfg.cache_workers, cfg.cache_block_mb, parsed_cores)
        self.G = AffinityMod(cfg.affinity_on, cfg.affinity_cores)
        self.mods = [self.A, self.B, self.C, self.D, self.E, self.F, self.G]

    def _parse_cores(self, s):
        if not s or not s.strip():
            return None
        try:
            return [int(x.strip()) for x in s.split(",") if x.strip()]
        except ValueError:
            return None

    def go(self):
        """自动监听触发时调用"""
        if self._run:
            print(f"  {C.YLW}⚠ 序列正在运行中, 请等待完成{C.R}")
            return
        c = self.c
        parsed_cores = self._parse_cores(c.affinity_cores)
        self.A = RTSSMod(c.rtss_on, c.rtss_hotkey, c.rtss_restore)
        self.B = ScreenMod(c.sd_on, c.sd_thresh, c.sd_ratio, c.sd_interval,
                           c.sd_monitor, c.sd_region_x, c.sd_region_y,
                           c.sd_region_w, c.sd_region_h)
        self.C = FocusMod(c.focus_on, c.focus_method, c.focus_delay, c.focus_dur)
        self.D = CPUMod(c.cpu_on, c.cpu_cores)
        self.E = AutoWatchMod(c.aw_on, c.aw_click_x, c.aw_click_y,
                              c.aw_tolerance, c.aw_esc_delay, c.aw_retry_timeout)
        self.F = CacheMod(c.cache_on, c.cache_workers, c.cache_block_mb, parsed_cores)
        self.G = AffinityMod(c.affinity_on, c.affinity_cores)
        self.mods = [self.A, self.B, self.C, self.D, self.E, self.F, self.G]
        self._run = True
        self._hw = get_fg_hwnd()
        for m in self.mods:
            m.trigger(self._hw)
        threading.Thread(target=self._seq, daemon=True).start()

    def _seq(self):
        """核心时序流水线 (在独立线程中运行, 不阻塞热键监听)"""
        c = self.c
        try:
            # ── Phase 0: 预处理 ──
            self._ph("Phase 0", "预处理")
            self.A.pre()
            self.G.pre()
            if c.beep_on: beep(800, 60)

            # ── Phase 1: 等待黑屏 ──
            self._ph("Phase 1", "等待黑屏")
            ok = self.B.wait_black(4.0) if self.B.on else False
            if not ok:
                self._lg(f"{C.RED}未检测到黑屏, 放弃本轮, 回到监听{C.R}")
                if c.beep_on: beep(200, 200)
                return
            if c.beep_on: beep(600, 60)

            # ── Phase 1.5: 黑屏后延迟 ──
            self.C.black()

            # ── Phase 2: 进入后台 ──
            self._ph("Phase 2", "进入后台")
            self.C.bg_enter()
            self.D.bg_enter()
            self.F.bg_enter()

            # ── Phase 3: （后台)等待 ──
            self._ph("Phase 3", f"后台等待 ({c.focus_dur}s)")
            self._cd(c.focus_dur)
            if c.beep_on: beep(1000, 80)

            # ── Phase 4: 返回游戏 ──
            self._ph("Phase 4", "返回游戏")
            self.D.bg_exit()
            self.F.bg_exit()
            self.C.bg_exit()

            # ── Phase 5: 后处理 ──
            self._ph("Phase 5", f"等待321结束 ({c.fb_post}s)")
            self._cd(c.fb_post, "倒计时")
            self.A.post()

            # ── 完成 ──
            print(f"\n  {C.GRN}{C.B}{'='*46}{C.R}")
            print(f"  {C.GRN}{C.B}  ✓ 序列执行完成! 自动回到监听...{C.R}")
            print(f"  {C.GRN}{C.B}{'='*46}{C.R}\n")
            if c.beep_on: beep(1200, 150)

        except Exception as e:
            self._lg(f"{C.RED}✗ 序列执行出错: {e}{C.R}")
            import traceback
            traceback.print_exc()
        finally:
            for m in self.mods:
                m.clean()
            self._run = False

    def _ph(self, name, desc):
        """打印阶段标题"""
        print(f"\n  {C.B}{C.BLU}── {name}: {desc} ──{C.R}  "
              f"[{time.strftime('%H:%M:%S')}]")

    def _cd(self, secs, label="等待"):
        """带进度条的倒计时"""
        t = int(secs)
        r = secs - t
        for i in range(t, 0, -1):
            if _shutdown.is_set():
                return
            f = int((1 - i / secs) * 20)
            bar = "\u2588" * f + "\u2591" * (20 - f)
            sys.stdout.write(
                f"\r  {C.D}{label}: {bar} {i}s{C.R}  "
            )
            sys.stdout.flush()
            time.sleep(1)
        if r > 0 and not _shutdown.is_set():
            time.sleep(r)
        full_bar = "\u2588" * 20
        sys.stdout.write(
            f"\r  {label}: {full_bar} 完成    \n"
        )
        sys.stdout.flush()

    def _lg(self, s):
        print(f"  [{time.strftime('%H:%M:%S')}] {s}")


# ═══════════════════════════════════════════════════════════════
# 8. CLI — 交互式命令行界面
# ═══════════════════════════════════════════════════════════════

def banner():
    print(f"""{C.CYN}{'='*52}
  原神挑战计时优化器  v1.0
  Genshin Challenge Timer Optimizer
{'='*52}{C.R}

{C.D}基于 Unity 底层引擎行为分析{C.R}
{C.D}利用 RTSS帧率锁定 / 后台切换 / CPU压力 优化计时{C.R}""")


def show_cfg(c):
    """展示当前配置 (避免终端宽字符导致表格错位)"""
    def st(v):
        return f"{C.GRN}ON {C.R}" if v else f"{C.RED}OFF{C.R}"

    core_text = "自动" if c.cpu_cores == 0 else str(c.cpu_cores)
    region_pos = "居中" if c.sd_region_x == -1 else f"X={c.sd_region_x} Y={c.sd_region_y}"
    aff_text = c.affinity_cores if c.affinity_cores else "不绑"
    print(f"""
{C.B}当前配置:{C.R}
    触发热键: {C.YLW}{c.trigger_key}{C.R}
    [A] RTSS帧率锁定: {st(c.rtss_on)}  热键: {c.rtss_hotkey}
    [B] 后台切换:     {st(c.focus_on)}  方式: {c.focus_method}
    [C] CPU压力:      {st(c.cpu_on)}  核心: {core_text}
    [D] 黑屏检测:     {st(c.sd_on)}
    [E] 自动监听:     {st(c.aw_on)}
    [F] 缓存污染:     {st(c.cache_on)}  进程: {c.cache_workers}  Block: {c.cache_block_mb}MB
    [G] CPU绑核:      {st(c.affinity_on)}  核心: {aff_text}
    [H] 蜂鸣提示:     {st(c.beep_on)}

    后台停留时长: {c.focus_dur:.2f}s
    黑屏后延迟:   {c.focus_delay:.2f}s
    黑屏阈值:     亮度<{c.sd_thresh} 且占比>{c.sd_ratio:.0%}
    检测区域:     {c.sd_region_w}×{c.sd_region_h} @ 显示器{c.sd_monitor} ({region_pos})
    固定延迟(黑屏不可用时): {c.fb_black:.2f}s
    固定延迟(后置): {c.fb_post:.2f}s
    自动监听:     ESC+点击触发 (位置误差≤{c.aw_tolerance}px)
""")


def customize():
    """交互式自定义配置"""
    c = Config()
    print(f"\n  {C.B}自定义模式{C.R}")
    print(f"  {C.D}命令: a/b/c/d/e/f/g/h 切换模块 | duration/delay/cores/{C.R}")
    print(f"  {C.D}       method/trigger/hotkey/region/monitor/{C.R}")
    print(f"  {C.D}       fb_black/fb_post/calibrate/aw_tol | 空行确认{C.R}")
    while True:
        show_cfg(c)
        i = input(f"  {C.YLW}> {C.R}").strip().lower()
        if not i:
            break
        elif i == "a":
            c.rtss_on = not c.rtss_on
        elif i == "b":
            c.focus_on = not c.focus_on
        elif i == "c":
            c.cpu_on = not c.cpu_on
        elif i == "d":
            c.sd_on = not c.sd_on
        elif i == "e":
            c.aw_on = not c.aw_on
        elif i == "f":
            c.cache_on = not c.cache_on
        elif i == "g":
            c.affinity_on = not c.affinity_on
        elif i == "h":
            c.beep_on = not c.beep_on
        elif i == "duration":
            try:
                v = input(f"  后台停留时长 (当前 {c.focus_dur}s): ")
                c.focus_dur = float(v) if v.strip() else c.focus_dur
            except ValueError:
                pass
        elif i == "delay":
            try:
                v = input(f"  黑屏后延迟 (当前 {c.focus_delay}s): ")
                c.focus_delay = float(v) if v.strip() else c.focus_delay
            except ValueError:
                pass
        elif i == "fb_black":
            try:
                v = input(f"  固定延迟-黑屏 (当前 {c.fb_black}s): ")
                c.fb_black = float(v) if v.strip() else c.fb_black
            except ValueError:
                pass
        elif i == "fb_post":
            try:
                v = input(f"  固定延迟-后置 (当前 {c.fb_post}s): ")
                c.fb_post = float(v) if v.strip() else c.fb_post
            except ValueError:
                pass
        elif i == "cores":
            try:
                v = input("  CPU核心数 (0=自动): ")
                c.cpu_cores = int(v) if v.strip() else c.cpu_cores
            except ValueError:
                pass
        elif i == "method":
            c.focus_method = input(
                f"  切换方式 minimize/win_d/alt_tab/none (当前 {c.focus_method}): "
            ) or c.focus_method
        elif i == "trigger":
            c.trigger_key = input(
                f"  触发热键 (当前 {c.trigger_key}): "
            ) or c.trigger_key
        elif i == "hotkey":
            c.rtss_hotkey = input(
                f"  RTSS切换热键 (当前 {c.rtss_hotkey}): "
            ) or c.rtss_hotkey
        elif i == "region":
            try:
                w = input(f"  检测区域宽度 (当前 {c.sd_region_w}): ")
                if w.strip(): c.sd_region_w = int(w)
                h = input(f"  检测区域高度 (当前 {c.sd_region_h}): ")
                if h.strip(): c.sd_region_h = int(h)
                x = input(f"  区域X偏移 (-1=居中, 当前 {c.sd_region_x}): ")
                if x.strip(): c.sd_region_x = int(x)
                y = input(f"  区域Y偏移 (-1=居中, 当前 {c.sd_region_y}): ")
                if y.strip(): c.sd_region_y = int(y)
            except ValueError:
                pass
        elif i == "monitor":
            try:
                v = input(f"  检测显示器编号 (1=主屏, 当前 {c.sd_monitor}): ")
                if v.strip(): c.sd_monitor = int(v)
            except ValueError:
                pass
        elif i == "calibrate":
            o = Orch(c)
            o.B.calibrate()
        elif i == "aw_tol":
            try:
                v = input(f"  点击位置允许误差 (当前 {c.aw_tolerance}px): ")
                if v.strip(): c.aw_tolerance = int(v)
            except ValueError:
                pass
        elif i == "cache_workers":
            try:
                v = input(f"  缓存污染进程数 (当前 {c.cache_workers}): ")
                if v.strip(): c.cache_workers = int(v)
            except ValueError:
                pass
        elif i == "cache_block":
            try:
                v = input(f"  缓存Block大小MB (当前 {c.cache_block_mb}): ")
                if v.strip(): c.cache_block_mb = int(v)
            except ValueError:
                pass
        elif i == "affinity":
            c.affinity_cores = input(
                f"  绑核核心列表, 如 4,5,6,7 (当前 {c.affinity_cores or '不绑'}): "
            ) or c.affinity_cores
        elif i == "help":
            print("""
  可用命令:
    a/b/c/d/e/f/g/h 切换模块 [A-H] 开关
    duration       修改后台停留时长 (秒)
    delay          修改黑屏后延迟 (秒)
    fb_black       修改固定延迟-黑屏 (秒)
    fb_post        修改固定延迟-后置 (秒)
    cores          修改CPU压力核心数 (0=自动)
    method         切换方式: minimize / win_d / alt_tab / none
    trigger        修改触发热键
    hotkey         修改RTSS切换热键
    region         修改检测区域 (宽/高/X/Y偏移)
    monitor        修改检测显示器编号
    calibrate      进入黑屏检测校准模式
    aw_tol         修改自动监听点击位置允许误差 (像素)
    cache_workers  修改缓存污染进程数
    cache_block    修改缓存Block大小 (MB)
    affinity       修改绑核核心列表 (如 4,5,6,7)
    help           显示此帮助
    (空行)         确认配置并继续""")
    show_cfg(c)
    return c


# ═══════════════════════════════════════════════════════════════
# 9. Interactive Ready — 交互式准备就绪 (自定义模式)
# ═══════════════════════════════════════════════════════════════

def interactive_ready(cfg, orch):
    """
    交互式准备就绪状态:
      ◄ ►  调值
      ▲ ▼  切换参数
      F9   触发优化序列
      实时显示黑屏检测数据
      自动监听 ESC+点击 触发优化 (全自动循环)
    """
    import keyboard

    # ── 可调参数字典 (用户可在此增删) ──
    # 格式: (显示名, 属性名, 步长, 最小值, 最大值, 格式, 单位)
    TUNABLE_PARAMS = [
        ("后台停留时长",    'focus_dur',      0.05, 0.1,  10.0, '.2f', 's'),
        ("黑屏后延迟",      'focus_delay',    0.05, 0.0,  3.0,  '.2f', 's'),
        ("固定延迟(黑屏)",  'fb_black',       0.05, 0.0,  3.0,  '.2f', 's'),
        ("固定延迟(后置)",  'fb_post',        0.05, 0.5,  10.0, '.2f', 's'),
        ("亮度阈值",        'sd_thresh',      5,    0,    255,  'd',   ''),
        ("黑色占比阈值",    'sd_ratio',       0.05, 0.0,  1.0,  '.0%', ''),
        ("检测区域宽",      'sd_region_w',    10,   20,   500,  'd',   'px'),
        ("检测区域高",      'sd_region_h',    10,   20,   500,  'd',   'px'),
        ("检测显示器",      'sd_monitor',     1,    1,    4,    'd',   '号屏'),
        ("缓存污染进程数",  'cache_workers',  1,    1,    16,   'd',   '个'),
        ("缓存Block(MB)",   'cache_block_mb', 4,    4,    256,  'd',   'MB'),
        ("CPU压力核心数",   'cpu_cores',      1,    0,    32,   'd',   '核'),
        ("点击位置误差",    'aw_tolerance',   5,    5,    100,  'd',   'px'),
    ]

    params = TUNABLE_PARAMS

    sel = [0]

    def _adjust(delta):
        name, attr, step, vmin, vmax, fmt, unit = params[sel[0]]
        cur = getattr(cfg, attr)
        new = cur + delta * step
        new = max(vmin, min(vmax, new))
        if isinstance(step, int):
            new = int(round(new / step)) * step
        if isinstance(step, float):
            new = round(new, 2)
        setattr(cfg, attr, new)

    def _select(delta):
        sel[0] = (sel[0] + delta) % len(params)

    # ── 注册热键 (◄►调值, ▲▼切换, F9开关自动监听) ──
    hooks = {}
    try:
        hooks['left']  = keyboard.add_hotkey('left',  lambda: _adjust(-1),  suppress=True)
        hooks['right'] = keyboard.add_hotkey('right', lambda: _adjust(1),   suppress=True)
        hooks['up']    = keyboard.add_hotkey('up',    lambda: _select(-1),  suppress=True)
        hooks['down']  = keyboard.add_hotkey('down',  lambda: _select(1),   suppress=True)

        def _toggle_aw():
            if aw._watching:
                aw.stop()
            else:
                aw.start()

        hooks['f9'] = keyboard.add_hotkey(cfg.trigger_key, _toggle_aw, suppress=False)
    except Exception as e:
        print(f"\n  {C.RED}热键注册失败: {e}{C.R}")
        print(f"  {C.YLW}降级为普通模式, 按 {cfg.trigger_key} 触发{C.R}")
        keyboard.add_hotkey(cfg.trigger_key, orch.go, suppress=False)
        try:
            keyboard.wait()
        except KeyboardInterrupt:
            pass
        return

    mon_count = 1
    try:
        import mss
        with mss.mss() as sct:
            mon_count = len(sct.monitors) - 1
    except Exception:
        pass

    aw = orch.E
    aw.set_trigger_cb(orch.go)
    aw.start()

    print(f"\033[2J\033[H", end="")

    prev_running = False

    try:
        while not _shutdown.is_set():
            running = orch._run

            if running:
                sys.stdout.write(
                    f"\r  {C.YLW}{C.B}⚡ 序列执行中... 等待完成{C.R}"
                    f"  [{time.strftime('%H:%M:%S')}]"
                )
                sys.stdout.flush()
                time.sleep(0.5)
                continue

            if prev_running and not running:
                time.sleep(1.0)
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.flush()
            prev_running = running

            lines = []
            lines.append(f"{C.CYN}{'='*58}{C.R}")
            lines.append(
                f"  {C.GRN}{C.B}● 准备就绪!{C.R}"
                f"  [{C.YLW}F9{C.R}] 开关监听  "
                f"  |  ▲ ▼ 切换  ◄ ► 调整  |  Ctrl+C 退出"
            )
            lines.append(f"{C.CYN}{'='*58}{C.R}")
            lines.append("")
            lines.append(f"  {C.B}参数调整:{C.R}")

            for i, (name, attr, step, vmin, vmax, fmt, unit) in enumerate(params):
                val = getattr(cfg, attr)
                if fmt == 'd':
                    vs = f"{val}{unit}"
                elif fmt == '.0%':
                    vs = f"{val:.0%}"
                else:
                    vs = f"{val:{fmt}}{unit}"

                marker = f"{C.B}{C.YLW}►{C.R}" if i == sel[0] else " "
                lines.append(f"  {marker}  {name}: {vs}")

            lines.append("")

            if cfg.sd_on:
                try:
                    sd = ScreenMod(
                        True, cfg.sd_thresh, cfg.sd_ratio, cfg.sd_interval,
                        cfg.sd_monitor, cfg.sd_region_x, cfg.sd_region_y,
                        cfg.sd_region_w, cfg.sd_region_h
                    )
                    r = sd.get_ratio()
                    bl = int(r * 30)
                    bar = "\u2588" * bl + "\u2591" * (30 - bl)
                    st = f"{C.GRN}黑屏{C.R}" if r >= cfg.sd_ratio else f"{C.RED}非黑屏{C.R}"
                    lines.append(f"  实时黑屏: [{bar}] {r:.1%}  {st}")
                except Exception:
                    lines.append(f"  实时黑屏: {C.RED}检测失败{C.R}")
            else:
                lines.append(f"  实时黑屏: {C.D}已禁用{C.R}")

            lines.append("")

            act = []
            if cfg.rtss_on:     act.append(f"{C.GRN}[A]RTSS{C.R}")
            if cfg.focus_on:    act.append(f"{C.GRN}[B]后台{C.R}")
            if cfg.cpu_on:      act.append(f"{C.GRN}[C]CPU{C.R}")
            if cfg.sd_on:       act.append(f"{C.GRN}[D]黑屏{C.R}")
            if cfg.aw_on:       act.append(f"{C.GRN}[E]监听{C.R}")
            if cfg.cache_on:    act.append(f"{C.GRN}[F]缓存{C.R}")
            if cfg.affinity_on: act.append(f"{C.GRN}[G]绑核{C.R}")
            lines.append(f"  模块: {', '.join(act) if act else C.RED + '无' + C.R}")
            lines.append(f"  切屏: {cfg.focus_method}  |  检测: 显示器{cfg.sd_monitor}/{mon_count}  {cfg.sd_region_w}×{cfg.sd_region_h}")

            if cfg.aw_on:
                aw_st = f"{C.GRN}● 监听中{C.R}" if aw._watching else f"{C.YLW}○ 已停止{C.R}"
                lines.append(f"  自动监听: {aw_st}  (F9开关 | ESC+点击触发 | 全自动循环)")

            output = "\n".join(lines)
            sys.stdout.write(f"\033[H\033[J{output}\n")
            sys.stdout.flush()

            time.sleep(0.1)

    except KeyboardInterrupt:
        _shutdown.set()
    finally:
        aw.stop()
        for k, h in hooks.items():
            try:
                keyboard.remove_hotkey(h)
            except Exception:
                pass
        print(f"\033[H\033[J", end="")
        print(f"  {C.D}交互模式已退出{C.R}")


# ═══════════════════════════════════════════════════════════════
# 10. Main — 入口
# ═══════════════════════════════════════════════════════════════

def main():
    banner()

    if not is_admin():
        print(f"\n  {C.YLW}⚠ 未以管理员身份运行{C.R}")
        print(f"  {C.D}keyboard 库的全局热键需要管理员权限{C.R}")
        print(f"  {C.D}建议: 右键脚本 → 以管理员身份运行{C.R}")
        if input("\n  是否继续? (y/N): ").strip().lower() != "y":
            sys.exit(0)

    miss = []
    try:
        import keyboard
    except ImportError:
        miss.append("keyboard")
    try:
        import mss
    except ImportError:
        pass
    if miss:
        print(f"\n  {C.RED}缺少必要依赖: {', '.join(miss)}{C.R}")
        print(f"  请运行: pip install {' '.join(miss)}")
        if "keyboard" in miss:
            print(f"  可选:   pip install mss numpy  (启用黑屏检测和缓存污染模块)")
        sys.exit(1)

    mss_ok = False
    try:
        import mss
        mss_ok = True
    except ImportError:
        pass
    if not mss_ok:
        print(f"  {C.YLW}mss 未安装, 黑屏检测模块不可用{C.R}")
        print(f"  {C.D}安装命令: pip install mss{C.R}")

    set_priority("high")

    cfg = customize()
    orch = Orch(cfg)

    def on_sig(s, f):
        _shutdown.set()
        for m in orch.mods:
            m.clean()
        sys.exit(0)
    signal.signal(signal.SIGINT, on_sig)

    interactive_ready(cfg, orch)


if __name__ == "__main__":
    main()
