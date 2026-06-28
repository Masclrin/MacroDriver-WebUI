# 宏驱动 WebUI - Fork/Join 并发架构设计书

## 1. 项目现状

### 1.1 项目概述
宏驱动 WebUI 是一个基于 Python + Webview 的自动化宏执行平台，支持可视化节点编辑器设计自动化流程。当前版本处于测试阶段，核心用户群体较小，允许进行不兼容的架构重构。

### 1.2 现有执行架构

#### 1.2.1 执行模型
- **主执行流**：单线程顺序执行，由 `_execute_flow()` → `_execute_node()` 驱动
- **监视器**：后台轮询线程（daemon），当前无执行输入端口，在自动化开始时同步启动
- **异步任务**：`TaskPool` 支持异步子宏执行，但缺少通用的多分支并发能力

#### 1.2.2 核心组件
| 组件 | 文件路径 | 职责 |
|------|----------|------|
| 执行引擎 | `automation/engine.py` | 主执行循环、上下文管理、任务池 |
| 节点编译器 | `automation/compiler.py` | 图解析、节点连接关系构建 |
| 节点注册 | `automation/nodes/*.py` | 各类型节点定义（动作、检测、控制、监视器） |
| 节点处理器 | `automation/handlers/*.py` | 各类型节点的执行逻辑 |
| 精度引擎 | `engine/precision.py` | 高分辨率定时器、忙等、自适应补偿、绑核 |
| 前端核心 | `webui/modules/auto/core.js` | 节点编辑器画布、连接管理 |
| 节点定义 | `webui/modules/auto/nodes.js` | 前端节点注册与分类 |

#### 1.2.3 性能基础设施
- **高分辨率定时器**：`HighResTimer`（WaitableTimerEx），微秒级精度，释放 GIL
- **混合忙等**：x64 原生机器码 + 100μs 脉冲，亚毫秒级尾延迟控制
- **自适应补偿器**：`AdaptiveCompensator`（线程本地），动态修正调度偏差
- **优先级提升**：进程级 REALTIME_PRIORITY_CLASS，线程级 THREAD_PRIORITY_TIME_CRITICAL
- **线程绑核**：`set_thread_affinity(core_index=3)`，默认绑定到第 4 核

#### 1.2.4 当前问题
1. **无显式并发机制**：无法在设计时明确表达"同时执行 A 和 B"
2. **监视器不可控**：监视器在自动化开始时全局启动，不能按需启用/停用
3. **顺序执行瓶颈**：开始节点多出线时，子节点顺序执行而非并发
4. **绑核单一**：所有执行集中在单个核心，多分支场景下互相争抢

---

## 2. 新设计需求

### 2.1 核心目标
引入 **Fork/Join** 并发控制等多种节点，实现可控的多分支并行执行，同时保证宏动作执行的低延迟特性。

### 2.2 设计原则
1. **显式优于隐式**：并发必须通过 Fork 节点显式声明
2. **可控性**：用户可决定每个分支是否绑核、绑哪个核心
3. **容错隔离**：分支异常不影响其他分支
4. **向后不兼容**：测试阶段直接重构，不保留旧监视器行为

---

## 3. 架构设计

### 3.1 新增节点

#### 3.1.1 Fork 节点（并发分支）
```
类型：control/fork
显示名：并发执行
输入：in（流程）
输出：branch1 ~ branch8（流程，动态渲染）
参数：
  - branch_affinity_1: 分支1绑核设置（见 3.3 绑核设计）
  - branch_affinity_2: 分支2绑核设置
  - ...
  - branch_affinity_N: 分支N绑核设置
```

**行为语义**：
- 接收到 `in` 流程后，为每个有连接的 branch 端口启动独立线程
- 主线程**继续执行 Fork 的下一个节点**（Fire-and-Forget 语义）
- 每个分支线程独立执行其下游节点图

