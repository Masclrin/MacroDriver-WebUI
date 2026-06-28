'use strict';

import { _groupPresetColors } from '../core/constants.js';
import { _s } from '../core/state.js';
import { _renderAllConnections } from './connection-renderer.js';

var _coreRef = null;

function _setCoreRef(ref) {
    _coreRef = ref;
}

function _getNodesInGroup(gp) {
    var result = [];
    var gpLeft = gp.pos[0];
    var gpTop = gp.pos[1];
    var gpRight = gpLeft + gp.size[0];
    var gpBottom = gpTop + gp.size[1];
    for (var nid in _s._nodes) {
        if (!_s._nodes.hasOwnProperty(nid)) continue;
        var node = _s._nodes[nid];
        var nodeW = node.size ? node.size[0] : 180;
        var nodeH = node.size ? node.size[1] : 80;
        var nodeCX = node.pos[0] + nodeW / 2;
        var nodeCY = node.pos[1] + nodeH / 2;
        if (nodeCX >= gpLeft && nodeCX <= gpRight && nodeCY >= gpTop && nodeCY <= gpBottom) {
            result.push(node);
        }
    }
    return result;
}

function _getAnnotationsInGroup(gp) {
    var result = [];
    var gpLeft = gp.pos[0];
    var gpTop = gp.pos[1];
    var gpRight = gpLeft + gp.size[0];
    var gpBottom = gpTop + gp.size[1];
    for (var ai = 0; ai < _s._annotations.length; ai++) {
        var an = _s._annotations[ai];
        var anW = an._domEl ? an._domEl.offsetWidth : 120;
        var anH = an._domEl ? an._domEl.offsetHeight : 40;
        var anCX = an.pos[0] + anW / 2;
        var anCY = an.pos[1] + anH / 2;
        if (anCX >= gpLeft && anCX <= gpRight && anCY >= gpTop && anCY <= gpBottom) {
            result.push(an);
        }
    }
    return result;
}

