以下是综合两轮分析后，整理出的正式 Bug 汇报，按优先级和模块分类。

***

# 自动化引擎 Bug 汇报

## 一、编译器（compiler.py）

### Bug 1.1：入口选择逻辑错误——纯数据节点可被误选为主入口

**优先级：高**

**现象：**\
`parse_graph` 将“没有任何 flow 输入连接”的节点全部列为入口候选。`utility/const_number`、`utility/math_op` 等纯数据节点（无 flow 输出端口）可能被选为 `entry_node_id`，导致引擎单独执行一次无意义节点后立即终止。

**根因：**

```python
entry_candidates = [nid for nid in graph.nodes if nid not in has_flow_input]
```

未过滤节点是否具备 flow 输出能力。

**修复建议：**\
入口候选需同时满足：

1. 无 flow 输入连接；
2. 节点定义中包含 flow 输出端口，或属于可主动触发类型（action/control/detection/preset/script\_block/monitor）。

***

### Bug 1.2：入口选择逻辑错误——有 flow 输入端口的未连接节点被当作入口

**优先级：高**

**现象：**\
`control/if_else` 等节点声明了 flow 输入端口 `in`，若用户断开其 flow 连接、仅保留 data 连接，该节点会被当成入口执行。此时条件数据来源尚未就绪，导致分支走向不可预期。

**根因：**\
仅按“是否有 flow 输入连接”判断，未按“节点类型是否声明了 flow 输入端口”判断。

**修复建议：**\
只要节点类型在注册表中声明了 `type="flow"` 的输入端口，无论是否实际连接，均不得纳入入口候选。

***

### Bug 1.3：`monitor_entry_ids` 收集不完全

**优先级：中**

**现象：**\
`monitor_entry_ids` 依赖“无 flow 输入连接”这一假设筛选。若未来监视器节点定义增加了 flow 输入端口，被连接后将无法被收集为监视器入口。

**根因：**

```python
graph.monitor_entry_ids = monitor_nodes  # 基于 entry_candidates 子集
```

**修复建议：**\
直接按节点类型前缀筛选：

```python
graph.monitor_entry_ids = [nid for nid, node in graph.nodes.items() 
                           if node.type.startswith("monitor/")]
```

***

### Bug 1.4：入口选择优先级误导

**优先级：中**

**现象：**\
当前优先级 `action > 其他 > monitor` 中，“其他”类别包含 `utility/delay` 等节点，可能导致无意义节点作为主入口，而监视器仅在后台运行。

**修复建议：**\
明确优先级：`action/script_block > control > detection/preset > monitor`，`utility` 节点不得作为主入口候选。

***

## 二、数据流运行时（engine / handlers）

### Bug 2.1：数据连接通道断裂——utility 节点输出无法被流程节点读取

**优先级：高**

**现象：**\
`utility/const_number` 将输出写入 `ctx.variables[node.id + "_out"]`，而 `control/if_else` 等节点从 `ctx.check_results[f"{src.node_id}.{src.port_name}"]` 读取。两者通道不统一，导致前端拖拽的 data 连线在运行时完全失效。

**根因：**\
双轨制输出：有 flow 端口的节点写 `check_results`，纯数据节点写 `variables`，键名格式也不同。

**修复建议：**\
统一为单轨制。所有节点的 data 输出由引擎按 `{node_id}.{port_name}` 自动映射到统一上下文，handler 只负责计算结果，不负责键名拼接。

***

### Bug 2.2：`wait_cond` / `seq_check` / `state_machine` 条件键名错误

**优先级：致命**

**现象：**\
三个节点均读取 `ctx.check_results[f"{node.id}.cond"]`，但没有任何节点会写入该键。数据连接的源节点写入的是 `{node_id}.result`。

- `wait_cond`：永远等不到条件，超时后走 timeout 分支；
- `seq_check`：永远判定失败，重试到上限后走 fail 分支；
- `state_machine`：`cond` 为 `None`，进入 `else` 分支忙等待死循环。

**根因：**\
硬编码键名 `self.cond` 与数据连接实际键名 `{source_node_id}.{source_port}` 不匹配。

**修复建议：**\
参照 `_handle_if_else` 的实现，从 `node.get_data_inputs("cond")` 解析源节点和端口，动态拼接键名读取。

***

### Bug 2.3：`loop_while` 条件更新语义隐晦

**优先级：中**

**现象：**\
循环条件依赖 `ctx.check_results` 快照。若循环体内不包含源检测节点，条件值永不变，导致无限循环或立即退出。

**根因：**\
数据流语义与命令式循环语义不匹配——“重新求值”需要“重新执行源节点”，但源节点可能不在循环体内。

**修复建议：**

- 短期：编译期检查，若 `loop_while` 的 cond data 输入来自循环体外部节点，发出警告；
- 长期：引入数据流惰性求值，循环条件强制重新执行上游数据依赖链。

***

## 三、节点设计（nodes registry）

### Bug 3.1：功能重叠节点未合并

**优先级：中**

**现象：**\
同一概念存在两套节点定义，增加维护负担和用户困惑：

