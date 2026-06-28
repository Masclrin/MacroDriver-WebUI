# 自动化引擎执行模型升级 — 详细设计说明

> **版本**: 1.0
> **日期**: 2026-04-30
> **关联文档**: `问题/Bug审查意见书.md`、`问题/atomation节点审查1~4.md`、`docs/bug-fix-review-prompt.md`
> **替代**: 本文档替代 `docs/fork_race_join_nested_design.md` 第13节（Race竞争模型部分），后者仅作存档，不必读取

---

## 0. 设计决策汇总

本文档记录的所有设计决策均来自 Bug 审查意见书的逐条讨论，以下是决策与审查意见书的对照：

| 审查编号       | 原始判定 | 新判定             | 决策摘要                                       | 本文档章节 |
| -------------- | -------- | ------------------ | ---------------------------------------------- | ---------- |
| A-37 (BUG-C7)  | 采纳     | 采纳（方案变更）   | race 执行模型缺陷→新增 race_win 节点          | §1        |
| R-04 (BUG-C6)  | 拒绝     | **采纳**     | fork next 端口重命名为"立即"，新增"完成"端口   | §2        |
| R-05 (BUG-C9)  | 拒绝     | **采纳**     | 条件类控制节点重新执行上游条件节点             | §3        |
| R-07 (BUG-P7)  | 拒绝     | **采纳**     | preset_read_text 必须输出文本数据              | §7        |
| R-11 (BUG-D4)  | 拒绝     | **采纳**     | 截图方式必须在终端报告                         | §8        |
| A-12 (BUG-M2)  | 采纳     | 采纳（方案扩展）   | 监视器循环模式 + 自动关闭条件                  | §4        |
| A-15 (BUG-U5)  | 采纳     | 采纳（方案明确）   | bookmark 实现 mode/hwnd_var + 每次引用重新计算 | §6        |
| A-16 (BUG-U4)  | 采纳     | **方案变更** | 常量节点保留 varRef，不限制灵活性              | §9        |
| A-38 (BUG-C5)  | 采纳     | **方案变更** | 重新执行上游条件节点，非"文档说明"             | §3        |
| D-26 (BUG-C10) | 后期考虑 | **采纳**     | 分支标识用户友好化（重命名+选择器）            | §5        |
| D-55 (BUG-L2)  | 后期考虑 | **拒绝**     | 数据端口+变量双路径是设计如此                  | —         |

---

## 1. Race 竞争模型与 race_win 节点

### 1.1 当前问题

`_handle_race` 的 `race_worker` 中 `_execute_flow(node.id, port_name, ctx)` 执行整个分支链直到末端才标记 winner。存在以下缺陷：

1. 没有"竞争结束点"——无法标识"到此竞争结束"
2. 取消其他分支时机太晚——要等赢家整条链跑完
3. 赢家分支无法继续执行后续节点——流程终止
4. 每个分支的后续动作可能不同——无法支持

### 1.2 典型游戏场景

```
Race（竞争：谁先检测到目标）
├── branch1: [检测红色怪物] → race_win → [攻击红色怪物的连招A]
├── branch2: [检测蓝色怪物] → race_win → [攻击蓝色怪物的连招B]
└── branch3: [检测BOSS动作]  → race_win → [BOSS闪避逻辑]
```

### 1.3 新增 `control/race_win` 节点

#### 节点定义

```python
registry.register_node({
    "type": "control/race_win",
    "category": "control",
    "display_name": "竞争胜出",
    "color": "#f59e0b",
    "inputs": [{"name": "in", "type": "flow"}],
    "outputs": [
        {"name": "next", "type": "flow"},
        {"name": "winner_branch", "type": "data_string"},
    ],
    "params_schema": {},
    "handler": "_handle_race_win",
})
```

#### 处理器逻辑

```python
def _handle_race_win(node, ctx):
    branch_id = ctx._get_branch_id()
    branch_ctx = ctx._branches.get(branch_id)

    if branch_ctx and branch_ctx.scope_id:
        scope = ctx._scopes.get(branch_ctx.scope_id)
        if scope:
            with ctx._data_lock:
                if scope.winner_branch_id is None:
                    scope.winner_branch_id = branch_id
                    race_event = ctx._race_events.get(scope.scope_id)
                    if race_event:
                        race_event.set()

            for bid in scope.branch_ids:
                if bid != branch_id:
                    bctx = ctx._branches.get(bid)
                    if bctx and bctx.status == "running":
                        bctx.cancel()
                _cancel_child_scopes(bid, ctx)

    ctx.check_results[f"{node.id}.winner_branch"] = branch_id
    _execute_flow(node.id, "next", ctx)
```

核心要点：

