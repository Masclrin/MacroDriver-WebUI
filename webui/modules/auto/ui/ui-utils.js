import { serializeGraph, deserializeGraph } from '../graph/graph-serializer.js';
import { updateVarPanel } from './var-panel.js';

export var undoManager = {
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
      var selectedId = window.AutomationCore.getSelectedNodes()[0]?.id;
      deserializeGraph(data);
      if (window.AutomationProperty) {
        if (selectedId) {
          var restoredNode = window.AutomationCore.lgGraphObj.getNodeById(selectedId);
          window.AutomationProperty.render(restoredNode);
        } else {
          window.AutomationProperty.render(null);
        }
      }
    } catch(e) {
      console.error('[UndoManager] restore error:', e);
    } finally {
      this._paused = false;
    }
  },
  reset: function() { this._stack = []; this._idx = -1; this.push(); }
};

export function setExecutionState(state) {
  state = state.toUpperCase();
  window.AutomationCore.executionState = state;
  var dot = document.getElementById('st-dot');
  var txt = document.getElementById('st-txt');
  if (state === 'RUNNING') {
    dot.style.background = 'var(--c-action)';
    dot.classList.add('run-i');
    txt.textContent = '运行中';
    var btnRun = document.getElementById('btn-run');
    if (btnRun) {
      btnRun.disabled = true;
      btnRun.style.opacity = '0.5';
      btnRun.style.pointerEvents = 'none';
      var icon = btnRun.querySelector('i');
      if (icon) { icon.className = 'fa-solid fa-spinner fa-spin'; }
    }
  } else if (state === 'PAUSED') {
    dot.style.background = 'var(--c-detect)';
    dot.classList.remove('run-i');
    txt.textContent = '已暂停';
    var btnRun = document.getElementById('btn-run');
    if (btnRun) {
      btnRun.disabled = false; btnRun.style.opacity = ''; btnRun.style.pointerEvents = ''; btnRun.style.boxShadow = '';
      var icon = btnRun.querySelector('i');
      if (icon) { icon.className = 'fa-solid fa-play'; }
    }
  } else if (state === 'COMPLETED') {
    dot.style.background = 'var(--c-ok,#22c55e)';
    dot.classList.remove('run-i');
    txt.textContent = '已完成';
    var btnRun = document.getElementById('btn-run');
    if (btnRun) {
      btnRun.disabled = false; btnRun.style.opacity = ''; btnRun.style.pointerEvents = ''; btnRun.style.boxShadow = '';
      var icon = btnRun.querySelector('i');
      if (icon) { icon.className = 'fa-solid fa-play'; }
    }
  } else {
    dot.style.background = 'var(--txt3)';
    dot.classList.remove('run-i');
    txt.textContent = '就绪';
    var btnRun = document.getElementById('btn-run');
    if (btnRun) {
      btnRun.disabled = false; btnRun.style.opacity = ''; btnRun.style.pointerEvents = '';
      var icon = btnRun.querySelector('i');
      if (icon) { icon.className = 'fa-solid fa-play'; }
    }
  }
}

export function updateStatusBar() {
  var nodes = window.AutomationCore.getNodes();
  var conns = window.AutomationCore.getConnections();
  var monitorCount = 0;
  var varNames = {};
  for (var i = 0; i < nodes.length; i++) {
    var n = nodes[i];
    if (n._category === 'monitor') monitorCount++;
    if (n.properties && n.properties.store_var) {
      varNames[n.properties.store_var] = true;
    }
    if (n.properties && n.properties.counter_var && n._defKey && n._defKey.indexOf('loop_count') >= 0) {
      varNames[n.properties.counter_var] = true;
    }
    if (n.properties && n.properties.store_hwnd_var) {
      varNames[n.properties.store_hwnd_var] = true;
    }
    if (n.properties && n.properties.store_number) {
      varNames[n.properties.store_number] = true;
    }
    if (n.properties && (n._defKey || '').indexOf('var_set') >= 0 && n.properties.vars_json) {
      try {
        var multiVars = JSON.parse(n.properties.vars_json || '[]');
        if (Array.isArray(multiVars)) {
          for (var mi = 0; mi < multiVars.length; mi++) {
            if (multiVars[mi] && multiVars[mi].name) varNames[multiVars[mi].name] = true;
          }
        }
      } catch(e) {}
    }
  }
  document.getElementById('s-n').textContent = nodes.length;
  document.getElementById('s-c').textContent = conns.length;
  document.getElementById('s-m').textContent = monitorCount;
  document.getElementById('s-v').textContent = Object.keys(varNames).length;
  document.getElementById('s-zm').textContent = Math.round(window.AutomationCore.getZoomLevel() * 100) + '%';
  document.getElementById('zm-lv').textContent = Math.round(window.AutomationCore.getZoomLevel() * 100) + '%';

  var emptyHint = document.getElementById('empty-hint');
  if (emptyHint) {
    emptyHint.style.opacity = nodes.length === 0 ? '1' : '0';
  }

  updateVarPanel(nodes);
}
