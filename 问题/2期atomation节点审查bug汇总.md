# 自动化编辑器 2期 Bug 汇总文档

> **编制日期**: 2026-05-01
> **编制依据**: Bug修复意见书2期.md + 2期atomation节点审查.md + Bug审查意见书.md(1期) + atomation节点审查1~4
> **配套文档**: Bug修复意见书2期.md（决策与修复方案）
> **编号规则**: B-*=采纳, P-*=后期考虑, X-*=拒绝；B-01~B-24/P-01~P-24/X-01~X-09 对应2期意见书，B-25~/P-25~/X-10~ 为2期审查新发现

---

## 审查结论概览

| 分类              | 数量 | 说明                                         |
| ----------------- | ---- | -------------------------------------------- |
| ✅ 采纳（需修复） | 63   | 含2期意见书24项 + 2期审查新发现39项         |
| ⏳ 后期考虑       | 38   | 含2期意见书24项 + 2期审查新发现14项          |
| ❌ 拒绝           | 12   | 含2期意见书9项 + 2期审查新发现3项            |

---

## 一、✅ 采纳项

### 1.1 2期意见书已采纳项 (B-01 ~ B-24)

> 修复方案详见 Bug修复意见书2期.md，此处列出代码定位信息

| 编号 | 问题摘要 | 原始编号 | 代码位置 |
| ---- | -------- | -------- | -------- |
| B-01 | mouse_click 缺少"原地点击"功能 | D-01 | `automation/nodes/action.py` mouse_click 定义；`automation/handlers/action.py` _handle_mouse_click；`webui/modules/auto/nodes.js` mouse_click fallback |
| B-02 | string_op/var_string 参数名不透明 | D-13 | `automation/nodes/utility.py` string_op 定义；`automation/nodes/variable.py` var_string 定义；`automation/handlers/utility.py` _handle_string_op；`automation/handlers/variable.py` _handle_var_string；`webui/modules/auto/nodes.js` 两节点 fallback |
| B-03 | var_math abs/round 一元运算隐藏B端口 | D-14 | `automation/nodes/variable.py` var_math b 参数；`webui/modules/auto/nodes.js` var_math fallback |
| B-04 | logic_op not 一元运算隐藏B端口 | D-15 | `automation/nodes/utility.py` logic_op b 参数；`webui/modules/auto/nodes.js` logic_op fallback |
| B-05 | check_ocr match_number 缺 varRef | D-17 | `automation/nodes/detection.py` check_ocr match_number 定义；`webui/modules/auto/nodes.js` check_ocr fallback |
| B-06 | check_ocr cache_interval_ms 缺 varRef | D-18 | `automation/nodes/detection.py` check_ocr cache_interval_ms 定义；`webui/modules/auto/nodes.js` check_ocr fallback |
| B-07 | check_image template_path 缺 varRef | D-19 | `automation/nodes/detection.py` check_image template_path 定义；`webui/modules/auto/nodes.js` check_image fallback |
| B-08 | mouse_click store_hwnd_var 不在变量面板 | R-03 | `webui/modules/auto/editor-app.js` _collectStructuredVars 函数(~L379-443) |
| B-09 | check_screen state/threshold 含义不透明 | D-07 | `automation/nodes/detection.py` check_screen state/threshold 定义；`webui/modules/auto/nodes.js` check_screen fallback；`webui/modules/auto/property.js` 动态描述渲染 |
| B-10 | var_string substr 参数格式不直观 | D-10 | `automation/nodes/variable.py` var_string c 参数；`webui/modules/auto/nodes.js` var_string fallback |
| B-11 | key_action 缺少按键选择器 | D-03 | `webui/modules/auto/property.js` key 字段渲染；`webui/modules/auto/nodes.js` key_action fallback |
| B-12 | text_input 长文本用单行输入框 | D-04 | `webui/modules/auto/property.js` text 字段渲染逻辑 |
| B-13 | program_close force 描述不清晰 | D-06 | `automation/nodes/action.py` program_close force 参数 description |
| B-14 | math_func sin/cos 弧度无说明 | D-08 | `automation/nodes/utility.py` math_func sin/cos 参数 description |
| B-15 | if_else fallback 显示英文 true/false | D-09 | `webui/modules/auto/property.js` 布尔值渲染逻辑 |
| B-16 | 变量面板覆盖不全+刷新不触发 | D-38+D-50 | `webui/modules/auto/editor-app.js` _collectStructuredVars(~L379-443) + updateVarPanel 调用点 |
| B-17 | store_var 等输出变量标记为 varRef 误导 | D-30~34替代 | `webui/modules/auto/property.js` store_var/counter_var/store_hwnd_var/store_number 字段渲染 |
| B-18 | 粘贴不保留 _customName | D-36 | `webui/modules/auto/core.js` 粘贴逻辑 |
| B-19 | 撤销后属性面板不刷新 | D-39 | `webui/modules/auto/editor-app.js` undo 回调；需调用 AutomationProperty.render(null) |
| B-20 | 执行完成后不清除节点高亮 | D-41 | `webui/modules/auto/editor-app.js` 执行完成回调；需调用 clearAllHighlights() |
| B-21 | 不保存画布视口位置和缩放 | D-43 | `webui/modules/auto/core.js` 序列化/反序列化；`webui/modules/auto/editor-app.js` 视口状态 |
| B-22 | 工具箱搜索不支持中文 | D-46 | `webui/modules/auto/editor-app.js` 工具箱搜索逻辑 |
| B-23 | 工具箱节点没有 tooltip | D-47 | `webui/modules/auto/editor-app.js` 工具箱渲染 |
| B-24 | bookmark hwnd_var 缺 showWhen | D-57 | `automation/nodes/utility.py` bookmark hwnd_var 定义；`webui/modules/auto/nodes.js` bookmark fallback |

---