1. 到达 `race_win` 时立即标记当前分支为 winner 并通知 race 主线程
2. 立即取消同一 scope 内的其他分支（包括子作用域）
3. **当前分支继续执行 `next` 端口**，走自己的后续逻辑
4. 输出 `winner_branch` 数据，供后续节点读取

### 1.4 `_handle_race` 改造

```python
def _handle_race(node: ExecNode, ctx: ExecContext):
    # 创建 scope，增加 winner_branch_id 字段
    scope = Scope(
        scope_id=scope_id,
        fork_node_id=node.id,
        parent_branch_id=parent_branch_id,
        winner_branch_id=None,
    )

    # 将 race_event 存入 ctx，供 race_win 访问
    ctx._race_events[scope_id] = race_event

    # race_worker 中不再设置 winner（由 race_win 负责）
    def race_worker(bid, bctx, port_name, core_idx):
        try:
            ctx._set_branch_id(bid)
            _execute_flow(node.id, port_name, ctx)
            bctx.set_status("completed")
        except Exception as e:
            bctx.set_status("error")
        finally:
            # 向后兼容：如果分支执行完还没有 winner，将当前分支设为 winner
            scope = ctx._scopes.get(scope_id)
            if scope and scope.winner_branch_id is None and bctx.status == "completed":
                with race_lock:
                    if scope.winner_branch_id is None:
                        scope.winner_branch_id = bid
                        race_event.set()
                for other_bid in scope.branch_ids:
                    if other_bid != bid:
                        other_bctx = ctx._branches.get(other_bid)
                        if other_bctx and other_bctx.status == "running":
                            other_bctx.cancel()

    # 主线程只负责等待和超时处理
    deadline = time.time() + timeout_ms / 1000.0 if timeout_ms > 0 else None
    while not race_event.is_set() and not ctx.stop_event.is_set():
        if deadline and time.time() >= deadline:
            break
        race_event.wait(timeout=0.05)

    # 超时处理：如果没有任何分支到达 race_win，取消所有分支
    if scope.winner_branch_id is None:
        for bid in scope.branch_ids:
            bctx = ctx._branches.get(bid)
            if bctx and bctx.status == "running":
                bctx.cancel()
            _cancel_child_scopes(bid, ctx)
```

### 1.5 数据结构变更

```python
@dataclass
class Scope:
    scope_id: str
    fork_node_id: str
    parent_branch_id: str
    branch_ids: list[str]
    child_scope_ids: list[str]
    status: str
    winner_branch_id: str = None  # 新增

class ExecContext:
    def __init__(self, ...):
        self._race_events: dict[str, threading.Event] = {}  # 新增
```

### 1.6 Race + Join 汇合

多分支共享后续时，用 Join(any) 汇合：

```
Race
├── branch1: [检测红色] → race_win → [连招A] ──┐
├── branch2: [检测蓝色] → race_win → [连招B] ──┤→ Join(any) → [公共收尾]
└── branch3: [检测BOSS]  → race_win → [闪避]  ──┘
```

部分分支汇合：

```
Race
├── branch1: [检测红色] → race_win → [近战连招] ──┐
├── branch2: [检测蓝色] → race_win → [近战连招] ──┤→ Join(any) → [近战收尾]
└── branch3: [检测BOSS]  → race_win → [闪避]  → [重新检测]
```

Join 与 Race 配合规则：

| Join wait_mode              | 行为                            | 适用性                  |
| --------------------------- | ------------------------------- | ----------------------- |
| `any`                     | 任一分支到达即触发              | **Race 场景推荐** |
| `all` + cancel_others     | 等同 any（被取消分支不会到达）  | 可用但冗余              |
| `all`（无 cancel_others） | 被取消分支永远不到达，Join 超时 | **不适用**        |

### 1.7 向后兼容

分支中无 `race_win` 节点时，`race_worker` 的 finally 块会在整条链执行完后标记 winner，行为与旧版一致。

### 1.8 前端定义

```javascript
'control/race_win': {
    display_name: '竞争胜出',
    color: '#f59e0b',
    category: 'control',
    icon: 'fa-solid fa-trophy',
    inputs: [{name:'in', type:'flow'}],
    outputs: [
        {name:'next', type:'flow'},
        {name:'winner_branch', type:'data_string'}
    ],
    params_schema: {}
}
```

### 1.9 修改文件清单

| 文件                               | 修改内容                                                                   |
| ---------------------------------- | -------------------------------------------------------------------------- |
| `automation/nodes/control.py`    | 新增 `control/race_win` 节点注册                                         |
| `automation/handlers/control.py` | 新增 `_handle_race_win`；改造 `_handle_race`                           |
| `automation/engine.py`           | `Scope` 增加 `winner_branch_id`；`ExecContext` 增加 `_race_events` |
| `webui/modules/auto/nodes.js`    | 新增 `control/race_win` 前端定义                                         |

