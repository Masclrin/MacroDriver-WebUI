'use strict';

import { _escapeHtml } from '../core/utils.js';
var _pe = _escapeHtml;

window._screenDpiScale = null;
window._ensureScreenDpiScale = function() {
    if (window._screenDpiScale !== null) return;
    window._screenDpiScale = 1.0;
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_screen_info) {
        window.pywebview.api.get_screen_info().then(function(resp) {
            if (resp && resp.ok && resp.data && resp.data.dpi_scale) {
                var prevScale = window._screenDpiScale;
                window._screenDpiScale = resp.data.dpi_scale;
                if (prevScale !== resp.data.dpi_scale) {
                    window._dpiScaleReady = true;
                    if (window.AutomationProperty && window.AutomationProperty._currentNode) {
                        window.AutomationProperty.render(window.AutomationProperty._currentNode);
                    }
                }
            }
        }).catch(function() {});
    }
};
window._ensureScreenDpiScale();

window._isScreenCoordMode = function(node) {
    if (!node || !node.properties) return false;
    var mode = node.properties.mode || node.properties.capture_mode || 'screen';
    return mode === 'screen';
};

window.AutomationProperty._renderGroup = function(groupName, paramEntries, node) {
    var html = '<div class="prop-group">' +
        '<div class="prop-group-header"><i class="fa-solid fa-chevron-down arrow"></i> ' + groupName + '</div>' +
        '<div class="prop-group-body">';

    for (var i = 0; i < paramEntries.length; i++) {
        var key = paramEntries[i][0];
        var schema = paramEntries[i][1];

        if (schema.showWhen && !this._checkShowWhen(schema.showWhen, node.properties)) {
            if (node.properties[key] === undefined && schema.default !== undefined) {
                node.properties[key] = schema.default;
            }
            continue;
        }

        if (schema._branchIndex !== undefined) {
            var bc = parseInt(node.properties.branch_count) || 2;
            if (schema._branchIndex > bc) continue;
        }

        var val = node.properties[key];
        if (val === undefined) {
            val = schema.default !== undefined ? schema.default : (schema.type === 'number' ? 0 : '');
            node.properties[key] = val;
        }
        var isVarRef = typeof val === 'string' && val.indexOf('${') === 0 && val.charAt(val.length - 1) === '}';
        var varBadge = isVarRef ? '<span class="var-badge">VAR</span>' : '';

        switch (schema.type) {
            case 'enum':
                html += this._renderEnumField(key, schema, val, varBadge);
                break;
            case 'number':
                if (key === 'branch_count') {
                    html += this._renderBranchCountField(key, schema, val, node);
                } else {
                    html += this._renderNumberField(key, schema, val, varBadge, node.properties, node);
                }
                break;
            case 'string':
                html += this._renderStringField(key, schema, val, varBadge, node);
                break;
            case 'bool':
            case 'boolean':
                html += this._renderBoolField(key, schema, val);
                break;
            case 'color':
                html += this._renderColorField(key, schema, val, varBadge);
                break;
            case 'region':
                html += this._renderRegionField(key, schema, val, varBadge, node);
                break;
            case 'path':
                html += this._renderPathField(key, schema, val, varBadge, node);
                break;
            case 'var_list':
                html += this._renderVarListField(key, schema, val, node);
                break;
            case 'stage_list':
                html += this._renderStageListField(key, schema, val, node);
                break;
            case 'stage_ref':
                html += this._renderStageRefField(key, schema, val, node);
                break;
            case 'affinity':
                html += this._renderAffinityField(key, schema, val, node);
                break;
            default:
                if (schema.nodeRef) {
                    html += this._renderNodeRefField(key, schema, val, node);
                } else {
                    html += this._renderStringField(key, schema, val, varBadge, node);
                }
        }
    }

    html += '</div></div>';
    return html;
};

window.AutomationProperty._checkShowWhen = function(showWhen, allParams) {
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
};

