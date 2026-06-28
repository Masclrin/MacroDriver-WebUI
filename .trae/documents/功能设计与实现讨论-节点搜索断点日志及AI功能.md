# 功能设计与实现讨论

> 基于宏驱动 WebUI 2.8 现有架构的深入分析，逐项讨论新功能的设计与实现方案。

---

## 一、现有架构回顾（与功能相关的关键点）

### 1.1 后端引擎

| 模块 | 文件 | 关键机制 |
|------|------|----------|
| 执行引擎 | `automation/engine.py` | `_execute_node()` → 逐节点执行，goto 循环，重试机制，暂停/停止/分支 |
| 编译解析 | `automation/compiler.py` | `parse_graph()` → 将前端 JSON 图转为 `ExecNode` / `ExecGraph` |
| 节点注册 | `automation/registry.py` | `PluginRegistry` 统一注册内置与插件节点 |
| 桥接 API | `bridge/automation_api.py` | `run_automation` / `stop_automation` / `pause_automation` / `get_automation_status` |
| 精确引擎 | `engine/precision.py` | `precise_sleep_v5` 0.1ms 级等待 |

**关键发现：**
- `ExecContext` 中已有 `_executed_nodes: set` 用于防止节点重复执行 — 这是断点实现的切入点
- `execute_graph()` 在线程中运行，通过 `stop_event` / `pause_event` 控制
- `get_automation_status()` 目前只返回 `running/paused/completed/error` 四种状态，没有节点级信息
- 引擎在执行循环中已处理 `goto_target` 跳转机制 — 断点恢复可以从这里入手

### 1.2 前端编辑器

| 模块 | 文件 | 关键机制 |
|------|------|----------|
| 核心状态 | `core/core.js` | `AutomationCore` 对象，管理 `_nodes` / `_connections` / `executionState` |
| 节点渲染 | `render/node-renderer.js` | `_renderNodeDOM()` / `_addNodeToDOM()` — 纯 DOM 渲染，无第三方库 |
| 右键菜单 | `ui/context-menu.js` | `showContextMenu()` / `handleContextAction()` — 基于自定义 DOM 菜单 |
| 变量面板 | `ui/var-panel.js` | 浮动面板 `#var-float`，支持拖拽/调整大小/搜索/筛选/dock |
| 图形执行 | `graph/graph-executor.js` | `runGraph()` → 调用后端 API / `simulateExecution()` 模拟 |
| 节点高亮 | `core/core.js` | `setNodeHighlight(nodeId, state)` 和 `clearAllHighlights()` |
| 事件处理 | `logic/events-handlers.js` | `highlightNode` / `unhighlightNode` / `flashNode` / `clearAllHighlights` |
| 工具箱 | `ui/toolbox-renderer.js` | 左侧分类工具栏，支持拼音搜索 |
| 主入口 | `app/editor-app.js` | `initEditor()` → 绑定所有事件、初始化 |

**关键发现：**
- 右键菜单是纯自定义实现（非系统原生），位于 `context-menu.js`，在 `editor-app.js` 的 `contextmenu` 事件中触发
- 节点高亮已有 CSS class 系统：`.executing` / `.check-pass` / `.check-fail` / `.triggered`
- 变量面板的浮动机制非常完善：支持拖拽移动、大小调整（CSS resize）、dock/undock、搜索筛选
- 工具箱已有节点搜索功能（`#ns-in` 输入框 + 拼音匹配）
- 工具箱按钮位于左侧边栏底部：`#btn-toolbox`、`#btn-plugin`

---

## 二、功能一：节点搜索高亮

### 2.1 需求分析

在工作流画布中搜索节点名称/类型，匹配的节点高亮显示，支持快速定位跳转。

### 2.2 现有能力

- **工具箱搜索**：`toolbox-renderer.js` 已有 `renderToolbox(filterText)` 按节点类型过滤工具箱列表
- **节点高亮**：`AutomationCore.setNodeHighlight(nodeId, state)` 和 CSS class 系统
- **视图适配**：`fitView()` 可自动缩放+平移以显示所有节点
- **状态栏坐标**：`#s-pos` 实时显示鼠标在画布中的坐标

### 2.3 设计方案

**方案 A：在工具箱搜索中增强（轻量级）**

在现有工具箱搜索框 `#ns-in` 中增加画布节点名称匹配。用户输入时：
1. 同时过滤工具箱列表（现有行为）
2. 在画布中将匹配名称/类型的节点高亮（新增）

**方案 B：独立的节点搜索栏（更强大）**

