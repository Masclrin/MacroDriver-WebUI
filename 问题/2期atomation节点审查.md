# 🔍 自动化项目全面 Bug 审查 — 最终汇总报告

> **审查方法**: 按 toolbox-categories 模块分类，逐模块读取对应代码，模拟用户全生命周期操作
> **交叉验证**: 已与 Bug审查意见书.md 对比，排除"后期考虑"(D-*)和"拒绝"(R-*)项
> **标记说明**: 🆕=审查意见书未涉及的新发现；✅=与审查意见书采纳项一致（补充细节）

---

## 一、🔴🔴🔴 致命级 Bug（核心功能完全失效）

### 1. 🆕 插件数据输出端口完全失效 — check_results 键名缺少 node_id 前缀

- **文件**: [engine.py:553-575](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L553-L575)
- **问题**: `_handle_plugin_node` 将插件的 `check_results` 直接写入 `ctx.check_results`，键名如 `"success"`，但下游节点通过数据连线读取时使用的键名格式为 `"{node_id}.success"`，两者永远不匹配
- **影响**: 所有插件节点（email/notify/record/screenshot）的数据输出端口（success、filepath、error_message等）**完全无法被下游节点读取**
- **修复**: `ctx.safe_set_check_result(f"{node.id}.{k}", v)`

### 2. 🆕 插件参数不经过 `_resolve_value` — varRef 变量引用完全失效

- **文件**: [engine.py:553](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L553)
- **问题**: `_handle_plugin_node` 将 `node.params` 原样传递给插件，不解析 `${var}` 引用
- **影响**: 用户在插件节点的 varRef 字段（如 email 的 to/subject/body、screenshot 的 hwnd_var/save_dir）使用变量引用时，传入的是字面字符串 `"${my_var}"` 而非变量值
- **修复**: 根据 params_schema 中的 varRef 标记，对标记参数调用 `_resolve_value`

### 3. 🆕 插件节点始终走 next 流，不区分成功/失败

- **文件**: [engine.py:575](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L575)
- **问题**: 无论插件执行成功还是失败，都执行 `_execute_flow(node.id, "next", ctx)`
- **影响**: 邮件发送失败、OBS连接失败等场景下，自动化流程仍继续执行，可能导致逻辑错误

### 4. 🆕 `_automationEvents` 导出时为 undefined — 后端事件回调可能完全失效