window.AutomationProperty._renderEnumField = function(key, schema, val, varBadge) {
    var displayNames = schema.display_names || {};
    var options = (schema.options || []).map(function(o) {
        var displayText = displayNames[o] || o;
        return '<option value="' + _pe(o) + '"' + (val === o ? ' selected' : '') + '>' + _pe(displayText) + '</option>';
    }).join('');
    var desc = schema.description ? '<span style="font-size:10px;color:var(--txt3)">' + _pe(schema.description) + '</span>' : '';
    return '<div class="prop-field">' +
        '<label class="prop-field-label">' + (schema.label || key) + ' ' + varBadge + '</label>' +
        '<select data-key="' + key + '" data-type="enum">' + options + '</select>' +
        desc +
      '</div>';
};

window.AutomationProperty._renderNumberField = function(key, schema, val, varBadge, allParams, node) {
    var step = schema.step || ((schema.coordRef && (allParams.mode === 'relative' || allParams.capture_mode === 'relative')) ? '0.01' : '1');
    var placeholder = (schema.coordRef && (allParams.mode === 'relative' || allParams.capture_mode === 'relative')) ? '0.0 ~ 1.0' : '';
    var desc = schema.description ? '<span style="font-size:10px;color:var(--txt3)">' + _pe(schema.description) + '</span>' : '';
    if (schema.descriptionMap && allParams) {
        var condKey = schema.descriptionMapCond || 'state';
        var condVal = allParams[condKey];
        if (condVal && schema.descriptionMap[condVal]) {
            desc = '<span style="font-size:10px;color:var(--txt3)">' + _pe(schema.descriptionMap[condVal]) + '</span>';
        }
    }
    var isVarRef = typeof val === 'string' && val.indexOf('${') === 0 && val.charAt(val.length - 1) === '}';
    var displayVal;
    if (isVarRef) {
        displayVal = val.slice(2, -1);
    } else {
        displayVal = (val !== null && val !== undefined ? val : schema.default || 0);
    }
    var inputClass = isVarRef ? 'var-input' : '';
    var html = '<div class="prop-field">' +
        '<label class="prop-field-label">' + (schema.label || key) + ' ' + varBadge + '</label>';
    var hasPickBtn = (schema.coordRef || schema.pickable) && node;
    var hasVarBtn = schema.varRef;
    if (hasPickBtn || hasVarBtn) {
        html += '<div style="display:flex;gap:4px">' +
          '<input type="text" data-key="' + key + '" data-type="number" data-raw-value="' + (val !== null && val !== undefined ? val : '') + '" value="' + displayVal + '" step="' + step + '" placeholder="' + placeholder + '" style="flex:1" class="' + inputClass + '">';
        if (hasVarBtn) {
            html += '<button class="prop-btn outline var-ref-btn" data-key="' + key + '" data-vartype="number" onclick="window.AutomationProperty._toggleVarSelector(this,' + node.id + ',\'' + key + '\',\'number\')" style="flex-shrink:0;padding:6px 16px" title="选择变量"><i class="fa-solid fa-dollar-sign"></i></button>';
        }
        if (hasPickBtn) {
            html += '<button class="prop-btn outline" onclick="window.AutomationTools.startCoordPick(' + node.id + ',\'' + key + '\')" style="flex-shrink:0;padding:6px 16px" title="拾取坐标"><i class="fa-solid fa-crosshairs"></i></button>';
        }
        html += '</div>';
    } else {
        html += '<input type="text" data-key="' + key + '" data-type="number" data-raw-value="' + (val !== null && val !== undefined ? val : '') + '" value="' + displayVal + '" step="' + step + '" placeholder="' + placeholder + '" class="' + inputClass + '">';
    }
    html += desc + '</div>';
    return html;
};

