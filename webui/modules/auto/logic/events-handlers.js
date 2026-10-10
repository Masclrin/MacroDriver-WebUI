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
                onPluginEvent: function(data) {
                    AutomationEvents.handlePluginEvent(data);
                },
            };
            if (window.parent && window.parent !== window) {
                window.parent._automationEvents = window._automationEvents;
            }
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

        handlePluginEvent: function(data) {
            if (!data) return;
            var eventName = data.event_name;
            var eventData = data.data || {};
            if (!eventName) return;

            if (eventName === 'plugin_reloaded') {
                // 原来是 get_node_defs —— 后端根本不存在这个方法（正确名是
                // get_node_definitions），守卫恒为 false，导致插件重载后
                // 前端节点定义永远停留在旧版本且无任何报错。
                // 响应信封为 {ok, data:{nodes, engines}}，需取 data.nodes。
                if (window.pywebview && window.pywebview.api && window.pywebview.api.get_node_definitions) {
                    window.pywebview.api.get_node_definitions().then(function(resp) {
                        var defs = (resp && resp.ok && resp.data) ? (resp.data.nodes || resp.data) : null;
                        if (defs && window.AutomationNodes && AutomationNodes.registerPluginNodes) {
                            var pluginDefs = {};
                            for (var k in defs) {
                                if (defs.hasOwnProperty(k) && k.indexOf('plugin/') === 0) {
                                    pluginDefs[k] = defs[k];
                                }
                            }
                            AutomationNodes.registerPluginNodes(pluginDefs);
                        }
                    }).catch(function(e) {
                        console.error('[AutomationEvents] 重载插件节点定义失败:', e);
                    });
                }
            }

            if (window.AutomationNodes && AutomationNodes._nodeDefs) {
                for (var typeKey in AutomationNodes._nodeDefs) {
                    if (!AutomationNodes._nodeDefs.hasOwnProperty(typeKey)) continue;
                    if (!typeKey.startsWith('plugin/')) continue;
                    var def = AutomationNodes._nodeDefs[typeKey];
                    if (def.onPluginEvent && typeof def.onPluginEvent === 'function') {
                        try {
                            def.onPluginEvent(eventName, eventData);
                        } catch(e) {
                            console.error('[AutomationEvents] 插件 onPluginEvent 错误:', typeKey, e);
                        }
                    }
                }
            }
        },
    };

export const AutomationEvents = window.AutomationEvents;
export function getAutomationEvents() { return window._automationEvents; }