---

## 2. Fork "立即"端口重命名与"完成"端口

### 2.1 当前问题

Fork 的 `next` 端口语义是"与分支并行执行"，但用户直觉认为 `next` = "fork 之后"（所有分支完成后执行）。语义误导导致用户困惑。

### 2.2 设计方案

#### 端口重命名

`next` → `立即`（前端显示名），端口内部名保持 `next` 不变（避免破坏已保存脚本的连线）。

```python
# 后端定义不变，仅改 display_name
"outputs": [
    {"name": "next", "type": "flow", "display_name": "立即"},  # 改名
    {"name": "branch1", "type": "flow"},
    {"name": "branch2", "type": "flow"},
]
```

前端渲染时使用 `display_name`，连线序列化仍使用 `name`。

#### 新增"完成"端口

```python
"outputs": [
    {"name": "next", "type": "flow", "display_name": "立即"},
    {"name": "done", "type": "flow", "display_name": "完成"},
    {"name": "branch1", "type": "flow"},
    {"name": "branch2", "type": "flow"},
]
```

"完成"端口的语义：**该 Fork 的所有分支全部执行完毕后触发**。

### 2.3 处理器逻辑

```python
def _handle_fork(node: ExecNode, ctx: ExecContext):
    # ... 创建 scope、分支、线程（与现有逻辑相同）

    # 立即端口：与分支并行执行（原有逻辑）
    _execute_flow(node.id, "next", ctx)

    # 完成端口：等待所有分支结束
    all_done_event = threading.Event()
    remaining = [len(active_branches)]  # 用列表包装以允许闭包修改
    done_lock = threading.Lock()

    def on_branch_done(bid):
        with done_lock:
            remaining[0] -= 1
            if remaining[0] <= 0:
                all_done_event.set()

    # 在每个 branch_worker 的 finally 中调用 on_branch_done
    for branch_info in active_branches:
        # ... 启动线程
        original_worker = branch_worker
        def wrapped_worker(bid, *args, **kwargs):
            try:
                original_worker(bid, *args, **kwargs)
            finally:
                on_branch_done(bid)

    # 等待所有分支完成（不阻塞主线程——在独立线程中等待）
    def wait_all_done():
        while not all_done_event.is_set() and not ctx.stop_event.is_set():
            all_done_event.wait(timeout=0.1)
        if not ctx.stop_event.is_set():
            _execute_flow(node.id, "done", ctx)

    t = threading.Thread(target=wait_all_done, daemon=True)
    t.start()
```

### 2.4 Fork 与 Join 的区别

|               | Fork "完成"                  | Join "done"                |
| ------------- | ---------------------------- | -------------------------- |
| 等待范围      | 该 Fork 的**所有**分支 | 连到 Join 的分支（可部分） |
| 灵活性        | 固定等全部                   | 可选 any/all/custom        |
| cancel_others | 不支持                       | 支持                       |
| 适用场景      | 简单的"全做完再继续"         | 复杂的分支汇合控制         |

### 2.5 前端定义

```javascript
'control/fork': {
    // ...
    outputs: [
        {name:'next', type:'flow', display_name:'立即'},
        {name:'done', type:'flow', display_name:'完成'},
        {name:'branch1', type:'flow'},
        {name:'branch2', type:'flow'}
    ],
    // ...
}
```

### 2.6 用户提示

在 Fork 节点的属性面板中，对"立即"端口添加说明文字："此端口与各分支同时执行，不等分支完成。如需等待所有分支完成，请使用'完成'端口。"

### 2.7 修改文件清单

| 文件                               | 修改内容                                                        |
| ---------------------------------- | --------------------------------------------------------------- |
| `automation/nodes/control.py`    | Fork outputs 增加 `done` 端口，`next` 增加 `display_name` |
| `automation/handlers/control.py` | `_handle_fork` 增加"完成"端口等待逻辑                         |
| `webui/modules/auto/nodes.js`    | Fork 前端定义增加 `done` 端口，`next` 显示名改为"立即"      |

---

## 3. 条件类控制节点 — 上游条件重新执行机制

### 3.1 当前问题

`loop_while`、`if_else`、`wait_cond`、`seq_check`、`state_machine` 等条件类控制节点，在求值条件时只读取 `check_results` 缓存，不会重新执行上游条件节点。导致：

- `loop_while` 循环条件永远不更新
- `wait_cond` 条件永远不更新
- 循环体内检测节点结果不更新（配合 A-04 修复后部分解决）

