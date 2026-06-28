# 自动化编辑器 Bug 修复意见书 — 第5期

> **审查人**: 高级架构师
> **审查日期**: 2026-05-02
> **审查范围**: 5期Bug检查汇总.md 全部43项
> **审查原则**: 以 `docs/设计标准/` 为准绳，设计意图明确的非Bug项移除；暂停行为按用户决策规范处理；技术债务降级
> **决策依据**: 08-已知缺陷与待办功能.md 第4/5/6节

---

## 审查结论概览

| 分类 | 数量 | 说明 |
|------|------|------|
| ✅ 采纳（需修复） | 22 | 功能缺陷、数据正确性、行为不一致 |
| 🔧 技术债务 | 3 | 双重解析，当前幂等不影响功能 |
| ❌ 拒绝（非Bug/设计意图） | 10 | 设计标准已明确或用户决策确认 |
| ⏳ 后期考虑 | 8 | UI体验优化、低频场景 |

---

## 一、✅ 采纳的 Bug（24项）

### 1.1 🔴🔴 严重/致命级（6项）

#### N5-001 | `flow/end` handler 死代码 — handler 永不被调用

- **模块**: 流程
- **文件**: [engine.py:678-681](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L678-L681) + [handlers/flow.py:10-12](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/flow.py#L10-L12)
- **问题**: engine.py 在到达 handler 调用之前就 `return` 了，`_handle_flow_end` 永远不被调用
- **修复方案**: 将全局停止逻辑移入 `_handle_flow_end` handler 内部，由 handler 调用 `ctx.stop_event.set()` + `ctx.task_pool.stop_all()`，引擎正常调用 handler
- **注意**: 全局停止行为本身是设计意图（08-5节），但 handler 不应是死代码

#### N5-003 | `鼠标点击` 移动使用线性插值（无缓动），而 `鼠标移动` 支持缓动函数

- **模块**: 动作
- **文件**: [handlers/action.py:85-86](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py#L85-L86) / [handlers/action.py:535-538](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py#L535-L538)
- **问题**: 鼠标点击设置移动耗时后僵硬线性移动，必须组合两个节点才能缓动
- **修复方案**: `mouse_click` 的移动路径改用 `_eased_move()`，与 `mouse_move` 行为一致

#### N5-004 | 多个`截图源`节点并存时无法各自独立配置

- **模块**: 检测
- **文件**: [handlers/detection.py:42-52](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L42-L52)
- **问题**: `CaptureManager` 全局单例，第二个截图源配置被静默忽略
- **修复方案**: 改为按 node_id 管理多个截图实例，或检测参数变化时重启 DXGI

#### N5-005 | `fork` 在循环体内时，下一迭代清除首轮运行分支的 `check_results`

- **模块**: 控制
- **文件**: [engine.py:129](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L129) + [engine.py:478-481](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/engine.py#L478-L481) + [handlers/control.py:383](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L383)
- **问题**: `BranchContext` 使用 `parent_ctx.check_results` 共享引用（非拷贝），循环 reset 清除其他分支数据
- **修复方案**: `_reset_body_nodes` 清除 check_results 时，仅清除属于当前迭代节点的 key，不影响仍在运行的分支线程的 key

#### N5-006 | `race` 的 `cancel_on_first=false` 参数完全失效

- **模块**: 控制
- **文件**: [handlers/control.py:706-715](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L706-L715)
- **问题**: race_worker 的 finally 块无条件取消其他分支，`cancel_on_first` 形同虚设
- **修复方案**: finally 块中增加 `if cancel_on_first:` 条件判断

#### N5-008 | 9个工具运算/常量节点自动创建不可预测的 `_out` 隐式变量

- **模块**: 工具
- **文件**: [handlers/utility.py:36](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L36)
- **问题**: 变量名 `{数字}_out` 不可预测，变量选择器被污染
- **修复方案**: 改为使用节点显示名或自定义名作为变量前缀，如 `{customName}_out` 或 `{displayName}_out`，使变量名可预测。若节点无自定义名则仍用 node_id

### 1.2 🔴 高优先级（12项）

#### N5-009 | 检测节点 wait 轮询循环不响应暂停

- **模块**: 检测
- **文件**: [handlers/detection.py:121](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L121)
- **问题**: 只检查 `ctx.stop_event`，不检查 `ctx.pause_event`
- **修复方案**: 轮询循环中添加 `ctx.pause_event.wait()` 暂停响应。暂停期间倒计时继续，恢复后若超时已到则立即返回

#### N5-010 | `等待条件`/`序列检测`/`状态机` 轮询不暂停

- **模块**: 控制
- **文件**: [handlers/control.py:200/228/256](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L200)
- **修复方案**: 同 N5-009

#### N5-011 | `延迟` precise_sleep 不检查暂停

- **模块**: 工具
- **文件**: [handlers/utility.py:240-241](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L240-L241)
- **问题**: precise_sleep 只检查 stop_event
- **修复方案**: precise_sleep 中添加 pause_event 检查。暂停期间底层计时器不停止，恢复后若延迟已过期则立即完成（见08-6.2节）

#### N5-012 | `同步宏` 短路径 precise_sleep 不暂停

- **模块**: 动作块
- **文件**: [handlers/control.py:140](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L140)
- **修复方案**: 同 N5-011，短路径与长路径行为应一致

#### N5-016 | `鼠标点击` `store_hwnd_var` 在 screen/current 模式下静默忽略

- **模块**: 动作
- **文件**: [handlers/action.py:95-99](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py#L95-L99)
- **问题**: screen/current 模式下变量不更新，无日志
- **修复方案**: screen 模式下也应存储当前前台窗口句柄；current 模式下存储鼠标所在窗口句柄。若无法获取则 log_warning

#### N5-017 | `同步宏`/`异步宏` 文件不存在时静默继续

- **模块**: 动作块
- **文件**: [handlers/control.py:113-116](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L113-L116) / [handlers/control.py:149-152](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L149-L152)
- **问题**: 仅 `print()` → `_execute_flow(next)`，无 log_error
- **修复方案**: 改为 `ctx.log_error("宏文件不存在: " + path)` 并走 fail 端口（如有）或 next 端口

#### N5-018 | `找图点击` 所有异常统一走 `not_found` 端口

- **模块**: 预设
- **文件**: [handlers/preset.py:78-80](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/preset.py#L78-L80)
- **问题**: IO错误、cv2错误全部当"没找到"处理
- **修复方案**: 区分异常类型——IO错误/cv2错误走 `next` 端口并 log_error；模板匹配未找到走 `not_found` 端口

#### N5-019 | `数学运算` 除零静默返回0

- **模块**: 变量
- **文件**: [handlers/variable.py:88](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/variable.py#L88)
- **问题**: 无日志，后续链路全部污染
- **修复方案**: 除零时 `ctx.log_error("除零错误: a/b where b=0")` 并返回 0（保持不崩溃）

#### N5-020 | `数学运算`/`数学函数` 非法输入静默返回0

- **模块**: 工具
- **文件**: [handlers/utility.py:62-63](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L62-L63) / [handlers/utility.py:83-86](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L83-L86)
- **修复方案**: 非法输入时 `ctx.log_error(...)` 并返回 0

#### N5-025 | `屏幕状态` frozen 检测在非 wait 模式下始终返回 false

- **模块**: 检测
- **文件**: [handlers/detection.py:523-530](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L523-L530)
- **问题**: frozen 需要上一帧做对比；第一帧 `last_img=None` → `found=False`
- **修复方案**: 非 wait 模式下取两帧进行比对——先截一帧作为基线，短暂等待后截第二帧，两帧对比判断是否冻结

#### N5-026 | `定时器` `repeat_count` 被读取但从不在轮询中使用

- **模块**: 监视器
- **文件**: [handlers/monitor.py:106](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L106) + [handlers/monitor.py:139-141](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L139-L141)
- **问题**: repeat_count 是死参数，实际由 max_triggers 控制
- **修复方案**: 移除 `repeat_count` 参数，统一使用 `max_triggers`。或添加 showWhen 使两者互斥并明确语义

### 1.3 🟡 中优先级（6项）

#### N5-021 | `书签` handler 手动解析 hwnd，不走统一 `_get_hwnd`

- **文件**: [handlers/utility.py:213-223](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/utility.py#L213-L223)
- **修复方案**: 改用引擎统一的 `_get_hwnd()` 函数，走缓存

#### N5-024 | `按键动作` type 模式多字符输入无间隔控制

- **文件**: [handlers/action.py:118-126](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py#L118-L126)
- **问题**: 字符瞬间全发，游戏可能丢字符
- **修复方案**: type 模式下使用全局参数 `text_input_delay` 作为字符间隔（已有全局参数，但 type 模式未使用）

#### N5-027 | 复制-粘贴不携带连线信息

- **文件**: [editor-app.js:1544-1550](file:///g:/宏引擎/宏驱动 webui 2.7.7/webui/modules/auto/editor-app.js#L1544-L1550)
- **修复方案**: 粘贴时保留被复制节点之间的连线。连到复制范围外节点的连线不保留（见08-5节设计意图）

#### N5-028 | `图像匹配` pyramid+multi_match 每次全量覆盖 store_var

- **文件**: [handlers/detection.py:364-367](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/detection.py#L364-L367)
- **问题**: wait 模式下每次匹配覆盖存储变量（非追加）
- **修复方案**: multi_match 模式下累积结果到数组而非覆盖

#### N5-033 | `target_task` nodeRef（指向node_id）但传给 task_pool 需用 task_id

- **文件**: [handlers/monitor.py:86-94](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L86-L94)
- **问题**: 如果 task_pool 内部索引键不是纯 node_id，则查找失败
- **修复方案**: 确认 task_pool 的索引键是否为 node_id；若是则无问题；若不是则添加映射

---

## 二、🔧 技术债务（3项）

> 当前幂等不影响功能，但架构上应统一。若将来 `_resolve_value` 有副作用则出问题。

| 编号 | 问题 | 文件 | 建议 |
|------|------|------|------|
| N5-013 | `鼠标点击` handler 对引擎已解析参数重复调用 `_resolve_value` | [handlers/action.py:69-72](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/action.py#L69-L72) | 统一为引擎层解析，handler 不再重复解析 |
| N5-014 | `循环计数`/`等待条件`/`goto` 等全部 handler 双重解析 | [handlers/control.py:63/80/196-197/216/246-247](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/control.py#L63) | 同上 |
| N5-015 | `_handle_monitor_node` 全部参数双重解析 | [handlers/monitor.py:101-110](file:///g:/宏引擎/宏驱动 webui 2.7.7/automation/handlers/monitor.py#L101-L110) | 同上 |

**统一修复方案**: 在引擎层 `_execute_node` 中统一解析所有 varRef 参数后，将解析结果写入 `node._resolved_params`，handler 直接使用 `_resolved_params` 而非再次调用 `_resolve_value`。此改动影响面大，建议作为独立重构任务。

---

## 三、❌ 拒绝项（10项）

| 编号 | 问题 | 拒绝理由 | 依据 |
|------|------|----------|------|
| N5-002 | `flow/end` 在fork分支中触发全局停止 | 设计意图：任何分支到达结束节点 = 任务完成 | 08-5节 + 02-并发模型 8.3节 |
| N5-007 | 监视器后台线程不响应暂停 | 监视器模型不允许暂停恢复 | 08-4节 + 08-6.1节 |
| N5-022 | 检测节点 `store_var` 输出变量标记为 `varRef` | 设计意图：允许用户通过 `$` 按钮选择已有变量进行覆盖，或使用 `${动态变量名}` 实现运行时决定存储目标 | 08-5节 |
| N5-023 | `变量运算` store_var 同样标记为 varRef | 同 N5-022 | 08-5节 |
| N5-030 | flow分类颜色与flow/start节点颜色不一致 | 起始/结束节点颜色特殊化是有意设计 | 08-4节 + 08-5节 |
| N5-032 | `窗口管理` frontend fallback store_hwnd_var 缺 varRef | 运行时 `_normalizeSchema` 自动修复，非功能性Bug | 可维护性差但不影响功能 |
| N5-034 | 右键菜单"粘贴"在无剪贴板时仍显示可用 | 极低影响，仅多一次点击 | UI体验微小 |
| N5-035 | 小地图节点颜色依赖 `_accentColor` 可能不准 | fallback 灰色可接受 | UI体验微小 |
| N5-036 | `设置变量` name 字段无 varRef，不支持动态变量名 | 用户若需动态命名，再使用一次设置变量节点 | 08-4节 |
| N5-031 | `_pickSummaryKeys` 中 mode 被硬编码 skip | 坐标模式与坐标捕获器联动，单独修改坐标模式意义不大 | 08-4节 |

---

## 四、⏳ 后期考虑（8项）

| 编号 | 问题 | 说明 |
|------|------|------|
| N5-029 | 前端 validateGraph 不检查 flow/end 节点 | 用户可以不配置 end 节点（08-4节），但前后端校验一致性可后期优化 |
| N5-037 | Ctrl+滚轮缩放后不更新状态栏百分比 | 状态栏信息不准确，体验问题 |
| N5-038 | `_pickSummaryKeys` skip 排除 tolerance 等调参 | 高频调参操作效率低，但需评估哪些参数适合内联编辑 |
| N5-013 | `鼠标点击` 双重解析 | 见技术债务章节 |
| N5-014 | 控制 handler 双重解析 | 见技术债务章节 |
| N5-015 | 监视器 handler 双重解析 | 见技术债务章节 |
| N5-008 | 隐式变量名可预测性改进 | 已采纳但变量命名策略可后期进一步优化 |
| N5-026 | `定时器` repeat_count 与 max_triggers 语义重叠 | 已采纳移除 repeat_count，但需评估向后兼容 |

---

## 五、修复优先级排序

### P0 — 致命级（必须首先修复）

1. **N5-005** — fork 循环体内 check_results 数据竞争
2. **N5-006** — race cancel_on_first=false 失效
3. **N5-001** — flow/end handler 死代码

### P1 — 严重级

4. **N5-003** — 鼠标点击移动无缓动
5. **N5-004** — 多截图源配置被忽略
6. **N5-008** — 隐式变量名不可预测

### P2 — 暂停响应专项（5项统一修复）

7. **N5-009** — 检测节点 wait 轮询不暂停
8. **N5-010** — 控制节点轮询不暂停
9. **N5-011** — 延迟 precise_sleep 不暂停
10. **N5-012** — 同步宏短路径不暂停

> 暂停响应修复原则：监视器不暂停（08-6.1节），其余组件统一添加 pause_event 检查。延迟类暂停恢复后若超时已到则立即完成（08-6.2节）。

### P3 — 高优先级

11. **N5-016** — store_hwnd_var 静默忽略
12. **N5-017** — 宏文件不存在静默继续
13. **N5-018** — 找图点击异常不区分
14. **N5-019** — 除零静默返回0
15. **N5-020** — 非法输入静默返回0
16. **N5-022** — store_var 标记为 varRef
17. **N5-025** — frozen 非wait模式取两帧比对
18. **N5-026** — repeat_count 死参数

### P4 — 中优先级

19. **N5-021** — 书签 hwnd 解析不走缓存
20. **N5-023** — 变量运算 store_var 标记为 varRef
21. **N5-024** — 按键 type 模式无间隔
22. **N5-027** — 复制粘贴保留内部连线
23. **N5-028** — multi_match 覆盖而非累积
24. **N5-033** — target_task nodeRef/task_id 映射

---

## 六、修复依赖关系

```
N5-001 (flow/end handler) ──→ 无依赖，独立修复
N5-005 (check_results 竞争) ──→ 需理解 BranchContext 共享机制
N5-006 (cancel_on_first) ──→ 简单条件判断，独立修复
N5-009~012 (暂停响应) ──→ 统一修改 precise_sleep + 轮询循环，需先更新 precise_sleep_v5 签名
N5-022 + N5-023 (store_var varRef) ──→ 同类问题，与2期 B-17 方案一致
N5-025 (frozen 两帧) ──→ 需设计非wait模式下的双帧截取间隔
```

---

*审查完毕。请开发人员按优先级排序进行修复，如有疑问请对照 `docs/设计标准/08-已知缺陷与待办功能.md` 确认。*
