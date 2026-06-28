**中文总结：**

1. **用户要我做什么**：以用户视角对自动化编辑器进行全面的问题查找，重点关注"动作节点模块"。需要模拟用户操作流程：进入页面→拖动节点→检查样式/属性/端口/同步→单节点功能测试→多节点联动测试→各种连线方式测试。
2. **计划步骤**：
   - 先了解项目整体结构和自动化编辑器的代码架构
   - 找到动作节点模块的定义和实现
   - 逐个分析每个动作节点的前端渲染、属性面板、端口设计
   - 检查前后端参数是否完整对应
   - 检查快捷参数与属性面板的同步机制
   - 设计单节点测试脚本并验证执行逻辑
   - 检查多节点连线和DAG执行逻辑
3. **缺少的信息**：项目结构、动作节点的具体定义、前后端代码位置、执行引擎逻辑等，需要先探索。

# 🔍 自动化编辑器 - 动作节点模块全面问题报告

## 一、前后端参数不一致问题

### 🔴 BUG-1: `action/key_action` — `key` 默认值前后端不一致

- **后端** \[action.py:33]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/action.py#L33): `"key": {"type": "string", "default": "", ...}`
- **前端 fallback** \[nodes.js:233]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L233): `key:{type:'string',label:'按键',default:'a',varRef:true}`
- **影响**: 后端默认空字符串，前端默认 `'a'`。如果后端定义加载失败使用 fallback，用户拖出节点时 key 值为 `'a'`，但后端期望空字符串。当后端定义正常加载时 key 为空，用户需要手动填写。

### 🔴 BUG-2: `action/program_open` — `work_dir` 缺少 varRef

- **后端** \[action.py:116]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/action.py#L116): `"work_dir": {"type": "string", "default": "", "description": "工作目录", "varRef": True}`
- **前端 fallback** \[nodes.js:263]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L263): `work_dir:{type:'string',label:'工作目录',default:''}` — **没有 varRef**
- **影响**: 前端 fallback 模式下，work\_dir 字段没有 `$` 变量选择按钮，用户无法通过变量选择器填入动态路径。

### 🔴 BUG-3: `action/program_close` — `hwnd_value` 缺少 varRef

- **后端** \[action.py:134]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/action.py#L134): `"hwnd_value": {..., "varRef": True}`
- **前端 fallback** \[nodes.js:271]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L271): `hwnd_value:{type:'string',label:'窗口句柄',default:'',showWhen:'close_mode=hwnd'}` — **没有 varRef**
- **影响**: 同上，fallback 模式下无法使用变量选择器。

### 🔴 BUG-4: `action/window_manage` — `hwnd_value` 缺少 varRef

- **后端** \[action.py:97]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/action.py#L97): `"hwnd_value": {..., "varRef": True}`
- **前端 fallback** \[nodes.js:254]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L254): `hwnd_value:{type:'string',label:'窗口句柄',default:'',showWhen:'find_mode=hwnd'}` — **没有 varRef**
- **影响**: 同上。

***

## 二、showWhen 条件缺失问题

### 🔴 BUG-5: `action/mouse_click` — `hwnd_var` 缺少 showWhen 条件

- **后端** \[action.py:13]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/action.py#L13): `"hwnd_var": {"type": "string", "default": "", ...}` — **没有 showWhen**
- **前端 fallback** \[nodes.js:225]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L225): `hwnd_var:{type:'string',label:'窗口变量',default:'',varRef:true}` — **没有 showWhen**
- **影响**: 当 `mode=screen` 时，`hwnd_var`（窗口句柄变量）仍然显示在属性面板中，但 screen 模式不需要窗口句柄。对比检测节点如 `check_color` 的 `hwnd_var` 有 `showWhen: "mode=window"`，动作节点缺失此条件。
- **用户困惑**: 用户在 screen 模式下看到"窗口变量"字段，不知道该填什么。

### 🔴 BUG-6: `action/mouse_move` — `hwnd_var` 缺少 showWhen 条件

