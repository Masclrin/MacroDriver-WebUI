**中文总结：**

1. **用户要做什么**：
   - 阅读之前的优秀对话存档，理解其bug查找方法论
   - 基于该方法论，继续之前未完成的任务：对监视器、变量、预设、工具模块进行深度探索和bug检查
2. **计划步骤**：
   - 分析当前项目结构，了解各模块
   - 对监视器、变量、预设、工具模块逐一进行深度bug检查
3. **缺少的信息**：
   - 需要了解项目整体结构
   <br />

***

# 🔍 自动化编辑器 - 监视器、变量、预设、工具模块 全面问题报告

***

## 一、监视器模块

### 🔴🔴 BUG-M1: `monitor_color/monitor_ocr/monitor_timer` — interval/timeout 使用变量引用时崩溃

- **后端定义** \[monitor.py:18-19]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/monitor.py#L18): `interval` 和 `timeout` 标记了 `varRef: True`
- **前端 fallback** \[nodes.js:337]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L337): 同样有 `varRef:true`，用户可以点击 `$` 按钮选择变量
- **后端处理器** \[monitor.py:95-96]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/monitor.py#L95):
  ```python
  interval = float(node.params.get("interval", 100)) / 1000.0
  timeout_ms = float(node.params.get("timeout", 0))
  ```
- **影响**: 用户通过 `$` 按钮输入 `${my_interval}` 后，`float("${my_interval}")` 抛出 `ValueError`，且此处**没有 try/except**，异常直接传播到引擎的 `_execute_node`，导致**整个脚本执行终止**。用户完全不知道为什么脚本突然停了。
- **修复建议**: 使用 `_resolve_value` 解析后再转 float，并添加异常处理。

### 🔴🔴 BUG-M2: `monitor_color/monitor_ocr` — `auto_stop` 参数完全无效

- **后端定义** \[monitor.py:23]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/monitor.py#L23): `"auto_stop": {"type": "boolean", "default": True, "description": "触发后是否自动停止此监视器"}`
- **后端处理器** \[monitor.py:142-148]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/monitor.py#L142):
  ```python
  if should_trigger:
      triggered_count += 1
      if repeat_count > 0 and triggered_count >= repeat_count:
          trigger_event.set()
          break
      trigger_event.set()
      break  # ← 无论 auto_stop 是什么值，都直接 break！
  ```
- **影响**: 无论 `auto_stop` 设为 True 还是 False，监视器在第一次触发后**总是停止**。用户设置 `auto_stop=False` 期望监视器持续监控并多次触发，但实际上只能触发一次。**auto\_stop 功能完全失效**。
- **修复方案**（详见 `docs/execution-model-upgrade-design.md` §4）：`auto_stop=False` 时进入循环模式——触发后执行后续节点，然后自动回到监视状态继续监听（并发执行后续节点）；新增 `recheck_delay_ms` 防抖参数；新增 `max_triggers`/`auto_close_after_ms` 自动关闭条件。

### 🔴 BUG-M3: `monitor_color` — 缺少 `check_mode` 和 `sample_mode` 参数定义

- **后端处理器** \[monitor.py:33-34]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/monitor.py#L33):
  ```python
  params.get("check_mode", "contain"), params.get("sample_mode", "center"),
  ```
- **后端定义** \[monitor.py:12-24]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/monitor.py#L12): `params_schema` 中**没有** `check_mode` 和 `sample_mode`
- **前端 fallback** \[nodes.js:332-341]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L332): 同样没有这两个参数
- **影响**: 处理器使用了 `check_mode` 和 `sample_mode`，但用户在UI上**无法设置**这些参数。颜色监视永远使用默认的 "contain" 检测方式和 "center" 采样方式。对比检测节点 `check_color` 有完整的 `check_mode`（exact/contain/change/area）和 `sample_mode`（center/mean/max\_diff）选项。
- **同样缺失**: `change_threshold` 参数（处理器第35行使用，但定义中没有）

### 🔴 BUG-M4: `monitor_color` — `hwnd_var` 缺少 showWhen 条件

