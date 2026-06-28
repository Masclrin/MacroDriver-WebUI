# 自动化脚本引擎 V5.1 — 系统架构设计与研发执行    修订内容

基于前期架构探讨与代码审查，本文档整合了“大脑与四肢分离”、“物理隔离”、“插件化注册制”、“输入原语抽离”等核心决策，形成V5.0的修订版本，对原先设计做出部分修改和补充，详情要参考原始设计！
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

## 第一部分：核心设计哲学与原则修订

### 1.1 V5 新增三大原则

1. **绝对物理隔离**：底层输入原语（WinAPI结构体、SendInput封装）必须抽离至独立模块。新旧引擎不得直接互相引用执行逻辑代码，仅共享原子级原语。
2. **注册驱动**：节点类型、检测引擎、长期服务（如视频录制）均采用注册制。前端UI完全由后端下发的 `params_schema` (JSON Schema) 驱动渲染，不再硬编码。
3. **分层精度控制**：路径1（新引擎直发）不启用时序误差补偿器（无PI/前馈），但提供 `ExecutionProfile` 档案，允许用户按需开启 Interception 和线程增强。

### 1.2 监视器执行模型修正（关键修订）

放弃“主循环轮询”方案，采用**内部独立轮询线程 + 主线程轻量等待**模型：

- 耗时操作（截图、OCR）在独立子线程中执行，不卡死主线程。
- 主线程在监视器节点处执行 `Event.wait(timeout=0.005)` 轻量死循环，保持对异步任务的毫秒级打断响应能力。

### 1.3 旧编辑器复用策略（最终定论）

现有的 `editor.js` 与全局状态和DOM强耦合，**禁止直接在节点图模态框中复用**。

- **提取**：将 `normalizeAction`、`buildActionFromInputs` 等纯数据逻辑抽取至 `shared/macro-utils.js`。
- **重写**：为节点图开发极简版内嵌编辑器 `automation-block-editor.js`（局部状态、动态DOM、砍掉拖拽和内联编辑）。

---

## 第二部分：整体架构与目录结构

### 2.1 模块依赖边界图

```text
[PyWebView 前端]
   │
   ├── automation-core.js (LiteGraph实例)
   ├── automation-nodes.js (由 API 动态生成，不再硬编码)
   ├── automation-block-editor.js (极简版，依赖 macro-utils.js)
   └── macro-utils.js (纯逻辑，无DOM依赖)
   │
   ▼ JS Bridge
[Python 后端桥接层] (webui_app.py -> AutomationApiMixin)
   │
   ├── automation_engine.py (新引擎大脑，仅依赖下方原子层)
   ├── automation_compiler.py (JSON解析)
   ├── plugin_registry.py (节点与引擎注册中心)
   │
   ├───[路径1调用]──► input_primitives.py (WinAPI/Interception统一封装)
   │                   └── precision_engine_v5.py (精确等待)
   │
   └───[路径2调用]──► 宏执行框架3.2.py (旧引擎，仅导入 input_primitives 的基础结构)
                       └── precision_engine_v5.py
```

### 2.2 最终目录基准

```text
项目根目录/
├── 宏执行框架3.2.py                 # [重构] 移除底层定义，改为 import
├── precision_engine_v5.py           # [不修改]
├── webui_app.py                     # [微调] 初始化时扫描插件
│
├── webui_backend/
│   ├── input_primitives.py          # [新增] 底层输入原语(结构体/SendInput)
│   ├── plugin_registry.py           # [新增] 插件/节点/引擎注册表
│   ├── automation_engine.py         # [新增] 新引擎调度器
│   ├── automation_compiler.py       # [新增] 图解析器
│   ├── automation_bridge_api.py     # [新增] JS Bridge API
│   ├── coordinate_resolver.py       # [新增] 坐标转换
│   ├── detection/                   # [新增] 感知模块
│   │   ├── __init__.py
│   │   ├── capture.py
│   │   ├── color.py
│   │   └── ocr.py                   # [含可配置缓存策略]
│   └── services/                    # [新增] 长期服务层(P2)
│       └── video_recorder.py
│
├── webui/
│   ├── automation_editor.html       # [重写] 三栏布局+Canvas
│   └── modules/
│       ├── shared/
│       │   └── macro-utils.js       # [新增] 从editor.js剥离的纯逻辑
│       ├── automation-core.js       # [新增] LiteGraph初始化
│       ├── automation-nodes.js      # [新增] 动态节点类工厂
│       ├── automation-property.js   # [新增] Schema驱动属性面板
│       ├── automation-tools.js      # [新增] 坐标拾取器
│       ├── automation-events.js     # [新增] 后端回调监听
│       └── automation-block-editor.js # [新增] 极简版块编辑器
│
└── plugins/                         # [新增] 插件目录(默认全量扫描)
    ├── email_sender/
    │   └── __init__.py              # 必须包含 register(registry) 函数
    └── ...
```

