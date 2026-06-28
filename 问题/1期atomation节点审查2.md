**中文总结：**

1. **用户要我做什么**：对检测节点模块和控制节点模块进行与动作节点同样深度的全面检查，特别关注"截图源"和各控制节点的联动场景、嵌套使用等复杂情况。
2. **计划步骤**：
   - 读取检测节点后端处理器代码
   - 读取控制节点后端处理器代码
   - 逐个检查每个节点的前后端参数一致性、showWhen、端口设计
   - 特别分析截图源与其他检测节点的联动关系
   - 分析控制节点的嵌套场景（循环嵌套、fork/join配对、goto跳转等）
   - 检查DAG执行引擎中控制流的处理逻辑
   - 汇总所有问题
3. **缺少的信息**：检测节点和控制节点的后端处理器代码，需要先读取。

***

# 🔍 自动化编辑器 - 检测节点 & 控制节点 全面问题报告

***

## 一、检测节点模块

### 🔴 BUG-D1: `check_screen` — 后端调用 `_do_check()` 函数名错误

- **代码位置**: \[detection.py:528]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/detection.py#L528)

```python
if not wait:
    found = _do_check()  # ❌ 函数名错误！
```

- **实际定义**: 第503行定义的是 `_do_check_screen()`
- **影响**: **当** **`wait=False`（默认值）时，`check_screen`** **节点会直接抛出** **`NameError`** **异常**，被 except 捕获后走 `no` 分支。也就是说，**屏幕状态检测节点在非等待模式下永远返回"不匹配"**。
- **严重性**: 🔴🔴🔴 **这是一个致命BUG**，核心功能完全失效！
- **同样的问题也出现在第538行**: `found = _do_check()` 也应该是 `_do_check_screen()`

### 🔴 BUG-D2: `capture_source` — 输出端口名与后端执行不一致

- **后端定义** \[detection.py:8]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/detection.py#L8): `"outputs": [{"name": "out", "type": "flow"}]`
- **后端处理器** \[detection.py:66]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/detection.py#L66): `_execute_flow(node.id, "out", ctx)` ✅ 一致
- **前端 fallback** \[nodes.js:275]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L275): `outputs: [{name:'out',type:'flow'}]` ✅ 一致
- **但是**: 所有其他检测节点的输出端口名是 `match`/`no`，而截图源是 `out`。这本身不是bug，但端口名映射 `_portNameMap` 中 `out: '输出'`，而截图源的 `out` 含义是"下一步"而非"数据输出"，容易让用户误解。
- **建议**: 将截图源的输出端口名改为 `next`，与其他节点保持一致。

### 🔴 BUG-D3: `capture_source` — window 模式不支持但参数仍可设置

- **后端处理器** \[detection.py:56-57]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/detection.py#L56):

```python
if capture_mode == "window" and hwnd:
    ctx.log_error("截图源: window模式暂不支持DXGI，将使用全屏采集", node_id=node.id)
```

- **问题**: `capture_mode` 的 enum 包含 `window` 选项，但后端明确不支持。用户选择 window 模式后，虽然不会崩溃，但会静默回退到全屏，且只在日志中记录错误。
- **影响**: 用户以为在采集特定窗口，实际在采集全屏，后续检测节点的坐标会不匹配。
- **修复建议**: 要么真正实现 window 模式，要么从 enum 中移除 `window` 选项，或在前端给出明确警告。

### 🔴 BUG-D4: `capture_source` — 截图源与检测节点的联动存在隐式依赖

- **截图源**启动 DXGI 后台采集，将 `CaptureManager` 存入 `ctx._capture_manager`
- **检测节点**通过 `capture_screen(region, ctx=ctx)` 使用截图源
- **关键代码** \[capture.py:31-36]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/detection/capture.py#L31):

```python
def capture_screen(region=None, ctx=None):
    if ctx is not None and hasattr(ctx, '_capture_manager'):
        cm = ctx._capture_manager
        if cm is not None:
            return cm.capture(region)
    return _capture_mss(region)
```

- **问题1**: 如果截图源节点**未被连接到流程中**（没有 flow 连接），DXGI 不会启动，检测节点会回退到 mss 截图。但前端没有任何提示告诉用户需要先连接截图源。
- **问题2**: 截图源的 `region` 参数只用于 DXGI 启动时的采集范围，但检测节点自己也有 `rect` 参数。如果截图源设置了 region 裁剪，检测节点的 rect 是基于全屏坐标还是裁剪后的坐标？**代码中** **`cm.capture(region)`** **传入的是检测节点解析后的 region，而 DXGI 的** **`get_region_frame`** **是在全屏帧上裁剪**，所以检测节点的坐标应该是全屏坐标——但这与截图源设置的 region 参数无关，造成用户困惑。
- **问题3**: 截图源设置了 `fps` 参数，但检测节点在 `wait=True` 模式下使用自己的 `wait_interval_ms` 控制轮询频率。两者之间没有协调机制。

