# WebUI 参数与 UI 一致性核查报告

> 核查范围：用户能否真正改到全部设计参数、Automation Editor 如何开关 Standby 引擎、
> 以及"已实现但用户看不到"的功能是否上线。
> 核查方式：静态遍历 + 运行时枚举真实 API/数据 + 回归测试 + 实际启动。
> 日期：2026-10-05 / 版本：v3.3.0

---

## 一、共享帧缓存：机制与对实时检测的影响

### 1.1 它如何运作

`automation/detection/capture_manager.py` 中的共享帧缓存，**不是**"定期刷新一次的帧队列"，
而是一个**按区域键（region）+ 帧世代（epoch）+ TTL 三重约束**的复用点：

| 约束 | 取值 | 作用 |
| --- | --- | --- |
| 区域键 | `(x, y, w, h)` 或 `__full__` | 只有**同一块区域**才可能命中，不同区域各截各的 |
| 帧世代 epoch | 由引擎在**每次循环迭代开始**（`_reset_body_nodes`）自增 | 新的循环迭代 = 新世代，缓存全部作废 |
| TTL 上限 | 档位下发 2 / 4 / 8 ms（兜底 `_FRAME_CACHE_HARD_TTL_MS = 4ms`） | 即使没有循环节点（epoch 不增），也最多陈旧 4ms |

命中条件三者**同时**满足：区域相同 + 世代相同 + 未超 TTL。

**意图**：一次循环迭代里如果有 N 个检测节点（例如"先看血条、再看技能 CD、再看敌人存在性"），
它们看到的是**同一瞬间**的画面，因此可以复用**一次**截图，省掉 N-1 次全屏 BitBlt（每次约 13.7ms）。

### 1.2 会不会让"阻塞重复检测"看到旧画面？—— 曾会，已修复

你担心的正是关键点。一个开了 `wait=true`（持续等待）的检测节点，其**内部 while 轮询**
在逻辑上是**不同瞬间**——它必须看到战斗画面的实时变化。而这条轮询循环**不会**触发 epoch 自增
（它不是循环节点）。当 `wait_interval_ms` 小于 TTL 时（例如间隔 1~2ms，或档位为"低占用"8ms），
缓存会连续命中同一帧，让"实时检测"退化成"盯着旧画面"，从而**漏掉血条骤降、技能 CD 归零等瞬时跃迁**。

**修复**：在 `automation/handlers/detection.py` 新增 `_invalidate_frame(ctx)`，
并在以下**全部 5 处轮询循环**的每一轮开头调用；`automation/handlers/monitor.py` 的监视器 poll 循环同样接入：

- `check_color`（持续等待）
- `check_ocr`（持续等待）
- `check_image`（持续等待）
- `check_screen`（持续等待）
- `check_digits`（持续等待）
- `monitor_color` / `monitor_ocr` / `monitor_timer` 的后台轮询

**语义边界因此变得清晰**：

- ✅ **同一次遍历里**的多个检测节点 → 复用一次截图（安全，同一瞬间，省 CPU）
- ✅ **轮询/监视**的连续检测 → 每次都抓新帧（实时，不牺牲正确性）

### 1.3 实测数据（新增回归用例 `test_polling_detection_never_sees_stale_frame`）

刻意把 TTL 放大到 50ms 以复现最坏情况，8 轮轮询（间隔 5ms）：

| 场景 | 看到旧帧次数 |
| --- | --- |
| 轮询内不作废（修复前行为） | **7 / 8** |
| 每轮作废（修复后行为） | **0 / 8** |

同一用例同时验证了"同轮多节点复用"仍然成立：5 次同区域截图 = 1 次真实截图 + 4 次缓存命中。

> **结论**：共享帧缓存不会损害快速变化场景的检测——前提是轮询循环显式作废缓存（现已默认如此）。
> 若你的流程里存在"节点动作 → 立刻再检测同一区域"的组合，动作耗时会自然超过 4ms TTL，因此也会重新抓帧。

---

## 二、参数系统：用户能否改到全部参数

### 2.1 结构（已核实）

| 层 | 真源 | UI 渲染方式 |
| --- | --- | --- |
| 全局参数（128 项） | `bridge/metadata.py::PARAM_SCHEMA` | `get_global_params().sections[].rows` **动态渲染** |
| 节点参数（内置 60 类 / 361 项，另加插件节点） | `automation/nodes/*.py` | `get_node_definitions()` **动态渲染**属性面板 |

**结论**：两处都是**数据驱动**——后端新增参数会自动出现在 UI，无需改前端。本次新增的
`PRECISION_PROFILE` / `PROCESS_PRIORITY_TIER` / `DETECTION_FRAME_CACHE_TTL_MS` 已确认自动上线。


### 2.2 本轮发现并修复的问题