- **后端定义** \[monitor.py:15]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/monitor.py#L15): `"hwnd_var": {...}` — 没有 showWhen
- **前端 fallback** \[nodes.js:335]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L335): 同样没有 showWhen
- **影响**: 当 `mode=screen` 时，`hwnd_var`（窗口变量）仍然显示在属性面板中，但 screen 模式不需要窗口句柄。对比检测节点 `check_color` 的 `hwnd_var` 有 `showWhen: "mode=window"`。同时，`relative` 模式也需要 hwnd\_var（参考 \[coordinate.py:98-104]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/engine/coordinate.py#L98)），showWhen 应为 `"mode=window,mode=relative"`。
- **同样影响**: `monitor_ocr` 的 `hwnd_var` 也缺少 showWhen

### 🔴 BUG-M5: `monitor_ocr` — `match_number` 不使用 `_resolve_value`

- **后端处理器** \[monitor.py:61]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/monitor.py#L61):
  ```python
  match_number = float(params.get("match_number", 0))
  ```
- **后端定义** \[monitor.py:44]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/monitor.py#L44): `match_number` 有 `varRef: True`
- **影响**: 用户通过变量选择器输入 `${my_threshold}`，`float("${my_threshold}")` 抛出 ValueError，被外层 try/except 捕获后返回 False。监视器**永远不会触发**，但用户不知道为什么。

### 🟡 BUG-M6: `monitor_timer` / `monitor_time` — `timeout` 输出端口永远不会触发

- **后端定义** \[monitor.py:63-64]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/monitor.py#L63): outputs 包含 `{name: "timeout", type: "flow"}`
- **monitor\_timer**: 没有 `timeout` 参数，`timeout_ms` 始终为 0
- **monitor\_time**: `_handle_monitor_time` 处理器从不执行 `timeout` 输出端口
- **影响**: 用户看到 timeout 输出端口，连线到后续节点，但这条线**永远不会被执行**。用户困惑于"为什么超时后的逻辑不运行"。

### 🟡 BUG-M7: `monitor_ocr` — `store_var`/`store_number` 是输出变量但标记为 varRef

- **后端定义** \[monitor.py:51-52]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/monitor.py#L51): `store_var` 和 `store_number` 都有 `varRef: True`
- **影响**: varRef 标记让前端显示 `$` 变量选择按钮，用户点击后看到已有变量列表，可能误以为要**选择**一个已有变量来读取，而实际是**创建/覆盖**该变量。应使用不同的标记（如 `varOutput`）。

### 🟡 BUG-M8: `monitor_color` — `tolerance`/`change_threshold` 不使用 `_resolve_value`

- **后端处理器** \[monitor.py:32-35]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/monitor.py#L32):
  ```python
  int(params.get("tolerance", 10)), ... float(params.get("change_threshold", 10))
  ```
- **前端** `_normalizeSchema` 自动给 `tolerance` 和 `change_threshold` 加了 varRef
- **影响**: 与 BUG-M5 类似，用户使用变量引用时会导致 ValueError，监视器永远不触发。

***

## 二、变量模块

### 🔴🔴 BUG-V1: `var_set` — boolean 类型转换错误

- **后端处理器** \[variable.py:47]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/variable.py#L47):
  ```python
  elif var_type == "boolean":
      value = bool(value)
  ```
- **影响**: Python 的 `bool()` 对任何非空字符串返回 True，包括 `"false"`、`"0"`、`"no"`。用户设置 `var_type=boolean`，`value="false"`，期望存储 False，实际存储了 True。这是**数据正确性**问题。
- **修复建议**: 参考 `var_convert` 的实现，使用 `value.lower() not in ("", "0", "false", "no", "off", "none", "null")`

### 🔴 BUG-V2: `var_math` — op 枚举选项前后端不一致

- **后端定义** \[variable.py:33]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/variable.py#L33): `enum: ["add", "sub", "mul", "div", "mod", "min", "max", "abs", "round"]`
- **前端 fallback** \[nodes.js:376]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L376): `options:['+','-','*','/','%','min','max','abs','round']`
- **影响**: 后端定义加载时，用户看到英文 "add/sub/mul/div/mod"；fallback 模式下，用户看到符号 "+/-/\*/÷/%"。虽然处理器有别名映射，但**用户体验不一致**。

