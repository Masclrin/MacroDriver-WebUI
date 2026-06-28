# 并发模型：Fork / Join / Race

## 1. 概述

MacroDriver 自动化引擎支持三种并发控制原语，通过 Scope Tree 实现嵌套并发管理。

| 节点 | 显示名 | 语义 |
|------|--------|------|
| `control/fork` | 并发执行 | 启动多个并行分支，主线程不等待 |
| `control/join` | 汇合 | 等待多个分支到达后继续 |
| `control/race` | 竞速 | 多个分支竞争，首个完成者胜出 |

## 2. Scope Tree（作用域树）

每个 Fork/Race 节点创建一个 Scope，Scope 之间形成父子树结构：

```
[Fork A] → Scope A
  ├── branch1
  │     └── [Fork B] → Scope B (child of Scope A)
  │           ├── branch1.1
  │           └── branch1.2
  └── branch2
```

- 父 Scope 记录所有子 Scope ID
- 取消父分支时，递归取消所有子 Scope 的分支
- Join 可通过 `target_fork_node_id` 显式指定目标 Fork/Race

## 3. Fork 节点

### 3.1 端口

| 端口 | 方向 | 显示名 | 说明 |
|------|------|--------|------|
| `in` | 输入 | 入口 | 触发 Fork |
| `next` | 输出 | 立即 | 分支启动后立刻执行，不等待 |
| `done` | 输出 | 完成 | 所有分支完成后执行 |
| `branch1`~`branch8` | 输出 | 分支 N | 并发分支 |

### 3.2 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `branch_count` | number | 2 | 分支数量（2~8） |
| `branch_name_N` | string | "" | 分支显示名（空=默认） |
| `branch_affinity_N` | affinity | disabled | 分支绑核设置 |

### 3.3 执行语义

1. 收到 `in` 信号后，为每个有下游连线的 `branchN` 端口创建分支线程
2. 所有分支线程启动后，**立即**执行 `next` 端口下游
3. 同时启动一个后台 daemon 线程轮询所有分支状态，全部完成后执行 `done` 端口下游

### 3.4 `next` vs `done` 的选择

- **简单场景**：用 `done` 端口，等所有分支完成自动汇合，无需额外连线
- **复杂场景**：用 `next` 端口 + Join 节点，支持跨层级汇合、any/custom 模式

```
简单场景：                        复杂场景：
[Fork]──done──→ [结束]           [Fork]──next──→ [其他工作]
  ├─branch1──→ [工作1]             ├─branch1──→ [工作1]──→ [Join]
  └─branch2──→ [工作2]             └─branch2──→ [工作2]──→ [Join]
                                     [Join]──done──→ [结束]
```

## 4. Join 节点

### 4.1 端口

| 端口 | 方向 | 说明 |
|------|------|------|
| `branch1`~`branch8` | 输入 | 等待分支到达 |
| `done` | 输出 | 条件满足后执行 |

### 4.2 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `wait_mode` | enum | all | all / any / custom |
| `timeout_ms` | number | 30000 | 超时时间（ms） |
| `cancel_others` | bool | false | 条件满足后取消未到达分支 |
| `target_fork_node_id` | string | "" | 显式指定目标 Fork/Race ID |
| `branch_required_N` | bool | true | custom 模式下该分支是否必须 |

### 4.3 等待模式

| 模式 | 行为 |
|------|------|
| `all` | 等待所有目标分支到达 |
| `any` | 任意一个分支到达即触发 |
| `custom` | 等待标记为 required 的分支全部到达 |

### 4.4 目标解析

Join 通过两种方式确定等待哪些分支：

1. **显式指定**：`target_fork_node_id` 参数直接指定目标 Fork/Race
2. **自动追溯**：从 Join 的 `branchN` 输入端口向上游追溯，找到 Fork/Race 节点

### 4.5 超时行为

超时后仍然执行 `done` 端口，不区分"全部到达"和"超时 partial 到达"。

## 5. Race 节点

### 5.1 端口

| 端口 | 方向 | 说明 |
|------|------|------|
| `in` | 输入 | 触发 Race |
| `branch1`~`branch8` | 输出 | 竞速分支 |

Race 节点**没有流程输出端口**。主线程在 Race 处阻塞等待。

### 5.2 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `cancel_on_first` | bool | true | 首个分支完成即取消其他 |
| `timeout_ms` | number | 0 | 超时（0=无限等待） |
| `branch_affinity_N` | affinity | disabled | 分支绑核设置 |

### 5.3 胜出判定

1. **自然胜出**：分支正常执行完毕（状态变为 `completed`）→ 自动成为胜出者
2. **提前宣告**：分支内放置 `control/race_win` 节点 → 不等分支结束即宣告胜利

两种方式都会取消同 Scope 内的其他 Race 分支，但**不影响其他 Fork 分支**。

### 5.4 `race_win` 节点

| 端口 | 方向 | 说明 |
|------|------|------|
| `in` | 输入 | 触发宣告 |
| `next` | 输出 | 宣告后继续执行 |

- 在节点栏中以高亮颜色显示，便于识别
- 非必须——分支自然结束也会自动胜出
- 用途：不等分支全部执行完就抢占胜利

### 5.5 超时行为

- `timeout_ms=0`：无限等待
- `timeout_ms>0`：超时后取消所有分支，无胜出者

## 6. 分支控制节点

### 6.1 `control/stop_branch`（停止分支）

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `target_branch` | string | all_others | 目标分支 ID 或 "all_others" |

停止指定分支或除当前分支外的所有分支。

### 6.2 `control/pause_branch`（暂停分支）

暂停指定分支的执行。

### 6.3 `control/resume_branch`（恢复分支）

恢复指定分支的执行。

## 7. 嵌套并发规则

1. 任何分支内可以再放置 Fork/Race，形成嵌套
2. 子 Scope 的 branch_id 记录在父 Scope 的 `child_scope_ids` 中
3. 取消父分支时递归取消所有子分支
4. Join 的 `target_fork_node_id` 可以跨越层级指定目标
5. `flow/end` 节点触发全局停止，终止所有并发分支和异步任务

## 8. 设计意图说明

### 8.1 为什么 Fork 有 `done` 端口又有 Join 节点？

`done` 端口用于简单场景（等所有分支完成自动汇合），Join 用于复杂场景（跨层级、any/custom 模式）。两者共存，用户按需选择。

### 8.2 为什么 Race 没有输出端口？

Race 的胜出分支在分支内部继续执行（通过 `race_win` 或自然结束），不需要在 Race 节点层面输出。Race 只负责启动分支和裁定胜者。

### 8.3 为什么 `flow/end` 是全局核爆？

设计意图：任何一个分支到达结束节点意味着整个自动化任务完成。如果只需要结束当前分支，不放置 `flow/end` 即可（分支自然结束）。
