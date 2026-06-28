'use strict';

import { _escapeHtml, _pickSummaryKeys, _isConnected, _renderInlineField, _toZh } from '../core/utils.js';
import { _s } from '../core/state.js';

var _selectNodeById = null;

function _setSelectNodeByIdFn(fn) {
    _selectNodeById = fn;
}

function _renderNodeDOM(node) {
    var def = window.AutomationNodes ? AutomationNodes.getNodeDef(node._defKey) : null;
    var el = document.createElement('div');
    el.className = 'nd' + (node.id === _s._selectedNodeId ? ' sel' : '') + (node.properties._breakpoint ? ' has-breakpoint' : '');
    el.id = 'nd-' + node.id;
    el.dataset.c = node._category;
    el.dataset.id = String(node.id);
    el.dataset.type = node._defKey;
    el.style.left = node.pos[0] + 'px';
    el.style.top = node.pos[1] + 'px';

    var h = document.createElement('div');
    h.className = 'nd-h';
    h.innerHTML = '<div class="bp-dot"></div><i class="ni ' + node._iconClass + '" style="color:' + node._accentColor + '"></i>' +
        '<span class="nl">' + _escapeHtml(node._customName || (def ? def.display_name : node.type)) + '</span>' +
        '<div class="nx" data-action="delete"><i class="fa-solid fa-xmark"></i></div>';
    el.appendChild(h);

    var nlEl = h.querySelector('.nl');
    nlEl.addEventListener('dblclick', function(e) {
        e.stopPropagation();
        e.preventDefault();
        nlEl.contentEditable = 'true';
        nlEl.focus();
        var range = document.createRange();
        range.selectNodeContents(nlEl);
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
    });
    nlEl.addEventListener('blur', function() {
        nlEl.contentEditable = 'false';
        var newName = nlEl.textContent.trim();
        if (newName && newName !== (def ? def.display_name : node.type)) {
            node._customName = newName;
        } else {
            node._customName = null;
            nlEl.textContent = def ? def.display_name : node.type;
        }
        if (window.AutomationProperty && AutomationProperty._currentNode === node) {
            AutomationProperty.render(node);
        }
    });
    nlEl.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') { e.preventDefault(); nlEl.blur(); }
        if (e.key === 'Escape') {
            nlEl.textContent = node._customName || (def ? def.display_name : node.type);
            nlEl.blur();
        }
    });
    nlEl.addEventListener('mousedown', function(e) {
        if (nlEl.contentEditable === 'true') {
            e.stopPropagation();
        }
    });

    var b = document.createElement('div');
    b.className = 'nd-b nd-body-grid';

    var sKeys = (def && def.params_schema) ? _pickSummaryKeys(def.params_schema, node.properties) : [];

    var hasManyParams = sKeys.length > 2;
    var hasWideContent = false;
    for (var ski = 0; ski < sKeys.length; ski++) {
        var sk = sKeys[ski];
        var ss = def.params_schema[sk];
        if (ss.type === 'string' || ss.type === 'text' || ss.type === 'region') {
            hasWideContent = true; break;
        }
    }
    if (sKeys.length <= 2 && !hasWideContent && node.inputs.length <= 1 && node.outputs.length <= 1) {
        el.classList.add('nd-compact');
    }

    var paramStartRow = node.inputs.length;
    var totalRows = Math.max(node.inputs.length, node.outputs.length, paramStartRow + sKeys.length);

    for (var ri = 0; ri < totalRows; ri++) {
        var rowEl = document.createElement('div');
        rowEl.className = 'nd-row';

        if (ri < node.inputs.length) {
            var piS = document.createElement('div');
            piS.className = 'pi-s';
            var inp = node.inputs[ri];
            var con = _isConnected(node.id, ri, 'i');
            var ptType = inp.type === 'flow' ? 'flow' : 'data';
            var ptR = document.createElement('div');
            ptR.className = 'pt-r i';
            ptR.innerHTML = '<div class="pt ' + ptType + '" data-n="' + node.id + '" data-p="' + inp._portKey + '" data-d="i" data-pt="' + inp.type + '">' +
                '<div class="pd' + (con ? ' con' : '') + '"></div>' +
                '<span>' + inp.name + '</span></div>';
            piS.appendChild(ptR);
            rowEl.appendChild(piS);
        } else if (ri >= paramStartRow && ri < paramStartRow + sKeys.length) {
            var piSpacer = document.createElement('div');
            piSpacer.className = 'pi-s';
            piSpacer.style.visibility = 'hidden';
            piSpacer.innerHTML = '<div class="pt-r i"><div class="pt flow"><div class="pd"></div><span>&nbsp;</span></div></div>';
            rowEl.appendChild(piSpacer);
        }

        if (ri >= paramStartRow && ri < paramStartRow + sKeys.length) {
            var sIdx = ri - paramStartRow;
            var key = sKeys[sIdx];
            var s = def.params_schema[key];
            var val = node.properties[key];
            if (val === undefined) val = s.default;
            var pr = document.createElement('div');
            pr.className = 'nd-pr';
            pr.innerHTML = '<span class="pl">' + (s.label || key) + '</span>' + _renderInlineField(node.id, key, s, val);
            rowEl.appendChild(pr);
        } else if (ri < node.outputs.length || (ri >= paramStartRow + sKeys.length && ri < Math.max(node.outputs.length, paramStartRow + sKeys.length))) {
            var spacer = document.createElement('div');
            spacer.className = 'nd-pr';
            spacer.style.visibility = 'hidden';
            spacer.innerHTML = '<span class="pl">&nbsp;</span>';
            rowEl.appendChild(spacer);
        }

        if (ri < node.outputs.length) {
            var poS = document.createElement('div');
            poS.className = 'po-s';
            var out = node.outputs[ri];
            var con2 = _isConnected(node.id, ri, 'o');
            var ptType2 = out.type === 'flow' ? 'flow' : 'data';
            var ptR2 = document.createElement('div');
            ptR2.className = 'pt-r o';
            ptR2.innerHTML = '<div class="pt ' + ptType2 + '" data-n="' + node.id + '" data-p="' + out._portKey + '" data-d="o" data-pt="' + out.type + '">' +
                '<span>' + out.name + '</span>' +
                '<div class="pd' + (con2 ? ' con' : '') + '"></div></div>';
            poS.appendChild(ptR2);
            rowEl.appendChild(poS);
        } else if (ri >= paramStartRow && ri < paramStartRow + sKeys.length && node.outputs.length === 0) {
            var poSpacer = document.createElement('div');
            poSpacer.className = 'po-s';
            poSpacer.style.visibility = 'hidden';
            poSpacer.innerHTML = '<div class="pt-r o"><div class="pt flow"><span>&nbsp;</span><div class="pd"></div></div></div>';
            rowEl.appendChild(poSpacer);
        }

        b.appendChild(rowEl);
    }

    el.appendChild(b);
    return el;
}

