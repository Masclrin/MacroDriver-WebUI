/*
 * _standby_engine.c — 工业级精度 standby 引擎 C 扩展
 *
 * 编译: python engine\setup_standby.py build_ext --inplace
 *
 * 架构:
 *   - Python 层编译时间线 → submit_timeline 拷贝到共享内存
 *   - start() 创建 native standby 线程, 单核硬绑 + TIME_CRITICAL
 *   - standby 线程自旋消费时间线, 到点执行 SendInput / Interception
 *   - 完成后 SetEvent, Python 读取结果算抖动
 *
 * 执行段完全绕过 Python/GIL, 把抖动压到 native 层物理极限。
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <windows.h>
#include <intrin.h>
#include <stdbool.h>
#include <stdint.h>

/* ========== 常量 ========== */
#define MAX_TIMELINE_EVENTS     200000
#define STANDBY_SPIN_THRESHOLD  100     /* us: < 100us 纯自旋 */
#define STANDBY_COARSE_THRESHOLD 2000   /* us: > 2ms 用 WaitForSingleObject 粗睡眠 */

/* ActionType — 与 Python 侧 compile_to_timeline 对齐 */
#define ACT_NOP                   0   /* 无注入, 仅测时序 */
#define ACT_KEY_DOWN              1   /* SendInput key down,   p1=vk */
#define ACT_KEY_UP                2   /* SendInput key up,     p1=vk */
#define ACT_MOUSE_MOVE_REL        3   /* SendInput rel move,   p1=dx, p2=dy */
#define ACT_MOUSE_DOWN            4   /* SendInput mouse down, p1=button(1=L,2=R,3=M) */
#define ACT_MOUSE_UP              5   /* SendInput mouse up,   p1=button */
#define ACT_MOUSE_SCROLL          6   /* SendInput wheel,      p1=delta */
#define ACT_SET_CURSOR_POS        7   /* SetCursorPos,         p1=x, p2=y */
#define ACT_INTERCEPTION_KEY      8   /* Interception key,     p1=scan, p2=up(1)/down(0), p3=extended */
#define ACT_INTERCEPTION_MOUSE    9   /* Interception mouse,   p1=left(1)/right(0), p2=up(1)/down(0) */

/* status */
#define ST_OK                 0
#define ST_SENDINPUT_FAILED   1
#define ST_INTERCEPTION_FAIL  2
#define ST_SKIPPED            3

/* Interception 常量 (与 input_interception.py 对齐) */
#define IC_KEYBOARD_START   1
#define IC_KEYBOARD_END     10
#define IC_MOUSE_START      11
#define IC_MOUSE_END        20
#define IC_KEY_DOWN         0x00
#define IC_KEY_UP           0x01
#define IC_KEY_E0           0x02
#define IC_MOUSE_L_DOWN     0x001
#define IC_MOUSE_L_UP       0x002
#define IC_MOUSE_R_DOWN     0x004
#define IC_MOUSE_R_UP       0x008

/* ========== 数据结构 ========== */
typedef struct {
    uint64_t offset_ns;    /* 距时间线起点的偏移(纳秒) */
    uint32_t action_type;  /* ACT_* */
    int32_t  param1;       /* vk / button / x / dx / scan */
    int32_t  param2;       /* scan / y / dy / down_up */
    int32_t  param3;       /* flags / extended */
} TimelineEvent;           /* 24 bytes */

typedef struct {
    uint64_t target_qpc;          /* C 扩展计算 */
    uint64_t actual_qpc;          /* standby 线程到达时间点 (注入前) */
    uint64_t injection_done_qpc;  /* 注入完成时间 (注入后), 用于端到端延迟测量 */
    uint32_t action_type;
    uint32_t status;              /* ST_* */
} ResultEvent;                    /* 32 bytes */

/* Interception stroke 结构 (与 interception.h 对齐) */
#pragma pack(push, 1)
typedef struct {
    unsigned short code;
    unsigned short state;
    unsigned int   information;
} IKeyStroke;              /* 8 bytes */

typedef struct {
    unsigned short state;
    unsigned short flags;
    short          rolling;
    int            x;
    int            y;
    unsigned int   information;
} IMouseStroke;            /* 16 bytes */
#pragma pack(pop)

/* ========== 全局状态 ========== */
static uint64_t g_qpc_freq = 0;

static TimelineEvent *g_timeline = NULL;     /* 动态分配, MAX_TIMELINE_EVENTS */
static ResultEvent   *g_results  = NULL;
static volatile LONG  g_event_count = 0;
static volatile LONG  g_stop_flag   = 0;
static volatile LONG  g_finished    = 0;
static HANDLE  g_thread_handle     = NULL;
static HANDLE  g_completion_event  = NULL;
static HANDLE  g_coarse_timer      = NULL;   /* 高分辨率可等待定时器, 长等待粗睡眠 */
static int     g_selected_core     = -1;
static CRITICAL_SECTION g_exec_lock;         /* 互斥: 保证同一时刻只有一个 standby 宏 */
static bool    g_exec_lock_inited  = false;
static volatile LONG  g_lock_held  = 0;      /* 是否持有 g_exec_lock (防止 double-release) */
static volatile LONG  g_keep_pressed = 0;    /* 1=standby 线程退出时不补发抬起 (分段执行模式, 由 Python 层统一兜底释放) */