### 🔴 BUG-D5: `check_color` — `change_threshold` 和 `area_ratio_threshold` 缺少 varRef

- **后端定义** \[detection.py:39-40]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/detection.py#L39):
  - `change_threshold`: **没有 varRef**
  - `area_ratio_threshold`: **没有 varRef**
- **前端 fallback** \[nodes.js:287-288]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L287): 同样没有 varRef
- **但后端处理器** \[detection.py:91]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/detection.py#L91): `area_ratio_threshold = float(_resolve_value(params.get("area_ratio_threshold", 0.5), ctx))` — 使用了 `_resolve_value`！
- **影响**: 后端支持变量引用但前端不提供变量选择按钮。用户如果手动输入 `${var}` 可以工作，但没有 UI 辅助。
- **同样**: `change_threshold` 在后端 \[detection.py:105]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/detection.py#L105) 没有使用 `_resolve_value`，但 `tolerance` 使用了。设计不一致。

### 🟡 BUG-D6: `check_ocr` — `match_number` 缺少 varRef

- **后端定义** \[detection.py:68]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/detection.py#L68): `"match_number": {...}` — **没有 varRef**
- **后端处理器** \[detection.py:174]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/detection.py#L174): `match_number = float(params.get("match_number", 0))` — **没有使用** **`_resolve_value`**
- **前端 fallback** \[nodes.js:300]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L300): 也没有 varRef
- **影响**: 用户无法通过变量动态设置比较数值，限制了灵活性。

### 🟡 BUG-D7: `check_ocr` — `cache_interval_ms` 缺少 varRef

- **后端处理器** \[detection.py:184]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/detection.py#L184): `cache_interval_ms=int(params.get("cache_interval_ms", 100))` — **没有使用** **`_resolve_value`**
- **对比**: `wait_interval_ms` 使用了 `_resolve_value`，设计不一致。

### 🟡 BUG-D8: `check_image` — `template_path` 缺少 varRef 和 browseType 不一致

- **后端定义** \[detection.py:98]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/detection.py#L98): `"template_path": {"type": "string", "default": "", "format": "path", ...}` — **没有 varRef**
- **前端 fallback** \[nodes.js:405]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L405): `template_path:{type:'path',label:'模板图片',default:'',browseType:'template'}`
- **问题1**: 后端没有 varRef，前端 fallback 中 `_normalizeSchema` 会自动给 `template_path` 加 `browseType:'template'`（见 nodes.js:140-142），但不会自动加 varRef。
- **问题2**: 后端定义中 `format: "path"` 但前端 fallback 中 `type: 'path'`，经过 `_normalizeSchema` 后 `type` 会被改为 `'path'`，但后端定义中 `type` 仍是 `'string'`。如果后端定义正常加载，`_normalizeSchema` 的 `format === 'path'` 检查会将 type 改为 `'path'`，所以这是一致的。

### 🟡 BUG-D9: `check_image` — `method` 和 `pyramid_levels` 缺少 varRef

- **后端处理器** \[detection.py:321]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/detection.py#L321): `method = method_map.get(params.get("method", ...))` — 不需要 varRef（enum）
- **但** `pyramid_levels` 在后端 \[detection.py:324]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/detection.py#L324): `pyramid_levels = int(_resolve_value(params.get("pyramid_levels", 2), ctx))` — 使用了 `_resolve_value`
- **后端定义** \[detection.py:102]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/detection.py#L102): `"pyramid_levels": {...}` — **没有 varRef**
- **前端 fallback** \[nodes.js:409]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L409): 也没有 varRef，但 `_normalizeSchema` 会自动给 `pyramid_levels` 加 varRef（见 nodes.js:121-124）。所以前端 fallback 是OK的，但后端定义缺少 varRef。

### 🟡 BUG-D10: `check_color` — `check_mode` 的 `change` 和 `area` 模式缺少 showWhen 对 `sample_mode` 的限制

