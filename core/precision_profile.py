# -*- coding: utf-8 -*-
"""精度/占用档位（Precision Profile）。

背景
----
自动化流程要同时满足两个互相拉扯的目标：
  * 低延迟 —— 节点间延迟、输入注入抖动要小（原神战斗连招要求毫秒级）
  * 低占用 —— 不能把 CPU 从游戏进程手里抢走

在此之前，这两个目标由 25+ 个平铺的布尔/数值开关控制，没有任何统一入口，
用户只能逐个试，且存在互斥组合（如同时开 ENABLE_LOW_CPU_EXECUTION 和
ENABLE_STANDBY_ENGINE）。本模块把它们收敛成 4 个档位。

关键认知
--------
**精度不等于高优先级。** 原实现一路把进程抬到 HIGH/REALTIME_PRIORITY_CLASS
并且从不恢复，这是"抢游戏 CPU"的最大元凶。真正能兼顾两者的手段是：
  * 绑核（core binding）—— 把宏线程限制在指定核心上，其余核心留给游戏
  * native standby 引擎 —— 单核自旋换取极低抖动，而非提高优先级
  * 共享帧缓存 —— 减少重复截图，降低总 CPU 时间
因此除 latency_first 档外，进程优先级一律不超过 above。
"""

# 档位名 -> {"label", "desc", "executor": {参数: 值}, "engine": {内部旋钮: 值}}
PRECISION_PROFILES = {
    "latency_first": {
        "label": "延迟优先",
        "desc": "最低节点延迟。启用 native standby 引擎并绑核；"
                "进程优先级 only above（不抢游戏），靠核隔离而非高优先级换精度。"
                "CPU 占用较高，适合需要精确时序的连招宏。",
        "executor": {
            "ENABLE_STANDBY_ENGINE": True,
            "STANDBY_PS_PRIORITY": False,   # REALTIME 会饿死游戏，默认关
            "STANDBY_PS_TIMER": True,
            "STANDBY_PS_MMCSS": False,      # 实测长间隔下反而劣化
            "STANDBY_PS_POWER": True,
            "ENABLE_REALTIME_PRIORITY": False,
            "ENABLE_PRO_AUDIO": False,
            "ENABLE_THREAD_CORE_BINDING": True,
            "CORE_BINDING_MAX_CORES": 2,
            "ENABLE_LOW_CPU_EXECUTION": False,
            "LOW_CPU_ENABLE_TIME_PERIOD": True,
            "ENABLE_BATCH_SEND": False,
            "ABSOLUTE_TIMELINE_WAIT_CHUNK_MS": 0.5,
            "TIMELINE_EXECUTION_MODE": "absolute",
            "RTSS_ENABLED": True,
        },
        "engine": {
            "process_priority_tier": "above",
            "system_timer_resolution": True,
            "frame_cache_ttl_ms": 2.0,
        },
    },
    "balanced": {
        "label": "均衡（推荐）",
        "desc": "默认档位。启用 standby 与绑核，关闭 REALTIME/MMCSS 等侵略性选项，"
                "检测缓存关闭以保证实时性，共享帧缓存 TTL 4ms。",
        "executor": {
            "ENABLE_STANDBY_ENGINE": True,
            "STANDBY_PS_PRIORITY": False,
            "STANDBY_PS_TIMER": True,
            "STANDBY_PS_MMCSS": False,
            "STANDBY_PS_POWER": True,
            "ENABLE_REALTIME_PRIORITY": False,
            "ENABLE_PRO_AUDIO": False,
            "ENABLE_THREAD_CORE_BINDING": True,
            "CORE_BINDING_MAX_CORES": 2,
            "ENABLE_LOW_CPU_EXECUTION": False,
            "LOW_CPU_ENABLE_TIME_PERIOD": True,
            "ENABLE_BATCH_SEND": True,
            "ABSOLUTE_TIMELINE_WAIT_CHUNK_MS": 1.0,
            "TIMELINE_EXECUTION_MODE": "absolute",
            "RTSS_ENABLED": True,
        },
        "engine": {
            "process_priority_tier": "normal",
            "system_timer_resolution": True,
            "frame_cache_ttl_ms": 4.0,
        },
    },
    "cpu_saver": {
        "label": "低占用",
        "desc": "把 CPU 尽量让给游戏。关闭 standby 自旋，进程优先级保持 normal，"
                "关闭全局 1ms 定时器分辨率（该设置影响整机中断率），"
                "开启低占用睡眠与批量发送，共享帧缓存 TTL 放宽到 8ms。",
        "executor": {
            "ENABLE_STANDBY_ENGINE": False,
            "STANDBY_PS_PRIORITY": False,
            "STANDBY_PS_TIMER": False,
            "STANDBY_PS_MMCSS": False,
            "STANDBY_PS_POWER": False,
            "ENABLE_REALTIME_PRIORITY": False,
            "ENABLE_PRO_AUDIO": False,
            "ENABLE_THREAD_CORE_BINDING": True,
            "CORE_BINDING_MAX_CORES": 1,
            "ENABLE_LOW_CPU_EXECUTION": True,
            "LOW_CPU_ENABLE_TIME_PERIOD": False,
            "ENABLE_BATCH_SEND": True,
            "ABSOLUTE_TIMELINE_WAIT_CHUNK_MS": 2.0,
            "TIMELINE_EXECUTION_MODE": "absolute",
            "RTSS_ENABLED": False,
        },
        "engine": {
            "process_priority_tier": "normal",
            "system_timer_resolution": False,
            "frame_cache_ttl_ms": 8.0,
        },
    },
    "custom": {
        "label": "自定义",
        "desc": "不覆盖任何参数，完全由下方各开关决定。",
        "executor": {},
        "engine": {},
    },
}