### 🔴 BUG-V3: `var_math` — a/b 默认值前后端不一致

- **后端定义** \[variable.py:34-35]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/variable.py#L34): `a` 默认 `"0"`, `b` 默认 `"0"`
- **前端 fallback** \[nodes.js:377]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L377): `a` 默认 `''`, `b` 默认 `''`
- **影响**: 后端定义加载时，a/b 默认为 "0"（运算结果为 0）；fallback 模式下，a/b 默认为空字符串，`float("")` 抛出 ValueError。用户拖出节点后不填参数直接运行，行为取决于后端定义是否成功加载。

### 🔴 BUG-V4: `var_compare` — op 枚举选项前后端不一致

- **后端定义** \[variable.py:56]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/variable.py#L56): `enum: ["eq", "ne", "gt", "lt", "ge", "le"]`
- **前端 fallback** \[nodes.js:380]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L380): `options:['>','<','>=','<=','==','!=']`
- **影响**: 同 BUG-V2，用户体验不一致。

### 🔴 BUG-V5: `var_string` — `replace` 操作只能替换为空字符串（删除）

- **后端处理器** \[variable.py:136]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/variable.py#L136):
  ```python
  elif op == "replace":
      result = a.replace(b, "")
  ```
- **影响**: `replace` 操作的第二个参数硬编码为空字符串，用户**无法指定替换内容**。这实际上是"删除"操作而非"替换"。对比 `utility/string_op` 的 replace 正确使用了 `s.replace(pa, pb)`。
- **修复建议**: 添加第三个参数作为替换内容，或至少在UI中说明这是删除操作。

### 🟡 BUG-V6: `var_string` — `substr` 的参数格式不直观

- **后端处理器** \[variable.py:128-132]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/variable.py#L128):
  ```python
  parts = b.split(",")
  start = int(parts[0]) if len(parts) > 0 else 0
  length = int(parts[1]) if len(parts) > 1 else len(a)
  ```
- **影响**: 用户需要在参数B中输入 `"0,5"` 格式来截取前5个字符。没有单独的"起始位置"和"长度"字段，也没有提示说明格式。对比 `utility/string_op` 的 substring 使用了独立的 param\_b（起始）和 param\_c（结束）参数，更直观。

### 🟡 BUG-V7: `var_string` — `split` 只返回第一部分

- **后端处理器** \[variable.py:138-139]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/variable.py#L138):
  ```python
  result = parts[0] if parts else ""
  ```
- **影响**: split 操作只返回分割后的第一个元素，用户无法获取其他部分。对比 `utility/string_op` 的 `split_index` 支持指定索引。

### 🟡 BUG-V8: `var_math` — `abs`/`round` 是一元运算但有二元输入

- **后端定义** \[variable.py:23-24]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/variable.py#L23): inputs 包含 `A` 和 `B` 两个数据端口
- **影响**: `abs` 和 `round` 只使用操作数A，但节点始终显示A和B两个输入端口。用户困惑于"abs操作时B应该填什么"。

### 🟡 BUG-V9: `var_compare` — 字符串比较回退逻辑不直观

- **后端处理器** \[variable.py:100-104]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/variable.py#L100):
  ```python
  try:
      a_num = float(a)
      b_num = float(b)
  except (ValueError, TypeError):
      a_num, b_num = str(a), str(b)
  ```
- **影响**: 当值无法转为数字时，回退到字符串比较。字符串的 `"10" > "9"` 结果为 False（字典序），用户可能期望数值比较。

***

## 三、预设模块

### 🔴 BUG-P1: 所有预设节点 — `hwnd_var` 缺少 showWhen 条件

- **preset\_click** \[preset.py:13]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/preset.py#L13): `hwnd_var` 没有 showWhen
- **preset\_find\_click** \[preset.py:33]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/preset.py#L33): 同上
- **preset\_read\_text** \[preset.py:51]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/preset.py#L51): 同上
- **前端 fallback** \[nodes.js:484/490/497]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L484): 同样没有 showWhen
- **影响**: 与检测节点同类问题。当 `mode=screen` 时，`hwnd_var` 仍然显示，但不需要。`mode=relative` 时需要 hwnd\_var 但没有提示。

