import { state } from '../core/state.js';
import { q, showToast } from '../core/dom.js';
import { apiCall } from '../core/api.js';
import { renderMacroTreeList } from '../macro-tree.js';
import { normalizeMacroRows, pathKey, keyToPath, cloneAction } from './action-model.js';
import { setSelectedLine, insertActionAtTarget, resolveInsertTargetAfterSelection, getActionAndContainerByPath, getActionAtPath, clearExpandedLoopKeysByPrefix } from './action-ops.js';
import { fillActionEditorByAction, buildActionFromInputs, ensureActionFormDefaultsForType, switchActionType, refreshExtForm } from './action-form.js';
import { loadExtCommands, setExtCommandsForPreview } from './ext-commands.js';
import { renderViewList, refreshBatchCommentButton, updateCurrentActionFromEditor, initPaneContainerEvents } from './action-list-render.js';

export { renderViewList };
export { renderEditorMacroBrowser, bindEditorActions };
export { renderActionList } from './action-list-render.js';

// 小窗口最多 3 个；标签页数量不限
const MAX_PANES = 3;

// ─────────────────────────────────────────────────────────────
// 模型：tab（文档，不限数量） + view（编辑小窗，最多 3）
//   tab 持有内容 rows（真相源）、保存快照、脏标记
//   view 持有 DOM 与「显示/选择/展开/内联编辑」状态，并绑定一个 tab
// ─────────────────────────────────────────────────────────────
function getFocusedView() {
  return state.editorViews.find((v) => v.id === state.focusedViewId && v.tabId) || null;
}

function findView(id) {
  return state.editorViews.find((v) => v.id === id) || null;
}

function activeTab() {
  return state.editorTabs.find((t) => t.id === state.activeTabId) || null;
}

function tabOf(view) {
  return view && view.tabId ? state.editorTabs.find((t) => t.id === view.tabId) || null : null;
}

function tabLabel(path) {
  return String(path || '').split('/').pop() || String(path || '');
}

function snapshotTab(tab) {
  try { tab.savedSnapshot = JSON.stringify(tab.rows); } catch (e) { tab.savedSnapshot = ''; }
}

function markTabDirty(tab) {
  if (!tab) return;
  let now = '';
  try { now = JSON.stringify(tab.rows); } catch (e) { now = ''; }
  tab.dirty = now !== (tab.savedSnapshot || '');
  const el = q(`#editorTabBar .editor-tab[data-tab-id="${tab.id}"]`);
  if (el) el.classList.toggle('dirty', !!tab.dirty);
  const view = state.editorViews.find((v) => v.tabId === tab.id);
  if (view) {
    const pane = view.el;
    if (pane) pane.classList.toggle('dirty', !!tab.dirty);
  }
}

// ── 小窗（view）──────────────────────────────────────────────
function ensurePanes() {
  const wrap = q('#editorPanes');
  if (!wrap) return null;
  return wrap;
}

function createView() {
  const wrap = ensurePanes();
  if (!wrap || state.editorViews.length >= MAX_PANES) return null;

  const id = `v${++state.editorViewSeq}`;
  const el = document.createElement('div');
  el.className = 'editor-pane';
  el.dataset.viewId = id;

  const head = document.createElement('div');
  head.className = 'editor-pane-head';
  const title = document.createElement('span');
  title.className = 'editor-pane-title';
  title.textContent = '（空窗格）';
  head.appendChild(title);

  // 关闭小窗（与标题同行），腾出空间
  const close = document.createElement('button');
  close.type = 'button';
  close.className = 'editor-pane-close';
  close.textContent = '×';
  close.title = '关闭此小窗';
  head.appendChild(close);
  el.appendChild(head);

  const listEl = document.createElement('ul');
  listEl.className = 'list action-list';
  el.appendChild(listEl);

  wrap.appendChild(el);

  const view = {
    id,
    el,
    listEl,
    titleEl: title,
    tabId: null,
    rows: [],
    selectedActionPath: null,
    selectedLineKind: 'action',
    expandedLoopPathKeys: new Set(),
    inlineEditingPathKey: null,
  };
  state.editorViews.push(view);

  close.addEventListener('mousedown', (e) => e.stopPropagation());
  close.addEventListener('click', (e) => { e.stopPropagation(); closePane(view); });
  close.draggable = false;

  // 拖动标题栏 → 调整小窗排列位置
  head.draggable = true;
  head.title = '拖动可调整小窗排列位置';
  head.addEventListener('dragstart', (e) => {
    state.draggedPaneId = view.id;
    view.el.classList.add('dragging');
    try {
      e.dataTransfer.setData('text/pane-id', view.id);
      e.dataTransfer.effectAllowed = 'move';
    } catch (err) { /* ignore */ }
  });
  head.addEventListener('dragend', () => {
    state.draggedPaneId = null;
    view.el.classList.remove('dragging');
    document.querySelectorAll('.editor-pane.reorder-target').forEach((p) => p.classList.remove('reorder-target'));
  });

  renderPanesPlaceholder();
  return view;
}

// 计算"插到第几个"：按鼠标横坐标落在哪个小窗的左/右半区
function computePaneInsertIndex(clientX, excludeId) {
  const views = state.editorViews.filter((v) => v.id !== excludeId);
  for (let i = 0; i < views.length; i++) {
    const r = views[i].el.getBoundingClientRect();
    if (r.width > 0 && clientX < r.left + r.width / 2) return i;
  }
  return views.length;
}

