'use strict';

    function _getNode(nodeId) {
        if (window.AutomationCore && AutomationCore.lgGraphObj) {
            return AutomationCore.lgGraphObj.getNodeById(parseInt(nodeId));
        }
        return null;
    }

    window.AutomationTools = {
        _pickMode: false,
        _pickNodeId: null,
        _pickParamKey: null,
        _isRegionPick: false,
        _regionStart: null,
        _screenshotData: null,
        _screenshotOverlay: null,
        _coordMode: 'screen',

        startCoordPick: function(nodeId, paramKey) {
            this._pickNodeId = nodeId;
            this._pickParamKey = paramKey;
            this._isRegionPick = false;
            this._pickMode = true;
            this._regionStart = null;

            var node = _getNode(nodeId);
            var mode = node ? (node.properties.mode || node.properties.capture_mode || 'screen') : 'screen';
            this._coordMode = mode;
            var self = this;

            if (mode === 'screen') {
                self._startScreenCapturePick();
            } else if (mode === 'relative') {
                self._startRelativeCapturePick();
            } else {
                self._startWindowCapturePick();
            }
        },

        startRegionPick: function(nodeId, paramKey) {
            this._pickNodeId = nodeId;
            this._pickParamKey = paramKey || 'rect';
            this._isRegionPick = true;
            this._pickMode = true;
            this._regionStart = null;

            var node = _getNode(nodeId);
            var mode = node ? (node.properties.mode || node.properties.capture_mode || 'screen') : 'screen';
            this._coordMode = mode;
            var self = this;

            if (mode === 'screen') {
                self._startScreenCapturePick();
            } else if (mode === 'relative') {
                self._startRelativeCapturePick();
            } else {
                self._startWindowCapturePick();
            }
        },

        _startScreenCapturePick: function() {
            var self = this;
            if (window._autoEditor) window._autoEditor.showToast('请切换到目标屏幕后点击任意位置截图...', 'inf');
            if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.pick_coordinate) {
                self._pickMode = false; return;
            }
            window.pywebview.api.pick_coordinate('screen').then(function(resp) {
                if (resp && resp.ok && resp.data && resp.data.status === 'picking') {
                    self._pollClickForCapture('screen');
                } else if (resp && resp.ok && resp.data && resp.data.phys_x !== undefined) {
                    self._captureAndShow('screen', resp.data);
                } else { self._pickMode = false; }
            }).catch(function(err) {
                if (window._autoEditor) window._autoEditor.showToast('拾取失败: ' + (err || ''), 'err');
                self._pickMode = false;
            });
        },

        _startWindowCapturePick: function() {
            var self = this;
            if (window._autoEditor) window._autoEditor.showToast('请点击目标窗口进行截图...', 'inf');
            if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.pick_coordinate) {
                self._pickMode = false; return;
            }
            window.pywebview.api.pick_coordinate('window').then(function(resp) {
                if (resp && resp.ok && resp.data) {
                    if (resp.data.status === 'picking') {
                        self._pollClickForCapture('window');
                    } else if (resp.data.phys_x !== undefined) {
                        self._captureAndShow('window', resp.data);
                    } else {
                        self._pickMode = false;
                    }
                } else { self._pickMode = false; }
            }).catch(function(err) {
                if (window._autoEditor) window._autoEditor.showToast('拾取失败: ' + (err || ''), 'err');
                self._pickMode = false;
            });
        },

        _startRelativeCapturePick: function() {
            var self = this;
            if (window._autoEditor) window._autoEditor.showToast('请点击目标窗口进行相对坐标截图...', 'inf');
            if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.pick_coordinate) {
                self._pickMode = false; return;
            }
            window.pywebview.api.pick_coordinate('window').then(function(resp) {
                if (resp && resp.ok && resp.data) {
                    if (resp.data.status === 'picking') {
                        self._pollRelativeCapture();
                    } else if (resp.data.phys_x !== undefined) {
                        var hwnd = resp.data.hwnd;
                        if (hwnd) {
                            window.pywebview.api.relative_capture_pick(hwnd).then(function(r) {
                                if (r && r.ok && r.data && r.data.image) {
                                    self._screenshotData = r.data;
                                    self._showScreenshotOverlay(r.data);
                                } else {
                                    if (window._autoEditor) window._autoEditor.showToast('截图失败', 'err');
                                    self._pickMode = false;
                                }
                            }).catch(function(err) {
                                if (window._autoEditor) window._autoEditor.showToast('截图失败: ' + (err || ''), 'err');
                                self._pickMode = false;
                            });
                        } else {
                            if (window._autoEditor) window._autoEditor.showToast('未找到窗口', 'err');
                            self._pickMode = false;
                        }
                    } else {
                        self._pickMode = false;
                    }
                } else { self._pickMode = false; }
            }).catch(function(err) {
                if (window._autoEditor) window._autoEditor.showToast('拾取失败: ' + (err || ''), 'err');
                self._pickMode = false;
            });
        },

        _pollRelativeCapture: function() {
            var self = this;
            if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.get_pick_result) return;
            if (self._pollRetries === undefined) self._pollRetries = 0;
            self._pollRetries++;
            if (self._pollRetries > 150) {
                if (window._autoEditor) window._autoEditor.showToast('拾取超时(30秒)', 'warn');
                self._pickMode = false;
                self._pollRetries = 0;
                return;
            }
            window.pywebview.api.get_pick_result().then(function(resp) {
                if (resp && resp.ok && resp.data && resp.data.status === 'picking') {
                    setTimeout(function() { self._pollRelativeCapture(); }, 200);
                } else if (resp && resp.ok && resp.data && resp.data.phys_x !== undefined) {
                    self._pollRetries = 0;
                    var hwnd = resp.data.hwnd;
                    if (hwnd) {
                        window.pywebview.api.relative_capture_pick(hwnd).then(function(r) {
                            if (r && r.ok && r.data && r.data.image) {
                                self._screenshotData = r.data;
                                self._showScreenshotOverlay(r.data);
                            } else {
                                if (window._autoEditor) window._autoEditor.showToast('截图失败', 'err');
                                self._pickMode = false;
                            }
                        }).catch(function(err) {
                            if (window._autoEditor) window._autoEditor.showToast('截图失败: ' + (err || ''), 'err');
                            self._pickMode = false;
                        });
                    } else {
                        if (window._autoEditor) window._autoEditor.showToast('未找到窗口', 'err');
                        self._pickMode = false;
                    }
                } else {
                    self._pollRetries = 0;
                    if (window._autoEditor) window._autoEditor.showToast('拾取超时', 'warn');
                    self._pickMode = false;
                }
            }).catch(function() { self._pickMode = false; self._pollRetries = 0; });
        },

        _pollClickForCapture: function(mode) {
            var self = this;
            if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.get_pick_result) return;
            if (self._pollRetries === undefined) self._pollRetries = 0;
            self._pollRetries++;
            if (self._pollRetries > 150) {
                if (window._autoEditor) window._autoEditor.showToast('拾取超时(30秒)', 'warn');
                self._pickMode = false;
                self._pollRetries = 0;
                return;
            }
            window.pywebview.api.get_pick_result().then(function(resp) {
                if (resp && resp.ok && resp.data && resp.data.status === 'picking') {
                    setTimeout(function() { self._pollClickForCapture(mode); }, 200);
                } else if (resp && resp.ok && resp.data && resp.data.phys_x !== undefined) {
                    self._pollRetries = 0;
                    self._captureAndShow(mode, resp.data);
                } else {
                    self._pollRetries = 0;
                    if (window._autoEditor) window._autoEditor.showToast('拾取超时', 'warn');
                    self._pickMode = false;
                }
            }).catch(function() { self._pickMode = false; self._pollRetries = 0; });
        },

        _captureAndShow: function(mode, clickData) {
            var self = this;
            var api = window.pywebview && window.pywebview.api;
            if (!api) return;
            var capturePromise;
            if (mode === 'screen') {
                capturePromise = api.screen_capture_pick();
            } else if (mode === 'relative') {
                capturePromise = api.relative_capture_pick(clickData && clickData.hwnd ? clickData.hwnd : null);
            } else {
                capturePromise = api.window_capture_pick(clickData && clickData.hwnd ? clickData.hwnd : null);
            }
            capturePromise.then(function(resp) {
                if (resp && resp.ok && resp.data && resp.data.image) {
                    self._screenshotData = resp.data;
                    self._showScreenshotOverlay(resp.data);
                } else {
                    if (window._autoEditor) window._autoEditor.showToast('截图失败', 'err');
                    self._pickMode = false;
                }
            }).catch(function(err) {
                if (window._autoEditor) window._autoEditor.showToast('截图失败: ' + (err || ''), 'err');
                self._pickMode = false;
            });
        },

        _showScreenshotOverlay: function(data) {
            var self = this;
            var existing = document.getElementById('screenshot-pick-overlay');
            if (existing) existing.remove();

            var overlay = document.createElement('div');
            overlay.id = 'screenshot-pick-overlay';
            overlay.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:99999;background:#000;cursor:crosshair;';

            var hint = document.createElement('div');
            hint.style.cssText = 'position:fixed;top:10px;left:50%;transform:translateX(-50%);color:#10b981;font-size:16px;font-weight:bold;z-index:100000;';
            hint.textContent = this._isRegionPick ? '在截图上拖动框选区域' : '在截图上点击拾取坐标';
            overlay.appendChild(hint);

            var img = document.createElement('img');
            img.id = 'screenshot-pick-img';
            img.style.cssText = 'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);cursor:crosshair;display:block;';

            var scaleX, scaleY;
            img.onload = function() {
                var winW = window.innerWidth * 0.92;
                var winH = window.innerHeight * 0.88;
                var imgW = data.width;
                var imgH = data.height;
                var imgAspect = imgW / imgH;
                var winAspect = winW / winH;
                var natW = img.naturalWidth, natH = img.naturalHeight;
                
                
                var displayW, displayH;
                if (imgAspect > winAspect) {
                    displayW = winW;
                    displayH = winW / imgAspect;
                } else {
                    displayH = winH;
                    displayW = winH * imgAspect;
                }
                
                img.style.width = displayW + 'px';
                img.style.height = displayH + 'px';
                
                scaleX = data.width / displayW;
                scaleY = data.height / displayH;
            };
            img.src = 'data:image/png;base64,' + data.image;

            var canvas = document.createElement('canvas');
            canvas.id = 'screenshot-pick-canvas';
            canvas.style.cssText = 'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);pointer-events:none;';
            overlay.appendChild(img);
            overlay.appendChild(canvas);

            var closeBtn = document.createElement('button');
            closeBtn.textContent = '取消 (Esc)';
            closeBtn.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);padding:8px 20px;background:#ef4444;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:14px;z-index:100000;';
            closeBtn.onclick = function() { self._hideScreenshotOverlay(); };
            overlay.appendChild(closeBtn);

            document.body.appendChild(overlay);
            this._screenshotOverlay = overlay;

            var coordMode = this._coordMode || data.mode || 'screen';
            var regionStart = null;

            function calcLogicCoords(px, py) {
                var virtualW = data.virtual_width || data.width;
                var virtualH = data.virtual_height || data.height;
                if (coordMode === 'relative') {
                    return {
                        x: Math.round(px / virtualW * 1000) / 1000,
                        y: Math.round(py / virtualH * 1000) / 1000,
                        displayX: Math.round(px / virtualW * 1000) / 1000,
                        displayY: Math.round(py / virtualH * 1000) / 1000
                    };
                } else if (coordMode === 'screen') {
                    var physX = data.origin_x + px;
                    var physY = data.origin_y + py;
                    return {
                        x: Math.round(physX),
                        y: Math.round(physY),
                        displayX: Math.round(physX),
                        displayY: Math.round(physY)
                    };
                } else {
                    return {
                        x: Math.round(px),
                        y: Math.round(py),
                        displayX: Math.round(px),
                        displayY: Math.round(py)
                    };
                }
            }

            function onRegionMouseMove(e) {
                if (!self._isRegionPick || !regionStart) return;
                var rect = img.getBoundingClientRect();
                var px = (e.clientX - rect.left) * scaleX;
                var py = (e.clientY - rect.top) * scaleY;
                var ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                var sx = regionStart.x / scaleX, sy = regionStart.y / scaleY;
                var ex = (e.clientX - rect.left), ey = (e.clientY - rect.top);
                var rx = Math.min(sx, ex), ry = Math.min(sy, ey);
                var rw = Math.abs(ex - sx), rh = Math.abs(ey - sy);
                ctx.fillStyle = 'rgba(16,185,129,0.2)';
                ctx.fillRect(rx, ry, rw, rh);
                ctx.strokeStyle = '#10b981';
                ctx.lineWidth = 2;
                ctx.setLineDash([6, 3]);
                ctx.strokeRect(rx, ry, rw, rh);
                ctx.setLineDash([]);
                hint.textContent = Math.round(Math.abs(px - regionStart.x)) + ' x ' + Math.round(Math.abs(py - regionStart.y));
            }

            function onRegionMouseUp(e) {
                if (!self._isRegionPick || !regionStart) return;
                var rect = img.getBoundingClientRect();
                var px = (e.clientX - rect.left) * scaleX;
                var py = (e.clientY - rect.top) * scaleY;
                var rw = Math.abs(px - regionStart.x);
                var rh = Math.abs(py - regionStart.y);
                if (rw < 5 || rh < 5) { regionStart = null; return; }
                var x1 = Math.min(regionStart.x, px), y1 = Math.min(regionStart.y, py);
                var virtualW = data.virtual_width || data.width;
                var virtualH = data.virtual_height || data.height;
                var logicRect;
                var displayRect;
                if (coordMode === 'relative') {
                    logicRect = [
                        Math.round(x1 / virtualW * 1000) / 1000,
                        Math.round(y1 / virtualH * 1000) / 1000,
                        Math.round(rw / virtualW * 1000) / 1000,
                        Math.round(rh / virtualH * 1000) / 1000
                    ];
                    displayRect = logicRect;
                } else if (coordMode === 'screen') {
                    var physX1 = data.origin_x + x1;
                    var physY1 = data.origin_y + y1;
                    logicRect = [
                        Math.round(physX1),
                        Math.round(physY1),
                        Math.round(rw),
                        Math.round(rh)
                    ];
                    displayRect = logicRect;
                } else {
                    logicRect = [
                        Math.round(x1),
                        Math.round(y1),
                        Math.round(rw),
                        Math.round(rh)
                    ];
                    displayRect = logicRect;
                }
                document.removeEventListener('mousemove', onRegionMouseMove);
                document.removeEventListener('mouseup', onRegionMouseUp);
                self._fillRegionInput(logicRect);
                if ((data.mode === 'window' || data.mode === 'relative') && data.hwnd) {
                    self._fillWindowInfo(data);
                }
                if (window._autoEditor) window._autoEditor.showToast('区域拾取成功: ' + displayRect.join(', '), 'ok');
                self._hideScreenshotOverlay();
                regionStart = null;
            }

            img.addEventListener('mousedown', function(e) {
                e.preventDefault();
                var rect = img.getBoundingClientRect();
                var px = (e.clientX - rect.left) * scaleX;
                var py = (e.clientY - rect.top) * scaleY;

                if (self._isRegionPick) {
                    regionStart = { x: px, y: py };
                    canvas.width = img.clientWidth;
                    canvas.height = img.clientHeight;
                    document.addEventListener('mousemove', onRegionMouseMove);
                    document.addEventListener('mouseup', onRegionMouseUp);
                } else {
                    var coords = calcLogicCoords(px, py);
                    self._fillCoordInput(coords.x, coords.y);
                    if ((data.mode === 'window' || data.mode === 'relative') && data.hwnd) {
                        self._fillWindowInfo(data);
                    }
                    if (window._autoEditor) window._autoEditor.showToast('坐标拾取成功: (' + coords.displayX + ', ' + coords.displayY + ')', 'ok');
                    self._hideScreenshotOverlay();
                }
            });

            document.addEventListener('keydown', function escHandler(e) {
                if (e.key === 'Escape') {
                    self._hideScreenshotOverlay();
                    document.removeEventListener('keydown', escHandler);
                }
            });
        },

        _fillWindowInfo: function(data) {
            if (!this._pickNodeId) return;
            var node = _getNode(this._pickNodeId);
            if (!node) return;
            if (data.hwnd) node.properties.hwnd_var = String(data.hwnd);
            if (data.mode) {
                if (node.properties.capture_mode !== undefined) {
                    node.properties.capture_mode = data.mode;
                } else {
                    node.properties.mode = data.mode;
                }
            }
            if (window.AutomationProperty._currentNode === node) window.AutomationProperty.render(node);
            if (window.AutomationCore && AutomationCore.refreshNode) AutomationCore.refreshNode(node);
        },

        _hideScreenshotOverlay: function() {
            var overlay = document.getElementById('screenshot-pick-overlay');
            if (overlay) overlay.remove();
            this._screenshotOverlay = null;
            this._screenshotData = null;
            this._pickMode = false;
            this._pickNodeId = null;
            this._pickParamKey = null;
            this._isRegionPick = false;
            this._regionStart = null;
        },

        _fillCoordInput: function(x, y) {
            if (!this._pickNodeId) return;
            var node = _getNode(this._pickNodeId);
            if (!node) return;

            var key = this._pickParamKey;
            if (key === 'x' || key === 'y') {
                node.properties.x = x;
                node.properties.y = y;
            } else if (key === 'rect') {
                node.properties.rect = [x, y, 10, 10];
            } else {
                node.properties[key] = x;
                var def = window.AutomationNodes ? AutomationNodes.getNodeDef(node._defKey) : null;
                if (def && def.params_schema) {
                    var schema = def.params_schema;
                    var hasY = false;
                    for (var sk in schema) {
                        if (schema.hasOwnProperty(sk) && sk !== key && schema[sk].coordRef) {
                            node.properties[sk] = y;
                            hasY = true;
                            break;
                        }
                    }
                    if (!hasY && schema['y']) {
                        node.properties['y'] = y;
                    }
                }
            }
            if (window.AutomationProperty._currentNode === node) {
                window.AutomationProperty.render(node);
            }
            if (window.AutomationCore && AutomationCore.refreshNode) {
                AutomationCore.refreshNode(node);
            }
            if (window.AutomationCore && window.AutomationCore._notifyGraphChange) {
                window.AutomationCore._notifyGraphChange();
            }
        },

        _fillRegionInput: function(rect) {
            if (!this._pickNodeId) return;
            var node = _getNode(this._pickNodeId);
            if (!node) return;

            node.properties[this._pickParamKey || 'rect'] = rect;
            if (window.AutomationProperty._currentNode === node) {
                window.AutomationProperty.render(node);
            }
            if (window.AutomationCore && window.AutomationCore._notifyGraphChange) {
                window.AutomationCore._notifyGraphChange();
            }
            if (window.AutomationCore && AutomationCore.refreshNode) {
                AutomationCore.refreshNode(node);
            }
        },
    };

export const AutomationTools = window.AutomationTools;