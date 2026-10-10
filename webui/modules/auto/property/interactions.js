'use strict';

window.AutomationProperty._syncNodeInlineField = function(node, key, value) {
    if (!node || !node._domEl) return;
    var field = node._domEl.querySelector('.nf[data-key="' + key + '"]');
    if (!field) return;
    if (field.tagName === 'SELECT') {
        field.value = value;
    } else if (field.tagName === 'LABEL') {
        var cb = field.querySelector('input[type="checkbox"]');
        if (cb) cb.checked = (value === true || value === 'true');
    } else if (field.type === 'checkbox') {
        field.checked = value;
    } else if (field.type === 'number') {
        field.value = value;
    } else if (field.type === 'color') {
        field.value = value;
    } else if (field.dataset.type === 'region') {
        if (Array.isArray(value)) {
            field.value = value.join(',');
        } else if (typeof value === 'string' && value.indexOf('${') === 0) {
            field.value = value;
        } else {
            field.value = value;
        }
    } else if (field.dataset.type === 'affinity') {
        var aff = value;
        if (typeof aff === 'string') { try { aff = JSON.parse(aff || '{}'); } catch(e) { aff = {}; } }
        if (aff && aff.enabled) {
            field.value = '核心' + aff.core;
        } else {
            field.value = '关闭';
        }
    } else if (field.dataset.type === 'var_list') {
        console.log('[VAR_LIST] _syncNodeInlineField var_list node=' + node.id + ' key=' + key + ' value=' + (value||'').substring(0,80) + ' -> calling _refreshNodeDOM');
        if (window.AutomationCore && window.AutomationCore._refreshNodeDOM) {
            window.AutomationCore._refreshNodeDOM(node);
        }
    } else if (field.tagName === 'SPAN') {
        // 只读内联字段（stage_list / stage_ref / region）：重建节点 DOM 以刷新文本
        if (window.AutomationCore && window.AutomationCore._refreshNodeDOM) {
            window.AutomationCore._refreshNodeDOM(node);
        }
    } else {
        field.value = value;
    }
};

window.AutomationProperty._openKeySelector = function(btn, nodeId, key) {
    var existing = document.getElementById('key-selector-popup');
    if (existing) { existing.remove(); return; }
    var commonKeys = ['Enter','Escape','Tab','Backspace','Delete','Insert','Home','End',
        'PageUp','PageDown','Up','Down','Left','Right','Space','F1','F2','F3','F4',
        'F5','F6','F7','F8','F9','F10','F11','F12',
        '0','1','2','3','4','5','6','7','8','9',
        'A','B','C','D','E','F','G','H','I','J','K','L','M',
        'N','O','P','Q','R','S','T','U','V','W','X','Y','Z'];
    var popup = document.createElement('div');
    popup.id = 'key-selector-popup';
    popup.style.cssText = 'position:fixed;z-index:10001;background:var(--bg2);border:1px solid var(--bd);border-radius:8px;padding:8px;max-height:300px;overflow-y:auto;box-shadow:0 4px 12px rgba(0,0,0,.3);width:220px;';
    var rect = btn.getBoundingClientRect();
    popup.style.top = (rect.bottom + 4) + 'px';
    popup.style.left = rect.left + 'px';
    var html = '<div style="font-size:11px;color:var(--txt2);margin-bottom:4px">按任意键捕获 或 从列表选择:</div>';
    html += '<input type="text" id="key-capture-input" placeholder="点击此处按键捕获..." style="width:100%;margin-bottom:6px;padding:4px 8px;font-size:12px;background:var(--bg1);color:var(--txt1);border:1px solid var(--bd);border-radius:4px;" readonly>';
    for (var i = 0; i < commonKeys.length; i++) {
        html += '<span class="key-item" data-key-name="' + commonKeys[i] + '" style="display:inline-block;padding:2px 6px;margin:1px;background:var(--bg1);border:1px solid var(--bd);border-radius:3px;font-size:11px;cursor:pointer;color:var(--txt1)">' + commonKeys[i] + '</span>';
    }
    popup.innerHTML = html;
    document.body.appendChild(popup);

    var self = this;
    var captureInput = document.getElementById('key-capture-input');
    captureInput.focus();
    captureInput.addEventListener('keydown', function(e) {
        e.preventDefault();
        e.stopPropagation();
        var keyName = e.key;
        if (keyName === ' ') keyName = 'Space';
        _applyKey(keyName);
    });

    popup.querySelectorAll('.key-item').forEach(function(el) {
        el.addEventListener('click', function() {
            _applyKey(el.dataset.keyName);
        });
    });

    function _applyKey(keyName) {
        var node = AutomationCore.lgGraphObj.getNodeById(nodeId);
        if (node) {
            node.properties[key] = keyName;
            var inp = document.querySelector('#prop-panel input[data-key="' + key + '"]');
            if (inp) { inp.value = keyName; inp.dataset.rawValue = keyName; }
            self._syncNodeInlineField(node, key, keyName);
        }
        popup.remove();
    }

    setTimeout(function() {
        document.addEventListener('mousedown', function _close(e) {
            if (!popup.contains(e.target)) {
                popup.remove();
                document.removeEventListener('mousedown', _close);
            }
        });
    }, 100);
};

