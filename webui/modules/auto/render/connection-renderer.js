'use strict';

import { _bezier, _getPortCenter } from '../core/utils.js';
import { _portTypeColors } from '../core/constants.js';
import { _s } from '../core/state.js';
import { _refreshNodeDOM } from './node-renderer.js';
import { _getGlobalNotify } from '../core/notify.js';

function _renderAllConnections() {
    if (!_s._connSvgEl) return;
    _s._connSvgEl.innerHTML = '';
    for (var i = 0; i < _s._connections.length; i++) {
        _renderConnection(_s._connections[i]);
    }
}

function _renderConnection(conn) {
    if (!_s._connSvgEl) return;
    var fromNode = _s._nodes[conn.origin_id];
    var toNode = _s._nodes[conn.target_id];
    if (!fromNode || !toNode) return;

    var fromPort = fromNode.outputs[conn.origin_slot];
    var toPort = toNode.inputs[conn.target_slot];
    if (!fromPort || !toPort) return;

    var fe = _getPortCenter(conn.origin_id, fromPort._portKey, 'o');
    var te = _getPortCenter(conn.target_id, toPort._portKey, 'i');
    if (!fe || !te) return;

    var g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('data-link-id', String(conn.id));
    g.style.cursor = 'pointer';

    var hitPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    hitPath.setAttribute('d', _bezier(fe.x, fe.y, te.x, te.y));
    hitPath.setAttribute('stroke', 'transparent');
    hitPath.setAttribute('stroke-width', '14');
    hitPath.setAttribute('fill', 'none');
    g.appendChild(hitPath);

    var visPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    visPath.setAttribute('d', _bezier(fe.x, fe.y, te.x, te.y));
    visPath.setAttribute('stroke', _portTypeColors[fromPort.type] || '#94a3b8');
    visPath.setAttribute('stroke-width', '2.5');
    visPath.setAttribute('fill', 'none');
    visPath.style.transition = 'stroke-width .12s';
    g.appendChild(visPath);

    g.addEventListener('mouseenter', function() {
        visPath.setAttribute('stroke-width', '4');
    });
    g.addEventListener('mouseleave', function() {
        visPath.setAttribute('stroke-width', '2.5');
    });
    g.addEventListener('contextmenu', function(e) {
        e.preventDefault();
        e.stopPropagation();
        _removeConnectionById(conn.id);
    });
    g.addEventListener('dblclick', function(e) {
        e.preventDefault();
        e.stopPropagation();
        _removeConnectionById(conn.id);
    });

    _s._connSvgEl.appendChild(g);
}

function _updateAffectedConnections() {
    if (!_s._connSvgEl) return;
    var affectedIds = {};
    if (_s._dragIsMultiSelect) {
        for (var id in _s._dragStartPositions) {
            if (_s._dragStartPositions.hasOwnProperty(id)) affectedIds[id] = true;
        }
    } else if (_s._dragNodeId !== null) {
        affectedIds[_s._dragNodeId] = true;
    }
    if (Object.keys(affectedIds).length === 0) {
        _renderAllConnections();
        return;
    }
    var gs = _s._connSvgEl.children;
    for (var i = gs.length - 1; i >= 0; i--) {
        var g = gs[i];
        var linkId = g.getAttribute('data-link-id');
        if (!linkId) continue;
        var linkIdNum = parseInt(linkId);
        var conn = _s._linksSparse[linkIdNum];
        if (!conn) continue;
        if (!affectedIds[conn.origin_id] && !affectedIds[conn.target_id]) continue;
        var fromNode = _s._nodes[conn.origin_id];
        var toNode = _s._nodes[conn.target_id];
        if (!fromNode || !toNode) continue;
        var fromPort = fromNode.outputs[conn.origin_slot];
        var toPort = toNode.inputs[conn.target_slot];
        if (!fromPort || !toPort) continue;
        var fe = _getPortCenter(conn.origin_id, fromPort._portKey, 'o');
        var te = _getPortCenter(conn.target_id, toPort._portKey, 'i');
        if (!fe || !te) continue;
        var paths = g.querySelectorAll('path');
        var d = _bezier(fe.x, fe.y, te.x, te.y);
        for (var pi = 0; pi < paths.length; pi++) {
            paths[pi].setAttribute('d', d);
        }
    }
}

