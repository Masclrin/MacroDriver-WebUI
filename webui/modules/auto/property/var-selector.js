'use strict';

window.AutomationProperty._addVarListItem = function(btn, nodeId, key) {
    var node = AutomationCore.lgGraphObj.getNodeById(nodeId);
    if (!node) return;
    var items = [];
    try { items = JSON.parse(node.properties[key] || '[]'); } catch(e) { items = []; }
    items.push({name: '', value: '', type: 'string'});
    var newVal = JSON.stringify(items);
    console.log('[VAR_LIST] _addVarListItem node=' + nodeId + ' key=' + key + ' newCount=' + items.length + ' newVal=' + newVal);
    node.properties[key] = newVal;
    this._syncNodeInlineField(node, key, newVal);
    if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
    this.render(node);
};

window.AutomationProperty._toggleVarSelectorForVarList = function(btn, nodeId, key, itemIndex) {
    var existing = document.getElementById('var-selector-popup');
    if (existing) { existing.remove(); return; }
    var allStructuredVars = this._collectStructuredVars(null, nodeId);
    var builtinDefs = [
        {name: 'timestamp', ref: 'timestamp', type: 'number', typeLabel: '时间戳(ms)'},
        {name: 'timestamp_s', ref: 'timestamp_s', type: 'number', typeLabel: '时间戳(s)'},
        {name: 'date', ref: 'date', type: 'string', typeLabel: '日期'},
        {name: 'time', ref: 'time', type: 'string', typeLabel: '时间'},
        {name: 'datetime', ref: 'datetime', type: 'string', typeLabel: '日期时间'},
        {name: 'datetime_compact', ref: 'datetime_compact', type: 'string', typeLabel: '紧凑日期时间'},
        {name: 'random', ref: 'random', type: 'number', typeLabel: '随机数'},
        {name: 'random_int', ref: 'random_int', type: 'number', typeLabel: '随机整数'},
        {name: 'year', ref: 'year', type: 'number', typeLabel: '年'},
        {name: 'month', ref: 'month', type: 'number', typeLabel: '月'},
        {name: 'day', ref: 'day', type: 'number', typeLabel: '日'},
        {name: 'hour', ref: 'hour', type: 'number', typeLabel: '时'},
        {name: 'minute', ref: 'minute', type: 'number', typeLabel: '分'},
        {name: 'second', ref: 'second', type: 'number', typeLabel: '秒'},
        {name: 'weekday', ref: 'weekday', type: 'number', typeLabel: '星期'},
        {name: 'pid', ref: 'pid', type: 'number', typeLabel: '进程ID'},
    ];
    var orderedGroups = [];
    if (!filterType || filterType === 'number') {
        var numBuiltin = [];
        for (var bi = 0; bi < builtinDefs.length; bi++) {
            if (builtinDefs[bi].type === 'number') numBuiltin.push(builtinDefs[bi]);
        }
        if (numBuiltin.length > 0) orderedGroups.push({label: '内置变量 (数字)', vars: numBuiltin, priority: 0});
    }
    if (!filterType || filterType === 'string') {
        var strBuiltin = [];
        for (var bi2 = 0; bi2 < builtinDefs.length; bi2++) {
            if (builtinDefs[bi2].type === 'string') strBuiltin.push(builtinDefs[bi2]);
        }
        if (strBuiltin.length > 0) orderedGroups.push({label: '内置变量 (文本)', vars: strBuiltin, priority: 0});
    }
    for (var nodeLabel in allStructuredVars) {
        orderedGroups.push({label: nodeLabel, vars: allStructuredVars[nodeLabel], priority: 1});
    }
    orderedGroups.sort(function(a, b) { return a.priority - b.priority; });
    var popup = document.createElement('div');
    popup.id = 'var-selector-popup';
    popup.style.cssText = 'position:fixed;z-index:99999;background:var(--bg-raised,#1e293b);border:1px solid var(--border,#334155);border-radius:8px;box-shadow:0 8px 32px rgba(0,0,0,0.5);max-height:300px;overflow-y:auto;min-width:220px;padding:8px 0';
    var rect = btn.getBoundingClientRect();
    var popLeft = rect.left;
    var popTop = rect.bottom + 4;
    if (popLeft + 240 > window.innerWidth) popLeft = window.innerWidth - 250;
    if (popLeft < 4) popLeft = 4;
    if (popTop + 300 > window.innerHeight) popTop = rect.top - 304;
    if (popTop < 4) popTop = 4;
    popup.style.left = popLeft + 'px';
    popup.style.top = popTop + 'px';
    var html = '<div style="padding:4px 12px;font-size:11px;color:var(--txt3,#94a3b8);font-weight:600">选择变量</div>';
    for (var gi = 0; gi < orderedGroups.length; gi++) {
        var group = orderedGroups[gi];
        html += '<div style="padding:4px 12px;font-size:11px;color:var(--txt2,#cbd5e1);font-weight:600;border-bottom:1px solid var(--border,#334155)">' + group.label + '</div>';
        for (var j = 0; j < group.vars.length; j++) {
            var v = group.vars[j];
            html += '<div class="var-selector-item" data-varref="' + v.ref + '" style="padding:6px 12px 6px 24px;cursor:pointer;font-size:12px;color:var(--txt1,#f1f5f9);display:flex;justify-content:space-between">' +
              '<span>' + v.name + '</span>' +
              '<span style="color:var(--txt3,#94a3b8);font-size:10px">' + v.typeLabel + '</span></div>';
        }
    }
    popup.innerHTML = html;
    document.body.appendChild(popup);
    var self = this;
    popup.querySelectorAll('.var-selector-item').forEach(function(item) {
        item.addEventListener('mouseenter', function() { this.style.background = 'var(--bg-hover,#334155)'; });
        item.addEventListener('mouseleave', function() { this.style.background = ''; });
        item.addEventListener('click', function() {
            var varRef = this.dataset.varref;
            var node = AutomationCore.lgGraphObj.getNodeById(nodeId);
            if (!node) return;
            var items = [];
            try { items = JSON.parse(node.properties[key] || '[]'); } catch(e) { items = []; }
            if (itemIndex >= 0 && itemIndex < items.length) {
                items[itemIndex].value = '${' + varRef + '}';
                var newVal = JSON.stringify(items);
                node.properties[key] = newVal;
                self._syncNodeInlineField(node, key, newVal);
                if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
                self.render(node);
            }
            popup.remove();
        });
    });
    setTimeout(function() {
        function close(e) { if (!popup.contains(e.target) && e.target !== btn) { popup.remove(); document.removeEventListener('click', close); } }
        document.addEventListener('click', close);
    }, 100);
};

