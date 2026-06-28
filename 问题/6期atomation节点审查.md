# Automation 节点审查 — 第6期

> **审查日期**: 2026-05-02
> **审查范围**: 全模块（流程/动作/检测/控制/监视器/变量/预设/工具/动作块/画布UI/编译器引擎/插件系统）
> **审查方法**: 按 toolbox-categories 模块分类，逐模块读取对应代码，以用户视角进行全生命周期检查
> **交叉验证**: 已对照 `待修复问题存档（1-5期整合）.md`、`08-已知缺陷与待办功能.md`、`Bug查找指导.md`，过滤了已拒绝/后期考虑/设计意图项

---

## 🔴🔴🔴 致命级BUG

### N6-001: `detection/check_image` — 金字塔匹配ROI切片行列顺序错误

- **后端处理器** [detection.py:282](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L282): `roi = img[roi_y1:roi_x2, roi_x1:roi_x2]`
- **正确应为**: `roi = img[roi_y1:roi_y2, roi_x1:roi_x2]`
- **影响**: 当金字塔匹配启用时，ROI裁剪使用 `roi_x2` 作为行的终止索引而非 `roi_y2`，导致：
  1. 如果 `roi_y2 != roi_x2`，裁剪出完全错误的图像区域
  2. 如果 `roi_x2 > 图像高度`，会导致数组越界崩溃
  3. 匹配坐标偏移，找图结果完全不可靠
- **复现路径**: 用户拖出 `check_image` 节点 → 设置 `pyramid_levels > 1` → 设置非零ROI区域 → 执行 → 匹配结果错误或崩溃
- **修复建议**: 将 `img[roi_y1:roi_x2, roi_x1:roi_x2]` 改为 `img[roi_y1:roi_y2, roi_x1:roi_x2]`

---

### N6-002: `engine.py` — _resolve_value对未定义变量的替换策略不一致

- **引擎代码** [engine.py:396-417](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L396-L417): 单变量引用 `${unknown}` 时，返回原始字符串 `"${unknown}"`
- **引擎代码** [engine.py:448-450](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L448-L450): 多变量混合 `"prefix_${unknown}_suffix"` 时，未定义变量替换为 `"0"`
- **影响**: 用户在参数中引用了不存在的变量时：
  - 数值参数：单引用时传入 `"${unknown}"` 字符串，后续 `float()` 转换抛异常；多引用时传入0，静默失败
  - 字符串参数：单引用时保留原始文本，多引用时变为 `"prefix_0_suffix"`
  - 行为完全不可预测，用户无法判断变量是否正确解析
- **复现路径**: 在任意节点的varRef参数中输入 `${不存在的变量名}` → 执行 → 观察结果
- **修复建议**: 统一未定义变量的替换策略。建议：1) 都返回原始字符串并记录警告；2) 或都替换为空字符串/0并记录警告。关键是一致性

---

### N6-003: `engine.py` — _execute_node修改共享node.params存在线程安全风险

- **引擎代码** [engine.py:746-810](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L746-L810): 执行前将 `node.params` 替换为 resolved 版本，finally 中恢复
- **影响**: node对象在 `graph.nodes` 中是共享的。如果fork的多个分支同时引用同一个数据源节点（如 `const_number`），`_ensure_data_inputs` 可能触发对同一节点的并发执行。虽然 `executed_set` 会阻止重复执行，但在极端时序下，一个线程修改params后、finally恢复前，另一个线程可能读到修改后的值
- **复现路径**: 创建fork → 两个分支都引用同一个const_number → 极端时序下可能出现params被覆盖
- **修复建议**: 不修改 `node.params`，而是在handler调用时传入resolved_params作为额外参数，或使用线程本地存储

---

## 🔴🔴 严重级BUG

### N6-004: `preset/preset_type` — 后端缺少节点定义和处理器

- **前端fallback** [nodes.js:627-638](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L627-L638): 有 `preset/preset_type` 的完整fallback定义（参数：mode, rect, hwnd_var, text, before_delay, after_delay, store_var）
- **后端定义** [preset.py](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/preset.py): 只有 `preset_click`, `preset_find_click`, `preset_read_text`，**没有 `preset_type`**
- **影响**: 
  1. 当后端API可用时，`preset_type` 节点不会出现在节点列表中
  2. 当API不可用时，前端fallback会显示该节点，但执行时handler为空，节点静默跳过
  3. 用户从旧版本迁移的脚本中如果包含 `preset_type` 节点，执行时会被忽略
- **复现路径**: 拖出预设分类 → 观察是否有"输入文本"节点 → 添加到画布 → 执行 → 节点被跳过
- **修复建议**: 在后端 `automation/nodes/preset.py` 和 `automation/handlers/preset.py` 中添加 `preset_type` 的完整定义和处理器

---

