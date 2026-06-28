# 自动化脚本引擎 V5.1 开发执行清单

## 阶段 0：底层原语抽离与旧引擎隔离改造

**执行目标**：建立物理隔离基础，将底层输入代码从旧引擎中剥离，完成旧引擎的全量 `Options` 化改造，确保向后100%兼容。
**预估耗时**：1-2天

### 任务 0.1：创建底层输入原语模块

* **操作步骤**：
  1. 创建文件 `webui_backend/input_primitives.py`。
  2. 从 `宏执行框架3.2.py` 中**搬迁**所有 WinAPI 结构体定义（`MOUSEINPUT`, `KEYBDINPUT` 等）、`VK_MAP` 字典、`get_vk` 函数。
  3. 实现纯 `SendInput` 封装函数：`send_key_sendinput`、`send_click_sendinput`、`send_move_sendinput`、`set_cursor_pos`。
  4. **（关键新增）**实现 `InterceptionSession` 类：包含独立的安全回退逻辑（键盘失败5次冷却10秒），供新引擎路径1使用。
* **技术规范**：禁止在此模块中引入任何业务逻辑或全局配置变量，仅保留纯底层原子操作。
* **交付物**：`webui_backend/input_primitives.py`

### 任务 0.2：重构旧引擎 `宏执行框架3.2.py`

* **操作步骤**：
  1. 删除文件内被搬迁的结构体和底层函数代码。
  2. 在文件顶部增加：`from webui_backend.input_primitives import *`，并做兼容性重命名（`send_key_event = send_key_sendinput` 等）。
  3. **全量 Options 化**：重写 `execute_macro_once` 函数签名，增加 `options=None`。在函数开头解析 `_opt`，将 `EXEC_SPEED_FACTOR`、`TIMELINE_EXECUTION_MODE`、`ENABLE_RANDOM_DELAY_ADJUST`、`LAG_USE_PI_CONTROLLER`、`ENABLE_LOW_CPU_EXECUTION`、`ENABLE_BATCH_SEND` 等所有原全局变量替换为 `local_xxx = _opt.get("xxx", GLOBAL_VAR)` 格式，并在后续代码中强制使用 `local_` 前缀变量。
  4. **扩展指令**：在 `_parse` 函数中增加 `move_to`（线性插值移动）、`scroll`（`MOUSEEVENTF_WHEEL`）、中键（`MOUSEEVENTF_MIDDLEDOWN/UP`）的解析分支。
  5. **修饰键开关**：在 `finally` 块中增加 `should_release = _opt.get("auto_release_modifiers", True)` 判断，为 False 时跳过释放。
* **技术规范**：不传 `options` 时，所有变量 fallback 到全局，行为必须与改造前二进制一致。
* **交付物**：修改后的 `宏执行框架3.2.py`

---

## 阶段 1：新引擎骨架与 Schema 驱动注册制

**执行目标**：搭建最小可用的画布与执行闭环，彻底抛弃前端硬编码节点，实现后端 Schema 下发驱动。
**预估耗时**：3-4天

### 任务 1.1：构建后端注册中心与编译器

* **操作步骤**：
  1. 创建 `webui_backend/plugin_registry.py`：实现 `PluginRegistry` 类，包含 `register_node(def_dict)`、`get_frontend_payload()` 方法。`def_dict` 必须包含 `params_schema` (JSON Schema格式)。
  2. 创建 `webui_backend/automation_compiler.py`：定义 `ExecNode` 和 `ExecGraph` 数据类，实现 `parse_graph(json_data)` 方法，解析节点、构建 flow/data 连接字典、寻找入口节点。
* **技术规范**：`get_frontend_payload` 序列化时必须剥离 `def_dict` 中的 `handler` 字段（不可暴露给前端）。
* **交付物**：`webui_backend/plugin_registry.py`, `webui_backend/automation_compiler.py`

### 任务 1.2：实现新引擎核心调度器（仅路径1）

* **操作步骤**：
  1. 创建 `webui_backend/automation_engine.py`。
  2. 定义 `ExecutionProfile` 字典（lite/standard/precision，控制是否启用 Interception、绑核等）。
  3. 实现 `ExecContext` 类（包含 `variables`、`check_results`、`stop_event`）。
  4. 实现 `execute_graph` 入口和 `_execute_node` 递归分发器。
  5. 仅实现三个基础 Handler：`_handle_mouse_click`、`_handle_key_action`、`_handle_wait`。它们需调用 `input_primitives.py` 和 `precision_engine_v5.py`。
* **交付物**：`webui_backend/automation_engine.py`

### 任务 1.3：实现 JS Bridge 与后端入口

* **操作步骤**：
  1. 创建 `webui_backend/automation_bridge_api.py`：实现 `AutomationApiMixin` 类。
  2. 实现 `run_automation(graph_json)`：调用 `parse_graph` -> `execute_graph`。
  3. 实现 `get_node_definitions()`：调用 `PluginRegistry.get_frontend_payload()` 返回给前端。
  4. 修改 `webui_app.py`：使 `MacroBridge` 继承 `AutomationApiMixin`，并在启动时初始化插件。
