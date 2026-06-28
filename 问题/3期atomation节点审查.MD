## 1. 项目根目录结构

```
g:\宏引擎\宏驱动 webui 2.7.7/
├── .vscode/
├── Interception/          # 键盘拦截驱动
├── __pycache__/
├── automation/            # 自动化核心（后端Python）
│   ├── detection/         # 检测模块（截图、颜色、OCR）
│   ├── handlers/          # 节点处理器（action, control, detection, flow, monitor, preset, utility, variable）
│   ├── nodes/             # 节点定义（同上分类）
│   └── tests/
├── bin/                   # 安装脚本和依赖
├── bridge/                # 前后端桥接API
├── core/                  # 核心服务
├── docs/                  # 文档
├── engine/                # 输入引擎（Interception/SendInput）
├── macro_io/              # 宏文件读写
├── plugins/               # 插件（email, notify, record, screenshot）
├── recorder/              # 宏录制
├── webui/                 # 前端代码
│   ├── modules/
│   │   ├── auto/          # 自动化编辑器模块
│   │   ├── core/          # 核心工具库
│   │   └── editor/        # 宏编辑器模块
│   ├── app.js
│   ├── automation_editor.html
│   ├── index.html
│   └── styles.css
├── 宏/                    # 宏文件存储
├── 自动化脚本/            # 自动化脚本存储
├── 问题/                  # Bug和审查文档
├── 存档内容/              # 历史存档
├── webui_app.py           # WebUI主入口
├── 宏执行框架3.2.py       # 宏执行引擎
└── ...
```
---

## 2. TOOLBOX_CATEGORIES 完整分类列表

定义在 [editor-app.js:181-191](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L181-L191)：

| 序号 | id | name (中文名) | color | icon |
|------|-----|--------------|-------|------|
| 1 | `flow` | 流程 | `#ffffffff` | `fa-solid fa-route` |
| 2 | `action` | 动作节点 | `#22c55e` | `fa-solid fa-bolt` |
| 3 | `detection` | 检测节点 | `#eab308` | `fa-solid fa-magnifying-glass` |
| 4 | `control` | 控制节点 | `#a855f7` | `fa-solid fa-code-branch` |
| 5 | `script_block` | 动作块 | `#3b82f6` | `fa-solid fa-cubes` |
| 6 | `monitor` | 监视器 | `#06b6d4` | `fa-solid fa-eye` |
| 7 | `variable` | 变量 | `#f97316` | `fa-solid fa-database` |
| 8 | `preset` | 预设 | `#f472b6` | `fa-solid fa-wand-magic-sparkles` |
| 9 | `utility` | 工具 | `#d8d8d8ff` | `fa-solid fa-screwdriver-wrench` |

另外，在 [nodes.js](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js) 中还有一个动态分类 `plugin`（插件），由插件系统动态注册，不在 `TOOLBOX_CATEGORIES` 静态数组中。

---

## 3. 分类定义的文件路径和行号

分类定义存在于**两个位置**，分别负责不同层面的分类：

### (A) 前端工具箱渲染定义 -- `TOOLBOX_CATEGORIES`

- **文件**: [editor-app.js](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js)
- **行号**: 第 181-191 行
- **作用**: 定义左侧工具箱面板的分类显示顺序、名称、颜色和图标，用于 `renderToolbox()` 函数渲染 DOM 到 `#toolbox-categories` 容器

```javascript
var TOOLBOX_CATEGORIES = [
  { id: 'flow', name: '流程', color: '#ffffffff', icon: 'fa-solid fa-route' },
  { id: 'action', name: '动作节点', color: '#22c55e', icon: 'fa-solid fa-bolt' },
  { id: 'detection', name: '检测节点', color: '#eab308', icon: 'fa-solid fa-magnifying-glass' },
  { id: 'control', name: '控制节点', color: '#a855f7', icon: 'fa-solid fa-code-branch' },
  { id: 'script_block', name: '动作块', color: '#3b82f6', icon: 'fa-solid fa-cubes' },
  { id: 'monitor', name: '监视器', color: '#06b6d4', icon: 'fa-solid fa-eye' },
  { id: 'variable', name: '变量', color: '#f97316', icon: 'fa-solid fa-database' },
  { id: 'preset', name: '预设', color: '#f472b6', icon: 'fa-solid fa-wand-magic-sparkles' },
  { id: 'utility', name: '工具', color: '#d8d8d8ff', icon: 'fa-solid fa-screwdriver-wrench' },
];
```

### (B) 节点分类注册定义 -- `_categories`

- **文件**: [nodes.js](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js)
- **行号**: 第 72 行（`_categories: {}` 初始化），第 97-98 行和第 679-680 行（分类名称和颜色映射）
- **作用**: 定义节点实际归属的分类，每个节点通过 `category` 属性关联到对应分类

分类名称映射（第 97 行和第 679 行，两处一致）：
```javascript
var catNames = { action:'动作节点', detection:'检测节点', control:'控制节点', 
  script_block:'动作块', monitor:'监视器', variable:'变量', preset:'预设', 
  utility:'工具', flow:'流程', plugin:'插件' };
```

分类颜色映射（第 98 行和第 680 行）：
```javascript
var catColors = { action:'#22c55e', detection:'#eab308', control:'#a855f7', 
  script_block:'#3b82f6', monitor:'#06b6d4', variable:'#f97316', preset:'#f472b6', 
  utility:'#adadadff', flow:'#ff0000ff', plugin:'#a855f7' };
```

### (C) 右键菜单分类顺序

- **文件**: [editor-app.js](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js)
- **行号**: 第 1352 行
- **作用**: 右键菜单"添加节点"子菜单的分类显示顺序

```javascript
var catOrder = ['flow', 'action', 'detection', 'control', 'monitor', 'variable', 'preset', 'utility', 'script_block'];
```

---

### 总结

`toolbox-categories` 的分类定义核心在 **[editor-app.js 第 181-191 行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L181-L191)** 的 `TOOLBOX_CATEGORIES` 数组，共 9 个分类（flow、action、detection、control、script_block、monitor、variable、preset、utility）。节点层面的分类注册在 **[nodes.js](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js)** 中，额外包含 `plugin` 分类用于动态加载的插件节点。两处定义的颜色值有细微差异（如 utility 的颜色在 editor-app.js 中为 `#d8d8d8ff`，在 nodes.js 中为 `#adadadff`；flow 的颜色在 editor-app.js 中为 `#ffffffff`，在 nodes.js 中为 `#ff0000ff`）。
        
---

## 模块1: flow（流程）Bug报告

### 🟡 FLOW-1: `flow` 分类颜色在三处定义不一致