function _addNodeToDOM(node) {
    if (!_s._nodeLayerEl) return;
    var el = _renderNodeDOM(node);
    _s._nodeLayerEl.appendChild(el);
    node._domEl = el;
    node.size = [el.offsetWidth || 220, el.offsetHeight || 100];
    _bindInlineFields(el, node);
}

function _bindInlineFields(el, node) {
    var fields = el.querySelectorAll('.nf');
    for (var i = 0; i < fields.length; i++) {
        (function(f) {
            var nid = parseInt(f.dataset.nid);
            var key = f.dataset.key;
            if (f.tagName === 'SELECT') {
                f.addEventListener('change', function() {
                    var n = _s._nodes[nid];
                    if (!n) return;
                    n.properties[key] = f.value;
                    if (window.AutomationProperty && AutomationProperty._currentNode === n) {
                        AutomationProperty.render(n);
                    }
                    _refreshNodeDOM(n);
                });
                f.addEventListener('mousedown', function(e) { e.stopPropagation(); });
            } else if (f.tagName === 'LABEL') {
                var cb = f.querySelector('input[type="checkbox"]');
                if (cb) {
                    cb.addEventListener('change', function() {
                        var n = _s._nodes[nid];
                        if (!n) return;
                        n.properties[key] = cb.checked;
                        if (window.AutomationProperty && AutomationProperty._currentNode === n) {
                            AutomationProperty.render(n);
                        }
                        _refreshNodeDOM(n);
                    });
                    f.addEventListener('mousedown', function(e) { e.stopPropagation(); });
                }
            } else if (f.type === 'checkbox') {
                f.addEventListener('change', function() {
                    var n = _s._nodes[nid];
                    if (!n) return;
                    n.properties[key] = f.checked;
                    if (window.AutomationProperty && AutomationProperty._currentNode === n) {
                        AutomationProperty.render(n);
                    }
                    _refreshNodeDOM(n);
                });
                f.addEventListener('mousedown', function(e) { e.stopPropagation(); });
            } else if (f.type === 'number') {
                f.addEventListener('input', function() {
                    var n = _s._nodes[nid];
                    if (!n) return;
                    var v = f.value;
                    if (v && v.indexOf('${') >= 0) {
                        n.properties[key] = v;
                    } else {
                        n.properties[key] = parseFloat(v) || 0;
                    }
                });
                f.addEventListener('change', function() {
                    var n = _s._nodes[nid];
                    if (!n) return;
                    var v = f.value;
                    if (v && v.indexOf('${') >= 0) {
                        n.properties[key] = v;
                    } else {
                        n.properties[key] = parseFloat(v) || 0;
                    }
                    if (window.AutomationProperty && AutomationProperty._currentNode === n) {
                        AutomationProperty.render(n);
                    }
                    _refreshNodeDOM(n);
                });
                f.addEventListener('mousedown', function(e) { e.stopPropagation(); });
                f.addEventListener('click', function(e) { e.stopPropagation(); });
            } else if (f.type === 'color') {
                f.addEventListener('input', function() {
                    var n = _s._nodes[nid];
                    if (!n) return;
                    n.properties[key] = f.value;
                });
                f.addEventListener('change', function() {
                    var n = _s._nodes[nid];
                    if (!n) return;
                    n.properties[key] = f.value;
                    if (window.AutomationProperty && AutomationProperty._currentNode === n) {
                        AutomationProperty.render(n);
                    }
                    _refreshNodeDOM(n);
                });
                f.addEventListener('mousedown', function(e) { e.stopPropagation(); });
            } else if (f.type === 'text') {
                f.addEventListener('input', function() {
                    var n = _s._nodes[nid];
                    if (!n) return;
                    n.properties[key] = f.value;
                });
                f.addEventListener('change', function() {
                    var n = _s._nodes[nid];
                    if (!n) return;
                    n.properties[key] = f.value;
                    if (window.AutomationProperty && AutomationProperty._currentNode === n) {
                        AutomationProperty.render(n);
                    }
                    _refreshNodeDOM(n);
                });
                f.addEventListener('mousedown', function(e) { e.stopPropagation(); });
                f.addEventListener('click', function(e) { e.stopPropagation(); });
            } else if (f.classList.contains('nf-ro')) {
                f.addEventListener('click', function() {
                    var n = _s._nodes[nid];
                    if (n) {
                        if (_selectNodeById) _selectNodeById(nid);
                        if (window.AutomationProperty) AutomationProperty.render(n);
                    }
                });
            }
        })(fields[i]);
    }
    var vlContainers = el.querySelectorAll('.nf-vl');
    for (var vli = 0; vli < vlContainers.length; vli++) {
        (function(vlc) {
            var vlnid = parseInt(vlc.dataset.nid);
            var vlkey = vlc.dataset.key;
            function _vlSync() {
                if (!document.contains(vlc)) return;
                var n = _s._nodes[vlnid];
                if (!n) return;
                var items = [];
                vlc.querySelectorAll('.vl-json').forEach(function(inp) {
                    try {
                        var obj = JSON.parse(inp.value || '{}');
                        if (obj && typeof obj === 'object' && !Array.isArray(obj)) {
                            items.push({
                                name: obj.name || '',
                                value: obj.value !== undefined ? obj.value : '',
                                type: obj.type || 'string'
                            });
                        }
                    } catch(e) {
                        items.push({name: '', value: inp.value || '', type: 'string'});
                    }
                });
                var newJson = JSON.stringify(items);
                console.log('[VAR_LIST] _vlSync node=' + vlnid + ' key=' + vlkey + ' items.length=' + items.length + ' json=' + newJson);
                n.properties[vlkey] = newJson;
                if (window.AutomationProperty && AutomationProperty._currentNode === n) {
                    AutomationProperty.render(n);
                }
            }
            vlc.querySelectorAll('.vl-json').forEach(function(inp) {
                inp.addEventListener('input', _vlSync);
                inp.addEventListener('mousedown', function(e) { e.stopPropagation(); });
                inp.addEventListener('click', function(e) { e.stopPropagation(); });
            });
        })(vlContainers[vli]);
    }
}

