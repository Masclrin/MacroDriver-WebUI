'use strict';

import { _s } from '../core/state.js';
import { _screenToLocal, _getPortCenter, _bezier, _pointToBezierDist, _toZh } from '../core/utils.js';
import { _portTypeColors } from '../core/constants.js';
import { _createNodeData } from '../render/node-renderer.js';
import { _renderAllConnections, _updateAffectedConnections, _addConnection, _removeConnectionById } from '../render/connection-renderer.js';
import { _updateViewport, _updateMinimap, _setZoom } from '../render/viewport.js';
import { _removeNodeById, _selectNodeById, _getAnnotationsNearNodes, _deselectAll } from './graph-ops.js';

function _startAutoPan() {
    if (_s._autoPanActive) return;
    _s._autoPanActive = true;
    function tick() {
        if (!_s._autoPanActive || !_s._isDraggingNode) {
            _s._autoPanActive = false;
            return;
        }
        var r = _s._canvasArea.getBoundingClientRect();
        var edge = 40;
        var speed = 8;
        var dx = 0, dy = 0;
        if (_s._autoPanMouseX - r.left < edge) dx = speed * (1 - Math.max(0, _s._autoPanMouseX - r.left) / edge);
        else if (r.right - _s._autoPanMouseX < edge) dx = -speed * (1 - Math.max(0, r.right - _s._autoPanMouseX) / edge);
        if (_s._autoPanMouseY - r.top < edge) dy = speed * (1 - Math.max(0, _s._autoPanMouseY - r.top) / edge);
        else if (r.bottom - _s._autoPanMouseY < edge) dy = -speed * (1 - Math.max(0, r.bottom - _s._autoPanMouseY) / edge);
        if (dx !== 0 || dy !== 0) {
            _s._vpOffset.x += dx;
            _s._vpOffset.y += dy;
            _updateViewport();
            _updateMinimap();
            if (_s._dragGhostStartLocal) {
                _s._dragGhostStartLocal.x -= dx / _s._vpScale;
                _s._dragGhostStartLocal.y -= dy / _s._vpScale;
            }
            if (_s._dragGhostEl && _s._dragGhostStartLocal) {
                var gDx = (_s._autoPanMouseX - r.left - _s._vpOffset.x) / _s._vpScale - _s._dragGhostStartLocal.x;
                var gDy = (_s._autoPanMouseY - r.top - _s._vpOffset.y) / _s._vpScale - _s._dragGhostStartLocal.y;
                var gOx = parseFloat(_s._dragGhostEl.dataset.ox) || 0;
                var gOy = parseFloat(_s._dragGhostEl.dataset.oy) || 0;
                _s._dragGhostEl.style.left = (gOx + gDx) + 'px';
                _s._dragGhostEl.style.top = (gOy + gDy) + 'px';
                _s._dragPendingDx = gDx;
                _s._dragPendingDy = gDy;
            }
            for (var dai = 0; dai < _s._dragNearbyAnnotations.length; dai++) {
                var dna = _s._dragNearbyAnnotations[dai];
                var aDx = _s._dragPendingDx;
                var aDy = _s._dragPendingDy;
                dna.an.pos[0] = dna.startX + aDx;
                dna.an.pos[1] = dna.startY + aDy;
                if (dna.an._domEl) {
                    dna.an._domEl.style.left = dna.an.pos[0] + 'px';
                    dna.an._domEl.style.top = dna.an.pos[1] + 'px';
                }
            }
        }
        _s._autoPanRAF = requestAnimationFrame(tick);
    }
    _s._autoPanRAF = requestAnimationFrame(tick);
}

function _stopAutoPan() {
    _s._autoPanActive = false;
    if (_s._autoPanRAF) {
        cancelAnimationFrame(_s._autoPanRAF);
        _s._autoPanRAF = 0;
    }
}

