# 自动化编辑器 3期 Bug 汇总文档

> **编制日期**: 2026-05-01
> **编制依据**: 3期atomation节点审查.MD + 2期Bug汇总文档.md + 用户讨论决策
> **配套文档**: Bug修复意见书3期.md（待创建，但已无意义）
> **编号规则**: B-*=采纳, P-*=后期考虑, X-\*=拒绝；延续2期编号，B-64起为3期新增

***

## 审查结论概览

| 分类        | 数量 | 说明                         |
| --------- | -- | -------------------------- |
| ✅ 采纳（需修复） | 28 | 含致命级5项 + 高优先级12项 + 中优先级11项 |
| 🆕 新功能需求  | 4  | 变量浏览器优化                    |
| ⏳ 后期考虑    | 18 | 体验优化/非核心功能                 |
| ❌ 拒绝      | 8  | 3期新拒绝项                     |

***

## 一、✅ 采纳项

### 1.1 🔴🔴🔴 致命级（必须优先修复）

#### B-64 | `_checkShowWhen` 不支持 `>=` 运算符 — fork/join/race 分支3-8配置完全失效

- **严重级别**: 致命
- **影响模块**: 前端核心（所有带 showWhen 条件的节点）
- **文件**: `webui/modules/auto/core.js:130-169` + `webui/modules/auto/property.js:392-432`
- **问题**: `_checkShowWhen` 解析 `branch_count>=3` 时，`indexOf('=')` 找到 `>` 后面的 `=`，导致字段名被解析为 `branch_count>` 而非 `branch_count`，条件永远为 false
- **影响**: fork/join/race 节点增加分支数量到3以上时，属性面板中分支3-8的名称、绑核、必须到达等配置字段**全部不可见**
- **修复方案**: 修改 `_checkShowWhen` 支持 `>=` 运算符，先检测 `>=` 再检测 `=`
- **关联**: 此bug是 B-57（fork branch\_affinity 缺 showWhen）的前置阻塞项

#### B-65 | `_resolve_value` 不处理数组内元素变量引用 — 9个 rect/region 参数 varRef 完全失效

- **严重级别**: 致命
- **影响模块**: 引擎核心（所有检测/监视/预设节点）
- **文件**: `automation/engine.py:347-349`
- **问题**: `_resolve_value` 对非字符串类型直接返回，当参数值为 `["${x}", "${y}", "${w}", "${h}"]` 时，数组内变量引用不会被解析
- **受影响参数**（共9个）:
  - `detection/capture_source.region`
  - `detection/check_color.rect`
  - `detection/check_ocr.rect`
  - `detection/check_image.rect`
  - `detection/check_screen.region`
  - `preset/preset_find_click.rect`
  - `preset/preset_read_text.rect`
  - `monitor/monitor_color.rect`
  - `monitor/monitor_ocr.rect`
- **修复方案**: 在 `_resolve_value` 开头添加对 `list` 类型的递归处理

```python
if isinstance(value, list):
    return [_resolve_value(item, ctx) for item in value]
```

#### B-66 | 普通节点异常后执行链断裂 — 需增加重试机制与异常分类

- **严重级别**: 致命
- **影响模块**: 引擎核心（所有普通节点）
- **文件**: `automation/engine.py:712-738`
- **问题**: `_execute_node` 中 handler 抛异常后只记录日志，不调用 `_execute_flow()`，后续节点全部不执行
- **用户决策**:
  1. 增加**重试机制**：在"全局参数配置页面"添加 `节点执行重试次数`（默认3次），`节点重试等待时间`（默认500ms）
  2. 区分**业务异常**与**系统异常**：
     - 业务异常（截图没找到目标、点击坐标无效等）：等待后重试，超时/超次数后走 fail/next
     - 系统异常（内存溢出、核心依赖库崩溃、ctx损坏）：立即终止
  3. 采用方案B：定义 `BusinessException` 异常类，handler 内部对业务异常封装
- **修复方案**:
  1. 在 `engine.py` 定义 `BusinessException` 类
  2. 在 `_execute_node` 的 except 块中区分处理
  3. 添加重试逻辑
  4. 业务异常超限后调用 `_execute_flow(node.id, "fail" if _has_output_port(node, "fail") else "next", ctx)`