window.AutomationProperty._renderStringField = function(key, schema, val, varBadge, node) {
    var isHwndVar = (key === 'hwnd_var');
    var hasVarBtn = schema.varRef;
    var hasProgramPicker = schema.browseType === 'program';
    var hasWindowPicker = schema.windowPicker === true;
    var hasProcessPicker = schema.processPicker === true;
    var hasKeySelector = schema.keySelector === true;
    var isVarRef = typeof val === 'string' && val.indexOf('${') === 0 && val.charAt(val.length - 1) === '}';
    var displayVal = isVarRef ? val.slice(2, -1) : (val || '');
    var inputClass = isVarRef ? 'var-input' : '';
    var desc = schema.description ? '<span style="font-size:10px;color:var(--txt3)">' + _pe(schema.description) + '</span>' : '';
    var html = '<div class="prop-field">' +
        '<label class="prop-field-label">' + (schema.label || key) + ' ' + varBadge + '</label>';
    if (isHwndVar || hasVarBtn || hasProgramPicker || hasWindowPicker || hasProcessPicker || hasKeySelector) {
        html += '<div style="display:flex;gap:4px">' +
          '<input type="text" data-key="' + key + '" data-type="string" data-raw-value="' + _pe(val || '') + '" value="' + _pe(displayVal) + '" placeholder="' + _pe(schema.placeholder || '') + '" style="flex:1" class="' + inputClass + '">';
        if (hasVarBtn) {
            html += '<button class="prop-btn outline var-ref-btn" data-key="' + key + '" data-vartype="string" onclick="window.AutomationProperty._toggleVarSelector(this,' + node.id + ',\'' + key + '\',\'string\')" style="flex-shrink:0;padding:6px 16px" title="选择变量"><i class="fa-solid fa-dollar-sign"></i></button>';
        }
        if (hasKeySelector) {
            html += '<button class="prop-btn outline" onclick="window.AutomationProperty._openKeySelector(this,' + node.id + ',\'' + key + '\')" style="flex-shrink:0;padding:6px 16px" title="按键选择"><i class="fa-solid fa-keyboard"></i></button>';
        }
        if (hasProgramPicker) {
            html += '<button class="prop-btn outline" onclick="window._autoEditor.browseProgramFile(' + node.id + ',\'' + key + '\')" style="flex-shrink:0;padding:6px 16px" title="选择程序"><i class="fa-solid fa-folder-open"></i></button>';
        }
        if (hasWindowPicker) {
            html += '<button class="prop-btn outline" onclick="window._autoEditor.browseWindowTitle(' + node.id + ',\'' + key + '\')" style="flex-shrink:0;padding:6px 16px" title="选择窗口"><i class="fa-solid fa-window-restore"></i></button>';
        }
        if (hasProcessPicker) {
            html += '<button class="prop-btn outline" onclick="window._autoEditor.browseProcessList(' + node.id + ',\'' + key + '\')" style="flex-shrink:0;padding:6px 16px" title="选择进程"><i class="fa-solid fa-list-check"></i></button>';
        }
        if (isHwndVar) {
            html += '<button class="prop-btn outline" onclick="window._autoEditor.browseWindowList(' + node.id + ',\'' + key + '\')" style="flex-shrink:0;padding:6px 16px" title="选择窗口"><i class="fa-solid fa-window-restore"></i></button>';
        }
        html += '</div>';
    } else if (schema.multiline) {
        html += '<textarea data-key="' + key + '" data-type="string" data-raw-value="' + _pe(val || '') + '" placeholder="' + _pe(schema.placeholder || '') + '" class="' + inputClass + '" rows="3" style="width:100%;resize:vertical;font-size:12px">' + _pe(displayVal) + '</textarea>';
    } else {
        html += '<input type="text" data-key="' + key + '" data-type="string" data-raw-value="' + _pe(val || '') + '" value="' + _pe(displayVal) + '" placeholder="' + _pe(schema.placeholder || '') + '" class="' + inputClass + '">';
    }
    html += desc + '</div>';
    return html;
};

