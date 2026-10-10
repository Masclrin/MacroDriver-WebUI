"""自动化执行引擎实时性回归测试。

覆盖本项目在原神实时战斗场景下的三个关键缺陷：
  1. goto 循环只能执行一圈（executed_set 只 discard 目标节点）
  2. goto 循环导致递归栈随圈数线性增长，最终 RecursionError
  3. _execute_flow / _reset_body_nodes 中的 O(M) / O(M*B) 全量扫描

运行： python -m automation.tests.test_engine_realtime
"""
import sys
import threading
import time

from automation.compiler import ExecGraph, ExecNode
from automation.engine import ExecContext, _GotoSignal, _drive_with_goto_trampoline
from automation.handlers import NODE_HANDLERS
from automation.registry import PluginRegistry

# 计数器：每个测试节点执行次数
_COUNTS = {}


def _make_test_handler(name):
    def _handler(node, ctx):
        from automation.engine import _execute_flow
        _COUNTS[name] = _COUNTS.get(name, 0) + 1
        # 到达上限后置 stop，让执行优雅结束
        limit = int(node.params.get("_stop_after", 0) or 0)
        if limit and _COUNTS[name] >= limit:
            ctx.stop_event.set()
            return
        # 与真实 handler 一致：推进 next 端口
        _execute_flow(node.id, "next", ctx)
    return _handler


def _register(type_name, handler_name, outputs=None):
    if handler_name not in NODE_HANDLERS:
        NODE_HANDLERS[handler_name] = _make_test_handler(handler_name)
    if PluginRegistry.get_node(type_name) is None:
        PluginRegistry.register_node({
            "type": type_name,
            "category": "test",
            "display_name": type_name,
            "color": "#888",
            "inputs": [],
            "outputs": outputs or [{"name": "next"}],
            "params_schema": {},
            "handler": handler_name,
        })


def _build_goto_loop():
    """start(1) -> tick(2) -> goto(1)"""
    g = ExecGraph()
    g.nodes["1"] = ExecNode(id="1", type="test/tick", params={"_stop_after": 200},
                            position={}, flow_children={"next": ["2"]})
    g.nodes["2"] = ExecNode(id="2", type="test/goto", params={"target_node_id": "1"},
                            position={}, flow_children={"next": []})
    g.entry_node_id = "1"
    return g


def _run(graph, timeout=30.0):
    stop = threading.Event()
    ctx = ExecContext(graph, stop)
    ctx.node_retry_count = 0
    ctx.node_retry_delay_ms = 0
    t = threading.Thread(target=_drive_with_goto_trampoline, args=(graph.entry_node_id, ctx))
    t.daemon = True
    t0 = time.perf_counter()
    t.start()
    t.join(timeout)
    return time.perf_counter() - t0, t.is_alive()


def test_goto_loop_runs_multiple_iterations():
    """goto 回跳必须能真正形成循环（修复前第二圈即终止）。"""
    _register("test/tick", "tick")
    _register("test/goto", "goto")
    _COUNTS.clear()
    # 直接复用真实 goto 处理器语义：它只设置 ctx._goto_target
    from automation.handlers.control import _handle_goto
    NODE_HANDLERS["goto"] = _handle_goto

    graph = _build_goto_loop()
    elapsed, alive = _run(graph)
    assert not alive, "执行线程未在超时内结束（可能死循环）"
    n = _COUNTS.get("tick", 0)
    print(f"  goto 循环执行次数 = {n}, 耗时 {elapsed*1000:.1f}ms")
    assert n >= 100, f"goto 循环只执行了 {n} 次，期望 >=100（说明 goto 未形成循环）"


def test_goto_loop_stack_does_not_grow():
    """goto 循环 1000+ 圈不得 RecursionError / 栈溢出。"""
    _register("test/tick", "tick")
    from automation.handlers.control import _handle_goto
    NODE_HANDLERS["goto"] = _handle_goto
    _COUNTS.clear()

    g = ExecGraph()
    g.nodes["1"] = ExecNode(id="1", type="test/tick", params={"_stop_after": 2000},
                            position={}, flow_children={"next": ["2"]})
    g.nodes["2"] = ExecNode(id="2", type="test/goto", params={"target_node_id": "1"},
                            position={}, flow_children={"next": []})
    g.entry_node_id = "1"
    elapsed, alive = _run(g, timeout=60)
    assert not alive, "执行线程未在超时内结束"
    n = _COUNTS.get("tick", 0)
    print(f"  长循环执行次数 = {n}, 耗时 {elapsed*1000:.1f}ms")
    assert n >= 1500, f"长 goto 循环仅执行 {n} 次，疑似栈溢出被吞"


