import sys
sys.path.insert(0, r"d:\Rin\宏驱动 webui 1.3 - 副本")

from webui_backend.plugin_registry import PluginRegistry, register_builtin_nodes
register_builtin_nodes()
payload = PluginRegistry.get_frontend_payload()
print(f"Registered {len(payload['nodes'])} node types")
print("Node types:", list(payload['nodes'].keys()))

for ntype, ndef in payload['nodes'].items():
    schema = ndef.get('params_schema', {})
    inputs = ndef.get('inputs', [])
    outputs = ndef.get('outputs', [])
    handler = PluginRegistry.get_node(ntype).get('handler', 'MISSING')
    print(f"  {ntype}: params={len(schema)} inputs={len(inputs)} outputs={len(outputs)} handler={handler}")
