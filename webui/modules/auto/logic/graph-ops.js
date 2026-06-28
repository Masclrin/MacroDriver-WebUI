'use strict';

import { _s } from '../core/state.js';
import { _getGlobalNotify } from '../core/notify.js';
import { _addNodeToDOM, _removeNodeFromDOM, _refreshNodeDOM, _createNodeData } from '../render/node-renderer.js';
import { _removeConnectionsForNode, _addConnection, _removeConnectionsForPort, _renderAllConnections, _removeConnectionById } from '../render/connection-renderer.js';

function _addNode(node) {
    _s._nodes[node.id] = node;
    _s._nodeList.push(node);
    _addNodeToDOM(node);
    if (_s._onNodeAdded) _s._onNodeAdded(node);
    var nf = _getGlobalNotify();
    if (nf) nf();
}

function _removeNodeById(nodeId) {
    var node = _s._nodes[nodeId];
    if (!node) return;
    _removeConnectionsForNode(nodeId);
    _removeNodeFromDOM(nodeId);
    delete _s._nodes[nodeId];
    var idx = _s._nodeList.indexOf(node);
    if (idx >= 0) _s._nodeList.splice(idx, 1);
    var nf2 = _getGlobalNotify();
    if (nf2) nf2();
    var selIdx = _s._selectedNodes.indexOf(node);
    if (selIdx >= 0) _s._selectedNodes.splice(selIdx, 1);
    if (_s._selectedNodeId === nodeId) {
        _s._selectedNodeId = null;
        if (_s._onNodeDeselected) _s._onNodeDeselected(node);
    }
    if (_s._onNodeRemoved) _s._onNodeRemoved(node);
}

function _selectNodeById(nodeId) {
    if (_s._selectedNodeId === nodeId) return;
    if (_s._selectedNodeId !== null) {
        var prevEl = document.getElementById('nd-' + _s._selectedNodeId);
        if (prevEl) prevEl.classList.remove('sel');
        var prevNode = _s._nodes[_s._selectedNodeId];
        if (prevNode) prevNode.selected = false;
        if (_s._onNodeDeselected && prevNode) _s._onNodeDeselected(prevNode);
    }
    if (_s._selectedAnnotationId !== null) {
        var prevAnEl = document.getElementById('an-' + _s._selectedAnnotationId);
        if (prevAnEl) prevAnEl.classList.remove('sel');
        _s._selectedAnnotationId = null;
    }
    if (_s._selectedGroupId !== null) {
        var prevGpEl = document.getElementById('gp-' + _s._selectedGroupId);
        if (prevGpEl) prevGpEl.classList.remove('sel');
        _s._selectedGroupId = null;
    }
    _s._selectedNodeId = nodeId;
    if (nodeId !== null) {
        var el = document.getElementById('nd-' + nodeId);
        if (el) el.classList.add('sel');
        var node = _s._nodes[nodeId];
        if (node) node.selected = true;
        if (_s._onNodeSelected) _s._onNodeSelected(node);
    }
}

function _getAnnotationsNearNodes(nodeIds, threshold) {
    threshold = threshold || 30;
    var result = [];
    for (var ai = 0; ai < _s._annotations.length; ai++) {
        var an = _s._annotations[ai];
        var anW = an._domEl ? an._domEl.offsetWidth : 120;
        var anH = an._domEl ? an._domEl.offsetHeight : 40;
        var anCX = an.pos[0] + anW / 2;
        var anCY = an.pos[1] + anH / 2;
        for (var ni = 0; ni < nodeIds.length; ni++) {
            var node = _s._nodes[nodeIds[ni]];
            if (!node) continue;
            var nodeW = node.size ? node.size[0] : 180;
            var nodeH = node.size ? node.size[1] : 80;
            var nodeLeft = node.pos[0] - threshold;
            var nodeRight = node.pos[0] + nodeW + threshold;
            var nodeTop = node.pos[1] - threshold;
            var nodeBottom = node.pos[1] + nodeH + threshold;
            if (anCX >= nodeLeft && anCX <= nodeRight && anCY >= nodeTop && anCY <= nodeBottom) {
                result.push(an);
                break;
            }
        }
    }
    return result;
}