---

## 第三部分：对旧引擎的改造协议（阶段0详细规范）

### 3.1 底层原语抽离（必须首先执行）

创建 `webui_backend/input_primitives.py`，从 `宏执行框架3.2.py` 中**搬迁**以下内容：

- 所有 WinAPI 结构体（`MOUSEINPUT`, `KEYBDINPUT`, `INPUT_STR` 等约50行）。
- `VK_MAP` 字典与 `get_vk` 函数。
- 基础发送函数：`send_key_sendinput`、`send_click_sendinput`、`send_move_sendinput`、`set_cursor_pos`。
  **旧引擎改造**：
  在 `宏执行框架3.2.py` 顶部删除被搬迁的代码，替换为：

```python
from webui_backend.input_primitives import (
    INPUT_MOUSE, INPUT_KEYBOARD, KEYEVENTF_KEYUP, MOUSEEVENTF_MOVE,
    MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP,
    send_key_sendinput, send_click_sendinput, send_move_sendinput, set_cursor_pos,
    get_vk, VK_MAP
)
# 旧引擎内部重命名以兼容现有代码
send_key_event = send_key_sendinput 
send_mouse_click = send_click_sendinput
send_mouse_move = send_move_sendinput
```

### 3.2 `execute_macro_once` 的完整 Options 化

除文档原有的6个变量外，**必须追加**以下全局变量的 Options 化改造（在函数开头解析）：

```python
def execute_macro_once(compiled_macro, stop_event, pause_event=None, macro_name="未知宏", options=None):
    _opt = options if options else {}
    # --- 必须覆盖的变量清单 ---
    local_speed = _opt.get("speed_factor", EXEC_SPEED_FACTOR)
    local_timeline = str(_opt.get("timeline_mode", TIMELINE_EXECUTION_MODE)).lower()
    local_random_delay = _opt.get("random_delay", ENABLE_RANDOM_DELAY_ADJUST)
    local_runtime_offset = _opt.get("runtime_random_offset", ENABLE_RUNTIME_RANDOM_OFFSET)
    local_offset_min = _opt.get("offset_min_ms", RUNTIME_RANDOM_OFFSET_MIN_MS)
    local_offset_max = _opt.get("offset_max_ms", RUNTIME_RANDOM_OFFSET_MAX_MS)
    local_lag_comp = _opt.get("lag_compensation", LAG_COMPENSATION_ENABLED)
    local_lag_pi = _opt.get("lag_use_pi", LAG_USE_PI_CONTROLLER)
    local_lag_ff = _opt.get("lag_use_ff", LAG_USE_FEEDFORWARD)
    # --- V5 新增覆盖清单 ---
    local_test_trace = _opt.get("test_trace", ENABLE_TEST_TRACE)       # 控制追踪报告生成
    local_low_cpu = _opt.get("low_cpu", ENABLE_LOW_CPU_EXECUTION)      # 控制睡眠策略
    local_batch_send = _opt.get("batch_send", ENABLE_BATCH_SEND)       # 影响编译(需传给batch函数)
    local_max_exec_time = _opt.get("max_exec_time", MAX_MACRO_EXEC_TIME) # 超时控制
  
    # 后续代码中，将所有引用上述全局变量的地方，替换为 local_ 前缀的局部变量
```

### 3.3 新增指令与修饰键释放

按照 V5 设计文档规范，在 `_parse` 中增加 `move_to`、`scroll`，在 `md/mu` 中增加 `middle` 中键分支。
`finally` 块增加 `auto_release_modifiers` 开关（默认True，新引擎调用时传False）。
------------------------------------------------

