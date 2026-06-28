import { showToast } from '../app/toast.js';
import { updateStatusBar, undoManager } from './ui-utils.js';
import { updateMinimap, fitView } from './sidebar.js';

var contextTarget = null;
var contextPos = null;
var _clipboard = null;
var _pasteCount = 0;
var _contextAnnotation = null;
var _contextGroup = null;

export { contextTarget, contextPos, _clipboard, _pasteCount, _contextAnnotation, _contextGroup };
export function _setContextTarget(v) { contextTarget = v; }
export function _setContextPos(v) { contextPos = v; }
export function _setClipboard(v) { _clipboard = v; }
export function _setPasteCount(v) { _pasteCount = v; }
export function _setAnnotationContext(an) { _contextAnnotation = an; _contextGroup = null; }
export function _setGroupContext(gp) { _contextGroup = gp; _contextAnnotation = null; }

export function updateToolboxButtonState(buttonId, isActive) {
  var btn = document.getElementById('btn-' + buttonId);
  if (btn) {
    btn.classList.toggle('active', isActive);
  }
}

export function hideContextMenu() {
  var menu = document.getElementById('ctx');
  if (menu) menu.classList.remove('show');
  _contextAnnotation = null;
  _contextGroup = null;
}

export function showContextMenu(x, y, items) {
  var menu = document.getElementById('ctx');
  var html = '';
  var fnActions = [];
  for (var i = 0; i < items.length; i++) {
    var item = items[i];
    if (item === '---' || item.divider) {
      html += '<div class="cx-s"></div>';
      continue;
    }
    var subHtml = '';
    if (item.submenu) {
      if (typeof item.submenu === 'object' && item.submenu.items) {
        subHtml = '<div class="cx-sub">';
        for (var si = 0; si < item.submenu.items.length; si++) {
          var sm = item.submenu.items[si];
          if (sm.divider) {
            subHtml += '<div class="cx-s"></div>';
            continue;
          }
          var smFnIdx = fnActions.length;
          fnActions.push(sm.action);
          subHtml += '<div class="cx-sn" data-fn-idx="' + smFnIdx + '">' +
            '<i class="' + (sm.icon || 'fa-solid fa-circle') + '" style="color:' + (sm.iconColor || '') + '"></i>' +
            '<span>' + sm.label + '</span></div>';
        }
        subHtml += '</div>';
      } else {
        subHtml = buildAddNodeSubmenu();
      }
    }
    var iconStyle = item.iconStyle ? ' style="' + item.iconStyle + '"' : '';
    var checkedHtml = item.checked ? '<i class="fa-solid fa-check" style="margin-left:auto;font-size:10px;color:var(--primary)"></i>' : '';
    var actionAttr = '';
    var disabledClass = item.disabled ? ' cx-d' : '';
    if (item.disabled) {
      actionAttr = '';
    } else if (typeof item.action === 'function') {
      var fnIdx = fnActions.length;
      fnActions.push(item.action);
      actionAttr = ' data-fn-idx="' + fnIdx + '"';
    } else {
      actionAttr = ' data-action="' + item.action + '"';
    }
    html += '<div class="cx-i' + disabledClass + '"' + actionAttr + '>' +
      '<i class="' + (item.icon || 'fa-solid fa-circle') + '"' + iconStyle + '></i>' +
      '<span>' + item.label + '</span>' +
      (item.submenu ? '<i class="fa-solid fa-chevron-right" style="margin-left:auto;font-size:8px"></i>' : '') +
      (item.shortcut ? '<span style="margin-left:auto;font-size:9px;color:var(--txt3)">' + item.shortcut + '</span>' : '') +
      checkedHtml +
      subHtml +
      '</div>';
  }
  menu.innerHTML = html;
  menu.style.left = Math.min(x, window.innerWidth - 180) + 'px';
  menu.style.visibility = 'hidden';
  menu.classList.add('show');
  menu.style.top = Math.min(y, window.innerHeight - menu.offsetHeight - 10) + 'px';
  menu.style.visibility = '';

  var ctxItems = menu.querySelectorAll('.cx-i');
  for (var j = 0; j < ctxItems.length; j++) {
    (function(el, fns) {
      el.addEventListener('click', function(e) {
        if (this.querySelector('.cx-sub') && this.querySelector('.cx-sub').contains(e.target)) return;
        if (this.querySelector('.cx-sub')) return;
        var fnIdx = this.dataset.fnIdx;
        if (fnIdx !== undefined && fns[parseInt(fnIdx)]) {
          fns[parseInt(fnIdx)]();
        } else if (this.dataset.action) {
          handleContextAction(this.dataset.action);
        }
        menu.classList.remove('show');
      });
    })(ctxItems[j], fnActions);
  }

  var subItems = menu.querySelectorAll('.cx-sn');
  for (var k = 0; k < subItems.length; k++) {
    (function(el, fns) {
      el.addEventListener('click', function(e) {
        e.stopPropagation();
        var fnIdx = this.dataset.fnIdx;
        if (fnIdx !== undefined && fns[parseInt(fnIdx)]) {
          fns[parseInt(fnIdx)]();
          menu.classList.remove('show');
          return;
        }
        var nodeType = this.dataset.nodeType;
        if (nodeType) {
          addNodeAtPosition(nodeType, contextPos);
          menu.classList.remove('show');
        }
      });
    })(subItems[k], fnActions);
  }
}