window.AutomationProperty._removeVarListItem = function(btn, nodeId, key) {
    var node = AutomationCore.lgGraphObj.getNodeById(nodeId);
    if (!node) return;
    var items = [];
    try { items = JSON.parse(node.properties[key] || '[]'); } catch(e) { items = []; }
    var row = btn.closest('.var-list-row');
    var idx = parseInt(row.dataset.index);
    items.splice(idx, 1);
    var newVal = JSON.stringify(items);
    node.properties[key] = newVal;
    this._syncNodeInlineField(node, key, newVal);
    if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
    this.render(node);
};

window.AutomationProperty._toggleVarSelector = function(btn, nodeId, key, varType) {
    var existing = document.getElementById('var-selector-popup');
    if (existing) { existing.remove(); return; }
    var allStructuredVars = this._collectStructuredVars(null, nodeId);
    var builtinDefs = [
        {name: 'timestamp', ref: 'timestamp', type: 'number', typeLabel: '时间戳(ms)'},
        {name: 'timestamp_s', ref: 'timestamp_s', type: 'number', typeLabel: '时间戳(s)'},
        {name: 'date', ref: 'date', type: 'string', typeLabel: '日期'},
        {name: 'time', ref: 'time', type: 'string', typeLabel: '时间'},
        {name: 'datetime', ref: 'datetime', type: 'string', typeLabel: '日期时间'},
        {name: 'datetime_compact', ref: 'datetime_compact', type: 'string', typeLabel: '紧凑日期时间'},
        {name: 'random', ref: 'random', type: 'number', typeLabel: '随机数'},
        {name: 'random_int', ref: 'random_int', type: 'number', typeLabel: '随机整数'},
        {name: 'year', ref: 'year', type: 'number', typeLabel: '年'},
        {name: 'month', ref: 'month', type: 'number', typeLabel: '月'},
        {name: 'day', ref: 'day', type: 'number', typeLabel: '日'},
        {name: 'hour', ref: 'hour', type: 'number', typeLabel: '时'},
        {name: 'minute', ref: 'minute', type: 'number', typeLabel: '分'},
        {name: 'second', ref: 'second', type: 'number', typeLabel: '秒'},
        {name: 'weekday', ref: 'weekday', type: 'number', typeLabel: '星期'},
        {name: 'pid', ref: 'pid', type: 'number', typeLabel: '进程ID'},
    ];
    var typeLabels = {number: '数字', string: '文本', boolean: '布尔', any: '任意'};
    var matchType = varType || '';
    var orderedGroups = [];
    var builtinMatched = [];
    var builtinOther = [];
    for (var bi3 = 0; bi3 < builtinDefs.length; bi3++) {
        if (!matchType || builtinDefs[bi3].type === matchType || builtinDefs[bi3].type === 'any') {
            builtinMatched.push(builtinDefs[bi3]);
        } else {
            builtinOther.push(builtinDefs[bi3]);
        }
    }
    if (builtinMatched.length > 0) {
        orderedGroups.push({label: '内置变量', vars: builtinMatched, priority: 0});
    }
    if (builtinOther.length > 0) {
        orderedGroups.push({label: '内置变量 (' + (typeLabels[matchType] || '其他') + '不匹配)', vars: builtinOther, priority: 4});
    }
    for (var nodeLabel in allStructuredVars) {
        var vars = allStructuredVars[nodeLabel];
        var matched = [];
        var other = [];
        for (var vi = 0; vi < vars.length; vi++) {
            if (!matchType || vars[vi].type === matchType || vars[vi].type === 'any') {
                matched.push(vars[vi]);
            } else {
                other.push(vars[vi]);
            }
        }
        if (matched.length > 0) {
            orderedGroups.push({label: nodeLabel, vars: matched, priority: 1});
        }
        if (other.length > 0) {
            orderedGroups.push({label: nodeLabel + ' (' + (typeLabels[matchType] || '其他') + '不匹配)', vars: other, priority: 3});
        }
    }
    orderedGroups.sort(function(a, b) { return a.priority - b.priority; });
    if (orderedGroups.length === 0) {
        this._showToast('没有可用的变量');
        return;
    }
    var popup = document.createElement('div');
    popup.id = 'var-selector-popup';
    popup.style.cssText = 'position:fixed;z-index:99999;background:var(--bg-raised,#1e293b);border:1px solid var(--border,#334155);border-radius:8px;box-shadow:0 8px 32px rgba(0,0,0,0.5);max-height:300px;overflow-y:auto;min-width:220px;padding:8px 0';
    var rect = btn.getBoundingClientRect();
    var popLeft = rect.left;
    var popTop = rect.bottom + 4;
    if (popLeft + 240 > window.innerWidth) popLeft = window.innerWidth - 250;
    if (popLeft < 4) popLeft = 4;
    if (popTop + 300 > window.innerHeight) popTop = rect.top - 304;
    if (popTop < 4) popTop = 4;
    popup.style.left = popLeft + 'px';
    popup.style.top = popTop + 'px';
    var html = '<div style="padding:4px 12px;font-size:11px;color:var(--txt3,#94a3b8);font-weight:600">选择变量' + (matchType ? ' (推荐' + (typeLabels[matchType] || matchType) + '类型)' : '') + '</div>';
    for (var gi = 0; gi < orderedGroups.length; gi++) {
        var group = orderedGroups[gi];
        html += '<div style="padding:4px 12px;font-size:11px;color:var(--txt2,#cbd5e1);font-weight:600;border-bottom:1px solid var(--border,#334155)">' + group.label + '</div>';
        for (var j = 0; j < group.vars.length; j++) {
            var v = group.vars[j];
            html += '<div class="var-selector-item" data-varref="' + v.ref + '" style="padding:6px 12px 6px 24px;cursor:pointer;font-size:12px;color:var(--txt1,#f1f5f9);display:flex;justify-content:space-between">' +
              '<span>' + v.name + '</span>' +
              '<span style="color:var(--txt3,#94a3b8);font-size:10px">' + v.typeLabel + '</span></div>';
        }
    }
    popup.innerHTML = html;
    document.body.appendChild(popup);
    var self = this;
    popup.querySelectorAll('.var-selector-item').forEach(function(item) {
        item.addEventListener('mouseenter', function() { this.style.background = 'var(--bg-hover,#334155)'; });
        item.addEventListener('mouseleave', function() { this.style.background = ''; });
        item.addEventListener('click', function() {
            var varRef = this.dataset.varref;
            var node = AutomationCore.lgGraphObj.getNodeById(nodeId);
            if (!node) return;
            var newVal = '${' + varRef + '}';
            node.properties[key] = newVal;
            self._syncNodeInlineField(node, key, newVal);
            if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
            self.render(node);
            popup.remove();
        });
    });
    setTimeout(function() {
        function close(e) { if (!popup.contains(e.target) && e.target !== btn) { popup.remove(); document.removeEventListener('click', close); } }
        document.addEventListener('click', close);
    }, 100);
};

