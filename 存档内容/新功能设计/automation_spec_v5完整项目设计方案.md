# 自动化脚本引擎 V5.0 — 系统架构设计文档（完整定稿）

## 一、项目定位与设计哲学

基于现有宏驱动平台（高精度录制 + 执行引擎），构建**完全独立的自动化脚本引擎**。与旧宏系统物理隔离、各司其职。

### 1.1 核心设计哲学

**"大脑与四肢分离 + 物理隔离 + 双轨执行"**

| 层次                     | 职责                                                                                         | 对应模块                                                |
| ------------------------ | -------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| **大脑（新引擎）** | 感知（OCR/颜色/图像检测）、决策（条件判断/状态机）、调度（何时执行什么）、变量管理、并发控制 | `automation_engine.py` + `detection/`               |
| **四肢（旧引擎）** | 高精度时序执行（绝对/相对时间线、PI/前馈补偿器、输入模拟、批量发送、线程绑核）               | `宏执行框架3.2.py`（不重构，仅微调接口）              |
| **神经（原子层）** | 精确等待、WinAPI 调用、屏幕截图                                                              | `precision_engine_v5.py` + WinAPI + `mss`/`numpy` |

### 1.2 三大不可违反的原则

1. **物理隔离**：新脚本格式为 `.auto.json`，旧宏格式为 `.json`。两者不可互相执行。文件存放目录分离（`自动化脚本/` vs `宏/`）。
2. **手脚盲化**：旧引擎永远不感知窗口句柄、坐标模式、逻辑判断。它只接收**屏幕物理像素绝对坐标**和**具体动作指令**（kd/ku/md/mu/move_to/scroll/wait）。所有坐标解析在新引擎侧完成。
3. **双轨执行**：节点图中的原子动作走"路径1：新引擎直发"（零编译开销），通过 `call_script` 加载的旧格式长连招走"路径2：旧引擎托管"（完整精度）。

### 1.3 新引擎不做的事情

- 不实现误差补偿控制器（PI/前馈）—— 交给旧引擎
- 不实现批量发送优化 —— 交给旧引擎
- 不实现线程绑核/进程优先级 —— 交给旧引擎
- 不实现 Interception 驱动对接 —— 路径1 只用 SendInput/SetCursorPos，路径2 交给旧引擎
- 不实现宏录制 —— 保持旧录制系统独立

---

## 二、整体架构

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        pywebview 前端                               │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ 自动化节点编辑器   │  │ 旧块编辑器    │  │ 宏管理/录制页面       │   │
│  │ (LiteGraph.js)   │  │ (现有,保留)   │  │ (现有,保留)          │   │
│  │                  │  │              │  │                      │   │
│  │ ┌──────────────┐ │  │              │  │                      │   │
│  │ │ call_script  │ │  │              │  │                      │   │
│  │ │ 双击弹出旧    │─┼──┼─► 复用旧UI  │  │                      │   │
│  │ │ 块编辑器     │ │  │              │  │                      │   │
│  │ └──────────────┘ │  │              │  │                      │   │
│  └────────┬─────────┘  └──────┬───────┘  └──────────┬───────────┘   │
│           └────────────┬──────┘                       │              │
│                        │         JS Bridge            │              │
└────────────────────────┼──────────────────────────────┼──────────────┘
                         │                              │
                         ▼                              │
┌────────────────────────────────────────────────────────────────────┐
│                    Python 后端桥接层                                │
│                 (webui_app.py → MacroBridge)                       │
│         继承 AutomationApiMixin，暴露 JS 可调用方法                  │
└────────────────────────────┬───────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────────────┐
              │              │                      │
              ▼              │                      ▼
┌─────────────────────────┐  │          ┌─────────────────────────┐
│    新自动化调度引擎       │  │          │   旧宏执行框架           │
│   automation_engine.py  │  │          │  宏执行框架3.2.py       │
│                         │  │          │                         │
│  ┌───────────────────┐  │  │          │  - execute_macro_once() │
│  │ 流程控制/状态机    │  │  │          │  - compile_macro()      │
│  ├───────────────────┤  │  │          │  - 误差补偿器            │
│  │ 感知模块           │  │  │          │  - 批量发送              │
│  │  detection/       │  │  │          │  - Interception         │
│  ├───────────────────┤  │  │          │                         │
│  │ 动态坐标解析器     │  │  │          │                         │
│  │ coordinate_       │  │  │          │                         │
│  │ resolver.py       │  │  │          │                         │
│  ├───────────────────┤  │  │          │                         │
│  │ 变量/并发任务池    │  │  │          │                         │
│  └───────┬───────────┘  │  │          └─────────────────────────┘
│          │              │  │
│    ┌─────┴─────┐        │  │
│    │           │        │  │
│    ▼           ▼        │  │
│  路径1        路径2──────┘  │
│  新引擎直发   调用          │
│             execute_       │
│             macro_once()   │
└────┬──────────┬────────────┘
     │          │
     ▼          ▼
┌────────────────────────────────────────────────────────────────────┐
│                      底层原子能力层                                 │
│                                                                    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │ precision_       │  │ WinAPI           │  │ mss / numpy /   │  │
│  │ engine_v5.py     │  │ SendInput        │  │ RapidOCR        │  │
│  │                  │  │ SetCursorPos     │  │ OpenCV          │  │
│  │ precise_sleep_v5 │  │ MOUSEEVENTF_WHEEL│  │                 │  │
│  │ (精确等待)        │  │ (输入与定位)      │  │ (截图与检测)     │  │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

**模块职责边界表：**
| 模块 | 知道窗口吗？ | 知道坐标模式吗？ | 做条件判断吗？ | 控制时序精度吗？ |
|------|:---:|:---:|:---:|:---:|
| 新引擎 | ✅ | ✅ | ✅ | ❌（路径1用绝对时间线，无补偿） |
| 旧引擎 | ❌ | ❌ | ❌ | ✅（PI/前馈/批量/绑核） |
| 精度引擎 | ❌ | ❌ | ❌ | ✅（仅提供精确等待原语） |
| 检测模块 | ✅（按需获取hwnd） | ✅ | ❌（只返回原始结果） | ❌ |
------------------------------------------------------------------

## 三、对旧引擎的改造协议（极小侵入）

旧引擎（`宏执行框架3.2.py`）不做任何重构，仅做以下三处接口级扩展。改造后必须通过回归测试：**不传 `options` 时，所有旧宏的执行行为与改造前 100% 一致**。

### 3.1 执行函数支持动态传参

**位置**：`execute_macro_once` 函数签名
**改造内容**：增加 `options=None` 参数。函数内部涉及执行配置的变量，优先从 `options` 读取，未传入则 fallback 到全局变量。

```python
def execute_macro_once(compiled_macro, stop_event, pause_event=None,
                       macro_name="未知宏", options=None):
    # 优先级：options > 全局变量
    exec_speed = (options.get("speed_factor", EXEC_SPEED_FACTOR)
                  if options else EXEC_SPEED_FACTOR)
    timeline_mode = str(
        options.get("timeline_mode", TIMELINE_EXECUTION_MODE)
    ).lower() if options else TIMELINE_EXECUTION_MODE
    random_delay = (options.get("random_delay", ENABLE_RANDOM_DELAY_ADJUST)
                    if options else ENABLE_RANDOM_DELAY_ADJUST)
    # ... 后续所有引用这些配置的地方，使用局部变量替代全局变量 ...
```

**影响范围**：`execute_macro_once` 内部所有引用 `EXEC_SPEED_FACTOR`、`TIMELINE_EXECUTION_MODE`、`ENABLE_RANDOM_DELAY_ADJUST`、`ENABLE_RUNTIME_RANDOM_OFFSET`、`RUNTIME_RANDOM_OFFSET_MIN_MS`、`RUNTIME_RANDOM_OFFSET_MAX_MS`、`LAG_COMPENSATION_ENABLED`、`LAG_USE_PI_CONTROLLER`、`LAG_USE_FEEDFORWARD` 的位置。

### 3.2 新增动作指令解析

**位置**：`compile_macro` 内部的 `_parse` 函数，在 `if cmd == "view":` 分支之后
**新增指令**：

| 指令        | 格式                                         | 底层实现                                                  | 走 Interception？ |
| ----------- | -------------------------------------------- | --------------------------------------------------------- | :---------------: |
| `move_to` | `["move_to", phys_x, phys_y, duration_ms]` | WinAPI 分步插值移动，步间用 `precise_sleep_v5` 控制延迟 |        ❌        |
| `scroll`  | `["scroll", delta, 0]`                     | WinAPI `MOUSEEVENTF_WHEEL`                              |        ❌        |

**move_to 的插值实现**（在 `_parse` 内）

```python
if cmd == "move_to":
    target_x = int(item[1])
    target_y = int(item[2])
    dur_ms = max(0.0, float(item[3]))
    min_step_ms = 10
    max_steps = 100
    steps = max(1, min(int(dur_ms / min_step_ms), max_steps))
    step_delay_list = _split_float_duration_preserve_sum(dur_ms / 1000.0, steps)
    _reserve_actions(steps)
    result = []
    for i in range(steps):
        # 每步计算当前位置（线性插值，后续可扩展缓动）
        t = (i + 1) / steps
        cur_x = int(round(target_x * t))
        cur_y = int(round(target_y * t))
        s_del = step_delay_list[i]
        func = lambda cx=cur_x, cy=cur_y: set_cursor_pos(cx, cy)
        result.append((func, s_del, "move_to",
                       f"move_to({cx},{cy})", None))
    return result
```

**scroll 的实现**：

```python
if cmd == "scroll":
    delta = int(item[1])
    _reserve_actions(1)
    func = lambda d=delta: user32.mouse_event(0x0800, 0, 0, d, 0)
    return [(func, 0.0, "scroll", f"scroll({delta})", None)]
```

**md/mu 中键扩展**：
在现有的 `is_left = (key_name.lower() == "left")` 判断处增加：

```python
if cmd == "md":
    key_lower = key_name.lower()
    if key_lower == "middle":
        func = lambda: user32.mouse_event(0x0020, 0, 0, 0, 0)  # MOUSEEVENTF_MIDDLEDOWN
        raw_info = {"type": "mouse_click", "left": None, "middle": True, "up": False}
    elif key_lower == "left":
        func = lambda: send_mouse_click(left=True, up=False)
        raw_info = {"type": "mouse_click", "left": True, "up": False}
    else:
        func = lambda: send_mouse_click(left=False, up=False)
        raw_info = {"type": "mouse_click", "left": False, "up": False}
# mu 同理，MOUSEEVENTF_MIDDLEUP = 0x0040
```

### 3.3 修饰键释放权开关

**位置**：`execute_macro_once` 的 `finally` 块
**改造内容**：

```python
finally:
    # ... 现有的 gc.enable() 和测试追踪输出 ...
  
    # 仅在未显式关闭时释放修饰键
    should_release = (options.get("auto_release_modifiers", True)
                      if options else True)
    if should_release:
        send_key_event(get_vk("shift"), True)
        send_key_event(get_vk("ctrl"), True)
        send_key_event(get_vk("alt"), True)
        send_mouse_click(True, True)
        send_mouse_click(False, True)
```

**新引擎调用旧引擎时，强制传入 `options["auto_release_modifiers"] = False`**，释放权由新引擎统一管理。

### 3.4 回归测试要求

改造完成后，必须验证：

1. 不传 `options` 时，运行现有 `MACRO_BINDINGS` 中绑定的所有宏，行为与改造前完全一致。
2. 传入 `options={"speed_factor": 2.0}` 时，倍速生效，且不污染全局 `EXEC_SPEED_FACTOR`。
3. 传入 `options={"auto_release_modifiers": False}` 时，`finally` 块不发送修饰键释放事件。
4. `move_to` 指令在旧 JSON 宏中可直接使用，鼠标轨迹为直线插值。
5. `scroll` 指令在旧 JSON 宏中可直接使用。
6. `["md", "middle", 0]` / `["mu", "middle", 0]` 在旧 JSON 宏中可直接使用。

---

## 四、双轨执行模型

### 4.1 路径选择决策

```
节点类型？ ──► 原子动作节点 ──► 路径1：新引擎直发
           ──► call_script ──► 路径2：旧引擎托管
           ──► 检测/控制 ────► 新引擎内部处理（不走任何引擎）
```

### 4.2 路径 1：新引擎直发

**适用节点**：`mouse_click`、`key_action`、`mouse_scroll`、`text_input`、`wait`
**执行方式**：新引擎在自己的调度循环中，直接调用底层 WinAPI 函数。
**精度特征**：