export function buildAddNodeSubmenu() {
  var cats = window.AutomationNodes.getCategories();
  var html = '<div class="cx-sub">';
  var catOrder = ['flow', 'action', 'detection', 'control', 'script_block', 'monitor', 'variable', 'preset', 'utility'];
  for (var ci = 0; ci < catOrder.length; ci++) {
    var catKey = catOrder[ci];
    var cat = cats[catKey];
    if (!cat) continue;
    html += '<div class="cx-sc">' + cat.name + '</div>';
    for (var ni = 0; ni < cat.nodes.length; ni++) {
      var nd = cat.nodes[ni];
      var def = window.AutomationNodes.getNodeDef(nd.type);
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

export function addNodeAtPosition(nodeType, pos) {
  if (!pos) { window.addNodeToCenter(nodeType); return; }
  var local = window.AutomationCore.screenToLocal(pos.x, pos.y);
  var node = window.AutomationCore.addNodeAtPosition(nodeType, local.x, local.y);
  if (!node) { showToast('未知节点类型: ' + nodeType, 'err'); return; }
  window.AutomationCore.selectNode(node);
  updateStatusBar();
  updateMinimap();
  undoManager.push();
}

export function handleContextAction(action) {
  if (!contextTarget && !_contextAnnotation && !_contextGroup && action !== 'paste' && action !== 'select_all' && action !== 'fit_view' && action !== 'clear_all' && action !== 'add_comment' && action !== 'add_group' && action !== 'toggle_line_delete' && action !== 'toggle_breakpoint') return;
  switch (action) {
    case 'toggle_breakpoint': {
      var node = contextTarget;
      if (!node) break;
      node.properties._breakpoint = !node.properties._breakpoint;
      var el = document.getElementById('nd-' + node.id);
      if (el) {
        if (node.properties._breakpoint) {
          el.classList.add('has-breakpoint');
        } else {
          el.classList.remove('has-breakpoint');
        }
      }
      showToast(node.properties._breakpoint ? '已设置断点' : '已取消断点', 'inf');
      break;
    }
    case 'toggle_line_delete':
      var currentMode = window.AutomationCore.isLineDeleteMode();
      window.AutomationCore.setLineDeleteMode(!currentMode);
      updateToolboxButtonState('line_delete', !currentMode);
      showToast(!currentMode ? '已启用删除连线模式（点击连线即可删除）' : '已关闭删除连线模式', 'inf');
      break;
    case 'delete':
      if (contextTarget) {
        window.AutomationCore.lgGraphObj.remove(contextTarget);
        window.AutomationCore.selectedNode = null;
        window.AutomationProperty.render(null);
        updateStatusBar();
        updateMinimap();
        undoManager.push();
      }
      break;
    case 'duplicate':
      if (contextTarget) {
        var cloned = contextTarget.clone();
        if (cloned) {
          window.AutomationCore.lgGraphObj.add(cloned);
          window.AutomationCore.selectNode(cloned);
          updateStatusBar();
          updateMinimap();
          undoManager.push();
          showToast('已复制节点', 'ok');
        } else {
          showToast('复制节点失败', 'err');
        }
      }
      break;
    case 'disconnect':
      if (contextTarget) {
        window.AutomationCore.disconnectNode(contextTarget.id);
        updateStatusBar();
        updateMinimap();
        undoManager.push();
        showToast('已断开所有连线', 'inf');
      }
      break;
    case 'copy':
      var graphObj = window.AutomationCore.lgGraphObj;
      var selectedNodes = window.AutomationCore.getSelectedNodes();
      if (selectedNodes.length > 1) {
        _pasteCount = 0;
        var nodeSet = {};
        var copiedNodes = [];
        for (var si = 0; si < selectedNodes.length; si++) {
          var sn = selectedNodes[si];
          nodeSet[sn.id] = true;
          copiedNodes.push({
            id: sn.id,
            nodeType: sn._defKey,
            params: JSON.parse(JSON.stringify(sn.properties || {})),
            pos: { x: sn.pos[0], y: sn.pos[1] },
            customName: sn._customName || null
          });
        }
        var connections = [];
        var allConns = window.AutomationCore.getConnections();
        for (var ci = 0; ci < allConns.length; ci++) {
          var c = allConns[ci];
          if (nodeSet[c.origin_id] && nodeSet[c.target_id]) {
            connections.push({
              origin_id: c.origin_id,
              origin_slot: c.origin_slot,
              target_id: c.target_id,
              target_slot: c.target_slot,
              type: c.type
            });
          }
        }
        _clipboard = [{ nodes: copiedNodes, connections: connections }];
        showToast('已复制 ' + copiedNodes.length + ' 个节点及连线', 'inf');
      } else if (contextTarget) {
        _pasteCount = 0;
        _clipboard = [{
          nodeType: contextTarget._defKey,
          params: JSON.parse(JSON.stringify(contextTarget.properties || {})),
          pos: { x: contextTarget.pos[0], y: contextTarget.pos[1] },
          customName: contextTarget._customName || null
        }];
        showToast('已复制节点: ' + (contextTarget.title || contextTarget._defKey), 'inf');
      }
      break;
    case 'paste':
      if (_clipboard) {
        var pastedNodes = [];
        var pastedAnnotations = 0;
        var pastedGroups = 0;
        var idMap = {};
        var pasteCenterX = 0;
        var pasteCenterY = 0;
        if (contextPos) {
          var local = window.AutomationCore.screenToLocal(contextPos.x, contextPos.y);
          pasteCenterX = local.x;
          pasteCenterY = local.y;
        }
        for (var j = 0; j < _clipboard.length; j++) {
          var item = _clipboard[j];
          if (item.type === 'annotation') {
            var anOffX = 40 * (_pasteCount + 1);
            var anOffY = 40 * (_pasteCount + 1);
            if (contextPos) { anOffX = pasteCenterX - item.pos.x; anOffY = pasteCenterY - item.pos.y; }
            var newAn = window.AutomationCore.addAnnotation(
              item.pos.x + anOffX,
              item.pos.y + anOffY,
              item.text,
              item.color
            );
            if (item.bgColor) { newAn.bgColor = item.bgColor; if (newAn._domEl) newAn._domEl.style.background = item.bgColor; }
            if (item.collapsed) { newAn.collapsed = true; if (newAn._domEl) newAn._domEl.classList.add('collapsed'); }
            pastedAnnotations++;
          } else if (item.type === 'group') {
            var gpOffX = 40 * (_pasteCount + 1);
            var gpOffY = 40 * (_pasteCount + 1);
            if (contextPos) { gpOffX = pasteCenterX - item.pos.x; gpOffY = pasteCenterY - item.pos.y; }
            var newGp = window.AutomationCore.addGroup(
              item.pos.x + gpOffX,
              item.pos.y + gpOffY,
              item.size.w,
              item.size.h,
              item.title,
              item.color
            );
            if (item.bgColor) { newGp.bgColor = item.bgColor; if (newGp._domEl) { newGp._domEl.style.setProperty('--gp-bg', item.bgColor); newGp._domEl.style.background = item.bgColor; } }
            pastedGroups++;
          } else if (item.nodes) {
            var nodeList = item.nodes;
            var origCX = 0, origCY = 0;
            for (var oi = 0; oi < nodeList.length; oi++) {
              origCX += nodeList[oi].pos.x;
              origCY += nodeList[oi].pos.y;
            }
            origCX /= nodeList.length;
            origCY /= nodeList.length;
            var offsetX = pasteCenterX - origCX;
            var offsetY = pasteCenterY - origCY;
            if (!contextPos) { offsetX = 40 * (_pasteCount + 1); offsetY = 40 * (_pasteCount + 1); }
            for (var k = 0; k < nodeList.length; k++) {
              var nodeItem = nodeList[k];
              var newNode = window.AutomationCore.addNodeAtPosition(nodeItem.nodeType, nodeItem.pos.x + offsetX, nodeItem.pos.y + offsetY);
              if (newNode) {
                for (var pk in nodeItem.params) {
                  if (nodeItem.params.hasOwnProperty(pk)) {
                    newNode.properties[pk] = JSON.parse(JSON.stringify(nodeItem.params[pk]));
                  }
                }
                if (nodeItem.customName) {
                  newNode._customName = nodeItem.customName;
                  newNode.title = nodeItem.customName;
                }
                window.AutomationCore.refreshNode(newNode);
                pastedNodes.push(newNode);
                idMap[nodeItem.id] = newNode.id;
              }
            }
            if (item.connections) {
              var conns = item.connections;
              for (var ci = 0; ci < conns.length; ci++) {
                var conn = conns[ci];
                var newFromId = idMap[conn.origin_id];
                var newToId = idMap[conn.target_id];
                if (newFromId && newToId) {
                  window.AutomationCore.lgGraphObj.connect(newFromId, conn.origin_slot, newToId, conn.target_slot);
                }
              }
            }
          } else {
            var posX = item.pos.x + 40 * (_pasteCount + 1);
            var posY = item.pos.y + 40 * (_pasteCount + 1);
            if (contextPos) { posX = pasteCenterX; posY = pasteCenterY; }
            var newNode = window.AutomationCore.addNodeAtPosition(item.nodeType, posX, posY);
            if (newNode) {
              for (var pk in item.params) {
                if (item.params.hasOwnProperty(pk)) {
                  newNode.properties[pk] = JSON.parse(JSON.stringify(item.params[pk]));
                }
              }
              if (item.customName) {
                newNode._customName = item.customName;
                newNode.title = item.customName;
              }
              window.AutomationCore.refreshNode(newNode);
              pastedNodes.push(newNode);
            }
          }
        }
        if (pastedNodes.length > 0 || pastedAnnotations > 0 || pastedGroups > 0) {
          if (pastedNodes.length === 1 && pastedAnnotations === 0 && pastedGroups === 0) {
            window.AutomationCore.selectNode(pastedNodes[0]);
            window.AutomationProperty.render(pastedNodes[0]);
          }
          updateStatusBar();
          updateMinimap();
          undoManager.push();
          var pasteMsg = [];
          if (pastedNodes.length > 0) pasteMsg.push(pastedNodes.length + ' 个节点');
          if (pastedAnnotations > 0) pasteMsg.push(pastedAnnotations + ' 个注释');
          if (pastedGroups > 0) pasteMsg.push(pastedGroups + ' 个分组');
          showToast('已粘贴 ' + pasteMsg.join('、'), 'ok');
        }
      } else {
        showToast('剪贴板为空，请先复制节点', 'warn');
      }
      break;
    case 'select_all':
      window.AutomationCore.selectAll();
      var totalSel = window.AutomationCore.getSelectedNodes().length + window.AutomationCore.getSelectedAnnotations().length + window.AutomationCore.getSelectedGroups().length;
      showToast('已全选 ' + totalSel + ' 个元素', 'inf');
      break;
    case 'fit_view':
      fitView();
      break;
    case 'clear_all':
      if (window.AutomationCore.getNodes().length > 0 || window.AutomationCore.getAnnotations().length > 0 || window.AutomationCore.getGroups().length > 0) {
        window.AutomationCore.clearAll();
        window.AutomationProperty.render(null);
        updateStatusBar();
        updateMinimap();
        undoManager.push();
        showToast('画布已清空', 'inf');
      }
      break;
    case 'add_comment':
      if (contextPos) {
        var local = window.AutomationCore.screenToLocal(contextPos.x, contextPos.y);
        window.AutomationCore.addAnnotation(local.x, local.y, '双击编辑注释');
        undoManager.push();
      }
      break;
    case 'add_group':
      if (contextPos) {
        var local2 = window.AutomationCore.screenToLocal(contextPos.x, contextPos.y);
        window.AutomationCore.addGroup(local2.x - 150, local2.y - 100, 300, 200, '分组');
        undoManager.push();
      }
      break;
    case 'delete_annotation':
      if (_contextAnnotation) {
        window.AutomationCore.removeAnnotation(_contextAnnotation.id);
        _contextAnnotation = null;
        if (window.AutomationProperty) window.AutomationProperty.render(null);
        updateStatusBar();
        updateMinimap();
        undoManager.push();
        showToast('已删除注释', 'inf');
      } else {
        var selAns = window.AutomationCore.getSelectedAnnotations();
        if (selAns.length > 0) {
          for (var dai = 0; dai < selAns.length; dai++) {
            window.AutomationCore.removeAnnotation(selAns[dai].id);
          }
          if (window.AutomationProperty) window.AutomationProperty.render(null);
          updateStatusBar();
          updateMinimap();
          undoManager.push();
          showToast('已删除 ' + selAns.length + ' 个注释', 'inf');
        }
      }
      break;
    case 'duplicate_annotation':
      if (_contextAnnotation) {
        var newAn = window.AutomationCore.addAnnotation(
          _contextAnnotation.pos[0] + 20,
          _contextAnnotation.pos[1] + 20,
          _contextAnnotation.text,
          _contextAnnotation.color
        );
        if (_contextAnnotation.bgColor) { newAn.bgColor = _contextAnnotation.bgColor; if (newAn._domEl) newAn._domEl.style.background = _contextAnnotation.bgColor; }
        if (_contextAnnotation.collapsed) { newAn.collapsed = true; if (newAn._domEl) newAn._domEl.classList.add('collapsed'); }
        _contextAnnotation = null;
        updateMinimap();
        undoManager.push();
        showToast('已重复注释', 'inf');
      }
      break;
    case 'copy_annotation':
      if (_contextAnnotation) {
        _clipboard = [{
          type: 'annotation',
          text: _contextAnnotation.text,
          color: _contextAnnotation.color,
          bgColor: _contextAnnotation.bgColor,
          collapsed: _contextAnnotation.collapsed,
          pos: { x: _contextAnnotation.pos[0], y: _contextAnnotation.pos[1] }
        }];
        _pasteCount = 0;
        _contextAnnotation = null;
        showToast('已复制注释', 'inf');
      }
      break;
    case 'delete_group':
      if (_contextGroup) {
        window.AutomationCore.removeGroupKeepContents(_contextGroup.id);
        _contextGroup = null;
        if (window.AutomationProperty) window.AutomationProperty.render(null);
        updateStatusBar();
        updateMinimap();
        undoManager.push();
        showToast('已删除分组(内容已保留)', 'inf');
      } else {
        var selGps = window.AutomationCore.getSelectedGroups();
        if (selGps.length > 0) {
          for (var dgi = 0; dgi < selGps.length; dgi++) {
            window.AutomationCore.removeGroupKeepContents(selGps[dgi].id);
          }
          if (window.AutomationProperty) window.AutomationProperty.render(null);
          updateStatusBar();
          updateMinimap();
          undoManager.push();
          showToast('已删除 ' + selGps.length + ' 个分组(内容已保留)', 'inf');
        }
      }
      break;
    case 'duplicate_group':
      if (_contextGroup) {
        var newGp = window.AutomationCore.addGroup(
          _contextGroup.pos[0] + 30,
          _contextGroup.pos[1] + 30,
          _contextGroup.size[0],
          _contextGroup.size[1],
          _contextGroup.title,
          _contextGroup.color
        );
        if (_contextGroup.bgColor) { newGp.bgColor = _contextGroup.bgColor; if (newGp._domEl) { newGp._domEl.style.setProperty('--gp-bg', _contextGroup.bgColor); newGp._domEl.style.background = _contextGroup.bgColor; } }
        _contextGroup = null;
        updateMinimap();
        undoManager.push();
        showToast('已重复分组', 'inf');
      }
      break;
    case 'copy_group':
      if (_contextGroup) {
        _clipboard = [{
          type: 'group',
          title: _contextGroup.title,
          color: _contextGroup.color,
          bgColor: _contextGroup.bgColor,
          size: { w: _contextGroup.size[0], h: _contextGroup.size[1] },
          pos: { x: _contextGroup.pos[0], y: _contextGroup.pos[1] }
        }];
        _pasteCount = 0;
        _contextGroup = null;
        showToast('已复制分组', 'inf');
      }
      break;
  }
}
