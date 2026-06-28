# 🔧 自动化编辑器 — 4期Bug修复汇总

> 审查来源 : 4期节点审查.md
> 汇总日期 : 2026-05-02
> 决策原则 : 致命/严重级全修；上期采纳未修复必须修；varRef解析统一修；设计取舍搁置；外部插件自身问题拒绝

---

## 一、✅ 修复清单（共 41 项）

### A. 致命级 — 核心功能完全失效（3项）

| 序号 | 模块 | 问题 | 位置 | 修复方式 |
|------|------|------|------|----------|
| F-01 | property.js | `this._container` 从未赋值，showWhen 字段只能显示不能隐藏 | property.js:1561 | render() 中添加 `this._container = container` |
| F-02 | property.js | 按键选择器 `_openKeySelector` 使用 `getNode()` 而非 `getNodeById()`，按键选择功能完全失效 | property.js:895 | 改为 `AutomationCore.lgGraphObj.getNodeById(nodeId)` |
| F-03 | core.js | `_checkShowWhen` 多条件使用 OR 逻辑，跨字段条件应为 AND | core.js:152-186 | 区分同字段多值（OR）和跨字段条件（AND） |

### B. 严重级 — varRef 参数 `_resolve_value` 统一修复（17项）

> 同类问题批量修复：所有标记 `varRef: True` 的参数在 handler 中必须调用 `_resolve_value` 解析变量引用

| 序号 | 模块 | 参数 | 位置 |
|------|------|------|------|
| F-04 | detection/check_color | target_color | handlers/detection.py:78 |
| F-05 | detection/check_image | template_path | handlers/detection.py:302 |
| F-06 | detection/check_ocr | cache_interval_ms | handlers/detection.py:185 |
| F-07 | monitor/monitor_color | target_color | handlers/monitor.py:29 |
| F-08 | monitor/monitor_node | target_task | handlers/monitor.py:105 |
| F-09 | monitor/monitor_time | target_task | handlers/monitor.py:220 |
| F-10 | control/goto | target_node_id | handlers/control.py:216 |
| F-11 | control/call_script_sync | path | handlers/control.py:112 |
| F-12 | control/call_script_async | path | handlers/control.py:148 |
| F-13 | control/state_machine | states / fail_state | handlers/control.py:246-247 |
| F-14 | preset/preset_find_click | template_path / rect | handlers/preset.py:41-43 |
| F-15 | preset/preset_read_text | rect | handlers/preset.py:92 |
| F-16 | variable/var_convert | input_var | handlers/variable.py:180 |
| F-17 | monitor（通用） | interval / timeout | handlers/monitor.py — A-06/A-07 |
| F-18 | condition | cond_var | handlers/utility.py — A-08 |
| F-19 | string_op | param_a / param_b / param_c | handlers/utility.py — A-09 |
| F-20 | monitor/monitor_ocr | match_number | handlers/monitor.py — A-10 |

### C. 严重级 — 其他功能失效（8项）

| 序号 | 模块 | 问题 | 位置 | 修复方式 |
|------|------|------|------|----------|
| F-21 | core.js | 注释/分组选择时先置空 `_selectedNodeId` 再查找旧节点，高亮无法移除 | core.js:744-746, 975-977 | 先查找旧节点再置空 |
| F-22 | editor-app.js | PAUSED 状态下运行按钮可重新启动执行，导致多实例并行 | editor-app.js:1165 | runGraph 检查 PAUSED 状态 |
| F-23 | editor-app.js | PAUSED 状态运行按钮图标未重置，仍显示 spinner | editor-app.js:272-279 | 暂停时重置按钮图标 |
| F-24 | PluginManager | 全局 context 缺少 `_var_get_fn` / `_var_set_fn`，插件 set_variable 无效 | plugin_manager.py:15-17 | 全局 context 补充变量读写函数 |
| F-25 | nodes.js | `registerPluginNodes` 未调用 `_normalizeSchema`，插件节点显示异常 | nodes.js:747-765 | 注册时调用标准化 |
| F-26 | monitor/monitor_color | tolerance / change_threshold 未使用 `_resolve_value` | handlers/monitor.py — A-11 | 同 varRef 批量修复 |
| F-27 | monitor（通用） | auto_stop 完全无效 | handlers/monitor.py — A-12 | 实现 auto_stop 逻辑 |
| F-28 | variable/var_set | boolean 转换错误 | handlers/variable.py — A-13 | 修正 boolean 值解析 |

### D. 高优先级 — 用户体验与正确性（13项）

| 序号 | 模块 | 问题 | 位置 | 修复方式 |
|------|------|------|------|----------|
| F-29 | core.js | `_checkShowWhen` 的 `!=` 运算符在 undefined 时误判 | core.js:170-173 | undefined 时 `!=` 条件不应通过 |
| F-30 | property.js | 字符串/枚举/路径字段值未 HTML 转义，存在 XSS 风险 | property.js:455,506,534,608,628 | 值写入 DOM 前转义 |
| F-31 | control/seq_check | steps 参数在 handler 中完全未使用，误导用户 | handlers/control.py:223 | 删除或实现 |
| F-32 | automation_api.py | run_automation 旧任务超时未停止时新任务仍启动 | automation_api.py:62-64 | 启动前检查并停止旧任务 |
| F-33 | plugin_manager.py | 重载插件后未通知前端刷新节点定义 | plugin_manager.py:143-149 — A-54 | 重载后推送前端刷新 |
| F-34 | monitor/monitor_timer | repeat_count 缺少 `showWhen: "auto_stop=false"` 条件 | nodes/monitor.py:79 — A-22~A-26 | 添加 showWhen 条件 |
| F-35 | 多个节点 | showWhen 条件缺失（A-22~A-26 共5处） | 各节点定义 | 补全 showWhen 条件 |
| F-36 | property.js | 内联快捷参数不检查 showWhen — A-31 | property.js | 内联渲染时检查 showWhen |
| F-37 | property.js | 属性面板修改 mode 后节点内联字段不刷新 — A-32 | property.js | mode 变更时触发内联刷新 |
| F-38 | editor-app.js | 多次 Ctrl+V 粘贴节点位置重叠 — A-47 | editor-app.js:2543 | 添加 `_pasteCount` 递增偏移 |
| F-39 | plugin_manager.py | 插件后端注册空定义覆盖前端完整定义 — A-53 | plugin_manager.py | 空定义时不覆盖 |
| F-40 | preset/preset_read_text | 异常后 raise 导致节点执行中断 — A-56 | handlers/preset.py:131 | 改为走 no/match 分支 |

