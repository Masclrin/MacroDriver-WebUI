import { showToast } from '../app/toast.js';
import { serializeGraph } from './graph-serializer.js';
import { setExecutionState } from '../ui/ui-utils.js';
import { refreshLogPanel } from '../ui/log-panel.js';

export function validateGraph(data) {
  if (!data || !data.graph) return { ok: false, message: '无效的图数据' };
  var nodes = data.graph.nodes || [];
  var connections = data.graph.connections || [];
  var startNodes = nodes.filter(function(n) { return n.type === 'flow/start'; });
  if (startNodes.length === 0) {
    return { ok: false, message: '图中没有开始节点，请从工具箱拖入"流程开始"节点' };
  }
  if (startNodes.length > 1) {
    return { ok: false, message: '图中存在 ' + startNodes.length + ' 个开始节点，只能有 1 个' };
  }
  var endNodes = nodes.filter(function(n) { return n.type === 'flow/end'; });
  // if (endNodes.length === 0) {
  //   showToast('提示: 图中没有"流程结束"节点，建议添加以确保流程完整', 'warn', 3000);
  // }
  var hasAction = nodes.some(function(n) {
    return n.type.startsWith('action/') || n.type.startsWith('script_block/')
        || n.type.startsWith('control/') || n.type.startsWith('preset/')
        || n.type.startsWith('detection/') || n.type.startsWith('monitor/')
        || n.type.startsWith('variable/') || n.type.startsWith('utility/')
        || n.type.startsWith('plugin/');
  });
  if (!hasAction) return { ok: false, message: '图中没有任何可执行节点，请添加节点并连线' };
  var nodeMap = {};
  for (var i = 0; i < nodes.length; i++) nodeMap[nodes[i].id] = nodes[i];
  var adj = {};
  for (var i = 0; i < nodes.length; i++) adj[nodes[i].id] = [];
  var gotoSourceNodes = {};
  for (var i = 0; i < nodes.length; i++) {
    if (nodes[i].type === 'control/goto' && nodes[i].params && nodes[i].params.target_node_id) {
      gotoSourceNodes[nodes[i].id] = true;
    }
  }
  for (var j = 0; j < connections.length; j++) {
    var c = connections[j];
    if (c.type === 'flow' && nodeMap[c.from.node] && nodeMap[c.to.node]) {
      if (gotoSourceNodes[c.from.node]) continue;
      adj[c.from.node].push(c.to.node);
    }
  }
  var visited = {};
  var recStack = {};
  function hasCycle(nid) {
    visited[nid] = true;
    recStack[nid] = true;
    var neighbors = adj[nid] || [];
    for (var k = 0; k < neighbors.length; k++) {
      if (!visited[neighbors[k]]) {
        if (hasCycle(neighbors[k])) return true;
      } else if (recStack[neighbors[k]]) {
        return true;
      }
    }
    recStack[nid] = false;
    return false;
  }
  for (var nid in adj) {
    if (!visited[nid]) {
      if (hasCycle(nid)) return { ok: false, message: '图中存在循环连线，请检查流程是否形成回环' };
    }
  }
  return { ok: true };
}

export function runGraph() {
  if (window.AutomationCore.executionState === 'RUNNING' || window.AutomationCore.executionState === 'PAUSED') {
    showToast('脚本正在运行或已暂停，请先停止', 'warn');
    return;
  }
  var data = serializeGraph();
  if (!data || !data.graph.nodes || data.graph.nodes.length === 0) {
    showToast('画布为空，无法运行', 'warn'); return;
  }
  var validation = validateGraph(data);
  if (!validation.ok) {
    showToast(validation.message, 'err', 5000); return;
  }

  var breakpoints = [];
  var nodes = window.AutomationCore.getNodes();
  for (var i = 0; i < nodes.length; i++) {
    if (nodes[i].properties && nodes[i].properties._breakpoint) {
      breakpoints.push(String(nodes[i].id));
    }
  }

  var logEnabled = false;
  if (window.isLogEnabled) {
    logEnabled = window.isLogEnabled();
  }

  setExecutionState('running');
  showToast('开始执行', 'inf');

  if (window.pywebview && window.pywebview.api && window.pywebview.api.run_automation) {
    window.pywebview.api.run_automation(JSON.stringify(data), breakpoints, logEnabled)
      .then(function(res) {
        if (res && res.ok) {
          showToast('任务已启动', 'ok');
          startStatusPolling();
        } else {
          showToast((res && res.error) || '启动失败', 'err');
          setExecutionState('idle');
        }
      })
      .catch(function(err) {
        showToast('执行错误: ' + (err.message || err), 'err');
        setExecutionState('idle');
      });
  } else {
    simulateExecution();
  }
}

