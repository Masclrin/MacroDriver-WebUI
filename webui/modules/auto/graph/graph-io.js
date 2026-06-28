import { showToast } from '../app/toast.js';

export function importInsert() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.choose_script_file) {
    window.pywebview.api.choose_script_file().then(function(res) {
      if (res && res.ok && !res.canceled && res.data && res.data.path) {
        var filePath = res.data.path;
        window.pywebview.api.load_auto_script(filePath).then(function(loadRes) {
          if (loadRes && loadRes.ok && loadRes.data) {
            _doInsertGraphData(loadRes.data);
          } else {
            showToast((loadRes && loadRes.error) || '加载脚本失败', 'err');
          }
        }).catch(function(err) { showToast('加载脚本失败: ' + (err.message || err), 'err'); });
      }
    }).catch(function(err) { showToast('选择文件失败: ' + (err.message || err), 'err'); });
  } else {
    var fileInput = document.getElementById('file-input-insert');
    if (fileInput) {
      fileInput.value = '';
      fileInput.click();
    }
  }
}

function _doInsertGraphData(data) {
  try {
    if (!data || !data.graph || !data.graph.nodes || data.graph.nodes.length === 0) {
      showToast('文件中没有节点，无法导入', 'err');
      return;
    }

    var graphNodes = data.graph.nodes;
    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (var i = 0; i < graphNodes.length; i++) {
      var nj = graphNodes[i];
      var nx = (nj.position && nj.position.x) || 0;
      var ny = (nj.position && nj.position.y) || 0;
      var def = window.AutomationNodes ? window.AutomationNodes.getNodeDef(nj.type) : null;
      var nw = (def && def.size) ? def.size[0] : 220;
      var nh = (def && def.size) ? def.size[1] : 100;
      minX = Math.min(minX, nx);
      minY = Math.min(minY, ny);
      maxX = Math.max(maxX, nx + nw);
      maxY = Math.max(maxY, ny + nh);
    }

    var annotations = data.graph.annotations || [];
    for (var ai = 0; ai < annotations.length; ai++) {
      var aj = annotations[ai];
      var ax = (aj.position && aj.position.x) || 0;
      var ay = (aj.position && aj.position.y) || 0;
      minX = Math.min(minX, ax);
      minY = Math.min(minY, ay);
    }

    var importCenterX = (minX + maxX) / 2;
    var importCenterY = (minY + maxY) / 2;

    var cvArea = document.getElementById('cv-area');
    var vpOffset = window.AutomationCore.getViewportOffset();
    var vpScale = window.AutomationCore.getViewportScale();
    var rect = cvArea.getBoundingClientRect();
    var viewportCenterX = (rect.width / 2 - vpOffset.x) / vpScale;
    var viewportCenterY = (rect.height / 2 - vpOffset.y) / vpScale;

    var offsetX = viewportCenterX - importCenterX;
    var offsetY = viewportCenterY - importCenterY;

    var idMap = {};
    var maxId = 0;

    for (var j = 0; j < graphNodes.length; j++) {
      var nj2 = graphNodes[j];
      var node = window.AutomationCore.lgGraphObj.createNode(nj2.type);
      if (!node) {
        showToast('无法创建节点类型: ' + nj2.type, 'err');
        continue;
      }
      node.pos[0] = ((nj2.position && nj2.position.x) || 0) + offsetX;
      node.pos[1] = ((nj2.position && nj2.position.y) || 0) + offsetY;
      if (nj2.params) {
        for (var k in nj2.params) {
          if (!nj2.params.hasOwnProperty(k)) continue;
          node.properties[k] = nj2.params[k];
        }
      }
      if (nj2.customName) {
        node._customName = nj2.customName;
      }
      if (node.id > maxId) maxId = node.id;
      idMap[String(nj2.id)] = node;
      window.AutomationCore.lgGraphObj.add(node);

      var nodeDef = window.AutomationNodes ? window.AutomationNodes.getNodeDef(nj2.type) : null;
      if (nodeDef && nodeDef.dynamic_branches && node.properties.branch_count && node.properties.branch_count !== 2) {
        window.AutomationCore.updateBranchPorts(node, node.properties.branch_count);
      }
    }

    if (maxId > 0) {
      window.AutomationCore.lgGraphObj.setNextNodeId(maxId + 1);
    }

    var connections = data.graph.connections || [];
    var connAdded = 0;
    for (var c = 0; c < connections.length; c++) {
      var conn = connections[c];
      var fromNode = idMap[String(conn.from.node)];
      var toNode = idMap[String(conn.to.node)];
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
      window.AutomationCore.lgGraphObj.connect(fromNode.id, fromSlot, toNode.id, toSlot);
      connAdded++;
    }

    for (var ai2 = 0; ai2 < annotations.length; ai2++) {
      var aj2 = annotations[ai2];
      var an = window.AutomationCore.addAnnotation(
        ((aj2.position && aj2.position.x) || 0) + offsetX,
        ((aj2.position && aj2.position.y) || 0) + offsetY,
        aj2.text || '',
        aj2.color || '#fbbf24'
      );
      if (aj2.bgColor) an.bgColor = aj2.bgColor;
      if (aj2.collapsed) an.collapsed = true;
    }

    var groups = data.graph.groups || [];
    for (var gi = 0; gi < groups.length; gi++) {
      var gj = groups[gi];
      var gp = window.AutomationCore.addGroup(
        ((gj.position && gj.position.x) || 0) + offsetX,
        ((gj.position && gj.position.y) || 0) + offsetY,
        (gj.size && gj.size.w) || 200,
        (gj.size && gj.size.h) || 150,
        gj.title || '',
        gj.color || '#3b82f6'
      );
      if (gj.bgColor) gp.bgColor = gj.bgColor;
    }

    _setGraphDirty(true);
    updateStatusBar();
    updateMinimap();
    undoManager.push();

    var importedName = (data.meta && data.meta.name) || '未命名脚本';
    showToast('已导入: ' + importedName + ' (' + graphNodes.length + ' 个节点, ' + connAdded + ' 条连线)', 'ok');
  } catch (err) {
    showToast('导入失败: ' + err.message, 'err');
  }
}

