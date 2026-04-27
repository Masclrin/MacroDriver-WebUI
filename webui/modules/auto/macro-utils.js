'use strict';

    window.MacroUtils = {
        parseNumber: function(val, fallback) {
            var n = parseFloat(val);
            return isNaN(n) ? (fallback || 0) : n;
        },

        cloneAction: function(action) {
            if (!action) return null;
            if (Array.isArray(action)) return action.slice();
            if (typeof action === 'object') {
                var clone = {};
                for (var key in action) {
                    if (action.hasOwnProperty(key)) clone[key] = action[key];
                }
                return clone;
            }
            return action;
        },

        normalizeAction: function(action) {
            if (!Array.isArray(action) || action.length === 0) return null;
            var cmd = action[0];
            if (typeof cmd !== 'string') return null;
            return action;
        },

        isLoopAction: function(action) {
            return Array.isArray(action) && action.length >= 3 && action[0] === 'loop';
        },

        buildActionFromInputs: function(params) {
            var type = params.type || '';
            var arg1 = params.arg1;
            var arg2 = params.arg2;
            switch (type) {
                case 'kd': case 'ku': case 'md': case 'mu':
                    return [type, arg1 || 'left', this.parseNumber(arg2, 0)];
                case 'wait':
                    return ['wait', this.parseNumber(arg1, 100)];
                case 'view':
                    return ['view', [this.parseNumber(arg1, 0), this.parseNumber(arg2, 0)], this.parseNumber(params.arg3, 0)];
                case 'move_to':
                    return ['move_to', this.parseNumber(arg1, 0), this.parseNumber(arg2, 0), this.parseNumber(params.arg3, 0)];
                case 'scroll':
                    return ['scroll', this.parseNumber(arg1, 120), 0];
                default:
                    return null;
            }
        },

        formatActionLabel: function(action) {
            if (!Array.isArray(action) || action.length === 0) return '???';
            var cmd = action[0];
            switch (cmd) {
                case 'kd': return '↓ ' + (action[1] || '');
                case 'ku': return '↑ ' + (action[1] || '');
                case 'md': return '🖱↓ ' + (action[1] || 'left');
                case 'mu': return '🖱↑ ' + (action[1] || 'left');
                case 'wait': return '⏱ ' + (action[1] || 0) + 'ms';
                case 'view': return '👁 [' + (action[1] || [0,0]) + '] ' + (action[2] || 0) + 'ms';
                case 'loop': return '🔁 ×' + (action[1] || 0);
                case 'move_to': return '➡ (' + (action[1] || 0) + ',' + (action[2] || 0) + ')';
                case 'scroll': return '📜 ' + (action[1] || 120);
                default: return cmd;
            }
        },
    };

export const MacroUtils = window.MacroUtils;