| 项目         | 配置                                             |
| ------------ | ------------------------------------------------ |
| 时间线模式   | 强制 `absolute`                                |
| 误差补偿器   | 不启用（无 PI、无前馈）                          |
| 批量发送     | 不启用（每个动作独立 SendInput）                 |
| 延迟控制     | 直接调用 `precise_sleep_v5(delay, stop_event)` |
| 随机延迟修正 | 不启用（`options["random_delay"] = False`）    |
| Interception | 不使用（路径1 只用 SendInput / SetCursorPos）    |
| 精度预期     | 0.1ms ~ 0.5ms 级，完全满足自动化场景             |

**为什么路径1不启用补偿器？** 补偿器的价值在于"连续几百步动作的累计误差控制"。路径1 处理的是离散的原子动作（点击一下、按一个键），动作之间通常有检测/判断逻辑，不存在连续高密度时序需求。启用补偿器反而引入不必要的复杂度。
 **路径1 的具体调用链**：

```
mouse_click 节点执行
  │
  ├─ 1. resolve_coords(mode, x, y, hwnd) → 物理像素 (phys_x, phys_y)
  ├─ 2. set_cursor_pos(phys_x, phys_y)     ← WinAPI 直接调用
  ├─ 3. precise_sleep_v5(press_delay, stop_event)  ← 可选的按下前等待
  ├─ 4. send_mouse_click(left=True, up=False)      ← SendInput
  ├─ 5. precise_sleep_v5(hold_time, stop_event)    ← 长按支持
  └─ 6. send_mouse_click(left=True, up=True)       ← SendInput
```

### 4.3 路径 2：旧引擎托管

**适用节点**：`call_script_sync`、`call_script_async`
**执行方式**：将指定的 `.json` 文件通过 `compile_macro()` 预编译为闭包列表，然后传入 `execute_macro_once()` 执行。
**调用参数规范**：

```python
default_opts = {
    "speed_factor": 1.0,           # 从节点参数读取
    "timeline_mode": "absolute",   # 新引擎默认给绝对模式
    "random_delay": False,         # 新引擎默认关闭随机修正
    "auto_release_modifiers": False,  # 强制关闭，释放权归新引擎
}
execute_macro_once(compiled, stop_event, pause_event,
                   macro_name=name, options=default_opts)
```

**路径2 的坐标注入**：
如果旧 JSON 中包含需要动态坐标的指令（如 `move_to` 的参数需要根据当前窗口位置计算），新引擎提供两种处理方式：

- **方式A（推荐，P0实现）**：旧 JSON 中直接写死物理像素坐标。适用于窗口位置固定的场景。
- **方式B（P2实现）**：旧 JSON 中用占位符标记动态坐标（如 `["move_to", "$DYNAMIC:x", "$DYNAMIC:y", 100]`），新引擎在每次执行前扫描闭包列表，替换占位符为实时计算的物理像素。适用于窗口可能移动的场景。

### 4.4 超短动作优化

当 `call_script_sync` 加载的 JSON 编译后只有 ≤ 2 个闭包时（如单纯的按下+抬起），绕过 `execute_macro_once` 的初始化开销（GC 禁用、补偿器创建、追踪初始化等），直接在路径1的上下文中执行：

```python
if len(compiled) <= 2:
    for func, delay, _, _ in compiled:
        if stop_event.is_set(): break
        if func: func()
        if delay > 0:
            precise_sleep_v5(delay, stop_event)
else:
    execute_macro_once(compiled, stop_event, pause_event,
                       macro_name=name, options=opts)
```

---

## 五、坐标系统与动态解析

### 5.1 坐标模式定义

| 模式         | 原点                   | 输入值域                       | 适用场景                 | 示例           |
| ------------ | ---------------------- | ------------------------------ | ------------------------ | -------------- |
| `screen`   | 主屏幕左上角 `(0,0)` | 逻辑像素（与系统显示设置一致） | 固定位置的按钮、图标     | `(960, 540)` |
| `window`   | 目标窗口客户区左上角   | 逻辑像素                       | 窗口内元素，跟随窗口移动 | `(200, 100)` |
| `relative` | 窗口客户区左上角       | `0.0 ~ 1.0` 比例值           | 不同分辨率下保持相对位置 | `(0.5, 0.3)` |

### 5.2 DPI 缩放转换

所有坐标在交给 `SetCursorPos` 前，必须转换为物理像素：

```python
# 获取系统 DPI 缩放比
dpi_raw = ctypes.windll.user32.GetDpiForWindow(0)  # 0 = 桌面窗口
dpi_scale = dpi_raw / 100.0  # 如 150% → 1.5
# 逻辑像素 → 物理像素
phys_x = logic_x * dpi_scale
phys_y = logic_y * dpi_scale
```

### 5.3 多显示器坐标

```
主屏:    (0, 0) ───────────── (1920, 1080)     ← 物理像素
副屏左:  (-1920, 0) ──────── (0, 1080)         ← 在主屏左侧
副屏右:  (1920, 0) ───────── (3840, 1080)       ← 在主屏右侧
```

`screen` 模式下的坐标经 DPI 缩放后，直接传给 `SetCursorPos`，WinAPI 自动处理多显示器映射。`window` 和 `relative` 模式通过 `ClientToScreen` 获取的已经是多显示器统一的屏幕坐标。

### 5.4 区域定义格式

所有检测区域统一使用 `[x, y, width, height]` 格式：

```json
{"mode": "screen",   "rect": [100, 200, 300, 400]}   // 屏幕逻辑像素
{"mode": "window",   "rect": [100, 200, 300, 400]}   // 窗口内逻辑像素
{"mode": "relative", "rect": [0.1, 0.2, 0.3, 0.4]}   // 比例值
```

解析为物理像素区域的函数：

```python
def resolve_region(mode, rect, hwnd=None):
    """返回 (phys_x, phys_y, phys_w, phys_h) 物理像素区域"""
    dpi_scale = get_dpi_scale()
    if mode == "screen":
        return (rect[0]*dpi_scale, rect[1]*dpi_scale,
                rect[2]*dpi_scale, rect[3]*dpi_scale)
    elif mode == "window":
        cx, cy = get_window_client_origin(hwnd)  # ClientToScreen
        return (cx + rect[0]*dpi_scale, cy + rect[1]*dpi_scale,
                rect[2]*dpi_scale, rect[3]*dpi_scale)
    elif mode == "relative":
        cx, cy, cw, ch = get_window_client_rect(hwnd)
        return (cx + rect[0]*cw*dpi_scale, cy + rect[1]*ch*dpi_scale,
                rect[2]*cw*dpi_scale, rect[3]*ch*dpi_scale)
```

### 5.5 动态刷新策略（核心设计）

**问题**：用户在 loop 节点内放了一个 `mouse_click` 节点，使用 `window` 模式坐标。如果游戏窗口在循环执行期间被拖动了，坐标必须自动跟随。
**方案**：新引擎的执行器在每次循环迭代开始时，不使用"编译时一次性解析好的死坐标"，而是**实时调用 WinAPI 获取当前窗口位置**。
具体实现：节点的坐标参数在解析阶段不立即计算物理像素，而是保存原始的 `(mode, x, y, hwnd)` 四元组。执行到该节点时，调用 `resolve_coords()` 实时计算。

```python
# 解析阶段：只记录原始参数，不计算
node.params["_raw_coords"] = {"mode": "window", "x": 200, "y": 100, "hwnd": target_hwnd}
# 执行阶段：每次都实时计算
raw = node.params["_raw_coords"]
phys_x, phys_y = resolve_coords(raw["mode"], raw["x"], raw["y"], raw["hwnd"])
set_cursor_pos(phys_x, phys_y)
```

**性能考量**：`GetWindowRect` + `ClientToScreen` 的 WinAPI 调用开销约 0.01ms，在自动化场景（每步 10ms~100ms 量级）下完全可忽略。
**路径2 的动态坐标**：如果旧 JSON 块内部的 `move_to` 需要动态坐标，只能通过方式B（占位符替换）实现，且替换发生在每次循环迭代调用 `execute_macro_once` 之前。旧引擎内部的 loop 展开期间坐标是死的——这是路径2的固有限制，用户需要理解并接受。
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

## 六、并发与中断模型

### 6.1 异步动作块节点

`call_script_async` 节点的行为：

```text
主执行线程                           异步执行线程
    │                                     │
    ├── call_script_async 启动 ──────────► threading.Thread
    │   （不阻塞，立刻继续）               │   execute_macro_once()
    │                                     │   （持有独立的 stop/pause event）
    ├── monitor_color 检测循环             │
    │   每 50ms 检测一次                   │
    │                                     │
    ├── 检测到异常颜色！                   │
    │   调用 task.stop_event.set() ───────► 旧引擎检测到 stop_event
    │                                     │   退出执行循环
    │                                     │   线程结束
    │   ◄── call_script_async 的           │
    │       "interrupted" 输出被激活        │
    │                                     │
    ├── 执行"吃药"分支                     │
    │                                     │
```

### 6.2 任务追踪数据结构

```python
class AsyncTask:
    def __init__(self, task_id, thread, stop_event, pause_event,
                 node_id, macro_name):
        self.task_id = task_id
        self.thread = thread
        self.stop_event = stop_event
        self.pause_event = pause_event
        self.node_id = node_id          # 对应节点图的节点 ID
        self.macro_name = macro_name
        self.status = "running"         # running / completed / interrupted / error
        self.start_time = time.perf_counter()
class TaskPool:
    def __init__(self):
        self.tasks: dict[str, AsyncTask] = {}  # task_id → AsyncTask
        self._lock = threading.Lock()
  
    def start(self, node_id, compiled, macro_name, options) -> str:
        """启动异步任务，返回 task_id"""
  
    def stop(self, task_id) -> bool:
        """发送 stop 信号"""
  
    def pause(self, task_id) -> bool:
        """发送 pause 信号"""
  
    def resume(self, task_id) -> bool:
        """清除 pause 信号"""
  
    def get_status(self, task_id) -> str:
        """查询任务状态"""
  
    def stop_all(self):
        """停止所有任务"""
```

### 6.3 监视器节点的实现

监视器节点本质上是"带超时的循环检测 + 触发后执行动作"。
**实现方式**：不使用独立线程池，而是在新引擎的主执行循环中轮询。这样避免线程同步的复杂度，且与任务池的交互更简单。

```python
# 监视器在新引擎主循环中的处理
class MonitorState:
    def __init__(self, node, context):
        self.node = node
        self.interval = node.params["interval"] / 1000.0
        self.last_check = 0.0
        self.timeout = node.params.get("timeout", 0) / 1000.0
        self.start_time = time.perf_counter()
        self.triggered = False
        self.timed_out = False
def check_monitors(monitors, context, now):
    """在主循环每步执行前调用"""
    for mon in monitors:
        if mon.triggered or mon.timed_out:
            continue
        if now - mon.last_check < mon.interval:
            continue
        mon.last_check = now
        # 执行检测
        result = execute_detection_node(mon.node, context)
        if result:
            mon.triggered = True
            # 返回触发信息，由主循环决定执行哪个分支
            return ("trigger", mon.node.id)
        # 检查超时
        if mon.timeout > 0 and (now - mon.start_time) > mon.timeout:
            mon.timed_out = True
            return ("timeout", mon.node.id)
    return None
```

**注意**：如果检测本身耗时较长（如 PaddleOCR 300ms），且检测间隔设为 50ms，则主循环会被阻塞。解决方案：检测间隔由用户自行配置，前端在属性面板中显示预估耗时提示。

### 6.4 监视器触发后的行为

| 行为           | 说明                               | 适用场景                 |
| -------------- | ---------------------------------- | ------------------------ |
| `stop_all`   | 停止所有异步任务 + 停止主流程      | 检测到致命异常           |
| `stop_task`  | 停止指定异步任务，主流程继续       | 检测到连招被打断         |
| `pause_task` | 暂停指定异步任务，主流程继续       | 检测到需要临时处理的情况 |
| `branch`     | 不干预异步任务，走监视器的输出分支 | 定时触发、变量更新       |

行为通过监视器节点的 `on_trigger` 参数配置，输出端口对应：

```
monitor_color
  ├─ trigger   (检测到目标)
  ├─ timeout   (超时未检测到)
  └─ interval  (每次检测周期，可选，用于持续更新变量)
```

### 6.5 中断链路完整时序

