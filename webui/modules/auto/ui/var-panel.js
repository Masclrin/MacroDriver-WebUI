import { showToast } from '../app/toast.js';

var _varSearchVal = '';
var _varFilterType = '';

export function refreshVarPanel() {
  var nodes = window.AutomationCore.getNodes();
  updateVarPanel(nodes);
}

export function updateVarPanel(nodes) {
  var vlEl = document.getElementById('vl');
  var vlFloat = document.getElementById('vl-f');
  if (!vlEl && !vlFloat) return;
  if (!nodes) nodes = window.AutomationCore.getNodes();

  var builtinDefs = [
    {name: 'timestamp', desc: '时间戳(ms)', type: 'number'},
    {name: 'timestamp_s', desc: '时间戳(s)', type: 'number'},
    {name: 'date', desc: '日期', type: 'string'},
    {name: 'time', desc: '时间', type: 'string'},
    {name: 'datetime', desc: '日期时间', type: 'string'},
    {name: 'datetime_compact', desc: '紧凑日期时间', type: 'string'},
    {name: 'random', desc: '随机数', type: 'number'},
    {name: 'random_int', desc: '随机整数', type: 'number'},
    {name: 'year', desc: '年', type: 'number'},
    {name: 'month', desc: '月', type: 'number'},
    {name: 'day', desc: '日', type: 'number'},
    {name: 'hour', desc: '时', type: 'number'},
    {name: 'minute', desc: '分', type: 'number'},
    {name: 'second', desc: '秒', type: 'number'},
    {name: 'weekday', desc: '星期', type: 'number'},
    {name: 'pid', desc: '进程ID', type: 'number'},
  ];

  var userVars = [];
  var nodeOutputs = [];
  var typeLabels = {number: '数字', string: '文本', boolean: '布尔'};

  for (var i = 0; i < nodes.length; i++) {
    var node = nodes[i];
    var defKey = node._defKey || node.type || '';

    if (defKey.indexOf('var_set') >= 0 && node.properties.vars_json) {
      try {
        var multiVars = JSON.parse(node.properties.vars_json || '[]');
        if (Array.isArray(multiVars)) {
          for (var mi = 0; mi < multiVars.length; mi++) {
            if (multiVars[mi] && multiVars[mi].name) {
              userVars.push({name: multiVars[mi].name, type: multiVars[mi].type || 'string', nodeId: node.id, nodeLabel: node.title || defKey});
            }
          }
        }
      } catch(e) {}
    }
    if (defKey.indexOf('loop_count') >= 0 && node.properties.counter_var) {
      userVars.push({name: node.properties.counter_var, type: 'number', nodeId: node.id, nodeLabel: node.title || defKey});
    }
    if (node.properties.store_var) {
      var sType = 'string';
      if (defKey.indexOf('check_color') >= 0) { sType = 'string'; }
      else if (defKey.indexOf('check_image') >= 0) { sType = 'string'; }
      else if (defKey.indexOf('check_ocr') >= 0) { sType = 'string'; }
      else if (defKey.indexOf('check_digits') >= 0) { sType = 'number'; }
      else if (defKey.indexOf('check_screen') >= 0) { sType = 'boolean'; }
      else if (defKey.indexOf('monitor_color') >= 0) { sType = 'boolean'; }
      else if (defKey.indexOf('monitor_ocr') >= 0) { sType = 'string'; }
      else if (defKey.indexOf('preset_read_text') >= 0) { sType = 'string'; }
      else if (defKey.indexOf('preset_find_click') >= 0 || defKey.indexOf('preset_click') >= 0) { sType = 'boolean'; }
      userVars.push({name: node.properties.store_var, type: sType, nodeId: node.id, nodeLabel: node.title || defKey});
    }
    if (node.properties.store_number) {
      userVars.push({name: node.properties.store_number, type: 'number', nodeId: node.id, nodeLabel: node.title || defKey});
    }
    if (node.properties.store_hwnd_var) {
      userVars.push({name: node.properties.store_hwnd_var, type: 'string', nodeId: node.id, nodeLabel: node.title || defKey});
    }

    var def = window.AutomationNodes ? window.AutomationNodes.getNodeDef(defKey) : null;
    if (def && def.outputs) {
      for (var j = 0; j < def.outputs.length; j++) {
        var out = def.outputs[j];
        if (out.type === 'flow') continue;
        nodeOutputs.push({ref: node.id + '.' + out.name, name: out.name, type: out.type, nodeId: node.id, nodeLabel: (node.title || defKey) + ' #' + node.id});
      }
    }
  }

  var _collapsed = {};
  try { _collapsed = JSON.parse(localStorage.getItem('varPanel_collapsed') || '{}'); } catch(e) {}

  var varNameCounts = {};
  for (var vi = 0; vi < userVars.length; vi++) {
    varNameCounts[userVars[vi].name] = (varNameCounts[userVars[vi].name] || 0) + 1;
  }

  function renderVarPanel() {
    var searchVal = _varSearchVal;
    var filterType = _varFilterType;

    var barHtml = '';
    barHtml += '<div style="display:flex;gap:4px;padding:4px 6px;border-bottom:1px solid var(--border,#334155)">';
    barHtml += '<div style="flex:1;position:relative;display:flex;align-items:center">';
    barHtml += '<input class="var-search-in" type="text" placeholder="搜索变量..." style="flex:1;background:var(--bg,#0f172a);border:1px solid var(--border,#334155);border-radius:4px;color:var(--txt1,#f1f5f9);padding:2px 20px 2px 6px;font-size:11px;outline:none;width:100%" value="' + searchVal.replace(/"/g, '&quot;') + '">';
    barHtml += '<button class="var-search-clear" style="position:absolute;right:3px;top:50%;transform:translateY(-50%);background:none;border:none;color:var(--txt3,#64748b);cursor:pointer;padding:0;font-size:12px;line-height:1;display:' + (searchVal ? 'block' : 'none') + '" title="清空">×</button>';
    barHtml += '</div>';
    barHtml += '<select class="var-type-filter" style="background:var(--bg,#0f172a);border:1px solid var(--border,#334155);border-radius:4px;color:var(--txt1,#f1f5f9);padding:2px 4px;font-size:11px">';
    barHtml += '<option value="">全部</option><option value="string"' + (filterType === 'string' ? ' selected' : '') + '>文本</option><option value="number"' + (filterType === 'number' ? ' selected' : '') + '>数字</option><option value="boolean"' + (filterType === 'boolean' ? ' selected' : '') + '>布尔</option>';
    barHtml += '</select></div>';

    var listHtml = '';

    function matchesSearch(name) {
      if (!searchVal) return true;
      return name.toLowerCase().indexOf(searchVal.toLowerCase()) >= 0;
    }
    function matchesType(type) {
      if (!filterType) return true;
      return type === filterType;
    }

    var groups = [
      {id: 'builtin', label: '内置变量', color: 'var(--c-var)', items: builtinDefs.map(function(b) { return {name: b.name, desc: b.desc, type: b.type || 'string', ref: '${' + b.name + '}'}; })},
      {id: 'user', label: '用户变量', color: 'var(--c-action)', items: userVars.map(function(uv) {
        var count = varNameCounts[uv.name] || 1;
        var desc = '${' + uv.name + '}';
        if (count > 1) desc += ' (来自 ' + uv.nodeLabel + ')';
        return {name: uv.name, desc: desc, type: uv.type, ref: '${' + uv.name + '}', assignCount: count, nodeLabel: uv.nodeLabel};
      })},
      {id: 'output', label: '节点输出', color: 'var(--c-ctrl)', items: nodeOutputs.map(function(no) { return {name: no.nodeLabel, desc: '.' + no.name, type: no.type, ref: '${' + no.ref + '}'}; })}
    ];

    for (var gi = 0; gi < groups.length; gi++) {
      var group = groups[gi];
      var filtered = [];
      for (var fi = 0; fi < group.items.length; fi++) {
        var item = group.items[fi];
        if (matchesSearch(item.name) && matchesType(item.type)) {
          filtered.push(item);
        }
      }
      if (filtered.length === 0) continue;
      var isCollapsed = _collapsed[group.id] === true;
      listHtml += '<div class="var-group-header" data-group="' + group.id + '" style="padding:3px 10px;font-size:9px;color:' + group.color + ';font-weight:600;letter-spacing:.3px;cursor:pointer;user-select:none;display:flex;align-items:center;gap:4px;margin-top:4px">';
      listHtml += '<span style="font-size:8px;transition:transform .15s;' + (isCollapsed ? '' : 'transform:rotate(90deg)') + '">&#9654;</span>';
      listHtml += '<span>' + group.label + '</span>';
      listHtml += '<span style="color:var(--txt3,#94a3b8);font-weight:400">(' + filtered.length + ')</span>';
      listHtml += '</div>';
      if (!isCollapsed) {
        for (var vi = 0; vi < filtered.length; vi++) {
          var v = filtered[vi];
          var titleAttr = '点击复制 ' + v.ref.replace(/"/g, '&quot;');
          if (v.assignCount && v.assignCount > 1) {
            titleAttr = '⚠ 此变量被 ' + v.assignCount + ' 个节点赋值，最终值取决于执行顺序\n' + v.ref.replace(/"/g, '&quot;');
          }
          listHtml += '<div class="vi' + (v.assignCount && v.assignCount > 1 ? ' vi-multi' : '') + '" data-copy="' + v.ref.replace(/"/g, '&quot;') + '" title="' + titleAttr + '">' +
            '<span class="vn">' + v.name + (v.assignCount && v.assignCount > 1 ? ' <b style="color:#f59e0b;font-size:9px">×' + v.assignCount + '</b>' : '') + '</span>' +
            '<span class="vv">' + v.desc + '</span>' +
            '<span class="vt">' + (typeLabels[v.type] || v.type) + '</span></div>';
        }
      }
    }

    var anyMatch = false;
    for (var gi2 = 0; gi2 < groups.length; gi2++) {
      var g2 = groups[gi2];
      for (var fi2 = 0; fi2 < g2.items.length; fi2++) {
        if (matchesSearch(g2.items[fi2].name) && matchesType(g2.items[fi2].type)) {
          anyMatch = true;
          break;
        }
      }
      if (anyMatch) break;
    }
    if (!anyMatch) {
      listHtml = '<div style="padding:6px 10px;font-size:10px;color:var(--txt3,#94a3b8)">暂无匹配的变量</div>';
    }

    var fullHtml = barHtml + listHtml;

    if (vlEl) vlEl.innerHTML = fullHtml;
    if (vlFloat) vlFloat.innerHTML = fullHtml;

    bindVarPanelEvents();
  }

  function bindVarPanelEvents() {
    var containers = [vlEl, vlFloat];
    for (var ci = 0; ci < containers.length; ci++) {
      var container = containers[ci];
      if (!container) continue;

      container.querySelectorAll('.var-group-header').forEach(function(header) {
        header.addEventListener('click', function() {
          var groupId = this.dataset.group;
          _collapsed[groupId] = !_collapsed[groupId];
          try { localStorage.setItem('varPanel_collapsed', JSON.stringify(_collapsed)); } catch(e) {}
          renderVarPanel();
        });
      });

      container.querySelectorAll('.vi').forEach(function(viEl) {
        viEl.style.cursor = 'pointer';
        viEl.addEventListener('click', function() {
          var varRef = viEl.dataset.copy || viEl.title || '';
          if (navigator.clipboard) {
            navigator.clipboard.writeText(varRef).then(function() {
              showToast('已复制: ' + varRef, 'ok', 1500);
            });
          } else {
            showToast(varRef, 'inf', 2000);
          }
        });
        viEl.addEventListener('mouseenter', function() { this.style.background = 'var(--bg-hover)'; });
        viEl.addEventListener('mouseleave', function() { this.style.background = ''; });
      });

      var searchInput = container.querySelector('.var-search-in');
      if (searchInput) {
        searchInput.addEventListener('input', function() {
          _varSearchVal = this.value;
          _varFilterType = (container.querySelector('.var-type-filter') || {}).value || '';
          var savedSelStart = this.selectionStart;
          var savedSelEnd = this.selectionEnd;
          renderVarPanel();
          var targetContainer = container;
          setTimeout(function() {
            var newInput = targetContainer.querySelector('.var-search-in');
            if (newInput) {
              newInput.focus();
              newInput.selectionStart = savedSelStart;
              newInput.selectionEnd = savedSelEnd;
            }
          }, 0);
        });
      }
      var clearBtn = container.querySelector('.var-search-clear');
      if (clearBtn) {
        clearBtn.addEventListener('click', function() {
          _varSearchVal = '';
          renderVarPanel();
          var newInput = container.querySelector('.var-search-in');
          if (newInput) newInput.focus();
        });
      }
      var typeFilter = container.querySelector('.var-type-filter');
      if (typeFilter) {
        typeFilter.addEventListener('change', function() {
          _varSearchVal = (container.querySelector('.var-search-in') || {}).value || '';
          _varFilterType = this.value;
          renderVarPanel();
        });
      }
    }
  }

  renderVarPanel();
}

export var _varPanelFloating = false;

export function toggleVarPanel() {
  var varsP = document.getElementById('vars-p');
  var varFloat = document.getElementById('var-float');
  var chevron = document.getElementById('vp-chevron');

  if (_varPanelFloating) {
    varFloat.classList.toggle('visible');
  } else {
    var isCollapsed = varsP.classList.contains('collapsed');
    if (isCollapsed) {
      varsP.classList.remove('collapsed');
      if (chevron) chevron.style.transform = 'rotate(180deg)';
    } else {
      varsP.classList.add('collapsed');
      if (chevron) chevron.style.transform = '';
    }
  }
}

export function undockVarPanel() {
  var varsP = document.getElementById('vars-p');
  var varFloat = document.getElementById('var-float');
  varsP.classList.add('collapsed');
  varFloat.classList.add('visible');
  _varPanelFloating = true;
  var cvArea = document.getElementById('cv-area');
  if (cvArea) {
    var rect = cvArea.getBoundingClientRect();
    varFloat.style.right = '16px';
    varFloat.style.top = rect.top + 16 + 'px';
    varFloat.style.left = '';
  }
}

export function dockVarPanel() {
  var varsP = document.getElementById('vars-p');
  var varFloat = document.getElementById('var-float');
  varFloat.classList.remove('visible');
  varsP.classList.remove('collapsed');
  _varPanelFloating = false;
  var chevron = document.getElementById('vp-chevron');
  if (chevron) chevron.style.transform = 'rotate(180deg)';
}

export function _initVarFloatDrag() {
  var header = document.getElementById('vf-header');
  var panel = document.getElementById('var-float');
  if (!header || !panel) return;
  var dragging = false, startX, startY, startLeft, startTop;
  header.addEventListener('mousedown', function(e) {
    if (e.target.closest('button')) return;
    dragging = true;
    startX = e.clientX;
    startY = e.clientY;
    var rect = panel.getBoundingClientRect();
    startLeft = rect.left;
    startTop = rect.top;
    e.preventDefault();
  });
  document.addEventListener('mousemove', function(e) {
    if (!dragging) return;
    var dx = e.clientX - startX;
    var dy = e.clientY - startY;
    panel.style.left = (startLeft + dx) + 'px';
    panel.style.top = (startTop + dy) + 'px';
    panel.style.right = '';
  });
  document.addEventListener('mouseup', function() {
    dragging = false;
  });
}
