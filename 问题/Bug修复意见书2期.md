# 自动化编辑器 Bug 修复意见书 — 第2期

> **审查人**: 高级架构师
> **审查日期**: 2026-04-30
> **审查范围**: 1期审查意见书中标记为"⏳ 后期考虑"和"❌ 拒绝"的全部条目
> **审查原则**: 基于1期修复后的项目现状和用户反馈，重新评估剩余条目的优先级；采纳影响用户体验和数据正确性的问题；标记低优先级优化项为后期考虑；拒绝因设计取舍导致的问题并给出原因
> **用户画像**: 有一定编程能力和理解力的深度游戏玩家，有宏编辑经验，对英文复杂参数名理解困难，但理解参数名后一般能看懂其作用

---

## 审查结论概览

| 分类              | 数量 | 说明                                           |
| ----------------- | ---- | ---------------------------------------------- |
| ✅ 采纳（需修复） | 24   | 功能改进、UX优化、变量面板完善、描述/参数透明化 |
| ⏳ 后期考虑       | 26   | 非核心增强、低频场景、性能优化                 |
| ❌ 拒绝           | 9    | 设计取舍、架构选择、非bug建议项                |

---

## 一、✅ 采纳的 Bug（按模块分组）

### 1.1 节点功能改进

| 编号  | 原始编号 | 问题摘要                                                       | 审查意见                                                                                                                                                                                                                                                            |
| ----- | -------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B-01  | D-01     | `mouse_click` 缺少"原地点击"功能，必须填写坐标并移动鼠标     | **采纳**。当前 mouse_click 总是先移动到目标坐标再点击，但游戏场景中经常需要"先移动到位，等条件满足后再原地点击"。新增 `mode=current`（显示名"当前位置"），选择后隐藏 x/y/hwnd_var 参数，处理器跳过坐标解析和鼠标移动，直接在当前位置执行点击。修改文件：`automation/nodes/action.py`、`automation/handlers/action.py`、`webui/modules/auto/nodes.js` |
| B-02  | D-13     | `string_op`/`var_string` 参数名不透明，用户无法理解各操作用法 | **采纳**。当前 `param_a/b/c` 含义随操作变化但无任何提示，用户根本不知道怎么填。按操作类型拆分参数名并添加 showWhen 控制：concat 用 `concat_str`；replace 用 `search_str`+`replace_str`；substring 用 `start_pos`+`length`；split_index 用 `delimiter`+`index`。`var_string` 同步改进。修改文件：`automation/nodes/utility.py`、`automation/nodes/variable.py`、`automation/handlers/utility.py`、`automation/handlers/variable.py`、`webui/modules/auto/nodes.js` |
| B-03  | D-14     | `var_math` 的 `abs`/`round` 一元运算有二元输入，B 端口被忽略  | **采纳**。B 端口对一元运算无意义，显示着会误导用户以为 B 有效。添加 showWhen 隐藏 B 端口：`"showWhen": "op=add,op=sub,op=mul,op=div,op=mod,op=min,op=max"`。修改文件：`automation/nodes/variable.py`、`webui/modules/auto/nodes.js` |
| B-04  | D-15     | `logic_op` 的 `not` 一元运算有二元输入，B 端口被忽略          | **采纳**。同 B-03。添加 showWhen 隐藏 B 参数：`"showWhen": "op=and,op=or,op=xor,op=nand,op=nor"`。修改文件：`automation/nodes/utility.py`、`webui/modules/auto/nodes.js` |
| B-05  | D-17     | `check_ocr` 的 `match_number` 缺少 varRef                    | **采纳**。1期修复了监视器节点的 varRef 问题，但检测节点的 match_number 仍然不支持变量引用，造成不一致。用户在监视器中能用变量，在检测节点中不能。添加 `varRef: True`。修改文件：`automation/nodes/detection.py`、`webui/modules/auto/nodes.js` |
| B-06  | D-18     | `check_ocr` 的 `cache_interval_ms` 缺少 varRef               | **采纳**。同 B-05。添加 `varRef: True`。修改文件同上                                                                                                                                                                                                               |
| B-07  | D-19     | `check_image` 的 `template_path` 缺少 varRef                 | **采纳**。游戏场景中模板路径可能来自配置变量（如 `${boss_template}`），动态路径需求不低。添加 `varRef: True`。修改文件：`automation/nodes/detection.py`、`webui/modules/auto/nodes.js` |
| B-08  | R-03     | `mouse_click` 的 `store_hwnd_var` 输出不在变量面板中         | **采纳**。用户点击后可能需要在后续节点中引用点击位置的窗口句柄，但 store_hwnd_var 不在变量选择器中。方案B：保留变量存储方式，确保变量面板 `_collectStructuredVars` 能收集 `store_hwnd_var`。动作节点的数据输出应罕见，仅此特例。修改文件：`webui/modules/auto/property.js`、`webui/modules/auto/editor-app.js` |