```
时间轴 ──►
主线程:     [monitor_color 检测] [检测] [检测] [触发!] [走trigger分支]
                                          │
异步线程:   [execute_macro_once 持续执行中...]  │
                                          │ stop_event.set()
                                          ▼
                                     [旧引擎检测到stop, 退出]
                                     [新引擎执行修饰键兜底释放]
                                     [task.status = "interrupted"]
```

---

## 七、修饰键安全释放协议

### 7.1 设计背景

旧引擎在 `execute_macro_once` 的 `finally` 块中会无条件释放 Shift/Ctrl/Alt/鼠标按键。这在旧引擎独占执行时是安全的。但在新引擎的异步打断场景下：

1. 新引擎启动异步任务执行"按住 Shift + 连招"
2. 监视器检测到异常，发送 `stop_event`
3. 旧引擎 `finally` 块释放 Shift
4. 但此时用户可能正在物理按住 Shift 做其他操作
5. 旧引擎的释放导致用户的 Shift 被意外抬起
   更严重的情况：如果异步任务在循环中间被打断，而旧 JSON 内部的 `ku shift` 还没执行到，`finally` 的释放反而是正确的行为。但如果旧 JSON 内部已经正确写了 `ku`，`finally` 的二次释放就是多余的（虽然通常无害，但在极端时序下可能干扰用户后续操作）。

### 7.2 协议规则

| 场景                              | 释放修饰键？ | 执行者                         |
| --------------------------------- | :----------: | ------------------------------ |
| 旧引擎独立执行（不通过新引擎）    |      ✅      | 旧引擎 `finally`             |
| 新引擎路径1执行原子动作           |      ❌      | 新引擎（在脚本结束时统一释放） |
| 新引擎路径2同步调用，正常完成     |      ❌      | 依赖旧 JSON 内部的 `ku` 指令 |
| 新引擎路径2同步调用，被 stop 打断 |      ✅      | 新引擎（打断后立即释放）       |
| 新引擎路径2异步调用，正常完成     |      ❌      | 依赖旧 JSON 内部的 `ku` 指令 |
| 新引擎路径2异步调用，被 stop 打断 |      ✅      | 新引擎（打断后立即释放）       |
| 整个自动化脚本结束（无论原因）    |      ✅      | 新引擎（最终兜底释放）         |

### 7.3 兜底释放实现

```python
def release_all_modifiers():
    """全局无差别修饰键释放兜底"""
    send_key_event(get_vk("shift"), True)
    send_key_event(get_vk("ctrl"), True)
    send_key_event(get_vk("alt"), True)
    # 鼠标三键
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
    user32.mouse_event(0x0010, 0, 0, 0, 0)  # MOUSEEVENTF_RIGHTUP
    user32.mouse_event(0x0040, 0, 0, 0, 0)  # MOUSEEVENTF_MIDDLEUP
```

**调用时机**：

1. 异步任务被 `stop_event` 打断后，新引擎立即调用。
2. 用户按 ESC 或点击"停止"按钮后，新引擎在停止所有任务后调用。
3. 脚本正常执行到最后一个节点后，新引擎调用。

---

## 八、变量系统

### 8.1 类型定义

| 类型        | 内部表示       | 示例                      | 可用运算                                                                |
| ----------- | -------------- | ------------------------- | ----------------------------------------------------------------------- |
| `number`  | `float`      | `100`, `3.14`         | `+`, `-`, `*`, `/`, `%`, `min`, `max`, `abs`, `round` |
| `string`  | `str`        | `"hello"`, `"HP: 85"` | 拼接, 截取, 替换, 分割, 正则提取                                        |
| `point`   | `dict{x, y}` | `{"x": 960, "y": 540}`  | 取x, 取y, 距离计算                                                      |
| `color`   | `str`        | `"#FF0000"`             | 取R/G/B分量, 比较                                                       |
| `boolean` | `bool`       | `true`, `false`       | AND, OR, NOT                                                            |
| `any`     | `dynamic`    | —                        | 自动推断                                                                |

### 8.2 作用域

| 作用域                                                                                                                                                          | 说明                           | 生命周期                   |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ | -------------------------- |
| `global`                                                                                                                                                      | 脚本全局，所有节点和监视器共享 | 整个脚本运行期间           |
| `local`                                                                                                                                                       | 当前脚本实例内有效             | `call_script` 返回后销毁 |
| 不实现 `param`（子脚本参数传递）和 `builtin`（内置只读变量）—— 子脚本参数通过 `call_script` 节点的 `params` 字典传递，内置信息通过专用 API 按需获取。 |                                |                            |

### 8.3 变量在节点图中的使用方式

**方式1：直接引用**
在节点参数中用 `${var_name}` 语法引用变量：

```json
{
    "type": "mouse_click",
    "params": {
        "x": "${target_x}",
        "y": "${target_y}",
        "mode": "screen"
    }
}
```

执行时，新引擎自动将 `${target_x}` 替换为变量当前值。
**方式2：检测节点存储**
检测节点通过 `store_var` 参数将结果存入变量：

```json
{
    "type": "check_ocr",
    "params": {
        "region": {"mode": "window", "rect": [100, 0, 50, 30]},
        "text": "",
        "engine": "rapidocr",
        "store_var": "hp_text"
    }
}
```

执行后，`hp_text` 的值变为 OCR 识别到的原始文本（如 `"HP: 85"`）。
**方式3：变量操作节点**
通过专用的变量操作节点进行类型转换和数学运算：

```
[check_ocr] → store_var="hp_text" → [var_string: 正则提取数字] → store_var="hp_num" → [var_convert: string→number] → [var_compare: hp_num < 30] → [if_else]
```

### 8.4 变量操作节点定义

| 节点            | 参数                          | 输入                 | 输出                     | 说明           |
| --------------- | ----------------------------- | -------------------- | ------------------------ | -------------- |
| `var_set`     | name, value, type             | —                   | next                     | 设置变量值     |
| `var_math`    | op, a, b, store_var           | a, b（支持变量引用） | next                     | 数学运算       |
| `var_compare` | op, a, b                      | a, b                 | result(boolean data端口) | 比较产生布尔值 |
| `var_string`  | op, a, b, store_var           | a, b                 | next                     | 字符串操作     |
| `var_convert` | to_type, input_var, store_var | —                   | next                     | 类型转换       |

### 8.5 变量引用解析规则

在节点参数值中，`${var_name}` 的解析优先级：

1. 如果变量存在且类型匹配目标参数类型 → 直接替换
2. 如果变量存在但类型不匹配 → 尝试隐式转换（number→string 自动，其他报错）
3. 如果变量不存在 → 报错并跳过该节点
   对于 `point` 类型的变量，在坐标参数中支持展开：`${point_var.x}` 和 `${point_var.y}`。

---

## 九、节点类型完整定义

### 9.1 端口类型约定

| 端口类型        | 颜色      | 语义       | 连线规则               |
| --------------- | --------- | ---------- | ---------------------- |
| `flow`        | 白色/灰色 | 执行流方向 | 一个输出只能连一个输入 |
| `data_bool`   | 红色      | 布尔数据   | 一个输出可连多个输入   |
| `data_number` | 绿色      | 数值数据   | 同上                   |
| `data_string` | 蓝色      | 字符串数据 | 同上                   |
| `data_any`    | 白色虚线  | 任意类型   | 同上                   |

### 9.2 动作节点（绿色，走路径1）

#### `mouse_click`

移动到坐标并执行鼠标点击。

| 端口                 | 方向   | 类型       | 说明                                       |
| -------------------- | ------ | ---------- | ------------------------------------------ |
| in                   | 输入   | flow       | 执行流输入                                 |
| next                 | 输出   | flow       | 执行流输出                                 |
| 参数                 | 类型   | 默认值     | 说明                                       |
| ------               | ------ | --------   | ------                                     |
| mode                 | enum   | `screen` | 坐标模式：screen/window/relative           |
| x                    | number | 0          | X 坐标（逻辑像素或比例值）                 |
| y                    | number | 0          | Y 坐标                                     |
| hwnd_var             | string | —         | 窗口句柄变量名（window/relative 模式必填） |
| button               | enum   | `left`   | left/right/middle                          |
| click_type           | enum   | `click`  | click/dblclick/press/release/long_press    |
| hold_time            | number | 0          | 长按持续时间                               |
| move_duration        | number | 0          | 移动到目标坐标的耗时，0=瞬移               |
| before_delay         | number | 0          | 点击前额外等待                             |
| after_delay          | number | 0          | 点击后额外等待                             |
| **执行语义**： |        |            |                                            |

1. `resolve_coords(mode, x, y, hwnd)` → 物理像素
2. 如果 `move_duration > 0`：分步插值移动
3. `precise_sleep(before_delay)`
4. 执行点击动作
5. `precise_sleep(after_delay)`
6. 流转到 `next`

#### `key_action`

| 参数   | 类型   | 默认值    | 说明                                                          |
| ------ | ------ | --------- | ------------------------------------------------------------- |
| action | enum   | `press` | press/release/type                                            |
| key    | string | —        | 按键名（a-z, 0-9, f1-f12, enter, space, shift, ctrl, alt 等） |
| delay  | number | 0         | 动作后延迟                                                    |

#### `mouse_scroll`

| 参数  | 类型   | 默认值 | 说明                       |
| ----- | ------ | ------ | -------------------------- |
| delta | number | 120    | 滚动量，正值向上，负值向下 |
| delay | number | 0      | 动作后延迟                 |

#### `text_input`

逐字符输入文本，每个字符之间有可选间隔。

| 参数                                                                                                   | 类型   | 默认值 | 说明         |
| ------------------------------------------------------------------------------------------------------ | ------ | ------ | ------------ |
| text                                                                                                   | string | —     | 要输入的文本 |
| interval                                                                                               | number | 50     | 字符间间隔   |
| before_delay                                                                                           | number | 0      | 输入前等待   |
| **执行语义**：对于每个字符，如果是大写字母或特殊符号，自动按下 Shift → 输入字符 → 释放 Shift。 |        |        |              |

#### `wait`

| 参数     | 类型   | 默认值 | 说明     |
| -------- | ------ | ------ | -------- |
| duration | number | —     | 等待时长 |

### 9.3 检测节点（金色，大脑感知）

检测节点有两个 flow 输出端口：`match`（条件满足）和 `no`（条件不满足）。同时通过 data 端口输出布尔值，供 `if_else` 节点通过 data 连线消费。

#### `check_color`

| 端口                            | 方向   | 类型        | 说明                                                         |
| ------------------------------- | ------ | ----------- | ------------------------------------------------------------ |
| in                              | 输入   | flow        | 执行流输入                                                   |
| match                           | 输出   | flow        | 颜色匹配成功                                                 |
| no                              | 输出   | flow        | 颜色不匹配                                                   |
| result                          | 输出   | data_bool   | 检测结果布尔值                                               |
| 参数                            | 类型   | 默认值      | 说明                                                         |
| ------                          | ------ | --------    | ------                                                       |
| mode                            | enum   | `screen`  | 坐标模式                                                     |
| rect                            | array  | —          | 检测区域 [x, y, w, h]                                        |
| hwnd_var                        | string | —          | 窗口句柄变量名                                               |
| target_color                    | string | —          | 目标颜色 "#RRGGBB"                                           |
| tolerance                       | number | 10          | 容差（0-255，基于欧氏距离）                                  |
| check_mode                      | enum   | `contain` | exact（精确匹配）/ contain（区域内包含）/ change（相对变化） |
| sample_mode                     | enum   | `center`  | center（中心点）/ mean（均值）/ max_diff（最大偏差点）       |
| store_var                       | string | —          | 存储检测到的实际颜色值                                       |
| **check_mode 详细语义**： |        |             |                                                              |

- `exact`：区域所有像素与目标颜色的差值均 ≤ tolerance
- `contain`：区域中至少一个像素与目标颜色的差值 ≤ tolerance
- `change`：与上次检测结果比较，区域像素变化量 > threshold（需要 `change_threshold` 参数）
  **后端实现**（`detection/color.py`）：

