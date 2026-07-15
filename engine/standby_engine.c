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
#include <avrt.h>
#include <mmsystem.h>
#include <intrin.h>
#include <stdbool.h>
#include <stdint.h>

#pragma comment(lib, "avrt.lib")
#pragma comment(lib, "winmm.lib")

/* NtSetTimerResolution — 未文档化 API, 动态加载 */
typedef LONG (NTAPI *NtSetTimerResolutionFn)(ULONG DesiredResolution, BOOLEAN SetResolution, PULONG CurrentResolution);

/* ProcessPowerThrottling — Win11 power throttling 控制
 * Windows SDK 10.0.26100.0 已定义 PROCESS_POWER_THROTTLING_STATE 和常量。
 * 旧 SDK 可能缺失, 此处补充常量定义 (结构体由 SDK 提供)。 */
#ifndef ProcessPowerThrottlingClass
#define ProcessPowerThrottlingClass 4
#endif
#ifndef ProcessPowerThrottlingCurrentVersion
#define ProcessPowerThrottlingCurrentVersion 1
#endif
#ifndef ProcessPowerThrottlingExecutionSpeed
#define ProcessPowerThrottlingExecutionSpeed 0x00000001
#endif
#ifndef ProcessPowerThrottlingIgnoreTimerResolution
#define ProcessPowerThrottlingIgnoreTimerResolution 0x00000004
#endif

/* ========== 常量 ========== */
#define MAX_TIMELINE_EVENTS     200000
#define STANDBY_SPIN_THRESHOLD  100     /* us: < 100us 纯自旋 */
#define STANDBY_COARSE_THRESHOLD 2000   /* us: > 2ms 用 WaitForSingleObject 粗睡眠 */

/* Config 变体: 用于拆分变量测试 */
#define CONFIG_A                 0      /* 基线: 单 worker 单核硬绑, 无 PrecisionScope */
#define CONFIG_B                 1      /* PrecisionScope 全套 (REALTIME+NtSetTimer+MMCSS+power), 无 helper */
#define CONFIG_C                 2      /* PrecisionScope + 2-worker rescue (全套, 无进程 affinity) */
#define CONFIG_D                 3      /* PrecisionScope-Lite: 仅 NtSetTimer+MMCSS+power, 不提升进程优先级 */
#define HELPER_RESCUE_DELAY_US   2      /* helper rescue delay = 2us (MacroHID) */
#define HELPER_ACTIVATE_MAX_US   2500   /* helper 仅在间隔 ≤ 2.5ms 时激活 */
#define PROCESS_AFFINITY_MASK    0xE    /* 进程级 affinity: 核 1/2/3 (核 0 留给系统) */

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
#define ACT_RTSS_WAIT_FRAMES     10   /* RTSS 帧等待,          p1=帧数; 完成后重置 base_qpc 为帧对齐瞬间 */

/* status */
#define ST_OK                 0
#define ST_SENDINPUT_FAILED   1
#define ST_INTERCEPTION_FAIL  2
#define ST_SKIPPED            3
#define ST_SEGMENT_START      0x80000000u  /* 高位标记: 段起点事件 (ACT_RTSS_WAIT_FRAMES 后的首个事件) */

/* RTSS 共享内存常量 */
#define RTSS_MAP_NAME         L"RTSSSharedMemoryV2"
#define RTSS_SIGNATURE        0x52545353u   /* 'RTSS' */
#define RTSS_MIN_VER          0x00020000u
/* entry 内字段偏移 (与 _RtssSync._current_tick 对齐) */
#define RTSS_OFF_T1           0x110u  /* t1: 帧开始 tick */
#define RTSS_OFF_FR           0x114u  /* fr: 已渲染帧数 (每帧必 +1) */
#define RTSS_OFF_FT           0x118u  /* ft: 帧时间 us */

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
static volatile LONG  g_enable_stats = 1;    /* 1=记录 actual_qpc/injection_done_qpc (Python 用于抖动统计); 0=跳过, 榨干 ~10ns 精度 */

/* ========== Config C 全局: 2-worker rescue + PrecisionScope ========== */
static int     g_config_mode = CONFIG_A;       /* 0=A 现状, 1=C MacroHID 风格 */
static int     g_helper_core = -1;             /* helper worker 绑定的核 */
static HANDLE  g_helper_thread_handle = NULL;  /* helper worker 线程句柄 */
static volatile LONG  g_helper_stop = 0;       /* helper 退出标志 */
static volatile LONG  g_generation  = 0;       /* helper 等待的代际号 (每事件 +1) */
static volatile LONG *g_batch_claims = NULL;   /* CAS 数组: 0=未claim, 1=primary, 2=helper */
static int64_t g_helper_rescue_delay_ticks = 0;/* helper rescue delay (QPC ticks, ~2us) */
static BOOL    g_precision_scope_active = FALSE; /* PrecisionScope 是否已激活 */

