from dataclasses import dataclass, field
from automation.registry import PluginRegistry


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
    monitor_entry_ids: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)


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

    start_nodes = [nid for nid, node in graph.nodes.items() if node.type == "flow/start"]
    end_nodes = [nid for nid, node in graph.nodes.items() if node.type == "flow/end"]

    if start_nodes:
        if len(start_nodes) > 1:
            graph.errors.append(f"图中存在 {len(start_nodes)} 个开始节点，必须且只能有 1 个")
        graph.entry_node_id = start_nodes[0]

        for nid in start_nodes:
            node = graph.nodes[nid]
            if node.data_inputs:
                graph.errors.append(f"开始节点 {nid} 不允许有数据输入连接")
            if any(port != "next" for port in node.flow_children.keys()):
                graph.errors.append(f"开始节点 {nid} 只能有 'next' 流程输出端口")

        for nid in end_nodes:
            node = graph.nodes[nid]
            if node.flow_children:
                graph.errors.append(f"结束节点 {nid} 不允许有流程输出连接")
            if node.data_inputs:
                graph.errors.append(f"结束节点 {nid} 不允许有数据输入连接")
    else:
        entry_candidates = [nid for nid in graph.nodes if nid not in has_flow_input]
        filtered_candidates = []
        for nid in entry_candidates:
            node = graph.nodes[nid]
            if node.type.startswith("utility/const_") or node.type in ("utility/comment", "utility/group", "utility/bookmark"):
                continue
            node_def = PluginRegistry.get_node(node.type)
            if node_def:
                has_flow_output = any(p.get("type") == "flow" for p in node_def.get("outputs", []))
                has_flow_input_port = any(p.get("type") == "flow" for p in node_def.get("inputs", []))
                if has_flow_input_port and not has_flow_output:
                    continue
                if not has_flow_output and not node.type.startswith("monitor/"):
                    continue
            filtered_candidates.append(nid)

        if filtered_candidates:
            action_nodes = []
            monitor_nodes = []
            other_nodes = []
            for nid in filtered_candidates:
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
        graph.warnings.append("图中缺少开始节点(flow/start)，建议添加以明确执行入口")

    graph.monitor_entry_ids = [nid for nid, node in graph.nodes.items()
                               if node.type.startswith("monitor/")]

    for nid, node in graph.nodes.items():
        if node.type == "control/goto":
            target_id = node.params.get("target_node_id", "")
            if not target_id:
                graph.errors.append(f"跳转节点 {nid} 未指定目标节点ID")
            elif target_id not in graph.nodes:
                graph.errors.append(f"跳转节点 {nid} 的目标节点 '{target_id}' 不存在于图中")
            elif graph.nodes[target_id].type == "flow/start":
                graph.errors.append(f"跳转节点 {nid} 不允许跳转到开始节点")

    import re
    bookmark_names = set()
    for nid, node in graph.nodes.items():
        if node.type == "utility/bookmark":
            bm_name = node.params.get("name", "")
            if bm_name:
                bookmark_names.add(bm_name)

    bookmark_ref_pattern = re.compile(r'@([\w\u4e00-\u9fff]+)\.(x|y|w|h|mode|hwnd_var|remark|name)')
    for nid, node in graph.nodes.items():
        if node.type == "utility/bookmark":
            continue
        for pkey, pval in node.params.items():
            if not isinstance(pval, str):
                continue
            for match in bookmark_ref_pattern.finditer(pval):
                ref_name = match.group(1)
                if ref_name not in bookmark_names:
                    graph.errors.append(
                        f"节点 {nid}({node.type}) 引用了不存在的坐标书签 '@{ref_name}'"
                    )

    var_ref_pattern = re.compile(r'\$\{([^}]+)\}')
    for nid, node in graph.nodes.items():
        for pkey, pval in node.params.items():
            if not isinstance(pval, str):
                continue
            for match in var_ref_pattern.finditer(pval):
                ref = match.group(1)
                if '.' in ref:
                    parts = ref.split('.', 1)
                    first_part = parts[0]
                    if first_part in bookmark_names:
                        second_part = parts[1]
                        valid_bm_params = {'x', 'y', 'w', 'h', 'mode', 'hwnd_var', 'remark', 'name'}
                        if second_part not in valid_bm_params:
                            graph.warnings.append(
                                f"节点 {nid}({node.type}) 引用了书签 '{first_part}' 的无效参数 '{second_part}'"
                            )
                    elif first_part not in graph.nodes:
                        graph.warnings.append(
                            f"节点 {nid}({node.type}) 引用了不存在的节点 '{first_part}' 的输出"
                        )

    for mid in graph.monitor_entry_ids:
        _check_goto_in_flow(graph, mid, set(), graph.errors)

    for nid, node in graph.nodes.items():
        if node.type == "control/loop_while":
            cond_sources = node.data_inputs.get("cond", [])
            for src in cond_sources:
                src_node = graph.nodes.get(src["source_node_id"])
                if src_node and not src_node.type.startswith("monitor/"):
                    body_children = set()
                    _collect_flow_children(graph, nid, "body", set(), body_children)
                    if src["source_node_id"] not in body_children:
                        graph.warnings.append(
                            f"条件循环 {nid} 的条件输入来自循环体外部节点 {src['source_node_id']}，"
                            f"条件值在循环中不会更新，可能导致无限循环或立即退出"
                        )

    return graph


def _check_goto_in_flow(graph, node_id, visited, errors):
    if node_id in visited:
        return
    visited.add(node_id)
    node = graph.nodes.get(node_id)
    if node is None:
        return
    if node.type == "control/goto":
        errors.append(f"监视器节点的触发分支中包含跳转节点 {node_id}，监视器中不允许使用跳转")
        return
    for port_name in node.flow_children:
        for child_id in node.flow_children[port_name]:
            _check_goto_in_flow(graph, child_id, visited, errors)


def _collect_flow_children(graph, node_id, port_name, visited, result):
    children = graph.nodes[node_id].flow_children.get(port_name, [])
    for child_id in children:
        if child_id in visited:
            continue
        visited.add(child_id)
        result.add(child_id)
        child_node = graph.nodes.get(child_id)
        if child_node:
            for pn in child_node.flow_children:
                _collect_flow_children(graph, child_id, pn, visited, result)


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