#### 3.1.2 Join 节点（并发汇合）
```
类型：control/join
显示名：等待汇合
输入：branch1 ~ branch8（流程，动态渲染，与 Fork 对应）
输出：done（流程）
参数：
  - wait_mode: "all" | "any" | "custom"（默认 all）
  - branch_required_1: 分支1是否必须到达（wait_mode=custom 时显示）
  - branch_required_2: 分支2是否必须到达
  - ...
  - timeout_ms: 超时时间（0=无限）
  - cancel_others: 是否取消未到达的分支（默认 false）
```

**行为语义**：
- **all 模式**：所有已连接的 branch 都必须有分支到达，才触发 `done`
- **any 模式**：任一分支到达即触发 `done`
- **custom 模式**：用户通过勾选框决定每个 branch 是否必须到达
- **超时**：超过 timeout_ms 后，强制触发 `done`（无论是否满足条件）
- **cancel_others**：当 Join 触发 `done` 时，若设为 `true`，则向所有未到达的分支发送停止信号，强制终止其执行；若为 `false`，未到达的分支继续在后台运行
- 前端展示已连接的节点列表，每个节点后有勾选框控制 `branch_required_N`

#### 3.1.3 Race 节点（竞争执行）
```
类型：control/race
显示名：竞争执行
输入：in（流程）
输出：branch1 ~ branch8（流程，动态渲染）
参数：
  - cancel_on_first: 首个分支到达后是否取消其他分支（默认 true）
  - timeout_ms: 超时时间（0=无限）
```

**行为语义**：
- 接收到 `in` 流程后，为每个有连接的 branch 端口启动独立线程
- 主线程**阻塞等待**，直到任一分支到达 Race 的下游汇合点
- 当任一分支先到达时：
  - 若 `cancel_on_first=true`（默认）：立即向其他所有分支发送停止信号，强制终止其执行
  - 若 `cancel_on_first=false`：其他分支继续在后台运行
- 获胜分支的后续流程继续执行
- 适用于"检测到条件即中断其他分支"的竞赛场景

**与 Join(any+cancel_others) 的区别**：
- Race 是**阻塞等待**语义，主线程在 Race 处等待，不会继续执行下游
- Join 是**汇合点**语义，需要分支主动连接到 Join 的输入端口
- Race 更适合"谁先完成谁赢"的竞赛模式；Join 更适合"多分支协作后汇合"的模式

### 3.2 监视器改造

#### 3.2.1 所有监视器添加执行输入端口
```python
# 改造前
"inputs": [],
"outputs": [{"name": "trigger", "type": "flow"}],

# 改造后
"inputs": [{"name": "in", "type": "flow"}],
"outputs": [
    {"name": "trigger", "type": "flow"},
    {"name": "timeout", "type": "flow"},  # 统一添加超时输出
],
```

#### 3.2.2 移除自动全局启动
- 删除 `ExecGraph.monitor_entry_ids` 的自动收集逻辑
- 删除监视器自动启动相关代码
- 监视器必须通过流程连接显式触发（如 开始 → Fork → 监视器）
- 支持作为 Fork 分支被启动，实现"计时器并发"等场景

#### 3.2.3 受影响的监视器类型
- `monitor/monitor_color`（颜色监视）
- `monitor/monitor_ocr`（OCR 监视）
- `monitor/monitor_timer`（定时器）
- `monitor/monitor_time`（时间监视）

#### 3.2.4 监视器 on_trigger 行为改进
**保留现有 `on_trigger` 功能**，并新增 `resume_task` 选项：

```python
"on_trigger": {
    "type": "string",
    "enum": ["branch", "stop_all", "stop_task", "pause_task", "resume_task"],
    "default": "branch",
    "description": "触发行为"
}
```

| 选项 | 行为 |
|------|------|
| `branch` | 只触发流程输出，不操作任务（默认） |
| `stop_all` | 停止整个自动化流程 + 所有异步任务 |
| `stop_task` | 停止指定的异步宏任务 |
| `pause_task` | 暂停指定的异步宏任务 |
| `resume_task` | **新增**：恢复指定的异步宏任务 |

