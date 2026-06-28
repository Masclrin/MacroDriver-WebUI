# Fork/Race/Join 嵌套与高级汇合设计文档 Done

## 1. 当前痛点

### 1.1 分支管理扁平化

现有 `ExecContext._branches` 是一个全局字典，所有 Fork/Race 创建的分支平铺存放：

- `fork1_branch1`, `fork1_branch2`, `race1_race_branch1`...
- **没有层级关系**，无法表达"Fork2 嵌套在 Fork1 的 branch3 里"

### 1.2 Join 无法区分分支来源

Join 节点仅通过 `ctx._get_upstream_node_id()` 判断到达者，**不知道到达者属于哪个 Fork/Race**：

- 多个 Fork-Join 对共存时，Join 会误收其他 Fork 的分支
- `cancel_others` 会**全局取消所有 running 分支**，误杀无关分支

### 1.3 嵌套 Fork/Race 状态不可见

外层 Join 无法感知内层 Fork/Race 创建的分支：

```
Fork1 ──→ branch3 ──→ Fork2 ──→ branch1 ──→ [C]
                                    └─→ branch2 ──→ [D]
```

Fork1 的 Join 不知道 Fork2 的存在，无法正确等待 branch3 的"子分支"。

### 1.4 复杂连线无法支持

用户直觉上期望的连线方式当前无法正确运行：

- Fork1 的 branch1/2 走 Join1，branch3/4 走另一个 Join
- Race 后接 Join（虽然简单场景能跑，但 cancel 逻辑混乱）
- Fork → Join → Fork 链式嵌套
- 跨层级分支汇合（Fork2 的分支 + Fork1 的分支 汇入同一个 Join）

***

## 2. 设计目标

1. **符合用户直觉**：Join 等待"所有连到它的分支"，不管来自哪一层嵌套
2. **cancel 向前追溯**：Join 触发 cancel 时，只取消"连到它的分支及其子分支"，不影响后续节点
3. **自动推断 + 显式兜底**：Join 自动根据连线图解析目标分支，复杂情况允许用户显式指定
4. **Fork/Race 可互相嵌套**：Fork 里可以有 Race，Race 里可以有 Fork，Join 可以接入任意层级

***

## 3. 核心概念：作用域树（Scope Tree）

### 3.1 作用域（Scope）

每个 **Fork** 或 **Race** 节点执行时创建一个作用域。作用域记录了：

- 哪个节点创建的（fork\_node\_id）
- 从哪个父分支创建的（parent\_branch\_id）
- 包含哪些分支（branch\_ids）
- 子作用域（child\_scope\_ids）—— 用于嵌套

```python
@dataclass
class Scope:
    scope_id: str              # "{fork_node_id}_scope"
    fork_node_id: str          # 创建者节点 ID
    parent_branch_id: str      # 从哪个分支创建的（None 表示顶级）
    branch_ids: list[str]      # 这个作用域内的所有分支 ID
    child_scope_ids: list[str] # 子作用域（嵌套 Fork/Race 创建）
    status: str                # "running" | "completed" | "cancelled"
```

### 3.2 作用域树示例

```
ExecContext
├── _scopes
│   ├── "fork1_scope": Scope(
│   │   fork_node_id="fork1",
│   │   parent_branch_id=None,
│   │   branch_ids=["fork1_branch1", "fork1_branch2", "fork1_branch3", "fork1_branch4"],
│   │   child_scope_ids=["fork2_scope"]
│   │ )
│   └── "fork2_scope": Scope(
│   │   fork_node_id="fork2",
│   │   parent_branch_id="fork1_branch3",  # ← 关键！绑定到父分支
│   │   branch_ids=["fork2_branch1", "fork2_branch2"],
│   │   child_scope_ids=[]
│   │ )
│
├── _branches
│   ├── "fork1_branch1": BranchContext(scope_id="fork1_scope", ...)
│   ├── "fork1_branch2": BranchContext(scope_id="fork1_scope", ...)
│   ├── "fork1_branch3": BranchContext(scope_id="fork1_scope", ...)
│   ├── "fork2_branch1": BranchContext(scope_id="fork2_scope", parent_branch_id="fork1_branch3", ...)
│   └── "fork2_branch2": BranchContext(scope_id="fork2_scope", parent_branch_id="fork1_branch3", ...)
```

### 3.3 BranchContext 改造

```python
class BranchContext:
    def __init__(self, branch_id, parent_ctx, fork_node_id=None,
                 parent_branch_id=None, scope_id=None, ...):
        self.branch_id = branch_id
        self.parent_ctx = parent_ctx          # ExecContext
        self.fork_node_id = fork_node_id
        self.parent_branch_id = parent_branch_id   # ← 新增：父分支ID
        self.scope_id = scope_id                   # ← 新增：所属作用域
        self.child_scope_ids = []                  # ← 新增：子作用域
        # ... 其他原有字段
```

***

## 4. Join 目标解析算法

### 4.1 核心问题

Join 需要回答：**"哪些分支应该到达我这里？"**