### 1.2 2期审查新采纳项 (B-25 ~ B-62)

#### 🔴🔴🔴 致命级 — 插件系统

**B-25** | 插件 check_results 键名缺少 node_id 前缀 — 数据输出端口完全失效
- **2期审查编号**: #1
- **文件**: `automation/engine.py:553-575`
- **问题**: `_handle_plugin_node` 将插件 `check_results` 直接写入 `ctx.check_results`，键名如 `"success"`，但下游节点通过数据连线读取时使用 `"{node_id}.success"` 格式，两者永远不匹配
- **影响**: 所有插件节点（email/notify/record/screenshot）的数据输出端口（success、filepath、error_message等）**完全无法被下游节点读取**
- **修复**: `ctx.safe_set_check_result(f"{node.id}.{k}", v)`

**B-26** | 插件参数不经过 _resolve_value — varRef 变量引用完全失效
- **2期审查编号**: #2
- **文件**: `automation/engine.py:553`
- **问题**: `_handle_plugin_node` 将 `node.params` 原样传递给插件，不解析 `${var}` 引用
- **影响**: 用户在插件节点的 varRef 字段（如 email 的 to/subject/body、screenshot 的 hwnd_var/save_dir）使用变量引用时，传入的是字面字符串 `"${my_var}"` 而非变量值
- **修复**: 根据 params_schema 中的 varRef 标记，对标记参数调用 `_resolve_value`
- **关联**: 需同步修改 `plugins/插件开发指南.md`，告知第三方作者 varRef 标记的作用

**B-27** | 插件节点始终走 next 流，不区分成功/失败
- **2期审查编号**: #3
- **文件**: `automation/engine.py:575`
- **问题**: 无论插件执行成功还是失败，都执行 `_execute_flow(node.id, "next", ctx)`
- **影响**: 邮件发送失败、OBS连接失败等场景下，自动化流程仍继续执行，可能导致逻辑错误
- **修复**: 成功走 success/next，失败走 fail/next（需在插件 manifest 中声明 flow 端口）

**B-28** | _automationEvents 导出时为 undefined — 后端事件回调可能完全失效
- **2期审查编号**: #4
- **文件**: `webui/modules/auto/events-handlers.js:127`
- **问题**: `export const _automationEvents = window._automationEvents` 在模块评估时执行，此时 `window._automationEvents` 尚未定义（`init()` 在 editor-app.js:2032 才调用），且 `const` 不可重新赋值
- **影响**: 如果后端 Python 通过导入的 `_automationEvents` 调用事件，节点执行高亮、状态更新等回调完全无法触发
- **修复**: 改为 getter 或延迟引用：`export function getAutomationEvents() { return window._automationEvents; }` 或 `export const _automationEvents = { onNodeStart: (...a) => window._automationEvents?.onNodeStart(...a), ... }`

#### 🔴🔴🔴 致命级 — 截图拾取器

**B-29** | 截图拾取器 img.onload 在 img.src 之后设置 — 坐标计算可能永远为 NaN
- **2期审查编号**: #5
- **文件**: `webui/modules/auto/tools.js:200-228`
- **问题**: data URI 可能同步加载完成，`onload` 在处理器绑定前已触发，`scaleX`/`scaleY` 永远为 `undefined`
- **影响**: 坐标拾取器计算出的所有坐标为 NaN，用户无法正确拾取坐标
- **修复**: 将 `img.onload = ...` 移到 `img.src = ...` 之前

**B-30** | 区域选择拖出图片后事件丢失 — 选区永远无法完成
- **2期审查编号**: #6
- **文件**: `webui/modules/auto/tools.js:294-319`
- **问题**: `mousemove`/`mouseup` 绑定在 `img` 元素上，拖出图片范围后事件不触发
- **影响**: 用户框选区域时鼠标移出图片，选区卡住且永远无法完成
- **修复**: 将 `mousemove`/`mouseup` 绑定到 `document`，在 `mouseup` 时移除监听

#### 🔴🔴 严重级 — varRef 未解析

**B-31** | check_ocr match_text 有 varRef 但 handler 未使用 _resolve_value
- **2期审查编号**: #7
- **后端定义**: `automation/nodes/detection.py:65` — `match_text` 有 `"varRef": True`
- **处理器**: `automation/handlers/detection.py:175` — `match_text=params.get("match_text", "")` 未解析
- **影响**: 用户在匹配文本字段使用 `${my_text}` 时，OCR 直接拿字面字符串匹配，永远匹配不到
- **修复**: `match_text = _resolve_value(ctx, params.get("match_text", ""))`

**B-32** | monitor_ocr match_text 同样未解析
- **2期审查编号**: #8
- **处理器**: `automation/handlers/monitor.py:63` — 同 B-31 问题
- **修复**: 同 B-31

**B-33** | seq_check max_retries 有 varRef 但 handler 未使用 _resolve_value
- **2期审查编号**: #9
- **后端定义**: `automation/nodes/control.py:108` — `max_retries` 有 `"varRef": True`
- **处理器**: `automation/handlers/control.py:225` — `int(node.params.get("max_retries", 100))` 未解析
- **影响**: 用户使用变量引用时 `int()` 转换抛出 ValueError
- **修复**: `int(_resolve_value(ctx, node.params.get("max_retries", "100")))`

**B-34** | monitor 全系列 recheck_delay_ms/max_triggers/auto_close_after_ms 有 varRef 但未解析
- **2期审查编号**: #10
- **处理器**: `automation/handlers/monitor.py:105-107` — 三个参数均直接 `params.get()` 未使用 `_resolve_value`
- **影响**: 这些参数使用变量引用时类型转换崩溃
- **修复**: 对三个参数统一使用 `_resolve_value`

**B-35** | monitor_timer repeat_count 有 varRef 但未解析
- **2期审查编号**: #11
- **处理器**: `automation/handlers/monitor.py:103` — `int(node.params.get("repeat_count", 0))` 未解析
- **修复**: 同 B-33

