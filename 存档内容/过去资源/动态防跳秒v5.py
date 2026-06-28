import time
import threading
import cv2
import mss
import numpy as np
import multiprocessing
import os
import sys
import argparse
import signal
import subprocess
import re
from pynput import mouse, keyboard

# ==============================================================================
#                           用户配置 & 阈值
# ==============================================================================

# 1. E技能白框检测区域 (红框)
WHITE_DETECTION_RECT = {"left": 2247, "top": 1383, "width": 30, "height": 20}
WHITE_PIXEL_THRESHOLD = 10

# 2. 加载界面检测 (蓝框)
LOADING_SCAN_AREA = {"top": 300, "left": 500, "width": 900, "height": 500}
LOADING_COLOR_RATIO = 0.90

# 按键配置
START_KEY = keyboard.Key.shift
RESET_KEY = keyboard.Key.f12
DEBUG_KEY = keyboard.Key.f8
AUTO_KEY = keyboard.Key.f10
SNAPSHOT_KEY = keyboard.Key.f9

# ==============================================================================
#                           硬件检测工具 (修复版)
# ==============================================================================


def get_l3_cache_mb():
    """
    [修复版] 智能获取 L3 缓存大小
    解决了 12/13/14代 酷睿大小核架构识别错误的问题
    """
    try:
        if os.name != "nt":
            return None

        # 方法1: 尝试通过 Win32_CacheMemory (更精准，直接找 Level 3)
        try:
            cmd = 'wmic path Win32_CacheMemory where "Level=3" get InstalledSize'
            result = subprocess.check_output(cmd, shell=True).decode()
            numbers = re.findall(r"\d+", result)
            # 过滤掉小于 2048KB (2MB) 的数值，排除标题干扰和L1缓存
            valid_sizes = [int(n) for n in numbers if int(n) > 2048]
            if valid_sizes:
                return max(valid_sizes) / 1024  # 取最大值并转MB
        except:
            pass

        # 方法2: 回退到 cpu get L3CacheSize (兼容旧电脑)
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


# ==============================================================================
#                           系统工具
# ==============================================================================


def set_priority(level):
    if os.name != "nt":
        return
    try:
        import ctypes

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
    """
    设置当前进程的 CPU 亲和性 (绑核)
    """
    if not core_list:
        return

    try:
        # Windows 绑核逻辑
        if os.name == "nt":
            import ctypes

            # 计算掩码: Core 0=1, Core 1=2, Core 2=4 ...
            mask = 0
            for core in core_list:
                mask |= 1 << int(core)

            pid = os.getpid()
            # 0x001F0FFF = PROCESS_ALL_ACCESS
            handle = ctypes.windll.kernel32.OpenProcess(0x001F0FFF, False, pid)
            success = ctypes.windll.kernel32.SetProcessAffinityMask(handle, mask)
            ctypes.windll.kernel32.CloseHandle(handle)
            if success:
                # print(f"[System] PID {pid} 成功绑定至核: {core_list}")
                pass
            else:
                print(f"[警告] PID {pid} 绑核失败")

        # Linux 绑核逻辑 (备用)
        elif hasattr(os, "sched_setaffinity"):
            os.sched_setaffinity(0, core_list)

    except Exception as e:
        print(f"[错误] 绑核操作异常: {e}")