/* ========== Interception 全局 ========== */
static HMODULE g_ic_dll = NULL;
static void   *g_ic_ctx = NULL;
typedef void*  (*ic_create_context_fn)(void);
typedef void   (*ic_destroy_context_fn)(void*);
typedef int    (*ic_send_fn)(void*, int, void*, unsigned int);
typedef int    (*ic_is_keyboard_fn)(int);
typedef int    (*ic_is_mouse_fn)(int);
static ic_create_context_fn  g_ic_create_ctx  = NULL;
static ic_destroy_context_fn g_ic_destroy_ctx = NULL;
static ic_send_fn            g_ic_send        = NULL;
static ic_is_keyboard_fn     g_ic_is_keyboard = NULL;
static ic_is_mouse_fn        g_ic_is_mouse    = NULL;

static int  g_kb_devices[10];
static int  g_kb_count = 0;
static int  g_pref_kb  = -1;
static int  g_ms_devices[10];
static int  g_ms_count = 0;
static int  g_pref_ms  = -1;
static int  g_last_left_down[10];
static int  g_last_left_down_count = 0;

/* ========== 按下状态跟踪 (线程退出前补发抬起, 防止"按下未抬起") ==========
 * 场景: ESC 中断 / 异常退出时, 剩余事件被 SKIPPED, 可能跳过"抬起"动作。
 * 解法: 每次按下记录, 线程退出前统一补发抬起。
 */
#define MAX_TRACKED_KEYS 64
typedef struct {
    int code;       /* vk (SI 路径) 或 scan (IC 路径) */
    int extended;   /* IC 的 KEY_E0 标志 */
} TrackedKey;
static TrackedKey g_ic_pressed_keys[MAX_TRACKED_KEYS];  /* Interception 键盘按下表 */
static int        g_ic_pressed_count = 0;
static TrackedKey g_si_pressed_keys[MAX_TRACKED_KEYS];  /* SendInput 键盘按下表 */
static int        g_si_pressed_count = 0;
static int        g_mouse_down_mask = 0;   /* bit0=left, bit1=right, bit2=middle */
static int        g_mouse_use_ic = 0;      /* 鼠标注入方式: 1=IC, 0=SI (中键恒为 SI) */

/* Interception 冗余配置 (由 py_configure_interception 设置) */
static int g_cfg_kb_redundant             = 1;
static int g_cfg_mouse_left_down_limited  = 1;
static int g_cfg_mouse_left_down_redundant= 1;
static int g_cfg_mouse_left_up_limited    = 1;
static int g_cfg_mouse_left_up_redundant  = 2;
static int g_ic_available = 0;

/* ========== QPC 辅助 ========== */
static inline uint64_t qpc_now(void) {
    LARGE_INTEGER li;
    QueryPerformanceCounter(&li);
    return (uint64_t)li.QuadPart;
}

static inline uint64_t ns_to_qpc(uint64_t offset_ns) {
    /* offset_ns * qpc_freq / 1e9
     * offset_ns 最大约 10s = 1e10, qpc_freq 最大约 1e7, 乘积 1e17 < uint64_t 上限 1.8e19, 不会溢出 */
    return offset_ns * g_qpc_freq / 1000000000ULL;
}

/* ========== Interception 加载 ========== */
static bool ic_load(void) {
    if (g_ic_dll) return g_ic_available != 0;

    /* 尝试多个路径 */
    const char *paths[] = {
        "interception.dll",
        "Interception\\library\\x64\\interception.dll",
        ".\\Interception\\library\\x64\\interception.dll",
    };
    for (int i = 0; i < 3; i++) {
        g_ic_dll = LoadLibraryA(paths[i]);
        if (g_ic_dll) break;
    }
    if (!g_ic_dll) return false;

    g_ic_create_ctx  = (ic_create_context_fn)GetProcAddress(g_ic_dll, "interception_create_context");
    g_ic_destroy_ctx = (ic_destroy_context_fn)GetProcAddress(g_ic_dll, "interception_destroy_context");
    g_ic_send        = (ic_send_fn)GetProcAddress(g_ic_dll, "interception_send");
    g_ic_is_keyboard = (ic_is_keyboard_fn)GetProcAddress(g_ic_dll, "interception_is_keyboard");
    g_ic_is_mouse    = (ic_is_mouse_fn)GetProcAddress(g_ic_dll, "interception_is_mouse");

    if (!g_ic_create_ctx || !g_ic_send || !g_ic_is_keyboard || !g_ic_is_mouse) {
        FreeLibrary(g_ic_dll);
        g_ic_dll = NULL;
        return false;
    }

    g_ic_ctx = g_ic_create_ctx();
    if (!g_ic_ctx) {
        FreeLibrary(g_ic_dll);
        g_ic_dll = NULL;
        return false;
    }

    /* 枚举键盘设备 (1..10) */
    g_kb_count = 0;
    for (int dev = IC_KEYBOARD_START; dev <= IC_KEYBOARD_END; dev++) {
        if (g_ic_is_keyboard(dev) && g_kb_count < 10) {
            g_kb_devices[g_kb_count++] = dev;
        }
    }
    g_pref_kb = g_kb_count > 0 ? g_kb_devices[0] : -1;

    /* 枚举鼠标设备 (11..20) */
    g_ms_count = 0;
    for (int dev = IC_MOUSE_START; dev <= IC_MOUSE_END; dev++) {
        if (g_ic_is_mouse(dev) && g_ms_count < 10) {
            g_ms_devices[g_ms_count++] = dev;
        }
    }
    g_pref_ms = g_ms_count > 0 ? g_ms_devices[0] : -1;

    g_ic_available = 1;
    return true;
}