#### B-67 | `control/join` 前端缺少 `branch_required_3`\~`branch_required_8`

- **严重级别**: 严重
- **影响模块**: 控制节点
- **文件**: `webui/modules/auto/nodes.js:558-559`
- **问题**: 后端定义了 `branch_required_1`\~`branch_required_8`，前端仅有 1 和 2
- **影响**: 当 `branch_count >= 3` 且 `wait_mode=custom` 时，无法配置分支3-8是否必须到达
- **修复方案**: 在前端添加 `branch_required_3`\~`branch_required_8`，带 `showWhen:'branch_count>=3'` 等条件

#### B-68 | 颜色解析逻辑不一致 — monitor 直接用字符串索引会崩溃

- **严重级别**: 严重
- **影响模块**: 检测节点 + 监视器节点
- **文件**:
  - `automation/handlers/detection.py:18-27` — 使用正则 `_parse_target_color()` 安全解析
  - `automation/handlers/monitor.py:28-31` — 直接用 `target_hex[1:3]` 字符串索引
- **问题**: monitor 的颜色解析对变量引用格式（如 `"${var}"`）或短格式（如 `"#fff"`）会直接崩溃
- **修复方案**: 统一使用 `_parse_target_color()` 函数

***

### 1.2 🔴 高优先级

#### B-69 | `key_action` "press" 语义与 `mouse_click` 不一致

- **影响模块**: 动作节点
- **文件**: `automation/handlers/action.py:137-139` vs `automation/handlers/action.py:78`
- **问题**:
  - `mouse_click` 的 "press" = key\_down（按下不放）
  - `key_action` 的 "press" = key\_down + key\_up（完整点击）
- **影响**: 用户认知混乱，"按住Shift再点击"操作结果与预期相反
- **修复方案**: 将 `key_action` 的选项改为 `["click", "press", "release", "type"]`
  - click = 按下+释放（原有press的行为）
  - press = 仅按下（与mouse\_click一致）
  - release = 仅释放
  - type = 模拟打字输入
- **注意**: 修复人员需再次确认 key 的 press 确实是单击行为

#### B-70 | `program_open` 句柄获取失败需加日志提示

- **影响模块**: 动作节点
- **文件**: `automation/handlers/action.py:412-446`
- **问题**: 当前重试10次×0.2秒=共2秒，某些程序启动慢会导致 `store_hwnd_var` 为空，用户不知道失败原因
- **修复方案**: 当句柄获取失败时，通过日志明确告知用户"未找到窗口句柄"
- **注意**: 不会重复启动程序，重试是查找窗口句柄而非重复启动

#### B-71 | `sample_mode` 选项不一致 + 英文参数名改中文

- **影响模块**: 检测节点 + 监视器节点
- **文件**:
  - `automation/nodes/detection.py:37` — `["center", "mean", "max_diff"]`
  - `automation/nodes/monitor.py:19` — `["center", "average", "corner"]`
- **问题**: 名称和行为都不一致，用户在检测节点学会"mean"，到监视器找不到
- **修复方案**:
  1. 统一为 `["center", "mean", "max_diff"]`
  2. 英文参数名在前端改成中文
  3. 悬停显示英文名与参数说明
- **注意**: 需设计兼容方案，旧脚本中的 "average" 映射到 "mean"

#### B-72 | `monitor_time` 缺少循环触发参数

- **影响模块**: 监视器节点
- **文件**: `automation/nodes/monitor.py:89-112` + `automation/handlers/monitor.py:168-276`
- **问题**: `monitor_time` 只有 `auto_stop` 参数，缺少 `recheck_delay_ms`、`max_triggers`、`auto_close_after_ms`
- **影响**: 时间监视器触发后只能自动停止，无法配置循环触发行为
- **修复方案**:
  1. 在节点定义中添加三个参数，带 `showWhen: "auto_stop=false"`
  2. 在 handler 中实现循环触发逻辑（参考 `_handle_monitor_node`）

#### B-73 | `var_math` round 操作隐藏 B 端口

