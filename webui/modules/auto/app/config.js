export var TOOLBOX_CATEGORIES = [
  { id: 'flow', name: '流程', color: '#ff0000ff', icon: 'fa-solid fa-route' },
  { id: 'action', name: '动作节点', color: '#22c55e', icon: 'fa-solid fa-bolt' },
  { id: 'detection', name: '检测节点', color: '#eab308', icon: 'fa-solid fa-magnifying-glass' },
  { id: 'control', name: '控制节点', color: '#a855f7', icon: 'fa-solid fa-code-branch' },
  { id: 'script_block', name: '动作块', color: '#3b82f6', icon: 'fa-solid fa-cubes' },
  { id: 'monitor', name: '监视器', color: '#06b6d4', icon: 'fa-solid fa-eye' },
  { id: 'variable', name: '变量', color: '#f97316', icon: 'fa-solid fa-database' },
  { id: 'preset', name: '预设', color: '#f472b6', icon: 'fa-solid fa-wand-magic-sparkles' },
  { id: 'utility', name: '工具', color: '#d8d8d8ff', icon: 'fa-solid fa-screwdriver-wrench' },
  { id: 'plugin', name: '插件', color: '#a855f7', icon: 'fa-solid fa-puzzle-piece', collapsed: true },
];

export var _hotkeyEnabled = true;
export var _hotkeyRun = 'F6';
export var _hotkeyPause = 'F7';
export var _hotkeyStop = 'F8';
export var _hotkeyFullscreen = 'F11';

export function _loadEditorHotkeys() {
  try {
    var saved = localStorage.getItem('editor_hotkeys');
    if (saved) {
      var cfg = JSON.parse(saved);
      _hotkeyEnabled = cfg.enabled !== false;
      if (cfg.run) _hotkeyRun = cfg.run;
      if (cfg.pause) _hotkeyPause = cfg.pause;
      if (cfg.stop) _hotkeyStop = cfg.stop;
      if (cfg.fullscreen) _hotkeyFullscreen = cfg.fullscreen;
    }
  } catch (e) {}
}

export function _saveEditorHotkeys() {
  try {
    localStorage.setItem('editor_hotkeys', JSON.stringify({
      enabled: _hotkeyEnabled,
      run: _hotkeyRun,
      pause: _hotkeyPause,
      stop: _hotkeyStop,
      fullscreen: _hotkeyFullscreen
    }));
  } catch (e) {}
}

_loadEditorHotkeys();
