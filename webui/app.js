import { state, q, qa, showToast, apiCall } from './modules/app-core.js';
import { renderGlobalParams, bindParamsActions } from './modules/params.js';
import {
  refreshMacros,
  refreshBindings,
  refreshMacroRuntimeProfile,
  renderMacroList,
  bindMacroActions,
} from './modules/macro-bind.js';
import {
  loadMacroToEditor,
  renderEditorMacroBrowser,
  renderActionList,
  bindEditorActions,
  seedPreviewTabs,
  previewOps,
} from './modules/editor/index.js';
import {
  refreshRecordControls,
  renderRecordMacroBrowser,
  bindRecorderActions,
} from './modules/recorder.js';
import { pollConsole, clearConsole, popoutConsole } from './modules/console.js';
import { refreshSnapshot, refreshListenerButtonState } from './modules/dashboard.js';
import { initExtraTab } from './modules/extra.js';
import { initConverterTab } from './modules/converter.js';
import { initThemeFromServer } from './modules/theme.js';

state.renderEditorMacroBrowser = renderEditorMacroBrowser;
state.renderRecordMacroBrowser = renderRecordMacroBrowser;
state.renderActionList = renderActionList;
state.onSelectMacroForEditor = loadMacroToEditor;

function setAutomationEditorShellFullscreen(enabled) {
  const body = document.body;
  body.classList.toggle('automation-editor-fullscreen', !!enabled);
}

// ── 幂等绑定 ─────────────────────────────────────────────────
// pywebviewready 与 DOMContentLoaded 兜底都可能触发绑定；若不设防，
// 同一按钮会被 addEventListener 两次 → 点一次触发两次 toggle（折叠看起来"失效"）。
const _boundOnce = new Set();
function bindOnce(name, fn) {
  if (_boundOnce.has(name)) return;
  _boundOnce.add(name);
  try {
    fn();
    console.log(`[bind] ${name} done`);
  } catch (e) {
    console.error(`[bind] ${name} error:`, e);
  }
}

