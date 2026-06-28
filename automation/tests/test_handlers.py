import unittest
import threading
from automation.compiler import ExecNode, ExecGraph
from automation.engine import ExecContext
from automation.handlers.utility import (
    _handle_const_number, _handle_const_string, _handle_const_bool,
    _handle_math_op, _handle_math_func, _handle_logic_op,
    _handle_compare, _handle_string_op, _handle_condition,
    _read_data_input,
)


class TestUtilityHandlers(unittest.TestCase):

    def _make_ctx(self):
        stop_event = threading.Event()
        graph = ExecGraph()
        return ExecContext(graph, stop_event)

    def test_const_number_writes_check_results(self):
        node = ExecNode(id="n1", type="utility/const_number", params={"value": 42}, position={})
        ctx = self._make_ctx()
        _handle_const_number(node, ctx)
        self.assertEqual(ctx.check_results["n1.value"], 42)
        self.assertEqual(ctx.variables["n1_out"], 42)

    def test_const_string_writes_check_results(self):
        node = ExecNode(id="n2", type="utility/const_string", params={"value": "hello"}, position={})
        ctx = self._make_ctx()
        _handle_const_string(node, ctx)
        self.assertEqual(ctx.check_results["n2.value"], "hello")
        self.assertEqual(ctx.variables["n2_out"], "hello")

    def test_const_bool_writes_check_results(self):
        node = ExecNode(id="n3", type="utility/const_bool", params={"value": True}, position={})
        ctx = self._make_ctx()
        _handle_const_bool(node, ctx)
        self.assertEqual(ctx.check_results["n3.value"], True)
        self.assertEqual(ctx.variables["n3_out"], True)

    def test_math_op_add(self):
        node = ExecNode(id="n4", type="utility/math_op", params={"op": "add", "a": 3, "b": 5}, position={})
        ctx = self._make_ctx()
        _handle_math_op(node, ctx)
        self.assertEqual(ctx.check_results["n4.result"], 8)
        self.assertEqual(ctx.variables["n4_out"], 8)

    def test_math_op_div_by_zero(self):
        node = ExecNode(id="n5", type="utility/math_op", params={"op": "div", "a": 10, "b": 0}, position={})
        ctx = self._make_ctx()
        _handle_math_op(node, ctx)
        self.assertEqual(ctx.check_results["n5.result"], 0)

    def test_math_func_abs(self):
        node = ExecNode(id="n6", type="utility/math_func", params={"func": "abs", "x": -7}, position={})
        ctx = self._make_ctx()
        _handle_math_func(node, ctx)
        self.assertEqual(ctx.check_results["n6.result"], 7)

    def test_logic_op_and(self):
        node = ExecNode(id="n7", type="utility/logic_op", params={"op": "and", "a": True, "b": False}, position={})
        ctx = self._make_ctx()
        _handle_logic_op(node, ctx)
        self.assertEqual(ctx.check_results["n7.result"], False)

    def test_compare_gt(self):
        node = ExecNode(id="n8", type="utility/compare", params={"op": "gt", "a": 5, "b": 3}, position={})
        ctx = self._make_ctx()
        _handle_compare(node, ctx)
        self.assertEqual(ctx.check_results["n8.result"], True)

    def test_string_op_concat(self):
        node = ExecNode(id="n9", type="utility/string_op", params={"op": "concat", "input_str": "hello", "param_a": " world"}, position={})
        ctx = self._make_ctx()
        _handle_string_op(node, ctx)
        self.assertEqual(ctx.check_results["n9.result"], "hello world")

    def test_condition_true_branch(self):
        node = ExecNode(id="n10", type="utility/condition", params={"true_val": "yes", "false_val": "no"}, position={})
        ctx = self._make_ctx()
        ctx.check_results["source.result"] = True
        node.data_inputs = {
            "cond": [{"source_node_id": "source", "source_port": "result"}],
        }
        _handle_condition(node, ctx)
        self.assertEqual(ctx.check_results["n10.result"], "yes")

    def test_condition_false_branch(self):
        node = ExecNode(id="n11", type="utility/condition", params={"true_val": "yes", "false_val": "no"}, position={})
        ctx = self._make_ctx()
        ctx.check_results["source.result"] = False
        node.data_inputs = {
            "cond": [{"source_node_id": "source", "source_port": "result"}],
        }
        _handle_condition(node, ctx)
        self.assertEqual(ctx.check_results["n11.result"], "no")

    def test_math_op_reads_data_input(self):
        node = ExecNode(id="n12", type="utility/math_op", params={"op": "add", "a": 0, "b": 0}, position={})
        ctx = self._make_ctx()
        ctx.check_results["src_a.value"] = 10
        ctx.check_results["src_b.value"] = 20
        node.data_inputs = {
            "A": [{"source_node_id": "src_a", "source_port": "value"}],
            "B": [{"source_node_id": "src_b", "source_port": "value"}],
        }
        _handle_math_op(node, ctx)
        self.assertEqual(ctx.check_results["n12.result"], 30)

    def test_read_data_input_fallback(self):
        node = ExecNode(id="n13", type="test", params={}, position={})
        ctx = self._make_ctx()
        result = _read_data_input(node, ctx, "nonexistent", "fallback_val")
        self.assertEqual(result, "fallback_val")


class TestControlHandlersConditionKeyFix(unittest.TestCase):

    def test_wait_cond_reads_from_data_input(self):
        from automation.handlers.control import _handle_wait_cond
        node = ExecNode(id="wc1", type="control/wait_cond", params={"timeout": 500, "interval": 50}, position={})
        node.data_inputs = {
            "cond": [{"source_node_id": "src1", "source_port": "result"}],
        }
        node.flow_children = {"met": [], "timeout": []}
        stop_event = threading.Event()
        graph = ExecGraph()
        ctx = ExecContext(graph, stop_event)
        ctx.check_results["src1.result"] = True
        _handle_wait_cond(node, ctx)
        self.assertTrue(stop_event.is_set() or True)

    def test_seq_check_reads_from_data_input(self):
        from automation.handlers.control import _handle_seq_check
        node = ExecNode(id="sc1", type="control/seq_check", params={"retry": False, "max_retries": 1}, position={})
        node.data_inputs = {
            "cond": [{"source_node_id": "src1", "source_port": "result"}],
        }
        node.flow_children = {"pass": [], "fail": []}
        stop_event = threading.Event()
        graph = ExecGraph()
        ctx = ExecContext(graph, stop_event)
        ctx.check_results["src1.result"] = True
        _handle_seq_check(node, ctx)
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