**B-36** | monitor_time hour/minute/second/check_interval/timeout 全部有 varRef 但未解析
- **2期审查编号**: #12
- **处理器**: `automation/handlers/monitor.py:210-215` — 全部 `params.get()` 直接获取
- **影响**: 时间监视器节点的变量引用功能完全失效
- **修复**: 对所有时间参数统一使用 `_resolve_value`

#### 🔴🔴 严重级 — 前端逻辑

**B-37** | var_string 前端 fallback 的 op 选项与后端严重不匹配
- **2期审查编号**: #13
- **后端**: `automation/nodes/variable.py:77` — `["concat", "replace", "upper", "lower", "trim", "substring", "split_index", "regex_extract"]`
- **前端**: `webui/modules/auto/nodes.js:398` — `['concat','substr','replace','split','regex_extract']`
- **差异**: 前端缺少 `upper`/`lower`/`trim`；`substring`→`substr`；`split_index`→`split`
- **影响**: 离线模式下无法使用大小写转换/去空格；选项名不匹配导致运行时错误
- **修复**: 前端 fallback 与后端定义完全对齐（此为 B-02 实现细节，需同步修复）
- **关联**: B-02（参数名拆分时需同步修正 op 选项）

**B-38** | serializeGraph 中 outputs 数组越界访问
- **2期审查编号**: #15
- **文件**: `webui/modules/auto/editor-app.js:664`
- **问题**: `originNode.outputs[link.origin_slot]` 无越界检查，动态分支节点端口数变化后可能崩溃
- **影响**: 复制/粘贴/保存动态分支节点时可能触发 JS 运行时错误
- **修复**: 添加越界检查 `if (originSlot < originNode.outputs.length)`

**B-39** | showWhen 隐藏字段变为可见时默认值未写回 node.properties
- **2期审查编号**: #16
- **文件**: `webui/modules/auto/property.js:333-334`
- **问题**: 只设置局部变量 `val` 用于显示，未将默认值写回 `node.properties[key]`
- **影响**: 用户不修改该字段就保存时，属性值为 `undefined` 而非默认值
- **修复**: 在显示默认值时同步写回 `node.properties[key] = defaultValue`

**B-40** | path 浏览按钮硬编码属性名，写入错误属性
- **2期审查编号**: #17
- **文件**: `webui/modules/auto/property.js:557` + `webui/modules/auto/editor-app.js:1530`
- **问题**: 浏览按钮只传 nodeId 不传 key，后端硬编码写入 `path` 或 `template_path`
- **影响**: 如果 path 字段的 key 不是 `path`/`template_path`，浏览按钮会将路径写入错误属性
- **修复**: 浏览按钮传递 `key` 参数，后端根据 `key` 写入对应属性

#### 🔴 高优先级 — 节点定义

**B-41** | fork + race 未添加 branch_name_3~8
- **2期审查编号**: #19
- **前端**: `webui/modules/auto/nodes.js:188-204` — `_expandDynamicBranches` 只添加 `branch_affinity_*`，未添加 `branch_name_3~8`
- **影响**: 分支数≥3 时无法为分支3+设置自定义名称
- **修复**: 在 `_expandDynamicBranches` 中同步添加 `branch_name_3` ~ `branch_name_8`

**B-42** | resume_branch 后端缺少 branchRef 属性
- **2期审查编号**: #20
- **后端**: `automation/nodes/control.py:269` — `target_branch` 只有 `varRef`，缺少 `branchRef`
- **对比**: stop_branch/pause_branch 都有 `branchRef: True`
- **影响**: 用户无法从下拉列表中选择分支，只能手动输入分支标识
- **修复**: 添加 `"branchRef": True`

**B-43** | check_ocr store_number label 与 store_var 重复
- **2期审查编号**: #21
- **前端**: `webui/modules/auto/nodes.js:302` — 两者 label 都是"存入变量"
- **影响**: 用户无法区分哪个存文本、哪个存数字
- **修复**: store_number label 改为"存入数字变量"

**B-44** | const_number + const_string 前端 fallback 缺少 varRef
- **2期审查编号**: #23
- **前端**: `webui/modules/auto/nodes.js:526/529` — `value` 字段无 `varRef:true`
- **_normalizeSchema**: 不自动为 `value` 键添加 varRef
- **影响**: 离线模式下常量节点值字段不显示变量选择器
- **修复**: 前端 fallback 中 `value` 字段添加 `varRef: true`

**B-45** | check_screen threshold 后端无 varRef 但 handler 使用 _resolve_value
- **2期审查编号**: #24
- **后端**: `automation/nodes/detection.py:124` — threshold 无 varRef
- **处理器**: `automation/handlers/detection.py:493` — 使用 `_resolve_value`
- **影响**: 前端不显示变量选择按钮，但后端实际支持变量引用，用户不知道可以用
- **修复**: 后端定义添加 `"varRef": True`

**B-46** | monitor_color tolerance/change_threshold/area_ratio_threshold 后端无 varRef 但 handler 使用 _resolve_value
- **2期审查编号**: #25
- **后端**: `automation/nodes/monitor.py:17-21` — 三个参数均无 varRef
- **处理器**: 使用 `_resolve_value`
- **影响**: 同 B-45
- **修复**: 后端定义添加 `"varRef": True`

#### 🔴 高优先级 — 前端交互

**B-47** | 右键菜单 catOrder 缺少 script_block 分类
- **2期审查编号**: #28
- **文件**: `webui/modules/auto/editor-app.js:1322` — `catOrder` 无 `script_block`
- **影响**: 右键菜单无法添加动作块节点
- **修复**: catOrder 数组中添加 `"script_block"`

