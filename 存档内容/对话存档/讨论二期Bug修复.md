# 讨论二期Bug修复

> **Workspace:** c:\Users\肖鸣\Downloads\宏驱动 webui 2.7.7 - 副本

***

## User

目前项目已经修复了 `c:\Users\肖鸣\Downloads\宏驱动 webui 2.7.7 - 副本\问题\Bug审查意见书.md` 中提到的，已经采纳个各种类型bug。
现在进入了2期，需要将剩余bug提上日程。请理解我们的项目架构，了解它可能服务的对象。和我讨论剩余各bug的取舍和可能的冲突。
我们最终要生成bug修复意见书2期。先和我讨论

## Assistant

## 简要总结

1. **用户要我做什么**：项目已完成1期采纳的bug修复，现在进入2期，需要讨论剩余的"后期考虑"（41个）和"拒绝"（10个）bug的取舍和冲突，最终生成2期bug修复意见书。
2. **计划步骤**：
   - 先完整阅读Bug审查意见书，了解所有⏳和❌条目
   - 探索项目架构，理解项目定位和服务对象
   - 与用户逐类讨论各bug的取舍
3. **缺少的信息**：完整的审查意见书后半部分（⏳和❌的详细内容）、项目架构细节

让我先获取完整信息：

现在，让我来了解一下项目架构，以便更好地理解其服务对象和设计理念：

现在我已经完整阅读了审查意见书和项目架构。让我整理一下2期需要讨论的全部内容，然后我们逐类讨论。

***

## 📋 2期 Bug 盘点总览

经过1期修复，剩余条目如下：

| 分类     | 数量                                      | 说明                        |
| ------ | --------------------------------------- | ------------------------- |
| ⏳ 后期考虑 | 41个 (D-01 \~ D-57)                      | UX优化、功能增强、varRef全局设计、画布交互 |
| ❌ 拒绝   | 8个 (R-01\~R-03, R-06, R-08\~R-10, R-12) | 设计取舍、架构选择                 |

> 注：R-04/R-05/R-07/R-11/D-26 在设计文档中已被升级为采纳，D-55 已升级为拒绝。

***

## 🔍 项目定位与用户画像分析

基于我对项目的理解：

- **MacroDriver WebUI** 是一款面向 **游戏玩家/自动化爱好者** 的本地宏驱动工具
- 核心场景：**游戏内自动化**（检测怪物→攻击、血条监视→吃药、BOSS动作识别→闪避）
- 用户技术水平：**中等偏低**——需要可视化节点编辑器，而非手写代码
- 关键需求：**可靠性**（不能崩溃）、**直观性**（节点含义一目了然）、**灵活性**（支持复杂逻辑）

基于这个定位，我来逐类分析2期bug的取舍。

***

## 一、⏳ 2.1 UX/描述优化（D-01 \~ D-11）— 11项

| 编号   | 问题                                  | 我的建议     | 理由                                                |
| ---- | ----------------------------------- | -------- | ------------------------------------------------- |
| D-01 | `mouse_click` hold\_time 缺 showWhen | **2期采纳** | long\_press模式下hold\_time才有意义，不隐藏会困惑新手             |
| D-02 | 延迟参数命名不统一                           | **2期采纳** | before\_delay/after\_delay/delay 混用，对中低水平用户造成理解负担 |
| D-03 | key\_action 缺少按键选择器                 | **2期采纳** | 用户需要查文档才知道按键名，体验差。这是高频操作节点                        |
| D-04 | text\_input 长文本用单行输入框               | **2期采纳** | 改动极小（input→textarea），收益明显                         |
| D-05 | mouse\_scroll delta 120 不直观         | **保持后期** | 120是Windows标准，加个tooltip说明即可                       |
| D-06 | program\_close force 描述不清晰          | **2期采纳** | 改描述文字，零风险                                         |
| D-07 | check\_screen threshold 描述不完整       | **2期采纳** | 不同模式含义不同，用户会误设参数                                  |
| D-08 | math\_func sin/cos 弧度无说明            | **2期采纳** | 用户默认角度制，弧度会导致计算错误                                 |
| D-09 | if\_else fallback 显示英文 true/false   | **2期采纳** | 中文用户界面显示英文，不一致                                    |
| D-10 | var\_string substr 参数格式不直观          | **保持后期** | 功能可用，只是格式说明问题                                     |
| D-11 | var\_compare 字符串比较回退不直观             | **保持后期** | 数值优先比较是合理设计                                       |