### 3.2 设计方案

**核心原则**：条件类控制节点每次需要求值条件时，自动重新执行**直接连到其 cond 数据输入端口的那个上游节点**。

**追溯范围**：只追溯作为条件直接连入的**单个节点**，不递归追溯更上游。如果用户想实现复杂逻辑，需自行设计循环结构。

### 3.3 实现机制

```python
def _re_execute_condition_sources(node, ctx):
    """
    重新执行直接连到 node 的 cond 数据输入端口的上游节点。
    只执行直接上游，不递归。
    """
    data_sources = node.get_data_inputs("cond")
    for src in data_sources:
        src_node_id = src["source_node_id"]
        src_node = ctx.graph.nodes.get(src_node_id)
        if src_node:
            # 只重新执行检测类/条件类节点，不执行动作类节点
            if src_node.type.startswith(("detection/", "monitor/", "utility/condition")):
                # 从 executed_set 中移除，允许重新执行
                branch_ctx = ctx._get_current_branch_ctx()
                executed_set = branch_ctx._executed_nodes if branch_ctx else ctx._executed_nodes
                with ctx._data_lock:
                    executed_set.discard(src_node_id)
                _execute_node(src_node_id, ctx)
```

### 3.4 各节点改造

#### loop_while

```python
def _handle_loop_while(node, ctx):
    max_iter = int(node.params.get("max_iterations", 10000))
    check_at = node.params.get("check_at", "start")

    for i in range(max_iter):
        if ctx.stop_event.is_set():
            return

        if check_at == "start":
            _re_execute_condition_sources(node, ctx)  # 新增
            data_sources = node.get_data_inputs("cond")
            conditions = [ctx.check_results.get(f"{src['source_node_id']}.{src['source_port']}", False)
                          for src in data_sources]
            if not conditions or not all(conditions):
                break

        if i > 0:
            _reset_body_nodes(body_nodes, ctx)
        _execute_flow(node.id, "body", ctx)

        if check_at == "end":
            _re_execute_condition_sources(node, ctx)  # 新增
            data_sources = node.get_data_inputs("cond")
            conditions = [ctx.check_results.get(f"{src['source_node_id']}.{src['source_port']}", False)
                          for src in data_sources]
            if not conditions or not all(conditions):
                break

    _execute_flow(node.id, "next", ctx)
```

#### wait_cond

```python
def _handle_wait_cond(node, ctx):
    timeout = float(node.params.get("timeout", 10000))
    interval = float(node.params.get("interval", 100))
    deadline = time.time() + timeout / 1000.0

    while time.time() < deadline:
        _re_execute_condition_sources(node, ctx)  # 新增：每次检查前重新执行上游
        data_sources = node.get_data_inputs("cond")
        conditions = [ctx.check_results.get(f"{src['source_node_id']}.{src['source_port']}", False)
                      for src in data_sources]
        if conditions and all(conditions):
            _execute_flow(node.id, "met", ctx)
            return
        precise_sleep(interval / 1000.0, ctx.stop_event)

    _execute_flow(node.id, "timeout", ctx)
```

#### if_else

```python
def _handle_if_else(node, ctx):
    _re_execute_condition_sources(node, ctx)  # 新增：求值前重新执行上游
    data_sources = node.get_data_inputs("cond")
    # ... 后续逻辑不变
```

#### seq_check / state_machine

同理，在每次条件求值前调用 `_re_execute_condition_sources`。

### 3.5 安全限制

- **只重新执行检测类/条件类/监视器类节点**，不执行动作类节点（避免误触发鼠标点击等）
- **只追溯直接上游**，不递归
- 变量引用方式（`cond_var="${found}"`）不触发重新执行——用户需将检测节点放在循环体内

### 3.6 修改文件清单

| 文件                               | 修改内容                                                                                      |
| ---------------------------------- | --------------------------------------------------------------------------------------------- |
| `automation/engine.py`           | 新增 `_re_execute_condition_sources` 函数                                                   |
| `automation/handlers/control.py` | `loop_while`/`wait_cond`/`if_else`/`seq_check`/`state_machine` 增加条件重新执行调用 |

---

## 4. 监视器循环模式与自动关闭条件

### 4.1 当前问题

- `auto_stop` 参数完全无效——无论 True/False，触发后总是 break
- `auto_stop=False` 时用户期望"持续监听多次触发"，但实际只触发一次就停止
- 没有自动关闭条件——监视器可能永久运行，导致 Fork "完成"端口永远不触发

### 4.2 设计方案

#### 循环模式（auto_stop=False）

监视器触发后执行后续节点，然后**自动回到监视状态**继续监听。

