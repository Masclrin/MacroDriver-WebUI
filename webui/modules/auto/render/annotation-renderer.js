'use strict';

import { _annotationPresetColors } from '../core/constants.js';
import { _s } from '../core/state.js';

var _coreRef = null;

function _setCoreRef(ref) {
    _coreRef = ref;
}

function _renderAnnotation(an) {
    if (!_s._annotationLayerEl) return;
    var existing = document.getElementById('an-' + an.id);
    if (existing) existing.remove();
    var el = document.createElement('div');
    el.id = 'an-' + an.id;
    el.className = 'an' + (an.collapsed ? ' collapsed' : '');
    el.style.left = an.pos[0] + 'px';
    el.style.top = an.pos[1] + 'px';
    var bgStyle = an.bgColor || 'linear-gradient(135deg,rgba(251,191,36,.72),rgba(251,191,36,.58))';
    el.style.background = bgStyle;

    var txtEl = document.createElement('div');
    txtEl.className = 'an-t';
    txtEl.contentEditable = 'false';
    txtEl.textContent = an.text;
    el.appendChild(txtEl);

    var toggleEl = document.createElement('div');
    toggleEl.className = 'an-toggle';
    toggleEl.innerHTML = an.collapsed ? '<i class="fa-solid fa-expand"></i>' : '<i class="fa-solid fa-compress"></i>';
    toggleEl.title = an.collapsed ? '展开' : '折叠';
    el.appendChild(toggleEl);

    toggleEl.addEventListener('click', function(e) {
        e.stopPropagation();
        an.collapsed = !an.collapsed;
        el.classList.toggle('collapsed', an.collapsed);
        toggleEl.innerHTML = an.collapsed ? '<i class="fa-solid fa-expand"></i>' : '<i class="fa-solid fa-compress"></i>';
        toggleEl.title = an.collapsed ? '展开' : '折叠';
        if (_coreRef) _coreRef._notifyGraphChange();
        if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
    });

    txtEl.addEventListener('dblclick', function(e) {
        e.stopPropagation();
        e.preventDefault();
        if (an.collapsed) {
            an.collapsed = false;
            el.classList.remove('collapsed');
            toggleEl.innerHTML = '<i class="fa-solid fa-compress"></i>';
            toggleEl.title = '折叠';
        }
        txtEl.contentEditable = 'true';
        txtEl.focus();
        var range = document.createRange();
        range.selectNodeContents(txtEl);
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
    });
    txtEl.addEventListener('blur', function() {
        txtEl.contentEditable = 'false';
        an.text = txtEl.textContent || '';
        if (_coreRef) _coreRef._notifyGraphChange();
        if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
    });
    txtEl.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            txtEl.blur();
        }
        if (e.key === 'Escape') {
            txtEl.textContent = an.text;
            txtEl.blur();
        }
    });
    txtEl.addEventListener('mousedown', function(e) {
        if (txtEl.contentEditable === 'true') {
            e.stopPropagation();
        }
    });
    el.addEventListener('mousedown', function(e) {
        if (e.target === txtEl && txtEl.contentEditable === 'true') return;
        if (e.target === toggleEl || toggleEl.contains(e.target)) return;
        e.stopPropagation();
        if (e.button === 0) {
            var isMulti = e.ctrlKey || e.metaKey;
            if (isMulti) {
                var alreadySel = false;
                for (var si = 0; si < _s._selectedAnnotations.length; si++) {
                    if (_s._selectedAnnotations[si].id === an.id) { alreadySel = true; break; }
                }
                if (alreadySel) {
                    _s._selectedAnnotations = _s._selectedAnnotations.filter(function(a) { return a.id !== an.id; });
                    el.classList.remove('sel');
                    if (_s._selectedAnnotations.length === 0) _s._selectedAnnotationId = null;
                } else {
                    _s._selectedAnnotations.push(an);
                    el.classList.add('sel');
                    _s._selectedAnnotationId = an.id;
                }
                if (_s._selectedAnnotations.length > 0 && window.AutomationProperty) {
                    AutomationProperty.renderAnnotation(_s._selectedAnnotations[_s._selectedAnnotations.length - 1]);
                }
            } else {
                for (var ci2 = 0; ci2 < _s._selectedAnnotations.length; ci2++) {
                    var cel = _s._selectedAnnotations[ci2]._domEl || document.getElementById('an-' + _s._selectedAnnotations[ci2].id);
                    if (cel) cel.classList.remove('sel');
                }
                _s._selectedAnnotations = [];
                for (var sni = 0; sni < _s._selectedNodes.length; sni++) {
                    var snel = _s._selectedNodes[sni]._domEl || document.getElementById('nd-' + _s._selectedNodes[sni].id);
                    if (snel) snel.classList.remove('sel');
                }
                _s._selectedNodes = [];
                for (var cgi = 0; cgi < _s._selectedGroups.length; cgi++) {
                    var cgel = _s._selectedGroups[cgi]._domEl || document.getElementById('gp-' + _s._selectedGroups[cgi].id);
                    if (cgel) cgel.classList.remove('sel');
                }
                _s._selectedGroups = [];
                var prevAnEl = document.getElementById('an-' + _s._selectedAnnotationId);
                if (prevAnEl) prevAnEl.classList.remove('sel');
                _s._selectedAnnotationId = an.id;
                el.classList.add('sel');
                var prevNodeEl = document.getElementById('nd-' + _s._selectedNodeId);
                if (prevNodeEl) prevNodeEl.classList.remove('sel');
                _s._selectedNodeId = null;
                var prevGpEl = document.getElementById('gp-' + _s._selectedGroupId);
                if (prevGpEl) prevGpEl.classList.remove('sel');
                _s._selectedGroupId = null;
                if (window.AutomationProperty) {
                    AutomationProperty.renderAnnotation(an);
                }
            }
            var startX = e.clientX, startY = e.clientY;
            var startLeft = an.pos[0], startTop = an.pos[1];
            var multiSelStarts = [];
            for (var msi = 0; msi < _s._selectedAnnotations.length; msi++) {
                var msa = _s._selectedAnnotations[msi];
                if (msa.id !== an.id) {
                    multiSelStarts.push({ an: msa, sx: msa.pos[0], sy: msa.pos[1] });
                }
            }
            function onMove(ev) {
                var dx = (ev.clientX - startX) / _s._vpScale;
                var dy = (ev.clientY - startY) / _s._vpScale;
                var newX = startLeft + dx;
                var newY = startTop + dy;
                var snapDist = 8 / _s._vpScale;
                var anW = el.offsetWidth || 120;
                var anH = el.offsetHeight || 40;
                for (var nid in _s._nodes) {
                    if (!_s._nodes.hasOwnProperty(nid)) continue;
                    var node = _s._nodes[nid];
                    var nodeW = node.size ? node.size[0] : 180;
                    var nodeH = node.size ? node.size[1] : 80;
                    if (Math.abs(newX - (node.pos[0] + nodeW)) < snapDist) { newX = node.pos[0] + nodeW; }
                    if (Math.abs(newX + anW - node.pos[0]) < snapDist) { newX = node.pos[0] - anW; }
                    if (Math.abs(newY - (node.pos[1] + nodeH)) < snapDist) { newY = node.pos[1] + nodeH; }
                    if (Math.abs(newY + anH - node.pos[1]) < snapDist) { newY = node.pos[1] - anH; }
                }
                for (var gi = 0; gi < _s._groups.length; gi++) {
                    var gp = _s._groups[gi];
                    if (Math.abs(newX - (gp.pos[0] + gp.size[0])) < snapDist) { newX = gp.pos[0] + gp.size[0]; }
                    if (Math.abs(newX + anW - gp.pos[0]) < snapDist) { newX = gp.pos[0] - anW; }
                    if (Math.abs(newY - (gp.pos[1] + gp.size[1])) < snapDist) { newY = gp.pos[1] + gp.size[1]; }
                    if (Math.abs(newY + anH - gp.pos[1]) < snapDist) { newY = gp.pos[1] - anH; }
                }
                an.pos[0] = newX;
                an.pos[1] = newY;
                el.style.left = an.pos[0] + 'px';
                el.style.top = an.pos[1] + 'px';
                var actualDx = newX - startLeft;
                var actualDy = newY - startTop;
                for (var mvi = 0; mvi < multiSelStarts.length; mvi++) {
                    var mviItem = multiSelStarts[mvi];
                    mviItem.an.pos[0] = mviItem.sx + actualDx;
                    mviItem.an.pos[1] = mviItem.sy + actualDy;
                    if (mviItem.an._domEl) {
                        mviItem.an._domEl.style.left = mviItem.an.pos[0] + 'px';
                        mviItem.an._domEl.style.top = mviItem.an.pos[1] + 'px';
                    }
                }
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
    el.addEventListener('contextmenu', function(e) {
        e.preventDefault();
        e.stopPropagation();
        var colorSubItems = [];
        for (var ci = 0; ci < _annotationPresetColors.length; ci++) {
            (function(preset) {
                colorSubItems.push({
                    label: preset.name,
                    icon: 'fa-solid fa-circle',
                    iconColor: preset.color,
                    action: function() {
                        an.color = preset.color;
                        an.bgColor = preset.bg;
                        el.style.background = preset.bg;
                        if (_coreRef) _coreRef._notifyGraphChange();
                        if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
                    }
                });
            })(_annotationPresetColors[ci]);
        }
        var menuItems = [
            { label: '更改颜色', icon: 'fa-solid fa-palette', submenu: { items: colorSubItems } },
            { label: '分隔线', divider: true },
            { label: '复制注释', icon: 'fa-solid fa-copy', action: 'copy_annotation' },
            { label: '重复注释', icon: 'fa-solid fa-clone', action: 'duplicate_annotation' },
            { label: '分隔线', divider: true },
            { label: '删除注释', icon: 'fa-solid fa-trash-can', action: 'delete_annotation' }
        ];
        if (window.AutomationApp && AutomationApp.showContextMenu) {
            window.AutomationApp._setContextTarget(null);
            window.AutomationApp._setAnnotationContext(an);
            AutomationApp.showContextMenu(e.clientX, e.clientY, menuItems);
        }
    });
    _s._annotationLayerEl.appendChild(el);
    an._domEl = el;
}

export { _renderAnnotation, _setCoreRef };