// 重排小窗（拖动标题栏）
function reorderPanes(draggedId, clientX) {
  const from = state.editorViews.findIndex((v) => v.id === draggedId);
  if (from < 0) return;
  const dragged = state.editorViews[from];
  const rest = state.editorViews.filter((v) => v.id !== draggedId);
  const idx = computePaneInsertIndex(clientX, draggedId);
  rest.splice(Math.max(0, Math.min(idx, rest.length)), 0, dragged);
  state.editorViews = rest;
  const wrap = ensurePanes();
  if (wrap) state.editorViews.forEach((v) => wrap.appendChild(v.el));
}

function closePane(view) {
  const idx = state.editorViews.findIndex((v) => v.id === view.id);
  if (idx < 0) return;
  // 该窗显示的标签仍留在标签栏（只是不再显示）
  view.el.remove();
  state.editorViews.splice(idx, 1);

  if (state.focusedViewId === view.id) {
    const next = state.editorViews[idx] || state.editorViews[idx - 1] || null;
    state.focusedViewId = next ? next.id : null;
    if (next) { focusView(next); syncFormFromView(next); }
  }

  // 至少保留 1 个小窗：若全关了就重建一个，并把当前标签放回去
  if (!state.editorViews.length) {
    const v = createView();
    const t = activeTab();
    if (v && t) { setViewTab(v, t); focusView(v); syncFormFromView(v); }
    else if (v) { focusView(v); }
  }
  renderPanesPlaceholder();
}

function renderPanesPlaceholder() {
  const wrap = ensurePanes();
  if (!wrap) return;
  const empty = state.editorViews.length === 0;
  wrap.classList.toggle('empty', empty);
  let ph = wrap.querySelector('.editor-panes-placeholder');
  if (empty && !ph) {
    ph = document.createElement('div');
    ph.className = 'editor-panes-placeholder';
    ph.textContent = '没有小窗 —— 点击标签栏中的宏，或把标签拖到这里新建小窗';
    wrap.appendChild(ph);
  } else if (!empty && ph) {
    ph.remove();
  }
}

function focusView(view, options = {}) {
  if (!view) return;
  state.focusedViewId = view.id;
  state.editorViews.forEach((v) => v.el.classList.toggle('active', v.id === view.id));
  state.editorRows = view.rows; // 兼容旧的全局引用
  // 供宏绑定等其它模块继续使用
  const t = tabOf(view);
  state.selectedMacro = t ? t.path : null;
  const pathInput = q('#selectedMacroPath');
  if (pathInput) pathInput.value = t ? t.path : '';
  if (!options.silent && view.selectedActionPath && view.selectedActionPath.length) {
    const a = getActionAtPath(view, view.selectedActionPath);
    if (a) fillActionEditorByAction(a);
  }
}

function setViewTab(view, tab) {
  if (!view) return;
  view.tabId = tab ? tab.id : null;
  view.rows = tab ? tab.rows : [];
  view.selectedActionPath = view.rows.length ? [0] : null;
  view.selectedLineKind = 'action';
  view.expandedLoopPathKeys = new Set();
  view.inlineEditingPathKey = null;
  // 测试点归属"文档"（tab），切换小窗不丢
  view.breakpoints = tab ? (tab.breakpoints || (tab.breakpoints = new Set())) : new Set();
  view.el.classList.toggle('empty', !tab);
  view.titleEl.textContent = tab ? tabLabel(tab.path) : '（空窗格）';
  view.titleEl.title = tab ? tab.path : '';
  view.el.classList.toggle('dirty', !!(tab && tab.dirty));
  renderViewList(view);
}

// 把标签装入某个小窗（默认装入当前聚焦/唯一小窗，不自动新增小窗）
function placeTab(tab) {
  const shown = state.editorViews.find((v) => v.tabId === tab.id);
  if (shown) { focusView(shown); syncFormFromView(shown); return shown; }

  let view = getFocusedView() || state.editorViews[0] || createView();
  if (!view) return null;
  setViewTab(view, tab);
  focusView(view);
  syncFormFromView(view);
  renderPanesPlaceholder();
  return view;
}

// 通过把标签拖到小窗区域来新增小窗（最多 3 个）；insertIdx 决定新窗的排列位置
function createNewPaneWithTab(tab, insertIdx) {
  if (!tab) return;
  const already = state.editorViews.find((v) => v.tabId === tab.id);
  if (already) { focusView(already); syncFormFromView(already); return; }
  if (state.editorViews.length >= MAX_PANES) {
    showToast(`最多同时 ${MAX_PANES} 个小窗`);
    return;
  }
  const view = createView();
  if (!view) return;

  if (Number.isInteger(insertIdx)) {
    const cur = state.editorViews.indexOf(view);
    if (cur >= 0) state.editorViews.splice(cur, 1);
    const i = Math.max(0, Math.min(insertIdx, state.editorViews.length));
    state.editorViews.splice(i, 0, view);
    const wrap = ensurePanes();
    if (wrap) state.editorViews.forEach((v) => wrap.appendChild(v.el));
  }

  setViewTab(view, tab);
  focusView(view);
  syncFormFromView(view);
  state.activeTabId = tab.id;
  renderEditorTabBar();
  showToast('已新建小窗');
}