window.AutomationProperty._renderBoolField = function(key, schema, val) {
    var displayNames = schema.display_names || {};
    var trueLabel = displayNames['true'] || displayNames[true] || '是';
    var falseLabel = displayNames['false'] || displayNames[false] || '否';
    var desc = schema.description ? '<span style="font-size:10px;color:var(--txt3)">' + _pe(schema.description) + '</span>' : '';
    return '<div class="prop-field">' +
        '<label class="prop-field-label">' + (schema.label || key) + '</label>' +
        '<select data-key="' + key + '" data-type="bool">' +
          '<option value="true"' + (val === true || val === 'true' ? ' selected' : '') + '>' + trueLabel + '</option>' +
          '<option value="false"' + (val === false || val === 'false' ? ' selected' : '') + '>' + falseLabel + '</option>' +
        '</select>' +
        desc +
      '</div>';
};

window.AutomationProperty._renderColorField = function(key, schema, val, varBadge) {
    var colorVal = val || '#FF0000';
    return '<div class="prop-field">' +
        '<label class="prop-field-label">' + (schema.label || key) + ' ' + varBadge + '</label>' +
        '<div style="display:flex;gap:6px;align-items:center">' +
          '<input type="color" data-key="' + key + '" data-type="color" value="' + colorVal + '" style="width:36px;height:28px;padding:1px;cursor:pointer;border:1px solid var(--border);border-radius:var(--rs);background:var(--bg-surface)">' +
          '<input type="text" data-key="' + key + '" data-type="color-text" value="' + colorVal + '" style="flex:1" placeholder="#RRGGBB">' +
        '</div>' +
      '</div>';
};

window.AutomationProperty._renderRegionField = function(key, schema, val, varBadge, node) {
    var effectiveMode = node.properties.mode || node.properties.capture_mode || 'screen';
    var isRelative = (effectiveMode === 'relative');
    var step = isRelative ? '0.01' : '1';
    var isVarRefVal = typeof val === 'string' && val.indexOf('${') === 0 && val.charAt(val.length - 1) === '}';
    var vals;
    if (isVarRefVal) {
        vals = [0, 0, 0, 0];
    } else {
        vals = Array.isArray(val) ? val : (schema.default || [0,0,10,10]);
    }
    var labels = ['X', 'Y', 'W', 'H'];
    var html = '<div class="prop-field">' +
        '<label class="prop-field-label">' + (schema.label || key) + ' ' + varBadge + '</label>';
    if (isVarRefVal) {
        var varName = val.slice(2, -1);
        html += '<div style="display:flex;gap:4px">' +
            '<input type="text" data-key="' + key + '" data-type="region-varref" data-raw-value="' + val + '" value="' + varName + '" class="var-input" style="flex:1" placeholder="变量名">' +
            '<button class="prop-btn outline var-ref-btn" data-key="' + key + '" data-vartype="region" onclick="window.AutomationProperty._toggleVarSelector(this,' + node.id + ',\'' + key + '\',\'region\')" style="flex-shrink:0;padding:6px 16px" title="选择变量"><i class="fa-solid fa-dollar-sign"></i></button>' +
          '</div>';
    } else {
        html += '<div class="region-grid">';
        for (var i = 0; i < 4; i++) {
            var displayV = vals[i] || 0;
            html += '<div class="region-cell">' +
                '<label>' + labels[i] + '</label>' +
                '<input type="number" data-key="' + key + '" data-type="region" data-index="' + i + '" value="' + displayV + '" step="' + step + '">' +
              '</div>';
        }
        html += '</div>';
        html += '<div class="prop-btn-row" style="margin-top:6px">' +
            '<button class="prop-btn outline" onclick="window.AutomationTools.startRegionPick(' + node.id + ',\'' + key + '\')">' +
              '<i class="fa-solid fa-crop-simple"></i> 框选区域' +
            '</button>' +
          '</div>';
    }
    html += '</div>';
    return html;
};

