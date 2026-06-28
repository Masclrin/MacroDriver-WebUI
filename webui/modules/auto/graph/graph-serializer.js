import { _currentScriptName } from '../app/editor-state.js';

export function serializeGraph() {
  var nodes = window.AutomationCore.getNodes();
  var connections = window.AutomationCore.getConnections();
  var annotations = window.AutomationCore.getAnnotations();
  var groups = window.AutomationCore.getGroups();
  if (nodes.length === 0 && connections.length === 0 && annotations.length === 0 && groups.length === 0) return null;

  var outNodes = [];
  for (var i = 0; i < nodes.length; i++) {
    var node = nodes[i];
    var outNode = {
      id: String(node.id),
      type: node._defKey || node.type,
      position: { x: Math.round(node.pos[0]), y: Math.round(node.pos[1]) },
      params: JSON.parse(JSON.stringify(node.properties || {})),
    };
    if (node._customName) {
      outNode.customName = node._customName;
    }
    outNodes.push(outNode);
  }

  var outConns = [];
  for (var j = 0; j < connections.length; j++) {
    var link = connections[j];
    if (!link) continue;
    var originNode = window.AutomationCore.lgGraphObj.getNodeById(link.origin_id);
    var targetNode = window.AutomationCore.lgGraphObj.getNodeById(link.target_id);
    if (!originNode || !targetNode) continue;
    var output = (link.origin_slot < originNode.outputs.length) ? originNode.outputs[link.origin_slot] : null;
    var linkType = (output && output.type === 'flow') ? 'flow' : 'data';
    var fromPortKey = (output && output._portKey) || '';
    if (!fromPortKey && output) {
      var fromDef = window.AutomationNodes.getNodeDef(originNode._defKey);
      if (fromDef && fromDef.outputs && fromDef.outputs[link.origin_slot]) {
        fromPortKey = fromDef.outputs[link.origin_slot].name;
      }
    }
    var toInput = (link.target_slot >= 0 && link.target_slot < targetNode.inputs.length) ? targetNode.inputs[link.target_slot] : null;
    var toPortKey = (toInput && toInput._portKey) || '';
    if (!toPortKey && toInput) {
      var toDef = window.AutomationNodes.getNodeDef(targetNode._defKey);
      if (toDef && toDef.inputs && toDef.inputs[link.target_slot]) {
        toPortKey = toDef.inputs[link.target_slot].name;
      }
    }
    outConns.push({
      id: String(link.id),
      from: { node: String(link.origin_id), port: fromPortKey || String(link.origin_slot) },
      to: { node: String(link.target_id), port: toPortKey || String(link.target_slot) },
      type: linkType,
    });
  }

  var outAnnotations = [];
  for (var a = 0; a < annotations.length; a++) {
    var an = annotations[a];
    var anObj = {
      id: an.id,
      position: { x: Math.round(an.pos[0]), y: Math.round(an.pos[1]) },
      text: an.text,
      color: an.color,
    };
    if (an.bgColor) anObj.bgColor = an.bgColor;
    if (an.collapsed) anObj.collapsed = true;
    outAnnotations.push(anObj);
  }

  var outGroups = [];
  for (var g = 0; g < groups.length; g++) {
    var gp = groups[g];
    var gpObj = {
      id: gp.id,
      position: { x: Math.round(gp.pos[0]), y: Math.round(gp.pos[1]) },
      size: { w: Math.round(gp.size[0]), h: Math.round(gp.size[1]) },
      title: gp.title,
      color: gp.color,
    };
    if (gp.bgColor) gpObj.bgColor = gp.bgColor;
    outGroups.push(gpObj);
  }

  var viewport = window.AutomationCore.getViewportOffset();
  var vpScale = window.AutomationCore.getViewportScale();

  return {
    meta: { name: _currentScriptName || '未命名脚本', version: '2.0', created: new Date().toISOString(), modified: new Date().toISOString(), description: '' },
    variables: {},
    settings: { viewport: { x: Math.round(viewport.x), y: Math.round(viewport.y), scale: Math.round(vpScale * 1000) / 1000 } },
    graph: { nodes: outNodes, connections: outConns, annotations: outAnnotations, groups: outGroups },
  };
}