async function switchTab(tabName) {
  state.currentTab = tabName;
  if (tabName !== 'automation') {
    setAutomationEditorShellFullscreen(false);
    const frame = q('#automationFrame');
    if (frame && frame.contentWindow) {
      frame.contentWindow.postMessage({
        source: 'macro-forge-host',
        type: 'host-force-exit-fullscreen',
      }, '*');
    }
  }
  qa('.tab-btn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });
  qa('.tab-page').forEach((page) => {
    page.classList.toggle('active', page.dataset.tabPage === tabName);
  });

  if (tabName === 'params') {
    await renderGlobalParams();
  }
  if (tabName === 'macro') {
    await refreshMacros().catch((err) => showToast(`加载宏列表失败: ${err.message}`));
    await refreshBindings().catch(() => {});
    await refreshMacroRuntimeProfile().catch(() => {});
  }
  if (tabName === 'record') {
    await refreshMacros().catch((err) => showToast(`加载宏列表失败: ${err.message}`));
    await refreshRecordControls();
    const { renderRecordMacroBrowser: renderRecord } = await import('./modules/recorder.js');
    renderRecord();
  }
  if (tabName === 'editor') {
    await refreshMacros().catch((err) => showToast(`加载宏列表失败: ${err.message}`));
    try {
      const { enableResizableGrid } = await import('./modules/layout-resize.js');
      enableResizableGrid(q('#editorGrid'), { storageKey: 'ui_split_editorGrid', min: 260 });
    } catch (e) { console.error('editor grid resize init error:', e); }
  }
  if (tabName === 'extra') {
    initExtraTab();
  }
  if (tabName === 'converter') {
    initConverterTab();
  }
}

function bindTabs() {
  q('#tabNav').addEventListener('click', (e) => {
    const btn = e.target.closest('.tab-btn');
    if (!btn) return;
    switchTab(btn.dataset.tab).catch((err) => showToast(err.message));
  });
}

function bindTopbarToggle() {
  const btn = q('#btnToggleTopbar');
  const topbar = q('#topbar');
  if (!btn || !topbar) return;
  btn.addEventListener('click', () => {
    const collapsed = topbar.classList.toggle('collapsed');
    btn.textContent = collapsed ? '+' : '−';
    btn.title = collapsed ? '展开状态栏' : '折叠状态栏';
  });
}

function bindSidebarToggle() {
  const mark = q('#brandMark');
  const shell = document.querySelector('.app-shell');
  if (!mark || !shell) return;
  const KEY = 'ui_sidebar_collapsed';
  let collapsed = false;
  try { collapsed = localStorage.getItem(KEY) === '1'; } catch (e) {}
  const apply = (v) => {
    shell.classList.toggle('sidebar-collapsed', v);
    mark.title = v ? '展开侧栏' : '折叠侧栏';
    try { localStorage.setItem(KEY, v ? '1' : '0'); } catch (e) {}
  };
  apply(collapsed);
  mark.addEventListener('click', () => {
    apply(!shell.classList.contains('sidebar-collapsed'));
  });
}

function bindAutomationFullscreenBridge() {
  window.addEventListener('message', (event) => {
    const data = event && event.data;
    if (!data || typeof data !== 'object') return;
    if (data.source !== 'automation-editor') return;
    if (data.type !== 'fullscreen-change') return;
    if (state.currentTab !== 'automation') return;
    setAutomationEditorShellFullscreen(!!data.enabled);
  });
}

window._onGlobalEditorHotkey = function(action) {
  try {
    var frame = document.getElementById('automationFrame');
    if (frame && frame.contentWindow) {
      frame.contentWindow.postMessage({
        source: 'macro-forge-host',
        type: 'global-hotkey',
        action: action
      }, '*');
    }
  } catch (e) {}
};

async function waitForApi(maxRetries = 20, intervalMs = 300) {
  for (let i = 0; i < maxRetries; i++) {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.health === 'function') {
      console.log('API ready after', i * intervalMs, 'ms');
      return true;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  console.warn('API not fully ready after timeout, proceeding anyway');
  return false;
}

async function bootstrap() {
  if (state.bootstrapDone) return;
  state.bootstrapDone = true;
  console.log('bootstrap starting...');

  try { bindOnce('tabs', bindTabs); } catch(e) { console.error('bindTabs error:', e); }
  try { bindOnce('topbar', bindTopbarToggle); } catch(e) { console.error('bindTopbarToggle error:', e); }
  try { bindOnce('sidebar', bindSidebarToggle); } catch(e) { console.error('bindSidebarToggle error:', e); }
  try { bindOnce('automation-bridge', bindAutomationFullscreenBridge); } catch(e) { console.error('bindAutomationFullscreenBridge error:', e); }
  try { bindOnce('params', bindParamsActions); } catch(e) { console.error('bindParamsActions error:', e); }
  try { bindOnce('macro', bindMacroActions); } catch(e) { console.error('bindMacroActions error:', e); }
  try { bindOnce('editor', bindEditorActions); } catch(e) { console.error('bindEditorActions error:', e); }
  try { bindOnce('recorder', bindRecorderActions); } catch(e) { console.error('bindRecorderActions error:', e); }

  try {
    const { ACTION_FORM_DEFAULTS } = await import('./modules/core/constants.js');
    console.log('constants loaded');
    const type = q('#actionType').value || 'kd';
    const defaults = ACTION_FORM_DEFAULTS[type] || ACTION_FORM_DEFAULTS.wait;
    const arg1 = q('#actionArg1');
    const arg2 = q('#actionArg2');
    if (arg1 && !arg1.value.trim()) arg1.value = defaults.arg1;
    if (arg2 && !arg2.value.trim()) arg2.value = defaults.arg2;
    console.log('form defaults set');
  } catch(e) { console.error('constants/forms error:', e); }

  bindOnce('console-buttons', () => {
    q('#btnClearConsole').addEventListener('click', async () => { await clearConsole(); });
    q('#btnPopoutConsole').addEventListener('click', () => { popoutConsole(); });
  });

  await waitForApi();

  try { await initThemeFromServer(); console.log('theme initialized'); } catch(e) { console.error('theme init error:', e); }

  try {
    await switchTab('macro');
    console.log('switchTab(macro) done');
  } catch(e) { console.error('switchTab error:', e); }
  startPolling();
}

window.addEventListener('pywebviewready', () => {
  bootstrap().catch((err) => showToast(err.message || String(err)));
});

// 静态预览用的切页（不触碰后端 API，避免截图里出现错误提示）
function previewSwitchTab(tabName) {
  qa('.tab-btn').forEach((btn) => btn.classList.toggle('active', btn.dataset.tab === tabName));
  qa('.tab-page').forEach((page) => page.classList.toggle('active', page.dataset.tabPage === tabName));
  if (tabName === 'editor') {
    import('./modules/layout-resize.js')
      .then(({ enableResizableGrid }) => enableResizableGrid(q('#editorGrid'), { storageKey: 'ui_split_editorGrid', min: 260 }))
      .catch((e) => console.error(e));
  }
}

window.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    if (window.pywebview && window.pywebview.api) {
      if (!state.bootstrapDone) {
        bootstrap().catch((err) => showToast(err.message || String(err)));
      }
      return;
    }

    // 静态预览（无后端）：绑定纯前端交互；支持 URL 参数预设界面状态，便于自动截图
    //   例：?p_tab=editor&p_panes=3&p_sidebar=collapsed&p_topbar=collapsed
    const params = new URLSearchParams(location.search);
    const hasPreviewParams = Array.from(params.keys()).some((k) => k.startsWith('p_'));

    bindOnce('tabs', bindTabs);
    bindOnce('topbar', bindTopbarToggle);
    bindOnce('sidebar', bindSidebarToggle);
    bindOnce('editor', bindEditorActions);

    try {
      const paneCount = Math.max(1, Math.min(3, parseInt(params.get('p_panes') || '1', 10) || 1));
      seedPreviewTabs(paneCount);

      if (params.get('p_sidebar') === 'collapsed') {
        const shell = document.querySelector('.app-shell');
        if (shell) shell.classList.add('sidebar-collapsed');
      }
      if (params.get('p_topbar') === 'collapsed') {
        const topbar = q('#topbar');
        const btn = q('#btnToggleTopbar');
        if (topbar) topbar.classList.add('collapsed');
        if (btn) { btn.textContent = '+'; btn.title = '展开状态栏'; }
      }
      const tabName = params.get('p_tab');
      if (tabName) previewSwitchTab(tabName);

      const op = params.get('p_op');
      if (op) previewOps(op);
    } catch (e) {
      console.error(e);
    }

    if (!hasPreviewParams) showToast('当前不在 PyWebView 环境，界面仅做静态预览');
  }, 800);
});

function pollDashboard() {
  if (state.currentTab === 'macro') {
    refreshBindings().catch(() => {});
  }
  refreshSnapshot().catch(() => {});
  refreshListenerButtonState().catch(() => {});
}

function startPolling() {
  if (state.pollTimerId) return;
  console.log('Starting polling timers...');
  state.pollTimerId = setInterval(() => {
    pollConsole();
  }, 500);
  state.snapshotTimerId = setInterval(() => {
    refreshSnapshot();
  }, 1000);
  state.bindingTimerId = setInterval(() => {
    if (state.currentTab === 'macro') {
      refreshBindings().catch(() => {});
    }
  }, 900);
  state.listenerTimerId = setInterval(() => {
    refreshListenerButtonState();
  }, 1500);
}