* **交付物**：`webui_backend/automation_bridge_api.py`，修改后的 `webui_app.py`

### 任务 1.4：前端剥离公共逻辑与 LiteGraph 初始化

* **操作步骤**：
  1. **（禁止复用旧编辑器）**创建 `webui/modules/shared/macro-utils.js`：从现有 `editor.js` 中剥离 `normalizeAction`、`buildActionFromInputs` 等纯函数，移除所有对 `state` 和 DOM 的依赖。
  2. 创建 `webui/modules/automation-core.js`：初始化 LiteGraph 实例，配置画布，监听节点拖拽。
* **交付物**：`webui/modules/shared/macro-utils.js`, `webui/modules/automation-core.js`

### 任务 1.5：前端 Schema 驱动动态节点工厂

* **操作步骤**：
  1. 创建 `webui/modules/automation-nodes.js`。
  2. 实现 `createNodeClass(def)` 通用工厂函数：根据后端下发的 `def.inputs`、`def.outputs`、`def.params_schema` 动态生成 LiteGraph 节点类。
  3. 实现 `initNodes()` 异步函数：请求 `pywebview.api.get_node_definitions()`，遍历动态 `registerNodeType`，并根据 category 动态渲染左侧工具箱。
* **技术规范**：此文件中**绝对不能**出现任何硬编码的节点类型字符串（如 "mouse_click"）或颜色值。
* **交付物**：`webui/modules/automation-nodes.js`

---

## 阶段 2：路径2集成与坐标系统

**执行目标**：打通新旧引擎调用链路，实现三种坐标模式的动态解析。
**预估耗时**：2-3天

### 任务 2.1：实现坐标解析器与路径2调用

* **操作步骤**：
  1. 创建 `webui_backend/coordinate_resolver.py`：实现 `resolve_coords(mode, x, y, hwnd)` 和 `resolve_region(...)`，处理 `screen`/`window`/`relative` 逻辑及 DPI 缩放转换。
  2. 在 `automation_engine.py` 中新增 `_handle_call_script_sync` 处理器：调用旧引擎的 `compile_macro`，构造规范化 `opts` 字典（强制 `auto_release_modifiers: False`），调用 `execute_macro_once`。
  3. 实现超短动作优化：判断 `len(compiled) <= 2` 时，绕过旧引擎主循环，直接在路径1上下文中执行闭包。
* **交付物**：`webui_backend/coordinate_resolver.py`，更新后的 `automation_engine.py`

### 任务 2.2：极简版内嵌块编辑器与坐标联动 UI

* **操作步骤**：
  1. 创建 `webui/modules/automation-block-editor.js`：使用局部变量 `let localRows = []` 维护状态，通过 `document.createElement` 构建UI，引入 `macro-utils.js` 处理数据。提供“上移/下移”代替拖拽。
  2. 更新 `automation-property.js`：当渲染 `call_script_sync` 节点时，增加“编辑动作块”按钮，点击弹出上述极简编辑器模态框。
  3. 实现坐标模式联动：监听 `mode` 下拉框变化，动态修改同节点内坐标输入框的 `step` 属性（`screen/window` 为 1，`relative` 为 0.01）。
* **交付物**：`webui/modules/automation-block-editor.js`，更新后的 `automation-property.js`

---

## 阶段 3：感知模块与条件决策

**执行目标**：实现“眼睛”和“大脑”的基础判断能力，打通 Data 连线。
**预估耗时**：3-4天

### 任务 3.1：后端检测能力模块

* **操作步骤**：
  1. 创建 `webui_backend/detection/capture.py`：封装 `mss`，实现 `capture_screen(region)` 返回 BGR numpy 数组。
  2. 创建 `webui_backend/detection/color.py`：实现 `check_color` 函数，支持 `exact`/`contain`/`change` 模式。
  3. 创建 `webui_backend/detection/ocr.py`：封装 RapidOCR。实现**可配置缓存策略**：根据 Schema 参数 `cache_strategy` 走不同分支（`frame_diff` 用 np.max 判断，`time_interval` 用时间戳，`disabled` 必检）。
* **交付物**：`webui_backend/detection/` 目录下三个文件

### 任务 3.2：后端决策逻辑与预览 API

* **操作步骤**：
  1. 在 `plugin_registry.py` 中注册 `check_color`、`check_ocr`、`if_else` 节点定义（包含完整的 JSON Schema，如 `cache_strategy` 的 enum）。
  2. 在 `automation_engine.py` 中实现 `check_color`/`check_ocr` 处理器：调用检测模块，将结果写入 `ctx.check_results[f"{node_id}.result"]`。
  3. 实现 `if_else` 处理器：收集 `node.data_inputs["cond"]`，从 `ctx.check_results` 提取布尔值，按 `logic` (AND/OR/NOT) 组合决定走向。
  4. 在 API 层实现 `preview_color` 和 `preview_ocr` 接口。
* **交付物**：更新后的 `automation_engine.py`, `automation_bridge_api.py`

### 任务 3.3：前端 Data 端口与检测预览