function syncFormFromView(view) {
  if (!view) return;
  if (view.selectedActionPath && view.selectedActionPath.length) {
    const a = getActionAtPath(view, view.selectedActionPath);
    if (a) fillActionEditorByAction(a);
  } else {
    ensureActionFormDefaultsForType(q('#actionType').value || 'kd', true);
  }
}

// ── 标签（tab）──────────────────────────────────────────────
export async function loadMacroToEditor(path) {
  if (!path) return;

  const existing = state.editorTabs.find((t) => t.path === path);
  if (existing) { state.activeTabId = existing.id; placeTab(existing, { preferNewView: false }); renderEditorTabBar(); return; }

  if (state.editorLoadAbortController) state.editorLoadAbortController.abort();
  const controller = new AbortController();
  state.editorLoadAbortController = controller;

  try {
    const data = await apiCall('read_macro', path);
    if (controller.signal.aborted) return;

    const tab = {
      id: `t${++state.editorTabSeq}`,
      path: data.path || path,
      rows: normalizeMacroRows(data.rows),
      dirty: false,
      savedSnapshot: '',
      breakpoints: new Set(),
    };
    snapshotTab(tab);
    state.editorTabs.push(tab);
    state.activeTabId = tab.id;
    placeTab(tab);
    renderEditorTabBar();
  } finally {
    if (state.editorLoadAbortController === controller) state.editorLoadAbortController = null;
  }
}

function activateTab(tabId) {
  const tab = state.editorTabs.find((t) => t.id === tabId);
  if (!tab) return;
  state.activeTabId = tabId;
  placeTab(tab);
  // 只就地更新高亮，**不重建标签栏**（否则会打断双击重命名）
  syncTabBarActive();
  renderEditorMacroBrowser();
}

// 就地同步标签栏高亮（不重建 DOM）
function syncTabBarActive() {
  const bar = q('#editorTabBar');
  if (!bar) return;
  bar.querySelectorAll('.editor-tab').forEach((el) => {
    el.classList.toggle('active', el.dataset.tabId === state.activeTabId);
  });
}

function closeTab(tabId) {
  const idx = state.editorTabs.findIndex((t) => t.id === tabId);
  if (idx < 0) return;
  const tab = state.editorTabs[idx];
  if (tab.dirty && !window.confirm(`标签「${tabLabel(tab.path)}」有未保存的修改，仍然关闭？`)) return;

  const view = state.editorViews.find((v) => v.tabId === tab.id);
  state.editorTabs.splice(idx, 1);

  if (view) {
    const next = state.editorTabs[idx] || state.editorTabs[idx - 1] || null;
    setViewTab(view, next);
    if (next) { state.activeTabId = next.id; focusView(view); syncFormFromView(view); }
  }
  if (!state.editorTabs.length) {
    state.activeTabId = null;
    state.editorViews.forEach((v) => setViewTab(v, null));
    state.focusedViewId = state.editorViews[0] ? state.editorViews[0].id : null;
  } else if (!state.activeTabId) {
    state.activeTabId = state.editorTabs[0].id;
  }
  renderEditorTabBar();
  renderEditorMacroBrowser();
}

function startTabRename(tabEl, tab) {
  const lbl = tabEl.querySelector('.editor-tab-label');
  if (!lbl) return;
  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'editor-tab-rename';
  input.value = tabLabel(tab.path);
  lbl.replaceWith(input);
  input.focus();
  input.select();

  let done = false;
  const finish = async (commit) => {
    if (done) return;
    done = true;
    const name = input.value.trim();
    if (commit && name && name !== tabLabel(tab.path)) {
      try {
        const ret = await apiCall('rename_macro', tab.path, name);
        tab.path = ret.path;
        if (tab.id === state.activeTabId) q('#selectedMacroPath').value = ret.path;
        const view = state.editorViews.find((v) => v.tabId === tab.id);
        if (view) { view.titleEl.textContent = tabLabel(tab.path); view.titleEl.title = tab.path; }
        showToast('标签已重命名');
        const { refreshMacros, refreshBindings } = await import('../macro-bind.js');
        await refreshMacros();
        await refreshBindings();
      } catch (err) {
        showToast(`重命名失败: ${err.message}`);
      }
    }
    renderEditorTabBar();
    renderEditorMacroBrowser();
  };

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); finish(true); }
    else if (e.key === 'Escape') { e.preventDefault(); finish(false); }
  });
  input.addEventListener('blur', () => { finish(true); });
  input.addEventListener('click', (e) => e.stopPropagation());
}