window.AutomationProperty._collectStructuredVars = function(filterType, currentNodeId) {
    var result = {};
    if (!AutomationCore.lgGraphObj) return result;
    var nodes = AutomationCore.lgGraphObj._nodes || [];
    var connections = AutomationCore.getConnections ? AutomationCore.getConnections() : [];
    var upstreamNodeIds = new Set();
    if (currentNodeId) {
        for (var c = 0; c < connections.length; c++) {
            var conn = connections[c];
            if (conn.target_id === currentNodeId) {
                upstreamNodeIds.add(conn.origin_id);
            }
        }
    }
    var typeLabels = {number: '数字', string: '文本', boolean: '布尔'};
    for (var i = 0; i < nodes.length; i++) {
        var node = nodes[i];
        var nodeId = node.id;
        var defKey = node._defKey || node.type || '';
        var isUpstream = upstreamNodeIds.has(nodeId);
        var isGlobal = (defKey.indexOf('var_set') >= 0);
        var isBookmark = (defKey === 'utility/bookmark');
        var nodeLabel = (node.title || defKey) + ' #' + node.id;
        var nodeVars = [];
        if (defKey.indexOf('var_set') >= 0) {
            try {
                var multiVars = JSON.parse(node.properties.vars_json || '[]');
                if (Array.isArray(multiVars)) {
                    for (var mi = 0; mi < multiVars.length; mi++) {
                        var mv = multiVars[mi];
                        if (mv && mv.name) {
                            var mvType = mv.type || 'string';
                            if (!filterType || mvType === filterType) {
                                nodeVars.push({name: mv.name, ref: mv.name, type: mvType, typeLabel: typeLabels[mvType] || mvType, isGlobal: true});
                            }
                        }
                    }
                }
            } catch(e) {}
        }
        if (defKey.indexOf('loop_count') >= 0 && node.properties.counter_var) {
            if (!filterType || filterType === 'number') {
                nodeVars.push({name: node.properties.counter_var, ref: node.properties.counter_var, type: 'number', typeLabel: '数字', isGlobal: true});
            }
        }
        if (defKey.indexOf('check_') >= 0 && defKey.indexOf('check_image') < 0 && defKey.indexOf('check_ocr') < 0 && defKey.indexOf('check_screen') < 0) {
            if (isUpstream || isGlobal) {
                var outputs = (AutomationNodes.getNodeDef(defKey) || {}).outputs || [];
                for (var j = 0; j < outputs.length; j++) {
                    var out = outputs[j];
                    if (out.type === 'flow') continue;
                    if (filterType && out.type !== filterType && out.type !== 'any') continue;
                    var outRef = node.id + '.' + out.name;
                    nodeVars.push({name: out.name, ref: outRef, type: out.type, typeLabel: typeLabels[out.type] || out.type, isGlobal: false});
                }
            }
            if (node.properties.store_var) {
                var sType = defKey.indexOf('check_digits') >= 0 ? 'number' : 'string';
                if (!filterType || sType === filterType) {
                    nodeVars.push({name: node.properties.store_var, ref: node.properties.store_var, type: sType, typeLabel: typeLabels[sType] || sType, isGlobal: true});
                }
            }
        }
        if (defKey === 'utility/bookmark' && node.properties.name) {
            var bmName = node.properties.name;
            var bmFields = [
                {key: 'x', type: 'number'}, {key: 'y', type: 'number'},
                {key: 'w', type: 'number'}, {key: 'h', type: 'number'}
            ];
            for (var k = 0; k < bmFields.length; k++) {
                if (!filterType || bmFields[k].type === filterType) {
                    nodeVars.push({name: bmName + '.' + bmFields[k].key, ref: bmName + '.' + bmFields[k].key, type: bmFields[k].type, typeLabel: typeLabels[bmFields[k].type], isGlobal: true});
                }
            }
        }
        if (defKey.indexOf('const_') >= 0) {
            var cType = defKey.indexOf('number') >= 0 ? 'number' : defKey.indexOf('bool') >= 0 ? 'boolean' : 'string';
            if (!filterType || cType === filterType) {
                nodeVars.push({name: 'value', ref: node.id + '.value', type: cType, typeLabel: typeLabels[cType] || cType, isGlobal: isUpstream || isGlobal});
            }
        }
        if (defKey.indexOf('var_math') >= 0) {
            if (isUpstream || isGlobal) {
                if (!filterType || filterType === 'number') {
                    nodeVars.push({name: 'result', ref: node.id + '.result', type: 'number', typeLabel: '数字', isGlobal: false});
                }
            }
        }
        if (defKey.indexOf('var_string') >= 0) {
            if (isUpstream || isGlobal) {
                if (!filterType || filterType === 'string') {
                    nodeVars.push({name: 'result', ref: node.id + '.result', type: 'string', typeLabel: '文本', isGlobal: false});
                }
            }
        }
        if (defKey.indexOf('var_convert') >= 0) {
            if (isUpstream || isGlobal) {
                var convertType = node.properties.to_type || 'number';
                if (!filterType || convertType === filterType) {
                    nodeVars.push({name: 'result', ref: node.id + '.result', type: convertType, typeLabel: typeLabels[convertType] || convertType, isGlobal: false});
                }
            }
        }
        if (defKey.indexOf('var_compare') >= 0) {
            if (isUpstream || isGlobal) {
                if (!filterType || filterType === 'boolean') {
                    nodeVars.push({name: 'result', ref: node.id + '.result', type: 'boolean', typeLabel: '布尔', isGlobal: false});
                }
            }
        }
        if (defKey.indexOf('check_image') >= 0) {
            if (isUpstream || isGlobal) {
                if (!filterType || filterType === 'boolean') {
                    nodeVars.push({name: 'result', ref: node.id + '.result', type: 'boolean', typeLabel: '布尔', isGlobal: false});
                }
                if (!filterType || filterType === 'number') {
                    nodeVars.push({name: 'match_x', ref: node.id + '.match_x', type: 'number', typeLabel: '数字', isGlobal: false});
                    nodeVars.push({name: 'match_y', ref: node.id + '.match_y', type: 'number', typeLabel: '数字', isGlobal: false});
                }
            }
            if (node.properties.store_var) {
                if (!filterType || filterType === 'string') {
                    nodeVars.push({name: node.properties.store_var, ref: node.properties.store_var, type: 'string', typeLabel: '文本', isGlobal: true});
                }
            }
        }
        if (defKey.indexOf('check_ocr') >= 0) {
            if (isUpstream || isGlobal) {
                if (!filterType || filterType === 'boolean') {
                    nodeVars.push({name: 'result', ref: node.id + '.result', type: 'boolean', typeLabel: '布尔', isGlobal: false});
                }
                if (!filterType || filterType === 'string') {
                    nodeVars.push({name: 'text', ref: node.id + '.text', type: 'string', typeLabel: '文本', isGlobal: false});
                }
                if (!filterType || filterType === 'number') {
                    nodeVars.push({name: 'number', ref: node.id + '.number', type: 'number', typeLabel: '数字', isGlobal: false});
                }
            }
            if (node.properties.store_var) {
                var ocrStoreType = 'string';
                if (!filterType || ocrStoreType === filterType) {
                    nodeVars.push({name: node.properties.store_var, ref: node.properties.store_var, type: ocrStoreType, typeLabel: typeLabels[ocrStoreType] || ocrStoreType, isGlobal: true});
                }
            }
            if (node.properties.store_number) {
                if (!filterType || filterType === 'number') {
                    nodeVars.push({name: node.properties.store_number, ref: node.properties.store_number, type: 'number', typeLabel: '数字', isGlobal: true});
                }
            }
        }
        if (defKey.indexOf('check_screen') >= 0) {
            if (isUpstream || isGlobal) {
                if (!filterType || filterType === 'boolean') {
                    nodeVars.push({name: 'result', ref: node.id + '.result', type: 'boolean', typeLabel: '布尔', isGlobal: false});
                }
            }
        }
        if (defKey.indexOf('monitor_') >= 0) {
            if (node.properties.store_var) {
                var monStoreType = defKey.indexOf('ocr') >= 0 ? 'string' : 'boolean';
                if (!filterType || monStoreType === filterType) {
                    nodeVars.push({name: node.properties.store_var, ref: node.properties.store_var, type: monStoreType, typeLabel: typeLabels[monStoreType] || monStoreType, isGlobal: true});
                }
            }
            if (node.properties.store_number) {
                if (!filterType || filterType === 'number') {
                    nodeVars.push({name: node.properties.store_number, ref: node.properties.store_number, type: 'number', typeLabel: '数字', isGlobal: true});
                }
            }
        }
        if (defKey.indexOf('preset_read_text') >= 0) {
            if (isUpstream || isGlobal) {
                if (!filterType || filterType === 'string') {
                    nodeVars.push({name: 'text', ref: node.id + '.text', type: 'string', typeLabel: '文本', isGlobal: false});
                }
            }
            if (node.properties.store_var) {
                if (!filterType || filterType === 'string') {
                    nodeVars.push({name: node.properties.store_var, ref: node.properties.store_var, type: 'string', typeLabel: '文本', isGlobal: true});
                }
            }
        }
        if (defKey.indexOf('utility/math_op') >= 0 || defKey.indexOf('utility/math_func') >= 0) {
            if (isUpstream || isGlobal) {
                if (!filterType || filterType === 'number') {
                    nodeVars.push({name: 'result', ref: node.id + '.result', type: 'number', typeLabel: '数字', isGlobal: false});
                }
            }
        }
        if (defKey.indexOf('utility/logic_op') >= 0 || defKey.indexOf('utility/compare') >= 0) {
            if (isUpstream || isGlobal) {
                if (!filterType || filterType === 'boolean') {
                    nodeVars.push({name: 'result', ref: node.id + '.result', type: 'boolean', typeLabel: '布尔', isGlobal: false});
                }
            }
        }
        if (defKey.indexOf('utility/string_op') >= 0) {
            if (isUpstream || isGlobal) {
                if (!filterType || filterType === 'string') {
                    nodeVars.push({name: 'result', ref: node.id + '.result', type: 'string', typeLabel: '文本', isGlobal: false});
                }
            }
        }
        if (defKey.indexOf('utility/condition') >= 0) {
            if (isUpstream || isGlobal) {
                nodeVars.push({name: 'result', ref: node.id + '.result', type: 'any', typeLabel: '任意', isGlobal: false});
            }
        }
        if (node.properties && node.properties.store_hwnd_var) {
            if (!filterType || filterType === 'string') {
                nodeVars.push({name: node.properties.store_hwnd_var, ref: node.properties.store_hwnd_var, type: 'string', typeLabel: '句柄', isGlobal: true});
            }
        }
        if (nodeVars.length > 0) {
            result[nodeLabel] = nodeVars;
        }
    }
    return result;
};
