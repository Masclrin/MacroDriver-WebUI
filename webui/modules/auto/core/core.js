'use strict';

import { _s } from './state.js';
import {
    _renderNodeDOM, _addNodeToDOM, _bindInlineFields,
    _removeNodeFromDOM, _refreshNodeDOM, _createNodeData,
    _setSelectNodeByIdFn
} from '../render/node-renderer.js';
import {
    _renderAllConnections, _renderConnection, _updateAffectedConnections,
    _addConnection, _removeConnectionById, _removeConnectionsForNode, _removeConnectionsForPort
} from '../render/connection-renderer.js';
import { _renderAnnotation, _setCoreRef as _setAnnotationCoreRef } from '../render/annotation-renderer.js';
import { _renderGroup, _setCoreRef as _setGroupCoreRef, _getNodesInGroup, _getAnnotationsInGroup } from '../render/group-renderer.js';
import { _updateViewport, _setZoom, _updateMinimap, _navigateMinimap } from '../render/viewport.js';
import {
    _startAutoPan, _stopAutoPan,
    _onCanvasMouseDown, _onCanvasMouseMove, _onCanvasMouseUp,
    _onCanvasWheel, _onCanvasDblClick,
    _checkLineDeleteAtPoint, _updateSelectionFromBox
} from '../logic/events.js';
import {
    _addNode, _removeNodeById, _selectNodeById,
    _getAnnotationsNearNodes, _deselectAll, _updateBranchPorts
} from '../logic/graph-ops.js';
import { _setGlobalNotify } from './notify.js';
import { _screenToLocal, _toZh } from './utils.js';

var _graphAPI = {
    _nodes: _s._nodeList,
    _links: _s._linksSparse,

    getNodeById: function(id) {
        return _s._nodes[id] || null;
    },

    getNodes: function() {
        return _s._nodeList;
    },

    createNode: function(type) {
        return _createNodeData(type);
    },

    add: function(node) {
        _addNode(node);
    },

    remove: function(node) {
        if (typeof node === 'object' && node !== null) {
            _removeNodeById(node.id);
        }
    },

    connect: function(fromNodeId, fromSlot, toNodeId, toSlot) {
        return _addConnection(fromNodeId, fromSlot, toNodeId, toSlot);
    },

    clear: function() {
        _s._connections = [];
        _s._linksSparse = [];
        _s._nodeList.length = 0;
        for (var k in _s._nodes) {
            if (_s._nodes.hasOwnProperty(k)) delete _s._nodes[k];
        }
        _s._selectedNodeId = null;
        _s._selectedNodes = [];
        _s._nextNodeId = 1;
        _s._nextLinkId = 1;
        if (_s._nodeLayerEl) _s._nodeLayerEl.innerHTML = '';
        if (_s._connSvgEl) _s._connSvgEl.innerHTML = '';
        if (AutomationCore) {
            AutomationCore.clearAnnotations();
            AutomationCore.clearGroups();
        }
        AutomationCore._notifyGraphChange();
    },

    setNextNodeId: function(id) {
        if (typeof id === 'number' && id >= _s._nextNodeId) {
            _s._nextNodeId = id + 1;
        }
    },

    get onNodeAdded() { return _s._onNodeAdded; },
    set onNodeAdded(fn) { _s._onNodeAdded = fn; },
    get onNodeRemoved() { return _s._onNodeRemoved; },
    set onNodeRemoved(fn) { _s._onNodeRemoved = fn; },
    get onConnectionChange() { return _s._onConnectionChange; },
    set onConnectionChange(fn) { _s._onConnectionChange = fn; }
};

var _canvasAPI = {
    canvas: null,
    ds: {
        get scale() { return _s._vpScale; },
        get offset() { return [_s._vpOffset.x, _s._vpOffset.y]; }
    },

    selectNode: function(node) {
        if (node) _selectNodeById(node.id);
        else _deselectAll();
    },

    setDirty: function() {},

    getNodeAt: function(x, y) {
        var local = _screenToLocal(x, y);
        for (var i = _s._nodeList.length - 1; i >= 0; i--) {
            var n = _s._nodeList[i];
            if (local.x >= n.pos[0] && local.x <= n.pos[0] + (n.size[0] || 220) &&
                local.y >= n.pos[1] && local.y <= n.pos[1] + (n.size[1] || 100)) {
                return n;
            }
        }
        return null;
    },

    resize: function() {
        _renderAllConnections();
        _updateMinimap();
    },

    get onNodeSelected() { return _s._onNodeSelected; },
    set onNodeSelected(fn) { _s._onNodeSelected = fn; },
    get onNodeDeselected() { return _s._onNodeDeselected; },
    set onNodeDeselected(fn) { _s._onNodeDeselected = fn; }
};

