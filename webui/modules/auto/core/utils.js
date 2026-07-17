'use strict';

import { _portNameMap } from './constants.js';
import { _s } from './state.js';

function _toZh(name, portDef) {
    if (portDef && portDef.display_name) return portDef.display_name;
    return _portNameMap[name] || name;
}

function _screenToLocal(cx, cy) {
    var r = _s._canvasArea.getBoundingClientRect();
    return {
        x: (cx - r.left - _s._vpOffset.x) / _s._vpScale,
        y: (cy - r.top - _s._vpOffset.y) / _s._vpScale
    };
}

function _getPortCenter(nodeId, portKey, dir) {
    var el = document.getElementById('nd-' + nodeId);
    if (!el) return null;
    var dot = el.querySelector('.pt[data-p="' + portKey + '"][data-d="' + dir + '"] .pd');
    if (!dot) return null;
    var dr = dot.getBoundingClientRect();
    var ar = _s._canvasArea.getBoundingClientRect();
    return {
        x: (dr.left + dr.width / 2 - ar.left - _s._vpOffset.x) / _s._vpScale,
        y: (dr.top + dr.height / 2 - ar.top - _s._vpOffset.y) / _s._vpScale
    };
}

function _bezier(x1, y1, x2, y2) {
    var dx = Math.abs(x2 - x1);
    var cp = Math.max(50, dx * 0.5);
    return 'M' + x1 + ',' + y1 + ' C' + (x1 + cp) + ',' + y1 + ' ' + (x2 - cp) + ',' + y2 + ' ' + x2 + ',' + y2;
}

function _checkShowWhen(showWhen, allParams) {
    if (!showWhen) return true;
    var segments = showWhen.split(',');
    var conditions = [];
    var currentField = null;
    var currentValues = [];
    for (var i = 0; i < segments.length; i++) {
        var seg = segments[i].trim();
        var opMatch = seg.match(/^(.+?)(>=|<=|!=|>|<|=)(.+)$/);
        if (opMatch) {
            var newField = opMatch[1].trim();
            if (currentField !== null && newField === currentField) {
                currentValues.push({op: opMatch[2], value: opMatch[3].trim()});
            } else {
                if (currentField !== null) {
                    conditions.push({field: currentField, values: currentValues});
                }
                currentField = newField;
                currentValues = [{op: opMatch[2], value: opMatch[3].trim()}];
            }
        } else if (currentField !== null) {
            currentValues.push({op: '=', value: seg});
        }
    }
    if (currentField !== null) {
        conditions.push({field: currentField, values: currentValues});
    }
    if (conditions.length === 0) return true;
    for (var c = 0; c < conditions.length; c++) {
        var cond = conditions[c];
        var rawVal = allParams[cond.field];
        var currentVal;
        if (rawVal === true || rawVal === false) {
            currentVal = String(rawVal);
        } else {
            currentVal = String(rawVal ?? '');
        }
        var fieldMatch = false;
        for (var v = 0; v < cond.values.length; v++) {
            var item = cond.values[v];
            var op = item.op;
            var val = item.value;
            if (op === '=') {
                if (val === currentVal) { fieldMatch = true; break; }
                if (val === 'true' && rawVal === true) { fieldMatch = true; break; }
                if (val === 'false' && rawVal === false) { fieldMatch = true; break; }
            } else if (op === '!=') {
                if (rawVal === undefined || rawVal === null || rawVal === '') { continue; }
                if (val !== currentVal) { fieldMatch = true; break; }
                if (val === 'true' && rawVal !== true) { fieldMatch = true; break; }
                if (val === 'false' && rawVal !== false) { fieldMatch = true; break; }
            } else {
                var numCur = parseFloat(currentVal);
                var numVal = parseFloat(val);
                if (!isNaN(numCur) && !isNaN(numVal)) {
                    if (op === '>=' && numCur >= numVal) { fieldMatch = true; break; }
                    if (op === '<=' && numCur <= numVal) { fieldMatch = true; break; }
                    if (op === '>' && numCur > numVal) { fieldMatch = true; break; }
                    if (op === '<' && numCur < numVal) { fieldMatch = true; break; }
                }
            }
        }
        if (!fieldMatch) return false;
    }
    return true;
}

function _pickSummaryKeys(schema, properties) {
    var keys = [];
    var skip = { hwnd_var: true, store_var: true, store_number: true, path: true, template_path: true, method: true, trigger_mode: true, on_trigger: true, auto_stop: true, recheck_delay_ms: true, max_triggers: true, mode: true, wait: true, wait_interval_ms: true, wait_timeout_ms: true, pyramid_levels: true, area_ratio_threshold: true, monitor_index: true, fps: true, enabled: true, check_mode: true, sample_mode: true, cache_strategy: true, cache_interval_ms: true, engine: true, change_threshold: true, tolerance: true, c: true, standby_override: true, rtss_override: true };
    var priority = { x: 1, y: 2, dx: 3, dy: 4, button: 5, key: 6, text: 7, delay: 8, duration: 9, amount: 10 };
    var allKeys = [];
    for (var k in schema) {
        if (!schema.hasOwnProperty(k)) continue;
        if (skip[k]) continue;
        if (schema[k].showWhen && properties) {
            if (!_checkShowWhen(schema[k].showWhen, properties)) continue;
        }
        allKeys.push(k);
    }
    allKeys.sort(function(a, b) {
        var pa = priority[a] || 99;
        var pb = priority[b] || 99;
        return pa - pb;
    });
    for (var i = 0; i < allKeys.length && i < 4; i++) {
        keys.push(allKeys[i]);
    }
    return keys;
}