```python
import numpy as np
def check_color(image: np.ndarray, target: tuple, tolerance: int,
                mode: str = "contain", sample: str = "center") -> dict:
    """
    image: BGR 格式的 numpy 数组
    target: (B, G, R) 元组
    返回: {"found": bool, "actual_color": str, "diff": float}
    """
    if sample == "center":
        h, w = image.shape[:2]
        pixel = image[h // 2, w // 2]
        diff = np.linalg.norm(pixel.astype(float) - np.array(target, dtype=float))
        found = diff <= tolerance
    elif sample == "mean":
        mean_color = image.mean(axis=(0, 1))
        diff = np.linalg.norm(mean_color - np.array(target, dtype=float))
        found = diff <= tolerance
    elif sample == "max_diff":
        # 找到与目标颜色最接近的像素
        diff_map = np.linalg.norm(
            image.astype(float) - np.array(target, dtype=float), axis=2
        )
        min_diff = diff_map.min()
        found = min_diff <= tolerance
  
    actual_bgr = pixel if sample == "center" else image.mean(axis=(0, 1))
    actual_hex = "#{:02X}{:02X}{:02X}".format(
        int(actual_bgr[2]), int(actual_bgr[1]), int(actual_bgr[0])
    )
    return {"found": bool(found), "actual_color": actual_hex, "diff": float(diff)}
```

#### `check_ocr`

| 参数                            | 类型   | 默认值       | 说明                                              |
| ------------------------------- | ------ | ------------ | ------------------------------------------------- |
| mode                            | enum   | `screen`   | 坐标模式                                          |
| rect                            | array  | —           | 检测区域                                          |
| hwnd_var                        | string | —           | 窗口句柄变量名                                    |
| match_text                      | string | —           | 匹配文本                                          |
| match_mode                      | enum   | `contain`  | contain/exact/regex/number_gt/number_lt/number_eq |
| engine                          | enum   | `rapidocr` | rapidocr/paddleocr（可选安装）                    |
| store_var                       | string | —           | 存储识别到的原始文本                              |
| store_number                    | string | —           | 存储提取的数字值（number_* 模式时有效）           |
| **match_mode 详细语义**： |        |              |                                                   |

- `contain`：识别结果包含 match_text
- `exact`：识别结果完全等于 match_text
- `regex`：match_text 作为正则表达式匹配
- `number_gt`：从识别结果中提取数字，与 match_text（数字）比较，大于则匹配
- `number_lt`：小于则匹配
- `number_eq`：等于则匹配

#### `check_image`

| 参数          | 类型   | 默认值     | 说明                               |
| ------------- | ------ | ---------- | ---------------------------------- |
| template_path | string | —         | 模板图片路径（相对于项目根目录）   |
| search_region | object | null       | 搜索区域（null=全屏），格式同 rect |
| threshold     | number | 0.8        | 匹配阈值（0.0~1.0）                |
| store_pos     | string | —         | 存储匹配位置 {"x": ..., "y": ...}  |
| mode          | enum   | `screen` | 坐标模式                           |
| hwnd_var      | string | —         | 窗口句柄变量名                     |

#### `check_screen`

| 参数      | 类型   | 默认值    | 说明                  |
| --------- | ------ | --------- | --------------------- |
| state     | enum   | `black` | black/bright          |
| region    | object | null      | 检测区域（null=全屏） |
| threshold | number | 30        | 亮度阈值（0-255）     |

#### `check_pixel_diff`

| 参数      | 类型   | 默认值     | 说明           |
| --------- | ------ | ---------- | -------------- |
| mode      | enum   | `screen` | 坐标模式       |
| rect      | array  | —         | 检测区域       |
| threshold | number | 10         | 像素变化量阈值 |
| hwnd_var  | string | —         | 窗口句柄变量名 |

### 9.4 控制节点（紫色，大脑决策）

#### `if_else`

| 端口                 | 方向   | 类型      | 说明                                       |
| -------------------- | ------ | --------- | ------------------------------------------ |
| in                   | 输入   | flow      | 执行流输入                                 |
| cond                 | 输入   | data_bool | 条件输入（可连多个检测节点的 data 输出）   |
| true                 | 输出   | flow      | 条件为真                                   |
| false                | 输出   | flow      | 条件为假                                   |
| 参数                 | 类型   | 默认值    | 说明                                       |
| ------               | ------ | --------  | ------                                     |
| logic                | enum   | `AND`   | AND/OR/NOT                                 |
| fallback             | enum   | `false` | 当无任何 data 连接时的默认走向：true/false |
| **执行语义**： |        |           |                                            |

1. 收集所有通过 data 端口连接到此节点的检测节点的布尔结果
2. 按 `logic` 组合
3. 走对应分支
   **关于 data 端口与 flow 端口的关系**：检测节点的 flow 输出必须连接到 if_else 的 flow 输入（保证执行顺序：先检测，再判断）。data 输出额外连接到 if_else 的 cond 输入（传递布尔值）。如果只有 data 连接没有 flow 连接，执行器会报错。

#### `loop_count`

| 端口                 | 方向   | 类型     | 说明                                  |
| -------------------- | ------ | -------- | ------------------------------------- |
| in                   | 输入   | flow     | 执行流输入                            |
| body                 | 输出   | flow     | 循环体                                |
| next                 | 输出   | flow     | 循环结束                              |
| 参数                 | 类型   | 默认值   | 说明                                  |
| ------               | ------ | -------- | ------                                |
| count                | number | —       | 循环次数（支持变量引用 `${var}`）   |
| counter_var          | string | —       | 循环计数器变量名（0-based，每轮递增） |
| **执行语义**： |        |          |                                       |

1. 解析 `count`（支持变量引用）
2. `for i in range(count):` 执行 body 连接的节点链
3. 每轮迭代开始时，更新 `counter_var`（如果指定）
4. **每轮迭代开始时，重新计算 body 内所有节点的坐标**（动态刷新）
5. 每步检查 `stop_event`，支持中途退出
6. 循环结束后走 `next`

#### `loop_while`

| 端口           | 方向   | 类型      | 说明                                               |
| -------------- | ------ | --------- | -------------------------------------------------- |
| in             | 输入   | flow      | 执行流输入                                         |
| cond           | 输入   | data_bool | 循环条件                                           |
| body           | 输出   | flow      | 循环体                                             |
| next           | 输出   | flow      | 条件不满足时退出                                   |
| 参数           | 类型   | 默认值    | 说明                                               |
| ------         | ------ | --------  | ------                                             |
| max_iterations | number | 10000     | 最大迭代次数（防止死循环）                         |
| check_at       | enum   | `start` | start（每次迭代开始检查）/ end（每次迭代结束检查） |

#### `sequence_check`（P2）

按序守卫链。内部维护状态机，步骤必须按序满足，任一步失败可回退。

| 参数                 | 类型   | 默认值      | 说明                                           |
| -------------------- | ------ | ----------- | ---------------------------------------------- |
| steps                | array  | —          | 步骤列表，每步包含 type（检测类型）和 params   |
| check_interval       | number | 100         | 检测间隔                                       |
| max_retry            | number | 0           | 失败后回退重试次数，0=不重试直接失败           |
| on_fail              | enum   | `restart` | restart（回到步骤1）/ fail（直接走 fail 分支） |
| **执行语义**： |        |             |                                                |

```
state = 0
retry_count = 0
while not stop_event:
    if state == 0 and check_step(steps[0]):
        state = 1
    if state == 1 and check_step(steps[1]):
        state = 2
    ...
    if state == len(steps):
        output("pass"); return
    sleep(check_interval)
    if max_retry > 0 and 检测到回退条件:
        retry_count += 1
        if retry_count > max_retry:
            output("fail"); return
        state = 0
output("fail")
```

#### `state_machine`（P2）

有限状态机，适用于复杂多阶段场景。

| 参数                        | 类型   | 默认值 | 说明         |
| --------------------------- | ------ | ------ | ------------ |
| states                      | array  | —     | 状态定义列表 |
| initial_state               | string | —     | 初始状态名   |
| check_interval              | number | 100    | 检测间隔     |
| **states 元素格式**： |        |        |              |

```json
{
    "name": "wait_color",
    "check": {"type": "check_color", "params": {...}},
    "on_match": "check_popup",
    "on_fail": null,
    "on_timeout": "wait_color",
    "timeout": 5000
}
```

### 9.5 动作块节点（蓝色，走路径2）

#### `call_script_sync`

| 端口                                                     | 方向   | 类型         | 说明                          |
| -------------------------------------------------------- | ------ | ------------ | ----------------------------- |
| in                                                       | 输入   | flow         | 执行流输入                    |
| next                                                     | 输出   | flow         | 执行完毕后继续                |
| 参数                                                     | 类型   | 默认值       | 说明                          |
| ------                                                   | ------ | --------     | ------                        |
| path                                                     | string | —           | 旧 JSON 宏文件路径            |
| speed_factor                                             | number | 1.0          | 倍速                          |
| timeline_mode                                            | enum   | `absolute` | absolute/relative_compensated |
| random_delay                                             | bool   | false        | 是否启用随机延迟修正          |
| **执行语义**：阻塞当前执行流，直到旧引擎执行完毕。 |        |              |                               |

#### `call_script_async`

| 端口                 | 方向                | 类型 | 说明                         |
| -------------------- | ------------------- | ---- | ---------------------------- |
| in                   | 输入                | flow | 执行流输入                   |
| next                 | 输出                | flow | 启动后立即继续（不等待完成） |
| completed            | 输出                | flow | 异步任务正常完成             |
| interrupted          | 输出                | flow | 异步任务被 stop_event 打断   |
| 参数                 | 同 call_script_sync |      |                              |
| **执行语义**： |                     |      |                              |

1. 在 TaskPool 中注册异步任务
2. 启动后台线程执行旧引擎
3. 主流程立刻走 `next`
4. 异步线程结束后，设置对应输出端口的标记
5. 主循环在每步轮询 TaskPool 状态，当异步任务完成/打断时，执行对应分支
   **关于 completed/interrupted 分支的触发时机**：这两个分支不是由 flow 连线自动触发的（因为主流程已经走 `next` 了）。新引擎维护一个"待执行分支队列"——当异步任务状态变化时，将对应分支的节点链加入队列，在主循环的下一次轮询中执行。

### 9.6 监视器节点（青色，并发触发）

#### `monitor_color`

| 端口         | 方向   | 类型       | 说明                                               |
| ------------ | ------ | ---------- | -------------------------------------------------- |
| trigger      | 输出   | flow       | 检测到目标颜色                                     |
| timeout      | 输出   | flow       | 超时未检测到                                       |
| lost         | 输出   | flow       | 目标颜色消失（可选）                               |
| 参数         | 类型   | 默认值     | 说明                                               |
| ------       | ------ | --------   | ------                                             |
| mode         | enum   | `screen` | 坐标模式                                           |
| rect         | array  | —         | 检测区域                                           |
| target_color | string | —         | 目标颜色                                           |
| tolerance    | number | 10         | 容差                                               |
| interval     | number | 100        | 检测间隔                                           |
| timeout      | number | 0          | 超时（0=无限）                                     |
| trigger_mode | enum   | `appear` | appear/disappear/change                            |
| on_trigger   | enum   | `branch` | branch/stop_all/stop_task/pause_task               |
| target_task  | string | —         | on_trigger 为 stop_task/pause_task 时的目标任务 ID |
| auto_stop    | bool   | true       | 触发后是否自动停止此监视器                         |

#### `monitor_ocr`

参数同 `check_ocr`，增加 `interval`、`timeout`、`on_trigger`、`target_task`、`auto_stop`。

#### `monitor_timer`

| 参数         | 类型   | 默认值     | 说明               |
| ------------ | ------ | ---------- | ------------------ |
| interval     | number | —         | 触发间隔           |
| repeat_count | number | 0          | 重复次数（0=无限） |
| on_trigger   | enum   | `branch` | 触发行为           |

### 9.7 变量节点（橙色）

见第八章变量系统。所有变量节点只有 `in` 和 `next` 两个 flow 端口（`var_compare` 额外有 `result` data_bool 输出端口）。

### 9.8 预设节点（粉色，P3 语法糖）

预设节点是多个基础节点的封装组合，用户不需要手动连线。在前端表现为单个节点，但在解析阶段会展开为基础节点树。
| 预设 | 展开为 | 说明 |
|------|--------|------|
| `preset_click` | mouse_click(mode,x,y,button) | 移动并点击 |
| `preset_find_click` | check_image → 提取匹配位置 → mouse_click(匹配位置) | 找图并点击 |
| `preset_read_number` | check_ocr(number模式) → var_set | OCR 识别数字存入变量 |
| `preset_wait_screen` | check_screen(loop 直到满足或超时) | 等待黑屏/亮屏 |
| `preset_wait_color` | check_color(loop) | 等待颜色出现 |
| `preset_find_and_wait` | check_image(loop) → 提取位置 | 等待图像出现 |
**实现方式**：在解析阶段，将预设节点的参数映射为基础节点的参数，生成一组基础节点和连线，替换原预设节点在图中的位置。对用户透明。
----------------------------------------------------------------------------------------------------------------------------