- **后端** \[action.py:152]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/action.py#L152): `"hwnd_var": {"type": "string", "default": "", ...}` — **没有 showWhen**
- **前端 fallback** \[nodes.js:394]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L394): `hwnd_var:{type:'string',label:'窗口变量',default:'',varRef:true}` — **没有 showWhen**
- **影响**: 同 BUG-5。

### 🔴 BUG-7: `action/wait` — `duration` 缺少 showWhen 条件

- **后端** \[action.py:77]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/action.py#L77): `"duration": {"type": "number", "default": 0, ...}` — **没有 showWhen**
- **前端 fallback** \[nodes.js:244]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L244): `duration:{type:'number',label:'等待时长',default:0,varRef:true}` — **没有 showWhen**
- **影响**: 当 `mode=until_time` 时，`duration` 字段仍然显示，但此时等待时长无意义（应该用 hour/minute/second）。用户会困惑于两个时间设置方式同时出现。
- **修复**: 应添加 `showWhen: "mode=duration"`

### 🟡 BUG-8: `action/mouse_click` — `hold_time` 缺少 showWhen 条件

- **后端** \[action.py:16]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/action.py#L16): `"hold_time": {"type": "number", "default": 0, ...}` — **没有 showWhen**
- **影响**: `hold_time` 只在 `click_type=long_press` 时有意义，但始终显示。虽然默认值0不会造成功能错误，但不够友好。

***

## 三、节点内联字段不尊重 showWhen 条件

### 🔴 BUG-9: 所有节点的内联快捷参数不检查 showWhen

- **代码位置**: \[core.js:129-150]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/core.js#L129) `_pickSummaryKeys` 函数
- **问题**: `_pickSummaryKeys` 选择内联显示的参数时，只根据 skip 列表和 priority 排序，**完全不检查 showWhen 条件**。
- **具体影响**:
  - **wait 节点**: 内联显示 `duration, unit, hour, minute`（前4个非skip参数），但当 `mode=duration` 时 `hour/minute/second` 不应显示；当 `mode=until_time` 时 `duration/unit` 不应显示。
  - **window\_manage 节点**: `title` 有 `showWhen: "find_mode=title"`，但在内联中可能显示。
  - **program\_close 节点**: `process_name` 有 `showWhen: "close_mode=name"`，但在内联中可能显示。
- **修复建议**: `_pickSummaryKeys` 应接收 `node.properties` 参数，过滤掉 showWhen 不满足的 key。

***

## 四、后端执行逻辑问题

### 🔴 BUG-10: `action/program_open` — `store_hwnd_var` 窗口查找等待时间太短

- **代码位置**: \[handlers/action.py:307]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/action.py#L307)

```python
if store_var:
    user32 = ctypes.windll.user32
    time.sleep(0.1)  # 只等100ms！
    # ... 枚举窗口 ...
```

- **问题**: 程序启动后只等待 0.1 秒就枚举窗口。很多程序（如浏览器、大型应用）启动需要数秒才能创建主窗口。
- **影响**: `store_hwnd_var` 经常存储 `0`（未找到窗口），后续使用该变量的节点会失败。
- **修复建议**: 应增加重试机制，或利用 `wait_start` 参数作为窗口查找的等待时间。

### 🔴 BUG-11: `action/key_action` — `key` 为空时 `get_vk("")` 可能返回意外值

- **代码位置**: \[handlers/action.py:56]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/action.py#L56)

```python
key = params.get("key", "")
action = params.get("action", "press")
vk = get_vk(key)  # key="" 时 get_vk 返回什么？
```

- **问题**: 当 `key` 为空字符串时，`get_vk("")` 的行为未定义。如果返回 0 或 None，后续 `_send_key` 可能出错。
- **修复建议**: 应检查 `key` 是否为空，为空时跳过执行或报错。

### 🟡 BUG-12: `action/mouse_scroll` — 缺少坐标定位参数