### 4.2 算法：向前追溯（Forward Tracing）

```python
def _resolve_join_targets(join_node, graph, ctx) -> set[str]:
    """
    根据 Join 的连线图，向前追溯所有应该到达它的分支。
    返回：分支 ID 集合
    """
    targets = set()
    visited = set()

    # 遍历所有连到 Join 的分支端口
    for port_name in join_node.connected_ports:
        for src in join_node.get_flow_inputs(port_name):
            upstream_node_id = src["source_node_id"]
            _trace_upstream_branches(upstream_node_id, graph, ctx, targets, visited)

    return targets


def _trace_upstream_branches(node_id, graph, ctx, targets, visited):
    """
    从某个节点向上追溯，找到所有"活跃的分支源头"。
    """
    if node_id in visited:
        return
    visited.add(node_id)

    node = graph.nodes.get(node_id)
    if not node:
        return

    # 情况1：这个节点是 Fork/Race 的分支出口直接连过来的
    # 找到创建这个节点的 Fork/Race，将其所有分支加入目标
    for src_port, sources in node.flow_inputs.items():
        for src in sources:
            src_node_id = src["source_node_id"]
            src_node = graph.nodes.get(src_node_id)
            if not src_node:
                continue

            # 如果上游是 Fork/Race
            if src_node.type in ("control/fork", "control/race"):
                # 找到这个 Fork/Race 对应的作用域
                scope = ctx._find_scope_by_fork(src_node.id)
                if scope:
                    # 这个作用域的所有分支都应该到达 Join
                    targets.update(scope.branch_ids)
                    # 递归处理这个作用域的子作用域
                    for child_scope_id in scope.child_scope_ids:
                        child_scope = ctx._scopes.get(child_scope_id)
                        if child_scope:
                            targets.update(child_scope.branch_ids)
                return

            # 如果上游是普通节点，继续向上追溯
            _trace_upstream_branches(src_node_id, graph, ctx, targets, visited)
```

### 4.3 示例分析

```
Fork1 ──→ branch1 ──→ [A] ──→ Join2
      ├─→ branch2 ──→ [B] ──┘
      ├─→ branch3 ──→ Fork2 ──→ branch1 ──→ [C] ──→ Join2
      │                       └─→ branch2 ──→ [D] ──┘
      └─→ branch4 ──→ [E] ───────────────────→ Join2
```

Join2 的 `connected_ports` = {branch1, branch2, branch3, branch4}

解析过程：

1. **branch1 端口**：上游是节点 A → 追溯 A 的上游是 Fork1 的 branch1 出口 → Fork1 是 Fork → 加入 `fork1_scope` 的所有分支：`{fork1_branch1, fork1_branch2, fork1_branch3, fork1_branch4}`
2. **branch2 端口**：上游是节点 B → 追溯 B 的上游是 Fork1 的 branch2 出口 → Fork1 已处理，跳过
3. **branch3 端口**：上游是节点 C → 追溯 C 的上游是 Fork2 的 branch1 出口 → Fork2 是 Fork → 加入 `fork2_scope` 的所有分支：`{fork2_branch1, fork2_branch2}`
4. **branch4 端口**：上游是节点 E → 追溯 E 的上游是 Fork1 的 branch4 出口 → Fork1 已处理，跳过

最终结果：`{fork1_branch1, fork1_branch2, fork1_branch3, fork1_branch4, fork2_branch1, fork2_branch2}`

**但 wait\_mode 决定实际等待哪些：**

- `all`：等上面所有 6 个分支
- `any`：等任意一个
- `custom`：用户勾选哪些等哪些

***

## 5. cancel\_others 的精确控制

### 5.1 设计原则

- **只取消"应该到达 Join 但没到达"的分支**
- **递归取消这些分支的子作用域内的所有分支**
- **绝不取消"不应该到达 Join"的分支**
- **绝不向后影响 Join 之后的节点**

### 5.2 算法

```python
def _cancel_join_targets(join_node, ctx, arrived_branches, expected_branches):
    """
    取消所有应该到达 Join 但未到达的分支，及其子作用域。
    """
    to_cancel = expected_branches - arrived_branches

    for branch_id in to_cancel:
        bctx = ctx._branches.get(branch_id)
        if bctx and bctx.status == "running":
            bctx.cancel()

        # 递归取消这个分支的子作用域
        _cancel_child_scopes(branch_id, ctx)


def _cancel_child_scopes(branch_id, ctx):
    """
    递归取消某个分支下的所有子作用域分支。
    """
    for scope in ctx._scopes.values():
        if scope.parent_branch_id == branch_id:
            for child_branch_id in scope.branch_ids:
                child_bctx = ctx._branches.get(child_branch_id)
                if child_bctx and child_bctx.status == "running":
                    child_bctx.cancel()
                # 继续递归
                _cancel_child_scopes(child_branch_id, ctx)
```

### 5.3 示例

```
Fork1 ──→ branch1 ──→ Join1 ──→ [X]
      ├─→ branch2 ──→ [B]
      └─→ branch3 ──→ Fork2 ──→ branch1 ──→ [C]
                                └─→ branch2 ──→ [D] ──→ Join1
```