/* PrecisionScope 组件掩码位 (用于精细拆分测试) */
#define PS_REALTIME         0x01    /* REALTIME_PRIORITY_CLASS (进程级) */
#define PS_PROC_BOOST_OFF   0x02    /* SetProcessPriorityBoost(TRUE) 禁用 (进程级) */
#define PS_THREAD_BOOST_OFF 0x04    /* SetThreadPriorityBoost(TRUE) 禁用 (线程级) */
#define PS_NT_TIMER         0x08    /* NtSetTimerResolution(5000) 0.5ms (全局) */
#define PS_TIME_PERIOD      0x10    /* timeBeginPeriod(1) (全局) */
#define PS_MMCSS            0x20    /* AvSetMmThreadCharacteristicsW("Pro Audio") (线程级) */
#define PS_POWER_THROTTLE   0x40    /* SetProcessInformation(PowerThrottling) 禁用 (进程级) */
#define PS_ALL              0x7F    /* 全部 7 项 */
static unsigned g_precision_mask = PS_ALL;  /* 默认全套 */

/* PrecisionScope 状态保存 (RAII 还原用) */
typedef struct {
    DWORD  oldProcessPriority;
    int    oldThreadPriority;
    BOOL   prevProcessPriorityBoost;
    BOOL   prevThreadPriorityBoost;
    BOOL   processBoostCaptured;
    BOOL   threadBoostCaptured;
    HANDLE avrtHandle;
    DWORD  avrtTaskIndex;
    BOOL   avrtActive;
    ULONG  prevTimerResolution;
    BOOL   timerResolutionSet;
    BOOL   powerThrottlingDisabled;
    DWORD_PTR oldProcessAffinity;
    BOOL   processAffinitySet;
    unsigned mask;  /* 实际应用的组件掩码 */
} PrecisionScope;

static PrecisionScope g_scope = {0};

/* ========== RTSS 共享内存全局 ========== */
/* Python 层 _RtssSync.detect_entry_offset 预侦测目标游戏 entry 后, 把该 entry 的
 * 起始偏移(base)传给 C 层。C 层从 base 读取 (t1, fr, ft) 三字段指纹做帧推进检测,
 * 与 Python _RtssSync._wait_one_frame 完全一致 —— 单独比较 t1 会漏帧 (高刷新率下
 * t1 多帧不变, 但 fr 每帧必 +1)。 */
static HANDLE  g_rtss_map_handle = NULL;
static void   *g_rtss_view       = NULL;     /* MapViewOfFile 返回的指针 */
static size_t  g_rtss_entry_offset = 0;      /* 目标 entry 起始偏移 (entry base) */
static int     g_rtss_fallback_ms_per_frame = 16;  /* RTSS 不可用时的回退帧时间 */

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

/* ========== RTSS 共享内存辅助 ==========
 * 共享内存布局 (与 _RtssSync._current_tick 对齐):
 *   offset 0x00: signature (uint32, 'RTSS' = 0x52545353)
 *   offset 0x04: version   (uint32, >= 0x00020000)
 *   offset 0x08: entry_size (uint32)
 *   offset 0x0C: arr_offset (uint32, entry 数组起始偏移)
 *   offset 0x10: arr_count  (uint32, entry 数量)
 * 每个 entry:
 *   base+0x00: pid (uint32, 0=空槽)
 *   base+0x04: name[260] (char)
 *   base+0x110: t1 (uint32, 帧开始 tick)
 *   base+0x114: fr (uint32, 已渲染帧数)
 *   base+0x118: ft (uint32, 帧时间 us)
 * Python 预侦测时把目标 entry 的 (base + 0x110) 传给 C, C 直接读该地址的 t1。
 */
static bool rtss_open(void) {
    if (g_rtss_view) return true;
    HANDLE h = OpenFileMappingW(FILE_MAP_READ, FALSE, RTSS_MAP_NAME);
    if (!h) return false;
    void *view = MapViewOfFile(h, FILE_MAP_READ, 0, 0, 0);
    if (!view) {
        CloseHandle(h);
        return false;
    }
    /* 校验 signature 和 version */
    uint32_t sig = *(volatile uint32_t*)((char*)view + 0x00);
    uint32_t ver = *(volatile uint32_t*)((char*)view + 0x04);
    if (sig != RTSS_SIGNATURE || ver < RTSS_MIN_VER) {
        UnmapViewOfFile(view);
        CloseHandle(h);
        return false;
    }
    g_rtss_map_handle = h;
    g_rtss_view = view;
    return true;
}

static void rtss_close(void) {
    if (g_rtss_view) {
        UnmapViewOfFile(g_rtss_view);
        g_rtss_view = NULL;
    }
    if (g_rtss_map_handle) {
        CloseHandle(g_rtss_map_handle);
        g_rtss_map_handle = NULL;
    }
    g_rtss_entry_offset = 0;
}

/* 三字段指纹 (t1, fr, ft) —— 与 Python _RtssSync._current_tick 返回的元组对齐。
 * 任一字段变化即认为帧推进; fr 每渲染一帧必 +1, 是最稳定的推进信号。 */
typedef struct {
    uint32_t t1;
    uint32_t fr;
    uint32_t ft;
} RtssFingerprint;