- **后端定义**: `sample_mode` 有 `center`, `mean`, `max_diff` 三个选项
- **问题**: 当 `check_mode=change` 时，`sample_mode` 的 `center` 选项没有意义（变化检测需要比较两帧图像，与采样方式无关）。当 `check_mode=area` 时，`max_diff` 选项也没有意义。
- **影响**: 不影响功能，但不够友好。

### 🟡 BUG-D11: `check_screen` — `region` 参数缺少 showWhen 条件

- **后端定义** \[detection.py:126]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/detection.py#L126): `"region": {...}` — **没有 showWhen**
- **前端 fallback** \[nodes.js:420]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L420): `region:{type:'region',...}` — **没有 showWhen**
- **问题**: `region` 参数在 `mode=window` 或 `mode=relative` 时才需要精确设置，在 `mode=screen` 时默认 `[0,0,0,0]`（全屏）即可。但没有 showWhen 限制。
- **对比**: `hwnd_var` 有 `showWhen: "mode=window"`，但 `region` 没有。

### 🟡 BUG-D12: `check_screen` — `threshold` 描述不完整

- **后端**: `"threshold": {"type": "number", "default": 30, "description": "亮度阈值(0-255)"}`
- **问题**: `threshold` 在不同 `state` 下含义不同：
  - `black`: 平均亮度低于 threshold → 匹配
  - `bright`: 平均亮度高于 (255-threshold) → 匹配
  - `frozen`: 帧差低于 threshold → 匹配
- **影响**: 用户不知道 threshold 在 frozen 模式下是帧差阈值而非亮度阈值。

### 🟡 BUG-D13: 所有检测节点 — `hwnd_var` 在 `mode=relative` 时也应显示

- **当前**: `hwnd_var` 的 showWhen 通常是 `"mode=window"`
- **但后端** \[coordinate.py:98-104]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/engine/coordinate.py#L98): `relative` 模式也需要 `hwnd` 来获取窗口客户区尺寸
- **影响**: 用户选择 `mode=relative` 时看不到 `hwnd_var` 字段，无法指定窗口，导致回退到 1920x1080 默认尺寸。
- **修复**: showWhen 应改为 `"mode=window,mode=relative"` 或 `"mode!=screen"`

### 🟡 BUG-D14: `check_image` — `confidence` 输出未在节点定义中声明

- **后端处理器** \[detection.py:438]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/detection.py#L438): `ctx.check_results[f"{node.id}.confidence"] = check_result["confidence"]`
- **但节点定义** \[detection.py:87-93]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/detection.py#L87): outputs 只有 `match`, `no`, `result`, `match_x`, `match_y` — **没有** **`confidence`** **输出端口**
- **影响**: `confidence` 数据被存储在 `check_results` 中，但没有对应的输出端口，用户无法通过数据连线获取置信度。只能通过 `${nodeID.confidence}` 变量引用获取，但前端变量选择器中也不会显示这个字段。

***

## 二、控制节点模块

### 🔴 BUG-C1: `loop_count` — `count` 默认值前后端不一致

- **后端定义** \[control.py:33]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/control.py#L33): `"count": {"type": "number", "default": 1, ...}`
- **前端 fallback** \[nodes.js:316]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L316): `count:{type:'number',label:'循环次数',default:5,varRef:true}`
- **影响**: 后端默认循环1次，前端默认5次。用户拖出节点后看到5次循环，但实际执行可能只有1次。

### 🔴 BUG-C2: `if_else` — `fallback` 参数类型设计问题

- **后端定义** \[control.py:17]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/control.py#L17): `"fallback": {"type": "string", "enum": ["true", "false"], "default": "false", ...}`
- **后端处理器** \[control.py:29]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/control.py#L29): `result = node.params.get("fallback", "false") == "true"`
- **前端 fallback** \[nodes.js:312]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L312): `fallback:{type:'enum',label:'无输入时',default:'false',options:['true','false']}`
- **问题**: `fallback` 是字符串 `"true"/"false"` 而不是布尔值。前端渲染为 enum 下拉框，选项显示的是英文 `"true"/"false"`，对中文用户不友好。
- **修复建议**: 改为布尔类型，或至少将选项显示为中文"是"/"否"。

### 🔴 BUG-C3: `goto` — 跳转到已执行节点时 executed\_set 阻止重新执行

- **引擎代码** \[engine.py:578-581]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/engine.py#L578):

```python
with ctx._data_lock:
    if node_id in executed_set:
        return  # 直接返回，不执行！
    executed_set.add(node_id)
```