export var _statusPollInterval = null;
export function startStatusPolling() {
  if (_statusPollInterval) clearInterval(_statusPollInterval);
  _statusPollInterval = setInterval(function() {
    if (window.AutomationCore.executionState !== 'RUNNING') {
      clearInterval(_statusPollInterval);
      _statusPollInterval = null;
      return;
    }
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_automation_status) {
      window.pywebview.api.get_automation_status().then(function(res) {
        if (res && res.ok && res.data && res.data.status) {
          var st = res.data.status.toUpperCase();
          if (st === 'COMPLETED') {
            setExecutionState('completed');
            clearInterval(_statusPollInterval);
            _statusPollInterval = null;
            window.AutomationCore.clearAllHighlights();
            showToast('执行完成', 'ok');
          } else if (st === 'PAUSED') {
            setExecutionState('paused');
            if (res.data.breakpoint_hit) {
              showToast('触发断点: 节点 #' + res.data.breakpoint_hit, 'warn', 3000);
              var bpEl = document.getElementById('nd-' + res.data.breakpoint_hit);
              if (bpEl) { bpEl.classList.add('executing'); setTimeout(function() { if (bpEl) bpEl.classList.remove('executing'); }, 500); }
            }
            if (res.data.current_node) {
              var cnEl = document.getElementById('nd-' + res.data.current_node);
              if (cnEl) { cnEl.classList.add('executing'); setTimeout(function() { if (cnEl) cnEl.classList.remove('executing'); }, 500); }
            }
          } else if (st === 'RUNNING') {
            setExecutionState('running');
            refreshLogPanel();
            if (res.data.current_node) {
              var rnEl = document.getElementById('nd-' + res.data.current_node);
              if (rnEl && !rnEl.classList.contains('executing')) {
                rnEl.classList.add('executing');
                setTimeout(function() { if (rnEl && rnEl.classList.contains('executing')) rnEl.classList.remove('executing'); }, 300);
              }
            }
          } else if (st === 'ERROR') {
            setExecutionState('idle');
            clearInterval(_statusPollInterval);
            _statusPollInterval = null;
            window.AutomationCore.clearAllHighlights();
            var errMsg = (res.data && res.data.error) || '执行过程中发生错误';
            showToast(errMsg, 'err', 5000);
          }
        }
      }).catch(function() {});
    }
  }, 1000);
}

export function stopGraph(silent) {
  var state = window.AutomationCore.executionState;
  if (state !== 'RUNNING' && state !== 'PAUSED' && state !== 'COMPLETED') return;
  if (_statusPollInterval) { clearInterval(_statusPollInterval); _statusPollInterval = null; }
  setExecutionState('idle');
  window.AutomationCore.clearAllHighlights();
  if (window.pywebview && window.pywebview.api && window.pywebview.api.stop_automation) {
    window.pywebview.api.stop_automation().catch(function() {});
  }
  if (!silent) showToast('已停止', 'inf');
}

export function pauseGraph() {
  var state = window.AutomationCore.executionState;
  if (state === 'RUNNING') {
    setExecutionState('paused');
    if (window.pywebview && window.pywebview.api && window.pywebview.api.pause_automation) {
      window.pywebview.api.pause_automation().catch(function() {});
    }
    showToast('已暂停', 'inf');
  } else if (state === 'PAUSED') {
    setExecutionState('running');
    if (window.pywebview && window.pywebview.api && window.pywebview.api.resume_automation) {
      window.pywebview.api.resume_automation().catch(function() {});
    }
    showToast('已继续', 'inf');
  }
}

export function simulateExecution() {
  window.AutomationCore.clearAllHighlights();
  var sortedNodes = _getFlowOrderedNodes();
  var idx = 0;
  var interval = setInterval(function() {
    if (window.AutomationCore.executionState === 'IDLE' || idx >= sortedNodes.length) {
      clearInterval(interval);
      window.AutomationCore.clearAllHighlights();
      setExecutionState('idle');
      if (idx >= sortedNodes.length) showToast('模拟执行完成', 'ok');
      return;
    }
    if (window.AutomationCore.executionState === 'PAUSED') return;

    if (idx > 0) {
      window.AutomationCore.setNodeHighlight(sortedNodes[idx - 1].id, null);
    }
    var node = sortedNodes[idx];
    if (node) {
      window.AutomationCore.setNodeHighlight(node.id, 'executing');
      window.AutomationCore.selectNode(node);
      window.AutomationProperty.render(node);
      var defKey = node._defKey || node.type;
      if (defKey && defKey.startsWith('plugin/')) {
        var nodeDef = window.AutomationNodes.getNodeDef(defKey);
        if (nodeDef && nodeDef.onExecute) {
          try {
            nodeDef.onExecute(node.properties || {});
          } catch(e) {
            console.error('[模拟执行] 插件 onExecute 错误:', e);
          }
        }
      }
    }
    idx++;
  }, 500);
}

function _getFlowOrderedNodes() {
  var allNodes = window.AutomationCore.getNodes();
  if (!allNodes || allNodes.length === 0) return [];

  var nodeMap = {};
  var adjList = {};
  for (var i = 0; i < allNodes.length; i++) {
    var n = allNodes[i];
    nodeMap[n.id] = n;
    adjList[n.id] = [];
  }

  for (var i = 0; i < allNodes.length; i++) {
    var node = allNodes[i];
    var conns = window.AutomationCore.getConnections ? window.AutomationCore.getConnections() : [];
    for (var j = 0; j < conns.length; j++) {
      var c = conns[j];
      if (c.origin_id === node.id) {
        adjList[node.id].push(c.target_id);
      }
    }
  }

  var visited = {};
  var result = [];

  function dfs(nodeId) {
    if (visited[nodeId]) return;
    visited[nodeId] = true;
    var children = adjList[nodeId] || [];
    for (var k = 0; k < children.length; k++) {
      dfs(children[k]);
    }
    if (nodeMap[nodeId]) result.push(nodeMap[nodeId]);
  }

  var entryNodes = allNodes.filter(function(n) {
    var defKey = n._defKey || n.type;
    return defKey === 'flow/start';
  });

  if (entryNodes.length > 0) {
    for (var i = 0; i < entryNodes.length; i++) {
      dfs(entryNodes[i].id);
    }
  } else {
    for (var i = 0; i < allNodes.length; i++) {
      dfs(allNodes[i].id);
    }
  }

  result.reverse();
  return result;
}