function _checkLineDeleteAtPoint(clientX, clientY) {
    if (!_s._connSvgEl) return;
    var local = _screenToLocal(clientX, clientY);
    var threshold = 12 / _s._vpScale;
    var toRemove = null;
    var minDist = Infinity;
    for (var i = 0; i < _s._connections.length; i++) {
        var conn = _s._connections[i];
        var fromNode = _s._nodes[conn.origin_id];
        var toNode = _s._nodes[conn.target_id];
        if (!fromNode || !toNode) continue;
        var fromPort = fromNode.outputs[conn.origin_slot];
        var toPort = toNode.inputs[conn.target_slot];
        if (!fromPort || !toPort) continue;
        var fe = _getPortCenter(conn.origin_id, fromPort._portKey, 'o');
        var te = _getPortCenter(conn.target_id, toPort._portKey, 'i');
        if (!fe || !te) continue;
        var dist = _pointToBezierDist(local.x, local.y, fe.x, fe.y, te.x, te.y);
        if (dist < threshold && dist < minDist) {
            minDist = dist;
            toRemove = conn;
        }
    }
    if (toRemove) {
        _removeConnectionById(toRemove.id);
        if (window._autoEditor && window._autoEditor.updateStatusBar) {
            window._autoEditor.updateStatusBar();
        }
    }
}

function _updateSelectionFromBox() {
    var selBox = document.getElementById('sel-box');
    if (!selBox || selBox.style.display === 'none') return;
    var bx = parseFloat(selBox.style.left) || 0;
    var by = parseFloat(selBox.style.top) || 0;
    var bw = parseFloat(selBox.style.width) || 0;
    var bh = parseFloat(selBox.style.height) || 0;
    if (bw < 5 && bh < 5) return;

    var cvRect = _s._canvasArea.getBoundingClientRect();
    var absX = bx + cvRect.left;
    var absY = by + cvRect.top;

    _s._selectedNodes = [];
    for (var i = 0; i < _s._nodeList.length; i++) {
        var node = _s._nodeList[i];
        var el = node._domEl || document.getElementById('nd-' + node.id);
        if (!el) continue;
        var r = el.getBoundingClientRect();
        if (r.left < absX + bw && r.right > absX && r.top < absY + bh && r.bottom > absY) {
            _s._selectedNodes.push(node);
            el.classList.add('sel');
        } else {
            el.classList.remove('sel');
        }
    }

    _s._selectedAnnotations = [];
    for (var ai = 0; ai < _s._annotations.length; ai++) {
        var an = _s._annotations[ai];
        var anEl = an._domEl || document.getElementById('an-' + an.id);
        if (!anEl) continue;
        var ar = anEl.getBoundingClientRect();
        if (ar.left < absX + bw && ar.right > absX && ar.top < absY + bh && ar.bottom > absY) {
            _s._selectedAnnotations.push(an);
            anEl.classList.add('sel');
        } else {
            anEl.classList.remove('sel');
        }
    }

    _s._selectedGroups = [];
    for (var gi = 0; gi < _s._groups.length; gi++) {
        var gp = _s._groups[gi];
        var gpEl = gp._domEl || document.getElementById('gp-' + gp.id);
        if (!gpEl) continue;
        var gr = gpEl.getBoundingClientRect();
        if (gr.left < absX + bw && gr.right > absX && gr.top < absY + bh && gr.bottom > absY) {
            _s._selectedGroups.push(gp);
            gpEl.classList.add('sel');
        } else {
            gpEl.classList.remove('sel');
        }
    }
}