function renderEditorTabBar() {
  const bar = q('#editorTabBar');
  if (!bar) return;
  bar.innerHTML = '';

  if (!state.editorTabs.length) {
    bar.classList.add('empty');
    const hint = document.createElement('span');
    hint.className = 'editor-tab-hint';
    hint.textContent = '从下方「宏文件夹」点击文件打开标签；标签数量不限，编辑小窗最多 3 个并排。双击标签名可重命名。';
    bar.appendChild(hint);
    return;
  }
  bar.classList.remove('empty');

  state.editorTabs.forEach((tab) => {
    const el = document.createElement('div');
    el.className = 'editor-tab';
    el.dataset.tabId = tab.id;
    el.classList.toggle('active', tab.id === state.activeTabId);
    el.classList.toggle('dirty', !!tab.dirty);
    el.title = `${tab.path}（双击名称重命名；点击装入当前小窗；拖到右侧小窗区域可新建小窗）`;
    el.draggable = true;

    const lbl = document.createElement('span');
    lbl.className = 'editor-tab-label';
    lbl.textContent = tabLabel(tab.path);
    el.appendChild(lbl);

    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'editor-tab-close';
    close.textContent = '×';
    close.title = '关闭标签';
    el.appendChild(close);

    el.addEventListener('dragstart', (e) => {
      try {
        e.dataTransfer.setData('text/tab-id', tab.id);
        e.dataTransfer.effectAllowed = 'copyMove';
      } catch (err) { /* ignore */ }
    });
    el.addEventListener('click', (e) => {
      if (e.target.closest('.editor-tab-close')) return;
      if (e.target.classList.contains('editor-tab-rename')) return;
      activateTab(tab.id);
    });
    close.addEventListener('click', (e) => { e.stopPropagation(); closeTab(tab.id); });

    bar.appendChild(el);
  });
}

export async function reloadActiveTab() {
  const tab = activeTab();
  if (!tab) { showToast('请先打开一个宏标签'); return; }
  const data = await apiCall('read_macro', tab.path);
  tab.rows = normalizeMacroRows(data.rows);
  snapshotTab(tab);
  const view = state.editorViews.find((v) => v.tabId === tab.id);
  if (view) setViewTab(view, tab);
  renderEditorTabBar();
  markTabDirty(tab);
  showToast('已重新加载当前标签');
}

export async function saveActiveTab() {
  const tab = activeTab();
  if (!tab) { showToast('请先打开一个宏标签'); return; }
  await apiCall('save_macro', tab.path, tab.rows);
  snapshotTab(tab);
  markTabDirty(tab);
  renderEditorTabBar();
  showToast('宏文件已保存');
  const { refreshMacros } = await import('../macro-bind.js');
  await refreshMacros();
}

// 测试点运行：从"当前选中行所在/之后的第一个测试点"跑到"下一个测试点"（无则到末尾）
async function runFromBreakpoint() {
  const view = getFocusedView();
  if (!view) return showToast('请先打开一个宏标签');
  const tab = tabOf(view);
  if (!tab) return showToast('请先打开一个宏标签');

  const bps = Array.from(view.breakpoints || [])
    .map((k) => parseInt(String(k).split('.')[0], 10))
    .filter((n) => Number.isInteger(n) && n >= 0)
    .sort((a, b) => a - b);
  if (!bps.length) return showToast('请先点击动作行号（或双击行内的「设为测试点」）设置测试点');

  const sel = Array.isArray(view.selectedActionPath) && view.selectedActionPath.length
    ? view.selectedActionPath[0]
    : -1;
  let start = bps.find((b) => b >= sel);
  if (start === undefined) start = bps[0];
  const next = bps.find((b) => b > start);

  try {
    const ret = await apiCall('run_macro_slice', tab.path, start, next === undefined ? null : next);
    showToast(`测试运行：第 ${ret.from_index + 1} ~ ${ret.to_index} 行（${ret.executed_rows} 条）`);
  } catch (err) {
    showToast(`测试运行失败: ${err.message}`);
  }
}

function renderEditorMacroBrowser() {
  const list = q('#editorMacroList');
  renderMacroTreeList({
    container: list,
    tree: state.macroTree,
    viewId: 'editor',
    selectedPath: null,
    openedPath: activeTab() ? activeTab().path : null,
    onSelect: (path) => { loadMacroToEditor(path).catch((err) => showToast(err.message)); },
  });
}