- **影响模块**: 变量节点
- **文件**: `automation/nodes/variable.py:16`
- **问题**: `b` 参数的 `showWhen` 不包含 `op=round`，但 round 需要 `b` 指定小数位数
- **影响**: 用户选 round 后想保留2位小数，但字段被隐藏
- **修复方案**: 在 `b` 的 `showWhen` 中添加 `op=round`
- **关联**: B-03 的漏网之鱼

#### B-74 | `preset_read_text` 异常不续流

- **影响模块**: 预设节点
- **文件**: `automation/handlers/preset.py:127-130`
- **问题**: 异常处理中只设置 check\_results 和 log\_error，不调用 `_execute_flow()`
- **修复方案**: 随 B-66 一起处理，引擎层统一增加续流机制

#### B-75 | 预设节点 `button` 选项缺 middle

- **影响模块**: 预设节点
- **文件**: `automation/nodes/preset.py:16`
- **问题**: `preset_click/preset_find_click` 的 button 只有 left/right，action/mouse\_click 有 left/right/middle
- **修复方案**: 添加 `"middle"` 选项

#### B-76 | rect `[0,0,0,0]` 判断不健壮

- **影响模块**: 检测/预设节点
- **文件**: `automation/handlers/detection.py:305` + `automation/handlers/preset.py:49`
- **问题**: `if rect == [0,0,0,0]` 精确列表比较，元组或浮点数会失效
- **修复方案**: 使用健壮判断 `all(v == 0 for v in rect)`

#### B-77 | `logic_op` bool 转换对字符串不安全

- **影响模块**: 工具节点
- **文件**: `automation/handlers/utility.py:87`
- **问题**: `bool("false")` 返回 True，字符串 "false" 是游戏自动化高频默认值
- **修复方案**: 使用安全布尔转换，与 `var_set` 保持一致

```python
str(val).lower() not in ("", "0", "false", "no", "off", "none", "null")
```

#### B-78 | `check_image` confidence 输出未声明

- **影响模块**: 检测节点
- **文件**: `automation/nodes/detection.py:check_image outputs`
- **问题**: 处理器输出 confidence 值，但节点定义未声明
- **修复方案**: 在 outputs 中添加 `{"name": "confidence", "type": "number"}`

#### B-79 | `join` target\_fork\_node\_id nodeRef 不完善

- **影响模块**: 控制节点
- **文件**: `webui/modules/auto/property.js` nodeRef 字段渲染
- **问题**: 应能从下拉列表选择 fork 节点，但配置不完善
- **修复方案**: 完善 nodeRef 配置，支持 fork 节点选择

#### B-80 | 模拟执行不按流程顺序 + 添加模拟执行按钮

- **影响模块**: 前端编辑器
- **文件**: `webui/modules/auto/editor-app.js`
- **问题**:
  1. 模拟执行时节点执行顺序与实际流程不一致
  2. 当前页面没有模拟执行按钮
- **修复方案**:
  1. 修复模拟执行逻辑，按流程顺序执行
  2. 在工具栏添加"模拟执行"按钮

***

### 1.3 🟡 中优先级（体验优化）

#### B-81 | 工具箱缺 plugin 分类

- **影响模块**: 前端工具箱
- **文件**: `webui/modules/auto/editor-app.js:181-191`
- **问题**: `TOOLBOX_CATEGORIES` 没有 plugin 分类，但所有内置插件节点都使用 `category: 'plugin'`
- **修复方案**: 在 `TOOLBOX_CATEGORIES` 中添加 `{ id: 'plugin', name: '插件', color: '#a855f7', icon: 'fa-solid fa-puzzle-piece' }`，放在工具分类下方，默认折叠

#### B-82 | `check_color` sample\_mode 缺 showWhen

- **影响模块**: 检测节点
- **文件**: `automation/nodes/detection.py:37`
- **问题**: sample\_mode 应只在 check\_mode=contain 时显示
- **修复方案**: 添加 `showWhen: "check_mode=contain"`

#### B-83 | `check_screen` region 缺 showWhen

- **影响模块**: 检测节点
- **文件**: `automation/nodes/detection.py:125`
- **问题**: region 应只在特定模式下显示
- **修复方案**: 添加适当的 showWhen 条件

#### B-84 | `check_image` pyramid\_levels 缺 varRef

- **影响模块**: 检测节点
- **文件**: `automation/nodes/detection.py`
- **问题**: pyramid\_levels 参数应支持变量引用
- **修复方案**: 添加 `"varRef": True`