在工具栏或画布上方添加一个独立的搜索栏：
1. 输入关键词 → 实时匹配所有画布节点（按名称、类型、ID 匹配）
2. 匹配结果以下拉列表展示（节点名 + 类型 + 坐标）
3. 点击结果 → 平滑移动到该节点并选中 + 高亮闪烁
4. 支持 `Enter` 键循环跳转匹配节点
5. 支持正则搜索（高级选项）

**建议：方案 B**

理由：
- 不与工具箱搜索混淆职责（工具箱搜索是"找节点类型"，画布搜索是"找已有节点实例"）
- 用户体验类似 VS Code 的 `Ctrl+F` 查找

### 2.4 实现要点

| 层 | 文件 | 改动 |
|----|------|------|
| HTML | `automation_editor.html` | 在工具栏添加搜索输入框 `#nd-search` + 结果计数 `#nd-search-count` |
| UI | 新建 `ui/node-search.js` | 搜索逻辑：遍历 `AutomationCore.getNodes()`，匹配名称/类型/ID |
| 渲染 | `render/node-renderer.js` | 新增高亮 class `.nd.search-match` 和 `.nd.search-active` |
| 事件 | `app/editor-app.js` | 绑定搜索框事件 + 快捷键 `Ctrl+F` |
| 动画 | 渲染层 | 选中时 `fitView` 动画定位到目标节点 |

### 2.5 伪代码

```javascript
// ui/node-search.js
function searchNodes(query) {
  var nodes = AutomationCore.getNodes();
  var results = [];
  var regex = new RegExp(query, 'i');
  for (var i = 0; i < nodes.length; i++) {
    var n = nodes[i];
    var def = AutomationNodes.getNodeDef(n._defKey);
    var name = n._customName || (def ? def.display_name : '');
    if (regex.test(name) || regex.test(n._defKey) || regex.test(String(n.id))) {
      results.push(n);
    }
  }
  // 高亮匹配节点
  AutomationCore.clearAllHighlights();
  for (var j = 0; j < results.length; j++) {
    AutomationCore.setNodeHighlight(results[j].id, 'search-match');
  }
  return results;
}
```

### 2.6 复杂度评估

**低复杂度**。主要在前端新增 ~200 行 JS 代码，不涉及后端改动。现有高亮基础设施完全够用。

---

## 三、功能二：节点断点调试

### 3.1 需求分析

- 在节点上右键 → 设置/取消断点（类似 IDE 的行断点）
- 脚本执行到断点节点时暂停
- 可从断点处继续执行（需支持断点位置恢复）
- 可视化显示断点标记（节点上的红色圆点/边框）

### 3.2 现有能力分析

**已有关键机制：**

1. **暂停系统**：`ExecContext.pause_event` + `BranchContext.pause_event`
   - 在 `_execute_node()` 第 803 行的 while 循环中检查暂停：
   ```python
   while (ctx.pause_event.is_set() or (branch_ctx and branch_ctx.pause_event.is_set())) ...
   ```

2. **节点执行前检查**：`_execute_node()` 在第 785-787 行检查 `executed_set` 防止重复执行

3. **执行状态查询**：`get_automation_status()` 返回 `running/paused/completed/error`

4. **执行在独立线程**中运行，主线程可随时操作 `pause_event`

**核心差距：**

- 引擎不知道"断点"概念 — `_execute_node` 在遇到暂停时只是等待，没有主动触发暂停的逻辑
- 前端不知道"当前执行到哪个节点" — 没有节点级别的状态反馈机制（只有整体 running/paused）
- 引擎恢复后直接从暂停点继续 — 恢复逻辑已就绪（`pause_event.clear()`）

### 3.3 设计方案

#### 3.3.1 断点设置/存储

**前端（右键菜单）：**

在 `context-menu.js` 的节点右键菜单中增加：
```javascript
{ label: '设置断点', icon: 'fa-solid fa-circle', iconStyle: 'color:#ef4444', action: 'toggle_breakpoint' },
{ label: '从断点执行', icon: 'fa-solid fa-play', action: 'run_from_breakpoint' },
```

断点信息存储：
- 前端：`_breakpoints = {}` / `_breakpointNodeIds = new Set()` （画布级状态）
- 后端：通过 API 将断点列表传给引擎（`run_automation` 时携带 `breakpoints` 数组）

**可视化：**
- 节点 DOM 添加 `.nd.has-breakpoint` class → 红色左边框/圆点
- `node-renderer.js` 的 `_renderNodeDOM()` 中检查断点状态

#### 3.3.2 引擎断点逻辑

在 `_execute_node()` 函数中（`engine.py` 第 785 行附近），在 `executed_set.add(node_id)` 之前插入：

