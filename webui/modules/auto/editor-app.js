import { AutomationCore } from './core.js';
import { AutomationNodes } from './nodes.js';
import { AutomationEvents } from './events-handlers.js';
import { AutomationProperty } from './property.js';
import { AutomationTools } from './tools.js';
import { AutomationBlockEditor } from './block-editor.js';
import { MacroUtils } from './macro-utils.js';
import { renderMacroTreeList } from '../macro-tree.js';

window.AutomationCore = AutomationCore;
window.AutomationNodes = AutomationNodes;
window.AutomationEvents = AutomationEvents;
window.AutomationProperty = AutomationProperty;
window.AutomationTools = AutomationTools;
window.AutomationBlockEditor = AutomationBlockEditor;
window.MacroUtils = MacroUtils;
window.renderMacroTreeList = renderMacroTreeList;

var _hotkeyEnabled = true;
var _hotkeyRun = 'F5';
var _hotkeyPause = 'F6';
var _hotkeyStop = 'F7';
var _hotkeyFullscreen = 'F11';

function _loadEditorHotkeys() {
  try {
    var saved = localStorage.getItem('editor_hotkeys');
    if (saved) {
      var cfg = JSON.parse(saved);
      _hotkeyEnabled = cfg.enabled !== false;
      if (cfg.run) _hotkeyRun = cfg.run;
      if (cfg.pause) _hotkeyPause = cfg.pause;
      if (cfg.stop) _hotkeyStop = cfg.stop;
      if (cfg.fullscreen) _hotkeyFullscreen = cfg.fullscreen;
    }
  } catch (e) {}
}

function _saveEditorHotkeys() {
  try {
    localStorage.setItem('editor_hotkeys', JSON.stringify({
      enabled: _hotkeyEnabled,
      run: _hotkeyRun,
      pause: _hotkeyPause,
      stop: _hotkeyStop,
      fullscreen: _hotkeyFullscreen
    }));
  } catch (e) {}
}

_loadEditorHotkeys();

var contextTarget = null;
var contextPos = null;
var _graphDirty = false;
var _currentScriptName = '未命名脚本';
var _lastSavedGraph = null;
var _clipboard = null;

var _sidebarLeftWidth = 208;
var _sidebarRightWidth = 264;
var _sidebarLeftCollapsed = false;
var _sidebarRightCollapsed = false;
var _sidebarLeftPrevWidth = 208;
var _sidebarRightPrevWidth = 264;