- **goto 处理器** \[control.py:196-201]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/control.py#L196): 设置 `ctx._goto_target = target_id`
- **引擎 goto 循环** \[engine.py:590-658]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/engine.py#L590): goto 后 `current_id = goto_target`，然后调用 `_execute_node(goto_target, ctx)`
- **问题**: 如果 goto 跳转回一个已经执行过的节点，`executed_set` 会阻止它重新执行，goto 循环实际上不会工作。
- **场景**: `开始 → 动作A → goto → 动作A`（想循环执行A），第二次执行A时会被跳过。
- **严重性**: 🔴🔴 goto 节点的核心循环功能失效！

### 🔴 BUG-C4: `loop_count` — 循环体内检测节点的 check\_results 不会重置

- **循环重置逻辑** \[engine.py:488-492]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/engine.py#L488):

```python
def _reset_body_nodes(body_nodes, ctx: ExecContext):
    branch_ctx = ctx._get_current_branch_ctx()
    executed_set = branch_ctx._executed_nodes if branch_ctx else ctx._executed_nodes
    with ctx._data_lock:
        executed_set -= body_nodes  # 只重置了 executed_set
```

- **问题**: 只重置了 `executed_set`（允许节点重新执行），但**没有重置** **`check_results`**。
- **场景**: `计数循环 → 颜色检测 → if_else`。第一次循环中颜色检测匹配了（`check_results[nodeID.result] = True`），第二次循环即使颜色不匹配，`check_results` 中仍保留上一次的 `True`，if\_else 仍走 true 分支。
- **影响**: 🔴 循环内检测节点的结果不会更新，导致条件判断错误！

### 🔴 BUG-C5: `loop_while` — 条件输入不随循环体更新

- **编译器警告** \[compiler.py:196-202]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/compiler.py#L196): 已经检测到这个问题并发出警告
- **引擎实现** \[control.py:74-78]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/control.py#L74):

```python
data_sources = node.get_data_inputs("cond")
conditions = [ctx.check_results.get(f"{src['source_node_id']}.{src['source_port']}", False)
              for src in data_sources]
```

- **问题**: `loop_while` 的 `cond` 数据输入来自循环体**外部**的节点时，条件值在循环中不会更新（因为外部节点只执行一次）。即使来自循环体内部的节点，由于 BUG-C4（check\_results 不重置），条件也可能不会正确更新。
- **场景**: 用户想实现"当屏幕上某颜色存在时循环"，将颜色检测放在循环体内，但颜色检测的 result 不会更新。
- **修复方案**（详见 `docs/execution-model-upgrade-design.md` §3）：条件类控制节点每次求值条件时，自动重新执行直接连到 cond 数据输入端口的上游节点。只追溯直接连入的单个节点，不递归。变量引用方式（`cond_var`）不触发重新执行。

### 🔴 BUG-C6: `fork` — `next` 输出端口语义误导 + 缺少"完成"端口

- **后端处理器** \[control.py:362]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/control.py#L362): `_execute_flow(node.id, "next", ctx)`
- **问题**: fork 节点先启动所有分支线程，然后**立即**执行 `next` 端口。这意味着 `next` 分支与各并发分支是**同时执行**的，而不是等待所有分支完成后执行。
- **用户预期**: 用户可能期望 `next` 是"fork 之后"的步骤，即所有分支完成后再执行。但实际上 `next` 是与分支并行的。
- **影响**: 如果 `next` 后面连接了 join 节点，会产生竞态条件。如果 `next` 后面连接了依赖分支结果的节点，会得到未完成的数据。
- **修复方案**（详见 `docs/execution-model-upgrade-design.md` §2）：
  1. `next` 端口前端显示名改为"立即"，端口内部名不变（避免破坏已保存脚本）
  2. 新增 `done` 端口（显示名"完成"），所有分支执行完毕后触发
  3. 属性面板添加用户提示说明"立即"端口的语义

### 🔴 BUG-C7: `race` — 执行模型设计缺陷：无竞争结束点，流程终止