### 1.2 描述与参数透明化

| 编号 | 原始编号 | 问题摘要                                                        | 审查意见                                                                                                                                                                                                                                  |
| ---- | -------- | --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| B-09 | D-07     | `check_screen` 的 `state` 和 `threshold` 含义不透明            | **采纳**。`frozen`（画面冻结）和 `帧差` 连开发者都不理解，用户更不可能看懂。修复方案：(1) `state` 枚举改为中文显示名：`black`→"黑屏"、`bright`→"白屏"、`frozen`→"画面冻结"；(2) `threshold` 的 description 根据 state 动态变化：black 时显示"亮度阈值(低于此值判定为黑屏)"，bright 时显示"亮度阈值(高于255-此值判定为白屏)"，frozen 时显示"差异阈值(低于此值判定为画面冻结)"。修改文件：`automation/nodes/detection.py`、`webui/modules/auto/nodes.js`、`webui/modules/auto/property.js` |
| B-10 | D-10     | `var_string` 的 `substr` 参数格式不直观，无示例               | **采纳**。`0,5` 格式没有任何提示，正常游戏用户根本想不到如何填写参数。修复方案：(1) 在 description 中添加示例："起始位置,长度 如 0,5"；(2) 配合 B-02 改进，substr 改为独立的 `start_pos`+`length` 参数，彻底消除格式歧义。修改文件：`automation/nodes/variable.py`、`webui/modules/auto/nodes.js` |
| B-11 | D-03     | `key_action` 缺少按键选择器                                    | **采纳**。用户需要查文档才知道按键名，体验差。添加可视化按键选择器（下拉或弹窗），列出常用按键及其名称。修改文件：`webui/modules/auto/property.js`、`webui/modules/auto/nodes.js` |
| B-12 | D-04     | `text_input` 长文本使用单行输入框                              | **采纳**。输入长文本时无法换行查看，改动极小（input→textarea），收益明显。对 `text` 字段使用 textarea 渲染。修改文件：`webui/modules/auto/property.js` |
| B-13 | D-06     | `program_close` 的 `force` 描述不清晰                          | **采纳**。当前描述"强制终止(跳过优雅关闭)"对用户不够直观。改为"强制结束进程(不等待程序响应)"。修改文件：`automation/nodes/action.py` |
| B-14 | D-08     | `math_func` 的 sin/cos 使用弧度无说明                          | **采纳**。用户默认角度制，弧度会导致计算错误。在 description 中添加"(弧度)"说明。修改文件：`automation/nodes/utility.py` |
| B-15 | D-09     | `if_else` 的 `fallback` 参数显示英文 true/false                | **采纳**。中文用户界面显示英文，不一致。前端渲染布尔值时统一显示中文"是/否"。修改文件：`webui/modules/auto/property.js` |

### 1.3 变量面板完善专项

| 编号 | 原始编号     | 问题摘要                                                      | 审查意见                                                                                                                                                                                                                                                                                                                                                                       |
| ---- | ------------ | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| B-16 | D-38+D-50   | 变量面板覆盖不全且刷新不触发                                 | **采纳**。合并两个问题为专项修复。**(1) 覆盖不全**：`_collectStructuredVars` 缺少 `utility/math_op`、`utility/math_func`、`utility/logic_op`、`utility/compare`、`utility/string_op`、`utility/condition`、`utility/bookmark`、`preset/preset_read_text`、`monitor/monitor_ocr`、`control/race_win` 等节点的 result/输出变量。**(2) 刷新不触发**：删除节点、撤销/重做、粘贴节点、修改 store_var/name 属性、连线/断开数据端口后，变量面板不更新。修复方案：统一收集所有有 result 输出或 store_var 的节点变量；在关键操作后触发 `updateVarPanel()` 刷新。修改文件：`webui/modules/auto/property.js`、`webui/modules/auto/editor-app.js` |
| B-17 | D-30~34替代 | `store_var`/`counter_var` 等输出变量标记为 varRef 误导用户    | **采纳**（降级方案）。不引入 `varOutput` 标记（改动面大），改为在前端渲染时对 `store_var`、`counter_var`、`store_hwnd_var`、`store_number` 等输出变量字段添加"存入变量"说明文字，区分"引用已有变量"和"定义新变量名"。修改文件：`webui/modules/auto/property.js` |