function initSidebarResize() {
  var sbLeft = document.getElementById('sb-l');
  var sbRight = document.getElementById('sb-r');
  var rszLeft = document.getElementById('sb-l-rsz');
  var rszRight = document.getElementById('sb-r-rsz');
  if (!sbLeft || !sbRight || !rszLeft || !rszRight) return;

  function startResize(rszEl, side, evt) {
    var startX = 0, startWidth = 0, targetEl = null;
    if (side === 'left') {
      if (_sidebarLeftCollapsed) return;
      startX = evt.clientX;
      startWidth = sbLeft.offsetWidth;
      targetEl = sbLeft;
    } else {
      if (_sidebarRightCollapsed) return;
      startX = evt.clientX;
      startWidth = sbRight.offsetWidth;
      targetEl = sbRight;
    }
    rszEl.classList.add('active');
    function onMove(e) {
      if (side === 'left') {
        var newW = Math.max(150, Math.min(400, startWidth + e.clientX - startX));
        targetEl.style.width = newW + 'px';
        targetEl.style.setProperty('--sb-l-w', newW + 'px');
        _sidebarLeftWidth = newW;
        _sidebarLeftPrevWidth = newW;
      } else {
        var newW = Math.max(200, Math.min(500, startWidth - (e.clientX - startX)));
        targetEl.style.width = newW + 'px';
        targetEl.style.setProperty('--sb-r-w', newW + 'px');
        _sidebarRightWidth = newW;
        _sidebarRightPrevWidth = newW;
      }
    }
    function onUp() {
      rszEl.classList.remove('active');
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      try { localStorage.setItem('sb_left_width', _sidebarLeftWidth); } catch(e) {}
      try { localStorage.setItem('sb_right_width', _sidebarRightWidth); } catch(e) {}
      _repositionMinimap();
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  rszLeft.addEventListener('mousedown', function(e) { e.preventDefault(); startResize(rszLeft, 'left', e); });
  rszRight.addEventListener('mousedown', function(e) { e.preventDefault(); startResize(rszRight, 'right', e); });

  try {
    var lw = localStorage.getItem('sb_left_width');
    if (lw) { var lwVal = parseInt(lw); if (lwVal >= 150 && lwVal <= 400) { sbLeft.style.width = lwVal + 'px'; sbLeft.style.setProperty('--sb-l-w', lwVal + 'px'); _sidebarLeftWidth = lwVal; _sidebarLeftPrevWidth = lwVal; } }
    var rw = localStorage.getItem('sb_right_width');
    if (rw) { var rwVal = parseInt(rw); if (rwVal >= 200 && rwVal <= 500) { sbRight.style.width = rwVal + 'px'; sbRight.style.setProperty('--sb-r-w', rwVal + 'px'); _sidebarRightWidth = rwVal; _sidebarRightPrevWidth = rwVal; } }
  } catch(e) {}
}

function initSidebarToggle() {
  var sbLeft = document.getElementById('sb-l');
  var sbRight = document.getElementById('sb-r');
  var toggleLeft = document.getElementById('sb-l-toggle');
  var toggleRight = document.getElementById('sb-r-toggle');
  if (!sbLeft || !sbRight || !toggleLeft || !toggleRight) return;

  toggleLeft.addEventListener('click', function() {
    _sidebarLeftCollapsed = !_sidebarLeftCollapsed;
    if (_sidebarLeftCollapsed) {
      _sidebarLeftPrevWidth = sbLeft.offsetWidth || _sidebarLeftPrevWidth;
      var w = sbLeft.offsetWidth || 208;
      sbLeft.style.left = '-' + w + 'px';
      sbLeft.classList.add('collapsed');
      toggleLeft.querySelector('i').className = 'fa-solid fa-angles-right';
    } else {
      sbLeft.classList.remove('collapsed');
      sbLeft.style.left = '0';
      sbLeft.style.width = _sidebarLeftPrevWidth + 'px';
      sbLeft.style.setProperty('--sb-l-w', _sidebarLeftPrevWidth + 'px');
      _sidebarLeftWidth = _sidebarLeftPrevWidth;
      toggleLeft.querySelector('i').className = 'fa-solid fa-angles-left';
    }
  });

  toggleRight.addEventListener('click', function() {
    _sidebarRightCollapsed = !_sidebarRightCollapsed;
    if (_sidebarRightCollapsed) {
      _sidebarRightPrevWidth = sbRight.offsetWidth || _sidebarRightPrevWidth;
      var w = sbRight.offsetWidth || 264;
      sbRight.style.right = '-' + w + 'px';
      sbRight.classList.add('collapsed');
      toggleRight.querySelector('i').className = 'fa-solid fa-angles-left';
    } else {
      sbRight.classList.remove('collapsed');
      sbRight.style.right = '0';
      sbRight.style.width = _sidebarRightPrevWidth + 'px';
      sbRight.style.setProperty('--sb-r-w', _sidebarRightPrevWidth + 'px');
      _sidebarRightWidth = _sidebarRightPrevWidth;
      toggleRight.querySelector('i').className = 'fa-solid fa-angles-right';
    }
    setTimeout(_repositionMinimap, 220);
  });
}

function _repositionMinimap() {
  var mm = document.getElementById('mm');
  var sbRight = document.getElementById('sb-r');
  if (!mm || !sbRight) return;
  var isCollapsed = sbRight.classList.contains('collapsed');
  var rightOffset = isCollapsed ? 10 : (Math.max(sbRight.offsetWidth, 200) + 10);
  mm.style.right = rightOffset + 'px';
}

var TOOLBOX_CATEGORIES = [
  { id: 'flow', name: '流程', color: '#ffffffff', icon: 'fa-solid fa-route' },
  { id: 'action', name: '动作节点', color: '#22c55e', icon: 'fa-solid fa-bolt' },
  { id: 'detection', name: '检测节点', color: '#eab308', icon: 'fa-solid fa-magnifying-glass' },
  { id: 'control', name: '控制节点', color: '#a855f7', icon: 'fa-solid fa-code-branch' },
  { id: 'script_block', name: '动作块', color: '#3b82f6', icon: 'fa-solid fa-cubes' },
  { id: 'monitor', name: '监视器', color: '#06b6d4', icon: 'fa-solid fa-eye' },
  { id: 'variable', name: '变量', color: '#f97316', icon: 'fa-solid fa-database' },
  { id: 'preset', name: '预设', color: '#f472b6', icon: 'fa-solid fa-wand-magic-sparkles' },
  { id: 'utility', name: '工具', color: '#d8d8d8ff', icon: 'fa-solid fa-screwdriver-wrench' },
];

var undoManager = {
  _stack: [], _idx: -1, _max: 50, _paused: false,
  push: function() {
    if (this._paused) return;
    var data = serializeGraph();
    if (!data) return;
    this._stack = this._stack.slice(0, this._idx + 1);
    this._stack.push(JSON.stringify(data));
    if (this._stack.length > this._max) this._stack.shift();
    this._idx = this._stack.length - 1;
  },
  undo: function() {
    if (this._idx <= 0) return;
    this._idx--;
    this._restore();
  },
  redo: function() {
    if (this._idx >= this._stack.length - 1) return;
    this._idx++;
    this._restore();
  },
  _restore: function() {
    this._paused = true;
    try {
      var data = JSON.parse(this._stack[this._idx]);
      deserializeGraph(data);
    } catch(e) {
      console.error('[UndoManager] restore error:', e);
    } finally {
      this._paused = false;
    }
  },
  reset: function() { this._stack = []; this._idx = -1; this.push(); }
};

function showToast(msg, type, duration) {
  type = type || 'inf';
  duration = duration || 3000;
  var container = document.getElementById('toast-c');
  var icons = { ok: 'fa-solid fa-check-circle', err: 'fa-solid fa-exclamation-circle', inf: 'fa-solid fa-info-circle', warn: 'fa-solid fa-triangle-exclamation' };
  var toast = document.createElement('div');
  toast.className = 'toast ' + type;
  toast.innerHTML = '<i class="' + (icons[type] || icons.inf) + '"></i><span>' + msg + '</span>';
  container.appendChild(toast);
  setTimeout(function() {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all .15s ease';
    setTimeout(function() { toast.remove(); }, 150);
  }, duration);
}

function setExecutionState(state) {
  state = state.toUpperCase();
  AutomationCore.executionState = state;
  var dot = document.getElementById('st-dot');
  var txt = document.getElementById('st-txt');
  if (state === 'RUNNING') {
    dot.style.background = 'var(--c-action)';
    dot.classList.add('run-i');
    txt.textContent = '运行中';
  } else if (state === 'PAUSED') {
    dot.style.background = 'var(--c-detect)';
    dot.classList.remove('run-i');
    txt.textContent = '已暂停';
  } else if (state === 'COMPLETED') {
    dot.style.background = 'var(--c-ok,#22c55e)';
    dot.classList.remove('run-i');
    txt.textContent = '已完成';
    var btnRun = document.getElementById('btn-run');
    if (btnRun) { btnRun.disabled = false; btnRun.style.opacity = ''; btnRun.style.pointerEvents = ''; btnRun.style.boxShadow = ''; }
  } else {
    dot.style.background = 'var(--txt3)';
    dot.classList.remove('run-i');
    txt.textContent = '就绪';
    var btnRun = document.getElementById('btn-run');
    if (btnRun) { btnRun.disabled = false; btnRun.style.opacity = ''; btnRun.style.pointerEvents = ''; }
  }
}

function updateStatusBar() {
  var nodes = AutomationCore.getNodes();
  var conns = AutomationCore.getConnections();
  var monitorCount = 0;
  var varNames = {};
  for (var i = 0; i < nodes.length; i++) {
    var n = nodes[i];
    if (n._category === 'monitor') monitorCount++;
    if (n.properties && n.properties.name && n._defKey && n._defKey.indexOf('var_set') >= 0) {
      varNames[n.properties.name] = true;
    }
    if (n.properties && n.properties.store_var) {
      varNames[n.properties.store_var] = true;
    }
  }
  document.getElementById('s-n').textContent = nodes.length;
  document.getElementById('s-c').textContent = conns.length;
  document.getElementById('s-m').textContent = monitorCount;
  document.getElementById('s-v').textContent = Object.keys(varNames).length;
  document.getElementById('s-zm').textContent = Math.round(AutomationCore.getZoomLevel() * 100) + '%';
  document.getElementById('zm-lv').textContent = Math.round(AutomationCore.getZoomLevel() * 100) + '%';

  var emptyHint = document.getElementById('empty-hint');
  if (emptyHint) {
    emptyHint.style.opacity = nodes.length === 0 ? '1' : '0';
  }
}

function updateMinimap() {
  AutomationCore.updateMinimap();
}

function renderToolbox(filterText) {
  var container = document.getElementById('toolbox-categories');
  container.innerHTML = '';
  var filter = (filterText || '').toLowerCase().trim();
  var nodeDefs = AutomationNodes._nodeDefs;

  for (var ci = 0; ci < TOOLBOX_CATEGORIES.length; ci++) {
    var cat = TOOLBOX_CATEGORIES[ci];
    var catNodes = [];
    for (var typeKey in nodeDefs) {
      if (!nodeDefs.hasOwnProperty(typeKey)) continue;
      var def = nodeDefs[typeKey];
      if (def.category !== cat.id) continue;
      if (filter && def.display_name.toLowerCase().indexOf(filter) < 0 && typeKey.toLowerCase().indexOf(filter) < 0) continue;
      catNodes.push({ type: typeKey, def: def });
    }

    if (catNodes.length === 0 && filter) continue;

    var catEl = document.createElement('div');
    catEl.className = 'sb-c' + (cat.id === 'utility' ? ' col' : '');

    var header = document.createElement('div');
    header.className = 'sb-ch';
    header.innerHTML =
      '<span class="cd" style="width:8px;height:8px;border-radius:2px;background:' + cat.color + ';display:inline-block;flex-shrink:0"></span>' +
      '<span style="flex:1">' + cat.name + '</span>' +
      '<span style="font-size:9px;color:var(--txt3);font-family:var(--fmo)">' + catNodes.length + '</span>' +
      '<i class="fa-solid fa-chevron-down ca"></i>';
    header.addEventListener('click', function() { this.parentElement.classList.toggle('col'); });

    var nodesEl = document.createElement('div');
    nodesEl.className = 'sb-ci';

    for (var ni = 0; ni < catNodes.length; ni++) {
      var item = document.createElement('div');
      item.className = 'sb-ni';
      item.dataset.nodeType = catNodes[ni].type;
      var iconClass = catNodes[ni].def.icon || 'fa-solid fa-circle';
      item.innerHTML = '<i class="' + iconClass + '" style="color:' + catNodes[ni].def.color + '"></i><span>' + catNodes[ni].def.display_name + '</span>';
      item.draggable = true;
      item.addEventListener('dragstart', (function(nt) {
        return function(e) {
          e.dataTransfer.setData('text/plain', nt);
          e.dataTransfer.setData('node-type', nt);
          e.dataTransfer.effectAllowed = 'copy';
        };
      })(catNodes[ni].type));
      item.addEventListener('dblclick', (function(nt) {
        return function() { addNodeToCenter(nt); };
      })(catNodes[ni].type));
      nodesEl.appendChild(item);
    }

    catEl.appendChild(header);
    catEl.appendChild(nodesEl);
    container.appendChild(catEl);
  }
}

function addNodeToCenter(nodeType) {
  var node = AutomationCore.addNodeAtCenter(nodeType);
  if (!node) { showToast('未知节点类型: ' + nodeType, 'err'); return; }
  AutomationCore.selectNode(node);
  updateStatusBar();
  updateMinimap();
  undoManager.push();
}

function serializeGraph() {
  var nodes = AutomationCore.getNodes();
  var connections = AutomationCore.getConnections();
  var annotations = AutomationCore.getAnnotations();
  var groups = AutomationCore.getGroups();
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
    var originNode = AutomationCore.lgGraphObj.getNodeById(link.origin_id);
    var targetNode = AutomationCore.lgGraphObj.getNodeById(link.target_id);
    if (!originNode || !targetNode) continue;
    var output = originNode.outputs[link.origin_slot];
    var linkType = (output && output.type === 'flow') ? 'flow' : 'data';
    var fromPortKey = (output && output._portKey) || '';
    if (!fromPortKey && output) {
      var fromDef = AutomationNodes.getNodeDef(originNode._defKey);
      if (fromDef && fromDef.outputs && fromDef.outputs[link.origin_slot]) {
        fromPortKey = fromDef.outputs[link.origin_slot].name;
      }
    }
    var toInput = targetNode.inputs[link.target_slot];
    var toPortKey = (toInput && toInput._portKey) || '';
    if (!toPortKey && toInput) {
      var toDef = AutomationNodes.getNodeDef(targetNode._defKey);
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

  return {
    meta: { name: _currentScriptName || '未命名脚本', version: '2.0', created: new Date().toISOString(), modified: new Date().toISOString(), description: '' },
    variables: {},
    settings: {},
    graph: { nodes: outNodes, connections: outConns, annotations: outAnnotations, groups: outGroups },
  };
}

function deserializeGraph(jsonData) {
  if (!jsonData || !jsonData.graph) return false;
  AutomationCore.clear();

  var nodeMap = {};
  var maxId = 0;
  var graphNodes = jsonData.graph.nodes || [];
  for (var i = 0; i < graphNodes.length; i++) {
    var nj = graphNodes[i];
    var node = AutomationCore.lgGraphObj.createNode(nj.type);
    if (!node) { showToast('无法创建节点: ' + nj.type, 'err'); continue; }
    if (nj.id !== undefined && nj.id !== null) node.id = parseInt(nj.id);
    if (node.id >= maxId) maxId = node.id + 1;
    node.pos[0] = Math.max(0, (nj.position && nj.position.x) || 0);
    node.pos[1] = Math.max(0, (nj.position && nj.position.y) || 0);
    if (nj.params) {
      for (var k in nj.params) {
        if (!nj.params.hasOwnProperty(k)) continue;
        node.properties[k] = nj.params[k];
      }
    }
    if (nj.customName) {
      node._customName = nj.customName;
    }
    AutomationCore.lgGraphObj.add(node);
    nodeMap[nj.id] = node;
  }

  if (maxId > 0) {
    AutomationCore.lgGraphObj.setNextNodeId(maxId);
  }

  var graphConns = jsonData.graph.connections || [];
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
    if (fromSlot < 0 || toSlot < 0) continue;
    AutomationCore.lgGraphObj.connect(fromNode.id, fromSlot, toNode.id, toSlot);
  }

  var graphAnnotations = jsonData.graph.annotations || [];
  for (var ai = 0; ai < graphAnnotations.length; ai++) {
    var aj = graphAnnotations[ai];
    var an = AutomationCore.addAnnotation(
      (aj.position && aj.position.x) || 0,
      (aj.position && aj.position.y) || 0,
      aj.text || '',
      aj.color || '#fbbf24'
    );
    if (aj.bgColor) an.bgColor = aj.bgColor;
    if (aj.collapsed) an.collapsed = true;
    if (an._domEl) {
      if (an.collapsed) an._domEl.classList.add('collapsed');
      if (an.bgColor) an._domEl.style.background = an.bgColor;
    }
  }

  var graphGroups = jsonData.graph.groups || [];
  for (var gi = 0; gi < graphGroups.length; gi++) {
    var gj = graphGroups[gi];
    var gp = AutomationCore.addGroup(
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

  AutomationCore.refreshAllConnections();
  updateStatusBar();
  updateMinimap();
  return true;
}

function exportGraph() {
  if (_currentScriptName === '未命名脚本') {
    var newName = prompt('脚本名称不能为默认名，请输入新的脚本名称：', '我的脚本');
    if (!newName || newName.trim() === '') {
      showToast('已取消导出', 'inf');
      return;
    }
    if (newName.trim() === '未命名脚本') {
      showToast('脚本名称不能为默认名，请修改后重试', 'warn');
      return;
    }
    _currentScriptName = newName.trim();
    updateScriptNameDisplay();
  }
  var data = serializeGraph();
  if (!data) { showToast('没有可导出的内容', 'warn'); return; }
  var blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = _currentScriptName + '.auto.json';
  a.click();
  URL.revokeObjectURL(url);
  showToast('已导出脚本文件', 'ok');
}

function importGraph() {
  document.getElementById('file-input-import').click();
}

function handleFileImport(e) {
  var file = e.target.files[0];
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function(ev) {
    try {
      var data = JSON.parse(ev.target.result);
      if (deserializeGraph(data)) {
        var importedName = (data.meta && data.meta.name) || '未命名脚本';
        _currentScriptName = importedName;
        _graphDirty = false;
        _lastSavedGraph = JSON.stringify(data);
        updateScriptNameDisplay();
        setExecutionState('idle');
        showToast('已导入: ' + importedName, 'ok');
      } else {
        showToast('导入失败：格式无效', 'err');
      }
    } catch (err) {
      showToast('导入失败: ' + err.message, 'err');
    }
  };
  reader.readAsText(file);
  e.target.value = '';
}

function saveGraph() {
  if (_currentScriptName === '未命名脚本') {
    var newName = prompt('脚本名称不能为默认名，请输入新的脚本名称：', '我的脚本');
    if (!newName || newName.trim() === '') {
      showToast('已取消保存', 'inf');
      return;
    }
    if (newName.trim() === '未命名脚本') {
      showToast('脚本名称不能为默认名，请修改后重试', 'warn');
      return;
    }
    _currentScriptName = newName.trim();
    updateScriptNameDisplay();
  }
  if (window.pywebview && window.pywebview.api && window.pywebview.api.save_auto_script) {
    var data = serializeGraph();
    _lastSavedGraph = JSON.stringify(data);
    _graphDirty = false;
    window.pywebview.api.save_auto_script('自动化脚本/' + _currentScriptName + '.auto.json', JSON.stringify(data, null, 2))
      .then(function(res) {
        if (res && res.ok) showToast('保存成功', 'ok');
        else showToast((res && res.error) || '保存失败', 'err');
      })
      .catch(function() { exportGraph(); });
  } else {
    exportGraph();
  }
}

function newCanvas() {
  var nodes = AutomationCore.getNodes();
  if (nodes.length > 0 && _graphDirty) {
    if (_currentScriptName === '未命名脚本') {
      if (!confirm('当前画布未命名且有未保存的更改，是否先命名并保存？\n\n点击"确定"命名并保存\n点击"取消"放弃更改并新建')) {
        // 用户选择放弃，直接新建
      } else {
        var newName = prompt('请输入脚本名称：', '我的脚本');
        if (!newName || newName.trim() === '' || newName.trim() === '未命名脚本') {
          showToast('名称无效，已取消新建', 'inf');
          return;
        }
        _currentScriptName = newName.trim();
        updateScriptNameDisplay();
        saveGraph();
        return;
      }
    } else {
      if (!confirm('当前画布有未保存的更改，是否保存后再新建？\n\n点击"确定"保存当前画布\n点击"取消"放弃更改并新建')) {
        // 用户选择放弃，直接新建
      } else {
        saveGraph();
        return;
      }
    }
  }
  AutomationCore.clearAll();
  AutomationCore.zoomReset();
  AutomationProperty.render(null);
  _currentScriptName = '未命名脚本';
  _lastSavedGraph = null;
  _graphDirty = false;
  updateScriptNameDisplay();
  addNodeToCenter('flow/start');
  setExecutionState('idle');
  updateStatusBar();
  updateMinimap();
  undoManager.reset();
  showToast('已创建新画布', 'inf');
}

function updateScriptNameDisplay() {
  var el = document.getElementById('script-name-input');
  if (el) {
    el.value = _currentScriptName || '未命名脚本';
  }
}

function renameScript() {
  var el = document.getElementById('script-name-input');
  if (!el) return;
  el.readOnly = false;
  el.style.borderColor = 'var(--acc)';
  el.style.background = 'var(--bg-hover)';
  el.focus();
  el.select();
}

function finishRenameScript(el) {
  if (!el) el = document.getElementById('script-name-input');
  if (!el) return;
  el.readOnly = true;
  el.style.borderColor = 'transparent';
  el.style.background = 'var(--bg-raised)';
  var newName = el.value.trim();
  if (!newName || newName === '未命名脚本') {
    el.value = _currentScriptName || '未命名脚本';
    if (!newName) showToast('名称不能为空', 'warn');
    return;
  }
  _currentScriptName = newName;
  _graphDirty = true;
  showToast('已重命名为: ' + _currentScriptName, 'ok');
}

function validateGraph(data) {
  if (!data || !data.graph) return { ok: false, message: '无效的图数据' };
  var nodes = data.graph.nodes || [];
  var connections = data.graph.connections || [];
  var startNodes = nodes.filter(function(n) { return n.type === 'flow/start'; });
  if (startNodes.length === 0) {
    var hasAction = nodes.some(function(n) { return n.type.startsWith('action/') || n.type.startsWith('script_block/') || n.type.startsWith('control/') || n.type.startsWith('preset/'); });
    if (!hasAction) return { ok: false, message: '图中没有任何可执行节点，请添加节点并连线' };
  }
  if (startNodes.length > 1) {
    return { ok: false, message: '图中存在 ' + startNodes.length + ' 个开始节点，只能有 1 个' };
  }
  var nodeMap = {};
  for (var i = 0; i < nodes.length; i++) nodeMap[nodes[i].id] = nodes[i];
  var adj = {};
  for (var i = 0; i < nodes.length; i++) adj[nodes[i].id] = [];
  for (var j = 0; j < connections.length; j++) {
    var c = connections[j];
    if (c.type === 'flow' && nodeMap[c.from.node] && nodeMap[c.to.node]) {
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

function runGraph() {
  if (AutomationCore.executionState === 'RUNNING') {
    showToast('脚本正在运行中，请先停止', 'warn');
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
  setExecutionState('running');
  var btnRun = document.getElementById('btn-run');
  if (btnRun) { btnRun.disabled = true; btnRun.style.opacity = '0.5'; btnRun.style.pointerEvents = 'none'; }
  showToast('开始执行', 'inf');

  if (window.pywebview && window.pywebview.api && window.pywebview.api.run_automation) {
    window.pywebview.api.run_automation(JSON.stringify(data))
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

var _statusPollInterval = null;
function startStatusPolling() {
  if (_statusPollInterval) clearInterval(_statusPollInterval);
  _statusPollInterval = setInterval(function() {
    if (AutomationCore.executionState !== 'RUNNING') {
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
          }
        }
      }).catch(function() {});
    }
  }, 1000);
}

function stopGraph(silent) {
  var state = AutomationCore.executionState;
  if (state !== 'RUNNING' && state !== 'PAUSED' && state !== 'COMPLETED') return;
  if (_statusPollInterval) { clearInterval(_statusPollInterval); _statusPollInterval = null; }
  setExecutionState('idle');
  AutomationCore.clearAllHighlights();
  var btnRun = document.getElementById('btn-run');
  if (btnRun) { btnRun.disabled = false; btnRun.style.opacity = ''; btnRun.style.pointerEvents = ''; }
  if (window.pywebview && window.pywebview.api && window.pywebview.api.stop_automation) {
    window.pywebview.api.stop_automation().catch(function() {});
  }
  if (!silent) showToast('已停止', 'inf');
}

function pauseGraph() {
  var state = AutomationCore.executionState;
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

function simulateExecution() {
  AutomationCore.clearAllHighlights();
  var allNodes = AutomationCore.getNodes();
  var idx = 0;
  var interval = setInterval(function() {
    if (AutomationCore.executionState === 'IDLE' || idx >= allNodes.length) {
      clearInterval(interval);
      AutomationCore.clearAllHighlights();
      setExecutionState('idle');
      if (idx >= allNodes.length) showToast('模拟执行完成', 'ok');
      return;
    }
    if (AutomationCore.executionState === 'PAUSED') return;

    if (idx > 0) {
      AutomationCore.setNodeHighlight(allNodes[idx - 1].id, null);
    }
    var node = allNodes[idx];
    if (node) {
      AutomationCore.setNodeHighlight(node.id, 'executing');
      AutomationCore.selectNode(node);
      AutomationProperty.render(node);
      if (node._defKey === 'plugin/notify' && window.AutomationEvents) {
        AutomationEvents.showNotifyPopup({
          title: node.properties.title || '提示',
          message: node.properties.message || '',
          sound: node.properties.sound || 'default',
          duration: node.properties.duration || 3000,
          position: node.properties.position || 'bottom-right'
        });
      }
    }
    idx++;
  }, 500);
}

var _isFullscreen = false;

function toggleFullscreen() {
  _isFullscreen = !_isFullscreen;
  var btn = document.getElementById('btn-fullscreen');
  try {
    var parentDoc = window.parent.document;
    var iframe = parentDoc.getElementById('automationFrame');
    if (_isFullscreen) {
      iframe.style.position = 'fixed';
      iframe.style.top = '0';
      iframe.style.left = '0';
      iframe.style.width = '100vw';
      iframe.style.height = '100vh';
      iframe.style.zIndex = '99999';
      iframe.style.border = 'none';
      if (btn) btn.innerHTML = '<i class="fa-solid fa-down-left-and-up-right-to-center"></i>';
      if (btn) btn.title = '退出全屏';
    } else {
      iframe.style.position = '';
      iframe.style.top = '';
      iframe.style.left = '';
      iframe.style.width = '100%';
      iframe.style.height = '100%';
      iframe.style.zIndex = '';
      iframe.style.border = 'none';
      if (btn) btn.innerHTML = '<i class="fa-solid fa-up-right-and-down-left-from-center"></i>';
      if (btn) btn.title = '全屏';
    }
  } catch (e) {
    var editorRoot = document.getElementById('app');
    if (_isFullscreen) {
      editorRoot.style.position = 'fixed';
      editorRoot.style.top = '0';
      editorRoot.style.left = '0';
      editorRoot.style.width = '100vw';
      editorRoot.style.height = '100vh';
      editorRoot.style.zIndex = '99999';
      if (btn) btn.innerHTML = '<i class="fa-solid fa-down-left-and-up-right-to-center"></i>';
      if (btn) btn.title = '退出全屏';
    } else {
      editorRoot.style.position = '';
      editorRoot.style.top = '';
      editorRoot.style.left = '';
      editorRoot.style.width = '';
      editorRoot.style.height = '';
      editorRoot.style.zIndex = '';
      if (btn) btn.innerHTML = '<i class="fa-solid fa-up-right-and-down-left-from-center"></i>';
      if (btn) btn.title = '全屏';
    }
  }
  setTimeout(function() {
    AutomationCore.refreshAllConnections();
    updateMinimap();
  }, 100);
}

function fitView() {
  var nodes = AutomationCore.getNodes();
  if (nodes.length === 0) {
    AutomationCore.zoomReset();
    return;
  }
  var minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
  for (var i = 0; i < nodes.length; i++) {
    var n = nodes[i];
    minX = Math.min(minX, n.pos[0]);
    minY = Math.min(minY, n.pos[1]);
    maxX = Math.max(maxX, n.pos[0] + (n.size[0] || 220));
    maxY = Math.max(maxY, n.pos[1] + (n.size[1] || 100));
  }
  var cvArea = document.getElementById('cv-area');
  var cvW = cvArea.clientWidth;
  var cvH = cvArea.clientHeight;
  var pad = 80;
  var gw = maxX - minX + pad * 2;
  var gh = maxY - minY + pad * 2;
  var scale = Math.min(cvW / gw, cvH / gh, 2);
  scale = Math.max(0.15, Math.min(3, scale));
  var cx = (minX + maxX) / 2;
  var cy = (minY + maxY) / 2;
  var offX = cvW / 2 - cx * scale;
  var offY = cvH / 2 - cy * scale;
  AutomationCore.setViewport(offX, offY, scale);
  AutomationCore.refreshAllConnections();
  updateStatusBar();
  updateMinimap();
}

function showContextMenu(x, y, items) {
  var menu = document.getElementById('ctx');
  var html = '';
  for (var i = 0; i < items.length; i++) {
    var item = items[i];
    if (item === '---' || item.divider) {
      html += '<div class="cx-s"></div>';
      continue;
    }
    var subHtml = '';
    if (item.submenu) {
      subHtml = buildAddNodeSubmenu();
    }
    var iconStyle = item.iconStyle ? ' style="' + item.iconStyle + '"' : '';
    html += '<div class="cx-i" data-action="' + item.action + '">' +
      '<i class="' + (item.icon || 'fa-solid fa-circle') + '"' + iconStyle + '></i>' +
      '<span>' + item.label + '</span>' +
      (item.submenu ? '<i class="fa-solid fa-chevron-right" style="margin-left:auto;font-size:8px"></i>' : '') +
      (item.shortcut ? '<span style="margin-left:auto;font-size:9px;color:var(--txt3)">' + item.shortcut + '</span>' : '') +
      subHtml +
      '</div>';
  }
  menu.innerHTML = html;
  menu.style.left = Math.min(x, window.innerWidth - 180) + 'px';
  menu.style.top = Math.min(y, window.innerHeight - menu.offsetHeight - 10) + 'px';
  menu.classList.add('show');

  var ctxItems = menu.querySelectorAll('.cx-i');
  for (var j = 0; j < ctxItems.length; j++) {
    ctxItems[j].addEventListener('click', function(e) {
      if (this.querySelector('.cx-sub') && this.querySelector('.cx-sub').contains(e.target)) return;
      if (this.querySelector('.cx-sub')) return;
      handleContextAction(this.dataset.action);
      menu.classList.remove('show');
    });
  }

  var subItems = menu.querySelectorAll('.cx-sn');
  for (var k = 0; k < subItems.length; k++) {
    subItems[k].addEventListener('click', function(e) {
      e.stopPropagation();
      var nodeType = this.dataset.nodeType;
      if (nodeType) {
        addNodeAtPosition(nodeType, contextPos);
        menu.classList.remove('show');
      }
    });
  }
}

function buildAddNodeSubmenu() {
  var cats = AutomationNodes.getCategories();
  var html = '<div class="cx-sub">';
  var catOrder = ['flow', 'action', 'detection', 'control', 'monitor', 'variable', 'preset', 'utility'];
  for (var ci = 0; ci < catOrder.length; ci++) {
    var catKey = catOrder[ci];
    var cat = cats[catKey];
    if (!cat) continue;
    html += '<div class="cx-sc">' + cat.name + '</div>';
    for (var ni = 0; ni < cat.nodes.length; ni++) {
      var nd = cat.nodes[ni];
      var def = AutomationNodes.getNodeDef(nd.type);
      var iconClass = (def && def.icon) ? def.icon : 'fa-solid fa-circle';
      var iconColor = (def && def.color) ? def.color : cat.color;
      html += '<div class="cx-sn" data-node-type="' + nd.type + '">' +
        '<i class="' + iconClass + '" style="color:' + iconColor + '"></i>' +
        '<span>' + nd.name + '</span></div>';
    }
  }
  html += '</div>';
  return html;
}

function addNodeAtPosition(nodeType, pos) {
  if (!pos) { addNodeToCenter(nodeType); return; }
  var cvArea = document.getElementById('cv-area');
  var canvasRect = cvArea.getBoundingClientRect();
  var vpOff = AutomationCore.getViewportOffset();
  var vpScale = AutomationCore.getViewportScale();
  var localX = (pos.x - canvasRect.left - vpOff.x) / vpScale;
  var localY = (pos.y - canvasRect.top - vpOff.y) / vpScale;
  var node = AutomationCore.addNodeAtPosition(nodeType, localX, localY);
  if (!node) { showToast('未知节点类型: ' + nodeType, 'err'); return; }
  AutomationCore.selectNode(node);
  updateStatusBar();
  updateMinimap();
  undoManager.push();
}

function hideContextMenu() {
  document.getElementById('ctx').classList.remove('show');
}

function handleContextAction(action) {
  if (!contextTarget && action !== 'paste' && action !== 'select_all' && action !== 'fit_view' && action !== 'clear_all' && action !== 'add_comment' && action !== 'add_group') return;
  switch (action) {
    case 'delete':
      if (contextTarget) {
        AutomationCore.lgGraphObj.remove(contextTarget);
        AutomationCore.selectedNode = null;
        AutomationProperty.render(null);
        updateStatusBar();
        updateMinimap();
        undoManager.push();
      }
      break;
    case 'duplicate':
      if (contextTarget) {
        var cloned = contextTarget.clone();
        if (cloned) {
          AutomationCore.lgGraphObj.add(cloned);
          AutomationCore.selectNode(cloned);
          updateStatusBar();
          updateMinimap();
          undoManager.push();
        }
      }
      break;
    case 'disconnect':
      if (contextTarget) {
        AutomationCore.disconnectNode(contextTarget.id);
        updateStatusBar();
        updateMinimap();
        undoManager.push();
        showToast('已断开所有连线', 'inf');
      }
      break;
    case 'copy':
      if (contextTarget) {
        _clipboard = [{
          nodeType: contextTarget._defKey,
          params: JSON.parse(JSON.stringify(contextTarget.properties || {})),
          pos: { x: contextTarget.pos[0], y: contextTarget.pos[1] }
        }];
        showToast('已复制节点: ' + (contextTarget.title || contextTarget._defKey), 'inf');
      }
      break;
    case 'paste':
      if (_clipboard) {
        var pastedNodes = [];
        for (var j = 0; j < _clipboard.length; j++) {
          var item = _clipboard[j];
          var newNode = AutomationCore.addNodeAtPosition(item.nodeType, item.pos.x + 40, item.pos.y + 40);
          if (newNode) {
            for (var pk in item.params) {
              if (item.params.hasOwnProperty(pk)) {
                newNode.properties[pk] = JSON.parse(JSON.stringify(item.params[pk]));
              }
            }
            AutomationCore.refreshNode(newNode);
            pastedNodes.push(newNode);
          }
        }
        if (pastedNodes.length > 0) {
          if (pastedNodes.length === 1) {
            AutomationCore.selectNode(pastedNodes[0]);
            AutomationProperty.render(pastedNodes[0]);
          }
          updateStatusBar();
          updateMinimap();
          undoManager.push();
          showToast('已粘贴 ' + pastedNodes.length + ' 个节点', 'ok');
        }
      } else {
        showToast('剪贴板为空，请先复制节点', 'warn');
      }
      break;
    case 'select_all':
      AutomationCore.selectAll();
      showToast('已全选 ' + AutomationCore.getSelectedNodes().length + ' 个节点', 'inf');
      break;
    case 'fit_view':
      fitView();
      break;
    case 'clear_all':
      if (AutomationCore.getNodes().length > 0 || AutomationCore.getAnnotations().length > 0 || AutomationCore.getGroups().length > 0) {
        AutomationCore.clearAll();
        AutomationProperty.render(null);
        updateStatusBar();
        updateMinimap();
        undoManager.push();
        showToast('画布已清空', 'inf');
      }
      break;
    case 'add_comment':
      console.log('[DEBUG] add_comment triggered, contextPos:', contextPos);
      if (contextPos) {
        var r = AutomationCore.lgCanvas.canvas.getBoundingClientRect();
        var x = (contextPos.x - r.left - AutomationCore.getViewportOffset().x) / AutomationCore.getViewportScale();
        var y = (contextPos.y - r.top - AutomationCore.getViewportOffset().y) / AutomationCore.getViewportScale();
        console.log('[DEBUG] addAnnotation called with x:', x, 'y:', y);
        AutomationCore.addAnnotation(x, y, '双击编辑注释');
        undoManager.push();
      }
      break;
    case 'add_group':
      console.log('[DEBUG] add_group triggered, contextPos:', contextPos);
      if (contextPos) {
        var r2 = AutomationCore.lgCanvas.canvas.getBoundingClientRect();
        var x2 = (contextPos.x - r2.left - AutomationCore.getViewportOffset().x) / AutomationCore.getViewportScale();
        var y2 = (contextPos.y - r2.top - AutomationCore.getViewportOffset().y) / AutomationCore.getViewportScale();
        console.log('[DEBUG] addGroup called with x:', x2 - 150, 'y:', y2 - 100);
        AutomationCore.addGroup(x2 - 150, y2 - 100, 300, 200, '分组');
        undoManager.push();
      }
      break;
  }
}

function browseMacroPath(nodeId) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.list_macro_tree) {
    window.pywebview.api.list_macro_tree('').then(function(res) {
      var treeData = (res && res.tree) ? res.tree : (res && res.items ? res.items : null);
      if (treeData) {
        showMacroTreePicker(nodeId, treeData);
      } else {
        showToast('未找到宏文件', 'warn');
      }
    }).catch(function() { showToast('无法访问宏目录', 'err'); });
  } else if (window.pywebview && window.pywebview.api && window.pywebview.api.list_macros) {
    window.pywebview.api.list_macros().then(function(res) {
      var items = (res && res.items) ? res.items : (res && res.data ? res.data : []);
      if (items && items.length > 0) {
        showMacroPicker(nodeId, items);
      } else {
        showToast('未找到宏文件', 'warn');
      }
    }).catch(function() { showToast('无法访问宏目录', 'err'); });
  } else {
    showToast('需要后端支持以浏览宏文件', 'inf');
  }
}

function showMacroTreePicker(nodeId, treeData) {
  var modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.innerHTML =
    '<div class="modal-content" style="width:420px;max-height:520px">' +
      '<div class="modal-header"><span>选择宏</span><button class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()"><i class="fa-solid fa-xmark"></i></button></div>' +
      '<div class="modal-body" style="padding:8px;max-height:420px;overflow-y:auto">' +
        '<ul id="macro-tree-picker-list" style="list-style:none;padding:0;margin:0"></ul>' +
      '</div>' +
    '</div>';
  document.body.appendChild(modal);

  var listContainer = modal.querySelector('#macro-tree-picker-list');
  if (listContainer && window.renderMacroTreeList) {
    window.renderMacroTreeList({
      container: listContainer,
      tree: treeData,
      viewId: 'auto-macro-picker',
      selectedPath: null,
      openedPath: null,
      onSelect: function(path) {
        var node = AutomationCore.lgGraphObj ? AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
        if (node) {
          node.properties.path = path;
          AutomationProperty.render(node);
          AutomationCore.refreshNode(node);
        }
        modal.remove();
      },
      onFill: function(path) {
        var node = AutomationCore.lgGraphObj ? AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
        if (node) {
          node.properties.path = path;
          AutomationProperty.render(node);
          AutomationCore.refreshNode(node);
        }
        modal.remove();
      }
    });
  } else {
    listContainer.innerHTML = '<div style="padding:12px;color:var(--txt3);text-align:center">宏树组件未加载</div>';
  }
  modal.addEventListener('click', function(e) { if (e.target === modal) modal.remove(); });
}

function browseTemplatePath(nodeId) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.list_templates) {
    window.pywebview.api.list_templates().then(function(res) {
      if (res && res.ok && res.data && res.data.length > 0) {
        showTemplatePicker(nodeId, res.data);
      } else {
        showToast('未找到模板图片，请将图片放入"图片模板"文件夹', 'warn');
      }
    }).catch(function() { showToast('无法访问模板目录', 'err'); });
  } else {
    showToast('需要后端支持以浏览模板图片', 'inf');
  }
}

function showTemplatePicker(nodeId, templates) {
  var modal = document.createElement('div');
  modal.className = 'modal-overlay';
  var listHtml = '';
  for (var i = 0; i < templates.length; i++) {
    listHtml += '<div class="cx-i" data-path="' + templates[i].path + '" style="padding:10px 14px">' + templates[i].name + '</div>';
  }
  modal.innerHTML =
    '<div class="modal-content" style="width:400px;max-height:500px">' +
      '<div class="modal-header"><span>选择模板图片</span><button class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()"><i class="fa-solid fa-xmark"></i></button></div>' +
      '<div class="modal-body" style="padding:4px 0;max-height:380px;overflow-y:auto">' + listHtml + '</div>' +
    '</div>';
  document.body.appendChild(modal);
  var pathItems = modal.querySelectorAll('[data-path]');
  for (var j = 0; j < pathItems.length; j++) {
    pathItems[j].addEventListener('click', function() {
      var node = AutomationCore.lgGraphObj ? AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
      if (node) {
        node.properties.template_path = this.dataset.path;
        AutomationProperty.render(node);
        AutomationCore.refreshNode(node);
      }
      modal.remove();
    });
  }
  modal.addEventListener('click', function(e) { if (e.target === modal) modal.remove(); });
}

function showMacroPicker(nodeId, macros) {
  var modal = document.createElement('div');
  modal.className = 'modal-overlay';
  var listHtml = '';
  for (var i = 0; i < macros.length; i++) {
    listHtml += '<div class="cx-i" data-path="' + macros[i].path + '" style="padding:10px 14px">' + macros[i].name + '</div>';
  }
  modal.innerHTML =
    '<div class="modal-content" style="width:400px;max-height:500px">' +
      '<div class="modal-header"><span>选择宏文件</span><button class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()"><i class="fa-solid fa-xmark"></i></button></div>' +
      '<div class="modal-body" style="padding:4px 0;max-height:380px;overflow-y:auto">' + listHtml + '</div>' +
    '</div>';
  document.body.appendChild(modal);
  var pathItems = modal.querySelectorAll('[data-path]');
  for (var j = 0; j < pathItems.length; j++) {
    pathItems[j].addEventListener('click', function() {
      var node = AutomationCore.lgGraphObj ? AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
      if (node) {
        node.properties.path = this.dataset.path;
        AutomationProperty.render(node);
        AutomationCore.refreshNode(node);
      }
      modal.remove();
    });
  }
  modal.addEventListener('click', function(e) { if (e.target === modal) modal.remove(); });
}

function browseWindowList(nodeId, paramKey) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_window_list) {
    window.pywebview.api.get_window_list().then(function(res) {
      if (res && res.ok && res.data && res.data.length > 0) {
        showWindowPicker(nodeId, paramKey, res.data);
      } else {
        showToast('未找到可见窗口', 'warn');
      }
    }).catch(function() { showToast('无法获取窗口列表', 'err'); });
  } else {
    showToast('需要后端支持以选择窗口', 'inf');
  }
}

function showWindowPicker(nodeId, paramKey, windows) {
  var modal = document.createElement('div');
  modal.className = 'modal-overlay';
  var listHtml = '';
  for (var i = 0; i < windows.length; i++) {
    var w = windows[i];
    var displayText = w.title + ' [' + w.class_name + ']';
    listHtml += '<div class="cx-i" data-hwnd="' + w.hwnd + '" data-hwnd-title="' + w.title.replace(/"/g, '&quot;') + '" style="padding:8px 14px;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="' + displayText.replace(/"/g, '&quot;') + '">' + displayText + '</div>';
  }
  modal.innerHTML =
    '<div class="modal-content" style="width:450px;max-height:500px">' +
      '<div class="modal-header"><span>选择窗口</span><button class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()"><i class="fa-solid fa-xmark"></i></button></div>' +
      '<div class="modal-body" style="padding:4px 0;max-height:380px;overflow-y:auto">' + listHtml + '</div>' +
    '</div>';
  document.body.appendChild(modal);
  var items = modal.querySelectorAll('[data-hwnd-title]');
  for (var j = 0; j < items.length; j++) {
    items[j].addEventListener('click', function() {
      var node = AutomationCore.lgGraphObj ? AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
      if (node) {
        node.properties[paramKey] = this.dataset.hwnd;
        AutomationProperty.render(node);
        AutomationCore.refreshNode(node);
      }
      modal.remove();
    });
  }
  modal.addEventListener('click', function(e) { if (e.target === modal) modal.remove(); });
}

function runPreview(defKey, nodeId) {
  var node = AutomationCore.lgGraphObj ? AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
  if (!node) return;
  var area = document.getElementById('preview-area');
  if (!area) return;
  area.innerHTML = '<span style="color:var(--txt3)">正在预览...</span>';

  if (window.pywebview && window.pywebview.api) {
    var params = node.properties;
    if (defKey.indexOf('check_color') >= 0 || defKey.indexOf('monitor_color') >= 0) {
      window.pywebview.api.preview_color(params.mode, JSON.stringify(params.rect || [0,0,10,10]), params.hwnd_var || '')
        .then(function(res) {
          if (res && res.ok && res.data) {
            var d = res.data;
            area.innerHTML = '<div style="text-align:center">' +
              '<div style="display:flex;align-items:center;gap:8px;justify-content:center">' +
                '<div style="width:24px;height:24px;border-radius:4px;background:' + (d.center_color || '#000') + ';border:1px solid var(--border)"></div>' +
                '<span style="font-family:var(--fmo);font-size:13px">' + (d.center_color || 'N/A') + '</span>' +
              '</div></div>';
          } else {
            area.innerHTML = '<span style="color:var(--red)">' + ((res && res.error) || '预览失败') + '</span>';
          }
        })
        .catch(function(err) { area.innerHTML = '<span style="color:var(--red)">' + (err.message || err) + '</span>'; });
    } else if (defKey.indexOf('check_ocr') >= 0 || defKey.indexOf('monitor_ocr') >= 0) {
      window.pywebview.api.preview_ocr(params.mode, JSON.stringify(params.rect || [0,0,100,30]), params.hwnd_var || '', params.engine || 'rapidocr')
        .then(function(res) {
          if (res && res.ok && res.data) {
            var d = res.data;
            area.innerHTML = '<div style="text-align:center">' +
              '<div style="font-family:var(--fmo);font-size:13px">' + (d.text || '(空)') + '</div>' +
              '<div style="font-size:10px;color:var(--txt3);margin-top:4px">置信度: ' + (d.confidence ? d.confidence.toFixed(1) : '-') + '%</div>' +
            '</div>';
          } else {
            area.innerHTML = '<span style="color:var(--red)">' + ((res && res.error) || '预览失败') + '</span>';
          }
        })
        .catch(function(err) { area.innerHTML = '<span style="color:var(--red)">' + (err.message || err) + '</span>'; });
    } else {
      area.innerHTML = '<span style="color:var(--txt3)">此节点暂不支持预览</span>';
    }
  } else {
    setTimeout(function() {
      area.innerHTML = '<div style="text-align:center;color:var(--txt3)">需要后端支持</div>';
    }, 500);
  }
}

function initEditor() {
  var cvArea = document.getElementById('cv-area');

  AutomationCore.init(cvArea);

  AutomationCore.onGraphChange(function() {
    _graphDirty = true;
  });

  AutomationEvents.init();

  AutomationNodes.init(function() {
    renderToolbox();
    console.log('[自动化编辑器] 节点定义加载完成');
  });

  cvArea.addEventListener('dragover', function(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  });
  cvArea.addEventListener('drop', function(e) {
    e.preventDefault();
    e.stopPropagation();
    var toolType = e.dataTransfer.getData('tool-type');
    if (toolType === 'annotation') {
      var local = AutomationCore.screenToLocal(e.clientX, e.clientY);
      var an = AutomationCore.addAnnotation(local.x - 50, local.y - 15, '双击编辑注释');
      updateStatusBar();
      updateMinimap();
      undoManager.push();
      return;
    }
    if (toolType === 'group') {
      var gLocal = AutomationCore.screenToLocal(e.clientX, e.clientY);
      var gp = AutomationCore.addGroup(gLocal.x - 150, gLocal.y - 100, 300, 200, '分组');
      updateStatusBar();
      updateMinimap();
      undoManager.push();
      return;
    }
    var nodeType = e.dataTransfer.getData('text/plain') || e.dataTransfer.getData('node-type');
    if (!nodeType) return;
    var node = AutomationCore.addNodeAtMouse(nodeType, e);
    if (node) {
      AutomationCore.selectNode(node);
      updateStatusBar();
      updateMinimap();
      undoManager.push();
    }
  });

  AutomationCore.lgGraphObj.onNodeAdded = function() { updateStatusBar(); updateMinimap(); undoManager.push(); };
  AutomationCore.lgGraphObj.onNodeRemoved = function() { updateStatusBar(); updateMinimap(); undoManager.push(); };
  AutomationCore.lgGraphObj.onConnectionChange = function() { updateStatusBar(); updateMinimap(); undoManager.push(); };

  AutomationCore.lgCanvas.onNodeSelected = function(node) {
    AutomationCore.selectedNode = node;
    AutomationProperty.render(node);
  };
  AutomationCore.lgCanvas.onNodeDeselected = function(node) {
    AutomationCore.selectedNode = null;
    AutomationProperty.render(null);
  };

  cvArea.addEventListener('mousemove', function(e) {
    var local = AutomationCore.screenToLocal(e.clientX, e.clientY);
    document.getElementById('s-pos').textContent = Math.round(local.x) + ', ' + Math.round(local.y);
  });

  cvArea.addEventListener('contextmenu', function(e) {
    e.preventDefault();
    e.stopPropagation();
    var nodeEl = e.target.closest('.nd');
    if (nodeEl) {
      var nid = parseInt(nodeEl.dataset.id);
      contextTarget = AutomationCore.lgGraphObj.getNodeById(nid);
      showContextMenu(e.clientX, e.clientY, [
        { label: '复制', icon: 'fa-regular fa-copy', action: 'copy', shortcut: 'Ctrl+C' },
        { label: '重复', icon: 'fa-regular fa-clone', action: 'duplicate', shortcut: 'Ctrl+D' },
        '---',
        { label: '断开所有连线', icon: 'fa-solid fa-link-slash', action: 'disconnect' },
        { label: '删除节点', icon: 'fa-solid fa-trash-can', action: 'delete', shortcut: 'Del' },
      ]);
    } else {
      contextTarget = null;
      contextPos = { x: e.clientX, y: e.clientY };
      showContextMenu(e.clientX, e.clientY, [
        { label: '添加节点', icon: 'fa-solid fa-plus', action: 'add_node', submenu: true },
        '---',
        { label: '添加注释', icon: 'fa-solid fa-note-sticky', action: 'add_comment' },
        { label: '添加分组', icon: 'fa-solid fa-object-group', action: 'add_group' },
        '---',
        { label: '粘贴', icon: 'fa-regular fa-paste', action: 'paste', shortcut: 'Ctrl+V' },
        { label: '全选', icon: 'fa-solid fa-object-group', action: 'select_all', shortcut: 'Ctrl+A' },
        '---',
        { label: '适配视图', icon: 'fa-solid fa-expand', action: 'fit_view', shortcut: 'Home' },
        { label: '清空画布', icon: 'fa-solid fa-trash', action: 'clear_all' },
      ]);
    }
  });

  cvArea.addEventListener('mousedown', function() { hideContextMenu(); });

  document.getElementById('btn-run').addEventListener('click', runGraph);
  document.getElementById('btn-stop').addEventListener('click', function() { stopGraph(); });
  document.getElementById('btn-pause').addEventListener('click', pauseGraph);
  document.getElementById('btn-export').addEventListener('click', exportGraph);
  document.getElementById('btn-import').addEventListener('click', importGraph);
  document.getElementById('btn-save').addEventListener('click', saveGraph);
  document.getElementById('btn-new').addEventListener('click', newCanvas);
  document.getElementById('btn-zoom-in').addEventListener('click', function() { AutomationCore.zoomIn(); updateStatusBar(); });
  document.getElementById('btn-zoom-out').addEventListener('click', function() { AutomationCore.zoomOut(); updateStatusBar(); });
  document.getElementById('btn-zoom-reset').addEventListener('click', function() { AutomationCore.zoomReset(); updateStatusBar(); });
  document.getElementById('btn-fit-view').addEventListener('click', fitView);
  document.getElementById('btn-fullscreen').addEventListener('click', toggleFullscreen);
  document.getElementById('file-input-import').addEventListener('change', handleFileImport);

  var btnAddComment = document.getElementById('btn-add-comment');
  if (btnAddComment) {
    btnAddComment.addEventListener('dragstart', function(e) {
      e.dataTransfer.setData('text/plain', '__annotation__');
      e.dataTransfer.setData('tool-type', 'annotation');
      e.dataTransfer.effectAllowed = 'copy';
    });
  }
  var btnAddGroup = document.getElementById('btn-add-group');
  if (btnAddGroup) {
    btnAddGroup.addEventListener('dragstart', function(e) {
      e.dataTransfer.setData('text/plain', '__group__');
      e.dataTransfer.setData('tool-type', 'group');
      e.dataTransfer.effectAllowed = 'copy';
    });
  }

  var btnToolbox = document.getElementById('btn-toolbox');
  var toolboxExpand = document.getElementById('toolbox-expand');
  var pluginExpand = document.getElementById('plugin-expand');
  if (btnToolbox && toolboxExpand) {
    btnToolbox.addEventListener('click', function() {
      var isOpen = toolboxExpand.style.display !== 'none';
      toolboxExpand.style.display = isOpen ? 'none' : 'flex';
      if (pluginExpand) pluginExpand.style.display = 'none';
      btnToolbox.classList.toggle('active', !isOpen);
      var pluginBtn = document.getElementById('btn-plugin');
      if (pluginBtn) pluginBtn.classList.remove('active');
    });
  }

  var btnPlugin = document.getElementById('btn-plugin');
  if (btnPlugin && pluginExpand) {
    btnPlugin.addEventListener('click', function() {
      var isOpen = pluginExpand.style.display !== 'none';
      pluginExpand.style.display = isOpen ? 'none' : 'flex';
      if (toolboxExpand) toolboxExpand.style.display = 'none';
      btnPlugin.classList.toggle('active', !isOpen);
      var tbBtn = document.getElementById('btn-toolbox');
      if (tbBtn) tbBtn.classList.remove('active');
    });
  }

  var btnLineDelete = document.getElementById('btn-line-delete');
  if (btnLineDelete) {
    btnLineDelete.addEventListener('click', function() {
      var isActive = btnLineDelete.classList.toggle('active');
      AutomationCore.setLineDeleteMode(isActive);
      if (isActive) {
        showToast('连线删除模式已启用，长按拖动删除连线', 'inf');
      }
    });
  }

  var btnPluginNotify = document.getElementById('btn-plugin-notify');
  if (btnPluginNotify) {
    btnPluginNotify.addEventListener('dragstart', function(e) {
      e.dataTransfer.setData('text/plain', 'plugin/notify');
      e.dataTransfer.setData('node-type', 'plugin/notify');
      e.dataTransfer.effectAllowed = 'copy';
    });
  }

  var scriptNameInput = document.getElementById('script-name-input');
  if (scriptNameInput) {
    scriptNameInput.addEventListener('dblclick', renameScript);
    scriptNameInput.addEventListener('blur', function() { finishRenameScript(this); });
    scriptNameInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') { e.preventDefault(); finishRenameScript(this); }
      if (e.key === 'Escape') {
        this.value = _currentScriptName || '未命名脚本';
        finishRenameScript(this);
      }
    });
  }

  document.getElementById('ns-in').addEventListener('input', function(e) {
    renderToolbox(e.target.value);
  });

  var mmCanvas = document.getElementById('minimap-canvas');
  var mmDragging = false;
  mmCanvas.addEventListener('mousedown', function(e) {
    mmDragging = true;
    AutomationCore.navigateMinimap(e.clientX, e.clientY);
    e.stopPropagation();
    e.preventDefault();
  });
  document.addEventListener('mousemove', function(e) {
    if (mmDragging) {
      AutomationCore.navigateMinimap(e.clientX, e.clientY);
    }
  });
  document.addEventListener('mouseup', function() {
    mmDragging = false;
  });

  document.addEventListener('keydown', function(e) {
    if (AutomationTools._pickMode && e.key === 'Escape') {
      AutomationTools._hideScreenshotOverlay();
      return;
    }

    var tag = e.target.tagName.toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') {
      if (e.key === 'Escape') e.target.blur();
      return;
    }

    if (_hotkeyEnabled) {
      if (e.key === _hotkeyRun) { e.preventDefault(); runGraph(); }
      if (e.key === _hotkeyPause) { e.preventDefault(); pauseGraph(); }
      if (e.key === _hotkeyStop) { e.preventDefault(); stopGraph(); }
      if (e.key === _hotkeyFullscreen) { e.preventDefault(); toggleFullscreen(); }
      if (e.key === 'Escape') {
        if (_isFullscreen) { toggleFullscreen(); return; }
        if (AutomationCore.executionState === 'RUNNING' || AutomationCore.executionState === 'PAUSED') {
          stopGraph();
        }
        hideContextMenu();
      }
    }
    if (e.key === 'Home') { e.preventDefault(); fitView(); }
    if (e.key === 'Delete') {
      var selNodes = AutomationCore.getSelectedNodes();
      if (selNodes.length > 0) {
        AutomationCore.deleteSelectedNodes();
        AutomationCore.selectedNode = null;
        AutomationProperty.render(null);
        updateStatusBar();
        updateMinimap();
        undoManager.push();
      } else if (AutomationCore.selectedNode) {
        AutomationCore.lgGraphObj.remove(AutomationCore.selectedNode);
        AutomationCore.selectedNode = null;
        AutomationProperty.render(null);
        updateStatusBar();
        updateMinimap();
        undoManager.push();
      }
    }
    if (e.ctrlKey && e.key === 's') { e.preventDefault(); saveGraph(); }
    if (e.ctrlKey && e.key === 'e') { e.preventDefault(); exportGraph(); }
    if (e.ctrlKey && e.key === 'z') { e.preventDefault(); undoManager.undo(); }
    if (e.ctrlKey && e.key === 'y') { e.preventDefault(); undoManager.redo(); }
    if (e.ctrlKey && e.key === 'a') {
      e.preventDefault();
      AutomationCore.selectAll();
      showToast('已全选 ' + AutomationCore.getSelectedNodes().length + ' 个节点', 'inf');
    }
    if (e.ctrlKey && e.key === 'c') {
      var target = e.target || e.srcElement;
      if (target && (target.tagName === 'TEXTAREA' || target.tagName === 'INPUT' || target.contentEditable === 'true')) {
        return;
      }
      var selNodes = AutomationCore.getSelectedNodes();
      if (selNodes.length > 0) {
        e.preventDefault();
        _clipboard = [];
        for (var i = 0; i < selNodes.length; i++) {
          _clipboard.push({
            nodeType: selNodes[i]._defKey,
            params: JSON.parse(JSON.stringify(selNodes[i].properties || {})),
            pos: { x: selNodes[i].pos[0], y: selNodes[i].pos[1] }
          });
        }
        showToast('已复制 ' + _clipboard.length + ' 个节点', 'inf');
      } else if (AutomationCore.selectedNode) {
        e.preventDefault();
        _clipboard = [{
          nodeType: AutomationCore.selectedNode._defKey,
          params: JSON.parse(JSON.stringify(AutomationCore.selectedNode.properties || {})),
          pos: { x: AutomationCore.selectedNode.pos[0], y: AutomationCore.selectedNode.pos[1] }
        }];
        showToast('已复制节点: ' + (AutomationCore.selectedNode.title || AutomationCore.selectedNode._defKey), 'inf');
      }
    }
    if (e.ctrlKey && e.key === 'v' && _clipboard) {
      var target = e.target || e.srcElement;
      if (target && (target.tagName === 'TEXTAREA' || target.tagName === 'INPUT' || target.contentEditable === 'true')) {
        return;
      }
      e.preventDefault();
      var pastedNodes = [];
      for (var j = 0; j < _clipboard.length; j++) {
        var item = _clipboard[j];
        var newNode = AutomationCore.addNodeAtPosition(item.nodeType, item.pos.x + 40, item.pos.y + 40);
        if (newNode) {
          for (var pk in item.params) {
            if (item.params.hasOwnProperty(pk)) {
              newNode.properties[pk] = JSON.parse(JSON.stringify(item.params[pk]));
            }
          }
          AutomationCore.refreshNode(newNode);
          pastedNodes.push(newNode);
        }
      }
      if (pastedNodes.length > 0) {
        if (pastedNodes.length === 1) {
          AutomationCore.selectNode(pastedNodes[0]);
          AutomationProperty.render(pastedNodes[0]);
        }
        updateStatusBar();
        updateMinimap();
        undoManager.push();
        showToast('已粘贴 ' + pastedNodes.length + ' 个节点', 'ok');
      }
    }
    if (e.ctrlKey && e.key === 'd' && AutomationCore.selectedNode) {
      e.preventDefault();
      var cloned = AutomationCore.selectedNode.clone();
      if (cloned) {
        AutomationCore.lgGraphObj.add(cloned);
        AutomationCore.selectNode(cloned);
        AutomationProperty.render(cloned);
        updateStatusBar();
        undoManager.push();
      }
    }
  });

  document.addEventListener('click', function(e) {
    if (!e.target.closest('#ctx')) hideContextMenu();
    var colorMenus = document.querySelectorAll('.gp-color-menu.show');
    for (var i = 0; i < colorMenus.length; i++) {
      if (!colorMenus[i].contains(e.target)) {
        colorMenus[i].classList.remove('show');
      }
    }
  });

  window.addEventListener('resize', function() {
    updateMinimap();
  });

  setExecutionState('idle');
  updateStatusBar();
  updateMinimap();
  setInterval(function() { updateMinimap(); }, 280);
  undoManager.reset();

  initSidebarResize();
  initSidebarToggle();
  requestAnimationFrame(function() { _repositionMinimap(); });

  var existingNodes = AutomationCore.lgGraphObj.getNodes();
  if (existingNodes.length === 0) {
      function addStartWhenReady() {
          var cv = document.getElementById('cv-area');
          if (cv && cv.clientWidth > 0 && cv.clientHeight > 0) {
              AutomationCore.zoomReset();
              addNodeToCenter('flow/start');
              _repositionMinimap();
          } else {
              requestAnimationFrame(addStartWhenReady);
          }
      }
      requestAnimationFrame(addStartWhenReady);
  }

  console.log('[自动化编辑器] V2.0 DOM渲染引擎初始化完成');
}

window._autoEditor = {
  showToast: showToast,
  setExecutionState: setExecutionState,
  updateStatusBar: updateStatusBar,
  serializeGraph: serializeGraph,
  deserializeGraph: deserializeGraph,
  runPreview: runPreview,
  browseMacroPath: browseMacroPath,
  browseTemplatePath: browseTemplatePath,
  browseWindowList: browseWindowList,
  addNodeToCenter: addNodeToCenter,
  clearNodeHighlights: function() { AutomationCore.clearAllHighlights(); },
  undoPush: function() { undoManager.push(); },
};

window.AutomationApp = window._autoEditor;

document.addEventListener('DOMContentLoaded', initEditor);