## 第四部分：双轨执行与精度配置模型

### 4.1 路径1：新引擎直发与 ExecutionProfile

路径1绝对不启用时序误差补偿（无PI/前馈），但引入精度档案：

```python
# input_primitives.py 中新增
class InterceptionSession:
    """新引擎专用的 Interception 会话（独立安全机制）"""
    def __init__(self, use_keyboard=False, use_mouse=False):
        self.use_keyboard = use_keyboard
        self.use_mouse = use_mouse
        self._kb_fail_count = 0
        self._kb_disabled_until = 0.0
        self._init_interception()
    
    def send_key(self, vk, up=False):
        if not self.use_keyboard or self._is_kb_cooled_down(): 
            return send_key_sendinput(vk, up)
        # 调用 interception，失败时 self._kb_fail_count += 1 (5次冷却10秒)
```

```python
# automation_engine.py
PROFILE_PRESETS = {
    "lite":      {"interception_kb": False, "interception_mouse": False, "boost_priority": False, "affinity": False},
    "standard":  {"interception_kb": False, "interception_mouse": False, "boost_priority": True,  "affinity": False},
    "precision": {"interception_kb": True,  "interception_mouse": True,  "boost_priority": True,  "affinity": True},
}
```

### 4.2 路径2：旧引擎托管

完全保持旧引擎的原有精度能力。新引擎调用时强制传入：

```python
opts = {
    "speed_factor": 1.0, "timeline_mode": "absolute",
    "test_trace": False, "batch_send": True, # 充分利用旧引擎能力
    "auto_release_modifiers": False # 释放权交给新引擎
}
```

---

## 第五部分：监视器与并发模型（V5修订）

### 5.1 监视器内部轮询线程实现

```python
def _handle_monitor_node(node, ctx):
    trigger_event = threading.Event()
    poll_thread = threading.Thread(
        target=_monitor_poll_loop, 
        args=(node, ctx, trigger_event), 
        daemon=True
    )
    poll_thread.start()
  
    # 主线程轻量等待，保持5ms级别的打断响应能力
    while not trigger_event.is_set() and not ctx.stop_event.is_set():
        trigger_event.wait(timeout=0.005)
def _monitor_poll_loop(node, ctx, trigger_event):
    """子线程：处理耗时的截图与OCR操作"""
    while not trigger_event.is_set() and not ctx.stop_event.is_set():
        now = time.perf_counter()
        if now - node.last_check < node.interval: 
            time.sleep(0.001)
            continue
        node.last_check = now
    
        # 耗时操作在子线程执行，不卡死主线程
        result = execute_detection(node, ctx) 
        if result["found"]:
            trigger_event.set() # 唤醒主线程
            break
```

---

## 第六部分：插件系统与注册机制

### 6.1 统一注册表 (`plugin_registry.py`)

```python
class PluginRegistry:
    _node_types = {}      # "action/mouse_click" -> NodeDefinition
    _detect_engines = {}  # "rapidocr" -> DetectEngineDefinition
  
    @classmethod
    def register_node(cls, def_dict):
        """def_dict 必须包含: type, category, display_name, color, inputs, outputs, params_schema(JSON Schema), handler"""
        cls._node_types[def_dict["type"]] = def_dict
    
    @classmethod
    def register_detect_engine(cls, def_dict):
        """def_dict 必须包含: id, name, params_schema, detect_func"""
        cls._detect_engines[def_dict["id"]] = def_dict
    @classmethod
    def get_frontend_payload(cls):
        """序列化给前端的完整节点与引擎定义"""
        return {
            "nodes": {k: {kk: vv for kk, vv in v.items() if kk != "handler"} for k, v in cls._node_types.items()},
            "engines": [{k: v for k, v in val.items() if k != "detect_func"} for val in cls._detect_engines.values()]
        }
```

### 6.2 插件发现与加载 (在 `webui_app.py` 启动时)