## 十、节点图格式（.auto.json）

```json
{
  "meta": {
    "name": "挂机打怪自动化",
    "version": "4.0",
    "created": "2024-01-01T12:00:00",
    "modified": "2024-01-02T15:30:00",
    "description": "自动打怪，血量低时吃药"
  },
  "variables": {
    "hp_num": {"type": "number", "init": 100, "scope": "global"},
    "target_x": {"type": "number", "init": 960, "scope": "global"}
  },
  "settings": {
    "target_hwnd_var": "game_hwnd",
    "default_coord_mode": "window"
  },
  "graph": {
    "nodes": [
      {
        "id": "n1",
        "type": "call_script_async",
        "position": {"x": 100, "y": 200},
        "params": {
          "path": "宏/连招.json",
          "speed_factor": 1.0
        }
      },
      {
        "id": "n2",
        "type": "monitor_ocr",
        "position": {"x": 100, "y": 400},
        "params": {
          "mode": "window",
          "rect": [100, 0, 50, 30],
          "match_text": "",
          "match_mode": "number_lt",
          "match_number": 30,
          "engine": "rapidocr",
          "interval": 200,
          "timeout": 0,
          "on_trigger": "stop_task",
          "target_task": "n1",
          "auto_stop": true
        }
      },
      {
        "id": "n3",
        "type": "call_script_sync",
        "position": {"x": 350, "y": 400},
        "params": {
          "path": "宏/吃药.json"
        }
      },
      {
        "id": "n4",
        "type": "wait",
        "position": {"x": 600, "y": 400},
        "params": {
          "duration": 1000
        }
      }
    ],
    "connections": [
      {
        "id": "c1",
        "from": {"node": "n1", "port": "next"},
        "to": {"node": "n2", "port": "in"},
        "type": "flow"
      },
      {
        "id": "c2",
        "from": {"node": "n2", "port": "trigger"},
        "to": {"node": "n3", "port": "in"},
        "type": "flow"
      },
      {
        "id": "c3",
        "from": {"node": "n3", "port": "next"},
        "to": {"node": "n4", "port": "in"},
        "type": "flow"
      }
    ]
  }
}
```

**与 V1 版本格式的差异**：

- 去掉了 `settings.precision_engine` 等旧引擎配置（这些属于路径2的 `call_script` 参数）
- 去掉了 `settings.interception`（路径1 不用 Interception）
- `connections` 中 `type` 字段明确区分 `flow` 和 `data`
- 检测节点的输出端口从 `match`/`no`（flow）+ `result`（data）明确区分

---

## 十一、新引擎内部执行模型

### 11.1 解析阶段（JSON → 执行树）

不是编译为线性指令，而是将 JSON 解析为内存中的图结构：

```python
@dataclass
class ExecNode:
    id: str
    type: str
    params: dict
    position: dict  # 画布位置（仅用于序列化回去）
    # 端口连接（由解析器构建）
    flow_children: dict[str, list[str]]   # port_name → [child_node_id, ...]
    data_inputs: dict[str, list[dict]]    # port_name → [{source_node_id, source_port}, ...]
@dataclass
class ExecGraph:
    nodes: dict[str, ExecNode]     # node_id → ExecNode
    variables: dict                 # 变量定义
    settings: dict                  # 全局设置
    entry_node_id: str              # 入口节点 ID（没有 flow 输入连接的节点）
```

**解析器逻辑**（`automation_compiler.py`）：

```python
def parse_graph(json_data: dict) -> ExecGraph:
    graph = ExecGraph(nodes={}, variables={}, settings={})
  
    # 1. 解析变量和设置
    graph.variables = json_data.get("variables", {})
    graph.settings = json_data.get("settings", {})
  
    # 2. 创建所有节点
    for node_json in json_data["graph"]["nodes"]:
        node = ExecNode(
            id=node_json["id"],
            type=node_json["type"],
            params=node_json.get("params", {}),
            position=node_json.get("position", {"x": 0, "y": 0}),
            flow_children={},
            data_inputs={},
        )
        graph.nodes[node.id] = node
  
    # 3. 构建连接关系
    for conn in json_data["graph"]["connections"]:
        from_node = graph.nodes[conn["from"]["node"]]
        to_node = graph.nodes[conn["to"]["node"]]
        port_name = conn["to"]["port"]
  
        if conn["type"] == "flow":
            from_port = conn["from"]["port"]
            from_node.flow_children.setdefault(from_port, []).append(to_node.id)
        elif conn["type"] == "data":
            to_node.data_inputs.setdefault(port_name, []).append({
                "source_node_id": conn["from"]["node"],
                "source_port": conn["from"]["port"],
            })
  
    # 4. 确定入口节点（没有 flow 输入连接的节点）
    has_flow_input = set()
    for conn in json_data["graph"]["connections"]:
        if conn["type"] == "flow":
            has_flow_input.add(conn["to"]["node"])
    entry_candidates = [nid for nid in graph.nodes if nid not in has_flow_input]
    graph.entry_node_id = entry_candidates[0] if entry_candidates else None
  
    # 5. 预设节点展开（P3阶段实现）
    # expand_preset_nodes(graph)
  
    return graph
```

### 11.2 执行上下文

```python
class ExecContext:
    def __init__(self, graph: ExecGraph, stop_event: threading.Event):
        self.graph = graph
        self.stop_event = stop_event
        self.variables: dict[str, any] = {}
        self.check_results: dict[str, bool] = {}   # node_id.port → bool
        self.task_pool = TaskPool()
        self.monitors: list[MonitorState] = []
        self.pending_branches: list[tuple[str, str]] = []  # (node_id, port_name)
        self.loop_index: int = 0
        self.last_capture_cache: dict[str, np.ndarray] = {}  # node_id → 上次截图
        self.hwnd_cache: dict[str, int] = {}  # hwnd_var → hwnd
  
        # 初始化变量默认值
        for var_name, var_def in graph.variables.items():
            self.variables[var_name] = var_def.get("init")
```

### 11.3 执行器核心循环

```python
def execute_graph(graph: ExecGraph, stop_event: threading.Event):
    context = ExecContext(graph, stop_event)
  
    if not graph.entry_node_id:
        print("[新引擎] 错误：未找到入口节点")
        return
  
    try:
        _execute_node(graph.entry_node_id, context)
    finally:
        # 脚本结束，兜底释放修饰键
        release_all_modifiers()
        # 停止所有异步任务
        context.task_pool.stop_all()
def _execute_node(node_id: str, ctx: ExecContext):
    if ctx.stop_event.is_set():
        return
  
    node = ctx.graph.nodes[node_id]
  
    # 检查是否有待执行的分支（来自异步任务完成/监视器触发）
    _process_pending_branches(ctx)
  
    # 检查监视器
    monitor_result = _check_monitors(ctx.monitors, ctx)
    if monitor_result:
        action, source_node_id = monitor_result
        _handle_monitor_trigger(action, source_node_id, ctx)
        if ctx.stop_event.is_set():
            return
  
    # 根据节点类型执行
    handler = NODE_HANDLERS.get(node.type)
    if handler is None:
        print(f"[新引擎] 未知节点类型: {node.type}")
        return
  
    handler(node, ctx)
def _execute_flow(node_id: str, port_name: str, ctx: ExecContext):
    """执行指定节点的指定输出端口连接的子节点链"""
    if ctx.stop_event.is_set():
        return
    node = ctx.graph.nodes[node_id]
    children = node.flow_children.get(port_name, [])
    for child_id in children:
        _execute_node(child_id, ctx)
        if ctx.stop_event.is_set():
            return
```

### 11.4 各类型节点的处理器

```python
def _handle_mouse_click(node: ExecNode, ctx: ExecContext):
    params = node.params
    # 解析变量引用
    x = _resolve_value(params["x"], ctx)
    y = _resolve_value(params["y"], ctx)
    mode = params.get("mode", ctx.graph.settings.get("default_coord_mode", "screen"))
    hwnd = _get_hwnd(params.get("hwnd_var"), ctx)
  
    # 动态解析坐标
    phys_x, phys_y = resolve_coords(mode, x, y, hwnd)
  
    # 移动
    move_dur = params.get("move_duration", 0)
    if move_dur > 0:
        _interpolated_move(phys_x, phys_y, move_dur, ctx.stop_event)
    else:
        set_cursor_pos(phys_x, phys_y)
  
    # 等待
    before_delay = params.get("before_delay", 0)
    if before_delay > 0:
        precise_sleep_v5(before_delay / 1000.0, ctx.stop_event)
  
    # 点击
    button = params.get("button", "left")
    click_type = params.get("click_type", "click")
    _do_click(button, click_type, params.get("hold_time", 0), ctx.stop_event)
  
    # 等待
    after_delay = params.get("after_delay", 0)
    if after_delay > 0:
        precise_sleep_v5(after_delay / 1000.0, ctx.stop_event)
  
    # 流转
    _execute_flow(node.id, "next", ctx)
def _handle_check_color(node: ExecNode, ctx: ExecContext):
    params = node.params
    rect = _resolve_region(params, ctx)
  
    # 截图
    img = capture_screen(rect)
  
    # 检测
    target = _parse_color(params["target_color"])
    result = check_color(img, target, params.get("tolerance", 10),
                         params.get("check_mode", "contain"),
                         params.get("sample_mode", "center"))
  
    # 存储结果
    if params.get("store_var"):
        ctx.variables[params["store_var"]] = result["actual_color"]
  
    # 记录 data 端口结果
    ctx.check_results[f"{node.id}.result"] = result["found"]
  
    # 流转
    if result["found"]:
        _execute_flow(node.id, "match", ctx)
    else:
        _execute_flow(node.id, "no", ctx)
def _handle_if_else(node: ExecNode, ctx: ExecContext):
    # 收集 data 输入
    data_sources = node.data_inputs.get("cond", [])
    conditions = []
    for src in data_sources:
        key = f"{src['source_node_id']}.{src['source_port']}"
        conditions.append(ctx.check_results.get(key, False))
  
    logic = node.params.get("logic", "AND")
  
    if not conditions:
        # 无 data 连接时使用 fallback
        result = node.params.get("fallback", "false") == "true"
    elif logic == "AND":
        result = all(conditions)
    elif logic == "OR":
        result = any(conditions)
    elif logic == "NOT":
        result = not conditions[0]
  
    if result:
        _execute_flow(node.id, "true", ctx)
    else:
        _execute_flow(node.id, "false", ctx)
def _handle_loop_count(node: ExecNode, ctx: ExecContext):
    count = _resolve_value(node.params["count"], ctx)
    count = int(count)
    counter_var = node.params.get("counter_var")
  
    for i in range(count):
        if ctx.stop_event.is_set():
            return
        ctx.loop_index = i
        if counter_var:
            ctx.variables[counter_var] = i
        _execute_flow(node.id, "body", ctx)
  
    _execute_flow(node.id, "next", ctx)
def _handle_call_script_async(node: ExecNode, ctx: ExecContext):
    # 预编译旧 JSON
    path = node.params["path"]
    script = load_macro_from_file(path)
    compiled = compile_macro(script)
    compiled = batch_compiled_macro(compiled)
  
    # 构造 options
    opts = {
        "speed_factor": node.params.get("speed_factor", 1.0),
        "timeline_mode": node.params.get("timeline_mode", "absolute"),
        "random_delay": node.params.get("random_delay", False),
        "auto_release_modifiers": False,
    }
  
    # 启动异步任务
    task_id = ctx.task_pool.start(
        node_id=node.id,
        compiled=compiled,
        macro_name=os.path.basename(path),
        options=opts,
    )
  
    # 主流程立刻继续
    _execute_flow(node.id, "next", ctx)
  
    # 注意：completed/interrupted 分支由 _process_pending_branches 处理
```

### 11.5 变量引用解析

```python
def _resolve_value(value, ctx: ExecContext):
    """解析参数值中的变量引用 ${var_name}"""
    if not isinstance(value, str):
        return value
    if not value.startswith("${") or not value.endswith("}"):
        return value
    var_name = value[2:-1]
    if var_name in ctx.variables:
        return ctx.variables[var_name]
    print(f"[新引擎] 警告：变量 '{var_name}' 未定义")
    return 0  # 默认值
```

---

## 十二、检测能力模块

### 12.1 模块结构

```
webui_backend/detection/
├── __init__.py
├── capture.py      # mss 截图封装
├── color.py        # numpy 颜色检测
├── ocr.py          # RapidOCR 封装
├── matcher.py      # OpenCV 模板匹配
└── screen.py       # 屏幕亮度判断
```