**讨论点**：D-02（延迟参数命名统一）改动面较大，涉及多个节点定义的参数重命名，可能破坏已保存脚本的兼容性。你倾向哪种方案？

- **方案A**：只改前端显示名（display\_name），保留内部参数名
- **方案B**：统一重命名，加兼容层映射旧名

***

## 二、⏳ 2.2 功能增强（D-12 \~ D-29）— 18项

这是最需要讨论的部分，我按优先级重新分组：

### 🔴 建议升级为2期采纳（6项）

| 编号   | 问题                                      | 理由                             |
| ---- | --------------------------------------- | ------------------------------ |
| D-17 | check\_ocr match\_number 缺 varRef       | 与1期A-10同类问题，监视器修了但检测节点没修，不一致   |
| D-18 | check\_ocr cache\_interval\_ms 缺 varRef | 同上                             |
| D-19 | check\_image template\_path 缺 varRef    | 游戏场景中模板路径可能来自配置变量，需求不低         |
| D-14 | var\_math abs/round 一元运算有二元输入           | B端口被忽略但显示着，用户会困惑"为什么设了B没效果"    |
| D-15 | logic\_op not 一元运算有二元输入                 | 同D-14                          |
| D-13 | var\_string split 只返回第一部分               | 功能缺陷——split只返回第一部分不是正常的split行为 |

### 🟡 建议保持后期考虑（8项）

| 编号   | 问题                                                 | 理由                                  |
| ---- | -------------------------------------------------- | ----------------------------------- |
| D-12 | mouse\_scroll 缺坐标定位                                | 可先移动再滚动，workaround存在                |
| D-16 | string\_op concat 只拼两个                             | 链式可用，设计简化                           |
| D-20 | check\_image pyramid\_levels 缺 varRef              | \_normalizeSchema已处理                |
| D-21 | check\_color check\_mode 对 sample\_mode 缺 showWhen | 不影响功能                               |
| D-22 | check\_screen region 缺 showWhen                    | 全屏默认值即可                             |
| D-23 | check\_image confidence 输出未声明                      | 可通过变量引用获取                           |
| D-24 | preset\_find\_click template\_path 缺 varRef        | 与D-19同类但预设节点定位是简化版                  |
| D-25 | preset\_find\_click 没移动动画                          | 防作弊是特殊场景                            |
| D-26 | stop\_branch target\_branch 不友好                    | **已在设计文档中升级为采纳**                    |
| D-27 | join target\_fork\_node\_id 不完善                    | 基本功能可用                              |
| D-28 | call\_script path 缺 varRef                         | 脚本路径通常固定                            |
| D-29 | text\_input 中文输入不稳定                                | SendInput Unicode是标准方式，个别应用不兼容是已知限制 |

### ⚠️ 关键讨论点

**D-13（split只返回第一部分）**：这不是"简化"，而是**语义错误**。用户期望 `split("a,b,c", ",")` 返回数组或至少返回 `"b,c"`，但当前只返回 `"a"`。这应该算bug而非功能增强。你怎么看？

**D-17/D-18/D-19（检测节点varRef缺失）**：1期修复了监视器和utility节点的varRef问题，但检测节点（check\_ocr/check\_image）的varRef缺失没修。这造成了**不一致**——用户在监视器中能用变量，在检测节点中不能。建议统一修复。

***

## 三、⏳ 2.3 varRef/varOutput 全局设计（D-30 \~ D-34）— 5项

| 编号   | 问题                                             | 我的建议     |
| ---- | ---------------------------------------------- | -------- |
| D-30 | store\_hwnd\_var varRef误导                      | **2期采纳** |
| D-31 | 变量选择器 store\_hwnd\_var 类型标注                    | 与D-30一起修 |
| D-32 | monitor\_ocr store\_var/store\_number 标记varRef | 与D-30一起修 |
| D-33 | loop\_count counter\_var 标记varRef              | 与D-30一起修 |
| D-34 | 所有store\_var 输出标记varRef误导                      | 与D-30一起修 |

**这是一个整体方案**，5项必须一起做。核心问题是：

