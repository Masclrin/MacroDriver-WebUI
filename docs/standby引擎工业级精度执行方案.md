# Standby 引擎工业级精度执行方案

> 版本：v1.0
> 范围：宏执行框架 3.2 简单单宏 PoC
> 目标：用 native standby 线程 + 动态单核硬绑，实现超高精度宏执行，显著降低延迟抖动

---

## 1. 背景与动机

### 1.1 现状

当前项目的高精度定时基础设施 [engine/precision.py](file:///h:/宏驱动%20webui%203.1/engine/precision.py) 已经相当完善：

- `timeBeginPeriod(1)` 全局时钟分辨率
- `CreateWaitableTimerExW` + `CREATE_WAITABLE_TIMER_HIGH_RESOLUTION` 高分辨率可等待定时器
- `WaitForSingleObject`（释放 GIL）
- QPC 时钟
- x64 原生机器码自旋（`VirtualAlloc` + 字节流）
- 三阶段 `precise_sleep_v5`：粗睡眠 → 中精度 → 混合忙等
- `AdaptiveCompensator` 自适应偏差补偿

但执行路径仍是 **Python worker 线程**：[宏执行框架3.2.py:1693](file:///h:/宏驱动%20webui%203.1/宏执行框架3.2.py#L1693-L1720) 的 `macro_worker` 在 `threading.Thread` 里调用 `execute_macro_once`，每个动作经过 Python 调度、GIL、`precise_sleep`、`send_key_sendinput` 等多层托管代码。

### 1.2 抖动来源

| 来源 | 机制 | 影响 |
|------|------|------|
| GIL 争用 | Python 字节码执行需持有 GIL，多线程切换引入微秒级抖动 | 中 |
| Python 调度 | `execute_macro_once` 循环、属性查找、异常处理 | 中 |
| `precise_sleep_v5` 三阶段切换 | Phase 1→2→3 边界处的定时器切换 | 低 |
| 线程唤醒 | `WaitForSingleObject` 唤醒后回到 Python 仍有调度延迟 | 中 |
| 系统中断 | DPC、硬件中断抢占执行核 | 高（不可控） |
| 核间迁移 | 若亲和性为多核掩码，线程在核间迁移引入缓存失效与调度抖动 | 高 |

### 1.3 目标

用 **native standby 线程**承担"时序 + 注入"全部职责，**执行段完全绕过 Python 托管运行**，把抖动压到 native 层物理极限。

---

## 2. 自我审查决策树结论

本方案经过逐层自我审查推敲，关键决策记录如下。每个决策点都给出了推荐答案与权衡理由。

### 2.1 根决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| native standby 定义 | 原生常驻线程 + 自旋待命，执行段绕过托管运行 | 工业级精度的必经之路 |
| affinity 语义 | **单核硬绑**（动态选最优 P-core） | 单核硬绑无迁移抖动，精度最高；多核掩码（0xE）允许迁移，与"超高精度"目标矛盾 |
| 落地位置 | 先在宏执行框架3.2.py 简单单宏做 PoC | 控制改动范围，快速验证极限精度 |

### 2.2 实现路径决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| native 实现方式 | **纯 Python C API（单 .c 文件）** | 与项目轻依赖风格一致，无 C++ 运行时，调试比机器码字节流可行 |
| standby 职责边界 | **时序 + 注入都由 standby 完成（全 native）** | 任何回调 Python 都会重新引入 GIL 抖动，破坏"全 native"边界 |
| 触发机制 | **预编时间线（QPC 序列）** | 精度最高，standby 自旋消费，无唤醒延迟；代价是宏必须预编译、不支持运行时分支 |
| C 扩展形态 | **源码 + 预编译混合分发** | 优先加载 .pyd，失败回退提示编译；兼顾开发与部署 |
| 集成模式 | **新增 `ENABLE_STANDBY_ENGINE` 开关**（PoC 阶段不引入 profile） | 与现有路径并存，可随时回退；不破坏现有执行逻辑 |

### 2.3 放弃的方案

| 方案 | 放弃理由 |
|------|----------|
| 多核掩码 0xE（核 1/2/3） | 允许核间迁移，迁移成本本身是抖动源；与"超高精度"目标矛盾 |
| Python daemon 线程 + Event 唤醒 | 受 GIL 约束，唤醒抖动大，达不到工业级 |
| 预热式 standby（仅优化 Phase 3） | 增量改进有限，未触及"绕过托管"核心 |
| pybind11 / Cython | 引入额外依赖，与项目纯 ctypes 风格不一致 |
| 纯机器码字节流（扩展现有 `_create_native_spin_func`） | standby 线程逻辑远比自旋复杂，机器码维护极难 |
| 全类型支持（检测节点回调 Python） | 破坏"全 native"边界，GIL 抖动重新引入 |

---

## 3. 架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│  Python 层（宏执行框架3.2.py）                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐    │
│  │ compile_macro│──▶│ timeline编译 │──▶│ submit_timeline│   │
│  │ (现有)       │   │ (新增)       │   │ (C API 调用)  │   │
│  └──────────────┘   └──────────────┘   └──────┬───────┘    │
│                                                │            │
│  ┌──────────────┐   ┌──────────────┐          │            │
│  │ macro_worker │──▶│ standby_start│──────────┘            │
│  │ (现有,加分支)│   │ (C API 调用) │                       │
│  └──────────────┘   └──────┬───────┘                       │
│                             │                               │
│  ┌──────────────┐           │                               │
│  │ get_results  │◀──────────┘ (standby 完成后 SetEvent)    │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
                              │ ctypes / Python C API
┌─────────────────────────────▼──────────────────────────────┐
│  Native 层（_standby_engine.pyd）                           │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐    │
│  │ CPU 拓扑检测 │──▶│ 选最优 P-core│──▶│ SetThreadAff │    │
│  │ (CpuSet API) │   │ (避开核0/E)  │   │ inityMask    │    │
│  └──────────────┘   └──────────────┘   └──────┬───────┘    │
│                                                │            │
│  ┌──────────────┐   ┌──────────────┐          │            │
│  │ standby 线程 │◀──│ CreateThread │──────────┘            │
│  │ (全 C 实现)  │   │ (绑核+优先级)│                       │
│  └──────┬───────┘   └──────────────┘                       │
│         │                                                    │
│         │  自旋循环：                                         │
│         │  while (QPC < target_qpc) { _mm_pause(); }       │
│         │  switch (action.type) {                           │
│         │    case KEY:   SendInput(...)                     │
│         │    case MOUSE: SendInput(...)                     │
│         │    case INTERCEPTION: interception_send(...)      │
│         │  }                                                │
│         │  record actual_qpc                                │
│         ▼                                                    │
│  ┌──────────────┐                                           │
│  │ 结果缓冲区   │ (共享内存, Python 读取)                   │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 执行时序

```
t0: Python compile_macro → compiled_macro（现有）
t1: Python timeline编译 → events[]（新增，纯 Python，无 GIL 压力）
t2: Python submit_timeline(events) → C 扩展拷贝到共享内存
t3: Python standby_start() → CreateThread + 绑核 + 优先级提升
t4: standby 线程进入自旋循环（此时 Python 可休眠或做其他事）
t5: standby 自旋到 target_qpc → SendInput/interception_send
t6: standby 消费完时间线 → SetEvent 通知 Python
t7: Python get_results() → 读取实际 QPC 记录
```

关键点：**t4~t6 之间 Python 完全不参与**，GIL 抖动被彻底消除。

---

## 4. C 扩展 API 设计

### 4.1 模块导出函数

文件：`engine/standby_engine.c` → 编译为 `_standby_engine.pyd`

```c
// 模块初始化
static PyObject* py_init(PyObject* self, PyObject* args);
//   参数: 无
//   返回: None
//   作用: 检测 CPU 拓扑、加载 interception.dll、初始化全局状态
//   幂等: 是（重复调用安全）

// 自动选择最优 P-core 并返回核心索引
static PyObject* py_auto_pick_core(PyObject* self, PyObject* args);
//   参数: 无
//   返回: int (核心索引, 如 3) 或 None (检测失败)
//   作用: 调用 GetSystemCpuSetInformation, 避开核 0 和 E-core, 选最优 P-core

// 提交预编时间线
static PyObject* py_submit_timeline(PyObject* self, PyObject* args);
//   参数: (events: list[tuple], base_offset_ns: int)
//     events 每项: (offset_ns: int, action_type: int, param1: int, param2: int, param3: int)
//     base_offset_ns: 时间线基准偏移(纳秒), 通常为 0
//   返回: int (提交的事件数) 或 -1 (失败)
//   作用: 拷贝时间线到共享内存, 计算绝对 QPC

// 启动 standby 线程
static PyObject* py_start(PyObject* self, PyObject* args);
//   参数: (core_index: int, use_interception: int)
//   返回: int (线程句柄, 0 表示失败)
//   作用: CreateThread + SetThreadAffinityMask + SetThreadPriority(TIME_CRITICAL)
//         线程函数进入自旋消费循环

// 停止 standby 线程
static PyObject* py_stop(PyObject* self, PyObject* args);
//   参数: 无
//   返回: None
//   作用: 设置停止标志, 等待线程退出, CloseHandle

// 获取执行结果
static PyObject* py_get_results(PyObject* self, PyObject* args);
//   参数: 无
//   返回: list[tuple] 每项: (target_qpc: int, actual_qpc: int, action_type: int, status: int)
//   作用: 读取共享内存中的结果缓冲区

// 获取 QPC 频率
static PyObject* py_get_qpc_frequency(PyObject* self, PyObject* args);
//   参数: 无
//   返回: int (QPC 频率, Hz)
```

### 4.2 Python 侧调用示例

```python
import _standby_engine as se

# 初始化（程序启动时一次）
se.init()
qpc_freq = se.get_qpc_frequency()
core = se.auto_pick_core()
print(f"[standby] 选定核心: CPU{core}, QPC 频率: {qpc_freq}")

# 编译时间线（宏触发时）
events = compile_to_timeline(compiled_macro)  # 新增函数
se.submit_timeline(events, 0)

# 启动 standby 线程
se.start(core, use_interception=1)

# 等待完成（standby 内部 SetEvent, Python 阻塞等待）
# ... 可通过 select/Event 机制实现

# 读取结果
results = se.get_results()
for target_qpc, actual_qpc, action_type, status in results:
    jitter_ns = (actual_qpc - target_qpc) * 1e9 / qpc_freq
    print(f"action={action_type} jitter={jitter_ns:.0f}ns status={status}")
```

---

## 5. 时间线数据结构

### 5.1 C 侧结构定义

```c
typedef enum {
    ACTION_KEY_DOWN     = 1,
    ACTION_KEY_UP       = 2,
    ACTION_MOUSE_MOVE   = 3,
    ACTION_MOUSE_DOWN   = 4,
    ACTION_MOUSE_UP     = 5,
    ACTION_MOUSE_SCROLL = 6,
    ACTION_INTERCEPTION_KEY   = 7,  // param1=vk, param2=scan, param3=down(1)/up(0)
    ACTION_INTERCEPTION_MOUSE = 8,  // param1=button, param2=x, param3=y
} ActionType;

typedef struct {
    uint64_t offset_ns;    // 距时间线起点的偏移(纳秒)
    uint8_t  action_type;  // ActionType
    uint8_t  reserved;
    uint16_t param1;       // vk / button / x
    uint16_t param2;       // scan / y
    uint16_t param3;       // flags / down_up
} TimelineEvent;

typedef struct {
    uint64_t target_qpc;   // C 扩展计算: start_qpc + offset_ns * qpc_freq / 1e9
    uint64_t actual_qpc;   // standby 线程执行时记录
    uint8_t  action_type;
    uint8_t  status;       // 0=ok, 1=sendinput_failed, 2=interception_failed
    uint16_t reserved;
} ResultEvent;
```

### 5.2 时间线缓冲区

- **时间线缓冲区**：固定大小数组，`MAX_TIMELINE_EVENTS = 200000`（与 `MAX_COMPILED_ACTIONS` 对齐）
- **结果缓冲区**：同大小，standby 线程写入，Python 读取
- **同步**：standby 线程结束后 `SetEvent`，Python 在 `WaitForSingleObject` 上阻塞

### 5.3 时间基准

采用**相对偏移 + 启动时计算绝对**策略：

1. Python 编译时间线时，每个事件存 `offset_ns`（距宏起点偏移）
2. `py_start` 调用时，C 扩展读取当前 QPC 作为 `start_qpc`
3. 对每个事件计算 `target_qpc = start_qpc + offset_ns * qpc_freq / 1e9`
4. standby 线程严格按 `target_qpc` 自旋等待

这样宏编译时不需要知道执行时刻，启动时才确定基准。

---

## 6. CPU 拓扑检测与亲和性策略

### 6.1 检测 API

使用 `GetSystemCpuSetInformation`（Windows 10+），能区分 P-core / E-core：

```c
#include <windows.h>

// 优先调用 GetSystemCpuSetInformation (Win10+)
// 回退到 GetLogicalProcessorInformationEx (Vista+)

int auto_pick_best_core() {
    // 1. 枚举所有 CPU Set
    // 2. 过滤掉 E-core (CPU_SET_EFFICIENCY_CLASS = 1)
    // 3. 过滤掉核 0 (系统核, 中断/DPC 偏好)
    // 4. 在剩余 P-core 中选索引最小的（或按 NUMA 距离选最近的）
    // 5. 返回核心索引
}
```

### 6.2 亲和性设置

```c
// standby 线程启动时
DWORD_PTR mask = (DWORD_PTR)1 << core_index;
SetThreadAffinityMask(hThread, mask);
SetThreadPriority(hThread, THREAD_PRIORITY_TIME_CRITICAL);  // 15

// 可选: 进程级软约束, 避免其他线程抢占 standby 核
// SetProcessAffinityMask(GetCurrentProcess(), all_cores_mask & ~mask);
```

### 6.3 降级策略

| 场景 | 降级方案 |
|------|----------|
| `GetSystemCpuSetInformation` 不可用（Win7/8） | 回退 `GetLogicalProcessorInformationEx`，不区分 P/E-core |
| 单核机器 | 返回核 0，standby 仍可工作但精度受限 |
| 检测失败 | 返回 `None`，Python 层回退到现有 `precise_sleep_v5` 路径 |

---

## 7. standby 线程函数流程

### 7.1 伪代码

```c
DWORD WINAPI standby_thread(LPVOID arg) {
    // 1. 绑核 + 提升优先级
    SetThreadAffinityMask(GetCurrentThread(), 1 << core_index);
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_TIME_CRITICAL);

    // 2. 可选: MMCSS Pro Audio 注入
    // AvSetMmThreadCharacteristicsW("Pro Audio", &task_index);

    // 3. 记录起点 QPC
    QueryPerformanceCounter(&start_qpc);

    // 4. 预计算每个事件的绝对 target_qpc
    for (int i = 0; i < event_count; i++) {
        timeline[i].target_qpc = start_qpc
            + (uint64_t)((double)timeline[i].offset_ns * qpc_freq / 1e9);
    }

    // 5. 自旋消费循环
    for (int i = 0; i < event_count; i++) {
        if (stop_flag) break;

        // 自旋等待到 target_qpc
        uint64_t now;
        do {
            if (stop_flag) goto done;
            QueryPerformanceCounter(&now);
            // 短自旋用 _mm_pause 降功耗, 长等待可插入 WaitForSingleObject(timer, 0)
            _mm_pause();
        } while (now < timeline[i].target_qpc);

        // 到点, 执行注入
        QueryPerformanceCounter(&results[i].actual_qpc);
        results[i].action_type = timeline[i].action_type;

        switch (timeline[i].action_type) {
            case ACTION_KEY_DOWN:
            case ACTION_KEY_UP:
                results[i].status = do_sendinput_key(...);
                break;
            case ACTION_MOUSE_MOVE:
            case ACTION_MOUSE_DOWN:
            case ACTION_MOUSE_UP:
            case ACTION_MOUSE_SCROLL:
                results[i].status = do_sendinput_mouse(...);
                break;
            case ACTION_INTERCEPTION_KEY:
                results[i].status = do_interception_key(...);
                if (results[i].status != 0) {
                    // Interception 失败, 回退 SendInput
                    results[i].status = do_sendinput_key(...);
                }
                break;
            case ACTION_INTERCEPTION_MOUSE:
                results[i].status = do_interception_mouse(...);
                if (results[i].status != 0) {
                    results[i].status = do_sendinput_mouse(...);
                }
                break;
        }
    }

done:
    // 6. 通知 Python
    SetEvent(completion_event);
    return 0;
}
```

### 7.2 自旋优化

- **短等待（< 100us）**：纯 `_mm_pause()` 自旋
- **长等待（>= 100us）**：先 `WaitForSingleObject(high_res_timer, chunk)` 粗睡眠，最后 100us 自旋
- **停止响应**：每次 `_mm_pause()` 后检查 `stop_flag`，确保 ESC 能终止

### 7.3 Interception 集成

C 扩展内部 `LoadLibrary("interception.dll")`，缓存函数指针：

```c
static HMODULE g_interception_dll = NULL;
static InterceptionContext g_interception_ctx = NULL;
static InterceptionSendProc g_interception_send = NULL;

void load_interception() {
    g_interception_dll = LoadLibrary("interception.dll");
    if (!g_interception_dll) return;
    g_interception_send = (InterceptionSendProc)GetProcAddress(
        g_interception_dll, "interception_send");
    // 创建 context...
}
```

与现有 [engine/input_interception.py](file:///h:/宏驱动%20webui%203.1/engine/input_interception.py) 的 Python 层单例**独立**，避免跨语言共享句柄。Interception 失败时 C 层自动回退 SendInput。

---

## 8. 与宏执行框架3.2.py 的集成

### 8.1 新增配置开关

在 [宏执行框架3.2.py:69](file:///h:/宏驱动%20webui%203.1/宏执行框架3.2.py#L69-L100) 配置区新增：

```python
# —— Standby 引擎（工业级精度, PoC）——
ENABLE_STANDBY_ENGINE = False        # 总开关, 默认关闭
STANDBY_USE_INTERCEPTION = True      # standby 线程是否走 Interception
STANDBY_FALLBACK_ON_FAIL = True      # C 扩展加载/初始化失败时回退到现有路径
STANDBY_MAX_EVENTS = 200000          # 时间线最大事件数
```

### 8.2 macro_worker 分支

修改 [宏执行框架3.2.py:1693](file:///h:/宏驱动%20webui%203.1/宏执行框架3.2.py#L1693-L1720) 的 `macro_worker`：

```python
def macro_worker(worker_macro_id=..., ...):
    boost_thread_priority()
    if ENABLE_PRO_AUDIO and not apply_pro_audio(True):
        print(">>> [系统] ProAudio 注入失败")

    # —— Standby 引擎分支 ——
    if ENABLE_STANDBY_ENGINE and _standby_available():
        try:
            _execute_via_standby(worker_compiled, worker_stop, worker_macro_name)
            return
        except Exception as e:
            if not STANDBY_FALLBACK_ON_FAIL:
                raise
            print(f"[standby] 执行失败, 回退到 Python 路径: {e}")

    # —— 现有 Python 执行路径（保持不变）——
    assigned_core = _pick_core_for_macro(worker_macro_id)
    if assigned_core is not None:
        try:
            set_thread_affinity(assigned_core)
        except Exception as affinity_err:
            print(f"[宏绑核] 绑定失败: {affinity_err}")

    try:
        if repeat_count > 1:
            for i in range(repeat_count):
                if worker_stop.is_set(): break
                execute_macro_once(worker_compiled, worker_stop, worker_pause, worker_macro_name)
        else:
            execute_macro_once(worker_compiled, worker_stop, worker_pause, worker_macro_name)
    finally:
        _release_core_for_macro(worker_macro_id)
        unregister_active_macro(worker_macro_id)
```

### 8.3 时间线编译函数

新增 `compile_to_timeline(compiled_macro)`，把现有的 `compiled_macro`（kd/ku/md/mu/wait/loop 扁平列表）转成 `TimelineEvent` 元组列表：

```python
def compile_to_timeline(compiled_macro):
    """把 compiled_macro 转成 standby 时间线格式。
    返回: list[tuple(offset_ns, action_type, param1, param2, param3)]
    """
    events = []
    offset_ns = 0
    for action in compiled_macro:
        # action 格式: (type, delay_ms, *params)
        action_type, delay_ms, *params = action
        offset_ns += int(delay_ms * 1_000_000)  # ms → ns

        if action_type == "kd":
            events.append((offset_ns, ACTION_KEY_DOWN, get_vk(params[0]), 0, 0))
        elif action_type == "ku":
            events.append((offset_ns, ACTION_KEY_UP, get_vk(params[0]), 0, 0))
        elif action_type == "md":
            events.append((offset_ns, ACTION_MOUSE_DOWN, params[0], 0, 0))
        elif action_type == "mu":
            events.append((offset_ns, ACTION_MOUSE_UP, params[0], 0, 0))
        elif action_type == "mv":
            events.append((offset_ns, ACTION_MOUSE_MOVE, params[0], params[1], 0))
        elif action_type == "scroll":
            events.append((offset_ns, ACTION_MOUSE_SCROLL, int(params[0]), 0, 0))
        # ... 其他动作类型
    return events
```

### 8.4 standby 执行函数

```python
def _execute_via_standby(compiled_macro, stop_event, macro_name):
    """通过 standby 引擎执行宏。"""
    import _standby_engine as se

    # 1. 编译时间线
    events = compile_to_timeline(compiled_macro)
    if len(events) > STANDBY_MAX_EVENTS:
        raise ValueError(f"时间线事件数 {len(events)} 超过上限 {STANDBY_MAX_EVENTS}")

    # 2. 选核
    core = se.auto_pick_core()
    if core is None:
        raise RuntimeError("无法检测可用 P-core")

    # 3. 提交时间线
    se.submit_timeline(events, 0)

    # 4. 启动 standby 线程
    se.start(core, 1 if STANDBY_USE_INTERCEPTION else 0)
    print(f"[standby] 启动: CPU{core}, events={len(events)}, interception={STANDBY_USE_INTERCEPTION}")

    # 5. 等待完成或停止
    #    standby 内部 SetEvent, 这里用轮询 stop_event + 检测完成标志
    while not stop_event.is_set():
        if se.is_finished():  # 新增 API: 检测是否完成
            break
        time.sleep(0.001)  # 1ms 轮询, 不影响 standby 精度
    else:
        se.stop()  # ESC 触发, 停止 standby
        return

    # 6. 读取结果
    results = se.get_results()
    qpc_freq = se.get_qpc_frequency()
    jitters = [(r[1] - r[0]) * 1e9 / qpc_freq for r in results]  # ns
    print(f"[standby] 完成: events={len(results)}, "
          f"jitter p50={statistics.median(jitters):.0f}ns, "
          f"max={max(jitters):.0f}ns")
```

### 8.5 C 扩展可用性检测

```python
_standby_engine_module = None

def _standby_available():
    global _standby_engine_module
    if _standby_engine_module is False:
        return False
    try:
        if _standby_engine_module is None:
            import _standby_engine as se
            se.init()
            _standby_engine_module = se
        return True
    except Exception as e:
        print(f"[standby] 不可用, 回退到 Python 路径: {e}")
        _standby_engine_module = False
        return False
```

---

## 9. 编译与分发

### 9.1 目录结构

```
engine/
├── precision.py              # 现有高精度定时
├── input_sendinput.py        # 现有 SendInput
├── input_interception.py     # 现有 Interception
├── standby_engine.c          # 新增: C 扩展源码
├── standby_engine.pyd        # 新增: 预编译产物 (cp311/cp312/cp313 win_amd64)
└── setup_standby.py          # 新增: 构建脚本
```

### 9.2 setup_standby.py

```python
from setuptools import setup, Extension

module = Extension(
    '_standby_engine',
    sources=['engine/standby_engine.c'],
    libraries=['user32'],           # SendInput
    # interception.dll 运行时 LoadLibrary, 不需要链接
    extra_compile_args=['/O2', '/GL', '/GS-'],  # MSVC 优化
)

setup(
    name='_standby_engine',
    version='1.0.0',
    ext_modules=[module],
)
```

### 9.3 构建命令

```powershell
# 需要: Visual Studio Build Tools + Python 开发头文件
python engine\setup_standby.py build_ext --inplace
```

### 9.4 预编译产物分发

仓库 `engine/` 下带预编译 `.pyd`：

| 文件名 | Python 版本 | 平台 |
|--------|-------------|------|
| `_standby_engine.cp311-win_amd64.pyd` | 3.11 | Windows x64 |
| `_standby_engine.cp312-win_amd64.pyd` | 3.12 | Windows x64 |
| `_standby_engine.cp313-win_amd64.pyd` | 3.13 | Windows x64 |

加载逻辑：Python `import _standby_engine` 会自动按版本匹配 `.pyd`，无需手动处理。

### 9.5 PyInstaller 打包

[lite/](file:///h:/宏驱动%20webui%203.1/lite/) 打包时需包含 `.pyd` 和 `interception.dll`，在 `.spec` 文件的 `datas` / `binaries` 中添加：

```python
binaries = [
    ('engine/_standby_engine.*.pyd', 'engine'),
    ('Interception/library/x64/interception.dll', '.'),
]
```

---

## 10. 验证方法

### 10.1 软件级验证（C 扩展内部 QPC）

standby 线程记录每个事件的 `target_qpc` 和 `actual_qpc`，Python 读取后计算抖动：

```python
# 抖动指标
jitters_ns = [(r.actual_qpc - r.target_qpc) * 1e9 / qpc_freq for r in results]
p50 = statistics.median(jitters_ns)
p99 = percentile(jitters_ns, 0.99)
p999 = percentile(jitters_ns, 0.999)
max_jitter = max(jitters_ns)
```

**预期目标**（PoC 验收标准）：

| 指标 | 现有 precise_sleep_v5 | standby 引擎目标 |
|------|----------------------|-------------------|
| p50 抖动 | ~5-15 us | < 1 us |
| p99 抖动 | ~30-80 us | < 5 us |
| p99.9 抖动 | ~100-300 us | < 15 us |
| max 抖动 | ~500-2000 us | < 50 us |

### 10.2 端到端验证（HardwareEventProbe）

使用 [test/HardwareEventProbe](file:///h:/宏驱动%20webui%203.1/test/HardwareEventProbe/Program.cs)（C# .NET 8 RawInput 探针）测量从 standby 触发到硬件事件被接收的全链路延迟：

1. 启动 HardwareEventProbe.exe（监听 RawInput）
2. 触发宏，standby 发送按键
3. 探针记录接收时刻，输出 CSV
4. 对比 standby 的 `actual_qpc` 与探针接收时刻

现有测试产物在 [test/artifacts/](file:///h:/宏驱动%20webui%203.1/test/artifacts/)，可作基线对比。

### 10.3 对比测试脚本

新增 `test/测试_standby引擎对比.py`：

```python
"""
对比 standby 引擎 vs 现有 precise_sleep_v5 路径的抖动。
同一宏分别用两条路径执行 N 次, 输出统计对比表。
"""
# 1. 编译一个固定时间线的测试宏（如 100 个按键, 间隔 10ms）
# 2. 跑现有路径 100 次, 收集 jitter
# 3. 跑 standby 路径 100 次, 收集 jitter
# 4. 输出 p50/p99/p999/max 对比表
```

---

## 11. 风险与降级

### 11.1 技术风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| C 扩展编译失败（用户无 MSVC） | 中 | 无法使用 standby | 预编译 .pyd + 回退现有路径 |
| Interception 在 native 线程崩溃 | 低 | 进程崩溃 | C 层 try/catch + SendInput 回退 |
| CPU 拓扑检测异常 | 低 | 绑核失败 | 返回 None, Python 回退 |
| standby 线程无法响应 ESC | 中 | 宏无法停止 | 每次 `_mm_pause` 后检查 `stop_flag` |
| 预编时间线不支持运行时分支 | 高 | 限制宏类型 | PoC 仅支持线性宏, 复杂宏回退现有路径 |

### 11.2 降级链

```
standby 引擎 (全 native, 单核硬绑)
    ↓ C 扩展加载失败
现有 precise_sleep_v5 路径 (Python worker + 高精度定时器)
    ↓ ENABLE_LOW_CPU_EXECUTION
低占用模式 (time.sleep 分片)
```

### 11.3 已知限制

1. **仅支持线性宏**：预编时间线不支持 fork/join/race、检测节点、变量系统。PoC 阶段在 `compile_to_timeline` 中检测，遇到不支持的动作类型抛异常并回退。
2. **CPU 100% 占用**：standby 线程自旋期间占满一个核。宏执行期间该核不可用。
3. **不支持运行时调速**：`EXEC_SPEED_FACTOR` 在时间线编译时固化，执行中无法调整。
4. **不支持暂停/继续**：`pause_event` 机制在 native 层难以实现，PoC 阶段不支持。

---

## 12. 实施步骤

### 阶段 1：C 扩展骨架（最小可运行）

1. 创建 `engine/standby_engine.c`，实现模块初始化 + 6 个导出函数的空壳
2. 创建 `engine/setup_standby.py`
3. 本地编译验证 `python setup_standby.py build_ext --inplace`
4. Python 侧 `import _standby_engine` 成功

### 阶段 2：CPU 拓扑检测

1. 实现 `auto_pick_core()`：`GetSystemCpuSetInformation` + 回退
2. Python 侧验证返回的核心索引合理

### 阶段 3：standby 线程核心循环

1. 实现 `submit_timeline` + `start` + `stop`
2. standby 线程函数：自旋等待 + SendInput 键盘/鼠标
3. 实现 `get_results`，Python 读取抖动数据
4. 用 `test/调试_宏延迟测试.py` 对比验证

### 阶段 4：Interception 集成

1. C 层 `LoadLibrary("interception.dll")`
2. 实现 `ACTION_INTERCEPTION_KEY` / `ACTION_INTERCEPTION_MOUSE`
3. Interception 失败自动回退 SendInput
4. 用 HardwareEventProbe 端到端验证

### 阶段 5：宏执行框架集成

1. 新增配置开关 `ENABLE_STANDBY_ENGINE`
2. 实现 `compile_to_timeline`
3. 修改 `macro_worker` 加分支
4. 实现 `_execute_via_standby`
5. 真实宏触发测试

### 阶段 6：预编译与打包

1. 在 CI 或本地编译 cp311/cp312/cp313 win_amd64 的 .pyd
2. 更新 PyInstaller spec
3. 端到端打包验证

### 阶段 7：基准测试与文档

1. 新增 `test/测试_standby引擎对比.py`
2. 跑 100 次对比测试，输出报告
3. 根据实测数据调整自旋策略（如长等待阈值）
4. 更新本文档的预期目标表格

---

## 13. 关键文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `engine/standby_engine.c` | 新增 | C 扩展源码 |
| `engine/setup_standby.py` | 新增 | 构建脚本 |
| `engine/_standby_engine.*.pyd` | 新增 | 预编译产物 |
| `宏执行框架3.2.py` | 修改 | 加 `ENABLE_STANDBY_ENGINE` 分支 + `compile_to_timeline` |
| `test/测试_standby引擎对比.py` | 新增 | 对比基准测试 |
| `docs/standby引擎工业级精度执行方案.md` | 本文档 | 指导文档 |

---

## 14. 决策树审查遗留问题

以下问题在 PoC 验证后再决定，不阻塞阶段 1-3：

1. **多宏并发**：多个 standby 线程各绑不同 P-core，还是共享一个 standby 线程排队消费？取决于实测抖动。
2. **fork/join 支持**：是否扩展时间线格式支持并行分支？取决于 PoC 精度是否达标。
3. **运行时调速**：是否支持执行中调整 `EXEC_SPEED_FACTOR`？需要时间线动态重计算。
4. **暂停/继续**：是否在 native 层实现 `pause_event`？需要 `stop_flag` 之外的第二个标志位。
5. **MMCSS Pro Audio**：standby 线程是否也注入 Pro Audio？与 TIME_CRITICAL 优先级叠加效果待测。

---

## 附录 A：现有代码参考点

| 功能 | 文件:行号 | 说明 |
|------|-----------|------|
| 高精度定时核心 | [engine/precision.py](file:///h:/宏驱动%20webui%203.1/engine/precision.py) | `precise_sleep_v5` 三阶段 |
| 原生机器码自旋先例 | [engine/precision.py:136](file:///h:/宏驱动%20webui%203.1/engine/precision.py#L136-L163) | `_create_native_spin_func` |
| 线程优先级/亲和性 | [engine/precision.py:268](file:///h:/宏驱动%20webui%203.1/engine/precision.py#L268-L281) | `boost_thread_priority` / `set_thread_affinity` |
| 宏执行 worker | [宏执行框架3.2.py:1693](file:///h:/宏驱动%20webui%203.1/宏执行框架3.2.py#L1693-L1720) | `macro_worker` |
| 宏编译缓存 | [宏执行框架3.2.py:643](file:///h:/宏驱动%20webui%203.1/宏执行框架3.2.py#L643-L695) | `_build_compiled_macro_cache_for_all_bindings` |
| SendInput 注入 | [engine/input_sendinput.py](file:///h:/宏驱动%20webui%203.1/engine/input_sendinput.py) | `send_key_sendinput` / `send_click_sendinput` |
| Interception 注入 | [engine/input_interception.py](file:///h:/宏驱动%20webui%203.1/engine/input_interception.py) | `InterceptionContext` |
| 延迟测试脚本 | [test/调试_宏延迟测试.py](file:///h:/宏驱动%20webui%203.1/test/调试_宏延迟测试.py) | 软件级延迟测量 |
| 硬件事件探针 | [test/HardwareEventProbe/Program.cs](file:///h:/宏驱动%20webui%203.1/test/HardwareEventProbe/Program.cs) | C# RawInput 端到端测量 |
| 测试产物基线 | [test/artifacts/](file:///h:/宏驱动%20webui%203.1/test/artifacts/) | CSV 历史数据 |

---

## 附录 B：affinity 0xE 方案为何被放弃

用户最初提出 `native standby + affinity 0xE`（0xE = 核 1/2/3 多核掩码）。经自我审查后改为**单核硬绑**，理由：

1. **0xE 允许核间迁移**：`SetThreadAffinityMask(0xE)` 表示线程可在核 1/2/3 上运行，调度器可随时迁移。每次迁移引入：
   - L1/L2 缓存冷启动（~10-50 ns）
   - 调度器决策延迟（~100-500 ns）
   - 可能迁移到刚被中断抢占的核（抖动放大）
2. **单核硬绑无迁移**：`SetThreadAffinityMask(1<<n)` 把线程钉死在一个核上，零迁移成本，自旋期间缓存命中率最高。
3. **抗干扰靠进程级约束**：若担心 standby 核被其他线程抢占，用 `SetProcessAffinityMask` 把进程其他线程排除在 standby 核之外，而非让 standby 线程迁移。
4. **0xE 的"动态"语义保留**：单核硬绑的核心索引仍由 `GetSystemCpuSetInformation` 动态选择最优 P-core，只是结果是单核掩码而非多核掩码。

因此最终方案是"**动态单核硬绑**"，而非"动态多核掩码 0xE"。这是精度与抗干扰的最优折中。