**并发策略**：并发模式——每次触发启动新线程执行后续节点，与监视线程并行。

**防抖参数**：新增 `recheck_delay_ms` 参数，控制触发后再次检测的等待时间。

```
monitor_color(血条<30%, auto_stop=False, recheck_delay_ms=500)
  → [吃药]
```

执行流程：

1. 监视线程检测到条件满足
2. 启动新线程执行 `[吃药]`
3. 等待 `recheck_delay_ms` 毫秒
4. 回到监视状态继续检测

#### 自动关闭条件

新增参数：

| 参数                    | 类型   | 默认值 | 说明                                 |
| ----------------------- | ------ | ------ | ------------------------------------ |
| `max_triggers`        | number | 0      | 最大触发次数（0=无限）               |
| `auto_close_after_ms` | number | 0      | 最后一次触发后多久自动关闭（0=无限） |

当 `max_triggers > 0` 时，触发达到次数后自动停止监视。
当 `auto_close_after_ms > 0` 时，最后一次触发后经过指定时间无新触发，自动停止。

### 4.3 节点定义变更

```python
registry.register_node({
    "type": "monitor/color",
    # ...
    "params_schema": {
        # ... 原有参数
        "auto_stop": {"type": "boolean", "default": True, "description": "触发后是否自动停止此监视器"},
        "recheck_delay_ms": {"type": "number", "default": 0, "description": "触发后再次检测的等待时间(ms, 0=立即)", "showWhen": "auto_stop=false"},
        "max_triggers": {"type": "number", "default": 0, "description": "最大触发次数(0=无限)", "showWhen": "auto_stop=false"},
        "auto_close_after_ms": {"type": "number", "default": 0, "description": "最后一次触发后自动关闭时间(ms, 0=无限)", "showWhen": "auto_stop=false"},
    },
})
```

### 4.4 处理器逻辑

```python
def _handle_monitor_color(node, ctx):
    auto_stop = node.params.get("auto_stop", True)
    recheck_delay_ms = float(_resolve_value(node.params.get("recheck_delay_ms", 0), ctx))
    max_triggers = int(_resolve_value(node.params.get("max_triggers", 0), ctx))
    auto_close_after_ms = float(_resolve_value(node.params.get("auto_close_after_ms", 0), ctx))

    trigger_count = 0
    last_trigger_time = None

    while not ctx.stop_event.is_set():
        # ... 检测逻辑（与现有相同）
        if matched:
            trigger_count += 1
            last_trigger_time = time.time()

            # 并发执行后续节点
            def run_trigger():
                _execute_flow(node.id, "match", ctx)

            t = threading.Thread(target=run_trigger, daemon=True)
            t.start()

            # 检查自动关闭条件
            if auto_stop:
                break
            if max_triggers > 0 and trigger_count >= max_triggers:
                break

            # 防抖等待
            if recheck_delay_ms > 0:
                precise_sleep(recheck_delay_ms / 1000.0, ctx.stop_event)

        # 检查超时自动关闭
        if auto_close_after_ms > 0 and last_trigger_time is not None:
            if (time.time() - last_trigger_time) * 1000 >= auto_close_after_ms:
                break

        # ... 等待间隔
        precise_sleep(interval / 1000.0, ctx.stop_event)

    _execute_flow(node.id, "next", ctx)
```

### 4.5 与 Fork "完成"端口的配合

监视器在 Fork 分支中且 `auto_stop=False` 时，如果设置了 `max_triggers` 或 `auto_close_after_ms`，监视器最终会停止，Fork "完成"端口可以正常触发。

如果监视器没有设置自动关闭条件（永久运行），Fork "完成"端口将永远不触发——这是预期行为，用户应确保永久监视器有合理的终止条件。

### 4.6 修改文件清单

| 文件                               | 修改内容                                                                              |
| ---------------------------------- | ------------------------------------------------------------------------------------- |
| `automation/nodes/monitor.py`    | 所有监视器节点增加 `recheck_delay_ms`/`max_triggers`/`auto_close_after_ms` 参数 |
| `automation/handlers/monitor.py` | 改造所有监视器处理器，支持循环模式 + 自动关闭条件                                     |
| `webui/modules/auto/nodes.js`    | 前端定义同步增加参数                                                                  |

---

## 5. 分支标识用户友好化

### 5.1 当前问题

- `stop_branch`/`pause_branch`/`resume_branch` 的 `target_branch` 参数需要填写运行时分支ID（如 `5_race_branch2`），用户无法知道
- Join 的 `branch_required_1~8` 显示"分支1必须到达"——哪个是分支1？
- `race_win` 的 `winner_branch` 输出运行时ID，用户看不懂
- 调试日志中的分支ID无法对应到图上的节点

