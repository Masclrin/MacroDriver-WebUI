'use strict';

var _notifyFn = null;
function _setGlobalNotify(fn) { _notifyFn = fn; }
function _getGlobalNotify() { return _notifyFn; }

export { _setGlobalNotify, _getGlobalNotify };