### 🔴 BUG-P2: `preset_find_click` — `template_path` 缺少 varRef

- **后端定义** \[preset.py:34]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/preset.py#L34): `"template_path": {"type": "string", "default": "", "format": "path"}` — 没有 varRef
- **前端 fallback** \[nodes.js:491]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L491): `template_path:{type:'string',...}` — 没有 varRef
- **影响**: 用户无法通过变量动态指定模板图片路径。`_normalizeSchema` 只给 `template_path` 加 `browseType:'template'`，不加 varRef。对比 `check_image` 的 `template_path` 也没有 varRef，但后端处理器使用 `_resolve_value` 解析了它。

### 🔴 BUG-P3: `preset_read_text` — `store_var` 不在变量选择器中

- **前端** `_collectStructuredVars` \[property.js:889-1101]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/property.js#L889): 没有任何 `preset` 相关的匹配逻辑
- **影响**: 用户在 `preset_read_text` 中设置了 `store_var="my_text"`，但在其他节点的变量选择器中**看不到**这个变量。用户必须手动输入 `${my_text}`，没有自动补全和类型提示。

### 🟡 BUG-P4: `preset_find_click` — 没有移动动画，直接跳转鼠标

- **后端处理器** \[preset.py:72]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/preset.py#L72):
  ```python
  set_cursor_pos(phys_x, phys_y)  # 直接跳转
  ```
- **对比** `preset_click` \[preset.py:22-25]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/preset.py#L22): 使用 `_interpolated_move` 平滑移动
- **影响**: 找图点击时鼠标瞬间跳转到目标位置，没有移动过程。某些游戏/应用的防作弊检测可能会识别这种瞬移行为。与 `preset_click` 的行为不一致。

### 🟡 BUG-P5: `preset_find_click` — 没有数据输出端口

- **后端定义** \[preset.py:27-28]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/preset.py#L27): outputs 只有 `found` 和 `not_found`（flow类型）
- **影响**: 找到匹配后，匹配坐标和置信度没有通过数据端口输出。用户如果需要在匹配位置做进一步操作（如右键点击、拖拽等），必须使用更复杂的 `check_image` + `mouse_click` 组合。

### 🟡 BUG-P6: `preset_read_text` — 错误时仍执行 next 流程

- **后端处理器** \[preset.py:118-120]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/preset.py#L118):
  ```python
  except Exception as e:
      print(f"[新引擎] 读取数字文本出错: {e}")
      _execute_flow(node.id, "next", ctx)  # 错误后仍继续执行！
  ```
- **影响**: OCR 识别失败时，`store_var` 可能是空值或未设置，但后续节点仍会执行。用户可能基于空值做判断，导致意外行为。对比 `preset_find_click` 在错误时走 `not_found` 分支，设计更合理。

### 🟡 BUG-P7: `preset_read_text` — 没有数据输出端口

- **后端定义** \[preset.py:47]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/preset.py#L47): outputs 只有 `{name: "next", type: "flow"}`
- **影响**: 读取的文本值只能通过 `store_var` 变量获取，没有数据输出端口。其他节点无法通过数据连线直接获取读取结果。

***

## 四、工具模块

### 🔴🔴 BUG-U1: `utility/delay` — `ms` 使用变量引用时崩溃

- **后端定义** \[utility.py:140]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/utility.py#L140): `ms` 有 `varRef: True`
- **后端处理器** \[utility.py:187]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/utility.py#L187):
  ```python
  ms = float(node.params.get("ms", 1000))
  ```
- **影响**: 与 BUG-M1 同类。用户输入 `${delay_ms}` 后，`float("${delay_ms}")` 抛出 ValueError，**整个脚本执行终止**。

### 🔴🔴 BUG-U2: `utility/condition` — `cond_var` 不解析 `${}` 变量引用语法

- **后端处理器** \[utility.py:161-163]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/utility.py#L161):
  ```python
  cond_var = node.params.get("cond_var", "")
  if cond_var:
      cond = bool(ctx.variables.get(cond_var, False))
  ```