/* 读取当前 entry 的三字段指纹。g_rtss_view 或 entry_offset 无效时返回 0。 */
static inline int rtss_read_fp(RtssFingerprint *out) {
    if (!g_rtss_view || g_rtss_entry_offset == 0) return 0;
    char *base = (char*)g_rtss_view + g_rtss_entry_offset;
    out->t1 = *(volatile uint32_t*)(base + RTSS_OFF_T1);
    out->fr = *(volatile uint32_t*)(base + RTSS_OFF_FR);
    out->ft = *(volatile uint32_t*)(base + RTSS_OFF_FT);
    return 1;
}

static inline int rtss_fp_eq(const RtssFingerprint *a, const RtssFingerprint *b) {
    return a->t1 == b->t1 && a->fr == b->fr && a->ft == b->ft;
}

/* fallback: RTSS 不可用或读取异常时, 按 g_rtss_fallback_ms_per_frame × n 自旋等待。
 * 返回 1=正常完成, 0=被 stop 中断。 */
static int rtss_wait_frames_fallback(int n, uint64_t *out_frame_aligned_qpc) {
    uint64_t start = qpc_now();
    uint64_t total_ns = (uint64_t)n * (uint64_t)g_rtss_fallback_ms_per_frame * 1000000ULL;
    uint64_t target = start + ns_to_qpc(total_ns);
    while (1) {
        if (g_stop_flag) return 0;
        if (qpc_now() >= target) break;
        _mm_pause();
    }
    if (out_frame_aligned_qpc) *out_frame_aligned_qpc = qpc_now();
    return 1;
}

/* RTSS 帧等待: 自旋直到指纹变化 n 次, 或 g_stop_flag 被置位。
 * 返回 1=正常完成, 0=被 stop 中断。
 * g_rtss_view 不可用或读取异常时退化到固定 ms 自旋。 */
