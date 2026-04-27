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
} from './modules/editor/index.js';
import {
  refreshRecordControls,
  renderRecordMacroBrowser,
  bindRecorderActions,
} from './modules/recorder.js';
import { pollConsole, clearConsole } from './modules/console.js';
import { refreshSnapshot, refreshListenerButtonState } from './modules/dashboard.js';

state.renderEditorMacroBrowser = renderEditorMacroBrowser;
state.renderRecordMacroBrowser = renderRecordMacroBrowser;
state.renderActionList = renderActionList;
state.onSelectMacroForEditor = loadMacroToEditor;

function setAutomationEditorShellFullscreen(enabled) {
  const body = document.body;
  body.classList.toggle('automation-editor-fullscreen', !!enabled);
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
  }
}

function bindTabs() {
  q('#tabNav').addEventListener('click', (e) => {
    const btn = e.target.closest('.tab-btn');
    if (!btn) return;
    switchTab(btn.dataset.tab).catch((err) => showToast(err.message));
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

  try { bindTabs(); console.log('bindTabs done'); } catch(e) { console.error('bindTabs error:', e); }
  try { bindAutomationFullscreenBridge(); console.log('bindAutomationFullscreenBridge done'); } catch(e) { console.error('bindAutomationFullscreenBridge error:', e); }
  try { bindParamsActions(); console.log('bindParamsActions done'); } catch(e) { console.error('bindParamsActions error:', e); }
  try { bindMacroActions(); console.log('bindMacroActions done'); } catch(e) { console.error('bindMacroActions error:', e); }
  try { bindEditorActions(); console.log('bindEditorActions done'); } catch(e) { console.error('bindEditorActions error:', e); }
  try { bindRecorderActions(); console.log('bindRecorderActions done'); } catch(e) { console.error('bindRecorderActions error:', e); }

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

  try {
    q('#btnClearConsole').addEventListener('click', async () => { await clearConsole(); });
    console.log('clearConsole listener set');
  } catch(e) { console.error('clearConsole listener error:', e); }

  await waitForApi();

  try {
    await switchTab('macro');
    console.log('switchTab(macro) done');
  } catch(e) { console.error('switchTab error:', e); }
  startPolling();
}

window.addEventListener('pywebviewready', () => {
  bootstrap().catch((err) => showToast(err.message || String(err)));
});

window.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    if (window.pywebview && window.pywebview.api) {
      if (!state.bootstrapDone) {
        bootstrap().catch((err) => showToast(err.message || String(err)));
      }
      return;
    }
    showToast('当前不在 PyWebView 环境，界面仅做静态预览');
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