* **操作步骤**：
  1. 修改 `automation-core.js`：配置 LiteGraph 的 link colors，当端口类型为 `boolean`/`data_bool` 时，连线渲染为红色。
  2. 更新 `automation-property.js`：根据 Schema 中的 `description` 或特定标记，为检测节点渲染“预览”按钮，点击调用预览 API 并展示结果弹窗。
* **交付物**：更新后的前端 JS 文件

---

## 阶段 4：变量系统与循环动态刷新

**执行目标**：赋予脚本记忆能力和精确的动态寻址能力。
**预估耗时**：2天

### 任务 4.1：后端变量解析与循环节点

* **操作步骤**：
  1. 在 `automation_engine.py` 中实现变量系统：初始化 `graph.variables`，实现 `_resolve_value(value, ctx)` 解析 `${var_name}` 语法。
  2. 实现 `loop_count` 处理器：**关键逻辑** - 在每次 `for` 循环体开始前，强制重新调用 `resolve_coords()` 计算坐标（验证动态刷新机制），更新 `counter_var`。
  3. 实现变量操作节点 Handler：`var_set`、`var_math`、`var_compare`。
* **交付物**：更新后的 `automation_engine.py`

### 任务 4.2：前端变量语法支持

* **操作步骤**：
  1. 更新 `automation-property.js`：在文本输入框中监听输入，当检测到 `${` 时，提供已定义变量的自动补全提示，并对变量引用部分进行高亮显示（如添加特定背景色）。
* **交付物**：更新后的 `automation-property.js`

---

## 阶段 5：并发调度与异步打断（核心难点）

**执行目标**：实现后台任务、监视器触发及安全的修饰键管理。
**预估耗时**：3-4天

### 任务 5.1：任务池与异步调用

* **操作步骤**：
  1. 在 `automation_engine.py` 中实现 `TaskPool` 和 `AsyncTask` 数据结构。
  2. 实现 `call_script_async` 处理器：启动独立线程执行旧引擎，主线程立即走 `next` 分支。
  3. 实现“待执行分支队列”机制：异步线程结束时，将 `completed` 或 `interrupted` 分支 ID 压入队列，主循环在下一次轮询时弹出执行。

### 任务 5.2：修订版监视器模型实现

* **操作步骤**：
  1. 实现 `_handle_monitor_node`：创建 `trigger_event = threading.Event()`，启动后台轮询线程 `_monitor_poll_loop`。
  2. **（严格遵守修订版）**在 `_monitor_poll_loop` 中执行耗时的截图/OCR，若检测到目标则 `trigger_event.set()`。
  3. **主线程等待**：使用 `while not trigger_event.is_set(): trigger_event.wait(timeout=0.005)` 保持轻量级死循环，确保能即时响应 `stop_event`（打断异步任务）。

### 任务 5.3：修饰键安全释放协议

* **操作步骤**：
  1. 在 `input_primitives.py` 中实现 `release_all_modifiers()` 兜底函数。
  2. 在 `automation_engine.py` 的 `execute_graph` 的 `finally` 块中调用兜底释放。
  3. 在异步任务被打断（捕获到 `stop_event`）的瞬间，立即调用释放函数。
* **交付物**：更新后的核心引擎文件

### 任务 5.4：前端异步状态指示

* **操作步骤**：
  1. 监听后端 `onTaskStatus` 事件。
  2. 当状态为 `running` 时，在 `call_script_async` 节点右上角渲染一个 CSS 旋转动画图标。
  3. 实现工具栏“暂停/继续”按钮对 `pause_automation` API 的正确调用。
* **交付物**：更新后的 `automation-events.js`, `automation_editor.html`

---

## 阶段 6：交互工具与最终打磨

**执行目标**：完善开发者体验，集成坐标拾取工具。
**预估耗时**：2天

### 任务 6.1：坐标拾取工具链

* **操作步骤**：
  1. 后端实现 `pick_coordinate(mode)` 和 `pick_region(mode)` API：使用 `pynput.mouse.Listener` 阻塞监听，计算物理/逻辑坐标转换后返回。
  2. 创建 `webui/modules/automation-tools.js`：
     * 控制已有的 `#pick-overlay` 覆盖层显示/隐藏。
     * 实现单点拾取：监听 click，调用 API，回调填充输入框。
     * 实现区域框选：监听 mousedown/mousemove/mouseup，在 `#pick-canvas` 上绘制矩形，计算宽高后调用 API 填充 4 个输入框。

### 任务 6.2：Schema 驱动属性面板完善

* **操作步骤**：
  1. 重构 `automation-property.js` 的渲染引擎：实现一个通用的 `renderSchema(schema, value)` 函数。
  2. 支持 `type: "string"` + `format: "path"` 渲染为【输入框+浏览按钮】。
  3. 支持 `type: "array"` + `format: "region"` 渲染为【4个输入框+框选按钮】。
  4. 确保所有属性变更实时同步回 LiteGraph 节点的 `properties` 对象。
* **交付物**：`webui/modules/automation-tools.js`，最终版的 `automation-property.js`
