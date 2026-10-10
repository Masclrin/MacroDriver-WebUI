"""状态机 / 多条件检测 控制节点回归测试。

覆盖用户层改造中修复的缺陷：
  1. 状态机未连接 cond 时不再无限死等（旧实现会永久 sleep 轮询）
  2. 状态机 cond 为假时的分支不再忙等（旧实现不 sleep，100% 占 CPU）
  3. 状态机新增「单阶段超时」可强制跳出
  4. 多条件检测未连接 cond 时立即 fail 而非白等
  5. 多条件检测 timeout_ms 生效

运行： python -m automation.tests.test_control_nodes
"""
import sys
import threading
import time

from automation.compiler import ExecGraph, ExecNode
from automation.engine import ExecContext, _drive_with_goto_trampoline
from automation.handlers import NODE_HANDLERS, register_all_handlers
from automation.nodes.control import register as register_control_nodes
from automation.registry import PluginRegistry

_REACHED = set()


def _setup():
    register_all_handlers()
    if PluginRegistry.get_node("control/state_machine") is None:
        register_control_nodes(PluginRegistry)

    def _term(node, ctx):
        _REACHED.add(node.id)

    NODE_HANDLERS["_test_term"] = _term
    if PluginRegistry.get_node("test/term") is None:
        PluginRegistry.register_node({
            "type": "test/term",
            "category": "test",
            "display_name": "终止",
            "color": "#888",
            "inputs": [],
            "outputs": [{"name": "next"}],
            "params_schema": {},
            "handler": "_test_term",
        })


def _cond_input(cond_val, has_cond):
    """构造 cond 数据输入；source 节点故意不在图里，直接读预置的 check_results。"""
    if not has_cond:
        return {}
    return {"cond": [{"source_node_id": "src", "source_port": "result"}]}


def _run(graph, cond_key=None, cond_val=None, wait_s=5.0):
    stop = threading.Event()
    ctx = ExecContext(graph, stop)
    ctx.node_retry_count = 0
    ctx.node_retry_delay_ms = 0
    if cond_key is not None:
        ctx.check_results[cond_key] = cond_val
    t = threading.Thread(target=_drive_with_goto_trampoline, args=(graph.entry_node_id, ctx))
    t.daemon = True
    t0 = time.perf_counter()
    t.start()
    t.join(wait_s)
    return ctx, (time.perf_counter() - t0), t


def _build_state_machine(states, has_cond=True, fail_state="", stage_timeout_ms=0,
                         poll_interval_ms=10, done_target="20"):
    g = ExecGraph()
    g.nodes["10"] = ExecNode(
        id="10", type="control/state_machine",
        params={"states": states, "fail_state": fail_state,
                "stage_timeout_ms": stage_timeout_ms, "poll_interval_ms": poll_interval_ms},
        position={}, flow_children={"done": [done_target]},
        data_inputs=_cond_input(True, has_cond),
    )
    g.nodes["20"] = ExecNode(id="20", type="test/term", params={}, position={}, flow_children={"next": []})
    g.entry_node_id = "10"
    return g


def _build_seq_check(has_cond=True, retry=True, max_retries=100, poll_interval_ms=10, timeout_ms=0):
    g = ExecGraph()
    g.nodes["10"] = ExecNode(
        id="10", type="control/seq_check",
        params={"retry": retry, "max_retries": max_retries,
                "poll_interval_ms": poll_interval_ms, "timeout_ms": timeout_ms},
        position={}, flow_children={"pass": ["20"], "fail": ["21"]},
        data_inputs=_cond_input(True, has_cond),
    )
    g.nodes["20"] = ExecNode(id="20", type="test/term", params={}, position={}, flow_children={"next": []})
    g.nodes["21"] = ExecNode(id="21", type="test/term", params={}, position={}, flow_children={"next": []})
    g.entry_node_id = "10"
    return g


def test_state_machine_without_cond_does_not_hang():
    """未连接 cond：旧实现永久 sleep 轮询（表现为卡死），现在应报错并放行。"""
    _setup()
    _REACHED.clear()
    ctx, elapsed, t = _run(_build_state_machine("A→B→C", has_cond=False), wait_s=3.0)
    print(f"  未接 cond: 耗时 {elapsed*1000:.1f}ms, alive={t.is_alive()}, errors={len(ctx.errors)}")
    assert not t.is_alive(), "状态机未接 cond 时仍在运行（死等未修复）"
    assert "20" in _REACHED, "未接 cond 时应直接放行走 done"
    assert len(ctx.errors) >= 1, "未接 cond 时未产生错误日志（用户无从得知）"


def test_state_machine_advances_and_completes():
    """cond 恒真：应逐阶段推进并最终 done。"""
    _setup()
    _REACHED.clear()
    _, elapsed, t = _run(_build_state_machine("A→B→C", has_cond=True),
                         cond_key="src.result", cond_val=True, wait_s=3.0)
    print(f"  cond 恒真: 耗时 {elapsed*1000:.1f}ms, alive={t.is_alive()}")
    assert not t.is_alive(), "状态机 cond 恒真时未结束"
    assert "20" in _REACHED, "状态机未走到 done"