function _onCanvasMouseDown(e) {
    if (e.target.closest('#mm')) return;

    if (_s._lineDeleteMode && e.button === 0) {
        _s._lineDeleteDragging = true;
        _checkLineDeleteAtPoint(e.clientX, e.clientY);
        e.preventDefault();
        e.stopPropagation();
        return;
    }

    var closeBtn = e.target.closest('.nx[data-action="delete"]');
    if (closeBtn) {
        var ndEl = closeBtn.closest('.nd');
        if (ndEl) {
            var _nid = parseInt(ndEl.dataset.id);
            _removeNodeById(_nid);
            e.stopPropagation();
            return;
        }
    }

    var portEl = e.target.closest('.pt');
    if (portEl && e.button === 0) {
        e.preventDefault();
        e.stopPropagation();
        _s._isConnecting = true;
        _s._connFromNodeId = parseInt(portEl.dataset.n);
        _s._connFromPortKey = portEl.dataset.p;
        _s._connFromDir = portEl.dataset.d;
        _s._connFromPortType = portEl.dataset.pt;
        if (!_s._tmpPathEl && _s._connSvgEl) {
            _s._tmpPathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            _s._tmpPathEl.setAttribute('class', 'tmp');
            _s._tmpPathEl.setAttribute('stroke', _portTypeColors[_s._connFromPortType] || '#94a3b8');
            _s._connSvgEl.appendChild(_s._tmpPathEl);
        }
        return;
    }

    var headerEl = e.target.closest('.nd-h');
    if (headerEl && e.button === 0) {
        var ndEl = headerEl.closest('.nd');
        if (ndEl) {
            var nid = parseInt(ndEl.dataset.id);
            var node = _s._nodes[nid];
            if (node) {
                var isInSelection = false;
                for (var ci = 0; ci < _s._selectedNodes.length; ci++) {
                    if (_s._selectedNodes[ci].id === nid) { isInSelection = true; break; }
                }
                if (!isInSelection) {
                    for (var di = 0; di < _s._selectedNodes.length; di++) {
                        var selEl = _s._selectedNodes[di]._domEl || document.getElementById('nd-' + _s._selectedNodes[di].id);
                        if (selEl) selEl.classList.remove('sel');
                    }
                    _s._selectedNodes = [];
                }
                _selectNodeById(nid);
                _s._isDraggingNode = true;
                _s._dragNodeId = nid;
                var local = _screenToLocal(e.clientX, e.clientY);
                _s._dragOffsetX = local.x - node.pos[0];
                _s._dragOffsetY = local.y - node.pos[1];
                _s._dragStartPositions = {};
                var isInSelection2 = false;
                for (var si = 0; si < _s._selectedNodes.length; si++) {
                    if (_s._selectedNodes[si].id === nid) { isInSelection2 = true; break; }
                }
                if (isInSelection2) {
                    for (var sj = 0; sj < _s._selectedNodes.length; sj++) {
                        _s._dragStartPositions[_s._selectedNodes[sj].id] = {
                            x: _s._selectedNodes[sj].pos[0],
                            y: _s._selectedNodes[sj].pos[1]
                        };
                    }
                } else {
                    _s._dragStartPositions[nid] = { x: node.pos[0], y: node.pos[1] };
                }
                _s._dragIsMultiSelect = isInSelection2 && _s._selectedNodes.length > 1;
                ndEl.classList.add('drag');

                _s._dragGhostStartLocal = { x: local.x, y: local.y };
                _s._dragGhostEl = document.createElement('div');
                _s._dragGhostEl.className = 'drag-ghost';
                _s._dragGhostEl.style.cssText = 'position:absolute;pointer-events:none;z-index:200;border:2px dashed var(--acc);border-radius:var(--r);background:rgba(34,211,238,0.08);transition:none';
                if (_s._dragIsMultiSelect) {
                    var minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
                    for (var gid in _s._dragStartPositions) {
                        if (!_s._dragStartPositions.hasOwnProperty(gid)) continue;
                        var gn = _s._nodes[gid];
                        if (!gn) continue;
                        minX = Math.min(minX, gn.pos[0]);
                        minY = Math.min(minY, gn.pos[1]);
                        maxX = Math.max(maxX, gn.pos[0] + (gn.size[0] || 220));
                        maxY = Math.max(maxY, gn.pos[1] + (gn.size[1] || 100));
                    }
                    _s._dragGhostEl.style.left = minX + 'px';
                    _s._dragGhostEl.style.top = minY + 'px';
                    _s._dragGhostEl.style.width = (maxX - minX) + 'px';
                    _s._dragGhostEl.style.height = (maxY - minY) + 'px';
                    _s._dragGhostEl.dataset.ox = String(minX);
                    _s._dragGhostEl.dataset.oy = String(minY);
                } else {
                    _s._dragGhostEl.style.left = node.pos[0] + 'px';
                    _s._dragGhostEl.style.top = node.pos[1] + 'px';
                    _s._dragGhostEl.style.width = (node.size[0] || 220) + 'px';
                    _s._dragGhostEl.style.height = (node.size[1] || 100) + 'px';
                    _s._dragGhostEl.dataset.ox = String(node.pos[0]);
                    _s._dragGhostEl.dataset.oy = String(node.pos[1]);
                }
                _s._nodeLayerEl.appendChild(_s._dragGhostEl);

                if (_s._dragIsMultiSelect) {
                    for (var hid in _s._dragStartPositions) {
                        if (!_s._dragStartPositions.hasOwnProperty(hid)) continue;
                        var hel = document.getElementById('nd-' + hid);
                        if (hel) hel.style.opacity = '0.3';
                    }
                } else {
                    ndEl.style.opacity = '0.3';
                }
                if (_s._connSvgEl) _s._connSvgEl.style.opacity = '0.2';

                var _draggedNodeIds = _s._dragIsMultiSelect ? Object.keys(_s._dragStartPositions).map(Number) : [_s._dragNodeId];
                var nearAnns = _getAnnotationsNearNodes(_draggedNodeIds, 30);
                _s._dragNearbyAnnotations = [];
                for (var nai = 0; nai < nearAnns.length; nai++) {
                    _s._dragNearbyAnnotations.push({ an: nearAnns[nai], startX: nearAnns[nai].pos[0], startY: nearAnns[nai].pos[1] });
                }

                _s._autoPanMouseX = e.clientX;
                _s._autoPanMouseY = e.clientY;
                _startAutoPan();

                e.preventDefault();
                return;
            }
        }
    }

    var nodeEl = e.target.closest('.nd');
    if (nodeEl && e.button === 0) {
        var _nid2 = parseInt(nodeEl.dataset.id);
        _selectNodeById(_nid2);
        return;
    }

    if (e.button === 1 || (e.button === 0 && _s._spaceHeld)) {
        _s._isPanning = true;
        _s._panStartX = e.clientX;
        _s._panStartY = e.clientY;
        _s._panStartOffX = _s._vpOffset.x;
        _s._panStartOffY = _s._vpOffset.y;
        _s._canvasArea.style.cursor = 'grabbing';
        e.preventDefault();
        return;
    }

    if (e.button === 0 && !e.target.closest('.nd') && !e.target.closest('#mm') && !e.target.closest('#conn-l g')) {
        _deselectAll();
        _s._isSelecting = true;
        var cvRect = _s._canvasArea.getBoundingClientRect();
        _s._selStartX = e.clientX;
        _s._selStartY = e.clientY;
        _s._selOffX = cvRect.left;
        _s._selOffY = cvRect.top;
        _s._selectedNodes = [];
        var selBox = document.getElementById('sel-box');
        if (selBox) {
            selBox.style.display = 'block';
            selBox.style.left = (e.clientX - cvRect.left) + 'px';
            selBox.style.top = (e.clientY - cvRect.top) + 'px';
            selBox.style.width = '0';
            selBox.style.height = '0';
        }
    }
}