export function deserializeGraph(jsonData) {
  if (!jsonData || !jsonData.graph) return false;
  window.AutomationCore.clear();

  var nodeMap = {};
  var maxId = 0;
  var graphNodes = jsonData.graph.nodes || [];
  for (var i = 0; i < graphNodes.length; i++) {
    var nj = graphNodes[i];
    var node = window.AutomationCore.lgGraphObj.createNode(nj.type);
    if (!node) { window.AutomationApp && window.AutomationApp.showToast('无法创建节点: ' + nj.type, 'err'); continue; }
    if (nj.id !== undefined && nj.id !== null) node.id = parseInt(nj.id);
    if (node.id >= maxId) maxId = node.id + 1;
    node.pos[0] = (nj.position && nj.position.x) || 0;
    node.pos[1] = (nj.position && nj.position.y) || 0;
    if (nj.params) {
      for (var k in nj.params) {
        if (!nj.params.hasOwnProperty(k)) continue;
        node.properties[k] = nj.params[k];
      }
    }
    if (nj.customName) {
      node._customName = nj.customName;
    }
    window.AutomationCore.lgGraphObj.add(node);
    var nodeDef = window.AutomationNodes ? window.AutomationNodes.getNodeDef(nj.type) : null;
    if (nodeDef && nodeDef.dynamic_branches && node.properties.branch_count && node.properties.branch_count !== 2) {
      window.AutomationCore.updateBranchPorts(node, node.properties.branch_count);
    }
    nodeMap[nj.id] = node;
  }

  if (maxId > 0) {
    window.AutomationCore.lgGraphObj.setNextNodeId(maxId);
  }

  var graphConns = jsonData.graph.connections || [];
  var _lostConns = [];
  for (var c = 0; c < graphConns.length; c++) {
    var conn = graphConns[c];
    var fromNode = nodeMap[conn.from.node];
    var toNode = nodeMap[conn.to.node];
    if (!fromNode || !toNode) continue;

    var fromSlot = -1;
    if (fromNode.outputs) {
      for (var fi = 0; fi < fromNode.outputs.length; fi++) {
        var outKey = fromNode.outputs[fi]._portKey || fromNode.outputs[fi].name;
        if (outKey === conn.from.port) { fromSlot = fi; break; }
      }
    }
    var toSlot = -1;
    if (toNode.inputs) {
      for (var ti = 0; ti < toNode.inputs.length; ti++) {
        var inKey = toNode.inputs[ti]._portKey || toNode.inputs[ti].name;
        if (inKey === conn.to.port) { toSlot = ti; break; }
      }
    }
    if (fromSlot < 0 || toSlot < 0) {
      console.warn('[反序列化] 连接端口不匹配，已跳过: 节点', conn.from.node, conn.from.port, '->', conn.to.node, conn.to.port);
      _lostConns.push(conn.from.node + '.' + conn.from.port + ' → ' + conn.to.node + '.' + conn.to.port);
      continue;
    }
    window.AutomationCore.lgGraphObj.connect(fromNode.id, fromSlot, toNode.id, toSlot);
  }
  if (_lostConns.length > 0) {
    window.AutomationApp && window.AutomationApp.showToast('导入时 ' + _lostConns.length + ' 条连线因端口不匹配被跳过（详见控制台）', 'warn');
  }

  var graphAnnotations = jsonData.graph.annotations || [];
  for (var ai = 0; ai < graphAnnotations.length; ai++) {
    var aj = graphAnnotations[ai];
    var an = window.AutomationCore.addAnnotation(
      (aj.position && aj.position.x) || 0,
      (aj.position && aj.position.y) || 0,
      aj.text || '',
      aj.color || '#fbbf24'
    );
    if (aj.bgColor) an.bgColor = aj.bgColor;
    if (aj.collapsed) an.collapsed = true;
    if (aj.fontSize) an.fontSize = aj.fontSize;
    if (aj.borderColor) an.borderColor = aj.borderColor;
    if (an._domEl) {
      if (an.collapsed) an._domEl.classList.add('collapsed');
      if (an.bgColor) an._domEl.style.background = an.bgColor;
      if (an.fontSize) an._domEl.style.fontSize = an.fontSize + 'px';
      if (an.borderColor) an._domEl.style.borderColor = an.borderColor;
    }
  }

  var graphGroups = jsonData.graph.groups || [];
  for (var gi = 0; gi < graphGroups.length; gi++) {
    var gj = graphGroups[gi];
    var gp = window.AutomationCore.addGroup(
      (gj.position && gj.position.x) || 0,
      (gj.position && gj.position.y) || 0,
      (gj.size && gj.size.w) || 300,
      (gj.size && gj.size.h) || 200,
      gj.title || '分组',
      gj.color || '#3b82f6'
    );
    if (gj.bgColor) {
      gp.bgColor = gj.bgColor;
      if (gp._domEl) {
        gp._domEl.style.setProperty('--gp-bg', gj.bgColor);
        gp._domEl.style.background = gj.bgColor;
      }
    }
  }

  window.AutomationCore.refreshAllConnections();

  if (jsonData.settings && jsonData.settings.viewport) {
    var vp = jsonData.settings.viewport;
    if (vp.x !== undefined && vp.y !== undefined) {
      window.AutomationCore.setViewport(vp.x, vp.y, vp.scale || 1);
    }
  }

  return true;
}