**B-48** | _checkShowWhen 对 rawVal===0 处理错误
- **2期审查编号**: #29
- **文件**: `webui/modules/auto/property.js:414` — `String(rawVal || '')` 当 rawVal 为 0 时变成空字符串
- **影响**: showWhen 条件 `field=0` 永远无法匹配
- **修复**: 改为 `String(rawVal ?? '')` 或 `String(rawVal !== undefined && rawVal !== null ? rawVal : '')`

**B-49** | varRef 清空输入产生空引用 ${}
- **2期审查编号**: #30
- **文件**: `webui/modules/auto/property.js:1203-1205` — 清空时 `node.properties[key] = '${' + currentVal + '}'` 产生 `'${}'`
- **影响**: 清空变量引用后保存为 `${}`，后续解析出错
- **修复**: 清空时直接设为空字符串 `node.properties[key] = ''`

**B-50** | _syncInlineField 不支持 region/affinity/var_list 类型
- **2期审查编号**: #31
- **文件**: `webui/modules/auto/property.js:1152-1169` — 数组/对象类型 `field.value = value` 变成 `"[object Array]"`
- **影响**: 内联字段显示 `[object Array]` 或 `[object Object]`
- **修复**: 对数组/对象类型跳过内联显示或格式化输出

**B-51** | affinity 字段保存对象/字符串不一致
- **2期审查编号**: #32
- **保存时**: `webui/modules/auto/property.js:1351-1352` — `node.properties[key] = cur` 保存为对象
- **渲染时**: `webui/modules/auto/property.js:622-623` — `JSON.parse(aff)` 尝试从字符串解析
- **影响**: 可能导致运行时 JSON.parse 错误
- **修复**: 统一保存格式（建议保存为 JSON 字符串，渲染时解析）

**B-52** | 右键菜单 offsetHeight 在隐藏状态下为 0
- **2期审查编号**: #34
- **文件**: `webui/modules/auto/editor-app.js:1292-1293` — 菜单未添加 `show` 类时 `offsetHeight` 为 0，位置计算无效
- **影响**: 右键菜单位置计算错误
- **修复**: 先设为可见但透明，计算高度后再定位显示

**B-53** | 窗口/相对模式拾取不处理直接返回坐标
- **2期审查编号**: #35
- **文件**: `webui/modules/auto/tools.js:86-93` — `_startWindowCapturePick` 只处理 `status==='picking'`
- **对比**: `_startScreenCapturePick` 正确处理了直接返回坐标
- **影响**: 窗口/相对模式下如果后端直接返回坐标（非拾取流程），前端无法处理
- **修复**: 添加对直接返回坐标状态的处理

**B-54** | 轮询函数无超时/取消机制
- **2期审查编号**: #36
- **文件**: `webui/modules/auto/tools.js:112-157` — 递归 `setTimeout` 无最大重试次数，可能无限轮询
- **影响**: 后端无响应时前端无限轮询，占用资源
- **修复**: 添加最大重试次数和超时取消

**B-55** | _cancel_child_scopes 非递归版本遗漏嵌套作用域
- **2期审查编号**: #41
- **问题**: 嵌套 fork 场景下，取消外层 scope 不会递归取消内层 scope 的分支
- **影响**: 嵌套分支场景下产生僵尸分支
- **修复**: 改为递归取消所有子作用域

**B-56** | 插件后端注册表 inputs/outputs/params_schema 与前端不一致
- **2期审查编号**: #42
- **文件**: `automation/registry.py:78-109` — manifest.json 无 node_params/node_inputs/node_outputs，注册空定义
- **影响**: 后端引擎不知道插件有额外数据输出端口和参数定义，导致 B-25/B-26 问题
- **修复**: registry.py 从 manifest.json 读取完整定义，或从插件的 node.py 动态获取
- **关联**: B-25/B-26 的根因修复；需同步修改 `plugins/插件开发指南.md`

**B-57** | fork branch_affinity 字段缺少 showWhen 条件
- **2期审查编号**: #45
- **后端**: `automation/nodes/control.py:148-155` — 8个绑核字段全部无 showWhen
- **影响**: 2个分支时仍显示8个绑核设置，界面混乱
- **修复**: 添加 `showWhen` 条件，如 `branch_affinity_3` 的 showWhen 为 `"branch_count>=3"`

**B-58** | _checkShowChanges 过度重渲染
- **2期审查编号**: #46
- **文件**: `webui/modules/auto/property.js:1387-1398` — 只要存在任何 showWhen 字段就重渲染整个面板
- **影响**: 用户编辑输入框时丢失焦点和光标位置
- **修复**: 精确判断哪些字段受影响，只重渲染受影响的字段

**B-59** | region 字段 varRef 模式下丢失实际值
- **2期审查编号**: #47
- **文件**: `webui/modules/auto/property.js:521-547` — varRef 字符串被默认值 `[0,0,10,10]` 替代
- **影响**: 切换 varRef 模式后原有区域值丢失
- **修复**: varRef 模式下保留原始值，不使用默认值覆盖

**B-60** | nodeRef select/input 双向同步缺失
- **2期审查编号**: #48
- **文件**: `webui/modules/auto/property.js:1371-1384` — select 变更更新 input，但 input 变更不更新 select
- **影响**: 手动输入节点ID后下拉列表不同步
- **修复**: 添加 input 的 onchange 回调同步更新 select

**B-61** | _changeBranchCount 硬编码 min/max 与 schema 定义不一致
- **2期审查编号**: #49
- **文件**: `webui/modules/auto/property.js:613` — 硬编码 `min=2, max=8`，而渲染用 `schema.min || 2`
- **影响**: 如果 schema 中 min/max 不同，行为不一致
- **修复**: 从 schema 中读取 min/max，不硬编码