### 12.2 截图模块（capture.py）

```python
import mss
import numpy as np
_mss_instance = None
def _get_mss():
    global _mss_instance
    if _mss_instance is None:
        _mss_instance = mss.mss()
    return _mss_instance
def capture_screen(region: tuple = None) -> np.ndarray:
    """
    截取屏幕区域
    region: (phys_x, phys_y, phys_w, phys_h) 物理像素，None=全屏
    返回: BGR 格式的 numpy 数组
    """
    sct = _get_mss()
    if region is None:
        monitor = sct.monitors[1]  # 主屏
    else:
        monitor = {
            "left": int(region[0]),
            "top": int(region[1]),
            "width": int(region[2]),
            "height": int(region[3]),
        }
    sct_img = sct.grab(monitor)
    # mss 返回 BGRA，去掉 alpha 通道
    img = np.array(sct_img)[:, :, :3]
    return img
```

**性能**：mss 截取 1920×1080 全屏约 5-15ms，截取小区域（如 100×50）约 1-3ms。

### 12.3 OCR 模块（ocr.py）

```python
class OCREngine:
    def __init__(self):
        self._rapidocr = None
        self._last_result = {}  # cache_key → {text, found, timestamp}
  
    def _get_rapidocr(self):
        if self._rapidocr is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._rapidocr = RapidOCR()
            except ImportError:
                raise RuntimeError("RapidOCR 未安装，请运行: pip install rapidocr_onnxruntime")
        return self._rapidocr
  
    def detect(self, image: np.ndarray, match_text: str = None,
               match_mode: str = "contain", match_number: float = None,
               cache_key: str = None, last_image: np.ndarray = None) -> dict:
        """
        返回: {
            "found": bool,
            "text": str,
            "confidence": float,
            "number": float or None,
            "cost_ms": float
        }
        """
        # 帧差缓存：如果图片没变，直接返回上次结果
        if cache_key and last_image is not None:
            diff = np.mean(np.abs(image.astype(float) - last_image.astype(float)))
            if diff < 2.0:  # 像素平均变化 < 2，认为画面没变
                cached = self._last_result.get(cache_key)
                if cached:
                    cached["cost_ms"] = 0.1  # 缓存命中，耗时极低
                    return cached
  
        engine = self._get_rapidocr()
        start = time.perf_counter()
        results, _ = engine(image)
        cost_ms = (time.perf_counter() - start) * 1000
  
        # 合并所有识别结果
        full_text = ""
        if results:
            full_text = " ".join(item[1] for item in results)
  
        found = False
        extracted_number = None
  
        if match_mode == "contain":
            found = match_text in full_text if match_text else False
        elif match_mode == "exact":
            found = full_text.strip() == match_text
        elif match_mode == "regex":
            import re
            found = bool(re.search(match_text, full_text))
        elif match_mode in ("number_gt", "number_lt", "number_eq"):
            import re
            numbers = re.findall(r'[\d.]+', full_text)
            if numbers:
                extracted_number = float(numbers[0])
                if match_mode == "number_gt":
                    found = extracted_number > match_number
                elif match_mode == "number_lt":
                    found = extracted_number < match_number
                elif match_mode == "number_eq":
                    found = abs(extracted_number - match_number) < 0.01
  
        result = {
            "found": found,
            "text": full_text,
            "confidence": results[0][2] if results else 0.0,
            "number": extracted_number,
            "cost_ms": cost_ms,
        }
  
        if cache_key:
            self._last_result[cache_key] = result
  
        return result
```

### 12.4 引擎选择策略

| 引擎      | 安装命令                               | 适用场景            | 预期延迟  | P 阶段     |
| --------- | -------------------------------------- | ------------------- | --------- | ---------- |
| RapidOCR  | `pip install rapidocr_onnxruntime`   | 固定区域短文字/数字 | 30-80ms   | P1         |
| PaddleOCR | `pip install paddleocr paddlepaddle` | 大区域复杂文字      | 100-300ms | P2（可选） |

前端 OCR 节点的引擎下拉框根据后端实际安装情况动态显示。如果 PaddleOCR 未安装，下拉框中不显示该选项。

### 12.5 帧差缓存策略

每个检测节点有一个隐式的 `cache_key`（默认为节点 ID）。执行器在调用检测前，保存当前截图到 `ctx.last_capture_cache[node_id]`。下次检测时，先做帧差判断：

```python
def _do_detection(node, ctx, detect_func):
    rect = _resolve_region(node.params, ctx)
    current_img = capture_screen(rect)
    last_img = ctx.last_capture_cache.get(node.id)
  
    # 帧差预检
    if last_img is not None and current_img.shape == last_img.shape:
        diff = np.mean(np.abs(current_img.astype(float) - last_img.astype(float)))
        if diff < 2.0:
            # 画面没变，返回缓存结果
            cached = ctx.check_results.get(f"{node.id}.cached")
            if cached is not None:
                return cached
  
    # 执行实际检测
    result = detect_func(current_img)
    ctx.last_capture_cache[node.id] = current_img
    ctx.check_results[f"{node.id}.cached"] = result
    return result
```

**用户控制**：对于需要持续检测变化值（如计时器）的场景，用户可以在节点参数中设置 `cache_enabled: false`，强制每次都执行实际检测。
-------------------------------------------------------------------------------------------------------

## 十三、前端 UI 架构

### 13.1 页面结构

```html
<div id="automation-page" style="display:none; width:100%; height:100%; flex-direction:column;">
    <!-- 顶部工具栏 -->
    <div id="auto-toolbar">
        <div class="toolbar-left">
            <button id="btn-run">运行</button>
            <button id="btn-stop">停止</button>
            <button id="btn-pause">暂停</button>
        </div>
        <div class="toolbar-center">
            <span id="auto-status">IDLE</span>
            <div id="auto-progress-bar"><div id="auto-progress-fill"></div></div>
        </div>
        <div class="toolbar-right">
            <button id="btn-export">导出</button>
            <button id="btn-import">导入</button>
            <button id="btn-save">保存</button>
        </div>
    </div>
  
    <!-- 主体三栏 -->
    <div id="auto-main" style="flex:1; display:flex; overflow:hidden;">
        <!-- 左侧工具箱 -->
        <div id="auto-toolbox">
            <div class="toolbox-search">
                <input type="text" placeholder="搜索节点..." id="node-search-input">
            </div>
            <div id="toolbox-categories">
                <!-- 由 JS 动态生成 -->
            </div>
        </div>
  
        <!-- 中间画布 -->
        <div id="canvas-container" style="flex:1; position:relative; overflow:hidden;">
            <canvas id="node-canvas"></canvas>
            <!-- 小地图 -->
            <div id="minimap" style="position:absolute; bottom:10px; right:10px; width:150px; height:100px; border:1px solid var(--border); opacity:0.7;"></div>
        </div>
  
        <!-- 右侧属性面板 -->
        <div id="auto-property-panel">
            <div class="panel-header">属性面板</div>
            <div id="property-panel-content">
                <div class="empty-hint">选择节点查看属性</div>
            </div>
        </div>
    </div>
  
    <!-- 底部状态栏 -->
    <div id="auto-statusbar">
        <span>节点: <b id="stat-nodes">0</b></span>
        <span>连线: <b id="stat-connections">0</b></span>
        <span>监视器: <b id="stat-monitors">0</b></span>
        <span>变量: <b id="stat-variables">0</b></span>
        <span id="stat-cursor">坐标: 0, 0</span>
    </div>
</div>
<!-- 坐标拾取覆盖层（全局隐藏） -->
<div id="pick-overlay" style="display:none; position:fixed; top:0; left:0; width:100vw; height:100vh; z-index:9999; cursor:crosshair; background:rgba(0,0,0,0.3);">
    <canvas id="pick-canvas"></canvas>
    <div id="pick-info" style="position:absolute; top:10px; left:10px; color:white; font-size:14px; background:rgba(0,0,0,0.6); padding:8px; border-radius:4px;">
        点击确认坐标 / 拖动框选区域
    </div>
    <button id="pick-cancel" style="position:absolute; top:10px; right:10px;">取消 (ESC)</button>
</div>
```

### 13.2 工具箱分类设计

```javascript
const TOOLBOX_CATEGORIES = [
    {
        id: "action",
        name: "动作节点",
        color: "#22c55e",
        nodes: [
            { type: "mouse_click", name: "鼠标点击", icon: "fa-mouse-pointer" },
            { type: "key_action", name: "按键动作", icon: "fa-keyboard" },
            { type: "mouse_scroll", name: "鼠标滚轮", icon: "fa-arrows-up-down" },
            { type: "text_input", name: "文本输入", icon: "fa-font" },
            { type: "wait", name: "等待", icon: "fa-clock" },
        ]
    },
    {
        id: "detection",
        name: "检测节点",
        color: "#eab308",
        nodes: [
            { type: "check_color", name: "颜色检测", icon: "fa-palette" },
            { type: "check_ocr", name: "OCR识别", icon: "fa-font" },
            { type: "check_image", name: "图像匹配", icon: "fa-image" },
            { type: "check_screen", name: "屏幕状态", icon: "fa-desktop" },
            { type: "check_pixel_diff", name: "帧差检测", icon: "fa-exchange-alt" },
        ]
    },
    {
        id: "control",
        name: "控制节点",
        color: "#a855f7",
        nodes: [
            { type: "if_else", name: "条件分支", icon: "fa-code-branch" },
            { type: "loop_count", name: "计数循环", icon: "fa-repeat" },
            { type: "loop_while", name: "条件循环", icon: "fa-sync" },
        ]
    },
    {
        id: "script_block",
        name: "动作块",
        color: "#3b82f6",
        nodes: [
            { type: "call_script_sync", name: "调用宏(同步)", icon: "fa-play" },
            { type: "call_script_async", name: "调用宏(异步)", icon: "fa-play-circle" },
        ]
    },
    {
        id: "monitor",
        name: "监视器",
        color: "#06b6d4",
        nodes: [
            { type: "monitor_color", name: "颜色监视", icon: "fa-eye" },
            { type: "monitor_ocr", name: "OCR监视", icon: "fa-eye" },
            { type: "monitor_timer", name: "定时器", icon: "fa-stopwatch" },
        ]
    },
    {
        id: "variable",
        name: "变量",
        color: "#f97316",
        nodes: [
            { type: "var_set", name: "设置变量", icon: "fa-equals" },
            { type: "var_math", name: "数学运算", icon: "fa-calculator" },
            { type: "var_compare", name: "比较", icon: "fa-not-equal" },
            { type: "var_string", name: "字符串操作", icon: "fa-text-width" },
            { type: "var_convert", name: "类型转换", icon: "fa-exchange-alt" },
        ]
    },
];
```

### 13.3 属性面板动态渲染规则

当选中节点时，`#property-panel-content` 被清空，根据 `node.type` 动态生成表单。
**渲染规则**：

| 参数类型 | 渲染为                        | 特殊处理                                       |
| -------- | ----------------------------- | ---------------------------------------------- |
| enum     | `<select>` 下拉框           | 选项列表由参数定义决定                         |
| number   | `<input type="number">`     | step 根据 mode 联动（relative 模式 step=0.01） |
| string   | `<input type="text">`       | 支持 `${var}` 语法高亮                       |
| array    | 多个 `<input>` 或专用编辑器 | rect 参数渲染为 4 个输入框                     |
| bool     | `<input type="checkbox">`   | —                                             |
| path     | `<input>` + 浏览按钮        | 点击浏览按钮打开文件选择对话框                 |
| coords   | `<input>` + 拾取按钮        | 点击拾取按钮进入坐标拾取模式                   |
| region   | 4个 `<input>` + 框选按钮    | 点击框选按钮进入区域框选模式                   |
| hwnd     | `<input>` + 窗口选择按钮    | 点击打开窗口列表下拉                           |

**坐标模式联动**：当用户切换坐标模式时，同一节点的所有坐标输入框的 step 和 placeholder 联动变化：

```javascript
function updateCoordInputs(mode) {
    const isRelative = (mode === "relative");
    document.querySelectorAll(".coord-input").forEach(input => {
        input.step = isRelative ? "0.01" : "1";
        input.placeholder = isRelative ? "0.0 ~ 1.0" : "逻辑像素";
    });
}
```

### 13.4 call_script 节点的内嵌编辑器

双击 `call_script_sync` 或 `call_script_async` 节点时，弹出模态框，复用现有的块编辑器 UI：