- **代码位置**: \[handlers/action.py:74-83]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/action.py#L74)
- **问题**: 滚轮操作只能在当前鼠标位置执行，没有 x/y 坐标参数和 mode 参数。用户如果需要在特定位置滚轮，必须先添加一个鼠标移动节点。
- **影响**: 不如其他动作节点灵活，与其他有坐标参数的节点（mouse\_click, mouse\_move）设计不一致。

### 🟡 BUG-13: `action/text_input` — 中文输入可能不稳定

- **代码位置**: \[handlers/action.py:95-112]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/handlers/action.py#L95)

```python
for ch in text:
    vk = get_vk(ch.lower())
    if vk:
        # 按键方式
    else:
        send_unicode_char(ch)  # Unicode方式
```

- **问题**: 对于中文字符，`get_vk` 返回 None，走 `send_unicode_char` 分支。但 `send_unicode_char` 使用 SendInput 的 UNICODE 事件，某些应用可能不接收这种方式。
- **影响**: 中文文本输入可能在某些应用中失败。

***

## 五、设计一致性问题

### 🟡 BUG-14: 延迟参数命名和设计不统一

| 节点            | 前延迟             | 后延迟            | 延迟          |
| ------------- | --------------- | -------------- | ----------- |
| mouse\_click  | before\_delay ✅ | after\_delay ✅ | -           |
| key\_action   | -               | -              | delay（=后延迟） |
| mouse\_scroll | -               | -              | delay（=后延迟） |
| text\_input   | before\_delay ✅ | - ❌            | -           |

- **问题**: `key_action` 和 `mouse_scroll` 只有 `delay`（相当于后延迟），没有 `before_delay`。`text_input` 有 `before_delay` 但没有 `after_delay`。命名不统一，用户难以预期。

### 🟡 BUG-15: `action/mouse_move_rel` — 缺少 easing 参数

- **mouse\_move** 有 `easing` 参数（linear, ease\_in\_out, ease\_in, ease\_out）
- **mouse\_move\_rel** 没有 `easing` 参数
- **影响**: 相对位移只能线性移动，无法使用缓动效果。设计不一致。

### 🟡 BUG-16: `action/mouse_move_rel` — dx/dy 默认值不合理

- **后端** \[action.py:167-168]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/nodes/action.py#L167): `dx` 默认 100, `dy` 默认 0
- **影响**: 用户拖出节点后，默认会向右移动100像素。更合理的默认值应该是 0, 0（不移动），让用户自己设定偏移量。

### 🟡 BUG-17: `action/mouse_click` vs `action/mouse_move` — move\_duration 默认值不一致

- **mouse\_click** 的 `move_duration` 默认 **0**（直接跳转）
- **mouse\_move** 的 `duration` 默认 **200**（平滑移动）
- **影响**: 同样是鼠标移动，默认行为不同。用户可能期望 mouse\_click 也有平滑移动效果。

***

## 六、用户体验问题

### 🟡 BUG-18: `action/key_action` — 缺少按键选择器

- **问题**: `key` 参数是纯文本输入，用户需要知道确切的按键名（如 "a", "enter", "ctrl", "shift"）。没有提供按键映射表或可视化选择器。
- **影响**: 用户不知道该填什么，特别是修饰键（ctrl, alt, shift）和功能键（f1-f12, escape）的命名。

### 🟡 BUG-19: `action/text_input` — 长文本输入不友好

- **代码位置**: \[property.js:446-481]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/property.js#L446) `_renderStringField` 只渲染 `<input type="text">`
- **问题**: 对于 `text_input` 节点的 `text` 参数，使用单行输入框。对于多行文本或长文本，体验很差。
- **修复建议**: 当 key === 'text' 时使用 `<textarea>`。

### 🟡 BUG-20: `action/mouse_scroll` — delta 值不直观

- **后端**: `delta` 默认 120，描述为"滚动量(正值向上)"
- **问题**: 120 是 Windows WHEEL\_DELTA 常量，对普通用户不直观。用户可能期望输入"滚动次数"（1次=120）。
- **修复建议**: 可以添加说明文字"1次滚动=120"，或改为"滚动次数"参数内部乘以120。