DEFAULT_PRECISION_PROFILE = "balanced"


def get_profile_names():
    return [
        {"name": k, "label": v["label"], "desc": v["desc"]}
        for k, v in PRECISION_PROFILES.items()
    ]


def get_profile(name):
    return PRECISION_PROFILES.get(str(name).lower())


def apply_precision_profile(name, executor_module=None, engine_module=None,
                            on_change=None) -> dict:
    """把档位值写入目标模块，并同步引擎级旋钮。

    :param name: 档位名；"custom" 表示不覆盖
    :param executor_module: 执行框架模块（宏执行框架3.2 加载后的 module 对象）
    :param engine_module: engine.precision 模块
    :param on_change: 可选的 (key, value) 回调，用于把变更同步到 UI/配置
    :return: {"applied": {...执行器参数...}, "engine": {...}, "profile": name}
    """
    profile = get_profile(name)
    if profile is None:
        return {"applied": {}, "engine": {}, "profile": name, "error": "未知档位"}

    applied = {}
    for key, value in (profile.get("executor") or {}).items():
        if executor_module is not None and hasattr(executor_module, key):
            try:
                setattr(executor_module, key, value)
                applied[key] = value
            except Exception:
                continue
        if on_change is not None:
            try:
                on_change(key, value)
            except Exception:
                pass

    engine_applied = {}
    eng = profile.get("engine") or {}
    if engine_module is not None:
        tier = eng.get("process_priority_tier")
        if tier:
            try:
                engine_module.set_process_priority_tier(tier)
                engine_applied["process_priority_tier"] = tier
            except Exception:
                pass
        if "system_timer_resolution" in eng:
            try:
                engine_module.set_system_timer_resolution_enabled(
                    bool(eng["system_timer_resolution"]))
                engine_applied["system_timer_resolution"] = bool(eng["system_timer_resolution"])
            except Exception:
                pass

    # 共享帧缓存 TTL：对每次执行新建的 CaptureManager 通过模块级默认值下发
    ttl = eng.get("frame_cache_ttl_ms")
    if ttl is not None:
        try:
            set_default_frame_cache_ttl(float(ttl))
            engine_applied["frame_cache_ttl_ms"] = float(ttl)
        except Exception:
            pass

    return {"applied": applied, "engine": engine_applied, "profile": name}


# ---------------------------------------------------------------------------
# 共享帧缓存默认 TTL（由档位下发，供新建的 CaptureManager 读取）
# ---------------------------------------------------------------------------
_default_frame_cache_ttl_ms = 0.0


def set_default_frame_cache_ttl(ttl_ms: float):
    global _default_frame_cache_ttl_ms
    _default_frame_cache_ttl_ms = max(0.0, float(ttl_ms or 0.0))


def get_default_frame_cache_ttl() -> float:
    return _default_frame_cache_ttl_ms