```python
# 断点检查（在 try 块之前）
if ctx.has_breakpoint(current_id):
    ctx.log_info(f"触发断点: 节点 {current_id}({node.type})", node_id=current_id)
    ctx.pause_event.set()  # 自动暂停
    ctx._breakpoint_hit_node = current_id
    # 等待用户恢复...
    while ctx.pause_event.is_set() and not ctx.stop_event.is_set():
        time.sleep(0.1)
```

**关键问题：断点位置恢复**

目前引擎的暂停/恢复机制**已经支持精确恢复**：`pause_event.clear()` 后，while 循环继续，执行后面的 handler 代码。所以断点暂停恢复后，当前节点会**继续执行并完成**。

如果需求是"停在断点处、恢复后从断点**之后**继续"，当前行为已满足（暂停就在 handler 执行之前）。

如果需求是"停在断点处还没执行、恢复后立即执行该节点"，也满足（暂停后恢复，继续执行 handler）。

**唯一需要注意的边界：** 断点节点本身是否算"已执行"。
- 如果暂停在 handler 之前：节点不应标记为 `executed`
- 如果节点已标记为 `executed`，无法"重新执行该节点"（会被第 786 行的 `executed_set` 检查跳过）

**建议：** 断点检查放在 `executed_set.add(current_id)` 之前。暂停发生时节点尚未标记为已执行，恢复后正常执行。

#### 3.3.3 前端状态反馈

需要新增 API：`get_node_execution_state()` 返回当前执行到的节点 ID。

后端 `get_automation_status()` 增强：
```python
def get_automation_status(self):
    # 现有逻辑...
    if ctx:
        return _ok({
            "status": "paused",
            "breakpoint_hit": ctx._breakpoint_hit_node,  # 新增
            "last_executed_node": ctx._current_executing_node,  # 新增
        })
```

前端轮询（`startStatusPolling`）在收到 `breakpoint_hit` 时：
- 高亮该节点（`.executing` class）
- 显示 toast "已触发断点"

### 3.4 需要的后端改动

| 改动 | 文件 | 描述 |
|------|------|------|
| 断点数据传递 | `bridge/automation_api.py` | `run_automation()` 接收 `breakpoints` 参数，传给 `parse_graph()` |
| 断点存储 | `automation/engine.py` | `ExecContext` 新增 `breakpoints: set` |
| 断点检查 | `automation/engine.py` | `_execute_node()` 在 `executed_set.add()` 之前检查断点 |
| 状态返回增强 | `bridge/automation_api.py` | `get_automation_status()` 返回 `current_node` / `breakpoint_hit` |
| 从断点处执行 | `bridge/automation_api.py` | 新增 `run_from_breakpoint()` API 或在 `run_automation` 中支持 `start_node_id` |

### 3.5 "从断点处开始执行"的实现

方案：
1. `run_automation()` 增加 `start_node_id` 参数
2. 编译时如果指定了 `start_node_id`，跳过该节点之前的所有节点（不标记为 `executed`）
3. 引擎从 `start_node_id` 开始执行

这需要编译器支持"跳过前置节点"，或引擎执行时传入 `executed_set` 预填充。

**具体实现：**
- `parse_graph()` 增加 `start_node_id` 参数
- 如果指定，`ExecContext._executed_nodes` 预填充从入口到 `start_node_id` 之前的所有节点
- 或者更简单：新增 `run_graph_from_node(graph, start_node_id, stop_event)` 函数

### 3.6 复杂度评估

**中等复杂度**。核心逻辑改动在 `engine.py`（~30 行），API 层（~30 行），前端菜单（~10 行）。但需要仔细处理：
- 断点与并发分支的交互（每个分支独立暂停？）
- 断点节点标记存储（`.auto.json` 文件中是否持久化？）

---

## 四、功能三：执行日志面板

### 4.1 需求分析

- 类似变量浏览器的浮动面板，放在工具箱区域，点击按钮弹出
- 可改变大小、拖动位置
- 显示每个节点的执行状态/耗时/平均执行时间/调用次数
- 自动化运行时实时更新

### 4.2 性能影响分析

**核心问题**：高精度脚本是否需要担心日志记录的性能影响？

**分析：**

1. **日志记录的开销来源：**
   - `time.perf_counter()` 调用（每次约 0.1μs，可忽略）
   - 日志数据结构构建（dict 分配，约 1-5μs）
   - 锁竞争（`ctx._data_lock` RLock，仅在写日志时短暂持有）
   - 前端轮询开销（JS 每 1 秒通过 `get_automation_status` 查询）