- **后端定义** \[control.py:184-188]: outputs 只有 `branch1`, `branch2`... 没有 `next` 或 `done`
- **后端处理器** \[control.py:553-675]: race 启动所有分支后，`race_worker` 中 `_execute_flow(node.id, port_name, ctx)` 会执行整个分支链直到末端，然后才标记 winner。race 主线程阻塞等待后取消其他分支，但**没有执行任何输出端口**。
- **根本问题**：
  1. **没有"竞争结束点"**：分支中所有节点都属于"竞争阶段"，没有分界线标识"到此竞争结束"。`_execute_flow` 会沿连线一直执行到分支链末端，然后才标记 winner。
  2. **取消其他分支的时机太晚**：要等赢家分支的整条链都跑完，其他分支才能被取消。实际场景中，用户希望某个检测成功后**立即**取消其他分支。
  3. **赢家分支无法继续执行后续节点**：`_execute_flow` 已执行完整条链，race 结束后流程就终止了。用户无法在 race 胜出后继续执行专属后续逻辑。
  4. **每个分支的后续动作可能不同**：游戏场景中，检测到红色怪物→执行红色连招，检测到蓝色怪物→执行蓝色连招，各分支后续不同。当前设计无法支持。
- **场景**：
  - 用户想实现"颜色检测和OCR检测竞争，谁先成功就走谁的分支，然后继续执行该分支的专属后续步骤"——无法实现
  - 用户想实现"检测红色怪物→红色连招、检测蓝色怪物→蓝色连招、检测BOSS→闪避逻辑"——无法实现
  - 用户想让两个分支共享后续动作（通过Join汇合）——无法实现
- **修复方案**（详见 `docs/execution-model-upgrade-design.md` §1）：
  - **新增 `control/race_win` 节点**：放在分支内部，标记"竞争结束点"
  - 到达 `race_win` 时：立即通知 race 主线程取消其他分支，**当前分支继续执行 `race_win` 之后的节点**
  - `Scope` 增加 `winner_branch_id` 字段，`ExecContext` 增加 `_race_events` 字典
  - 改造 `_handle_race`：`race_worker` 不再设置 winner，由 `race_win` 节点负责；主线程只负责等待和超时处理
  - 向后兼容：分支中无 `race_win` 时，整条链执行完仍标记 winner（与当前行为一致）
  - **多分支共享后续**：race_win 之后接 Join(any) 节点汇合，执行公共收尾动作
  - **部分分支汇合**：只有部分分支的后续连到同一个 Join，其他分支独立

### 🟡 BUG-C8: `seq_check` 和 `state_machine` — 缺少 `cond` 数据输入端口

- **后端定义**:
  - `seq_check` \[control.py:97]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/control.py#L97): inputs 只有 `{"name": "in", "type": "flow"}`
  - `state_machine` \[control.py:115]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/control.py#L115): inputs 只有 `{"name": "in", "type": "flow"}`
- **但后端处理器**:
  - `seq_check` \[control.py:212-213]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/control.py#L212): `data_sources = node.get_data_inputs("cond")` — 读取 `cond` 数据输入
  - `state_machine` \[control.py:239-240]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/control.py#L239): 同样读取 `cond` 数据输入
- **影响**: **节点定义中没有声明** **`cond`** **数据输入端口，用户无法从其他节点连线到** **`cond`** **端口**。但后端处理器却依赖 `cond` 输入。这意味着这两个节点**永远收到空的 conditions 列表**：
  - `seq_check`: `conditions` 为空 → `all(conditions)` 为 `True`（Python 中 `all([])` 返回 `True`）→ **永远走 pass 分支**
  - `state_machine`: `cond_val` 为 `None` → 进入 `else` 分支持续 sleep → **永远卡住**
- **严重性**: 🔴🔴 这两个节点在当前定义下**完全无法正常工作**！

### 🟡 BUG-C9: `wait_cond` — 条件检查不重新执行上游检测节点

- **后端处理器** \[control.py:182-193]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/control.py#L182):

```python
while time.time() < deadline:
    data_sources = node.get_data_inputs("cond")
    conditions = [ctx.check_results.get(f"{src['source_node_id']}.{src['source_port']}", False)
                  for src in data_sources]
    if conditions and all(conditions):
        _execute_flow(node.id, "met", ctx)
        return
    precise_sleep(interval_ms / 1000.0, ctx.stop_event)
```

- **问题**: `wait_cond` 在循环中只读取 `check_results`，但**不会重新执行上游检测节点**。如果上游检测节点只执行了一次（在 `wait_cond` 之前），`check_results` 中的值不会更新。
- **场景**: `颜色检测 → wait_cond`。颜色检测执行一次后，无论结果如何，`wait_cond` 只会反复读取同一个结果。
- **正确用法**: 需要将检测节点放在循环体内部，但这需要 `loop_while` 配合，而 `loop_while` 又有 BUG-C5 的问题。
- **影响**: `wait_cond` 节点在当前设计下**几乎无法正确使用**。
- **修复方案**（详见 `docs/execution-model-upgrade-design.md` §3）：与 BUG-C5 统一修复——条件类控制节点每次求值条件时，自动重新执行直接连到 cond 数据输入端口的上游节点。