- **文件**: [events-handlers.js:127](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/events-handlers.js#L127)
- **问题**: `export const _automationEvents = window._automationEvents` 在模块评估时执行，此时 `window._automationEvents` 尚未定义（`init()` 在 editor-app.js:2032 才调用），且 `const` 不可重新赋值
- **影响**: 如果后端 Python 通过导入的 `_automationEvents` 调用事件，节点执行高亮、状态更新等回调完全无法触发

### 5. 🆕 截图拾取器 `img.onload` 在 `img.src` 之后设置 — 坐标计算可能永远为 NaN

- **文件**: [tools.js:200-228](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/tools.js#L200-L228)
- **问题**: data URI 可能同步加载完成，`onload` 在处理器绑定前已触发，`scaleX`/`scaleY` 永远为 `undefined`
- **影响**: 坐标拾取器计算出的所有坐标为 NaN，用户无法正确拾取坐标

### 6. 🆕 区域选择拖出图片后事件丢失 — 选区永远无法完成

- **文件**: [tools.js:294-319](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/tools.js#L294-L319)
- **问题**: `mousemove`/`mouseup` 绑定在 `img` 元素上，拖出图片范围后事件不触发
- **影响**: 用户框选区域时鼠标移出图片，选区卡住且永远无法完成

---

## 二、🔴🔴 严重级 Bug（主要功能不可用）

### 7. 🆕 `detection/check_ocr` — match_text 有 varRef 但 handler 未使用 _resolve_value

- **后端定义** [detection.py:65](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/detection.py#L65): `match_text` 有 `"varRef": True`
- **处理器** [detection.py:175](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L175): `match_text=params.get("match_text", "")` 未解析
- **影响**: 用户在匹配文本字段使用 `${my_text}` 时，OCR 直接拿字面字符串匹配，永远匹配不到

### 8. 🆕 `monitor/monitor_ocr` — match_text 同样未解析

- **处理器** [monitor.py:63](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L63): 同上问题

### 9. 🆕 `control/seq_check` — max_retries 有 varRef 但 handler 未使用 _resolve_value

- **后端定义** [control.py:108](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/control.py#L108): `max_retries` 有 `"varRef": True`
- **处理器** [control.py:225](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L225): `int(node.params.get("max_retries", 100))` 未解析
- **影响**: 用户使用变量引用时 `int()` 转换抛出 ValueError

### 10. 🆕 `monitor` 全系列 — recheck_delay_ms/max_triggers/auto_close_after_ms 有 varRef 但未解析

- **处理器** [monitor.py:105-107](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L105-L107): 三个参数均直接 `params.get()` 未使用 `_resolve_value`
- **影响**: 这些参数使用变量引用时类型转换崩溃

### 11. 🆕 `monitor/monitor_timer` — repeat_count 有 varRef 但未解析

- **处理器** [monitor.py:103](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L103): `int(node.params.get("repeat_count", 0))` 未解析

### 12. 🆕 `monitor/monitor_time` — hour/minute/second/check_interval/timeout 全部有 varRef 但未解析

- **处理器** [monitor.py:210-215](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L210-L215): 全部 `params.get()` 直接获取
- **影响**: 时间监视器节点的变量引用功能完全失效

### 13. 🆕 `variable/var_string` — 前端 fallback 的 op 选项与后端严重不匹配

- **后端** [variable.py:77](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/variable.py#L77): `["concat", "replace", "upper", "lower", "trim", "substring", "split_index", "regex_extract"]`
- **前端** [nodes.js:398](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L398): `['concat','substr','replace','split','regex_extract']`
- **差异**: 前端缺少 `upper`/`lower`/`trim`；`substring`→`substr`；`split_index`→`split`
- **影响**: 离线模式下无法使用大小写转换/去空格；选项名不匹配导致运行时错误

### 14. 🆕 UndoManager 重复 push — 每次 addNodeToCenter 等操作 push 两次

- **文件**: [editor-app.js:2076-2078](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L2076-L2078) + [editor-app.js:632](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L632)
- **问题**: `onNodeAdded` 回调调用 `undoManager.push()`，同时 `addNodeToCenter` 也手动调用，导致 undo 一次只能回退"半个操作"
- **影响**: 用户按一次 Ctrl+Z 无法完全撤销一次添加节点操作

### 15. 🆕 serializeGraph 中 outputs 数组越界访问

- **文件**: [editor-app.js:664](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L664)
- **问题**: `originNode.outputs[link.origin_slot]` 无越界检查，动态分支节点端口数变化后可能崩溃

### 16. 🆕 property.js — showWhen 隐藏字段变为可见时默认值未写回 node.properties

- **文件**: [property.js:333-334](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L333-L334)
- **问题**: 只设置局部变量 `val` 用于显示，未将默认值写回 `node.properties[key]`
- **影响**: 用户不修改该字段就保存时，属性值为 `undefined` 而非默认值

### 17. 🆕 property.js — path 浏览按钮硬编码属性名，写入错误属性

- **文件**: [property.js:557](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L557) + [editor-app.js:1530](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L1530)
- **问题**: 浏览按钮只传 nodeId 不传 key，后端硬编码写入 `path` 或 `template_path`
- **影响**: 如果 path 字段的 key 不是 `path`/`template_path`，浏览按钮会将路径写入错误属性

### 18. 🆕 record 插件"开始录制"实际只启动回放缓冲

- **文件**: [record/backend.py:72-75](file:///g:/宏引擎/宏驱动 webui 2.7.7/plugins/record/backend.py#L72-L75)
- **问题**: 调用 `cl.start_replay_buffer()` 而非 `cl.start_record()`
- **影响**: 用户期望点击"开始录制"后 OBS 开始录制，但实际只启动了回放缓冲

---

## 三、🔴 高优先级 Bug（影响用户体验或功能正确性）

### 19. 🆕 `control/fork` + `control/race` — _expandDynamicBranches 未添加 branch_name_3~8

- **前端** [nodes.js:188-204](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L188-L204): 只添加 `branch_affinity_*`，未添加 `branch_name_3~8`
- **影响**: 分支数≥3 时无法为分支3+设置自定义名称

### 20. 🆕 `control/resume_branch` — 后端缺少 branchRef 属性

- **后端** [control.py:269](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/control.py#L269): `target_branch` 只有 `varRef`，缺少 `branchRef`
- **对比**: stop_branch/pause_branch 都有 `branchRef: True`

### 21. 🆕 `detection/check_ocr` — store_number label 与 store_var 重复

- **前端** [nodes.js:302](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L302): 两者 label 都是"存入变量"
- **影响**: 用户无法区分哪个存文本、哪个存数字

### 22. 🆕 `variable/var_string` — c 参数 showWhen 缺少 op=split_index

- **前端** [nodes.js:399](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L399): showWhen 为 `'op=replace,op=split'`，缺少 `op=split_index`

### 23. 🆕 `utility/const_number` + `utility/const_string` — 前端 fallback 缺少 varRef

- **前端** [nodes.js:526/529](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L526): `value` 字段无 `varRef:true`
- **_normalizeSchema**: 不自动为 `value` 键添加 varRef
- **影响**: 离线模式下常量节点值字段不显示变量选择器

### 24. 🆕 `detection/check_screen` — threshold 后端无 varRef 但 handler 使用 _resolve_value

- **后端** [detection.py:124](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/detection.py#L124): 无 varRef
- **处理器** [detection.py:493](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L493): 使用 `_resolve_value`

### 25. 🆕 `monitor/monitor_color` — tolerance/change_threshold/area_ratio_threshold 后端无 varRef 但 handler 使用 _resolve_value

- **后端** [monitor.py:17-21](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/monitor.py#L17-L21): 无 varRef
- **处理器**: 使用 `_resolve_value`

### 26. 🆕 `store_hwnd_var` 未被 _pickSummaryKeys 跳过

- **文件** [core.js:174](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L174): skip 列表有 `store_var`、`store_number`，但无 `store_hwnd_var`
- **影响**: window_manage/program_open 节点上内联显示输出变量名，占用空间

### 27. 🆕 分类颜色多处定义不一致

- **flow**: TOOLBOX_CATEGORIES `#ffffffff` vs catColors `#ff0000ff`
- **utility**: TOOLBOX_CATEGORIES `#d8d8d8ff` vs catColors `#adadadff`
- **文件**: [editor-app.js:181-191](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L181-L191) vs [nodes.js:49](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L49)

### 28. 🆕 右键菜单 catOrder 缺少 script_block 分类

- **文件**: [editor-app.js:1322](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L1322): `catOrder` 无 `script_block`
- **影响**: 右键菜单无法添加动作块节点

### 29. 🆕 property.js — _checkShowWhen 对 `rawVal === 0` 处理错误

- **文件**: [property.js:414](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L414): `String(rawVal || '')` 当 rawVal 为 0 时变成空字符串
- **影响**: showWhen 条件 `field=0` 永远无法匹配

### 30. 🆕 property.js — varRef 清空输入产生空引用 `${}`

- **文件**: [property.js:1203-1205](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L1203-L1205): 清空时 `node.properties[key] = '${' + currentVal + '}'` 产生 `'${}'`

### 31. 🆕 property.js — _syncInlineField 不支持 region/affinity/var_list 类型

- **文件**: [property.js:1152-1169](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L1152-L1169): 数组/对象类型 `field.value = value` 变成 `"[object Array]"`

### 32. 🆕 property.js — affinity 字段保存对象/字符串不一致

- **保存时** [property.py:1351-1352](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.py#L1351-L1352): `node.properties[key] = cur` 保存为对象
- **渲染时** [property.py:622-623](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.py#L622-L623): `JSON.parse(aff)` 尝试从字符串解析

### 33. 🆕 editor-app.js — _graphDirty 在 undo/redo 后状态不正确

- **文件**: [editor-app.js:214-227](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L214-L227): undo 回到上次保存状态后仍显示为未保存

### 34. 🆕 editor-app.js — 右键菜单 offsetHeight 在隐藏状态下为 0

- **文件**: [editor-app.js:1292-1293](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L1292-L1293): 菜单未添加 `show` 类时 `offsetHeight` 为 0，位置计算无效

### 35. 🆕 tools.js — 窗口/相对模式拾取不处理直接返回坐标的情况

- **文件**: [tools.js:86-93](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/tools.js#L86-L93): `_startWindowCapturePick` 只处理 `status==='picking'`
- **对比**: `_startScreenCapturePick` 正确处理了直接返回坐标

### 36. 🆕 tools.js — 轮询函数无超时/取消机制

- **文件**: [tools.js:112-157](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/tools.js#L112-L157): 递归 `setTimeout` 无最大重试次数，可能无限轮询

### 37. 🆕 tools.js — ESC 键事件监听器泄漏

- **文件**: [tools.js:361-366](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/tools.js#L361-L366): 非 ESC 关闭 overlay 时处理器不移除，多次操作累积

### 38. 🆕 tools.js — 拾取修改属性不触发撤销系统

- **文件**: [tools.js:397-446](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/tools.js#L397-L446): 直接修改 `node.properties`，Ctrl+Z 无法撤销

### 39. 🆕 events-handlers.js — flashNode 多次调用产生多个未取消的 setTimeout

- **文件**: [events-handlers.js:55-63](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/events-handlers.js#L55-L63): 无 clearTimeout 机制

### 40. 🆕 编译器/引擎 — check_results 无锁并发读写

- **问题**: `ctx.check_results` 字典在 fork 多分支中被并发读写，无锁保护
- **影响**: 可能导致运行时崩溃或数据不一致

### 41. 🆕 编译器/引擎 — _cancel_child_scopes 非递归版本遗漏嵌套作用域

- **问题**: 嵌套 fork 场景下，取消外层 scope 不会递归取消内层 scope 的分支
- **影响**: 嵌套分支场景下产生僵尸分支

### 42. 🆕 插件后端注册表 inputs/outputs/params_schema 与前端不一致

- **文件**: [registry.py:78-109](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/registry.py#L78-L109): manifest.json 无 node_params/node_inputs/node_outputs，注册空定义
- **影响**: 后端引擎不知道插件有额外数据输出端口和参数定义

### 43. 🆕 notify 插件桌面弹窗阻塞引擎线程

- **文件**: [notify/backend.py:155-201](file:///g:/宏引擎/宏驱动 webui 2.7.7/plugins/notify/backend.py#L155-L201): Win32 消息循环阻塞调用线程
- **影响**: 弹窗显示期间整个自动化流程被阻塞

---

## 四、🟡 中优先级 Bug（设计不一致或体验不佳）

### 44. 🆕 `monitor/monitor_time` — 缺少 recheck_delay_ms/max_triggers/auto_close_after_ms

- **对比**: monitor_color/monitor_ocr/monitor_timer 都有这些循环触发参数
- **影响**: 时间监视器触发后只能自动停止，无法配置循环触发行为

### 45. 🆕 `control/fork` — branch_affinity 字段缺少 showWhen 条件

- **后端** [control.py:148-155](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/control.py#L148-L155): 8个绑核字段全部无 showWhen
- **影响**: 2个分支时仍显示8个绑核设置，界面混乱

### 46. 🆕 property.js — _checkShowChanges 过度重渲染

- **文件**: [property.js:1387-1398](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L1387-L1398): 只要存在任何 showWhen 字段就重渲染整个面板
- **影响**: 用户编辑输入框时丢失焦点和光标位置

### 47. 🆕 property.js — region 字段 varRef 模式下丢失实际值

- **文件**: [property.js:521-547](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L521-L547): varRef 字符串被默认值 `[0,0,10,10]` 替代

### 48. 🆕 property.js — nodeRef select/input 双向同步缺失

- **文件**: [property.js:1371-1384](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L1371-L1384): select 变更更新 input，但 input 变更不更新 select

### 49. 🆕 property.js — _changeBranchCount 硬编码 min/max 与 schema 定义不一致

- **文件**: [property.js:613](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L613): 硬编码 `min=2, max=8`，而渲染用 `schema.min || 2`

### 50. 🆕 editor-app.js — 变量面板用户变量不去重

- **文件**: [editor-app.js:379-443](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L379-L443): 同名变量在列表中出现两次

### 51. 🆕 editor-app.js — 多处 try-catch 静默吞掉错误

- **文件**: [editor-app.js:36/48/108/124/327/400](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L36): `catch(e) {}` 无任何日志输出

### 52. 🆕 插件重载不更新后端 PluginRegistry

- **文件**: [plugin_manager.py:132-143](file:///g:/宏引擎/宏驱动 webui 2.7.7/core/plugin_manager.py#L132-L143): 只清前端定义，后端旧定义残留

### 53. 🆕 插件 backendAction 未存入注册表，action 解析依赖脆弱命名约定

- **文件**: [registry.py:96](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/registry.py#L96): 第三方插件可能无法正确路由

---

## 五、💡 建议项（改进方向）

### 54. 🆕 property.js — 多处 HTML 注入/XSS 风险

- enum/number/string/path/var_list 字段值未使用 `_propEscapeHtml` 转义
- 虽然当前是本地应用风险较低，但应统一使用转义函数

### 55. 🆕 property.js — color 字段不支持 varRef 输入

- 显示 VAR 标记但不提供变量选择按钮

### 56. 🆕 editor-app.js — 遗留的 console.log 调试语句

- [editor-app.js:1459/1464/1470/1475](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L1459) 有多处 `[DEBUG]` 日志

### 57. 🆕 email 插件密码明文存储在节点参数中

- [email/node.js:14](file:///g:/宏引擎/宏驱动 webui 2.7.7/plugins/email/node.js#L14): 分享脚本时密码泄露

---

## 六、统计与优先级建议

| 严重程度 | 数量 | 说明 |
|---------|------|------|
| 🔴🔴🔴 致命 | 6 | 插件数据流失效、事件回调失效、坐标拾取崩溃 |
| 🔴🔴 严重 | 12 | varRef 不解析（8个）、选项不匹配、undo 重复 push、序列化越界、属性默认值、path 硬编码、录制功能错误 |
| 🔴 高优先级 | 25 | 分类不一致、showWhen 缺失、前端 fallback 缺 varRef、并发安全、属性面板同步 |
| 🟡 中优先级 | 10 | 循环触发参数缺失、重渲染、变量去重、插件重载 |
| 💡 建议 | 4 | XSS、color varRef、调试语句、密码安全 |

### 修复优先级建议

**P0 — 立即修复**:
1. 插件 check_results 键名前缀（#1）
2. 插件 _resolve_value（#2）
3. _automationEvents 导出问题（#4）
4. 截图拾取器 onload 顺序（#5）+ 区域选择事件绑定（#6）
5. check_ocr/monitor_ocr match_text _resolve_value（#7, #8）
6. monitor 全系列 varRef 参数 _resolve_value（#10-12）

**P1 — 尽快修复**:
7. var_string op 选项对齐（#13）
8. UndoManager 重复 push（#14）
9. property.js 默认值写回（#16）+ path 硬编码（#17）
10. record 插件 start_record（#18）
11. seq_check max_retries _resolve_value（#9）
12. 编译器/引擎并发安全（#40, #41）

**P2 — 计划修复**: 其余高优先级和中优先级项
        
全面审查已完成。以下是关键发现总结：

## 审查总结

本次独立审查共发现 **57 个问题**，经与 Bug审查意见书.md 交叉验证后：

- **排除了**与审查意见书"后期考虑"一致的 bug（如 mouse_move_rel 缺少 easing → R-01拒绝、mouse_scroll 缺少坐标 → D-12后期、varRef/varOutput 全局设计 → D-30~D-34后期、check_ocr cache_interval_ms → D-18后期 等）
- **保留了**审查意见书已采纳但本审查补充了更多细节的 bug（如 var_string op 不匹配、const_number/const_string 缺 varRef 等）
- **新发现了**审查意见书未涉及的 bug，最关键的包括：
  1. **插件系统 4 个致命 bug**（数据输出失效、varRef 不解析、始终走 next、注册表空定义）
  2. **_automationEvents 导出 undefined**（后端事件回调可能完全失效）
  3. **截图拾取器 2 个致命 bug**（onload 顺序、区域选择事件丢失）
  4. **check_ocr/monitor_ocr match_text 未解析**（比审查意见书中的 match_number 更严重）
  5. **monitor 全系列 recheck_delay_ms/max_triggers/auto_close_after_ms 未解析**
  6. **record 插件"开始录制"实际只启动回放缓冲**
  7. **UndoManager 重复 push**（undo 一次只回退半个操作）
  8. **property.js 默认值未写回 + path 硬编码属性名**
  9. **编译器/引擎 check_results 并发安全 + 嵌套 scope 遗漏**

这些新发现中有多个是**致命级别**的问题，建议优先修复插件系统和截图拾取器相关的 bug。