def test_state_machine_no_busy_spin_when_waiting():
    """cond 恒假 + 失败回退到当前阶段：必须 sleep 轮询，不能忙等 100% CPU。"""
    _setup()
    _REACHED.clear()
    g = _build_state_machine("A→B", has_cond=True, fail_state="A", poll_interval_ms=5)
    stop = threading.Event()
    ctx = ExecContext(g, stop)
    ctx.node_retry_count = 0
    ctx.node_retry_delay_ms = 0
    ctx.check_results["src.result"] = False
    t = threading.Thread(target=_drive_with_goto_trampoline, args=(g.entry_node_id, ctx))
    t.daemon = True
    cpu0 = time.process_time()
    t0 = time.perf_counter()
    t.start()
    time.sleep(0.5)
    wall = time.perf_counter() - t0
    cpu = time.process_time() - cpu0
    stop.set()
    t.join(2.0)
    ratio = cpu / wall if wall > 0 else 1.0
    print(f"  等待 0.5s: CPU占用比={ratio:.3f} (wall={wall:.3f}s, cpu={cpu:.3f}s)")
    assert ratio < 0.5, f"状态机等待时 CPU 占用比 {ratio:.2f}，疑似忙等未修复"


def test_state_machine_stage_timeout_advances():
    """cond 恒假 + 无回退 + 单阶段超时：应按超时=失败（前进）并最终结束。"""
    _setup()
    _REACHED.clear()
    g = _build_state_machine("A→B", has_cond=True, fail_state="", stage_timeout_ms=30, poll_interval_ms=5)
    _, elapsed, t = _run(g, cond_key="src.result", cond_val=False, wait_s=3.0)
    print(f"  阶段超时: 耗时 {elapsed*1000:.1f}ms, alive={t.is_alive()}")
    assert not t.is_alive(), "单阶段超时未生效，状态机仍未结束"
    assert "20" in _REACHED, "阶段超时后未走到 done"


def test_seq_check_without_cond_fails_fast():
    """多条件检测未接 cond：应立刻 fail，而不是白等到超时。"""
    _setup()
    _REACHED.clear()
    ctx, elapsed, t = _run(_build_seq_check(has_cond=False, max_retries=100, poll_interval_ms=10), wait_s=3.0)
    print(f"  未接 cond: 耗时 {elapsed*1000:.1f}ms, 到达={sorted(_REACHED)}, errors={len(ctx.errors)}")
    assert not t.is_alive(), "多条件检测未接 cond 时仍在等待"
    assert "21" in _REACHED and "20" not in _REACHED, "未接 cond 时应走 fail 分支"
    assert len(ctx.errors) >= 1, "未接 cond 时未产生错误日志"


def test_seq_check_passes_when_all_conds_true():
    """所有 cond 为真：应走 pass。"""
    _setup()
    _REACHED.clear()
    _, _, t = _run(_build_seq_check(has_cond=True), cond_key="src.result", cond_val=True, wait_s=3.0)
    print(f"  cond 全真: 到达={sorted(_REACHED)}")
    assert not t.is_alive()
    assert "20" in _REACHED and "21" not in _REACHED, "条件全真时应走 pass 分支"


def test_seq_check_retry_false_fails_immediately():
    """关闭重复检测且 cond 为假：只检测一次即 fail。"""
    _setup()
    _REACHED.clear()
    _, elapsed, t = _run(_build_seq_check(has_cond=True, retry=False),
                         cond_key="src.result", cond_val=False, wait_s=3.0)
    print(f"  不重复检测: 耗时 {elapsed*1000:.1f}ms, 到达={sorted(_REACHED)}")
    assert not t.is_alive()
    assert "21" in _REACHED and "20" not in _REACHED, "关闭重复检测后应一次即 fail"


def test_seq_check_timeout_fails():
    """timeout_ms 生效：cond 恒假时到点即 fail（不等满 max_retries）。"""
    _setup()
    _REACHED.clear()
    _, elapsed, t = _run(_build_seq_check(has_cond=True, retry=True, max_retries=100000,
                                          poll_interval_ms=10, timeout_ms=100),
                         cond_key="src.result", cond_val=False, wait_s=3.0)
    print(f"  总超时100ms: 耗时 {elapsed*1000:.1f}ms, 到达={sorted(_REACHED)}")
    assert not t.is_alive(), "timeout_ms 未生效（仍在等待）"
    assert "21" in _REACHED, "超时后应走 fail 分支"
    assert elapsed < 1.0, f"超时 100ms 但实际耗时 {elapsed*1000:.0f}ms，timeout 未生效"


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            print(f"[RUN] {name}")
            try:
                fn()
                print("  PASS\n")
            except AssertionError as e:
                failed += 1
                print(f"  FAIL: {e}\n")
            except Exception as e:
                failed += 1
                import traceback
                traceback.print_exc()
                print(f"  ERROR: {e}\n")
    print("全部通过" if failed == 0 else f"{failed} 项失败")
    sys.exit(1 if failed else 0)