// ── 绑定 ────────────────────────────────────────────────────
function bindEditorActions() {
  const panes = q('#editorPanes');
  if (panes) initPaneContainerEvents(panes, (paneEl) => findView(paneEl.dataset.viewId));

  // 默认 1 个小窗（且默认不打开任何标签）
  if (panes && !state.editorViews.length) {
    const v = createView();
    if (v) { state.focusedViewId = v.id; v.el.classList.add('active'); }
  }
  renderPanesPlaceholder();

  // 拖放：标签 → 新建小窗（按落点决定排列位置）；小窗标题栏 → 调整排列位置
  if (panes && panes.dataset.tabDropReady !== '1') {
    panes.dataset.tabDropReady = '1';

    const typesOf = (e) => Array.from((e.dataTransfer && e.dataTransfer.types) || []);

    panes.addEventListener('dragover', (e) => {
      const types = typesOf(e);
      if (types.includes('text/tab-id')) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
        panes.classList.add('tab-drop');
        return;
      }
      if (types.includes('text/pane-id')) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        const id = state.draggedPaneId;
        const idx = computePaneInsertIndex(e.clientX, id);
        const rest = state.editorViews.filter((v) => v.id !== id);
        state.editorViews.forEach((v) => v.el.classList.remove('reorder-target'));
        if (rest[idx]) rest[idx].el.classList.add('reorder-target');
        else if (rest.length) rest[rest.length - 1].el.classList.add('reorder-target');
      }
    });

    panes.addEventListener('dragleave', (e) => {
      if (!panes.contains(e.relatedTarget)) {
        panes.classList.remove('tab-drop');
        state.editorViews.forEach((v) => v.el.classList.remove('reorder-target'));
      }
    });

    panes.addEventListener('drop', (e) => {
      const types = typesOf(e);
      panes.classList.remove('tab-drop');
      state.editorViews.forEach((v) => v.el.classList.remove('reorder-target'));

      if (types.includes('text/pane-id')) {
        e.preventDefault();
        e.stopPropagation();
        const id = e.dataTransfer.getData('text/pane-id');
        if (id) reorderPanes(id, e.clientX);
        return;
      }

      if (!types.includes('text/tab-id')) return;
      e.preventDefault();
      e.stopPropagation();
      const tabId = e.dataTransfer.getData('text/tab-id');
      const tab = state.editorTabs.find((t) => t.id === tabId);
      // 新窗插到鼠标所在位置
      const insertIdx = computePaneInsertIndex(e.clientX, null);
      if (tab) createNewPaneWithTab(tab, insertIdx);
    });
  }

  // 双击标签重命名（事件委托：标签栏重建后依然有效）
  const tabBar = q('#editorTabBar');
  if (tabBar && tabBar.dataset.dblReady !== '1') {
    tabBar.dataset.dblReady = '1';
    tabBar.addEventListener('dblclick', (e) => {
      const tel = e.target instanceof Element ? e.target : (e.target && e.target.parentElement);
      if (!tel || tel.closest('.editor-tab-close')) return;
      const tabEl = tel.closest('.editor-tab');
      if (!tabEl) return;
      const tab = state.editorTabs.find((t) => t.id === tabEl.dataset.tabId);
      if (!tab) return;
      e.preventDefault();
      e.stopPropagation();
      startTabRename(tabEl, tab);
    });
  }

  state.onSelectMacroForEditor = loadMacroToEditor;
  state.renderEditorMacroBrowser = renderEditorMacroBrowser;
  state.renderRecordMacroBrowser = async () => {};
  state.getFocusedView = getFocusedView;
  state.findView = findView;
  state.onFocusView = (view) => focusView(view, { silent: true });
  state.onViewRendered = (view) => markTabDirty(tabOf(view));
  state.renderActionList = () => { const v = getFocusedView(); if (v) renderViewList(v); };
  state.closeTabByPath = (path) => {
    const t = state.editorTabs.find((x) => x.path === path);
    if (t) closeTab(t.id);
  };

  renderEditorTabBar();

  // 预取 ext 指令描述符（供"动作插入器"生成参数表单；失败不影响其它功能）
  loadExtCommands(true).then(() => refreshExtForm()).catch(() => {});

  q('#btnRefreshEditorMacroBrowser').addEventListener('click', async () => {
    const { refreshMacros } = await import('../macro-bind.js');
    await refreshMacros();
    showToast('编辑区宏文件夹已刷新');
  });

  q('#btnBatchComment')?.addEventListener('click', () => {
    state.batchCommentMode = !state.batchCommentMode;
    if (state.batchCommentMode) {
      state.editorViews.forEach((v) => { v.inlineEditingPathKey = null; });
      showToast('批量注释模式已开启');
    } else {
      showToast('批量注释模式已关闭');
    }
    refreshBatchCommentButton();
    state.editorViews.forEach((v) => renderViewList(v));
  });

  async function generateUniqueFileName(folder, baseName) {
    let name = baseName;
    let counter = 1;
    const allPaths = new Set((state.macros || []).map((m) => m.path));
    while (allPaths.has(`${folder}/${name}`)) {
      const ext = name.endsWith('.json') ? '.json' : '';
      const stem = ext ? name.slice(0, -5) : name;
      name = `${stem}_${counter}${ext}`;
      counter += 1;
      if (counter > 999) break;
    }
    return name;
  }

  q('#btnEditorCreate').addEventListener('click', async () => {
    const folder = q('#editorFolder').value.trim() || '宏/录制宏';
    const inputName = q('#editorNewName').value.trim();
    const fileName = inputName
      ? await generateUniqueFileName(folder, inputName)
      : await generateUniqueFileName(folder, '新建宏.json');
    const ret = await apiCall('create_macro', folder, fileName);
    const { refreshMacros } = await import('../macro-bind.js');
    await refreshMacros();
    showToast(`已创建: ${ret.path}`);
    await loadMacroToEditor(ret.path);
  });

  q('#btnEditorRename').addEventListener('click', async () => {
    const tab = activeTab();
    if (!tab) return showToast('请先打开一个宏标签');
    const inputName = q('#editorNewName').value.trim();
    if (!inputName) return showToast('请输入新文件名');
    const folder = q('#editorFolder').value.trim() || '宏/录制宏';
    const newName = await generateUniqueFileName(folder, inputName);

    const ret = await apiCall('rename_macro', tab.path, newName);
    tab.path = ret.path;
    q('#selectedMacroPath').value = ret.path;
    const view = state.editorViews.find((v) => v.tabId === tab.id);
    if (view) { view.titleEl.textContent = tabLabel(tab.path); view.titleEl.title = tab.path; }
    showToast('重命名完成');
    const { refreshMacros, refreshBindings } = await import('../macro-bind.js');
    await refreshMacros();
    await refreshBindings();
    renderEditorTabBar();
    renderEditorMacroBrowser();
  });

  q('#btnDeleteEditorMacro').addEventListener('click', async () => {
    const tab = activeTab();
    if (!tab) return showToast('请先打开一个宏标签');
    if (!window.confirm(`确认删除 ${tab.path} ?`)) return;
    if (!window.confirm(`再次确认：将永久删除 ${tab.path}，此操作不可恢复！`)) return;
    await apiCall('delete_macro', tab.path);
    closeTab(tab.id);
    showToast('已删除宏文件');
    const { refreshMacros, refreshBindings } = await import('../macro-bind.js');
    await refreshMacros();
    await refreshBindings();
    renderEditorTabBar();
    renderEditorMacroBrowser();
  });

  q('#btnMoveMacro').addEventListener('click', async () => {
    const tab = activeTab();
    if (!tab) return showToast('请先打开一个宏标签');
    const targetFolder = q('#editorFolder').value.trim() || '宏/录制宏';
    const ret = await apiCall('move_macro', tab.path, targetFolder);
    tab.path = ret.path;
    q('#selectedMacroPath').value = ret.path;
    const view = state.editorViews.find((v) => v.tabId === tab.id);
    if (view) { view.titleEl.textContent = tabLabel(tab.path); view.titleEl.title = tab.path; }
    showToast('移动完成');
    const { refreshMacros, refreshBindings } = await import('../macro-bind.js');
    await refreshMacros();
    await refreshBindings();
    renderEditorTabBar();
    renderEditorMacroBrowser();
  });

  q('#actionType').addEventListener('change', () => {
    switchActionType(q('#actionType').value);
  });

  q('#btnInsertBelow').addEventListener('click', () => {
    const view = getFocusedView();
    if (!view) return showToast('请先打开一个宏标签');
    try {
      const row = buildActionFromInputs();
      const target = resolveInsertTargetAfterSelection(view);
      insertActionAtTarget(view, row, target);
      renderViewList(view);
    } catch (err) {
      showToast(err.message);
    }
  });

  q('#btnAppendAction').addEventListener('click', () => {
    const view = getFocusedView();
    if (!view) return showToast('请先打开一个宏标签');
    try {
      const row = buildActionFromInputs();
      insertActionAtTarget(view, row, { type: 'root', index: view.rows.length });
      renderViewList(view);
    } catch (err) {
      showToast(err.message);
    }
  });

  q('#btnUpdateAction').addEventListener('click', () => {
    const view = getFocusedView();
    if (!view) return showToast('请先打开一个宏标签');
    try {
      updateCurrentActionFromEditor({ view });
      view.inlineEditingPathKey = pathKey(view.selectedActionPath);
    } catch (err) {
      showToast(err.message);
    }
  });

  q('#btnDeleteAction').addEventListener('click', () => {
    const view = getFocusedView();
    if (!view) return showToast('请先打开一个宏标签');
    if (!Array.isArray(view.selectedActionPath) || !view.selectedActionPath.length) {
      showToast('请先选择一个动作');
      return;
    }
    const info = getActionAndContainerByPath(view, view.selectedActionPath);
    if (!info) { showToast('选中动作已失效，请重新选择'); return; }

    const removedPath = [...view.selectedActionPath];
    info.container.splice(info.index, 1);
    view.inlineEditingPathKey = null;
    clearExpandedLoopKeysByPrefix(view, removedPath);

    if (info.container.length > 0) {
      const nextIndex = Math.min(info.index, info.container.length - 1);
      const nextPath = [...removedPath.slice(0, -1), nextIndex];
      setSelectedLine(view, nextPath, 'action');
      const selected = getActionAtPath(view, nextPath);
      if (selected) fillActionEditorByAction(selected);
    } else if (!removedPath.slice(0, -1).length) {
      setSelectedLine(view, null, 'action');
      ensureActionFormDefaultsForType(q('#actionType').value || 'kd', true);
    } else {
      setSelectedLine(view, removedPath.slice(0, -1), 'action');
      const selected = getActionAtPath(view, removedPath.slice(0, -1));
      if (selected) fillActionEditorByAction(selected);
    }
    renderViewList(view);
  });

  q('#btnSaveEditor').addEventListener('click', async () => {
    try { await saveActiveTab(); } catch (err) { showToast(err.message); }
  });

  q('#btnReloadEditor').addEventListener('click', async () => {
    try { await reloadActiveTab(); } catch (err) { showToast(err.message); }
  });

  q('#btnRunFromBreakpoint')?.addEventListener('click', () => {
    runFromBreakpoint().catch((err) => showToast(err.message));
  });

  // 点击窗格外部：收起内联编辑器
  document.addEventListener('click', (e) => {
    const view = getFocusedView();
    if (!view || !view.inlineEditingPathKey) return;
    const target = e.target;
    if (!(target instanceof Element)) return;
    if (target.closest('#editorPanes')) return;
    if (target.closest('#actionType') || target.closest('#actionArg1') || target.closest('#actionArg2')
      || target.closest('#btnUpdateAction') || target.closest('#btnInsertBelow')
      || target.closest('#btnAppendAction') || target.closest('#btnDeleteAction')) {
      return;
    }
    const editingPath = keyToPath(view.inlineEditingPathKey);
    if (editingPath && editingPath.length) {
      setSelectedLine(view, editingPath, 'action');
      updateCurrentActionFromEditor({ silent: true, view });
    }
    view.inlineEditingPathKey = null;
    renderViewList(view);
  }, true);

  bindEditorRecord();
}