function _renderGroup(gp) {
    if (!_s._groupLayerEl) return;
    var existing = document.getElementById('gp-' + gp.id);
    if (existing) existing.remove();
    var el = document.createElement('div');
    el.id = 'gp-' + gp.id;
    el.className = 'gp';
    el.style.left = gp.pos[0] + 'px';
    el.style.top = gp.pos[1] + 'px';
    el.style.width = gp.size[0] + 'px';
    el.style.height = gp.size[1] + 'px';
    el.style.setProperty('--gp-color', gp.color);
    var bgStyle = gp.bgColor || 'rgba(59,130,246,.08)';
    el.style.setProperty('--gp-bg', bgStyle);
    el.style.background = bgStyle;

    var hEl = document.createElement('div');
    hEl.className = 'gp-h';

    var tEl = document.createElement('span');
    tEl.className = 'gp-t';
    tEl.textContent = gp.title;
    hEl.appendChild(tEl);

    var colorMenuEl = document.createElement('div');
    colorMenuEl.className = 'gp-color-menu';
    for (var ci = 0; ci < _groupPresetColors.length; ci++) {
        (function(preset) {
            var btn = document.createElement('div');
            btn.className = 'gp-color-btn';
            btn.style.background = preset.color;
            btn.title = preset.name;
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                gp.color = preset.color;
                gp.bgColor = preset.bg;
                el.style.setProperty('--gp-color', preset.color);
                el.style.setProperty('--gp-bg', preset.bg);
                el.style.background = preset.bg;
                colorMenuEl.classList.remove('show');
                if (_coreRef) _coreRef._notifyGraphChange();
                if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
            });
            colorMenuEl.appendChild(btn);
        })(_groupPresetColors[ci]);
    }
    el.appendChild(colorMenuEl);

    var rszEl = document.createElement('div');
    rszEl.className = 'gp-rsz';

    el.appendChild(hEl);
    el.appendChild(rszEl);

    tEl.addEventListener('dblclick', function(e) {
        e.stopPropagation();
        e.preventDefault();
        tEl.contentEditable = 'true';
        tEl.focus();
        var range = document.createRange();
        range.selectNodeContents(tEl);
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
    });
    tEl.addEventListener('blur', function() {
        tEl.contentEditable = 'false';
        gp.title = tEl.textContent || '';
        if (_coreRef) _coreRef._notifyGraphChange();
        if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
    });
    tEl.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') { e.preventDefault(); tEl.blur(); }
        if (e.key === 'Escape') { tEl.textContent = gp.title; tEl.blur(); }
    });
    tEl.addEventListener('mousedown', function(e) {
        if (tEl.contentEditable === 'true') {
            e.stopPropagation();
        }
    });
    hEl.addEventListener('mousedown', function(e) {
        if (e.target === tEl && tEl.contentEditable === 'true') return;
        e.stopPropagation();
        if (e.button === 0) {
            var gpIsMulti = e.ctrlKey || e.metaKey;
            if (gpIsMulti) {
                var gpAlreadySel = false;
                for (var gsi = 0; gsi < _s._selectedGroups.length; gsi++) {
                    if (_s._selectedGroups[gsi].id === gp.id) { gpAlreadySel = true; break; }
                }
                if (gpAlreadySel) {
                    _s._selectedGroups = _s._selectedGroups.filter(function(g) { return g.id !== gp.id; });
                    el.classList.remove('sel');
                    if (_s._selectedGroups.length === 0) _s._selectedGroupId = null;
                } else {
                    _s._selectedGroups.push(gp);
                    el.classList.add('sel');
                    _s._selectedGroupId = gp.id;
                }
                if (_s._selectedGroups.length > 0 && window.AutomationProperty) {
                    AutomationProperty.renderGroup(_s._selectedGroups[_s._selectedGroups.length - 1]);
                }
            } else {
                for (var gci = 0; gci < _s._selectedGroups.length; gci++) {
                    var gcel = _s._selectedGroups[gci]._domEl || document.getElementById('gp-' + _s._selectedGroups[gci].id);
                    if (gcel) gcel.classList.remove('sel');
                }
                _s._selectedGroups = [];
                for (var sni = 0; sni < _s._selectedNodes.length; sni++) {
                    var snel = _s._selectedNodes[sni]._domEl || document.getElementById('nd-' + _s._selectedNodes[sni].id);
                    if (snel) snel.classList.remove('sel');
                }
                _s._selectedNodes = [];
                for (var aci = 0; aci < _s._selectedAnnotations.length; aci++) {
                    var ael2 = _s._selectedAnnotations[aci]._domEl || document.getElementById('an-' + _s._selectedAnnotations[aci].id);
                    if (ael2) ael2.classList.remove('sel');
                }
                _s._selectedAnnotations = [];
                var prevGpEl = document.getElementById('gp-' + _s._selectedGroupId);
                if (prevGpEl) prevGpEl.classList.remove('sel');
                _s._selectedGroupId = gp.id;
                el.classList.add('sel');
                var prevNodeEl = document.getElementById('nd-' + _s._selectedNodeId);
                if (prevNodeEl) prevNodeEl.classList.remove('sel');
                _s._selectedNodeId = null;
                var prevAnEl = document.getElementById('an-' + _s._selectedAnnotationId);
                if (prevAnEl) prevAnEl.classList.remove('sel');
                _s._selectedAnnotationId = null;
                if (window.AutomationProperty) {
                    AutomationProperty.renderGroup(gp);
                }
            }
            var startX = e.clientX, startY = e.clientY;
            var startLeft = gp.pos[0], startTop = gp.pos[1];
            var nodesInGroup = _getNodesInGroup(gp);
            var nodeStartPositions = [];
            for (var ni = 0; ni < nodesInGroup.length; ni++) {
                nodeStartPositions.push({
                    node: nodesInGroup[ni],
                    x: nodesInGroup[ni].pos[0],
                    y: nodesInGroup[ni].pos[1]
                });
            }
            var annotationsInGroup = _getAnnotationsInGroup(gp);
            var annotationStartPositions = [];
            for (var ai = 0; ai < annotationsInGroup.length; ai++) {
                annotationStartPositions.push({
                    an: annotationsInGroup[ai],
                    x: annotationsInGroup[ai].pos[0],
                    y: annotationsInGroup[ai].pos[1]
                });
            }
            function onMove(ev) {
                var dx = (ev.clientX - startX) / _s._vpScale;
                var dy = (ev.clientY - startY) / _s._vpScale;
                gp.pos[0] = startLeft + dx;
                gp.pos[1] = startTop + dy;
                el.style.left = gp.pos[0] + 'px';
                el.style.top = gp.pos[1] + 'px';
                for (var i = 0; i < nodeStartPositions.length; i++) {
                    var item = nodeStartPositions[i];
                    item.node.pos[0] = item.x + dx;
                    item.node.pos[1] = item.y + dy;
                    if (item.node._domEl) {
                        item.node._domEl.style.left = item.node.pos[0] + 'px';
                        item.node._domEl.style.top = item.node.pos[1] + 'px';
                    }
                }
                for (var j = 0; j < annotationStartPositions.length; j++) {
                    var anItem = annotationStartPositions[j];
                    anItem.an.pos[0] = anItem.x + dx;
                    anItem.an.pos[1] = anItem.y + dy;
                    if (anItem.an._domEl) {
                        anItem.an._domEl.style.left = anItem.an.pos[0] + 'px';
                        anItem.an._domEl.style.top = anItem.an.pos[1] + 'px';
                    }
                }
                _renderAllConnections();
            }
            function onUp() {
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
                if (_coreRef) _coreRef._notifyGraphChange();
                if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
            }
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        }
    });
    hEl.addEventListener('contextmenu', function(e) {
        e.preventDefault();
        e.stopPropagation();
        var colorSubItems = [];
        for (var ci = 0; ci < _groupPresetColors.length; ci++) {
            (function(preset) {
                colorSubItems.push({
                    label: preset.name,
                    icon: 'fa-solid fa-circle',
                    iconColor: preset.color,
                    action: function() {
                        gp.color = preset.color;
                        gp.bgColor = preset.bg;
                        el.style.setProperty('--gp-color', preset.color);
                        el.style.setProperty('--gp-bg', preset.bg);
                        el.style.background = preset.bg;
                        if (_coreRef) _coreRef._notifyGraphChange();
                        if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
                    }
                });
            })(_groupPresetColors[ci]);
        }
        var menuItems = [
            { label: '更改颜色', icon: 'fa-solid fa-palette', submenu: { items: colorSubItems } },
            { label: '分隔线', divider: true },
            { label: '复制分组', icon: 'fa-solid fa-copy', action: 'copy_group' },
            { label: '重复分组', icon: 'fa-solid fa-clone', action: 'duplicate_group' },
            { label: '分隔线', divider: true },
            { label: '删除分组(保留内容)', icon: 'fa-solid fa-trash-can', action: 'delete_group' }
        ];
        if (window.AutomationApp && AutomationApp.showContextMenu) {
            window.AutomationApp._setContextTarget(null);
            window.AutomationApp._setGroupContext(gp);
            AutomationApp.showContextMenu(e.clientX, e.clientY, menuItems);
        }
    });
    rszEl.addEventListener('mousedown', function(e) {
        e.stopPropagation();
        if (e.button !== 0) return;
        var startX2 = e.clientX, startY2 = e.clientY;
        var startW = gp.size[0], startH = gp.size[1];
        function onMove2(ev) {
            var dw = (ev.clientX - startX2) / _s._vpScale;
            var dh = (ev.clientY - startY2) / _s._vpScale;
            gp.size[0] = Math.max(140, startW + dw);
            gp.size[1] = Math.max(100, startH + dh);
            el.style.width = gp.size[0] + 'px';
            el.style.height = gp.size[1] + 'px';
        }
        function onUp2() {
            document.removeEventListener('mousemove', onMove2);
            document.removeEventListener('mouseup', onUp2);
            if (_coreRef) _coreRef._notifyGraphChange();
            if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
        }
        document.addEventListener('mousemove', onMove2);
        document.addEventListener('mouseup', onUp2);
    });
    _s._groupLayerEl.appendChild(el);
    gp._domEl = el;
}

export { _renderGroup, _setCoreRef, _getNodesInGroup, _getAnnotationsInGroup };