#### B-85 | `call_script` path 缺 varRef

- **影响模块**: 控制节点
- **文件**: `automation/nodes/control.py`
- **问题**: path 参数应支持变量引用
- **修复方案**: 添加 `"varRef": True`

#### B-86 | 拼音搜索映射缺失/过时（批量修复）

- **影响模块**: 前端工具箱
- **文件**: `webui/modules/auto/nodes.js:18-64`
- **问题**: 多个节点缺少拼音映射或存在过时条目
- **需添加**:
  - `flow/start`: 'kaishi start'
  - `flow/end`: 'jieshu end'
  - `detection/capture_source`: 'jietu jieping yuan capture'
  - `monitor/monitor_time`: 'shijian jianshi time'
  - `variable/var_set`: 'shezhi bianliang set'
  - `variable/var_convert`: 'leixing zhuanhuan convert'
  - `utility/const_bool`: 'buer changliang bool'
  - `utility/math_op`: 'shuxue yunsuan math'
  - `utility/math_func`: 'shuxue hanshu func'
  - `utility/compare`: 'shuzhi bijiao compare'
  - `utility/string_op`: 'zifuchuan caozuo string'
  - `utility/condition`: 'tiaojian xuanze condition'
  - `utility/delay`: 'yanchi delay'
- **需移除过时条目**:
  - `action/screenshot`（不存在）
  - `action/program_launch`（应为 program\_open）
  - `action/bookmark`（不存在于action）
  - `action/move_window`（应为 window\_manage）
  - `action/scroll`（应为 mouse\_scroll）
  - `variable/logic_op`（属 utility）
  - `variable/const_number`（属 utility）
  - `variable/const_string`（属 utility）
  - `monitor/monitor_image`（不存在）

#### B-87 | `utility/string_op` 缺 regex\_extract 操作

- **影响模块**: 工具节点
- **文件**: `automation/nodes/utility.py:108`
- **问题**: `variable/var_string` 有 regex\_extract，但 `utility/string_op` 没有
- **修复方案**: 添加 `regex_extract` 操作

#### B-88 | 分类颜色多处定义不一致

- **影响模块**: 前端核心
- **文件**:
  - `webui/modules/auto/editor-app.js:182,190` — flow=#ffffffff, utility=#d8d8d8ff
  - `webui/modules/auto/nodes.js:680` — flow=#ff0000ff, utility=#adadadff
- **修复方案**: 统一两处颜色定义

***

## 二、🆕 新功能需求

### F-01 | 变量选择按钮不展示内置变量

- **需求**: 内置变量不再在 `prop-btn outline var-ref-btn` 变量选择按钮中展示（太多了且不常用）
- **原因**: 内置变量数量多，影响用户查找常用变量
- **实现**:
  - 变量选择下拉列表过滤掉内置变量
  - 用户需打开变量浏览器查看/复制内置变量，或手动输入

### F-02 | 变量浏览器支持分类折叠

- **需求**: 变量浏览器支持将各个分类进行折叠，如"内置变量"、"节点输入"等
- **实现**:
  - 每个分类标题可点击展开/折叠
  - 记住用户折叠状态

### F-03 | 变量浏览器支持搜索和类型筛选

- **需求**: 变量浏览器支持变量搜索和按类型筛选
- **实现**:
  - 新增一行工具栏
  - 左侧：搜索框（支持变量名/拼音搜索）
  - 右侧：类型筛选下拉栏（全部/文本/数字/布尔/数组）

### F-04 | 变量浏览器支持拖拽改变大小

- **需求**: 变量浏览器面板支持拖拽改变大小
- **实现**:
  - 添加拖拽手柄
  - 记住用户调整的大小

***

## 三、⏳ 后期考虑项

### 3.1 2期延续项

