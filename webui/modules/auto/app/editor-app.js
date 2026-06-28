import { AutomationCore } from '../core/core.js';
import { AutomationNodes } from '../core/nodes.js';
import { AutomationEvents } from '../logic/events-handlers.js';
import { AutomationProperty } from '../property/index.js';
import { AutomationTools } from '../pickers/tools.js';
import { AutomationBlockEditor } from '../editor/block-editor.js';
import { MacroUtils } from '../core/macro-utils.js';
import { renderMacroTreeList } from '../../macro-tree.js';

window.AutomationCore = AutomationCore;
window.AutomationNodes = AutomationNodes;
window.AutomationEvents = AutomationEvents;
window.AutomationProperty = AutomationProperty;
window.AutomationTools = AutomationTools;
window.AutomationBlockEditor = AutomationBlockEditor;
window.MacroUtils = MacroUtils;
window.renderMacroTreeList = renderMacroTreeList;

import { showToast } from './toast.js';
import { _hotkeyEnabled, _hotkeyRun, _hotkeyPause, _hotkeyStop, _hotkeyFullscreen, _loadEditorHotkeys } from './config.js';
import { initSidebarResize, initSidebarToggle, _repositionMinimap, updateMinimap, _isFullscreen, toggleFullscreen, fitView } from '../ui/sidebar.js';
import { undoManager, setExecutionState, updateStatusBar } from '../ui/ui-utils.js';
import { refreshVarPanel, toggleVarPanel, undockVarPanel, dockVarPanel, _initVarFloatDrag } from '../ui/var-panel.js';
import { initLogPanel, toggleLogPanel, undockLogPanel, dockLogPanel, refreshLogPanel, isLogEnabled } from '../ui/log-panel.js';
import { initNodeSearch } from '../ui/node-search.js';
import { initCoordOverlay, openPanel as openCoordOverlay, closePanel as closeCoordOverlay } from '../ui/coord-overlay-panel.js';
import { serializeGraph, deserializeGraph } from '../graph/graph-serializer.js';
import { _graphDirty, _currentScriptName, _setGraphDirty, _setCurrentScriptName, exportGraph, importGraph, handleFileImport, importInsert, handleFileInsert, saveGraph, newCanvas, updateScriptNameDisplay, renameScript, finishRenameScript } from '../graph/graph-io.js';
import { runGraph, stopGraph, pauseGraph, simulateExecution } from '../graph/graph-executor.js';
import { renderToolbox, addNodeToCenter } from '../ui/toolbox-renderer.js';
import { showContextMenu, hideContextMenu, handleContextAction, contextTarget, contextPos, _clipboard, _pasteCount, _setContextTarget, _setContextPos, _setClipboard, _setPasteCount, _setAnnotationContext, _setGroupContext, addNodeAtPosition } from '../ui/context-menu.js';
import { browseMacroPath, browseTemplatePath, browseWindowList, browseProgramFile, browseWindowTitle, browseProcessList, runPreview, browseScriptPath, browseFolderPath } from '../pickers/file-pickers.js';
import { loadPlugins } from '../plugins/plugin-loader.js';

window.toggleVarPanel = toggleVarPanel;
window.undockVarPanel = undockVarPanel;
window.dockVarPanel = dockVarPanel;
window.toggleLogPanel = toggleLogPanel;
window.undockLogPanel = undockLogPanel;
window.dockLogPanel = dockLogPanel;
window.isLogEnabled = isLogEnabled;
window.addNodeToCenter = addNodeToCenter;