def save_debug_screenshot():
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            img = np.array(sct_img)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            x = WHITE_DETECTION_RECT["left"] - monitor["left"]
            y = WHITE_DETECTION_RECT["top"] - monitor["top"]
            w = WHITE_DETECTION_RECT["width"]
            h = WHITE_DETECTION_RECT["height"]
            if 0 <= x < img.shape[1] and 0 <= y < img.shape[0]:
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.putText(
                    img,
                    "White Check",
                    (x, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    1,
                )

            lx = LOADING_SCAN_AREA["left"] - monitor["left"]
            ly = LOADING_SCAN_AREA["top"] - monitor["top"]
            lw = LOADING_SCAN_AREA["width"]
            lh = LOADING_SCAN_AREA["height"]
            if 0 <= lx < img.shape[1] and 0 <= ly < img.shape[0]:
                cv2.rectangle(img, (lx, ly), (lx + lw, ly + lh), (255, 0, 0), 2)
                cv2.putText(
                    img,
                    "Smart Scan Area",
                    (lx, ly - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 0, 0),
                    1,
                )

            filename = time.strftime("debug_%Y%m%d_%H%M%S.png")
            cv2.imwrite(filename, img)
            print(f"\n[截图] 已保存: {filename}")
    except Exception as e:
        print(f"\n[截图] 失败: {e}")


# ==============================================================================
#                           核心引擎
# ==============================================================================


def optimized_cache_worker(flag, block_size_mb, show_monitor, core_list):
    """
    工作进程：如果指定了 core_list，则先进行绑核
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # 1. 尝试绑核
    if core_list:
        set_cpu_affinity(core_list)

    # 2. 设置优先级
    set_priority("below_normal")

    total_bytes = int(block_size_mb * 1024 * 1024)
    num_elements = int(total_bytes / 8)

    try:
        source_data = np.ones(num_elements, dtype=np.float64)
        dest_data = np.zeros(num_elements, dtype=np.float64)
    except Exception:
        return

    last_print_time = time.time()
    loop_count = 0
    accumulated_time = 0

    while True:
        if flag.value == 1:
            try:
                t0 = time.time()
                _ = np.sum(source_data)
                t1 = time.time()

                if show_monitor:
                    copy_duration = t1 - t0
                    accumulated_time += copy_duration
                    loop_count += 1

                    if time.time() - last_print_time > 2.0:
                        if accumulated_time > 0:
                            bandwidth_gb = (
                                (loop_count * block_size_mb) / 1024 / accumulated_time
                            )
                            # 如果绑核了，打印信息里可以带上
                            core_msg = (
                                f"[Cores:{','.join(map(str, core_list))}]"
                                if core_list
                                else ""
                            )
                            print(f"[监控]{core_msg} 速度:{bandwidth_gb:.1f} GB/s")

                        last_print_time = time.time()
                        loop_count = 0
                        accumulated_time = 0
            except:
                pass
        else:
            time.sleep(0.1)


class OptimizedEngine:
    def __init__(self, worker_count, block_mb, show_monitor, core_list=None):
        self.manager = multiprocessing.Manager()
        self.flag = self.manager.Value("i", 0)
        self.processes = []
        self.worker_count = max(1, worker_count)
        self.block_mb = max(1, block_mb)
        self.show_monitor = show_monitor
        self.core_list = core_list  # 绑核列表 [3, 5, 7]

    def start(self):
        core_info = str(self.core_list) if self.core_list else "自动(OS调度)"
        print(
            f"[*] 引擎启动: {self.worker_count} 线程 | Block: {self.block_mb} MB | Cores: {core_info}"
        )

        for _ in range(self.worker_count):
            p = multiprocessing.Process(
                target=optimized_cache_worker,
                args=(self.flag, self.block_mb, self.show_monitor, self.core_list),
            )
            p.daemon = True
            p.start()
            self.processes.append(p)

    def enable(self):
        if self.flag.value == 0:
            self.flag.value = 1

    def disable(self):
        if self.flag.value == 1:
            self.flag.value = 0

    def cleanup(self):
        for p in self.processes:
            if p.is_alive():
                p.terminate()


# ==============================================================================
#                           检测逻辑
# ==============================================================================

is_auto_armed = threading.Event()
is_debug_active = False
is_smart_mode = False

# 新增：预热标志，默认为 True，表示刚启动时需要预热
is_initial_warmup = True
engine = None


def check_is_loading_screen(sct):
    try:
        img = np.array(sct.grab(LOADING_SCAN_AREA))
        small_img = cv2.resize(img, (100, 100))
        hsv_img = cv2.cvtColor(small_img, cv2.COLOR_BGRA2BGR)
        hsv_img = cv2.cvtColor(hsv_img, cv2.COLOR_BGR2HSV)

        lower_dark = np.array([0, 0, 0])
        upper_dark = np.array([180, 255, 60])

        mask = cv2.inRange(hsv_img, lower_dark, upper_dark)
        ratio = cv2.countNonZero(mask) / (100 * 100)
        return ratio > LOADING_COLOR_RATIO
    except:
        return False


def smart_detection_daemon():
    sct = mss.mss()
    print(">>> 智能扫描线程启动...")
    while True:
        # 如果还在预热中，不要进行智能扫描
        if (
            is_smart_mode
            and not is_auto_armed.is_set()
            and not is_debug_active
            and not is_initial_warmup
        ):
            if check_is_loading_screen(sct):
                print("\n[智能] 识别到加载界面 -> 自动启动引擎！")
                is_auto_armed.set()
                time.sleep(2)
        time.sleep(0.5)


def detection_loop():
    sct = mss.mss()
    lower_white = np.array([245, 245, 245])
    upper_white = np.array([255, 255, 255])

    print(">>> 监控循环就绪")

    while True:
        is_auto_armed.wait()

        if not is_debug_active:
            print("[系统] 引擎介入 -> 等待E技能白框...")
            if engine:
                engine.enable()

        triggered = False

        while is_auto_armed.is_set() and not triggered:
            if is_debug_active:
                time.sleep(0.1)
                continue

            try:
                raw_img = np.array(sct.grab(WHITE_DETECTION_RECT))
                img_bgr = cv2.cvtColor(raw_img, cv2.COLOR_BGRA2BGR)
                mask = cv2.inRange(img_bgr, lower_white, upper_white)
                if cv2.countNonZero(mask) > WHITE_PIXEL_THRESHOLD:
                    triggered = True
            except Exception:
                pass

            time.sleep(0.015)

        if not is_debug_active:
            if engine:
                engine.disable()

            if triggered:
                print("[系统] 检测到E技能白框 -> 引擎休息")
            elif not is_auto_armed.is_set():
                pass

        is_auto_armed.clear()
        time.sleep(2.0)


def on_press(key):
    global is_debug_active, is_smart_mode, is_initial_warmup

    # === 新增：检测是否在预热阶段，如果是，按下特定键先结束预热 ===
    if is_initial_warmup:
        if key == START_KEY or key == AUTO_KEY:
            print(f"\n[预热] 结束预热 -> 引擎暂停，转入正常逻辑")
            if engine:
                engine.disable()
            is_initial_warmup = False
            # 注意：这里不 return，代码继续往下走，直接触发 Tab 或 F10 的功能
        elif key == RESET_KEY:
            # 重置键也应该关闭预热
            if engine:
                engine.disable()
            is_initial_warmup = False

    # === 原有逻辑 ===
    if key == START_KEY:
        if not is_debug_active and not is_auto_armed.is_set():
            print("\n[按键] 手动触发")
            is_auto_armed.set()

    if key == AUTO_KEY:
        is_smart_mode = not is_smart_mode
        status = "开启 (进图自动跑)" if is_smart_mode else "关闭 (手动按Tab)"
        print(f"\n[设置] 智能托管模式: {status}")

    if key == RESET_KEY:
        print("\n[系统] !!! 立即重置 !!!")
        if is_auto_armed.is_set():
            is_auto_armed.clear()
        if is_debug_active:
            is_debug_active = False
            print("[调试] 手动模式已关闭")
        if is_smart_mode:
            is_smart_mode = False
            print("[设置] 智能托管模式: 已强制关闭")
        # 此时 engine 可能已经被上面的 is_initial_warmup 关了，但再关一次无妨
        if engine:
            engine.disable()

    if key == DEBUG_KEY:
        # F8 如果在预热时按，逻辑上会切换 debug 状态
        if is_initial_warmup:
            is_initial_warmup = False

        is_debug_active = not is_debug_active
        if is_debug_active:
            if is_auto_armed.is_set():
                is_auto_armed.clear()
            if engine:
                engine.enable()
            print(f"\n[调试] 强制开启 (常开)")
        else:
            if engine:
                engine.disable()
            print(f"\n[调试] 关闭")

    if key == SNAPSHOT_KEY:
        threading.Thread(target=save_debug_screenshot).start()


# ==============================================================================
#                           入口 (最终逻辑)
# ==============================================================================

if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        import numpy
    except ImportError:
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=3, help="并发线程数")
    parser.add_argument("--block", type=int, default=None, help=f"单次搬运数据大小(MB)")
    parser.add_argument("--monitor", action="store_true", help="是否显示实时带宽速度")
    # 新增 cores 参数
    parser.add_argument(
        "--cores", type=str, default=None, help="指定绑定的核心，例如: 3,5,7"
    )
    args = parser.parse_args()

    # 解析 cores 参数
    parsed_cores = None
    if args.cores:
        try:
            parsed_cores = [int(x.strip()) for x in args.cores.split(",") if x.strip()]
        except ValueError:
            print("[警告] cores 参数格式错误，应为 3,5,7 格式。将忽略该参数。")
            parsed_cores = None

    # 硬件检测
    detected_l3_mb = get_l3_cache_mb()
    safe_workers = max(1, args.workers)

    final_block_size = 32
    detected_msg = "检测失败或数值异常，使用默认 32MB"

    if args.block is not None:
        final_block_size = args.block
        detected_msg = f"用户手动指定 Block={final_block_size}MB"
    elif detected_l3_mb:
        final_block_size = int(detected_l3_mb // safe_workers) + 1

        detected_msg = f"检测到 L3={detected_l3_mb:.1f}MB, Workers={safe_workers} -> 自动设定 Block={final_block_size}MB (溢出优化)"

    set_priority("high")

    print(f"代码里的 WHITE_DETECTION_RECT 的值需要自己改")
    print(f"[*] 硬件检测: {detected_msg}")
    print(f"[*] 最终配置: Workers={safe_workers} | Block={final_block_size}MB")
    if parsed_cores:
        print(f"[*] 核心绑定: {parsed_cores}")
    print(f"[*] 监控显示: {'开启' if args.monitor else '隐藏'}")
    print("-----------------------------------")
    print("【快捷键说明】")
    print(" [F10] : 开启/关闭 智能托管 (结束预热)")
    print(" [Tab] : 手动单次触发 (结束预热)")
    print(" [F12] : 重置到最初状态")
    print(" [F8]  : 强制常开")
    print(" [F9]  : 保存调试截图")
    print(" [Ctrl+C] : 完全退出脚本")
    print("-----------------------------------")

    # 传入 parsed_cores
    engine = OptimizedEngine(
        safe_workers, final_block_size, args.monitor, core_list=parsed_cores
    )
    engine.start()

    # === 修改点：启动即开启引擎进行预热 ===
    print(">>> [预热模式] 正在全速运行以清理原有缓存数据...")
    print(">>> 请按 [Tab] 或 [F10] 结束预热，并开始正常游戏流程。")
    engine.enable()
    # ==================================

    t_detect = threading.Thread(target=detection_loop, daemon=True)
    t_detect.start()

    t_smart = threading.Thread(target=smart_detection_daemon, daemon=True)
    t_smart.start()

    k_listener = keyboard.Listener(on_press=on_press)
    k_listener.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[系统] 退出...")
        if engine:
            engine.cleanup()
        os._exit(0)