当前 `store_var`、`counter_var`、`store_hwnd_var` 等是**输出变量名**，但前端把它们标记为 `varRef: True`，导致：

1. 用户以为这些字段是"引用一个已有变量"，实际是"定义一个新变量名"
2. 变量选择器显示这些字段，用户选了一个变量后，该变量会被覆盖

**方案**：引入 `varOutput: True` 标记，前端对 varOutput 字段显示"变量名输入框"而非"变量选择器"。

**冲突点**：这个改动影响面大——所有有 `store_var` 的节点都需要改。但审查意见书建议在 v2.8 统一规划。你觉得2期做还是推到3期？

***

## 四、⏳ 2.4 画布/编辑器交互优化（D-35 \~ D-44）— 10项

| 编号   | 问题                                                | 我的建议     | 理由                         |
| ---- | ------------------------------------------------- | -------- | -------------------------- |
| D-35 | 内联字段修改后属性面板完全重渲染                                  | **2期采纳** | 性能问题，频繁操作时卡顿               |
| D-36 | 粘贴不保留 \_customName                                | **2期采纳** | 用户重命名后粘贴丢失名称，困惑            |
| D-37 | Ctrl+D 只支持单节点                                     | 保持后期     | Ctrl+C/V已支持多选              |
| D-38 | Delete后变量面板不更新                                    | **2期采纳** | 删除节点后变量残留，误导               |
| D-39 | 撤销后属性面板不刷新                                        | **2期采纳** | 与A-48相关但A-48只修了核心，面板刷新仍需处理 |
| D-40 | 拖拽节点位置不可撤销                                        | 保持后期     | 需改undo系统，改动大               |
| D-41 | 执行完成后不清除节点高亮                                      | **2期采纳** | 改动极小，体验提升明显                |
| D-42 | 模拟执行不按流程顺序                                        | 保持后期     | 调试功能，不影响实际执行               |
| D-43 | 不保存画布视口位置和缩放                                      | **2期采纳** | 每次打开脚本都要重新定位，烦人            |
| D-44 | mouse\_click vs mouse\_move move\_duration 默认值不一致 | 保持后期     | 各有道理                       |

***

## 五、⏳ 2.5 其他后期考虑项（D-45 \~ D-57）— 13项

| 编号   | 问题                          | 我的建议       | 理由                             |
| ---- | --------------------------- | ---------- | ------------------------------ |
| D-45 | 工具箱缺plugin分类                | 保持后期       | 底部面板可用                         |
| D-46 | 工具箱搜索不支持中文/拼音               | **2期采纳**   | 中文用户搜中文节点名搜不到，体验差              |
| D-47 | 工具箱节点没tooltip               | **2期采纳**   | 新用户不知道节点用途                     |
| D-48 | 坐标拾取hwnd\_var被覆盖            | 保持后期       | 拾取工具的设计意图                      |
| D-49 | 拾取后自动修改mode                 | 保持后期       | 预期行为                           |
| D-50 | 变量操作节点result输出格式不直观         | 保持后期       | UX优化                           |
| D-51 | 变量面板点击只复制不插入                | **2期采纳**   | 减少操作步骤                         |
| D-52 | COMPLETED状态下停止按钮异常          | 保持后期       | 已完成时停止按钮意义不大                   |
| D-53 | 新建画布保存确认逻辑中断                | 保持后期       | 边界场景                           |
| D-54 | 插件串行加载速度慢                   | **2期采纳**   | 插件多时启动慢，改并行改动小                 |
| D-55 | 检测+if\_else数据端口vs变量引用歧义     | **已升级为拒绝** | 设计如此                           |
| D-56 | fork多分支截图竞争                 | 保持后期       | 帧差异毫秒级                         |
| D-57 | bookmark hwnd\_var缺showWhen | **2期采纳**   | 1期A-15实现了bookmark，此showWhen应同步 |

***

## 六、❌ 拒绝项重新审视（8项）