### 🟡 BUG-C10: `stop_branch`/`pause_branch`/`resume_branch` — `target_branch` 填写不友好

- **参数**: `"target_branch": {"type": "string", "default": "all_others", ...}`
- **问题**: 用户需要填写分支ID（如 `"5_branch1"`），但：
  1. 分支ID是运行时动态生成的，用户在编辑时不知道具体ID
  2. 没有提供分支选择器（类似 nodeRef 的分支引用）
  3. 默认值 `all_others` 是唯一容易使用的选项
- **影响**: 除了 `all_others` 之外，用户几乎无法正确指定特定分支ID。
- **修复方案**（详见 `docs/execution-model-upgrade-design.md` §5）：(1) 允许用户给 Fork/Race 分支端口重命名；(2) `target_branch` 参数改为分支选择器（类似 nodeRef），下拉显示 Fork/Race 节点及其端口名；(3) `race_win` 的 `winner_branch` 输出改为用户可读标识。

### 🟡 BUG-C11: `fork`/`race` — `branch_affinity` 参数类型前后端不一致

- **后端定义** \[control.py:137]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/control.py#L137): `"type": "object"`，默认值是 Python dict `{"enabled": False, "core": -1}`
- **前端 fallback** \[nodes.js:447-448]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L447): `type:'affinity'`，默认值是 JS 对象
- **`_normalizeSchema`** 处理: 后端 `type: "object"` 不会被转换为 `'affinity'`，只有前端 fallback 中才用 `'affinity'` 类型
- **问题**: 如果后端定义正常加载，`branch_affinity` 的 type 是 `"object"`，前端 `_renderGroup` 的 switch 语句没有 `"object"` case，会走到 default 分支，渲染为普通字符串输入框。用户需要手动输入 JSON 格式如 `{"enabled": true, "core": 0}`。
- **影响**: 后端定义加载时，绑核设置无法通过友好的 checkbox + number 输入设置。

### 🟡 BUG-C12: `join` — `target_fork_node_id` 的 nodeRef 在前端实现但不完善

- **后端定义** \[control.py:173]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/control.py#L173): `"nodeRef": "fork_race"`
- **前端** `_renderNodeRefField` 实现: 会查找类型为 `control/fork` 或 `control/race` 的节点，提供下拉选择
- **问题**: 选择后存储的是节点 ID（数字），但后端处理器 \[control.py:368-370]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/control.py#L368) 使用这个 ID 查找 scope：

```python
target_fork_node_id = join_node.params.get("target_fork_node_id", "")
scope = ctx._scopes.get(f"{target_fork_node_id}_scope")
```

- **潜在问题**: 如果用户通过下拉选择了 fork 节点，存储的是 fork 节点的 ID（如 `"5"`），scope 的 key 是 `"5_scope"`。这应该是正确的。但如果用户手动输入了错误的 ID，会找不到 scope，join 会回退到自动推断模式。

### 🟡 BUG-C13: `fork` + `join` 嵌套使用时的 scope 隔离问题

- **场景**: `fork_A → [branch1: fork_B → [branch1_1, branch1_2], branch2] → join_B → join_A`
- **代码分析**:
  - `fork_A` 创建 `scope_A`，包含 `branch1`, `branch2`
  - `branch1` 内的 `fork_B` 创建 `scope_B`，`scope_B.parent_branch_id = branch1_id`
  - `fork_A` 的代码 \[control.py:306-309]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/control.py#L306): `parent_bctx.child_scope_ids.append(scope_id)` — 将 `scope_B` 添加为 `branch1` 的子 scope
  - `join_A` 的 `_resolve_join_targets` \[control.py:370-376]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/control.py#L370): 会收集 `scope_A` 的所有 branch\_ids 和 child\_scope\_ids 的 branch\_ids
  - **问题**: `join_A` 会等待 `scope_B` 的分支（`branch1_1`, `branch1_2`）也完成，但 `join_B` 已经在 `branch1` 内部等待了这些分支。这可能导致 `join_A` 永远等待 `branch1_1`/`branch1_2`，因为它们已经被 `join_B` 处理完毕但没有通知 `join_A`。
  - **影响**: 嵌套 fork/join 可能导致死锁。

### 🟡 BUG-C14: `loop_count` — `counter_var` 是输出变量但标记为 varRef

