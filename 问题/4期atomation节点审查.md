# 🔍 自动化编辑器 — 独立Bug排查最终汇总报告 审查人 : 独立QA审查 审查日期 : 2026-05-02 审查范围 : 全项目分模块检查（动作/检测/控制/监视器/变量/预设/工具/画布核心/编译器引擎/插件/Bridge API） 交叉验证 : 已与 Bug审查意见书.md 对比，过滤后期考虑/拒绝项，标注已采纳但未修复项

## 一、🔴🔴🔴 致命级 Bug（核心功能完全失效）

### 1. property.js — this.\_container 从未赋值，showWhen 字段无法隐藏

- 位置 : \[property.js:1561]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L1561)
- 问题 : \_checkShowWhenChanges 方法引用 this.\_container ，但 render() 方法中 container 是局部变量，从未赋值给 this.\_container 。导致 wasVisible 始终为 false ，字段只能显示不能隐藏
- 影响 : 用户修改触发字段后，不该显示的参数仍然停留在属性面板上，造成界面混乱和误操作
- 修复 : 在 render() 中添加 this.\_container = container;

### 2. property.js — 按键选择器 \_openKeySelector 使用错误API导致功能完全失效

- 位置 : \[property.js:895]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L895)
- 问题 : 使用 AutomationCore.lgCanvas.graph.getNode(nodeId) ，但 LiteGraph API 是 getNodeById
- 影响 : 用户点击按键选择按钮后，选中的按键无法写入节点属性，按键选择功能完全失效
- 修复 : 改为 AutomationCore.lgGraphObj.getNodeById(nodeId)

### 3. core.js — \_checkShowWhen 多条件使用 OR 逻辑，应为 AND 逻辑

- 位置 : \[core.js:152-186]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L152-L186)
- 问题 : 逗号分隔的多个 showWhen 条件，只要任意一个满足就返回 true。但语义应为所有条件同时满足
- 影响 : 所有使用多条件 showWhen 的参数（如 showWhen: "mode=window,mode=relative" ）实际上变成了 OR 逻辑——只要 mode 是 window 或 relative 就显示，而非需要同时满足。 注意 ：当前项目中大部分 showWhen 都是同字段多值（如 mode=window,mode=relative ），这种情况下 OR 逻辑恰好是正确的。但如果有跨字段条件（如 mode=click,button=left ），则会出错
- 修复 : 区分同字段多值（OR）和跨字段条件（AND）

### 4. record 插件 — 录制功能完全不可用

- 位置 : \[plugins/record/backend.py:73]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/plugins/record/backend.py#L73)
- 问题 : \_start\_record 调用 cl.start\_replay\_buffer() 而非 cl.start\_record() ，整个录制流程从未真正开始录制
- 影响 : 用户点击"开始录制"实际启动的是回放缓冲，而非正式录制。停止录制后返回的文件路径也是猜测的，非实际路径
- 修复 : 改为 cl.start\_record() ，并使用 OBS WebSocket 事件获取实际录制文件路径

## 二、🔴🔴 严重级 Bug（主要功能不可用）

### 5. core.js — 注释/分组选择时先置空 \_selectedNodeId 再查找旧节点，节点高亮无法移除

- 位置 : \[core.js:744-746]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L744-L746), \[core.js:975-977]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L975-L977)
- 问题 : 先将 \_selectedNodeId = null ，然后用 document.getElementById('nd-' + \_selectedNodeId) 查找旧节点，实际查找 'nd-null' ，永远找不到
- 影响 : 选中节点后点击注释/分组，原节点高亮无法取消，视觉上仍显示为选中状态

### 6. editor-app.js — PAUSED 状态下运行按钮可重新启动执行，导致多实例并行

- 位置 : \[editor-app.js:1165]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L1165)
- 问题 : runGraph 只检查 RUNNING 状态，未检查 PAUSED。暂停后点击运行会启动新执行实例
- 影响 : 两个执行实例同时运行，鼠标键盘操作冲突

### 7. editor-app.js — PAUSED 状态运行按钮图标未重置

- 位置 : \[editor-app.js:272-279]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L272-L279)
- 问题 : 暂停后运行按钮仍显示旋转 spinner 图标，但可点击
- 影响 : UI 状态与实际状态不一致，用户误以为脚本仍在运行