| 编号   | 问题                                       | 说明                 |
| ---- | ---------------------------------------- | ------------------ |
| P-01 | mouse\_scroll delta 120 不直观              | 加 tooltip 说明即可     |
| P-02 | var\_compare 字符串比较回退不直观                  | 加说明即可              |
| P-06 | string\_op concat 只能拼接两个                 | 功能增强               |
| P-10 | preset\_find\_click 没有移动动画               | 功能增强               |
| P-13 | text\_input 中文输入可能不稳定                    | 需实际测试验证            |
| P-14 | Ctrl+D 只支持单节点复制                          | 功能增强               |
| P-15 | 拖拽节点位置不可撤销                               | 需配合 UndoManager 重构 |
| P-18 | 坐标拾取 hwnd\_var 被覆盖                       | 设计如此，优化体验的取舍       |
| P-19 | 拾取后自动修改 mode                             | 设计如此，优化体验的取舍       |
| P-21 | COMPLETED 状态下停止按钮行为异常                    | 体验优化               |
| P-22 | 新建画布保存确认逻辑可能中断                           | 体验优化               |
| P-23 | 插件串行加载速度慢                                | 性能优化               |
| P-25 | UndoManager 重复 push                      | 需梳理所有 push 调用点     |
| P-26 | store\_hwnd\_var 未被 \_pickSummaryKeys 跳过 | 仅影响内联显示            |
| P-28 | \_graphDirty 在 undo/redo 后状态不正确          | 需精确追踪 dirty 状态     |
| P-29 | ESC 键事件监听器泄漏                             | 内存泄漏量极小            |
| P-30 | 拾取修改属性不触发撤销系统                            | 需配合 UndoManager 重构 |
| P-31 | flashNode 多次调用产生多个 setTimeout            | 视觉效果问题             |
| P-32 | check\_results 无锁并发读写                    | Python GIL 提供基本保护  |
| P-34 | 变量面板用户变量不去重                              | 不影响功能正确性           |
| P-35 | 多处 try-catch 静默吞掉错误                      | 仅影响调试              |
| P-36 | 插件 backendAction 未存入注册表                  | 第三方插件生态发展后再改       |
| P-37 | color 字段不支持 varRef 输入                    | 颜色变量引用需求极低         |

### 3.2 3期新增后期考虑项

| 编号   | 问题                  | 说明          |
| ---- | ------------------- | ----------- |
| P-39 | `_pinyinMap` 过时条目清理 | 与 B-86 合并处理 |
| P-40 | 变量面板类型推断不完整         | 可接受"未知类型"   |

***

## 四、❌ 拒绝项

### 4.1 3期新拒绝项

| 编号   | 问题                                                | 拒绝原因                              |
| ---- | ------------------------------------------------- | --------------------------------- |
| X-13 | mouse\_scroll 缺坐标参数                               | 非核心场景，有替代方案（加鼠标移动节点）              |
| X-14 | mouse\_move\_rel 缺 easing 参数                      | 短距离缓动不可感知，增加复杂度收益低                |
| X-15 | mouse\_click vs mouse\_move move\_duration 默认值不一致 | 两种不同使用场景：点击UI类不需要延迟，视角转动需要延迟，设计合理 |
| X-16 | fork 多分支截图竞争                                      | 符合预期，能截到即可，微小变化可接受                |
| X-17 | email 插件密码明文存储                                    | 让插件作者自行解决                         |
| X-18 | DETECT-5 check\_ocr 隐式变量存储                        | 维持现状，用户可显式指定 store\_var           |
| X-19 | UTIL-5 bookmark name/remark 无实际功能                 | 仅作标注用途，维持现状                       |

### 4.2 2期拒绝项维持

| 编号         | 问题                   | 维持原因    |
| ---------- | -------------------- | ------- |
| X-01\~X-09 | 2期拒绝项，具体看“2期Bug汇总文档" | 用户决策维持  |
| X-10       | record 插件回放缓冲        | 有意设计    |
| X-11       | notify 弹窗阻塞          | 有意设计    |
| X-12       | HTML 注入/XSS          | 本地应用低风险 |

***

## 五、修复优先级排序

### P0 — 阻塞性（必须首先修复）

1. **B-64** — showWhen 不支持 `>=`（阻塞 B-57/B-67 等多分支配置）
2. **B-65** — 数组 varRef 不解析（影响9个核心参数）

### P1 — 致命级

1. **B-66** — 异常续流+重试机制（涉及全局配置+异常分类）
2. **B-67** — join 分支3-8配置缺失
3. **B-68** — 颜色解析不一致

### P2 — 高优先级