- **后端定义** \[utility.py:125]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/utility.py#L125): `cond_var` 有 `varRef: True`
- **影响**: 用户通过 `$` 按钮选择变量后，`cond_var` 的值为 `"${my_var}"`。但处理器直接用这个值作为 key 去 `ctx.variables` 查找，找不到名为 `"${my_var}"` 的变量，**条件永远为 False**。用户期望条件节点根据变量值判断，但实际永远走 false\_val 分支。
- **修复建议**: 使用 `_extract_var_name` 去除 `${}` 包装，或使用 `_resolve_value` 解析。

### 🔴 BUG-U3: `utility/string_op` — `param_a/b/c` 不使用 `_resolve_value`

- **后端处理器** \[utility.py:120-122]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/utility.py#L120):
  ```python
  pa = node.params.get("param_a", "")
  pb = node.params.get("param_b", "")
  pc = node.params.get("param_c", "")
  ```
- **后端定义** \[utility.py:110-112]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/utility.py#L110): 三个参数都有 `varRef: True`
- **对比**: `input_str` 在同一处理器中使用了 `_resolve_value`（第118行）
- **影响**: 用户在 param\_a/b/c 中使用 `${var}` 引用变量时，得到的是字面字符串 `"${var}"` 而非变量值。例如 replace 操作中，用户想用变量作为替换内容，但替换结果中出现了 `${var}` 字面文本。

### 🔴 BUG-U4: `utility/const_number/const_string` — varRef 标记但处理器不解析

- **后端定义** \[utility.py:10]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/utility.py#L10): `value` 有 `varRef: True`
- **前端 fallback** \[nodes.js:503]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L503): `value` **没有** varRef
- **后端处理器** \[utility.py:18]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/utility.py#L18): `value = node.params.get("value", 0)` — 不使用 `_resolve_value`
- **影响**: 后端定义加载时，常量节点的 value 字段有 `$` 按钮，但输入变量引用后不会被解析，存储的是字面字符串。**常量节点不应该支持 varRef**——如果值是变量引用，就不应该用常量节点。

### 🔴 BUG-U5: `utility/bookmark` — `mode` 和 `hwnd_var` 参数在处理器中完全未使用

- **后端定义** \[utility.py:159-164]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/utility.py#L159): 定义了 `mode`（screen/window/relative）和 `hwnd_var`
- **后端处理器** \[utility.py:175-184]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/utility.py#L175):
  ```python
  x = float(node.params.get("x", 0))
  y = float(node.params.get("y", 0))
  # ... 只存储原始值，完全忽略 mode 和 hwnd_var
  ```
- **`_resolve_value`** \[engine.py:354-356]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/engine.py#L354): 引用 `@name.x` 时也只读取原始参数值
- **影响**: 用户设置 `mode=window` 并填写 `hwnd_var`，期望坐标是相对于窗口的，但实际存储和使用的是原始坐标值。`mode` 和 `hwnd_var` 参数是**完全无效的装饰**，误导用户。
- **修复方案**（详见 `docs/execution-model-upgrade-design.md` §6）：重写 bookmark 节点，定位为"快捷存储常用位置框，供各节点调用"。支持多书签、mode 坐标转换、hwnd_var 窗口定位。每次被下游引用时重新计算当前值（而非缓存）。

### 🟡 BUG-U6: `utility/bookmark` — `hwnd_var` 缺少 showWhen 条件

- 与其他有 mode 参数的节点同类问题。

### 🟡 BUG-U7: `utility/logic_op` — `not` 是一元运算但有二元输入

- **后端定义** \[utility.py:75-76]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/utility.py#L75): inputs 包含 A 和 B 两个 boolean 端口
- **后端处理器** \[utility.py:88]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/utility.py#L88): `"not": lambda: not a` — 只使用 A
- **影响**: 选择 `not` 运算时，B 输入端口仍然显示但完全无用。用户困惑于"B应该连什么"。

### 🟡 BUG-U8: `utility/math_func` — sin/cos 使用弧度，无说明