export const AutomationCore = {
    lgGraphObj: _graphAPI,
    lgCanvas: _canvasAPI,
    selectedNode: null,
    executionState: 'IDLE',
    _onGraphChange: null,
    onGraphChange: function(callback) {
        this._onGraphChange = callback;
    },
    _notifyGraphChange: function() {
        if (this._onGraphChange) {
            this._onGraphChange();
        }
    },

    init: function(canvasAreaEl) {
        _s._canvasArea = canvasAreaEl;
        _canvasAPI.canvas = canvasAreaEl;

        _s._viewportEl = document.getElementById('cv-vp');
        if (!_s._viewportEl) {
            _s._viewportEl = document.createElement('div');
            _s._viewportEl.id = 'cv-vp';
            _s._viewportEl.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;transform-origin:0 0;';
            _s._canvasArea.appendChild(_s._viewportEl);
        }

        _s._bgEl = document.getElementById('cv-bg');
        if (!_s._bgEl) {
            _s._bgEl = document.createElement('div');
            _s._bgEl.id = 'cv-bg';
            _s._bgEl.style.cssText = 'position:absolute;top:-10000px;left:-10000px;width:20000px;height:20000px;' +
                'background-image:radial-gradient(circle,rgba(255,255,255,0.04) 1px,transparent 1px);' +
                'background-size:24px 24px;pointer-events:none;';
            _s._viewportEl.appendChild(_s._bgEl);
        }

        _s._connSvgEl = document.getElementById('conn-l');
        if (!_s._connSvgEl) {
            _s._connSvgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            _s._connSvgEl.id = 'conn-l';
            _s._connSvgEl.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
            _s._connSvgEl.style.cssText = 'position:absolute;top:0;left:0;width:20000px;height:20000px;pointer-events:none;z-index:1;overflow:visible;';
            _s._viewportEl.appendChild(_s._connSvgEl);
        }
        _s._connSvgEl.innerHTML = '';

        _s._nodeLayerEl = document.getElementById('nd-l');
        if (!_s._nodeLayerEl) {
            _s._nodeLayerEl = document.createElement('div');
            _s._nodeLayerEl.id = 'nd-l';
            _s._nodeLayerEl.style.cssText = 'position:absolute;top:0;left:0;width:20000px;height:20000px;z-index:2;';
            _s._viewportEl.appendChild(_s._nodeLayerEl);
        }
        _s._nodeLayerEl.innerHTML = '';

        _s._groupLayerEl = document.getElementById('gp-l');
        if (!_s._groupLayerEl) {
            _s._groupLayerEl = document.createElement('div');
            _s._groupLayerEl.id = 'gp-l';
            _s._groupLayerEl.style.cssText = 'position:absolute;top:0;left:0;width:20000px;height:20000px;z-index:3;pointer-events:none;';
            _s._viewportEl.appendChild(_s._groupLayerEl);
        }
        _s._groupLayerEl.innerHTML = '';

        _s._annotationLayerEl = document.getElementById('an-l');
        if (!_s._annotationLayerEl) {
            _s._annotationLayerEl = document.createElement('div');
            _s._annotationLayerEl.id = 'an-l';
            _s._annotationLayerEl.style.cssText = 'position:absolute;top:0;left:0;width:20000px;height:20000px;z-index:4;pointer-events:none;';
            _s._viewportEl.appendChild(_s._annotationLayerEl);
        }
        _s._annotationLayerEl.innerHTML = '';

        _s._canvasArea.addEventListener('mousedown', _onCanvasMouseDown);
        document.addEventListener('mousemove', _onCanvasMouseMove);
        document.addEventListener('mouseup', _onCanvasMouseUp);
        _s._canvasArea.addEventListener('wheel', _onCanvasWheel, { passive: false });
        _s._canvasArea.addEventListener('dblclick', _onCanvasDblClick);

        _s._canvasArea.addEventListener('contextmenu', function(e) { e.preventDefault(); });

        document.addEventListener('keydown', function(e) {
            if (e.code === 'Space' && !e.target.closest('input,textarea,select')) {
                _s._spaceHeld = true;
                _s._canvasArea.style.cursor = 'grab';
            }
        });
        document.addEventListener('keyup', function(e) {
            if (e.code === 'Space') {
                _s._spaceHeld = false;
                if (!_s._isPanning) _s._canvasArea.style.cursor = '';
            }
        });

        _updateViewport();
        console.log('[AutomationCore] DOM渲染引擎初始化完成');
    },

    addNodeAtCenter: function(nodeType) {
        var node = _createNodeData(nodeType);
        if (!node) return null;
        var r = _s._canvasArea.getBoundingClientRect();
        var cx = (r.width / 2 - _s._vpOffset.x) / _s._vpScale;
        var cy = (r.height / 2 - _s._vpOffset.y) / _s._vpScale;
        node.pos[0] = cx - (node.size[0] || 110);
        node.pos[1] = cy - (node.size[1] || 50);
        _addNode(node);
        return node;
    },

    addNodeAtMouse: function(nodeType, event) {
        var node = _createNodeData(nodeType);
        if (!node) return null;
        var local = _screenToLocal(event.clientX, event.clientY);
        node.pos[0] = local.x - 60;
        node.pos[1] = local.y - 20;
        _addNode(node);
        return node;
    },

    addNodeAtPosition: function(nodeType, x, y) {
        var node = _createNodeData(nodeType);
        if (!node) return null;
        node.pos[0] = x;
        node.pos[1] = y;
        _addNode(node);
        return node;
    },

    clear: function() {
        _graphAPI.clear();
        this.selectedNode = null;
    },

    selectNode: function(node) {
        if (node) _selectNodeById(node.id);
        else _deselectAll();
    },

    refreshNode: function(node) {
        if (node) _refreshNodeDOM(node);
    },

    updateBranchPorts: function(node, newCount) {
        _updateBranchPorts(node, newCount);
    },

    _refreshNodeDOM: function(node) {
        _refreshNodeDOM(node);
    },

    refreshAllConnections: function() {
        _renderAllConnections();
    },

    setZoom: function(scale, cx, cy) {
        _setZoom(scale, cx, cy);
    },

    setViewport: function(offsetX, offsetY, scale) {
        _s._vpOffset.x = offsetX;
        _s._vpOffset.y = offsetY;
        _s._vpScale = Math.max(0.15, Math.min(3, scale));
        _updateViewport();
        _updateMinimap();
    },

    zoomIn: function() {
        var r = _s._canvasArea.getBoundingClientRect();
        _setZoom(_s._vpScale * 1.15, r.width / 2, r.height / 2);
    },

    zoomOut: function() {
        var r = _s._canvasArea.getBoundingClientRect();
        _setZoom(_s._vpScale / 1.15, r.width / 2, r.height / 2);
    },

    zoomReset: function() {
        _s._vpScale = 1;
        _s._vpOffset = { x: 100, y: 100 };
        _updateViewport();
        _updateMinimap();
    },

    getZoomLevel: function() {
        return _s._vpScale;
    },

    screenToLocal: function(cx, cy) {
        return _screenToLocal(cx, cy);
    },

    updateMinimap: function() {
        _updateMinimap();
    },

    navigateMinimap: function(mx, my) {
        _navigateMinimap(mx, my);
    },

    setNodeHighlight: function(nodeId, state) {
    var el = document.getElementById('nd-' + nodeId);
    if (!el) return;
    el.classList.remove('executing', 'check-pass', 'check-fail', 'triggered', 'search-match', 'search-active');
    if (state) el.classList.add(state);
  },

  clearAllHighlights: function() {
    var highlighted = _s._nodeLayerEl ? _s._nodeLayerEl.querySelectorAll('.nd.executing,.nd.check-pass,.nd.check-fail,.nd.triggered,.nd.search-match,.nd.search-active') : [];
    for (var i = 0; i < highlighted.length; i++) {
      highlighted[i].classList.remove('executing', 'check-pass', 'check-fail', 'triggered', 'search-match', 'search-active');
    }
  },

    getViewportOffset: function() { return _s._vpOffset; },
    getViewportScale: function() { return _s._vpScale; },
    getNodes: function() { return _s._nodeList; },
    getConnections: function() { return _s._connections; },
    getSelectedNodes: function() { return _s._selectedNodes; },
    deleteSelectedNodes: function() {
        var ids = [];
        for (var i = 0; i < _s._selectedNodes.length; i++) {
            ids.push(_s._selectedNodes[i].id);
        }
        for (var j = 0; j < ids.length; j++) {
            _removeNodeById(ids[j]);
        }
        _s._selectedNodes = [];
        _updateMinimap();
    },
    disconnectNode: function(nodeId) {
        _removeConnectionsForNode(nodeId);
    },
    selectAll: function() {
        _s._selectedNodes = [];
        for (var i = 0; i < _s._nodeList.length; i++) {
            var node = _s._nodeList[i];
            _s._selectedNodes.push(node);
            var el = node._domEl || document.getElementById('nd-' + node.id);
            if (el) el.classList.add('sel');
        }
        _s._selectedAnnotations = [];
        for (var ai = 0; ai < _s._annotations.length; ai++) {
            _s._selectedAnnotations.push(_s._annotations[ai]);
            var ael = _s._annotations[ai]._domEl || document.getElementById('an-' + _s._annotations[ai].id);
            if (ael) ael.classList.add('sel');
        }
        _s._selectedGroups = [];
        for (var gi = 0; gi < _s._groups.length; gi++) {
            _s._selectedGroups.push(_s._groups[gi]);
            var gel = _s._groups[gi]._domEl || document.getElementById('gp-' + _s._groups[gi].id);
            if (gel) gel.classList.add('sel');
        }
    },

    addAnnotation: function(x, y, text, color) {
        var id = _s._nextAnnotationId++;
        var an = {
            id: id,
            pos: [x, y],
            text: text || '双击编辑注释',
            color: color || '#fbbf24',
            bgColor: 'linear-gradient(135deg,rgba(251,191,36,.72),rgba(251,191,36,.58))',
            collapsed: false,
            _domEl: null
        };
        _s._annotations.push(an);
        _renderAnnotation(an);
        AutomationCore._notifyGraphChange();
        return an;
    },
    removeAnnotation: function(id) {
        for (var i = 0; i < _s._annotations.length; i++) {
            if (_s._annotations[i].id === id) {
                if (_s._annotations[i]._domEl) _s._annotations[i]._domEl.remove();
                _s._annotations.splice(i, 1);
                _s._selectedAnnotations = _s._selectedAnnotations.filter(function(a) { return a.id !== id; });
                if (_s._selectedAnnotationId === id) _s._selectedAnnotationId = null;
                AutomationCore._notifyGraphChange();
                break;
            }
        }
    },
    getAnnotations: function() { return _s._annotations; },
    getSelectedAnnotations: function() { return _s._selectedAnnotations; },
    clearAnnotations: function() {
        _s._annotations = [];
        _s._nextAnnotationId = 1;
        if (_s._annotationLayerEl) _s._annotationLayerEl.innerHTML = '';
    },

    addGroup: function(x, y, w, h, title, color) {
        var id = _s._nextGroupId++;
        var gp = {
            id: id,
            pos: [x, y],
            size: [w || 300, h || 200],
            title: title || '分组',
            color: color || '#3b82f6',
            bgColor: 'rgba(59,130,246,.08)',
            _domEl: null
        };
        _s._groups.push(gp);
        _renderGroup(gp);
        AutomationCore._notifyGraphChange();
        return gp;
    },
    removeGroup: function(id) {
        for (var i = 0; i < _s._groups.length; i++) {
            if (_s._groups[i].id === id) {
                if (_s._groups[i]._domEl) _s._groups[i]._domEl.remove();
                _s._groups.splice(i, 1);
                _s._selectedGroups = _s._selectedGroups.filter(function(g) { return g.id !== id; });
                if (_s._selectedGroupId === id) _s._selectedGroupId = null;
                AutomationCore._notifyGraphChange();
                break;
            }
        }
    },
    removeGroupKeepContents: function(id) {
        for (var i = 0; i < _s._groups.length; i++) {
            if (_s._groups[i].id === id) {
                if (_s._groups[i]._domEl) _s._groups[i]._domEl.remove();
                _s._groups.splice(i, 1);
                _s._selectedGroups = _s._selectedGroups.filter(function(g) { return g.id !== id; });
                if (_s._selectedGroupId === id) _s._selectedGroupId = null;
                AutomationCore._notifyGraphChange();
                break;
            }
        }
    },
    getGroups: function() { return _s._groups; },
    getSelectedGroups: function() { return _s._selectedGroups; },
    clearGroups: function() {
        _s._groups = [];
        _s._nextGroupId = 1;
        if (_s._groupLayerEl) _s._groupLayerEl.innerHTML = '';
    },

    clearAll: function() {
        _graphAPI.clear();
        AutomationCore.clearAnnotations();
        AutomationCore.clearGroups();
        AutomationCore.selectedNode = null;
    },

    setLineDeleteMode: function(enabled) {
        _s._lineDeleteMode = !!enabled;
        _s._lineDeleteDragging = false;
        if (_s._lineDeleteMode) {
            _s._canvasArea.style.cursor = 'crosshair';
        } else {
            _s._canvasArea.style.cursor = '';
        }
    },
    isLineDeleteMode: function() {
        return _s._lineDeleteMode;
    }
};

_setSelectNodeByIdFn(_selectNodeById);

var _coreRef2 = {
    _notifyGraphChange: function() { AutomationCore._notifyGraphChange(); },
    removeAnnotation: function(id) { AutomationCore.removeAnnotation(id); },
    removeGroup: function(id) { AutomationCore.removeGroup(id); }
};
_setAnnotationCoreRef(_coreRef2);
_setGroupCoreRef(_coreRef2);

_setGlobalNotify(function() { AutomationCore._notifyGraphChange(); });

window.AutomationCore = AutomationCore;