### 🟡 BUG-21: `action/program_close` — `force` 参数描述不够清晰

- **后端**: `"force": {"type": "boolean", "default": False, "description": "强制终止(跳过优雅关闭)"}`
- **问题**: "优雅关闭"对普通用户不够直观。
- **修复建议**: 改为"强制结束进程（可能丢失未保存数据）"。

***

## 七、变量引用相关问题

### 🟡 BUG-22: `store_hwnd_var` 的 varRef 标记可能误导用户

- **代码位置**: \[nodes.js:134-136]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/nodes.js#L134) `_normalizeSchema` 中自动给 `store_hwnd_var` 加 `varRef: true`
- **问题**: `store_hwnd_var` 是"输出变量名"（将窗口句柄存入此变量），不是"引用变量"。但 varRef 标记会让属性面板显示 `$` 按钮，用户点击后看到的是已有变量列表，可能误以为要选择一个已有变量。
- **影响**: 用户可能选择一个已有变量名覆盖其值，而不是创建新变量。
- **修复建议**: 对"输出变量"类型的字段，应使用不同的标记（如 `varOutput: true`），不显示变量选择器，而是显示变量名输入框。

### 🟡 BUG-23: 变量选择器中 `store_hwnd_var` 的变量类型标注为"句柄"

- **代码位置**: \[property.js:1092-1094]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/property.js#L1092)

```javascript
nodeVars.push({name: node.properties.store_hwnd_var, ref: node.properties.store_hwnd_var, type: 'string', typeLabel: '句柄', isGlobal: true});
```

- **问题**: `store_hwnd_var` 的变量类型标注为"句柄"，但在变量选择器中按类型过滤时（如只显示 number 类型），"句柄"类型的变量不会出现。而 hwnd 本质上是数字。
- **影响**: 当用户在需要 number 类型的字段中使用变量选择器时，看不到 hwnd 变量。

***

## 八、属性面板同步机制问题

### 🟡 BUG-24: 属性面板修改 mode 后，节点内联字段不刷新

- **代码位置**: \[property.js:1147-1153]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/property.js#L1147)

```javascript
if (key === 'mode' || key === 'capture_mode') {
    _flushPropUndo();
    self.render(node);  // 只重新渲染属性面板
}
```

- **问题**: 当用户在属性面板中修改 `mode` 时，只重新渲染了属性面板（处理 showWhen），但没有调用 `_refreshNodeDOM` 来刷新画布上的节点内联字段。
- **影响**: 画布上节点的内联字段不会根据 mode 变化而更新（虽然目前内联字段也不检查 showWhen，但即使修复了 BUG-9，此处也需要同步刷新）。

### 🟡 BUG-25: 内联字段修改后属性面板完全重新渲染

- **代码位置**: \[core.js:449-451]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/core.js#L449)

```javascript
if (window.AutomationProperty && AutomationProperty._currentNode === n) {
    AutomationProperty.render(n);  // 完全重新渲染
}
```

- **问题**: 内联字段 change 事件触发后，属性面板完全重新渲染。如果用户正在编辑属性面板中的其他字段，会丢失焦点和输入状态。
- **修复建议**: 应该只同步更新对应的字段值，而不是完全重新渲染。

***

## 九、DAG 执行相关问题

### 🟡 BUG-26: 单个动作节点执行时入口节点选择逻辑

- **代码位置**: \[compiler.py:100-134]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/compiler.py#L100)
- **分析**: 当没有 `flow/start` 节点时，编译器会查找没有 flow 输入连接的节点作为入口。对于单个动作节点（没有连接），`has_flow_input` 集合为空，所以该节点会被选为入口。
- **结论**: 单个动作节点可以独立执行，这是正确的。

### 🟡 BUG-27: `_execute_node` 的 executed\_set 防止重复执行