```python
import importlib, os
def load_plugins():
    plugin_dir = "plugins"
    if not os.path.exists(plugin_dir): return
    for folder in os.listdir(plugin_dir):
        init_path = os.path.join(plugin_dir, folder, "__init__.py")
        if os.path.exists(init_path):
            try:
                mod = importlib.import_module(f"plugins.{folder}")
                if hasattr(mod, 'register'):
                    mod.register(PluginRegistry)
                    print(f"[插件] 加载成功: {folder}")
            except Exception as e:
                print(f"[插件] 加载失败: {folder} -> {e}")
```

### 6.3 检测缓存策略开放化

在 `check_ocr` 等检测节点的 `params_schema` 中统一定义：

```json
{
  "cache_strategy": {"type": "string", "enum": ["frame_diff", "time_interval", "disabled"], "default": "time_interval"},
  "cache_interval_ms": {"type": "number", "default": 100, "description": "time_interval模式的间隔"}
}
```

后端根据策略走不同分支：`frame_diff`用np.max判断，`time_interval`用时间戳，`disabled`必检。
------------------------------------------------------

## 第七部分：前端 UI 与块编辑器策略

### 7.1 节点动态生成（Schema驱动）

前端 `automation-nodes.js` 不再硬编码任何节点类，改为通用工厂：

```javascript
function createNodeClass(def) {
    return function() {
        def.inputs.forEach(p => this.addInput(p.name, p.type));
        def.outputs.forEach(p => this.addOutput(p.name, p.type));
        this.properties = generateDefaultsFromSchema(def.params_schema);
        this.color = def.color;
        this.title = def.display_name;
    };
}
async function initNodes() {
    const payload = await pywebview.api.get_node_definitions();
    for (const [type, def] of Object.entries(payload.nodes)) {
        LiteGraph.registerNodeType(type, createNodeClass(def));
    }
    renderToolbox(payload.nodes); // 动态渲染左侧工具箱
}
```

### 7.2 极简版内嵌块编辑器 (`automation-block-editor.js`)

**规范**：

- **状态隔离**：维护局部的 `let localRows = []`，绝不触碰 `state.editorRows`。
- **DOM隔离**：在模态框内通过 `document.createElement` 动态生成所有UI，不依赖外部HTML的ID。
- **逻辑复用**：`import { normalizeAction, buildActionFromInputs } from './shared/macro-utils.js'`。
- **功能阉割**：无内联编辑、无拖拽排序（提供“上移/下移”按钮）、无宏文件浏览器（直接编辑动作列表）。
- **输出**：点击“保存到节点”时，将 `localRows` 序列化赋值给节点的 `params.actions`。

### 7.3 macro-utils.js 剥离清单

从 `editor.js` 中提取以下纯函数（移除对 `state` 和 `q` 的依赖）：

- `parseNumber`
- `cloneAction`
- `normalizeAction`
- `isLoopAction`
- `buildActionFromInputs` (需改造，不再从DOM读取，改为接收参数对象 `{type, arg1, arg2}`)
- `formatActionLabel`

---

## 第八部分：端到端研发执行清单（V5 详细版）

### 阶段 0：底层抽离与旧引擎极小侵入改造（预估 2 天）

**目标**：实现物理隔离基础，完成旧引擎 Options 全量覆盖。

- **任务 0.1**：创建 `webui_backend/input_primitives.py`。
  - 搬迁 WinAPI 结构体、`VK_MAP`、基础发送函数。
  - 新增 `InterceptionSession` 类（实现独立的安全回退机制）。
- **任务 0.2**：改造 `宏执行框架3.2.py`。
  - 删除被搬迁代码，改为 `from webui_backend.input_primitives import ...`。
  - 重写 `execute_macro_once` 头部，将**所有**列出的全局变量替换为 `_opt.get()` 模式。
  - `_parse` 函数增加 `move_to`、`scroll`、中键逻辑。
  - `finally` 增加 `auto_release_modifiers` 判断。
- **验收标准**：运行现有所有 `MACRO_BINDINGS` 宏，行为与改造前100%一致；传入 `options={"speed_factor": 2.0, "test_trace": False}` 验证隔离性。

### 阶段 1：新引擎骨架与路径1直发（预估 4 天）

**目标**：最小可用的画布与执行闭环。