/* Interception 键盘发送 (含冗余策略复刻) */
static bool ic_send_key(int scan_code, bool down, bool extended) {
    if (!g_ic_ctx || g_pref_kb < 0) return false;

    IKeyStroke ks;
    ks.code = (unsigned short)scan_code;
    ks.state = (unsigned short)(down ? IC_KEY_DOWN : IC_KEY_UP);
    if (extended) ks.state |= IC_KEY_E0;
    ks.information = 0;

    /* 首选设备 */
    bool ok = g_ic_send(g_ic_ctx, g_pref_kb, &ks, 1) > 0;
    if (!ok) {
        /* 回退其他键盘 */
        for (int i = 0; i < g_kb_count; i++) {
            if (g_kb_devices[i] == g_pref_kb) continue;
            if (g_ic_send(g_ic_ctx, g_kb_devices[i], &ks, 1) > 0) {
                g_pref_kb = g_kb_devices[i];
                ok = true;
                break;
            }
        }
        if (!ok) return false;
    }

    /* 冗余设备 */
    int need = g_cfg_kb_redundant;
    int sent_extra = 0;
    for (int i = 0; i < g_kb_count && sent_extra < need; i++) {
        if (g_kb_devices[i] == g_pref_kb) continue;
        if (g_ic_send(g_ic_ctx, g_kb_devices[i], &ks, 1) > 0) sent_extra++;
    }
    return true;
}

/* Interception 鼠标点击发送 (含左键抗吞冗余策略复刻) */
static bool ic_send_mouse_click(bool left, bool up) {
    if (!g_ic_ctx || g_pref_ms < 0) return false;

    unsigned short state;
    if (left) state = (unsigned short)(up ? IC_MOUSE_L_UP : IC_MOUSE_L_DOWN);
    else      state = (unsigned short)(up ? IC_MOUSE_R_UP : IC_MOUSE_R_DOWN);

    IMouseStroke ms;
    ms.state = state;
    ms.flags = 0;
    ms.rolling = 0;
    ms.x = 0;
    ms.y = 0;
    ms.information = 0;

    /* 左键抬起: 优先 _last_left_down_devices + 冗余 */
    if (left && up) {
        int targets[10];
        int tcount = 0;
        /* 先加 _last_left_down */
        for (int i = 0; i < g_last_left_down_count && tcount < 10; i++) {
            targets[tcount++] = g_last_left_down[i];
        }
        if (g_cfg_mouse_left_up_limited) {
            int need = g_cfg_mouse_left_up_redundant;
            for (int i = 0; i < g_ms_count && tcount < 10; i++) {
                bool already = false;
                for (int j = 0; j < tcount; j++) if (targets[j] == g_ms_devices[i]) { already = true; break; }
                if (already) continue;
                targets[tcount++] = g_ms_devices[i];
                if (tcount >= 1 + need) break;
            }
        } else {
            for (int i = 0; i < g_ms_count && tcount < 10; i++) {
                bool already = false;
                for (int j = 0; j < tcount; j++) if (targets[j] == g_ms_devices[i]) { already = true; break; }
                if (already) continue;
                targets[tcount++] = g_ms_devices[i];
            }
        }
        bool ok = false;
        for (int i = 0; i < tcount; i++) {
            if (g_ic_send(g_ic_ctx, targets[i], &ms, 1) > 0) ok = true;
        }
        g_last_left_down_count = 0;
        return ok;
    }

    /* 按下 (左/右): 首选设备 + 回退 + 冗余 */
    int primary = g_pref_ms;
    bool ok = g_ic_send(g_ic_ctx, primary, &ms, 1) > 0;
    if (!ok) {
        for (int i = 0; i < g_ms_count; i++) {
            if (g_ms_devices[i] == primary) continue;
            if (g_ic_send(g_ic_ctx, g_ms_devices[i], &ms, 1) > 0) {
                g_pref_ms = g_ms_devices[i];
                primary = g_ms_devices[i];
                ok = true;
                break;
            }
        }
        if (!ok) return false;
    }

    /* 左键按下: 记录设备 + 冗余 */
    if (left && !up) {
        g_last_left_down_count = 0;
        g_last_left_down[g_last_left_down_count++] = primary;
        if (g_cfg_mouse_left_down_limited) {
            int need = g_cfg_mouse_left_down_redundant;
            int sent_extra = 0;
            for (int i = 0; i < g_ms_count && sent_extra < need; i++) {
                if (g_ms_devices[i] == primary) continue;
                if (g_ic_send(g_ic_ctx, g_ms_devices[i], &ms, 1) > 0) {
                    if (g_last_left_down_count < 10)
                        g_last_left_down[g_last_left_down_count++] = g_ms_devices[i];
                    sent_extra++;
                }
            }
        } else {
            for (int i = 0; i < g_ms_count; i++) {
                if (g_ms_devices[i] == primary) continue;
                if (g_ic_send(g_ic_ctx, g_ms_devices[i], &ms, 1) > 0) {
                    if (g_last_left_down_count < 10)
                        g_last_left_down[g_last_left_down_count++] = g_ms_devices[i];
                }
            }
        }
    }
    return true;
}

/* ========== SendInput 发送 ========== */
static bool si_send_key(int vk, bool down) {
    INPUT in;
    ZeroMemory(&in, sizeof(INPUT));
    in.type = INPUT_KEYBOARD;
    in.ki.wVk = (WORD)vk;
    in.ki.wScan = (WORD)MapVirtualKeyA((UINT)vk, 0);
    in.ki.dwFlags = down ? 0 : KEYEVENTF_KEYUP;
    return SendInput(1, &in, sizeof(INPUT)) > 0;
}

static bool si_send_mouse_move(int dx, int dy) {
    INPUT in;
    ZeroMemory(&in, sizeof(INPUT));
    in.type = INPUT_MOUSE;
    in.mi.dx = dx;
    in.mi.dy = dy;
    in.mi.dwFlags = MOUSEEVENTF_MOVE;
    return SendInput(1, &in, sizeof(INPUT)) > 0;
}