function _onCanvasMouseMove(e) {
    var local = _screenToLocal(e.clientX, e.clientY);

    _s._autoPanMouseX = e.clientX;
    _s._autoPanMouseY = e.clientY;

    if (_s._lineDeleteMode && _s._lineDeleteDragging) {
        _checkLineDeleteAtPoint(e.clientX, e.clientY);
        return;
    }

    if (_s._isPanning) {
        _s._vpOffset.x = _s._panStartOffX + (e.clientX - _s._panStartX);
        _s._vpOffset.y = _s._panStartOffY + (e.clientY - _s._panStartY);
        _updateViewport();
        _updateMinimap();
        return;
    }

    if (_s._isSelecting) {
        var selBox = document.getElementById('sel-box');
        if (selBox) {
            var x1 = Math.min(_s._selStartX, e.clientX) - _s._selOffX;
            var y1 = Math.min(_s._selStartY, e.clientY) - _s._selOffY;
            var x2 = Math.max(_s._selStartX, e.clientX) - _s._selOffX;
            var y2 = Math.max(_s._selStartY, e.clientY) - _s._selOffY;
            selBox.style.left = x1 + 'px';
            selBox.style.top = y1 + 'px';
            selBox.style.width = (x2 - x1) + 'px';
            selBox.style.height = (y2 - y1) + 'px';
        }
        _updateSelectionFromBox();
        return;
    }

    if (_s._isDraggingNode && _s._dragNodeId !== null) {
        if (_s._dragGhostEl && _s._dragGhostStartLocal) {
            var gDx = local.x - _s._dragGhostStartLocal.x;
            var gDy = local.y - _s._dragGhostStartLocal.y;
            var gOx = parseFloat(_s._dragGhostEl.dataset.ox) || 0;
            var gOy = parseFloat(_s._dragGhostEl.dataset.oy) || 0;
            _s._dragGhostEl.style.left = (gOx + gDx) + 'px';
            _s._dragGhostEl.style.top = (gOy + gDy) + 'px';
            _s._dragPendingDx = gDx;
            _s._dragPendingDy = gDy;
            for (var dai = 0; dai < _s._dragNearbyAnnotations.length; dai++) {
                var dna = _s._dragNearbyAnnotations[dai];
                dna.an.pos[0] = dna.startX + gDx;
                dna.an.pos[1] = dna.startY + gDy;
                if (dna.an._domEl) {
                    dna.an._domEl.style.left = dna.an.pos[0] + 'px';
                    dna.an._domEl.style.top = dna.an.pos[1] + 'px';
                }
            }
        } else {
            var node = _s._nodes[_s._dragNodeId];
            if (node) {
                if (_s._dragIsMultiSelect && _s._dragStartPositions) {
                    var _mmDx = _s._dragGhostStartLocal ? (local.x - _s._dragGhostStartLocal.x) : (local.x - _s._dragOffsetX - (_s._dragStartPositions[_s._dragNodeId] ? _s._dragStartPositions[_s._dragNodeId].x : node.pos[0]));
                    var _mmDy = _s._dragGhostStartLocal ? (local.y - _s._dragGhostStartLocal.y) : (local.y - _s._dragOffsetY - (_s._dragStartPositions[_s._dragNodeId] ? _s._dragStartPositions[_s._dragNodeId].y : node.pos[1]));
                    _s._dragPendingDx = _mmDx;
                    _s._dragPendingDy = _mmDy;
                    var _mminX = Infinity, _mminY = Infinity;
                    for (var mid in _s._dragStartPositions) {
                        if (!_s._dragStartPositions.hasOwnProperty(mid)) continue;
                        var _mnx = _s._dragStartPositions[mid].x + _mmDx;
                        var _mny = _s._dragStartPositions[mid].y + _mmDy;
                        if (_mnx < _mminX) _mminX = _mnx;
                        if (_mny < _mminY) _mminY = _mny;
                    }
                    var _mmadjX = _mminX < 0 ? -_mminX : 0;
                    var _mmadjY = _mminY < 0 ? -_mminY : 0;
                    for (var mid in _s._dragStartPositions) {
                        if (!_s._dragStartPositions.hasOwnProperty(mid)) continue;
                        var mn = _s._nodes[mid];
                        if (!mn) continue;
                        mn.pos[0] = _s._dragStartPositions[mid].x + _mmDx + _mmadjX;
                        mn.pos[1] = _s._dragStartPositions[mid].y + _mmDy + _mmadjY;
                        var mel = document.getElementById('nd-' + mid);
                        if (mel) {
                            mel.style.left = mn.pos[0] + 'px';
                            mel.style.top = mn.pos[1] + 'px';
                        }
                    }
                    _updateAffectedConnections();
                } else {
                    node.pos[0] = local.x - _s._dragOffsetX;
                    node.pos[1] = local.y - _s._dragOffsetY;
                    var el = document.getElementById('nd-' + _s._dragNodeId);
                    if (el) {
                        el.style.left = node.pos[0] + 'px';
                        el.style.top = node.pos[1] + 'px';
                    }
                    _updateAffectedConnections();
                }
            }
        }
        return;
    }

    if (_s._isConnecting && _s._tmpPathEl) {
        var fromCenter = _getPortCenter(_s._connFromNodeId, _s._connFromPortKey, _s._connFromDir);
        if (fromCenter) {
            var d;
            if (_s._connFromDir === 'o') {
                d = _bezier(fromCenter.x, fromCenter.y, local.x, local.y);
            } else {
                d = _bezier(local.x, local.y, fromCenter.x, fromCenter.y);
            }
            _s._tmpPathEl.setAttribute('d', d);
        }
        return;
    }
}

