'use strict';

var _nodes = {};
    var _nodeList = [];
    var _connections = [];
    var _linksSparse = [];
    var _nextNodeId = 1;
    var _nextLinkId = 1;
    var _selectedNodeId = null;

    var _annotations = [];
    var _nextAnnotationId = 1;
    var _selectedAnnotationId = null;
    var _selectedAnnotations = [];
    var _groups = [];
    var _nextGroupId = 1;
    var _selectedGroupId = null;
    var _selectedGroups = [];

    var _vpOffset = { x: 100, y: 100 };
    var _vpScale = 1;

    var _canvasArea = null;
    var _viewportEl = null;
    var _nodeLayerEl = null;
    var _connSvgEl = null;
    var _bgEl = null;
    var _annotationLayerEl = null;
    var _groupLayerEl = null;

    var _isPanning = false;
    var _panStartX = 0;
    var _panStartY = 0;
    var _panStartOffX = 0;
    var _panStartOffY = 0;

    var _isDraggingNode = false;
    var _dragNodeId = null;
    var _dragOffsetX = 0;
    var _dragOffsetY = 0;

    var _isConnecting = false;
    var _connFromNodeId = null;
    var _connFromPortKey = null;
    var _connFromDir = null;
    var _connFromPortType = null;
    var _tmpPathEl = null;

    var _spaceHeld = false;

    var _isSelecting = false;
    var _selStartX = 0;
    var _selStartY = 0;
    var _selOffX = 0;
    var _selOffY = 0;
    var _selectedNodes = [];
    var _dragStartPositions = {};
    var _dragIsMultiSelect = false;
    var _dragRAF = 0;
    var _dragPendingDx = 0;
    var _dragPendingDy = 0;
    var _dragGhostEl = null;
    var _dragGhostStartLocal = null;
    var _dragNearbyAnnotations = [];

    var _lineDeleteMode = false;
    var _lineDeleteDragging = false;

    var _onNodeSelected = null;
    var _onNodeDeselected = null;
    var _onNodeAdded = null;
    var _onNodeRemoved = null;
    var _onConnectionChange = null;

    var _portNameMap = {
        in: '执行', out: '输出', next: '下一步', body: '循环体',
        done: '完成', true: '是', false: '否', cond: '条件',
        trigger: '触发', timeout: '超时', completed: '完成',
        interrupted: '中断', match: '匹配', no: '不匹配',
        result: '结果', val: '值', met: '满足', pass: '通过', fail: '失败'
    };

    var _portTypeColors = {
        flow: '#94a3b8',
        boolean: '#ef4444',
        number: '#22c55e',
        string: '#60a5fa',
        any: '#94a3b8'
    };

    function _toZh(name) {
        return _portNameMap[name] || name;
    }

    function _screenToLocal(cx, cy) {
        var r = _canvasArea.getBoundingClientRect();
        return {
            x: (cx - r.left - _vpOffset.x) / _vpScale,
            y: (cy - r.top - _vpOffset.y) / _vpScale
        };
    }

    function _getPortCenter(nodeId, portKey, dir) {
        var el = document.getElementById('nd-' + nodeId);
        if (!el) return null;
        var dot = el.querySelector('.pt[data-p="' + portKey + '"][data-d="' + dir + '"] .pd');
        if (!dot) return null;
        var dr = dot.getBoundingClientRect();
        var ar = _canvasArea.getBoundingClientRect();
        return {
            x: (dr.left + dr.width / 2 - ar.left - _vpOffset.x) / _vpScale,
            y: (dr.top + dr.height / 2 - ar.top - _vpOffset.y) / _vpScale
        };
    }

    function _bezier(x1, y1, x2, y2) {
        var dx = Math.abs(x2 - x1);
        var cp = Math.max(50, dx * 0.5);
        return 'M' + x1 + ',' + y1 + ' C' + (x1 + cp) + ',' + y1 + ' ' + (x2 - cp) + ',' + y2 + ' ' + x2 + ',' + y2;
    }

    function _pickSummaryKeys(schema) {
        var keys = [];
        var skip = { hwnd_var: true, store_var: true, store_number: true, path: true, template_path: true, method: true, trigger_mode: true, on_trigger: true, auto_stop: true, mode: true };
        var priority = { x: 1, y: 2, dx: 3, dy: 4, button: 5, key: 6, text: 7, delay: 8, duration: 9, amount: 10 };
        var allKeys = [];
        for (var k in schema) {
            if (!schema.hasOwnProperty(k)) continue;
            if (skip[k]) continue;
            allKeys.push(k);
        }
        // 按优先级排序，优先显示常用参数
        allKeys.sort(function(a, b) {
            var pa = priority[a] || 99;
            var pb = priority[b] || 99;
            return pa - pb;
        });
        // 最多显示4个参数
        for (var i = 0; i < allKeys.length && i < 4; i++) {
            keys.push(allKeys[i]);
        }
        return keys;
    }

    function _fmtVal(val, s) {
        if (val === undefined || val === null) return '';
        if (s.type === 'bool') return val ? '是' : '否';
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
        if (schema.type === 'bool') {
            var chk = val ? ' checked' : '';
            return '<label class="nf nf-chk"><input type="checkbox" data-nid="' + nid + '" data-key="' + k + '"' + chk + '><span class="chk-mk"></span></label>';
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
        return '<input type="text" class="nf nf-txt" data-nid="' + nid + '" data-key="' + k + '" value="' + (val !== null && val !== undefined ? _escapeHtml(val) : '') + '">';
    }

    function _isConnected(nodeId, slotIdx, dir) {
        for (var i = 0; i < _connections.length; i++) {
            var c = _connections[i];
            if (dir === 'i' && c.target_id === nodeId && c.target_slot === slotIdx) return true;
            if (dir === 'o' && c.origin_id === nodeId && c.origin_slot === slotIdx) return true;
        }
        return false;
    }

    function _updateViewport() {
        if (!_viewportEl) return;
        _viewportEl.style.transform = 'translate(' + _vpOffset.x + 'px,' + _vpOffset.y + 'px) scale(' + _vpScale + ')';
    }

    function _renderNodeDOM(node) {
        var def = window.AutomationNodes ? AutomationNodes.getNodeDef(node._defKey) : null;
        var el = document.createElement('div');
        el.className = 'nd' + (node.id === _selectedNodeId ? ' sel' : '');
        el.id = 'nd-' + node.id;
        el.dataset.c = node._category;
        el.dataset.id = String(node.id);
        el.dataset.type = node._defKey;
        el.style.left = node.pos[0] + 'px';
        el.style.top = node.pos[1] + 'px';

        var h = document.createElement('div');
        h.className = 'nd-h';
        h.innerHTML = '<i class="ni ' + node._iconClass + '" style="color:' + node._accentColor + '"></i>' +
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

        var sKeys = (def && def.params_schema) ? _pickSummaryKeys(def.params_schema) : [];
        // 参数从输入端口下方开始显示

        // 计算节点宽度策略：根据参数数量和内容决定
        var hasManyParams = sKeys.length > 2;
        var hasWideContent = false;
        for (var ski = 0; ski < sKeys.length; ski++) {
            var sk = sKeys[ski];
            var ss = def.params_schema[sk];
            if (ss.type === 'string' || ss.type === 'text' || ss.type === 'region') {
                hasWideContent = true; break;
            }
        }
        // 参数少且无宽内容时，使用紧凑模式
        if (sKeys.length <= 2 && !hasWideContent && node.inputs.length <= 1 && node.outputs.length <= 1) {
            el.classList.add('nd-compact');
        }

        // 参数从第2行开始显示（第1行留给输入端口），确保对齐
        var paramStartRow = node.inputs.length;
        var totalRows = Math.max(node.inputs.length, node.outputs.length, paramStartRow + sKeys.length);

        for (var ri = 0; ri < totalRows; ri++) {
            var rowEl = document.createElement('div');
            rowEl.className = 'nd-row';

            // 左侧输入端口
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
                // 参数行：左侧占位保持对齐
                var piSpacer = document.createElement('div');
                piSpacer.className = 'pi-s';
                piSpacer.style.visibility = 'hidden';
                piSpacer.innerHTML = '<div class="pt-r i"><div class="pt flow"><div class="pd"></div><span>&nbsp;</span></div></div>';
                rowEl.appendChild(piSpacer);
            }

            // 中间参数区域
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
                // 空白占位
                var spacer = document.createElement('div');
                spacer.className = 'nd-pr';
                spacer.style.visibility = 'hidden';
                spacer.innerHTML = '<span class="pl">&nbsp;</span>';
                rowEl.appendChild(spacer);
            }

            // 右侧输出端口
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
                // 参数行但无输出端口：右侧占位保持对齐
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
        if (!_nodeLayerEl) return;
        var el = _renderNodeDOM(node);
        _nodeLayerEl.appendChild(el);
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
                        var n = _nodes[nid];
                        if (!n) return;
                        n.properties[key] = f.value;
                        if (window.AutomationProperty && AutomationProperty._currentNode === n) {
                            AutomationProperty.render(n);
                        }
                    });
                    f.addEventListener('mousedown', function(e) { e.stopPropagation(); });
                } else if (f.type === 'checkbox') {
                    f.addEventListener('change', function() {
                        var n = _nodes[nid];
                        if (!n) return;
                        n.properties[key] = f.checked;
                        if (window.AutomationProperty && AutomationProperty._currentNode === n) {
                            AutomationProperty.render(n);
                        }
                    });
                    f.addEventListener('mousedown', function(e) { e.stopPropagation(); });
                } else if (f.type === 'number') {
                    f.addEventListener('input', function() {
                        var n = _nodes[nid];
                        if (!n) return;
                        var v = f.value;
                        if (v && v.indexOf('${') >= 0) {
                            n.properties[key] = v;
                        } else {
                            n.properties[key] = parseFloat(v) || 0;
                        }
                    });
                    f.addEventListener('change', function() {
                        var n = _nodes[nid];
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
                    });
                    f.addEventListener('mousedown', function(e) { e.stopPropagation(); });
                    f.addEventListener('click', function(e) { e.stopPropagation(); });
                } else if (f.type === 'color') {
                    f.addEventListener('input', function() {
                        var n = _nodes[nid];
                        if (!n) return;
                        n.properties[key] = f.value;
                    });
                    f.addEventListener('change', function() {
                        var n = _nodes[nid];
                        if (!n) return;
                        n.properties[key] = f.value;
                        if (window.AutomationProperty && AutomationProperty._currentNode === n) {
                            AutomationProperty.render(n);
                        }
                    });
                    f.addEventListener('mousedown', function(e) { e.stopPropagation(); });
                } else if (f.type === 'text') {
                    f.addEventListener('input', function() {
                        var n = _nodes[nid];
                        if (!n) return;
                        n.properties[key] = f.value;
                    });
                    f.addEventListener('change', function() {
                        var n = _nodes[nid];
                        if (!n) return;
                        n.properties[key] = f.value;
                        if (window.AutomationProperty && AutomationProperty._currentNode === n) {
                            AutomationProperty.render(n);
                        }
                    });
                    f.addEventListener('mousedown', function(e) { e.stopPropagation(); });
                    f.addEventListener('click', function(e) { e.stopPropagation(); });
                } else if (f.classList.contains('nf-ro')) {
                    f.addEventListener('click', function() {
                        var n = _nodes[nid];
                        if (n) {
                            _selectNodeById(nid);
                            if (window.AutomationProperty) AutomationProperty.render(n);
                        }
                    });
                }
            })(fields[i]);
        }
    }

    function _removeNodeFromDOM(nodeId) {
        var el = document.getElementById('nd-' + nodeId);
        if (el) el.remove();
    }

    var _annotationPresetColors = [
        { color: '#fbbf24', name: '黄色', bg: 'linear-gradient(135deg,rgba(251,191,36,.38),rgba(251,191,36,.28))' },
        { color: '#22c55e', name: '绿色', bg: 'linear-gradient(135deg,rgba(34,197,94,.38),rgba(34,197,94,.28))' },
        { color: '#3b82f6', name: '蓝色', bg: 'linear-gradient(135deg,rgba(59,130,246,.38),rgba(59,130,246,.28))' },
        { color: '#f97316', name: '橙色', bg: 'linear-gradient(135deg,rgba(249,115,22,.38),rgba(249,115,22,.28))' },
        { color: '#a855f7', name: '紫色', bg: 'linear-gradient(135deg,rgba(168,85,247,.38),rgba(168,85,247,.28))' },
        { color: '#ef4444', name: '红色', bg: 'linear-gradient(135deg,rgba(239,68,68,.38),rgba(239,68,68,.28))' },
        { color: '#06b6d4', name: '青色', bg: 'linear-gradient(135deg,rgba(6,182,212,.38),rgba(6,182,212,.28))' },
        { color: '#94a3b8', name: '灰色', bg: 'linear-gradient(135deg,rgba(148,163,184,.38),rgba(148,163,184,.28))' }
    ];

    function _renderAnnotation(an) {
        if (!_annotationLayerEl) return;
        var existing = document.getElementById('an-' + an.id);
        if (existing) existing.remove();
        var el = document.createElement('div');
        el.id = 'an-' + an.id;
        el.className = 'an' + (an.collapsed ? ' collapsed' : '');
        el.style.left = an.pos[0] + 'px';
        el.style.top = an.pos[1] + 'px';
        var bgStyle = an.bgColor || 'linear-gradient(135deg,rgba(251,191,36,.38),rgba(251,191,36,.28))';
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
            AutomationCore._notifyGraphChange();
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
            AutomationCore._notifyGraphChange();
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
            if (e.button === 2) {
                e.preventDefault();
                var colorMenuItems = [];
                for (var ci = 0; ci < _annotationPresetColors.length; ci++) {
                    (function(preset) {
                        colorMenuItems.push({
                            label: preset.name,
                            icon: 'fa-solid fa-circle',
                            iconStyle: 'color:' + preset.color,
                            action: function() {
                                an.color = preset.color;
                                an.bgColor = preset.bg;
                                el.style.background = preset.bg;
                                AutomationCore._notifyGraphChange();
                            }
                        });
                    })(_annotationPresetColors[ci]);
                }
                colorMenuItems.push({ label: '分隔线', divider: true });
                colorMenuItems.push({ label: '删除注释', icon: 'fa-solid fa-trash-can', action: function() { AutomationCore.removeAnnotation(an.id); } });
                if (window.AutomationApp && AutomationApp.showContextMenu) {
                    AutomationApp.showContextMenu(e.clientX, e.clientY, colorMenuItems);
                }
                return;
            }
            if (e.button === 0) {
                var isMulti = e.ctrlKey || e.metaKey;
                if (isMulti) {
                    var alreadySel = false;
                    for (var si = 0; si < _selectedAnnotations.length; si++) {
                        if (_selectedAnnotations[si].id === an.id) { alreadySel = true; break; }
                    }
                    if (alreadySel) {
                        _selectedAnnotations = _selectedAnnotations.filter(function(a) { return a.id !== an.id; });
                        el.classList.remove('sel');
                        if (_selectedAnnotations.length === 0) _selectedAnnotationId = null;
                    } else {
                        _selectedAnnotations.push(an);
                        el.classList.add('sel');
                        _selectedAnnotationId = an.id;
                    }
                    if (_selectedAnnotations.length > 0 && window.AutomationProperty) {
                        AutomationProperty.renderAnnotation(_selectedAnnotations[_selectedAnnotations.length - 1]);
                    }
                } else {
                    for (var ci = 0; ci < _selectedAnnotations.length; ci++) {
                        var cel = _selectedAnnotations[ci]._domEl || document.getElementById('an-' + _selectedAnnotations[ci].id);
                        if (cel) cel.classList.remove('sel');
                    }
                    _selectedAnnotations = [];
                    for (var cgi = 0; cgi < _selectedGroups.length; cgi++) {
                        var cgel = _selectedGroups[cgi]._domEl || document.getElementById('gp-' + _selectedGroups[cgi].id);
                        if (cgel) cgel.classList.remove('sel');
                    }
                    _selectedGroups = [];
                    _selectedAnnotationId = an.id;
                    el.classList.add('sel');
                    _selectedNodeId = null;
                    var prevNodeEl = document.getElementById('nd-' + _selectedNodeId);
                    if (prevNodeEl) prevNodeEl.classList.remove('sel');
                    _selectedGroupId = null;
                    var prevGpEl = document.getElementById('gp-' + _selectedGroupId);
                    if (prevGpEl) prevGpEl.classList.remove('sel');
                    if (window.AutomationProperty) {
                        AutomationProperty.renderAnnotation(an);
                    }
                }
                var startX = e.clientX, startY = e.clientY;
                var startLeft = an.pos[0], startTop = an.pos[1];
                function onMove(ev) {
                    var dx = (ev.clientX - startX) / _vpScale;
                    var dy = (ev.clientY - startY) / _vpScale;
                    var newX = startLeft + dx;
                    var newY = startTop + dy;
                    var snapDist = 8 / _vpScale;
                    var anW = el.offsetWidth || 120;
                    var anH = el.offsetHeight || 40;
                    for (var nid in _nodes) {
                        if (!_nodes.hasOwnProperty(nid)) continue;
                        var node = _nodes[nid];
                        var nodeW = node.size ? node.size[0] : 180;
                        var nodeH = node.size ? node.size[1] : 80;
                        if (Math.abs(newX - (node.pos[0] + nodeW)) < snapDist) { newX = node.pos[0] + nodeW; }
                        if (Math.abs(newX + anW - node.pos[0]) < snapDist) { newX = node.pos[0] - anW; }
                        if (Math.abs(newY - (node.pos[1] + nodeH)) < snapDist) { newY = node.pos[1] + nodeH; }
                        if (Math.abs(newY + anH - node.pos[1]) < snapDist) { newY = node.pos[1] - anH; }
                    }
                    for (var gi = 0; gi < _groups.length; gi++) {
                        var gp = _groups[gi];
                        if (Math.abs(newX - (gp.pos[0] + gp.size[0])) < snapDist) { newX = gp.pos[0] + gp.size[0]; }
                        if (Math.abs(newX + anW - gp.pos[0]) < snapDist) { newX = gp.pos[0] - anW; }
                        if (Math.abs(newY - (gp.pos[1] + gp.size[1])) < snapDist) { newY = gp.pos[1] + gp.size[1]; }
                        if (Math.abs(newY + anH - gp.pos[1]) < snapDist) { newY = gp.pos[1] - anH; }
                    }
                    an.pos[0] = newX;
                    an.pos[1] = newY;
                    el.style.left = an.pos[0] + 'px';
                    el.style.top = an.pos[1] + 'px';
                }
                function onUp() {
                    document.removeEventListener('mousemove', onMove);
                    document.removeEventListener('mouseup', onUp);
                    AutomationCore._notifyGraphChange();
                }
                document.addEventListener('mousemove', onMove);
                document.addEventListener('mouseup', onUp);
            }
        });
        _annotationLayerEl.appendChild(el);
        an._domEl = el;
    }

    var _groupPresetColors = [
        { color: '#3b82f6', name: '蓝色', bg: 'rgba(59,130,246,.08)' },
        { color: '#22c55e', name: '绿色', bg: 'rgba(34,197,94,.08)' },
        { color: '#f97316', name: '橙色', bg: 'rgba(249,115,22,.08)' },
        { color: '#a855f7', name: '紫色', bg: 'rgba(168,85,247,.08)' },
        { color: '#ef4444', name: '红色', bg: 'rgba(239,68,68,.08)' },
        { color: '#eab308', name: '黄色', bg: 'rgba(234,179,8,.08)' },
        { color: '#06b6d4', name: '青色', bg: 'rgba(6,182,212,.08)' },
        { color: '#64748b', name: '灰色', bg: 'rgba(100,116,139,.08)' }
    ];

    function _getNodesInGroup(gp) {
        var result = [];
        var gpLeft = gp.pos[0];
        var gpTop = gp.pos[1];
        var gpRight = gpLeft + gp.size[0];
        var gpBottom = gpTop + gp.size[1];
        for (var nid in _nodes) {
            if (!_nodes.hasOwnProperty(nid)) continue;
            var node = _nodes[nid];
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
        for (var ai = 0; ai < _annotations.length; ai++) {
            var an = _annotations[ai];
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
        if (!_groupLayerEl) return;
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
                    AutomationCore._notifyGraphChange();
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
            AutomationCore._notifyGraphChange();
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
            if (e.button === 2) {
                e.preventDefault();
                var menuItems = [
                    { label: '更改颜色', icon: 'fa-solid fa-palette', action: function() {
                        colorMenuEl.classList.toggle('show');
                    }},
                    { label: '删除分组', icon: 'fa-solid fa-trash-can', action: function() { AutomationCore.removeGroup(gp.id); } }
                ];
                if (window.AutomationApp && AutomationApp.showContextMenu) {
                    AutomationApp.showContextMenu(e.clientX, e.clientY, menuItems);
                }
                return;
            }
            if (e.button === 0) {
                var gpIsMulti = e.ctrlKey || e.metaKey;
                if (gpIsMulti) {
                    var gpAlreadySel = false;
                    for (var gsi = 0; gsi < _selectedGroups.length; gsi++) {
                        if (_selectedGroups[gsi].id === gp.id) { gpAlreadySel = true; break; }
                    }
                    if (gpAlreadySel) {
                        _selectedGroups = _selectedGroups.filter(function(g) { return g.id !== gp.id; });
                        el.classList.remove('sel');
                        if (_selectedGroups.length === 0) _selectedGroupId = null;
                    } else {
                        _selectedGroups.push(gp);
                        el.classList.add('sel');
                        _selectedGroupId = gp.id;
                    }
                    if (_selectedGroups.length > 0 && window.AutomationProperty) {
                        AutomationProperty.renderGroup(_selectedGroups[_selectedGroups.length - 1]);
                    }
                } else {
                    for (var gci = 0; gci < _selectedGroups.length; gci++) {
                        var gcel = _selectedGroups[gci]._domEl || document.getElementById('gp-' + _selectedGroups[gci].id);
                        if (gcel) gcel.classList.remove('sel');
                    }
                    _selectedGroups = [];
                    for (var aci = 0; aci < _selectedAnnotations.length; aci++) {
                        var ael2 = _selectedAnnotations[aci]._domEl || document.getElementById('an-' + _selectedAnnotations[aci].id);
                        if (ael2) ael2.classList.remove('sel');
                    }
                    _selectedAnnotations = [];
                    _selectedGroupId = gp.id;
                    el.classList.add('sel');
                    _selectedNodeId = null;
                    var prevNodeEl = document.getElementById('nd-' + _selectedNodeId);
                    if (prevNodeEl) prevNodeEl.classList.remove('sel');
                    _selectedAnnotationId = null;
                    var prevAnEl = document.getElementById('an-' + _selectedAnnotationId);
                    if (prevAnEl) prevAnEl.classList.remove('sel');
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
                    var dx = (ev.clientX - startX) / _vpScale;
                    var dy = (ev.clientY - startY) / _vpScale;
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
                    AutomationCore._notifyGraphChange();
                }
                document.addEventListener('mousemove', onMove);
                document.addEventListener('mouseup', onUp);
            }
        });
        rszEl.addEventListener('mousedown', function(e) {
            e.stopPropagation();
            if (e.button !== 0) return;
            var startX = e.clientX, startY = e.clientY;
            var startW = gp.size[0], startH = gp.size[1];
            function onMove(ev) {
                var dw = (ev.clientX - startX) / _vpScale;
                var dh = (ev.clientY - startY) / _vpScale;
                gp.size[0] = Math.max(140, startW + dw);
                gp.size[1] = Math.max(100, startH + dh);
                el.style.width = gp.size[0] + 'px';
                el.style.height = gp.size[1] + 'px';
            }
            function onUp() {
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
                AutomationCore._notifyGraphChange();
            }
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
        _groupLayerEl.appendChild(el);
        gp._domEl = el;
    }

    function _refreshNodeDOM(node) {
        var oldEl = document.getElementById('nd-' + node.id);
        if (!oldEl) return;
        var newEl = _renderNodeDOM(node);
        oldEl.parentNode.replaceChild(newEl, oldEl);
        node._domEl = newEl;
        node.size = [newEl.offsetWidth || 220, newEl.offsetHeight || 100];
        _bindInlineFields(newEl, node);
    }

    function _renderAllConnections() {
        if (!_connSvgEl) return;
        _connSvgEl.innerHTML = '';
        for (var i = 0; i < _connections.length; i++) {
            _renderConnection(_connections[i]);
        }
    }

    function _renderConnection(conn) {
        if (!_connSvgEl) return;
        var fromNode = _nodes[conn.origin_id];
        var toNode = _nodes[conn.target_id];
        if (!fromNode || !toNode) return;

        var fromPort = fromNode.outputs[conn.origin_slot];
        var toPort = toNode.inputs[conn.target_slot];
        if (!fromPort || !toPort) return;

        var fe = _getPortCenter(conn.origin_id, fromPort._portKey, 'o');
        var te = _getPortCenter(conn.target_id, toPort._portKey, 'i');
        if (!fe || !te) return;

        var g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('data-link-id', String(conn.id));
        g.style.cursor = 'pointer';

        var hitPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        hitPath.setAttribute('d', _bezier(fe.x, fe.y, te.x, te.y));
        hitPath.setAttribute('stroke', 'transparent');
        hitPath.setAttribute('stroke-width', '14');
        hitPath.setAttribute('fill', 'none');
        g.appendChild(hitPath);

        var visPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        visPath.setAttribute('d', _bezier(fe.x, fe.y, te.x, te.y));
        visPath.setAttribute('stroke', _portTypeColors[fromPort.type] || '#94a3b8');
        visPath.setAttribute('stroke-width', '2.5');
        visPath.setAttribute('fill', 'none');
        visPath.style.transition = 'stroke-width .12s';
        g.appendChild(visPath);

        g.addEventListener('mouseenter', function() {
            visPath.setAttribute('stroke-width', '4');
        });
        g.addEventListener('mouseleave', function() {
            visPath.setAttribute('stroke-width', '2.5');
        });
        g.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _removeConnectionById(conn.id);
        });
        g.addEventListener('dblclick', function(e) {
            e.preventDefault();
            e.stopPropagation();
            _removeConnectionById(conn.id);
        });

        _connSvgEl.appendChild(g);
    }

    function _updateAffectedConnections() {
        if (!_connSvgEl) return;
        var affectedIds = {};
        if (_dragIsMultiSelect) {
            for (var id in _dragStartPositions) {
                if (_dragStartPositions.hasOwnProperty(id)) affectedIds[id] = true;
            }
        } else if (_dragNodeId !== null) {
            affectedIds[_dragNodeId] = true;
        }
        if (Object.keys(affectedIds).length === 0) {
            _renderAllConnections();
            return;
        }
        var gs = _connSvgEl.children;
        for (var i = gs.length - 1; i >= 0; i--) {
            var g = gs[i];
            var linkId = g.getAttribute('data-link-id');
            if (!linkId) continue;
            var linkIdNum = parseInt(linkId);
            var conn = _linksSparse[linkIdNum];
            if (!conn) continue;
            if (!affectedIds[conn.origin_id] && !affectedIds[conn.target_id]) continue;
            var fromNode = _nodes[conn.origin_id];
            var toNode = _nodes[conn.target_id];
            if (!fromNode || !toNode) continue;
            var fromPort = fromNode.outputs[conn.origin_slot];
            var toPort = toNode.inputs[conn.target_slot];
            if (!fromPort || !toPort) continue;
            var fe = _getPortCenter(conn.origin_id, fromPort._portKey, 'o');
            var te = _getPortCenter(conn.target_id, toPort._portKey, 'i');
            if (!fe || !te) continue;
            var paths = g.querySelectorAll('path');
            var d = _bezier(fe.x, fe.y, te.x, te.y);
            for (var pi = 0; pi < paths.length; pi++) {
                paths[pi].setAttribute('d', d);
            }
        }
    }

    function _createNodeData(type) {
        var def = window.AutomationNodes ? AutomationNodes.getNodeDef(type) : null;
        if (!def) return null;

        var id = _nextNodeId++;
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
                return c;
            }
        };

        if (def.inputs) {
            for (var i = 0; i < def.inputs.length; i++) {
                var inp = def.inputs[i];
                node.inputs.push({
                    name: _toZh(inp.name),
                    type: inp.type,
                    _portKey: inp.name
                });
            }
        }
        if (def.outputs) {
            for (var i = 0; i < def.outputs.length; i++) {
                var out = def.outputs[i];
                node.outputs.push({
                    name: _toZh(out.name),
                    type: out.type,
                    _portKey: out.name
                });
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
            } else {
                node.properties[key] = s.default !== undefined ? s.default : (s.type === 'number' ? 0 : '');
            }
        }

        return node;
    }

    function _addNode(node) {
        _nodes[node.id] = node;
        _nodeList.push(node);
        _addNodeToDOM(node);
        if (_onNodeAdded) _onNodeAdded(node);
        AutomationCore._notifyGraphChange();
    }

    function _removeNodeById(nodeId) {
        var node = _nodes[nodeId];
        if (!node) return;
        _removeConnectionsForNode(nodeId);
        _removeNodeFromDOM(nodeId);
        delete _nodes[nodeId];
        var idx = _nodeList.indexOf(node);
        if (idx >= 0) _nodeList.splice(idx, 1);
        AutomationCore._notifyGraphChange();
        var selIdx = _selectedNodes.indexOf(node);
        if (selIdx >= 0) _selectedNodes.splice(selIdx, 1);
        if (_selectedNodeId === nodeId) {
            _selectedNodeId = null;
            if (_onNodeDeselected) _onNodeDeselected(node);
        }
        if (_onNodeRemoved) _onNodeRemoved(node);
    }

    function _addConnection(fromNodeId, fromSlot, toNodeId, toSlot) {
        var fromNode = _nodes[fromNodeId];
        var toNode = _nodes[toNodeId];
        if (!fromNode || !toNode) return null;
        if (!fromNode.outputs[fromSlot] || !toNode.inputs[toSlot]) return null;

        for (var i = _connections.length - 1; i >= 0; i--) {
            var c = _connections[i];
            if (c.target_id === toNodeId && c.target_slot === toSlot) {
                _removeConnectionById(c.id);
            }
        }

        var linkId = _nextLinkId++;
        var outPort = fromNode.outputs[fromSlot];
        var conn = {
            id: linkId,
            origin_id: fromNodeId,
            origin_slot: fromSlot,
            target_id: toNodeId,
            target_slot: toSlot,
            type: outPort.type === 'flow' ? 'flow' : 'data'
        };
        _connections.push(conn);
        _linksSparse[linkId] = conn;
        _renderConnection(conn);
        _refreshNodeDOM(fromNode);
        _refreshNodeDOM(toNode);
        if (_onConnectionChange) _onConnectionChange();
        AutomationCore._notifyGraphChange();
        return conn;
    }

    function _removeConnectionById(linkId) {
        var conn = _linksSparse[linkId];
        if (!conn) return;
        var fromNode = _nodes[conn.origin_id];
        var toNode = _nodes[conn.target_id];
        var pathEl = _connSvgEl ? _connSvgEl.querySelector('g[data-link-id="' + linkId + '"]') : null;
        if (pathEl) pathEl.remove();
        var idx = _connections.indexOf(conn);
        if (idx >= 0) _connections.splice(idx, 1);
        delete _linksSparse[linkId];
        if (fromNode) _refreshNodeDOM(fromNode);
        if (toNode) _refreshNodeDOM(toNode);
        if (_onConnectionChange) _onConnectionChange();
        AutomationCore._notifyGraphChange();
    }

    function _removeConnectionsForNode(nodeId) {
        var toRemove = [];
        for (var i = 0; i < _connections.length; i++) {
            if (_connections[i].origin_id === nodeId || _connections[i].target_id === nodeId) {
                toRemove.push(_connections[i].id);
            }
        }
        for (var j = 0; j < toRemove.length; j++) {
            _removeConnectionById(toRemove[j]);
        }
    }

    function _selectNodeById(nodeId) {
        if (_selectedNodeId === nodeId) return;
        if (_selectedNodeId !== null) {
            var prevEl = document.getElementById('nd-' + _selectedNodeId);
            if (prevEl) prevEl.classList.remove('sel');
            var prevNode = _nodes[_selectedNodeId];
            if (prevNode) prevNode.selected = false;
            if (_onNodeDeselected && prevNode) _onNodeDeselected(prevNode);
        }
        if (_selectedAnnotationId !== null) {
            var prevAnEl = document.getElementById('an-' + _selectedAnnotationId);
            if (prevAnEl) prevAnEl.classList.remove('sel');
            _selectedAnnotationId = null;
        }
        if (_selectedGroupId !== null) {
            var prevGpEl = document.getElementById('gp-' + _selectedGroupId);
            if (prevGpEl) prevGpEl.classList.remove('sel');
            _selectedGroupId = null;
        }
        _selectedNodeId = nodeId;
        if (nodeId !== null) {
            var el = document.getElementById('nd-' + nodeId);
            if (el) el.classList.add('sel');
            var node = _nodes[nodeId];
            if (node) node.selected = true;
            if (_onNodeSelected) _onNodeSelected(node);
        }
    }

    function _getAnnotationsNearNodes(nodeIds, threshold) {
        threshold = threshold || 30;
        var result = [];
        for (var ai = 0; ai < _annotations.length; ai++) {
            var an = _annotations[ai];
            var anW = an._domEl ? an._domEl.offsetWidth : 120;
            var anH = an._domEl ? an._domEl.offsetHeight : 40;
            var anCX = an.pos[0] + anW / 2;
            var anCY = an.pos[1] + anH / 2;
            for (var ni = 0; ni < nodeIds.length; ni++) {
                var node = _nodes[nodeIds[ni]];
                if (!node) continue;
                var nodeW = node.size ? node.size[0] : 180;
                var nodeH = node.size ? node.size[1] : 80;
                var nodeLeft = node.pos[0] - threshold;
                var nodeRight = node.pos[0] + nodeW + threshold;
                var nodeTop = node.pos[1] - threshold;
                var nodeBottom = node.pos[1] + nodeH + threshold;
                if (anCX >= nodeLeft && anCX <= nodeRight && anCY >= nodeTop && anCY <= nodeBottom) {
                    result.push(an);
                    break;
                }
            }
        }
        return result;
    }

    function _deselectAll() {
        for (var i = 0; i < _selectedNodes.length; i++) {
            var el = _selectedNodes[i]._domEl || document.getElementById('nd-' + _selectedNodes[i].id);
            if (el) el.classList.remove('sel');
        }
        _selectedNodes = [];
        for (var ai = 0; ai < _selectedAnnotations.length; ai++) {
            var ael = _selectedAnnotations[ai]._domEl || document.getElementById('an-' + _selectedAnnotations[ai].id);
            if (ael) ael.classList.remove('sel');
        }
        _selectedAnnotations = [];
        _selectedAnnotationId = null;
        for (var gi = 0; gi < _selectedGroups.length; gi++) {
            var gel = _selectedGroups[gi]._domEl || document.getElementById('gp-' + _selectedGroups[gi].id);
            if (gel) gel.classList.remove('sel');
        }
        _selectedGroups = [];
        _selectedGroupId = null;
        _selectNodeById(null);
    }

    function _setZoom(newScale, centerX, centerY) {
        var r = _canvasArea.getBoundingClientRect();
        var cx = centerX !== undefined ? centerX : r.width / 2;
        var cy = centerY !== undefined ? centerY : r.height / 2;
        var oldScale = _vpScale;
        _vpScale = Math.max(0.15, Math.min(3, newScale));
        var ratio = _vpScale / oldScale;
        _vpOffset.x = cx - (cx - _vpOffset.x) * ratio;
        _vpOffset.y = cy - (cy - _vpOffset.y) * ratio;
        _updateViewport();
        _updateMinimap();
    }

    var _mmBounds = null;

    function _updateMinimap() {
        var mmCv = document.getElementById('minimap-canvas');
        if (!mmCv) return;
        var dpr = window.devicePixelRatio || 1;
        var w = 160, h = 100;
        mmCv.width = Math.floor(w * dpr);
        mmCv.height = Math.floor(h * dpr);
        var ctx = mmCv.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = 'rgba(10,14,20,0.92)';
        ctx.fillRect(0, 0, w, h);

        var hasContent = _nodeList.length > 0 || _annotations.length > 0 || _groups.length > 0;
        if (!hasContent) { _mmBounds = null; return; }
        var minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
        for (var i = 0; i < _nodeList.length; i++) {
            var n = _nodeList[i];
            minX = Math.min(minX, n.pos[0]);
            minY = Math.min(minY, n.pos[1]);
            maxX = Math.max(maxX, n.pos[0] + (n.size[0] || 200));
            maxY = Math.max(maxY, n.pos[1] + (n.size[1] || 80));
        }
        for (var ai = 0; ai < _annotations.length; ai++) {
            var an = _annotations[ai];
            minX = Math.min(minX, an.pos[0]);
            minY = Math.min(minY, an.pos[1]);
            maxX = Math.max(maxX, an.pos[0] + 120);
            maxY = Math.max(maxY, an.pos[1] + 40);
        }
        for (var gi = 0; gi < _groups.length; gi++) {
            var gp = _groups[gi];
            minX = Math.min(minX, gp.pos[0]);
            minY = Math.min(minY, gp.pos[1]);
            maxX = Math.max(maxX, gp.pos[0] + gp.size[0]);
            maxY = Math.max(maxY, gp.pos[1] + gp.size[1]);
        }
        var pad = 60;
        minX -= pad; minY -= pad; maxX += pad; maxY += pad;
        var gw = Math.max(1, maxX - minX);
        var gh = Math.max(1, maxY - minY);
        var s = Math.min(w / gw, h / gh) * 0.85;
        var ox = (w - gw * s) / 2;
        var oy = (h - gh * s) / 2;

        ctx.strokeStyle = 'rgba(255,255,255,0.08)';
        ctx.lineWidth = 0.5;
        for (var j = 0; j < _connections.length; j++) {
            var c = _connections[j];
            var fn = _nodes[c.origin_id], tn = _nodes[c.target_id];
            if (!fn || !tn) continue;
            ctx.beginPath();
            ctx.moveTo(ox + (fn.pos[0] - minX + (fn.size[0] || 200) / 2) * s, oy + (fn.pos[1] - minY + 20) * s);
            ctx.lineTo(ox + (tn.pos[0] - minX + (tn.size[0] || 200) / 2) * s, oy + (tn.pos[1] - minY + 20) * s);
            ctx.stroke();
        }

        for (var k = 0; k < _nodeList.length; k++) {
            var nd = _nodeList[k];
            ctx.fillStyle = nd._accentColor || '#718096';
            ctx.globalAlpha = 0.6;
            ctx.fillRect(ox + (nd.pos[0] - minX) * s, oy + (nd.pos[1] - minY) * s,
                Math.max(3, (nd.size[0] || 200) * s), Math.max(2, (nd.size[1] || 80) * s));
        }
        ctx.globalAlpha = 1;

        for (var gi = 0; gi < _groups.length; gi++) {
            var gp = _groups[gi];
            ctx.fillStyle = gp.color || '#3b82f6';
            ctx.globalAlpha = 0.25;
            ctx.fillRect(ox + (gp.pos[0] - minX) * s, oy + (gp.pos[1] - minY) * s,
                Math.max(3, gp.size[0] * s), Math.max(2, gp.size[1] * s));
        }
        ctx.globalAlpha = 1;

        for (var ai = 0; ai < _annotations.length; ai++) {
            var an = _annotations[ai];
            ctx.fillStyle = an.color || '#fbbf24';
            ctx.globalAlpha = 0.5;
            ctx.fillRect(ox + (an.pos[0] - minX) * s, oy + (an.pos[1] - minY) * s,
                Math.max(3, 120 * s), Math.max(2, 40 * s));
        }
        ctx.globalAlpha = 1;

        var areaR = _canvasArea.getBoundingClientRect();
        var viewW = areaR.width / _vpScale;
        var viewH = areaR.height / _vpScale;
        var vx = ox + (-_vpOffset.x / _vpScale - minX) * s;
        var vy = oy + (-_vpOffset.y / _vpScale - minY) * s;
        var vw = viewW * s;
        var vh = viewH * s;
        ctx.strokeStyle = 'rgba(255,255,255,0.6)';
        ctx.lineWidth = 1;
        ctx.strokeRect(vx, vy, vw, vh);

        _mmBounds = { minX: minX, minY: minY, maxX: maxX, maxY: maxY, gw: gw, gh: gh, s: s, ox: ox, oy: oy, w: w, h: h };
    }

    function _navigateMinimap(mx, my) {
        if (!_mmBounds || !_canvasArea) return;
        var b = _mmBounds;
        var mmCv = document.getElementById('minimap-canvas');
        if (!mmCv) return;
        var rect = mmCv.getBoundingClientRect();
        var px = (mx - rect.left) / rect.width * b.w;
        var py = (my - rect.top) / rect.height * b.h;
        var localX = (px - b.ox) / b.s + b.minX;
        var localY = (py - b.oy) / b.s + b.minY;
        var areaR = _canvasArea.getBoundingClientRect();
        _vpOffset.x = areaR.width / 2 - localX * _vpScale;
        _vpOffset.y = areaR.height / 2 - localY * _vpScale;
        _updateViewport();
        _updateMinimap();
    }

    function _onCanvasMouseDown(e) {
        if (e.target.closest('#mm')) return;

        if (_lineDeleteMode && e.button === 0) {
            _lineDeleteDragging = true;
            _checkLineDeleteAtPoint(e.clientX, e.clientY);
            e.preventDefault();
            e.stopPropagation();
            return;
        }

        var closeBtn = e.target.closest('.nx[data-action="delete"]');
        if (closeBtn) {
            var ndEl = closeBtn.closest('.nd');
            if (ndEl) {
                var nid = parseInt(ndEl.dataset.id);
                _removeNodeById(nid);
                e.stopPropagation();
                return;
            }
        }

        var portEl = e.target.closest('.pt');
        if (portEl && e.button === 0) {
            e.preventDefault();
            e.stopPropagation();
            _isConnecting = true;
            _connFromNodeId = parseInt(portEl.dataset.n);
            _connFromPortKey = portEl.dataset.p;
            _connFromDir = portEl.dataset.d;
            _connFromPortType = portEl.dataset.pt;
            if (!_tmpPathEl && _connSvgEl) {
                _tmpPathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                _tmpPathEl.setAttribute('class', 'tmp');
                _tmpPathEl.setAttribute('stroke', _portTypeColors[_connFromPortType] || '#94a3b8');
                _connSvgEl.appendChild(_tmpPathEl);
            }
            return;
        }

        var headerEl = e.target.closest('.nd-h');
        if (headerEl && e.button === 0) {
            var ndEl = headerEl.closest('.nd');
            if (ndEl) {
                var nid = parseInt(ndEl.dataset.id);
                var node = _nodes[nid];
                if (node) {
                    var isInSelection = false;
                    for (var ci = 0; ci < _selectedNodes.length; ci++) {
                        if (_selectedNodes[ci].id === nid) { isInSelection = true; break; }
                    }
                    if (!isInSelection) {
                        for (var di = 0; di < _selectedNodes.length; di++) {
                            var selEl = _selectedNodes[di]._domEl || document.getElementById('nd-' + _selectedNodes[di].id);
                            if (selEl) selEl.classList.remove('sel');
                        }
                        _selectedNodes = [];
                    }
                    _selectNodeById(nid);
                    _isDraggingNode = true;
                    _dragNodeId = nid;
                    var local = _screenToLocal(e.clientX, e.clientY);
                    _dragOffsetX = local.x - node.pos[0];
                    _dragOffsetY = local.y - node.pos[1];
                    _dragStartPositions = {};
                    var isInSelection = false;
                    for (var si = 0; si < _selectedNodes.length; si++) {
                        if (_selectedNodes[si].id === nid) { isInSelection = true; break; }
                    }
                    if (isInSelection) {
                        for (var sj = 0; sj < _selectedNodes.length; sj++) {
                            _dragStartPositions[_selectedNodes[sj].id] = {
                                x: _selectedNodes[sj].pos[0],
                                y: _selectedNodes[sj].pos[1]
                            };
                        }
                    } else {
                        _dragStartPositions[nid] = { x: node.pos[0], y: node.pos[1] };
                    }
                    _dragIsMultiSelect = isInSelection && _selectedNodes.length > 1;
                    ndEl.classList.add('drag');

                    _dragGhostStartLocal = { x: local.x, y: local.y };
                    _dragGhostEl = document.createElement('div');
                    _dragGhostEl.className = 'drag-ghost';
                    _dragGhostEl.style.cssText = 'position:absolute;pointer-events:none;z-index:200;border:2px dashed var(--acc);border-radius:var(--r);background:rgba(34,211,238,0.08);transition:none';
                    if (_dragIsMultiSelect) {
                        var minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
                        for (var gid in _dragStartPositions) {
                            if (!_dragStartPositions.hasOwnProperty(gid)) continue;
                            var gn = _nodes[gid];
                            if (!gn) continue;
                            minX = Math.min(minX, gn.pos[0]);
                            minY = Math.min(minY, gn.pos[1]);
                            maxX = Math.max(maxX, gn.pos[0] + (gn.size[0] || 220));
                            maxY = Math.max(maxY, gn.pos[1] + (gn.size[1] || 100));
                        }
                        _dragGhostEl.style.left = minX + 'px';
                        _dragGhostEl.style.top = minY + 'px';
                        _dragGhostEl.style.width = (maxX - minX) + 'px';
                        _dragGhostEl.style.height = (maxY - minY) + 'px';
                        _dragGhostEl.dataset.ox = String(minX);
                        _dragGhostEl.dataset.oy = String(minY);
                    } else {
                        _dragGhostEl.style.left = node.pos[0] + 'px';
                        _dragGhostEl.style.top = node.pos[1] + 'px';
                        _dragGhostEl.style.width = (node.size[0] || 220) + 'px';
                        _dragGhostEl.style.height = (node.size[1] || 100) + 'px';
                        _dragGhostEl.dataset.ox = String(node.pos[0]);
                        _dragGhostEl.dataset.oy = String(node.pos[1]);
                    }
                    _nodeLayerEl.appendChild(_dragGhostEl);

                    if (_dragIsMultiSelect) {
                        for (var hid in _dragStartPositions) {
                            if (!_dragStartPositions.hasOwnProperty(hid)) continue;
                            var hel = document.getElementById('nd-' + hid);
                            if (hel) hel.style.opacity = '0.3';
                        }
                    } else {
                        ndEl.style.opacity = '0.3';
                    }
                    if (_connSvgEl) _connSvgEl.style.opacity = '0.2';

                    var _draggedNodeIds = _dragIsMultiSelect ? Object.keys(_dragStartPositions).map(Number) : [_dragNodeId];
                    var nearAnns = _getAnnotationsNearNodes(_draggedNodeIds, 30);
                    _dragNearbyAnnotations = [];
                    for (var nai = 0; nai < nearAnns.length; nai++) {
                        _dragNearbyAnnotations.push({ an: nearAnns[nai], startX: nearAnns[nai].pos[0], startY: nearAnns[nai].pos[1] });
                    }

                    e.preventDefault();
                    return;
                }
            }
        }

        var nodeEl = e.target.closest('.nd');
        if (nodeEl && e.button === 0) {
            var nid = parseInt(nodeEl.dataset.id);
            _selectNodeById(nid);
            return;
        }

        if (e.button === 1 || (e.button === 0 && _spaceHeld)) {
            _isPanning = true;
            _panStartX = e.clientX;
            _panStartY = e.clientY;
            _panStartOffX = _vpOffset.x;
            _panStartOffY = _vpOffset.y;
            _canvasArea.style.cursor = 'grabbing';
            e.preventDefault();
            return;
        }

        if (e.button === 0 && !e.target.closest('.nd') && !e.target.closest('#mm') && !e.target.closest('#conn-l g')) {
            _deselectAll();
            _isSelecting = true;
            var cvRect = _canvasArea.getBoundingClientRect();
            _selStartX = e.clientX;
            _selStartY = e.clientY;
            _selOffX = cvRect.left;
            _selOffY = cvRect.top;
            _selectedNodes = [];
            var selBox = document.getElementById('sel-box');
            if (selBox) {
                selBox.style.display = 'block';
                selBox.style.left = (e.clientX - cvRect.left) + 'px';
                selBox.style.top = (e.clientY - cvRect.top) + 'px';
                selBox.style.width = '0';
                selBox.style.height = '0';
            }
        }
    }

    function _onCanvasMouseMove(e) {
        var local = _screenToLocal(e.clientX, e.clientY);

        if (_lineDeleteMode && _lineDeleteDragging) {
            _checkLineDeleteAtPoint(e.clientX, e.clientY);
            return;
        }

        if (_isPanning) {
            _vpOffset.x = _panStartOffX + (e.clientX - _panStartX);
            _vpOffset.y = _panStartOffY + (e.clientY - _panStartY);
            _updateViewport();
            _updateMinimap();
            return;
        }

        if (_isSelecting) {
            var selBox = document.getElementById('sel-box');
            if (selBox) {
                var x1 = Math.min(_selStartX, e.clientX) - _selOffX;
                var y1 = Math.min(_selStartY, e.clientY) - _selOffY;
                var x2 = Math.max(_selStartX, e.clientX) - _selOffX;
                var y2 = Math.max(_selStartY, e.clientY) - _selOffY;
                selBox.style.left = x1 + 'px';
                selBox.style.top = y1 + 'px';
                selBox.style.width = (x2 - x1) + 'px';
                selBox.style.height = (y2 - y1) + 'px';
            }
            _updateSelectionFromBox();
            return;
        }

        if (_isDraggingNode && _dragNodeId !== null) {
            if (_dragGhostEl && _dragGhostStartLocal) {
                var gDx = local.x - _dragGhostStartLocal.x;
                var gDy = local.y - _dragGhostStartLocal.y;
                var gOx = parseFloat(_dragGhostEl.dataset.ox) || 0;
                var gOy = parseFloat(_dragGhostEl.dataset.oy) || 0;
                _dragGhostEl.style.left = (gOx + gDx) + 'px';
                _dragGhostEl.style.top = (gOy + gDy) + 'px';
                _dragPendingDx = gDx;
                _dragPendingDy = gDy;
                for (var dai = 0; dai < _dragNearbyAnnotations.length; dai++) {
                    var dna = _dragNearbyAnnotations[dai];
                    dna.an.pos[0] = dna.startX + gDx;
                    dna.an.pos[1] = dna.startY + gDy;
                    if (dna.an._domEl) {
                        dna.an._domEl.style.left = dna.an.pos[0] + 'px';
                        dna.an._domEl.style.top = dna.an.pos[1] + 'px';
                    }
                }
            } else {
                var node = _nodes[_dragNodeId];
                if (node) {
                    var dx = local.x - _dragOffsetX - node.pos[0];
                    var dy = local.y - _dragOffsetY - node.pos[1];
                    if (_dragIsMultiSelect && _dragStartPositions) {
                        _dragPendingDx = dx;
                        _dragPendingDy = dy;
                        for (var mid in _dragStartPositions) {
                            if (!_dragStartPositions.hasOwnProperty(mid)) continue;
                            var mn = _nodes[mid];
                            if (!mn) continue;
                            mn.pos[0] = Math.max(0, _dragStartPositions[mid].x + dx);
                            mn.pos[1] = Math.max(0, _dragStartPositions[mid].y + dy);
                            var mel = document.getElementById('nd-' + mid);
                            if (mel) {
                                mel.style.left = mn.pos[0] + 'px';
                                mel.style.top = mn.pos[1] + 'px';
                            }
                        }
                        _updateAffectedConnections();
                    } else {
                        node.pos[0] = Math.max(0, local.x - _dragOffsetX);
                        node.pos[1] = Math.max(0, local.y - _dragOffsetY);
                        var el = document.getElementById('nd-' + _dragNodeId);
                        if (el) {
                            el.style.left = node.pos[0] + 'px';
                            el.style.top = node.pos[1] + 'px';
                        }
                        _updateAffectedConnections();
                    }
                }
            }
            return;
        }

        if (_isConnecting && _tmpPathEl) {
            var fromCenter = _getPortCenter(_connFromNodeId, _connFromPortKey, _connFromDir);
            if (fromCenter) {
                var d;
                if (_connFromDir === 'o') {
                    d = _bezier(fromCenter.x, fromCenter.y, local.x, local.y);
                } else {
                    d = _bezier(local.x, local.y, fromCenter.x, fromCenter.y);
                }
                _tmpPathEl.setAttribute('d', d);
            }
            return;
        }
    }

    function _checkLineDeleteAtPoint(clientX, clientY) {
        if (!_connSvgEl) return;
        var local = _screenToLocal(clientX, clientY);
        var threshold = 12 / _vpScale;
        var toRemove = null;
        var minDist = Infinity;
        for (var i = 0; i < _connections.length; i++) {
            var conn = _connections[i];
            var fromNode = _nodes[conn.origin_id];
            var toNode = _nodes[conn.target_id];
            if (!fromNode || !toNode) continue;
            var fromPort = fromNode.outputs[conn.origin_slot];
            var toPort = toNode.inputs[conn.target_slot];
            if (!fromPort || !toPort) continue;
            var fe = _getPortCenter(conn.origin_id, fromPort._portKey, 'o');
            var te = _getPortCenter(conn.target_id, toPort._portKey, 'i');
            if (!fe || !te) continue;
            var dist = _pointToBezierDist(local.x, local.y, fe.x, fe.y, te.x, te.y);
            if (dist < threshold && dist < minDist) {
                minDist = dist;
                toRemove = conn;
            }
        }
        if (toRemove) {
            _removeConnectionById(toRemove.id);
            if (window._autoEditor && window._autoEditor.updateStatusBar) {
                window._autoEditor.updateStatusBar();
            }
        }
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

    function _onCanvasMouseUp(e) {
        if (_lineDeleteDragging) {
            _lineDeleteDragging = false;
        }

        if (_isPanning) {
            _isPanning = false;
            _canvasArea.style.cursor = '';
        }

        if (_isSelecting) {
            _isSelecting = false;
            var selBox = document.getElementById('sel-box');
            if (selBox) {
                selBox.style.display = 'none';
                selBox.style.width = '0';
                selBox.style.height = '0';
            }
        }

        if (_isDraggingNode) {
            if (_dragRAF) {
                cancelAnimationFrame(_dragRAF);
                _dragRAF = 0;
            }

            if (_dragGhostEl) {
                var pdx = _dragPendingDx;
                var pdy = _dragPendingDy;
                var draggedNodeIds = [];
                if (_dragIsMultiSelect && _dragStartPositions) {
                    for (var fid in _dragStartPositions) {
                        if (!_dragStartPositions.hasOwnProperty(fid)) continue;
                        var fn = _nodes[fid];
                        if (!fn) continue;
                        fn.pos[0] = Math.max(0, _dragStartPositions[fid].x + pdx);
                        fn.pos[1] = Math.max(0, _dragStartPositions[fid].y + pdy);
                        draggedNodeIds.push(fid);
                        var fel = document.getElementById('nd-' + fid);
                        if (fel) {
                            fel.style.left = fn.pos[0] + 'px';
                            fel.style.top = fn.pos[1] + 'px';
                            fel.style.opacity = '';
                        }
                    }
                } else {
                    var fn = _nodes[_dragNodeId];
                    if (fn) {
                        fn.pos[0] = fn.pos[0] + pdx;
                        fn.pos[1] = fn.pos[1] + pdy;
                        draggedNodeIds.push(_dragNodeId);
                        var fel = document.getElementById('nd-' + _dragNodeId);
                        if (fel) {
                            fel.style.left = fn.pos[0] + 'px';
                            fel.style.top = fn.pos[1] + 'px';
                            fel.style.opacity = '';
                        }
                    }
                }
                _dragGhostEl.remove();
                _dragGhostEl = null;
                _dragGhostStartLocal = null;
                _dragNearbyAnnotations = [];
            } else {
                if (_dragIsMultiSelect && _dragStartPositions && (_dragPendingDx !== 0 || _dragPendingDy !== 0)) {
                    for (var mfid in _dragStartPositions) {
                        if (!_dragStartPositions.hasOwnProperty(mfid)) continue;
                        var mfn = _nodes[mfid];
                        if (!mfn) continue;
                        mfn.pos[0] = Math.max(0, _dragStartPositions[mfid].x + _dragPendingDx);
                        mfn.pos[1] = Math.max(0, _dragStartPositions[mfid].y + _dragPendingDy);
                        var mfel = document.getElementById('nd-' + mfid);
                        if (mfel) {
                            mfel.style.left = mfn.pos[0] + 'px';
                            mfel.style.top = mfn.pos[1] + 'px';
                        }
                    }
                }
                var el = document.getElementById('nd-' + _dragNodeId);
                if (el) {
                    el.classList.remove('drag');
                    el.style.opacity = '';
                }
            }

            if (_connSvgEl) _connSvgEl.style.opacity = '';

            var node = _nodes[_dragNodeId];
            if (node && node._domEl) {
                node.size = [node._domEl.offsetWidth || 220, node._domEl.offsetHeight || 100];
            }
            _isDraggingNode = false;
            _dragNodeId = null;
            _dragStartPositions = {};
            _dragIsMultiSelect = false;
            _dragPendingDx = 0;
            _dragPendingDy = 0;
            _dragNearbyAnnotations = [];
            _renderAllConnections();
            _updateMinimap();
        }

        if (_isConnecting) {
            var portEl = e.target.closest('.pt');
            if (portEl) {
                var toNodeId = parseInt(portEl.dataset.n);
                var toPortKey = portEl.dataset.p;
                var toDir = portEl.dataset.d;

                if (toNodeId !== _connFromNodeId && toDir !== _connFromDir) {
                    var fromNode = _nodes[_connFromNodeId];
                    var toNode = _nodes[toNodeId];
                    if (fromNode && toNode) {
                        var fromSlot = -1, toSlot = -1;
                        if (_connFromDir === 'o') {
                            for (var i = 0; i < fromNode.outputs.length; i++) {
                                if (fromNode.outputs[i]._portKey === _connFromPortKey) { fromSlot = i; break; }
                            }
                            for (var i = 0; i < toNode.inputs.length; i++) {
                                if (toNode.inputs[i]._portKey === toPortKey) { toSlot = i; break; }
                            }
                        } else {
                            for (var i = 0; i < fromNode.inputs.length; i++) {
                                if (fromNode.inputs[i]._portKey === _connFromPortKey) { fromSlot = i; break; }
                            }
                            for (var i = 0; i < toNode.outputs.length; i++) {
                                if (toNode.outputs[i]._portKey === toPortKey) { toSlot = i; break; }
                            }
                            var tmpNode = fromNode; fromNode = toNode; toNode = tmpNode;
                            var tmpSlot = fromSlot; fromSlot = toSlot; toSlot = tmpSlot;
                        }
                        if (fromSlot >= 0 && toSlot >= 0) {
                            var fromPortDef = fromNode.outputs[fromSlot];
                            var toPortDef = toNode.inputs[toSlot];
                            var fromType = fromPortDef.type || 'any';
                            var toType = toPortDef.type || 'any';
                            if (fromType !== toType && fromType !== 'any' && toType !== 'any') {
                                if (window.AutomationApp && window.AutomationApp.showToast) {
                                    window.AutomationApp.showToast('端口类型不匹配: ' + _toZh(fromType) + ' ≠ ' + _toZh(toType), 'warn');
                                }
                            } else {
                                _addConnection(fromNode.id, fromSlot, toNode.id, toSlot);
                            }
                        }
                    }
                }
            }
            if (_tmpPathEl) { _tmpPathEl.remove(); _tmpPathEl = null; }
            _isConnecting = false;
            _connFromNodeId = null;
            _connFromPortKey = null;
            _connFromDir = null;
            _connFromPortType = null;
        }
    }

    function _onCanvasWheel(e) {
        e.preventDefault();
        var r = _canvasArea.getBoundingClientRect();
        var mx = e.clientX - r.left;
        var my = e.clientY - r.top;
        var factor = e.deltaY > 0 ? 0.92 : 1.08;
        _setZoom(_vpScale * factor, mx, my);
    }

    function _updateSelectionFromBox() {
        var selBox = document.getElementById('sel-box');
        if (!selBox || selBox.style.display === 'none') return;
        var bx = parseFloat(selBox.style.left) || 0;
        var by = parseFloat(selBox.style.top) || 0;
        var bw = parseFloat(selBox.style.width) || 0;
        var bh = parseFloat(selBox.style.height) || 0;
        if (bw < 5 && bh < 5) return;

        var cvRect = _canvasArea.getBoundingClientRect();
        var absX = bx + cvRect.left;
        var absY = by + cvRect.top;

        _selectedNodes = [];
        for (var i = 0; i < _nodeList.length; i++) {
            var node = _nodeList[i];
            var el = node._domEl || document.getElementById('nd-' + node.id);
            if (!el) continue;
            var r = el.getBoundingClientRect();
            if (r.left < absX + bw && r.right > absX && r.top < absY + bh && r.bottom > absY) {
                _selectedNodes.push(node);
                el.classList.add('sel');
            } else {
                el.classList.remove('sel');
            }
        }
    }

    function _onCanvasDblClick(e) {
        var nodeEl = e.target.closest('.nd');
        if (!nodeEl) return;
        var nid = parseInt(nodeEl.dataset.id);
        var node = _nodes[nid];
        if (!node) return;
        if (node._defKey && node._defKey.indexOf('call_script') >= 0) {
            if (window.AutomationBlockEditor) {
                AutomationBlockEditor.open(node);
            }
        }
    }

    var _graphAPI = {
        _nodes: _nodeList,
        _links: _linksSparse,

        getNodeById: function(id) {
            return _nodes[id] || null;
        },

        getNodes: function() {
            return _nodeList;
        },

        createNode: function(type) {
            return _createNodeData(type);
        },

        add: function(node) {
            _addNode(node);
        },

        remove: function(node) {
            if (typeof node === 'object' && node !== null) {
                _removeNodeById(node.id);
            }
        },

        connect: function(fromNodeId, fromSlot, toNodeId, toSlot) {
            return _addConnection(fromNodeId, fromSlot, toNodeId, toSlot);
        },

        clear: function() {
            _connections = [];
            _linksSparse = [];
            _nodeList.length = 0;
            _nodes = {};
            _selectedNodeId = null;
            _selectedNodes = [];
            _nextNodeId = 1;
            _nextLinkId = 1;
            if (_nodeLayerEl) _nodeLayerEl.innerHTML = '';
            if (_connSvgEl) _connSvgEl.innerHTML = '';
            if (AutomationCore) {
                AutomationCore.clearAnnotations();
                AutomationCore.clearGroups();
            }
            AutomationCore._notifyGraphChange();
        },

        setNextNodeId: function(id) {
            if (typeof id === 'number' && id > _nextNodeId) {
                _nextNodeId = id;
            }
        },

        get onNodeAdded() { return _onNodeAdded; },
        set onNodeAdded(fn) { _onNodeAdded = fn; },
        get onNodeRemoved() { return _onNodeRemoved; },
        set onNodeRemoved(fn) { _onNodeRemoved = fn; },
        get onConnectionChange() { return _onConnectionChange; },
        set onConnectionChange(fn) { _onConnectionChange = fn; }
    };

    var _canvasAPI = {
        canvas: null,
        ds: {
            get scale() { return _vpScale; },
            get offset() { return [_vpOffset.x, _vpOffset.y]; }
        },

        selectNode: function(node) {
            if (node) _selectNodeById(node.id);
            else _deselectAll();
        },

        setDirty: function() {},

        getNodeAt: function(x, y) {
            var local = _screenToLocal(x, y);
            for (var i = _nodeList.length - 1; i >= 0; i--) {
                var n = _nodeList[i];
                if (local.x >= n.pos[0] && local.x <= n.pos[0] + (n.size[0] || 220) &&
                    local.y >= n.pos[1] && local.y <= n.pos[1] + (n.size[1] || 100)) {
                    return n;
                }
            }
            return null;
        },

        resize: function() {
            _renderAllConnections();
            _updateMinimap();
        },

        get onNodeSelected() { return _onNodeSelected; },
        set onNodeSelected(fn) { _onNodeSelected = fn; },
        get onNodeDeselected() { return _onNodeDeselected; },
        set onNodeDeselected(fn) { _onNodeDeselected = fn; }
    };

export const AutomationCore = {
        lgGraphObj: _graphAPI,
        lgCanvas: _canvasAPI,
        selectedNode: null,
        executionState: 'IDLE',
        _onGraphChange: null,
        onGraphChange: function(callback) {
            this._onGraphChange = callback;
        },
        _notifyGraphChange: function() {
            if (this._onGraphChange) {
                this._onGraphChange();
            }
        },

        init: function(canvasAreaEl) {
            _canvasArea = canvasAreaEl;
            _canvasAPI.canvas = canvasAreaEl;

            _viewportEl = document.getElementById('cv-vp');
            if (!_viewportEl) {
                _viewportEl = document.createElement('div');
                _viewportEl.id = 'cv-vp';
                _viewportEl.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;transform-origin:0 0;';
                _canvasArea.appendChild(_viewportEl);
            }

            _bgEl = document.getElementById('cv-bg');
            if (!_bgEl) {
                _bgEl = document.createElement('div');
                _bgEl.id = 'cv-bg';
                _bgEl.style.cssText = 'position:absolute;top:-10000px;left:-10000px;width:20000px;height:20000px;' +
                    'background-image:radial-gradient(circle,rgba(255,255,255,0.04) 1px,transparent 1px);' +
                    'background-size:24px 24px;pointer-events:none;';
                _viewportEl.appendChild(_bgEl);
            }

            _connSvgEl = document.getElementById('conn-l');
            if (!_connSvgEl) {
                _connSvgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                _connSvgEl.id = 'conn-l';
                _connSvgEl.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
                _connSvgEl.style.cssText = 'position:absolute;top:0;left:0;width:20000px;height:20000px;pointer-events:none;z-index:1;overflow:visible;';
                _viewportEl.appendChild(_connSvgEl);
            }
            _connSvgEl.innerHTML = '';

            _nodeLayerEl = document.getElementById('nd-l');
            if (!_nodeLayerEl) {
                _nodeLayerEl = document.createElement('div');
                _nodeLayerEl.id = 'nd-l';
                _nodeLayerEl.style.cssText = 'position:absolute;top:0;left:0;width:20000px;height:20000px;z-index:2;';
                _viewportEl.appendChild(_nodeLayerEl);
            }
            _nodeLayerEl.innerHTML = '';

            _groupLayerEl = document.getElementById('gp-l');
            if (!_groupLayerEl) {
                _groupLayerEl = document.createElement('div');
                _groupLayerEl.id = 'gp-l';
                _groupLayerEl.style.cssText = 'position:absolute;top:0;left:0;width:20000px;height:20000px;z-index:3;pointer-events:none;';
                _viewportEl.appendChild(_groupLayerEl);
            }
            _groupLayerEl.innerHTML = '';

            _annotationLayerEl = document.getElementById('an-l');
            if (!_annotationLayerEl) {
                _annotationLayerEl = document.createElement('div');
                _annotationLayerEl.id = 'an-l';
                _annotationLayerEl.style.cssText = 'position:absolute;top:0;left:0;width:20000px;height:20000px;z-index:4;pointer-events:none;';
                _viewportEl.appendChild(_annotationLayerEl);
            }
            _annotationLayerEl.innerHTML = '';

            _canvasArea.addEventListener('mousedown', _onCanvasMouseDown);
            document.addEventListener('mousemove', _onCanvasMouseMove);
            document.addEventListener('mouseup', _onCanvasMouseUp);
            _canvasArea.addEventListener('wheel', _onCanvasWheel, { passive: false });
            _canvasArea.addEventListener('dblclick', _onCanvasDblClick);

            _canvasArea.addEventListener('contextmenu', function(e) { e.preventDefault(); });

            document.addEventListener('keydown', function(e) {
                if (e.code === 'Space' && !e.target.closest('input,textarea,select')) {
                    _spaceHeld = true;
                    _canvasArea.style.cursor = 'grab';
                }
            });
            document.addEventListener('keyup', function(e) {
                if (e.code === 'Space') {
                    _spaceHeld = false;
                    if (!_isPanning) _canvasArea.style.cursor = '';
                }
            });

            _updateViewport();
            console.log('[AutomationCore] DOM渲染引擎初始化完成');
        },

        addNodeAtCenter: function(nodeType) {
            var node = _createNodeData(nodeType);
            if (!node) return null;
            var r = _canvasArea.getBoundingClientRect();
            var cx = (r.width / 2 - _vpOffset.x) / _vpScale;
            var cy = (r.height / 2 - _vpOffset.y) / _vpScale;
            node.pos[0] = cx - (node.size[0] || 110);
            node.pos[1] = cy - (node.size[1] || 50);
            _addNode(node);
            return node;
        },

        addNodeAtMouse: function(nodeType, event) {
            var node = _createNodeData(nodeType);
            if (!node) return null;
            var local = _screenToLocal(event.clientX, event.clientY);
            node.pos[0] = local.x - 60;
            node.pos[1] = local.y - 20;
            _addNode(node);
            return node;
        },

        addNodeAtPosition: function(nodeType, x, y) {
            var node = _createNodeData(nodeType);
            if (!node) return null;
            node.pos[0] = x;
            node.pos[1] = y;
            _addNode(node);
            return node;
        },

        clear: function() {
            _graphAPI.clear();
            this.selectedNode = null;
        },

        selectNode: function(node) {
            if (node) _selectNodeById(node.id);
            else _deselectAll();
        },

        refreshNode: function(node) {
            if (node) _refreshNodeDOM(node);
        },

        refreshAllConnections: function() {
            _renderAllConnections();
        },

        setZoom: function(scale, cx, cy) {
            _setZoom(scale, cx, cy);
        },

        setViewport: function(offsetX, offsetY, scale) {
            _vpOffset.x = offsetX;
            _vpOffset.y = offsetY;
            _vpScale = Math.max(0.15, Math.min(3, scale));
            _updateViewport();
            _updateMinimap();
        },

        zoomIn: function() {
            var r = _canvasArea.getBoundingClientRect();
            _setZoom(_vpScale * 1.15, r.width / 2, r.height / 2);
        },

        zoomOut: function() {
            var r = _canvasArea.getBoundingClientRect();
            _setZoom(_vpScale / 1.15, r.width / 2, r.height / 2);
        },

        zoomReset: function() {
            _vpScale = 1;
            _vpOffset = { x: 100, y: 100 };
            _updateViewport();
            _updateMinimap();
        },

        getZoomLevel: function() {
            return _vpScale;
        },

        screenToLocal: function(cx, cy) {
            return _screenToLocal(cx, cy);
        },

        updateMinimap: function() {
            _updateMinimap();
        },

        navigateMinimap: function(mx, my) {
            _navigateMinimap(mx, my);
        },

        setNodeHighlight: function(nodeId, state) {
            var el = document.getElementById('nd-' + nodeId);
            if (!el) return;
            el.classList.remove('executing', 'check-pass', 'check-fail', 'triggered');
            if (state) el.classList.add(state);
        },

        clearAllHighlights: function() {
            var highlighted = _nodeLayerEl ? _nodeLayerEl.querySelectorAll('.nd.executing,.nd.check-pass,.nd.check-fail,.nd.triggered') : [];
            for (var i = 0; i < highlighted.length; i++) {
                highlighted[i].classList.remove('executing', 'check-pass', 'check-fail', 'triggered');
            }
        },

        getViewportOffset: function() { return _vpOffset; },
        getViewportScale: function() { return _vpScale; },
        getNodes: function() { return _nodeList; },
        getConnections: function() { return _connections; },
        getSelectedNodes: function() { return _selectedNodes; },
        deleteSelectedNodes: function() {
            for (var i = 0; i < _selectedNodes.length; i++) {
                _removeNodeById(_selectedNodes[i].id);
            }
            _selectedNodes = [];
            _updateMinimap();
        },
        disconnectNode: function(nodeId) {
            _removeConnectionsForNode(nodeId);
        },
        selectAll: function() {
            _selectedNodes = [];
            for (var i = 0; i < _nodeList.length; i++) {
                var node = _nodeList[i];
                _selectedNodes.push(node);
                var el = node._domEl || document.getElementById('nd-' + node.id);
                if (el) el.classList.add('sel');
            }
        },

        addAnnotation: function(x, y, text, color) {
            var id = _nextAnnotationId++;
            var an = {
                id: id,
                pos: [x, y],
                text: text || '双击编辑注释',
                color: color || '#fbbf24',
                bgColor: 'linear-gradient(135deg,rgba(251,191,36,.38),rgba(251,191,36,.28))',
                collapsed: false,
                _domEl: null
            };
            _annotations.push(an);
            _renderAnnotation(an);
            AutomationCore._notifyGraphChange();
            return an;
        },
        removeAnnotation: function(id) {
            for (var i = 0; i < _annotations.length; i++) {
                if (_annotations[i].id === id) {
                    if (_annotations[i]._domEl) _annotations[i]._domEl.remove();
                    _annotations.splice(i, 1);
                    AutomationCore._notifyGraphChange();
                    break;
                }
            }
        },
        getAnnotations: function() { return _annotations; },
        clearAnnotations: function() {
            _annotations = [];
            _nextAnnotationId = 1;
            if (_annotationLayerEl) _annotationLayerEl.innerHTML = '';
        },

        addGroup: function(x, y, w, h, title, color) {
            var id = _nextGroupId++;
            var gp = {
                id: id,
                pos: [x, y],
                size: [w || 300, h || 200],
                title: title || '分组',
                color: color || '#3b82f6',
                bgColor: 'rgba(59,130,246,.08)',
                _domEl: null
            };
            _groups.push(gp);
            _renderGroup(gp);
            AutomationCore._notifyGraphChange();
            return gp;
        },
        removeGroup: function(id) {
            for (var i = 0; i < _groups.length; i++) {
                if (_groups[i].id === id) {
                    if (_groups[i]._domEl) _groups[i]._domEl.remove();
                    _groups.splice(i, 1);
                    AutomationCore._notifyGraphChange();
                    break;
                }
            }
        },
        getGroups: function() { return _groups; },
        clearGroups: function() {
            _groups = [];
            _nextGroupId = 1;
            if (_groupLayerEl) _groupLayerEl.innerHTML = '';
        },

        clearAll: function() {
            _graphAPI.clear();
            AutomationCore.clearAnnotations();
            AutomationCore.clearGroups();
            AutomationCore.selectedNode = null;
        },

        setLineDeleteMode: function(enabled) {
            _lineDeleteMode = !!enabled;
            _lineDeleteDragging = false;
            if (_lineDeleteMode) {
                _canvasArea.style.cursor = 'crosshair';
            } else {
                _canvasArea.style.cursor = '';
            }
        },
        isLineDeleteMode: function() {
            return _lineDeleteMode;
        }
    };

window.AutomationCore = AutomationCore;