- **后端处理器** \[utility.py:68-69]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/utility.py#L68): `math.sin(x)`, `math.cos(x)` — 使用弧度
- **后端定义** \[utility.py:64]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/utility.py#L64): description 只写"函数"，没有说明弧度
- **影响**: 大多数非专业用户习惯使用角度。输入 90 期望 sin(90°)=1，实际 sin(90rad)≈0.894。

### 🟡 BUG-U9: `utility/string_op` — `concat` 只能拼接两个字符串

- **后端处理器** \[utility.py:123-124]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/utility.py#L123):
  ```python
  if op == "concat":
      result = s + pa
  ```
- **影响**: 只拼接输入字符串和 param\_a。用户无法一次拼接三个或更多字符串，需要链式使用多个 concat 操作。

***

## 五、跨模块通用问题

### 🔴 BUG-G1: 变量选择器中 `check_image` 的 `store_var` 被重复收集且类型冲突

- **前端** `_collectStructuredVars` \[property.js:940-956]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/property.js#L940): 通用 `check_` 分支将 `store_var` 类型设为 `boolean`
- **前端** `_collectStructuredVars` \[property.js:1015-1019]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/property.js#L1015): `check_image` 专用分支将 `store_var` 类型设为 `string`
- **影响**: `check_image` 的 `store_var` 在变量选择器中出现两次，一次标注为"布尔"类型，一次标注为"文本"类型。用户困惑于同一变量为什么出现两次且类型不同。

### 🟡 BUG-G2: 所有有 `mode` 参数的节点 — `hwnd_var` 在 `relative` 模式下不显示

- **当前**: `hwnd_var` 的 showWhen 通常是 `"mode=window"`
- **但后端** \[coordinate.py:98-104]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/engine/coordinate.py#L98): `relative` 模式也需要 `hwnd` 来获取窗口客户区尺寸
- **影响**: 用户选择 `mode=relative` 时看不到 `hwnd_var` 字段，无法指定窗口，坐标解析回退到 1920x1080 默认尺寸。relative 模式下的坐标计算结果不正确。
- **修复**: showWhen 应改为 `"mode=window,mode=relative"` 或 `"mode!=screen"`

### 🟡 BUG-G3: 所有 `store_var`/`store_number`/`counter_var` 字段 — 输出变量标记为 varRef 误导用户

- 涉及节点: `var_math`, `var_string`, `var_convert`, `monitor_ocr`, `preset_read_text`, `loop_count`, `check_color`, `check_ocr`, `check_image`
- **影响**: varRef 标记让变量选择器显示已有变量列表，用户误以为要**选择**一个变量来读取，而实际是**创建/覆盖**该变量。

***

## 问题优先级汇总