static bool si_send_mouse_button(int button, bool down) {
    INPUT in;
    ZeroMemory(&in, sizeof(INPUT));
    in.type = INPUT_MOUSE;
    DWORD flag;
    if (button == 1)      flag = down ? MOUSEEVENTF_LEFTDOWN   : MOUSEEVENTF_LEFTUP;
    else if (button == 2) flag = down ? MOUSEEVENTF_RIGHTDOWN  : MOUSEEVENTF_RIGHTUP;
    else                  flag = down ? MOUSEEVENTF_MIDDLEDOWN : MOUSEEVENTF_MIDDLEUP;
    in.mi.dwFlags = flag;
    return SendInput(1, &in, sizeof(INPUT)) > 0;
}

static bool si_send_scroll(int delta) {
    INPUT in;
    ZeroMemory(&in, sizeof(INPUT));
    in.type = INPUT_MOUSE;
    in.mi.mouseData = (DWORD)delta;
    in.mi.dwFlags = MOUSEEVENTF_WHEEL;
    return SendInput(1, &in, sizeof(INPUT)) > 0;
}

static bool si_set_cursor_pos(int x, int y) {
    return SetCursorPos(x, y) != 0;
}

/* ========== 按下状态跟踪 / 退出前补发抬起 ==========
 * 防止 ESC 中断或异常导致"按下未抬起" (左键卡死、修饰键卡死等)。
 * 每次 submit_timeline 重置; 每次注入更新; standby_thread 退出前 release_all。
 */
static void track_reset(void) {
    g_ic_pressed_count = 0;
    g_si_pressed_count = 0;
    g_mouse_down_mask  = 0;
    g_mouse_use_ic     = 0;
}

/* 键盘按下状态跟踪 (use_ic: 1=Interception scan, 0=SendInput vk) */
static void track_key(int use_ic, int code, int extended, bool down) {
    TrackedKey *arr = use_ic ? g_ic_pressed_keys : g_si_pressed_keys;
    int *cnt       = use_ic ? &g_ic_pressed_count : &g_si_pressed_count;
    if (down) {
        for (int i = 0; i < *cnt; i++) {
            if (arr[i].code == code) { arr[i].extended = extended; return; }
        }
        if (*cnt < MAX_TRACKED_KEYS) {
            arr[*cnt].code     = code;
            arr[*cnt].extended = extended;
            (*cnt)++;
        }
    } else {
        for (int i = 0; i < *cnt; i++) {
            if (arr[i].code == code) {
                arr[i] = arr[*cnt - 1];
                (*cnt)--;
                return;
            }
        }
    }
}

/* 鼠标按下状态跟踪 (button: 1=L, 2=R, 3=M) */
static void track_mouse(int button, bool down, int use_ic) {
    int bit = (button == 1) ? 1 : (button == 2) ? 2 : 4;
    if (down) {
        g_mouse_down_mask |= bit;
        g_mouse_use_ic     = use_ic;   /* 记录本次鼠标注入方式 */
    } else {
        g_mouse_down_mask &= ~bit;
    }
}

/* standby 线程退出前补发所有"按下未抬起"的抬起事件。
 * 必须在线程退出路径 (done 标签) 调用, 覆盖正常完成 / ESC 中断 / 异常 三种情况。
 * 抬起是幂等的: 对已抬起的键再发抬起无害, 所以即使状态表有残留误差也安全。 */
static void release_all_pressed(void) {
    /* 鼠标抬起 (按 left → right → middle 顺序) */
    if (g_mouse_down_mask & 1) {            /* left */
        if (g_mouse_use_ic) ic_send_mouse_click(true, true);
        else                si_send_mouse_button(1, false);
    }
    if (g_mouse_down_mask & 2) {            /* right */
        if (g_mouse_use_ic) ic_send_mouse_click(false, true);
        else                si_send_mouse_button(2, false);
    }
    if (g_mouse_down_mask & 4) {            /* middle (IC 不支持中键, 恒用 SI) */
        si_send_mouse_button(3, false);
    }
    g_mouse_down_mask = 0;

    /* Interception 键盘抬起 (按 scan code) */
    for (int i = 0; i < g_ic_pressed_count; i++) {
        ic_send_key(g_ic_pressed_keys[i].code, false, g_ic_pressed_keys[i].extended);
    }
    g_ic_pressed_count = 0;

    /* SendInput 键盘抬起 (按 vk) */
    for (int i = 0; i < g_si_pressed_count; i++) {
        si_send_key(g_si_pressed_keys[i].code, false);
    }
    g_si_pressed_count = 0;
}

/* ========== CPU 拓扑检测 ========== */
/* 动态加载 GetSystemCpuSetInformation (Win10+, 旧 SDK 可能未声明) 以区分 P/E-core。
 * 回退 GetLogicalProcessorInformationEx 选最后一个非核0的核心。 */

/* SYSTEM_CPU_SET_INFORMATION 字段 (仅取我们需要的) */
typedef struct _MY_CPU_SET_INFO {
    DWORD Size;
    DWORD CpuSetId;
    DWORD Reserved;
    BYTE  Type;            /* 0=system, 1=processor(CpuSet) */
    BYTE  EfficiencyClass; /* 0=P-core, 1=E-core */
    WORD  Reserved2;
    DWORD LogicalProcessorIndex;
    WORD  ProcessorGroup;
    WORD  Reserved3;
} MY_CPU_SET_INFO;

typedef BOOL (WINAPI *GetSystemCpuSetInformation_t)(
    MY_CPU_SET_INFO*, ULONG, PULONG, HANDLE, ULONG);