### 1.4 画布交互优化

| 编号 | 原始编号 | 问题摘要                           | 审查意见                                                                                                                                                                       |
| ---- | -------- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| B-18 | D-36     | 粘贴节点不保留 `_customName`     | **采纳**。用户给节点重命名后粘贴，名称丢失，困惑。粘贴逻辑应保留 `_customName` 属性。修改文件：`webui/modules/auto/core.js`                                               |
| B-19 | D-39     | 撤销后属性面板不刷新               | **采纳**。1期 A-48 修复了撤销后重建节点但属性面板不刷新的核心问题，但面板刷新仍需在撤销操作完成后调用 `AutomationProperty.render(null)` 清空面板。修改文件：`webui/modules/auto/editor-app.js` |
| B-20 | D-41     | 执行完成后不清除节点高亮           | **采纳**。执行完成后节点仍高亮为"执行中"状态，改动极小，体验提升明显。在执行完成回调中调用 `clearAllHighlights()`。修改文件：`webui/modules/auto/editor-app.js`       |
| B-21 | D-43     | 不保存画布视口位置和缩放级别       | **采纳**。每次打开脚本都要重新定位和缩放，烦人。在保存/加载脚本时序列化视口状态（scrollX, scrollY, zoom）。修改文件：`webui/modules/auto/core.js`、`webui/modules/auto/editor-app.js` |

### 1.5 工具箱与节点发现性

| 编号 | 原始编号 | 问题摘要                       | 审查意见                                                                                                                                                                                   |
| ---- | -------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| B-22 | D-46     | 工具箱搜索不支持中文/拼音      | **采纳**。中文用户搜中文节点名搜不到，体验差。搜索逻辑应同时匹配 display_name（中文）和 type（英文），支持拼音首字母匹配。修改文件：`webui/modules/auto/editor-app.js` |
| B-23 | D-47     | 工具箱节点没有 tooltip          | **采纳**。新用户不知道节点用途，悬停时显示简要说明。修改文件：`webui/modules/auto/editor-app.js`                                                                 |
| B-24 | D-57     | `bookmark` 的 `hwnd_var` 缺少 showWhen | **采纳**。1期 A-15 实现了 bookmark 的 mode/hwnd_var 功能，但 showWhen 未同步添加。添加 `showWhen: "mode_1=window,mode_1=relative"` 等。修改文件：`automation/nodes/utility.py`、`webui/modules/auto/nodes.js` |

---

## 二、⏳ 后期考虑的 Bug

### 2.1 UX/描述优化（优先级较低）

| 编号 | 原始编号 | 问题摘要                                            | 审查意见                                                                                                   |
| ---- | -------- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| P-01 | D-05     | `mouse_scroll` delta 值 120 不直观                  | **后期考虑**。120 是 Windows WHEEL_DELTA 标准值，可在 tooltip 中添加说明，非紧急                          |
| P-02 | D-11     | `var_compare` 字符串比较回退不直观                  | **后期考虑**。数值优先比较是合理的设计选择，非bug                                                          |
| P-03 | D-21     | `check_color` 的 `check_mode` 对 `sample_mode` 缺少 showWhen 限制 | **后期考虑**。不影响功能正确性，仅显示优化                                                                 |
| P-04 | D-22     | `check_screen` 的 `region` 缺少 showWhen            | **后期考虑**。全屏模式默认值即可，非核心                                                                   |

### 2.2 功能增强（当前设计简化，非缺陷）