function bindEditorRecord() {
  const btnRecord = q('#btnEditorRecord');
  if (!btnRecord) return;

  function applyRecordButtonUi() {
    if (state.editorRecording) {
      btnRecord.textContent = '停止';
      btnRecord.classList.add('recording');
    } else {
      btnRecord.textContent = '录制';
      btnRecord.classList.remove('recording');
    }
  }

  btnRecord.addEventListener('click', async () => {
    if (state.editorRecording) {
      try { await apiCall('editor_record_stop'); } catch (err) { showToast(`停止录制失败: ${err.message}`); }
      state.editorRecording = false;
      applyRecordButtonUi();
      return;
    }
    const view = getFocusedView();
    if (!view) { showToast('请先打开一个宏标签再录制'); return; }
    try {
      const ret = await apiCall('editor_record_start');
      if (ret.already_recording) { showToast('录制已在进行中'); return; }
      state.editorRecording = true;
      state.editorRecordInsertIndex = null;
      state.editorRecordInsertedCount = 0;
      if (Array.isArray(view.selectedActionPath) && view.selectedActionPath.length) {
        const target = resolveInsertTargetAfterSelection(view);
        if (target.type === 'root') state.editorRecordInsertIndex = target.index;
        else if (target.type === 'loop') state.editorRecordInsertIndex = { loopPath: target.loopPath, index: target.index };
      } else {
        state.editorRecordInsertIndex = view.rows.length;
      }
      state.editorRecordBuffer = [];
      applyRecordButtonUi();
      showToast('录制已开始，键鼠操作将被记录');
    } catch (err) {
      showToast(`启动录制失败: ${err.message}`);
    }
  });

  function recordView() { return getFocusedView(); }

  function getContainerForRecordTarget() {
    const view = recordView();
    if (!view) return null;
    const idx = state.editorRecordInsertIndex;
    if (idx === null || idx === undefined || typeof idx === 'number') return view.rows;
    if (idx.loopPath) {
      const loopAction = getActionAtPath(view, idx.loopPath);
      if (loopAction && Array.isArray(loopAction[2])) return loopAction[2];
    }
    return view.rows;
  }

  function getInsertIndexForRecord() {
    const view = recordView();
    if (!view) return 0;
    const idx = state.editorRecordInsertIndex;
    const count = state.editorRecordInsertedCount || 0;
    if (idx === null || idx === undefined) return view.rows.length;
    if (typeof idx === 'number') return idx + count;
    if (idx.loopPath) return idx.index + count;
    return view.rows.length;
  }

  function setSelectedLineByRecordIndex() {
    const view = recordView();
    if (!view) return;
    const idx = state.editorRecordInsertIndex;
    const count = state.editorRecordInsertedCount || 0;
    if (count <= 0) return;
    const lastInserted = count - 1;
    if (idx === null || idx === undefined) setSelectedLine(view, [view.rows.length - 1], 'action');
    else if (typeof idx === 'number') setSelectedLine(view, [idx + lastInserted], 'action');
    else if (idx.loopPath) setSelectedLine(view, [...idx.loopPath, idx.index + lastInserted], 'action');
  }

  window._onEditorRecordEvent = function(payload) {
    if (!state.editorRecording) return;
    const view = recordView();
    if (!view) return;
    try {
      const data = typeof payload === 'string' ? JSON.parse(payload) : payload;
      const { cmd, key, prev_delay_ms } = data;

      if (prev_delay_ms > 0 && state.editorRecordInsertedCount > 0) {
        const container = getContainerForRecordTarget();
        if (container) {
          const prevIdx = getInsertIndexForRecord() - 1;
          if (prevIdx >= 0 && prevIdx < container.length) {
            const prevAction = container[prevIdx];
            if (prevAction && prevAction[0] in { kd: 1, ku: 1, md: 1, mu: 1 }) prevAction[2] = prev_delay_ms;
          }
        }
      }
      if (state.editorRecordBuffer.length > 0 && prev_delay_ms > 0) {
        const last = state.editorRecordBuffer[state.editorRecordBuffer.length - 1];
        last[2] = prev_delay_ms;
      }

      const action = [cmd, key, 0];
      state.editorRecordBuffer.push(action);

      const container = getContainerForRecordTarget();
      if (container) {
        container.splice(getInsertIndexForRecord(), 0, cloneAction(action));
        state.editorRecordInsertedCount++;
        setSelectedLineByRecordIndex();
        renderViewList(view);
      }
    } catch (e) {
      console.error('_onEditorRecordEvent error:', e);
    }
  };

  window._onEditorRecordStop = function(payload) {
    if (!state.editorRecording) return;
    state.editorRecording = false;
    applyRecordButtonUi();
    const view = recordView();
    try {
      const container = getContainerForRecordTarget();
      if (view && container) {
        if (state.editorRecordInsertedCount > 0) {
          const lastIdx = getInsertIndexForRecord() - 1;
          if (lastIdx >= 0 && lastIdx < container.length) {
            const lastAction = container[lastIdx];
            if (lastAction && lastAction[0] === 'mu' && lastAction[1] === 'left') {
              container.splice(lastIdx, 1);
              state.editorRecordInsertedCount--;
              if (state.editorRecordInsertedCount > 0) {
                const prevIdx = getInsertIndexForRecord() - 1;
                if (prevIdx >= 0 && prevIdx < container.length) {
                  const prevAction = container[prevIdx];
                  if (prevAction && prevAction[0] === 'md' && prevAction[1] === 'left') {
                    container.splice(prevIdx, 1);
                    state.editorRecordInsertedCount--;
                  }
                }
              }
            }
          }
        }
        if (state.editorRecordInsertedCount > 0) setSelectedLineByRecordIndex();

        const data = typeof payload === 'string' ? JSON.parse(payload) : payload;
        const tailDelay = data?.tail_delay_ms || 0;
        if (tailDelay > 0 && state.editorRecordInsertedCount > 0) {
          const cont = getContainerForRecordTarget();
          if (cont) {
            const prevIdx = getInsertIndexForRecord() - 1;
            if (prevIdx >= 0 && prevIdx < cont.length) {
              const prevAction = cont[prevIdx];
              if (prevAction && prevAction[0] in { kd: 1, ku: 1, md: 1, mu: 1 }) prevAction[2] = tailDelay;
            }
          }
        }
      }
    } catch (e) {
      console.error('_onEditorRecordStop error:', e);
    }
    state.editorRecordBuffer = [];
    state.editorRecordInsertIndex = null;
    state.editorRecordInsertedCount = 0;
    if (view) renderViewList(view);
    showToast('录制已停止');
  };
}