static int auto_pick_best_core(void) {
    BYTE buffer[8192];

    /* 路径 1: 动态加载 GetSystemCpuSetInformation, 区分 P/E-core */
    HMODULE k32 = GetModuleHandleW(L"kernel32.dll");
    if (k32) {
        GetSystemCpuSetInformation_t pfn = (GetSystemCpuSetInformation_t)
            GetProcAddress(k32, "GetSystemCpuSetInformation");
        if (pfn) {
            ULONG needed = 0;
            pfn(NULL, 0, &needed, GetCurrentProcess(), 0);
            if (needed > 0 && needed <= sizeof(buffer)) {
                if (pfn((MY_CPU_SET_INFO*)buffer, needed, &needed, GetCurrentProcess(), 0)) {
                    int best = -1;
                    ULONG offset = 0;
                    while (offset + sizeof(MY_CPU_SET_INFO) <= needed) {
                        MY_CPU_SET_INFO *cs = (MY_CPU_SET_INFO*)(buffer + offset);
                        if (cs->Size == 0) break;
                        if (cs->Type == 1 && cs->EfficiencyClass == 0) {
                            /* P-core, 避开核 0 */
                            int idx = (int)cs->LogicalProcessorIndex;
                            if (idx != 0 && (best < 0 || idx < best)) best = idx;
                        }
                        offset += cs->Size;
                    }
                    if (best > 0) return best;
                }
            }
        }
    }

    /* 路径 2: GetLogicalProcessorInformationEx, 选最后一个非核0的核心 */
    PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX info = (PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX)buffer;
    DWORD len = sizeof(buffer);
    if (GetLogicalProcessorInformationEx(RelationProcessorCore, info, &len)) {
        BYTE *p = buffer;
        int best = -1;
        while (p < buffer + len) {
            PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX cur = (PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX)p;
            if (cur->Relationship == RelationProcessorCore && cur->Size > 0) {
                for (WORD g = 0; g < cur->Processor.GroupCount; g++) {
                    for (int b = 0; b < 64; b++) {
                        if (cur->Processor.GroupMask[g].Mask & ((KAFFINITY)1 << b)) {
                            int idx = g * 64 + b;
                            if (idx != 0 && idx > best) best = idx;
                        }
                    }
                }
            }
            if (cur->Size == 0) break;
            p += cur->Size;
        }
        if (best > 0) return best;
    }

    /* 最终回退: 核 1 */
    return 1;
}