| 编号   | 问题                                | 1期结论 | 2期建议       | 理由                                                                    |
| ---- | --------------------------------- | ---- | ---------- | --------------------------------------------------------------------- |
| R-01 | mouse\_move\_rel 缺easing          | 拒绝   | **保持拒绝**   | 短距离缓动不可感知                                                             |
| R-02 | 入口节点选择逻辑                          | 拒绝   | **保持拒绝**   | 正确设计                                                                  |
| R-03 | 动作节点添加数据输出                        | 拒绝   | **重新讨论**   | 1期采纳了R-07(preset\_read\_text数据输出)，逻辑一致性问题——为什么preset可以有数据输出但action不行？ |
| R-06 | preset\_find\_click 没数据输出         | 拒绝   | **保持拒绝**   | 需要完整数据应用check\_image+mouse\_click组合                                   |
| R-08 | 插件无沙箱                             | 拒绝   | **保持拒绝**   | 架构选择                                                                  |
| R-09 | 插件onExecute只在模拟时调用                | 拒绝   | **保持拒绝**   | 设计选择                                                                  |
| R-10 | 重命名不允许"未命名脚本"                     | 拒绝   | **保持拒绝**   | 有意设计                                                                  |
| R-12 | loop\_while+检测/goto+循环/监视器+fork联动 | 拒绝   | **2期重新评估** | 1期修复了核心引擎问题(A-03/A-04/A-38)，联动场景可能仍有问题，应验证                            |

**关键讨论点**：

1. **R-03（动作节点数据输出）**：1期采纳了R-07，给preset\_read\_text加了数据输出。那 `mouse_click` 的 `store_hwnd_var` 是否也应该从"变量存储"改为"数据输出端口"？这涉及varOutput系统（D-30\~D-34）的设计。
2. **R-12（联动问题）**：1期修复了goto executed\_set(A-03)、check\_results重置(A-04)、条件重新执行(A-38)等核心问题。这些修复后，原来的联动bug可能已经自然解决。建议**先做回归测试**，如果联动场景正常则保持拒绝，否则重新采纳。

***

## 📊 2期建议采纳汇总

| 分类          | 数量           | 主要内容                      |
| ----------- | ------------ | ------------------------- |
| UX/描述优化     | 8项           | D-01/02/03/04/06/07/08/09 |
| 功能增强升级      | 6项           | D-13/14/15/17/18/19       |
| varOutput系统 | 5项           | D-30\~34（整体方案，可选推3期）      |
| 画布交互        | 6项           | D-35/36/38/39/41/43       |
| 其他          | 5项           | D-46/47/51/54/57          |
| 拒绝重评        | 2项           | R-03(讨论)/R-12(验证)         |
| **合计**      | **约26\~32项** | 取决于varOutput和R-03的决策      |

***

## 🤔 需要你决策的核心问题

1. **varOutput系统（D-30\~34）**：2期做还是推3期？影响面大但用户困惑严重。
2. **D-13 split行为**：是bug还是功能增强？如果算bug应2期修。
3. **D-02 延迟参数命名统一**：方案A（只改显示名）还是方案B（重命名+兼容层）？
4. **R-03 动作节点数据输出**：是否与varOutput系统一起重新设计？
5. **R-12 联动问题**：是先验证1期修复效果，还是直接纳入2期？

请告诉我你的想法，我们确定方向后就可以生成正式的2期bug修复意见书。

## User

我们的用户是有一点编程能力和理解力的深度游戏玩家，有一定的宏编辑经验。但他们对英文类的复杂参数名的理解不好，但只要能理解参数名称，一般都能看懂其作用。

不说明的编号，默认同意你的意见：
D-01 不采纳，这个就像是鼠标短单击也有的少量延迟，作为人类特征模拟。不过我想要新增功能：目前的这个节点参数填入后是先执行坐标移动，再执行点击吧？我认为要添加直接点击，不移动坐标的功能。即可以隐藏坐标参数不填写也不移动鼠标。
D-02 不采纳，虽然混用，但是在app的展示是以中文形式友好的展现的，暂时不修复
D-07 采纳，且各模式要在app上显示明确的中文意思。我自己都不知道frozen和帧差是什么意思。
D-10 采纳，没有示例，正常游戏用户根本想不到如何填写参数，更想不到0,5这种格式。
D-13 split功能我在app上看了，根本不知道怎么用。对用户极不友好。不止是返回问题，整个字符串操作的大量操作功能都难以理解，需要大幅改进。
2.3 varRef/varOutput 全局设计 不改动，因为只要在前端app里有说明是存入变量，那么用户就理解了其中含义。
D-35 不采纳，一个属性面板渲染消耗很少，内联字段修改不频繁
D-38 采纳，其实还有有更多操作没有使变量更新
D-42 我在app里没找到这个功能，帮我看看是不是没开放给用户使用？
D-50 采纳，这个bug在实际的bug提交文档里是变量面板 — `var_math`/`var_string`/`var_convert`/`var_compare` 的 `result` 输出不在面板中  说明变量面板没有完全覆盖所有变量，必须修复
D-51 拒绝，设计如此，否则用户非常容易查看误触
D-54 后期，目前插件量较小
R-03 同意，可以为mouse\_click 的 store\_hwnd\_var添加输出。但动作节点设计的输出其实应该很罕见。  presetreadtext是因为有要读取文字内容才要有输出