### 8. detection/check\_color — target\_color 未使用 \_resolve\_value 解析变量引用

- 位置 : \[handlers/detection.py:78]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L78)
- 问题 : params.get("target\_color", "#FF0000") 直接取值，不解析 ${var}
- 影响 : 用户通过变量选择器引用颜色变量后，检测永远失败
- 审查书对照 : 此bug与 A-06/A-07/A-09/A-10/A-11 同类（varRef不解析），但 check\_color 的 target\_color 未在审查书中列出，属于 新发现的bug

### 9. detection/check\_image — template\_path 未使用 \_resolve\_value 解析变量引用

- 位置 : \[handlers/detection.py:302]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L302)
- 问题 : 同上， template\_path 有 varRef: True 但不解析
- 审查书对照 : 审查书中 D-19 标记为"后期考虑"，但这是 功能缺陷 ——用户使用变量引用时脚本崩溃，不应为后期考虑。需要再次提出

### 10. detection/check\_ocr — cache\_interval\_ms 未使用 \_resolve\_value 解析

- 位置 : \[handlers/detection.py:185]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L185)
- 问题 : 有 varRef: True 但直接 int(params.get(...)) 会崩溃
- 审查书对照 : 审查书中 D-18 标记为"后期考虑"，但使用变量时 int("${var}") 会崩溃，属于功能缺陷

### 11. monitor/monitor\_color — target\_color 未使用 \_resolve\_value 解析

- 位置 : \[handlers/monitor.py:29]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L29)
- 问题 : 同 BUG #8，监视器版本

### 12. monitor/monitor\_node — target\_task 未使用 \_resolve\_value 解析

- 位置 : \[handlers/monitor.py:105]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L105)
- 问题 : 有 varRef: True 但不解析，stop\_task/pause\_task/resume\_task 无法找到目标任务

### 13. monitor/monitor\_time — target\_task 未使用 \_resolve\_value 解析

- 位置 : \[handlers/monitor.py:220]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L220)
- 问题 : 同 BUG #12

### 14. control/goto — target\_node\_id 未使用 \_resolve\_value 解析

- 位置 : \[handlers/control.py:216]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L216)
- 问题 : 有 varRef: True 但不解析，goto 跳转失败
- 审查书对照 : 审查书 D-28 标记为"后期考虑"，但 goto 使用变量引用时跳转完全失败，属于功能缺陷

### 15. script\_block/call\_script\_sync/async — path 未使用 \_resolve\_value 解析

- 位置 : \[handlers/control.py:112]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L112), \[handlers/control.py:148]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L148)
- 问题 : path 有 varRef: True 但不解析，宏文件找不到
- 审查书对照 : 审查书 D-28 标记为"后期考虑"，同 BUG #14

### 16. control/state\_machine — states/fail\_state 未使用 \_resolve\_value 解析

- 位置 : \[handlers/control.py:246-247]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L246-L247)
- 问题 : 两者都有 varRef: True 但不解析

### 17. preset/preset\_find\_click — template\_path/rect 未使用 \_resolve\_value 解析

- 位置 : \[handlers/preset.py:41-43]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/preset.py#L41-L43)
- 问题 : 有 varRef: True 但不解析
- 审查书对照 : D-24 标记为"后期考虑"，但使用变量时功能失效

### 18. preset/preset\_read\_text — rect 未使用 \_resolve\_value 解析

- 位置 : \[handlers/preset.py:92]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/preset.py#L92)
- 问题 : 同上

### 19. variable/var\_convert — input\_var 未使用 \_resolve\_value 解析

- 位置 : \[handlers/variable.py:180]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L180)
- 问题 : 有 varRef: True 但手动处理 ${var} 格式，不统一

### 20. PluginManager — 全局 context 缺少变量读写能力，插件 set\_variable 无效

- 位置 : \[plugin\_manager.py:15-17]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/core/plugin\_manager.py#L15-L17)
- 问题 : 当 execute() 传入 context 为 None 时，回退到全局 context， \_var\_get\_fn 和 \_var\_set\_fn 为 None
- 影响 : 插件节点无法正确设置/读取流程变量（如 screenshot\_path 、 record\_path ）