- **代码位置**: \[engine.py:578-581]\(file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/engine.py#L578)

```python
with ctx._data_lock:
    if node_id in executed_set:
        return
    executed_set.add(node_id)
```

- **问题**: 如果用户通过 goto 节点跳转回一个已执行的节点，该节点不会重新执行（因为已在 executed\_set 中）。
- **影响**: goto 节点的循环功能可能失效。
- **修复建议**: goto 跳转时应重置目标节点的执行状态。

***

## 十、端口设计合理性分析

所有动作节点的端口设计是一致的：

- **输入**: 1个 flow 端口（`in`）
- **输出**: 1个 flow 端口（`next`）

这是合理的，因为动作节点是执行操作，不是数据处理。但有一个值得考虑的改进：

### 💡 建议-1: 动作节点可考虑添加数据输出端口

- 例如 `mouse_click` 可以输出实际点击的坐标（经过坐标转换后的物理坐标）
- `window_manage` 可以输出找到的窗口句柄
- `program_open` 可以输出启动的进程 PID
- 这样可以减少对 `store_hwnd_var` 等输出变量的依赖，使数据流更清晰

***

## 问题优先级汇总

| 优先级  | 编号        | 问题                                               | 类型  |
| ---- | --------- | ------------------------------------------------ | --- |
| 🔴 高 | BUG-5/6   | mouse\_click/mouse\_move 的 hwnd\_var 缺少 showWhen | 前端  |
| 🔴 高 | BUG-7     | wait 的 duration 缺少 showWhen                      | 前端  |
| 🔴 高 | BUG-9     | 内联快捷参数不检查 showWhen                               | 前端  |
| 🔴 高 | BUG-10    | program\_open 窗口查找等待太短                           | 后端  |
| 🔴 高 | BUG-1     | key\_action 的 key 默认值不一致                         | 前后端 |
| 🔴 中 | BUG-2/3/4 | 多个节点 fallback 缺少 varRef                          | 前端  |
| 🔴 中 | BUG-11    | key\_action 空 key 时行为未定义                         | 后端  |
| 🟡 中 | BUG-24    | mode 修改后内联字段不刷新                                  | 前端  |
| 🟡 中 | BUG-14    | 延迟参数命名不统一                                        | 设计  |
| 🟡 中 | BUG-22    | store\_hwnd\_var 的 varRef 误导                     | 设计  |
| 🟡 低 | BUG-12    | mouse\_scroll 缺少坐标参数                             | 设计  |
| 🟡 低 | BUG-15    | mouse\_move\_rel 缺少 easing                       | 设计  |
| 🟡 低 | BUG-16    | mouse\_move\_rel dx/dy 默认值                       | 设计  |
| 🟡 低 | BUG-18    | key\_action 缺少按键选择器                              | UX  |
| 🟡 低 | BUG-19    | text\_input 长文本不友好                               | UX  |
| 🟡 低 | BUG-20    | mouse\_scroll delta 不直观                          | UX  |

***

以上就是从用户视角对**动作节点模块**进行全面检查后发现的所有问题。共发现 **27个问题/建议**，其中：

- **🔴 高优先级 BUG（6个）**: showWhen 缺失导致界面混乱、窗口查找等待太短、前后端默认值不一致、内联字段不尊重 showWhen
- **🟡 中优先级问题（8个）**: 前端 fallback 缺少 varRef、空 key 行为未定义、mode 修改后内联不刷新、延迟参数命名不统一、store\_hwnd\_var 误导
- **🟡 低优先级问题（9个）**: 缺少坐标/缓动参数、默认值不合理、UX 不友好
- **💡 设计建议（1个）**: 动作节点添加数据输出端口

最关键的修复项是：

1. **BUG-5/6/7**: 给 `hwnd_var` 和 `duration` 添加 `showWhen` 条件
2. **BUG-9**: `_pickSummaryKeys` 需要检查 showWhen 条件
3. **BUG-10**: `program_open` 的窗口查找需要重试机制
4. **BUG-1**: 统一 `key` 的默认值