export function handleFileInsert(e) {
  var file = e.target.files[0];
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function(ev) {
    try {
      var data = JSON.parse(ev.target.result);
      _doInsertGraphData(data);
    } catch (err) {
      showToast('导入失败: ' + err.message, 'err');
    }
  };
  reader.readAsText(file);
  e.target.value = '';
}
import { serializeGraph, deserializeGraph } from './graph-serializer.js';
import { _graphDirty, _currentScriptName, _lastSavedGraph, _setGraphDirty, _setCurrentScriptName, _setLastSavedGraph } from '../app/editor-state.js';
import { setExecutionState, undoManager } from '../ui/ui-utils.js';
import { updateStatusBar } from '../ui/ui-utils.js';
import { updateMinimap } from '../ui/sidebar.js';

export { _graphDirty, _currentScriptName, _lastSavedGraph, _setGraphDirty, _setCurrentScriptName, _setLastSavedGraph };

function _ensureScriptNamed(cancelMsg) {
  if (_currentScriptName !== '未命名脚本') return true;
  var newName = prompt('脚本名称不能为默认名，请输入新的脚本名称：', '我的脚本');
  if (!newName || newName.trim() === '') {
    showToast(cancelMsg, 'inf');
    return false;
  }
  if (newName.trim() === '未命名脚本') {
    showToast('脚本名称不能为默认名，请修改后重试', 'warn');
    return false;
  }
  _setCurrentScriptName(newName.trim());
  updateScriptNameDisplay();
  return true;
}

export function updateScriptNameDisplay() {
  var el = document.getElementById('script-name-input');
  if (el) {
    el.value = _currentScriptName || '未命名脚本';
  }
}

export function renameScript() {
  var el = document.getElementById('script-name-input');
  if (!el) return;
  el.readOnly = false;
  el.style.borderColor = 'var(--acc)';
  el.style.background = 'var(--bg-hover)';
  el.focus();
  el.select();
}

export function finishRenameScript(el) {
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
  _setCurrentScriptName(newName);
  _setGraphDirty(true);
  showToast('已重命名为: ' + _currentScriptName, 'ok');
}

export function exportGraph() {
  if (!_ensureScriptNamed('已取消导出')) return;
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

export function importGraph() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.choose_script_file) {
    window.pywebview.api.choose_script_file().then(function(res) {
      if (res && res.ok && !res.canceled && res.data && res.data.path) {
        var filePath = res.data.path;
        window.pywebview.api.load_auto_script(filePath).then(function(loadRes) {
          if (loadRes && loadRes.ok && loadRes.data) {
            if (deserializeGraph(loadRes.data)) {
              var importedName = (loadRes.data.meta && loadRes.data.meta.name) || '未命名脚本';
              _setCurrentScriptName(importedName);
              _setGraphDirty(false);
              _setLastSavedGraph(JSON.stringify(loadRes.data));
              updateScriptNameDisplay();
              setExecutionState('idle');
              updateStatusBar();
              updateMinimap();
              showToast('已导入: ' + importedName, 'ok');
            } else {
              showToast('导入失败：格式无效', 'err');
            }
          } else {
            showToast((loadRes && loadRes.error) || '加载脚本失败', 'err');
          }
        }).catch(function(err) { showToast('加载脚本失败: ' + (err.message || err), 'err'); });
      }
    }).catch(function(err) { showToast('选择文件失败: ' + (err.message || err), 'err'); });
  } else {
    document.getElementById('file-input-import').click();
  }
}