可以理解我的决策么？先和我讨论，达成共识

## Assistant

我完全理解你的决策逻辑。让我先确认几个需要深入查看的问题，然后我们逐个讨论。

好的，我完全理解你的决策逻辑。让我逐个回应你的反馈，并就几个需要深入讨论的点展开。

***

## ✅ 我理解并同意的决策

| 编号        | 你的决策                                 | 我的理解                              |
| --------- | ------------------------------------ | --------------------------------- |
| D-01      | 不采纳showWhen，改为新增"不移动直接点击"功能          | mouse\_click当前总是先移动再点击，需要支持"原地点击" |
| D-02      | 不采纳                                  | 中文展示名已友好，内部名不一致不影响用户              |
| D-07      | 采纳，各模式要显示明确中文含义                      | frozen/帧差连你自己都不理解，必须改             |
| D-10      | 采纳                                   | substr的"0,5"格式无示例，用户根本不会填         |
| D-13      | 不止split，整个string\_op都要大幅改进           | 参数名不透明、无showWhen、无示例，全面改进         |
| varOutput | 不改动                                  | 前端加"存入变量"说明即可                     |
| D-35      | 不采纳                                  | 渲染消耗少，不频繁                         |
| D-38      | 采纳，且还有更多操作没触发变量更新                    | 变量面板刷新机制需要全面检查                    |
| D-50      | 采纳，result输出不在变量面板                    | `_collectStructuredVars`覆盖不全      |
| D-51      | 拒绝                                   | 设计如此，防误触                          |
| D-54      | 后期                                   | 插件量小                              |
| R-03      | 同意为mouse\_click的store\_hwnd\_var添加输出 | 动作节点输出应罕见                         |

***

## 🔍 D-42 模拟执行 — 确认结果

我查了代码，**模拟执行确实没有开放给用户**。