- **任务 1.1**：重构 `automation_editor.html`（三栏布局、Canvas、拾取覆盖层）。
- **任务 1.2**：创建 `webui/modules/shared/macro-utils.js`，从 `editor.js` 剥离纯逻辑。
- **任务 1.3**：创建 `webui/modules/automation-core.js`。初始化 LiteGraph，监听 drop 事件。
- **任务 1.4**：创建 `webui/modules/automation-nodes.js`。实现 `createNodeClass` 工厂和 `initNodes`。
- **任务 1.5**：创建 `webui_backend/plugin_registry.py`。实现 `PluginRegistry` 类。
- **任务 1.6**：创建 `webui_backend/automation_compiler.py`。实现 JSON 到 `ExecGraph` 的解析。
- **任务 1.7**：创建 `webui_backend/automation_engine.py`。
  - 实现 `ExecutionProfile` 档案与 `InterceptionSession` 的初始化。
  - 实现路径1执行器：仅支持 `mouse_click`、`key_action`、`wait`。
  - 调用 `input_primitives.py` 和 `precision_engine_v5.py` 执行。
- **任务 1.8**：创建 `webui_backend/automation_bridge_api.py`。实现 `run_automation`、`stop_automation` API。`webui_app.py` 继承 Mixin。
- **验收标准**：前端拖拽【按键A】→【等待2秒】→【按键B】→【循环5次】，点击运行，后端按路径1正确执行，支持切换 `lite/standard` 档案。

### 阶段 2：路径2同步调用与坐标系统（预估 3 天）

**目标**：打通旧引擎调用与三种坐标模式。

- **任务 2.1**：创建 `webui_backend/coordinate_resolver.py`。实现 `screen/window/relative` 模式与 DPI 转换。
- **任务 2.2**：后端实现 `call_script_sync` 处理器。调用旧引擎 `compile_macro` + `execute_macro_once`，传入规范化 `options`。
- **任务 2.3**：实现超短动作优化（编译闭包 ≤ 2 时直接在路径1上下文执行）。
- **任务 2.4**：创建 `webui/modules/automation-block-editor.js`。实现极简模态框编辑器，复用 `macro-utils.js`。
- **任务 2.5**：前端实现坐标模式联动 UI（切换 mode 时，输入框 step 在 1 和 0.01 间切换）。
- **验收标准**：`call_script_sync` 加载旧 JSON 正确执行；window 模式下拖动窗口后坐标仍准确；双击节点可打开极简编辑器修改 actions。

### 阶段 3：检测能力接入（预估 4 天）

**目标**：实现感知模块与条件分支。

- **任务 3.1**：创建 `detection/capture.py`（mss封装）与 `detection/color.py`（numpy检测）。
- **任务 3.2**：创建 `detection/ocr.py`。封装 RapidOCR，实现可配置缓存策略（`frame_diff`/`time_interval`/`disabled`分支）。
- **任务 3.3**：后端实现 `check_color`、`check_ocr` 处理器，将结果写入 `ctx.check_results`。
- **任务 3.4**：后端实现 `if_else` 处理器。收集 data 端口连接的布尔值，按 logic 组合。
- **任务 3.5**：前端实现 data 端口连线（红色布尔线）。
- **任务 3.6**：前端 `automation-property.js` 实现基础 Schema 驱动渲染（支持 enum 联动）。
- **任务 3.7**：实现 `preview_color`、`preview_ocr` API 与属性面板预览按钮。
- **验收标准**：`check_color` → `if_else` → 不同分支完整跑通；OCR 检测游戏血量，设置 `cache_strategy: "disabled"`，数值微变能正确触发。

### 阶段 4：循环与变量系统（预估 3 天）

**目标**：实现循环动态刷新与变量流转。

- **任务 4.1**：后端实现 `loop_count`。每轮迭代开始时重新计算 `resolve_coords`（动态刷新验证）。
- **任务 4.2**：后端实现变量系统（`ExecContext.variables`、`${var}` 解析器）。
- **任务 4.3**：后端实现 `var_set`、`var_math`、`var_compare`、`var_string` 处理器。
- **任务 4.4**：前端属性面板支持 `${var}` 语法高亮提示。
- **验收标准**：loop 内 mouse_click(window模式) → 运行中拖动窗口 → 坐标自动跟随；check_ocr提取数字存变量 → 比较 → 分支。