function _removeNodeFromDOM(nodeId) {
    var el = document.getElementById('nd-' + nodeId);
    if (el) el.remove();
}

function _refreshNodeDOM(node) {
    console.log('[VAR_LIST] _refreshNodeDOM node=' + node.id + ' type=' + node.type);
    var oldEl = document.getElementById('nd-' + node.id);
    if (!oldEl) return;
    var newEl = _renderNodeDOM(node);
    oldEl.parentNode.replaceChild(newEl, oldEl);
    node._domEl = newEl;
    _bindInlineFields(newEl, node);
    requestAnimationFrame(function() {
        var w = newEl.offsetWidth || 220;
        var h = newEl.scrollHeight || newEl.offsetHeight || 100;
        h += 6;
        node.size = [w, h];
        newEl.style.width = w + 'px';
        newEl.style.height = h + 'px';
        console.log('[VAR_LIST] _refreshNodeDOM size set to', w, 'x', h);
    });
}

function _createNodeData(type) {
    var def = window.AutomationNodes ? AutomationNodes.getNodeDef(type) : null;
    if (!def) return null;

    var id = _s._nextNodeId++;
    var isFlowNode = type === 'flow/start' || type === 'flow/end';
    var node = {
        id: id,
        type: type,
        _defKey: type,
        pos: [0, 0],
        size: isFlowNode ? [140, 60] : [200, 120],
        properties: {},
        inputs: [],
        outputs: [],
        _accentColor: def.color || '#888',
        _category: def.category || 'other',
        _iconClass: def.icon || 'fa-solid fa-circle',
        title: '   ' + (def.display_name || type),
        selected: false,
        boxcolor: def.color || '#888',
        _domEl: null,
        clone: function() {
            var c = _createNodeData(type);
            if (!c) return null;
            c.pos = [node.pos[0] + 30, node.pos[1] + 30];
            for (var k in node.properties) {
                if (node.properties.hasOwnProperty(k)) {
                    c.properties[k] = JSON.parse(JSON.stringify(node.properties[k]));
                }
            }
            if (node._customName) c._customName = node._customName;
            if (c.properties.branch_count && c.properties.branch_count !== 2 && window.AutomationCore && window.AutomationCore.updateBranchPorts) {
                window.AutomationCore.updateBranchPorts(c, c.properties.branch_count);
            }
            return c;
        }
    };

    var _initBranchCount = 0;
    if (def.dynamic_branches && def.params_schema && def.params_schema.branch_count) {
        _initBranchCount = def.params_schema.branch_count.default || 2;
    }

    if (def.inputs) {
        var branchCount = def.dynamic_branches ? _initBranchCount : 0;
        for (var i = 0; i < def.inputs.length; i++) {
            var inp = def.inputs[i];
            if (def.dynamic_branches && def.type === 'control/join') {
                if (i < branchCount) {
                    node.inputs.push({
                        name: _toZh(inp.name, inp),
                        type: inp.type,
                        _portKey: inp.name
                    });
                }
            } else {
                node.inputs.push({
                    name: _toZh(inp.name, inp),
                    type: inp.type,
                    _portKey: inp.name
                });
            }
        }
    }
    if (def.outputs) {
        var branchCount = def.dynamic_branches ? _initBranchCount : 0;
        for (var i = 0; i < def.outputs.length; i++) {
            var out = def.outputs[i];
            if (def.dynamic_branches && def.type !== 'control/join') {
                var isBranchPort = out.name.indexOf('branch') === 0;
                if (!isBranchPort) {
                    node.outputs.push({
                        name: _toZh(out.name, out),
                        type: out.type,
                        _portKey: out.name
                    });
                } else {
                    var branchIdx = parseInt(out.name.replace('branch', ''));
                    if (branchIdx <= branchCount) {
                        node.outputs.push({
                            name: _toZh(out.name, out),
                            type: out.type,
                            _portKey: out.name
                        });
                    }
                }
            } else if (def.dynamic_branches && def.type === 'control/join') {
                node.outputs.push({
                    name: _toZh(out.name, out),
                    type: out.type,
                    _portKey: out.name
                });
            } else if (!def.dynamic_branches) {
                node.outputs.push({
                    name: _toZh(out.name, out),
                    type: out.type,
                    _portKey: out.name
                });
            }
        }
    }

    var schema = def.params_schema || {};
    for (var key in schema) {
        if (!schema.hasOwnProperty(key)) continue;
        var s = schema[key];
        if (s.type === 'region') {
            node.properties[key] = s.default ? s.default.slice() : [0, 0, 10, 10];
        } else if (s.type === 'bool') {
            node.properties[key] = !!s.default;
        } else if (s.type === 'boolean') {
            node.properties[key] = !!s.default;
        } else if (s.type === 'var_list' && type === 'variable/var_set') {
            node.properties[key] = '[{"name":"","value":"","type":"string"}]';
        } else {
            node.properties[key] = s.default !== undefined ? s.default : (s.type === 'number' ? 0 : '');
        }
    }

    return node;
}

export {
    _renderNodeDOM,
    _addNodeToDOM,
    _bindInlineFields,
    _removeNodeFromDOM,
    _refreshNodeDOM,
    _createNodeData,
    _setSelectNodeByIdFn
};
