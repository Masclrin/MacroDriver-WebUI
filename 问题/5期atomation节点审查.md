# 自动化编辑器 — 5期Bug检查汇总

> 审查方式：按模块逐项检查（流程→动作→检测→控制→监视器→变量→预设→工具→动作块→画布/UI）
> 汇总日期：2026-05-02
> 交叉验证：已完成与3期/4期历史文档的对比，排除重复项

---

## 一、本期新发现Bug详表（43项）

---

### 🔴🔴 严重/致命级（8项）

#### N5-001 | `flow/end` handler 死代码 — handler 永不被调用

- **模块**: 流程
- **故障点**: `engine.py:678-681` 对 `flow/end` 做了硬编码检测，在到达 handler 调用之前就 `return` 了
- **用户预期**: 修改 `flow/end` handler 能影响节点的结束行为
- **实际情况**: `_handle_flow_end` 永远不被调用，成为死代码；开发者修改 handler 不会生效
- **文件**: [engine.py:678-681](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L678-L681) + [handlers/flow.py:10-12](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/flow.py#L10-L12)

#### N5-002 | `flow/end` 在fork分支中触发全局停止

- **模块**: 流程
- **故障点**: `engine.py:678-681` 中 `ctx.stop_event.set()` + `ctx.task_pool.stop_all()` 全局停止
- **用户预期**: fork分支内遇到 `flow/end` → 仅该分支结束，其他分支继续
- **实际情况**: 所有并发分支被杀死；项目已有 `control/stop_branch` 专用于分支停止，行为冲突
- **文件**: [engine.py:678-681](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L678-L681)

#### N5-003 | `鼠标点击` 移动使用线性插值（无缓动），而 `鼠标移动` 支持缓动函数

- **模块**: 动作
- **故障点**: `handlers/action.py:85-86` 使用 `_interpolated_move()`（线性），而 `handlers/action.py:535-538` 使用 `_eased_move()`（缓动）
- **用户预期**: "鼠标点击"设置移动耗时后应该平滑移动到目标
- **实际情况**: 僵硬线性移动；用户必须组合"鼠标移动"+"鼠标点击"两个节点才能缓动
- **文件**: [handlers/action.py:85-86](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py#L85-L86) / [handlers/action.py:535-538](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py#L535-L538)

#### N5-004 | 多个`截图源`节点并存时无法各自独立配置

- **模块**: 检测
- **故障点**: `CaptureManager` 全局单例，第二个截图源的 `start_dxgi` 因 `is_dxgi_running()=True` 被跳过
- **用户预期**: 两个截图源分别用不同帧率和区域独立截图
- **实际情况**: 第二个节点的fps/region配置被静默忽略，沿用第一个节点的配置
- **文件**: [handlers/detection.py:42-52](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L42-L52)

#### N5-005 | `fork` 在循环体内时，下一迭代清除首轮运行分支的 `check_results`

- **模块**: 控制
- **故障点**: `BranchContext` 使用 `parent_ctx.check_results` 共享引用（非拷贝）；`_reset_body_nodes` 清除所有后代节点的 check_results key
- **用户预期**: 循环中fork的分支应该独立运行，循环迭代不应互相干扰
- **实际情况**: 第一轮fork的分支还在运行时，第二轮循环的reset清除了它们的check_results → 分支内if_else/loop_while读取到错误False值 → 逻辑走错
- **文件**: [engine.py:129](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L129) + [engine.py:478-481](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L478-L481) + [handlers/control.py:383](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L383)

#### N5-006 | `race` 的 `cancel_on_first=false` 参数完全失效

- **模块**: 控制
- **故障点**: `handlers/control.py:706-715` race_worker 的 finally 块**无条件**遍历取消所有其他分支
- **用户预期**: 设置 `cancel_on_first=false` 时所有分支应跑到底
- **实际情况**: 第一个完成的分支无条件取消其他所有分支，`cancel_on_first` 形同虚设
- **文件**: [handlers/control.py:706-715](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L706-L715)

#### N5-007 | 监视器后台线程不响应暂停

- **模块**: 监视器
- **故障点**: poll_loop `while not trigger_event.is_set() and not ctx.stop_event.is_set()` 仅检查 stop_event；`precise_sleep` 也只检查 stop_event
- **用户预期**: 点击暂停时所有脚本行为冻结（包括监视器轮询）
- **实际情况**: 监视器(颜色/OCR/定时器)后台线程继续高频轮询，消耗CPU空转
- **文件**: [handlers/monitor.py:124](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L124) + [handlers/monitor.py:167](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L167)

#### N5-008 | 9个工具运算/常量节点自动创建不可预测的 `_out` 隐式变量

- **模块**: 工具
- **故障点**: `handlers/utility.py:36` 所有常量/运算节点都执行 `ctx.safe_set_variable(node.id + "_out", value)`
- **用户预期**: 变量列表中只出现我主动创建的变量
- **实际情况**: 每放一个运算节点就自动创建一个 `{数字}_out` 变量；变量选择器被不可预测变量污染
- **影响节点**: const_number, const_string, const_bool, math_op, math_func, logic_op, compare, string_op, condition（共9个）
- **文件**: [handlers/utility.py:36](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L36)

---

### 🔴 高优先级（20项）

#### N5-009 | 检测节点 wait 轮询循环不响应暂停

- **模块**: 检测
- **故障点**: `handlers/detection.py:121` 只检查 `ctx.stop_event`，不检查 `ctx.pause_event`
- **用户预期**: 等待颜色/OCR/图像时点击暂停 → 冻结等待
- **实际情况**: 轮询继续消耗CPU，暂停对这些节点形同虚设
- **文件**: [handlers/detection.py:121](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L121)

#### N5-010 | `等待条件`/`序列检测`/`状态机` 轮询不暂停

- **模块**: 控制
- **故障点**: `handlers/control.py:200/228/256` 只检查 stop_event
- **用户预期**: 暂停应冻结所有控制节点的轮询
- **实际情况**: 这三个控制节点的 while 循环继续空转
- **文件**: [handlers/control.py:200](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L200) / [handlers/control.py:228](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L228) / [handlers/control.py:256](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L256)

#### N5-011 | `延迟` precise_sleep 不检查暂停

- **模块**: 工具
- **故障点**: `handlers/utility.py:240-241` 仅检查 stop_event
- **用户预期**: 5000ms延迟中点击暂停 → 倒计时冻结
- **实际情况**: precise_sleep 继续倒计时，4秒后恢复时延迟已过期
- **文件**: [handlers/utility.py:240-241](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L240-L241)

#### N5-012 | `同步宏` 短路径 precise_sleep 不暂停

- **模块**: 动作块
- **故障点**: `handlers/control.py:140` `precise_sleep` 只检查 stop_event（对比长路径用老引擎正确处理了 pause_event）
- **用户预期**: 同一节点不同路径行为一致
- **实际情况**: 短路径不暂停、长路径暂停 — 行为不一致
- **文件**: [handlers/control.py:140](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L140)

#### N5-013 | `鼠标点击` handler 对引擎已解析参数重复调用 `_resolve_value`

- **模块**: 动作
- **故障点**: 引擎 `engine.py:705-713` 已全局解析 varRef；handler `handlers/action.py:69-72` 再次对 hold_time/move_duration/before_delay/after_delay 调用解析
- **用户预期**: 无感知（函数幂等）
- **实际情况**: 冗余计算 + 技术债务（若将来 _resolve_value 有副作用则出问题）
- **文件**: [handlers/action.py:69-72](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py#L69-L72) + [engine.py:705-713](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L705-L713)

#### N5-014 | `循环计数`/`等待条件`/`goto` 等全部 handler 双重解析

- **模块**: 控制
- **故障点**: 所有标有 `varRef` 的参数在 handler 内部再次调用 `_resolve_value`
- **用户预期**: 无（同上）
- **实际情况**: 同 N5-013，架构级技术债务
- **文件**: [handlers/control.py:63/80/196-197/216/246-247](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L63)

#### N5-015 | `_handle_monitor_node` 全部参数双重解析

- **模块**: 监视器
- **故障点**: interval/timeout/target_task/repeat_count 等全部二次解析
- **用户预期**: 无（同上）
- **实际情况**: 同 N5-013
- **文件**: [handlers/monitor.py:101-110](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L101-L110)

#### N5-016 | `鼠标点击` `store_hwnd_var` 在 screen/current 模式下静默忽略

- **模块**: 动作
- **故障点**: `handlers/action.py:95-99` `if store_hwnd_var and mode != "current" and mode != "screen"` — screen/current 直接跳过
- **用户预期**: 在 screen 模式下也能存储点击处的窗口句柄
- **实际情况**: 变量不更新，静默失败（无日志）
- **文件**: [handlers/action.py:95-99](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py#L95-L99)

#### N5-017 | `同步宏`/`异步宏` 文件不存在时静默继续

- **模块**: 动作块
- **故障点**: `handlers/control.py:113-116` 仅 `print()` → `_execute_flow(next)`，无 log_error
- **用户预期**: 宏文件找不到时应该有明显错误提示
- **实际情况**: 控制台一行日志，流程继续走 next，用户以为执行成功
- **文件**: [handlers/control.py:113-116](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L113-L116) / [handlers/control.py:149-152](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L149-L152)

#### N5-018 | `找图点击` 所有异常统一走 `not_found` 端口

- **模块**: 预设
- **故障点**: `handlers/preset.py:78-80` `except Exception: → _execute_flow(not_found)`
- **用户预期**: "模板图片损坏"应区别于"图片未出现"
- **实际情况**: IO错误、cv2错误全部当"没找到"处理 → 用户不停降低阈值重试，浪费时间
- **文件**: [handlers/preset.py:78-80](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/preset.py#L78-L80)

#### N5-019 | `数学运算` 除零静默返回0

- **模块**: 变量
- **故障点**: `handlers/variable.py:88` `lambda: a/b if b!=0 else 0` — 无日志
- **用户预期**: 除零应报错或警告
- **实际情况**: 结果静默变0，后续链路全部污染，用户排查困难
- **文件**: [handlers/variable.py:88](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L88)

#### N5-020 | `数学运算`/`数学函数` 非法输入静默返回0

- **模块**: 工具
- **故障点**: `handlers/utility.py:62-63` 除零/取模; `handlers/utility.py:83-86` sqrt/log 负数 → 全部返回0无警告
- **用户预期**: 错误输入应有明显反馈
- **实际情况**: 静默返回0，公式链污染
- **文件**: [handlers/utility.py:62-63](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L62-L63) / [handlers/utility.py:83-86](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L83-L86)

#### N5-021 | `书签` handler 手动解析 hwnd，不走统一 `_get_hwnd`

- **模块**: 工具
- **故障点**: `handlers/utility.py:213-223` 重新实现 hwnd 解析，不走引擎缓存
- **用户预期**: 所有节点的 hwnd 获取行为一致
- **实际情况**: bookmark 不走缓存；直接填数字hwnd会导致解析失败
- **文件**: [handlers/utility.py:213-223](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L213-L223)

#### N5-022 | 所有检测节点 `store_var` 输出变量被标记为 `varRef`

- **模块**: 检测
- **故障点**: `nodes.js:183-184` `_normalizeSchema` auto-varRef；后端 `nodes/detection.py` 也有 `"varRef":True`
- **用户预期**: "存入变量"字段应该让用户创建新变量名（输出变量）
- **实际情况**: UI显示 `$` 变量选择器，用户以为要从已有变量中引用值 → 输入/输出变量混淆
- **文件**: [nodes.js:183-184](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L183-L184) + [nodes/detection.py:40](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/detection.py#L40)

#### N5-023 | `变量运算` store_var 同样输出变量标记为 varRef

- **模块**: 变量
- **故障点**: 同 N5-022 模式，影响 var_math/var_string/var_convert
- **用户预期**: 同上
- **实际情况**: 同上
- **文件**: [nodes/variable.py:36](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/variable.py#L36)

#### N5-024 | `按键动作` type 模式多字符输入无间隔控制

- **模块**: 动作
- **故障点**: `handlers/action.py:118-126` type 模式下字符全部瞬间发出
- **用户预期**: 按键type模式应有字符间隔参数（类似"文本输入"的interval）
- **实际情况**: 字符瞬间全发，游戏可能来不及处理导致丢字符；用户必须改用"文本输入"节点
- **文件**: [handlers/action.py:118-126](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py#L118-L126)

#### N5-025 | `屏幕状态` frozen 检测在非 wait 模式下始终返回 false

- **模块**: 检测
- **故障点**: frozen 需要上一帧做对比；第一帧 `last_img=None` → `found=False`
- **用户预期**: 非wait模式下也能检测画面是否冻结
- **实际情况**: 无基线帧可对比 → 永远返回false → 走no端口，用户以为"没冻结"
- **文件**: [handlers/detection.py:523-530](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L523-L530)

#### N5-026 | `定时器` `repeat_count` 被读取但从不在轮询中使用

- **模块**: 监视器
- **故障点**: `handlers/monitor.py:106` 解析了；但 poll_loop 中 timer 永远返回 `found=True`，限制由 `max_triggers` 控制
- **用户预期**: `repeat_count=5` 触发5次后停止
- **实际情况**: repeat_count 是死参数，实际由 max_triggers 控制 → 两个语义重叠参数，用户困惑
- **文件**: [handlers/monitor.py:106](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L106) + [handlers/monitor.py:139-141](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L139-L141)

#### N5-027 | 复制-粘贴不携带连线信息

- **模块**: 画布/UI
- **故障点**: `editor-app.js:1544-1550` `_clipboard` 只存 nodeType/params/pos/customName
- **用户预期**: 复制一个有4条连线的节点→粘贴→连线一起保留
- **实际情况**: 粘贴后所有连线丢失，用户必须手动重连每根线
- **文件**: [editor-app.js:1544-1550](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L1544-L1550)

#### N5-028 | `图像匹配` pyramid+multi_match 每次全量覆盖 store_var

- **模块**: 检测
- **故障点**: `handlers/detection.py:364-367` wait模式下每次匹配覆盖存储变量（非追加）
- **用户预期**: 累积多次匹配结果
- **实际情况**: 每次匹配结果覆盖之前结果，旧数据丢失
- **文件**: [handlers/detection.py:364-367](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L364-L367)

---

### 🟡 中优先级（10项）

#### N5-029 | 前端 `validateGraph` 不检查 `flow/end` 节点

- **故障点**: `editor-app.js:1073-1084` 只检查 start 和可执行节点；后端 `compiler.py:93-98` 有 end 检查
- **用户预期**: 我在画布上的错误操作应该在点击运行前就有提示
- **实际情况**: 前后端校验不一致，end节点配置错误只能等到运行时才报
- **文件**: [editor-app.js:1073-1084](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L1073-L1084) / [compiler.py:93-98](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/compiler.py#L93-L98)

#### N5-030 | flow分类颜色(红)与flow/start节点颜色(绿)不一致

- **故障点**: `nodes.js:698` 分类色 `#ff0000ff`；`nodes/flow.py:5` start色 `#99ff00ff`
- **用户预期**: 工具箱"流程"分类颜色与拖出来的节点色协调
- **实际情况**: 红色分类标题→拖出绿色节点，视觉割裂（4期B-88已采纳但本实例独特）
- **文件**: [nodes.js:698](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L698) / [nodes/flow.py:5](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/flow.py#L5)

#### N5-031 | `_pickSummaryKeys` 中 `mode` 被硬编码 skip

- **故障点**: `core.js:199` skip集合包含 `mode`
- **用户预期**: 能在画布上快速切换坐标模式（screen↔window↔relative）
- **实际情况**: 高频操作必须打开属性面板才能切换，效率低
- **文件**: [core.js:199](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L199)

#### N5-032 | `窗口管理` frontend fallback `store_hwnd_var` 缺 `varRef`

- **故障点**: `nodes.js:331` fallback无 varRef；但 `_normalizeSchema` 自动修复
- **用户预期**: 无感知（运行时自动修复）
- **实际情况**: 定义不一致，靠硬编码兜底 → 可维护性差；自定义插件不会自动修复
- **文件**: [nodes.js:331](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/nodes.js#L331) + [nodes/action.py:102](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/action.py#L102)

#### N5-033 | `target_task` nodeRef（指向node_id）但传给 task_pool 需用 task_id

- **故障点**: `handlers/monitor.py:86-94` 直接传 node_id 给 `task_pool.stop()` 等
- **用户预期**: 监视器触发后能正确停止/暂停/恢复指定的异步任务
- **实际情况**: 如果 task_pool 内部索引键不是纯 node_id，则查找失败 → 静默无效
- **文件**: [handlers/monitor.py:86-94](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L86-L94)

#### N5-036 | `设置变量` name 字段无 `varRef`，不支持动态变量名

- **故障点**: `nodes/variable.py:11` name 无 varRef
- **用户预期**: 根据变量值动态命名新变量 `${dynamic_name}`
- **实际情况**: 不支持；用户尝试 → 原样存储 `${dynamic_name}` → 后续双层引用失败
- **文件**: [nodes/variable.py:11](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/variable.py#L11)

#### N5-034 | 右键菜单"粘贴"在无剪贴板时仍显示可用

- **故障点**: `editor-app.js:2262` 无 `_clipboard` 检查
- **用户预期**: 菜单项在不可用时应该灰色禁用
- **实际情况**: 任何时间都能点"粘贴"，点了才 toast 提示"剪贴板为空"
- **文件**: [editor-app.js:2262](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L2262)

#### N5-035 | 小地图节点颜色依赖 `_accentColor` 可能不准

- **故障点**: `core.js:1622-1626` 使用 `_accentColor || '#718096'` 灰色fallback
- **用户预期**: 小地图颜色与主画布节点颜色一致
- **实际情况**: 如 _accentColor 未设置，所有节点在小地图中都是灰色
- **文件**: [core.js:1622-1626](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L1622-L1626)

#### N5-037 | Ctrl+滚轮缩放后不更新状态栏百分比

- **故障点**: `core.js` 的 `_onWheel` 缩放逻辑中没有调用 `updateStatusBar()`
- **用户预期**: 状态栏显示当前实际缩放比例
- **实际情况**: Ctrl滚轮缩放后状态栏数字不更新，与实际不一致
- **文件**: [core.js:1375-1387](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L1375-L1387)

#### N5-038 | `_pickSummaryKeys` skip 排除 `tolerance` 等调参

- **故障点**: `core.js:199` skip 包含 tolerance/change_threshold/area_ratio_threshold
- **用户预期**: 画布上能直接调整容差/阈值（高频迭代操作）
- **实际情况**: 每次调容差都要打开属性面板 → 严重拖慢迭代效率
- **文件**: [core.js:199](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L199)

---

### 💡 建议（5项）

#### N5-039 | 编译器不对孤立 `flow/end` 给出提示

- **故障点**: `compiler.py:93-98` 不检查 end 节点是否有 flow_inputs
- **用户预期**: 拖出但没连线的 end 节点应该有警告
- **实际情况**: 完全无声，无用节点占据画布
- **文件**: [compiler.py:93-98](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/compiler.py#L93-L98)

#### N5-040 | `race_win` 节点无 race scope 时不报错

- **故障点**: `handlers/control.py:593-615` 依赖 branch_ctx.scope_id；无scope时只设winner_branch+调next
- **用户预期**: 无scope的race_win应该提示错误
- **实际情况**: 静默无效，用户困惑
- **文件**: [handlers/control.py:593-615](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L593-L615)

#### N5-041 | `var_set` 无 data 输入端口

- **故障点**: `nodes/variable.py:7` 只有 flow 输入
- **用户预期**: 从上游检测节点拖一根数据线到 var_set 直接赋值
- **实际情况**: 必须手写 `${node.result}` 引用，图形化编程体验断裂
- **文件**: [nodes/variable.py:7](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/nodes/variable.py#L7)

#### N5-042 | 工具栏缺少撤销/重做按钮

- **故障点**: 只有快捷键 Ctrl+Z/Y，无工具栏可视按钮
- **用户预期**: 新用户能看到撤销按钮
- **实际情况**: 新用户不知道快捷键 → 误操作无法回退；可发现性差
- **文件**: [editor-app.js:2282-2289](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L2282-L2289)

#### N5-043 | 小地图点击导航可能导致视口超出画布边界

- **故障点**: `core.js:1662-1674` 仅将视口中心对准点击位置，无边界约束
- **用户预期**: 小地图导航后视口应在画布有效区域内
- **实际情况**: 点击小地图边角 → 视口一半空白
- **文件**: [core.js:1662-1674](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/core.js#L1662-L1674)

---

## 二、本期优先修复批次建议

### P0 — 阻塞性（并发安全）

1. **N5-005** — fork在循环体内清除check_results（concurrency bug）
2. **N5-006** — race cancel_on_first失效

### P1 — 严重级

3. **N5-007** — 监视器后台线程不暂停（→合并修复N5-009~N5-012同类5项暂停漏洞）
4. **N5-004** — 多截图源共存冲突
5. **N5-008** — 9个工具节点自动隐式变量

### P2 — 高优先级

6. **N5-003** — 鼠标点击缓动不一致
7. **N5-013~N5-015** — handler双重解析（3模块合并修复）
8. **N5-022/N5-023** — 输出变量varRef UI混淆
9. **N5-027** — 粘贴丢失连线

---

## 三、附录：历史Bug汇总（3期/4期）

> 以下为之前bug文档中的拒绝、搁置、后期考虑项，供统一bug统计查阅。

---

### A. 3期+4期 ✅ 已采纳（已/待修复）— 3期28项 + 4期41项

#### 3期采纳（B-64 ~ B-88，共28项）

| 编号 | 级别 | 模块 | 简述 |
|------|------|------|------|
| B-64 | 🔴🔴🔴 | 前端核心 | `_checkShowWhen`不支持`>=`，fork/join/race分支3-8配置失效 |
| B-65 | 🔴🔴🔴 | 引擎核心 | `_resolve_value`不处理数组内变量引用，9个rect/region varRef失效 |
| B-66 | 🔴🔴🔴 | 引擎核心 | 普通节点异常后执行链断裂，需增加重试机制+异常分类 |
| B-67 | 🔴🔴 | 控制 | join前端缺branch_required_3~8 |
| B-68 | 🔴🔴 | 检测+监视 | 颜色解析不一致，monitor直接字符串索引可能崩溃 |
| B-69 | 🔴 | 动作 | key_action "press"语义与mouse_click不一致 |
| B-70 | 🔴 | 动作 | program_open句柄获取失败需加日志 |
| B-71 | 🔴 | 检测+监视 | sample_mode选项不一致+英文参数名改中文 |
| B-72 | 🔴 | 监视器 | monitor_time缺少循环触发参数(recheck_delay_ms等) |
| B-73 | 🔴 | 变量 | var_math round隐藏B端口 |
| B-74 | 🔴 | 预设 | preset_read_text异常不续流(随B-66) |
| B-75 | 🔴 | 预设 | preset_click/preset_find_click button缺middle |
| B-76 | 🔴 | 检测/预设 | rect `[0,0,0,0]`判断不健壮 |
| B-77 | 🔴 | 工具 | logic_op bool转换对字符串不安全 |
| B-78 | 🔴 | 检测 | check_image confidence输出未声明 |
| B-79 | 🔴 | 控制 | join target_fork_node_id nodeRef不完善 |
| B-80 | 🔴 | 前端 | 模拟执行不按流程顺序+添加模拟执行按钮 |
| B-81 | 🟡 | 前端 | 工具箱缺plugin分类 |
| B-82~B-85 | 🟡 | 各模块 | showWhen/varRef补充(4处) |
| B-86 | 🟡 | 前端 | 拼音搜索映射缺失/过时(批量修复13+9条) |
| B-87 | 🟡 | 工具 | utility/string_op 缺regex_extract操作 |
| B-88 | 🟡 | 前端 | 分类颜色多处定义不一致 |

#### 4期修复（F-01 ~ F-41，共41项）

| 批次 | 项数 | 简述 |
|------|------|------|
| 第一批(前端致命+核心) | 8 | F-01~F-03, F-21~F-23, F-29 |
| 第二批(varRef统一修复) | 17 | F-04~F-20, F-26 |
| 第三批(上期遗留) | 10 | F-27, F-28, F-34~F-41 |
| 第四批(安全+体验) | 6 | F-30~F-33, F-38~F-40 |

---

### B. 3期+4期 ❌ 拒绝项（共11项）

#### 3期拒绝（7项）

| 编号 | 问题 | 拒绝原因 |
|------|------|----------|
| X-13 | mouse_scroll缺坐标参数 | 非核心场景，有替代方案 |
| X-14 | mouse_move_rel缺easing参数 | 短距离缓动不可感知，增加复杂度收益低 |
| X-15 | mouse_click vs mouse_move 默认值不一致 | 两种不同使用场景，设计合理 |
| X-16 | fork多分支截图竞争 | 符合预期，微小变化可接受 |
| X-17 | email插件密码明文存储 | 插件作者自行解决 |
| X-18 | check_ocr隐式变量存储 | 维持现状，用户可显式指定store_var |
| X-19 | bookmark name/remark无实际功能 | 仅作标注用途，维持现状 |

#### 2期拒绝维持（12项）

| 编号 | 问题 | 维持原因 |
|------|------|----------|
| X-01~X-09 | 2期拒绝项 | 用户决策维持 |
| X-10 | record插件回放缓冲 | 有意设计 |
| X-11 | notify弹窗阻塞 | 有意设计 |
| X-12 | HTML注入/XSS | 本地应用低风险 |

#### 4期拒绝（2项）

| 编号 | 问题 | 拒绝理由 |
|------|------|----------|
| R-01 | 录制功能使用start_replay_buffer而非start_record | 设计如此：缓存+回放模式，非bug |
| R-02 | 鼠标绑定只支持侧键 | 键盘本身支持触发宏，鼠标其他按键自有用途 |

---

### C. 3期+4期 ⏳ 后期考虑/搁置（共33项）

#### 3期后期考虑（22项）

| 编号 | 问题 | 说明 |
|------|------|------|
| P-01 | mouse_scroll delta 120不直观 | 加tooltip说明即可 |
| P-02 | var_compare字符串比较回退不直观 | 加说明即可 |
| P-06 | string_op concat只能拼接两个 | 功能增强 |
| P-10 | preset_find_click没有移动动画 | 功能增强 |
| P-13 | text_input中文输入可能不稳定 | 需实际测试验证 |
| P-14 | Ctrl+D只支持单节点复制 | 功能增强 |
| P-15 | 拖拽节点位置不可撤销 | 需配合UndoManager重构 |
| P-18 | 坐标拾取hwnd_var被覆盖 | 设计取舍 |
| P-19 | 拾取后自动修改mode | 设计取舍 |
| P-21 | COMPLETED状态停止按钮行为异常 | 体验优化 |
| P-22 | 新建画布保存确认逻辑可能中断 | 体验优化 |
| P-23 | 插件串行加载速度慢 | 性能优化 |
| P-25 | UndoManager重复push | 需梳理所有push调用点 |
| P-26 | store_hwnd_var未被_pickSummaryKeys跳过 | 仅影响内联显示 |
| P-28 | _graphDirty在undo/redo后状态不正确 | 需精确追踪dirty状态 |
| P-29 | ESC键事件监听器泄漏 | 内存泄漏量极小 |
| P-30 | 拾取修改属性不触发撤销系统 | 需配合UndoManager重构 |
| P-31 | flashNode多次调用产生多个setTimeout | 视觉效果问题 |
| P-32 | check_results无锁并发读写 | Python GIL提供基本保护 |
| P-34 | 变量面板用户变量不去重 | 不影响功能正确性 |
| P-35 | 多处try-catch静默吞掉错误 | 仅影响调试 |
| P-36 | 插件backendAction未存入注册表 | 第三方插件生态发展后再改 |
| P-37 | color字段不支持varRef输入 | 颜色变量引用需求极低 |
| P-39 | _pinyinMap过时条目清理 | 与B-86合并处理 |
| P-40 | 变量面板类型推断不完整 | 可接受"未知类型" |

#### 4期搁置（15项）

| 编号 | 严重度 | 问题 | 搁置理由 |
|------|--------|------|----------|
| D-01 | 🔴 | 框选触发属性面板短暂闪烁 | 仅短暂闪烁，不影响功能 |
| D-02 | 🔴 | flow连线源端口未限制一对一 | 需更大设计讨论 |
| D-03 | 🔴 | key_action后端缺keySelector属性 | 影响有限 |
| D-04 | 🔴 | get_window_at_mouse不安全用法 | 少数Python版本，概率低 |
| D-05 | 🔴 | show_desktop_popup无法自动关闭 | 弹窗手动关闭即可 |
| D-06 | 🔴 | notify插件Unicode窗口字体问题 | 仅影响非中文系统 |
| D-07 | 🟡 | mouse_move_rel缺easing参数 | 设计取舍(R-01原已拒绝) |
| D-08 | 🟡 | monitor_color缺check_mode=exact | 与检测不一致但不影响 |
| D-09 | 🟡 | const节点varRef与"常量"语义矛盾 | 设计取舍 |
| D-10 | 🟡 | Ctrl+C复制不含customName | 影响有限 |
| D-11 | 🟡 | _getFlowOrderedNodes未区分flow/data | 模拟执行顺序问题 |
| D-12 | 🟡 | 连续删除连线连接指示状态不准 | 视觉小问题 |
| D-13 | 🟡 | ghost拖拽结束多选节点opacity未恢复 | 视觉小问题 |
| D-14 | 🟡 | screenshot插件fullscreen+window矛盾 | 设计取舍 |
| D-15 | 🟡 | bridge API返回格式不统一 | 代码规范问题 |

---

## 四、全量Bug统计

| 分类 | 数量 | 来源 |
|------|------|------|
| 🔴🔴 致命（本期新发现） | 8 | N5-001~008 |
| 🔴 高优（本期新发现） | 20 | N5-009~028 |
| 🟡 中优（本期新发现） | 10 | N5-029~038 |
| 💡 建议（本期新发现） | 5 | N5-039~043 |
| **本期新发现合计** | **43** | |
| ✅ 3期采纳（待/已修复） | 28 | B-64~B-88 |
| ✅ 4期修复（待/已修复） | 41 | F-01~F-41 |
| ❌ 历史拒绝 | 21 | 3期7+2期12+4期2 |
| ⏳ 历史搁置/后期考虑 | 37 | 3期22+4期15 |
| **全量合计** | **170** | |

---

**文档结束**