window.AutomationProperty._checkShowWhenChanges = function(node) {
    var def = window.AutomationNodes ? AutomationNodes.getNodeDef(node._defKey || node.type) : null;
    if (!def || !def.params_schema) return;
    var schema = def.params_schema;
    var needRender = false;
    for (var key in schema) {
        if (!schema.hasOwnProperty(key)) continue;
        if (schema[key].showWhen) {
            var showNow = this._checkShowWhen(schema[key].showWhen, node.properties);
            var fieldEl = this._container ? this._container.querySelector('[data-key="' + key + '"]') : null;
            var fieldWrap = fieldEl ? fieldEl.closest('.prop-field') : null;
            var wasVisible = fieldWrap ? (fieldWrap.style.display !== 'none') : false;
            if (wasVisible !== showNow) {
                needRender = true;
                break;
            }
        }
    }
    if (needRender) {
        this.render(node);
        if (window.AutomationCore && AutomationCore._refreshNodeDOM) {
            AutomationCore._refreshNodeDOM(node);
        }
    }
};

window.AutomationProperty._checkVarSyntax = function(inp) {
    var val = inp.value || '';
    var hasVar = val.indexOf('${') !== -1;
    if (hasVar) {
        inp.style.borderColor = 'var(--node-variable)';
        inp.style.boxShadow = '0 0 0 1px var(--node-variable)';
        var varMatches = val.match(/\$\{([^}]+)\}/g);
        if (varMatches) {
            inp.title = '变量引用: ' + varMatches.join(', ');
        }
    } else {
        inp.style.borderColor = '';
        inp.style.boxShadow = '';
        inp.title = '';
    }

    var cursorPos = inp.selectionStart;
    var beforeCursor = val.substring(0, cursorPos);
    var dollarIdx = beforeCursor.lastIndexOf('${');
    if (dollarIdx !== -1 && beforeCursor.indexOf('}', dollarIdx) === -1) {
        var partial = beforeCursor.substring(dollarIdx + 2);
        if (partial.length > 0 && /^[a-zA-Z_]\w*$/.test(partial)) {
            this._showVarHint(inp, partial);
            return;
        }
    }
    this._hideVarHint(inp);
};

window.AutomationProperty._showVarHint = function(inp, partial) {
    this._hideVarHint(inp);

    var knownVars = this._collectKnownVars();
    var matches = [];
    for (var i = 0; i < knownVars.length; i++) {
        if (knownVars[i].toLowerCase().indexOf(partial.toLowerCase()) === 0) {
            matches.push(knownVars[i]);
        }
    }
    if (matches.length === 0) return;

    var hint = document.createElement('div');
    hint.className = 'var-hint-popup';
    hint.style.cssText = 'position:absolute;z-index:9000;background:var(--bg-raised);border:1px solid var(--border);border-radius:var(--r);box-shadow:var(--sh);max-height:120px;overflow-y:auto;padding:2px 0;min-width:120px';

    var rect = inp.getBoundingClientRect();
    hint.style.left = rect.left + 'px';
    hint.style.top = (rect.bottom + 2) + 'px';

    for (var j = 0; j < matches.length; j++) {
        var item = document.createElement('div');
        item.style.cssText = 'padding:4px 10px;font-size:12px;color:var(--txt2);cursor:pointer;font-family:var(--fmo)';
        item.textContent = '${' + matches[j] + '}';
        item.dataset.varName = matches[j];
        item.addEventListener('mouseenter', function() { this.style.background = 'var(--bg-hover)'; });
        item.addEventListener('mouseleave', function() { this.style.background = ''; });
        item.addEventListener('mousedown', (function(vname, input) {
            return function(e) {
                e.preventDefault();
                AutomationProperty._insertVarRef(input, vname);
            };
        })(matches[j], inp));
        hint.appendChild(item);
    }

    document.body.appendChild(hint);
    inp._varHint = hint;
};