**`target_task` 参数改进**：
```python
"target_task": {
    "type": "string",
    "default": "",
    "description": "目标异步宏节点",
    "showWhen": "on_trigger=stop_task,pause_task,resume_task",
    "nodeRef": "script_block/call_script_async",  # 前端支持下拉框选择
    "varRef": True  # 支持变量引用（如 ${task_id}）
}
```

**前端展示要求**：
- `target_task` 字段提供**下拉框选择**当前图中所有 `call_script_async` 节点
- 同时**保留手动输入**，支持直接填入节点ID或变量引用（`${变量名}`）
- 下拉框选项格式：`节点显示名 #节点ID`

**触发后行为**：
- 无论 `on_trigger` 为何值，触发后**始终继续执行** `trigger` 或 `timeout` 端口的下游节点
- `on_trigger` 的操作（如 stop_task）与流程执行是**并行**的，不阻塞下游

### 3.3 新增控制节点

#### 3.3.1 StopBranch 节点（停止分支）
```
类型：control/stop_branch
显示名：停止分支
输入：in（流程）
输出：next（流程）
参数：
  - target_branch: "all_others" | "branch_id" | "${变量}"（默认 all_others）
    - "all_others"：停止除当前分支外的所有兄弟分支
    - "branch_id"：停止指定分支ID
    - "${变量}"：从变量中读取目标分支ID
```

**行为语义**：
- 执行时向目标分支发送停止信号
- 然后继续执行 `next` 端口下游
- 用于流程级的分支精细控制

#### 3.3.2 PauseBranch 节点（暂停分支）
```
类型：control/pause_branch
显示名：暂停分支
输入：in（流程）
输出：next（流程）
参数：
  - target_branch: "all_others" | "branch_id" | "${变量}"（默认 all_others）
```

#### 3.3.3 ResumeBranch 节点（恢复分支）
```
类型：control/resume_branch
显示名：恢复分支
输入：in（流程）
输出：next（流程）
参数：
  - target_branch: "all_others" | "branch_id" | "${变量}"（默认 all_others）
```

**与监视器 on_trigger 的关系**：
- 监视器的 `stop_task`/`pause_task`/`resume_task` 是**检测触发时自动执行**
- `StopBranch`/`PauseBranch`/`ResumeBranch` 是**流程执行到该节点时执行**
- 两者**互补**，不是替代关系

### 3.4 绑核设计（核心决策）

#### 3.4.1 设计选择
采用 **"Fork 节点统一配置各分支绑核"** 方案：
- 每拉出一个分支，Fork 的详细参数中自动增加一行绑核配置
- 用户可为每个分支独立决定是否绑核、绑哪个核心

#### 3.4.2 绑核参数结构
```python
"params_schema": {
    f"branch_affinity_{i}": {
        "type": "object",
        "default": {"enabled": False, "core": -1},  # -1 = 自动推荐
        "properties": {
            "enabled": {"type": "boolean", "default": False, "description": "是否绑核"},
            "core": {"type": "number", "default": -1, "description": "绑定核心索引（-1=自动）"},
        }
    }
    # i = 1..8，根据实际连接的分支动态渲染
}
```

#### 3.4.3 智能核心推荐
Fork 节点初始化时，需要获取系统 CPU 信息：
- 总核心数（物理核心 + 超线程）
- 当前已被绑定的核心状态（通过全局追踪或实时检测）

**推荐策略**：
1. 主线程默认绑定核心 3（保留现有行为）
2. 分支1推荐核心 4，分支2推荐核心 5，以此类推
3. 跳过已被占用的核心（如果用户在其他 Fork 中已绑定）
4. 前端显示每个核心的占用状态（空闲/已占用/推荐）

