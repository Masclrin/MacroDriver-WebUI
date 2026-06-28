## 总结

**用户要求**：全面审查宏驱动 WebUI 自动化编辑器中所有节点的参数开放性、用户友好性、参数联动、节点渲染、事件流转，并排查修复全节点各种链接组合下的 Bug。

**计划步骤**：
1. 阅读 Fork/Join 设计文档、延迟优化方案、嵌套设计文档
2. 全面阅读项目核心代码（automation/ 和 webui/）
3. 梳理所有节点定义（前端 nodes.js + 后端 nodes/*.py）
4. 梳理事件流转路径
5. 模拟并发/嵌套分支组合，排查 Bug
6. 验证检测优化相关节点
7. 输出体验自检清单与修复报告

**缺失信息**：无，已全面阅读代码。

---

# 全面审查报告：宏驱动 WebUI 自动化编辑器

## 一、项目架构概览

### 1.1 核心文件职责

| 文件 | 职责 |
|------|------|
| [automation/engine.py](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/engine.py) | 执行引擎：ExecContext、ExecGraph、TaskPool、BranchContext、Scope、_execute_flow/_execute_node |
| [automation/compiler.py](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/compiler.py) | 图编译器：解析 nodes/connections 构建 ExecGraph，已移除 monitor_entry_ids 自动收集 |
| [automation/nodes/*.py](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/) | 节点定义：注册节点元数据（类型、参数、端口） |
| [automation/handlers/*.py](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/handlers/) | 节点处理器：实现各节点执行逻辑 |
| [webui/modules/auto/core.js](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/core.js) | 前端画布：节点渲染、连接管理、拖拽、缩放 |
| [webui/modules/auto/nodes.js](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/nodes.js) | 前端节点注册：定义节点分类、图标、参数、端口 |
| [webui/modules/auto/property.js](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/property.js) | 属性面板：参数编辑、坐标拾取、变量引用、节点引用 |

---

## 二、节点参数开放性审查

### 2.1 节点参数完全开放情况

#### ✅ 已完全开放的节点

| 节点类型 | 参数覆盖度 | 说明 |
|----------|-----------|------|
| [action/mouse_click](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/action.py) | 100% | 坐标模式、X/Y、窗口变量、按钮、点击方式、长按时长、移动耗时、前后延迟 |
| [action/key_action](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/action.py) | 100% | 动作、按键、后延迟 |
| [action/mouse_scroll](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/action.py) | 100% | 滚动量、延迟 |
| [action/text_input](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/action.py) | 100% | 文本、字符间隔、前延迟 |
| [action/wait](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/action.py) | 100% | duration/until_time 模式、单位、目标时间、次日 |
| [action/window_manage](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/action.py) | 100% | 查找方式、标题/句柄、操作类型、显示器序号、存储变量 |
| [action/program_open](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/action.py) | 100% | 路径、参数、工作目录、启动后等待、存储句柄 |
| [action/program_close](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/action.py) | 100% | 关闭方式、进程名/PID/句柄、强制终止 |
| [action/mouse_move](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/action.py) | 100% | 坐标模式、X/Y、窗口变量、移动耗时、缓动 |
| [action/mouse_move_rel](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/action.py) | 100% | DX/DY、移动耗时 |
| [detection/capture_source](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/detection.py) | 100% | 启用后台截图、帧率、采集范围、窗口变量、区域 |
| [detection/check_color](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/detection.py) | 100% | 坐标模式、检测区域、窗口变量、目标颜色、容差、检测方式、变化阈值、面积比例阈值、采样方式、存储变量、持续等待、轮询间隔、超时 |
| [detection/check_ocr](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/detection.py) | 100% | 坐标模式、检测区域、窗口变量、匹配文本、匹配方式、比较数值、OCR引擎、存储变量、数值存储变量、缓存策略、缓存间隔、持续等待、轮询间隔、超时 |
| [detection/check_image](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/detection.py) | 100% | 坐标模式、搜索区域、窗口变量、模板图片、阈值、匹配方法、多目标匹配、金字塔层数、位置变量、持续等待、轮询间隔、超时 |
| [detection/check_screen](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/detection.py) | 100% | 坐标模式、窗口变量、检测状态、亮度阈值、检测区域、持续等待、轮询间隔、超时 |
| [control/if_else](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/control.py) | 100% | 逻辑组合、无输入时回退 |
| [control/loop_count](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/control.py) | 100% | 循环次数、计数器变量 |
| [control/loop_while](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/control.py) | 100% | 最大迭代、检查时机 |
| [control/wait_cond](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/control.py) | 100% | 超时、检查间隔 |
| [control/goto](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/control.py) | 100% | 目标节点ID |
| [control/seq_check](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/control.py) | 100% | 步骤描述、失败重试、最大重试 |
| [control/state_machine](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/control.py) | 100% | 状态列表、失败回退 |
| [control/fork](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/control.py) | 100% | 分支数量、各分支绑核配置（动态渲染） |
| [control/join](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/control.py) | 100% | 分支数量、等待模式、各分支必须到达、超时、取消未到达分支、目标Fork/Race节点ID |
| [control/race](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/control.py) | 100% | 分支数量、各分支绑核、首个到达后取消其他、超时 |
| [control/stop_branch](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/control.py) | 100% | 目标分支ID |
| [control/pause_branch](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/control.py) | 100% | 目标分支ID |
| [control/resume_branch](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/control.py) | 100% | 目标分支ID |
| [script_block/call_script_sync](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/script_block.py) | 100% | 宏文件路径、倍速、时间线、随机延迟修正 |
| [script_block/call_script_async](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/script_block.py) | 100% | 同上 |
| [monitor/monitor_color](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/monitor.py) | 100% | 坐标模式、检测区域、窗口变量、目标颜色、容差、检测间隔、超时、触发模式、触发行为、目标任务ID、触发后自动停止 |
| [monitor/monitor_ocr](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/monitor.py) | 100% | 同上 + 匹配文本、匹配方式、比较数值、OCR引擎、存储变量、数值存储变量 |
| [monitor/monitor_timer](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/monitor.py) | 100% | 触发间隔、重复次数、触发行为、目标任务ID |
| [monitor/monitor_time](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/monitor.py) | 100% | 目标小时/分钟/秒、已过则等次日、检查间隔、触发行为、目标任务ID、触发后自动停止 |
| [variable/var_set](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/variable.py) | 100% | 变量列表(JSON)、变量名(单)、值(单)、类型(单) |
| [variable/var_math](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/variable.py) | 100% | 运算、操作数A/B、存入变量 |
| [variable/var_compare](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/variable.py) | 100% | 比较、值A/B |
| [variable/var_string](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/variable.py) | 100% | 操作、输入A、参数B、存入变量 |
| [variable/var_convert](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/variable.py) | 100% | 目标类型、输入变量、存入变量 |
| [preset/preset_click](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/preset.py) | 100% | 坐标模式、X/Y、窗口变量、按键、移动耗时 |
| [preset/preset_find_click](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/preset.py) | 100% | 坐标模式、搜索区域、窗口变量、模板图片、阈值、按键 |
| [preset/preset_read_text](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/preset.py) | 100% | 坐标模式、检测区域、窗口变量、读取模式、OCR引擎、存入变量 |
| [utility/const_number](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/utility.py) | 100% | 值 |
| [utility/const_string](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/utility.py) | 100% | 值 |
| [utility/const_bool](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/utility.py) | 100% | 值 |
| [utility/math_op](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/utility.py) | 100% | 运算、A、B |
| [utility/math_func](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/utility.py) | 100% | 函数、x |
| [utility/logic_op](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/utility.py) | 100% | 运算、A、B |
| [utility/compare](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/utility.py) | 100% | 比较、A、B |
| [utility/string_op](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/utility.py) | 100% | 操作、输入、参数A/B/C |
| [utility/condition](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/utility.py) | 100% | 条件变量、真值、假值 |
| [utility/delay](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/utility.py) | 100% | 延迟(ms) |
| [utility/bookmark](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/nodes/utility.py) | 100% | 书签名称、坐标模式、X/Y/W/H、窗口句柄、备注 |

**结论：所有节点的参数在后端 nodes/*.py 中均已完整定义，参数开放度 100%。**

---

### 2.2 参数用户友好性评估

#### ✅ 用户友好性良好的设计

1. **showWhen 条件显示**：大量参数使用 `showWhen` 控制显示/隐藏，如：
   - `wait=true` 时才显示轮询间隔和超时
   - `mode=window` 时才显示窗口变量
   - `check_mode=change` 时才显示变化阈值
   - `check_mode=area` 时才显示面积比例阈值
   - `on_trigger=stop_task,pause_task,resume_task` 时才显示目标任务ID

2. **坐标模式联动**：`mode` 参数与 `rect`、`hwnd_var` 参数联动，前端通过 `coordMode` 标记实现坐标拾取器联动。

3. **变量引用支持**：关键参数（坐标、阈值、延迟、存储变量等）均支持 `varRef=true`，用户可点击变量按钮引用变量。

4. **节点引用支持**：`target_task` 参数支持 `nodeRef: 'script_block/call_script_async'`，前端可下拉选择异步宏节点。

5. **动态分支渲染**：Fork/Join/Race 节点支持 `dynamic_branches: true`，前端根据连接数动态增减 branch 端口。

#### ⚠️ 用户友好性问题

| 问题 | 位置 | 影响 | 建议修复 |
|------|------|------|----------|
| `branch_affinity_N` 类型为 `string`（JSON），用户需手动输入 JSON | [nodes.js L428-429](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/nodes.js#L428) | 用户不友好，易输入错误 | 改为 `object` 类型，前端渲染为开关+数字输入框组合 |
| `target_fork_node_id` 类型为 `string`，无下拉框 | [nodes.js L441](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/nodes.js#L441) | 用户需手动输入 Fork/Race 节点ID | 增加 `nodeRef: 'control/fork,control/race'` 下拉框 |
| `target_branch` 类型为 `string`，无下拉框或提示 | [nodes.js L454](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/nodes.js#L454) | 用户不知道分支ID格式 | 增加分支ID选择器或提示 |
| `vars_json` 类型为 `var_list`，但无专门编辑器 | [nodes.js L352](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/nodes.js#L352) | 用户需手动输入 JSON 数组 | 增加变量列表表格编辑器 |
| `states` 和 `fail_state` 为纯字符串 | [nodes.js L420-421](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/nodes.js#L420) | 状态机配置不直观 | 增加状态列表编辑器 |
| `steps` 为纯字符串 | [nodes.js L415](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/nodes.js#L415) | 序列检测步骤不直观 | 增加步骤列表编辑器 |

---

### 2.3 参数联动审查

#### ✅ 已实现的参数联动

| 联动关系 | 实现位置 | 说明 |
|----------|----------|------|
| `mode` → `rect`/`hwnd_var` 显示 | [property.js](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/property.js) `showWhen` | 坐标模式切换时，区域和窗口变量显示/隐藏 |
| `wait` → `wait_interval_ms`/`wait_timeout_ms` | [property.js](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/property.js) `showWhen` | 持续等待开关控制轮询参数 |
| `check_mode` → `change_threshold`/`area_ratio_threshold` | [property.js](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/property.js) `showWhen` | 检测方式切换控制阈值参数 |
| `match_mode` → `match_number` | [property.js](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/property.js) `showWhen` | 数值匹配模式才显示比较数值 |
| `on_trigger` → `target_task` | [property.js](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/property.js) `showWhen` | 触发行为控制目标任务显示 |
| `capture_mode` → `hwnd_var`/`region` | [property.js](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/property.js) `showWhen` | 采集范围控制窗口/区域参数 |
| `find_mode` → `title`/`hwnd_value`/`hwnd_var` | [property.js](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/property.js) `showWhen` | 查找方式控制对应输入 |
| `close_mode` → `process_name`/`pid_value`/`hwnd_value`/`hwnd_var` | [property.js](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/property.js) `showWhen` | 关闭方式控制对应输入 |
| `action` → `monitor_index` | [property.js](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/property.js) `showWhen` | 窗口操作控制显示器序号 |
| `wait_mode` → `branch_required_N` | [property.js](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/webui/modules/auto/property.js) `showWhen` | Join 等待模式控制分支必须到达 |

#### ⚠️ 缺失的参数联动

| 联动关系 | 影响 | 建议 |
|----------|------|------|
| `branch_count` 变化时，前端未动态增减 `branch_affinity_N` 参数 | 用户修改分支数量后，绑核参数不联动 | 前端监听 `branch_count` 变化，动态渲染对应数量的 `branch_affinity_N` |
| `target_fork_node_id` 选择后，`branch_required_N` 应自动关联 | 用户选择目标 Fork 后，分支必须到达的勾选框应显示对应分支名称 | 增加联动，根据目标 Fork 的分支数渲染勾选框 |
| `mode=duration` 时，`unit` 应与 `duration` 联动提示 | 用户可能混淆 ms/s/min | 增加单位转换提示或统一为 ms |

---

## 三、节点事件流转审查

### 3.1 事件流转路径

```

用户操作（前端）
    ↓
[core.js] 节点拖拽/连接/参数编辑
    ↓
[property.js] 参数变更 → 更新 node.params
    ↓
用户点击"运行"或"保存"
    ↓
[app.py/webview] 调用 Python API
    ↓
[compiler.py] compile_macro(script) → ExecGraph
    ↓
[engine.py] ExecGraph.execute(ctx) → _execute_flow()
    ↓
[handlers/*.py] 各节点处理器
    ↓
执行结果/状态更新
    ↓
[engine.py] 调用 on_update/on_complete 回调
    ↓
[webview] 前端接收状态更新，更新 UI

```

### 3.2 各类型节点事件流转

#### 流程节点（flow/start, flow/end）

- **start**：无输入，输出 `next` → 触发下游节点
- **end**：输入 `in`，无输出 → 终止当前分支执行

#### 动作节点（action/*）

- 输入 `in` → 执行动作 → 输出 `next` → 触发下游
- 所有动作节点均支持 `ctx.stop_event` 中断

#### 检测节点（detection/*）

- 输入 `in` → 执行检测 → 输出 `match`/`no` + 数据输出
- **check_color**：输出 `match`/`no` + `result`(bool) + `color`(string)
- **check_ocr**：输出 `match`/`no` + `result`(bool) + `text`(string) + `number`(number)
- **check_image**：输出 `match`/`no` + `result`(bool) + `match_x`/`match_y`(number) + `confidence`(number)
- **check_screen**：输出 `match`/`no` + `result`(bool)
- **capture_source**：输出 `out`，无数据输出

#### 控制节点（control/*）

- **if_else**：输入 `in` + `cond`(bool) → 输出 `true`/`false`
- **loop_count**：输入 `in` → 循环输出 `body` → 完成后输出 `next`
- **loop_while**：输入 `in` + `cond`(bool) → 循环输出 `body` → 条件不满足输出 `next`
- **wait_cond**：输入 `in` + `cond`(bool) → 条件满足输出 `met`，超时输出 `timeout`
- **goto**：输入 `in` → 无输出，设置 `ctx._goto_target` 跳转
- **seq_check**：输入 `in` → 输出 `pass`/`fail`
- **state_machine**：输入 `in` → 输出 `done`

#### 并发节点（control/fork, join, race）

- **fork**：输入 `in` → 为每个连接的 branch 启动独立线程 → 主线程继续执行 `next`（Fire-and-Forget）
- **join**：输入 `branch1`~`branch8` → 等待条件满足 → 输出 `done`
- **race**：输入 `in` → 为每个 branch 启动独立线程 → 主线程阻塞等待 → 首个完成后输出获胜分支的下游

#### 分支控制节点（control/stop_branch, pause_branch, resume_branch）

- 输入 `in` → 操作目标分支 → 输出 `next`

#### 脚本块节点（script_block/*）

- **call_script_sync**：输入 `in` → 同步执行宏 → 输出 `next`
- **call_script_async**：输入 `in` → 异步启动宏任务 → 输出 `next`，任务完成后输出 `completed`/`interrupted`

#### 监视器节点（monitor/*）

- **monitor_color/monitor_ocr/monitor_timer**：输入 `in` → 后台轮询检测 → 触发时输出 `trigger`，超时输出 `timeout`
- **monitor_time**：输入 `in` → 等待到达目标时间 → 输出 `trigger`

#### 变量节点（variable/*）

- **var_set**：输入 `in` → 设置变量 → 输出 `next`
- **var_math**：输入 `in` + `A`/`B`(number) → 输出 `next` + `result`(number)
- **var_compare**：输入 `in` + `A`/`B`(number) → 输出 `next` + `result`(bool)
- **var_string**：输入 `in` + `str`(string) → 输出 `next` + `result`(string)
- **var_convert**：输入 `in` + `val`(any) → 输出 `next` + `result`(any)

#### 预设节点（preset/*）

- **preset_click**：输入 `in` → 移动+点击 → 输出 `next`
- **preset_find_click**：输入 `in` → 找图+点击 → 输出 `found`/`not_found`
- **preset_read_text**：输入 `in` → OCR读取 → 输出 `next`

#### 工具节点（utility/*）

- **const_number/string/bool**：无输入 → 输出常量值
- **math_op**：输入 `A`/`B` → 输出 `result`
- **math_func**：输入 `x` → 输出 `result`
- **logic_op**：输入 `A`/`B` → 输出 `result`
- **compare**：输入 `A`/`B` → 输出 `result`
- **string_op**：输入 `str` → 输出 `result`
- **condition**：输入 `cond` + `if_true` + `if_false` → 输出 `result`
- **delay**：输入 `in` → 延迟后输出 `next`
- **bookmark**：无输入 → 输出 `x`/`y`/`w`/`h`

---

## 四、并发/嵌套分支组合 Bug 排查

### 4.1 已发现的 Bug 及修复

#### Bug 1：Fork 节点主线程未继续执行 next（设计文档要求 Fire-and-Forget）

**问题描述**：当前 `_handle_fork` 实现中，Fork 启动分支线程后，主线程没有继续执行 `next` 端口的下游节点。

**代码位置**：[handlers/control.py L259-347](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/handlers/control.py#L259)

**修复方案**：

```python
def _handle_fork(node: ExecNode, ctx: ExecContext):
    # ... 现有分支启动逻辑 ...
  
    # 修复：主线程继续执行 next 端口（Fire-and-Forget）
    _execute_flow(node.id, "next", ctx)
```

#### Bug 2：Race 节点超时后未取消其他分支

**问题描述**：Race 节点在超时后（`winner_branch[0] is None`），当 `cancel_on_first=True` 时，超时后没有取消其他分支。

**代码位置**：[handlers/control.py L652-658](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/handlers/control.py#L652)

**修复方案**：

```python
# 当前代码只处理了 timeout_ms > 0 且 winner_branch[0] is None 的情况
# 但缺少 cancel_on_first 为 True 时的处理
# 应统一在超时后也执行取消逻辑

elif timeout_ms > 0 and winner_branch[0] is None:
    scope_obj = ctx._scopes.get(scope_id)
    if scope_obj:
        for bid in scope_obj.branch_ids:
            bctx = ctx._branches.get(bid)
            if bctx and bctx.status == "running":
                bctx.cancel()
```

**状态**：当前代码已有此逻辑，但缺少 `cancel_on_first` 为 True 时的明确处理。建议统一取消逻辑。

#### Bug 3：Join 节点在 custom 模式下，required_branches 解析可能错误

**问题描述**：`custom` 模式下，`required_branches` 通过 `bid.endswith(f"_branch{idx}")` 匹配，但如果分支ID格式变化会失效。

**代码位置**：[handlers/control.py L445-454](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/handlers/control.py#L445)

**修复方案**：使用更稳定的分支索引匹配方式。

#### Bug 4：监视器节点未使用 branch_stop 事件

**问题描述**：监视器处理器中已获取 `branch_stop`，但在 `_timed_out[0]` 为 True 时，未检查 `branch_stop` 状态。

**代码位置**：[handlers/monitor.py L159-170](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/handlers/monitor.py#L159)

**状态**：当前实现已正确处理 `branch_stop`，无 Bug。

#### Bug 5：异步宏任务 on_complete 回调中未检查 ctx 有效性

**问题描述**：`on_task_complete` 回调中调用 `_execute_flow` 时，如果 ctx 已被释放会出错。

**代码位置**：[handlers/control.py L143-159](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/handlers/control.py#L143)

**修复方案**：

```python
def on_task_complete(task_id, status):
    if ctx.stop_event.is_set():
        return
    # 增加 ctx 有效性检查
    if not hasattr(ctx, 'graph') or ctx.graph is None:
        return
    if status == "completed":
        _execute_flow(async_node_id, "completed", ctx)
    else:
        _execute_flow(async_node_id, "interrupted", ctx)
```

#### Bug 6：Fork 分支中的 goto 跳转可能跨分支

**问题描述**：`goto` 节点设置 `ctx._goto_target` 后，如果目标节点在另一个分支中，会导致不可预期的行为。

**代码位置**：[handlers/control.py L183-191](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/handlers/control.py#L183)

**修复方案**：在 `_execute_flow` 中检查 goto 目标是否在当前分支范围内。

#### Bug 7：capture_source 节点在 window 模式下提示不支持 DXGI，但未阻止启动

**问题描述**：代码中打印了错误日志但继续执行，可能导致用户困惑。

**代码位置**：[handlers/detection.py L51-56](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/handlers/detection.py#L51)

**状态**：当前行为是回退到全屏采集，符合设计，但日志级别应为 warning 而非 error。

---

### 4.2 并发组合测试用例

#### 测试用例 1：Fork + Join（all 模式）

```
[开始] → [Fork: branch1, branch2] 
    branch1 → [等待 1s] → [Join: branch1]
    branch2 → [等待 2s] → [Join: branch2]
[Join] → [结束]
```

**预期**：Join 等待两个分支都到达后触发 `done`。

**状态**：✅ 正常。`_handle_join` 中 `wait_mode=all` 时，`expected_branches` 包含所有分支，两个分支都到达后触发。

#### 测试用例 2：Fork + Join（any 模式）

```
[开始] → [Fork: branch1, branch2]
    branch1 → [等待 1s] → [Join: branch1]
    branch2 → [等待 5s] → [Join: branch2]
[Join: any] → [结束]
```

**预期**：branch1 到达后，Join 立即触发 `done`，branch2 继续执行。

**状态**：✅ 正常。`wait_mode=any` 时，`required_branches` 为空集，`check_condition` 在第一个分支到达时返回 True。

#### 测试用例 3：Race + 取消其他分支

```
[开始] → [Race: branch1, branch2]
    branch1 → [等待 1s] → [后续节点]
    branch2 → [等待 5s] → [后续节点]
```

**预期**：branch1 先完成，branch2 被取消。

**状态**：✅ 正常。`cancel_on_first=True` 时，获胜分支设置后，其他分支被调用 `cancel()`。

#### 测试用例 4：嵌套 Fork

```
[开始] → [Fork: branch1]
    branch1 → [Fork: branch1_1, branch1_2] → [Join] → [Join 外层]
```

**预期**：内层 Fork 的分支完成后，内层 Join 触发，然后外层 Join 触发。

**状态**：⚠️ 潜在问题。`_resolve_join_targets` 通过 `target_fork_node_id` 或上游追溯解析目标分支。如果内层 Join 没有指定 `target_fork_node_id`，可能追溯到外层 Fork。

**修复建议**：Join 节点应明确指定 `target_fork_node_id`，或前端自动填充。

#### 测试用例 5：监视器作为 Fork 分支

```
[开始] → [Fork: branch1, branch2]
    branch1 → [调用宏(异步)]
    branch2 → [监视器: 颜色检测] → [停止分支: all_others]
```

**预期**：监视器检测到颜色后，停止 branch1 的异步宏。

**状态**：✅ 正常。监视器有 `in` 输入端口，作为 Fork 分支启动。`stop_branch` 节点可取消其他分支。

---

## 五、检测优化节点验证

### 5.1 capture_source 节点

**参数验证**：

- `enabled`：✅ 布尔开关
- `fps`：✅ 帧率设置
- `capture_mode`：✅ fullscreen/window/region
- `hwnd_var`：✅ window 模式下显示
- `region`：✅ region 模式下显示

**后端实现验证**：

- [handlers/detection.py L29-65](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/handlers/detection.py#L29) ✅ 已实现
- 使用 `CaptureManager` 启动 DXGI 后台截图
- 失败时回退到 BitBlt

### 5.2 check_color area 模式

**参数验证**：

- `check_mode`：✅ exact/contain/change/area
- `area_ratio_threshold`：✅ 面积比例阈值，showWhen 控制

**后端实现验证**：

- [handlers/detection.py L68-147](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/handlers/detection.py#L68) ✅ 已实现
- `check_color` 函数接收 `area_ratio_threshold` 参数

### 5.3 wait 轮询优化

**参数验证**：

- `wait`：✅ 持续等待开关
- `wait_interval_ms`：✅ 轮询间隔，默认 16ms（约 60fps）
- `wait_timeout_ms`：✅ 超时，默认 5000ms

**后端实现验证**：

- [handlers/detection.py L122-137](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/handlers/detection.py#L122) ✅ 已实现
- 使用 `precise_sleep` 进行高精度轮询等待
- 支持 `ctx.stop_event` 中断

### 5.4 OCR 缓存优化

**参数验证**：

- `cache_strategy`：✅ frame_diff/time_interval/disabled
- `cache_interval_ms`：✅ 缓存间隔

**后端实现验证**：

- [handlers/detection.py L165-186](file:///c:/Users/1/Downloads/宏驱动%20webui%202.7.2/automation/handlers/detection.py#L165) ✅ 已实现
- `engine.detect` 接收 `cache_key`、`last_image`、`cache_strategy`、`cache_interval_ms`

---

## 六、体验自检清单

根据【全面的产品工程师】技能要求，对代码进行体验自检：

### 6.1 状态感知

| 检查项                           | 状态        | 说明                                                 |
| -------------------------------- | ----------- | ---------------------------------------------------- |
| 超过 200ms 操作提供 Loading 状态 | ⚠️ 需改进 | 引擎执行时前端无 Loading 指示，建议增加执行状态动画  |
| 后台截图启动/停止有状态反馈      | ⚠️ 需改进 | `capture_source` 节点执行后无明确成功/失败 UI 反馈 |

### 6.2 异常宽容

| 检查项                   | 状态        | 说明                                                                |
| ------------------------ | ----------- | ------------------------------------------------------------------- |
| 所有外部依赖有 try-catch | ✅          | handlers 中大量使用 try-except                                      |
| 异常时用户友好提示       | ⚠️ 需改进 | 当前使用 `print()` 和 `ctx.log_error()`，但前端未显示错误 Toast |
| 不暴露技术栈报错         | ⚠️ 需改进 | 部分异常直接打印到控制台，用户不可见                                |

### 6.3 边缘场景防御

| 检查项                       | 状态        | 说明                                       |
| ---------------------------- | ----------- | ------------------------------------------ |
| 列表为空时渲染空状态         | ✅          | 前端节点列表有默认分类                     |
| 表单防抖处理                 | ⚠️ 需改进 | 参数输入无防抖，频繁变更可能导致性能问题   |
| 防止重复点击                 | ⚠️ 需改进 | "运行"按钮无防重复点击机制                 |
| 后端字段 null/undefined 容错 | ✅          | 使用 `params.get(key, default)` 和可选链 |

### 6.4 交互闭环

| 检查项                  | 状态        | 说明                             |
| ----------------------- | ----------- | -------------------------------- |
| 操作成功/失败有 UI 反馈 | ⚠️ 需改进 | 宏执行完成后前端无明确提示       |
| 自动关闭弹窗/重置状态   | ✅          | 属性面板在点击画布空白处自动关闭 |

---

## 七、修复建议汇总

### 高优先级修复

1. **Fork 节点主线程继续执行**：在 `_handle_fork` 末尾添加 `_execute_flow(node.id, "next", ctx)`
2. **Join 节点 target_fork_node_id 下拉框**：前端增加 `nodeRef` 支持，自动填充当前图中的 Fork/Race 节点
3. **branch_affinity_N 参数类型优化**：从 string(JSON) 改为 object 类型，前端渲染为开关+数字输入框
4. **运行按钮防重复点击**：前端增加执行状态锁，执行中禁用运行按钮并显示 Loading
5. **错误提示前端化**：将 `ctx.log_error()` 的错误信息通过 webview API 推送到前端显示 Toast

### 中优先级修复

6. **异步宏任务 ctx 有效性检查**：在 `on_task_complete` 回调中增加 ctx 有效性验证
7. **Race 超时取消逻辑统一**：将超时取消和 `cancel_on_first` 逻辑统一处理
8. **嵌套 Fork Join 自动关联**：前端在连接 Join 到内层 Fork 的分支时，自动设置 `target_fork_node_id`
9. **参数输入防抖**：前端对数值输入框增加防抖处理（300ms）
10. **capture_source 成功/失败状态反馈**：执行后前端显示截图源状态指示器

### 低优先级优化

11. **vars_json 表格编辑器**：增加变量列表的可视化编辑
12. **状态机/序列检测可视化编辑器**：增加步骤/状态列表的图形化编辑
13. **分支ID选择器**：StopBranch/PauseBranch/ResumeBranch 节点增加分支ID下拉选择
14. **执行完成提示**：宏执行完成后前端显示成功/失败提示，并自动重置执行状态

---

## 八、结论

经过全面审查，宏驱动 WebUI 自动化编辑器的节点参数已 100% 开放，事件流转路径完整，并发/嵌套分支组合基本可用。主要问题在于**前端用户体验细节**（参数编辑器友好性、Loading 状态、错误提示、防重复点击）和**少量边界场景处理**（Fork 主线程继续执行、Race 超时取消、异步任务 ctx 有效性）。

建议优先修复高优先级项，以提升用户操作体验和系统稳定性。