// 仅用于静态预览自检：验证小窗排序 / 拖放插入位置（不参与正常流程）
export function previewOps(op) {
  if (op === 'reorder-last-first') {
    const last = state.editorViews[state.editorViews.length - 1];
    if (last) reorderPanes(last.id, -1e6); // clientX 极小 → 插到最前
    return;
  }
  if (op === 'insert-front') {
    if (state.editorTabs[2]) createNewPaneWithTab(state.editorTabs[2], 0);
    return;
  }
  if (op === 'insert-mid') {
    if (state.editorTabs[2]) createNewPaneWithTab(state.editorTabs[2], 1);
    return;
  }
  if (op === 'bp') {
    const v = state.editorViews[0] || getFocusedView();
    if (v && v.rows && v.rows.length) {
      if (!v.breakpoints) v.breakpoints = new Set();
      v.breakpoints.add('0');
      if (v.rows.length > 4) v.breakpoints.add('4');
      renderViewList(v);
    }
    return;
  }
  if (op === 'bp-inline') {
    // 打开第 3 行的双击内联编辑面板（用于自检测试点开关按钮的呈现）
    previewOps('bp');
    const v = state.editorViews[0] || getFocusedView();
    if (v && v.rows && v.rows.length > 2) {
      if (v.breakpoints) v.breakpoints.add('2');
      v.inlineEditingPathKey = '2';
      renderViewList(v);
    }
    return;
  }
  if (op === 'ext') {
    setExtCommandsForPreview([
      {
        name: 'ext.echo', label: '测试回显（内置）', has_handler: true,
        args: [
          { name: 'text', label: '文本', type: 'string', default: 'hello' },
          { name: 'count', label: '次数', type: 'number', default: 1, min: 1, max: 10, step: 1 },
        ],
      },
      {
        name: 'fps.lock', label: '锁定帧率（需插件）', planned: true, has_handler: false,
        args: [
          { name: 'fps', label: '目标帧率', type: 'number', default: 30, min: 1, max: 240, step: 1 },
          { name: 'mode', label: '方式', type: 'enum', default: 'set', options: ['set', 'restore'] },
        ],
      },
    ]);
    const sel = q('#actionType');
    if (sel) sel.value = 'ext';
    refreshExtForm();
  }
}