| 功能    | utility 节点（无 flow）  | variable 节点（有 flow）    |
| :---- | :------------------ | :--------------------- |
| 数学运算  | `utility/math_op`   | `variable/var_math`    |
| 比较    | `utility/compare`   | `variable/var_compare` |
| 字符串操作 | `utility/string_op` | `variable/var_string`  |

**修复建议：**\
废弃 `variable/*` 系列，统一为带 flow 端口的 `utility/*` 版本（适配当前 flow 驱动执行模型）。合并后通过 data 连接支持纯数据用法。

***

## 四、并发与线程安全（monitor / TaskPool）

### Bug 4.1：监视器与主流程共享 `ExecContext` 无同步

**优先级：高**

**现象：**\
监视器线程的 `_monitor_check_color`、`_monitor_check_ocr` 直接写入 `ctx.variables`、`ctx.last_capture_cache`，与主流程或其他监视器存在竞态。

**根因：**\
`ExecContext` 的可变字段无任何锁保护。

**修复建议：**\
为 `variables`、`check_results`、`last_capture_cache` 引入 `threading.RLock()`。或采用节点级隔离策略（每个节点独立缓存，合并时加锁）。

***

### Bug 4.2：TaskPool 存在 check-then-act 竞态

**优先级：中**

**现象：**\
`pause()`、`resume()` 等方法先获取 task 引用、释放锁后再操作 `pause_event`，期间 task 可能被其他线程删除。

**根因：**

```python
with self._lock:
    task = self.tasks.get(task_id)
# 锁已释放
task.pause_event.set()  # task 可能已失效
```

**修复建议：**\
将对 task 对象的所有状态操作封装在锁内，或确保 `Event` 对象引用在线程间安全。

***

### Bug 4.3：监视器内 OCR 引擎重复创建

**优先级：高**

**现象：**\
`detection.py` 的 `_handle_check_ocr` 复用 `ctx._ocr_engine`，但 `monitor.py` 的 `_monitor_check_ocr` 每次直接 `engine = OCREngine()`，导致多个监视器各自加载模型，严重浪费内存和时间。

**修复建议：**\
`_monitor_check_ocr` 改为复用上下文引擎：

```python
engine = ctx._ocr_engine
if engine is None:
    engine = OCREngine()
    ctx._ocr_engine = engine
```

***

## 五、控制流（goto）

### Bug 5.1：goto 在监视器线程中行为未定义

**优先级：中**

**现象：**\
若监视器触发的分支中包含 goto 节点，`_goto_target` 会被监视器线程的 `_execute_node` 循环处理，可能导致执行流跳转至主流程节点，造成混乱。

**修复建议：**\
编译期禁止监视器节点的输出流中包含 goto 节点，或运行时检测到后抛出明确错误。

***

### Bug 5.2：goto 缺乏编译期校验

**优先级：中**

**现象：**\
`target_node_id` 由用户填写，编译器和运行时均不校验目标节点是否存在。若目标不存在，运行时静默失败。

**修复建议：**\
`parse_graph` 阶段校验所有 goto 节点的 `target_node_id` 是否存在于 `graph.nodes` 中，不存在则编译失败并提示。

***

## 六、错误处理

### Bug 6.1：系统级错误被静默吞掉

**优先级：中**

**现象：**\
几乎所有 handler 的异常处理模式为 `print` + 走失败分支。图像模板不存在、宏文件不存在、OCR 引擎未安装等系统错误无法被前端捕获，用户难以调试。

**修复建议：**\
区分两类失败：

- **业务级失败**（匹配未找到、颜色不匹配）：走正常分支，无需上报；
- **系统级错误**（文件不存在、ImportError、类型转换失败）：写入结构化错误日志（如 `ctx.errors.append(...)`），提供接口供前端查询。

***

## 修复优先级汇总

| 优先级    | Bug 编号 | 描述                                              |
| :----- | :----- | :---------------------------------------------- |
| **致命** | 2.2    | wait\_cond / seq\_check / state\_machine 条件键名错误 |
| **高**  | 1.1    | 纯数据节点误选为主入口                                     |
| **高**  | 1.2    | 有 flow 输入端口的节点被当作入口                             |
| **高**  | 2.1    | utility 与流程节点数据通道断裂                             |
| **高**  | 4.1    | 监视器与主流程共享 ctx 无同步                               |
| **高**  | 4.3    | 监视器内 OCR 引擎重复创建                                 |
| **中**  | 1.3    | monitor\_entry\_ids 收集不完全                       |
| **中**  | 1.4    | 入口选择优先级误导                                       |
| **中**  | 2.3    | loop\_while 条件更新语义隐晦                            |
| **中**  | 3.1    | 功能重叠节点未合并                                       |
| **中**  | 4.2    | TaskPool check-then-act 竞态                      |
| **中**  | 5.1    | goto 在监视器中行为未定义                                 |
| **中**  | 5.2    | goto 缺乏编译期校验                                    |
| **中**  | 6.1    | 系统级错误被静默吞掉                                      |