```javascript
function openBlockEditor(node) {
    const modal = document.createElement("div");
    modal.className = "modal-overlay";
    modal.innerHTML = `
        <div class="modal-content" style="width:90%; height:85%;">
            <div class="modal-header">
                <span>编辑动作块: ${node.params.path || "未选择文件"}</span>
                <button class="modal-close">✕</button>
            </div>
            <div class="modal-body" id="block-editor-container">
                <!-- 复用现有 editor.js 的渲染逻辑 -->
            </div>
            <div class="modal-footer">
                <button class="btn-save-block">保存到节点</button>
                <button class="btn-save-file">另存为文件</button>
                <button class="btn-cancel">取消</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
  
    // 初始化块编辑器
    initBlockEditor("block-editor-container", node.params.actions || []);
}
```

**"保存到节点"**：将编辑器中的动作列表序列化为 JSON 数组，存入节点的 `params.actions` 字段。运行时直接用这个数组调用 `compile_macro()`，不需要写文件。
**"另存为文件"**：将动作列表保存为 `.json` 文件到 `宏/` 目录，同时更新节点的 `params.path`。后续运行时从文件加载（支持在旧块编辑器中单独编辑该文件）。

### 13.5 坐标拾取器 UI

**单点拾取流程**：

```text
1. 用户在属性面板点击 [拾取] 按钮
2. #pick-overlay 显示，光标变为十字
3. 鼠标移动时，#pick-info 实时显示当前逻辑像素坐标
4. 用户点击，坐标确认
5. 调用 pywebview.api.pick_coordinate(mode) 获取物理像素
6. 反算为逻辑像素: logic = phys / dpi_scale
7. 填入对应输入框
8. #pick-overlay 隐藏
```

**区域框选流程**：

```text
1. 用户点击 [框选] 按钮
2. #pick-overlay 显示
3. 用户按下鼠标 → 记录起点
4. 拖动 → #pick-canvas 实时绘制矩形框
5. 释放鼠标 → 记录终点
6. 计算 rect = {x, y, w, h}（根据 mode 转换为逻辑像素或比例值）
7. 填入 4 个区域输入框
8. #pick-overlay 隐藏
```

### 13.6 状态栏设计

| 状态码            | 含义                     | 按钮状态                                    |
| ----------------- | ------------------------ | ------------------------------------------- |
| `IDLE`          | 空闲                     | 运行=可用, 停止=禁用, 暂停=禁用             |
| `RUNNING`       | 同步执行中               | 运行=禁用, 停止=可用, 暂停=禁用             |
| `RUNNING_ASYNC` | 异步执行中（有后台任务） | 运行=禁用, 停止=可用, 暂停=可用             |
| `PAUSED`        | 异步任务已暂停           | 运行=禁用, 停止=可用, 暂停=可用(显示"继续") |

**进度条**：不显示百分比（节点图没有线性的进度概念），改为显示"当前执行节点"的名称，类似状态指示器。

---

## 十四、前后端通信协议

### 14.1 统一返回格式

所有 Bridge API 返回：

```python
def _ok(data=None):
    return {"ok": True, "data": data, "error": None}
def _err(msg):
    return {"ok": False, "data": None, "error": msg}
```

### 14.2 API 列表

#### 脚本操作

| 方法                           | 参数               | 返回                      | 说明             |
| ------------------------------ | ------------------ | ------------------------- | ---------------- |
| `run_automation(graph_json)` | 节点图 JSON 字符串 | `{ok, data: {task_id}}` | 解析并启动执行   |
| `stop_automation()`          | —                 | `{ok}`                  | 停止所有执行     |
| `pause_automation(task_id)`  | 任务ID             | `{ok}`                  | 暂停指定异步任务 |
| `resume_automation(task_id)` | 任务ID             | `{ok}`                  | 恢复指定异步任务 |

#### 检测预览

| 方法                                      | 参数              | 返回                                              | 说明             |
| ----------------------------------------- | ----------------- | ------------------------------------------------- | ---------------- |
| `preview_color(mode, rect, hwnd)`       | 坐标模式和区域    | `{ok, data: {color, mean_color, image_base64}}` | 实时预览区域颜色 |
| `preview_ocr(mode, rect, hwnd, engine)` | 同上+引擎         | `{ok, data: {text, confidence, cost_ms}}`       | 实时预览OCR结果  |
| `preview_image(template_path, region)`  | 模板路径+搜索区域 | `{ok, data: {found, position, confidence}}`     | 实时预览找图结果 |

#### 坐标拾取

| 方法                      | 参数     | 返回                                               | 说明             |
| ------------------------- | -------- | -------------------------------------------------- | ---------------- |
| `pick_coordinate(mode)` | 坐标模式 | `{ok, data: {logic_x, logic_y, phys_x, phys_y}}` | 阻塞直到用户点击 |
| `pick_region(mode)`     | 坐标模式 | `{ok, data: {rect: [x,y,w,h]}}`                  | 阻塞直到用户框选 |

#### 系统信息

| 方法                  | 参数 | 返回                                           | 说明            |
| --------------------- | ---- | ---------------------------------------------- | --------------- |
| `get_screen_info()` | —   | `{ok, data: {width, height, dpi, monitors}}` | 屏幕信息        |
| `get_window_list()` | —   | `{ok, data: [{title, hwnd, class_name}]}`    | 窗口列表        |
| `get_ocr_engines()` | —   | `{ok, data: ["rapidocr", "paddleocr"]}`      | 已安装的OCR引擎 |

#### 文件操作

| 方法                             | 参数      | 返回                                     | 说明                              |
| -------------------------------- | --------- | ---------------------------------------- | --------------------------------- |
| `list_auto_scripts()`          | —        | `{ok, data: [{name, path, modified}]}` | 列出自动化脚本                    |
| `load_auto_script(path)`       | 文件路径  | `{ok, data: graph_json}`               | 加载脚本                          |
| `save_auto_script(path, json)` | 路径+JSON | `{ok}`                                 | 保存脚本                          |
| `list_macros()`                | —        | `{ok, data: [{name, path}]}`           | 列出旧格式宏（供call_script选择） |

### 14.3 后端回调前端

```python
# 在 AutomationApiMixin 中
def _notify_frontend(self, event_type, data):
    """通过 pywebview evaluate_js 回调前端"""
    try:
        js_code = f"window._automationEvents && window._automationEvents.{event_type}({json.dumps(data)})"
        pywebview.webview.windows[0].evaluate_js(js_code)
    except Exception:
        pass
```

| 事件                              | 数据                         | 触发时机           |
| --------------------------------- | ---------------------------- | ------------------ |
| `onNodeEnter(node_id)`          | `{node_id, type}`          | 执行器进入某个节点 |
| `onNodeExit(node_id)`           | `{node_id, result}`        | 执行器离开某个节点 |
| `onCheckResult(node_id, found)` | `{node_id, found, detail}` | 检测节点返回结果   |
| `onTaskStatus(task_id, status)` | `{task_id, status}`        | 异步任务状态变化   |
| `onMonitorTrigger(node_id)`     | `{node_id}`                | 监视器触发         |
| `onError(msg)`                  | `{message}`                | 执行出错           |
| `onScriptEnd(success)`          | `{success}`                | 脚本结束           |
| 前端监听：                        |                              |                    |

```javascript
window._automationEvents = {
    onNodeEnter: (data) => {
        highlightNode(data.node_id);  // 高亮当前执行的节点
        updateStatusbar(data.type);
    },
    onCheckResult: (data) => {
        flashNode(data.node_id, data.found ? "green" : "red");
    },
    // ...
};
```

---

## 十五、内置工具

### 15.1 坐标拾取器

作为编辑器内置功能，不是插件。实现在 `automation_bridge_api.py` 中。
**后端实现**：

```python
def pick_coordinate(self, mode="screen"):
    """阻塞直到用户点击，返回逻辑像素和物理像素"""
    import mouse
    result_event = threading.Event()
    result_data = {}
  
    def on_click(x, y, button, pressed):
        if pressed and button == mouse.Button.left:
            dpi_scale = get_dpi_scale()
            phys_x, phys_y = int(x), int(y)  # pynput 返回的是物理像素
            logic_x = phys_x / dpi_scale
            logic_y = phys_y / dpi_scale
            result_data.update({
                "logic_x": round(logic_x, 2),
                "logic_y": round(logic_y, 2),
                "phys_x": phys_x,
                "phys_y": phys_y,
            })
            result_event.set()
  
    listener = mouse.Listener(on_click=on_click)
    listener.start()
    result_event.wait()
    listener.stop()
    return self._ok(result_data)