2. **实际影响评估：**
   - 如果结点执行间隔 ≥ 1ms（大多数情况），日志开销 << 0.1%
   - 如果节点非常密集（如连续按键每 1ms 发送），锁竞争可能累积到可感知
   - `perf_counter` 精度为 0.1μs，且不阻塞

3. **建议：只在面板打开时进行日志记录**

   **强烈赞同你的建议。** 实现方式：
   - 前端开关控制 → `toggle_log_panel()` 或 `enable_logging` 参数
   - 后端 `ExecContext` 中有 `_log_enabled: bool` 标记
   - `_execute_node()` 中：
     ```python
     t0 = time.perf_counter() if ctx._log_enabled else 0
     handler(node, ctx)
     if ctx._log_enabled:
         elapsed = time.perf_counter() - t0
         ctx._node_logger.record(node.id, node.type, elapsed, "ok")
     ```
   - 不打开面板时，连 `perf_counter()` 调用都省掉

4. **更细粒度控制：**
   - 可提供三种模式：
     - `off`：完全不记录（默认）
     - `summary`：只记录每个节点的累计信息（总耗时/调用次数），不存每条记录
     - `full`：记录每次执行的详细信息（内存占用大，仅用于调试）

### 4.3 设计方案

#### 4.3.1 后端日志数据结构

```python
class NodeLogger:
    def __init__(self):
        self._lock = threading.Lock()
        self._entries: list = []          # 最近 N 条执行记录（滚动窗口）
        self._stats: dict = {}            # node_id → { total_time, count, avg_time, last_status }
        self._max_entries = 1000          # 滚动窗口大小

    def record(self, node_id, node_type, elapsed_ms, status):
        with self._lock:
            entry = {
                "node_id": node_id,
                "node_type": node_type,
                "elapsed_ms": round(elapsed_ms, 3),
                "status": status,
                "time": time.time(),
            }
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]
            
            stat = self._stats.get(node_id, {"total_time": 0, "count": 0, "avg_time": 0, "last_status": ""})
            stat["total_time"] += elapsed_ms
            stat["count"] += 1
            stat["avg_time"] = round(stat["total_time"] / stat["count"], 3)
            stat["last_status"] = status
            self._stats[node_id] = stat

    def get_entries(self, limit=100):
        with self._lock:
            return list(self._entries[-limit:])

    def get_stats(self):
        with self._lock:
            return dict(self._stats)
```

#### 4.3.2 前端面板设计

**参照变量面板 (`var-panel.js`) 实现：**

复用 `var-panel.js` 的架构模式：

```javascript
// ui/log-panel.js
var _logPanelFloating = false;

function toggleLogPanel() {
    // 实现与 toggleVarPanel 类似的逻辑
}

function undockLogPanel() {
    // 创建浮动 div #log-float，类似 #var-float
    // 支持拖拽 (mousedown/mousemove/mouseup) 和 resize (CSS resize: both)
}

function dockLogPanel() {
    // 收回到底部栏
}

function refreshLogPanel() {
    // 从后端获取日志数据并渲染
    // 显示：节点名 / 类型 / 耗时(ms) / 状态 / 累计调用次数 / 平均耗时
}
```

**面板布局：**

```
┌──────────────────────────────────────────┐
│ 📊 执行日志           [🔧] [×] [⤢]     │ ← 标题栏（拖动）
├──────────────────────────────────────────┤
│ [全部 ▾] [按名称搜索...] [清空日志]     │ ← 工具栏
├──────────────────────────────────────────┤
│ 状态  节点名      耗时    次数  平均     │ ← 表头
├──────────────────────────────────────────┤
│ ✅    鼠标点击     2.3ms   5    3.1ms   │
│ ✅    颜色检测    45.2ms   3   42.8ms   │
│ ❌    文字检测   120.0ms   1  120.0ms   │
│ ⏸    等待       500.0ms   2  500.0ms   │
│ ...                                      │
├──────────────────────────────────────────┤
│ 共 23 个节点 | 总耗时: 1.2s | 已暂停    │ ← 状态栏
└──────────────────────────────────────────┘
```

#### 4.3.3 后端 API 新增

```python
def get_execution_log(self, limit=100):
    ctx = getattr(self._automation_graph, '_exec_ctx', None)
    if not ctx or not hasattr(ctx, '_node_logger'):
        return _err("日志不可用")
    return _ok({
        "entries": ctx._node_logger.get_entries(limit),
        "stats": ctx._node_logger.get_stats(),
        "total_elapsed_ms": ctx._node_logger.total_elapsed_ms,
    })

def enable_execution_log(self, enabled=True):
    # 切换日志开关
    ...
```