function _deselectAll() {
    for (var i = 0; i < _s._selectedNodes.length; i++) {
        var el = _s._selectedNodes[i]._domEl || document.getElementById('nd-' + _s._selectedNodes[i].id);
        if (el) el.classList.remove('sel');
    }
    _s._selectedNodes = [];
    for (var ai = 0; ai < _s._selectedAnnotations.length; ai++) {
        var ael = _s._selectedAnnotations[ai]._domEl || document.getElementById('an-' + _s._selectedAnnotations[ai].id);
        if (ael) ael.classList.remove('sel');
    }
    _s._selectedAnnotations = [];
    _s._selectedAnnotationId = null;
    for (var gi = 0; gi < _s._selectedGroups.length; gi++) {
        var gel = _s._selectedGroups[gi]._domEl || document.getElementById('gp-' + _s._selectedGroups[gi].id);
        if (gel) gel.classList.remove('sel');
    }
    _s._selectedGroups = [];
    _s._selectedGroupId = null;
    if (_s._selectedNodeId !== null) {
        var prevEl = document.getElementById('nd-' + _s._selectedNodeId);
        if (prevEl) prevEl.classList.remove('sel');
        _s._selectedNodeId = null;
    }
}

function _updateBranchPorts(node, newCount) {
    var def = window.AutomationNodes ? window.AutomationNodes.getNodeDef(node.type) : null;
    if (!def || !def.dynamic_branches) return;

    var _toZh2 = null;
    _toZh2 = function(name, portDef) {
        if (portDef && portDef.display_name) return portDef.display_name;
        var map = { branch1: '分支1', branch2: '分支2', branch3: '分支3', branch4: '分支4',
            branch5: '分支5', branch6: '分支6', branch7: '分支7', branch8: '分支8' };
        return map[name] || name;
    };

    var isJoin = node.type === 'control/join';
    var oldCount = node.properties.branch_count || 2;
    newCount = Math.max(2, Math.min(8, newCount));
    node.properties.branch_count = newCount;

    if (isJoin) {
        while (node.inputs.length < newCount) {
            var idx = node.inputs.length + 1;
            node.inputs.push({
                name: _toZh2('branch' + idx),
                type: 'flow',
                _portKey: 'branch' + idx
            });
        }
        while (node.inputs.length > newCount) {
            var removeIdx = node.inputs.length - 1;
            _removeConnectionsForPort(node.id, removeIdx, 'i');
            node.inputs.pop();
        }
    } else {
        var staticOutputCount = 0;
        for (var k = 0; k < node.outputs.length; k++) {
            if (node.outputs[k]._portKey && node.outputs[k]._portKey.indexOf('branch') !== 0) {
                staticOutputCount++;
            }
        }
        var currentBranchCount = node.outputs.length - staticOutputCount;
        while (currentBranchCount < newCount) {
            var idx = currentBranchCount + 1;
            node.outputs.push({
                name: _toZh2('branch' + idx),
                type: 'flow',
                _portKey: 'branch' + idx
            });
            currentBranchCount++;
        }
        while (currentBranchCount > newCount) {
            var removeIdx = node.outputs.length - 1;
            _removeConnectionsForPort(node.id, removeIdx, 'o');
            node.outputs.pop();
            currentBranchCount--;
        }
    }

    _refreshNodeDOM(node);
    _renderAllConnections();
    var nf3 = _getGlobalNotify();
    if (nf3) nf3();
}

export {
    _addNode,
    _removeNodeById,
    _selectNodeById,
    _getAnnotationsNearNodes,
    _deselectAll,
    _updateBranchPorts
};