static int rtss_wait_frames(int n, uint64_t *out_frame_aligned_qpc) {
    if (n <= 0) {
        if (out_frame_aligned_qpc) *out_frame_aligned_qpc = qpc_now();
        return 1;
    }
    if (g_rtss_view && g_rtss_entry_offset > 0) {
        RtssFingerprint last;
        if (!rtss_read_fp(&last)) {
            return rtss_wait_frames_fallback(n, out_frame_aligned_qpc);
        }
        int waited = 0;
        while (waited < n) {
            if (g_stop_flag) return 0;
            RtssFingerprint curr;
            if (!rtss_read_fp(&curr)) {
                /* 中途读取异常 → 走 fallback 完成剩余帧 */
                return rtss_wait_frames_fallback(n - waited, out_frame_aligned_qpc);
            }
            if (!rtss_fp_eq(&curr, &last)) {
                last = curr;
                waited++;
            }
            _mm_pause();
        }
    } else {
        return rtss_wait_frames_fallback(n, out_frame_aligned_qpc);
    }
    if (out_frame_aligned_qpc) *out_frame_aligned_qpc = qpc_now();
    return 1;
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

/* ========== PrecisionScope (Config C) ========== */
/* 照搬 MacroHID NativePlayback.cpp PrecisionScope RAII 模式:
 *   - REALTIME_PRIORITY_CLASS (进程级)
 *   - SetProcessPriorityBoost(TRUE) / SetThreadPriorityBoost(TRUE) 禁用 boost
 *   - NtSetTimerResolution(5000) = 0.5ms 全局时钟精度
 *   - AvSetMmThreadCharacteristicsW(L"Pro Audio") + AVRT_PRIORITY_CRITICAL (MMCSS)
 *   - SetProcessInformation(ProcessPowerThrottling) 禁用 Win11 power throttling
 *   - SetProcessAffinityMask(0xE) 进程级 affinity 限制核池
 *   - 析构时还原所有状态
 */
static void precision_scope_begin(PrecisionScope *s, BOOL lite) {
    HANDLE proc = GetCurrentProcess();
    HANDLE thread = GetCurrentThread();
    memset(s, 0, sizeof(*s));

    /* lite 模式: 仅 NtSetTimer + timeBeginPeriod + MMCSS + power throttling (跳过 REALTIME + boost 禁用) */
    unsigned mask = lite ? (PS_NT_TIMER | PS_TIME_PERIOD | PS_MMCSS | PS_POWER_THROTTLE) : g_precision_mask;
    s->mask = mask;

    /* 1. 保存旧状态 */
    s->oldProcessPriority = GetPriorityClass(proc);
    s->oldThreadPriority  = GetThreadPriority(thread);
    s->processBoostCaptured = GetProcessPriorityBoost(proc, &s->prevProcessPriorityBoost);
    s->threadBoostCaptured  = GetThreadPriorityBoost(thread, &s->prevThreadPriorityBoost);

    /* 2. 不设进程级 affinity (MacroHID 代码内也不设, 靠外部启动) */

    /* 3. 禁用 priority boost (进程 + 线程) */
    if (mask & PS_PROC_BOOST_OFF) {
        if (s->processBoostCaptured) {
            SetProcessPriorityBoost(proc, TRUE);
        }
    }
    if (mask & PS_THREAD_BOOST_OFF) {
        if (s->threadBoostCaptured) {
            SetThreadPriorityBoost(thread, TRUE);
        }
    }

    /* 4. REALTIME_PRIORITY_CLASS (进程级) */
    if (mask & PS_REALTIME) {
        SetPriorityClass(proc, REALTIME_PRIORITY_CLASS);
    }

    /* 5. THREAD_PRIORITY_TIME_CRITICAL (线程级) — 基线已设, 这里再确认 */
    SetThreadPriority(thread, THREAD_PRIORITY_TIME_CRITICAL);

    /* 6. NtSetTimerResolution(5000) = 0.5ms */
    if (mask & PS_NT_TIMER) {
        HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
        if (ntdll) {
            NtSetTimerResolutionFn pfn = (NtSetTimerResolutionFn)GetProcAddress(ntdll, "NtSetTimerResolution");
            if (pfn) {
                ULONG cur = 0;
                if (pfn(5000, TRUE, &cur) == 0) {
                    s->timerResolutionSet = TRUE;
                    s->prevTimerResolution = cur;
                }
            }
        }
    }

    /* 7. timeBeginPeriod(1) */
    if (mask & PS_TIME_PERIOD) {
        timeBeginPeriod(1);
    }

    /* 8. MMCSS Pro Audio */
    if (mask & PS_MMCSS) {
        s->avrtHandle = AvSetMmThreadCharacteristicsW(L"Pro Audio", &s->avrtTaskIndex);
        if (s->avrtHandle) {
            s->avrtActive = TRUE;
            AvSetMmThreadPriority(s->avrtHandle, AVRT_PRIORITY_CRITICAL);
        }
    }

    /* 9. 禁用 Win11 power throttling */
    if (mask & PS_POWER_THROTTLE) {
        PROCESS_POWER_THROTTLING_STATE pts;
        pts.Version = ProcessPowerThrottlingCurrentVersion;
        pts.ControlMask = ProcessPowerThrottlingExecutionSpeed | ProcessPowerThrottlingIgnoreTimerResolution;
        pts.StateMask = 0;
        if (SetProcessInformation(proc, (PROCESS_INFORMATION_CLASS)ProcessPowerThrottlingClass,
                                  &pts, sizeof(pts))) {
            s->powerThrottlingDisabled = TRUE;
        }
    }

    g_precision_scope_active = TRUE;
}

static void precision_scope_end(PrecisionScope *s, BOOL lite) {
    HANDLE proc = GetCurrentProcess();
    HANDLE thread = GetCurrentThread();
    unsigned mask = s->mask;

    /* 9. 还原 power throttling */
    if ((mask & PS_POWER_THROTTLE) && s->powerThrottlingDisabled) {
        PROCESS_POWER_THROTTLING_STATE pts;
        pts.Version = ProcessPowerThrottlingCurrentVersion;
        pts.ControlMask = ProcessPowerThrottlingExecutionSpeed | ProcessPowerThrottlingIgnoreTimerResolution;
        pts.StateMask = ProcessPowerThrottlingExecutionSpeed | ProcessPowerThrottlingIgnoreTimerResolution;
        SetProcessInformation(proc, (PROCESS_INFORMATION_CLASS)ProcessPowerThrottlingClass,
                              &pts, sizeof(pts));
    }

    /* 8. 还原 MMCSS */
    if ((mask & PS_MMCSS) && s->avrtActive && s->avrtHandle) {
        AvRevertMmThreadCharacteristics(s->avrtHandle);
    }

    /* 7. 还原 timeBeginPeriod */
    if (mask & PS_TIME_PERIOD) {
        timeEndPeriod(1);
    }

    /* 6. 还原 NtSetTimerResolution */
    if ((mask & PS_NT_TIMER) && s->timerResolutionSet) {
        HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
        if (ntdll) {
            NtSetTimerResolutionFn pfn = (NtSetTimerResolutionFn)GetProcAddress(ntdll, "NtSetTimerResolution");
            if (pfn) {
                ULONG cur = 0;
                pfn(s->prevTimerResolution, FALSE, &cur);
            }
        }
    }

    /* 5. 还原线程优先级 */
    SetThreadPriority(thread, s->oldThreadPriority);

    /* 4. 还原进程优先级 */
    if (mask & PS_REALTIME) {
        SetPriorityClass(proc, s->oldProcessPriority);
    }

    /* 3. 还原 priority boost */
    if (mask & PS_THREAD_BOOST_OFF) {
        if (s->threadBoostCaptured) {
            SetThreadPriorityBoost(thread, s->prevThreadPriorityBoost);
        }
    }
    if (mask & PS_PROC_BOOST_OFF) {
        if (s->processBoostCaptured) {
            SetProcessPriorityBoost(proc, s->prevProcessPriorityBoost);
        }
    }

    /* 2. 进程 affinity 未设置, 无需还原 */

    g_precision_scope_active = FALSE;
    memset(s, 0, sizeof(*s));
}

/* ========== helper worker 线程 (Config C) ========== */
/* 始终自旋, 等待 generation 变化后尝试 CAS rescue。
 * rescue target = primary target + g_helper_rescue_delay_ticks (~2us)。
 * CAS: InterlockedCompareExchange(&g_batch_claims[i], 2, 0) == 0 → helper 赢, 执行注入。
 * 若 primary 已 claim (CAS 失败), helper 跳过该事件。
 * helper 在另一个核上自旋, 不与 primary 竞争 CPU。 */
static DWORD WINAPI helper_thread(LPVOID arg) {
    /* helper 绑到 g_helper_core (与 primary 不同) */
    SetThreadAffinityMask(GetCurrentThread(), (DWORD_PTR)1 << g_helper_core);
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_TIME_CRITICAL);

    /* MMCSS (helper 也需要 Pro Audio 优先级) */
    DWORD avrtTaskIndex = 0;
    HANDLE avrtHandle = AvSetMmThreadCharacteristicsW(L"Pro Audio", &avrtTaskIndex);
    if (avrtHandle) {
        AvSetMmThreadPriority(avrtHandle, AVRT_PRIORITY_CRITICAL);
    }

    uint32_t seen_generation = 0;
    int n = (int)g_event_count;

    while (!g_helper_stop) {
        const uint32_t gen = (uint32_t)InterlockedCompareExchange(&g_generation, 0, 0);
        if (gen == seen_generation) {
            _mm_pause();  /* 始终自旋, 不睡眠 */
            continue;
        }
        seen_generation = gen;

        /* generation 变化 → 新事件到了, 尝试 rescue */
        int idx = (int)(gen - 1);
        if (idx < 0 || idx >= n) continue;

        /* 跳过 RTSS 帧等待事件 (helper 不参与) */
        if (g_timeline[idx].action_type == ACT_RTSS_WAIT_FRAMES) continue;

        /* 计算 rescue target: primary target + rescue delay */
        uint64_t target = 0;
        /* 与 standby_thread 相同的 target 计算 — 简化版:
         * helper 只在 dense loop (≤2.5ms) 激活, 段内 base_qpc 由 primary 维护。
         * helper 读 g_results[idx].target_qpc 获取 primary 的 target。 */
        target = g_results[idx].target_qpc + (uint64_t)g_helper_rescue_delay_ticks;

        /* 自旋等 rescue target */
        while (!g_helper_stop && !g_stop_flag) {
            uint64_t now = qpc_now();
            if (now >= target) break;
            _mm_pause();
        }
        if (g_helper_stop || g_stop_flag) break;

        /* CAS 抢占: 0→2 (helper) */
        LONG prev = InterlockedCompareExchange(&g_batch_claims[idx], 2, 0);
        if (prev != 0) {
            /* primary 已 claim, helper 跳过 */
            continue;
        }

        /* helper 赢, 执行注入 */
        g_results[idx].actual_qpc = g_enable_stats ? qpc_now() : 0;
        g_results[idx].action_type = g_timeline[idx].action_type;
        g_results[idx].status = ST_OK;

        int32_t p1 = g_timeline[idx].param1;
        int32_t p2 = g_timeline[idx].param2;
        int32_t p3 = g_timeline[idx].param3;

        switch (g_timeline[idx].action_type) {
            case ACT_NOP:
                break;
            case ACT_KEY_DOWN:
                if (!si_send_key(p1, true)) g_results[idx].status = ST_SENDINPUT_FAILED;
                else track_key(0, p1, 0, true);
                break;
            case ACT_KEY_UP:
                if (!si_send_key(p1, false)) g_results[idx].status = ST_SENDINPUT_FAILED;
                else track_key(0, p1, 0, false);
                break;
            case ACT_MOUSE_MOVE_REL:
                if (!si_send_mouse_move(p1, p2)) g_results[idx].status = ST_SENDINPUT_FAILED;
                break;
            case ACT_MOUSE_DOWN:
                if (!si_send_mouse_button(p1, true)) g_results[idx].status = ST_SENDINPUT_FAILED;
                else track_mouse(p1, true, 0);
                break;
            case ACT_MOUSE_UP:
                if (!si_send_mouse_button(p1, false)) g_results[idx].status = ST_SENDINPUT_FAILED;
                else track_mouse(p1, false, 0);
                break;
            case ACT_MOUSE_SCROLL:
                if (!si_send_scroll(p1)) g_results[idx].status = ST_SENDINPUT_FAILED;
                break;
            case ACT_SET_CURSOR_POS:
                if (!si_set_cursor_pos(p1, p2)) g_results[idx].status = ST_SENDINPUT_FAILED;
                break;
            case ACT_INTERCEPTION_KEY: {
                bool up = (p2 != 0);
                bool ext = (p3 != 0);
                bool ic_ok = ic_send_key(p1, !up, ext);
                if (ic_ok) {
                    track_key(1, p1, ext, !up);
                } else {
                    int vk = (int)MapVirtualKeyA((UINT)p1, 1);
                    if (vk == 0) vk = p1;
                    if (!si_send_key(vk, !up)) g_results[idx].status = ST_INTERCEPTION_FAIL;
                    else track_key(0, vk, 0, !up);
                }
                break;
            }
            case ACT_INTERCEPTION_MOUSE: {
                bool left = (p1 != 0);
                bool up = (p2 != 0);
                int  btn = left ? 1 : 2;
                bool ic_ok = ic_send_mouse_click(left, up);
                if (ic_ok) {
                    track_mouse(btn, !up, 1);
                } else {
                    if (!si_send_mouse_button(btn, !up)) g_results[idx].status = ST_INTERCEPTION_FAIL;
                    else track_mouse(btn, !up, 0);
                }
                break;
            }
            default:
                g_results[idx].status = ST_SKIPPED;
                break;
        }
        g_results[idx].injection_done_qpc = g_enable_stats ? qpc_now() : 0;
    }

    if (avrtHandle) {
        AvRevertMmThreadCharacteristics(avrtHandle);
    }
    return 0;
}