### 21. nodes.js — registerPluginNodes 未调用 \_normalizeSchema 标准化

- 位置 : \[nodes.js:747-765]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L747-L765)
- 问题 : 插件节点定义直接写入 \_nodeDefs ，不经过标准化处理
- 影响 : 插件节点的输出端口类型可能显示为 data\_bool 而非 boolean ，showWhen 条件可能不生效

## 三、🔴 高优先级 Bug（影响用户体验或功能正确性）

### 22. core.js — \_checkShowWhen 的 != 运算符在 undefined 时误判

- 位置 : \[core.js:170-173]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L170-L173)
- 问题 : 当依赖参数值为 undefined 时， != 条件错误通过

### 23. core.js — 框选开始时调用 \_deselectAll 意外触发 onNodeDeselected 回调

- 位置 : \[core.js:1830-1838]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L1830-L1838)
- 影响 : 属性面板在框选开始时闪烁或短暂清空

### 24. core.js — flow 连线只限制目标端口一对一，未限制源端口

- 位置 : \[core.js:1397-1403]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L1397-L1403)
- 影响 : 一个 flow 输出可连到多个输入，执行顺序不确定

### 25. editor-app.js — Ctrl+V 粘贴不递增偏移量，节点重叠

- 位置 : \[editor-app.js:2543]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L2543)
- 影响 : 连续 Ctrl+V 粘贴的节点堆叠在同一位置
- 审查书对照 : A-47 已采纳但 未修复 （当前代码仍无 \_pasteCount 递增）

### 26. editor-app.js — Ctrl+C 复制不包含 customName

- 位置 : \[editor-app.js:2517-2521]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L2517-L2521)
- 影响 : 键盘复制粘贴丢失自定义名称
- 审查书对照 : D-36 标记为"后期考虑"，不重复提出

### 27. editor-app.js — \_getFlowOrderedNodes 未区分 flow/data 连线

- 位置 : \[editor-app.js:1316-1325]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L1316-L1325)
- 影响 : 模拟执行顺序可能不正确
- 审查书对照 : D-42 标记为"后期考虑"，不重复提出

### 28. property.js — 字符串/枚举/路径字段值未进行 HTML 转义

- 位置 : \[property.js:506]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L506), \[property.js:534]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L534), \[property.js:455]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L455), \[property.js:608]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L608), \[property.js:628]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L628)
- 影响 : 属性值包含双引号或HTML标签时输入框损坏，可能导致XSS

### 29. action/key\_action — 后端定义中 key 缺少 keySelector 属性

- 位置 : \[nodes/action.py:34]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/action.py#L34)
- 问题 : 前端fallback有 keySelector:true 但后端定义没有，API加载后按键选择器消失
- 审查书对照 : D-03 标记为"后期考虑"，不重复提出

### 30. control/seq\_check — steps 参数在handler中完全未使用

- 位置 : \[handlers/control.py:223]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L223)
- 问题 : 用户填写的步骤描述没有任何效果，误导用户

### 31. preset/preset\_read\_text — handler中异常后 raise 导致节点执行中断

- 位置 : \[handlers/preset.py:131]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/preset.py#L131)
- 问题 : 其他检测类节点异常时走 no/match 分支，但此处直接 raise 中断执行
- 审查书对照 : A-56 已采纳但 未修复 （当前代码仍有 raise）

### 32. automation\_api.py — run\_automation 旧任务超时未停止时新任务仍会启动

- 位置 : \[automation\_api.py:62-64]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/bridge/automation\_api.py#L62-L64)
- 影响 : 两个自动化任务并行运行，操作冲突

### 33. automation\_api.py — get\_window\_at\_mouse cursor\_pt 动态添加 _fields_ 用法不安全

- 位置 : \[automation\_api.py:354-356]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/bridge/automation\_api.py#L354-356)
- 影响 : 某些 Python 版本下可能返回错误坐标或崩溃

### 34. macro\_binding\_api.py — 鼠标绑定只支持侧键，不支持左/右/中键