### 5.2 设计方案：重命名 + 选择器

#### 5.2.1 分支端口重命名

允许用户给 Fork/Race 的分支端口重命名。默认名称为 `branch1`/`branch2`，用户可改为 `红色检测`/`蓝色检测`/`BOSS检测`。

```python
# Fork/Race 节点 params_schema 增加分支命名参数
"params_schema": {
    "branch_count": {"type": "number", "default": 2, "min": 2, "max": 8, "description": "分支数量"},
    "branch_name_1": {"type": "string", "default": "branch1", "description": "分支1名称"},
    "branch_name_2": {"type": "string", "default": "branch2", "description": "分支2名称"},
    # ...
}
```

前端渲染时，如果 `branch_name_1` 不为空且非默认值，端口显示用户命名。

#### 5.2.2 分支选择器

`stop_branch`/`pause_branch`/`resume_branch` 的 `target_branch` 参数改为**分支选择器**，类似 `nodeRef`。

```python
"params_schema": {
    "target_branch": {
        "type": "string",
        "default": "all_others",
        "description": "目标分支",
        "branchRef": True,  # 新增标记：分支引用
    }
}
```

前端渲染 `branchRef` 时，提供下拉选择器：

1. 固定选项：`all_others`（所有其他分支）
2. 动态选项：扫描当前图中的所有 Fork/Race 节点，列出其分支端口名（含用户重命名）

```javascript
// property.js 中新增 _renderBranchRefField
_renderBranchRefField: function(key, schema, node) {
    var select = document.createElement('select');
    // 固定选项
    var optAll = document.createElement('option');
    optAll.value = 'all_others';
    optAll.textContent = '所有其他分支';
    select.appendChild(optAll);

    // 扫描图中的 Fork/Race 节点
    var graph = AutomationCore.getGraph();
    for (var nid in graph.nodes) {
        var n = graph.nodes[nid];
        if (n.type === 'control/fork' || n.type === 'control/race') {
            var branchCount = n.properties.branch_count || 2;
            for (var i = 1; i <= branchCount; i++) {
                var portName = 'branch' + i;
                var customName = n.properties['branch_name_' + i] || '';
                var displayName = customName && customName !== portName
                    ? customName
                    : (n._customName || n.type) + '.' + portName;
                var opt = document.createElement('option');
                opt.value = nid + '.' + portName;
                opt.textContent = displayName;
                select.appendChild(opt);
            }
        }
    }
    return select;
}
```

后端处理器解析 `target_branch` 时：

- `all_others` → 取消所有其他分支（原有逻辑）
- `5.branch1` → 取消节点5的branch1分支（精确控制）
- `5.红色检测` → 如果用户重命名了，用命名查找

### 5.3 race_win 的 winner_branch 输出

`winner_branch` 输出改为**用户可读的分支标识**（如 `Race1.红色检测`），而非运行时ID（如 `5_race_branch2`）。

### 5.4 修改文件清单

| 文件                               | 修改内容                                                                                                |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `automation/nodes/control.py`    | Fork/Race 增加 `branch_name_N` 参数；stop/pause/resume_branch 的 `target_branch` 增加 `branchRef` |
| `automation/handlers/control.py` | `_resolve_target_branch` 支持 `nodeId.portName` 格式解析                                            |
| `webui/modules/auto/nodes.js`    | 前端定义同步                                                                                            |
| `webui/modules/auto/property.js` | 新增 `_renderBranchRefField`                                                                          |
| `webui/modules/auto/core.js`     | 分支端口显示用户命名                                                                                    |

---

## 6. Bookmark 节点实现

### 6.1 当前问题

`utility/bookmark` 的 `mode` 和 `hwnd_var` 参数在处理器中完全未使用，误导用户以为坐标模式生效。

### 6.2 设计定位

Bookmark 的本意是：**快捷存储常用位置框，供其他节点调用**。每次被下游节点引用时，应重新计算当前值（而非只计算一次缓存）。

### 6.3 实现方案

#### 节点定义

```python
registry.register_node({
    "type": "utility/bookmark",
    "category": "utility",
    "display_name": "位置书签",
    "color": "#6366f1",
    "inputs": [{"name": "in", "type": "flow"}],
    "outputs": [
        {"name": "next", "type": "flow"},
        {"name": "rect_1", "type": "data_string"},
        {"name": "rect_2", "type": "data_string"},
        {"name": "rect_3", "type": "data_string"},
    ],
    "params_schema": {
        "bookmark_count": {"type": "number", "default": 1, "min": 1, "max": 3, "description": "书签数量"},
        "mode_1": {"type": "string", "enum": ["screen", "window", "relative"], "default": "screen", "description": "位置1坐标模式"},
        "region_1": {"type": "string", "default": "[0,0,0,0]", "description": "位置1区域(x,y,w,h)", "format": "region"},
        "hwnd_var_1": {"type": "string", "default": "", "description": "位置1窗口变量", "showWhen": "mode_1=window,mode_1=relative", "varRef": True},
        "name_1": {"type": "string", "default": "位置1", "description": "位置1名称"},
        # mode_2, region_2, hwnd_var_2, name_2 ... (根据 bookmark_count 动态)
    },
    "handler": "_handle_bookmark",
})
```