/* ========== standby 线程 ========== */
static DWORD WINAPI standby_thread(LPVOID arg) {
    /* 1. 绑核 + 提升优先级 */
    SetThreadAffinityMask(GetCurrentThread(), (DWORD_PTR)1 << g_selected_core);
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_TIME_CRITICAL);

    /* 2. 记录起点 QPC */
    uint64_t start_qpc = qpc_now();

    /* 3. 预计算每个事件的绝对 target_qpc */
    int n = (int)g_event_count;
    for (int i = 0; i < n; i++) {
        g_timeline[i].offset_ns; /* 已存 offset_ns, 但我们需要 target_qpc 存到 results */
        g_results[i].target_qpc = start_qpc + ns_to_qpc(g_timeline[i].offset_ns);
    }

    /* 4. 自旋消费循环 */
    for (int i = 0; i < n; i++) {
        if (g_stop_flag) {
            g_results[i].status = ST_SKIPPED;
            continue;
        }

        uint64_t target = g_results[i].target_qpc;
        uint64_t now = qpc_now();

        /* 长等待优化: > 2ms 用 WaitForSingleObject 粗睡眠, 最后 100us 自旋 */
        uint64_t coarse_threshold_qpc = ns_to_qpc((uint64_t)STANDBY_COARSE_THRESHOLD * 1000);
        uint64_t spin_threshold_qpc   = ns_to_qpc((uint64_t)STANDBY_SPIN_THRESHOLD * 1000);

        if (target > now + coarse_threshold_qpc && g_coarse_timer) {
            /* 粗睡眠: 每次 sleep 到距离 target 还剩 ~2ms */
            while (1) {
                if (g_stop_flag) break;
                now = qpc_now();
                uint64_t remaining = (target > now) ? (target - now) : 0;
                if (remaining <= coarse_threshold_qpc) break;
                /* sleep 一个 chunk (留 coarse_threshold 余量) */
                uint64_t sleep_ns = (remaining - coarse_threshold_qpc) * (uint64_t)1000000000ULL / g_qpc_freq;
                if (sleep_ns < 1000000) sleep_ns = 1000000; /* 最少 1ms */
                LARGE_INTEGER due;
                due.QuadPart = -(LONGLONG)(sleep_ns / 100); /* 100ns 单位, 负值=相对 */
                SetWaitableTimer(g_coarse_timer, &due, 0, NULL, NULL, FALSE);
                WaitForSingleObject(g_coarse_timer, INFINITE);
            }
        }

        /* 中短等待: 纯自旋 + _mm_pause */
        while (1) {
            if (g_stop_flag) break;
            now = qpc_now();
            if (now >= target) break;
            _mm_pause();
        }

        if (g_stop_flag) {
            g_results[i].status = ST_SKIPPED;
            continue;
        }

        /* 到点, 记录 actual_qpc */
        g_results[i].actual_qpc = qpc_now();
        g_results[i].action_type = g_timeline[i].action_type;
        g_results[i].status = ST_OK;

        /* 执行注入 */
        int32_t p1 = g_timeline[i].param1;
        int32_t p2 = g_timeline[i].param2;
        int32_t p3 = g_timeline[i].param3;

        switch (g_timeline[i].action_type) {
            case ACT_NOP:
                /* 无注入, 仅记录时序 */
                break;
            case ACT_KEY_DOWN:
                if (!si_send_key(p1, true)) g_results[i].status = ST_SENDINPUT_FAILED;
                else track_key(0, p1, 0, true);   /* SI 按下登记 */
                break;
            case ACT_KEY_UP:
                if (!si_send_key(p1, false)) g_results[i].status = ST_SENDINPUT_FAILED;
                else track_key(0, p1, 0, false);  /* SI 抬起销账 */
                break;
            case ACT_MOUSE_MOVE_REL:
                if (!si_send_mouse_move(p1, p2)) g_results[i].status = ST_SENDINPUT_FAILED;
                break;
            case ACT_MOUSE_DOWN:
                if (!si_send_mouse_button(p1, true)) g_results[i].status = ST_SENDINPUT_FAILED;
                else track_mouse(p1, true, 0);    /* SI 鼠标按下登记 */
                break;
            case ACT_MOUSE_UP:
                if (!si_send_mouse_button(p1, false)) g_results[i].status = ST_SENDINPUT_FAILED;
                else track_mouse(p1, false, 0);   /* SI 鼠标抬起销账 */
                break;
            case ACT_MOUSE_SCROLL:
                if (!si_send_scroll(p1)) g_results[i].status = ST_SENDINPUT_FAILED;
                break;
            case ACT_SET_CURSOR_POS:
                if (!si_set_cursor_pos(p1, p2)) g_results[i].status = ST_SENDINPUT_FAILED;
                break;
            case ACT_INTERCEPTION_KEY: {
                /* p2 语义: 1=up(抬起), 0=down(按下), 与 Python 侧 compile_to_timeline 一致 */
                bool up   = (p2 != 0);
                bool ext  = (p3 != 0);
                bool ic_ok = ic_send_key(p1, !up, ext);
                if (ic_ok) {
                    track_key(1, p1, ext, !up);   /* IC 按下/抬起登记 */
                } else {
                    /* Interception 失败, 回退 SendInput (scan→vk: MAPVK_VSC_TO_VK=1) */
                    int vk = (int)MapVirtualKeyA((UINT)p1, 1);
                    if (vk == 0) vk = p1;
                    if (!si_send_key(vk, !up)) g_results[i].status = ST_INTERCEPTION_FAIL;
                    else track_key(0, vk, 0, !up);  /* 回退 SI: 按 vk 登记 */
                }
                break;
            }
            case ACT_INTERCEPTION_MOUSE: {
                bool left = (p1 != 0);
                bool up   = (p2 != 0);
                int  btn  = left ? 1 : 2;
                bool ic_ok = ic_send_mouse_click(left, up);
                if (ic_ok) {
                    track_mouse(btn, !up, 1);     /* IC 鼠标按下/抬起登记 */
                } else {
                    if (!si_send_mouse_button(btn, !up)) g_results[i].status = ST_INTERCEPTION_FAIL;
                    else track_mouse(btn, !up, 0);  /* 回退 SI: 登记 */
                }
                break;
            }
            default:
                g_results[i].status = ST_SKIPPED;
                break;
        }
        /* 记录注入完成时间 (端到端延迟测量) */
        g_results[i].injection_done_qpc = qpc_now();
    }

    /* 5. 退出前补发所有"按下未抬起"的抬起事件。
     *    覆盖三种退出场景:
     *    - 正常完成: 宏本身可能以"按下"结尾 (如连招收尾不抬起), 这里统一补抬起
     *    - ESC 中断: 剩余事件被 SKIPPED, 抬起事件可能被跳过 → 必须补发
     *    - 异常: 同上
     *    抬起幂等, 多发无害; 不补发则会导致左键/修饰键卡死。
     *
     *    分段执行模式 (g_keep_pressed=1) 下跳过本段补发:
     *    段间按键状态需要延续到下一段 (如 "kd e → 等2帧 → ku e" 长按),
     *    若本段退出时补发抬起, 长按会被截断为短按。
     *    此时由 Python 层 (_execute_via_standby_segmented 的 finally) 统一兜底释放。 */
    if (!g_keep_pressed) {
        release_all_pressed();
    }

    /* 6. 通知 Python */
    g_finished = 1;
    if (g_completion_event) SetEvent(g_completion_event);
    return 0;
}

/* ========== Python 导出函数 ========== */

/* init() — 检测 CPU 拓扑, 加载 interception.dll, 初始化全局状态 */
static PyObject* py_init(PyObject* self, PyObject* args) {
    if (g_qpc_freq == 0) {
        LARGE_INTEGER freq;
        QueryPerformanceFrequency(&freq);
        g_qpc_freq = (uint64_t)freq.QuadPart;
    }
    if (!g_exec_lock_inited) {
        InitializeCriticalSection(&g_exec_lock);
        g_exec_lock_inited = true;
    }
    if (!g_timeline) {
        g_timeline = (TimelineEvent*)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY,
                                               sizeof(TimelineEvent) * MAX_TIMELINE_EVENTS);
    }
    if (!g_results) {
        g_results = (ResultEvent*)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY,
                                            sizeof(ResultEvent) * MAX_TIMELINE_EVENTS);
    }
    if (!g_completion_event) {
        g_completion_event = CreateEventW(NULL, TRUE, FALSE, NULL);
    }
    if (!g_coarse_timer) {
        g_coarse_timer = CreateWaitableTimerExW(NULL, NULL, CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, TIMER_ALL_ACCESS);
        if (!g_coarse_timer) g_coarse_timer = CreateWaitableTimerW(NULL, TRUE, NULL);
    }
    /* 尝试加载 Interception (失败不报错, 运行时回退 SendInput) */
    ic_load();
    Py_RETURN_NONE;
}

/* auto_pick_core() → int 或 None */
static PyObject* py_auto_pick_core(PyObject* self, PyObject* args) {
    int core = auto_pick_best_core();
    if (core < 0) Py_RETURN_NONE;
    return PyLong_FromLong(core);
}