- **editor-app.js** [第182行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L182): `{ id: 'flow', name: '流程', color: '#ffffffff' }` — 白色
- **nodes.js catColors** [第680行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L680): `flow:'#ff0000ff'` — 红色
- **后端 flow/start** [第6行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/flow.py#L6): `color: "#99ff00ff"` — 绿色
- **影响**: 用户在工具箱面板看到的流程分类标题是白色（在浅色背景上几乎不可见），而节点在画布上显示为红色/绿色，视觉不一致
- **修复建议**: 统一三处颜色定义，建议使用与节点实际颜色一致的颜色

### 🟡 FLOW-2: `flow/start` 和 `flow/end` 缺少拼音搜索映射

- **nodes.js** [第18-64行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L18-64): `_pinyinMap` 中没有 `flow/start` 和 `flow/end` 的条目
- **影响**: 用户在工具箱搜索栏输入拼音（如 "kaishi"）无法搜索到"开始"节点
- **修复建议**: 添加 `'flow/start': 'kaishi start', 'flow/end': 'jieshu end'` 到 `_pinyinMap`

---

## 模块2: action（动作节点）Bug报告

### 🔴 ACTION-1: `action/key_action` 的 "press" 语义与 `action/mouse_click` 的 "press" 不一致

- **后端 action.py** [第137-139行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py#L137-L139): key_action 的 "press" 执行 key_down + key_up（完整点击）
- **后端 action.py** [第78行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py#L78): mouse_click 的 "press" 只执行 key_down（按住不放）
- **影响**: 用户在鼠标点击节点学会了"press=按下不放"，到按键节点却发现"press=按下并释放"，操作结果与预期完全不同。例如用户想按住Shift再点击，用key_action的press以为只是按下，结果按下后立刻释放了
- **修复建议**: 将 key_action 的选项改为 `["click", "press", "release", "type"]`，其中 "click"=按下+释放，"press"=仅按下，"release"=仅释放，与鼠标节点保持一致

### 🟡 ACTION-2: `_pinyinMap` 中存在大量过时条目且缺少新节点条目

- **nodes.js** [第18-64行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L18-64):
  - 过时条目：`'action/screenshot'`（后端不存在）、`'action/program_launch'`（应为 `program_open`）、`'action/bookmark'`（不存在于action分类）、`'action/move_window'`（应为 `window_manage`）、`'action/scroll'`（应为 `mouse_scroll`）
  - 缺失条目：`'action/mouse_move'`、`'action/mouse_move_rel'`
- **影响**: 用户搜索"鼠标移动"或"相对位移"的拼音时找不到对应节点；过时条目不会导致错误但浪费维护成本
- **修复建议**: 清理过时条目，添加缺失条目

### 🟡 ACTION-3: `action/mouse_scroll` 没有坐标模式，只能在当前鼠标位置滚动

- **后端 action.py** [第152-166行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py#L152-L166): 直接调用 `send_scroll_sendinput`，无坐标参数
- **后端 nodes/action.py** [第47-51行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/action.py#L47-L51): params_schema 中无 mode/x/y/hwnd_var 参数
- **影响**: 用户想先移动鼠标到指定位置再滚动滚轮，需要额外添加一个鼠标移动节点。而鼠标点击节点有坐标模式，滚轮节点却没有，功能不对等
- **修复建议**: 为 mouse_scroll 添加坐标模式参数（mode/x/y/hwnd_var），与 mouse_click 保持一致

### 🟡 ACTION-4: `action/program_open` 的 `store_hwnd_var` 可能找不到窗口句柄

- **后端 action.py** [第412-423行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py#L412-L423): 重试10次，每次0.2秒，共2秒
- **后端 action.py** [第431-446行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py#L431-L446): `_find_process_main_hwnd` 只查找可见且有标题的窗口
- **影响**: 某些程序启动后窗口需要超过2秒才出现，或窗口初始不可见/无标题，导致 `store_hwnd_var` 为空。用户不知道句柄获取失败，后续使用该变量的节点会静默失败
- **修复建议**: 增加重试次数或让重试时间可配置；当句柄获取失败时通过日志明确告知用户

### 💡 ACTION-5: `action/mouse_move_rel` 没有缓动函数参数

- **后端 nodes/action.py** [第167-172行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/action.py#L167-L172): params_schema 中无 easing 参数
- **后端 action.py** [第552行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py#L552): 硬编码 `"ease_in_out"`
- **影响**: mouse_move 有缓动函数选项，但 mouse_move_rel 没有，功能不对等
- **修复建议**: 为 mouse_move_rel 添加 easing 参数

---


## 模块3: detection（检测节点）Bug报告

### 🔴🔴 DETECT-1: 多个检测节点的 `target_color`/`template_path`/`region` 参数声明了 `varRef` 但处理器未解析变量引用

- **后端 detection.py** [第34行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/detection.py#L34): `target_color` 有 `varRef: True`
- **后端 handlers/detection.py** [第78行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L78): `target_hex = params.get("target_color", "#FF0000")` — 未调用 `_resolve_value()`
- **后端 detection.py** [第97行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/detection.py#L97): `template_path` 有 `varRef: True`
- **后端 handlers/detection.py** [第298行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L298): `template_path = params.get("template_path", "")` — 未调用 `_resolve_value()`
- **后端 handlers/detection.py** [第39行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L39): `region_param = params.get("region", [0, 0, 0, 0])` — capture_source 的 region 未解析
- **后端 handlers/detection.py** [第74行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L74): `rect = params.get("rect", [0, 0, 10, 10])` — check_color 的 rect 未解析
- **影响**: 用户在属性面板看到变量选择器按钮，输入 `${my_color}` 或 `${my_template}` 后，变量引用不会被解析，导致颜色检测永远失败（`_parse_target_color` 无法解析变量字符串）、图像匹配找不到模板文件、截图源区域无效
- **修复建议**: 对 `target_color`、`template_path` 使用 `_resolve_value()` 解析；对 `rect`/`region` 数组参数，需要支持数组内元素级别的变量解析

### 🔴 DETECT-2: `check_ocr` 的 `cache_interval_ms` 声明了 `varRef` 但处理器未解析

- **后端 detection.py** [第70行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/detection.py#L70): `cache_interval_ms` 有 `varRef: True`
- **后端 handlers/detection.py** [第181行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L181): `cache_interval_ms=int(params.get("cache_interval_ms", 100))` — 未调用 `_resolve_value()`
- **影响**: 用户输入变量引用作为缓存间隔，但实际使用的是原始字符串，`int()` 转换会抛出异常导致节点静默失败
- **修复建议**: 改为 `int(_resolve_value(params.get("cache_interval_ms", 100), ctx))`

### 🟡 DETECT-3: `detection/capture_source` 缺少拼音搜索映射

- **nodes.js** [第18-64行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L18-64): `_pinyinMap` 中没有 `detection/capture_source` 条目
- **影响**: 用户在工具箱搜索"截图源"的拼音时找不到该节点
- **修复建议**: 添加 `'detection/capture_source': 'jietu jieping yuan capture'`

### 🟡 DETECT-4: 后端检测节点输出端口类型 `data_bool` 与前端 `boolean` 不一致

- **后端 detection.py** [第27行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/detection.py#L27): `{"name": "result", "type": "data_bool"}`
- **前端 nodes.js** [第346行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L346): `{name:'result',type:'boolean'}`
- **影响**: 如果编译器对数据端口类型做严格匹配，`data_bool` 和 `boolean` 可能被视为不同类型，导致连线时类型不匹配。需要确认编译器是否做了类型归一化
- **修复建议**: 统一使用 `boolean` 或在编译器中添加类型别名映射

### 🟡 DETECT-5: `check_ocr` 有隐式变量存储行为，用户不可见

- **后端 handlers/detection.py** [第189-194行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L189-L194): 当 `store_var` 为空且 `match_text` 为空时，自动将 OCR 结果存入 `{node_id}_ocr_text` 和 `{node_id}_ocr_number`
- **影响**: 用户不知道这些隐式变量被创建了，可能在变量选择器中看到不认识的变量名；且变量名包含节点ID（数字），不直观
- **修复建议**: 要么在节点定义中明确说明此行为，要么移除隐式存储，要求用户显式指定 `store_var`

### 💡 DETECT-6: `check_image` 的 `rect == [0,0,0,0]` 判断全屏的逻辑不健壮

- **后端 handlers/detection.py** [第305行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L305): `if rect == [0, 0, 0, 0]:` 使用精确列表比较
- **影响**: 如果 `rect` 是元组 `(0,0,0,0)` 或包含浮点数 `[0.0,0.0,0.0,0.0]`，比较会失败，导致本应全屏搜索却使用了错误的区域
- **修复建议**: 使用更健壮的判断，如 `all(v == 0 for v in rect)` 或将值统一转为 int 后比较

---

继续检查 control 模块。

          
## 模块4: control（控制节点）Bug报告

### 🔴🔴 CTRL-1: `control/join` 前端缺少 `branch_required_3` 到 `branch_required_8` 参数

- **后端 control.py** [第178-185行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/control.py#L178-L185): 定义了 `branch_required_1` 到 `branch_required_8`，带 `showWhen` 条件
- **前端 nodes.js** [第558-559行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L558-L559): 仅有 `branch_required_1` 和 `branch_required_2`
- **影响**: 当用户设置 `branch_count >= 3` 且 `wait_mode=custom` 时，无法配置分支3-8是否必须到达。`custom` 模式对多分支完全失效
- **修复建议**: 在前端添加 `branch_required_3` 到 `branch_required_8`，带 `showWhen:'branch_count>=3'` 等条件

### 🔴 CTRL-2: `control/goto` 的 `target_node_id` 声明了 `varRef` 但处理器未解析

- **后端 control.py** [第87行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/control.py#L87): `target_node_id` 有 `varRef: True`
- **后端 handlers/control.py** [第216行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L216): `target_id = node.params.get("target_node_id", "")` — 未调用 `_resolve_value()`
- **影响**: 用户输入 `${target_node}` 作为跳转目标，但变量不会被解析，跳转永远失败
- **修复建议**: 改为 `target_id = str(_resolve_value(node.params.get("target_node_id", ""), ctx))`

### 🔴 CTRL-3: `control/state_machine` 的 `states` 和 `fail_state` 声明了 `varRef` 但处理器未解析

- **后端 control.py** [第124-125行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/control.py#L124-L125): `states` 和 `fail_state` 有 `varRef: True`
- **后端 handlers/control.py** [第246-247行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L246-L247): 直接使用 `params.get()` 获取，未调用 `_resolve_value()`
- **影响**: 用户无法通过变量动态控制状态机流程
- **修复建议**: 对 `states` 和 `fail_state` 使用 `_resolve_value()` 解析

### 🟡 CTRL-4: 前端控制节点 `cond` 输入端口类型不一致 — `boolean` vs `data_bool`

- **前端 nodes.js** [第374行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L374): `if_else` 的 cond 使用 `type:'boolean'`
- **前端 nodes.js** [第521行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L521): `seq_check` 的 cond 使用 `type:'data_bool'`
- **前端 nodes.js** [第526行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L526): `state_machine` 的 cond 使用 `type:'data_bool'`
- **影响**: 同样是接收布尔条件的端口，有的用 `boolean` 有的用 `data_bool`，连线时可能出现类型不匹配
- **修复建议**: 统一所有条件输入端口为同一类型

### 🟡 CTRL-5: `control/join` 前端 `branch_count` 缺少 `min`/`max` 约束

- **后端 control.py** [第176行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/control.py#L176): `branch_count` 有 `min: 2, max: 8`
- **前端 nodes.js** [第556行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L556): `branch_count` 无 `min`/`max` 约束
- **影响**: 用户可以在前端输入 1 或 99 等无效值，后端可能无法正确处理
- **修复建议**: 添加 `min:2, max:8` 约束

### 🟡 CTRL-6: `control/loop_count` 计数器从 0 开始，用户可能期望从 1 开始

- **后端 handlers/control.py** [第73行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L73): `ctx.safe_set_variable(_extract_var_name(counter_var), i)` — `i` 从 0 开始
- **影响**: 用户设置"循环3次"并使用计数器变量，期望第1次循环计数器为1，但实际为0。这在编程中常见但非技术用户可能困惑
- **修复建议**: 改为 `i + 1`，或在节点描述中明确说明计数器从0开始

### 🟡 CTRL-7: `_pinyinMap` 中 `control/loop` 应为 `control/loop_count`，且缺少 `wait_cond` 和 `goto`

- **nodes.js** [第34行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L34): `'control/loop'` — 过时键名
- **影响**: 搜索"计数循环"的拼音可能匹配不到正确节点；`wait_cond` 和 `goto` 无法通过拼音搜索
- **修复建议**: 修正为 `'control/loop_count'`，添加 `'control/wait_cond'` 和 `'control/goto'`

---

          
## 模块5+6: script_block + monitor Bug报告

### 🔴 MONITOR-1: 监视器节点的 `target_color`/`rect`/`target_task` 声明了 `varRef` 但处理器未解析

- **后端 monitor.py** [第16行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/monitor.py#L16): `target_color` 有 `varRef: True`
- **后端 handlers/monitor.py** [第28-31行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L28-L31): 直接用字符串索引解析颜色，未调用 `_resolve_value()`，变量引用会导致崩溃
- **后端 handlers/monitor.py** [第23行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L23): `rect = params.get("rect", ...)` — 未解析变量引用
- **后端 handlers/monitor.py** [第102行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L102): `target_task = node.params.get("target_task", "")` — 未解析变量引用
- **影响**: 与 DETECT-1 同类问题。用户输入变量引用后，颜色监视器会因字符串索引越界崩溃（`target_hex[1:3]` 对 `${var}` 无效），target_task 变量引用不生效
- **修复建议**: 使用 `_resolve_value()` 解析 `target_color`，并使用 `_parse_target_color()` 函数（与 detection 模块一致）安全解析颜色值

### 🔴 MONITOR-2: `monitor_color` 和 `check_color` 的 `sample_mode` 选项不一致

- **后端 nodes/monitor.py** [第19行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/monitor.py#L19): `["center", "average", "corner"]`
- **后端 nodes/detection.py** [第37行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/detection.py#L37): `["center", "mean", "max_diff"]`
- **影响**: 用户在颜色检测节点学会了 "mean" 和 "max_diff" 采样模式，到颜色监视器却发现只有 "average" 和 "corner"，功能不对等且命名不一致（mean vs average）
- **修复建议**: 统一两个节点的 sample_mode 选项

### 🟡 MONITOR-3: `monitor_time` 的 `auto_stop` 参数在处理器中未使用

- **后端 nodes/monitor.py** [第109行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/monitor.py#L109): 定义了 `auto_stop` 参数
- **后端 handlers/monitor.py** [第218行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L218): 读取了 `auto_stop` 但从未使用
- **影响**: 用户设置 `auto_stop=false` 期望时间监视器每天重复触发，但实际只触发一次就停止。参数形同虚设
- **修复建议**: 要么实现 `auto_stop=false` 时的循环触发逻辑（如每天重复触发），要么移除该参数

### 🟡 MONITOR-4: `_pinyinMap` 中 `monitor/monitor_image` 不存在且缺少 `monitor/monitor_time`

- **nodes.js** [第47行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L47): `'monitor/monitor_image'` — 后端不存在此节点
- **影响**: 搜索"时间监视"的拼音找不到该节点
- **修复建议**: 移除 `monitor/monitor_image`，添加 `'monitor/monitor_time'`

### 💡 MONITOR-5: 监视器颜色解析方式与检测节点不一致

- **后端 handlers/monitor.py** [第28-31行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L28-L31): 直接用字符串索引 `target_hex[1:3]` 解析
- **后端 handlers/detection.py** [第18-27行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L18-L27): 使用正则 `_parse_target_color()` 安全解析
- **影响**: 监视器的颜色解析更脆弱，非标准格式（如 `#fff`、空字符串）会导致崩溃而非优雅降级
- **修复建议**: 统一使用 `_parse_target_color()` 函数

---

## 模块7: variable（变量）Bug报告

### 🔴 VAR-1: `variable/var_math` 的 `round` 操作隐藏了 `b` 参数，导致无法指定小数位数

- **后端 nodes/variable.py** [第16行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/variable.py#L16): `b` 的 `showWhen` 不包含 `op=round`
- **后端 handlers/variable.py** [第90行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L90): `"round": lambda: round(a, int(b))` — 使用 `b` 作为小数位数
- **影响**: 用户选择"四舍五入"操作后，`b` 字段被隐藏，无法指定保留几位小数。实际效果永远是 `round(a, 0)` 即取整，用户无法得到如 `round(3.14159, 2) = 3.14` 的结果
- **修复建议**: 在 `b` 的 `showWhen` 中添加 `op=round`，或为 `round` 操作添加专用的 `decimal_places` 参数

### 🟡 VAR-2: `variable/var_set` 和 `variable/var_convert` 缺少拼音搜索映射

- **nodes.js** [第18-64行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L18-64): `_pinyinMap` 中缺少 `variable/var_set` 和 `variable/var_convert`
- **影响**: 搜索"设置变量"或"类型转换"的拼音找不到对应节点
- **修复建议**: 添加对应条目

### 🟡 VAR-3: `_pinyinMap` 中存在过时的 variable 节点条目

- **nodes.js** [第40-42行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L40-L42): `'variable/logic_op'`、`'variable/const_number'`、`'variable/const_string'` — 这些节点实际属于 `utility` 分类
- **影响**: 搜索拼音时可能匹配到错误分类的节点
- **修复建议**: 移除这些过时条目（它们对应的节点在 utility 分类下已有正确条目）

---

## 模块8: preset（预设）Bug报告

### 🔴 PRESET-1: `preset_find_click` 的 `template_path` 和 `rect` 声明了 `varRef` 但处理器未解析

- **后端 preset.py** [第36行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/preset.py#L36): `template_path` 有 `varRef: True`
- **后端 handlers/preset.py** [第43行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/preset.py#L43): `template_path = params.get("template_path", "")` — 未调用 `_resolve_value()`
- **后端 handlers/preset.py** [第41行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/preset.py#L41): `rect = params.get("rect", [0, 0, 0, 0])` — 未解析变量引用
- **影响**: 与 DETECT-1 同类问题。用户使用变量引用指定模板路径或搜索区域时，功能完全失效
- **修复建议**: 使用 `_resolve_value()` 解析 `template_path`；对 `rect` 添加变量解析支持

### 🔴 PRESET-2: `preset_read_text` 异常时未调用 `_execute_flow`，导致流程中断

- **后端 handlers/preset.py** [第127-130行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/preset.py#L127-L130): 异常处理中只设置了 `check_results` 和 `log_error`，但没有调用 `_execute_flow()`
- **影响**: 当 OCR 识别失败（如截图区域无效、引擎初始化失败）时，流程在此节点中断，后续节点全部不执行。用户只看到流程停止，不知道原因
- **修复建议**: 在异常处理中添加 `_execute_flow(node.id, "next", ctx)`，确保流程继续

### 🟡 PRESET-3: `preset_click` 和 `preset_find_click` 的 `button` 选项缺少 `middle`

- **后端 preset.py** [第16行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/preset.py#L16): `enum: ["left", "right"]`
- **后端 nodes/action.py** [第14行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/action.py#L14): `enum: ["left", "right", "middle"]`
- **影响**: 用户在动作节点可以使用中键点击，但预设节点不支持，功能不对等
- **修复建议**: 在预设节点的 `button` 选项中添加 `"middle"`

### 🟡 PRESET-4: `preset_find_click` 的 `rect == [0,0,0,0]` 判断不健壮

- **后端 handlers/preset.py** [第49行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/preset.py#L49): `if rect == [0, 0, 0, 0]:` 使用精确列表比较
- **影响**: 与 DETECT-6 同类问题。元组或浮点数格式会导致比较失败
- **修复建议**: 使用更健壮的判断方式

---

## 模块9: utility（工具）Bug报告

### 🔴 UTIL-1: `utility/logic_op` 的 `bool()` 转换对字符串变量引用不安全

- **后端 handlers/utility.py** [第87行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L87): `a = bool(a_val if a_val is not None else _resolve_value(node.params.get("a", True), ctx))`
- **影响**: 当变量引用解析为字符串 `"false"` 时，`bool("false")` 返回 `True`（Python 中非空字符串为真），导致逻辑运算结果完全错误。例如用户变量值为 "false"，期望逻辑非得 True，实际得 False
- **修复建议**: 使用安全的布尔转换，如 `str(val).lower() not in ("", "0", "false", "no", "off", "none", "null")`（与 `var_set` 的处理方式一致）

### 🟡 UTIL-2: `utility/math_op` 的 `b` 参数缺少 `showWhen` 条件

- **后端 nodes/utility.py** [第51行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/utility.py#L51): `b` 参数无 `showWhen`
- **对比 variable/var_math**: `b` 有 `showWhen: "op=+,op=-,op=*,op=/,op=%,op=min,op=max"`
- **影响**: 对于 `pow` 等需要 B 参数的操作，`b` 始终显示是正确的。但对于 `abs` 等不需要 B 的操作（虽然 math_op 没有 abs），`b` 也始终显示，可能造成困惑。与 var_math 的设计不一致
- **修复建议**: 根据操作类型添加适当的 `showWhen` 条件

### 🟡 UTIL-3: `utility/string_op` 缺少 `regex_extract` 操作，但 `variable/var_string` 有

- **后端 nodes/utility.py** [第108行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/utility.py#L108): `op` 选项不包含 `regex_extract`
- **后端 nodes/variable.py** [第31行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/variable.py#L31): `op` 选项包含 `regex_extract`
- **影响**: 两个功能相似的字符串操作节点，utility 版本功能更少，用户可能不知道 variable 版本有正则提取功能
- **修复建议**: 为 `utility/string_op` 添加 `regex_extract` 操作

### 🟡 UTIL-4: 多个 utility 节点缺少拼音搜索映射

- **nodes.js** `_pinyinMap` 缺少: `utility/const_bool`、`utility/math_op`、`utility/math_func`、`utility/compare`、`utility/string_op`、`utility/condition`、`utility/delay`
- **影响**: 搜索"布尔常量"、"数学运算"、"数学函数"、"数值比较"、"字符串操作"、"条件选择"、"延迟"的拼音时找不到对应节点
- **修复建议**: 添加对应的拼音映射条目

### 💡 UTIL-5: `utility/bookmark` 的 `name` 和 `remark` 参数没有实际功能

- **后端 nodes/utility.py** [第162行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/utility.py#L162): `name` 和 `remark` 参数仅作为描述性字段
- **后端 handlers/utility.py** [第186-215行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L186-L215): 处理器中完全未使用 `name` 和 `remark`
- **影响**: 用户填写书签名称和备注后，这些信息在执行时没有任何作用，仅作为画布上的标注
- **修复建议**: 如果仅为标注用途，可保留；如果期望通过名称引用书签，需实现查找逻辑

---
---

## Bug 1: core.js `_checkShowWhen` 中 falsy 值处理错误

**文件路径**: [core.js](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L160)

**行号范围**: 第 160 行

**问题描述**: `_checkShowWhen` 函数中使用 `rawVal || ''` 来处理当前值，当 `rawVal` 为数字 `0` 时，`0 || ''` 的结果是 `''`（空字符串），而非正确的 `"0"`。这导致 showWhen 条件如 `some_field=0` 永远无法匹配成功。

对比 [property.js 第 422 行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L422) 使用了正确的 `rawVal ?? ''`（空值合并运算符），`0 ?? ''` 结果是 `0`。

```javascript
// core.js 第 160 行 - 有Bug
currentVal = String(rawVal || '');   // 0 变成 ""

// property.js 第 422 行 - 正确
currentVal = String(rawVal ?? '');   // 0 变成 "0"
```

**用户影响**: 
- 当节点参数值为 `0` 且该参数有 `showWhen` 条件时，依赖该参数的其他字段无法正确显示/隐藏
- `_pickSummaryKeys` 调用了此函数，导致值为 0 的条件字段无法正确出现在节点的内联参数中

**修复建议**: 将 `rawVal || ''` 改为 `rawVal ?? ''`，与 property.js 保持一致：
```javascript
currentVal = String(rawVal ?? '');
```

---

## Bug 2: editor-app.js `TOOLBOX_CATEGORIES` 与 nodes.js `catColors` 颜色不一致

**文件路径**: 
- [editor-app.js 第 182-191 行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L182-L191)
- [nodes.js 第 98 行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L98)

**行号范围**: editor-app.js 第 182、190 行；nodes.js 第 98 行

**问题描述**: `TOOLBOX_CATEGORIES` 中 `flow` 和 `utility` 分类的颜色与 `nodes.js` 中 `catColors` 定义不一致：

| 分类 | TOOLBOX_CATEGORIES | nodes.js catColors |
|------|-------------------|-------------------|
| flow | `#ffffffff` (透明白) | `#ff0000ff` (红) |
| utility | `#d8d8d8ff` (浅灰) | `#adadadff` (深灰) |

```javascript
// editor-app.js 第 182 行
{ id: 'flow', name: '流程', color: '#ffffffff', ... }    // 白色
// editor-app.js 第 190 行
{ id: 'utility', name: '工具', color: '#d8d8d8ff', ... }  // 浅灰

// nodes.js 第 98 行
var catColors = { ..., flow:'#ff0000ff', utility:'#adadadff', ... };  // 红色、深灰
```

**用户影响**: 
- 工具箱侧栏中分类标题旁的色块颜色与节点定义中实际使用的分类颜色不一致
- 右键菜单"添加节点"子菜单中分类颜色（来自 `catColors`）与工具箱分类颜色（来自 `TOOLBOX_CATEGORIES`）不一致
- `flow` 分类在工具箱显示为白色（在深色背景上几乎不可见），而节点定义中为红色

**修复建议**: 统一颜色定义，建议将 `TOOLBOX_CATEGORIES` 中的颜色与 `nodes.js` 的 `catColors` 对齐：
```javascript
{ id: 'flow', name: '流程', color: '#ff0000ff', ... }
{ id: 'utility', name: '工具', color: '#adadadff', ... }
```

---

## Bug 3: editor-app.js `undoManager._restore` 使用不存在的 API

**文件路径**: [editor-app.js 第 222 行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L222)

**行号范围**: 第 222 行

**问题描述**: `undoManager._restore` 中使用了 `AutomationCore.lgCanvas.graph.getNode(selectedId)`，但 `lgCanvas`（即 `_canvasAPI`）没有 `graph` 属性，会导致 TypeError。

```javascript
// 第 222 行 - Bug
var restoredNode = AutomationCore.lgCanvas.graph.getNode(selectedId);
// lgCanvas 没有 graph 属性，调用会抛出 TypeError

// 正确的 API 应该是：
var restoredNode = AutomationCore.lgGraphObj.getNodeById(selectedId);
```

**用户影响**: 
- 当用户执行撤销/重做操作时，如果之前有选中的节点，此行代码会抛出 TypeError
- 虽然 try-catch 会捕获异常（图数据仍能恢复），但属性面板不会正确更新到选中节点的属性
- 控制台会输出 `[UndoManager] restore error:` 错误日志

**修复建议**: 将 `AutomationCore.lgCanvas.graph.getNode(selectedId)` 改为 `AutomationCore.lgGraphObj.getNodeById(selectedId)`

---

## Bug 4: property.js `_openKeySelector` 使用不存在的 API

**文件路径**: [property.js 第 879 行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L879)

**行号范围**: 第 879 行

**问题描述**: 按键选择器中使用了 `AutomationCore.lgCanvas.graph.getNode(nodeId)`，与 Bug 3 相同，`lgCanvas` 没有 `graph` 属性。

```javascript
// 第 879 行 - Bug
var node = AutomationCore.lgCanvas.graph.getNode(nodeId);

// 正确的 API 应该是：
var node = AutomationCore.lgGraphObj.getNodeById(nodeId);
```

**用户影响**: 
- 当用户在属性面板中使用按键选择器选择按键时，虽然按键名能被捕获，但无法正确写回到节点属性
- 会抛出 TypeError，导致按键选择功能完全失效

**修复建议**: 将 `AutomationCore.lgCanvas.graph.getNode(nodeId)` 改为 `AutomationCore.lgGraphObj.getNodeById(nodeId)`

---

## Bug 5: editor-app.js 多选复制丢失 `customName`

**文件路径**: [editor-app.js 第 2356-2364 行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L2356-L2364)

**行号范围**: 第 2356-2364 行

**问题描述**: 使用 Ctrl+C 复制多个选中节点时，剪贴板数据没有包含 `customName` 字段，而右键菜单复制单个节点时（第 1431-1437 行）包含了 `customName`。粘贴时（第 1454-1457 行）会检查 `item.customName`，但多选复制的数据中该字段不存在。

```javascript
// 第 2356-2364 行 - 多选复制，缺少 customName
_clipboard.push({
    nodeType: selNodes[i]._defKey,
    params: JSON.parse(JSON.stringify(selNodes[i].properties || {})),
    pos: { x: selNodes[i].pos[0], y: selNodes[i].pos[1] }
    // 缺少: customName: selNodes[i]._customName || null
});

// 对比第 1431-1437 行 - 单节点复制，包含 customName
_clipboard = [{
    nodeType: contextTarget._defKey,
    params: JSON.parse(JSON.stringify(contextTarget.properties || {})),
    pos: { x: contextTarget.pos[0], y: contextTarget.pos[1] },
    customName: contextTarget._customName || null  // 有这个字段
}];
```

**用户影响**: 
- 用户通过 Ctrl+C 复制多个已重命名的节点后粘贴，所有自定义名称会丢失
- 节点恢复为默认显示名称，破坏用户的工作流

**修复建议**: 在多选复制的剪贴板数据中添加 `customName`：
```javascript
_clipboard.push({
    nodeType: selNodes[i]._defKey,
    params: JSON.parse(JSON.stringify(selNodes[i].properties || {})),
    pos: { x: selNodes[i].pos[0], y: selNodes[i].pos[1] },
    customName: selNodes[i]._customName || null
});
```

---

## Bug 6: property.js `_checkShowWhenChanges` 中 `this._container` 从未赋值

**文件路径**: [property.js 第 1560 行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L1560)

**行号范围**: 第 1551-1570 行

**问题描述**: `_checkShowWhenChanges` 方法通过 `this._container` 查找当前显示的字段元素，但 `AutomationProperty` 对象从未设置 `_container` 属性。这导致 `fieldEl` 始终为 `null`，`wasVisible` 始终为 `false`。

```javascript
// 第 1560 行
var fieldEl = this._container ? this._container.querySelector(...) : null;
// this._container 始终为 undefined，所以 fieldEl 始终为 null

// 第 1562 行
var wasVisible = fieldWrap ? (fieldWrap.style.display !== 'none') : false;
// wasVisible 始终为 false
```

**逻辑影响分析**:
- 当 showWhen 条件从 false 变为 true（字段应显示）：`showNow=true, wasVisible=false` -> `needRender=true` -- 正确
- 当 showWhen 条件从 true 变为 false（字段应隐藏）：`showNow=false, wasVisible=false` -> `needRender=false` -- **Bug！字段不会隐藏**

**用户影响**: 
- 当用户在属性面板中修改某个字段值，导致另一个字段的 showWhen 条件从满足变为不满足时，该字段不会隐藏
- 隐藏的字段仍然可见且可编辑，用户可能修改不应显示的参数，导致运行时行为异常
- 注意：对于 `mode`、`capture_mode` 等特殊字段（第 1299 行），会直接调用 `self.render(node)` 完整重渲染，不受此Bug影响

**修复建议**: 在 `render` 方法中设置 `this._container`：
```javascript
render: function(node) {
    this._currentNode = node;
    var container = document.getElementById('property-panel-content');
    if (!container) return;
    this._container = container;  // 添加这行
    // ... 后续代码
}
```

---

## Bug 7: core.js 内联字段修改后不刷新节点 DOM（showWhen 不同步）

**文件路径**: [core.js 第 491-498 行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L491-L498)

**行号范围**: 第 491-533 行（所有内联字段的事件绑定）

**问题描述**: 当用户在节点上直接修改内联字段（如 select 下拉框、checkbox 等）时，事件处理器只更新了 `node.properties` 和属性面板，但没有调用 `_refreshNodeDOM(node)` 来刷新节点 DOM。如果修改的字段影响其他字段的 showWhen 条件，节点上的内联参数不会更新。

```javascript
// 第 491-498 行 - select 的 change 事件
f.addEventListener('change', function() {
    var n = _nodes[nid];
    if (!n) return;
    n.properties[key] = f.value;
    if (window.AutomationProperty && AutomationProperty._currentNode === n) {
        AutomationProperty.render(n);  // 只刷新了属性面板
    }
    // 缺少: _refreshNodeDOM(n); 来刷新节点上的内联字段
});
```

**用户影响**: 
- 用户在节点上直接切换 `mode` 等字段后，节点上依赖 showWhen 的内联参数不会更新显示/隐藏
- 例如：节点上切换 mode 从 "screen" 到 "window" 后，hwnd_var 字段应出现但不会出现
- 属性面板是正确同步的（因为 `AutomationProperty.render(n)` 被调用了），但节点上的内联视图是过时的

**修复建议**: 在内联字段的关键 change 事件中，对影响 showWhen 的字段调用 `_refreshNodeDOM`：
```javascript
f.addEventListener('change', function() {
    var n = _nodes[nid];
    if (!n) return;
    n.properties[key] = f.value;
    _refreshNodeDOM(n);  // 刷新节点DOM以同步showWhen
    _renderAllConnections();
    if (window.AutomationProperty && AutomationProperty._currentNode === n) {
        AutomationProperty.render(n);
    }
});
```

---

## 总结

| # | 文件 | 严重程度 | 简述 |
|---|------|---------|------|
| 1 | core.js:160 | 高 | `_checkShowWhen` 中 `rawVal \|\| ''` 将数字 0 转为空字符串，导致 showWhen 条件 `=0` 永远不匹配 |
| 2 | editor-app.js:182,190 | 中 | `TOOLBOX_CATEGORIES` 与 `nodes.js catColors` 的 flow/utility 颜色不一致 |
| 3 | editor-app.js:222 | 高 | `undoManager._restore` 调用不存在的 `lgCanvas.graph.getNode`，导致撤销后属性面板不更新 |
| 4 | property.js:879 | 高 | `_openKeySelector` 调用不存在的 `lgCanvas.graph.getNode`，导致按键选择器完全失效 |
| 5 | editor-app.js:2356 | 中 | Ctrl+C 多选复制丢失 `customName`，粘贴后自定义名称消失 |
| 6 | property.js:1560 | 中 | `_checkShowWhenChanges` 中 `this._container` 从未赋值，导致字段无法正确隐藏 |
| 7 | core.js:491 | 中 | 内联字段修改后不刷新节点 DOM，showWhen 条件变化时节点上参数不同步 |
        

          
以上就是对三个核心文件的完整 Bug 审查结果，共发现 7 个确认的 Bug，其中 3 个为高严重度（会导致功能失效或运行时错误），4 个为中严重度（导致 UI 不一致或状态不同步）。所有 Bug 均附有具体的文件路径、行号、问题描述、用户影响和修复建议。
        
          
搜索代理返回结果不够详细，让我直接读取核心文件进行检查。
        

          
## 模块10: 画布与核心功能 Bug报告

### 🔴🔴 CANVAS-1: `_checkShowWhen` 不支持 `>=` 比较运算符，导致 fork/join/race 节点的分支3-8配置字段始终隐藏

- **core.js** [第130-169行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L130-L169): `_checkShowWhen` 解析 `branch_count>=3` 时，`indexOf('=')` 找到 `>` 后面的 `=`，导致字段名被解析为 `branch_count>` 而非 `branch_count`
- **property.js** [第392-431行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L392-L431): 同样的 `_checkShowWhen` 实现，同样的 bug
- **property.js** [第326行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L326): `showWhen` 检查在 `_branchIndex` 检查之前执行，导致即使 `_branchIndex` 机制正确，字段也被 `showWhen` 的错误结果跳过
- **影响**: 用户在 fork/join/race 节点增加分支数量到3以上时，属性面板中分支3-8的名称、绑核、必须到达等配置字段**全部不可见**。用户无法自定义高级分支配置，多分支并发功能严重受损
- **修复建议**: 修改 `_checkShowWhen` 支持 `>=` 运算符。解析时先检查 `>=`，再检查 `=`：
  ```javascript
  var gteIdx = seg.indexOf('>=');
  var eqIdx = seg.indexOf('=');
  if (gteIdx > 0) {
      currentField = seg.substring(0, gteIdx).trim();
      currentValues = ['>=' + seg.substring(gteIdx + 2).trim()];
  } else if (eqIdx > 0) {
      currentField = seg.substring(0, eqIdx).trim();
      currentValues = [seg.substring(eqIdx + 1).trim()];
  }
  ```
  并在值比较时处理 `>=` 前缀

### 🟡 CANVAS-2: `utility` 分类颜色在 TOOLBOX_CATEGORIES 和 nodes.js 之间不一致

- **editor-app.js** [第189行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L189): `utility` 颜色为 `#d8d8d8ff`
- **nodes.js** [第680行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L680): `utility` 颜色为 `#adadadff`
- **影响**: 工具箱面板的分类标题颜色与画布上节点的颜色不一致，视觉体验割裂
- **修复建议**: 统一两处颜色定义

### 🟡 CANVAS-3: 变量面板对 `store_var` 的类型推断不完整

- **editor-app.js** [第416-426行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L416-L426): 仅对部分节点类型做了 `store_var` 的类型推断
- **影响**: `var_string`、`var_convert` 等节点的 `store_var` 变量在变量面板中显示为"文本"类型，但实际可能是数字或布尔值。用户可能误用变量类型
- **修复建议**: 为更多节点类型添加类型推断，或在变量面板中标注"未知类型"

### 💡 CANVAS-4: 变量面板中"节点输出"使用 `${node_id.port_name}` 格式，但后端不直接支持此引用格式

- **editor-app.js** [第460行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L460): 显示 `${node_id.port_name}` 格式的变量引用
- **影响**: 用户复制此格式的变量引用后，在后端 `${...}` 解析中可能无法正确解析（需要确认 `_resolve_value` 是否支持 `node_id.port_name` 格式）
- **修复建议**: 确认后端是否支持此格式；如不支持，应在变量面板中标注此为数据端口引用而非变量引用

---


我发现了关键信息！引擎在调用处理器之前会自动解析所有 `varRef` 参数（engine.py 第697-705行）。这意味着之前我报告的很多"处理器未解析变量引用"的bug实际上不是bug——引擎已经解析了。但**数组类型参数**（如 `rect`/`region`）内的元素级变量引用仍然无法被解析。

让我输出修正后的编译器与引擎 Bug 报告。

## 模块11: 编译器与引擎 Bug报告

### 🔴🔴 ENGINE-1: 引擎的 `_resolve_value()` 不处理数组内元素的变量引用，导致 `rect`/`region` 参数的元素级变量引用失效

- **engine.py** [第347-349行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L347-L349): `_resolve_value()` 对非字符串值直接返回，不处理列表内的变量引用
- **engine.py** [第697-705行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L697-L705): 引擎对 `varRef` 参数调用 `_resolve_value()`，但数组类型参数 `[0, 0, "${width}", "${height}"]` 不会被解析
- **影响**: 用户在区域编辑器的 x/y/w/h 字段输入变量引用如 `${width}`，实际执行时变量不被替换，使用了原始字符串 `"${width}"` 而非变量值，导致坐标计算完全错误
- **修复建议**: 在 `_resolve_value()` 中添加数组类型处理：遍历数组元素，对字符串元素递归调用 `_resolve_value()`

### 🔴 ENGINE-2: 引擎异常处理不调用 `_execute_flow()`，导致处理器异常时流程中断

- **engine.py** [第712-721行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L712-L721): 异常处理只记录日志，不调用 `_execute_flow()` 继续流程
- **影响**: 当节点处理器抛出未预期的异常时（如类型错误、文件不存在），流程在此节点中断，后续所有节点不执行。用户只看到流程停止，不知道哪个节点出了问题
- **修复建议**: 在异常处理中添加 `_execute_flow(node.id, "next", ctx)` 或根据节点类型选择合适的输出端口

### 🟡 ENGINE-3: 编译器不验证变量引用 `${node_id.port}` 中 port 是否实际存在

- **compiler.py** [第185-188行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/compiler.py#L185-L188): 只验证 `node_id` 是否存在，不验证 `port` 是否是该节点的输出端口
- **影响**: 用户输入 `${node_5.nonexistent_port}` 时编译不报错，运行时变量解析返回 `None`，可能导致静默失败
- **修复建议**: 在编译时检查引用的端口是否在节点的 outputs 列表中

### 🟡 ENGINE-4: 编译器 `goto` 验证不检查目标节点是否在同一 fork/join 作用域内

- **compiler.py** [第137-144行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/compiler.py#L137-L144): 只验证目标节点存在且非 `flow/start`
- **影响**: 用户在 fork 分支内使用 goto 跳转到分支外部的节点，可能导致并发安全问题（跳出的节点在主线程执行，而分支线程仍在运行）
- **修复建议**: 添加作用域检查，警告或禁止跨 fork/join 作用域的 goto

### 💡 ENGINE-5: `execute_graph` 入口节点不存在时未通知前端

- **engine.py** [第831-833行](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L831-L833): 只打印错误到控制台，不设置 stop_event 或通知前端
- **影响**: 用户点击运行后，如果图没有入口节点，前端可能一直显示"运行中"状态
- **修复建议**: 设置 stop_event 并通过回调通知前端执行失败

---

**重要修正**：由于引擎在调用处理器前自动解析 `varRef` 参数，以下之前报告的 bug 需要降级或撤回：
- ~~DETECT-1~~: `target_color`、`template_path` 的变量引用已被引擎解析，**不是bug**。但 `rect`/`region` 数组内元素级变量引用仍无法解析，归入 ENGINE-1
- ~~DETECT-2~~: `cache_interval_ms` 已被引擎解析，**不是bug**
- ~~CTRL-2~~: `target_node_id` 已被引擎解析，**不是bug**
- ~~CTRL-3~~: `states` 和 `fail_state` 已被引擎解析，**不是bug**
- ~~MONITOR-1~~: `target_color`、`target_task` 已被引擎解析，**不是bug**。但 `rect` 数组内元素级变量引用仍无法解析，归入 ENGINE-1
- ~~PRESET-1~~: `template_path` 已被引擎解析，**不是bug**。但 `rect` 数组内元素级变量引用仍无法解析，归入 ENGINE-1

现在进行交叉验证。
        
          
现在我已经获取了 `_checkShowWhen` 函数的完整实现。下面是分析结果：

---

## `_checkShowWhen` 函数完整代码

文件：[property.js](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L392-L432)

```javascript
_checkShowWhen: function(showWhen, allParams) {
    if (!showWhen) return true;
    var segments = showWhen.split(',');
    var conditions = [];
    var currentField = null;
    var currentValues = [];
    for (var i = 0; i < segments.length; i++) {
        var seg = segments[i].trim();
        var eqIdx = seg.indexOf('=');
        if (eqIdx > 0) {
            if (currentField !== null) {
                conditions.push({field: currentField, values: currentValues});
            }
            currentField = seg.substring(0, eqIdx).trim();
            currentValues = [seg.substring(eqIdx + 1).trim()];
        } else if (currentField !== null) {
            currentValues.push(seg);
        }
    }
    if (currentField !== null) {
        conditions.push({field: currentField, values: currentValues});
    }
    if (conditions.length === 0) return true;
    for (var c = 0; c < conditions.length; c++) {
        var cond = conditions[c];
        var rawVal = allParams[cond.field];
        var currentVal;
        if (rawVal === true || rawVal === false) {
            currentVal = String(rawVal);
        } else {
            currentVal = String(rawVal ?? '');
        }
        for (var v = 0; v < cond.values.length; v++) {
            var val = cond.values[v];
            if (val === currentVal) return true;
            if (val === 'true' && rawVal === true) return true;
            if (val === 'false' && rawVal === false) return true;
        }
    }
    return false;
},
```

**行号：第 392 ~ 432 行**

---

## 分析结论：**不支持 `>=` 比较运算符**

该函数**仅支持 `=`（相等）运算符**，不支持 `>=`、`>`、`<=`、`<` 等比较运算符。原因如下：

1. **解析逻辑只查找 `=` 字符**：第 400 行 `var eqIdx = seg.indexOf('=');` 只查找字符串中第一个 `=` 的位置，将 `=` 左侧作为字段名、右侧作为期望值。

2. **`>=` 会被错误解析**：如果传入 `"branch_count>=3"`，`indexOf('=')` 会找到 `>` 后面的 `=`（位置为 13），于是：
   - `currentField` = `"branch_count>"`（包含了 `>` 符号）
   - `currentValues` = `["3"]`
   
   字段名变成了 `"branch_count>"`，而 `allParams` 中不存在这个键，所以 `rawVal` 为 `undefined`，`currentVal` 变成空字符串 `""`，与 `"3"` 不匹配，条件永远为 `false`。

3. **比较逻辑是纯字符串相等比较**：第 426 行 `if (val === currentVal) return true;` 只做严格的字符串相等判断，没有任何数值大小比较的逻辑。

---

## 如果需要支持 `>=` 运算符

需要修改 `_checkShowWhen` 函数，在解析时识别 `>=`、`>`、`<=`、`<`、`=` 等运算符，并在比较阶段对数值类型做大小比较而非仅做字符串相等判断。如果需要我实现这个功能，请告知。
        
          
找到了 `_resolve_value` 函数定义在 [engine.py:347](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L347)。现在读取该函数的完整代码：
        
            

## 分析结果

我已完整阅读了 [engine.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py) 文件，以下是 `_execute_node` 函数中异常处理逻辑的详细分析。

---

### `_execute_node` 中的 try/except 块（第 712-724 行）

```python
        try:
            handler(node, ctx)
        except (FileNotFoundError, ImportError, TypeError, ValueError) as e:
            error_msg = f"节点 {node.type}({current_id}) 系统错误: {e}"
            print(f"[新引擎] {error_msg}")
            ctx.log_error(error_msg, node_id=current_id, error_type="system")
        except Exception as e:
            error_msg = f"节点 {node.type}({current_id}) 执行异常: {e}"
            print(f"[新引擎] {error_msg}")
            ctx.log_error(error_msg, node_id=current_id, error_type="runtime")
        finally:
            if _original_params is not None:
                node.params = _original_params
```

**关键发现：`_execute_node` 中异常发生后，没有调用 `_execute_flow()` 继续执行后续节点。**

异常被捕获后，代码仅做了两件事：
1. 打印错误信息到控制台
2. 通过 `ctx.log_error()` 记录错误

之后，在第 726 行检查 `goto_target`，如果没有 goto 目标，则直接在第 738 行 `return`，整个执行流就此终止。**后续节点不会被执行。**

---

### 对比：`_handle_plugin_node` 中的异常处理（第 620-623 行）

```python
    except Exception as e:
        ctx.log_error(f"插件节点异常 {node.type}: {e}", node_id=str(node.id), error_type="plugin")
        _execute_flow(node.id, "fail" if _has_output_port(node, "fail") else "next", ctx)
        return
```

**插件节点的异常处理逻辑不同：它确实调用了 `_execute_flow()`**，会尝试走 "fail" 端口（如果没有 fail 端口则走 "next" 端口）继续执行后续节点。

---

### 总结

| 函数 | 异常后是否调用 `_execute_flow()` | 行号 |
|---|---|---|
| `_execute_node` | **否** - 异常后仅记录错误，直接 return，流程中断 | [L712-724](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L712-L724) |
| `_handle_plugin_node` | **是** - 异常后调用 `_execute_flow(node.id, "fail"/"next", ctx)` 继续执行 | [L620-623](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L620-L623) |

**这意味着：普通节点（通过 `NODE_HANDLERS` 分发的节点）一旦抛出异常，整个流程就会中断，后续节点不会执行；而插件节点抛出异常后，会尝试通过 "fail" 端口继续流转。** 如果需要在普通节点异常后也继续执行，需要在 `_execute_node` 的 except 块中添加对 `_execute_flow()` 的调用，类似 `_handle_plugin_node` 的处理方式。
        
          
---

## `_resolve_value` 函数完整代码

函数位于 [engine.py:347-435](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L347-L435)：

```python
def _resolve_value(value, ctx: ExecContext):
    if not isinstance(value, str):
        return value
    bookmark_pattern = re.compile(r'@([\w\u4e00-\u9fff]+)\.(x|y|w|h|mode|hwnd_var|remark|name)')
    bookmark_matches = bookmark_pattern.findall(value)
    if bookmark_matches:
        result = value
        for bm_name, bm_param in bookmark_matches:
            found = False
            for nid, node in ctx.graph.nodes.items():
                if node.type == "utility/bookmark" and node.params.get("name") == bm_name:
                    bm_val = node.params.get(bm_param, 0)
                    result = result.replace(f"@{bm_name}.{bm_param}", str(bm_val))
                    found = True
                    break
            if not found:
                print(f"[新引擎] 错误：坐标书签 '@{bm_name}' 未找到")
                result = result.replace(f"@{bm_name}.{bm_param}", "0")
        try:
            if '.' in result or result.replace('-', '').replace('.', '').isdigit():
                return float(result)
        except (ValueError, TypeError):
            pass
        return result
    pattern = re.compile(r'\$\{([^}]+)\}')
    matches = pattern.findall(value)
    if not matches:
        return value
    if len(matches) == 1 and value == f"${{{matches[0]}}}":
        var_name = matches[0]
        if var_name in _BUILTIN_VARIABLES:
            return _BUILTIN_VARIABLES[var_name]()
        var_val = ctx.safe_get_variable(var_name)
        if var_val is not None:
            return var_val
        if '.' in var_name:
            parts = var_name.split('.', 1)
            if len(parts) == 2:
                bm_first, bm_second = parts
                for nid, node in ctx.graph.nodes.items():
                    if node.type == "utility/bookmark" and node.params.get("name") == bm_first:
                        return node.params.get(bm_second, 0)
                cr_key = f"{bm_first}.{bm_second}"
                cr_val = ctx.check_results.get(cr_key)
                if cr_val is not None:
                    return cr_val
        if var_name in ctx.check_results:
            return ctx.check_results[var_name]
        print(f"[新引擎] 警告：变量 '{var_name}' 未定义")
        return value
    result = value
    for var_name in matches:
        if var_name in _BUILTIN_VARIABLES:
            builtin_val = _BUILTIN_VARIABLES[var_name]()
            result = result.replace(f"${{{var_name}}}", builtin_val)
            continue
        var_val = ctx.safe_get_variable(var_name)
        if var_val is not None:
            result = result.replace(f"${{{var_name}}}", str(var_val))
        elif '.' in var_name:
            parts = var_name.split('.', 1)
            if len(parts) == 2:
                bm_first, bm_second = parts
                bm_found = False
                for nid, node in ctx.graph.nodes.items():
                    if node.type == "utility/bookmark" and node.params.get("name") == bm_first:
                        bm_val = node.params.get(bm_second, 0)
                        result = result.replace(f"${{{var_name}}}", str(bm_val))
                        bm_found = True
                        break
                if not bm_found:
                    cr_key = f"{bm_first}.{bm_second}"
                    cr_val = ctx.check_results.get(cr_key)
                    if cr_val is not None:
                        result = result.replace(f"${{{var_name}}}", str(cr_val))
                    else:
                        print(f"[新引擎] 警告：引用 '{var_name}' 未定义")
                        result = result.replace(f"${{{var_name}}}", "0")
        elif var_name in ctx.check_results:
            result = result.replace(f"${{{var_name}}}", str(ctx.check_results[var_name]))
        else:
            print(f"[新引擎] 警告：变量 '{var_name}' 未定义")
            result = result.replace(f"${{{var_name}}}", "0")
    try:
        if '.' in result or result.replace('-', '').replace('.', '').isdigit():
            return float(result)
    except (ValueError, TypeError):
        pass
    return result
```

---

## 分析结论：**`_resolve_value` 不能处理数组类型参数中每个元素的变量引用解析**

关键原因在函数的第 **348-349 行**：

```python
if not isinstance(value, str):
    return value
```

当传入的 `value` 是一个 `list`（如 `["${x}","${y}","${w}","${h}"]`）时，`isinstance(value, str)` 为 `False`，函数会**直接原样返回该列表**，不会对其中的任何字符串元素进行 `${}` 变量解析。

### 具体场景分析

假设参数配置为：
```yaml
rect: ["${x}", "${y}", "${w}", "${h}"]
```

调用处（[engine.py:593](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L593) 和 [engine.py:704](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L704)）的代码是：
```python
params[key] = _resolve_value(params[key], ctx)
```

当 `params[key]` 是 `["${x}", "${y}", "${w}", "${h}"]` 时，`_resolve_value` 收到一个 `list`，立即在第 349 行 `return value`，数组中的 `"${x}"` 等变量引用**完全不会被解析**。

### 如果要支持数组内元素解析

需要在函数开头增加对 `list` 类型的递归处理，例如：

```python
def _resolve_value(value, ctx: ExecContext):
    if isinstance(value, list):
        return [_resolve_value(item, ctx) for item in value]
    if not isinstance(value, str):
        return value
    # ... 后续原有逻辑
```

同样地，如果还需要支持 `dict` 类型值中的变量引用，也需要类似的递归处理。当前实现**只处理字符串类型的值**，对嵌套结构（list/dict）中的变量引用完全无感知。
        
          
三个关键bug已验证。让我继续检查更多可能不在审查意见书中的bug。
        
            

## 分析结果

### 1. `_normalizeSchema` 函数位置

`_normalizeSchema` 函数并不在 `property.js` 中，而是在 [nodes.js](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js) 的第 **125 行**。

### 2. `_normalizeSchema` 对 `showWhen` 的处理

[nodes.js:142-144](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L142-L144)：

```javascript
if (s.showWhen && typeof s.showWhen === 'string') {
    s.showWhen = s.showWhen.replace(/=True/g, '=true').replace(/=False/g, '=false');
}
```

`_normalizeSchema` 对 `showWhen` 的处理**非常有限**，仅做了一件事：将 Python 后端传来的布尔值 `=True` / `=False` 替换为 JavaScript 的 `=true` / `=false`。它**没有**对 `>=`、`<=`、`>`、`<` 等比较运算符做任何处理或转换。

### 3. `_checkShowWhen` 函数 -- 前端实际解析 `showWhen` 的逻辑

[property.js:392-432](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L392-L432)：

```javascript
_checkShowWhen: function(showWhen, allParams) {
    if (!showWhen) return true;
    var segments = showWhen.split(',');
    var conditions = [];
    var currentField = null;
    var currentValues = [];
    for (var i = 0; i < segments.length; i++) {
        var seg = segments[i].trim();
        var eqIdx = seg.indexOf('=');
        if (eqIdx > 0) {
            if (currentField !== null) {
                conditions.push({field: currentField, values: currentValues});
            }
            currentField = seg.substring(0, eqIdx).trim();
            currentValues = [seg.substring(eqIdx + 1).trim()];
        } else if (currentField !== null) {
            currentValues.push(seg);
        }
    }
    if (currentField !== null) {
        conditions.push({field: currentField, values: currentValues});
    }
    if (conditions.length === 0) return true;
    for (var c = 0; c < conditions.length; c++) {
        var cond = conditions[c];
        var rawVal = allParams[cond.field];
        var currentVal;
        if (rawVal === true || rawVal === false) {
            currentVal = String(rawVal);
        } else {
            currentVal = String(rawVal ?? '');
        }
        for (var v = 0; v < cond.values.length; v++) {
            var val = cond.values[v];
            if (val === currentVal) return true;
            if (val === 'true' && rawVal === true) return true;
            if (val === 'false' && rawVal === false) return true;
        }
    }
    return false;
},
```

### 4. 关键问题：`>=` 比较条件**无法被正确解析**

这是一个**严重的 Bug**。当 `showWhen` 的值为 `"branch_count>=3"` 时，`_checkShowWhen` 的解析逻辑如下：

1. 用 `split(',')` 分割，得到 `["branch_count>=3"]`
2. 对每个段用 `seg.indexOf('=')` 查找等号位置
3. `"branch_count>=3"` 中 `=` 出现在位置 **13**（即 `>=` 中的 `=`）
4. `eqIdx = 13 > 0`，进入等号分支
5. `currentField = seg.substring(0, 13).trim()` → 得到 `"branch_count>"`（**包含了 `>` 符号！**）
6. `currentValues = [seg.substring(14).trim()]` → 得到 `["3"]`
7. 最终条件变成：检查 `allParams["branch_count>"]` 的值是否等于 `"3"`

而 `allParams` 中只有 `branch_count` 这个键，不存在 `branch_count>` 这个键，所以 `rawVal` 为 `undefined`，`currentVal` 为空字符串 `""`，与 `"3"` 不相等，条件永远为 `false`。

**结论：`showWhen: 'branch_count>=3'` 这种带 `>=` 比较运算符的条件，在当前 `_checkShowWhen` 实现中完全无法正确工作。**

### 5. 但为什么分支字段仍然能显示？

因为在 [property.js:333-336](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L333-L336) 中，还有一个**独立的 `_branchIndex` 机制**：

```javascript
if (schema._branchIndex !== undefined) {
    var bc = parseInt(node.properties.branch_count) || 2;
    if (schema._branchIndex > bc) continue;
}
```

在 `_expandDynamicBranches` 中（[nodes.js:248-249](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L248-L249)），动态生成的分支字段同时设置了 `showWhen` 和 `_branchIndex`：

```javascript
schema['branch_name_' + i] = {
    type: 'string', default: '',
    description: '分支' + i + '名称(空=默认)',
    showWhen: 'branch_count>=' + i,
    _branchIndex: i
};
```

所以分支字段的显示/隐藏实际上是由 `_branchIndex` 机制控制的，`showWhen` 在这里形同虚设（因为解析错误，永远返回 `false`，但 `_branchIndex` 检查在 `showWhen` 检查之后，且是 `continue` 跳过逻辑，两者是或关系——实际上看代码是顺序执行，`showWhen` 失败就 `continue` 了，不会走到 `_branchIndex`）。

等等，让我再仔细看一下渲染逻辑的顺序：

[property.js:326-336](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L326-L336)：

```javascript
if (schema.showWhen && !this._checkShowWhen(schema.showWhen, node.properties)) {
    if (node.properties[key] === undefined && schema.default !== undefined) {
        node.properties[key] = schema.default;
    }
    continue;  // <-- showWhen 检查失败就直接跳过，不会走到 _branchIndex
}

if (schema._branchIndex !== undefined) {
    var bc = parseInt(node.properties.branch_count) || 2;
    if (schema._branchIndex > bc) continue;
}
```

这意味着 `showWhen` 检查在 `_branchIndex` 检查**之前**执行。由于 `showWhen: 'branch_count>=3'` 解析错误导致 `_checkShowWhen` 返回 `false`，代码会执行 `continue` 跳过该字段，**永远不会走到 `_branchIndex` 检查**。

这确认了：**对于带有 `>=` 运算符的 `showWhen` 条件，前端渲染确实存在 Bug，相关字段无法正确显示。**

### 6. 总结

| 项目 | 说明 |
|------|------|
| `_normalizeSchema` 位置 | [nodes.js:125](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L125) |
| `_normalizeSchema` 对 `showWhen` 的处理 | 仅替换 `=True` → `=true`、`=False` → `=false`，**不处理 `>=` 等比较运算符** |
| `_checkShowWhen` 位置 | [property.js:392](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L392) |
| `_checkShowWhen` 解析逻辑 | 仅支持 `field=value` 格式的等值匹配，用 `indexOf('=')` 查找等号 |
| **核心 Bug** | `showWhen: 'branch_count>=3'` 被错误解析为 `field="branch_count>"`, `value="3"`，导致条件永远不满足，相关字段无法显示 |
| 受影响的字段 | 所有使用 `>=` 比较符的 `showWhen` 条件，如 `branch_name_3` ~ `branch_name_8`、`branch_affinity_3` ~ `branch_affinity_8` 等 |

如果需要修复此 Bug，`_checkShowWhen` 函数需要增加对 `>=`、`<=`、`>`、`<` 等比较运算符的支持，在解析时优先匹配这些运算符，而不是简单地将第一个 `=` 作为分隔符。
        
          
我需要找到序列化和反序列化的核心逻辑。让我查看导出的 AutomationCore 对象中的相关方法：
        
---

## 分析结果：`ctx.variables` 读写操作与线程安全问题

### 一、`safe_get_variable` 和 `safe_set_variable` 的实现（有锁保护）

在 [engine.py:153-159](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L153-L159) 中，这两个方法**有锁保护**：

```python
def safe_set_variable(self, key, value):
    with self._data_lock:
        self.variables[key] = value

def safe_get_variable(self, key, default=None):
    with self._data_lock:
        return self.variables.get(key, default)
```

锁定义在 [engine.py:139](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L139)：

```python
self._data_lock = threading.RLock()
```

使用的是 `RLock`（可重入锁），这意味着同一线程可以多次获取该锁而不会死锁。

---

### 二、`ctx.variables` 的直接读写（无锁保护 -- 线程安全隐患）

#### 1. 初始化时直接写入（[engine.py:150-151](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L150-L151)）

```python
for var_name, var_def in graph.variables.items():
    self.variables[var_name] = var_def.get("init")
```

这里在 `__init__` 中直接写入，此时尚未多线程，**安全**。

#### 2. `_resolve_value` 中直接读取 `ctx.variables`（[engine.py:379](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L379) 和 [engine.py:403](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L403)）

```python
# 第379行 - 单变量解析
var_val = ctx.safe_get_variable(var_name)   # <-- 这里用了 safe 方法，安全

# 第403行 - 多变量解析
var_val = ctx.safe_get_variable(var_name)   # <-- 这里也用了 safe 方法，安全
```

`_resolve_value` 中对 `ctx.variables` 的访问**都通过 `safe_get_variable`**，是安全的。

#### 3. `variable.py` 中的直接访问（[variable.py:191](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L191)）

```python
value = ctx.safe_get_variable(var_name, "")
if value == "" and var_name not in ctx.variables:   # <-- 直接读取 ctx.variables，无锁！
    value = _resolve_value(input_var, ctx)
```

**这是一个线程安全隐患**：在 `safe_get_variable` 返回空字符串后，又直接用 `var_name not in ctx.variables` 检查变量是否存在，这个检查没有锁保护。在 fork 并发场景下，另一个分支可能正在修改 `ctx.variables`，导致：
- 竞态条件：读取到不一致的状态
- Python dict 的 `in` 操作虽然有 GIL 保护不会崩溃，但逻辑上可能读到中间状态

#### 4. 测试代码中的直接访问

测试文件中的直接访问（如 `ctx.variables["x"] = 10`、`ctx.variables.get("count")`）不在生产路径上，影响较小。

---

### 三、`ctx.check_results` 的直接读写（大量无锁操作 -- 严重线程安全隐患）

虽然 `ExecContext` 提供了 `safe_set_check_result` 和 `safe_get_check_result` 方法（[engine.py:161-167](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L161-L167)），但**大量代码直接操作 `ctx.check_results` 而不通过 safe 方法**：

#### engine.py 中的无锁直接访问：

| 行号 | 代码 | 操作类型 |
|------|------|---------|
| [390](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L390) | `cr_val = ctx.check_results.get(cr_key)` | 读 |
| [393](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L393) | `if var_name in ctx.check_results:` | 读 |
| [394](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L394) | `return ctx.check_results[var_name]` | 读 |
| [419](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L419) | `cr_val = ctx.check_results.get(cr_key)` | 读 |
| [425](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L425) | `elif var_name in ctx.check_results:` | 读 |
| [426](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L426) | `str(ctx.check_results[var_name])` | 读 |
| [472](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L472) | `if key in ctx.check_results:` | 读 |
| [544](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L544) | `for k, v in ctx.check_results.items():` | 读 |

#### handlers 目录中的无锁直接访问（部分示例）：

| 文件 | 行号 | 操作 |
|------|------|------|
| [variable.py:16](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L16) | `ctx.check_results.get(key, fallback)` | 读 |
| [variable.py:94](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L94) | `ctx.check_results[f"{node.id}.result"] = result` | 写 |
| [variable.py:123](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L123) | `ctx.check_results[f"{node.id}.result"] = result` | 写 |
| [utility.py:25](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L25) | `ctx.check_results[f"{node.id}.value"] = value` | 写 |
| [utility.py:15](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L15) | `ctx.check_results.get(key, fallback)` | 读 |
| [control.py:39](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L39) | `ctx.check_results.get(key, False)` | 读 |
| [control.py:54](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L54) | `ctx.check_results[f"{node.id}.result"] = result` | 写 |
| [detection.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py) | 大量行 | 读写 |

**总计在 handlers 中发现约 80+ 处直接操作 `ctx.check_results` 的代码，均未通过 safe 方法。**

---

### 四、Fork 分支并发执行机制分析

在 [control.py:293-402](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L293-L402) 中，`_handle_fork` 的实现：

```python
def _handle_fork(node: ExecNode, ctx: ExecContext):
    # ... 创建 BranchContext ...
    
    for branch_info in active_branches:
        # 每个分支启动一个独立线程
        def branch_worker(bid, bctx, port_name, core_idx):
            # ...
            ctx._set_branch_id(bid)           # 设置线程本地变量
            ctx._set_current_affinity(core_idx)
            _execute_flow(node.id, port_name, ctx)  # 在新线程中执行，共享同一个 ctx！
            bctx.set_status("completed")
        
        t = threading.Thread(
            target=branch_worker,
            args=(branch_id, branch_ctx, branch_info["port_name"], core_index),
            daemon=True,
        )
        branch_ctx.thread = t
        t.start()   # 并发启动！
```

**关键发现：所有 fork 分支共享同一个 `ctx`（ExecContext）对象**，包括共享 `ctx.variables` 和 `ctx.check_results`。这意味着：

1. 多个分支线程**同时**读写 `ctx.variables` 和 `ctx.check_results`
2. 通过 `safe_get_variable` / `safe_set_variable` 的操作有 `RLock` 保护，是安全的
3. 直接操作 `ctx.check_results` 的代码**完全没有锁保护**，存在竞态条件

---

### 五、线程安全问题总结

| 数据结构 | Safe 方法 | 实际使用情况 | 线程安全？ |
|----------|----------|-------------|-----------|
| `ctx.variables` | `safe_get/set_variable` (有 RLock) | 绝大多数通过 safe 方法，1处直接读取 | **基本安全，有1处隐患** |
| `ctx.check_results` | `safe_get/set_check_result` (有 RLock) | **80+处直接读写，未用 safe 方法** | **严重不安全** |
| `ctx.hwnd_cache` | 无 safe 方法 | 直接读写 | 不安全 |
| `ctx.last_capture_cache` | `safe_get/set_cache` (有 RLock) | 部分通过 safe 方法 | 部分安全 |

#### 具体隐患点：

1. **[variable.py:191](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L191)** -- `var_name not in ctx.variables` 无锁直接读取
2. **[engine.py:390-426](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L390-L426)** -- `_resolve_value` 中多处直接读取 `ctx.check_results`，无锁保护
3. **[engine.py:544](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L544)** -- `_execute_flow` 中 `ctx.check_results.items()` 无锁遍历
4. **handlers 目录中大量** -- 直接写入 `ctx.check_results[...] = ...`，无锁保护

#### Python GIL 的"假安全感"：

虽然 CPython 的 GIL 保证了单个 dict 操作的原子性（不会因为并发导致解释器崩溃），但它**不保证逻辑一致性**。例如：
- 分支 A 写入 `ctx.check_results["n1.result"] = True`，分支 B 可能读不到（内存可见性问题）
- `_resolve_value` 中的 "先 get 再判断 in" 模式不是原子操作，中间可能被其他线程修改
- `for k, v in ctx.check_results.items()` 遍历期间如果其他线程修改了 dict，可能抛出 `RuntimeError: dictionary changed size during iteration`

**结论：fork 并发执行时，`ctx.check_results` 的线程安全问题最为严重，建议将所有直接操作替换为 `safe_set_check_result` / `safe_get_check_result` 调用，或在 `_resolve_value` 等关键路径中加锁。`ctx.variables` 的隐患较小但 [variable.py:191](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L191) 处也应修复。**


继续进行交叉验证。我需要阅读2期Bug汇总文档来确认哪些bug是后期考虑或拒绝的，同时验证已采纳的bug是否已修复。
        
            
toolName: todo_write
            
status: success
          
Todos updated: 3 items
          

        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\问题\2期Bug汇总文档.md
          
现在我已完整阅读了两份文档。接下来需要验证1期已采纳的bug是否已修复。
        
            
toolName: todo_write
            
status: success
          
Todos updated: 3 items
          
让我验证1期关键已采纳bug的修复状态：
        
            
toolName: no_need_execute
            
status: no_need_execute
          
          

        
            
toolName: no_need_execute
            
status: no_need_execute
          
          

        
            
toolName: no_need_execute
            
status: no_need_execute
          
          

        
            
toolName: no_need_execute
            
status: no_need_execute
          
          
**中文总结：**
1. 用户要我检查 `utility.py` 中两个已知bug的修复状态：(A-08) condition节点的cond_var参数不解析`${}`语法，(A-09) string_op的param_a/b/c参数不使用`_resolve_value`。
2. 我计划直接读取该文件，搜索相关代码片段，确认是否已修复。
3. 无需额外信息，直接开始。
        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\automation\handlers\utility.py
          
用户要求我检查 `detection.py` 文件中 `_do_check` 和 `_do_check_screen` 函数的调用情况，确认第528行和538行附近是否已将错误的 `_do_check()` 修复为 `_do_check_screen()`。我直接读取文件相关行。
        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\automation\handlers\detection.py
          
**中文总结：**
1. 用户要我检查 `monitor.py` 中 `interval` 和 `timeout` 参数的获取方式，确认是否已使用 `_resolve_value` 修复了 `float("${var}")` 崩溃的bug。
2. 计划：直接读取该文件，搜索相关代码。
3. 不缺信息，直接执行。
        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\automation\handlers\monitor.py
          
现在让我也查看 `_extract_var_name` 的实现，以确认它是否能处理 `${}` 语法：
        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\automation\handlers\variable.py
          

        
            
toolName: search_by_regex
            
status: success
          
query: _do_check
          

        
            
toolName: search_by_regex
            
status: success
          
query: _resolve_value
          
**中文总结：**
1. 用户要我检查 `variable.py` 中两个已知bug是否已修复：(A-13) `bool("false")` 返回 `True` 的bug，(A-14) replace 硬编码替换为空字符串的bug
2. 我计划直接读取该文件，查找相关代码片段，判断修复状态
3. 不缺额外信息，直接开始
        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\automation\handlers\variable.py
          

        
            
toolName: search_by_regex
            
status: success
          
query: interval|timeout
          
## 检查结果：1期A-06 bug 已修复

`interval` 和 `timeout` 参数**已经改用 `_resolve_value`**，bug 已修复。以下是具体代码：

### `_handle_monitor_node` 函数（第 98-99 行）

```python
interval = float(_resolve_value(node.params.get("interval", 100), ctx)) / 1000.0
timeout_ms = float(_resolve_value(node.params.get("timeout", 0), ctx))
```

- [monitor.py:98](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L98) — `interval` 通过 `_resolve_value()` 解析后再转 `float`
- [monitor.py:99](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L99) — `timeout` 同样通过 `_resolve_value()` 解析后再转 `float`

### `_handle_monitor_time` 函数（第 214-215 行）

```python
check_interval = float(_resolve_value(params.get("check_interval", 500), ctx)) / 1000.0
timeout_ms = float(_resolve_value(params.get("timeout", 0), ctx))
```

- [monitor.py:214](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L214) — `check_interval` 也使用了 `_resolve_value()`
- [monitor.py:215](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L215) — `timeout` 同样使用了 `_resolve_value()`

### 其他相关参数也已修复

在 `_handle_monitor_node` 中，以下数值参数同样都已使用 `_resolve_value`：

| 参数 | 行号 | 代码 |
|------|------|------|
| `repeat_count` | 103 | `int(_resolve_value(node.params.get("repeat_count", 0), ctx))` |
| `recheck_delay_ms` | 105 | `float(_resolve_value(node.params.get("recheck_delay_ms", 500), ctx))` |
| `max_triggers` | 106 | `int(_resolve_value(node.params.get("max_triggers", 0), ctx))` |
| `auto_close_after_ms` | 107 | `float(_resolve_value(node.params.get("auto_close_after_ms", 0), ctx))` |

在 `_handle_monitor_time` 中：

| 参数 | 行号 | 代码 |
|------|------|------|
| `hour` | 210 | `int(_resolve_value(params.get("hour", 8), ctx))` |
| `minute` | 211 | `int(_resolve_value(params.get("minute", 0), ctx))` |
| `second` | 212 | `int(_resolve_value(params.get("second", 0), ctx))` |

### 结论

**1期A-06 bug 已修复。** 所有数值型参数（包括 `interval`、`timeout`、`check_interval` 等）都已通过 `_resolve_value()` 先解析变量引用（如 `${var}`），再进行 `float()` / `int()` 类型转换。这样当用户使用 `float("${var}")` 形式的变量引用时，`_resolve_value` 会先将 `${var}` 解析为实际值，再传给 `float()`，避免了直接对 `"${var}"` 字符串调用 `float()` 导致的 `ValueError` 崩溃。
        
          
让我再看看 `_do_check_screen` 函数定义附近的完整代码，以及对比 `_do_check` 在其他检测类型中的使用模式：
        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\automation\handlers\detection.py
          
## 检查结果

### Bug 1（1期A-13）：`var_set` 的 boolean 类型转换 — `bool("false")` 返回 `True`

**已修复。** 当前代码在 [variable.py:46-52](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L46-L52)（multi_mode 分支）和 [variable.py:63-69](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L63-L69)（单变量分支）中，boolean 转换逻辑为：

```python
# 第 46-52 行（multi_mode）
elif var_type == "boolean":
    if isinstance(value, bool):
        pass
    elif isinstance(value, str):
        value = value.lower() not in ("", "0", "false", "no", "off", "none", "null")
    else:
        value = bool(value)

# 第 63-69 行（单变量分支）
elif var_type == "boolean":
    if isinstance(value, bool):
        pass
    elif isinstance(value, str):
        value = value.lower() not in ("", "0", "false", "no", "off", "none", "null")
    else:
        value = bool(value)
```

**分析：** 原始 bug 是直接使用 Python 内置的 `bool("false")`，而 Python 中任何非空字符串的布尔值都是 `True`，所以 `bool("false")` 会错误地返回 `True`。当前代码已改为 `value.lower() not in ("", "0", "false", "no", "off", "none", "null")`，这样字符串 `"false"` 会被正确识别为 `False`。**此 bug 已修复。**

---

### Bug 2（1期A-14）：`var_string` 的 replace 操作 — 硬编码替换为空字符串

**已修复。** 当前代码在 [variable.py:136](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L136) 和 [variable.py:151-152](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L151-L152) 中：

```python
# 第 136 行 — 正确读取 replace_str 参数
replace_str = str(_resolve_value(node.params.get("replace_str", node.params.get("c", "")), ctx))

# 第 151-152 行 — replace 操作
elif op == "replace":
    result = a.replace(search_str, replace_str)
```

**分析：** 原始 bug 是 replace 操作中替换字符串被硬编码为空字符串 `""`，即无论用户指定什么替换内容，都只会执行删除操作。当前代码已从参数中正确读取 `replace_str`（优先取 `replace_str` 参数，回退到 `c` 参数），并将其传入 `a.replace(search_str, replace_str)`。**此 bug 已修复。**

---

### 总结

| Bug 编号 | 问题描述 | 修复状态 | 关键代码位置 |
|----------|---------|---------|-------------|
| 1期A-13 | `bool("false")` 返回 `True` | **已修复** | [variable.py:46-52](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L46-L52)、[variable.py:63-69](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L63-L69) |
| 1期A-14 | replace 硬编码替换为空字符串 | **已修复** | [variable.py:136](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L136)、[variable.py:151-152](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L151-L152) |

两个 bug 均已在当前代码中修复。
        
          
现在我已经获取了所有需要的信息，下面是完整的分析报告。

---

## 检查结果

### Bug 1期A-08：condition 节点的 `cond_var` 参数不解析 `${}` 语法

**状态：已修复**

相关代码位于 [utility.py:163-176](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L163-L176)：

```python
def _handle_condition(node: ExecNode, ctx: ExecContext):
    cond_val = _read_data_input(node, ctx, "cond")
    true_val = _read_data_input(node, ctx, "if_true")
    false_val = _read_data_input(node, ctx, "if_false")

    if cond_val is not None:
        cond = bool(cond_val)
    else:
        cond_var = node.params.get("cond_var", "")
        if cond_var:
            var_name = _extract_var_name(cond_var)    # <-- 第173行：已使用 _extract_var_name 解析
            cond = bool(ctx.safe_get_variable(var_name, False))
        else:
            cond = False
```

**修复说明：** 第173行调用了 `_extract_var_name(cond_var)`，该函数定义在 [variable.py:5-8](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L5-L8)：

```python
def _extract_var_name(val):
    if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
        return val[2:-1]
    return val
```

当 `cond_var` 的值为 `${some_var}` 格式时，`_extract_var_name` 会剥去 `${}` 包裹，返回纯变量名 `some_var`，然后再用 `ctx.safe_get_variable` 获取变量值。**此bug已修复。**

---

### Bug 1期A-09：string_op 的 `param_a/b/c` 参数不使用 `_resolve_value`

**状态：已修复**

相关代码位于 [utility.py:122-133](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L122-L133)：

```python
def _handle_string_op(node: ExecNode, ctx: ExecContext):
    s_val = _read_data_input(node, ctx, "str")
    s = str(s_val if s_val is not None else _resolve_value(node.params.get("input_str", ""), ctx))
    op = node.params.get("op", "concat")

    concat_str = str(_resolve_value(node.params.get("concat_str", node.params.get("param_a", "")), ctx))
    search_str = str(_resolve_value(node.params.get("search_str", node.params.get("param_a", "")), ctx))
    replace_str = str(_resolve_value(node.params.get("replace_str", node.params.get("param_b", "")), ctx))
    start_pos = int(_resolve_value(node.params.get("start_pos", node.params.get("param_b", 0)), ctx))
    length = int(_resolve_value(node.params.get("length", node.params.get("param_c", 0)), ctx))
    delimiter = str(_resolve_value(node.params.get("delimiter", node.params.get("param_a", ",")), ctx))
    index = int(_resolve_value(node.params.get("index", node.params.get("param_b", 0)), ctx))
```

**修复说明：** 每个 `param_a/b/c` 参数都作为 `_resolve_value` 的 fallback 值传入，整个表达式被 `_resolve_value` 包裹。具体逻辑是：

- 优先读取新参数名（如 `concat_str`、`search_str` 等），如果不存在则回退到旧参数名（`param_a`、`param_b`、`param_c`）
- 无论使用哪个参数名，最终值都经过 `_resolve_value()` 处理，因此 `${}` 语法会被正确解析

例如第127行：
```python
concat_str = str(_resolve_value(node.params.get("concat_str", node.params.get("param_a", "")), ctx))
```
- 先尝试获取 `concat_str` 参数
- 若不存在，回退到 `param_a`
- 无论哪种情况，最终值都传入 `_resolve_value` 进行变量解析

**此bug已修复。**

---

## 总结

| Bug编号 | 描述 | 修复状态 | 关键代码位置 |
|---------|------|---------|-------------|
| 1期A-08 | condition节点cond_var不解析`${}` | **已修复** | [utility.py:173](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L173) - 使用 `_extract_var_name(cond_var)` |
| 1期A-09 | string_op的param_a/b/c不使用`_resolve_value` | **已修复** | [utility.py:127-133](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L127-L133) - 所有参数均包裹在 `_resolve_value()` 中 |

两个bug均已在当前代码中修复。
        
          
## 检查结果

**1期A-01 bug 已修复。** 以下是详细分析：

### 函数定义

在 [detection.py:511](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L511) 处，函数定义名称正确为 `_do_check_screen`：

```python
511→        def _do_check_screen():
512→            img = capture_screen(region, ctx=ctx)
513→            if len(img.shape) == 3:
514→                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
515→            else:
516→                gray = img
517→            mean_brightness = float(np.mean(gray))
518→
519→            if state == "black":
520→                found = mean_brightness < threshold
521→            elif state == "bright":
522→                found = mean_brightness > (255 - threshold)
523→            elif state == "frozen":
524→                last_img = ctx.last_capture_cache.get(node.id)
525→                ctx.last_capture_cache[node.id] = img
526→                if last_img is not None:
527→                    diff = float(np.mean(np.abs(img.astype(float) - last_img.astype(float))))
528→                    found = diff < threshold
529→                else:
530→                    found = False
531→            else:
532→                found = False
533→            return found
```

### 函数调用

两处调用均已正确使用 `_do_check_screen()`：

1. **第536行**（非等待模式）：
```python
535→        if not wait:
536→            found = _do_check_screen()
537→            ctx.check_results[f"{node.id}.result"] = found
538→            if found:
539→                _execute_flow(node.id, "match", ctx)
540→            else:
541→                _execute_flow(node.id, "no", ctx)
542→            return
```

2. **第546行**（等待循环模式）：
```python
544→        start_time = time.perf_counter()
545→        while not ctx.stop_event.is_set():
546→            found = _do_check_screen()
547→            if found:
548→                ctx.check_results[f"{node.id}.result"] = True
549→                _execute_flow(node.id, "match", ctx)
550→                return
```

### 全局搜索确认

通过全局搜索 `_do_check`，在 `check_screen` 处理逻辑中，所有调用均已使用 `_do_check_screen()`，没有残留的错误调用 `_do_check()`。文件中其他位置的 `_do_check()` 调用（第94、109、122、163、201、211行）属于其他检测类型（如 `check_pixel` 等），它们各自定义了自己的 `_do_check` 内部函数，调用是正确的。

**结论：1期A-01 bug（check_screen 调用错误的 `_do_check()` 而非 `_do_check_screen()`）已经在当前代码中修复，第536行和第546行均正确调用了 `_do_check_screen()`。**
        
          
1期关键已采纳bug已确认修复。现在让我验证我独立发现的几个新bug是否确实不在已有文档中，并进一步确认它们的实际影响。
        
            
toolName: no_need_execute
            
status: no_need_execute
          
          

        
            
toolName: no_need_execute
            
status: no_need_execute
          
          
**中文总结：**

1. **用户要做什么**：在 `automation` 目录中搜索所有 `params_schema` 里 `type` 为 `"array"` 或有列表默认值，且同时设置了 `varRef: True` 的参数定义，特别关注 `rect`、`region`、`color` 等数组类型参数。

2. **计划步骤**：
   - 先用 Grep 搜索包含 `varRef` 的文件，定位候选文件
   - 同时搜索 `type.*array` 的参数定义
   - 搜索包含列表默认值模式（如 `[0,0,`）的参数定义
   - 交叉匹配同时满足条件的参数定义，返回文件和行号

3. **缺少的信息**：无，可以直接开始搜索。

现在开始执行搜索：
        
            
toolName: search_by_regex
            
status: success
          
query: varRef
          
**中文总结：**
1. 用户要求：对比 `engine.py` 中 `_execute_node`（普通节点）和 `_handle_plugin_node`（插件节点）两个函数的异常处理逻辑，重点关注异常后是否继续执行后续节点。
2. 计划步骤：读取 `engine.py` 文件，定位两个函数，提取 try/except 块完整代码和行号，进行对比分析。
3. 缺少信息：暂无，直接读取文件即可。

现在开始执行：
        
            
toolName: search_by_regex
            
status: success
          
query: def _execute_node|def _handle_plugin_node
          

        
            
toolName: search_by_regex
            
status: success
          
query: type.*array
          

        
            
toolName: search_by_regex
            
status: success
          
query: \[\d+,\s*\d+
          

        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\automation\engine.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\automation\engine.py
          
搜索结果已经非常清晰了。让我进一步读取 `detection.py` 中匹配行的上下文，确认完整的参数定义：
        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\automation\nodes\detection.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\automation\nodes\preset.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\automation\nodes\monitor.py
          
搜索结果已经非常完整。以下是所有匹配的参数定义汇总：

---

## 搜索结果：`type: "array"` 且 `varRef: True` 的参数定义

在整个 `automation` 目录中，共找到 **9 处**同时满足 `type: "array"`（或列表默认值）且 `varRef: True` 的参数定义，分布在 3 个文件中。所有匹配参数均为 `rect` 或 `region`，`format` 均为 `"region"`，默认值均为 `[x, y, w, h]` 形式的四元素数组。

---

### 一、[detection.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/detection.py) — 4 处匹配

| 行号 | 参数名 | 所属节点 | 完整定义 |
|------|--------|----------|----------|
| **第 13 行** | `region` | `detection/capture_source` (截图源) | `"region": {"type": "array", "format": "region", "default": [0, 0, 0, 0], "description": "采集区域[x,y,w,h]，0=全屏（region模式使用）", "showWhen": "capture_mode=region", "varRef": True}` |
| **第 32 行** | `rect` | `detection/check_color` (颜色检测) | `"rect": {"type": "array", "format": "region", "default": [0, 0, 10, 10], "description": "检测区域[x,y,w,h]", "varRef": True}` |
| **第 63 行** | `rect` | `detection/check_ocr` (OCR识别) | `"rect": {"type": "array", "format": "region", "default": [0, 0, 100, 30], "description": "检测区域[x,y,w,h]", "varRef": True}` |
| **第 95 行** | `rect` | `detection/check_image` (图像匹配) | `"rect": {"type": "array", "format": "region", "default": [0, 0, 0, 0], "description": "搜索区域[x,y,w,h], 0=全屏", "varRef": True}` |
| **第 125 行** | `region` | `detection/check_screen` (屏幕状态) | `"region": {"type": "array", "format": "region", "default": [0, 0, 0, 0], "description": "检测区域, 0=全屏", "varRef": True}` |

> detection.py 实际有 **5 处**匹配（上面更正）。

---

### 二、[preset.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/preset.py) — 2 处匹配

| 行号 | 参数名 | 所属节点 | 完整定义 |
|------|--------|----------|----------|
| **第 34 行** | `rect` | `preset/preset_find_click` (找图点击) | `"rect": {"type": "array", "format": "region", "default": [0, 0, 0, 0], "description": "搜索区域, 0=全屏", "varRef": True}` |
| **第 55 行** | `rect` | `preset/preset_read_text` (读取数字文本) | `"rect": {"type": "array", "format": "region", "default": [0, 0, 100, 30], "description": "检测区域[x,y,w,h]", "varRef": True}` |

---

### 三、[monitor.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/monitor.py) — 2 处匹配

| 行号 | 参数名 | 所属节点 | 完整定义 |
|------|--------|----------|----------|
| **第 14 行** | `rect` | `monitor/monitor_color` (颜色监视) | `"rect": {"type": "array", "format": "region", "default": [0, 0, 10, 10], "description": "检测区域[x,y,w,h]", "varRef": True}` |
| **第 47 行** | `rect` | `monitor/monitor_ocr` (OCR监视) | `"rect": {"type": "array", "format": "region", "default": [0, 0, 100, 30], "description": "检测区域[x,y,w,h]", "varRef": True}` |

---

## 汇总统计

| 文件 | 匹配数量 | 参数名 |
|------|----------|--------|
| [nodes/detection.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/detection.py) | 5 | `region` x2, `rect` x3 |
| [nodes/preset.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/preset.py) | 2 | `rect` x2 |
| [nodes/monitor.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/monitor.py) | 2 | `rect` x2 |
| **合计** | **9** | `rect` x7, `region` x2 |

## 关键特征

1. **所有匹配参数的共同模式**：`"type": "array"`, `"format": "region"`, `"varRef": True`，默认值均为四元素整数数组 `[x, y, w, h]`。
2. **默认值分布**：
   - `[0, 0, 0, 0]` — 表示"全屏/无限制"（4处）
   - `[0, 0, 10, 10]` — 小区域检测（2处，用于颜色检测/监视）
   - `[0, 0, 100, 30]` — 文本行区域（3处，用于OCR相关）
3. **未发现 `color` 类型参数同时满足 `type: "array"` 和 `varRef: True`** — 颜色参数（如 `target_color`）的 `type` 为 `"string"`、`format` 为 `"color"`，不属于数组类型。
4. **其他文件**（`control.py`、`utility.py`、`variable.py`）中的 `varRef: True` 参数均为 `number`、`string` 或 `bool` 类型，不满足数组条件。
        
          
现在我需要确认普通节点的 handler 内部是如何调用 `_execute_flow` 的，以完整理解异常后的流程：
        
            
toolName: search_by_regex
            
status: success
          
query: _execute_flow
          

        
            
toolName: search_by_regex
            
status: failed
          
query: _execute_flow
          

        
            
toolName: file_search
            
status: success
          
file_pattern: **/handlers.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\automation\engine.py
          

        
            
toolName: search_by_regex
            
status: success
          
query: _execute_flow
          
现在我已经获取了所有需要的信息。下面是完整的对比分析。

---

## `_execute_node` 与 `_handle_plugin_node` 异常处理逻辑对比

### 一、`_handle_plugin_node`（插件节点）—— 第 567-631 行

try/except 块位于 **第 568-623 行**：

```python
# engine.py:568-623
def _handle_plugin_node(node, ctx: ExecContext):
    try:                                                    # L568
        from core.plugin_manager import PluginManager
        from core.plugin_context import PluginContext
        from automation.detection.capture import capture_screen

        node_def = PluginRegistry.get_node(node.type)
        plugin_id = None
        action = node.type.split("/", 1)[-1]
        if node_def and isinstance(node_def, dict):
            plugin_id = node_def.get("_plugin_id")
            action = node_def.get("backendAction", action)
        if not plugin_id:
            for pid in PluginManager._plugins:
                manifest = PluginManager.get_manifest(pid)
                if manifest and action in manifest.get("nodes", []):
                    plugin_id = pid
                    break
        if not plugin_id:
            plugin_id = node.type.split("/", 1)[-1]
        params = dict(node.params) if node.params else {}

        if node_def and isinstance(node_def, dict):
            schema = node_def.get("params_schema", {})
            for key, field_def in schema.items():
                if isinstance(field_def, dict) and field_def.get("varRef") and key in params:
                    params[key] = _resolve_value(params[key], ctx)

        def _capture_fn(region):
            return capture_screen(region, ctx)

        plugin_ctx = PluginContext(
            emit_fn=PluginManager._emit_to_window,
            capture_fn=_capture_fn,
            var_get_fn=lambda name, default=None: ctx.safe_get_variable(name, default),
            var_set_fn=lambda name, value: ctx.safe_set_variable(name, value),
            ctx_ref=ctx,
        )

        result = PluginManager.execute(plugin_id, action, params, context=plugin_ctx)
        if result and isinstance(result, dict):
            for k, v in result.get("set_variables", {}).items():
                ctx.safe_set_variable(k, v)
            for k, v in result.get("check_results", {}).items():
                ctx.safe_set_check_result(f"{node.id}.{k}", v)
            if not result.get("ok"):
                ctx.log_error(
                    result.get("error", "插件执行失败"),
                    node_id=str(node.id),
                    error_type="plugin",
                )
    except Exception as e:                                  # L620
        ctx.log_error(f"插件节点异常 {node.type}: {e}", node_id=str(node.id), error_type="plugin")
        _execute_flow(node.id, "fail" if _has_output_port(node, "fail") else "next", ctx)
        return                                              # L623

    ok = result.get("ok", True) if result and isinstance(result, dict) else True
    if ok:
        flow_port = "success" if _has_output_port(node, "success") else "next"
    else:
        flow_port = "fail" if _has_output_port(node, "fail") else "next"
    _execute_flow(node.id, flow_port, ctx)
```

### 二、`_execute_node`（普通节点）—— 第 633-740 行

try/except 块位于 **第 712-724 行**：

```python
# engine.py:712-724
        try:                                                # L712
            handler(node, ctx)                              # L713
        except (FileNotFoundError, ImportError, TypeError, ValueError) as e:  # L714
            error_msg = f"节点 {node.type}({current_id}) 系统错误: {e}"
            print(f"[新引擎] {error_msg}")
            ctx.log_error(error_msg, node_id=current_id, error_type="system")
        except Exception as e:                              # L718
            error_msg = f"节点 {node.type}({current_id}) 执行异常: {e}"
            print(f"[新引擎] {error_msg}")
            ctx.log_error(error_msg, node_id=current_id, error_type="runtime")
        finally:                                            # L722
            if _original_params is not None:
                node.params = _original_params              # L724
```

异常之后的后续逻辑（第 726-738 行）：

```python
# engine.py:726-738
        goto_target = branch_ctx._goto_target if branch_ctx else ctx._goto_target
        if goto_target:
            with ctx._data_lock:
                executed_set.discard(goto_target)
            _ensure_data_inputs(goto_target, ctx)
            current_id = goto_target
            if branch_ctx:
                branch_ctx._goto_target = None
            else:
                ctx._goto_target = None
            continue

        return                                              # L738
```

---

### 三、核心差异对比

| 对比项 | `_execute_node`（普通节点） | `_handle_plugin_node`（插件节点） |
|---|---|---|
| try/except 行号 | L712-L724 | L568-L623 |
| 异常捕获粒度 | 两层：系统错误（FileNotFoundError/ImportError/TypeError/ValueError）+ 通用 Exception | 一层：统一捕获 Exception |
| 异常后是否调用 `_execute_flow` | **否** — 只做日志记录，不调用 `_execute_flow` | **是** — 显式调用 `_execute_flow(node.id, "fail" if _has_output_port(node, "fail") else "next", ctx)` |
| 异常后是否继续执行后续节点 | **否** — 异常被吞掉后，代码走到 L726 检查 goto_target，若无 goto 则直接 `return`（L738），流程断裂 | **是** — 通过 fail 端口（若有）或 next 端口继续执行下游节点 |
| 正常流程的推进方式 | 由 `handler(node, ctx)` 内部自行调用 `_execute_flow`（见 [action.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py) 各 handler） | 由 `_handle_plugin_node` 自身在函数末尾（L625-L630）根据 result.ok 决定走 success/fail/next 端口 |

### 四、关键结论

1. **普通节点异常后不会继续执行后续节点**：`handler(node, ctx)` 在 try 块中执行，如果抛出异常，handler 内部的 `_execute_flow` 调用不会被执行。except 块只记录日志，之后代码检查 goto_target（L726），若无 goto 则直接 `return`（L738），**整条执行链在此断裂**。

2. **插件节点异常后会走 fail/next 端口继续执行**：except 块（L620-623）在记录日志后，**显式调用** `_execute_flow(node.id, "fail" if _has_output_port(node, "fail") else "next", ctx)`，优先走 `fail` 端口，若无 fail 端口则走 `next` 端口，**确保流程不会因异常而断裂**。

3. **这是一个设计上的不对称**：插件节点有"容错续流"机制（异常后仍可沿 fail/next 端口继续），而普通节点没有——异常即停。如果需要统一行为，应考虑在 `_execute_node` 的 except 块中也加入类似的 `_execute_flow` 调用逻辑。
        
          
让我继续验证1期更多关键P0 bug的修复状态：
        
            
toolName: no_need_execute
            
status: no_need_execute
          
          

        
            
toolName: no_need_execute
            
status: no_need_execute
          
          
**任务总结：**
1. 用户要我查找 `editor-app.js` 和 `core.js` 中的循环检测（cycle detection）逻辑
2. 1期A-05 bug 是 goto 节点的合法回跳被循环检测错误阻止
3. 需要确认前端是否已排除 goto 产生的回边
4. 返回相关代码片段和行号

我现在开始并行搜索两个文件中的循环检测相关代码。
        
            
toolName: search_by_regex
            
status: success
          
query: cycle|循环|hasCycle|detectCycle|circular|loop.*detect|back.*edge|回跳|回边
          
## 任务总结

1. **用户要做什么**：验证 automation 目录中三个1期P0 bug（A-02、A-03、A-13）是否已修复
2. **计划步骤**：
   - 读取 `automation/nodes/control.py`，检查 seq_check 和 state_machine 是否有 cond 数据输入端口
   - 读取 `engine.py`，检查 _execute_node 中 goto 跳转时是否从 executed_set 移除目标节点
   - 读取 `automation/handlers/monitor.py`，检查 auto_stop 参数逻辑是否正确
3. **缺少信息**：无，文件路径已明确

现在开始并行读取相关文件：
        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\automation\nodes\control.py
          

        
            
toolName: search_by_regex
            
status: success
          
query: goto|GOTO|GoTo
          

        
            
toolName: search_by_regex
            
status: success
          
query: visited|dfs|topo|拓扑|环路|闭环
          

        
            
toolName: file_search
            
status: success
          
file_pattern: **/engine.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\automation\handlers\monitor.py
          
找到了关键代码。让我再读取更完整的上下文，确认整个循环检测函数的完整逻辑。
        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\webui\modules\auto\editor-app.js
          

        
            
toolName: search_by_regex
            
status: success
          
query: cycle|循环|hasCycle|detectCycle|circular|goto|visited|recStack|adj
          
现在读取 engine.py 中的 `_execute_node` 函数，查找 goto 跳转和 executed_set 的逻辑：
        
            
toolName: search_by_regex
            
status: success
          
query: executed_set|_execute_node|goto
          

        
            
toolName: view_files
            
status: success
          
            
filePath: g:\宏引擎\宏驱动 webui 2.7.7\automation\engine.py
          
现在我已经获取了完整的循环检测逻辑。让我再确认 `core.js` 中是否有独立的循环检测逻辑：
        
            
toolName: search_by_regex
            
status: success
          
query: validateGraph|hasCycle|循环连线|回环
          
`core.js` 中没有循环检测逻辑。所有循环检测代码都在 `editor-app.js` 中。下面是完整的分析结果。

---

## 分析结果：循环检测逻辑与 goto 回边排除

### 循环检测代码位置

循环检测逻辑全部位于 [editor-app.js](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js) 的 `validateGraph` 函数中，第 1015-1066 行。

### 完整代码片段

```javascript
// 第 1015-1066 行
function validateGraph(data) {
  if (!data || !data.graph) return { ok: false, message: '无效的图数据' };
  var nodes = data.graph.nodes || [];
  var connections = data.graph.connections || [];
  var startNodes = nodes.filter(function(n) { return n.type === 'flow/start'; });
  if (startNodes.length === 0) {
    var hasAction = nodes.some(function(n) { return n.type.startsWith('action/') || n.type.startsWith('script_block/') || n.type.startsWith('control/') || n.type.startsWith('preset/'); });
    if (!hasAction) return { ok: false, message: '图中没有任何可执行节点，请添加节点并连线' };
  }
  if (startNodes.length > 1) {
    return { ok: false, message: '图中存在 ' + startNodes.length + ' 个开始节点，只能有 1 个' };
  }
  var nodeMap = {};
  for (var i = 0; i < nodes.length; i++) nodeMap[nodes[i].id] = nodes[i];
  var adj = {};
  for (var i = 0; i < nodes.length; i++) adj[nodes[i].id] = [];

  // ---- 关键：goto 节点排除逻辑 ----
  var gotoSourceNodes = {};                                          // 第 1031 行
  for (var i = 0; i < nodes.length; i++) {                           // 第 1032 行
    if (nodes[i].type === 'control/goto' && nodes[i].params && nodes[i].params.target_node_id) {
      gotoSourceNodes[nodes[i].id] = true;                           // 第 1034 行
    }
  }
  for (var j = 0; j < connections.length; j++) {                     // 第 1037 行
    var c = connections[j];
    if (c.type === 'flow' && nodeMap[c.from.node] && nodeMap[c.to.node]) {
      if (gotoSourceNodes[c.from.node]) continue;                    // 第 1040 行 ← 跳过 goto 节点的出边
      adj[c.from.node].push(c.to.node);
    }
  }
  // ---- goto 排除逻辑结束 ----

  var visited = {};
  var recStack = {};
  function hasCycle(nid) {                                           // 第 1046 行
    visited[nid] = true;
    recStack[nid] = true;
    var neighbors = adj[nid] || [];
    for (var k = 0; k < neighbors.length; k++) {
      if (!visited[neighbors[k]]) {
        if (hasCycle(neighbors[k])) return true;
      } else if (recStack[neighbors[k]]) {
        return true;
      }
    }
    recStack[nid] = false;
    return false;
  }
  for (var nid in adj) {
    if (!visited[nid]) {
      if (hasCycle(nid)) return { ok: false, message: '图中存在循环连线，请检查流程是否形成回环' };
    }
  }
  return { ok: true };
}
```

### 结论：前端已排除 goto 产生的回边

**前端已经做了 goto 回边排除处理。** 具体机制如下：

1. **第 1031-1035 行**：遍历所有节点，将类型为 `control/goto` 且配置了 `target_node_id` 参数的节点 ID 收集到 `gotoSourceNodes` 集合中。

2. **第 1040 行**：在构建邻接表 `adj` 时，如果一条 flow 连线的起点（`c.from.node`）属于 `gotoSourceNodes`，则 `continue` 跳过，**不将该边加入邻接表**。

3. 由于 `hasCycle` DFS 检测只遍历 `adj` 中的边，goto 节点产生的出边已被排除，因此 goto 的合法回跳不会触发循环检测。

### 潜在问题分析

虽然前端已排除了 goto 节点的出边，但这个排除逻辑有一个**前提条件**：goto 节点必须有 `params.target_node_id` 参数（第 1033 行的判断条件）。如果：

- goto 节点尚未配置目标节点 ID（`target_node_id` 为空或 undefined），则该节点不会被加入 `gotoSourceNodes`
- 此时 goto 节点的 flow 出边（如果有的话）仍会被加入邻接表，可能被误判为循环

不过，从 [nodes.js 第 517-519 行](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L517-L519) 可以看到，`control/goto` 节点的 outputs 为空数组 `[]`，即 goto 节点本身没有 flow 输出端口，所以即使未配置 `target_node_id`，也不会有 flow 出边被加入邻接表。

**总结：前端的循环检测逻辑已正确排除了 goto 节点产生的回边，1期A-05 bug 在前端层面已被修复。如果 bug 仍然存在，问题可能在后端的循环检测逻辑中，而非前端。**
        
          
现在我已经获取了所有需要的信息。下面是三个 bug 的验证结果：

---

## Bug 验证报告

### A-02: seq_check/state_machine 缺少 cond 数据输入端口 -- 已修复

在 [control.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/control.py) 中：

**seq_check** (第92-111行) 已添加 `cond` 数据输入端口：

```python
registry.register_node({
    "type": "control/seq_check",
    ...
    "inputs": [
        {"name": "in", "type": "flow"},
        {"name": "cond", "type": "data_bool"},   # <-- 已添加
    ],
    ...
})
```

**state_machine** (第113-128行) 已添加 `cond` 数据输入端口：

```python
registry.register_node({
    "type": "control/state_machine",
    ...
    "inputs": [
        {"name": "in", "type": "flow"},
        {"name": "cond", "type": "data_bool"},   # <-- 已添加
    ],
    ...
})
```

**结论：A-02 已修复。** 两个节点都正确添加了 `{"name": "cond", "type": "data_bool"}` 数据输入端口，与 `if_else`、`loop_while`、`wait_cond` 等条件类节点保持一致。

---

### A-03: goto 跳转到已执行节点被 executed_set 阻止 -- 已修复

在 [engine.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L726-L736) 中，`_execute_node` 函数的 goto 处理逻辑：

```python
goto_target = branch_ctx._goto_target if branch_ctx else ctx._goto_target
if goto_target:
    with ctx._data_lock:
        executed_set.discard(goto_target)    # <-- 关键修复：从 executed_set 中移除目标节点
    _ensure_data_inputs(goto_target, ctx)
    current_id = goto_target
    if branch_ctx:
        branch_ctx._goto_target = None
    else:
        ctx._goto_target = None
    continue
```

**结论：A-03 已修复。** 当 goto 跳转时，代码在第729行通过 `executed_set.discard(goto_target)` 将目标节点从已执行集合中移除，这样目标节点在下一轮循环中不会被第640行的 `if node_id in executed_set: return` 检查拦截，可以正常重新执行。同时使用了 `ctx._data_lock` 保证线程安全。

---

### A-13: 监视器 auto_stop 完全无效 -- 已修复

在 [monitor.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L94-L206) 中，`_handle_monitor_node` 函数的 auto_stop 逻辑：

**1. 参数读取** (第104行)：
```python
auto_stop = node.params.get("auto_stop", True)
```

**2. 轮询线程中的处理** (第150-161行)：
```python
if should_trigger:
    triggered_count += 1
    _pending_trigger[0] = True
    if max_triggers > 0 and triggered_count >= max_triggers:
        trigger_event.set()
        break
    if auto_stop:                          # <-- auto_stop=True 时：触发后停止轮询
        trigger_event.set()
        break
    trigger_signal.set()                   # <-- auto_stop=False 时：通知主线程执行分支
    flow_done.wait()                       # <-- 等待分支执行完成
    flow_done.clear()
    _pending_trigger[0] = False
    if recheck_delay_ms > 0:
        precise_sleep(recheck_delay_ms / 1000.0, ctx.stop_event)
```

**3. 主线程中的处理** (第180-197行)：
```python
while not ctx.stop_event.is_set() and not (branch_stop and branch_stop.is_set()):
    if auto_stop:                          # <-- auto_stop=True：等待触发事件后退出
        trigger_event.wait(timeout=0.005)
        if trigger_event.is_set():
            break
    else:                                  # <-- auto_stop=False：循环模式
        trigger_signal.wait(timeout=0.005)
        if trigger_signal.is_set():
            trigger_signal.clear()
            if on_trigger != "branch":
                _apply_on_trigger(on_trigger, target_task, ctx)
            _execute_flow(node.id, "trigger", ctx)  # 执行触发分支
            flow_done.set()                          # 通知轮询线程继续
            if trigger_event.is_set():
                break
            continue
        if trigger_event.is_set():
            break
```

**结论：A-13 已修复。** auto_stop 参数现在有明确的分支逻辑：
- **auto_stop=True**（默认）：触发后设置 `trigger_event`，轮询线程和主线程都退出，监视器停止。这是"触发一次后停止"的行为。
- **auto_stop=False**：轮询线程通过 `trigger_signal` 通知主线程，主线程执行触发分支后通过 `flow_done` 通知轮询线程继续检测，形成循环模式。每次触发后轮询线程会等待分支执行完成再继续，并支持 `recheck_delay_ms` 延迟重检。

---

## 总结

| Bug ID | 描述 | 修复状态 | 关键代码位置 |
|--------|------|----------|-------------|
| A-02 | seq_check/state_machine 缺少 cond 数据输入端口 | **已修复** | [control.py:99](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/control.py#L99), [control.py:120](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/control.py#L120) |
| A-03 | goto 跳转到已执行节点被 executed_set 阻止 | **已修复** | [engine.py:729](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L729) |
| A-13 | 监视器 auto_stop 完全无效 | **已修复** | [monitor.py:156-161](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L156-L161), [monitor.py:181-197](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L181-L197) |

三个1期P0 bug 均已在当前代码中修复。
        
          
所有1期P0关键bug已确认修复。现在让我完成交叉验证并输出最终汇总。
        
            
toolName: todo_write
            
status: success
          
Todos updated: 3 items
          
---

# 🔍 独立Bug审查 — 最终汇总报告

## 交叉验证结论

### 1期已采纳Bug修复验证

对1期Bug审查意见书中P0级关键bug进行了代码级验证：

| 1期编号 | 问题 | 修复状态 |
|---------|------|---------|
| A-01 | check_screen 函数名错误 | ✅ 已修复 |
| A-02 | seq_check/state_machine 缺少 cond 端口 | ✅ 已修复 |
| A-03 | goto 跳转被 executed_set 阻止 | ✅ 已修复 |
| A-05 | goto 合法回跳被循环检测阻止 | ✅ 已修复 |
| A-06/A-07 | 监视器/延迟 varRef 崩溃 | ✅ 已修复 |
| A-08 | condition cond_var 不解析 ${} | ✅ 已修复 |
| A-09 | string_op param_a/b/c 不解析 | ✅ 已修复 |
| A-13 | var_set boolean 转换错误 | ✅ 已修复 |
| A-14 | var_string replace 硬编码为空 | ✅ 已修复 |

**结论：1期已采纳的P0级bug均已正确修复，无需重新提出。**

### 2期文档交叉验证

- **后期考虑项（38项）**：我独立发现的 `check_results 线程安全问题` 与2期 P-32 一致 → **不提出**
- **拒绝项（12项）**：无重叠 → 不涉及
- **采纳项（63项）**：2期文档为今日编制，修复尚未执行，无需验证

---

## 独立发现的新Bug（不在1期/2期文档中）

以下3个bug是我独立审查中发现、且在1期Bug审查意见书和2期Bug汇总文档中均未被覆盖的新问题：

---

### 🔴🔴🔴 NEW-1：`_checkShowWhen` 不支持 `>=` 比较运算符 — fork/race 分支配置字段完全无法显示

**严重级别**：致命  
**影响模块**：控制（fork/race）、属性面板  
**文件**：[property.js:392-432](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L392-L432)

**问题描述**：

`_checkShowWhen` 函数仅支持 `field=value` 格式的等值匹配，使用 `indexOf('=')` 查找等号位置作为字段名与值的分隔符。当 showWhen 值包含 `>=` 运算符时（如 `"branch_count>=3"`），解析逻辑错误：

```javascript
// property.js:400
var eqIdx = seg.indexOf('=');  // "branch_count>=3" 中找到的是 >= 中的 =，位置13
currentField = seg.substring(0, eqIdx).trim();  // → "branch_count>"  ← 包含了 > 符号！
currentValues = [seg.substring(eqIdx + 1).trim()];  // → ["3"]
```

`allParams["branch_count>"]` 为 `undefined`，条件永远为 `false`。

**受影响字段**（共28个）：

| 节点 | 字段 | showWhen |
|------|------|----------|
| fork | branch_name_3 ~ branch_name_8 | `branch_count>=3` ~ `branch_count>=8` |
| fork | branch_affinity_3 ~ branch_affinity_8 | `branch_count>=3` ~ `branch_count>=8` |
| race | branch_name_3 ~ branch_name_8 | `branch_count>=3` ~ `branch_count>=8` |
| race | branch_affinity_3 ~ branch_affinity_8 | `branch_count>=3` ~ `branch_count>=8` |

**实际影响**：

- fork/race 节点设置3个以上分支时，**分支名称和绑核配置字段完全不显示**
- 属性面板中 `_branchIndex` 机制本可作为后备，但由于 `_checkShowWhen` 检查在 `_branchIndex` 检查**之前**执行（property.js:326-336），showWhen 失败后直接 `continue`，`_branchIndex` 永远不会被检查
- 用户无法为3个以上的分支设置自定义名称或CPU绑核

**与2期文档的关系**：

- B-48 修复了 `_checkShowWhen` 中 `rawVal===0` 的问题，但**未触及 `>=` 运算符支持**
- B-57 要求给 branch_affinity 添加 `showWhen: "branch_count>=3"`，但**即使添加了也无法工作**，因为 `>=` 运算符不被解析
- **此bug是B-57修复的前置条件**，不先修复 `>=` 支持，B-57的修复将无效

**修复方案**：

修改 `_checkShowWhen` 函数，在解析时优先匹配 `>=`、`<=`、`>`、`<` 运算符，再回退到 `=` 运算符：

```javascript
_checkShowWhen: function(showWhen, allParams) {
    if (!showWhen) return true;
    var segments = showWhen.split(',');
    var conditions = [];
    var currentField = null;
    var currentValues = [];
    var currentOp = '=';
    for (var i = 0; i < segments.length; i++) {
        var seg = segments[i].trim();
        var opMatch = seg.match(/^(.+?)(>=|<=|>|<|=)(.+)$/);
        if (opMatch) {
            if (currentField !== null) {
                conditions.push({field: currentField, op: currentOp, values: currentValues});
            }
            currentField = opMatch[1].trim();
            currentOp = opMatch[2];
            currentValues = [opMatch[3].trim()];
        } else if (currentField !== null) {
            currentValues.push(seg);
        }
    }
    if (currentField !== null) {
        conditions.push({field: currentField, op: currentOp, values: currentValues});
    }
    if (conditions.length === 0) return true;
    for (var c = 0; c < conditions.length; c++) {
        var cond = conditions[c];
        var rawVal = allParams[cond.field];
        var currentVal;
        if (rawVal === true || rawVal === false) {
            currentVal = String(rawVal);
        } else {
            currentVal = String(rawVal !== undefined && rawVal !== null ? rawVal : '');
        }
        for (var v = 0; v < cond.values.length; v++) {
            var val = cond.values[v];
            if (cond.op === '=' || !cond.op) {
                if (val === currentVal) return true;
                if (val === 'true' && rawVal === true) return true;
                if (val === 'false' && rawVal === false) return true;
            } else {
                var numVal = parseFloat(currentVal);
                var numTarget = parseFloat(val);
                if (!isNaN(numVal) && !isNaN(numTarget)) {
                    if (cond.op === '>=' && numVal >= numTarget) return true;
                    if (cond.op === '<=' && numVal <= numTarget) return true;
                    if (cond.op === '>' && numVal > numTarget) return true;
                    if (cond.op === '<' && numVal < numTarget) return true;
                }
            }
        }
    }
    return false;
},
```

---

### 🔴🔴 NEW-2：`_resolve_value` 不处理数组类型参数中的变量引用 — rect/region 变量引用完全失效

**严重级别**：严重  
**影响模块**：检测、监视器、预设（共9个参数）  
**文件**：[engine.py:347-349](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L347-L349)

**问题描述**：

`_resolve_value` 函数在开头对非字符串类型直接返回原值：

```python
def _resolve_value(value, ctx: ExecContext):
    if not isinstance(value, str):
        return value  # ← list 类型直接返回，不解析内部元素
```

当参数值为数组类型（如 `rect: ["${x}", "${y}", "${w}", "${h}"]`）时，函数直接返回原数组，数组内每个字符串元素中的 `${}` 变量引用**完全不会被解析**。

**受影响参数**（共9个，全部为 `type: "array", format: "region", varRef: True`）：

| 文件 | 节点 | 参数 | 行号 |
|------|------|------|------|
| [detection.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/detection.py#L13) | capture_source | region | L13 |
| [detection.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/detection.py#L32) | check_color | rect | L32 |
| [detection.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/detection.py#L63) | check_ocr | rect | L63 |
| [detection.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/detection.py#L95) | check_image | rect | L95 |
| [detection.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/detection.py#L125) | check_screen | region | L125 |
| [preset.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/preset.py#L34) | preset_find_click | rect | L34 |
| [preset.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/preset.py#L55) | preset_read_text | rect | L55 |
| [monitor.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/monitor.py#L14) | monitor_color | rect | L14 |
| [monitor.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/monitor.py#L47) | monitor_ocr | rect | L47 |

**实际影响**：

用户在前端通过 `$` 按钮为 rect/region 字段选择变量后，参数值变为 `["${start_x}", "${start_y}", "${width}", "${height}"]`。执行时引擎的 varRef 自动解析机制（engine.py:593/704）调用 `_resolve_value(params[key], ctx)` 处理每个标记了 varRef 的参数，但由于数组被直接跳过，下游 handler 收到的仍是字面字符串 `"${start_x}"` 等，导致：
- `int("${start_x}")` 抛出 ValueError 崩溃
- 或坐标计算使用字面值导致检测位置完全错误

**与2期文档的关系**：

- B-59 (region varRef 丢失值) 是**前端问题**——切换 varRef 模式时属性面板丢失原始值
- 本bug是**后端问题**——即使前端正确传递了数组变量引用，后端也无法解析
- 两者是不同层面的bug，本bug不在2期文档中

**修复方案**：

在 `_resolve_value` 函数开头添加对 `list` 类型的递归处理：

```python
def _resolve_value(value, ctx: ExecContext):
    if isinstance(value, list):
        return [_resolve_value(item, ctx) for item in value]
    if not isinstance(value, str):
        return value
    # ... 后续原有逻辑不变
```

---

### 🔴 NEW-3：普通节点异常后不继续执行后续节点 — 执行链断裂

**严重级别**：高  
**影响模块**：引擎核心（所有普通节点）  
**文件**：[engine.py:712-738](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L712-L738)

**问题描述**：

`_execute_node` 函数中，当普通节点（通过 `NODE_HANDLERS` 分发的节点）抛出异常时，except 块仅记录日志，不调用 `_execute_flow()` 继续执行后续节点，导致整条执行链在此断裂：

```python
# engine.py:712-724
try:
    handler(node, ctx)
except (FileNotFoundError, ImportError, TypeError, ValueError) as e:
    error_msg = f"节点 {node.type}({current_id}) 系统错误: {e}"
    print(f"[新引擎] {error_msg}")
    ctx.log_error(error_msg, node_id=current_id, error_type="system")
except Exception as e:
    error_msg = f"节点 {node.type}({current_id}) 执行异常: {e}"
    print(f"[新引擎] {error_msg}")
    ctx.log_error(error_msg, node_id=current_id, error_type="runtime")
finally:
    if _original_params is not None:
        node.params = _original_params

# 异常后无 _execute_flow() 调用 → 后续 goto_target 检查后直接 return
goto_target = branch_ctx._goto_target if branch_ctx else ctx._goto_target
if goto_target:
    ...
return  # ← 流程终止
```

**对比插件节点的处理**（engine.py:620-623）：

```python
except Exception as e:
    ctx.log_error(f"插件节点异常 {node.type}: {e}", node_id=str(node.id), error_type="plugin")
    _execute_flow(node.id, "fail" if _has_output_port(node, "fail") else "next", ctx)
    return
```

插件节点异常后**显式调用 `_execute_flow()`**，优先走 `fail` 端口，无 fail 端口则走 `next` 端口，确保流程不中断。

**实际影响**：

- 任何普通节点（鼠标点击、键盘输入、检测、变量操作等）抛出运行时异常后，**整条执行链立即终止**
- 如果节点有 `fail` 端口（如检测节点），用户期望异常时走 fail 分支，但实际上 fail 分支也不会执行
- 与插件节点的容错行为不一致，设计不对称

**修复方案**：

在 `_execute_node` 的 except 块中添加 `_execute_flow()` 调用，与插件节点保持一致：

```python
except (FileNotFoundError, ImportError, TypeError, ValueError) as e:
    error_msg = f"节点 {node.type}({current_id}) 系统错误: {e}"
    print(f"[新引擎] {error_msg}")
    ctx.log_error(error_msg, node_id=current_id, error_type="system")
    _execute_flow(current_id, "fail" if _has_output_port(node, "fail") else "next", ctx)
except Exception as e:
    error_msg = f"节点 {node.type}({current_id}) 执行异常: {e}"
    print(f"[新引擎] {error_msg}")
    ctx.log_error(error_msg, node_id=current_id, error_type="runtime")
    _execute_flow(current_id, "fail" if _has_output_port(node, "fail") else "next", ctx)
```

---

## 汇总统计

| 分类 | 数量 | 说明 |
|------|------|------|
| 独立发现的新Bug | **3** | 不在1期/2期文档中 |
| 与2期后期考虑重叠 | 1 | check_results线程安全(P-32) → 不提出 |
| 1期已采纳且已修复 | 9项已验证 | 无需重新提出 |

### 新Bug优先级排序

| 优先级 | 编号 | 问题 | 影响范围 |
|--------|------|------|---------|
| **P0** | NEW-1 | showWhen `>=` 运算符不支持 | fork/race 3+分支配置完全失效，且阻塞2期B-57修复 |
| **P1** | NEW-2 | _resolve_value 不处理数组变量引用 | 9个rect/region参数的变量引用功能完全失效 |
| **P1** | NEW-3 | 普通节点异常后执行链断裂 | 任何节点异常导致整条链终止，与插件节点行为不一致 |

### 修复依赖关系

```
NEW-1 (showWhen >=) ──→ B-57 (branch_affinity showWhen)
                        B-57的修复依赖NEW-1先修复，否则添加的showWhen条件无法生效
```
        
            
toolName: todo_write
            
status: success
          
Todos updated: 3 items
          
全部任务完成。以上是独立Bug审查的最终汇总报告，共发现 **3个新Bug**，均不在1期Bug审查意见书和2期Bug汇总文档中：

1. **NEW-1 (P0)**：`_checkShowWhen` 不支持 `>=` 运算符 — fork/race 分支配置字段完全无法显示，且是2期B-57修复的前置阻塞项
2. **NEW-2 (P1)**：`_resolve_value` 不处理数组类型参数中的变量引用 — 9个rect/region参数的varRef功能完全失效
3. **NEW-3 (P1)**：普通节点异常后不继续执行后续节点 — 执行链断裂，与插件节点容错行为不一致

1期已采纳的P0级bug经验证均已正确修复，无需重新提出。与2期后期考虑项重叠的check_results线程安全问题（P-32）按规则不提出。