#### 3.4.4 绑核生命周期
```
Fork 启动分支线程
    → 线程初始化时应用绑核设置（如果 enabled）
    → 分支执行下游节点
    → 分支到达 Join 或结束节点
    → 线程结束前释放绑核（重置亲和性掩码为全核心）
```

**关键问题**：主线程的绑核是否会被子线程继承？
- Python `threading.Thread` 创建的线程**不继承**父线程的亲和性掩码
- 因此子线程默认在所有核心上运行，需要显式调用 `set_thread_affinity()` 才会绑核
- 这意味着：主线程绑核到核心 3，子线程如果不配置绑核，就在全核心运行；如果配置了，就按配置绑核

#### 3.4.5 宏执行任务的绑核继承
当分支中包含 `call_script_sync` 或 `call_script_async` 节点时：
- **同步调用**：在分支线程中直接执行，继承分支线程的绑核设置
- **异步调用**：通过 `TaskPool` 创建新线程，**继承父分支的绑核设置**

**TaskPool 改进**：
```python
def start(self, node_id, compiled, macro_name, options, 
          stop_event_parent, on_complete=None, affinity=None) -> str:
    def worker():
        if affinity is not None:
            set_thread_affinity(affinity)
        # ... 执行宏
```

在 `_handle_call_script_async` 中传递当前分支的绑核设置：
```python
task_id = ctx.task_pool.start(
    # ...
    affinity=ctx._current_affinity,  # 传递当前分支的绑核
)
```

### 3.5 分支上下文隔离

#### 3.5.1 共享状态（线程安全）
以下状态通过 `ExecContext` 共享，使用 `RLock` 保护：
- `variables`：全局变量表
- `check_results`：检测结果表
- `stop_event`：全局停止事件
- `errors`：错误日志

#### 3.5.2 独立状态（每个分支隔离）
以下状态需要分支级别隔离：
- `_executed_nodes`：已执行节点集合（防止重复执行）
- `_goto_target`：跳转目标（单值，分支内有效）
- `_upstream_outputs` / `_upstream_node_id`：上游输出上下文

**实现方案**：
- `ExecContext` 增加 `_branch_id` 字段
- `_executed_nodes` 改为 `dict[branch_id, set]` 或每个分支维护独立集合
- Join 节点检测分支到达时，通过 `branch_id` 标识

#### 3.5.3 分支独立停止事件
每个分支拥有独立的 `branch_stop_event`，用于 Race/Join 的取消操作：
```python
class BranchContext:
    def __init__(self, branch_id, parent_ctx):
        self.branch_id = branch_id
        self.thread = None
        self.stop_event = threading.Event()  # 分支独立的停止事件
        self.status = "running"  # running / completed / error / cancelled
```

Race/Join 的 `cancel_others` 通过设置目标分支的 `branch_stop_event` 实现，不影响全局 `ctx.stop_event`。

### 3.6 异常处理策略

#### 3.6.1 分支异常隔离
- 某分支抛出异常 → 仅标记该分支执行失败
- 该分支无法到达 Join 节点（如果 Join 要求所有分支，则超时后触发 done）
- 其他分支不受影响，继续执行

#### 3.6.2 异常传播
- 分支异常记录到 `ctx.errors`（线程安全）
- 如果 Join 的 `wait_mode` 是 `all`，且某分支异常退出，则：
  - 若配置了超时：超时后触发 `done`
  - 若未配置超时：Join 永久阻塞（需要在 UI 层面警告用户）

---

## 4. 需要修改的模块

### 4.1 后端（Python）

#### 4.1.1 `automation/nodes/control.py`
- 新增 Fork 节点定义
- 新增 Join 节点定义
- 新增 Race 节点定义
- 新增 StopBranch / PauseBranch / ResumeBranch 节点定义