- **后端定义** \[control.py:34]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/control.py#L34): `"counter_var": {"type": "string", "default": "", "varRef": True, ...}`
- **问题**: `counter_var` 是"将循环计数存入此变量"，是**输出**不是**输入**。但 varRef 标记让前端显示变量选择按钮，用户可能选择一个已有变量并期望读取它的值，而实际是覆盖它。
- **与动作节点的** **`store_hwnd_var`** **同类问题**。

### 🟡 BUG-C15: `call_script_sync`/`call_script_async` — `path` 参数缺少 varRef

- **后端定义** \[control.py:253]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/control.py#L253): `"path": {"type": "string", "format": "path", ...}` — **没有 varRef**
- **前端 fallback** \[nodes.js:324]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L324): `path:{type:'path',label:'宏文件路径',default:''}` — **没有 varRef**
- **影响**: 用户无法通过变量动态指定宏文件路径。

### 🟡 BUG-C16: `call_script_async` — `completed`/`interrupted` 端口的执行上下文问题

- **后端处理器** \[control.py:151-162]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/control.py#L151):

```python
def on_task_complete(task_id, status):
    if ctx.stop_event.is_set():
        return
    if status == "completed":
        _execute_flow(async_node_id, "completed", ctx)
    else:
        _execute_flow(async_node_id, "interrupted", ctx)
```

- **问题**: `on_task_complete` 在 TaskPool 的 worker 线程中调用，而 `_execute_flow` → `_execute_node` 会修改 `executed_set` 等共享状态。虽然 `executed_set` 有 `_data_lock` 保护，但 `_execute_node` 内部的操作并不全是线程安全的。
- **场景**: 主流程正在执行其他节点，同时异步任务完成触发 `on_task_complete`，两个线程同时操作图执行状态。
- **影响**: 可能导致竞态条件、节点重复执行或跳过执行。

***

## 三、联动场景分析

### 🔴 BUG-L1: 截图源 + 检测节点 — 截图源在循环内重复启动

- **场景**: `计数循环 → [截图源 → 颜色检测] → 下一步`
- **问题**: 每次循环都会执行截图源，调用 `cm.start_dxgi()`。虽然 `start_dxgi` 内部有检查（如果已运行会先 stop 再 start），但频繁重启 DXGI 会造成性能问题和短暂的黑帧。
- **修复建议**: 截图源应检测是否已启动，如果已启动且参数未变则跳过。

### 🔴 BUG-L2: 检测节点 + if\_else — 数据端口连线 vs 变量引用的歧义

- **场景1（数据端口连线）**: `颜色检测.result → if_else.cond` — if\_else 读取 `check_results` 中的值
- **场景2（变量引用）**: `颜色检测.store_var = "color_found"` → `if_else` 不使用 cond 端口，而是通过其他方式读取变量
- **问题**: 两种方式都能工作，但用户可能混淆。数据端口连线更直观，但前端变量选择器中也会显示检测节点的输出变量，造成选择困难。

### 🔴 BUG-L3: fork + 检测节点 — 多分支中的截图竞争

- **场景**: `fork → [branch1: 颜色检测A, branch2: 颜色检测B] → join`
- **问题**: 两个分支同时调用 `capture_screen()`，共享同一个 `CaptureManager`。DXGI 的 `get_latest_frame()` 返回的是最新帧，两个检测可能拿到不同的帧（如果帧更新了），导致结果不一致。
- **影响**: 在高帧率截图下，两个检测可能基于不同的屏幕状态做判断。

### 🟡 BUG-L4: loop\_while + 检测节点 — 条件更新的正确方式

- **正确场景**: `loop_while(body) → [颜色检测 → var_set(result_var)]`，`loop_while.cond` 连接 `颜色检测.result`
- **问题**: 由于 BUG-C4（check\_results 不重置），即使颜色检测重新执行了，`check_results` 中的值可能被覆盖也可能不被覆盖（取决于是否是同一个 key）。实际上 `check_results[key] = new_value` 会覆盖，所以这个场景**可能**工作。
- **但**: 如果颜色检测在循环体内但 `cond` 数据输入来自循环体外的节点，条件不会更新（BUG-C5）。

### 🟡 BUG-L5: goto + 循环 — goto 跳入循环体内部

- **场景**: `计数循环 → [动作A → 动作B] → 动作C → goto(动作B)`
- **问题**: goto 跳转到动作B，但动作B在循环体内。由于 executed\_set 的问题（BUG-C3），如果动作B已经执行过，goto 不会让它重新执行。
- **编译器检查** \[compiler.py:137-144]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/compiler.py#L137): 只检查 goto 不跳转到 start 节点，不检查跳入循环体的情况。