window.AutomationProperty._renderPathField = function(key, schema, val, varBadge, node) {
    var browseType = schema.browseType || 'macro';
    var browseFn;
    var browseIcon;
    if (browseType === 'template') {
        browseFn = 'window._autoEditor.browseTemplatePath';
        browseIcon = 'fa-solid fa-image';
    } else if (browseType === 'script') {
        browseFn = 'window._autoEditor.browseScriptPath';
        browseIcon = 'fa-solid fa-file-code';
    } else if (browseType === 'folder') {
        browseFn = 'window._autoEditor.browseFolderPath';
        browseIcon = 'fa-solid fa-folder-open';
    } else {
        browseFn = 'window._autoEditor.browseMacroPath';
        browseIcon = 'fa-solid fa-list';
    }
    return '<div class="prop-field">' +
        '<label class="prop-field-label">' + (schema.label || key) + ' ' + varBadge + '</label>' +
        '<div style="display:flex;gap:4px">' +
          '<input type="text" data-key="' + key + '" data-type="string" value="' + _pe(val || '') + '" placeholder="' + _pe(schema.placeholder || '') + '" style="flex:1">' +
          '<button class="prop-btn outline" onclick="' + browseFn + '(' + node.id + ',\'' + key + '\')" style="flex-shrink:0;padding:6px 16px"><i class="' + browseIcon + '"></i></button>' +
        '</div>' +
      '</div>';
};

window.AutomationProperty._renderVarListField = function(key, schema, val, node) {
    var items = [];
    try { items = JSON.parse(val || '[]'); } catch(e) { items = []; }
    if (!Array.isArray(items)) items = [];
    console.log('[VAR_LIST] _renderVarListField node=' + node.id + ' key=' + key + ' items.length=' + items.length + ' rawVal=' + (val||'').substring(0,80));
    var html = '<div class="prop-field var-list-field" data-key="' + key + '">' +
        '<label class="prop-field-label">' + (schema.label || key) +
        ' <button class="prop-btn outline" style="padding:3px 10px;font-size:11px" onclick="window.AutomationProperty._addVarListItem(this,' + node.id + ',\'' + key + '\')"><i class="fa-solid fa-plus"></i> 添加</button></label>';
    html += '<div class="var-list-items">';
    for (var i = 0; i < items.length; i++) {
        var item = items[i];
        var isVarRef = typeof item.value === 'string' && item.value.indexOf('${') === 0 && item.value.charAt(item.value.length - 1) === '}';
        var displayVal = isVarRef ? item.value.slice(2, -1) : (item.value || '');
        var inputClass = isVarRef ? 'var-input' : '';
        html += '<div class="var-list-row" data-index="' + i + '" style="border:1px solid var(--border,#334155);border-radius:6px;padding:3px 4px;margin-bottom:3px;background:var(--bg-card,#0f172a)">';
        html += '<div style="display:flex;align-items:center;gap:4px;margin-bottom:4px">';
        html += '<input type="text" data-subkey="name" value="' + _pe(item.name || '') + '" placeholder="变量名" style="flex:1;padding:3px 6px;font-size:11px;border-radius:3px">';
        html += '<select data-subkey="type" style="width:45px;padding:2px 5px;font-size:12px;border-radius:3px;flex-shrink:0">' +
            '<option value="string" style="padding:0px 4px"' + (item.type === 'string' ? ' selected' : '') + '> 文本</option>' +
            '<option value="number" style="padding:0px 4px"' + (item.type === 'number' ? ' selected' : '') + '> 数字</option>' +
            '<option value="boolean" style="padding:0px 4px"' + (item.type === 'boolean' ? ' selected' : '') + '> 布尔</option>' +
          '</select>';
        html += '<button class="prop-btn outline" style="padding:8px 16px;font-size:11px;color:#ef4444;flex-shrink:0" onclick="window.AutomationProperty._removeVarListItem(this,' + node.id + ',\'' + key + '\')" title="删除此变量"><i class="fa-solid fa-xmark"></i></button>';
        html += '</div>';
        html += '<div style="display:flex;align-items:center;gap:4px">';
        html += '<input type="text" data-subkey="value" value="' + _pe(displayVal) + '" data-raw-value="' + _pe(item.value || '') + '" placeholder="值 / ${变量}" style="flex:1;padding:4px 6px;font-size:12px;border-radius:3px" class="' + inputClass + '">';
        html += '<button class="prop-btn outline var-ref-btn" data-subkey="value" data-vartype="string" onclick="window.AutomationProperty._toggleVarSelectorForVarList(this,' + node.id + ',\'' + key + '\',' + i + ')" style="flex-shrink:0;padding:8px 16px;font-size:11px;border-radius:3px" title="选择变量"><i class="fa-solid fa-dollar-sign"></i></button>';
        html += '</div>';
        html += '</div>';
    }
    if (items.length === 0) {
        html += '<div style="padding:16px;text-align:center;color:var(--txt3,#94a3b8);font-size:12px">暂无变量，点击上方「添加」按钮新增</div>';
    }
    html += '</div></div>';
    return html;
};