Join1 的 expected\_branches = `{fork1_branch1, fork1_branch2, fork1_branch3, fork2_branch1, fork2_branch2}`

假设 `fork1_branch1` 先到达 Join1（通过 Join1 的 branch1 端口）：

- `arrived = {fork1_branch1}`
- `to_cancel = {fork1_branch2, fork1_branch3, fork2_branch1, fork2_branch2}`
- 取消 `fork1_branch2`（B 停止）
- 取消 `fork1_branch3`，并递归取消其子作用域 `fork2_scope`：
  - 取消 `fork2_branch1`（C 停止）
  - 取消 `fork2_branch2`（D 停止，即使 D 已经连到了 Join1）

**符合直觉**：Join1 被触发了，所有"应该到 Join1"的分支都要停，包括嵌套里的。

***

## 6. Fork/Race 执行流程改造

### 6.1 Fork 执行

```python
def _handle_fork(node: ExecNode, ctx: ExecContext):
    # 1. 创建作用域
    scope_id = f"{node.id}_scope"
    parent_branch_id = ctx._get_branch_id()  # 当前线程所在的分支（嵌套时用）

    scope = Scope(
        scope_id=scope_id,
        fork_node_id=node.id,
        parent_branch_id=parent_branch_id,
        branch_ids=[],
        child_scope_ids=[],
        status="running"
    )
    ctx._scopes[scope_id] = scope

    # 2. 如果有父分支，将作用域注册到父分支的子作用域列表
    if parent_branch_id:
        parent_bctx = ctx._branches.get(parent_branch_id)
        if parent_bctx:
            parent_bctx.child_scope_ids.append(scope_id)

    # 3. 创建分支（原有逻辑，但增加 scope_id）
    for i, port_name in enumerate(branch_ports):
        children = node.get_flow_children(port_name)
        if children:
            branch_id = f"{node.id}_branch{i + 1}"
            scope.branch_ids.append(branch_id)

            branch_ctx = BranchContext(
                branch_id=branch_id,
                parent_ctx=ctx,
                fork_node_id=node.id,
                parent_branch_id=parent_branch_id,
                scope_id=scope_id,
            )
            ctx._branches[branch_id] = branch_ctx

            # 启动线程...
```

### 6.2 Race 执行

与 Fork 类似，但增加 `cancel_on_first` 逻辑：

```python
def _handle_race(node: ExecNode, ctx: ExecContext):
    # 1. 创建作用域（与 Fork 相同）
    scope_id = f"{node.id}_scope"
    parent_branch_id = ctx._get_branch_id()
    # ...

    # 2. 创建 race_event 和 winner_branch（原有逻辑）

    # 3. 当 winner 产生时：
    if cancel_on_first and winner_branch[0]:
        # 只取消同一作用域内的其他分支
        scope = ctx._scopes.get(scope_id)
        for bid in scope.branch_ids:
            if bid != winner_branch[0]:
                bctx = ctx._branches.get(bid)
                if bctx and bctx.status == "running":
                    bctx.cancel()
                # 递归取消子作用域
                _cancel_child_scopes(bid, ctx)
```

***

## 7. Join 完整执行流程

```python
def _handle_join(node: ExecNode, ctx: ExecContext):
    # 1. 解析参数
    wait_mode = node.params.get("wait_mode", "all")
    timeout_ms = float(node.params.get("timeout_ms", 30000))
    cancel_others = node.params.get("cancel_others", False)

    # 2. 确定连到 Join 的端口
    connected_ports = _get_connected_ports(node)

    # 3. 【核心】向前追溯，确定应该到达的所有分支
    expected_branches = _resolve_join_targets(node, ctx.graph, ctx)

    # 4. 确定 required_branches（根据 wait_mode）
    if wait_mode == "all":
        required_branches = set(expected_branches)
    elif wait_mode == "any":
        required_branches = set()  # 任意一个即可
    elif wait_mode == "custom":
        required_branches = _get_custom_required(node, expected_branches)

    # 5. 记录到达
    join_key = node.id
    arrived_port = _get_arrived_port(node, ctx)

    with ctx._data_lock:
        _init_join_state(ctx, join_key)
        if arrived_port:
            # 找到到达的分支 ID
            arrived_branch = _find_arrived_branch(node, arrived_port, ctx)
            if arrived_branch:
                ctx._join_arrivals[join_key].add(arrived_branch)

    arrivals = ctx._join_arrivals[join_key]

    # 6. 检查条件
    def check_condition():
        if wait_mode == "all":
            return required_branches.issubset(arrivals)
        elif wait_mode == "any":
            return len(arrivals) > 0
        elif wait_mode == "custom":
            if required_branches:
                return required_branches.issubset(arrivals)
            return len(arrivals) > 0
        return False

    # 7. 判断是否触发
    with ctx._data_lock:
        if check_condition() and not ctx._join_done_flag.get(join_key, False):
            ctx._join_done_flag[join_key] = True
            should_execute = True
        else:
            should_execute = False

    if should_execute:
        if cancel_others:
            # 【核心】精确取消：只取消 expected 中未到达的，及其子作用域
            _cancel_join_targets(node, ctx, arrivals, expected_branches)
        _execute_flow(node.id, "done", ctx)
        return

    # 8. 等待逻辑（原有）
    deadline = time.time() + timeout_ms / 1000.0 if timeout_ms > 0 else None
    while not join_event.is_set() and not ctx.stop_event.is_set():
        # ... 等待并检查条件
        pass

    if should_execute:
        if cancel_others:
            _cancel_join_targets(node, ctx, arrivals, expected_branches)
        join_event.set()
        _execute_flow(node.id, "done", ctx)
```