/* submit_timeline(events: list, base_offset_ns: int) → int (事件数) 或 -1 */
static PyObject* py_submit_timeline(PyObject* self, PyObject* args) {
    PyObject* events_list;
    long long base_offset_ns;
    if (!PyArg_ParseTuple(args, "OL", &events_list, &base_offset_ns)) return NULL;

    if (!g_timeline) {
        PyErr_SetString(PyExc_RuntimeError, "standby engine not initialized");
        return NULL;
    }
    if (!PyList_Check(events_list)) {
        PyErr_SetString(PyExc_TypeError, "events must be a list");
        return NULL;
    }

    Py_ssize_t n = PyList_Size(events_list);
    if (n > MAX_TIMELINE_EVENTS) {
        PyErr_Format(PyExc_ValueError, "events count %zd exceeds max %d", n, MAX_TIMELINE_EVENTS);
        return NULL;
    }

    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject* item = PyList_GetItem(events_list, i);
        if (!PyTuple_Check(item) || PyTuple_Size(item) < 5) {
            PyErr_Format(PyExc_TypeError, "event[%zd] must be tuple(offset_ns, action_type, p1, p2, p3)", i);
            return NULL;
        }
        long long off_ns;
        int atype, p1, p2, p3;
        if (!PyArg_ParseTuple(item, "Liiii", &off_ns, &atype, &p1, &p2, &p3)) return NULL;
        g_timeline[i].offset_ns   = (uint64_t)(off_ns + base_offset_ns);
        g_timeline[i].action_type = (uint32_t)atype;
        g_timeline[i].param1      = p1;
        g_timeline[i].param2      = p2;
        g_timeline[i].param3      = p3;
    }

    g_event_count = (LONG)n;
    g_finished = 0;
    g_stop_flag = 0;
    track_reset();   /* 新宏开始: 清空按下状态表, 防止上次残留影响本次补发 */
    return PyLong_FromSsize_t(n);
}

/* start(core_index, use_interception, keep_pressed=0) → int (1=ok, 0=fail)
 * keep_pressed: 1=分段执行模式, standby 线程退出时不补发抬起, 由 Python 层统一释放 */
static PyObject* py_start(PyObject* self, PyObject* args) {
    int core, use_ic;
    int keep_pressed = 0;
    if (!PyArg_ParseTuple(args, "ii|i", &core, &use_ic, &keep_pressed)) return NULL;

    if (!g_timeline || g_event_count <= 0) {
        PyErr_SetString(PyExc_RuntimeError, "no timeline submitted");
        return NULL;
    }
    if (g_thread_handle) {
        PyErr_SetString(PyExc_RuntimeError, "standby thread already running");
        return NULL;
    }

    /* 互斥: 同一时刻只有一个 standby 宏 */
    if (!TryEnterCriticalSection(&g_exec_lock)) {
        PyErr_SetString(PyExc_RuntimeError, "another standby macro is running");
        return NULL;
    }
    g_lock_held = 1;

    g_selected_core = core;
    g_finished = 0;
    g_stop_flag = 0;
    InterlockedExchange(&g_keep_pressed, keep_pressed ? 1 : 0);
    if (g_completion_event) ResetEvent(g_completion_event);

    if (use_ic && !g_ic_available) {
        ic_load();
    }

    g_thread_handle = CreateThread(NULL, 0, standby_thread, NULL, 0, NULL);
    if (!g_thread_handle) {
        LeaveCriticalSection(&g_exec_lock);
        PyErr_SetString(PyExc_RuntimeError, "CreateThread failed");
        return NULL;
    }
    return PyLong_FromLong(1);
}

/* stop() → None */
static PyObject* py_stop(PyObject* self, PyObject* args) {
    g_stop_flag = 1;
    if (g_thread_handle) {
        Py_BEGIN_ALLOW_THREADS
        WaitForSingleObject(g_thread_handle, 2000);
        Py_END_ALLOW_THREADS
        CloseHandle(g_thread_handle);
        g_thread_handle = NULL;
    }
    if (InterlockedExchange(&g_lock_held, 0)) {
        LeaveCriticalSection(&g_exec_lock);
    }
    Py_RETURN_NONE;
}

/* is_finished() → int (0/1) */
static PyObject* py_is_finished(PyObject* self, PyObject* args) {
    return PyLong_FromLong(g_finished);
}

/* wait_completion(timeout_ms) → int (1=completed, 0=timeout) */
static PyObject* py_wait_completion(PyObject* self, PyObject* args) {
    int timeout_ms;
    if (!PyArg_ParseTuple(args, "i", &timeout_ms)) return NULL;
    if (!g_completion_event) return PyLong_FromLong(0);
    DWORD r;
    Py_BEGIN_ALLOW_THREADS
    r = WaitForSingleObject(g_completion_event, (DWORD)timeout_ms);
    Py_END_ALLOW_THREADS
    if (r == WAIT_OBJECT_0 && g_thread_handle) {
        Py_BEGIN_ALLOW_THREADS
        WaitForSingleObject(g_thread_handle, 1000);
        Py_END_ALLOW_THREADS
        CloseHandle(g_thread_handle);
        g_thread_handle = NULL;
        if (InterlockedExchange(&g_lock_held, 0)) {
            LeaveCriticalSection(&g_exec_lock);
        }
        return PyLong_FromLong(1);
    }
    return PyLong_FromLong(0);
}