function _addConnection(fromNodeId, fromSlot, toNodeId, toSlot) {
    var fromNode = _s._nodes[fromNodeId];
    var toNode = _s._nodes[toNodeId];
    if (!fromNode || !toNode) return null;
    if (!fromNode.outputs[fromSlot] || !toNode.inputs[toSlot]) return null;

    var outPort = fromNode.outputs[fromSlot];
    var isFlowConn = outPort.type === 'flow';
    if (isFlowConn) {
        for (var i = _s._connections.length - 1; i >= 0; i--) {
            var c = _s._connections[i];
            if (c.target_id === toNodeId && c.target_slot === toSlot) {
                _removeConnectionById(c.id);
            }
        }
    } else {
        var dup = false;
        for (var i = 0; i < _s._connections.length; i++) {
            var c = _s._connections[i];
            if (c.origin_id === fromNodeId && c.origin_slot === fromSlot &&
                c.target_id === toNodeId && c.target_slot === toSlot) {
                dup = true;
                break;
            }
        }
        if (dup) return null;
    }

    var linkId = _s._nextLinkId++;
    var conn = {
        id: linkId,
        origin_id: fromNodeId,
        origin_slot: fromSlot,
        target_id: toNodeId,
        target_slot: toSlot,
        type: outPort.type === 'flow' ? 'flow' : 'data'
    };
    _s._connections.push(conn);
    _s._linksSparse[linkId] = conn;
    _renderConnection(conn);
    _refreshNodeDOM(fromNode);
    _refreshNodeDOM(toNode);
    if (_s._onConnectionChange) _s._onConnectionChange();
    var nf = _getGlobalNotify();
    if (nf) nf();
    return conn;
}

function _removeConnectionById(linkId) {
    var conn = _s._linksSparse[linkId];
    if (!conn) return;
    var fromNode = _s._nodes[conn.origin_id];
    var toNode = _s._nodes[conn.target_id];
    var pathEl = _s._connSvgEl ? _s._connSvgEl.querySelector('g[data-link-id="' + linkId + '"]') : null;
    if (pathEl) pathEl.remove();
    var idx = _s._connections.indexOf(conn);
    if (idx >= 0) _s._connections.splice(idx, 1);
    delete _s._linksSparse[linkId];
    if (fromNode) _refreshNodeDOM(fromNode);
    if (toNode) _refreshNodeDOM(toNode);
    if (_s._onConnectionChange) _s._onConnectionChange();
    var nf2 = _getGlobalNotify();
    if (nf2) nf2();
}

function _removeConnectionsForNode(nodeId) {
    var toRemove = [];
    for (var i = 0; i < _s._connections.length; i++) {
        if (_s._connections[i].origin_id === nodeId || _s._connections[i].target_id === nodeId) {
            toRemove.push(_s._connections[i].id);
        }
    }
    for (var j = 0; j < toRemove.length; j++) {
        _removeConnectionById(toRemove[j]);
    }
}

function _removeConnectionsForPort(nodeId, slotIndex, direction) {
    var toRemove = [];
    for (var i = 0; i < _s._connections.length; i++) {
        var c = _s._connections[i];
        if (direction === 'o' && c.origin_id === nodeId && c.origin_slot === slotIndex) {
            toRemove.push(c.id);
        } else if (direction === 'i' && c.target_id === nodeId && c.target_slot === slotIndex) {
            toRemove.push(c.id);
        }
    }
    for (var i = 0; i < toRemove.length; i++) {
        _removeConnectionById(toRemove[i]);
    }
}

export {
    _renderAllConnections,
    _renderConnection,
    _updateAffectedConnections,
    _addConnection,
    _removeConnectionById,
    _removeConnectionsForNode,
    _removeConnectionsForPort
};
