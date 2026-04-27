'use strict';

    var ACTION_TYPES = [
        { type: 'wait', label: '等待', params: ['duration'] },
        { type: 'move_to', label: '移动鼠标', params: ['x', 'y'] },
        { type: 'left_click', label: '左键点击', params: [] },
        { type: 'right_click', label: '右键点击', params: [] },
        { type: 'middle_click', label: '中键点击', params: [] },
        { type: 'left_down', label: '左键按下', params: [] },
        { type: 'left_up', label: '左键释放', params: [] },
        { type: 'right_down', label: '右键按下', params: [] },
        { type: 'right_up', label: '右键释放', params: [] },
        { type: 'scroll', label: '滚轮', params: ['delta'] },
        { type: 'key_press', label: '按键按下', params: ['key'] },
        { type: 'key_release', label: '按键释放', params: ['key'] },
        { type: 'key_type', label: '输入文本', params: ['text'] },
    ];

    function normalizeAction(raw) {
        if (Array.isArray(raw)) {
            return { type: raw[0] || 'wait', params: raw.slice(1) };
        }
        if (typeof raw === 'object' && raw !== null) {
            return { type: raw.type || 'wait', params: raw.params || [] };
        }
        return { type: 'wait', params: [] };
    }

    function actionToRaw(action) {
        var arr = [action.type];
        for (var i = 0; i < action.params.length; i++) {
            arr.push(action.params[i]);
        }
        return arr;
    }

    function getActionLabel(action) {
        var norm = normalizeAction(action);
        if (window.MacroUtils && typeof MacroUtils.formatActionLabel === 'function') {
            var raw = actionToRaw(norm);
            var label = MacroUtils.formatActionLabel(raw);
            if (label && label !== '???' && label !== norm.type) return label;
        }
        for (var i = 0; i < ACTION_TYPES.length; i++) {
            if (ACTION_TYPES[i].type === norm.type) {
                var lbl = ACTION_TYPES[i].label;
                if (norm.params.length > 0) {
                    lbl += ' (' + norm.params.join(', ') + ')';
                }
                return lbl;
            }
        }
        return norm.type + ' (' + norm.params.join(', ') + ')';
    }

    window.AutomationBlockEditor = {
        _localRows: [],
        _targetNode: null,
        _bodyContainer: null,

        open: function(node) {
            if (!node) return;
            this._targetNode = node;
            this._localRows = Array.isArray(node.properties.actions)
                ? node.properties.actions.map(function(a) { return actionToRaw(normalizeAction(a)); })
                : [];

            var existing = document.getElementById('block-editor-modal');
            if (existing) existing.remove();

            var modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.id = 'block-editor-modal';

            var content = document.createElement('div');
            content.className = 'modal-content';
            content.style.width = '70%';
            content.style.maxHeight = '80vh';

            var header = document.createElement('div');
            header.className = 'modal-header';
            var pathLabel = node.properties.path || '未选择文件';
            header.innerHTML = '<span><i class="fa-solid fa-pen-to-square" style="margin-right:6px"></i>编辑动作块: ' + pathLabel + '</span>';
            var closeBtn = document.createElement('button');
            closeBtn.className = 'modal-close';
            closeBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
            closeBtn.addEventListener('click', function() { modal.remove(); });
            header.appendChild(closeBtn);
            content.appendChild(header);

            var body = document.createElement('div');
            body.className = 'modal-body';
            body.style.overflow = 'auto';
            body.style.maxHeight = '55vh';
            body.style.padding = '8px';
            this._bodyContainer = body;
            this._renderActionList(body);
            content.appendChild(body);

            var footer = document.createElement('div');
            footer.className = 'modal-footer';

            var addSelect = document.createElement('select');
            addSelect.style.cssText = 'padding:5px 8px;background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--rs);color:var(--txt);font-size:12px;margin-right:8px';
            for (var i = 0; i < ACTION_TYPES.length; i++) {
                var opt = document.createElement('option');
                opt.value = ACTION_TYPES[i].type;
                opt.textContent = '+ ' + ACTION_TYPES[i].label;
                addSelect.appendChild(opt);
            }
            footer.appendChild(addSelect);

            var addBtn = document.createElement('button');
            addBtn.className = 'prop-btn outline';
            addBtn.innerHTML = '<i class="fa-solid fa-plus"></i> 添加';
            addBtn.addEventListener('click', function() {
                var selType = addSelect.value;
                var newAction = [selType];
                var actionDef = null;
                for (var j = 0; j < ACTION_TYPES.length; j++) {
                    if (ACTION_TYPES[j].type === selType) { actionDef = ACTION_TYPES[j]; break; }
                }
                if (actionDef) {
                    for (var k = 0; k < actionDef.params.length; k++) {
                        newAction.push(actionDef.params[k] === 'duration' || actionDef.params[k] === 'delta' ? 100 : 0);
                    }
                }
                AutomationBlockEditor._localRows.push(newAction);
                AutomationBlockEditor._renderActionList(AutomationBlockEditor._bodyContainer);
            });
            footer.appendChild(addBtn);

            var spacer = document.createElement('span');
            spacer.style.flex = '1';
            footer.appendChild(spacer);

            var saveBtn = document.createElement('button');
            saveBtn.className = 'prop-btn accent-outline';
            saveBtn.innerHTML = '<i class="fa-solid fa-check"></i> 保存到节点';
            saveBtn.addEventListener('click', function() {
                AutomationBlockEditor._targetNode.properties.actions = AutomationBlockEditor._localRows.slice();
                if (window.AutomationProperty && AutomationProperty._currentNode === AutomationBlockEditor._targetNode) {
                    AutomationProperty.render(AutomationBlockEditor._targetNode);
                }
                if (window._autoEditor) window._autoEditor.showToast('动作块已保存到节点', 'ok');
                modal.remove();
            });
            footer.appendChild(saveBtn);

            var cancelBtn = document.createElement('button');
            cancelBtn.className = 'prop-btn outline';
            cancelBtn.textContent = '取消';
            cancelBtn.addEventListener('click', function() { modal.remove(); });
            footer.appendChild(cancelBtn);

            content.appendChild(footer);
            modal.appendChild(content);

            modal.addEventListener('click', function(e) {
                if (e.target === modal) modal.remove();
            });

            document.body.appendChild(modal);
        },

        _renderActionList: function(container) {
            container.innerHTML = '';

            if (this._localRows.length === 0) {
                var emptyEl = document.createElement('div');
                emptyEl.style.cssText = 'text-align:center;padding:40px 20px;color:var(--txt3);font-size:13px';
                emptyEl.innerHTML = '<i class="fa-solid fa-list" style="font-size:24px;opacity:0.3;display:block;margin-bottom:8px"></i>暂无动作，点击"添加"按钮创建';
                container.appendChild(emptyEl);
                return;
            }

            var table = document.createElement('div');
            table.style.cssText = 'display:flex;flex-direction:column;gap:4px';

            for (var i = 0; i < this._localRows.length; i++) {
                var row = this._localRows[i];
                var norm = normalizeAction(row);
                var rowEl = document.createElement('div');
                rowEl.style.cssText = 'display:flex;align-items:center;gap:8px;padding:6px 10px;background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--rs)';

                var idxEl = document.createElement('span');
                idxEl.style.cssText = 'font-family:var(--fmo);font-size:11px;color:var(--txt3);min-width:24px;text-align:right';
                idxEl.textContent = (i + 1) + '.';
                rowEl.appendChild(idxEl);

                var typeEl = document.createElement('span');
                typeEl.style.cssText = 'font-size:12px;color:var(--txt);flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis';
                typeEl.textContent = getActionLabel(row);
                rowEl.appendChild(typeEl);

                var editBtn = document.createElement('button');
                editBtn.style.cssText = 'padding:2px 6px;font-size:11px;color:var(--txt3);background:none;border:1px solid var(--border);border-radius:var(--rs);cursor:pointer';
                editBtn.textContent = '编辑';
                editBtn.title = '编辑动作参数';
                (function(idx, r) {
                    editBtn.addEventListener('click', function() {
                        AutomationBlockEditor._editAction(idx, r);
                    });
                })(i, row);
                rowEl.appendChild(editBtn);

                var upBtn = document.createElement('button');
                upBtn.style.cssText = 'padding:2px 6px;font-size:11px;color:var(--txt3);background:none;border:1px solid var(--border);border-radius:var(--rs);cursor:pointer';
                upBtn.innerHTML = '<i class="fa-solid fa-chevron-up"></i>';
                upBtn.disabled = (i === 0);
                upBtn.style.opacity = (i === 0) ? '0.3' : '1';
                (function(idx) {
                    upBtn.addEventListener('click', function() {
                        if (idx > 0) {
                            var tmp = AutomationBlockEditor._localRows[idx];
                            AutomationBlockEditor._localRows[idx] = AutomationBlockEditor._localRows[idx - 1];
                            AutomationBlockEditor._localRows[idx - 1] = tmp;
                            AutomationBlockEditor._renderActionList(AutomationBlockEditor._bodyContainer);
                        }
                    });
                })(i);
                rowEl.appendChild(upBtn);

                var downBtn = document.createElement('button');
                downBtn.style.cssText = 'padding:2px 6px;font-size:11px;color:var(--txt3);background:none;border:1px solid var(--border);border-radius:var(--rs);cursor:pointer';
                downBtn.innerHTML = '<i class="fa-solid fa-chevron-down"></i>';
                downBtn.disabled = (i === AutomationBlockEditor._localRows.length - 1);
                downBtn.style.opacity = (i === AutomationBlockEditor._localRows.length - 1) ? '0.3' : '1';
                (function(idx) {
                    downBtn.addEventListener('click', function() {
                        if (idx < AutomationBlockEditor._localRows.length - 1) {
                            var tmp = AutomationBlockEditor._localRows[idx];
                            AutomationBlockEditor._localRows[idx] = AutomationBlockEditor._localRows[idx + 1];
                            AutomationBlockEditor._localRows[idx + 1] = tmp;
                            AutomationBlockEditor._renderActionList(AutomationBlockEditor._bodyContainer);
                        }
                    });
                })(i);
                rowEl.appendChild(downBtn);

                var delBtn = document.createElement('button');
                delBtn.style.cssText = 'padding:2px 6px;font-size:11px;color:var(--red);background:none;border:1px solid rgba(248,113,113,.3);border-radius:var(--rs);cursor:pointer';
                delBtn.innerHTML = '<i class="fa-solid fa-trash-can"></i>';
                (function(idx) {
                    delBtn.addEventListener('click', function() {
                        AutomationBlockEditor._localRows.splice(idx, 1);
                        AutomationBlockEditor._renderActionList(AutomationBlockEditor._bodyContainer);
                    });
                })(i);
                rowEl.appendChild(delBtn);

                table.appendChild(rowEl);
            }

            container.appendChild(table);

            var countEl = document.createElement('div');
            countEl.style.cssText = 'text-align:right;padding:8px 4px 0;font-size:11px;color:var(--txt3);font-family:var(--fmo)';
            countEl.textContent = '共 ' + this._localRows.length + ' 个动作';
            container.appendChild(countEl);
        },

        _editAction: function(idx, currentRow) {
            var norm = normalizeAction(currentRow);
            var actionDef = null;
            for (var i = 0; i < ACTION_TYPES.length; i++) {
                if (ACTION_TYPES[i].type === norm.type) { actionDef = ACTION_TYPES[i]; break; }
            }
            if (!actionDef) return;

            var modal = document.createElement('div');
            modal.className = 'modal-overlay';

            var content = document.createElement('div');
            content.className = 'modal-content';
            content.style.width = '400px';

            var header = document.createElement('div');
            header.className = 'modal-header';
            header.innerHTML = '<span>编辑动作 #' + (idx + 1) + ': ' + actionDef.label + '</span>';
            var closeBtn = document.createElement('button');
            closeBtn.className = 'modal-close';
            closeBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
            closeBtn.addEventListener('click', function() { modal.remove(); });
            header.appendChild(closeBtn);
            content.appendChild(header);

            var body = document.createElement('div');
            body.className = 'modal-body';

            var typeSelect = document.createElement('select');
            typeSelect.style.cssText = 'width:100%;padding:6px 8px;margin-bottom:12px;background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--rs);color:var(--txt);font-size:12px';
            for (var j = 0; j < ACTION_TYPES.length; j++) {
                var opt = document.createElement('option');
                opt.value = ACTION_TYPES[j].type;
                opt.textContent = ACTION_TYPES[j].label;
                if (ACTION_TYPES[j].type === norm.type) opt.selected = true;
                typeSelect.appendChild(opt);
            }
            body.appendChild(typeSelect);

            var paramsContainer = document.createElement('div');
            paramsContainer.style.cssText = 'display:flex;flex-direction:column;gap:8px';

            function renderParams(selectedType) {
                paramsContainer.innerHTML = '';
                var def = null;
                for (var k = 0; k < ACTION_TYPES.length; k++) {
                    if (ACTION_TYPES[k].type === selectedType) { def = ACTION_TYPES[k]; break; }
                }
                if (!def) return;

                for (var p = 0; p < def.params.length; p++) {
                    var paramName = def.params[p];
                    var paramVal = norm.params[p] !== undefined ? norm.params[p] : (paramName === 'duration' || paramName === 'delta' ? 100 : 0);

                    var fieldEl = document.createElement('div');
                    fieldEl.className = 'prop-field';

                    var labelEl = document.createElement('label');
                    labelEl.className = 'prop-field-label';
                    labelEl.textContent = paramName;
                    fieldEl.appendChild(labelEl);

                    var inputEl = document.createElement('input');
                    inputEl.type = (typeof paramVal === 'number') ? 'number' : 'text';
                    inputEl.value = paramVal;
                    inputEl.dataset.paramIndex = p;
                    inputEl.style.cssText = 'width:100%;padding:5px 8px;background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--rs);color:var(--txt);font-size:12px';
                    fieldEl.appendChild(inputEl);

                    paramsContainer.appendChild(fieldEl);
                }
            }

            renderParams(norm.type);

            typeSelect.addEventListener('change', function() {
                var newType = typeSelect.value;
                var newDef = null;
                for (var k = 0; k < ACTION_TYPES.length; k++) {
                    if (ACTION_TYPES[k].type === newType) { newDef = ACTION_TYPES[k]; break; }
                }
                norm.type = newType;
                norm.params = [];
                if (newDef) {
                    for (var p = 0; p < newDef.params.length; p++) {
                        var paramName = newDef.params[p];
                        norm.params.push(paramName === 'duration' || paramName === 'delta' ? 100 : 0);
                    }
                }
                renderParams(newType);
            });

            body.appendChild(paramsContainer);
            content.appendChild(body);

            var footer = document.createElement('div');
            footer.className = 'modal-footer';

            var okBtn = document.createElement('button');
            okBtn.className = 'prop-btn accent-outline';
            okBtn.textContent = '确定';
            okBtn.addEventListener('click', function() {
                var newType = typeSelect.value;
                var newDef = null;
                for (var k = 0; k < ACTION_TYPES.length; k++) {
                    if (ACTION_TYPES[k].type === newType) { newDef = ACTION_TYPES[k]; break; }
                }
                var newRow = [newType];
                var paramInputs = paramsContainer.querySelectorAll('input[data-param-index]');
                for (var pi = 0; pi < paramInputs.length; pi++) {
                    var inp = paramInputs[pi];
                    var val = inp.type === 'number' ? (parseFloat(inp.value) || 0) : inp.value;
                    newRow.push(val);
                }
                AutomationBlockEditor._localRows[idx] = newRow;
                AutomationBlockEditor._renderActionList(AutomationBlockEditor._bodyContainer);
                modal.remove();
            });
            footer.appendChild(okBtn);

            var cancelBtn = document.createElement('button');
            cancelBtn.className = 'prop-btn outline';
            cancelBtn.textContent = '取消';
            cancelBtn.addEventListener('click', function() { modal.remove(); });
            footer.appendChild(cancelBtn);

            content.appendChild(footer);
            modal.appendChild(content);

            modal.addEventListener('click', function(e) {
                if (e.target === modal) modal.remove();
            });

            document.body.appendChild(modal);
        },
    };

export const AutomationBlockEditor = window.AutomationBlockEditor;