/* get_results() → list of (target_qpc, actual_qpc, injection_done_qpc, action_type, status) */
static PyObject* py_get_results(PyObject* self, PyObject* args) {
    if (!g_results) return PyList_New(0);
    int n = (int)g_event_count;
    PyObject* list = PyList_New(n);
    for (int i = 0; i < n; i++) {
        PyObject* item = Py_BuildValue("(KKKII)",
            (unsigned long long)g_results[i].target_qpc,
            (unsigned long long)g_results[i].actual_qpc,
            (unsigned long long)g_results[i].injection_done_qpc,
            (unsigned int)g_results[i].action_type,
            (unsigned int)g_results[i].status);
        PyList_SET_ITEM(list, i, item);
    }
    return list;
}

/* get_qpc_frequency() → int */
static PyObject* py_get_qpc_frequency(PyObject* self, PyObject* args) {
    return PyLong_FromUnsignedLongLong((unsigned long long)g_qpc_freq);
}

/* configure_interception(kb_redundant, ms_left_down_limited, ms_left_down_redundant,
 *                        ms_left_up_limited, ms_left_up_redundant) → None */
static PyObject* py_configure_interception(PyObject* self, PyObject* args) {
    int kb_red, ms_down_lim, ms_down_red, ms_up_lim, ms_up_red;
    if (!PyArg_ParseTuple(args, "iiiii", &kb_red, &ms_down_lim, &ms_down_red, &ms_up_lim, &ms_up_red)) return NULL;
    g_cfg_kb_redundant              = kb_red;
    g_cfg_mouse_left_down_limited   = ms_down_lim;
    g_cfg_mouse_left_down_redundant = ms_down_red;
    g_cfg_mouse_left_up_limited     = ms_up_lim;
    g_cfg_mouse_left_up_redundant   = ms_up_red;
    Py_RETURN_NONE;
}

/* is_interception_available() → int (0/1) */
static PyObject* py_is_interception_available(PyObject* self, PyObject* args) {
    return PyLong_FromLong(g_ic_available);
}

/* get_interception_devices() → (kb_count, ms_count, kb_devices, ms_devices) */
static PyObject* py_get_interception_devices(PyObject* self, PyObject* args) {
    PyObject* kb_list = PyList_New(g_kb_count);
    for (int i = 0; i < g_kb_count; i++) PyList_SET_ITEM(kb_list, i, PyLong_FromLong(g_kb_devices[i]));
    PyObject* ms_list = PyList_New(g_ms_count);
    for (int i = 0; i < g_ms_count; i++) PyList_SET_ITEM(ms_list, i, PyLong_FromLong(g_ms_devices[i]));
    return Py_BuildValue("(iiOO)", g_kb_count, g_ms_count, kb_list, ms_list);
}

/* ========== 模块定义 ========== */
static PyMethodDef StandbyMethods[] = {
    {"init",                      py_init,                      METH_NOARGS,  "Initialize standby engine"},
    {"auto_pick_core",            py_auto_pick_core,            METH_NOARGS,  "Auto pick best P-core"},
    {"submit_timeline",           py_submit_timeline,           METH_VARARGS, "Submit timeline events"},
    {"start",                     py_start,                     METH_VARARGS, "Start standby thread"},
    {"stop",                      py_stop,                      METH_NOARGS,  "Stop standby thread"},
    {"is_finished",               py_is_finished,               METH_NOARGS,  "Check if finished"},
    {"wait_completion",           py_wait_completion,           METH_VARARGS, "Wait completion with timeout"},
    {"get_results",               py_get_results,               METH_NOARGS,  "Get execution results"},
    {"get_qpc_frequency",         py_get_qpc_frequency,         METH_NOARGS,  "Get QPC frequency"},
    {"configure_interception",    py_configure_interception,    METH_VARARGS, "Configure interception redundancy"},
    {"is_interception_available", py_is_interception_available, METH_NOARGS,  "Check interception availability"},
    {"get_interception_devices",  py_get_interception_devices,  METH_NOARGS,  "Get interception device lists"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef standby_module = {
    PyModuleDef_HEAD_INIT,
    "_standby_engine",
    "Industrial-grade precision standby engine",
    -1,
    StandbyMethods
};

PyMODINIT_FUNC PyInit__standby_engine(void) {
    /* 初始化 QPC 频率 */
    if (g_qpc_freq == 0) {
        LARGE_INTEGER freq;
        QueryPerformanceFrequency(&freq);
        g_qpc_freq = (uint64_t)freq.QuadPart;
    }
    if (!g_exec_lock_inited) {
        InitializeCriticalSection(&g_exec_lock);
        g_exec_lock_inited = true;
    }
    PyObject* m = PyModule_Create(&standby_module);
    if (!m) return NULL;

    /* 导出常量 */
    PyModule_AddIntConstant(m, "ACT_KEY_DOWN",             ACT_KEY_DOWN);
    PyModule_AddIntConstant(m, "ACT_KEY_UP",               ACT_KEY_UP);
    PyModule_AddIntConstant(m, "ACT_MOUSE_MOVE_REL",       ACT_MOUSE_MOVE_REL);
    PyModule_AddIntConstant(m, "ACT_MOUSE_DOWN",           ACT_MOUSE_DOWN);
    PyModule_AddIntConstant(m, "ACT_MOUSE_UP",             ACT_MOUSE_UP);
    PyModule_AddIntConstant(m, "ACT_MOUSE_SCROLL",         ACT_MOUSE_SCROLL);
    PyModule_AddIntConstant(m, "ACT_SET_CURSOR_POS",       ACT_SET_CURSOR_POS);
    PyModule_AddIntConstant(m, "ACT_INTERCEPTION_KEY",     ACT_INTERCEPTION_KEY);
    PyModule_AddIntConstant(m, "ACT_INTERCEPTION_MOUSE",   ACT_INTERCEPTION_MOUSE);
    PyModule_AddIntConstant(m, "MAX_TIMELINE_EVENTS",      MAX_TIMELINE_EVENTS);
    return m;
}