***

## 8. 显式指定兜底机制

### 8.1 场景

自动推断在以下情况可能不明确：

- 多个 Fork 的分支通过复杂路径汇聚到同一个 Join
- 用户只想等待特定 Fork 的分支，而不是所有连到的分支

### 8.2 实现

Join 节点增加可选参数 `target_fork_node_id`：

```python
"params_schema": {
    # ... 原有参数
    "target_fork_node_id": {
        "type": "string",
        "default": "",
        "description": "显式指定要等待的 Fork/Race 节点ID（空=自动推断）"
    }
}
```

当 `target_fork_node_id` 不为空时：

- `_resolve_join_targets` 只返回该 Fork/Race 作用域内的分支
- 忽略其他连线路径

***

## 9. 边界情况处理

### 9.1 循环引用检测

如果用户连线形成循环（Fork → Join → Fork 形成环），编译期检测：

```python
# compiler.py 增加验证
def _check_fork_join_cycle(graph, node_id, visited, path):
    if node_id in path:
        cycle = path[path.index(node_id):]
        if any(graph.nodes[nid].type in ("control/fork", "control/race") for nid in cycle):
            graph.errors.append(f"检测到 Fork/Join 循环: {' -> '.join(cycle)}")
        return
    # ...
```

### 9.2 重复到达处理

同一个分支通过多条路径到达同一个 Join：

- `_join_arrivals` 使用 `set`，自动去重
- 不影响逻辑

### 9.3 分支已取消后到达

如果分支被 cancel 后，线程仍在执行并到达 Join：

- Join 检查分支状态，如果 `status == "cancelled"`，不计入到达
- 防止已取消分支误触发 Join

### 9.4 超时处理

超时后 `should_execute = True`：

- 如果 `cancel_others=True`，取消所有未到达的 expected 分支
- 执行 Join 的 `done` 出口

***

## 10. 数据结构变更汇总

### 10.1 ExecContext 新增字段

```python
class ExecContext:
    def __init__(self, ...):
        # ... 原有字段
        self._scopes: dict[str, Scope] = {}           # ← 新增：作用域字典
        # _branches 保留，但 BranchContext 增加 scope_id 和 parent_branch_id
```

### 10.2 BranchContext 新增字段

```python
class BranchContext:
    def __init__(self, ...):
        # ... 原有字段
        self.parent_branch_id: str = None              # ← 新增
        self.scope_id: str = None                      # ← 新增
        self.child_scope_ids: list[str] = []           # ← 新增
```

### 10.3 新增 Scope 类

```python
@dataclass
class Scope:
    scope_id: str
    fork_node_id: str
    parent_branch_id: str
    branch_ids: list[str]
    child_scope_ids: list[str]
    status: str
```

***

## 11. 前端适配设计

### 11.1 动态分支数量（Fork/Race/Join）

#### 当前问题

- Fork/Race/Join 节点固定显示 8 个分支端口
- 大多数场景只需要 2-4 个分支，造成界面拥挤
- 属性面板中固定显示 8 组参数（如 `branch_affinity_1` \~ `branch_affinity_8`）

#### 设计方案

**默认分支数改为 2**，支持用户动态添加/删除：

```javascript
// nodes.js / nodes.py 中节点定义改造
{
    "type": "control/fork",
    "inputs": [{"name": "in", "type": "flow"}],
    "outputs": [
        {"name": "branch1", "type": "flow"},
        {"name": "branch2", "type": "flow"}
    ],
    "params_schema": {
        "branch_count": {"type": "number", "default": 2, "min": 2, "max": 8, "description": "分支数量"},
        "branch_affinity_1": {"type": "string", "default": ""},
        "branch_affinity_2": {"type": "string", "default": ""}
        // branch_affinity_3~8 不再预定义，由前端动态生成
    }
}
```

**前端节点渲染逻辑（core.js** **`_renderNodeDOM`）：**

