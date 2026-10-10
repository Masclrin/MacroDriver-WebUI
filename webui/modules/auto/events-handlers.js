'use strict';

    window.AutomationEvents = {
        _highlightedNodes: {},

        init: function() {
            window._automationEvents = {
                onNodeEnter: function(data) {
                    AutomationEvents.highlightNode(data.node_id, 'executing');
                },
                onNodeExit: function(data) {
                    AutomationEvents.unhighlightNode(data.node_id);
                },
                onCheckResult: function(data) {
                    AutomationEvents.flashNode(data.node_id, data.found ? 'check-pass' : 'check-fail');
                },
                onTaskStatus: function(data) {
                    AutomationEvents.updateTaskStatus(data.task_id, data.status);
                },
                onMonitorTrigger: function(data) {
                    AutomationEvents.flashNode(data.node_id, 'triggered');
                },
                onError: function(data) {
                    AutomationEvents.showError(data.message);
                },
                onScriptEnd: function(data) {
                    AutomationEvents.clearAllHighlights();
                    if (window._autoEditor) window._autoEditor.setExecutionState('idle');
                },
                onPluginNotify: function(data) {
                    AutomationEvents.showNotifyPopup(data);
                },
            };
        },

        highlightNode: function(nodeId, state) {
            this._highlightedNodes[nodeId] = state;

            if (window.AutomationCore && AutomationCore.setNodeHighlight) {
                AutomationCore.setNodeHighlight(nodeId, state);
            }
        },

        unhighlightNode: function(nodeId) {
            delete this._highlightedNodes[nodeId];

            if (window.AutomationCore && AutomationCore.setNodeHighlight) {
                AutomationCore.setNodeHighlight(nodeId, null);
            }
        },

        flashNode: function(nodeId, state) {
            if (window.AutomationCore && AutomationCore.setNodeHighlight) {
                AutomationCore.setNodeHighlight(nodeId, state);
                var self = this;
                setTimeout(function() {
                    if (self._highlightedNodes[nodeId]) return;
                    AutomationCore.setNodeHighlight(nodeId, null);
                }, 2000);
            }
        },

        clearAllHighlights: function() {
            for (var nodeId in this._highlightedNodes) {
                if (!this._highlightedNodes.hasOwnProperty(nodeId)) continue;
                this.unhighlightNode(nodeId);
            }
            this._highlightedNodes = {};

            if (window.AutomationCore && AutomationCore.clearAllHighlights) {
                AutomationCore.clearAllHighlights();
            }
        },

        updateTaskStatus: function(taskId, status) {
            console.log('[AutomationEvents] Task', taskId, '->', status);

            if (window._autoEditor) {
                if (status === 'running') {
                    window._autoEditor.setExecutionState('running');
                } else if (status === 'paused') {
                    window._autoEditor.setExecutionState('paused');
                } else if (status === 'stopped' || status === 'completed' || status === 'error') {
                    window._autoEditor.setExecutionState('idle');
                }
            }

            if (status === 'error' && window._autoEditor && window._autoEditor.showToast) {
                window._autoEditor.showToast('任务 ' + taskId + ' 出错', 'error');
            }
        },

        showError: function(message) {
            console.error('[AutomationEvents] Error:', message);
            if (window._autoEditor && window._autoEditor.showToast) {
                window._autoEditor.showToast(message, 'error', 5000);
            }
        },

        _notifyAudioMap: {
            'default': null,
            'info': null,
            'success': null,
            'warning': null,
            'error': null,
            'none': null
        },

        _playNotifySound: function(soundType) {
            if (soundType === 'none') return;
            try {
                var ctx = new (window.AudioContext || window.webkitAudioContext)();
                var osc = ctx.createOscillator();
                var gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                gain.gain.value = 0.15;
                var freqMap = { 'default': 800, 'info': 600, 'success': 880, 'warning': 440, 'error': 330 };
                osc.frequency.value = freqMap[soundType] || 800;
                var typeMap = { 'default': 'sine', 'info': 'sine', 'success': 'sine', 'warning': 'triangle', 'error': 'sawtooth' };
                osc.type = typeMap[soundType] || 'sine';
                osc.start();
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
                osc.stop(ctx.currentTime + 0.5);
            } catch(e) {}
        },

        showNotifyPopup: function(data) {
            var title = data.title || '提示';
            var message = data.message || '';
            var sound = data.sound || 'default';
            var duration = data.duration || 3000;
            var position = data.position || 'bottom-right';

            this._playNotifySound(sound);

            var container = document.getElementById('notify-popup-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'notify-popup-container';
                container.style.cssText = 'position:fixed;z-index:99999;pointer-events:none;display:flex;flex-direction:column;gap:8px;';
                document.body.appendChild(container);
            }

            var posStyle = '';
            if (position === 'bottom-right') posStyle = 'bottom:20px;right:20px;align-items:flex-end;';
            else if (position === 'bottom-left') posStyle = 'bottom:20px;left:20px;align-items:flex-start;';
            else if (position === 'top-right') posStyle = 'top:20px;right:20px;align-items:flex-end;';
            else if (position === 'top-left') posStyle = 'top:20px;left:20px;align-items:flex-start;';
            else posStyle = 'top:50%;left:50%;transform:translate(-50%,-50%);align-items:center;';
            container.style.cssText = container.style.cssText.replace(/(position:fixed;z-index:99999;pointer-events:none;display:flex;flex-direction:column;gap:8px;)/, '$1') + posStyle;
            container.setAttribute('style', 'position:fixed;z-index:99999;pointer-events:none;display:flex;flex-direction:column;gap:8px;' + posStyle);

            var colorMap = { 'default': '#3b82f6', 'info': '#06b6d4', 'success': '#22c55e', 'warning': '#eab308', 'error': '#ef4444' };
            var borderColor = colorMap[sound] || '#3b82f6';

            var popup = document.createElement('div');
            popup.style.cssText = 'pointer-events:auto;min-width:260px;max-width:380px;background:var(--bg,#1e1e2e);border:1px solid ' + borderColor + ';border-radius:8px;padding:12px 16px;box-shadow:0 4px 20px rgba(0,0,0,.4);opacity:0;transform:translateY(10px);transition:all .3s ease;font-family:system-ui,sans-serif;';

            popup.innerHTML = '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">' +
                '<div style="width:4px;height:16px;border-radius:2px;background:' + borderColor + ';flex-shrink:0"></div>' +
                '<div style="font-size:13px;font-weight:600;color:var(--txt,#e2e2e2)">' + title + '</div>' +
                '<div style="margin-left:auto;cursor:pointer;pointer-events:auto;color:var(--txt3,#888);font-size:12px" class="notify-close">&times;</div>' +
                '</div>' +
                '<div style="font-size:12px;color:var(--txt2,#aaa);padding-left:12px;line-height:1.5">' + message + '</div>';

            container.appendChild(popup);

            requestAnimationFrame(function() {
                popup.style.opacity = '1';
                popup.style.transform = 'translateY(0)';
            });

            var closeBtn = popup.querySelector('.notify-close');
            function removePopup() {
                popup.style.opacity = '0';
                popup.style.transform = 'translateY(10px)';
                setTimeout(function() { popup.remove(); }, 300);
            }
            if (closeBtn) closeBtn.addEventListener('click', removePopup);
            setTimeout(removePopup, duration);
        },
    };

export const AutomationEvents = window.AutomationEvents;
export const _automationEvents = window._automationEvents;