#### 处理器逻辑

```python
def _handle_bookmark(node, ctx):
    bookmark_count = int(node.params.get("bookmark_count", 1))
    for i in range(1, bookmark_count + 1):
        mode = node.params.get(f"mode_{i}", "screen")
        region_raw = _resolve_value(node.params.get(f"region_{i}", "[0,0,0,0]"), ctx)
        hwnd_var = _extract_var_name(node.params.get(f"hwnd_var_{i}", ""))

        region = _parse_region(region_raw)
        if mode in ("window", "relative") and hwnd_var:
            hwnd = ctx.safe_get_variable(hwnd_var)
            if hwnd:
                region = convert_region(region, mode, hwnd)

        ctx.check_results[f"{node.id}.rect_{i}"] = json.dumps(region)

    _execute_flow(node.id, "next", ctx)
```

#### 每次引用重新计算

配合 §3 的条件重新执行机制，当 bookmark 被条件类节点引用时，会自动重新执行以更新值。

对于非条件类节点（如动作节点引用 bookmark 的 rect），需要在引擎层面支持"数据端口读取时重新计算上游"——这属于 §10 执行模型架构变更的一部分。

短期方案：bookmark 在每次被 `_execute_flow` 经过时重新计算（即放在循环体内即可更新）。

### 6.4 修改文件清单

| 文件                               | 修改内容               |
| ---------------------------------- | ---------------------- |
| `automation/nodes/utility.py`    | 重写 bookmark 节点定义 |
| `automation/handlers/utility.py` | 实现 bookmark 处理器   |
| `webui/modules/auto/nodes.js`    | 前端定义同步           |

---

## 7. 预设节点数据输出

### 7.1 当前问题

`preset_read_text` 读取了 OCR 文本但不输出文本数据，后续节点无法获取读取的内容。

### 7.2 设计方案

`preset_read_text` 增加文本数据输出端口：

```python
registry.register_node({
    "type": "preset/read_text",
    # ...
    "outputs": [
        {"name": "next", "type": "flow"},
        {"name": "text", "type": "data_string"},
        {"name": "error", "type": "flow"},
    ],
    # ...
})
```

处理器中：

```python
ctx.check_results[f"{node.id}.text"] = ocr_result
```

`preset_find_click` 不增加数据输出——用户如需坐标数据应使用 `check_image` + `mouse_click` 组合。

### 7.3 修改文件清单

| 文件                              | 修改内容                                        |
| --------------------------------- | ----------------------------------------------- |
| `automation/nodes/preset.py`    | `preset_read_text` 增加 `text` 数据输出端口 |
| `automation/handlers/preset.py` | 处理器写入 `check_results`                    |
| `webui/modules/auto/nodes.js`   | 前端定义同步                                    |

---

## 8. 截图方式报告

### 8.1 当前问题

截图源未连接时，检测节点静默回退到 mss 截图，用户以为在用 DXGI，实际在用 mss，无任何提示。

### 8.2 设计方案

在检测节点首次截图时，检查并报告使用的截图方式：

```python
def capture_screen(region=None, ctx=None):
    if ctx is not None and hasattr(ctx, '_capture_manager'):
        cm = ctx._capture_manager
        if cm is not None:
            if not getattr(ctx, '_capture_method_reported', False):
                print(f"[截图] 使用 DXGI 后台采集 (FPS: {cm.fps})")
                ctx._capture_method_reported = True
            return cm.capture(region)

    if not getattr(ctx, '_capture_method_reported', False):
        print("[截图] 使用 mss 截图 (未连接截图源节点或 DXGI 未启动)")
        ctx._capture_method_reported = True
    return _capture_mss(region)
```

### 8.3 修改文件清单

| 文件                                | 修改内容                            |
| ----------------------------------- | ----------------------------------- |
| `automation/detection/capture.py` | `capture_screen` 增加截图方式报告 |

---

## 9. 常量节点保留 varRef

### 9.1 决策

`utility/const_number` 和 `utility/const_string` 保留 `varRef: True`，不限制灵活性。