#### 4.1.2 `automation/handlers/control.py`
- 实现 `_handle_fork()` 处理器
- 实现 `_handle_join()` 处理器
- 实现 `_handle_race()` 处理器
- 实现 `_handle_stop_branch()` / `_handle_pause_branch()` / `_handle_resume_branch()` 处理器

#### 4.1.3 `automation/nodes/monitor.py`
- 所有监视器添加 `"inputs": [{"name": "in", "type": "flow"}]`
- 统一添加 `"timeout"` 输出端口
- `on_trigger` 枚举新增 `"resume_task"`
- `target_task` 新增 `"nodeRef"` 和 `"varRef"` 属性

#### 4.1.4 `automation/handlers/monitor.py`
- 修改 `_handle_monitor_node()`：支持从 `in` 端口触发启动
- 修改 `_handle_monitor_time()`：同上
- `_apply_on_trigger()` 新增 `resume_task` 支持

#### 4.1.5 `automation/compiler.py`
- 删除 `monitor_entry_ids` 的自动收集逻辑
- 删除监视器自动启动相关代码
- 新增 Fork/Join/Race 节点的连接合法性校验

#### 4.1.6 `automation/engine.py`
- `ExecContext` 增加分支隔离支持（`_branch_id`, `_branch_executed_nodes` 等）
- 新增 `BranchContext` 类，管理分支独立状态
- `_execute_flow()`：支持并发分支启动（Fork 场景）
- 新增全局绑核状态追踪（用于智能推荐）
- `TaskPool.start()` 增加 `affinity` 参数

#### 4.1.7 `engine/precision.py`
- 新增 `clear_thread_affinity()` 函数（释放绑核）
- 新增 `get_system_cpu_info()` 函数（获取核心数）

### 4.2 前端（JavaScript）

#### 4.2.1 `webui/modules/auto/nodes.js`
- 注册 Fork/Join/Race 节点定义
- 注册 StopBranch/PauseBranch/ResumeBranch 节点定义
- 更新监视器节点定义（添加输入端口、更新 on_trigger 枚举）

#### 4.2.2 `webui/modules/auto/core.js`
- 节点渲染：支持动态端口（Fork/Join/Race 的 branch 端口根据连接数动态增减）
- 连接逻辑：Fork 每增加一个输出连接，自动渲染新的 branch 端口
- Join/Race 的 branch 端口与上游 Fork 对应

#### 4.2.3 `webui/modules/auto/property.js`
- Fork 节点属性面板：动态渲染各分支的绑核配置
- Join 节点属性面板：展示已连接的节点列表 + 勾选框
- **新增 `_renderNodeRefField`**：支持下拉框选择节点 + 手动输入 + 变量引用
- 核心状态可视化：空闲/已占用/推荐

**`_renderNodeRefField` 实现要求**：
```javascript
_renderNodeRefField: function(key, schema, val, node) {
    // 1. 获取当前图中所有指定类型的节点（如 call_script_async）
    // 2. 渲染下拉框，选项格式：节点显示名 #节点ID
    // 3. 下拉框支持选择，同时保留文本输入框支持手动输入和变量引用
    // 4. 支持 varRef 按钮，点击后弹出变量选择器
}
```

### 4.3 数据格式