| 编号 | 原始编号 | 问题摘要                                                | 审查意见                                                                                                         |
| ---- | -------- | ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| P-05 | D-12     | `mouse_scroll` 缺少坐标定位参数                         | **后期考虑**。用户可先移动再滚动，workaround 存在                                                               |
| P-06 | D-16     | `string_op` 的 `concat` 只能拼接两个字符串              | **后期考虑**。可链式使用，设计简化                                                                               |
| P-07 | D-20     | `check_image` 的 `pyramid_levels` 缺少 varRef           | **后期考虑**。`_normalizeSchema` 已自动处理                                                                     |
| P-08 | D-23     | `check_image` 的 `confidence` 输出未在节点定义中声明    | **后期考虑**。可通过 `${nodeID.confidence}` 变量引用获取                                                         |
| P-09 | D-24     | `preset_find_click` 的 `template_path` 缺少 varRef      | **后期考虑**。预设节点定位是简化版，需动态路径应使用 check_image + mouse_click 组合                              |
| P-10 | D-25     | `preset_find_click` 没有移动动画                         | **后期考虑**。防作弊是特殊场景                                                                                   |
| P-11 | D-27     | `join` 的 `target_fork_node_id` nodeRef 实现不完善      | **后期考虑**。基本功能可用                                                                                       |
| P-12 | D-28     | `call_script` 的 `path` 缺少 varRef                     | **后期考虑**。脚本路径通常固定                                                                                   |
| P-13 | D-29     | `text_input` 中文输入可能不稳定                          | **后期考虑**。SendInput Unicode 是标准方式，大多数应用支持。个别应用不兼容是已知限制                              |

### 2.3 画布/编辑器交互优化

| 编号 | 原始编号 | 问题摘要                                | 审查意见                                                                                             |
| ---- | -------- | --------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| P-14 | D-37     | Ctrl+D 只支持单节点复制                 | **后期考虑**。Ctrl+C/V 已支持多选，Ctrl+D 是快捷增强                                               |
| P-15 | D-40     | 拖拽节点位置不可撤销                     | **后期考虑**。需改 undo 系统，在拖拽开始/结束时 push undo，改动较大                                 |
| P-16 | D-42     | 模拟执行不按流程顺序                     | **后期考虑**。模拟执行功能未开放给用户（仅在无后端时降级使用），不影响实际执行                       |
| P-17 | D-44     | `mouse_click` vs `mouse_move` 的 `move_duration` 默认值不一致 | **后期考虑**。点击场景瞬移更合理，移动场景平滑更合理，各有道理                           |
| P-18 | D-48     | 坐标拾取 `hwnd_var` 被覆盖为原始句柄值  | **后期考虑**。拾取工具的设计意图是填入实际值，变量引用需手动恢复                                     |
| P-19 | D-49     | 拾取后自动修改 mode                      | **后期考虑**。自动设置 mode 是拾取工具的预期行为                                                     |

### 2.4 其他后期考虑项

| 编号 | 原始编号 | 问题摘要                                   | 审查意见                                                                                             |
| ---- | -------- | ------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| P-20 | D-45     | 工具箱缺少 plugin 分类                     | **后期考虑**。插件通过底部面板添加，功能可用                                                         |
| P-21 | D-52     | COMPLETED 状态下停止按钮行为异常           | **后期考虑**。已完成时停止按钮意义不大                                                               |
| P-22 | D-53     | 新建画布保存确认逻辑可能中断               | **后期考虑**。边界场景                                                                                       |
| P-23 | D-54     | 插件串行加载速度慢                         | **后期考虑**。当前插件量较小，性能影响不大；后续插件增多时可改为并行加载                             |
| P-24 | D-56     | fork 中多分支截图竞争                      | **后期考虑**。帧差异通常在毫秒级，实际影响小                                                         |

---

## 三、❌ 拒绝的 Bug

