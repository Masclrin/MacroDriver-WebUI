def register(registry):
    registry.register_node({
        "type": "control/if_else",
        "category": "control",
        "display_name": "条件分支",
        "color": "#a855f7",
        "inputs": [
            {"name": "in", "type": "flow"},
            {"name": "cond", "type": "data_bool"},
        ],
        "outputs": [
            {"name": "true", "type": "flow"},
            {"name": "false", "type": "flow"},
        ],
        "params_schema": {
            "logic": {"type": "string", "enum": ["AND", "OR", "NOT"], "default": "AND", "description": "逻辑组合(多条件时)", "display_names": {"AND": "与(全部满足)", "OR": "或(任一满足)", "NOT": "非(取反)"}},
            "fallback": {"type": "string", "enum": ["true", "false"], "default": "false", "description": "无数据连接时默认走向", "display_names": {"true": "走'是'分支", "false": "走'否'分支"}},
        },
        "handler": "_handle_if_else",
    })

    registry.register_node({
        "type": "control/loop_count",
        "category": "control",
        "display_name": "计数循环",
        "color": "#a855f7",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "body", "type": "flow"},
            {"name": "next", "type": "flow"},
        ],
        "params_schema": {
            "count": {"type": "number", "default": 1, "description": "循环次数", "varRef": True},
            "counter_var": {"type": "string", "default": "", "description": "循环计数器变量名", "varRef": True},
        },
        "handler": "_handle_loop_count",
    })

    registry.register_node({
        "type": "control/loop_while",
        "category": "control",
        "display_name": "条件循环",
        "color": "#a855f7",
        "inputs": [
            {"name": "in", "type": "flow"},
            {"name": "cond", "type": "data_bool"},
        ],
        "outputs": [
            {"name": "body", "type": "flow"},
            {"name": "next", "type": "flow"},
        ],
        "params_schema": {
            "max_iterations": {"type": "number", "default": 10000, "description": "最大循环次数(防死循环)", "varRef": True},
            "check_at": {"type": "string", "enum": ["start", "end"], "default": "start", "description": "检查时机", "display_names": {"start": "循环前检查(先判断后执行)", "end": "循环后检查(先执行后判断)"}},
        },
        "handler": "_handle_loop_while",
    })

    registry.register_node({
        "type": "control/wait_cond",
        "category": "control",
        "display_name": "等待条件",
        "color": "#a855f7",
        "inputs": [
            {"name": "in", "type": "flow"},
            {"name": "cond", "type": "data_bool"},
        ],
        "outputs": [
            {"name": "met", "type": "flow"},
            {"name": "timeout", "type": "flow"},
        ],
        "params_schema": {
            "timeout": {"type": "number", "default": 10000, "description": "超时(ms)", "varRef": True},
            "interval": {"type": "number", "default": 100, "description": "检查间隔(ms)", "varRef": True},
        },
        "handler": "_handle_wait_cond",
    })

    registry.register_node({
        "type": "control/goto",
        "category": "control",
        "display_name": "跳转",
        "color": "#a855f7",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [],
        "params_schema": {
            "target_node_id": {"type": "string", "default": "", "description": "目标节点ID", "varRef": True},
        },
        "handler": "_handle_goto",
    })

    registry.register_node({
        "type": "control/seq_check",
        "category": "control",
        "display_name": "多条件检测",
        "color": "#a855f7",
        "inputs": [
            {"name": "in", "type": "flow"},
            {"name": "cond", "type": "data_bool"},
        ],
        "outputs": [
            {"name": "pass", "type": "flow"},
            {"name": "fail", "type": "flow"},
        ],
        "params_schema": {
            "retry": {"type": "boolean", "label": "重复检测", "default": True, "description": "是否一遍遍检测直到满足。关闭=只检测一次，不满足立即走 fail", "display_names": {"true": "是(反复检测)", "false": "否(只检测一次)"}},
            "max_retries": {"type": "number", "label": "最大检测次数", "default": 100, "description": "最多检测多少次（配合检测间隔≈最长等待时间）。例: 100次×100ms=最多等10秒；0=不限次数（由超时或编辑器停止中断）", "varRef": True},
            "poll_interval_ms": {"type": "number", "label": "检测间隔(ms)", "default": 100, "description": "每次检测之间的间隔，越小响应越快、越占CPU", "varRef": True},
            "timeout_ms": {"type": "number", "label": "总超时(ms)", "default": 0, "description": "整体最长等待时间，超过就走 fail。0=不单独计时，只用上面的「最大检测次数」；填了以后以本项为准", "varRef": True},
        },
        "handler": "_handle_seq_check",
    })

    registry.register_node({
        "type": "control/state_machine",
        "category": "control",
        "display_name": "状态机",
        "color": "#a855f7",
        "inputs": [
            {"name": "in", "type": "flow"},
            {"name": "cond", "type": "data_bool"},
        ],
        "outputs": [{"name": "done", "type": "flow"}],
        "params_schema": {
            "states": {
                "type": "stage_list", "label": "阶段列表", "default": "", "varRef": True,
                "description": (
                    "按先后顺序写下要经历的阶段名字（只是标签，不是节点名/变量名）。"
                    "执行时从第1个阶段开始：cond 为真就前进到下一阶段，走完最后一个阶段输出 done。"
                    "示例：待机 → 攻击 → 冷却 → 待机"
                )
            },
            "fail_state": {
                "type": "stage_ref", "label": "失败回退阶段", "default": "", "varRef": True,
                "description": (
                    "cond 为假时回到哪个阶段重新开始（从上面的阶段列表中选择）。"
                    "留空=不回退，cond 为假时停在当前阶段继续等待"
                )
            },
            "stage_timeout_ms": {
                "type": "number", "label": "单阶段超时(ms)", "default": 0, "varRef": True,
                "description": (
                    "单个阶段最长等待时间；某阶段一直等不到 cond 为真时按失败处理（回退/前进）。"
                    "0 = 不超时（只能靠编辑器停止或分支取消中断）"
                )
            },
            "poll_interval_ms": {"type": "number", "label": "判定间隔(ms)", "default": 100, "description": "每隔多久判定一次 cond，越小响应越快、越占CPU", "varRef": True},
        },
        "handler": "_handle_state_machine",
    })

    registry.register_node({
        "type": "control/fork",
        "category": "control",
        "display_name": "并发执行",
        "color": "#a855f7",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "next", "type": "flow", "display_name": "立即"},
            {"name": "done", "type": "flow", "display_name": "完成"},
            {"name": "branch1", "type": "flow"},
            {"name": "branch2", "type": "flow"},
        ],
        "params_schema": {
            "branch_count": {"type": "number", "default": 2, "min": 2, "max": 8, "description": "分支数量"},
            "branch_name_1": {"type": "string", "default": "", "description": "分支1名称(空=默认)"},
            "branch_name_2": {"type": "string", "default": "", "description": "分支2名称(空=默认)"},
            "branch_name_3": {"type": "string", "default": "", "description": "分支3名称(空=默认)", "showWhen": "branch_count>=3"},
            "branch_name_4": {"type": "string", "default": "", "description": "分支4名称(空=默认)", "showWhen": "branch_count>=4"},
            "branch_name_5": {"type": "string", "default": "", "description": "分支5名称(空=默认)", "showWhen": "branch_count>=5"},
            "branch_name_6": {"type": "string", "default": "", "description": "分支6名称(空=默认)", "showWhen": "branch_count>=6"},
            "branch_name_7": {"type": "string", "default": "", "description": "分支7名称(空=默认)", "showWhen": "branch_count>=7"},
            "branch_name_8": {"type": "string", "default": "", "description": "分支8名称(空=默认)", "showWhen": "branch_count>=8"},
            "branch_affinity_1": {"type": "affinity", "default": {"enabled": False, "core": -1}, "description": "分支1绑核设置"},
            "branch_affinity_2": {"type": "affinity", "default": {"enabled": False, "core": -1}, "description": "分支2绑核设置"},
            "branch_affinity_3": {"type": "affinity", "default": {"enabled": False, "core": -1}, "description": "分支3绑核设置", "showWhen": "branch_count>=3"},
            "branch_affinity_4": {"type": "affinity", "default": {"enabled": False, "core": -1}, "description": "分支4绑核设置", "showWhen": "branch_count>=4"},
            "branch_affinity_5": {"type": "affinity", "default": {"enabled": False, "core": -1}, "description": "分支5绑核设置", "showWhen": "branch_count>=5"},
            "branch_affinity_6": {"type": "affinity", "default": {"enabled": False, "core": -1}, "description": "分支6绑核设置", "showWhen": "branch_count>=6"},
            "branch_affinity_7": {"type": "affinity", "default": {"enabled": False, "core": -1}, "description": "分支7绑核设置", "showWhen": "branch_count>=7"},
            "branch_affinity_8": {"type": "affinity", "default": {"enabled": False, "core": -1}, "description": "分支8绑核设置", "showWhen": "branch_count>=8"},
        },
        "handler": "_handle_fork",
        "dynamic_branches": True,
    })

    registry.register_node({
        "type": "control/join",
        "category": "control",
        "display_name": "等待汇合",
        "color": "#a855f7",
        "inputs": [
            {"name": "branch1", "type": "flow"},
            {"name": "branch2", "type": "flow"},
        ],
        "outputs": [{"name": "done", "type": "flow"}],
        "params_schema": {
            "branch_count": {"type": "number", "default": 2, "min": 2, "max": 8, "description": "分支数量"},
            "wait_mode": {"type": "string", "enum": ["all", "any", "custom"], "default": "all", "description": "等待模式", "display_names": {"all": "全部到达(等所有分支)", "any": "任一到达(任一即继续)", "custom": "自定义(手动勾选)"}},
            "branch_required_1": {"type": "boolean", "default": True, "description": "分支1必须到达", "showWhen": "wait_mode=custom"},
            "branch_required_2": {"type": "boolean", "default": True, "description": "分支2必须到达", "showWhen": "wait_mode=custom"},
            "branch_required_3": {"type": "boolean", "default": True, "description": "分支3必须到达", "showWhen": "wait_mode=custom,branch_count>=3"},
            "branch_required_4": {"type": "boolean", "default": True, "description": "分支4必须到达", "showWhen": "wait_mode=custom,branch_count>=4"},
            "branch_required_5": {"type": "boolean", "default": True, "description": "分支5必须到达", "showWhen": "wait_mode=custom,branch_count>=5"},
            "branch_required_6": {"type": "boolean", "default": True, "description": "分支6必须到达", "showWhen": "wait_mode=custom,branch_count>=6"},
            "branch_required_7": {"type": "boolean", "default": True, "description": "分支7必须到达", "showWhen": "wait_mode=custom,branch_count>=7"},
            "branch_required_8": {"type": "boolean", "default": True, "description": "分支8必须到达", "showWhen": "wait_mode=custom,branch_count>=8"},
            "timeout_ms": {"type": "number", "default": 30000, "description": "超时(ms, 0=无限)", "varRef": True},
            "cancel_others": {"type": "boolean", "default": False, "description": "触发后取消未到达分支"},
            "target_fork_node_id": {"type": "string", "default": "", "description": "显式指定目标Fork/Race节点ID(空=自动推断)", "nodeRef": "fork_race"},
        },
        "handler": "_handle_join",
        "dynamic_branches": True,
    })

    registry.register_node({
        "type": "control/race",
        "category": "control",
        "display_name": "竞争执行",
        "color": "#a855f7",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "branch1", "type": "flow"},
            {"name": "branch2", "type": "flow"},
        ],
        "params_schema": {
            "branch_count": {"type": "number", "default": 2, "min": 2, "max": 8, "description": "分支数量"},
            "branch_name_1": {"type": "string", "default": "", "description": "分支1名称(空=默认)"},
            "branch_name_2": {"type": "string", "default": "", "description": "分支2名称(空=默认)"},
            "branch_name_3": {"type": "string", "default": "", "description": "分支3名称(空=默认)", "showWhen": "branch_count>=3"},
            "branch_name_4": {"type": "string", "default": "", "description": "分支4名称(空=默认)", "showWhen": "branch_count>=4"},
            "branch_name_5": {"type": "string", "default": "", "description": "分支5名称(空=默认)", "showWhen": "branch_count>=5"},
            "branch_name_6": {"type": "string", "default": "", "description": "分支6名称(空=默认)", "showWhen": "branch_count>=6"},
            "branch_name_7": {"type": "string", "default": "", "description": "分支7名称(空=默认)", "showWhen": "branch_count>=7"},
            "branch_name_8": {"type": "string", "default": "", "description": "分支8名称(空=默认)", "showWhen": "branch_count>=8"},
            "branch_affinity_1": {"type": "affinity", "default": {"enabled": False, "core": -1}, "description": "分支1绑核设置"},
            "branch_affinity_2": {"type": "affinity", "default": {"enabled": False, "core": -1}, "description": "分支2绑核设置"},
            "branch_affinity_3": {"type": "affinity", "default": {"enabled": False, "core": -1}, "description": "分支3绑核设置", "showWhen": "branch_count>=3"},
            "branch_affinity_4": {"type": "affinity", "default": {"enabled": False, "core": -1}, "description": "分支4绑核设置", "showWhen": "branch_count>=4"},
            "branch_affinity_5": {"type": "affinity", "default": {"enabled": False, "core": -1}, "description": "分支5绑核设置", "showWhen": "branch_count>=5"},
            "branch_affinity_6": {"type": "affinity", "default": {"enabled": False, "core": -1}, "description": "分支6绑核设置", "showWhen": "branch_count>=6"},
            "branch_affinity_7": {"type": "affinity", "default": {"enabled": False, "core": -1}, "description": "分支7绑核设置", "showWhen": "branch_count>=7"},
            "branch_affinity_8": {"type": "affinity", "default": {"enabled": False, "core": -1}, "description": "分支8绑核设置", "showWhen": "branch_count>=8"},
            "cancel_on_first": {"type": "boolean", "default": True, "description": "首个分支到达后取消其他分支"},
            "timeout_ms": {"type": "number", "default": 0, "description": "超时(ms, 0=无限)", "varRef": True},
        },
        "handler": "_handle_race",
        "dynamic_branches": True,
    })

    registry.register_node({
        "type": "control/race_win",
        "category": "control",
        "display_name": "竞争胜出",
        "color": "#f59e0b",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "next", "type": "flow"},
            {"name": "winner_branch", "type": "data_string"},
        ],
        "params_schema": {},
        "handler": "_handle_race_win",
    })

    registry.register_node({
        "type": "control/stop_branch",
        "category": "control",
        "display_name": "停止分支",
        "color": "#a855f7",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "target_branch": {"type": "string", "default": "all_others", "description": "目标分支ID(all_others/分支ID/${变量})", "varRef": True, "branchRef": True},
        },
        "handler": "_handle_stop_branch",
    })

    registry.register_node({
        "type": "control/pause_branch",
        "category": "control",
        "display_name": "暂停分支",
        "color": "#a855f7",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "target_branch": {"type": "string", "default": "all_others", "description": "目标分支ID(all_others/分支ID/${变量})", "varRef": True, "branchRef": True},
        },
        "handler": "_handle_pause_branch",
    })

    registry.register_node({
        "type": "control/resume_branch",
        "category": "control",
        "display_name": "恢复分支",
        "color": "#a855f7",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "target_branch": {"type": "string", "default": "all_others", "description": "目标分支ID(all_others/分支ID/${变量})", "varRef": True, "branchRef": True},
        },
        "handler": "_handle_resume_branch",
    })

    registry.register_node({
        "type": "script_block/call_script_sync",
        "category": "script_block",
        "display_name": "调用宏(同步)",
        "color": "#3b82f6",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [{"name": "next", "type": "flow"}],
        "params_schema": {
            "path": {"type": "string", "default": "", "format": "path", "description": "旧JSON宏文件路径(.json)", "varRef": True},
            "speed_factor": {"type": "number", "default": 1.0, "description": "倍速(1.0=原速,2.0=两倍)"},
            "timeline_mode": {"type": "string", "enum": ["absolute", "relative_compensated"], "default": "absolute", "description": "时间线模式", "display_names": {"absolute": "绝对时间线(高精度)", "relative_compensated": "相对补偿(低占用)"}},
            "random_delay": {"type": "boolean", "default": False, "description": "启用随机延迟修正(拟人化)"},
            "standby_override": {"type": "string", "enum": ["inherit", "on", "off"], "default": "inherit", "description": "Standby 工业级精度引擎覆盖。inherit=使用全局设置; on=强制启用(简单线性宏走 native dll 级精度); off=强制关闭走 Python 路径", "display_names": {"inherit": "继承全局", "on": "强制启用", "off": "强制关闭"}},
            "rtss_override": {"type": "string", "enum": ["inherit", "on", "off"], "default": "inherit", "description": "RTSS 帧同步覆盖(仅对含帧延迟f的宏生效)。inherit=使用全局设置; on=强制启用(未检测到RTSS时走fallback); off=强制关闭(帧延迟回退为固定ms)", "display_names": {"inherit": "继承全局", "on": "强制启用", "off": "强制关闭"}},
        },
        "handler": "_handle_call_script_sync",
    })

    registry.register_node({
        "type": "script_block/call_script_async",
        "category": "script_block",
        "display_name": "调用宏(异步)",
        "color": "#3b82f6",
        "inputs": [{"name": "in", "type": "flow"}],
        "outputs": [
            {"name": "next", "type": "flow"},
            {"name": "completed", "type": "flow"},
            {"name": "interrupted", "type": "flow"},
        ],
        "params_schema": {
            "path": {"type": "string", "default": "", "format": "path", "description": "旧JSON宏文件路径(.json)", "varRef": True},
            "speed_factor": {"type": "number", "default": 1.0, "description": "倍速(1.0=原速,2.0=两倍)"},
            "timeline_mode": {"type": "string", "enum": ["absolute", "relative_compensated"], "default": "absolute", "description": "时间线模式", "display_names": {"absolute": "绝对时间线(高精度)", "relative_compensated": "相对补偿(低占用)"}},
            "random_delay": {"type": "boolean", "default": False, "description": "启用随机延迟修正(拟人化)"},
            "standby_override": {"type": "string", "enum": ["inherit", "on", "off"], "default": "inherit", "description": "Standby 工业级精度引擎覆盖。inherit=使用全局设置; on=强制启用(简单线性宏走 native dll 级精度); off=强制关闭走 Python 路径", "display_names": {"inherit": "继承全局", "on": "强制启用", "off": "强制关闭"}},
            "rtss_override": {"type": "string", "enum": ["inherit", "on", "off"], "default": "inherit", "description": "RTSS 帧同步覆盖(仅对含帧延迟f的宏生效)。inherit=使用全局设置; on=强制启用(未检测到RTSS时走fallback); off=强制关闭(帧延迟回退为固定ms)", "display_names": {"inherit": "继承全局", "on": "强制启用", "off": "强制关闭"}},
        },
        "handler": "_handle_call_script_async",
    })