function initEditor() {
  var cvArea = document.getElementById('cv-area');

  AutomationCore.init(cvArea);

  AutomationCore.onGraphChange(function() {
    _setGraphDirty(true);
    try {
      var api = window.pywebview && window.pywebview.api;
      if (api && api.cache_overlay_graph_json) {
        var data = window.AutomationApp && window.AutomationApp.serializeGraph
          ? window.AutomationApp.serializeGraph() : null;
        if (data) {
          var jsonStr = typeof data === 'string' ? data : JSON.stringify(data);
          api.cache_overlay_graph_json(jsonStr).catch(function(){});
        }
      }
    } catch(e) {}
  });

  AutomationEvents.init();

  _initVarFloatDrag();

  AutomationNodes.init(function() {
    renderToolbox();
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
      AutomationCore.addAnnotation(local.x - 50, local.y - 15, '双击编辑注释');
      updateStatusBar();
      updateMinimap();
      undoManager.push();
      return;
    }
    if (toolType === 'group') {
      var gLocal = AutomationCore.screenToLocal(e.clientX, e.clientY);
      AutomationCore.addGroup(gLocal.x - 150, gLocal.y - 100, 300, 200, '分组');
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
      _setContextTarget(AutomationCore.lgGraphObj.getNodeById(nid));
      showContextMenu(e.clientX, e.clientY, [
        { label: '复制', icon: 'fa-regular fa-copy', action: 'copy', shortcut: 'Ctrl+C' },
        { label: '重复', icon: 'fa-regular fa-clone', action: 'duplicate', shortcut: 'Ctrl+D' },
        '---',
        { label: '切换断点', icon: 'fa-solid fa-circle', iconStyle: 'color:#ef4444', action: 'toggle_breakpoint' },
        '---',
        { label: '断开所有连线', icon: 'fa-solid fa-link-slash', action: 'disconnect' },
        { label: '删除节点', icon: 'fa-solid fa-trash-can', action: 'delete', shortcut: 'Del' },
      ]);
    } else {
      _setContextTarget(null);
      _setContextPos({ x: e.clientX, y: e.clientY });
      var isLineDeleteMode = AutomationCore.isLineDeleteMode();
      showContextMenu(e.clientX, e.clientY, [
        { label: '删除连线', icon: 'fa-solid fa-eraser', action: 'toggle_line_delete', checked: isLineDeleteMode },
        '---',
        { label: '添加节点', icon: 'fa-solid fa-plus', action: 'add_node', submenu: true },
        '---',
        { label: '添加注释', icon: 'fa-solid fa-note-sticky', action: 'add_comment' },
        { label: '添加分组', icon: 'fa-solid fa-object-group', action: 'add_group' },
        '---',
        { label: '粘贴', icon: 'fa-regular fa-paste', action: 'paste', shortcut: 'Ctrl+V', disabled: !_clipboard },
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
  document.getElementById('btn-simulate').addEventListener('click', function() {
    if (AutomationCore.executionState === 'IDLE') {
      setExecutionState('running');
      simulateExecution();
    }
  });
  document.getElementById('btn-export').addEventListener('click', exportGraph);
  document.getElementById('btn-open').addEventListener('click', importGraph);
  document.getElementById('btn-import-insert').addEventListener('click', importInsert);
  document.getElementById('btn-save').addEventListener('click', saveGraph);
  document.getElementById('btn-new').addEventListener('click', newCanvas);
  document.getElementById('btn-zoom-in').addEventListener('click', function() { AutomationCore.zoomIn(); updateStatusBar(); });
  document.getElementById('btn-zoom-out').addEventListener('click', function() { AutomationCore.zoomOut(); updateStatusBar(); });
  document.getElementById('btn-zoom-reset').addEventListener('click', function() { AutomationCore.zoomReset(); updateStatusBar(); });
  document.getElementById('btn-fit-view').addEventListener('click', fitView);
  document.getElementById('btn-fullscreen').addEventListener('click', toggleFullscreen);
  document.getElementById('file-input-import').addEventListener('change', handleFileImport);
  document.getElementById('file-input-insert').addEventListener('change', handleFileInsert);

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

  var btnReloadPlugins = document.getElementById('btn-reload-plugins');
  if (btnReloadPlugins) {
    btnReloadPlugins.addEventListener('click', function() {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.list_plugins) {
        window.pywebview.api.list_plugins().then(function(res) {
          var plugins = [];
          if (res && res.ok && res.data) plugins = res.data;
          else if (res && Array.isArray(res)) plugins = res;
          if (!plugins || !plugins.length) { loadPlugins(); return; }
          var reloadChain = Promise.resolve();
          for (var i = 0; i < plugins.length; i++) {
            (function(pid) {
              reloadChain = reloadChain.then(function() {
                if (window.pywebview.api.reload_plugin) {
                  return window.pywebview.api.reload_plugin(pid).catch(function() {});
                }
                return Promise.resolve();
              });
            })(plugins[i].id);
          }
          reloadChain.then(function() { loadPlugins(); });
        }).catch(function() { loadPlugins(); });
      } else {
        loadPlugins();
      }
    });
  }

  loadPlugins();

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
    document.getElementById('ns-clear').style.display = e.target.value ? 'block' : 'none';
  });

  document.getElementById('ns-clear').addEventListener('click', function() {
    var inp = document.getElementById('ns-in');
    inp.value = '';
    this.style.display = 'none';
    renderToolbox('');
    inp.focus();
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
      var selAns = AutomationCore.getSelectedAnnotations();
      var selGps = AutomationCore.getSelectedGroups();
      var deleted = false;
      if (selNodes.length > 0) {
        AutomationCore.deleteSelectedNodes();
        AutomationCore.selectedNode = null;
        deleted = true;
      } else if (AutomationCore.selectedNode) {
        AutomationCore.lgGraphObj.remove(AutomationCore.selectedNode);
        AutomationCore.selectedNode = null;
        deleted = true;
      }
      if (selAns.length > 0) {
        for (var dai = 0; dai < selAns.length; dai++) {
          AutomationCore.removeAnnotation(selAns[dai].id);
        }
        deleted = true;
      }
      if (selGps.length > 0) {
        for (var dgi = 0; dgi < selGps.length; dgi++) {
          AutomationCore.removeGroupKeepContents(selGps[dgi].id);
        }
        deleted = true;
      }
      if (deleted) {
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
      var target = e.target || e.srcElement;
      if (target && (target.tagName === 'TEXTAREA' || target.tagName === 'INPUT' || target.contentEditable === 'true')) {
        return;
      }
      e.preventDefault();
      AutomationCore.selectAll();
      var totalSel = AutomationCore.getSelectedNodes().length + AutomationCore.getSelectedAnnotations().length + AutomationCore.getSelectedGroups().length;
      showToast('已全选 ' + totalSel + ' 个元素', 'inf');
    }
    if (e.ctrlKey && e.key === 'c') {
      var target = e.target || e.srcElement;
      if (target && (target.tagName === 'TEXTAREA' || target.tagName === 'INPUT' || target.contentEditable === 'true')) {
        return;
      }
      var selNodes = AutomationCore.getSelectedNodes();
      var selAns = AutomationCore.getSelectedAnnotations();
      var selGps = AutomationCore.getSelectedGroups();
      var hasNodes = selNodes.length > 0 || AutomationCore.selectedNode;
      var hasAnnotations = selAns.length > 0;
      var hasGroups = selGps.length > 0;
      if (hasNodes || hasAnnotations || hasGroups) {
        e.preventDefault();
        _setPasteCount(0);
        var clipboardItems = [];
        if (selNodes.length > 0) {
          var nodeSet = {};
          var copiedNodes = [];
          for (var i = 0; i < selNodes.length; i++) {
            var sn = selNodes[i];
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
          var allConns = AutomationCore.getConnections();
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
          clipboardItems.push({ nodes: copiedNodes, connections: connections });
        } else if (AutomationCore.selectedNode) {
          clipboardItems.push({
            nodeType: AutomationCore.selectedNode._defKey,
            params: JSON.parse(JSON.stringify(AutomationCore.selectedNode.properties || {})),
            pos: { x: AutomationCore.selectedNode.pos[0], y: AutomationCore.selectedNode.pos[1] },
            customName: AutomationCore.selectedNode._customName || null
          });
        }
        for (var ai = 0; ai < selAns.length; ai++) {
          clipboardItems.push({
            type: 'annotation',
            text: selAns[ai].text,
            color: selAns[ai].color,
            bgColor: selAns[ai].bgColor,
            collapsed: selAns[ai].collapsed,
            pos: { x: selAns[ai].pos[0], y: selAns[ai].pos[1] }
          });
        }
        for (var gi = 0; gi < selGps.length; gi++) {
          clipboardItems.push({
            type: 'group',
            title: selGps[gi].title,
            color: selGps[gi].color,
            bgColor: selGps[gi].bgColor,
            size: { w: selGps[gi].size[0], h: selGps[gi].size[1] },
            pos: { x: selGps[gi].pos[0], y: selGps[gi].pos[1] }
          });
        }
        _setClipboard(clipboardItems);
        var copyMsg = [];
        if (selNodes.length > 0) copyMsg.push(selNodes.length + ' 个节点');
        else if (AutomationCore.selectedNode) copyMsg.push('1 个节点');
        if (selAns.length > 0) copyMsg.push(selAns.length + ' 个注释');
        if (selGps.length > 0) copyMsg.push(selGps.length + ' 个分组');
        showToast('已复制 ' + copyMsg.join('、'), 'inf');
      }
    }
    if (e.ctrlKey && e.key === 'v' && _clipboard) {
      var target = e.target || e.srcElement;
      if (target && (target.tagName === 'TEXTAREA' || target.tagName === 'INPUT' || target.contentEditable === 'true')) {
        return;
      }
      e.preventDefault();
      _setPasteCount(_pasteCount + 1);
      var pastedNodes = [];
      var pastedAnnotations = 0;
      var pastedGroups = 0;
      var idMap = {};
      for (var j = 0; j < _clipboard.length; j++) {
        var item = _clipboard[j];
        if (item.type === 'annotation') {
          var newAn = AutomationCore.addAnnotation(
            item.pos.x + 40 * _pasteCount,
            item.pos.y + 40 * _pasteCount,
            item.text,
            item.color
          );
          if (item.bgColor) { newAn.bgColor = item.bgColor; if (newAn._domEl) newAn._domEl.style.background = item.bgColor; }
          if (item.collapsed) { newAn.collapsed = true; if (newAn._domEl) newAn._domEl.classList.add('collapsed'); }
          pastedAnnotations++;
        } else if (item.type === 'group') {
          var newGp = AutomationCore.addGroup(
            item.pos.x + 40 * _pasteCount,
            item.pos.y + 40 * _pasteCount,
            item.size.w,
            item.size.h,
            item.title,
            item.color
          );
          if (item.bgColor) { newGp.bgColor = item.bgColor; if (newGp._domEl) { newGp._domEl.style.setProperty('--gp-bg', item.bgColor); newGp._domEl.style.background = item.bgColor; } }
          pastedGroups++;
        } else if (item.nodes) {
          var nodeList = item.nodes;
          for (var k = 0; k < nodeList.length; k++) {
            var nodeItem = nodeList[k];
            var newNode = AutomationCore.addNodeAtPosition(nodeItem.nodeType, nodeItem.pos.x + 40 * _pasteCount, nodeItem.pos.y + 40 * _pasteCount);
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
              AutomationCore.refreshNode(newNode);
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
                AutomationCore.lgGraphObj.connect(newFromId, conn.origin_slot, newToId, conn.target_slot);
              }
            }
          }
        } else {
          var newNode = AutomationCore.addNodeAtPosition(item.nodeType, item.pos.x + 40 * _pasteCount, item.pos.y + 40 * _pasteCount);
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
            AutomationCore.refreshNode(newNode);
            pastedNodes.push(newNode);
          }
        }
      }
      if (pastedNodes.length > 0 || pastedAnnotations > 0 || pastedGroups > 0) {
        if (pastedNodes.length === 1 && pastedAnnotations === 0 && pastedGroups === 0) {
          AutomationCore.selectNode(pastedNodes[0]);
          AutomationProperty.render(pastedNodes[0]);
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
  setInterval(function() { updateMinimap(); }, 280);  //部分节点变化可能会不自动触发更新，需定时更新
  undoManager.reset();

  initSidebarResize();
  initSidebarToggle();
  requestAnimationFrame(function() { _repositionMinimap(); });

  initNodeSearch();
  initLogPanel();
  initCoordOverlay();

  var btnNodeSearch = document.getElementById('btn-node-search');
  if (btnNodeSearch) {
    btnNodeSearch.addEventListener('click', function() {
      if (window._showSearchFloat) window._showSearchFloat();
    });
  }

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
  browseScriptPath: browseScriptPath,
  browseFolderPath: browseFolderPath,
  browseWindowList: browseWindowList,
  browseProgramFile: browseProgramFile,
  browseWindowTitle: browseWindowTitle,
  browseProcessList: browseProcessList,
  showContextMenu: showContextMenu,
  hideContextMenu: hideContextMenu,
  addNodeToCenter: addNodeToCenter,
  updateMinimap: updateMinimap,
  clearNodeHighlights: function() { AutomationCore.clearAllHighlights(); },
  undoPush: function() { undoManager.push(); },
  refreshVarPanel: refreshVarPanel,
  _setContextTarget: _setContextTarget,
  _setAnnotationContext: _setAnnotationContext,
  _setGroupContext: _setGroupContext,
};

window.AutomationApp = window._autoEditor;

window._onGlobalEditorHotkey = function(action) {
  try {
    if (action === 'run') {
      runGraph();
    } else if (action === 'pause') {
      pauseGraph();
    } else if (action === 'stop') {
      stopGraph();
    } else if (action === 'fullscreen') {
      toggleFullscreen();
    }
  } catch (e) {}
};

window.addEventListener('message', function(event) {
  var data = event && event.data;
  if (!data || typeof data !== 'object') return;
  if (data.source !== 'macro-forge-host') return;
  if (data.type === 'global-hotkey' && data.action && window._onGlobalEditorHotkey) {
    window._onGlobalEditorHotkey(data.action);
  }
  if (data.type === 'reload-hotkeys') {
    _loadEditorHotkeys();
  }
});

document.addEventListener('DOMContentLoaded', initEditor);
