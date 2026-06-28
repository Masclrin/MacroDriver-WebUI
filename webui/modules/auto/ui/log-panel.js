import { showToast } from '../app/toast.js';

var _logFloating = false;
var _logData = { runs: [], enabled: false, continuous: false, current_run_id: 0 };
var _logEnabled = false;
var _logPollTimer = null;
var _timeMode = 'timeline';
var _nameMode = 'zh';
var _continuousUserChoice = false;

export function toggleLogPanel() {
  var logFloat = document.getElementById('log-float');
  if (!logFloat) return;
  if (logFloat.classList.contains('visible')) { dockLogPanel(); } else { undockLogPanel(); }
}

export function undockLogPanel() {
  var logFloat = document.getElementById('log-float');
  if (!logFloat) return;
  logFloat.classList.add('visible');
  _logFloating = true;
  _logEnabled = true;
  setLogEnabledBackend(true);
  var lfModeOn = document.getElementById('lf-mode-on');
  var lfModeOff = document.getElementById('lf-mode-off');
  if (lfModeOn) lfModeOn.classList.add('active');
  if (lfModeOff) lfModeOff.classList.remove('active');
  var cvArea = document.getElementById('cv-area');
  if (cvArea && !logFloat.style.left) {
    var rect = cvArea.getBoundingClientRect();
    logFloat.style.left = (rect.left + 16) + 'px';
    logFloat.style.top = (rect.top + rect.height - 360) + 'px';
    logFloat.style.right = '';
  }
  _startLogPoll();
}

export function dockLogPanel() {
  var logFloat = document.getElementById('log-float');
  if (!logFloat) return;
  logFloat.classList.remove('visible');
  _logFloating = false;
  _stopLogPoll();
  _logEnabled = false;
  setLogEnabledBackend(false);
  var lfModeOn = document.getElementById('lf-mode-on');
  var lfModeOff = document.getElementById('lf-mode-off');
  if (lfModeOn) lfModeOn.classList.remove('active');
  if (lfModeOff) lfModeOff.classList.add('active');
}

export var isLogEnabled = function() { return _logEnabled; };

export function initLogPanel() {
  var btnLogPanel = document.getElementById('btn-log-panel');
  var lfClose = document.getElementById('lf-close');
  var lfDock = document.getElementById('lf-dock');
  var lfHeader = document.getElementById('lf-header');
  var lfClear = document.getElementById('lf-clear');
  var lfModeOff = document.getElementById('lf-mode-off');
  var lfModeOn = document.getElementById('lf-mode-on');
  var lfContBtn = document.getElementById('lf-continuous-btn');
  var lfStatusFilter = document.getElementById('lf-status-filter');

  if (btnLogPanel) {
    btnLogPanel.addEventListener('click', function() {
      var logFloat = document.getElementById('log-float');
      if (logFloat && logFloat.classList.contains('visible')) { dockLogPanel(); } else { undockLogPanel(); }
    });
  }

  if (lfClose) { lfClose.addEventListener('click', function() { dockLogPanel(); }); }
  if (lfDock) { lfDock.addEventListener('click', function() { dockLogPanel(); }); }

  if (lfClear) {
    lfClear.addEventListener('click', function() {
      _logData.runs = [];
      renderAll();
      if (window.pywebview && window.pywebview.api && window.pywebview.api.clear_execution_log) {
        window.pywebview.api.clear_execution_log().catch(function() {});
      }
    });
  }

  if (lfModeOff) {
    lfModeOff.addEventListener('click', function() {
      _logEnabled = false; this.classList.add('active');
      if (lfModeOn) lfModeOn.classList.remove('active');
      setLogEnabledBackend(false);
    });
  }

  if (lfModeOn) {
    lfModeOn.addEventListener('click', function() {
      _logEnabled = true; this.classList.add('active');
      if (lfModeOff) lfModeOff.classList.remove('active');
      setLogEnabledBackend(true);
    });
  }

  if (lfContBtn) {
    lfContBtn.addEventListener('click', function() {
      _continuousUserChoice = !_continuousUserChoice;
      _logData.continuous = _continuousUserChoice;
      this.classList.toggle('active', _continuousUserChoice);
      this.textContent = _continuousUserChoice ? '持续ON' : '持续OFF';
      if (window.pywebview && window.pywebview.api && window.pywebview.api.set_continuous_log) {
        window.pywebview.api.set_continuous_log(_continuousUserChoice).catch(function() {});
      }
    });
  }

  if (lfStatusFilter) {
    lfStatusFilter.addEventListener('change', function() { renderTable(); });
  }

  if (lfHeader) {
    var dragging = false, startX, startY, startLeft, startTop;
    lfHeader.addEventListener('mousedown', function(e) {
      if (e.target.closest('button') || e.target.closest('select')) return;
      dragging = true; startX = e.clientX; startY = e.clientY;
      var logFloat = document.getElementById('log-float');
      var rect = logFloat.getBoundingClientRect();
      startLeft = rect.left; startTop = rect.top;
      e.preventDefault();
    });
    document.addEventListener('mousemove', function(e) {
      if (!dragging) return;
      var logFloat = document.getElementById('log-float');
      logFloat.style.left = (startLeft + e.clientX - startX) + 'px';
      logFloat.style.top = (startTop + e.clientY - startY) + 'px';
      logFloat.style.right = '';
    });
    document.addEventListener('mouseup', function() { dragging = false; });
  }

  var lfContent = document.getElementById('lf-content');
  if (lfContent) {
    lfContent.addEventListener('click', function(e) {
      var row = e.target.closest('.lf-row');
      if (row) {
        var nid = parseInt(row.dataset.nid);
        if (!isNaN(nid)) {
          var nodes = window.AutomationCore ? window.AutomationCore.getNodes() : [];
          for (var i = 0; i < nodes.length; i++) {
            if (nodes[i].id === nid) {
              window.AutomationCore.selectNode(nodes[i]);
              if (window.AutomationProperty) window.AutomationProperty.render(nodes[i]);
              break;
            }
          }
        }
        return;
      }
      if (e.target.classList.contains('lf-th-name')) {
        _nameMode = _nameMode === 'zh' ? 'en' : 'zh';
        renderTable();
      }
      if (e.target.classList.contains('lf-th-time')) {
        _timeMode = _timeMode === 'timeline' ? 'duration' : 'timeline';
        renderTable();
      }
    });
  }

  renderAll();
}