function _onCanvasMouseUp(e) {
    _stopAutoPan();

    if (_s._lineDeleteDragging) {
        _s._lineDeleteDragging = false;
    }

    if (_s._isPanning) {
        _s._isPanning = false;
        _s._canvasArea.style.cursor = '';
    }

    if (_s._isSelecting) {
        _s._isSelecting = false;
        var selBox = document.getElementById('sel-box');
        if (selBox) {
            selBox.style.display = 'none';
            selBox.style.width = '0';
            selBox.style.height = '0';
        }
    }

    if (_s._isDraggingNode) {
        if (_s._dragRAF) {
            cancelAnimationFrame(_s._dragRAF);
            _s._dragRAF = 0;
        }

        if (_s._dragGhostEl) {
            var pdx = _s._dragPendingDx;
            var pdy = _s._dragPendingDy;
            var draggedNodeIds = [];
            if (_s._dragIsMultiSelect && _s._dragStartPositions) {
                for (var fid in _s._dragStartPositions) {
                    if (!_s._dragStartPositions.hasOwnProperty(fid)) continue;
                    var fn = _s._nodes[fid];
                    if (!fn) continue;
                    fn.pos[0] = _s._dragStartPositions[fid].x + pdx;
                    fn.pos[1] = _s._dragStartPositions[fid].y + pdy;
                    draggedNodeIds.push(fid);
                    var fel = document.getElementById('nd-' + fid);
                    if (fel) {
                        fel.style.left = fn.pos[0] + 'px';
                        fel.style.top = fn.pos[1] + 'px';
                        fel.style.opacity = '';
                    }
                }
            } else {
                var fn = _s._nodes[_s._dragNodeId];
                if (fn) {
                    fn.pos[0] = fn.pos[0] + pdx;
                    fn.pos[1] = fn.pos[1] + pdy;
                    draggedNodeIds.push(_s._dragNodeId);
                    var fel = document.getElementById('nd-' + _s._dragNodeId);
                    if (fel) {
                        fel.style.left = fn.pos[0] + 'px';
                        fel.style.top = fn.pos[1] + 'px';
                        fel.style.opacity = '';
                    }
                }
            }
            for (var dai = 0; dai < _s._dragNearbyAnnotations.length; dai++) {
                var dna = _s._dragNearbyAnnotations[dai];
                dna.an.pos[0] = dna.startX + pdx;
                dna.an.pos[1] = dna.startY + pdy;
                if (dna.an._domEl) {
                    dna.an._domEl.style.left = dna.an.pos[0] + 'px';
                    dna.an._domEl.style.top = dna.an.pos[1] + 'px';
                }
            }
            _s._dragGhostEl.remove();
            _s._dragGhostEl = null;
            _s._dragGhostStartLocal = null;
            _s._dragNearbyAnnotations = [];
        } else {
            if (_s._dragIsMultiSelect && _s._dragStartPositions && (_s._dragPendingDx !== 0 || _s._dragPendingDy !== 0)) {
                for (var mfid in _s._dragStartPositions) {
                    if (!_s._dragStartPositions.hasOwnProperty(mfid)) continue;
                    var mfn = _s._nodes[mfid];
                    if (!mfn) continue;
                    mfn.pos[0] = _s._dragStartPositions[mfid].x + _s._dragPendingDx;
                    mfn.pos[1] = _s._dragStartPositions[mfid].y + _s._dragPendingDy;
                    var mfel = document.getElementById('nd-' + mfid);
                    if (mfel) {
                        mfel.style.left = mfn.pos[0] + 'px';
                        mfel.style.top = mfn.pos[1] + 'px';
                    }
                }
            }
            for (var eai = 0; eai < _s._dragNearbyAnnotations.length; eai++) {
                var edna = _s._dragNearbyAnnotations[eai];
                edna.an.pos[0] = edna.startX + _s._dragPendingDx;
                edna.an.pos[1] = edna.startY + _s._dragPendingDy;
                if (edna.an._domEl) {
                    edna.an._domEl.style.left = edna.an.pos[0] + 'px';
                    edna.an._domEl.style.top = edna.an.pos[1] + 'px';
                }
            }
            var el = document.getElementById('nd-' + _s._dragNodeId);
            if (el) {
                el.classList.remove('drag');
                el.style.opacity = '';
            }
        }

        if (_s._connSvgEl) _s._connSvgEl.style.opacity = '';

        var node = _s._nodes[_s._dragNodeId];
        if (node && node._domEl) {
            node.size = [node._domEl.offsetWidth || 220, node._domEl.offsetHeight || 100];
        }
        _s._isDraggingNode = false;
        _s._dragNodeId = null;
        _s._dragStartPositions = {};
        _s._dragIsMultiSelect = false;
        _s._dragPendingDx = 0;
        _s._dragPendingDy = 0;
        _s._dragNearbyAnnotations = [];
        _renderAllConnections();
        _updateMinimap();
        if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
    }

    if (_s._isConnecting) {
        var portEl = e.target.closest('.pt');
        if (portEl) {
            var toNodeId = parseInt(portEl.dataset.n);
            var toPortKey = portEl.dataset.p;
            var toDir = portEl.dataset.d;

            if (toNodeId !== _s._connFromNodeId && toDir !== _s._connFromDir) {
                var fromNode = _s._nodes[_s._connFromNodeId];
                var toNode = _s._nodes[toNodeId];
                if (fromNode && toNode) {
                    var fromSlot = -1, toSlot = -1;
                    if (_s._connFromDir === 'o') {
                        for (var i = 0; i < fromNode.outputs.length; i++) {
                            if (fromNode.outputs[i]._portKey === _s._connFromPortKey) { fromSlot = i; break; }
                        }
                        for (var i = 0; i < toNode.inputs.length; i++) {
                            if (toNode.inputs[i]._portKey === toPortKey) { toSlot = i; break; }
                        }
                    } else {
                        for (var i = 0; i < fromNode.inputs.length; i++) {
                            if (fromNode.inputs[i]._portKey === _s._connFromPortKey) { fromSlot = i; break; }
                        }
                        for (var i = 0; i < toNode.outputs.length; i++) {
                            if (toNode.outputs[i]._portKey === toPortKey) { toSlot = i; break; }
                        }
                        var tmpNode = fromNode; fromNode = toNode; toNode = tmpNode;
                        var tmpSlot = fromSlot; fromSlot = toSlot; toSlot = tmpSlot;
                    }
                    if (fromSlot >= 0 && toSlot >= 0) {
                        var fromPortDef = fromNode.outputs[fromSlot];
                        var toPortDef = toNode.inputs[toSlot];
                        var fromType = fromPortDef.type || 'any';
                        var toType = toPortDef.type || 'any';
                        if (fromType !== toType && fromType !== 'any' && toType !== 'any') {
                            if (window.AutomationApp && window.AutomationApp.showToast) {
                                window.AutomationApp.showToast('端口类型不匹配: ' + _toZh(fromType) + ' != ' + _toZh(toType), 'warn');
                            }
                        } else {
                            _addConnection(fromNode.id, fromSlot, toNode.id, toSlot);
                        }
                    }
                }
            }
        }
        if (_s._tmpPathEl) { _s._tmpPathEl.remove(); _s._tmpPathEl = null; }
        _s._isConnecting = false;
        _s._connFromNodeId = null;
        _s._connFromPortKey = null;
        _s._connFromDir = null;
        _s._connFromPortType = null;
    }
}

function _onCanvasWheel(e) {
    e.preventDefault();
    var r = _s._canvasArea.getBoundingClientRect();
    var mx = e.clientX - r.left;
    var my = e.clientY - r.top;
    var factor = e.deltaY > 0 ? 0.92 : 1.08;
    _setZoom(_s._vpScale * factor, mx, my);
    try { window._autoEditor.updateStatusBar(); } catch(e) {}
}

function _onCanvasDblClick(e) {
    var nodeEl = e.target.closest('.nd');
    if (!nodeEl) return;
    var nid = parseInt(nodeEl.dataset.id);
    var node = _s._nodes[nid];
    if (!node) return;
    if (node._defKey && node._defKey.indexOf('call_script') >= 0) {
        if (window.AutomationBlockEditor) {
            window.AutomationBlockEditor.open(node);
        }
    }
}

export {
    _startAutoPan,
    _stopAutoPan,
    _onCanvasMouseDown,
    _onCanvasMouseMove,
    _onCanvasMouseUp,
    _onCanvasWheel,
    _onCanvasDblClick,
    _checkLineDeleteAtPoint,
    _updateSelectionFromBox
};
