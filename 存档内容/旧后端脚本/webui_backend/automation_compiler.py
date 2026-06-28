# -*- coding: utf-8 -*-
"""
图解析器 — 将 JSON 格式的节点图解析为内存中的 ExecGraph 结构
"""
from dataclasses import dataclass, field


@dataclass
class ExecNode:
    id: str
    type: str
    params: dict
    position: dict
    flow_children: dict = field(default_factory=dict)
    data_inputs: dict = field(default_factory=dict)

    def get_flow_children(self, port_name):
        return self.flow_children.get(port_name, [])

    def get_data_inputs(self, port_name):
        return self.data_inputs.get(port_name, [])


@dataclass
class ExecGraph:
    nodes: dict = field(default_factory=dict)
    variables: dict = field(default_factory=dict)
    settings: dict = field(default_factory=dict)
    entry_node_id: str = None


def parse_graph(json_data: dict) -> ExecGraph:
    graph = ExecGraph()

    graph.variables = json_data.get("variables", {})
    graph.settings = json_data.get("settings", {})

    graph_nodes = json_data.get("graph", json_data).get("nodes", [])
    for node_json in graph_nodes:
        node = ExecNode(
            id=str(node_json["id"]),
            type=node_json["type"],
            params=node_json.get("params", {}),
            position=node_json.get("position", {"x": 0, "y": 0}),
        )
        graph.nodes[node.id] = node

    connections = json_data.get("graph", json_data).get("connections", [])
    has_flow_input = set()
    for conn in connections:
        from_node_id = str(conn["from"]["node"])
        from_port = conn["from"]["port"]
        to_node_id = str(conn["to"]["node"])
        to_port = conn["to"]["port"]
        conn_type = conn.get("type", "flow")

        from_node = graph.nodes.get(from_node_id)
        to_node = graph.nodes.get(to_node_id)
        if from_node is None or to_node is None:
            continue

        if conn_type == "flow":
            from_node.flow_children.setdefault(from_port, []).append(to_node_id)
            has_flow_input.add(to_node_id)
        elif conn_type == "data":
            to_node.data_inputs.setdefault(to_port, []).append({
                "source_node_id": from_node_id,
                "source_port": from_port,
            })

    entry_candidates = [nid for nid in graph.nodes if nid not in has_flow_input]
    if entry_candidates:
        action_nodes = []
        monitor_nodes = []
        other_nodes = []
        for nid in entry_candidates:
            node = graph.nodes[nid]
            if node.type.startswith("action/") or node.type.startswith("script_block/"):
                action_nodes.append(nid)
            elif node.type.startswith("monitor/"):
                monitor_nodes.append(nid)
            else:
                other_nodes.append(nid)
        if action_nodes:
            graph.entry_node_id = action_nodes[0]
        elif other_nodes:
            graph.entry_node_id = other_nodes[0]
        elif monitor_nodes:
            graph.entry_node_id = monitor_nodes[0]
        graph.monitor_entry_ids = monitor_nodes

    return graph


def serialize_graph(graph: ExecGraph) -> dict:
    nodes = []
    for node in graph.nodes.values():
        nodes.append({
            "id": node.id,
            "type": node.type,
            "params": node.params,
            "position": node.position,
        })

    connections = []
    conn_id = 0
    for node in graph.nodes.values():
        for port_name, child_ids in node.flow_children.items():
            for child_id in child_ids:
                connections.append({
                    "id": str(conn_id),
                    "from": {"node": node.id, "port": port_name},
                    "to": {"node": child_id, "port": "in"},
                    "type": "flow",
                })
                conn_id += 1
        for port_name, sources in node.data_inputs.items():
            for src in sources:
                connections.append({
                    "id": str(conn_id),
                    "from": {"node": src["source_node_id"], "port": src["source_port"]},
                    "to": {"node": node.id, "port": port_name},
                    "type": "data",
                })
                conn_id += 1

    return {
        "variables": graph.variables,
        "settings": graph.settings,
        "graph": {
            "nodes": nodes,
            "connections": connections,
        },
    }