```javascript
function _renderNodeDOM(node) {
    // ... 原有代码
    
    // 对于 Fork/Race/Join 类型，根据 branch_count 动态生成端口
    var def = window.AutomationNodes ? AutomationNodes.getNodeDef(node._defKey) : null;
    var isDynamicBranch = node._defKey && (
        node._defKey === 'control/fork' || 
        node._defKey === 'control/race' || 
        node._defKey === 'control/join'
    );
    
    if (isDynamicBranch) {
        var branchCount = node.properties.branch_count || 2;
        // 动态生成 outputs/inputs
        node.outputs = [];
        for (var i = 1; i <= branchCount; i++) {
            node.outputs.push({
                name: '分支' + i,
                type: 'flow',
                _portKey: 'branch' + i
            });
        }
        // Join 还需要动态生成 inputs
        if (node._defKey === 'control/join') {
            node.inputs = [];
            for (var i = 1; i <= branchCount; i++) {
                node.inputs.push({
                    name: '分支' + i,
                    type: 'flow',
                    _portKey: 'branch' + i
                });
            }
            node.inputs.push({name: 'in', type: 'flow', _portKey: 'in'}); // Join 可能还需要 in？根据实际设计
        }
    }
    
    // ... 原有渲染逻辑
}
```

### 11.2 属性面板动态参数

**property.js 改造：**

```javascript
// 在 _renderGroup 中增加对动态分支参数的特殊处理
_renderGroup: function(groupName, paramEntries, node) {
    // ... 原有代码
    
    // 动态分支节点特殊处理
    var isDynamicBranch = node._defKey && (
        node._defKey === 'control/fork' || 
        node._defKey === 'control/race' || 
        node._defKey === 'control/join'
    );
    
    if (isDynamicBranch && groupName === '参数') {
        // 插入分支数量调节器
        html += this._renderBranchCountControl(node);
    }
    
    // ... 原有参数渲染
}

_renderBranchCountControl: function(node) {
    var branchCount = node.properties.branch_count || 2;
    var html = '<div class="prop-field">' +
        '<label class="prop-field-label">分支数量</label>' +
        '<div style="display:flex;gap:4px;align-items:center">' +
          '<input type="range" min="2" max="8" value="' + branchCount + '" ' +
          'onchange="window.AutomationProperty._onBranchCountChange(' + node.id + ', this.value)" ' +
          'style="flex:1">' +
          '<span style="min-width:24px;text-align:center;font-size:12px">' + branchCount + '</span>' +
        '</div>' +
      '</div>';
    return html;
}

_onBranchCountChange: function(nodeId, newCount) {
    var node = AutomationCore.lgGraphObj.getNodeById(nodeId);
    if (!node) return;
    
    var oldCount = node.properties.branch_count || 2;
    newCount = parseInt(newCount);
    if (oldCount === newCount) return;
    
    // 1. 更新 branch_count 属性
    node.properties.branch_count = newCount;
    
    // 2. 如果减少分支数，清理被删除分支的连线
    if (newCount < oldCount) {
        for (var i = newCount + 1; i <= oldCount; i++) {
            var portKey = 'branch' + i;
            // 清理该端口的所有连线
            _removeConnectionsForPort(node.id, portKey);
            // 清理对应的参数
            delete node.properties['branch_affinity_' + i];
            delete node.properties['branch_required_' + i];
        }
    }
    
    // 3. 重新渲染节点 DOM
    _refreshNodeDOM(node);
    
    // 4. 重新渲染属性面板
    this.render(node);
    
    // 5. 通知图变更
    AutomationCore._notifyGraphChange();
}
```

### 11.3 节点重新渲染机制

**core.js 已有** **`_refreshNodeDOM`，需要增强：**

```javascript
function _refreshNodeDOM(node) {
    var oldEl = document.getElementById('nd-' + node.id);
    if (!oldEl) return;
    
    // 保存旧元素的位置和选中状态
    var wasSelected = oldEl.classList.contains('sel');
    
    // 重新生成 DOM
    var newEl = _renderNodeDOM(node);
    
    // 恢复选中状态
    if (wasSelected) {
        newEl.classList.add('sel');
    }
    
    oldEl.parentNode.replaceChild(newEl, oldEl);
    node._domEl = newEl;
    node.size = [newEl.offsetWidth || 220, newEl.offsetHeight || 100];
    _bindInlineFields(newEl, node);
    
    // 重新渲染所有连线（因为端口位置可能变化）
    _renderAllConnections();
}
```

### 11.4 Join 属性面板增强

**新增** **`target_fork_node_id`** **参数渲染：**

```javascript
// property.js 中增加节点引用选择器
_renderNodeRefField: function(key, schema, val, node) {
    var html = '<div class="prop-field">' +
        '<label class="prop-field-label">' + (schema.label || key) + '</label>' +
        '<div style="display:flex;gap:4px">' +
          '<select data-key="' + key + '" data-type="node_ref" style="flex:1">' +
            '<option value="">自动推断</option>';
    
    // 遍历图中所有 Fork/Race 节点
    var nodes = AutomationCore.lgGraphObj.getNodes();
    for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        if (n._defKey === 'control/fork' || n._defKey === 'control/race') {
            var selected = (val === String(n.id)) ? ' selected' : '';
            html += '<option value="' + n.id + '"' + selected + '>' + 
                (n._customName || n.title || n._defKey) + ' #' + n.id + '</option>';
        }
    }
    
    html += '</select></div></div>';
    return html;
}
```