export function handleFileImport(e) {
  var file = e.target.files[0];
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function(ev) {
    try {
      var data = JSON.parse(ev.target.result);
      if (deserializeGraph(data)) {
        var importedName = (data.meta && data.meta.name) || '未命名脚本';
        _setCurrentScriptName(importedName);
        _setGraphDirty(false);
        _setLastSavedGraph(JSON.stringify(data));
        updateScriptNameDisplay();
        setExecutionState('idle');
        updateStatusBar();
        updateMinimap();
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

export function saveGraph() {
  if (!_ensureScriptNamed('已取消保存')) return Promise.resolve(false);
  if (window.pywebview && window.pywebview.api && window.pywebview.api.save_auto_script) {
    var data = serializeGraph();
    _setLastSavedGraph(JSON.stringify(data));
    return window.pywebview.api.save_auto_script('自动化脚本/' + _currentScriptName + '.auto.json', JSON.stringify(data, null, 2))
      .then(function(res) {
        if (res && res.ok) {
          _setGraphDirty(false);
          showToast('保存成功', 'ok');
          return true;
        } else {
          showToast((res && res.error) || '保存失败', 'err');
          return false;
        }
      })
      .catch(function() { exportGraph(); return false; });
  } else {
    exportGraph();
    return Promise.resolve(true);
  }
}

function _showNewCanvasModal() {
  var existing = document.getElementById('modal-new-canvas');
  if (existing) existing.remove();

  var overlay = document.createElement('div');
  overlay.id = 'modal-new-canvas';
  overlay.className = 'modal-overlay';
  overlay.innerHTML = [
    '<div class="modal-content" style="width:420px">',
      '<div class="modal-header">',
        '<span>新建画布</span>',
        '<div class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()"><i class="fa-solid fa-xmark"></i></div>',
      '</div>',
      '<div class="modal-body" style="font-size:12px;line-height:1.7;color:var(--txt2)">',
        '<p style="margin-bottom:8px">当前画布有未保存的更改，请选择操作：</p>',
        '<p style="font-size:11px;color:var(--txt3)"><i class="fa-solid fa-circle-info"></i> 脚本名：<b style="color:var(--txt)">' + (_currentScriptName || '未命名脚本').replace(/</g, '&lt;') + '</b></p>',
      '</div>',
      '<div class="modal-footer" style="justify-content:space-between">',
        '<button class="t-btn err" id="btn-new-discard" style="padding:8px 18px;font-size:12px"><i class="fa-solid fa-trash"></i> 不保存</button>',
        '<div style="display:flex;gap:8px">',
          '<button class="t-btn" id="btn-new-cancel" style="padding:8px 18px;font-size:12px"><i class="fa-solid fa-xmark"></i> 取消</button>',
          '<button class="t-btn pri" id="btn-new-save" style="padding:8px 18px;font-size:12px"><i class="fa-solid fa-floppy-disk"></i> 保存</button>',
        '</div>',
      '</div>',
    '</div>',
  ].join('');
  document.body.appendChild(overlay);

  document.getElementById('btn-new-cancel').addEventListener('click', function() {
    overlay.remove();
    showToast('已取消新建', 'inf');
  });

  document.getElementById('btn-new-save').addEventListener('click', function() {
    overlay.remove();
    if (_currentScriptName === '未命名脚本') {
      var newName = prompt('请输入脚本名称：', '我的脚本');
      if (!newName || newName.trim() === '' || newName.trim() === '未命名脚本') {
        showToast('名称无效，已取消新建', 'inf');
        return;
      }
      _setCurrentScriptName(newName.trim());
      updateScriptNameDisplay();
    }
    saveGraph().then(function(success) {
      if (success) {
        _doClearAndNew();
      } else {
        showToast('保存失败，未新建画布。请手动导出后再试', 'err', 5000);
      }
    });
  });

  document.getElementById('btn-new-discard').addEventListener('click', function() {
    overlay.remove();
    _doClearAndNew();
  });

  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) overlay.remove();
  });
}

export function newCanvas() {
  var nodes = window.AutomationCore.getNodes();
  if (nodes.length > 0 && _graphDirty) {
    _showNewCanvasModal();
    return;
  }
  _doClearAndNew();
}

function _doClearAndNew() {
  window.AutomationCore.clearAll();
  window.AutomationCore.zoomReset();
  window.AutomationProperty.render(null);
  _setCurrentScriptName('未命名脚本');
  _setLastSavedGraph(null);
  _setGraphDirty(false);
  updateScriptNameDisplay();
  window.addNodeToCenter('flow/start');
  setExecutionState('idle');
  updateStatusBar();
  updateMinimap();
  undoManager.reset();
  showToast('已创建新画布', 'inf');
}