#### 4.3.4 引擎集成点

在 `_execute_node()` 中（`engine.py`），将日志记录包裹在 handler 调用前后：

```python
# 在 handler(node, ctx) 调用前后
if ctx._log_enabled:
    _log_start = time.perf_counter()

try:
    handler(node, ctx)
finally:
    if ctx._log_enabled:
        elapsed = (time.perf_counter() - _log_start) * 1000
        ctx._node_logger.record(str(current_id), node.type, elapsed, "ok" if not _last_exception else "error")
```

注意：此代码应在现有的 `try/except/retry` 逻辑**内部**集成，以正确捕获异常状态。

### 4.4 HTML 布局集成

在 `automation_editor.html` 的侧边栏底部工具栏区域（`#toolbox-expand` 旁边或下面）添加日志面板的按钮和容器：

```html
<!-- 日志面板按钮 -->
<button id="btn-log-panel" class="sb-tool-btn" title="执行日志">
    <i class="fa-solid fa-list-check"></i> 执行日志
</button>

<!-- 日志面板容器（在侧边栏底部） -->
<div id="log-panel" class="sb-tool-expand" style="display:none">
    <div id="log-entries"><!-- 动态渲染 --></div>
</div>

<!-- 日志浮动面板 -->
<div id="log-float">
    <div id="lf-header" class="vf-h">
        <i class="fa-solid fa-list-check"></i>
        <span>执行日志</span>
        <button id="lf-dock" title="停靠">⤓</button>
        <button id="lf-close" title="关闭">×</button>
    </div>
    <div id="lf-content"><!-- 动态渲染 --></div>
</div>
```

### 4.5 复杂度评估

**中等复杂度**。后端新增 `NodeLogger` 类（~80 行）、API 扩展（~30 行）、引擎集成（~10 行）；前端新建 `log-panel.js`（~250 行，参照 `var-panel.js`）、HTML 新增面板元素（~30 行）。

**性能风险可控**：日志关闭时零开销，开启时 overhead 仅 `perf_counter()` + 锁 + dict 写入。

---

## 五、功能四：自动目标识别与跟随（插件形式）

### 5.1 需求分析

- 自动识别屏幕中的"物品"或"怪物"
- 执行鼠标移动跟踪目标
- 3D 游戏中将"怪物"摆放到屏幕"中央"
- 高度自定义的识别 → 鼠标/键盘操纵 → 跟随行为

### 5.2 现有检测能力

项目已有强大的检测子系统（`automation/detection/`）：

| 检测方式 | 文件 | 能力 |
|----------|------|------|
| 颜色检测 | `detection/color.py` | 按颜色/区域匹配 |
| OCR 文字 | `detection/ocr.py` | RapidOCR 文字识别 |
| 图片匹配 | `detection/` + `handlers/detection.py` | OpenCV 模板匹配（含金字塔加速） |
| 截图 | `detection/capture.py` | mss/BitBlt 截图 |
| DXGI 截图 | `detection/dxgi_capture.py` | 高性能 GPU 截图 |
| 帧差缓存 | `detection/image_cache.py` | 帧间去重 |

**插件系统也有截图能力**：`PluginContext` 提供 `capture_fn`。

### 5.3 作为插件的技术方案

#### 方案概述

创建一个插件 `plugins/target_tracker/`，包含：

```
plugins/target_tracker/
├── manifest.json    # 节点定义
├── backend.py       # 识别 + 鼠标操纵核心逻辑
└── node.js          # 前端配置 UI（可选）
```

#### 5.3.1 节点设计

```json
{
  "type": "plugin/target_track",
  "display_name": "目标跟踪",
  "category": "plugin",
  "color": "#ef4444",
  "inputs": [{"name": "in", "type": "flow"}],
  "outputs": [
    {"name": "found", "type": "flow"},
    {"name": "lost", "type": "flow"}
  ],
  "params_schema": {
    "target_method": {
      "type": "enum",
      "default": "color",
      "options": ["color", "image", "ocr", "yolo"],
      "description": "识别方式"
    },
    "target_color": { "type": "color", "default": "#FF0000", "description": "目标颜色" },
    "target_image": { "type": "string", "default": "", "description": "模板图片路径" },
    "target_text": { "type": "string", "default": "", "description": "OCR 目标文字" },
    "search_region": { "type": "region", "default": [0, 0, 0, 0], "description": "搜索区域(0=全屏)" },
    "track_mode": {
      "type": "enum",
      "default": "follow",
      "options": ["follow", "center", "avoid"],
      "description": "跟踪模式: 跟随/置中/避开"
    },
    "move_speed": { "type": "number", "default": 5, "min": 0.1, "max": 50, "description": "鼠标移动速度" },
    "smooth_mode": {
      "type": "enum",
      "default": "linear",
      "options": ["linear", "ease_out", "pid"],
      "description": "移动平滑模式"
    },
    "center_deadzone": { "type": "number", "default": 20, "description": "中心死区(像素)" },
    "track_timeout_ms": { "type": "number", "default": 10000, "description": "跟踪超时(毫秒)" },
    "key_follow": {
      "type": "enum",
      "default": "mouse",
      "options": ["mouse", "wasd", "arrows"],
      "description": "控制方式: 鼠标/WASD/方向键"
    },
    "store_var_found": { "type": "string", "default": "", "varRef": true, "description": "存储是否找到目标" },
  }
}
```