1. **B-69** — key\_action 语义不一致
2. **B-70** — program\_open 日志提示
3. **B-71** — sample\_mode 统一+中文化
4. **B-72** — monitor\_time 循环触发参数
5. **B-73** — var\_math round 隐藏 B
6. **B-74** — preset\_read\_text 异常续流（随 B-66）
7. **B-75** — 预设节点 middle 键
8. **B-76** — rect 判断健壮性
9. **B-77** — logic\_op bool 转换
10. **B-78** — check\_image confidence 输出
11. **B-79** — join nodeRef 完善
12. **B-80** — 模拟执行+按钮

### P3 — 中优先级

1. **B-81** — plugin 分类
2. **B-82\~B-85** — showWhen/varRef 补充
3. **B-86** — 拼音映射批量
4. **B-87** — string\_op regex\_extract
5. **B-88** — 颜色统一

### P4 — 新功能

1. **F-01\~F-04** — 变量浏览器优化

***

## 六、修复依赖关系

```
B-64 (showWhen >=) ──→ B-67 (join branch_required)
                    ──→ B-57 (fork branch_affinity，2期已采纳)
                    ──→ B-72 (monitor_time 循环参数)
                    ──→ B-82~B-83 (showWhen 条件)

B-66 (异常续流) ──→ B-74 (preset_read_text 异常)
                 ──→ 全局配置页面新增重试次数参数

B-65 (数组varRef) ──→ 所有 rect/region 参数的变量引用功能

B-71 (sample_mode统一) ──→ 需设计旧脚本兼容方案
```

***

## 七、编号对照表

### 3期审查编号 → B-/P-/X- 编号映射

| 3期审查编号           | 本文档编号 | 分类  |
| ---------------- | ----- | --- |
| NEW-1 / CANVAS-1 | B-64  | ✅采纳 |
| NEW-2 / ENGINE-1 | B-65  | ✅采纳 |
| NEW-3 / ENGINE-2 | B-66  | ✅采纳 |
| CTRL-1           | B-67  | ✅采纳 |
| DETECT-1         | B-68  | ✅采纳 |
| ACTION-1         | B-69  | ✅采纳 |
| ACTION-3         | X-13  | ❌拒绝 |
| ACTION-4         | B-70  | ✅采纳 |
| ACTION-5         | X-14  | ❌拒绝 |
| MONITOR-2        | B-71  | ✅采纳 |
| MONITOR-3        | B-72  | ✅采纳 |
| VAR-1            | B-73  | ✅采纳 |
| PRESET-2         | B-74  | ✅采纳 |
| PRESET-3         | B-75  | ✅采纳 |
| PRESET-4         | B-76  | ✅采纳 |
| UTIL-1           | B-77  | ✅采纳 |
| P-08             | B-78  | ✅采纳 |
| P-11             | B-79  | ✅采纳 |
| P-16             | B-80  | ✅采纳 |
| P-20             | B-81  | ✅采纳 |
| P-03             | B-82  | ✅采纳 |
| P-04             | B-83  | ✅采纳 |
| P-07             | B-84  | ✅采纳 |
| P-12             | B-85  | ✅采纳 |
| FLOW-1/2 + 多模块拼音 | B-86  | ✅采纳 |
| UTIL-3           | B-87  | ✅采纳 |
| CANVAS-2         | B-88  | ✅采纳 |
| P-17             | X-15  | ❌拒绝 |
| P-24             | X-16  | ❌拒绝 |
| P-38             | X-17  | ❌拒绝 |
| DETECT-5         | X-18  | ❌拒绝 |
| UTIL-5           | X-19  | ❌拒绝 |

***

## 八、统计汇总

| 分类     | 数量 | 说明                      |
| ------ | -- | ----------------------- |
| ✅ 致命级  | 5  | B-64\~B-68              |
| ✅ 高优先级 | 12 | B-69\~B-80              |
| ✅ 中优先级 | 11 | B-81\~B-88 + F-01\~F-04 |
| 🆕 新功能 | 4  | F-01\~F-04              |
| ⏳ 后期考虑 | 18 | P-01\~P-40              |
| ❌ 拒绝   | 8  | X-13\~X-19 + 2期维持       |

***

**文档结束**