### 阶段 5：并发调度与异步打断（预估 4 天，核心难点）

**目标**：实现后台任务与监视器打断。

- **任务 5.1**：后端实现 `TaskPool`（启动、停止、暂停、恢复）。
- **任务 5.2**：后端实现 `call_script_async` 处理器与"待执行分支队列"。
- **任务 5.3**：**核心修订**：实现监视器内部轮询线程模型（`_monitor_poll_loop` + `Event.wait`）。
- **任务 5.4**：后端实现修饰键兜底释放协议（所有退出路径必须调用 `release_all_modifiers`）。
- **任务 5.5**：前端实现异步节点状态指示（小动画）、暂停/继续按钮逻辑。
- **验收标准**：`call_script_async`(连招) → `monitor_ocr`(检测血量<30) → 触发后打断异步任务 → 走 trigger 分支(吃药) → 键盘无卡键残留。

### 阶段 6：插件化重构与工具集成（预估 3 天）

**目标**：将内置节点改为注册制，接入工具。

- **任务 6.1**：将阶段1-5硬编码的节点定义，全部改为符合 `PluginRegistry` 规范的字典，在 `webui_app.py` 启动时批量注册。
- **任务 6.2**：前端 `automation-nodes.js` 彻底改为纯动态生成，删除所有硬编码的 `registerNodeType`。
- **任务 6.3**：实现 `pick_coordinate`、`pick_region` API 与前端拾取器覆盖层交互。
- **任务 6.4**：实现 `get_node_definitions` API，返回完整的 Schema 给前端。
- **验收标准**：隐藏一个内置节点（如不注册 `mouse_scroll`），前端工具箱自动不显示该节点，且不影响其他节点执行。

### 阶段 7：服务层与高级扩展（P2，按需）

**目标**：支持脱离节点图生命周期的长期任务。

- **任务 7.1**：创建 `webui_backend/services/` 目录与 `ServiceManager`。
- **任务 7.2**：实现插件注册检测引擎能力。前端 `check_ocr` 下拉框动态加载已注册引擎。
- **任务 7.3**：开发示例插件：`plugins/video_recorder/`（基于环形缓冲区保存最后N分钟）。
- **任务 7.4**：开发示例插件：`plugins/email_sender/`。

---

## 附录 A：`input_primitives.py` 核心骨架示例

```python
# webui_backend/input_primitives.py
import ctypes
user32 = ctypes.windll.user32
# --- WinAPI 结构体定义 (从旧引擎搬迁) ---
class MOUSEINPUT(ctypes.Structure): _fields_ = [...]
class KEYBDINPUT(ctypes.Structure): _fields_ = [...]
# ... 省略其他结构体 ...
# --- 纯 SendInput 封装 ---
def send_key_sendinput(vk_code, up=False): ...
def send_click_sendinput(left=True, up=False): ...
def send_move_sendinput(x, y): ...
def set_cursor_pos(x, y): ...
# --- VK 映射 ---
VK_MAP = { "left": 0x01, ... }
def get_vk(key): return VK_MAP.get(str(key).lower(), 0)
# --- 新引擎专属：Interception 会话 ---
class InterceptionSession:
    def __init__(self, use_keyboard=False, use_mouse=False):
        self.use_keyboard = use_keyboard
        self.use_mouse = use_mouse
        self._available = False
        self._kb_fail_count = 0
        self._kb_disabled_until = 0.0
        if use_keyboard or use_mouse:
            self._init_interception()
      
    def _init_interception(self):
        try:
            from interception_input_v2 import get_interception_context, send_key_interception, send_mouse_interception
            get_interception_context()
            self._send_key = send_key_interception
            self._send_mouse = send_mouse_interception
            self._available = True
        except Exception:
            self._available = False
      
    def send_key(self, vk, up=False):
        if not self.use_keyboard or not self._available or self._is_kb_cooled_down():
            return send_key_sendinput(vk, up)
        # 实现独立的安全回退逻辑 (失败5次冷却10秒)
        ...
  
    def send_click(self, left=True, up=False):
        if not self.use_mouse or not self._available:
            return send_click_sendinput(left, up)
        ...
```