### 11.5 动态分支参数生成

**后端 nodes/control.py 改造：**

```python
def register(registry):
    # Fork 节点
    registry.register_node({
        "type": "control/fork",
        "category": "control",
        "display_name": "并发执行",
        "color": "#a855f7",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "branch1", "type": "flow"},
            {"name": "branch2", "type": "flow"},
        ],
        "params_schema": {
            "branch_count": {"type": "number", "default": 2, "min": 2, "max": 8, "description": "分支数量"},
            "branch_affinity_1": {"type": "string", "default": "", "description": "分支1绑核(JSON:{enabled,core})"},
            "branch_affinity_2": {"type": "string", "default": "", "description": "分支2绑核(JSON:{enabled,core})"},
        },
        "handler": "_handle_fork",
        "dynamic_branches": True,  # ← 新增标记
    })

    # Race 节点
    registry.register_node({
        "type": "control/race",
        # ... 类似 Fork
        "dynamic_branches": True,
    })

    # Join 节点
    registry.register_node({
        "type": "control/join",
        "category": "control",
        "display_name": "等待汇合",
        "color": "#a855f7",
        "inputs": [
            {"name": "branch1", "type": "flow"},
            {"name": "branch2", "type": "flow"},
        ],
        "outputs": [{"name": "done", "type": "flow"}],
        "params_schema": {
            "branch_count": {"type": "number", "default": 2, "min": 2, "max": 8, "description": "分支数量"},
            "wait_mode": {"type": "string", "enum": ["all", "any", "custom"], "default": "all", "description": "等待模式"},
            "branch_required_1": {"type": "boolean", "default": True, "description": "分支1必须到达", "showWhen": "wait_mode=custom"},
            "branch_required_2": {"type": "boolean", "default": True, "description": "分支2必须到达", "showWhen": "wait_mode=custom"},
            "timeout_ms": {"type": "number", "default": 30000, "description": "超时(ms, 0=无限)", "varRef": True},
            "cancel_others": {"type": "boolean", "default": False, "description": "触发后取消未到达分支"},
            "target_fork_node_id": {"type": "string", "default": "", "description": "显式指定目标Fork/Race节点ID(空=自动推断)", "nodeRef": "fork_race"},
        },
        "handler": "_handle_join",
        "dynamic_branches": True,
    })
```

### 11.6 前端节点定义加载改造

**nodes.js** **`_registerFromPayload`：**

```javascript
_registerFromPayload: function(payload) {
    // ... 原有代码
    for (var type in nodes) {
        // ... 原有代码
        this._normalizeSchema(def);
        
        // 动态分支节点：根据 branch_count 展开端口和参数
        if (def.dynamic_branches) {
            this._expandDynamicBranches(def);
        }
        
        this._nodeDefs[type] = def;
        // ... 原有代码
    }
}

_expandDynamicBranches: function(def) {
    var count = 8; // 最大支持 8 个分支
    
    // 展开 outputs
    def.outputs = [];
    for (var i = 1; i <= count; i++) {
        def.outputs.push({
            name: 'branch' + i,
            type: 'flow'
        });
    }
    
    // Join 还需要展开 inputs
    if (def.type === 'control/join') {
        def.inputs = [];
        for (var i = 1; i <= count; i++) {
            def.inputs.push({
                name: 'branch' + i,
                type: 'flow'
            });
        }
    }
    
    // 展开 params_schema 中的分支相关参数
    var schema = def.params_schema;
    for (var i = 3; i <= count; i++) {
        // Fork/Race 的 affinity 参数
        if (schema.branch_affinity_1 !== undefined) {
            schema['branch_affinity_' + i] = {
                type: 'string',
                default: '',
                description: '分支' + i + '绑核(JSON:{enabled,core})'
            };
        }
        // Join 的 required 参数
        if (schema.branch_required_1 !== undefined) {
            schema['branch_required_' + i] = {
                type: 'boolean',
                default: true,
                description: '分支' + i + '必须到达',
                showWhen: 'wait_mode=custom'
            };
        }
    }
}
```

***

## 12. 修改文件清单

### 后端

| 文件                               | 修改内容                                                                                                 |
| -------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `automation/engine.py`           | 新增 `Scope` 类，改造 `BranchContext`，`ExecContext` 新增 `_scopes`                                           |
| `automation/handlers/control.py` | 重写 `_handle_fork`, `_handle_race`, `_handle_join`，新增 `_resolve_join_targets`, `_cancel_join_targets` |
| `automation/nodes/control.py`    | Fork/Race/Join 增加 `branch_count` 参数，Join 增加 `target_fork_node_id` 参数，标记 `dynamic_branches`           |
| `automation/compiler.py`         | 增加 Fork/Join 循环检测验证                                                                                  |

### 前端