`simulateExecution()` 定义在 \[editor-app.js]\(file:///c:/Users/肖鸣/Downloads/宏驱动 webui 2.7.7 - 副本/webui/modules/auto/editor-app.js) 中，但它只在 `runGraph()` 函数中作为**后端不可用时的降级方案**被调用：

```javascript
if (window.pywebview && window.pywebview.api && window.pywebview.api.run_automation) {
    // 有后端 → 调用后端执行
    window.pywebview.api.run_automation(JSON.stringify(data))
} else {
    // 无后端 → 降级为模拟执行
    simulateExecution();
}
```

也就是说，正常使用pywebview启动时，永远不会触发模拟执行。它只在浏览器直接打开HTML调试时才生效。**用户界面上没有任何按钮或入口可以触发模拟执行。**

**建议**：D-42 保持后期考虑（甚至可以降级为"不采纳"），因为该功能未对用户开放，不影响实际使用。

***

## 🎯 D-01 mouse\_click "原地点击" — 深入讨论

看了代码，当前 `mouse_click` 的执行流程是：

```
1. 解析坐标(x,y) → resolve_coords → phys_x, phys_y
2. move_duration > 0 ? 平滑移动 : 瞬移到(phys_x, phys_y)
3. 执行点击
```

用户的需求是：**不移动鼠标，直接在当前位置点击**。这在游戏场景中很常见——比如先通过检测节点找到目标位置，用 `mouse_move` 移动过去，然后在某个条件下才点击。

### 实现方案

我建议给 `mode` 枚举新增一个选项 `"current"`（显示名"当前位置"）：

```python
"mode": {"type": "string", "enum": ["screen", "window", "relative", "current"], "default": "screen", "description": "坐标模式"}
```

当 `mode=current` 时：

- **隐藏** x、y、hwnd\_var 参数（showWhen排除）
- 处理器跳过坐标解析和鼠标移动，直接在当前位置执行点击

```python
if mode == "current":
    # 不移动，直接点击
    _do_click(button, click_type, hold_time, ctx.stop_event, ctx)
else:
    # 原有逻辑：解析坐标 → 移动 → 点击
    phys_x, phys_y = resolve_coords(mode, x, y, hwnd)
    ...
```

**与你确认**：这个方案是否符合你的预期？还是你更倾向于用一个独立的布尔参数（如 `skip_move`）来控制？

***

## 🎯 D-07 check\_screen 模式中文说明

看了后端代码，三个模式的实际含义是：

| 内部名      | 当前显示名  | 实际行为                 | 建议中文显示名  | 说明                 |
| -------- | ------ | -------------------- | -------- | ------------------ |
| `black`  | black  | 平均亮度 < threshold     | **黑屏**   | 检测屏幕是否变黑（加载画面、切屏）  |
| `bright` | bright | 平均亮度 > 255-threshold | **白屏**   | 检测屏幕是否过亮（闪光、白屏）    |
| `frozen` | frozen | 与上次截图差异 < threshold  | **画面冻结** | 检测画面是否停止变化（卡死、加载中） |

`frozen` 的逻辑是：保存上次截图，与当前截图逐像素比较，如果平均差异低于阈值，说明画面没变化（冻结了）。这在游戏场景中很有用——检测"加载画面是否结束"、"游戏是否卡死"等。

**threshold 参数**在不同模式下含义不同：

- black模式：亮度阈值（低于此值判定为黑屏）
- bright模式：亮度阈值（高于255-此值判定为白屏）
- frozen模式：差异阈值（低于此值判定为冻结）

建议 threshold 的 description 也根据 mode 动态变化，或者至少在描述中说明三种含义。

***

## 🎯 D-13 string\_op 大幅改进 — 核心讨论

这是2期最复杂的改动。让我先展示当前的问题：

### 当前 string\_op 的问题

1. **参数名完全不透明**：`param_a`、`param_b`、`param_c`——用户不知道每个操作下各参数是什么意思
2. **无 showWhen**：所有参数始终显示，用户不知道哪些该填
3. **无示例**：substring的 `0,5` 格式、split\_index的索引——没有任何提示
4. **功能重复**：`utility/string_op` 和 `variable/var_string` 有大量重叠操作

### 两套字符串操作的对比

| 操作             | utility/string\_op  | variable/var\_string     |
| -------------- | ------------------- | ------------------------ |
| concat         | ✅ s + param\_a      | ✅ a + b                  |
| replace        | ✅ s.replace(pa, pb) | ✅ a.replace(b, c)        |
| upper          | ✅                   | ✅                        |
| lower          | ✅                   | ✅                        |
| trim           | ✅                   | ✅                        |
| substring      | ✅ s\[pb:pc]         | ✅ a\[start:start+length] |
| split\_index   | ✅ s.split(pa)\[pb]  | ✅ a.split(b)\[c]         |
| regex\_extract | ❌                   | ✅                        |

**两者定位不同**：

- `utility/string_op`：纯数据流节点，无流程端口，用于数据管道
- `variable/var_string`：流程节点，有in/next端口，可存入变量

### 改进方案讨论

我建议从两个层面改进：

#### 层面1：参数可见性与描述（最小改动）

给 `param_a/b/c` 添加 showWhen 和更明确的 description：

```python
"param_a": {"type": "string", "description": "拼接内容/搜索文本/分隔符", "showWhen": "op=concat,op=replace,op=split_index", "varRef": True},
"param_b": {"type": "string", "description": "替换内容/起始位置/取第几段", "showWhen": "op=replace,op=substring,op=split_index", "varRef": True},
"param_c": {"type": "string", "description": "结束位置", "showWhen": "op=substring", "varRef": True},
```

但这治标不治本——description试图用一个文字覆盖多种含义，还是不直观。

#### 层面2：按操作类型拆分参数（推荐方案）

不同操作使用不同的参数名，通过 showWhen 控制显示：

```python
"params_schema": {
    "op": {...},
    "input_str": {"type": "string", "description": "输入字符串", "varRef": True},
    # concat 专用
    "concat_str": {"type": "string", "default": "", "description": "要拼接的字符串", "showWhen": "op=concat", "varRef": True},
    # replace 专用
    "search_str": {"type": "string", "default": "", "description": "要查找的文本", "showWhen": "op=replace", "varRef": True},
    "replace_str": {"type": "string", "default": "", "description": "替换为", "showWhen": "op=replace", "varRef": True},
    # substring 专用
    "start_pos": {"type": "number", "default": 0, "description": "起始位置(从0开始)", "showWhen": "op=substring"},
    "length": {"type": "number", "default": 0, "description": "截取长度(0=到末尾)", "showWhen": "op=substring"},
    # split_index 专用
    "delimiter": {"type": "string", "default": ",", "description": "分隔符", "showWhen": "op=split_index", "varRef": True},
    "index": {"type": "number", "default": 0, "description": "取第几段(从0开始)", "showWhen": "op=split_index"},
}
```

这样用户选择不同操作时，只看到该操作需要的参数，且参数名明确。

**var\_string 也需要同步改进**，否则两套节点的体验差距更大。

***

## 🎯 D-38 + D-50 变量面板刷新与覆盖 — 合并讨论

这两个问题本质上是同一个问题：**变量面板的数据收集和刷新不完整**。

### 当前 `_collectStructuredVars` 覆盖的节点

从代码看，它只覆盖了：

- `var_set` → name
- `check_color` → store\_var
- `check_ocr` → store\_var, text, number
- `check_image` → store\_var
- `var_math` → result
- `var_string` → result
- `var_convert` → result
- `var_compare` → result

### 缺失的变量来源

| 节点                        | 缺失变量                       | 类型            |
| ------------------------- | -------------------------- | ------------- |
| `utility/math_op`         | result                     | number        |
| `utility/math_func`       | result                     | number        |
| `utility/logic_op`        | result                     | boolean       |
| `utility/compare`         | result                     | boolean       |
| `utility/string_op`       | result                     | string        |
| `utility/condition`       | result                     | any           |
| `utility/bookmark`        | rect\_1/2/3                | string        |
| `preset/preset_read_text` | text                       | string        |
| `monitor/monitor_ocr`     | store\_var, store\_number  | string/number |
| `action/mouse_click`      | store\_hwnd\_var (R-03采纳后) | string        |
| `control/loop_count`      | counter\_var               | number        |
| `control/race_win`        | winner\_branch             | string        |

### 刷新触发缺失

变量面板在以下操作后不刷新：

- 删除节点（D-38）
- 撤销/重做
- 粘贴节点
- 修改节点的 store\_var / name 属性
- 连线/断开数据端口

**建议**：将 D-38 和 D-50 合并为一个"变量面板完善"专项，统一修复覆盖和刷新问题。

***

## 🎯 R-03 mouse\_click store\_hwnd\_var 输出

同意你的判断——动作节点的输出应该罕见。`mouse_click` 的 `store_hwnd_var` 是一个特殊情况：用户点击后可能需要在后续节点中引用点击位置的窗口句柄。

实现方式：给 `mouse_click` 增加一个 `hwnd` 数据输出端口（而非通过变量），这样更符合数据流的设计理念。但考虑到你说"动作节点输出应罕见"，用变量存储也可以接受。

**你倾向哪种**：

- **方案A**：增加 `hwnd` 数据输出端口（更符合数据流设计，但动作节点有了数据输出）
- **方案B**：保留 `store_hwnd_var` 变量存储方式，只确保变量面板能显示它

***

## 📊 2期最终采纳清单（基于讨论更新）

| 分类           | 编号         | 内容                                     | 优先级 |
| ------------ | ---------- | -------------------------------------- | --- |
| **功能改进**     | D-01(new)  | mouse\_click 新增"当前位置"模式                | P1  |
| **描述/UX**    | D-03       | key\_action 添加按键选择器                    | P2  |
| **描述/UX**    | D-04       | text\_input 长文本用textarea               | P2  |
| **描述/UX**    | D-06       | program\_close force描述优化               | P2  |
| **描述/UX**    | D-07       | check\_screen 各模式中文说明+threshold动态描述    | P1  |
| **描述/UX**    | D-08       | math\_func sin/cos弧度说明                 | P2  |
| **描述/UX**    | D-09       | if\_else fallback显示中文                  | P2  |
| **描述/UX**    | D-10       | var\_string substr添加示例                 | P1  |
| **功能增强**     | D-13       | string\_op + var\_string 全面改进          | P1  |
| **功能增强**     | D-14       | var\_math abs/round 一元运算隐藏B端口          | P2  |
| **功能增强**     | D-15       | logic\_op not 一元运算隐藏B端口                | P2  |
| **功能增强**     | D-17       | check\_ocr match\_number 缺varRef       | P1  |
| **功能增强**     | D-18       | check\_ocr cache\_interval\_ms 缺varRef | P1  |
| **功能增强**     | D-19       | check\_image template\_path 缺varRef    | P2  |
| **变量面板**     | D-38+D-50  | 变量面板覆盖不全+刷新不触发                         | P1  |
| **varRef说明** | D-30\~34替代 | 前端store\_var等字段添加"存入变量"说明              | P2  |
| **画布交互**     | D-36       | 粘贴保留\_customName                       | P2  |
| **画布交互**     | D-39       | 撤销后属性面板刷新                              | P2  |
| **画布交互**     | D-41       | 执行完成后清除节点高亮                            | P2  |
| **画布交互**     | D-43       | 保存画布视口位置和缩放                            | P2  |
| **其他**       | D-46       | 工具箱搜索支持中文                              | P2  |
| **其他**       | D-47       | 工具箱节点添加tooltip                         | P2  |
| **其他**       | D-57       | bookmark hwnd\_var缺showWhen            | P2  |
| **动作输出**     | R-03       | mouse\_click store\_hwnd\_var 输出       | P2  |

**合计约24项**

***

## ❓ 需要你确认的问题

1. **D-01 mouse\_click "原地点击"**：用 `mode=current` 方案还是 `skip_move` 布尔参数？
2. **D-13 string\_op 改进**：层面1（最小改动，只加showWhen和描述）还是层面2（按操作拆分参数名）？var\_string是否同步改？
3. **R-03 mouse\_click 输出**：方案A（数据输出端口）还是方案B（保留变量存储）？
4. **D-07 check\_screen**：threshold参数的描述，是动态变化（根据mode显示不同描述），还是统一写一段说明覆盖三种含义？

确认后我们就可以生成正式的2期bug修复意见书了。

## User

"原地点击" ：用 mode=current 方案；string\_op 按操作拆分参数名且var\_string同步；R-03为方案B；D7动态变化。
现在请你生成正式的修复意见书，记得要有未采纳，等后期的bug。便于3期意见书的完成。

## Assistant

2期Bug修复意见书已生成，文件位于 \[Bug修复意见书2期.md]\(file:///c:/Users/肖鸣/Downloads/宏驱动 webui 2.7.7 - 副本/问题/Bug修复意见书2期.md)。

文档结构总览：

| 章节          | 内容                                                                        |
| ----------- | ------------------------------------------------------------------------- |
| 一、✅ 采纳      | 24项，分5组：功能改进(8)、描述透明化(7)、变量面板专项(2)、画布交互(4)、工具箱(3)                         |
| 二、⏳ 后期考虑    | 26项，分4组：低优先级UX(4)、功能增强(9)、画布交互(6)、其他(5)                                   |
| 三、❌ 拒绝      | 9项，每项附拒绝原因                                                                |
| 四、优先级排序     | P1(6组) + P2(15项)                                                          |
| 五、跨模块方案     | 5个专项：参数透明化规范、变量面板完善、string\_op改进、check\_screen动态描述、mouse\_click current模式 |
| 六、1期→2期状态变更 | 8项判定变更及原因                                                                 |

几个关键设计决策已完整记录在第五章：

- **B-01**：`mode=current` 方案，含节点定义变更和处理器逻辑
- **B-02**：string\_op/var\_string 按操作拆分参数名的完整新参数定义
- **B-09**：check\_screen state 中文显示名 + threshold 动态描述对照表
- **B-17**：varOutput 降级方案——前端添加"存入变量"说明而非引入新标记

3期可以直接从"⏳ 后期考虑"的26项中继续筛选。

