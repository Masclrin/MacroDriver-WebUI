# Standby「长宏长尾优化」开关速查（面向使用者）

> 结论来源：`docs/standby引擎工业级精度执行方案.md` 第 C.4–C.7 节实测（2026-07）  
> 与 `core/precision_profile.py` 的档位预设。  
> 关心的问题：**哪些开关真的能提升精度？哪些在特定场景反而劣化？**

---

## 一、这四个开关是什么

在「全局参数 → 执行框架 3.2」里，`STANDBY_PS_*` 共 4 个分组开关。  
它们**只作用于 standby 引擎的工作线程（C 侧 standby_thread）**，不是把整个 WebUI 进程提权。  
任意一个开启即启用 PrecisionScope 框架。

| 开关                    | 做了什么                                                 | 作用对象                 |
| --------------------- | ---------------------------------------------------- | -------------------- |
| `STANDBY_PS_PRIORITY` | REALTIME_PRIORITY_CLASS + 禁用进程/线程 priority boost     | 工作线程不被系统线程抢占         |
| `STANDBY_PS_TIMER`    | `NtSetTimerResolution(0.5ms)` + `timeBeginPeriod(1)` | 唤醒精度（15.6ms → 0.5ms） |
| `STANDBY_PS_MMCSS`    | `AvSetMmThreadCharacteristics("Pro Audio")`          | 绕过普通调度器              |
| `STANDBY_PS_POWER`    | 禁用 Win11 PowerThrottling（EcoQoS）                     | 防止被降频/降定时器精度         |

---

## 二、实测结论（谁提升、谁劣化）

延迟用 p999 描述"最坏的那 0.1%"——**长尾**才是体感卡顿的来源。

| 开关                   | 短间隔宏（10ms，甜区） | 长间隔宏（300ms+）          | 判定                    |
| -------------------- | ------------- | --------------------- | --------------------- |
| **PRIORITY**         | p999 **-92%** | p999 **-99%**         | ✅ **甜区 + 长宏都优化，收益最大** |
| **TIMER**            | p999 **-76%** | p999 **-99%**         | ✅ 都优化                 |
| **POWER**            | 防御性（无独立数字）    | 防御性                   | ✅ 建议开（防 Win11 节流）     |
| **MMCSS（单独开）**       | p999 -80%     | p999 **+679%（灾难性劣化）** | ❌ **长宏有害**            |
| **MMCSS + PRIORITY** | p999 -82%     | p999 -98%             | ✅ 配对后安全               |
| REALTIME + TIMER     | p999 -79%     | p999 -99%             | ✅ 最佳组合                |

**已实测拒绝、不要再开的**：

- **进程级 affinity**（把 Python 主线程/GC 线程也限制到工作核）：1ms 间隔下 max **+5741%**，严重竞争。
- **2-worker rescue**：1ms 间隔下 p99 **+311%**，10ms+ 无一致收益。

---

## 三、给你的实操建议

**最稳的组合（甜区 + 长宏都吃到收益）**

```
STANDBY_PS_PRIORITY = 开
STANDBY_PS_TIMER    = 开
STANDBY_PS_POWER    = 开
STANDBY_PS_MMCSS    = 与 PRIORITY 同开（要么都开，要么都关）
```

**⚠️ 唯一的坑（你担心的"劣化"就在这里）**

> **MMCSS 单独开着、而 PRIORITY 关掉** → 长间隔（300ms+）宏的延迟会从约 0.8ms 崩到 **6ms 量级（+679%）**。  
> 所以：**若要关 PRIORITY，请把 MMCSS 一起关掉。**

**当前仓库里的持久化配置是**：4 个全开（PRIORITY/TIMER/MMCSS/POWER 均 `true`）。  
由于 MMCSS 与 PRIORITY 是配对的，**现在这套是安全的**；  
只有当你单独把 PRIORITY 改成 `false` 而 MMCSS 还是 `true` 时才会踩到上面那个坑。

**与「精度/占用档位」的关系**  
`core/precision_profile.py` 里四个档位的预设**把 PRIORITY 与 MMCSS 都设为 `false`**，  
理由是"REALTIME 在游戏吃满全核时可能饿死游戏"，改用**绑核隔离**换精度。

- 想稳（不抢游戏）→ 就用档位预设（PRIORITY/MMCSS 关，TIMER/POWER 开）。
- 想榨长尾极限 → 手动把 `STANDBY_PS_PRIORITY` 打开（务必确认绑核 `ENABLE_THREAD_CORE_BINDING` 生效，把工作线程钉在游戏不用的核上）。

---

## 四、一句话总结

| 想要             | 开什么                                           |
| -------------- | --------------------------------------------- |
| 短宏（10~100ms）更准 | PRIORITY 或 TIMER 任一即可（TIMER 最省事）              |
| 长宏（300ms+）长尾更稳 | PRIORITY + TIMER（实测 -99%）                     |
| 别踩坑            | MMCSS 不要单独开；进程 affinity / 2-worker rescue 不要开 |
| 不想抢游戏          | 用「均衡」档（PRIORITY/MMCSS 关，靠绑核）                  |

---

*数据出处：`docs/standby引擎工业级精度执行方案.md` C.4 / C.6 / C.7*