def test_flow_transfer_is_not_quadratic():
    """流程转移开销不应随 check_results 规模线性恶化（修复前 O(M) 全量扫描）。"""
    _register("test/tick", "tick")
    _COUNTS.clear()

    def bench(n_results):
        g = ExecGraph()
        prev = None
        for i in range(300):
            nid = str(i)
            g.nodes[nid] = ExecNode(id=nid, type="test/tick", params={}, position={},
                                    flow_children={"next": [str(i + 1)] if i < 299 else []})
            prev = nid
        g.entry_node_id = "0"
        stop = threading.Event()
        ctx = ExecContext(g, stop)
        ctx.node_retry_count = 0
        ctx.node_retry_delay_ms = 0
        for i in range(n_results):
            ctx.check_results[f"x{i}.out"] = {"value": i}
        t0 = time.perf_counter()
        _drive_with_goto_trampoline("0", ctx)
        return (time.perf_counter() - t0) * 1000

    small = bench(0)
    large = bench(5000)
    print(f"  300 节点链: check_results=0 -> {small:.2f}ms, =5000 -> {large:.2f}ms")
    # 修复前 5000 条时约 45ms+（300 次转移 × 150us），修复后应与规模无关
    assert large < small + 15, (
        f"流程转移仍随 check_results 规模恶化: {small:.2f}ms -> {large:.2f}ms"
    )


def test_shared_frame_cache_reuses_one_capture_per_iteration():
    """同一循环迭代内多个检测节点应共用一次截图。"""
    from automation.detection.capture_manager import CaptureManager

    cm = CaptureManager()
    region = [0, 0, 640, 480]
    cm.invalidate_frame_cache()
    methods = [cm.capture(region, prefer_dxgi=False)[1] for _ in range(5)]
    hits = sum(1 for m in methods if m == "共享帧缓存")
    print(f"  5 次截图命中共享缓存 {hits} 次: {methods}")
    assert hits == 4, f"预期 1 次真实截图 + 4 次缓存命中，实际 {methods}"

    # 新迭代必须重新截图，不能永远复用同一帧（否则画面冻结）
    cm.invalidate_frame_cache()
    m = cm.capture(region, prefer_dxgi=False)[1]
    print(f"  新迭代首次截图方式: {m}")
    assert m != "共享帧缓存", "新循环迭代仍命中缓存，会导致画面冻结"


def test_polling_detection_never_sees_stale_frame():
    """阻塞轮询检测必须每轮取新帧，不能被共享帧缓存黏住（战斗实时性红线）。"""
    import time as _time
    from automation.detection.capture_manager import CaptureManager

    cm = CaptureManager()
    region = [0, 0, 320, 240]
    cm.set_frame_ttl_ms(50.0)  # 故意放大 TTL 以复现"高频轮询被缓存黏住"的最坏情况

    # 反例：轮询循环内不做失效 —— 缓存会连续命中同一帧，等于盯着旧画面
    cm.invalidate_frame_cache()
    stale = 0
    for _ in range(8):
        method = cm.capture(region, prefer_dxgi=False)[1]
        if method == "共享帧缓存":
            stale += 1
        _time.sleep(0.005)
    print(f"  未作废(反例): 8 次轮询看到旧帧 {stale} 次")
    assert stale > 0, "用例前提不成立：未触发缓存复用"

    # 正例：每轮失效（即 _invalidate_frame 的行为）—— 每次都取新帧
    fresh = 0
    for _ in range(8):
        cm.invalidate_frame_cache()
        method = cm.capture(region, prefer_dxgi=False)[1]
        if method == "共享帧缓存":
            fresh += 1
        _time.sleep(0.005)
    print(f"  每轮作废(正例): 8 次轮询看到旧帧 {fresh} 次")
    assert fresh == 0, f"轮询仍看到旧帧 {fresh} 次，实时性被破坏"


def test_frame_diff_threshold_is_area_adaptive():
    """大区域+小目标场景下固定 2.0 阈值会永久漏检。"""
    from automation.handlers.detection import _frame_diff_threshold
    big_roi_small_target = _frame_diff_threshold((300, 500, 3), (40, 40, 3))
    print(f"  500x300 区域 + 40x40 目标 -> 阈值 {big_roi_small_target:.3f}")
    assert big_roi_small_target < 1.0, (
        f"阈值 {big_roi_small_target} 仍高于典型变化量(约0.64)，会永久漏检"
    )
    assert _frame_diff_threshold((120, 200, 3), (60, 60, 3)) <= 2.0


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            print(f"[RUN] {name}")
            try:
                fn()
                print(f"  PASS\n")
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