// ——— 状态机「阶段列表」可视化编辑器 ———
// 存储格式仍是 "阶段A→阶段B→阶段C" 字符串（与后端/旧脚本完全兼容），
// 只是给用户一个可增删、可排序的友好编辑界面，避免手写 → 分隔符。
window.AutomationProperty._parseStageList = function(val) {
    var arr = String(val === null || val === undefined ? '' : val).split('→');
    var out = [];
    for (var i = 0; i < arr.length; i++) {
        var s = arr[i].trim();
        if (s) out.push(s);
    }
    return out;
};

window.AutomationProperty._renderStageListField = function(key, schema, val, node) {
    var stages = this._parseStageList(val);
    var desc = schema.description ? '<div style="font-size:10px;color:var(--txt3);line-height:1.5;margin-top:4px">' + _pe(schema.description) + '</div>' : '';
    var html = '<div class="prop-field stage-list-field" data-key="' + key + '">' +
        '<label class="prop-field-label" style="display:flex;align-items:center;justify-content:space-between;gap:6px">' +
          '<span>' + (schema.label || key) + '</span>' +
          '<button class="prop-btn outline" style="padding:2px 8px;font-size:11px" onclick="window.AutomationProperty._stageListAdd(this,' + node.id + ',\'' + key + '\')"><i class="fa-solid fa-plus"></i> 添加阶段</button>' +
        '</label>';
    html += '<div class="stage-list-items">';
    for (var i = 0; i < stages.length; i++) {
        html += '<div class="stage-list-row" data-index="' + i + '" style="display:flex;align-items:center;gap:4px;margin-bottom:4px">';
        html += '<span style="width:18px;text-align:center;font-size:11px;color:var(--txt3);flex-shrink:0">' + (i + 1) + '</span>';
        html += '<input type="text" data-subkey="stage" value="' + _pe(stages[i]) + '" placeholder="阶段名称" style="flex:1;padding:4px 6px;font-size:12px;border-radius:3px">';
        html += '<button class="prop-btn outline" style="padding:4px 8px;font-size:11px;flex-shrink:0" onclick="window.AutomationProperty._stageListMove(this,' + node.id + ',\'' + key + '\',' + i + ',-1)" title="上移"' + (i === 0 ? ' disabled' : '') + '><i class="fa-solid fa-arrow-up"></i></button>';
        html += '<button class="prop-btn outline" style="padding:4px 8px;font-size:11px;flex-shrink:0" onclick="window.AutomationProperty._stageListMove(this,' + node.id + ',\'' + key + '\',' + i + ',1)" title="下移"' + (i === stages.length - 1 ? ' disabled' : '') + '><i class="fa-solid fa-arrow-down"></i></button>';
        html += '<button class="prop-btn outline" style="padding:4px 8px;font-size:11px;color:#ef4444;flex-shrink:0" onclick="window.AutomationProperty._stageListRemove(this,' + node.id + ',\'' + key + '\',' + i + ')" title="删除此阶段"><i class="fa-solid fa-xmark"></i></button>';
        html += '</div>';
    }
    if (stages.length === 0) {
        html += '<div style="padding:14px;text-align:center;color:var(--txt3);font-size:12px">还没有阶段，点上方「添加阶段」新增（如：待机、攻击、冷却）</div>';
    }
    html += '</div>';
    if (stages.length) {
        html += '<div style="font-size:10px;color:var(--txt3);margin-top:2px">执行顺序：' + _pe(stages.join(' → ')) + '</div>';
    }
    html += desc + '</div>';
    return html;
};