| 编号 | 原始编号 | 问题摘要                                           | 拒绝原因                                                                                                                                                              |
| ---- | -------- | -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| X-01 | D-01原   | `mouse_click` 的 `hold_time` 缺少 showWhen         | 用户决策：hold_time 类似鼠标短单击的少量延迟，作为人类特征模拟，不应隐藏。改为新增 mode=current 功能（见 B-01）                                                    |
| X-02 | D-02     | 延迟参数命名不统一（before_delay/after_delay/delay） | 用户决策：虽然内部名混用，但在 app 中以中文形式友好展现，用户不受影响，暂不修复                                                                                      |
| X-03 | D-35     | 内联字段修改后属性面板完全重新渲染                   | 用户决策：一个属性面板渲染消耗很少，内联字段修改不频繁，不需要优化                                                                                                    |
| X-04 | D-51     | 变量面板点击只复制不插入                            | 用户决策：设计如此。直接插入容易导致用户误触覆盖当前输入，复制到剪贴板更安全                                                                                          |
| X-05 | R-01     | `mouse_move_rel` 缺少 easing 参数                  | 相对移动通常距离很短（几像素到几十像素），缓动效果在短距离下几乎不可感知。添加 easing 增加复杂度但收益极低，是设计取舍                                                  |
| X-06 | R-06     | `preset_find_click` 没有数据输出端口                | 预设节点的设计定位是"一键完成常见操作"的简化版。需要完整数据输出应使用 `check_image` + `mouse_click` 组合。这是功能分层的取舍                                          |
| X-07 | R-08     | 插件 `node.js` 无沙箱执行                          | 已知的架构选择。插件系统需要完整的 JS 能力（DOM 操作、网络请求等），添加沙箱会大幅限制插件功能。用户安装第三方插件时应自行评估风险，与浏览器扩展的风险模型一致        |
| X-08 | R-10     | 重命名不允许"未命名脚本"但新建时默认就是             | 有意设计，防止用户保存默认名称的脚本导致混淆。默认名称是临时占位符，保存时应要求用户起有意义的名称                                                                    |
| X-09 | R-12     | `loop_while`+检测/`goto`+循环/监视器+`fork` 联动问题 | 这些是复杂边界场景的组合问题，不是独立 bug。1期已修复核心引擎问题（A-03 goto executed_set、A-04 check_results 重置、A-38 条件重新执行），大部分联动场景应已正常。建议先做回归测试验证，如仍有问题再单独提bug |

---

## 四、修复优先级排序（采纳项）

### P1 — 尽快修复（功能缺陷/用户理解障碍）

| 编号       | 问题                                        | 修复建议                                                                                                   |
| ---------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| B-01       | mouse_click 缺少"原地点击"功能              | 新增 `mode=current`，隐藏坐标参数，处理器跳过移动直接点击                                                 |
| B-02       | string_op/var_string 参数名不透明           | 按操作类型拆分参数名 + showWhen 控制，同步改进 var_string                                                  |
| B-09       | check_screen state/threshold 含义不透明     | state 枚举中文显示名 + threshold description 根据 state 动态变化                                           |
| B-10       | var_string substr 参数格式无示例            | 配合 B-02 改为独立 start_pos+length 参数                                                                  |
| B-05/B-06  | check_ocr match_number/cache_interval 缺varRef | 添加 `varRef: True`                                                                                       |
| B-16       | 变量面板覆盖不全+刷新不触发                 | 统一收集所有输出变量 + 关键操作后触发 updateVarPanel()                                                     |

### P2 — 计划修复（体验优化/一致性问题）

| 编号           | 问题                                  | 修复建议                                                     |
| -------------- | ------------------------------------- | ------------------------------------------------------------ |
| B-07           | check_image template_path 缺varRef    | 添加 `varRef: True`                                         |
| B-03/B-04      | 一元运算隐藏无效的B端口               | 添加 showWhen 条件                                           |
| B-08           | mouse_click store_hwnd_var 变量面板    | _collectStructuredVars 收集 store_hwnd_var                  |
| B-11           | key_action 按键选择器                 | 添加可视化按键选择器                                         |
| B-12           | text_input 长文本 textarea            | 对 text 字段使用 textarea 渲染                               |
| B-13           | program_close force 描述优化          | 改为"强制结束进程(不等待程序响应)"                           |
| B-14           | math_func sin/cos 弧度说明            | description 添加"(弧度)"                                    |
| B-15           | if_else fallback 显示中文             | 布尔值统一显示"是/否"                                        |
| B-17           | store_var 等字段添加"存入变量"说明    | 前端渲染时对输出变量字段添加说明文字                         |
| B-18           | 粘贴保留 _customName                  | 粘贴逻辑保留 _customName 属性                                |
| B-19           | 撤销后属性面板刷新                    | 撤销完成后调用 AutomationProperty.render(null)              |
| B-20           | 执行完成后清除节点高亮                | 完成回调中调用 clearAllHighlights()                         |
| B-21           | 保存画布视口位置和缩放                | 序列化/反序列化视口状态                                      |
| B-22           | 工具箱搜索支持中文                    | 搜索同时匹配 display_name 和 type，支持拼音                 |
| B-23           | 工具箱节点 tooltip                    | 悬停显示简要说明                                             |
| B-24           | bookmark hwnd_var 缺 showWhen         | 添加 showWhen 条件                                           |