### E. 默认值不一致（3项）

| 序号 | 模块 | 问题 | 来源 |
|------|------|------|------|
| F-41a | action/key_action | key 默认值前后端不一致 | A-17 |
| F-41b | control/loop_count | count 默认值前后端不一致 | A-18 |
| F-41c | variable/var_math | a/b 默认值前后端不一致 | A-19 |

---

## 二、❌ 拒绝清单（2项）

| 编号 | 模块 | 问题 | 拒绝理由 |
|------|------|------|----------|
| R-01 | record 插件 | 录制功能使用 `start_replay_buffer` 而非 `start_record` | 设计如此：缓存+回放模式，OBS 插件支持，非 bug |
| R-02 | macro_binding_api.py | 鼠标绑定只支持侧键，不支持左/右/中键 | 无意义：键盘本身支持触发宏，鼠标其他按键自有用途 |

---

## 三、⏸️ 搁置清单（15项）

> 搁置原因：设计取舍 / 影响较小 / 需要更大范围重构

| 编号 | 严重度 | 模块 | 问题 | 搁置理由 |
|------|--------|------|------|----------|
| D-01 | 🔴 | core.js | 框选开始时调用 `_deselectAll` 意外触发 `onNodeDeselected` 回调，属性面板短暂闪烁 | 仅短暂闪烁，不影响功能 |
| D-02 | 🔴 | core.js | flow 连线源端口未限制一对一 | 当前执行为串行，行为可预期；限制会降低灵活性，需更大设计讨论 |
| D-03 | 🔴 | action/key_action | 后端定义中 key 缺少 keySelector 属性 | D-03 原标记"后期考虑"，影响有限 |
| D-04 | 🔴 | automation_api.py | `get_window_at_mouse` cursor_pt 动态添加 `_fields_` 用法不安全 | 仅影响少数 Python 版本，概率低 |
| D-05 | 🔴 | plugin_context.py | `show_desktop_popup` 使用 MessageBoxW 无法自动关闭 | 弹窗手动关闭即可，影响小 |
| D-06 | 🔴 | notify 插件 | Unicode 窗口使用 ANSI 字体结构体 | 仅影响非中文系统，影响小 |
| D-07 | 🟡 | action/mouse_move_rel | 缺少 easing 参数，与 mouse_move 不一致 | 设计取舍，R-01 原已拒绝 |
| D-08 | 🟡 | monitor/monitor_color | 缺少 check_mode=exact 选项 | 设计取舍，与 detection 不一致但不影响使用 |
| D-09 | 🟡 | utility/const_number/const_string | value 有 varRef 但"常量"节点不应引用变量 | 设计取舍，D-30/D-34 标记"后期考虑" |
| D-10 | 🟡 | editor-app.js | Ctrl+C 复制不包含 customName | D-36 标记"后期考虑"，影响有限 |
| D-11 | 🟡 | editor-app.js | `_getFlowOrderedNodes` 未区分 flow/data 连线 | D-42 标记"后期考虑"，模拟执行顺序问题 |
| D-12 | 🟡 | core.js | 连续删除连线时 `_refreshNodeDOM` 导致连接指示状态不准确 | 视觉小问题 |
| D-13 | 🟡 | core.js | 无 ghost 拖拽结束时多选节点 opacity 未恢复 | 视觉小问题 |
| D-14 | 🟡 | screenshot 插件 | fullscreen+window 模式行为与语义矛盾 | 设计取舍，需明确语义 |
| D-15 | 🟡 | bridge API | recorder_api / plugin_api 返回格式与 automation_api 不统一 | 不影响功能，代码规范问题 |

---

## 四、修复优先级建议

### 第一批：前端致命 + 核心逻辑（F-01 ~ F-03, F-21 ~ F-23, F-29）
> 修复量小（多数1-2行），影响大，应立即修复

### 第二批：varRef 统一修复（F-04 ~ F-20, F-26）
> 同类问题，可批量处理，模式统一：在 handler 入口处对 varRef 参数调用 `_resolve_value`

### 第三批：上期遗留修复（F-27, F-28, F-34 ~ F-41）
> 上期已采纳但未修复，这次必须完成

### 第四批：安全 + 体验（F-30 ~ F-33, F-38 ~ F-40）
> XSS 修复、并发安全、粘贴体验等

---

## 五、统计

| 类别 | 数量 |
|------|------|
| ✅ 修复 | 41 |
| ❌ 拒绝 | 2 |
| ⏸️ 搁置 | 15 |
| **合计** | **58** |

| 修复批次 | 项数 | 预估难度 |
|----------|------|----------|
| 第一批：前端致命+核心逻辑 | 8 | ⭐ 低 |
| 第二批：varRef统一修复 | 17 | ⭐⭐ 中（模式统一） |
| 第三批：上期遗留 | 10 | ⭐⭐ 中 |
| 第四批：安全+体验 | 6 | ⭐⭐ 中 |