**B-62** | 插件重载不更新后端 PluginRegistry
- **2期审查编号**: #52
- **文件**: `core/plugin_manager.py:132-143` — 只清前端定义，后端旧定义残留
- **影响**: 重载插件后后端仍使用旧定义，可能导致参数/端口不一致
- **修复**: 重载时同步清除后端 registry 中的旧定义并重新注册

**B-63** | 遗留的 console.log 调试语句
- **2期审查编号**: #56
- **文件**: `webui/modules/auto/editor-app.js:1459/1464/1470/1475` — 多处 `[DEBUG]` 日志
- **影响**: 生产环境控制台输出调试信息
- **修复**: 移除或改为条件日志

---

## 二、⏳ 后期考虑项

### 2.1 2期意见书后期考虑项 (P-01 ~ P-24)

| 编号 | 问题摘要 | 原始编号 | 代码位置 |
| ---- | -------- | -------- | -------- |
| P-01 | mouse_scroll delta 值 120 不直观 | D-05 | `automation/nodes/action.py` mouse_scroll delta 参数 description |
| P-02 | var_compare 字符串比较回退不直观 | D-11 | `automation/nodes/variable.py` var_compare op 参数 |
| P-03 | check_color check_mode 对 sample_mode 缺 showWhen | D-21 | `automation/nodes/detection.py` check_color sample_mode 定义 |
| P-04 | check_screen region 缺 showWhen | D-22 | `automation/nodes/detection.py` check_screen region 定义 |
| P-05 | mouse_scroll 缺少坐标定位参数 | D-12 | `automation/nodes/action.py` mouse_scroll 定义 |
| P-06 | string_op concat 只能拼接两个字符串 | D-16 | `automation/nodes/utility.py` string_op 定义 |
| P-07 | check_image pyramid_levels 缺 varRef | D-20 | `automation/nodes/detection.py` check_image pyramid_levels 定义 |
| P-08 | check_image confidence 输出未在节点定义中声明 | D-23 | `automation/nodes/detection.py` check_image outputs 定义 |
| P-09 | preset_find_click template_path 缺 varRef | D-24 | `automation/nodes/preset.py` preset_find_click template_path 定义 |
| P-10 | preset_find_click 没有移动动画 | D-25 | `automation/handlers/preset.py` _handle_preset_find_click |
| P-11 | join target_fork_node_id nodeRef 不完善 | D-27 | `webui/modules/auto/property.js` nodeRef 字段渲染 |
| P-12 | call_script path 缺 varRef | D-28 | `automation/nodes/control.py` call_script path 定义 |
| P-13 | text_input 中文输入可能不稳定 | D-29 | `automation/handlers/action.py` _handle_text_input |
| P-14 | Ctrl+D 只支持单节点复制 | D-37 | `webui/modules/auto/editor-app.js` Ctrl+D 处理逻辑 |
| P-15 | 拖拽节点位置不可撤销 | D-40 | `webui/modules/auto/editor-app.js` 拖拽逻辑 + undoManager |
| P-16 | 模拟执行不按流程顺序 | D-42 | `webui/modules/auto/editor-app.js` 模拟执行逻辑 |
| P-17 | mouse_click vs mouse_move move_duration 默认值不一致 | D-44 | `automation/nodes/action.py` 两节点 move_duration 默认值 |
| P-18 | 坐标拾取 hwnd_var 被覆盖为原始句柄值 | D-48 | `webui/modules/auto/tools.js` 拾取回调 |
| P-19 | 拾取后自动修改 mode | D-49 | `webui/modules/auto/tools.js` 拾取回调 |
| P-20 | 工具箱缺少 plugin 分类 | D-45 | `webui/modules/auto/editor-app.js` TOOLBOX_CATEGORIES |
| P-21 | COMPLETED 状态下停止按钮行为异常 | D-52 | `webui/modules/auto/editor-app.js` 停止按钮逻辑 |
| P-22 | 新建画布保存确认逻辑可能中断 | D-53 | `webui/modules/auto/editor-app.js` 保存确认逻辑 |
| P-23 | 插件串行加载速度慢 | D-54 | `core/plugin_manager.py` 插件加载逻辑 |
| P-24 | fork 中多分支截图竞争 | D-56 | `automation/engine.py` fork 分支执行 |

---

### 2.2 2期审查新后期考虑项 (P-25 ~ P-38)

**P-25** | UndoManager 重复 push — 每次 addNodeToCenter 等操作 push 两次
- **2期审查编号**: #14
- **文件**: `webui/modules/auto/editor-app.js:2076-2078` + `webui/modules/auto/editor-app.js:632`
- **问题**: `onNodeAdded` 回调调用 `undoManager.push()`，同时 `addNodeToCenter` 也手动调用，导致 undo 一次只能回退"半个操作"
- **影响**: 用户按一次 Ctrl+Z 无法完全撤销一次添加节点操作
- **后期原因**: 需梳理所有 push 调用点，改动面较大

**P-26** | store_hwnd_var 未被 _pickSummaryKeys 跳过
- **2期审查编号**: #26
- **文件**: `webui/modules/auto/core.js:174` — skip 列表有 `store_var`、`store_number`，但无 `store_hwnd_var`
- **影响**: window_manage/program_open 节点上内联显示输出变量名，占用空间
- **后期原因**: 仅影响内联显示，不影响功能

**P-27** | 分类颜色多处定义不一致
- **2期审查编号**: #27
- **flow**: TOOLBOX_CATEGORIES `#ffffffff` vs catColors `#ff0000ff`
- **utility**: TOOLBOX_CATEGORIES `#d8d8d8ff` vs catColors `#adadadff`
- **文件**: `webui/modules/auto/editor-app.js:181-191` vs `webui/modules/auto/nodes.js:49`
- **后期原因**: 视觉差异微小，不影响功能

**P-28** | _graphDirty 在 undo/redo 后状态不正确
- **2期审查编号**: #33
- **文件**: `webui/modules/auto/editor-app.js:214-227`
- **问题**: undo 回到上次保存状态后仍显示为未保存
- **后期原因**: 需精确追踪 dirty 状态，改动面较大