| # | 问题 | 影响 | 修复 |
| --- | --- | --- | --- |
| 1 | 参数页**枚举下拉显示裸英文**（`latency_first` / `cpu_saver` …） | 用户看不懂档位含义 | `metadata.py` 补全 7 个枚举的 `display_names`；行数据下发；前端显示「延迟优先(最低延迟/占用高) (latency_first)」 |
| 2 | **「快捷键速查」硬编码** F8/ESC/F6/F7/F11 | 与实际配置（编辑器 运行=**F1**、停止=**F8**、全屏=**F10**）**不符**，且无视冲突 | 改为读取 `get_hotkey_conflicts().flat` 按真实配置渲染，冲突项标红 |
| 3 | 后端 `get_hotkey_conflicts()` **无 UI 入口** | 检测能力"存在但用户看不到" | 全局参数页新增「热键冲突检测」按钮 + 结果面板 |
| 4 | 引擎关键状态**无处可见** | 用户改了档位/Standby 开关却看不到联动结果；Standby 的 native 扩展缺失时会静默回退 Python 路径 | 新增 `get_engine_summary()` + 顶栏「精度档位」「Standby 引擎」常显（异常态高亮告警） |
| 5 | 前端兜底节点定义 `cache_strategy` 默认 `time_interval` | 与后端 `disabled` 不一致（静态预览/API 异常时注入陈旧缓存） | 3 处对齐为 `disabled` |
| 6 | 监视器/OCR 缓存默认仍为 `time_interval` | 实时场景隐患 | 统一改 `disabled` |

### 2.3 已确认**无需改动**的项（核查后判定正常）

- 前端调用缺失：**0 处**。枚举 `MacroBridge` 实际暴露的 119 个可调用方法与前端全部调用点交叉比对，无一处调用不存在的方法（上一轮已修 `get_node_defs` → `get_node_definitions`）。
- 配置文件与 schema 差异：**0 个孤儿参数**（config 里不存在 schema 未定义的键）。
- 节点参数类型覆盖：后端出现的全部类型 `enum/number/string/bool/boolean/color/region/path/var_list/affinity` 均被属性面板渲染器处理；`array` 类型均带 `format=region`，会被规范化。
- DOM 引用：JS 引用的元素 id 均存在于 `index.html` 或由 `innerHTML` 动态创建。

> **提示**：`webui/modules/auto/core/nodes.js` 里内嵌了一大段硬编码节点定义（约 300 行）。
> 运行时它会被后端 `get_node_definitions()` 覆盖（`_registerFromPayload`），仅在没有 pywebview 的
> 静态预览时才生效。它属于"技术债但当前不致命"——建议后续删除或改为构建期生成，以彻底消除漂移风险。

---

## 三、Automation Editor 如何启用/关闭 Standby 引擎

Standby 引擎有**两级开关**，两者都已确认可用、可被用户操作：

### 3.1 全局开关（影响所有"调用宏"节点）

**全局参数 → 执行框架 3.2 → 「启用 Standby 工业级精度引擎」**（`ENABLE_STANDBY_ENGINE`，基础层可见）

- 关：所有宏走 Python 路径
- 开：简单线性宏走 native `standby` 扩展（DLL 级精度，单核自旋）

顶栏「Standby 引擎」会常显其**实际状态**：

| 显示 | 含义 |
| --- | --- |
| 已加载 | 开关开且 native 扩展加载成功 |
| 不可用(回退) | 开关开但 native 扩展缺失 → 会静默回退 Python 路径（**红色告警**，避免误判） |
| 已关闭 | 开关关 |

### 3.2 节点级覆盖（针对单个宏调用）

**自动化编辑器 → 双击「调用宏(同步)」/「调用宏(异步)」节点 → 属性面板 → 「Standby 引擎」下拉**

| 选项 | 行为 |
| --- | --- |
| 继承全局 | 读全局 `ENABLE_STANDBY_ENGINE` |
| 强制启用 | 该节点强制尝试 native 路径（`standby_override=on`） |
| 强制关闭 | 该节点强制走 Python 路径（`standby_override=off`） |

同节点还有 **RTSS 帧同步**覆盖（仅对含帧延迟 `f` 的宏生效）。

> 后端消费点：`automation/handlers/control.py`（`_handle_call_script_sync/_async`）与
> `automation/engine.py`，均按 `inherit/on/off` 正确分派；决策为
> `use_standby = (override=="on") or (override=="inherit" and 全局开关 and 引擎可用)`。
> 「执行子脚本」节点执行的是另一个流程子图而非宏文件，因此**不含**该参数（符合设计）。

---

## 四、核查方法与可复用结论

1. **枚举真实 API**：实例化 `MacroBridge`，遍历 `dir(type(bridge))` 收集可调用方法 → 与前端
   `apiCall('x')` / `pywebview.api.x` 交叉比对。比正则扫描源码可靠（能正确处理 mixin 与多行签名）。
2. **参数真源判定**：前端参数页与节点属性面板均**动态渲染**，故"后端有 = UI 有"，
   唯一要查的是**枚举可读性**与**是否有后端能力无 UI 入口**。
3. **前端硬编码文本是重灾区**：本次发现的"错误快捷键速查"正属于此类。
   凡 UI 里的静态文案若与配置相关，都应改为从 API 读取。
4. **验证顺序**：`compileall` → `node --check` → 回归测试 → 实际启动 `webui_app.py` 看日志。

---

## 五、附带发现（未改动，供决策）

- `get_runtime_status()` 返回**逐宏运行明细表**（macro_id / 触发键 / 存活 / 暂停），
  但前端只用了聚合的 `get_dashboard_snapshot()`。可考虑加一个"运行中宏"面板展示明细。
- `get_record_state()` 相关与 `get_recording_state()` 存在功能重叠，`pick_region` 等为历史遗留未用接口。
- 上一轮提出的两个取舍项（`RTSS_FRAME_TIMEOUT_S=0.05`、`NODE_RETRY_COUNT=3`）经确认**按现状保留**。