#### 5.3.2 `backend.py` 核心逻辑

```python
import time
from automation.detection.capture import capture_screen
from automation.detection.color import check_color
from automation.handlers.detection import do_image_match
from engine.input_sendinput import set_cursor_pos
from engine.precision import precise_sleep_v5 as precise_sleep

def execute(params, context):
    method = params.get("target_method", "color")
    track_mode = params.get("track_mode", "follow")
    move_speed = float(params.get("move_speed", 5))
    deadzone = int(params.get("center_deadzone", 20))
    timeout_ms = int(params.get("track_timeout_ms", 10000))
    search_region = params.get("search_region", [0, 0, 0, 0])
    key_control = params.get("key_follow", "mouse")

    ctx = context.ctx_ref
    start_time = time.perf_counter()
    screen_w, screen_h = _get_screen_size()

    while True:
        if ctx.stop_event.is_set():
            return {"ok": False, "error": "任务已停止"}
        
        # 1. 截图搜索区域
        if all(v == 0 for v in search_region):
            region = (0, 0, screen_w, screen_h)
        else:
            region = tuple(search_region)
        
        img = capture_screen(region)

        # 2. 根据方法识别目标
        target_pos = None
        if method == "color":
            target_color_hex = params.get("target_color", "#FF0000")
            # 颜色检测 → 获取匹配像素的中心位置
            target_pos = _detect_by_color(img, target_color_hex)
        elif method == "image":
            template_path = params.get("target_image", "")
            result = do_image_match(img, template_path, threshold=0.7)
            if result["found"]:
                target_pos = (result["match_x"], result["match_y"])
        elif method == "ocr":
            # OCR 检测文字位置
            target_pos = _detect_by_ocr(img, params.get("target_text", ""), context)

        # 3. 计算鼠标移动
        if target_pos is None:
            # 未找到目标
            if track_mode == "avoid":
                return {"ok": True, "set_variables": {params.get("store_var_found", ""): False}, "flow": "lost"}
            if time.perf_counter() - start_time > timeout_ms / 1000:
                return {"ok": True, "flow": "lost"}
            precise_sleep(0.016, ctx.stop_event)  # ~60fps
            continue

        center_x, center_y = target_pos
        cursor_x, cursor_y = _get_cursor_pos()
        
        if track_mode == "center":
            # 将目标移动到屏幕中央
            dx = center_x - screen_w / 2
            dy = center_y - screen_h / 2
            target_cursor = (cursor_x + dx, cursor_y + dy)
        elif track_mode == "follow":
            target_cursor = (center_x, center_y)
        elif track_mode == "avoid":
            # 远离目标
            dx = center_x - cursor_x
            dy = center_y - cursor_y
            target_cursor = (cursor_x - dx, cursor_y - dy)

        # 4. 死区检查
        if abs(target_cursor[0] - cursor_x) < deadzone and abs(target_cursor[1] - cursor_y) < deadzone:
            precise_sleep(0.016, ctx.stop_event)
            continue

        # 5. 移动鼠标（平滑插值）
        _smooth_move(cursor_x, cursor_y, target_cursor[0], target_cursor[1], move_speed, ctx)

        if time.perf_counter() - start_time > timeout_ms / 1000:
            return {"ok": True, "flow": "found"}
```

#### 5.3.3 前端的 node.js（可选增强）

提供可视化配置界面，在属性面板中渲染目标选择器（颜色吸取、区域框选预览）。

### 5.4 YOLO/深度学习方案（进阶）

插件系统支持加载 ONNX 格式的 YOLO 模型进行目标检测：