window.AutomationProperty._renderStageRefField = function(key, schema, val, node) {
    var stages = this._parseStageList(node.properties.states);
    var cur = (val === null || val === undefined) ? '' : String(val);
    var desc = schema.description ? '<div style="font-size:10px;color:var(--txt3);line-height:1.5;margin-top:4px">' + _pe(schema.description) + '</div>' : '';
    var html = '<div class="prop-field">' +
        '<label class="prop-field-label">' + (schema.label || key) + '</label>' +
        '<select data-key="' + key + '" data-type="stageRef">' +
          '<option value=""' + (cur === '' ? ' selected' : '') + '>（不回退，停在当前阶段等待）</option>';
    for (var i = 0; i < stages.length; i++) {
        html += '<option value="' + _pe(stages[i]) + '"' + (cur === stages[i] ? ' selected' : '') + '>' + _pe(stages[i]) + '</option>';
    }
    html += '</select>';
    if (cur && stages.indexOf(cur) < 0) {
        html += '<div style="font-size:10px;color:#f59e0b;margin-top:2px">当前值「' + _pe(cur) + '」不在阶段列表中，运行时会被忽略</div>';
    }
    html += desc + '</div>';
    return html;
};

window.AutomationProperty._renderBranchCountField = function(key, schema, val, node) {
    var count = parseInt(val) || 2;
    var min = schema.min || 2;
    var max = schema.max || 8;
    var html = '<div class="prop-field">' +
        '<label class="prop-field-label">' + (schema.label || key) + '</label>' +
        '<div style="display:flex;align-items:center;gap:8px">' +
          '<button class="prop-btn outline" onclick="window.AutomationProperty._changeBranchCount(' + node.id + ',-1)" style="width:32px;height:32px;padding:0;display:flex;align-items:center;justify-content:center" ' + (count <= min ? 'disabled' : '') + '><i class="fa-solid fa-minus"></i></button>' +
          '<span style="font-size:16px;font-weight:600;min-width:24px;text-align:center" id="branch-count-display-' + node.id + '">' + count + '</span>' +
          '<button class="prop-btn outline" onclick="window.AutomationProperty._changeBranchCount(' + node.id + ',1)" style="width:32px;height:32px;padding:0;display:flex;align-items:center;justify-content:center" ' + (count >= max ? 'disabled' : '') + '><i class="fa-solid fa-plus"></i></button>' +
        '</div>' +
        '<input type="hidden" data-key="' + key + '" data-type="number" value="' + count + '">' +
      '</div>';
    return html;
};

window.AutomationProperty._changeBranchCount = function(nodeId, delta) {
    var node = AutomationCore.lgGraphObj.getNodeById(nodeId);
    if (!node) return;
    var defKey = node._defKey || node.type || '';
    var def = AutomationNodes ? AutomationNodes.getNodeDef(defKey) : null;
    var schema = (def && def.params_schema && def.params_schema.branch_count) || {};
    var min = schema.min || 2;
    var max = schema.max || 8;
    var currentCount = parseInt(node.properties.branch_count) || 2;
    var newCount = Math.max(min, Math.min(max, currentCount + delta));
    if (newCount === currentCount) return;
    if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
    AutomationCore.updateBranchPorts(node, newCount);
    this.render(node);
};