| 文件                                 | 修改内容                                                                        |
| ---------------------------------- | --------------------------------------------------------------------------- |
| `webui/modules/auto/nodes.js`      | `_registerFromPayload` 增加 `_expandDynamicBranches` 调用                       |
| `webui/modules/auto/core.js`       | `_renderNodeDOM` 增加动态分支端口生成；增强 `_refreshNodeDOM`                            |
| `webui/modules/auto/property.js`   | 增加 `_renderBranchCountControl`、`_onBranchCountChange`、`_renderNodeRefField` |
| `webui/modules/auto/editor-app.js` | 如有需要，增加分支数量变更的撤销/重做支持                                                       |

***

## 13. 验证测试场景

### 12.1 基础场景

- [ ] Fork → 2 分支 → Join (all)
- [ ] Fork → 2 分支 → Join (any)
- [ ] Race → 2 分支 → 一个 winner

### 12.2 嵌套场景

- [ ] Fork1 → branch1 → Fork2 → 2 分支 → Join2
- [ ] Fork1 → branch1/2 → Join1 → Fork2 → 2 分支 → Join2

### 12.3 跨层级汇合

- [ ] Fork1 → b1/b2 → Join1 + b3 → Fork2 → b1/b2 → Join2 + b4 → Join2

### 12.4 cancel\_others 验证

- [ ] Join(any) 触发后，嵌套 Fork 内的分支也被取消
- [ ] Join 触发后，不影响 Join 之后的节点

### 12.5 异常场景

- [ ] 循环连线检测
- [ ] 超时处理
- [ ] 分支已取消后到达 Join

***

## 13. Race 竞争模型与 race_win 节点

### 13.1 当前问题

当前 `_handle_race` 的执行模型存在根本性设计缺陷：

**race_worker 执行流程**：

```python
def race_worker(bid, bctx, port_name, core_idx):
    _execute_flow(node.id, port_name, ctx)   # 执行整个分支链直到末端
    winner_branch[0] = bid                    # 整条链执行完才标记"赢了"
    race_event.set()                          # 通知主线程
```

**问题**：

1. **没有"竞争结束点"**：分支中所有节点都属于"竞争阶段"，没有分界线标识"到此竞争结束"
2. **取消其他分支的时机太晚**：要等赢家分支的整条链都跑完，其他分支才能被取消
3. **赢家分支无法继续执行后续节点**：`_execute_flow` 已经执行完了整条链，race 结束后流程就终止了
4. **每个分支的后续动作可能不同**：用户需要"检测红色怪物→执行红色连招"、"检测蓝色怪物→执行蓝色连招"，各分支后续不同

### 13.2 典型游戏场景

```
Race（竞争：谁先检测到目标）
├── branch1: [检测红色怪物] → race_win → [攻击红色怪物的连招A]
├── branch2: [检测蓝色怪物] → race_win → [攻击蓝色怪物的连招B]
└── branch3: [检测BOSS动作]  → race_win → [BOSS闪避逻辑]
```

- `race_win` 节点 = **竞争结束点**，到达即意味着"我赢了"
- 到达 `race_win` 时：立即通知 race 主线程取消其他分支
- **当前分支继续执行 `race_win` 之后的节点**（这些是"竞争胜利后的专属逻辑"）

### 13.3 设计方案：新增 `control/race_win` 节点

#### 13.3.1 节点定义

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

#### 13.3.2 处理器逻辑

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

**核心要点**：

1. `race_win` 到达时，立即标记当前分支为 winner 并通知 race 主线程
2. 立即取消同一 scope 内的其他分支（包括子作用域）
3. **当前分支继续执行 `next` 端口**，走自己的后续逻辑
4. 输出 `winner_branch` 数据，供后续节点读取

#### 13.3.3 `_handle_race` 改造

```python
def _handle_race(node: ExecNode, ctx: ExecContext):
    # ... 创建 scope、分支、线程（与现有逻辑相同）

    # 关键改动1：在 scope 中增加 winner_branch_id 字段
    scope = Scope(
        scope_id=scope_id,
        fork_node_id=node.id,
        parent_branch_id=parent_branch_id,
        winner_branch_id=None,  # ← 新增
    )

    # 关键改动2：将 race_event 存入 ctx，供 race_win 访问
    ctx._race_events[scope_id] = race_event

    # 关键改动3：race_worker 中不再设置 winner
    def race_worker(bid, bctx, port_name, core_idx):
        # ... affinity 设置
        try:
            ctx._set_branch_id(bid)
            _execute_flow(node.id, port_name, ctx)
            # ← 删除 winner_branch[0] = bid 和 race_event.set()
            # 现在由 race_win 节点负责
            bctx.set_status("completed")
        except Exception as e:
            bctx.set_status("error")
        # ...

    # 关键改动4：主线程等待逻辑不变，但取消逻辑改为由 race_win 触发
    # 主线程只负责等待结果和超时处理
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

    # 注意：不再执行 _execute_flow(node.id, "done", ctx)
    # 因为赢家分支已经在 race_win 的 next 端口继续执行了
```

#### 13.3.4 Scope 数据结构变更

