import sys
sys.path.insert(0, r"d:\Rin\宏驱动 webui 1.3 - 副本")

from webui_backend.automation_compiler import parse_graph, serialize_graph, ExecGraph, ExecNode
from webui_backend.automation_engine import NODE_HANDLERS, execute_graph
from webui_backend.plugin_registry import register_builtin_nodes

register_builtin_nodes()

print("=== Compiler Round-Trip Test ===")
test_data = {
    "variables": {"count": {"init": 0}},
    "settings": {"profile": "standard"},
    "graph": {
        "nodes": [
            {"id": 1, "type": "action/wait", "params": {"duration": 1000}, "position": {"x": 0, "y": 0}},
            {"id": 2, "type": "action/key_action", "params": {"key": "a", "action": "press", "delay": 0}, "position": {"x": 200, "y": 0}},
        ],
        "connections": [
            {"id": "0", "from": {"node": 1, "port": "next"}, "to": {"node": 2, "port": "in"}, "type": "flow"}
        ]
    }
}

graph = parse_graph(test_data)
print(f"Entry node: {graph.entry_node_id}")
print(f"Nodes: {list(graph.nodes.keys())}")
print(f"Variables: {graph.variables}")

serialized = serialize_graph(graph)
print(f"Serialized nodes: {len(serialized['graph']['nodes'])}")
print(f"Serialized connections: {len(serialized['graph']['connections'])}")

graph2 = parse_graph(serialized)
print(f"Round-trip entry: {graph2.entry_node_id}")
print(f"Round-trip nodes: {list(graph2.nodes.keys())}")
print("Compiler round-trip: OK")

print("\n=== Engine Handler Check ===")
from webui_backend.plugin_registry import PluginRegistry
all_nodes = PluginRegistry.get_all_nodes()
missing_handlers = []
for ntype, ndef in all_nodes.items():
    handler_name = ndef.get("handler")
    if handler_name not in NODE_HANDLERS:
        missing_handlers.append(f"{ntype} -> {handler_name}")

if missing_handlers:
    print(f"MISSING HANDLERS ({len(missing_handlers)}):")
    for m in missing_handlers:
        print(f"  {m}")
else:
    print(f"All {len(all_nodes)} node handlers registered in NODE_HANDLERS")

print("\n=== Automation Bridge API Check ===")
from webui_backend.automation_bridge_api import AutomationApiMixin
methods = [m for m in dir(AutomationApiMixin) if not m.startswith('_')]
print(f"Exposed methods: {methods}")