#### 4.3.1 图 JSON 结构变化
Fork + Join + Race 节点连接示例：
```json
{
  "nodes": [
    {"id": "1", "type": "flow/start", ...},
    {"id": "2", "type": "control/fork", "params": {"branch_affinity_1": {"enabled": true, "core": 4}}},
    {"id": "3", "type": "script_block/call_script_async", "params": {"path": "macro1.json"}},
    {"id": "4", "type": "monitor/monitor_color", "params": {"target_color": "#FF0000", "on_trigger": "stop_task", "target_task": "3"}},
    {"id": "5", "type": "control/join", "params": {"wait_mode": "any", "cancel_others": true, "timeout_ms": 30000}},
    {"id": "6", "type": "control/race", "params": {"cancel_on_first": true, "timeout_ms": 10000}},
    {"id": "7", "type": "flow/end", ...}
  ],
  "connections": [
    {"from": {"node": "1", "port": "next"}, "to": {"node": "2", "port": "in"}, "type": "flow"},
    {"from": {"node": "2", "port": "branch1"}, "to": {"node": "3", "port": "in"}, "type": "flow"},
    {"from": {"node": "2", "port": "branch2"}, "to": {"node": "4", "port": "in"}, "type": "flow"},
    {"from": {"node": "3", "port": "next"}, "to": {"node": "5", "port": "branch1"}, "type": "flow"},
    {"from": {"node": "4", "port": "trigger"}, "to": {"node": "5", "port": "branch2"}, "type": "flow"},
    {"from": {"node": "5", "port": "done"}, "to": {"node": "7", "port": "in"}, "type": "flow"}
  ]
}
```

---

## 5. 使用场景示例

### 5.1 场景1：宏执行 + 监视器中断（Race 模式）
```
[开始] → [Race] ──┬─branch1(绑核:核心3)→ [调用宏(同步):连段A] ──→ [Race出口]
                  └─branch2(绑核:核心4)→ [监视器:检测怪物抬手] ─┘
                                           ↓ (trigger)
                                      [调用宏(同步):连段B] → [结束]
```
- 连段A 在核心 3 上精确执行
- 监视器在核心 4 上后台检测
- 检测到怪物抬手时：
  - Race 立即设置 branch1 的 branch_stop_event
  - 连段A 在 `precise_sleep` 或输入操作中检测到停止信号，立即中断
  - 继续执行 branch2 下游的"连段B"
- 如果连段A 先执行完毕：
  - Race 取消 branch2 的监视器
  - 继续执行连段A 的下游（如果有）

### 5.2 场景2：宏执行 + 计时器超时控制（Fork + Join）
```
[开始] → [Fork] ──┬─branch1(绑核:核心4)→ [调用宏(异步):连段A] ──→ [Join:any+cancel]
                  └─branch2(不绑核)────→ [监视器:计时器 10s] ──┘
                                           ↓ (trigger)
                                      [停止分支:all_others] → [结束]
```
- 连段A 在核心 4 上精确执行（异步，不阻塞主流程）
- 计时器在任意核心后台运行
- 10 秒后计时器触发，Join(any+cancel) 触发：
  - 停止 branch1 的异步宏
  - 继续执行 Join 下游

### 5.3 场景3：多检测并行等待（Fork + Join）
```
[开始] → [Fork] ──┬─branch1→ [颜色检测:等待红色]
                  ├─branch2→ [OCR检测:等待"完成"]
                  └─branch3→ [定时器:5秒超时]
                  
[Join: wait_mode=any] ←─┬─← branch1
                         ├─← branch2
                         └─← branch3
                         
[Join] → [结束]
```
- 三个检测同时运行
- 任一条件满足即继续（any 模式）
- 5 秒超时保底

### 5.4 场景4：开局启动多个监视器
```
[开始] → [Fork] ──┬─branch1→ [颜色监视:血条检测]
                  ├─branch2→ [OCR监视:状态检测]
                  └─branch3→ [主流程:正常执行]
```
- 所有监视器作为 Fork 分支同时启动
- 主流程不受监视器阻塞

### 5.5 场景5：暂停/恢复宏执行
```
[开始] → [Fork] ──┬─branch1→ [调用宏(异步):自动战斗]
                  └─branch2→ [监视器:检测玩家血量低]
                                   ↓ (trigger + pause_task=branch1)
                              [调用宏(同步):喝药恢复]
                              [恢复分支:branch1]
                              [结束]
```
- 自动战斗宏在 branch1 异步执行
- 血量低时监视器触发，暂停 branch1 的宏
- 执行喝药恢复
- 恢复 branch1 的宏继续执行

---

## 6. 风险与注意事项