| 优先级  | 编号     | 问题                                              | 类型  |
| ---- | ------ | ----------------------------------------------- | --- |
| 🔴🔴 | BUG-M1 | 监视器 interval/timeout 使用变量引用时崩溃                  | 后端  |
| 🔴🔴 | BUG-M2 | 监视器 auto\_stop 完全无效                             | 后端  |
| 🔴🔴 | BUG-V1 | var\_set boolean 类型转换错误                         | 后端  |
| 🔴🔴 | BUG-U1 | delay ms 使用变量引用时崩溃                              | 后端  |
| 🔴🔴 | BUG-U2 | condition cond\_var 不解析 ${} 语法                  | 后端  |
| 🔴   | BUG-M3 | monitor\_color 缺少 check\_mode/sample\_mode 定义   | 前后端 |
| 🔴   | BUG-M4 | 监视器 hwnd\_var 缺少 showWhen                       | 前后端 |
| 🔴   | BUG-M5 | monitor\_ocr match\_number 不使用 \_resolve\_value | 后端  |
| 🔴   | BUG-V2 | var\_math op 枚举前后端不一致                           | 前后端 |
| 🔴   | BUG-V3 | var\_math a/b 默认值前后端不一致                         | 前后端 |
| 🔴   | BUG-V4 | var\_compare op 枚举前后端不一致                        | 前后端 |
| 🔴   | BUG-V5 | var\_string replace 只能替换为空                      | 后端  |
| 🔴   | BUG-P1 | 预设节点 hwnd\_var 缺少 showWhen                      | 前后端 |
| 🔴   | BUG-P2 | preset\_find\_click template\_path 缺少 varRef    | 前后端 |
| 🔴   | BUG-P3 | preset\_read\_text store\_var 不在变量选择器中          | 前端  |
| 🔴   | BUG-U3 | string\_op param\_a/b/c 不使用 \_resolve\_value    | 后端  |
| 🔴   | BUG-U4 | const\_number/const\_string varRef 标记但处理器不解析    | 前后端 |
| 🔴   | BUG-U5 | bookmark mode/hwnd\_var 完全未使用                   | 后端  |
| 🔴   | BUG-G1 | check\_image store\_var 变量选择器重复且类型冲突            | 前端  |
| 🟡   | BUG-M6 | monitor\_timer/time timeout 端口永远不触发             | 设计  |
| 🟡   | BUG-M7 | monitor\_ocr store\_var 是输出但标记为 varRef          | 设计  |
| 🟡   | BUG-M8 | monitor\_color tolerance 不使用 \_resolve\_value   | 后端  |
| 🟡   | BUG-V6 | var\_string substr 参数格式不直观                      | UX  |
| 🟡   | BUG-V7 | var\_string split 只返回第一部分                       | 设计  |
| 🟡   | BUG-V8 | var\_math abs/round 一元运算有二元输入                   | 设计  |
| 🟡   | BUG-V9 | var\_compare 字符串比较回退不直观                         | 设计  |
| 🟡   | BUG-P4 | preset\_find\_click 没有移动动画                      | 设计  |
| 🟡   | BUG-P5 | preset\_find\_click 没有数据输出端口                    | 设计  |
| 🟡   | BUG-P6 | preset\_read\_text 错误时仍执行 next                  | 设计  |
| 🟡   | BUG-P7 | preset\_read\_text 没有数据输出端口                     | 设计  |
| 🟡   | BUG-U6 | bookmark hwnd\_var 缺少 showWhen                  | 前后端 |
| 🟡   | BUG-U7 | logic\_op not 一元运算有二元输入                         | 设计  |
| 🟡   | BUG-U8 | math\_func sin/cos 弧度无说明                        | UX  |
| 🟡   | BUG-U9 | string\_op concat 只能拼接两个字符串                     | 设计  |
| 🟡   | BUG-G2 | 所有节点 hwnd\_var relative 模式下不显示                  | 前后端 |
| 🟡   | BUG-G3 | 所有 store\_var 输出变量标记为 varRef 误导                 | 设计  |

***

**最关键的修复项**：

1. **BUG-M1/U1**: 监视器和延迟节点的 varRef 参数不使用 `_resolve_value`，使用变量引用时直接崩溃
2. **BUG-U2**: 条件节点的 `cond_var` 不解析 `${}` 语法，条件永远为 False
3. **BUG-M2**: 监视器 `auto_stop` 完全无效，只能触发一次——修复为循环模式 + 自动关闭条件（详见 `docs/execution-model-upgrade-design.md` §4）
4. **BUG-V1**: `var_set` 的 boolean 转换把 "false" 转为 True
5. **BUG-U3**: `string_op` 的 param\_a/b/c 不解析变量引用
6. <br />

所有任务已完成！以下是完成情况总结：

***

## ✅ 已完成的任务

###

### 2. 四模块深度Bug检查

共发现 **5个致命BUG**、**14个高优先级BUG**、**16个中优先级问题**：

| 模块  | 🔴🔴 | 🔴 | 🟡 |
| --- | ---- | -- | -- |
| 监视器 | 2    | 3  | 3  |
| 变量  | 1    | 4  | 4  |
| 预设  | 0    | 3  | 4  |
| 工具  | 2    | 3  | 4  |
| 跨模块 | 0    | 1  | 2  |

**最需要优先修复的5个问题**：

1. 监视器/延迟节点的 varRef 参数不使用 `_resolve_value`，使用变量引用时**直接崩溃**
2. 条件节点的 `cond_var` 不解析 `${}` 语法，条件**永远为 False**
3. 监视器 `auto_stop` 完全无效，**只能触发一次**
4. `var_set` 的 boolean 转换把 `"false"` **转为 True**
5. `string_op` 的 param\_a/b/c **不解析变量引用**