```python
@dataclass
class Scope:
    scope_id: str
    fork_node_id: str
    parent_branch_id: str
    branch_ids: list[str]
    child_scope_ids: list[str]
    status: str
    winner_branch_id: str = None  # ← 新增：记录哪个分支胜出
```

#### 13.3.5 ExecContext 变更

```python
class ExecContext:
    def __init__(self, ...):
        # ... 原有字段
        self._race_events: dict[str, threading.Event] = {}  # ← 新增
```

### 13.4 向后兼容：无 race_win 的分支

如果某个分支**没有** `race_win` 节点（旧图或简单场景），该分支执行完整个链后：

- 在 `race_worker` 的 finally 中检查：如果 scope 还没有 winner，则将当前分支设为 winner
- 行为与当前实现一致（整条链跑完才算赢）

```python
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
        # ... affinity 清理
```

### 13.5 Race + Join 汇合：多分支共享后续

#### 13.5.1 场景

当两个或多个 race 分支的后续动作相同时，可以用 Join 节点汇合：

```
Race
├── branch1: [检测红色怪物] → race_win → [攻击连招A] ──┐
├── branch2: [检测蓝色怪物] → race_win → [攻击连招B] ──┤→ Join → [公共收尾动作]
└── branch3: [检测BOSS动作]  → race_win → [BOSS闪避]  ──┘
```

**执行流程**：

1. Race 启动3个分支并行执行
2. branch1 的检测红色怪物先成功，到达 `race_win`
3. `race_win` 立即取消 branch2 和 branch3
4. branch1 继续执行 `[攻击连招A]`
5. branch1 到达 Join，Join 等待模式为 `any`（任一分支到达即可）
6. Join 触发 `done` 端口，执行 `[公共收尾动作]`

**注意**：被取消的 branch2/branch3 不会到达 Join，所以 Join 应使用 `any` 模式或 `wait_mode=all` + `cancel_others=True`。

#### 13.5.2 Join 与 Race 的配合规则

| Join wait_mode | 配合 Race 的行为 | 适用场景 |
|---|---|---|
| `any` | 任一分支到达即触发 | Race 场景最常用：赢家到达即可 |
| `all` + `cancel_others=True` | 等所有分支到达，但 Race 已取消其他分支，所以实际只等赢家 | 等同于 `any`，但会清理被取消分支 |
| `all`（无 cancel_others） | 等所有分支到达 | **不适用于 Race**：被取消的分支永远不会到达，Join 会超时 |
| `custom` | 用户指定哪些分支必须到达 | 灵活但复杂，一般不需要 |

**推荐**：Race 后接 Join 时，默认使用 `any` 模式。

#### 13.5.3 不同分支完全独立后续（不需要 Join）

```
Race
├── branch1: [检测红色] → race_win → [连招A] → [结算A]
├── branch2: [检测蓝色] → race_win → [连招B] → [结算B]
└── branch3: [检测BOSS]  → race_win → [闪避]  → [重新检测]
```

每个分支的后续完全不同，不需要 Join。race_win 的 `next` 端口直接连到各自的后续节点。

#### 13.5.4 部分分支汇合（选择性 Join）

```
Race
├── branch1: [检测红色] → race_win → [近战连招] ──┐
├── branch2: [检测蓝色] → race_win → [近战连招] ──┤→ Join → [公共近战收尾]
└── branch3: [检测BOSS]  → race_win → [闪避]  → [重新检测]
```

branch1 和 branch2 共享近战连招后的收尾动作，branch3 独立。Join 只连接 branch1 和 branch2 的后续。

### 13.6 前端节点定义

```javascript
// nodes.js
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

### 13.7 修改文件清单

| 文件 | 修改内容 |
|---|---|
| `automation/nodes/control.py` | 新增 `control/race_win` 节点注册 |
| `automation/handlers/control.py` | 新增 `_handle_race_win`；改造 `_handle_race` |
| `automation/engine.py` | `Scope` 增加 `winner_branch_id`；`ExecContext` 增加 `_race_events` |
| `webui/modules/auto/nodes.js` | 新增 `control/race_win` 前端定义 |

### 13.8 验证测试场景

- [ ] Race → 2分支(各有race_win) → 第一个到达后取消另一个，赢家继续后续
- [ ] Race → 2分支(各有race_win) → 各自后续不同，无Join
- [ ] Race → 2分支(各有race_win) → 后续接Join(any)，公共收尾
- [ ] Race → 3分支(部分汇合Join) → branch1/2共享后续，branch3独立
- [ ] Race → 2分支(无race_win) → 向后兼容，整条链执行完算赢
- [ ] Race → 超时 → 所有分支取消
- [ ] Race → 嵌套Race → 内层race_win不影响外层

***

## 14. 向后兼容性

- 现有简单 Fork-Join 对的逻辑不变
- 新增字段都有默认值，不影响旧图
- `target_fork_node_id` 为空时走自动推断逻辑
- Race 分支中无 `race_win` 节点时，行为与旧版一致（整条链执行完标记 winner）

***

*文档版本: 1.1*
*日期: 2026-04-30*