**P-29** | ESC 键事件监听器泄漏
- **2期审查编号**: #37
- **文件**: `webui/modules/auto/tools.js:361-366` — 非 ESC 关闭 overlay 时处理器不移除，多次操作累积
- **后期原因**: 内存泄漏量极小，不影响功能

**P-30** | 拾取修改属性不触发撤销系统
- **2期审查编号**: #38
- **文件**: `webui/modules/auto/tools.js:397-446` — 直接修改 `node.properties`，Ctrl+Z 无法撤销
- **后期原因**: 需在拾取前后 push undo，改动需配合 UndoManager 重构

**P-31** | flashNode 多次调用产生多个未取消的 setTimeout
- **2期审查编号**: #39
- **文件**: `webui/modules/auto/events-handlers.js:55-63` — 无 clearTimeout 机制
- **后期原因**: 视觉效果问题，不影响功能

**P-32** | check_results 无锁并发读写
- **2期审查编号**: #40
- **问题**: `ctx.check_results` 字典在 fork 多分支中被并发读写，无锁保护
- **影响**: 可能导致运行时崩溃或数据不一致
- **后期原因**: Python GIL 在 CPython 中提供基本保护，实际崩溃概率低；加锁需评估性能影响

**P-33** | monitor_time 缺少 recheck_delay_ms/max_triggers/auto_close_after_ms
- **2期审查编号**: #44
- **对比**: monitor_color/monitor_ocr/monitor_timer 都有这些循环触发参数
- **影响**: 时间监视器触发后只能自动停止，无法配置循环触发行为
- **后期原因**: 功能增强，非 bug

**P-34** | 变量面板用户变量不去重
- **2期审查编号**: #50
- **文件**: `webui/modules/auto/editor-app.js:379-443` — 同名变量在列表中出现两次
- **后期原因**: 不影响功能正确性

**P-35** | 多处 try-catch 静默吞掉错误
- **2期审查编号**: #51
- **文件**: `webui/modules/auto/editor-app.js:36/48/108/124/327/400` — `catch(e) {}` 无任何日志输出
- **后期原因**: 不影响用户，仅影响调试

**P-36** | 插件 backendAction 未存入注册表，action 解析依赖脆弱命名约定
- **2期审查编号**: #53
- **文件**: `automation/registry.py:96` — 第三方插件可能无法正确路由
- **后期原因**: 当前内置插件命名规范一致，暂不影响；第三方插件生态发展后再改

**P-37** | color 字段不支持 varRef 输入
- **2期审查编号**: #55
- **问题**: 显示 VAR 标记但不提供变量选择按钮
- **后期原因**: 颜色变量引用需求极低

**P-38** | email 插件密码明文存储在节点参数中
- **2期审查编号**: #57
- **文件**: `plugins/email/node.js:14`
- **影响**: 分享脚本时密码泄露
- **后期原因**: 需设计加密存储方案，改动面大

---

## 三、❌ 拒绝项

### 3.1 2期意见书拒绝项 (X-01 ~ X-09)

| 编号 | 原始编号 | 问题摘要 | 拒绝原因 |
| ---- | -------- | -------- | -------- |
| X-01 | D-01原 | mouse_click hold_time 缺少 showWhen | 用户决策：hold_time 作为人类特征模拟延迟，不应隐藏。改为新增 mode=current 功能（见 B-01） |
| X-02 | D-02 | 延迟参数命名不统一（before_delay/after_delay/delay） | 用户决策：内部名混用但以中文形式展现，用户不受影响 |
| X-03 | D-35 | 内联字段修改后属性面板完全重新渲染 | 用户决策：渲染消耗很少，修改不频繁，不需优化 |
| X-04 | D-51 | 变量面板点击只复制不插入 | 用户决策：设计如此，直接插入容易误触覆盖 |
| X-05 | R-01 | mouse_move_rel 缺少 easing 参数 | 短距离缓动不可感知，增加复杂度收益低 |
| X-06 | R-06 | preset_find_click 没有数据输出端口 | 预设节点定位简化版，需完整输出用 check_image+mouse_click |
| X-07 | R-08 | 插件 node.js 无沙箱执行 | 架构选择，插件需完整 JS 能力，用户自行评估风险 |
| X-08 | R-10 | 重命名不允许"未命名脚本"但新建时默认就是 | 有意设计，防止保存默认名称导致混淆 |
| X-09 | R-12 | loop_while+检测/goto+循环/监视器+fork 联动问题 | 复杂边界场景组合问题，非独立 bug；1期已修复核心引擎问题 |

### 3.2 2期审查新拒绝项 (X-10 ~ X-12)

**X-10** | record 插件"开始录制"实际只启动回放缓冲
- **2期审查编号**: #18
- **文件**: `plugins/record/backend.py:72-75` — 调用 `cl.start_replay_buffer()` 而非 `cl.start_record()`
- **拒绝原因**: 用户决策：插件开发有意为之，回放缓冲是设计选择

**X-11** | notify 插件桌面弹窗阻塞引擎线程
- **2期审查编号**: #43
- **文件**: `plugins/notify/backend.py:155-201` — Win32 消息循环阻塞调用线程
- **拒绝原因**: 用户决策：插件开发有意为之，弹窗阻塞是设计选择

**X-12** | HTML 注入/XSS 风险
- **2期审查编号**: #54
- **文件**: `webui/modules/auto/property.js` — enum/number/string/path/var_list 字段值未使用 `_propEscapeHtml` 转义
- **拒绝原因**: 本地应用风险极低，非当前优先级

---

## 四、编号对照表

### 4.1 2期审查 #1~#57 → B-/P-/X- 编号映射