### 6.1 GIL 限制
- Python GIL 意味着多线程在 CPU 密集型操作上并非真正并行
- 但宏执行主要是"睡眠 + I/O（输入模拟）"，GIL 影响较小
- 如果未来需要 CPU 密集型并行，考虑 `multiprocessing`

### 6.2 绑核过度
- 绑核过多会导致某些核心满载，其他核心空闲
- 建议限制：保留至少 1-2 个核心给系统和后台进程
- 前端需要警告用户"绑核过多可能影响系统稳定性"

### 6.3 Join/Race 死锁
- `wait_mode=all` 时，如果某分支进入无限循环或异常退出，Join 可能永久阻塞
- 必须配置 `timeout_ms` 作为保底
- 前端默认填充一个合理的超时值（如 30000ms）

### 6.4 监视器改造影响
- 所有现有自动化脚本中的监视器都需要重新连接流程
- 需要在更新日志中明确标注"破坏性变更"

### 6.5 异步宏绑核继承
- 异步宏任务继承父分支的绑核设置，但 `threading.Thread` 不继承亲和性
- 需要在 `TaskPool.start()` 中显式设置绑核
- 如果异步宏内部再创建子线程，绑核不会继续继承

---

## 7. 实现阶段规划

### Phase 1：基础 Fork/Join/Race + 监视器改造
1. 实现 Fork 节点（基础并发启动）
2. 实现 Join 节点（all / any / custom 模式 + cancel_others）
3. 实现 Race 节点（竞争执行 + cancel_on_first）
4. 改造所有监视器（添加 in 端口，移除自动启动）
5. 修改编译器（删除 monitor_entry_ids 逻辑）
6. 实现分支上下文隔离（BranchContext、独立 _executed_nodes）

### Phase 2：分支控制 + 绑核优化
1. 实现 StopBranch / PauseBranch / ResumeBranch 节点
2. 实现 Fork 分支绑核配置
3. 实现智能核心推荐算法
4. 实现绑核生命周期管理（启动绑定 / 结束释放）
5. 异步宏任务继承父分支绑核
6. 前端核心状态可视化

### Phase 3：监视器改进 + 前端优化
1. 监视器 `on_trigger` 新增 `resume_task`
2. `target_task` 支持下拉框选择 + 手动输入 + 变量引用
3. 前端 `_renderNodeRefField` 实现
4. Join 超时默认填充与死锁检测
5. 性能基准测试（并发 vs 顺序的延迟对比）

### Phase 4：文档与示例
1. 更新节点文档
2. 提供示例脚本（竞争执行、多监视器、暂停恢复等场景）
3. 更新日志标注破坏性变更

---

## 8. 附录

### 8.1 术语表
| 术语 | 说明 |
|------|------|
| Fork | 并发分支节点，将一个流程分裂为多个并行分支 |
| Join | 并发汇合节点，等待多个分支到达后汇合 |
| Race | 竞争执行节点，谁先完成谁赢，其他分支可被取消 |
| 绑核 | 将线程绑定到特定 CPU 核心运行，减少调度延迟 |
| GIL | Python 全局解释器锁，限制多线程真正并行 |
| Fire-and-Forget | 启动任务后不等待其完成，继续执行主流程 |
| BranchContext | 分支上下文，管理分支独立状态（停止事件、执行状态等） |

### 8.2 相关文件清单
- `automation/engine.py` - 执行引擎核心
- `automation/compiler.py` - 图编译器
- `automation/nodes/control.py` - 控制节点定义
- `automation/handlers/control.py` - 控制节点处理器
- `automation/nodes/monitor.py` - 监视器节点定义
- `automation/handlers/monitor.py` - 监视器节点处理器
- `engine/precision.py` - 精度与绑核工具
- `webui/modules/auto/core.js` - 前端画布核心
- `webui/modules/auto/nodes.js` - 前端节点定义
- `webui/modules/auto/property.js` - 前端属性面板