- 位置 : \[macro\_binding\_api.py:189-200]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/bridge/macro\_binding\_api.py#L189-L200)
- 影响 : 用户无法将鼠标左键/右键/中键绑定为宏触发键

### 35. plugin\_context.py — show\_desktop\_popup 使用 MessageBoxW 无法自动关闭

- 位置 : \[plugin\_context.py:262-276]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/core/plugin\_context.py#L262-L276)
- 影响 : 设置了自动关闭时间的弹窗不会自动消失

### 36. plugin\_manager.py — 重载插件后未通知前端刷新节点定义

- 位置 : \[plugin\_manager.py:143-149]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/core/plugin\_manager.py#L143-L149)
- 影响 : 重载插件后编辑器看不到更新，需刷新页面
- 审查书对照 : A-54 已采纳但 未修复

### 37. notify 插件 — Unicode窗口使用ANSI字体结构体

- 位置 : \[plugins/notify/backend.py:271-274]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/plugins/notify/backend.py#L271-L274)
- 影响 : 非中文系统弹窗字体可能回退到默认字体

## 四、🟡 中优先级 Bug（设计不一致或体验不佳）

### 38. action/mouse\_move\_rel — 缺少 easing 参数，与 mouse\_move 不一致

- 审查书对照 : R-01 已 拒绝 ，不重复提出

### 39. monitor/monitor\_timer — repeat\_count 缺少 showWhen: "auto\_stop=false" 条件

- 位置 : \[nodes/monitor.py:79]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/monitor.py#L79)
- 影响 : auto\_stop=true 时 repeat\_count 无意义但仍显示

### 40. monitor/monitor\_color — 缺少 check\_mode=exact 选项，与 detection/check\_color 不一致

- 位置 : \[nodes/monitor.py:18]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/monitor.py#L18)

### 41. utility/const\_number/const\_string — value 有 varRef 但"常量"节点不应引用变量

- 审查书对照 : D-30/D-34 相关，标记为"后期考虑"，不重复提出

### 42. core.js — 连续删除连线时 \_refreshNodeDOM 导致连接指示状态不准确

- 位置 : \[core.js:1436-1450]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L1436-L1450)

### 43. core.js — 无 ghost 拖拽结束时多选节点 opacity 未恢复

- 位置 : \[core.js:2103-2143]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L2103-L2143)

### 44. screenshot 插件 — fullscreen+window 模式行为与语义矛盾

- 位置 : \[plugins/screenshot/backend.py:51-58]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/plugins/screenshot/backend.py#L51-L58)

### 45. recorder\_api.py — \_ok 返回格式与 automation\_api 不一致

- 位置 : \[recorder\_api.py:20]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/bridge/recorder\_api.py#L20)

### 46. plugin\_api.py — call\_plugin 返回格式不统一