| 2期审查 | 编号 | 分类 | 备注 |
| ------- | ---- | ---- | ---- |
| #1 | B-25 | ✅采纳 | 插件 check_results 键名前缀 |
| #2 | B-26 | ✅采纳 | 插件 varRef 不解析 |
| #3 | B-27 | ✅采纳 | 插件始终走 next |
| #4 | B-28 | ✅采纳 | _automationEvents undefined |
| #5 | B-29 | ✅采纳 | img.onload 顺序 |
| #6 | B-30 | ✅采纳 | 区域选择事件丢失 |
| #7 | B-31 | ✅采纳 | check_ocr match_text 未解析 |
| #8 | B-32 | ✅采纳 | monitor_ocr match_text 未解析 |
| #9 | B-33 | ✅采纳 | seq_check max_retries 未解析 |
| #10 | B-34 | ✅采纳 | monitor recheck_delay_ms 等未解析 |
| #11 | B-35 | ✅采纳 | monitor_timer repeat_count 未解析 |
| #12 | B-36 | ✅采纳 | monitor_time 全部时间参数未解析 |
| #13 | B-37 | ✅采纳 | var_string op 选项不匹配（B-02 实现细节） |
| #14 | P-25 | ⏳后期 | UndoManager 重复 push |
| #15 | B-38 | ✅采纳 | serializeGraph outputs 越界 |
| #16 | B-39 | ✅采纳 | showWhen 默认值未写回 |
| #17 | B-40 | ✅采纳 | path 浏览按钮硬编码属性名 |
| #18 | X-10 | ❌拒绝 | record 插件回放缓冲（有意设计） |
| #19 | B-41 | ✅采纳 | fork/race 缺 branch_name_3~8 |
| #20 | B-42 | ✅采纳 | resume_branch 缺 branchRef |
| #21 | B-43 | ✅采纳 | check_ocr store_number label 重复 |
| #22 | — | ✅采纳 | var_string c 参数 showWhen（B-02 实现细节，不单独编号） |
| #23 | B-44 | ✅采纳 | const_number/const_string 前端缺 varRef |
| #24 | B-45 | ✅采纳 | check_screen threshold 后端缺 varRef |
| #25 | B-46 | ✅采纳 | monitor_color 后端缺 varRef |
| #26 | P-26 | ⏳后期 | store_hwnd_var 内联显示 |
| #27 | P-27 | ⏳后期 | 分类颜色不一致 |
| #28 | B-47 | ✅采纳 | 右键菜单缺 script_block |
| #29 | B-48 | ✅采纳 | _checkShowWhen rawVal===0 |
| #30 | B-49 | ✅采纳 | varRef 清空产生 ${} |
| #31 | B-50 | ✅采纳 | _syncInlineField 不支持数组/对象 |
| #32 | B-51 | ✅采纳 | affinity 保存/渲染不一致 |
| #33 | P-28 | ⏳后期 | _graphDirty undo/redo 状态 |
| #34 | B-52 | ✅采纳 | 右键菜单 offsetHeight |
| #35 | B-53 | ✅采纳 | 窗口拾取直接返回坐标 |
| #36 | B-54 | ✅采纳 | 轮询函数无超时 |
| #37 | P-29 | ⏳后期 | ESC 键监听器泄漏 |
| #38 | P-30 | ⏳后期 | 拾取不触发撤销 |
| #39 | P-31 | ⏳后期 | flashNode setTimeout |
| #40 | P-32 | ⏳后期 | check_results 并发读写 |
| #41 | B-55 | ✅采纳 | _cancel_child_scopes 非递归 |
| #42 | B-56 | ✅采纳 | 插件注册表空定义 |
| #43 | X-11 | ❌拒绝 | notify 弹窗阻塞（有意设计） |
| #44 | P-33 | ⏳后期 | monitor_time 缺循环触发参数 |
| #45 | B-57 | ✅采纳 | fork branch_affinity 缺 showWhen |
| #46 | B-58 | ✅采纳 | _checkShowChanges 过度渲染 |
| #47 | B-59 | ✅采纳 | region varRef 丢失值 |
| #48 | B-60 | ✅采纳 | nodeRef 双向同步缺失 |
| #49 | B-61 | ✅采纳 | _changeBranchCount 硬编码 |
| #50 | P-34 | ⏳后期 | 变量面板不去重 |
| #51 | P-35 | ⏳后期 | try-catch 静默吞错 |
| #52 | B-62 | ✅采纳 | 插件重载不更新后端 |
| #53 | P-36 | ⏳后期 | backendAction 注册表缺失 |
| #54 | X-12 | ❌拒绝 | HTML 注入/XSS（本地应用低风险） |
| #55 | P-37 | ⏳后期 | color 字段缺 varRef |
| #56 | B-63 | ✅采纳 | console.log 调试语句 |
| #57 | P-38 | ⏳后期 | email 密码明文存储 |

### 4.2 2期意见书 B-01~B-24 / P-01~P-24 / X-01~X-09 原始编号映射

| 2期编号 | 原始编号(1期) | 2期编号 | 原始编号(1期) |
| ------- | ------------- | ------- | ------------- |
| B-01 | D-01 | P-01 | D-05 |
| B-02 | D-13 | P-02 | D-11 |
| B-03 | D-14 | P-03 | D-21 |
| B-04 | D-15 | P-04 | D-22 |
| B-05 | D-17 | P-05 | D-12 |
| B-06 | D-18 | P-06 | D-16 |
| B-07 | D-19 | P-07 | D-20 |
| B-08 | R-03 | P-08 | D-23 |
| B-09 | D-07 | P-09 | D-24 |
| B-10 | D-10 | P-10 | D-25 |
| B-11 | D-03 | P-11 | D-27 |
| B-12 | D-04 | P-12 | D-28 |
| B-13 | D-06 | P-13 | D-29 |
| B-14 | D-08 | P-14 | D-37 |
| B-15 | D-09 | P-15 | D-40 |
| B-16 | D-38+D-50 | P-16 | D-42 |
| B-17 | D-30~34替代 | P-17 | D-44 |
| B-18 | D-36 | P-18 | D-48 |
| B-19 | D-39 | P-19 | D-49 |
| B-20 | D-41 | P-20 | D-45 |
| B-21 | D-43 | P-21 | D-52 |
| B-22 | D-46 | P-22 | D-53 |
| B-23 | D-47 | P-23 | D-54 |
| B-24 | D-57 | P-24 | D-56 |