### 🟡 BUG-L6: 监视器节点 + fork — 监视器在 fork 分支中的行为

- **场景**: `fork → [branch1: monitor_color, branch2: 动作A]`
- **问题**: `monitor_color` 会阻塞当前分支直到触发或超时。如果 `branch2` 先完成，fork 的 `next` 端口已经执行了后续流程，但 `branch1` 的监视器仍在运行。
- **影响**: 监视器的触发分支可能在 fork 的后续流程已经执行完毕后才触发，导致意外行为。

***

## 问题优先级汇总

| 优先级    | 编号      | 问题                                          | 类型      |
| ------ | ------- | ------------------------------------------- | ------- |
| 🔴🔴🔴 | BUG-D1  | check\_screen 函数名错误，非等待模式完全失效               | 后端致命BUG |
| 🔴🔴   | BUG-C8  | seq\_check/state\_machine 缺少 cond 端口，完全无法工作 | 前后端     |
| 🔴🔴   | BUG-C3  | goto 跳转到已执行节点被阻止                            | 引擎      |
| 🔴🔴   | BUG-C4  | 循环体内 check\_results 不重置                     | 引擎      |
| 🔴     | BUG-D3  | capture\_source window 模式不支持但可选             | 设计      |
| 🔴     | BUG-D4  | 截图源与检测节点联动隐式依赖                              | 设计      |
| 🔴     | BUG-C5  | loop\_while 条件不随循环体更新                       | 引擎      |
| 🔴     | BUG-C6  | fork 的 next 端口语义误导 + 缺少"完成"端口            | 设计      |
| 🔴     | BUG-C7  | race 执行模型设计缺陷：无竞争结束点，需新增race_win节点         | 设计     |
| 🔴     | BUG-C9  | wait\_cond 不重新执行上游检测节点                      | 引擎      |
| 🔴     | BUG-L1  | 截图源在循环内重复启动                                 | 后端      |
| 🟡     | BUG-D5  | check\_color 参数 varRef 缺失                   | 前后端     |
| 🟡     | BUG-D13 | hwnd\_var 在 relative 模式下不显示                 | 前端      |
| 🟡     | BUG-D14 | check\_image confidence 输出未声明               | 前后端     |
| 🟡     | BUG-C1  | loop\_count 默认值不一致                          | 前后端     |
| 🟡     | BUG-C2  | if\_else fallback 参数类型不友好                   | 设计      |
| 🟡     | BUG-C11 | fork/join affinity 类型前后端不一致                 | 前后端     |
| 🟡     | BUG-C13 | 嵌套 fork/join 可能死锁                           | 引擎      |
| 🟡     | BUG-C16 | async completed 端口线程安全                      | 引擎      |
| 🟡     | BUG-L3  | fork 中多分支截图竞争                               | 引擎      |

***

以上就是检测节点和控制节点模块的全面问题报告。最关键的发现是：

**致命BUG（必须立即修复）**:

1. **BUG-D1**: `check_screen` 的 `_do_check()` 函数名错误，导致非等待模式下完全失效
2. **BUG-C8**: `seq_check` 和 `state_machine` 缺少 `cond` 数据输入端口，完全无法正常工作
3. **BUG-C3**: `goto` 跳转到已执行节点被 `executed_set` 阻止
4. **BUG-C4**: 循环体内 `check_results` 不重置，导致检测节点结果不更新

**严重设计问题**:

1. **BUG-C7**: `race` 节点执行模型设计缺陷——无竞争结束点，赢家分支无法继续执行后续节点，需新增 `race_win` 节点（详见 `docs/execution-model-upgrade-design.md` §1）
2. **BUG-C9**: `wait_cond` 不重新执行上游检测节点——与 BUG-C5 统一修复，条件重新执行机制（详见 `docs/execution-model-upgrade-design.md` §3）
3. **BUG-C6**: `fork` 的 `next` 端口语义误导——重命名"立即"+ 新增"完成"端口（详见 `docs/execution-model-upgrade-design.md` §2）
4. **BUG-D3/D4**: 截图源 window 模式不可用、与检测节点联动存在隐式依赖——终端报告截图方式（详见 `docs/execution-model-upgrade-design.md` §8）

**执行模型升级专项**: 以上设计问题涉及执行模型的根本性变更，应作为整体升级规划。详见 `docs/execution-model-upgrade-design.md`。

