'use strict';

window.AutomationProperty._bindEvents = function(container, node, schema) {
    var self = this;
    var _propDirty = false;

    function _markPropDirty() { _propDirty = true; }
    function _flushPropUndo() {
        if (_propDirty && window.AutomationApp && window.AutomationApp.undoPush) {
            window.AutomationApp.undoPush();
            _propDirty = false;
        }
        if (window.AutomationApp && window.AutomationApp.refreshVarPanel) {
            window.AutomationApp.refreshVarPanel();
        }
    }
    function _syncInlineField(key, value) {
        if (node._domEl) {
            var field = node._domEl.querySelector('.nf[data-key="' + key + '"]');
            if (field) {
                if (field.tagName === 'SELECT') {
                    field.value = value;
                } else if (field.tagName === 'LABEL') {
                    var cb = field.querySelector('input[type="checkbox"]');
                    if (cb) cb.checked = (value === true || value === 'true');
                } else if (field.type === 'checkbox') {
                    field.checked = (value === true || value === 'true');
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
                    console.log('[VAR_LIST] _bindEvents._syncInlineField var_list node=' + node.id + ' key=' + key + ' -> calling _refreshNodeDOM');
                    if (window.AutomationCore && window.AutomationCore._refreshNodeDOM) {
                        window.AutomationCore._refreshNodeDOM(node);
                    }
                } else if (field.tagName === 'SPAN') {
                    // 只读内联字段（stage_list / stage_ref / region）
                    if (window.AutomationCore && window.AutomationCore._refreshNodeDOM) {
                        window.AutomationCore._refreshNodeDOM(node);
                    }
                } else {
                    field.value = value;
                }
            }
        }
    }

    container.querySelectorAll('select[data-key]:not([data-type="bool"])').forEach(function(sel) {
        sel.addEventListener('change', function() {
            var key = sel.dataset.key;
            node.properties[key] = sel.value;
            _syncInlineField(key, sel.value);
            _markPropDirty();
            if (window.AutomationCore && window.AutomationCore._notifyGraphChange) {
                window.AutomationCore._notifyGraphChange();
            }
            if (key === 'mode' || key === 'capture_mode' || key === 'check_mode' || key === 'find_mode' || key === 'close_mode' || key === 'click_type' || key === 'auto_stop') {
                _flushPropUndo();
                self.render(node);
                if (window.AutomationCore && window.AutomationCore._refreshNodeDOM) {
                    window.AutomationCore._refreshNodeDOM(node);
                }
            } else {
                _flushPropUndo();
                self._checkShowWhenChanges(node);
                for (var _sk in schema) {
                    if (schema[_sk].descriptionMapCond === sel.dataset.key) {
                        self.render(node);
                        break;
                    }
                }
            }
        });
        sel.addEventListener('blur', _flushPropUndo);
    });

    container.querySelectorAll('input[data-type="number"]').forEach(function(inp) {
        inp.addEventListener('input', function() {
            var key = inp.dataset.key;
            var currentVal = inp.value || '';
            var isVarRefNow = currentVal.indexOf('${') === 0 && currentVal.charAt(currentVal.length - 1) === '}';
            if (isVarRefNow) {
                node.properties[key] = currentVal;
                inp.dataset.rawValue = currentVal;
                inp.classList.add('var-input');
            } else {
                var rawVal = inp.dataset.rawValue || '';
                var wasVarRef = typeof rawVal === 'string' && rawVal.indexOf('${') === 0 && rawVal.charAt(rawVal.length - 1) === '}';
                if (wasVarRef) {
                    if (currentVal === '') {
                        node.properties[key] = '';
                        inp.dataset.rawValue = '';
                    } else {
                        node.properties[key] = '${' + currentVal + '}';
                        inp.dataset.rawValue = '${' + currentVal + '}';
                    }
                } else {
                    var numVal = parseFloat(currentVal) || 0;
                    node.properties[key] = numVal;
                    inp.dataset.rawValue = currentVal;
                    inp.classList.remove('var-input');
                }
            }
            _syncInlineField(key, node.properties[key]);
            _markPropDirty();
            if (window.AutomationCore && window.AutomationCore._notifyGraphChange) {
                window.AutomationCore._notifyGraphChange();
            }
        });
        inp.addEventListener('blur', function() {
            _flushPropUndo();
            self._checkShowWhenChanges(node);
        });
    });

    container.querySelectorAll('input[data-type="region"]').forEach(function(inp) {
        inp.addEventListener('input', function() {
            var key = inp.dataset.key;
            var idx = parseInt(inp.dataset.index);
            if (!Array.isArray(node.properties[key])) node.properties[key] = [0,0,10,10];
            var numVal = parseFloat(inp.value) || 0;
            node.properties[key][idx] = numVal;
            _syncInlineField(key, node.properties[key]);
            _markPropDirty();
            if (window.AutomationCore && window.AutomationCore._notifyGraphChange) {
                window.AutomationCore._notifyGraphChange();
            }
        });
        inp.addEventListener('blur', _flushPropUndo);
    });

    container.querySelectorAll('input[data-type="region-varref"]').forEach(function(inp) {
        inp.addEventListener('input', function() {
            var key = inp.dataset.key;
            var currentVal = inp.value || '';
            if (currentVal === '') {
                node.properties[key] = '';
                inp.dataset.rawValue = '';
            } else {
                node.properties[key] = '${' + currentVal + '}';
                inp.dataset.rawValue = '${' + currentVal + '}';
            }
            _syncInlineField(key, node.properties[key]);
            _markPropDirty();
        });
        inp.addEventListener('blur', _flushPropUndo);
    });

    container.querySelectorAll('input[data-type="string"]').forEach(function(inp) {
        inp.addEventListener('input', function() {
            var key = inp.dataset.key;
            var currentVal = inp.value || '';
            var isVarRefNow = currentVal.indexOf('${') === 0 && currentVal.charAt(currentVal.length - 1) === '}';
            if (isVarRefNow) {
                node.properties[key] = currentVal;
                inp.dataset.rawValue = currentVal;
                inp.classList.add('var-input');
            } else {
                var rawVal = inp.dataset.rawValue || '';
                var wasVarRef = typeof rawVal === 'string' && rawVal.indexOf('${') === 0 && rawVal.charAt(rawVal.length - 1) === '}';
                if (wasVarRef) {
                    if (currentVal === '') {
                        node.properties[key] = '';
                        inp.dataset.rawValue = '';
                    } else {
                        node.properties[key] = '${' + currentVal + '}';
                        inp.dataset.rawValue = '${' + currentVal + '}';
                    }
                } else {
                    node.properties[key] = currentVal;
                    inp.dataset.rawValue = currentVal;
                    inp.classList.remove('var-input');
                }
            }
            _syncInlineField(key, node.properties[key]);
            _markPropDirty();
            self._checkVarSyntax(inp);
            var nodeRefSel = container.querySelector('select[data-key="' + key + '"][data-type="nodeRef"]');
            if (nodeRefSel) {
                nodeRefSel.value = node.properties[key];
            }
        });
        inp.addEventListener('focus', function() {
            self._checkVarSyntax(inp);
        });
        inp.addEventListener('blur', function() {
            _flushPropUndo();
            self._hideVarHint(inp);
        });
        inp.addEventListener('keydown', function(e) {
            self._handleVarAutocomplete(e, inp, node);
        });
    });

    container.querySelectorAll('textarea[data-type="string"]').forEach(function(inp) {
        inp.addEventListener('input', function() {
            var key = inp.dataset.key;
            node.properties[key] = inp.value;
            inp.dataset.rawValue = inp.value;
            _syncInlineField(key, inp.value);
            _markPropDirty();
        });
        inp.addEventListener('blur', _flushPropUndo);
    });

    container.querySelectorAll('input[data-type="color"]').forEach(function(inp) {
        inp.addEventListener('input', function() {
            node.properties[inp.dataset.key] = inp.value;
            _syncInlineField(inp.dataset.key, inp.value);
            var textInput = container.querySelector('input[data-type="color-text"][data-key="' + inp.dataset.key + '"]');
            if (textInput) textInput.value = inp.value;
            _markPropDirty();
        });
        inp.addEventListener('blur', _flushPropUndo);
    });

    container.querySelectorAll('input[data-type="color-text"]').forEach(function(inp) {
        inp.addEventListener('input', function() {
            if (/^#[0-9a-fA-F]{6}$/.test(inp.value)) {
                node.properties[inp.dataset.key] = inp.value;
                _syncInlineField(inp.dataset.key, inp.value);
                var colorInput = container.querySelector('input[data-type="color"][data-key="' + inp.dataset.key + '"]');
                if (colorInput) colorInput.value = inp.value;
                _markPropDirty();
            }
        });
        inp.addEventListener('blur', _flushPropUndo);
    });

    container.querySelectorAll('select[data-type="bool"]').forEach(function(sel) {
        sel.addEventListener('change', function() {
            var key = sel.dataset.key;
            var boolVal = sel.value === 'true';
            node.properties[key] = boolVal;
            _syncInlineField(key, boolVal);
            _markPropDirty();
            if (window.AutomationCore && window.AutomationCore._notifyGraphChange) {
                window.AutomationCore._notifyGraphChange();
            }
            _flushPropUndo();
            self._checkShowWhenChanges(node);
        });
    });

    container.querySelectorAll('.var-list-row').forEach(function(row) {
        row.querySelectorAll('input, select').forEach(function(inp) {
            inp.addEventListener('input', function() {
                var listField = row.closest('.var-list-field');
                var listKey = listField.dataset.key;
                console.log('[VAR_LIST] _bindEvents var-list input node=' + node.id + ' key=' + listKey + ' subkey=' + (inp.dataset.subkey || ''));
                var items = [];
                listField.querySelectorAll('.var-list-row').forEach(function(r) {
                    var nameInput = r.querySelector('[data-subkey="name"]');
                    var valueInput = r.querySelector('[data-subkey="value"]');
                    var typeSelect = r.querySelector('[data-subkey="type"]');
                    var rawVal = valueInput ? (valueInput.dataset.rawValue || valueInput.value) : '';
                    var actualVal = rawVal;
                    if (valueInput) {
                        var currentDisplayVal = valueInput.value || '';
                        var isVarRefNow = currentDisplayVal.indexOf('${') === 0 && currentDisplayVal.charAt(currentDisplayVal.length - 1) === '}';
                        if (isVarRefNow) {
                            actualVal = currentDisplayVal;
                            valueInput.dataset.rawValue = currentDisplayVal;
                            valueInput.classList.add('var-input');
                        } else {
                            var wasVarRef = typeof rawVal === 'string' && rawVal.indexOf('${') === 0 && rawVal.charAt(rawVal.length - 1) === '}';
                            if (wasVarRef) {
                                actualVal = '${' + currentDisplayVal + '}';
                                valueInput.dataset.rawValue = actualVal;
                            } else {
                                actualVal = currentDisplayVal;
                                valueInput.dataset.rawValue = currentDisplayVal;
                                valueInput.classList.remove('var-input');
                            }
                        }
                    }
                    items.push({
                        name: nameInput ? nameInput.value : '',
                        value: actualVal,
                        type: typeSelect ? typeSelect.value : 'string'
                    });
                });
                node.properties[listKey] = JSON.stringify(items);
                _syncInlineField(listKey, JSON.stringify(items));
                _markPropDirty();
            });
            inp.addEventListener('blur', _flushPropUndo);
        });
    });

    container.querySelectorAll('.stage-list-row input[data-subkey="stage"]').forEach(function(inp) {
        inp.addEventListener('input', function() {
            var listField = inp.closest('.stage-list-field');
            if (!listField) return;
            var listKey = listField.dataset.key;
            var stages = [];
            listField.querySelectorAll('.stage-list-row').forEach(function(r) {
                var t = r.querySelector('[data-subkey="stage"]');
                if (t && t.value.trim()) stages.push(t.value.trim());
            });
            node.properties[listKey] = stages.join('→');
            _syncInlineField(listKey, node.properties[listKey]);
            _markPropDirty();
            if (window.AutomationCore && window.AutomationCore._notifyGraphChange) {
                window.AutomationCore._notifyGraphChange();
            }
        });
        inp.addEventListener('blur', function() {
            _flushPropUndo();
            // 阶段名变化后刷新「失败回退」下拉项
            self.render(node);
        });
    });

    container.querySelectorAll('select[data-type="stageRef"]').forEach(function(sel) {
        sel.addEventListener('change', function() {
            var key = sel.dataset.key;
            node.properties[key] = sel.value;
            _syncInlineField(key, sel.value);
            _markPropDirty();
            if (window.AutomationCore && window.AutomationCore._notifyGraphChange) {
                window.AutomationCore._notifyGraphChange();
            }
            _flushPropUndo();
        });
    });

    container.querySelectorAll('input[data-type="affinity_enabled"]').forEach(function(inp) {
        inp.addEventListener('change', function() {
            var key = inp.dataset.key;
            var cur = node.properties[key];
            if (typeof cur === 'string') { try { cur = JSON.parse(cur || '{}'); } catch(e) { cur = {}; } }
            if (!cur || typeof cur !== 'object') cur = {};
            cur.enabled = inp.checked;
            node.properties[key] = JSON.stringify(cur);
            _markPropDirty();
            _flushPropUndo();
        });
    });

    container.querySelectorAll('input[data-type="affinity_core"]').forEach(function(inp) {
        inp.addEventListener('input', function() {
            var key = inp.dataset.key;
            var cur = node.properties[key];
            if (typeof cur === 'string') { try { cur = JSON.parse(cur || '{}'); } catch(e) { cur = {}; } }
            if (!cur || typeof cur !== 'object') cur = {};
            cur.core = parseInt(inp.value) || -1;
            node.properties[key] = JSON.stringify(cur);
            _markPropDirty();
        });
        inp.addEventListener('blur', _flushPropUndo);
    });

    container.querySelectorAll('select[data-type="nodeRef"]').forEach(function(sel) {
        sel.addEventListener('change', function() {
            var key = sel.dataset.key;
            node.properties[key] = sel.value;
            var textInput = container.querySelector('input[data-key="' + key + '"][data-type="string"]');
            if (textInput) {
                textInput.value = sel.value;
                textInput.dataset.rawValue = sel.value;
            }
            _syncInlineField(key, sel.value);
            _markPropDirty();
            _flushPropUndo();
        });
    });
};