window.AutomationProperty._hideVarHint = function(inp) {
    if (inp._varHint) {
        inp._varHint.remove();
        inp._varHint = null;
    }
};

window.AutomationProperty._handleVarAutocomplete = function(e, inp, node) {
    if (!inp._varHint) return;
    if (e.key === 'Escape') {
        this._hideVarHint(inp);
        e.preventDefault();
        return;
    }
    if (e.key === 'Enter' || e.key === 'Tab') {
        var items = inp._varHint.querySelectorAll('[data-var-name]');
        if (items.length === 1) {
            e.preventDefault();
            this._insertVarRef(inp, items[0].dataset.varName);
        }
    }
};

window.AutomationProperty._insertVarRef = function(inp, varName) {
    var val = inp.value || '';
    var cursorPos = inp.selectionStart;
    var beforeCursor = val.substring(0, cursorPos);
    var dollarIdx = beforeCursor.lastIndexOf('${');
    if (dollarIdx !== -1) {
        var after = val.substring(cursorPos);
        var newVal = val.substring(0, dollarIdx) + '${' + varName + '}' + after;
        inp.value = newVal;
        var newCursor = dollarIdx + varName.length + 3;
        inp.setSelectionRange(newCursor, newCursor);
        inp.dispatchEvent(new Event('input'));
    }
    this._hideVarHint(inp);
};

window.AutomationProperty._collectKnownVars = function() {
    var vars = [];
    var structured = this._collectStructuredVars(null, null);
    var seen = {};
    for (var groupLabel in structured) {
        if (!structured.hasOwnProperty(groupLabel)) continue;
        var groupVars = structured[groupLabel];
        for (var i = 0; i < groupVars.length; i++) {
            var v = groupVars[i];
            var key = v.ref || v.name;
            if (!seen[key]) {
                seen[key] = true;
                vars.push(v.ref || v.name);
            }
        }
    }
    var builtinNames = ['timestamp','timestamp_s','date','time','datetime','datetime_compact','random','random_int','year','month','day','hour','minute','second','weekday','pid'];
    for (var bi = 0; bi < builtinNames.length; bi++) {
        if (!seen[builtinNames[bi]]) {
            seen[builtinNames[bi]] = true;
            vars.push(builtinNames[bi]);
        }
    }
    return vars;
};

// ——— 状态机阶段列表增删/排序 ———
window.AutomationProperty._writeStageList = function(node, key, stages, pushUndo) {
    node.properties[key] = stages.join('→');
    this._syncNodeInlineField(node, key, node.properties[key]);
    if (pushUndo && window.AutomationApp && window.AutomationApp.undoPush) {
        window.AutomationApp.undoPush();
    }
    if (window.AutomationCore && window.AutomationCore._notifyGraphChange) {
        window.AutomationCore._notifyGraphChange();
    }
    this.render(node);
};

window.AutomationProperty._stageListAdd = function(btn, nodeId, key) {
    var node = AutomationCore.lgGraphObj.getNodeById(nodeId);
    if (!node) return;
    var stages = this._parseStageList(node.properties[key]);
    stages.push('阶段' + (stages.length + 1));
    this._writeStageList(node, key, stages, true);
};

window.AutomationProperty._stageListRemove = function(btn, nodeId, key, index) {
    var node = AutomationCore.lgGraphObj.getNodeById(nodeId);
    if (!node) return;
    var stages = this._parseStageList(node.properties[key]);
    if (index < 0 || index >= stages.length) return;
    stages.splice(index, 1);
    this._writeStageList(node, key, stages, true);
};

window.AutomationProperty._stageListMove = function(btn, nodeId, key, index, delta) {
    var node = AutomationCore.lgGraphObj.getNodeById(nodeId);
    if (!node) return;
    var stages = this._parseStageList(node.properties[key]);
    var target = index + delta;
    if (index < 0 || index >= stages.length || target < 0 || target >= stages.length) return;
    var tmp = stages[index];
    stages[index] = stages[target];
    stages[target] = tmp;
    this._writeStageList(node, key, stages, true);
};