function _fmtVal(val, s) {
    if (val === undefined || val === null) return '';
    if (s.type === 'bool' || s.type === 'boolean') return val ? '是' : '否';
    if (s.type === 'enum' || (s.type === 'string' && s.enum)) return val;
    if (s.type === 'region') return Array.isArray(val) ? val.join(', ') : val;
    if (s.type === 'color') return val;
    return String(val);
}

function _escapeHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function _renderInlineField(nodeId, key, schema, val) {
    var nid = nodeId, k = key;
    var isEnum = (schema.type === 'enum' && schema.options) || (schema.type === 'string' && schema.enum);
    if (isEnum) {
        var opts = schema.options || schema.enum;
        var html = '<select class="nf nf-sel" data-nid="' + nid + '" data-key="' + k + '">';
        for (var i = 0; i < opts.length; i++) {
            var opt = opts[i];
            var sel = (String(val) === String(opt)) ? ' selected' : '';
            html += '<option value="' + _escapeHtml(opt) + '"' + sel + '>' + _escapeHtml(opt) + '</option>';
        }
        html += '</select>';
        return html;
    }
    if (schema.type === 'bool' || schema.type === 'boolean') {
        var chk = (val === true || val === 'true') ? ' checked' : '';
        return '<label class="nf nf-chk" data-nid="' + nid + '" data-key="' + k + '"><input type="checkbox"' + chk + '><span class="chk-mk"></span></label>';
    }
    if (schema.type === 'number') {
        var step = (schema.coordRef) ? '0.01' : '1';
        return '<input type="number" class="nf nf-num" data-nid="' + nid + '" data-key="' + k + '" value="' + (val !== null && val !== undefined ? val : (schema.default || 0)) + '" step="' + step + '">';
    }
    if (schema.type === 'color') {
        return '<input type="color" class="nf nf-col" data-nid="' + nid + '" data-key="' + k + '" value="' + (val || '#FF0000') + '">';
    }
    if (schema.type === 'region') {
        var rv = Array.isArray(val) ? val.join(', ') : (val || '');
        return '<span class="nf nf-ro" data-nid="' + nid + '" data-key="' + k + '" title="点击在属性面板中编辑">' + _escapeHtml(rv) + '</span>';
    }
    if (schema.type === 'var_list') {
        var items = [];
        try { items = JSON.parse(val || '[]'); } catch(e) { items = []; }
        if (!Array.isArray(items)) items = [];
        console.log('[VAR_LIST] _renderInlineField var_list node=' + nid + ' key=' + k + ' items.length=' + items.length);
        var vlHtml = '<div class="nf nf-vl" data-nid="' + nid + '" data-key="' + k + '" data-type="var_list" style="display:flex;flex-direction:column;gap:2px">';
        for (var vi = 0; vi < items.length; vi++) {
            var vit = items[vi];
            var jsonStr = JSON.stringify(vit);
            vlHtml += '<input type="text" class="vl-json" data-vi="' + vi + '" value="' + _escapeHtml(jsonStr) + '" style="padding:2px 4px;font-size:10px;border-radius:2px;border:1px solid var(--border,#334155);background:rgba(15,23,42,0.6);color:var(--txt1,#f1f5f9);width:100%;box-sizing:border-box;font-family:var(--fmo,monospace)">';
        }
        if (items.length === 0) {
            vlHtml += '<span style="color:var(--txt3,#94a3b8);font-size:10px;padding:4px 0;display:block">在属性面板添加变量</span>';
        }
        vlHtml += '</div>';
        return vlHtml;
    }
    return '<input type="text" class="nf nf-txt" data-nid="' + nid + '" data-key="' + k + '" value="' + (val !== null && val !== undefined ? _escapeHtml(val) : '') + '">';
}

function _isConnected(nodeId, slotIdx, dir) {
    for (var i = 0; i < _s._connections.length; i++) {
        var c = _s._connections[i];
        if (dir === 'i' && c.target_id === nodeId && c.target_slot === slotIdx) return true;
        if (dir === 'o' && c.origin_id === nodeId && c.origin_slot === slotIdx) return true;
    }
    return false;
}

function _pointToBezierDist(px, py, x1, y1, x2, y2) {
    var dx = Math.abs(x2 - x1);
    var cp = Math.max(50, dx * 0.5);
    var minDist = Infinity;
    var steps = 20;
    for (var i = 0; i <= steps; i++) {
        var t = i / steps;
        var it = 1 - t;
        var cx1 = x1 + cp, cy1 = y1;
        var cx2 = x2 - cp, cy2 = y2;
        var bx = it*it*it*x1 + 3*it*it*t*cx1 + 3*it*t*t*cx2 + t*t*t*x2;
        var by = it*it*it*y1 + 3*it*it*t*cy1 + 3*it*t*t*cy2 + t*t*t*y2;
        var d = Math.sqrt((px-bx)*(px-bx) + (py-by)*(py-by));
        if (d < minDist) minDist = d;
    }
    return minDist;
}

export {
    _toZh,
    _screenToLocal,
    _getPortCenter,
    _bezier,
    _checkShowWhen,
    _pickSummaryKeys,
    _fmtVal,
    _escapeHtml,
    _renderInlineField,
    _isConnected,
    _pointToBezierDist
};