```python
# 在 backend.py 初始化时加载模型
import onnxruntime as ort
import numpy as np

_YOLO_SESSION = None

def _get_yolo():
    global _YOLO_SESSION
    if _YOLO_SESSION is None:
        _YOLO_SESSION = ort.InferenceSession("plugins/target_tracker/yolo.onnx")
    return _YOLO_SESSION

def _detect_by_yolo(img):
    session = _get_yolo()
    # 预处理 + 推理 + 后处理
    ...
    return (center_x, center_y), class_name, confidence
```

### 5.5 复杂度评估

**中高复杂度（插件形式）**。核心工作量：
- 插件框架已有，直接可用
- 颜色/图片匹配逻辑已有现成库（`do_image_match` / `check_color`）
- PID 平滑控制需要新写（可选）
- YOLO/ONNX 推理需额外依赖

---

## 六、功能五：大语言模型接入（插件形式）

### 6.1 需求分析

1. **自然语言自动化脚本创作**：用户用自然语言描述需求 → LLM 生成 `.auto.json` 节点图
2. **自主根据截图进行决策**：执行过程中截图 → LLM 分析画面 → 决定下一步动作

### 6.2 设计方案

#### 6.2.1 自然语言 → 脚本生成

```
用户输入： "每秒检测一次血条颜色，低于30%就按Q键吃药，打完BOSS后自动拾取"

     ↓ LLM (system prompt = 节点类型定义 + 示例脚本)
     
输出： .auto.json 格式的节点图
     ↓
前端加载到画布 → 用户可预览/编辑/执行
```

**实现方式（插件）：**

创建 `plugins/llm_assistant/`，提供 `plugin/llm_generate` 节点：

| 参数 | 类型 | 说明 |
|------|------|------|
| `prompt` | text | 用户自然语言描述 |
| `api_endpoint` | string | LLM API 地址（Ollama/OpenAI 兼容） |
| `api_key` | string | API Key |
| `model` | string | 模型名称 |
| `temperature` | number | 生成温度 |
| `store_var_result` | string | 存储生成的 JSON |

**System Prompt 设计：**

需要将节点类型定义、参数 schema、连线规则 compile 到 prompt 中。项目已有 `PluginRegistry.get_frontend_payload()` 可以获取所有节点定义。

```python
SYSTEM_PROMPT = """
你是一个自动化脚本生成器。根据用户的自然语言描述，生成一个 JSON 格式的节点图。

## 可用节点类型
{node_definitions}

## 输出格式
```json
{{
  "variables": {{}},
  "settings": {{"execution_profile": "standard"}},
  "graph": {{
    "nodes": [...],
    "connections": [...]
  }}
}}
```

## 规则
1. 必须有且仅有一个 flow/start 节点
2. 每个节点的 id 必须是唯一数字
3. 连线指定 from/port 和 to/port
4. 坐标随意分配（用户可在编辑器中调整）
"""
```

#### 6.2.2 截图 → LLM 决策

创建一个"AI 决策"节点 `plugin/ai_decide`，在执行流程中：
1. 截图当前画面
2. 将截图 + 预设的决策 prompt 发送给视觉 LLM
3. 根据 LLM 返回的决策走不同分支

```json
{
  "type": "plugin/ai_decide",
  "display_name": "AI 决策",
  "outputs": [
    {"name": "action_a", "type": "flow"},
    {"name": "action_b", "type": "flow"},
    {"name": "action_c", "type": "flow"},
    {"name": "unknown", "type": "flow"}
  ],
  "params_schema": {
    "api_endpoint": {"type": "string", "default": "http://localhost:11434"},
    "model": {"type": "string", "default": "llava"},
    "prompt_template": {"type": "text", "default": "分析画面中的情况：\n- 如果看到怪物，回复 A\n- 如果血量低，回复 B\n- 如果看到宝箱，回复 C\n- 否则回复 UNKNOWN"},
    "capture_mode": {"type": "enum", "default": "full", "options": ["full", "region"]},
    "region": {"type": "region", "default": [0, 0, 0, 0]},
    "max_tokens": {"type": "number", "default": 100},
    "store_var_decision": {"type": "string", "default": "", "varRef": true},
  }
}
```

```python
# backend.py
def execute(params, context):
    api_endpoint = params.get("api_endpoint", "http://localhost:11434")
    model = params.get("model", "llava")
    prompt = params.get("prompt_template", "")
    
    # 1. 截图
    region = params.get("region", [0, 0, 0, 0])
    img = context.capture(region)
    
    # 2. 编码图片为 base64
    import base64, cv2
    _, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
    img_b64 = base64.b64encode(buffer).decode()
    
    # 3. 调用 LLM
    response = _call_llm(api_endpoint, model, prompt, img_b64)
    
    # 4. 解析决策
    decision = response.strip().upper()
    flow_map = {"A": "action_a", "B": "action_b", "C": "action_c"}
    flow = flow_map.get(decision, "unknown")
    
    return {
        "ok": True,
        "set_variables": {params.get("store_var_decision", ""): decision},
        "flow": flow,
    }
```