/* ========== standby 线程 ========== */
static DWORD WINAPI standby_thread(LPVOID arg) {
    /* 1. 绑核 + 提升优先级 */
    SetThreadAffinityMask(GetCurrentThread(), (DWORD_PTR)1 << g_selected_core);
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_TIME_CRITICAL);

    /* Config B/C/D: 应用 PrecisionScope */
    if (g_config_mode == CONFIG_B || g_config_mode == CONFIG_C) {
        precision_scope_begin(&g_scope, FALSE);  /* 全套 */
    } else if (g_config_mode == CONFIG_D) {
        precision_scope_begin(&g_scope, TRUE);   /* lite: 跳过 REALTIME + boost 禁用 */
    }
    /* Config C: helper rescue delay 转 QPC ticks */
    if (g_config_mode == CONFIG_C) {
        g_helper_rescue_delay_ticks = (int64_t)((double)g_qpc_freq * HELPER_RESCUE_DELAY_US / 1000000.0);
        if (g_helper_rescue_delay_ticks < 1) g_helper_rescue_delay_ticks = 1;
    }

    /* 2. 记录段起点 QPC (base_qpc)。
     *    初始为线程启动时刻; 遇到 ACT_RTSS_WAIT_FRAMES 后重置为帧对齐瞬间。
     *    段内事件 target = base_qpc + ns_to_qpc(offset_ns), offset_ns 是段内偏移。
     *    next_is_segment_start: 标记下一个事件为段起点 (用于段起点偏移统计)。 */
    uint64_t base_qpc = qpc_now();
    bool next_is_segment_start = false;

    int n = (int)g_event_count;

    /* 3. 自旋消费循环 (target 动态计算, 因段间 base_qpc 会重置) */
    for (int i = 0; i < n; i++) {
        if (g_stop_flag) {
            g_results[i].status = ST_SKIPPED;
            continue;
        }

        /* 3a. RTSS 帧等待事件: 自旋等 N 帧后重置 base_qpc 为帧对齐瞬间。
         *     该事件本身无注入, 仅记录时序; 完成后下一个事件标记为段起点。 */
        if (g_timeline[i].action_type == ACT_RTSS_WAIT_FRAMES) {
            uint64_t frame_aligned_qpc = 0;
            int ok = rtss_wait_frames(g_timeline[i].param1, &frame_aligned_qpc);
            if (!ok) {
                g_results[i].status = ST_SKIPPED;
                continue;
            }
            base_qpc = frame_aligned_qpc;
            g_results[i].target_qpc    = frame_aligned_qpc;
            g_results[i].actual_qpc    = frame_aligned_qpc;
            g_results[i].injection_done_qpc = frame_aligned_qpc;
            g_results[i].action_type   = ACT_RTSS_WAIT_FRAMES;
            g_results[i].status        = ST_OK;
            next_is_segment_start = true;
            continue;
        }

        /* 3b. 普通事件: target = base_qpc + offset_ns (段内偏移) */
        uint64_t target = base_qpc + ns_to_qpc(g_timeline[i].offset_ns);
        uint64_t now = qpc_now();

        /* 长等待优化: > 2ms 用 WaitForSingleObject 粗睡眠, 最后 100us 自旋 */
        uint64_t coarse_threshold_qpc = ns_to_qpc((uint64_t)STANDBY_COARSE_THRESHOLD * 1000);

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

        /* 到点, 记录 target_qpc (Config C: 必须在 generation 前写, helper 读 target_qpc) */
        g_results[i].target_qpc = target;
        g_results[i].action_type = g_timeline[i].action_type;

        /* Config C: 通知 helper + CAS claim (0→1 primary)
         * 仅在 ShouldUseRedundantWaiter: 间隔 ≤ 2500us 时激活 helper。
         * 长间隔时 helper 无价值且浪费 CPU 自旋, 不通知。 */
        bool primary_owns = true;
        if (g_config_mode == CONFIG_C) {
            int64_t interval_us = (i > 0)
                ? (int64_t)(g_timeline[i].offset_ns - g_timeline[i-1].offset_ns) / 1000
                : (int64_t)g_timeline[i].offset_ns / 1000;
            if (interval_us > 0 && interval_us <= HELPER_ACTIVATE_MAX_US) {
                InterlockedExchange(&g_generation, (LONG)(i + 1));
                LONG prev = InterlockedCompareExchange(&g_batch_claims[i], 1, 0);
                primary_owns = (prev == 0);
            }
        }

        if (primary_owns) {
            /* primary 赢, 记录 actual_qpc + 执行注入。
             * g_enable_stats=0 时跳过 qpc_now() 以榨干最后 ~10ns 精度。 */
            g_results[i].actual_qpc = g_enable_stats ? qpc_now() : 0;
            /* 段起点事件在 status 高位打标记, 供 Python 单独统计段起点偏移 */
            g_results[i].status = next_is_segment_start ? (ST_OK | ST_SEGMENT_START) : ST_OK;

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
            /* 记录注入完成时间 (端到端延迟测量)。g_enable_stats=0 时跳过。 */
            g_results[i].injection_done_qpc = g_enable_stats ? qpc_now() : 0;
        }
        /* else: helper 已抢 (CAS 失败), actual_qpc/injection_done_qpc/status 由 helper 写入,
         *       primary 不覆盖。primary 继续下一个事件。 */
        next_is_segment_start = false;
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

    /* Config C: 停止 helper */
    if (g_config_mode == CONFIG_C) {
        InterlockedExchange(&g_helper_stop, 1);
        if (g_helper_thread_handle) {
            WaitForSingleObject(g_helper_thread_handle, 2000);
            CloseHandle(g_helper_thread_handle);
            g_helper_thread_handle = NULL;
        }
    }
    /* Config B/C/D: 还原 PrecisionScope */
    if (g_config_mode == CONFIG_B || g_config_mode == CONFIG_C) {
        precision_scope_end(&g_scope, FALSE);
    } else if (g_config_mode == CONFIG_D) {
        precision_scope_end(&g_scope, TRUE);
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
    /* 尝试打开 RTSS 共享内存 (失败不报错, 段间帧等待走 fallback ms 自旋) */
    rtss_open();
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

/* set_rtss_config(entry_offset: int, fallback_ms_per_frame: int) → None
 * entry_offset: Python _RtssSync.detect_entry_offset 返回的目标 entry 起始偏移 (entry base);
 *               C 层从该偏移读 (t1, fr, ft) 三字段指纹做帧推进检测。
 *               传 0 表示让 C 层走 fallback 路径 (固定 ms 自旋)。
 * fallback_ms_per_frame: RTSS 共享内存不可用时的回退帧时间 (ms)。
 * 若共享内存尚未打开, 此处尝试打开一次。 */
static PyObject* py_set_rtss_config(PyObject* self, PyObject* args) {
    long long entry_offset;
    int fallback_ms;
    if (!PyArg_ParseTuple(args, "Li", &entry_offset, &fallback_ms)) return NULL;
    if (!g_rtss_view) rtss_open();
    g_rtss_entry_offset = (size_t)entry_offset;
    if (fallback_ms > 0) g_rtss_fallback_ms_per_frame = fallback_ms;
    Py_RETURN_NONE;
}

/* set_stats_enabled(enabled: int) → None
 * enabled=1: 记录 actual_qpc / injection_done_qpc (默认, Python 用于抖动统计)
 * enabled=0: 跳过两次 qpc_now() 调用, 榨干最后 ~10ns 注入精度 (统计关闭场景)
 * 由 Python 层根据 ENABLE_TEST_TRACE 调用: 开启测试追踪时同步开启统计,
 * 关闭时同步关闭, 既减少 QPC 开销又能在生产场景获得极致精度。 */
static PyObject* py_set_stats_enabled(PyObject* self, PyObject* args) {
    int enabled;
    if (!PyArg_ParseTuple(args, "i", &enabled)) return NULL;
    g_enable_stats = enabled ? 1 : 0;
    Py_RETURN_NONE;
}

/* set_precision_mask(mask: int) → None
 * 设置 PrecisionScope 组件掩码 (PS_REALTIME | PS_PROC_BOOST_OFF | ... | PS_ALL)。
 * 仅对后续 precision_scope_begin 生效 (CONFIG_B/C/D)。 */
static PyObject* py_set_precision_mask(PyObject* self, PyObject* args) {
    unsigned mask;
    if (!PyArg_ParseTuple(args, "I", &mask)) return NULL;
    g_precision_mask = mask;
    Py_RETURN_NONE;
}

/* submit_segmented_timeline(events: list, base_offset_ns: int) → int (事件数) 或 -1
 * 与 submit_timeline 区别: 不调 track_reset, 保留跨段按键状态。
 * 用于含 ACT_RTSS_WAIT_FRAMES 的扁平化分段时间线 (B 方案完全下沉路径)。 */
static PyObject* py_submit_segmented_timeline(PyObject* self, PyObject* args) {
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
    /* 不调 track_reset: 分段宏整体一次提交, 段间按键状态需要保留 */
    return PyLong_FromSsize_t(n);
}

/* start(core_index, use_interception, keep_pressed=0, config=0) → int (1=ok, 0=fail)
 * keep_pressed: 1=分段执行模式, standby 线程退出时不补发抬起, 由 Python 层统一释放
 * config: 0=CONFIG_A (现状单 worker), 1=CONFIG_C (0xE进程级 + 2 worker rescue + PrecisionScope 全套) */
static PyObject* py_start(PyObject* self, PyObject* args) {
    int core, use_ic;
    int keep_pressed = 0;
    int config = 0;
    if (!PyArg_ParseTuple(args, "ii|ii", &core, &use_ic, &keep_pressed, &config)) return NULL;

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
    g_config_mode = (config == CONFIG_C) ? CONFIG_C
                  : (config == CONFIG_B) ? CONFIG_B
                  : (config == CONFIG_D) ? CONFIG_D
                  : CONFIG_A;
    g_finished = 0;
    g_stop_flag = 0;
    InterlockedExchange(&g_keep_pressed, keep_pressed ? 1 : 0);
    if (g_completion_event) ResetEvent(g_completion_event);

    if (use_ic && !g_ic_available) {
        ic_load();
    }

    /* Config C: 初始化 helper 协调状态 + 创建 helper 线程 */
    if (g_config_mode == CONFIG_C) {
        /* 分配 CAS 数组 (首次使用时分配, 后续复用) */
        if (!g_batch_claims) {
            g_batch_claims = (volatile LONG*)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY,
                                                       sizeof(LONG) * MAX_TIMELINE_EVENTS);
            if (!g_batch_claims) {
                g_config_mode = CONFIG_A;
                LeaveCriticalSection(&g_exec_lock);
                PyErr_SetString(PyExc_RuntimeError, "batch_claims alloc failed");
                return NULL;
            }
        }
        /* 清零 CAS 数组 + 重置协调状态 */
        int n = (int)g_event_count;
        for (int i = 0; i < n; i++) g_batch_claims[i] = 0;
        InterlockedExchange(&g_helper_stop, 0);
        InterlockedExchange(&g_generation, 0);

        /* 选择 helper core: 在进程 affinity 池里找一个与 primary 不同的核。
         * 遍历进程可用核, 跳过 primary 和核0, 选第一个可用的。 */
        DWORD_PTR procMask = 0, sysMask2 = 0;
        GetProcessAffinityMask(GetCurrentProcess(), &procMask, &sysMask2);
        g_helper_core = -1;
        if (procMask) {
            for (int b = 0; b < 64; b++) {
                if (!(procMask & ((DWORD_PTR)1 << b))) continue;
                if (b == 0 || b == core) continue;  /* 跳过核0和primary */
                g_helper_core = b;
                break;
            }
        }
        /* 回退: 如果没找到合适的核, helper = primary (同核, rescue 无效但不崩溃) */
        if (g_helper_core < 0) g_helper_core = core;

        /* 创建 helper 线程 (在 standby_thread 之前创建, 确保 helper 就绪) */
        g_helper_thread_handle = CreateThread(NULL, 0, helper_thread, NULL, 0, NULL);
        if (!g_helper_thread_handle) {
            g_config_mode = CONFIG_A;
            LeaveCriticalSection(&g_exec_lock);
            PyErr_SetString(PyExc_RuntimeError, "helper CreateThread failed");
            return NULL;
        }
    }

    g_thread_handle = CreateThread(NULL, 0, standby_thread, NULL, 0, NULL);
    if (!g_thread_handle) {
        if (g_config_mode == CONFIG_C && g_helper_thread_handle) {
            InterlockedExchange(&g_helper_stop, 1);
            WaitForSingleObject(g_helper_thread_handle, 2000);
            CloseHandle(g_helper_thread_handle);
            g_helper_thread_handle = NULL;
        }
        g_config_mode = CONFIG_A;
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
    {"submit_segmented_timeline", py_submit_segmented_timeline, METH_VARARGS, "Submit segmented timeline (no track_reset)"},
    {"set_rtss_config",           py_set_rtss_config,           METH_VARARGS, "Set RTSS tick offset and fallback ms"},
    {"set_stats_enabled",         py_set_stats_enabled,         METH_VARARGS, "Enable/disable stats collection (actual_qpc/injection_done_qpc)"},
    {"set_precision_mask",        py_set_precision_mask,        METH_VARARGS, "Set PrecisionScope component mask (PS_REALTIME|...)"},
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
    PyModule_AddIntConstant(m, "ACT_RTSS_WAIT_FRAMES",     ACT_RTSS_WAIT_FRAMES);
    PyModule_AddIntConstant(m, "ST_SEGMENT_START",         ST_SEGMENT_START);
    PyModule_AddIntConstant(m, "MAX_TIMELINE_EVENTS",      MAX_TIMELINE_EVENTS);
    PyModule_AddIntConstant(m, "CONFIG_A",                 CONFIG_A);
    PyModule_AddIntConstant(m, "CONFIG_B",                 CONFIG_B);
    PyModule_AddIntConstant(m, "CONFIG_C",                 CONFIG_C);
    PyModule_AddIntConstant(m, "CONFIG_D",                 CONFIG_D);
    PyModule_AddIntConstant(m, "PS_REALTIME",              PS_REALTIME);
    PyModule_AddIntConstant(m, "PS_PROC_BOOST_OFF",        PS_PROC_BOOST_OFF);
    PyModule_AddIntConstant(m, "PS_THREAD_BOOST_OFF",      PS_THREAD_BOOST_OFF);
    PyModule_AddIntConstant(m, "PS_NT_TIMER",              PS_NT_TIMER);
    PyModule_AddIntConstant(m, "PS_TIME_PERIOD",           PS_TIME_PERIOD);
    PyModule_AddIntConstant(m, "PS_MMCSS",                 PS_MMCSS);
    PyModule_AddIntConstant(m, "PS_POWER_THROTTLE",        PS_POWER_THROTTLE);
    PyModule_AddIntConstant(m, "PS_ALL",                   PS_ALL);
    return m;
}