```

### 15.2 OCR 模板训练器（P2）

用于固定格式数字（如游戏计时器）的高精度低延迟识别。
**工作流程**：

1. 用户指定检测区域
2. 截取当前画面
3. 在截图上标记每个字符的 bounding box
4. 为每个标记输入正确值
5. 提供多张样本增强鲁棒性
6. 导出为 `.tmpl` 文件（JSON + 裁剪图片）
   **运行时**：
7. 加载 `.tmpl` 文件
8. 截取检测区域
9. 按标记的 bounding box 裁剪出每个字符
10. 逐字符做模板匹配（归一化互相关）
11. 拼接结果
    **预期性能**：1-5ms，不需要加载 OCR 模型。
    **前端实现**：独立的模态框页面，内嵌 Canvas 用于标记。

---

## 十六、目录结构

```text
项目根目录/
├── 宏执行框架3.2.py              # [微调] options参数、move_to/scroll/中键、修饰键开关
├── precision_engine_v5.py        # [不修改] 新引擎路径1直接import precise_sleep_v5
├── webui_app.py                  # [微调] MacroBridge 继承 AutomationApiMixin
│
├── webui_backend/
│   ├── automation_engine.py      # [新增] 新引擎执行器（递归遍历、双轨调度、任务池）
│   ├── automation_compiler.py    # [新增] JSON → ExecGraph 解析器
│   ├── automation_bridge_api.py  # [新增] JS Bridge API（AutomationApiMixin 类）
│   ├── coordinate_resolver.py    # [新增] 坐标模式解析器
│   └── detection/                # [新增] 检测能力模块
│       ├── __init__.py
│       ├── capture.py            # mss 截图
│       ├── color.py              # numpy 颜色检测
│       ├── ocr.py                # RapidOCR 封装 + 帧差缓存
│       ├── matcher.py            # OpenCV 模板匹配
│       └── screen.py             # 屏幕亮度判断
│
├── webui/
│   ├── automation_editor.html    # [新增] 节点编辑器页面
│   └── modules/
│       ├── automation-core.js    # [新增] LiteGraph 初始化、画布配置
│       ├── automation-nodes.js   # [新增] 节点类型定义（LiteGraph Node 子类）
│       ├── automation-property.js# [新增] 属性面板动态渲染
│       ├── automation-tools.js   # [新增] 坐标拾取器、框选器
│       └── automation-events.js  # [新增] 后端事件监听、节点高亮
│
├── 宏/                           # [现有] 旧格式宏文件目录
├── 自动化脚本/                    # [新增] .auto.json 文件目录
└── 自动化模板/                    # [新增,P2] OCR模板 .tmpl 文件目录
```

---

## 十七、分阶段实施路径

### 阶段 0：旧引擎手脚改造（1-2天）

**目标**：不破坏现有功能的前提下，新增底层接口。
**任务**：

- [ ] `execute_macro_once` 增加 `options` 参数
- [ ] `_parse` 增加 `move_to`、`scroll`、中键解析
- [ ] `finally` 块增加 `auto_release_modifiers` 开关
- [ ] 回归测试：现有宏绑定行为不变
  **验收标准**：现有 `MACRO_BINDINGS` 中所有宏执行结果与改造前一致。

### 阶段 1：新引擎骨架与路径1直发（3-5天）

**目标**：搭建最小可用的执行框架，实现原子动作的直发执行。
**前端**：

- [ ] 重构 `automation_editor.html`（三栏布局 + canvas）
- [ ] `automation-core.js`：LiteGraph 初始化、画布平移缩放
- [ ] `automation-nodes.js`：P0 节点类定义（mouse_click、key_action、wait）
- [ ] 工具箱分类面板、拖拽创建节点
- [ ] 基础连线（flow 类型）
- [ ] `automation-property.js`：基础属性面板渲染
- [ ] 导出/导入 JSON
  **后端**：
- [ ] `automation_compiler.py`：JSON → ExecGraph 解析
- [ ] `automation_engine.py`：基础执行器（仅支持路径1节点）
- [ ] `automation_bridge_api.py`：run/stop API
- [ ] `coordinate_resolver.py`：screen 模式坐标解析
- [ ] `webui_app.py` 继承 AutomationApiMixin
  **验收**：前端画布实现【按键A】→【等待2秒】→【按键B】→ 循环5次，点击运行后后端正确执行。

### 阶段 2：路径2同步调用与坐标系统（2-3天）

**目标**：实现 call_script_sync，完成三种坐标模式。
**前端**：

- [ ] call_script_sync 节点
- [ ] 坐标模式联动 UI（mode 切换时输入框 step 变化）
- [ ] call_script 双击弹出块编辑器模态框
- [ ] 窗口选择下拉框
  **后端**：
- [ ] `coordinate_resolver.py`：window/relative 模式
- [ ] 路径2同步调用逻辑
- [ ] 超短动作优化（≤2步绕过 execute_macro_once）
- [ ] `get_window_list` API
  **验收**：

1. call_script_sync 加载旧 JSON 宏并正确执行
2. window 模式坐标在窗口移动后仍然准确
3. relative 模式坐标在不同分辨率下保持相对位置

### 阶段 3：检测能力接入（3-5天）

**目标**：实现颜色检测和 OCR 检测，打通"感知→决策→执行"链路。
**前端**：

- [ ] check_color 节点（含 match/no 两个 flow 输出）
- [ ] check_ocr 节点（含引擎选择下拉框）
- [ ] if_else 节点（含 data 端口连线支持）
- [ ] data 端口连线（红色布尔线）
- [ ] 检测预览按钮（在属性面板中）
- [ ] 节点执行高亮（onNodeEnter/onCheckResult 回调）
  **后端**：
- [ ] `detection/capture.py`：mss 截图
- [ ] `detection/color.py`：numpy 颜色检测
- [ ] `detection/ocr.py`：RapidOCR 封装 + 帧差缓存
- [ ] preview_color / preview_ocr API
- [ ] if_else 的 data 端口收集逻辑
  **验收**：

1. check_color → if_else → 不同分支，完整链路跑通
2. check_ocr(number_lt模式) → if_else → 分支，跑通
3. 前端点击"预览"能看到实时检测结果
4. 节点执行时有视觉高亮反馈

### 阶段 4：循环与变量系统（2-3天）

**目标**：实现循环节点的动态坐标刷新和变量系统。
**前端**：

- [ ] loop_count 节点
- [ ] var_set、var_math、var_compare、var_string、var_convert 节点
- [ ] 变量引用语法 `${var}` 在输入框中的支持
- [ ] 变量监视窗（底部状态栏区域，可选展开）
  **后端**：
- [ ] loop_count 执行器（含坐标动态刷新验证）
- [ ] 变量系统（类型、作用域、引用解析）
- [ ] 变量操作节点处理器
  **验收**：

1. loop_count 内 mouse_click(window模式) → 拖动窗口 → 坐标自动跟随
2. check_ocr → store_var → var_convert → var_compare → if_else 完整链路

### 阶段 5：并发调度与异步打断（3-5天，核心难点）

**目标**：实现异步任务、监视器触发、修饰键兜底释放。
**前端**：

- [ ] call_script_async 节点（含 completed/interrupted 输出端口）
- [ ] monitor_color 节点
- [ ] monitor_ocr 节点
- [ ] monitor_timer 节点
- [ ] 暂停/继续按钮功能
- [ ] 异步任务状态指示器（节点上显示小动画）
  **后端**：
- [ ] TaskPool 实现
- [ ] call_script_async 执行器
- [ ] 待执行分支队列机制
- [ ] 监视器轮询逻辑
- [ ] 监视器触发行为（stop_task/pause_task/branch）
- [ ] 修饰键兜底释放
- [ ] pause_automation / resume_automation API
  **验收**：

1. call_script_async 执行长连招 → monitor_color 检测到颜色 → 停止异步任务 → 走 trigger 分支
2. 打断后键盘无卡键残留
3. 暂停/恢复异步任务正常工作
4. monitor_timer 定时触发分支

### 阶段 6：UI 打磨与工具集成（3-5天）

**目标**：完善交互体验，集成坐标拾取等工具。

- [ ] 坐标拾取器（单点 + 区域框选）
- [ ] 小地图优化
- [ ] 节点搜索/快速添加
- [ ] 撤销/重做（Ctrl+Z/Ctrl+Y）
- [ ] 右键菜单（删除节点、复制节点、对齐）
- [ ] 键盘快捷键（Delete 删除、Ctrl+C/V 复制粘贴）
- [ ] 保存/加载 .auto.json 文件
- [ ] 执行日志面板（实时显示每步操作和检测结果）
- [ ] call_script 块编辑器的"保存到节点"功能
- [ ] 深色主题适配

### 阶段 7：高级功能（P2，按需）

- [ ] loop_while 节点
- [ ] sequence_check 节点
- [ ] state_machine 节点（含状态编辑 UI）
- [ ] check_image 节点（OpenCV 模板匹配）
- [ ] check_pixel_diff 节点
- [ ] check_screen 节点
- [ ] PaddleOCR 可选接入
- [ ] OCR 模板训练器
- [ ] call_script 动态坐标注入（方式B：占位符替换）
- [ ] 调试模式（单步执行、断点）

### 阶段 8：预设与生态（P3，按需）

- [ ] 预设节点（preset_click、preset_find_click 等）
- [ ] 脚本模板库（常见场景一键生成）
- [ ] 性能分析面板（各节点耗时统计）
- [ ] 自动化脚本分享格式

---

## 十八、与现有代码的集成要点

### 18.1 不需要修改的模块

| 模块                                   | 原因                                                                 |
| -------------------------------------- | -------------------------------------------------------------------- |
| `precision_engine_v5.py`             | 新引擎路径1直接 `from precision_engine_v5 import precise_sleep_v5` |
| `宏录制V2.1_3D.py`                   | 录制系统完全独立，产出旧格式 .json                                   |
| 旧 WebUI 的块编辑器 (`editor.js` 等) | 作为 call_script 节点的内嵌编辑器复用，不修改                        |
| 宏管理页面                             | 保持独立                                                             |

### 18.2 需要微调的模块

| 模块                 | 改动内容                                           | 改动量 |
| -------------------- | -------------------------------------------------- | ------ |
| `宏执行框架3.2.py` | options 参数、move_to/scroll/中键、修饰键开关      | ~50 行 |
| `webui_app.py`     | MacroBridge 继承 AutomationApiMixin，import 新模块 | ~10 行 |

### 18.3 需要新增的模块

| 模块                                                            | 代码量估算 | 复杂度                           |
| --------------------------------------------------------------- | ---------- | -------------------------------- |
| `automation_engine.py`                                        | ~400 行    | 高（双轨调度、任务池、分支队列） |
| `automation_compiler.py`                                      | ~200 行    | 中（JSON 解析、图构建）          |
| `automation_bridge_api.py`                                    | ~300 行    | 中（API 封装、坐标拾取、预览）   |
| `coordinate_resolver.py`                                      | ~80 行     | 低                               |
| `detection/capture.py`                                        | ~40 行     | 低                               |
| `detection/color.py`                                          | ~60 行     | 低                               |
| `detection/ocr.py`                                            | ~120 行    | 中（缓存逻辑）                   |
| `detection/matcher.py`                                        | ~80 行     | 中                               |
| `detection/screen.py`                                         | ~30 行     | 低                               |
| `automation_editor.html`                                      | ~300 行    | 中（布局结构）                   |
| `automation-core.js`                                          | ~200 行    | 中（LiteGraph 配置）             |
| `automation-nodes.js`                                         | ~500 行    | 中（节点类定义）                 |
| `automation-property.js`                                      | ~400 行    | 中高（动态表单渲染）             |
| `automation-tools.js`                                         | ~200 行    | 中（拾取器交互）                 |
| `automation-events.js`                                        | ~100 行    | 低                               |
| **总计**：后端 ~1,310 行 Python，前端 ~1,700 行 JS/HTML。 |            |                                  |

---

## 附录 A：LiteGraph.js 节点注册示例

```javascript
// automation-nodes.js
function MouseClickNode() {
    this.addInput("in", "flow");
    this.addOutput("next", "flow");
    this.addOutput("match", "flow");  // 不用于此节点，仅为统一
    this.properties = {
        mode: "screen",
        x: 0, y: 0,
        hwnd_var: "",
        button: "left",
        click_type: "click",
        hold_time: 0,
        move_duration: 0,
        before_delay: 0,
        after_delay: 0,
    };
    this.color = "#22c55e";
    this.title = "鼠标点击";
    this.size = [200, 120];
}
MouseClickNode.prototype.onExecute = function() {
    // LiteGraph 的 onExecute 不用于我们的执行逻辑
    // 真正的执行在后端 Python 中
};
MouseClickNode.prototype.onGetCode = function() {
    // 不需要生成代码，直接序列化 properties 即可
};
LiteGraph.registerNodeType("action/mouse_click", MouseClickNode);
function IfElseNode() {
    this.addInput("in", "flow");
    this.addInput("cond", "boolean");
    this.addOutput("true", "flow");
    this.addOutput("false", "flow");
    this.properties = {
        logic: "AND",
        fallback: "false",
    };
    this.color = "#a855f7";
    this.title = "条件分支";
    this.size = [180, 80];
}
LiteGraph.registerNodeType("control/if_else", IfElseNode);
function CheckColorNode() {
    this.addInput("in", "flow");
    this.addOutput("match", "flow");
    this.addOutput("no", "flow");
    this.addOutput("result", "boolean");
    this.properties = {
        mode: "screen",
        rect: [0, 0, 10, 10],
        hwnd_var: "",
        target_color: "#FF0000",
        tolerance: 10,
        check_mode: "contain",
        sample_mode: "center",
        store_var: "",
    };
    this.color = "#eab308";
    this.title = "颜色检测";
    this.size = [220, 160];
}
LiteGraph.registerNodeType("detection/check_color", CheckColorNode);
```

**关键设计决策**：LiteGraph.js 的 `onExecute` 方法不被使用。LiteGraph 只负责画布渲染、节点拖拽、连线可视化。实际的执行逻辑完全在后端 Python 中。前端在点击"运行"时，将整个图序列化为 JSON 发送给后端，后端解析并执行。
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

## 附录 B：节点图序列化与反序列化

从前端导出给后端的 JSON 格式：

```javascript
function serializeGraph(litegraph_instance) {
    const nodes = [];
    const connections = [];
  
    for (const node of litegraph_instance.graph._nodes) {
        nodes.push({
            id: node.id.toString(),
            type: node.type.replace(/\//g, "."),  // "action/mouse_click" → "action.mouse_click"
            position: { x: node.pos[0], y: node.pos[1] },
            params: { ...node.properties },
        });
    }
  
    for (const link of litegraph_instance.graph._links) {
        if (!link) continue;
        const origin_node = litegraph_instance.graph.getNodeById(link.origin_id);
        const target_node = litegraph_instance.graph.getNodeById(link.target_id);
  
        connections.push({
            id: link.id.toString(),
            from: {
                node: link.origin_id.toString(),
                port: origin_node.outputs[link.origin_slot].name,
            },
            to: {
                node: link.target_id.toString(),
                port: target_node.inputs[link.target_slot].name,
            },
            type: _getLinkType(origin_node, link.origin_slot),  // "flow" or "data"
        });
    }
  
    return { nodes, connections };
}
```

**端口类型判断规则**：

- 如果输出端口的类型是 `"flow"` → `type: "flow"`
- 如果输出端口的类型是 `"boolean"` / `"number"` / `"string"` → `type: "data"`

---

## 附录 C：错误处理规范

| 错误类型                   | 处理方式               | 前端表现                   |
| -------------------------- | ---------------------- | -------------------------- |
| 节点类型未知               | 跳过该节点，打印警告   | 节点显示红色边框           |
| 变量未定义                 | 使用默认值 0，打印警告 | 属性面板变量名显示黄色警告 |
| 坐标解析失败（窗口不存在） | 跳过该动作，打印错误   | 节点闪烁红色               |
| OCR 引擎未安装             | 返回错误，不执行检测   | 属性面板引擎选择显示红色   |
| 旧 JSON 宏文件不存在       | 跳过 call_script 节点  | 节点显示红色"文件不存在"   |
| 旧 JSON 宏编译失败         | 跳过 call_script 节点  | 节点显示编译错误信息       |
| 执行超时                   | 停止执行               | 状态栏显示"执行超时"       |
| 用户手动停止               | 设置 stop_event        | 状态栏显示"已停止"         |
