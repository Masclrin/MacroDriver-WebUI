import unittest
import threading
import time
from automation.compiler import parse_graph, ExecGraph, ExecNode
from automation.engine import ExecContext, TaskPool, _resolve_value


class TestCompilerParseGraph(unittest.TestCase):

    def test_empty_graph(self):
        graph = parse_graph({"graph": {"nodes": [], "connections": []}})
        self.assertIsNone(graph.entry_node_id)
        self.assertEqual(len(graph.nodes), 0)
        self.assertEqual(len(graph.monitor_entry_ids), 0)

    def test_start_node_as_entry(self):
        data = {
            "graph": {
                "nodes": [
                    {"id": "1", "type": "flow/start", "params": {}, "position": {"x": 0, "y": 0}},
                    {"id": "2", "type": "action/wait", "params": {"duration": 100}, "position": {"x": 200, "y": 0}},
                ],
                "connections": [
                    {"from": {"node": "1", "port": "next"}, "to": {"node": "2", "port": "in"}, "type": "flow"},
                ],
            }
        }
        graph = parse_graph(data)
        self.assertEqual(graph.entry_node_id, "1")
        self.assertEqual(len(graph.errors), 0)

    def test_multiple_start_nodes_error(self):
        data = {
            "graph": {
                "nodes": [
                    {"id": "1", "type": "flow/start", "params": {}, "position": {"x": 0, "y": 0}},
                    {"id": "2", "type": "flow/start", "params": {}, "position": {"x": 0, "y": 200}},
                ],
                "connections": [],
            }
        }
        graph = parse_graph(data)
        self.assertTrue(any("2 个开始节点" in e for e in graph.errors))

    def test_end_node_flow_output_error(self):
        data = {
            "graph": {
                "nodes": [
                    {"id": "1", "type": "flow/start", "params": {}, "position": {"x": 0, "y": 0}},
                    {"id": "2", "type": "flow/end", "params": {}, "position": {"x": 200, "y": 0}},
                    {"id": "3", "type": "action/wait", "params": {"duration": 100}, "position": {"x": 400, "y": 0}},
                ],
                "connections": [
                    {"from": {"node": "1", "port": "next"}, "to": {"node": "2", "port": "in"}, "type": "flow"},
                    {"from": {"node": "2", "port": "next"}, "to": {"node": "3", "port": "in"}, "type": "flow"},
                ],
            }
        }
        graph = parse_graph(data)
        self.assertTrue(any("结束节点" in e and "流程输出" in e for e in graph.errors))

    def test_fallback_entry_without_start_node(self):
        data = {
            "graph": {
                "nodes": [
                    {"id": "1", "type": "action/wait", "params": {"duration": 100}, "position": {"x": 0, "y": 0}},
                ],
                "connections": [],
            }
        }
        graph = parse_graph(data)
        self.assertEqual(graph.entry_node_id, "1")
        self.assertTrue(any("开始节点" in w for w in graph.warnings))

    def test_pure_data_node_not_as_entry(self):
        data = {
            "graph": {
                "nodes": [
                    {"id": "1", "type": "utility/const_number", "params": {"value": 42}, "position": {"x": 0, "y": 0}},
                    {"id": "2", "type": "action/wait", "params": {"duration": 100}, "position": {"x": 200, "y": 0}},
                ],
                "connections": [],
            }
        }
        graph = parse_graph(data)
        self.assertEqual(graph.entry_node_id, "2")

    def test_monitor_entry_ids_collected_by_type(self):
        data = {
            "graph": {
                "nodes": [
                    {"id": "1", "type": "flow/start", "params": {}, "position": {"x": 0, "y": 0}},
                    {"id": "2", "type": "monitor/monitor_color", "params": {}, "position": {"x": 200, "y": 0}},
                    {"id": "3", "type": "monitor/monitor_timer", "params": {}, "position": {"x": 200, "y": 200}},
                ],
                "connections": [],
            }
        }
        graph = parse_graph(data)
        self.assertIn("2", graph.monitor_entry_ids)
        self.assertIn("3", graph.monitor_entry_ids)
        self.assertEqual(len(graph.monitor_entry_ids), 2)

    def test_goto_target_validation(self):
        data = {
            "graph": {
                "nodes": [
                    {"id": "1", "type": "flow/start", "params": {}, "position": {"x": 0, "y": 0}},
                    {"id": "2", "type": "control/goto", "params": {"target_node_id": "999"}, "position": {"x": 200, "y": 0}},
                ],
                "connections": [
                    {"from": {"node": "1", "port": "next"}, "to": {"node": "2", "port": "in"}, "type": "flow"},
                ],
            }
        }
        graph = parse_graph(data)
        self.assertTrue(any("不存在" in e for e in graph.errors))

    def test_goto_to_start_node_error(self):
        data = {
            "graph": {
                "nodes": [
                    {"id": "1", "type": "flow/start", "params": {}, "position": {"x": 0, "y": 0}},
                    {"id": "2", "type": "control/goto", "params": {"target_node_id": "1"}, "position": {"x": 200, "y": 0}},
                ],
                "connections": [
                    {"from": {"node": "1", "port": "next"}, "to": {"node": "2", "port": "in"}, "type": "flow"},
                ],
            }
        }
        graph = parse_graph(data)
        self.assertTrue(any("开始节点" in e for e in graph.errors))

    def test_goto_in_monitor_error(self):
        data = {
            "graph": {
                "nodes": [
                    {"id": "1", "type": "flow/start", "params": {}, "position": {"x": 0, "y": 0}},
                    {"id": "2", "type": "monitor/monitor_timer", "params": {}, "position": {"x": 200, "y": 0}},
                    {"id": "3", "type": "control/goto", "params": {"target_node_id": "1"}, "position": {"x": 400, "y": 0}},
                ],
                "connections": [
                    {"from": {"node": "2", "port": "trigger"}, "to": {"node": "3", "port": "in"}, "type": "flow"},
                ],
            }
        }
        graph = parse_graph(data)
        self.assertTrue(any("监视器" in e and "跳转" in e for e in graph.errors))

    def test_loop_while_external_cond_warning(self):
        data = {
            "graph": {
                "nodes": [
                    {"id": "1", "type": "flow/start", "params": {}, "position": {"x": 0, "y": 0}},
                    {"id": "2", "type": "detection/check_color", "params": {}, "position": {"x": 200, "y": 0}},
                    {"id": "3", "type": "control/loop_while", "params": {}, "position": {"x": 400, "y": 0}},
                ],
                "connections": [
                    {"from": {"node": "1", "port": "next"}, "to": {"node": "3", "port": "in"}, "type": "flow"},
                    {"from": {"node": "2", "port": "result"}, "to": {"node": "3", "port": "cond"}, "type": "data"},
                ],
            }
        }
        graph = parse_graph(data)
        self.assertTrue(any("循环体外部" in w for w in graph.warnings))

    def test_data_inputs_parsed(self):
        data = {
            "graph": {
                "nodes": [
                    {"id": "1", "type": "utility/const_number", "params": {"value": 10}, "position": {"x": 0, "y": 0}},
                    {"id": "2", "type": "control/if_else", "params": {}, "position": {"x": 200, "y": 0}},
                ],
                "connections": [
                    {"from": {"node": "1", "port": "value"}, "to": {"node": "2", "port": "cond"}, "type": "data"},
                ],
            }
        }
        graph = parse_graph(data)
        cond_inputs = graph.nodes["2"].get_data_inputs("cond")
        self.assertEqual(len(cond_inputs), 1)
        self.assertEqual(cond_inputs[0]["source_node_id"], "1")
        self.assertEqual(cond_inputs[0]["source_port"], "value")