- 位置 : \[plugin\_api.py:37-43]\(file:///g:/宏引擎/宏驱动 webui 2.7.7/bridge/plugin\_api.py#L37-L43)

## 五、已采纳但未修复的 Bug（审查书 A-xx，代码中仍存在问题）

以下bug在审查意见书中已标记为"采纳"，但当前代码中 仍然存在 ，说明修复未完全执行：

审查书编号 问题摘要 当前状态 A-06/A-07 监视器/延迟 varRef 参数崩溃 未修复 — monitor.py 中 interval/timeout 仍直接取值 A-08 condition cond\_var 不解析 ${} 未修复 — utility handler 中仍直接取值 A-09 string\_op param\_a/b/c 不使用 \_resolve\_value 未修复 A-10 monitor\_ocr match\_number 不使用 \_resolve\_value 未修复 A-11 monitor\_color tolerance/change\_threshold 不使用 \_resolve\_value 未修复 A-12 监视器 auto\_stop 完全无效 未修复 A-13 var\_set boolean 转换错误 未修复 A-17 key\_action key 默认值不一致 未修复 A-18 loop\_count count 默认值不一致 未修复 A-19 var\_math a/b 默认值不一致 未修复 A-22\~A-26 showWhen 条件缺失 未修复 A-31 内联快捷参数不检查 showWhen 未修复 A-32 属性面板修改 mode 后节点内联字段不刷新 未修复 A-47 多次粘贴节点位置重叠 未修复 — Ctrl+V 仍无 \_pasteCount 递增 A-53 插件后端注册空定义覆盖前端完整定义 未修复 A-54 插件重载不清后端注册 未修复 A-56 preset\_read\_text 错误时仍执行 next 未修复 — 仍有 raise

## 六、独立新发现（审查书中未覆盖的 Bug）

以下bug是本次独立审查新发现的，在原审查意见书中 未出现 ：

编号 严重程度 模块 问题摘要 NEW-1 🔴🔴🔴 property.js this.\_container 从未赋值，showWhen 字段无法隐藏 NEW-2 🔴🔴🔴 property.js 按键选择器使用错误 API getNode ，功能完全失效 NEW-3 🔴🔴🔴 core.js \_checkShowWhen 多条件 OR/AND 逻辑错误 NEW-4 🔴🔴🔴 record 插件 录制功能完全不可用（start\_replay\_buffer 代替 start\_record） NEW-5 🔴🔴 core.js 注释/分组选择时节点高亮无法移除 NEW-6 🔴🔴 editor-app.js PAUSED 状态可重复启动执行 NEW-7 🔴🔴 editor-app.js PAUSED 状态运行按钮图标未重置 NEW-8 🔴🔴 detection check\_color target\_color 未使用 \_resolve\_value NEW-9 🔴🔴 detection check\_image template\_path 未使用 \_resolve\_value NEW-10 🔴🔴 detection check\_ocr cache\_interval\_ms 未使用 \_resolve\_value NEW-11 🔴🔴 monitor monitor\_color target\_color 未使用 \_resolve\_value NEW-12 🔴🔴 monitor monitor\_node/monitor\_time target\_task 未使用 \_resolve\_value NEW-13 🔴🔴 control goto target\_node\_id 未使用 \_resolve\_value NEW-14 🔴🔴 control call\_script path 未使用 \_resolve\_value NEW-15 🔴🔴 control state\_machine states/fail\_state 未使用 \_resolve\_value NEW-16 🔴🔴 preset preset\_find\_click template\_path/rect 未使用 \_resolve\_value NEW-17 🔴🔴 preset preset\_read\_text rect 未使用 \_resolve\_value NEW-18 🔴🔴 variable var\_convert input\_var 未使用 \_resolve\_value NEW-19 🔴🔴 PluginManager 全局 context 缺少变量读写能力 NEW-20 🔴🔴 nodes.js registerPluginNodes 未调用 \_normalizeSchema NEW-21 🔴 core.js \_checkShowWhen != 运算符 undefined 误判 NEW-22 🔴 core.js 框选触发 onNodeDeselected 回调 NEW-23 🔴 core.js flow 连线源端口未限制一对一 NEW-24 🔴 property.js 多处字段值未 HTML 转义（XSS风险） NEW-25 🔴 control seq\_check steps 参数完全未使用 NEW-26 🔴 bridge run\_automation 旧任务超时后新任务仍启动 NEW-27 🔴 bridge get\_window\_at\_mouse cursor\_pt 动态 fields 不安全 NEW-28 🔴 bridge 鼠标绑定只支持侧键 NEW-29 🔴 plugin\_context MessageBoxW 无法自动关闭 NEW-30 🔴 notify 插件 Unicode 窗口使用 ANSI 字体结构体 NEW-31 🟡 core.js 连续删除连线连接指示状态不准确 NEW-32 🟡 core.js 无 ghost 拖拽多选节点 opacity 未恢复 NEW-33 🟡 monitor monitor\_timer repeat\_count 缺少 showWhen NEW-34 🟡 monitor monitor\_color 缺少 exact 检测模式 NEW-35 🟡 screenshot 插件 fullscreen+window 模式行为矛盾 NEW-36 🟡 bridge API 返回格式不统一

## 七、总结

分类 数量 说明 🔴🔴🔴 致命级 4 核心功能完全失效 🔴🔴 严重级 16 主要功能不可用 🔴 高优先级 16 影响用户体验或功能正确性 🟡 中优先级 9 设计不一致或体验不佳 独立新发现 36 审查书中未覆盖的bug 已采纳未修复 17+ 审查书已采纳但代码中仍存在

##