### 6.3 性能考虑

- **延迟问题**：LLM 推理通常需要 0.5-5 秒，不适合实时战斗场景
- **适用场景**：战略决策（如"先打哪个"）、非实时分析、脚本生成阶段
- **成本控制**：本地 Ollama 无 API 费用，但远程 API 需记录 token 用量

### 6.4 复杂度评估

**中等复杂度（插件形式）**。核心工作量：
- LLM 调用客户端（`requests` 或 `openai` 库）
- System prompt 工程（从 `PluginRegistry` 生成节点定义文档）
- 前端节点 UI
- `node.js` 中提供 Prompt 模板编辑器和测试功能

---

## 七、总体实施优先级建议

| 优先级 | 功能 | 理由 |
|--------|------|------|
| **P0（周期1）** | 节点搜索高亮 | 低复杂度，无后端改动，极大提升大画布可用性 |
| **P1（周期2）** | 执行日志面板 | 中复杂度，参照变量面板实现，性能风险可控 |
| **P2（周期3）** | 节点断点调试 | 中复杂度，依赖日志面板提供反馈，需引擎改造 |
| **P3（周期4）** | 目标跟踪（插件） | 中高复杂度，插件形式独立开发，可渐进增强 |
| **P4（周期5）** | LLM 接入（插件） | 中复杂度，插件形式，依赖外部 LLM 服务 |

### 依赖关系

```
节点搜索高亮 ──────────────────────────────────────────────────────→ 独立
执行日志面板 ─────→ 为断点调试提供执行状态可视化 ─────────────────→ 被断点依赖
节点断点调试 ─────→ 需要日志面板反馈 + 引擎暂停/恢复改造 ────────→ 依赖日志
目标跟踪(插件) ───→ 独立插件，可单独开发 ─────────────────────────→ 独立
LLM接入(插件) ────→ 独立插件，可单独开发 ─────────────────────────→ 独立
```

---

## 八、待讨论的关键决策点

### 8.1 断点数据持久化

是否将断点信息保存到 `.auto.json` 文件中？

- **选项 A**：不持久化，断点只在编辑会话内有效
- **选项 B**：持久化到脚本文件中（在 `graph.breakpoints` 字段）

建议先做 A，后续按需做 B。

### 8.2 断点与分支的交互

在 Fork/Race 并发分支中遇到断点时的行为：

- **选项 A**：所有分支统一暂停（当前 `ctx.pause_event` 行为）
- **选项 B**：仅暂停当前分支，其他分支继续执行

建议先做 A（利用现有暂停机制），如果用户反馈需要分支级断点再扩展。

### 8.3 日志面板的默认状态

- **建议**：默认关闭（`_log_enabled = False`），用户手动开启
- 面板关闭时引擎零开销
- 面板打开时的开销主要为 `perf_counter()`（亚微秒级），不会影响毫秒级精度的宏执行

### 8.4 日志面板实时更新策略

- **前端轮询**：复用现有 `setInterval` 机制（1 秒间隔），从 `get_execution_log` 获取增量数据
- **增量传输**：只传新记录（基于 `last_log_id`），减少带宽
- **统计信息**：`get_stats` 独立传输（仅在面板打开时请求）

### 8.5 LLM 模型选择

- **本地部署**：Ollama + llava/qwen-vl（免费但需 GPU）
- **远程 API**：OpenAI GPT-4V / Claude Vision（付费但效果好）
- **混合**：脚本生成用远程 API（低频），决策用本地模型（高频）

---

## 九、总结

各项功能均可在现有架构基础上实现，无需大规模重构：

| 功能 | 涉及后端改动 | 涉及前端改动 | 新增文件 | 风险 |
|------|-------------|-------------|----------|------|
| 节点搜索高亮 | 无 | ~200 行 | 1 个 JS | 低 |
| 节点断点调试 | ~60 行 | ~100 行 | 0 | 中（需仔细处理并发） |
| 执行日志面板 | ~120 行 | ~250 行 | 2 个文件 | 低（性能可控） |
| 目标跟踪(插件) | ~300 行 | ~150 行 | 3 个文件 | 中 |
| LLM接入(插件) | ~250 行 | ~200 行 | 3 个文件 | 中（依赖外部服务） |

请对以上设计提出你的意见和反馈，我们再细化具体实现细节。