class TestExecContext(unittest.TestCase):

    def test_thread_safe_variables(self):
        stop_event = threading.Event()
        graph = ExecGraph()
        ctx = ExecContext(graph, stop_event)

        results = []
        errors = []

        def writer():
            try:
                for i in range(100):
                    ctx.safe_set_variable("counter", i)
                    time.sleep(0.0001)
                results.append("writer_done")
            except Exception as e:
                errors.append(str(e))

        def reader():
            try:
                for i in range(100):
                    val = ctx.safe_get_variable("counter")
                    time.sleep(0.0001)
                results.append("reader_done")
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)
        self.assertEqual(len(errors), 0)
        self.assertIn("writer_done", results)
        self.assertIn("reader_done", results)

    def test_error_tracking(self):
        stop_event = threading.Event()
        graph = ExecGraph()
        ctx = ExecContext(graph, stop_event)

        ctx.log_error("test error", node_id="n1", error_type="system")
        errors = ctx.get_errors()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["message"], "test error")
        self.assertEqual(errors[0]["node_id"], "n1")
        self.assertEqual(errors[0]["type"], "system")

        ctx.clear_errors()
        self.assertEqual(len(ctx.get_errors()), 0)

    def test_variable_init_from_graph(self):
        graph = ExecGraph()
        graph.variables = {"count": {"init": 0}, "name": {"init": "hello"}}
        stop_event = threading.Event()
        ctx = ExecContext(graph, stop_event)
        self.assertEqual(ctx.variables.get("count"), 0)
        self.assertEqual(ctx.variables.get("name"), "hello")


class TestTaskPool(unittest.TestCase):

    def test_task_status_unknown(self):
        pool = TaskPool()
        self.assertEqual(pool.get_status("nonexistent"), "unknown")

    def test_stop_nonexistent_task(self):
        pool = TaskPool()
        self.assertFalse(pool.stop("nonexistent"))


class TestResolveValue(unittest.TestCase):

    def test_plain_number(self):
        stop_event = threading.Event()
        graph = ExecGraph()
        ctx = ExecContext(graph, stop_event)
        self.assertEqual(_resolve_value(42, ctx), 42)

    def test_variable_substitution(self):
        stop_event = threading.Event()
        graph = ExecGraph()
        ctx = ExecContext(graph, stop_event)
        ctx.variables["x"] = 10
        result = _resolve_value("${x}", ctx)
        self.assertEqual(result, 10)

    def test_no_substitution(self):
        stop_event = threading.Event()
        graph = ExecGraph()
        ctx = ExecContext(graph, stop_event)
        result = _resolve_value("hello", ctx)
        self.assertEqual(result, "hello")


class TestExecNode(unittest.TestCase):

    def test_get_data_inputs(self):
        node = ExecNode(id="1", type="test", params={}, position={})
        node.data_inputs = {
            "cond": [{"source_node_id": "2", "source_port": "result"}],
        }
        result = node.get_data_inputs("cond")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_node_id"], "2")

    def test_get_data_inputs_empty(self):
        node = ExecNode(id="1", type="test", params={}, position={})
        result = node.get_data_inputs("nonexistent")
        self.assertEqual(len(result), 0)


if __name__ == "__main__":
    unittest.main()