---

## 五、跨模块通用修复建议

### 5.1 参数透明化统一规范

**问题**: 多个节点的参数名使用英文缩写或技术术语（如 `frozen`、`param_a`、`delta`），对中文用户不友好。

**修复方案**: 建立参数命名规范：
1. 节点定义中 `enum` 选项使用英文内部名 + 中文 `display_name`
2. `description` 使用中文，对技术参数添加示例
3. 不同操作共用参数时，使用独立参数名 + `showWhen` 控制，避免一个参数名覆盖多种含义
4. 一元运算的无效端口必须通过 `showWhen` 隐藏

### 5.2 变量面板完善方案

**问题**: 变量面板的变量收集和刷新机制不完整。

**修复方案**:

**(1) 收集完善**：`_collectStructuredVars` 应统一遍历所有节点，按以下规则收集变量：
- 有 `result` 数据输出端口的节点 → 收集 `nodeID.result`，类型根据端口类型推断
- 有 `store_var`/`store_number`/`store_hwnd_var` 参数的节点 → 收集对应变量
- 有 `counter_var` 参数的节点 → 收集对应变量
- `utility/bookmark` → 收集 `rect_1/2/3`
- `control/race_win` → 收集 `winner_branch`

**(2) 刷新机制**：在以下操作后调用 `updateVarPanel()` 刷新变量面板：
- 删除节点
- 撤销/重做
- 粘贴节点
- 修改节点的 `store_var`/`name`/`counter_var` 等属性
- 连线/断开数据端口（影响上游变量可见性）

### 5.3 string_op/var_string 改进方案

**问题**: 两套字符串操作节点参数名不透明，用户无法理解各操作用法。

**修复方案**: 按操作类型拆分参数名，通过 `showWhen` 控制显示：

#### utility/string_op 新参数定义

```python
"params_schema": {
    "op": {"type": "string", "enum": ["concat", "replace", "upper", "lower", "trim", "substring", "split_index"], "default": "concat", "description": "操作类型"},
    "input_str": {"type": "string", "default": "", "description": "输入字符串", "varRef": True},
    "concat_str": {"type": "string", "default": "", "description": "要拼接的字符串", "showWhen": "op=concat", "varRef": True},
    "search_str": {"type": "string", "default": "", "description": "要查找的文本", "showWhen": "op=replace", "varRef": True},
    "replace_str": {"type": "string", "default": "", "description": "替换为", "showWhen": "op=replace", "varRef": True},
    "start_pos": {"type": "number", "default": 0, "description": "起始位置(从0开始)", "showWhen": "op=substring"},
    "length": {"type": "number", "default": 0, "description": "截取长度(0=到末尾)", "showWhen": "op=substring"},
    "delimiter": {"type": "string", "default": ",", "description": "分隔符", "showWhen": "op=split_index", "varRef": True},
    "index": {"type": "number", "default": 0, "description": "取第几段(从0开始)", "showWhen": "op=split_index"},
}
```

#### variable/var_string 新参数定义

```python
"params_schema": {
    "op": {"type": "string", "enum": ["concat", "replace", "upper", "lower", "trim", "substring", "split_index", "regex_extract"], "default": "concat", "description": "操作类型"},
    "a": {"type": "string", "default": "", "description": "输入字符串(支持${var})", "varRef": True},
    "concat_str": {"type": "string", "default": "", "description": "要拼接的字符串", "showWhen": "op=concat", "varRef": True},
    "search_str": {"type": "string", "default": "", "description": "要查找的文本", "showWhen": "op=replace", "varRef": True},
    "replace_str": {"type": "string", "default": "", "description": "替换为", "showWhen": "op=replace", "varRef": True},
    "start_pos": {"type": "number", "default": 0, "description": "起始位置(从0开始)", "showWhen": "op=substring"},
    "length": {"type": "number", "default": 0, "description": "截取长度(0=到末尾)", "showWhen": "op=substring"},
    "delimiter": {"type": "string", "default": ",", "description": "分隔符", "showWhen": "op=split_index", "varRef": True},
    "index": {"type": "number", "default": 0, "description": "取第几段(从0开始)", "showWhen": "op=split_index"},
    "regex_pattern": {"type": "string", "default": "", "description": "正则表达式", "showWhen": "op=regex_extract", "varRef": True},
    "store_var": {"type": "string", "default": "", "description": "存入变量名", "varRef": True},
}
```

