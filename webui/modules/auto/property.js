'use strict';

    function _propEscapeHtml(str) {
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    window.AutomationProperty = {
        _currentNode: null,

        render: function(node) {
            this._currentNode = node;
            var container = document.getElementById('property-panel-content');
            if (!container) return;

            if (!node) {
                container.innerHTML = '<div class="empty-hint"><i class="fa-regular fa-hand-pointer" style="gap: 14px;"></i><span>选择节点查看属性</span></div>';
                return;
            }

            var def = window.AutomationNodes ? AutomationNodes.getNodeDef(node._defKey || node.type) : null;
            var schema = def ? def.params_schema : {};

            var html = '';

            html += '<div class="prop-node-header">' +
                '<div class="prop-node-color" style="background:' + (def ? def.color : '#888') + '"></div>' +
                '<div>' +
                  '<div class="prop-node-title">' + (node.title || (def ? def.display_name : node.type)) + '</div>' +
                  '<div class="prop-node-type">' + (node._defKey || node.type) + ' #' + node.id + '</div>' +
                '</div>' +
              '</div>';

            var coordParams = [];
            var mainParams = [];
            for (var key in schema) {
                if (!schema.hasOwnProperty(key)) continue;
                var s = schema[key];
                if (s.coordRef || s.coordMode) {
                    coordParams.push([key, s]);
                } else {
                    mainParams.push([key, s]);
                }
            }

            if (coordParams.length > 0) {
                html += this._renderGroup('坐标', coordParams, node);
            }
            if (mainParams.length > 0) {
                html += this._renderGroup('参数', mainParams, node);
            }

            var defKey = node._defKey || node.type || '';
            if (defKey.indexOf('check_color') >= 0 || defKey.indexOf('check_ocr') >= 0 || defKey.indexOf('monitor_color') >= 0 || defKey.indexOf('monitor_ocr') >= 0) {
                html += '<div class="prop-group">' +
                    '<div class="prop-group-header"><i class="fa-solid fa-chevron-down arrow"></i> 实时预览</div>' +
                    '<div class="prop-group-body">' +
                      '<div class="prop-preview" id="preview-area"><span>点击预览查看结果</span></div>' +
                      '<div class="prop-btn-row">' +
                        '<button class="prop-btn accent-outline" onclick="window._autoEditor.runPreview(\'' + defKey + '\', ' + node.id + ')">' +
                          '<i class="fa-solid fa-bolt"></i> 预览' +
                        '</button>' +
                      '</div>' +
                    '</div>' +
                  '</div>';
            }

            if (defKey.indexOf('call_script') >= 0) {
                html += '<div class="prop-group">' +
                    '<div class="prop-group-header"><i class="fa-solid fa-chevron-down arrow"></i> 动作编辑</div>' +
                    '<div class="prop-group-body">' +
                      '<div class="prop-btn-row">' +
                        '<button class="prop-btn accent-outline" onclick="window.AutomationBlockEditor.open(AutomationCore.lgGraphObj.getNodeById(' + node.id + '))">' +
                          '<i class="fa-solid fa-pen"></i> 编辑动作块' +
                        '</button>' +
                      '</div>' +
                    '</div>' +
                  '</div>';
            }

            container.innerHTML = html;

            this._bindEvents(container, node, schema);

            container.querySelectorAll('.prop-group-header').forEach(function(h) {
                h.addEventListener('click', function() { this.classList.toggle('collapsed'); });
            });
        },

        renderAnnotation: function(an) {
            this._currentNode = null;
            this._currentAnnotation = an;
            this._currentGroup = null;
            var container = document.getElementById('property-panel-content');
            if (!container) return;

            var html = '';
            html += '<div class="prop-node-header">' +
                '<div class="prop-node-color" style="background:' + (an.color || '#fbbf24') + '"></div>' +
                '<div>' +
                  '<div class="prop-node-title">注释</div>' +
                  '<div class="prop-node-type">#' + an.id + '</div>' +
                '</div>' +
              '</div>';

            html += '<div class="prop-group">' +
                '<div class="prop-group-header"><i class="fa-solid fa-chevron-down arrow"></i> 内容</div>' +
                '<div class="prop-group-body">';

            html += '<div class="prop-field">' +
                '<label class="prop-field-label">文本内容</label>' +
                '<textarea data-key="text" rows="3" style="width:100%;resize:vertical;background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--rs);padding:6px 8px;color:var(--txt);font-size:12px;font-family:var(--fmo);outline:none;transition:border-color var(--t)">' + _propEscapeHtml(an.text || '') + '</textarea>' +
              '</div>';

            html += '<div class="prop-field">' +
                '<label class="prop-field-label">颜色</label>' +
                '<div style="display:flex;gap:4px;flex-wrap:wrap">';
            var presetColors = [
                { color: '#fbbf24', name: '黄色', bg: 'linear-gradient(135deg,rgba(251,191,36,.38),rgba(251,191,36,.28))' },
                { color: '#22c55e', name: '绿色', bg: 'linear-gradient(135deg,rgba(34,197,94,.38),rgba(34,197,94,.28))' },
                { color: '#3b82f6', name: '蓝色', bg: 'linear-gradient(135deg,rgba(59,130,246,.38),rgba(59,130,246,.28))' },
                { color: '#f97316', name: '橙色', bg: 'linear-gradient(135deg,rgba(249,115,22,.38),rgba(249,115,22,.28))' },
                { color: '#a855f7', name: '紫色', bg: 'linear-gradient(135deg,rgba(168,85,247,.38),rgba(168,85,247,.28))' },
                { color: '#ef4444', name: '红色', bg: 'linear-gradient(135deg,rgba(239,68,68,.38),rgba(239,68,68,.28))' },
                { color: '#06b6d4', name: '青色', bg: 'linear-gradient(135deg,rgba(6,182,212,.38),rgba(6,182,212,.28))' },
                { color: '#94a3b8', name: '灰色', bg: 'linear-gradient(135deg,rgba(148,163,184,.38),rgba(148,163,184,.28))' }
            ];
            for (var i = 0; i < presetColors.length; i++) {
                var pc = presetColors[i];
                var isActive = an.bgColor === pc.bg;
                html += '<div style="width:24px;height:24px;border-radius:4px;cursor:pointer;border:2px solid ' + (isActive ? 'var(--acc)' : 'transparent') + ';box-sizing:border-box;transition:all .15s;flex-shrink:0;background:' + pc.color + '" data-color="' + pc.color + '" data-bg="' + pc.bg + '" title="' + pc.name + '"></div>';

            }
            html += '</div></div>';

            html += '<div class="prop-field">' +
                '<label class="prop-field-label" style="display:flex;align-items:center;gap:8px">折叠<input type="checkbox" id="prop-an-collapsed" ' + (an.collapsed ? 'checked' : '') + ' style="accent-color:var(--acc);cursor:pointer"></label>' +
              '</div>';

            html += '</div></div>';

            html += '<div class="prop-group">' +
                '<div class="prop-group-header"><i class="fa-solid fa-chevron-down arrow"></i> 位置</div>' +
                '<div class="prop-group-body">';
            html += '<div class="prop-field"><label class="prop-field-label">X</label><input type="number" data-key="posX" value="' + Math.round(an.pos[0]) + '" style="width:100%"></div>';
            html += '<div class="prop-field"><label class="prop-field-label">Y</label><input type="number" data-key="posY" value="' + Math.round(an.pos[1]) + '" style="width:100%"></div>';
            html += '</div></div>';

            html += '<div style="padding:10px 14px 14px"><button class="prop-btn outline" style="width:100%;justify-content:center" onclick="if(window.AutomationCore)window.AutomationCore.removeAnnotation(' + an.id + ');if(window.AutomationProperty)AutomationProperty.render(null);"><i class="fa-solid fa-trash-can"></i> 删除注释</button></div>';

            container.innerHTML = html;

            container.querySelectorAll('.prop-group-header').forEach(function(h) {
                h.addEventListener('click', function() { this.classList.toggle('collapsed'); });
            });

            container.querySelector('textarea[data-key="text"]').addEventListener('input', function() {
                an.text = this.value;
                if (an._domEl) {
                    an._domEl.querySelector('.an-t').textContent = an.text;
                }
                AutomationCore._notifyGraphChange();
            });

            container.querySelectorAll('[data-color]').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    an.color = this.dataset.color;
                    an.bgColor = this.dataset.bg;
                    if (an._domEl) {
                        an._domEl.style.background = an.bgColor;
                    }
                    container.querySelectorAll('[data-color]').forEach(function(b) { b.style.borderColor = 'transparent'; });
                    this.style.borderColor = 'var(--acc)';
                    AutomationCore._notifyGraphChange();
                });
                if (an.bgColor === btn.dataset.bg) {
                    btn.style.borderColor = 'var(--acc)';
                }
            });

            container.querySelector('#prop-an-collapsed').addEventListener('change', function() {
                an.collapsed = this.checked;
                if (an._domEl) {
                    an._domEl.classList.toggle('collapsed', an.collapsed);
                    var toggleEl = an._domEl.querySelector('.an-toggle');
                    if (toggleEl) {
                        toggleEl.innerHTML = an.collapsed ? '<i class="fa-solid fa-expand"></i>' : '<i class="fa-solid fa-compress"></i>';
                    }
                }
                AutomationCore._notifyGraphChange();
            });

            container.querySelector('input[data-key="posX"]').addEventListener('change', function() {
                an.pos[0] = parseFloat(this.value) || 0;
                if (an._domEl) an._domEl.style.left = an.pos[0] + 'px';
                AutomationCore._notifyGraphChange();
            });
            container.querySelector('input[data-key="posY"]').addEventListener('change', function() {
                an.pos[1] = parseFloat(this.value) || 0;
                if (an._domEl) an._domEl.style.top = an.pos[1] + 'px';
                AutomationCore._notifyGraphChange();
            });
        },

        renderGroup: function(gp) {
            this._currentNode = null;
            this._currentAnnotation = null;
            this._currentGroup = gp;
            var container = document.getElementById('property-panel-content');
            if (!container) return;

            var html = '';
            html += '<div class="prop-node-header">' +
                '<div class="prop-node-color" style="background:' + (gp.color || '#3b82f6') + '"></div>' +
                '<div>' +
                  '<div class="prop-node-title">分组</div>' +
                  '<div class="prop-node-type">#' + gp.id + '</div>' +
                '</div>' +
              '</div>';

            html += '<div class="prop-group">' +
                '<div class="prop-group-header"><i class="fa-solid fa-chevron-down arrow"></i> 内容</div>' +
                '<div class="prop-group-body">';

            html += '<div class="prop-field">' +
                '<label class="prop-field-label">标题</label>' +
                '<input type="text" data-key="title" value="' + _propEscapeHtml(gp.title || '') + '" style="width:100%">' +
              '</div>';

            html += '<div class="prop-field">' +
                '<label class="prop-field-label">颜色</label>' +
                '<div style="display:flex;gap:4px;flex-wrap:wrap">';
            var presetColors = [
                { color: '#3b82f6', name: '蓝色', bg: 'rgba(59,130,246,.08)' },
                { color: '#22c55e', name: '绿色', bg: 'rgba(34,197,94,.08)' },
                { color: '#f97316', name: '橙色', bg: 'rgba(249,115,22,.08)' },
                { color: '#a855f7', name: '紫色', bg: 'rgba(168,85,247,.08)' },
                { color: '#ef4444', name: '红色', bg: 'rgba(239,68,68,.08)' },
                { color: '#eab308', name: '黄色', bg: 'rgba(234,179,8,.08)' },
                { color: '#06b6d4', name: '青色', bg: 'rgba(6,182,212,.08)' },
                { color: '#64748b', name: '灰色', bg: 'rgba(100,116,139,.08)' }
            ];
            for (var i = 0; i < presetColors.length; i++) {
                var pc = presetColors[i];
                var gIsActive = gp.bgColor === pc.bg;
                html += '<div style="width:24px;height:24px;border-radius:4px;cursor:pointer;border:2px solid ' + (gIsActive ? 'var(--acc)' : 'transparent') + ';box-sizing:border-box;transition:all .15s;flex-shrink:0;background:' + pc.color + '" data-gp-color="' + pc.color + '" data-gp-bg="' + pc.bg + '" title="' + pc.name + '"></div>';

            }
            html += '</div></div>';

            html += '</div></div>';

            html += '<div class="prop-group">' +
                '<div class="prop-group-header"><i class="fa-solid fa-chevron-down arrow"></i> 位置和大小</div>' +
                '<div class="prop-group-body">';
            html += '<div class="prop-field"><label class="prop-field-label">X</label><input type="number" data-key="posX" value="' + Math.round(gp.pos[0]) + '" style="width:100%"></div>';
            html += '<div class="prop-field"><label class="prop-field-label">Y</label><input type="number" data-key="posY" value="' + Math.round(gp.pos[1]) + '" style="width:100%"></div>';
            html += '<div class="prop-field"><label class="prop-field-label">宽度</label><input type="number" data-key="sizeW" value="' + Math.round(gp.size[0]) + '" style="width:100%"></div>';
            html += '<div class="prop-field"><label class="prop-field-label">高度</label><input type="number" data-key="sizeH" value="' + Math.round(gp.size[1]) + '" style="width:100%"></div>';
            html += '</div></div>';

            html += '<div style="padding:10px 14px 14px"><button class="prop-btn outline" style="width:100%;justify-content:center" onclick="if(window.AutomationCore)window.AutomationCore.removeGroup(' + gp.id + ');if(window.AutomationProperty)AutomationProperty.render(null);"><i class="fa-solid fa-trash-can"></i> 删除分组</button></div>';

            container.innerHTML = html;

            container.querySelectorAll('.prop-group-header').forEach(function(h) {
                h.addEventListener('click', function() { this.classList.toggle('collapsed'); });
            });

            container.querySelector('input[data-key="title"]').addEventListener('input', function() {
                gp.title = this.value;
                if (gp._domEl) {
                    gp._domEl.querySelector('.gp-t').textContent = gp.title;
                }
                AutomationCore._notifyGraphChange();
            });

            container.querySelectorAll('[data-gp-color]').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    gp.color = this.dataset.gpColor;
                    gp.bgColor = this.dataset.gpBg;
                    if (gp._domEl) {
                        gp._domEl.style.setProperty('--gp-color', gp.color);
                        gp._domEl.style.setProperty('--gp-bg', gp.bgColor);
                        gp._domEl.style.background = gp.bgColor;
                    }
                    container.querySelectorAll('[data-gp-color]').forEach(function(b) { b.style.borderColor = 'transparent'; });
                    this.style.borderColor = 'var(--acc)';
                    AutomationCore._notifyGraphChange();
                });
                if (gp.bgColor === btn.dataset.gpBg) {
                    btn.style.borderColor = 'var(--acc)';
                }
            });

            container.querySelector('input[data-key="posX"]').addEventListener('change', function() {
                gp.pos[0] = parseFloat(this.value) || 0;
                if (gp._domEl) gp._domEl.style.left = gp.pos[0] + 'px';
                AutomationCore._notifyGraphChange();
            });
            container.querySelector('input[data-key="posY"]').addEventListener('change', function() {
                gp.pos[1] = parseFloat(this.value) || 0;
                if (gp._domEl) gp._domEl.style.top = gp.pos[1] + 'px';
                AutomationCore._notifyGraphChange();
            });
            container.querySelector('input[data-key="sizeW"]').addEventListener('change', function() {
                gp.size[0] = Math.max(140, parseFloat(this.value) || 300);
                if (gp._domEl) gp._domEl.style.width = gp.size[0] + 'px';
                AutomationCore._notifyGraphChange();
            });
            container.querySelector('input[data-key="sizeH"]').addEventListener('change', function() {
                gp.size[1] = Math.max(100, parseFloat(this.value) || 200);
                if (gp._domEl) gp._domEl.style.height = gp.size[1] + 'px';
                AutomationCore._notifyGraphChange();
            });
        },

        _renderGroup: function(groupName, paramEntries, node) {
            var html = '<div class="prop-group">' +
                '<div class="prop-group-header"><i class="fa-solid fa-chevron-down arrow"></i> ' + groupName + '</div>' +
                '<div class="prop-group-body">';

            for (var i = 0; i < paramEntries.length; i++) {
                var key = paramEntries[i][0];
                var schema = paramEntries[i][1];

                if (schema.showWhen && !this._checkShowWhen(schema.showWhen, node.properties)) continue;

                var val = node.properties[key];
                if (val === undefined) val = schema.default !== undefined ? schema.default : (schema.type === 'number' ? 0 : '');
                var isVarRef = typeof val === 'string' && val.indexOf('${') === 0 && val.charAt(val.length - 1) === '}';
                var varBadge = isVarRef ? '<span class="var-badge">VAR</span>' : '';

                switch (schema.type) {
                    case 'enum':
                        html += this._renderEnumField(key, schema, val, varBadge);
                        break;
                    case 'number':
                        html += this._renderNumberField(key, schema, val, varBadge, node.properties, node);
                        break;
                    case 'string':
                        html += this._renderStringField(key, schema, val, varBadge, node);
                        break;
                    case 'bool':
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
                    default:
                        html += this._renderStringField(key, schema, val, varBadge);
                }
            }

            html += '</div></div>';
            return html;
        },

        _checkShowWhen: function(showWhen, allParams) {
            if (!showWhen) return true;
            var parts = showWhen.split('=');
            if (parts.length === 2) {
                var field = parts[0].trim();
                var values = parts[1].split(',');
                var currentVal = String(allParams[field] || '');
                for (var i = 0; i < values.length; i++) {
                    if (values[i].trim() === currentVal) return true;
                }
                return false;
            }
            return true;
        },

        _renderEnumField: function(key, schema, val, varBadge) {
            var options = (schema.options || []).map(function(o) {
                return '<option value="' + o + '"' + (val === o ? ' selected' : '') + '>' + o + '</option>';
            }).join('');
            return '<div class="prop-field">' +
                '<label class="prop-field-label">' + (schema.label || key) + ' ' + varBadge + '</label>' +
                '<select data-key="' + key + '" data-type="enum">' + options + '</select>' +
              '</div>';
        },

        _renderNumberField: function(key, schema, val, varBadge, allParams, node) {
            var step = (schema.coordRef && allParams.mode === 'relative') ? '0.01' : '1';
            var placeholder = (schema.coordRef && allParams.mode === 'relative') ? '0.0 ~ 1.0' : '';
            var desc = schema.desc ? '<span style="font-size:10px;color:var(--txt3)">' + schema.desc + '</span>' : '';
            var isVarRef = typeof val === 'string' && val.indexOf('${') === 0 && val.charAt(val.length - 1) === '}';
            var displayVal = isVarRef ? val.slice(2, -1) : (val !== null && val !== undefined ? val : schema.default || 0);
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
        },

        _renderStringField: function(key, schema, val, varBadge, node) {
            var isHwndVar = (key === 'hwnd_var');
            var hasVarBtn = schema.varRef;
            var isVarRef = typeof val === 'string' && val.indexOf('${') === 0 && val.charAt(val.length - 1) === '}';
            var displayVal = isVarRef ? val.slice(2, -1) : (val || '');
            var inputClass = isVarRef ? 'var-input' : '';
            var html = '<div class="prop-field">' +
                '<label class="prop-field-label">' + (schema.label || key) + ' ' + varBadge + '</label>';
            if (isHwndVar || hasVarBtn) {
                html += '<div style="display:flex;gap:4px">' +
                  '<input type="text" data-key="' + key + '" data-type="string" data-raw-value="' + (val || '') + '" value="' + displayVal + '" placeholder="' + (schema.placeholder || '') + '" style="flex:1" class="' + inputClass + '">';
                if (hasVarBtn) {
                    html += '<button class="prop-btn outline var-ref-btn" data-key="' + key + '" data-vartype="string" onclick="window.AutomationProperty._toggleVarSelector(this,' + node.id + ',\'' + key + '\',\'string\')" style="flex-shrink:0;padding:6px 16px" title="选择变量"><i class="fa-solid fa-dollar-sign"></i></button>';
                }
                if (isHwndVar) {
                    html += '<button class="prop-btn outline" onclick="window._autoEditor.browseWindowList(' + node.id + ',\'' + key + '\')" style="flex-shrink:0;padding:6px 16px" title="选择窗口"><i class="fa-solid fa-window-restore"></i></button>';
                }
                html += '</div>';
            } else {
                html += '<input type="text" data-key="' + key + '" data-type="string" data-raw-value="' + (val || '') + '" value="' + displayVal + '" placeholder="' + (schema.placeholder || '') + '" class="' + inputClass + '">';
            }
            html += '</div>';
            return html;
        },

        _renderBoolField: function(key, schema, val) {
            return '<div class="prop-field">' +
                '<div class="checkbox-row">' +
                  '<input type="checkbox" data-key="' + key + '" data-type="bool" id="cb_' + key + '"' + (val ? ' checked' : '') + '>' +
                  '<label for="cb_' + key + '">' + (schema.label || key) + '</label>' +
                '</div>' +
              '</div>';
        },

        _renderColorField: function(key, schema, val, varBadge) {
            var colorVal = val || '#FF0000';
            return '<div class="prop-field">' +
                '<label class="prop-field-label">' + (schema.label || key) + ' ' + varBadge + '</label>' +
                '<div style="display:flex;gap:6px;align-items:center">' +
                  '<input type="color" data-key="' + key + '" data-type="color" value="' + colorVal + '" style="width:36px;height:28px;padding:1px;cursor:pointer;border:1px solid var(--border);border-radius:var(--rs);background:var(--bg-surface)">' +
                  '<input type="text" data-key="' + key + '" data-type="color-text" value="' + colorVal + '" style="flex:1" placeholder="#RRGGBB">' +
                '</div>' +
              '</div>';
        },

        _renderRegionField: function(key, schema, val, varBadge, node) {
            var isRelative = (node.properties.mode === 'relative');
            var step = isRelative ? '0.01' : '1';
            var vals = Array.isArray(val) ? val : (schema.default || [0,0,10,10]);
            var labels = ['X', 'Y', 'W', 'H'];
            var html = '<div class="prop-field">' +
                '<label class="prop-field-label">' + (schema.label || key) + ' ' + varBadge + '</label>' +
                '<div class="region-grid">';
            for (var i = 0; i < 4; i++) {
                html += '<div class="region-cell">' +
                    '<label>' + labels[i] + '</label>' +
                    '<input type="number" data-key="' + key + '" data-type="region" data-index="' + i + '" value="' + (vals[i] || 0) + '" step="' + step + '">' +
                  '</div>';
            }
            var isVarRefVal = typeof val === 'string' && val.indexOf('${') === 0 && val.charAt(val.length - 1) === '}';
            html += '</div>';
            if (!isVarRefVal) {
                html += '<div class="prop-btn-row" style="margin-top:6px">' +
                    '<button class="prop-btn outline" onclick="window.AutomationTools.startRegionPick(' + node.id + ',\'' + key + '\')">' +
                      '<i class="fa-solid fa-crop-simple"></i> 框选区域' +
                    '</button>' +
                  '</div>';
            }
            html += '</div>';
            return html;
        },

        _renderPathField: function(key, schema, val, varBadge, node) {
            var browseType = schema.browseType || 'macro';
            var browseFn = browseType === 'template' ? 'window._autoEditor.browseTemplatePath' : 'window._autoEditor.browseMacroPath';
            var browseIcon = browseType === 'template' ? 'fa-solid fa-folder-open' : 'fa-solid fa-list';
            return '<div class="prop-field">' +
                '<label class="prop-field-label">' + (schema.label || key) + ' ' + varBadge + '</label>' +
                '<div style="display:flex;gap:4px">' +
                  '<input type="text" data-key="' + key + '" data-type="string" value="' + (val || '') + '" placeholder="' + (schema.placeholder || '') + '" style="flex:1">' +
                  '<button class="prop-btn outline" onclick="' + browseFn + '(' + node.id + ')" style="flex-shrink:0;padding:6px 16px"><i class="' + browseIcon + '"></i></button>' +
                '</div>' +
              '</div>';
        },

        _renderVarListField: function(key, schema, val, node) {
            var items = [];
            try { items = JSON.parse(val || '[]'); } catch(e) { items = []; }
            if (!Array.isArray(items)) items = [];
            var html = '<div class="prop-field var-list-field" data-key="' + key + '">' +
                '<label class="prop-field-label">' + (schema.label || key) +
                ' <button class="prop-btn outline" style="padding:2px 8px;font-size:11px" onclick="window.AutomationProperty._addVarListItem(this,' + node.id + ',\'' + key + '\')"><i class="fa-solid fa-plus"></i> 添加</button></label>';
            html += '<div class="var-list-items">';
            for (var i = 0; i < items.length; i++) {
                var item = items[i];
                html += '<div class="var-list-row" data-index="' + i + '">' +
                  '<input type="text" data-subkey="name" value="' + (item.name || '') + '" placeholder="变量名" style="width:30%">' +
                  '<input type="text" data-subkey="value" value="' + (item.value || '') + '" placeholder="值/${var}" style="width:35%">' +
                  '<select data-subkey="type" style="width:20%">' +
                    '<option value="string"' + (item.type === 'string' ? ' selected' : '') + '>文本</option>' +
                    '<option value="number"' + (item.type === 'number' ? ' selected' : '') + '>数字</option>' +
                    '<option value="boolean"' + (item.type === 'boolean' ? ' selected' : '') + '>布尔</option>' +
                  '</select>' +
                  '<button class="prop-btn outline" style="padding:2px 6px" onclick="window.AutomationProperty._removeVarListItem(this,' + node.id + ',\'' + key + '\')"><i class="fa-solid fa-xmark"></i></button>' +
                '</div>';
            }
            html += '</div></div>';
            return html;
        },

        _addVarListItem: function(btn, nodeId, key) {
            var node = AutomationCore.lgGraphObj.getNodeById(nodeId);
            if (!node) return;
            var items = [];
            try { items = JSON.parse(node.properties[key] || '[]'); } catch(e) { items = []; }
            items.push({name: '', value: '', type: 'string'});
            node.properties[key] = JSON.stringify(items);
            if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
            this.render(node);
        },

        _removeVarListItem: function(btn, nodeId, key) {
            var node = AutomationCore.lgGraphObj.getNodeById(nodeId);
            if (!node) return;
            var items = [];
            try { items = JSON.parse(node.properties[key] || '[]'); } catch(e) { items = []; }
            var row = btn.closest('.var-list-row');
            var idx = parseInt(row.dataset.index);
            items.splice(idx, 1);
            node.properties[key] = JSON.stringify(items);
            if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
            this.render(node);
        },

        _toggleVarSelector: function(btn, nodeId, key, varType) {
            var existing = document.getElementById('var-selector-popup');
            if (existing) { existing.remove(); return; }
            var structuredVars = this._collectStructuredVars(varType, nodeId);
            if (Object.keys(structuredVars).length === 0) {
                this._showToast('没有可用的' + (varType === 'number' ? '数字' : varType === 'string' ? '字符串' : '布尔') + '类型变量');
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
            var html = '<div style="padding:4px 12px;font-size:11px;color:var(--txt3,#94a3b8);font-weight:600">选择变量</div>';
            for (var nodeLabel in structuredVars) {
                var vars = structuredVars[nodeLabel];
                html += '<div style="padding:4px 12px;font-size:11px;color:var(--txt2,#cbd5e1);font-weight:600;border-bottom:1px solid var(--border,#334155)">' + nodeLabel + '</div>';
                for (var j = 0; j < vars.length; j++) {
                    var v = vars[j];
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
                    node.properties[key] = '${' + varRef + '}';
                    if (window.AutomationApp && window.AutomationApp.undoPush) window.AutomationApp.undoPush();
                    self.render(node);
                    popup.remove();
                });
            });
            setTimeout(function() {
                function close(e) { if (!popup.contains(e.target) && e.target !== btn) { popup.remove(); document.removeEventListener('click', close); } }
                document.addEventListener('click', close);
            }, 100);
        },

        _collectStructuredVars: function(filterType, currentNodeId) {
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
                if (defKey.indexOf('var_set') >= 0 && node.properties.name) {
                    var vType = node.properties.var_type || 'string';
                    if (!filterType || vType === filterType) {
                        nodeVars.push({name: node.properties.name, ref: node.properties.name, type: vType, typeLabel: typeLabels[vType] || vType, isGlobal: true});
                    }
                }
                if (defKey.indexOf('loop_count') >= 0 && node.properties.counter_var) {
                    if (!filterType || filterType === 'number') {
                        nodeVars.push({name: node.properties.counter_var, ref: node.properties.counter_var, type: 'number', typeLabel: '数字', isGlobal: true});
                    }
                }
                if (defKey.indexOf('check_') >= 0) {
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
                        var sType = defKey.indexOf('ocr') >= 0 ? 'string' : 'boolean';
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
                if (nodeVars.length > 0) {
                    result[nodeLabel] = nodeVars;
                }
            }
            return result;
        },

        _showToast: function(msg) {
            var toast = document.createElement('div');
            toast.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:var(--bg-raised,#1e293b);color:var(--txt1,#f1f5f9);padding:8px 20px;border-radius:8px;font-size:13px;z-index:999999;box-shadow:0 4px 16px rgba(0,0,0,0.4);border:1px solid var(--border,#334155)';
            toast.textContent = msg;
            document.body.appendChild(toast);
            setTimeout(function() { toast.remove(); }, 2000);
        },

        _bindEvents: function(container, node, schema) {
            var self = this;
            var _propDirty = false;

            function _markPropDirty() { _propDirty = true; }
            function _flushPropUndo() {
                if (_propDirty && window.AutomationApp && window.AutomationApp.undoPush) {
                    window.AutomationApp.undoPush();
                    _propDirty = false;
                }
            }
            function _syncInlineField(key, value) {
                if (node._domEl) {
                    var field = node._domEl.querySelector('.nf[data-key="' + key + '"]');
                    if (field) {
                        if (field.tagName === 'SELECT') {
                            field.value = value;
                        } else if (field.type === 'checkbox') {
                            field.checked = value;
                        } else if (field.type === 'number') {
                            field.value = value;
                        } else if (field.type === 'color') {
                            field.value = value;
                        } else {
                            field.value = value;
                        }
                    }
                }
            }

            container.querySelectorAll('select[data-key]').forEach(function(sel) {
                sel.addEventListener('change', function() {
                    var key = sel.dataset.key;
                    node.properties[key] = sel.value;
                    _syncInlineField(key, sel.value);
                    _markPropDirty();
                    if (key === 'mode') {
                        _flushPropUndo();
                        self.render(node);
                    } else {
                        _flushPropUndo();
                        self._checkShowWhenChanges(node);
                    }
                });
                sel.addEventListener('blur', _flushPropUndo);
            });

            container.querySelectorAll('input[data-type="number"]').forEach(function(inp) {
                inp.addEventListener('input', function() {
                    var key = inp.dataset.key;
                    var rawVal = inp.dataset.rawValue || '';
                    var isVarRef = typeof rawVal === 'string' && rawVal.indexOf('${') === 0 && rawVal.charAt(rawVal.length - 1) === '}';
                    if (isVarRef) {
                        node.properties[key] = '${' + (inp.value || '') + '}';
                        _syncInlineField(key, node.properties[key]);
                    } else {
                        node.properties[key] = parseFloat(inp.value) || 0;
                        _syncInlineField(key, node.properties[key]);
                    }
                    _markPropDirty();
                });
                inp.addEventListener('blur', _flushPropUndo);
            });

            container.querySelectorAll('input[data-type="region"]').forEach(function(inp) {
                inp.addEventListener('input', function() {
                    var key = inp.dataset.key;
                    var idx = parseInt(inp.dataset.index);
                    if (!Array.isArray(node.properties[key])) node.properties[key] = [0,0,10,10];
                    node.properties[key][idx] = parseFloat(inp.value) || 0;
                    _syncInlineField(key, node.properties[key]);
                    _markPropDirty();
                });
                inp.addEventListener('blur', _flushPropUndo);
            });

            container.querySelectorAll('input[data-type="string"]').forEach(function(inp) {
                inp.addEventListener('input', function() {
                    var key = inp.dataset.key;
                    var rawVal = inp.dataset.rawValue || '';
                    var isVarRef = typeof rawVal === 'string' && rawVal.indexOf('${') === 0 && rawVal.charAt(rawVal.length - 1) === '}';
                    if (isVarRef) {
                        node.properties[key] = '${' + inp.value + '}';
                    } else {
                        node.properties[key] = inp.value;
                    }
                    _syncInlineField(key, node.properties[key]);
                    _markPropDirty();
                    self._checkVarSyntax(inp);
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

            container.querySelectorAll('input[data-type="bool"]').forEach(function(inp) {
                inp.addEventListener('change', function() {
                    node.properties[inp.dataset.key] = inp.checked;
                    _syncInlineField(inp.dataset.key, inp.checked);
                    _markPropDirty();
                    _flushPropUndo();
                });
            });

            container.querySelectorAll('.var-list-row').forEach(function(row) {
                row.querySelectorAll('input, select').forEach(function(inp) {
                    inp.addEventListener('input', function() {
                        var listField = row.closest('.var-list-field');
                        var listKey = listField.dataset.key;
                        var items = [];
                        listField.querySelectorAll('.var-list-row').forEach(function(r) {
                            var nameInput = r.querySelector('[data-subkey="name"]');
                            var valueInput = r.querySelector('[data-subkey="value"]');
                            var typeSelect = r.querySelector('[data-subkey="type"]');
                            items.push({
                                name: nameInput ? nameInput.value : '',
                                value: valueInput ? valueInput.value : '',
                                type: typeSelect ? typeSelect.value : 'string'
                            });
                        });
                        node.properties[listKey] = JSON.stringify(items);
                        _markPropDirty();
                    });
                    inp.addEventListener('blur', _flushPropUndo);
                });
            });
        },

        _checkShowWhenChanges: function(node) {
            var def = window.AutomationNodes ? AutomationNodes.getNodeDef(node._defKey || node.type) : null;
            if (!def || !def.params_schema) return;
            var schema = def.params_schema;
            for (var key in schema) {
                if (!schema.hasOwnProperty(key)) continue;
                if (schema[key].showWhen) {
                    this.render(node);
                    return;
                }
            }
        },

        _checkVarSyntax: function(inp) {
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
        },

        _showVarHint: function(inp, partial) {
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
        },

        _hideVarHint: function(inp) {
            if (inp._varHint) {
                inp._varHint.remove();
                inp._varHint = null;
            }
        },

        _handleVarAutocomplete: function(e, inp, node) {
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
        },

        _insertVarRef: function(inp, varName) {
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
        },

        _collectKnownVars: function() {
            var vars = [];
            if (!AutomationCore.lgGraphObj) return vars;
            var nodes = AutomationCore.lgGraphObj._nodes || [];
            for (var i = 0; i < nodes.length; i++) {
                var node = nodes[i];
                if (node.properties && node.properties.name && (node._defKey || '').indexOf('var_set') >= 0) {
                    if (vars.indexOf(node.properties.name) < 0) {
                        vars.push(node.properties.name);
                    }
                }
                if (node.properties && node.properties.store_var && (node._defKey || '').indexOf('check_') >= 0) {
                    if (vars.indexOf(node.properties.store_var) < 0) {
                        vars.push(node.properties.store_var);
                    }
                }
                if (node.properties && node.properties.counter_var && (node._defKey || '').indexOf('loop_count') >= 0) {
                    if (vars.indexOf(node.properties.counter_var) < 0) {
                        vars.push(node.properties.counter_var);
                    }
                }
            }
            return vars;
        },
    };

export const AutomationProperty = window.AutomationProperty;