function _startLogPoll() {
  _stopLogPoll();
  _fetchLogData();
  _logPollTimer = setInterval(_fetchLogData, 1000);
}

function _stopLogPoll() {
  if (_logPollTimer) { clearInterval(_logPollTimer); _logPollTimer = null; }
}

function _fetchLogData() {
  if (!_logFloating) return;
  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_execution_log) {
    window.pywebview.api.get_execution_log().then(function(res) {
      if (res && res.ok && res.data) {
        var newData = res.data;
        newData.continuous = _continuousUserChoice;
        _logData = newData;
        renderAll();
      }
    }).catch(function() {});
  } else { renderAll(); }
}

export function refreshLogPanel() { if (_logFloating) _fetchLogData(); }

function setLogEnabledBackend(enabled) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.enable_execution_log) {
    window.pywebview.api.enable_execution_log(enabled).catch(function() {});
  }
}

function _getNodeDefKey(nodeType) {
  return nodeType || '';
}

function _getNodeName(nodeType) {
  var def = window.AutomationNodes ? window.AutomationNodes.getNodeDef(nodeType) : null;
  return def ? def.display_name || nodeType : nodeType;
}

function _getNodeDisplayName(entry) {
  var nodeType = entry.node_type || '';
  var nodeId = entry.node_id;
  var base;
  if (_nameMode === 'zh') {
    base = _getNodeName(nodeType);
  } else {
    base = nodeType;
  }
  if (!base) base = '#' + nodeId;
  return base + ' #' + nodeId;
}

function _fmtTime(msVal) {
  var absVal = Math.abs(msVal);
  if (absVal >= 86400000)    return (msVal / 3600000).toFixed(3) + 'h';
  if (absVal >= 3600000)   return (msVal / 60000).toFixed(3) + 'min';
  if (absVal >= 60000) return (msVal / 1000).toFixed(3) + 's';
  
  return msVal.toFixed(3) + 'ms';
}


function _fmtOffset(msVal) {
  if (msVal < 0) msVal = 0;
  return _fmtTime(msVal);
}

function renderAll() {
  renderToolbarState();
  renderTable();
  updateSummary();
}

function renderToolbarState() {
  var lfModeOn = document.getElementById('lf-mode-on');
  var lfModeOff = document.getElementById('lf-mode-off');
  var lfContBtn = document.getElementById('lf-continuous-btn');

  if (_logEnabled) {
    if (lfModeOn) lfModeOn.classList.add('active');
    if (lfModeOff) lfModeOff.classList.remove('active');
  } else {
    if (lfModeOff) lfModeOff.classList.add('active');
    if (lfModeOn) lfModeOn.classList.remove('active');
  }

  if (lfContBtn) {
    lfContBtn.classList.toggle('active', !!_continuousUserChoice);
    lfContBtn.textContent = _continuousUserChoice ? '持续ON' : '持续OFF';
  }
}

function _computeAggregate(entries) {
  var map = {};
  for (var i = 0; i < entries.length; i++) {
    var e = entries[i];
    var key = e.node_type + '|' + e.node_id;
    var rec = map[key];
    if (!rec) {
      rec = { node_id: e.node_id, node_type: e.node_type, total_duration: 0, total_offset: 0, count: 0, min_offset: Infinity, max_offset: -Infinity, entries: [] };
      map[key] = rec;
    }
    rec.total_duration += e.duration_ms || 0;
    rec.total_offset += e.offset_ms || 0;
    rec.count++;
    if (e.offset_ms < rec.min_offset) rec.min_offset = e.offset_ms;
    if (e.offset_ms > rec.max_offset) rec.max_offset = e.offset_ms;
    rec.entries.push(e);
  }
  return map;
}