常量节点的"常量"含义是"方便用户直接设置的值"，而非"不可变"。用户可能需要 `const_number` 的值来自变量（如 `${config_delay}`），这样可以统一修改一个变量来调整所有引用处的延迟。

### 9.2 修改文件清单

无需修改——维持现状即可。审查意见书中的 A-16 修复方案从"移除 varRef"改为"保留 varRef"。

---

## 10. 执行模型架构变更

### 10.1 模型演进

综合以上所有设计决策，系统的执行模型正在从"单次 DAG"演进为"事件驱动 + 局部重执行"：

| 特性         | 原始 DAG 模型      | 新模型                             |
| ------------ | ------------------ | ---------------------------------- |
| 节点执行次数 | 一次（循环内除外） | 监视器可无限次触发                 |
| 条件更新     | 读取缓存值         | 自动重新执行上游条件节点           |
| 分支生命周期 | 执行完即结束       | 监视器分支可永久存活               |
| 数据流       | 自顶向下一次       | bookmark 等可被多次读取            |
| 终止方式     | 执行到末端         | race_win 主动终止 + 监视器条件终止 |
| 分支汇合     | Join 阻塞等待      | Fork "完成"端口 + Join 灵活汇合    |

### 10.2 引擎核心能力需求

1. **局部重新执行**——不是从头开始，而是只执行指定节点及其数据依赖
2. **节点级循环**——监视器的循环触发模式
3. **分支完成通知**——Fork "完成"端口的事件回调机制
4. **并发触发安全**——监视器并发触发时的线程安全

### 10.3 实施建议

以上改动应作为一个**整体执行模型升级**来规划，而不是逐个 bug 修复。建议分阶段实施：

**阶段1（P0）**：修复致命缺陷

- A-01 check_screen 函数名
- A-02 seq_check/state_machine 缺端口
- A-03 goto executed_set
- A-04 check_results 重置
- A-06~A-11 varRef 崩溃

**阶段2（P1）**：执行模型核心升级

- §1 race_win 节点 + race 改造
- §2 Fork "立即"重命名 + "完成"端口
- §3 条件重新执行机制
- §4 监视器循环模式

**阶段3（P2）**：用户体验完善

- §5 分支标识友好化
- §6 bookmark 实现
- §7 preset_read_text 数据输出
- §8 截图方式报告
- 其余审查意见书 P2 项目

---

## 11. 验证测试场景

### Race + race_win

- [ ] Race → 2分支(各有race_win) → 第一个到达后取消另一个，赢家继续后续
- [ ] Race → 2分支(各有race_win) → 各自后续不同，无Join
- [ ] Race → 2分支(各有race_win) → 后续接Join(any)，公共收尾
- [ ] Race → 3分支(部分汇合Join) → branch1/2共享后续，branch3独立
- [ ] Race → 2分支(无race_win) → 向后兼容，整条链执行完算赢
- [ ] Race → 超时 → 所有分支取消
- [ ] Race → 嵌套Race → 内层race_win不影响外层

### Fork "完成"端口

- [ ] Fork → 2分支 → 完成 → 后续节点执行
- [ ] Fork → 1分支含监视器(auto_stop=False, max_triggers=3) → 完成 → 3次触发后执行
- [ ] Fork → 1分支含监视器(auto_stop=False, 无关闭条件) → 完成永远不触发

### 条件重新执行

- [ ] loop_while + 颜色检测(cond数据连线) → 每次循环重新检测
- [ ] wait_cond + 颜色检测(cond数据连线) → 每次检查重新检测
- [ ] if_else + 颜色检测(cond数据连线) → 求值前重新检测
- [ ] loop_while + 变量引用(cond_var) → 不自动重新执行（用户需放循环体内）

### 监视器循环模式

- [ ] monitor_color(auto_stop=False) → 多次触发，每次启动新线程
- [ ] monitor_color(auto_stop=False, recheck_delay_ms=500) → 触发后等500ms再检测
- [ ] monitor_color(auto_stop=False, max_triggers=3) → 3次后自动停止
- [ ] monitor_color(auto_stop=False, auto_close_after_ms=5000) → 5秒无触发自动停止

### 分支标识

- [ ] Fork 分支重命名为"红色检测"/"蓝色检测" → 选择器显示用户命名
- [ ] stop_branch 选择特定分支 → 精确取消
- [ ] race_win winner_branch 输出 → 显示用户可读名称

### Bookmark

- [ ] bookmark(mode=screen) → 输出正确区域
- [ ] bookmark(mode=relative, hwnd_var=xxx) → 根据窗口位置动态计算
- [ ] bookmark 在循环内 → 每次循环重新计算

---

*文档版本: 1.0*
*日期: 2026-04-30*