// 仅用于"无后端静态预览"：填充示例标签与小窗（paneCount 控制默认展开几个小窗）
export function seedPreviewTabs(paneCount = 1) {
  // 第一条故意做长，便于自检"小窗内独立滚动"
  const longRows = [['note', '长宏示例（用于验证小窗内滚动）']];
  for (let i = 0; i < 18; i++) {
    const k = ['w', 'a', 's', 'd'][i % 4];
    longRows.push(['kd', k, 50], ['ku', k, 60]);
  }
  longRows.push(['ext', 'fps.lock', 30]);

  const samples = [
    ['宏/示例/连招A.json', longRows],
    ['宏/示例/连招B.json', [['loop', 3, [['kd', 'w', 50], ['ku', 'w', 100]]], ['move_to', 960, 540, 150], ['scroll', 120]]],
    ['宏/示例/测试C.json', [['note', '演示注释'], ['md', 'left', 50], ['mu', 'left', 50], { __raw: '["未知指令示例",1,2]' }]],
  ];
  samples.forEach(([path, rows]) => {
    const tab = { id: `t${++state.editorTabSeq}`, path, rows: normalizeMacroRows(rows), dirty: false, savedSnapshot: '' };
    snapshotTab(tab);
    state.editorTabs.push(tab);
  });
  state.activeTabId = state.editorTabs[0] ? state.editorTabs[0].id : null;
  // 只把第一个标签装入默认小窗；其余留在标签栏，可拖拽出更多小窗
  if (state.editorTabs[0]) placeTab(state.editorTabs[0]);
  const extra = Math.max(0, Math.min(MAX_PANES, paneCount) - 1);
  for (let i = 0; i < extra; i++) {
    if (state.editorTabs[i + 1]) createNewPaneWithTab(state.editorTabs[i + 1]);
  }
  if (state.editorTabs[1]) state.editorTabs[1].dirty = true;
  renderEditorTabBar();
  state.editorTabs.forEach((tab) => markTabDirty(tab));
}