function renderTable() {
  var tbody = document.getElementById('lf-tbody');
  if (!tbody) return;

  var filterVal = (document.getElementById('lf-status-filter') || {}).value || '';
  var runs = _logData.runs || [];

  var entries = [];
  for (var ri = 0; ri < runs.length; ri++) {
    var re = runs[ri].entries || [];
    for (var ei = 0; ei < re.length; ei++) { entries.push(re[ei]); }
  }

  if (filterVal) { entries = entries.filter(function(e) { return e.status === filterVal; }); }

  var continuousOff = !_continuousUserChoice;
  var totalCols = continuousOff ? 4 : 6;

  if (entries.length === 0) {
    tbody.innerHTML = '<tr><td colspan="' + totalCols + '" style="text-align:center;color:var(--txt3);padding:12px">' +
      (!_logEnabled ? '日志已关闭，点击 ON 开启' :
       runs.length === 0 ? '等待执行数据...' : '当前筛选无结果') + '</td></tr>';
    return;
  }

  entries.sort(function(a, b) { return (a.offset_ms || 0) - (b.offset_ms || 0); });

  var aggregateMap = _computeAggregate(entries);
  var aggregateArr = [];
  for (var k in aggregateMap) { if (aggregateMap.hasOwnProperty(k)) aggregateArr.push(aggregateMap[k]); }
  aggregateArr.sort(function(a, b) { return (a.min_offset || 0) - (b.min_offset || 0); });

  var maxShow = 200;
  if (entries.length > maxShow) entries = entries.slice(0, maxShow);

  var timeLabel = _timeMode === 'timeline' ? '时间线' : '耗时';
  var nameLabel = _nameMode === 'zh' ? '节点' : 'Node';

  var html = '<tr class="lf-hdr">' +
    '<th style="width:32px">状态</th>' +
    '<th class="lf-th-name" style="cursor:pointer;color:var(--acc);user-select:none">' + nameLabel + '</th>' +
    '<th class="lf-th-time" style="cursor:pointer;color:var(--acc);text-align:right;user-select:none">' + timeLabel + '</th>';
  if (!continuousOff) {
    html += '<th style="text-align:right;width:34px">次数</th>' +
      '<th style="text-align:right;width:50px">平均</th>' +
      '<th style="width:24px;text-align:right">轮</th>';
  }
  html += '</tr>';

  for (var i = 0; i < aggregateArr.length; i++) {
    var agg = aggregateArr[i];
    var rep = agg.entries[0];
    for (var ei = 1; ei < agg.entries.length; ei++) {
      if ((agg.entries[ei].run_id || 0) > (rep.run_id || 0)) rep = agg.entries[ei];
    }
    var sc = rep.status === 'ok' ? 'lf-ok' : (rep.status === 'error' ? 'lf-err' : '');
    var si = rep.status === 'ok' ? '✓' : (rep.status === 'error' ? '✗' : '?');
    var dn = _getNodeDisplayName(rep);

    var ts;
    if (_timeMode === 'timeline') {
      ts = _fmtOffset(agg.min_offset);
    } else {
      ts = _fmtTime(rep.duration_ms || 0);
    }

    var avgTime;
    if (_timeMode === 'timeline') {
      avgTime = agg.count > 0 ? _fmtTime(agg.total_offset / agg.count) : '-';
    } else {
      avgTime = agg.count > 0 ? _fmtTime(agg.total_duration / agg.count) : '-';
    }
    var countStr = agg.count > 1 ? String(agg.count) : '-';

    html += '<tr class="lf-row" data-nid="' + rep.node_id + '" style="cursor:pointer">';
    html += '<td class="' + sc + '">' + si + '</td>';
    html += '<td class="lf-name" title="' + (rep.node_type || '').replace(/</g, '&lt;') + '">' + dn.replace(/</g, '&lt;') + '</td>';
    html += '<td class="lf-time">' + ts + '</td>';
    if (!continuousOff) {
      html += '<td class="lf-time" style="font-size:9px;color:var(--txt2)">' + countStr + '</td>';
      html += '<td class="lf-time" style="font-size:9px;color:var(--txt2)">' + (agg.count > 1 ? avgTime : '-') + '</td>';
      html += '<td class="lf-time" style="font-size:9px;color:var(--txt2)">' + rep.run_id + '</td>';
    }
    html += '</tr>';
  }
  tbody.innerHTML = html;
}

function updateSummary() {
  var el = document.getElementById('lf-summary');
  if (!el) return;
  var runs = _logData.runs || [];
  var tN = 0;
  for (var i = 0; i < runs.length; i++) {
    tN += (runs[i].entries || []).length;
  }
  var tD = 0;
  if (runs.length > 0) {
    var lastEntries = runs[runs.length - 1].entries || [];
    var maxEnd = 0;
    for (var j = 0; j < lastEntries.length; j++) {
      var e = lastEntries[j];
      var end = (e.offset_ms || 0) + (e.duration_ms || 0);
      if (end > maxEnd) maxEnd = end;
    }
    tD = maxEnd;
  }
  el.textContent = runs.length + '轮 | ' + tN + '节点 | 总耗时 ' + _fmtTime(tD) + ' | ' + (_logEnabled ? '记录中' : '已停止');
}