**向后兼容**: 旧参数名 `param_a/b/c` 和 `b/c` 在处理器中保留映射，已保存的脚本加载时自动转换。

### 5.4 check_screen 参数描述动态化方案

**问题**: `threshold` 参数在不同 `state` 模式下含义完全不同，但当前只有一个通用描述。

**修复方案**: 前端属性面板在渲染 `threshold` 参数时，根据当前 `state` 值动态修改 description：

| state 值 | threshold description                    |
| -------- | ---------------------------------------- |
| black    | 亮度阈值(低于此值判定为黑屏，默认30)     |
| bright   | 亮度阈值(高于255-此值判定为白屏，默认30) |
| frozen   | 差异阈值(低于此值判定为画面冻结，默认30) |

`state` 枚举的中文显示名：

| 内部名  | 中文显示名 |
| ------- | ---------- |
| black   | 黑屏       |
| bright  | 白屏       |
| frozen  | 画面冻结   |

### 5.5 mouse_click mode=current 实现方案

**节点定义变更**:

```python
"mode": {"type": "string", "enum": ["screen", "window", "relative", "current"], "default": "screen", "description": "坐标模式"},
"x": {"type": "number", "default": 0, "description": "X坐标", "showWhen": "mode=screen,mode=window,mode=relative", "varRef": True},
"y": {"type": "number", "default": 0, "description": "Y坐标", "showWhen": "mode=screen,mode=window,mode=relative", "varRef": True},
"hwnd_var": {"type": "string", "default": "", "description": "窗口句柄变量名", "showWhen": "mode=window,mode=relative", "varRef": True},
"move_duration": {"type": "number", "default": 0, "description": "移动到目标坐标的耗时(ms)", "showWhen": "mode=screen,mode=window,mode=relative", "varRef": True},
```

**处理器逻辑**:

```python
def _handle_mouse_click(node, ctx):
    mode = params.get("mode", "screen")
    if mode == "current":
        # 不移动，直接在当前位置点击
        _do_click(button, click_type, hold_time, ctx.stop_event, ctx)
    else:
        # 原有逻辑：解析坐标 → 移动 → 点击
        phys_x, phys_y = resolve_coords(mode, x, y, hwnd)
        ...
```

---

## 六、1期→2期状态变更对照

以下条目在1期审查意见书中的判定与2期不同，记录变更原因：

| 1期编号 | 1期判定 | 2期编号 | 2期判定 | 变更原因                                                                 |
| ------- | ------- | ------- | ------- | ------------------------------------------------------------------------ |
| D-01    | 后期考虑 | B-01    | 采纳    | 用户反馈需求从"showWhen"变为"原地点击"功能，是功能改进而非UX优化         |
| D-10    | 后期考虑 | B-10    | 采纳    | 配合 B-02 string_op 改进，substr 问题需同步解决                          |
| D-13    | 后期考虑 | B-02    | 采纳    | 问题严重程度超出预期，不止 split 返回问题，整个 string_op 对用户极不友好 |
| D-38    | 后期考虑 | B-16    | 采纳    | 与 D-50 合并，变量面板覆盖不全影响核心使用流程                           |
| D-50    | 后期考虑 | B-16    | 采纳    | 变量面板缺失 result 输出，用户无法通过变量选择器获取关键数据             |
| D-30~34 | 后期考虑 | B-17    | 采纳    | 降级方案：不引入 varOutput 标记，改为前端添加"存入变量"说明              |
| R-03    | 拒绝    | B-08    | 采纳    | 有限采纳：仅为 mouse_click 的 store_hwnd_var 确保变量面板可见            |
| D-42    | 后期考虑 | P-16    | 后期考虑 | 确认模拟执行未开放给用户，优先级进一步降低                               |

---

*审查完毕。请前后端开发人员按优先级排序进行修复，如有疑问可联系审查人确认。*
