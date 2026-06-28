var _graphDirty = false;
var _currentScriptName = '未命名脚本';
var _lastSavedGraph = null;

export { _graphDirty, _currentScriptName, _lastSavedGraph };

export function _setGraphDirty(v) { _graphDirty = v; }
export function _setCurrentScriptName(v) { _currentScriptName = v; }
export function _setLastSavedGraph(v) { _lastSavedGraph = v; }