window.AutomationProperty._renderAffinityField = function(key, schema, val, node) {
    var aff = val;
    if (typeof aff === 'string') {
        try { aff = JSON.parse(aff || '{}'); } catch(e) { aff = {}; }
    }
    if (!aff || typeof aff !== 'object') aff = {};
    var enabled = !!aff.enabled;
    var core = aff.core !== undefined ? aff.core : -1;
    var branchIdx = schema._branchIndex || 0;
    var label = schema.label || key;

    var html = '<div class="prop-field">' +
        '<label class="prop-field-label">' + label + '</label>' +
        '<div style="display:flex;gap:6px;align-items:center">' +
        '<label style="display:flex;align-items:center;gap:4px;cursor:pointer;white-space:nowrap">' +
        '<input type="checkbox" data-key="' + key + '" data-type="affinity_enabled" ' + (enabled ? 'checked' : '') + ' style="margin:0"> 启用' +
        '</label>' +
        '<input type="number" data-key="' + key + '" data-type="affinity_core" value="' + core + '" min="-1" max="63" style="width:60px" title="-1=自动推荐">' +
        '<span style="color:#888;font-size:12px">核心(-1=自动)</span>' +
        '</div></div>';
    return html;
};

window.AutomationProperty._renderNodeRefField = function(key, schema, val, node) {
    var nodeRefType = schema.nodeRef || '';
    var refNodes = this._findNodesByType(nodeRefType);
    var isVarRef = typeof val === 'string' && val.indexOf('${') === 0 && val.charAt(val.length - 1) === '}';
    var displayVal = isVarRef ? val.slice(2, -1) : (val || '');
    var inputClass = isVarRef ? 'var-input' : '';

    var html = '<div class="prop-field">' +
        '<label class="prop-field-label">' + (schema.label || key) + '</label>';

    html += '<div style="display:flex;gap:4px;flex-direction:column">';
    if (refNodes.length > 0) {
        html += '<select data-key="' + key + '" data-type="nodeRef" style="width:100%">' +
            '<option value="">-- 选择节点 --</option>';
        for (var i = 0; i < refNodes.length; i++) {
            var rn = refNodes[i];
            var optVal = String(rn.id);
            var optLabel = (rn._customName || rn.title || rn._defKey || '') + ' #' + rn.id;
            html += '<option value="' + optVal + '"' + (val === optVal ? ' selected' : '') + '>' + _pe(optLabel) + '</option>';
        }
        html += '</select>';
    }
    html += '<div style="display:flex;gap:4px">' +
        '<input type="text" data-key="' + key + '" data-type="string" data-raw-value="' + (val || '') + '" value="' + displayVal + '" placeholder="节点ID（留空自动推断）" style="flex:1" class="' + inputClass + '">';
    if (schema.varRef) {
        html += '<button class="prop-btn outline var-ref-btn" data-key="' + key + '" data-vartype="string" onclick="window.AutomationProperty._toggleVarSelector(this,' + node.id + ',\'' + key + '\',\'string\')" style="flex-shrink:0;padding:6px 16px" title="选择变量"><i class="fa-solid fa-dollar-sign"></i></button>';
    }
    html += '</div></div></div>';
    return html;
};

window.AutomationProperty._findNodesByType = function(typeFilter) {
    var result = [];
    if (!AutomationCore.lgGraphObj || !typeFilter) return result;
    var nodes = AutomationCore.lgGraphObj._nodes || [];
    var typeList = typeFilter.split(',');
    for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        var defKey = n._defKey || n.type || '';
        for (var j = 0; j < typeList.length; j++) {
            if (typeList[j] === 'fork_race') {
                if (defKey === 'control/fork' || defKey === 'control/race') {
                    result.push(n);
                    break;
                }
            } else if (defKey === typeList[j]) {
                result.push(n);
                break;
            }
        }
    }
    return result;
};