| 2期编号 | 原始编号(1期) |
| ------- | ------------- |
| X-01 | D-01原 |
| X-02 | D-02 |
| X-03 | D-35 |
| X-04 | D-51 |
| X-05 | R-01 |
| X-06 | R-06 |
| X-07 | R-08 |
| X-08 | R-10 |
| X-09 | R-12 |

---

## 五、修复优先级排序

### P0 — 立即修复（核心功能完全失效）

| 编号 | 问题 | 涉及文件 |
| ---- | ---- | -------- |
| B-25 | 插件 check_results 键名前缀 | `automation/engine.py` |
| B-26 | 插件 varRef 不解析 | `automation/engine.py` + `plugins/插件开发指南.md` |
| B-27 | 插件始终走 next | `automation/engine.py` |
| B-28 | _automationEvents undefined | `webui/modules/auto/events-handlers.js` |
| B-29 | img.onload 顺序 | `webui/modules/auto/tools.js` |
| B-30 | 区域选择事件丢失 | `webui/modules/auto/tools.js` |
| B-31 | check_ocr match_text 未解析 | `automation/handlers/detection.py` |
| B-32 | monitor_ocr match_text 未解析 | `automation/handlers/monitor.py` |
| B-33 | seq_check max_retries 未解析 | `automation/handlers/control.py` |
| B-34 | monitor recheck_delay_ms 等未解析 | `automation/handlers/monitor.py` |
| B-35 | monitor_timer repeat_count 未解析 | `automation/handlers/monitor.py` |
| B-36 | monitor_time 全部时间参数未解析 | `automation/handlers/monitor.py` |

### P1 — 尽快修复（功能缺陷/用户体验障碍）

| 编号 | 问题 | 涉及文件 |
| ---- | ---- | -------- |
| B-01 | mouse_click 原地点击 | `automation/nodes/action.py` + `automation/handlers/action.py` + `webui/modules/auto/nodes.js` |
| B-02 | string_op/var_string 参数透明化 | `automation/nodes/utility.py` + `automation/nodes/variable.py` + handlers + `webui/modules/auto/nodes.js` |
| B-09 | check_screen state/threshold 透明化 | `automation/nodes/detection.py` + `webui/modules/auto/nodes.js` + `webui/modules/auto/property.js` |
| B-10 | var_string substr 格式改进 | `automation/nodes/variable.py` + `webui/modules/auto/nodes.js` |
| B-05/B-06 | check_ocr match_number/cache_interval_ms varRef | `automation/nodes/detection.py` + `webui/modules/auto/nodes.js` |
| B-16 | 变量面板覆盖+刷新 | `webui/modules/auto/editor-app.js` |
| B-37 | var_string op 选项对齐 | `webui/modules/auto/nodes.js`（B-02 实现细节） |
| B-38 | serializeGraph 越界 | `webui/modules/auto/editor-app.js` |
| B-39 | showWhen 默认值写回 | `webui/modules/auto/property.js` |
| B-40 | path 浏览按钮属性名 | `webui/modules/auto/property.js` + `webui/modules/auto/editor-app.js` |
| B-56 | 插件注册表空定义 | `automation/registry.py` + `plugins/插件开发指南.md` |

### P2 — 计划修复（体验优化/一致性问题）

| 编号 | 问题 |
| ---- | ---- |
| B-03/B-04 | 一元运算隐藏无效B端口 |
| B-07 | check_image template_path varRef |
| B-08 | mouse_click store_hwnd_var 变量面板 |
| B-11 | key_action 按键选择器 |
| B-12 | text_input textarea |
| B-13 | program_close force 描述 |
| B-14 | math_func sin/cos 弧度说明 |
| B-15 | if_else fallback 中文 |
| B-17 | store_var 等字段添加说明 |
| B-18 | 粘贴保留 _customName |
| B-19 | 撤销后属性面板刷新 |
| B-20 | 执行完成清除高亮 |
| B-21 | 保存画布视口 |
| B-22 | 工具箱中文搜索 |
| B-23 | 工具箱 tooltip |
| B-24 | bookmark hwnd_var showWhen |
| B-41 | fork/race branch_name_3~8 |
| B-42 | resume_branch branchRef |
| B-43 | check_ocr store_number label |
| B-44 | const_number/const_string 前端 varRef |
| B-45 | check_screen threshold 后端 varRef |
| B-46 | monitor_color 后端 varRef |
| B-47 | 右键菜单 script_block |
| B-48 | _checkShowWhen rawVal===0 |
| B-49 | varRef 清空 ${} |
| B-50 | _syncInlineField 数组/对象 |
| B-51 | affinity 保存/渲染不一致 |
| B-52 | 右键菜单 offsetHeight |
| B-53 | 窗口拾取直接返回 |
| B-54 | 轮询函数超时 |
| B-55 | _cancel_child_scopes 递归 |
| B-57 | fork branch_affinity showWhen |
| B-58 | _checkShowChanges 过度渲染 |
| B-59 | region varRef 丢失值 |
| B-60 | nodeRef 双向同步 |
| B-61 | _changeBranchCount 硬编码 |
| B-62 | 插件重载后端注册表 |
| B-63 | console.log 清理 |

---

*文档编制完毕。修复时参考本文档定位代码，参考 Bug修复意见书2期.md 了解修复方案。*