### N6-005: `preset/preset_find_click` — 缺少capture_source数据输入支持

- **后端定义** [preset.py:32-41](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/preset.py#L32-L41): 无capture_source数据输入端口
- **处理器** [preset.py:59](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/preset.py#L59): 直接调用 `capture_screen(region, ctx=ctx)`，每次都重新截图
- **对比** `detection/check_image`: 支持capture_source数据输入，可复用上游截图
- **影响**: 用户在循环中反复使用"找图点击"时，每次都重新截图，无法利用capture_source节点的截图缓存，性能浪费严重。且在fork多分支场景下，截图源节点无法与找图点击联动
- **复现路径**: 创建 capture_source → 创建 preset_find_click → 无法连线（无数据输入端口）
- **修复建议**: 为 `preset_find_click` 添加 `capture_source` 数据输入端口，处理器中优先使用上游截图

---

### N6-006: `preset/preset_read_text` — capture_screen调用缺少ctx参数

- **处理器** [preset.py:91](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/preset.py#L91): `capture_screen(region)` — **缺少ctx参数**
- **对比** [preset.py:59](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/preset.py#L59): `preset_find_click` 中调用 `capture_screen(region, ctx=ctx)` — 有ctx参数
- **影响**: 
  1. 截图无法响应stop_event，用户停止脚本时截图操作可能继续执行
  2. 无法使用DXGI截图管理器，回退到mss/BitBlt，截图性能和兼容性降低
  3. 无法利用截图缓存机制
- **复现路径**: 使用preset_read_text节点 → 执行 → 尝试在截图期间停止脚本 → 截图不响应停止
- **修复建议**: 将 `capture_screen(region)` 改为 `capture_screen(region, ctx=ctx)`

---

## 🔴 高优先级BUG

### N6-007: `utility/string_op` — regex_extract捕获组越界时静默回退

- **处理器** [utility.py:198](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L198): `m.group(group) if group <= len(m.groups()) else m.group(0)`
- **影响**: 用户指定了不存在的捕获组编号时（如正则只有1个捕获组但用户输入group=5），静默返回整个匹配而非提示错误。用户可能不知道自己的捕获组配置有误，导致后续逻辑使用了错误的值
- **修复建议**: 当group超出范围时，记录警告日志 `ctx.log_error(...)` 并返回空字符串

---

### N6-008: `utility/math_func` — round函数缺少小数位数参数

- **后端定义** [utility.py:64](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/utility.py#L64): `func` enum包含 `"round"`
- **处理器** [utility.py:104](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L104): `"round": lambda: round(x)` — 只能取整
- **对比** `variable/var_math`: `round(a, int(b))` 支持指定小数位数
- **影响**: 用户在 `math_func` 中选择 `round` 期望四舍五入到指定小数位，但实际只能取整。与 `var_math` 的round功能不一致
- **修复建议**: 为 `math_func` 的round模式添加可选的"小数位数"参数，或在enum中说明"取整"

---

### N6-009: `utility/bookmark` — window/relative模式下w/h可能被错误缩放

- **处理器** [utility.py:250](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L250): `rw_rh = resolve_region(mode, (0, 0, w, h), hwnd)`
- **影响**: `resolve_region` 对window/relative模式会做坐标变换。传入 `(0, 0, w, h)` 作为region，其中w/h是"宽度和高度"，但resolve_region可能将它们当作坐标进行缩放。如果窗口有DPI缩放，输出的w/h可能不等于输入的w/h
- **修复建议**: 需确认 `resolve_region` 对window模式下region的w/h字段是否做了DPI缩放。如果是，则bookmark的w/h输出在window模式下可能不正确

---

### N6-010: `variable/var_math` — round模式下b参数标签不清晰

- **后端定义** [variable.py:35](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/variable.py#L35): b参数 `showWhen` 包含 `op=round`
- **处理器** [variable.py:100](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L100): `"round": lambda: round(a, int(b))` — b为小数位数
- **前端fallback** [nodes.js:474](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L474): b的label为"操作数B"
- **影响**: 用户在round模式下看到"操作数B"标签，不清楚这是"小数位数"。可能输入错误的值（如输入2期望2位小数，但实际是 `round(原值, 2)` 即保留2位小数，语义一致但标签不直观）
- **修复建议**: 为round模式下的b参数使用动态label"小数位数"，或在description中说明

---

### N6-011: `variable/var_string` — regex_extract不支持捕获组

- **处理器** [variable.py:170-172](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L170-L172): `match.group(0)` 只返回完整匹配
- **对比** `utility/string_op`: 有 `group` 参数支持捕获组
- **影响**: `var_string` 的 `regex_extract` 不支持捕获组，功能比 `utility/string_op` 弱。用户在var_string中无法提取正则的子组
- **修复建议**: 为 `var_string` 的regex_extract添加 `group` 参数

---

### N6-012: `compiler.py` — 多个start节点时报错但仍然执行

- **编译器代码** [compiler.py:82-84](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/compiler.py#L82-L84): 添加错误信息后仍设置 `graph.entry_node_id = start_nodes[0]`
- **影响**: 用户有多个start节点时，编译器记录了错误但仍然使用第一个start节点执行。如果用户忽略了编译错误，脚本可能以非预期的方式执行
- **修复建议**: 当存在多个start节点时，应将错误标记为致命错误，阻止执行

---

### N6-013: `property.js` — 变量选择器中check_类节点的store_var类型硬编码为string

- **前端代码** [property.js:1070-1075](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L1070-L1075): check_类节点的store_var类型硬编码为 `'string'`
- **影响**: `check_color` 的store_var实际存储颜色信息，`check_image` 的store_var存储匹配坐标dict。变量选择器中统一显示为"文本"类型，用户在选择变量时可能误判类型，将非字符串值当作字符串使用
- **修复建议**: 根据具体检测节点的store_var实际存储内容，正确标注类型。如check_image的store_var应为"any"或"对象"

---

### N6-014: `property.js` — _collectStructuredVars中check_节点过滤条件硬编码

- **前端代码** [property.js:1059](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L1059): `defKey.indexOf('check_') >= 0 && defKey.indexOf('check_image') < 0 && defKey.indexOf('check_ocr') < 0 && defKey.indexOf('check_screen') < 0`
- **影响**: 变量收集逻辑通过硬编码节点类型名来过滤，如果新增了其他check_类型节点（如check_pixel），变量选择器可能无法正确显示其输出。应改为基于节点定义的outputs自动收集
- **修复建议**: 改为基于 `AutomationNodes.getNodeDef(defKey).outputs` 自动收集数据输出端口变量

---

## 🟡 中优先级问题

### N6-015: `monitor/monitor_time` — auto_stop=false时循环创建线程存在竞态

- **处理器** [monitor.py:287-331](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L287-L331): auto_stop=false时，循环中创建新的wait_thread
- **影响**: 每次循环都创建新线程，且使用 `trigger_event.clear()` 后重新等待。如果在 `_execute_flow` 执行期间，新的wait_thread已经触发，可能导致事件丢失或重复触发
- **修复建议**: 考虑使用更简洁的循环等待机制，避免频繁创建/销毁线程

---

### N6-016: `script_block/call_script_sync` — 文件不存在时仍走next流程

- **处理器** [control.py:136-142](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L136-L142): 文件不存在时记录错误后执行 `_execute_flow(node.id, "next", ctx)`
- **影响**: 用户配置了错误的文件路径时，脚本不会停止，而是继续执行后续节点。后续节点可能在预期前置条件未满足的情况下运行，导致不可预测的行为
- **修复建议**: 考虑添加error输出端口，或在文件不存在时停止当前分支

---

### N6-017: `script_block/call_script_async` — 异步回调可能在ctx已清理后触发

- **处理器** [control.py:171-209](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L171-L209): 异步线程中的 `_execute_flow(node.id, "done", ctx)` 回调
- **影响**: 异步线程中的回调可能在主执行流程已经结束后触发，对已清理的ctx进行操作，可能导致异常
- **修复建议**: 在异步回调中检查stop_event状态，如果已停止则跳过回调

---

### N6-018: `control/join` — 循环中使用时状态重置存在竞态条件

- **处理器** [control.py:549-553](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L549-L553): 当join_event已设置时，清除所有状态重新开始
- **影响**: 如果同一个join节点在循环中被多次使用，两个分支几乎同时到达时，第一个分支可能已经设置了done_flag，第二个分支的重置可能导致第一个分支的done被忽略
- **修复建议**: 考虑使用更健壮的同步机制，如为每次join操作分配唯一ID

---

### N6-019: `plugin_manager.py` — 插件reload时注销所有插件节点

- **代码** [registry.py:51-54](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/registry.py#L51-L54): `unregister_plugin_nodes` 删除所有 `plugin/` 开头的节点
- **代码** [plugin_manager.py:151-152](file:///g:/宏引擎/宏驱动 webui 2.7.7/core/plugin_manager.py#L151-L152): reload时先注销所有插件节点再重新注册
- **影响**: 重载单个插件时，所有插件节点都会被暂时注销。如果画布上有其他插件的节点，其类型定义会暂时丢失
- **修复建议**: 只注销目标插件的节点，而非所有插件节点

---

### N6-020: `property.js` — _checkShowWhen对布尔值比较可能大小写不一致

- **前端代码** [property.js:420-432](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L420-L432): 将布尔值转为字符串后与showWhen条件比较
- **影响**: 后端showWhen条件如 `"wait=True"` (大写T) 与前端比较时，`rawVal` 为 `true` (布尔)，转为字符串 `"true"` (小写)，与 `"True"` 不匹配。虽然当前后端定义都使用小写，但如果未来有人使用大写，会导致showWhen失效
- **修复建议**: 统一大小写比较，或在 `_normalizeSchema` 中标准化showWhen值

---

## 💡 建议项

### N6-S01: `control/goto` — 无输出端口，流程走向不直观

- **后端定义** [control.py:84-85](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/control.py#L84-L85): outputs为空列表
- **建议**: 考虑添加一个"跳转目标"的视觉连线，或在goto节点上显示跳转目标信息，让用户直观看到流程走向

### N6-S02: `block-editor.js` — 编辑动作时参数标签为英文原始名

- **前端代码** [block-editor.js:322](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/block-editor.js#L322): `labelEl.textContent = paramName` — 直接使用"duration"、"delta"等
- **建议**: 为ACTION_TYPES的params添加中文标签映射，如 `duration → 持续时间(ms)`、`delta → 滚动量`

### N6-S03: `property.js` — 变量选择器缺少对preset_type节点的变量收集

- **前端代码** [property.js:1008-1231](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/property.js#L1008-L1231): _collectStructuredVars中未处理preset_type节点
- **建议**: 如果preset_type节点被实现，需在_collectStructuredVars中添加对应的变量收集逻辑

---

## 审查统计

| 优先级 | 数量 | 编号 |
|--------|------|------|
| 🔴🔴🔴 致命 | 3 | N6-001, N6-002, N6-003 |
| 🔴🔴 严重 | 3 | N6-004, N6-005, N6-006 |
| 🔴 高 | 8 | N6-007 ~ N6-014 |
| 🟡 中 | 6 | N6-015 ~ N6-020 |
| 💡 建议 | 3 | N6-S01 ~ N6-S03 |
| **合计** | **23** | |

## 过滤说明

以下问题在交叉验证中被过滤（已在1-5期存档中标记为拒绝/后期考虑/设计意图）：

| 我的原始编号 | 问题摘要 | 过滤原因 |
|-------------|----------|----------|
| FLOW-1 | flow/end 全局停止 | N5-002 拒绝：设计意图 |
| FLOW-2 | flow/start 缺少多入口 | 功能增强，非Bug |
| ACTION-1 | mouse_click store_hwnd_var showWhen | N6-001 拒绝：Fallback为主要场景 |
| ACTION-2 | mouse_move_rel 缺easing | R-01/X-14 拒绝：短距离缓动不可感知 |
| ACTION-3 | mouse_scroll 缺坐标参数 | X-13 拒绝：有替代方案 |
| ACTION-4 | program_close force在hwnd下无效 | 后期考虑 |
| ACTION-5 | window_manage store_hwnd_var显示 | N5-032 拒绝：_normalizeSchema自动修复 |
| ACTION-6 | key_action type与text_input重叠 | 功能增强 |
| DETECT-2 | check_color sample_mode showWhen | P-03 后期考虑 |
| DETECT-3 | check_screen frozen对比间隔 | N5-025 已采纳 |
| DETECT-4 | check_image store_var格式不一致 | 功能增强 |
| DETECT-5 | check_ocr 隐式变量 | X-18 拒绝 |
| MONITOR-1 | monitor_color 缺exact | D-08 后期考虑 |
| MONITOR-4 | monitor_ocr 缺cache | 功能增强 |
| UTIL-3 | const_bool 类型不一致 | _normalizeSchema自动修复 |
| UTIL-5 | condition 缺store_var | 隐式变量特性，拒绝 |
| BLOCK-4 | 动作块缺变量引用 | 功能增强 |
| ENGINE-4 | pause_event语义 | 技术债务 |
| ENGINE-5 | _interpolated_move无easing | N5-003 已采纳 |
| PLUGIN-1 | MessageBox无法自动关闭 | D-05 后期考虑 |
| PLUGIN-2 | 占位符参数 | 低风险 |
| CTRL-1/2 | seq_check/state_machine缺poll_interval_ms | F7-003 已修复 |
| VAR-3 | var_compare默认值不一致 | 代码风格 |
| BLOCK-3 | block-editor参数标签 | UX优化 |

## 修复优先级建议

1. **立即修复**: N6-001（金字塔ROI切片错误）— 1行代码修改，影响所有使用金字塔匹配的用户
2. **尽快修复**: N6-002（变量解析不一致）— 影响所有使用变量引用的用户
3. **尽快修复**: N6-006（preset_read_text缺ctx参数）— 1行代码修改
4. **计划修复**: N6-004（preset_type后端缺失）— 需要完整实现
5. **计划修复**: N6-005（preset_find_click缺capture_source）— 需要架构调整
6. **评估后决定**: N6-003（线程安全）— 需要评估实际触发概率
