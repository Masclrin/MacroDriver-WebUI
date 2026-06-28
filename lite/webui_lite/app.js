const state = {
  macros: [],
  macroTree: { name: '宏', path: '宏', folders: [], files: [] },
  selectedMacro: null,
  consoleLastId: 0,
  consoleLineCount: 0,
  currentTab: 'macro',
  showDebugParams: false,
  runtimeProfile: {
    speed_factor: 1,
    random_enabled: false,
    random_min_ms: 0,
    random_max_ms: 0,
    low_cpu_enabled: false,
    low_cpu_time_period: true,
  },
  bootstrapDone: false,
  pollConsoleBusy: false,
  pollTimerId: null,
  snapshotTimerId: null,
  bindingTimerId: null,
  listenerTimerId: null,
  statusToastTs: {},
  editorRows: [],
  expandedLoopPathKeys: new Set(),
  selectedActionPath: null,
  selectedLineKind: 'action',
  inlineEditingPathKey: null,
  batchCommentMode: false,
  draggedActionPath: null,
  _lastActionTypeGroupKey: null,
  editorRecording: false,
};

const PARAM_GUIDE_FALLBACK = {};
const RECOMMENDED_RANDOM_DELAY_RULES = [
  { min: 0, max: 199, fixed_ms: 3 },
  { min: 200, max: 800, fixed_ms: 6 },
];
const HIDE_DEFAULT_FIELD_IDS = new Set([
  'recorder.ALLOWED_KEYS',
  'executor.EXEC_SPEED_FACTOR',
  'executor.MACRO_RELOAD_KEY',
]);

const ACTION_FORM_DEFAULTS = {
  kd: { arg1: 'w', arg2: '50' },
  ku: { arg1: 'w', arg2: '50' },
  md: { arg1: 'left', arg2: '50' },
  mu: { arg1: 'left', arg2: '50' },
  wait: { arg1: '50', arg2: '' },
  view: { arg1: '0,0', arg2: '50' },
  loop: { arg1: '1', arg2: '' },
  import: { arg1: '', arg2: '' },
  note: { arg1: '备注', arg2: '' },
};

const ACTION_FORM_UI = {
  kd: { arg1Label: '按键', arg2Label: '延迟(ms)', arg1Placeholder: '如 w / space / 1', arg2Placeholder: '50', showArg2: true },
  ku: { arg1Label: '按键', arg2Label: '延迟(ms)', arg1Placeholder: '如 w / space / 1', arg2Placeholder: '50', showArg2: true },
  md: { arg1Label: '鼠标键', arg2Label: '延迟(ms)', arg1Placeholder: '如 left / right / middle', arg2Placeholder: '50', showArg2: true },
  mu: { arg1Label: '鼠标键', arg2Label: '延迟(ms)', arg1Placeholder: '如 left / right / middle', arg2Placeholder: '50', showArg2: true },
  wait: { arg1Label: '等待(ms)', arg2Label: '', arg1Placeholder: '如 50', arg2Placeholder: '', showArg2: false },
  view: { arg1Label: '位移(dx,dy)', arg2Label: '时长(ms)', arg1Placeholder: '如 120,-35', arg2Placeholder: '50', showArg2: true },
  loop: { arg1Label: '循环次数', arg2Label: '', arg1Placeholder: '>= 1', arg2Placeholder: '', showArg2: false },
  import: { arg1Label: '子宏路径', arg2Label: '', arg1Placeholder: '如 宏/录制宏/示例.json', arg2Placeholder: '', showArg2: false },
  note: { arg1Label: '注释内容', arg2Label: '', arg1Placeholder: '输入注释文本（无需输入 //）', arg2Placeholder: '', showArg2: false },
};

const RECOVERABLE_NOTE_PREFIX = '@action ';

const collapsedByView = new Map();

function q(selector) {
  return document.querySelector(selector);
}

function qa(selector) {
  return Array.from(document.querySelectorAll(selector));
}

let _toastTimer = null;
function showToast(text, timeout = 2800) {
  const box = q('#toast');
  box.textContent = text;
  box.classList.remove('hidden');
  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => {
    box.classList.add('hidden');
    _toastTimer = null;
  }, timeout);
}

async function apiCall(method, ...args) {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api[method]) {
    throw new Error(`API 不可用: ${method}`);
  }
  const result = await window.pywebview.api[method](...args);
  if (!result || result.ok === false) {
    const message = result && result.error ? result.error : `调用失败: ${method}`;
    const detail = result && result.detail ? String(result.detail) : '';
    throw new Error(detail ? `${message}: ${detail}` : message);
  }
  return result;
}

function normalizeParamTextValue(v) {
  if (Array.isArray(v) || (typeof v === 'object' && v !== null)) {
    return JSON.stringify(v);
  }
  return String(v ?? '');
}

function escapeHtml(text) {
  return String(text ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function parseNumber(text, fallback = 0) {
  const n = Number(text);
  return Number.isFinite(n) ? n : fallback;
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

function ensureCollapsedSet(viewId) {
  if (!collapsedByView.has(viewId)) {
    collapsedByView.set(viewId, new Set());
  }
  return collapsedByView.get(viewId);
}

function normalizeTree(tree) {
  if (!tree || typeof tree !== 'object') {
    return { name: '宏', path: '宏', folders: [], files: [] };
  }
  return {
    name: String(tree.name || '宏'),
    path: String(tree.path || '宏'),
    folders: Array.isArray(tree.folders) ? tree.folders : [],
    files: Array.isArray(tree.files) ? tree.files : [],
  };
}

function buildRows(tree, depth, collapsedSet, rows) {
  const folders = [...tree.folders].sort((a, b) => String(a.name).localeCompare(String(b.name), 'zh-Hans-CN'));
  const files = [...tree.files].sort((a, b) => String(a.path).localeCompare(String(b.path), 'zh-Hans-CN'));

  folders.forEach((folder) => {
    const folderPath = String(folder.path || '');
    const collapsed = collapsedSet.has(folderPath);
    rows.push({ kind: 'folder', name: String(folder.name || ''), path: folderPath, depth, collapsed });
    if (!collapsed) buildRows(normalizeTree(folder), depth + 1, collapsedSet, rows);
  });

  files.forEach((file) => {
    rows.push({ kind: 'file', name: String(file.name || ''), path: String(file.path || ''), depth });
  });
}

function createRowIndent(depth) {
  const indent = document.createElement('span');
  indent.className = 'macro-tree-indent';
  indent.style.width = `${Math.max(0, depth) * 14}px`;
  return indent;
}

function renderMacroTreeList({ container, tree, viewId, selectedPath, onSelect }) {
  if (!container) return;
  const safeTree = normalizeTree(tree);
  const collapsedSet = ensureCollapsedSet(viewId);
  const rows = [];
  buildRows(safeTree, 0, collapsedSet, rows);
  container.innerHTML = '';

  rows.forEach((row) => {
    const li = document.createElement('li');
    li.classList.add('macro-tree-row');
    li.classList.add(`macro-tree-${row.kind}`);
    li.dataset.path = row.path;

    const content = document.createElement('div');
    content.className = 'macro-tree-content';
    content.appendChild(createRowIndent(row.depth));

    if (row.kind === 'folder') {
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'macro-tree-toggle';
      toggle.textContent = row.collapsed ? '▶' : '▼';
      toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        if (collapsedSet.has(row.path)) collapsedSet.delete(row.path);
        else collapsedSet.add(row.path);
        renderMacroTreeList({ container, tree: safeTree, viewId, selectedPath, onSelect });
      });
      const name = document.createElement('span');
      name.className = 'macro-tree-name';
      name.textContent = row.name;
      content.appendChild(toggle);
      content.appendChild(name);
      li.appendChild(content);
      container.appendChild(li);
      return;
    }

    const dot = document.createElement('span');
    dot.className = 'macro-tree-file-dot';
    dot.textContent = '•';
    content.appendChild(dot);

    const name = document.createElement('span');
    name.className = 'macro-tree-name';
    name.textContent = row.path;
    content.appendChild(name);

    li.classList.toggle('active', row.path === selectedPath);
    li.addEventListener('click', () => {
      if (typeof onSelect === 'function') onSelect(row.path);
    });
    li.appendChild(content);
    container.appendChild(li);
  });
}

function renderMacroList() {
  const list = q('#macroList');
  renderMacroTreeList({
    container: list,
    tree: state.macroTree,
    viewId: 'macro',
    selectedPath: state.selectedMacro,
    onSelect: (path) => {
      state.selectedMacro = path;
      q('#selectedMacroPath').value = path;
      renderMacroList();
    },
  });
}

function pathKey(path) {
  return Array.isArray(path) ? path.join('.') : '';
}

function keyToPath(key) {
  if (!key) return null;
  return String(key)
    .split('.')
    .filter((part) => part.length > 0)
    .map((part) => Number.parseInt(part, 10))
    .filter((num) => Number.isInteger(num) && num >= 0);
}

function cloneAction(action) {
  return JSON.parse(JSON.stringify(action));
}

function isLoopAction(action) {
  return Array.isArray(action)
    && action.length >= 3
    && String(action[0]).trim().toLowerCase() === 'loop'
    && Array.isArray(action[2]);
}

function normalizeAction(action) {
  if (!Array.isArray(action) || !action.length) return ['wait', 50];
  const cmd = String(action[0]).trim().toLowerCase();
  if (cmd === 'loop') {
    const count = Math.max(1, parseNumber(action[1], 1));
    const block = Array.isArray(action[2]) ? action[2].map((row) => normalizeAction(row)) : [];
    return ['loop', count, block];
  }
  if (cmd === 'view') {
    const vec = Array.isArray(action[1]) ? action[1] : [0, 0];
    return ['view', [parseNumber(vec[0], 0), parseNumber(vec[1], 0)], Math.max(1, parseNumber(action[2], 50))];
  }
  if (cmd === 'wait') return ['wait', Math.max(0, parseNumber(action[1], 50))];
  if (cmd === 'import') return ['import', String(action[1] ?? '').trim()];
  if (cmd === 'note') return ['note', String(action[1] ?? '').trim()];
  if (['kd', 'ku', 'md', 'mu'].includes(cmd)) {
    const fallbackKey = cmd === 'md' || cmd === 'mu' ? 'left' : 'w';
    return [cmd, String(action[1] ?? fallbackKey), Math.max(0, parseNumber(action[2], 50))];
  }
  return cloneAction(action);
}

function normalizeMacroRows(rows) {
  if (!Array.isArray(rows)) return [];
  return rows.filter((row) => Array.isArray(row)).map((row) => normalizeAction(row));
}

function getActionAndContainerByPath(path) {
  if (!Array.isArray(path) || !path.length) return null;
  let container = state.editorRows;
  for (let depth = 0; depth < path.length; depth += 1) {
    const index = path[depth];
    if (!Array.isArray(container) || index < 0 || index >= container.length) return null;
    if (depth === path.length - 1) return { container, index, action: container[index] };
    const action = container[index];
    if (!isLoopAction(action)) return null;
    container = action[2];
  }
  return null;
}

function getActionAtPath(path) {
  const found = getActionAndContainerByPath(path);
  return found ? found.action : null;
}

function getParentInsertTarget(path, offset = 0) {
  if (!Array.isArray(path) || !path.length) return { type: 'root', index: state.editorRows.length };
  const parentPath = path.slice(0, -1);
  const index = path[path.length - 1] + offset;
  if (!parentPath.length) return { type: 'root', index };
  return { type: 'loop', loopPath: parentPath, index };
}

function getContainerForTarget(target) {
  if (!target) return null;
  if (target.type === 'root') return state.editorRows;
  if (target.type === 'loop') {
    const loopAction = getActionAtPath(target.loopPath);
    if (!isLoopAction(loopAction)) return null;
    return loopAction[2];
  }
  return null;
}

function isPathPrefix(prefix, full) {
  if (!Array.isArray(prefix) || !Array.isArray(full) || prefix.length > full.length) return false;
  return prefix.every((part, idx) => part === full[idx]);
}

function clearExpandedLoopKeysByPrefix(path) {
  const prefix = pathKey(path);
  if (!prefix) return;
  Array.from(state.expandedLoopPathKeys).forEach((key) => {
    if (key === prefix || key.startsWith(`${prefix}.`)) state.expandedLoopPathKeys.delete(key);
  });
}

function setSelectedLine(path, kind = 'action') {
  state.selectedActionPath = Array.isArray(path) ? [...path] : null;
  state.selectedLineKind = kind;
}

function getRecoverableActionFromNoteText(text) {
  const raw = String(text ?? '').trim();
  if (!raw.startsWith(RECOVERABLE_NOTE_PREFIX)) return null;
  const payload = raw.slice(RECOVERABLE_NOTE_PREFIX.length).trim();
  if (!payload) return null;
  try {
    const parsed = JSON.parse(payload);
    if (!Array.isArray(parsed) || !parsed.length) return null;
    if (String(parsed[0] ?? '').trim().toLowerCase() === 'note') return null;
    return normalizeAction(parsed);
  } catch (_err) { return null; }
}

function makeRecoverableNoteFromAction(action) {
  return ['note', `${RECOVERABLE_NOTE_PREFIX}${JSON.stringify(action)}`];
}

function getDefaultForType(type) {
  return ACTION_FORM_DEFAULTS[type] || ACTION_FORM_DEFAULTS.wait;
}

function getActionFormUi(type) {
  return ACTION_FORM_UI[type] || ACTION_FORM_UI.wait;
}

function updateActionFormUiForType(type) {
  const ui = getActionFormUi(type);
  const arg1Wrap = q('#actionArg1Wrap');
  const arg2Wrap = q('#actionArg2Wrap');
  const arg1Label = q('#actionArg1Label');
  const arg2Label = q('#actionArg2Label');
  const arg1 = q('#actionArg1');
  const arg2 = q('#actionArg2');
  const row = arg1Wrap?.closest('.field-row.triple');
  if (arg1Label) arg1Label.textContent = ui.arg1Label || '参数1';
  if (arg2Label) arg2Label.textContent = ui.arg2Label || '参数2';
  if (arg1) arg1.placeholder = ui.arg1Placeholder || '';
  if (arg2) arg2.placeholder = ui.arg2Placeholder || '';
  if (arg2Wrap) arg2Wrap.style.display = ui.showArg2 ? '' : 'none';
  if (arg1Wrap) arg1Wrap.style.gridColumn = ui.showArg2 ? '' : '2 / 4';
  if (row) row.classList.toggle('single-arg', !ui.showArg2);
}

const ACTION_TYPE_GROUPS = { kd: 'key', ku: 'key', md: 'mouse', mu: 'mouse' };

function switchActionType(newType) {
  const prevType = state._lastActionTypeGroupKey;
  const newGroup = ACTION_TYPE_GROUPS[newType];
  const prevGroup = ACTION_TYPE_GROUPS[prevType];
  if (newGroup && prevGroup && newGroup === prevGroup) {
    updateActionFormUiForType(newType);
  } else {
    ensureActionFormDefaultsForType(newType, true);
  }
  state._lastActionTypeGroupKey = newType;
}

function ensureActionFormDefaultsForType(type, force = false) {
  const defaults = getDefaultForType(type);
  const arg1 = q('#actionArg1');
  const arg2 = q('#actionArg2');
  updateActionFormUiForType(type);
  if (force || !arg1.value.trim()) arg1.value = defaults.arg1;
  if (force || !arg2.value.trim()) arg2.value = defaults.arg2;
  state._lastActionTypeGroupKey = type;
}

function fillActionEditorByAction(action) {
  if (!Array.isArray(action) || !action.length) return;
  const type = String(action[0]).trim().toLowerCase();
  q('#actionType').value = type;
  updateActionFormUiForType(type);
  state._lastActionTypeGroupKey = type;
  if (type === 'wait') { q('#actionArg1').value = String(action[1] ?? 50); q('#actionArg2').value = ''; return; }
  if (type === 'view') { const vec = Array.isArray(action[1]) ? action[1] : [0, 0]; q('#actionArg1').value = `${parseNumber(vec[0], 0)},${parseNumber(vec[1], 0)}`; q('#actionArg2').value = String(action[2] ?? 50); return; }
  if (type === 'loop') { q('#actionArg1').value = String(Math.max(1, parseNumber(action[1], 1))); q('#actionArg2').value = ''; return; }
  if (type === 'import') { q('#actionArg1').value = String(action[1] ?? ''); q('#actionArg2').value = ''; return; }
  if (type === 'note') { q('#actionArg1').value = String(action[1] ?? ''); q('#actionArg2').value = ''; return; }
  if (['kd', 'ku', 'md', 'mu'].includes(type)) { q('#actionArg1').value = String(action[1] ?? getDefaultForType(type).arg1); q('#actionArg2').value = String(action[2] ?? 50); return; }
  ensureActionFormDefaultsForType(type, true);
}

function buildActionFromInputs(options = {}) {
  const existingAction = options.existingAction || null;
  const type = q('#actionType').value;
  const arg1 = q('#actionArg1').value.trim();
  const arg2 = q('#actionArg2').value.trim();
  if (type === 'wait') return ['wait', Math.max(0, parseNumber(arg1 || '50', 50))];
  if (type === 'view') { const [dxText = '0', dyText = '0'] = (arg1 || '0,0').split(','); return ['view', [parseNumber(dxText, 0), parseNumber(dyText, 0)], Math.max(1, parseNumber(arg2 || '50', 50))]; }
  if (type === 'import') { if (!arg1) throw new Error('import 需要子宏路径'); return ['import', arg1]; }
  if (type === 'note') { if (!arg1) throw new Error('note 注释内容不能为空'); return ['note', arg1]; }
  if (type === 'loop') { const count = Math.max(1, parseNumber(arg1 || '1', 1)); const block = isLoopAction(existingAction) ? cloneAction(existingAction[2]) : []; return ['loop', count, block]; }
  if (['kd', 'ku', 'md', 'mu'].includes(type)) { const fallbackKey = getDefaultForType(type).arg1; return [type, arg1 || fallbackKey, Math.max(0, parseNumber(arg2 || '50', 50))]; }
  throw new Error('未知动作类型');
}

function insertActionAtTarget(action, target) {
  const container = getContainerForTarget(target);
  if (!Array.isArray(container)) throw new Error('插入目标无效');
  const insertIndex = Math.max(0, Math.min(parseNumber(target.index, container.length), container.length));
  container.splice(insertIndex, 0, cloneAction(action));
  if (target.type === 'root') { setSelectedLine([insertIndex], 'action'); }
  else { setSelectedLine([...target.loopPath, insertIndex], 'action'); state.expandedLoopPathKeys.add(pathKey(target.loopPath)); }
}

function moveActionToTarget(sourcePath, target) {
  const source = getActionAndContainerByPath(sourcePath);
  if (!source) return false;
  if (target.type === 'loop' && isPathPrefix(sourcePath, target.loopPath)) { showToast('不能将 loop 拖入它自己的循环体'); return false; }
  const targetContainer = getContainerForTarget(target);
  if (!Array.isArray(targetContainer)) return false;
  let targetIndex = Math.max(0, Math.min(parseNumber(target.index, targetContainer.length), targetContainer.length));
  const movingAction = source.action;
  if (source.container === targetContainer && source.index < targetIndex) targetIndex -= 1;
  if (source.container === targetContainer && source.index === targetIndex) return false;
  source.container.splice(source.index, 1);
  targetContainer.splice(targetIndex, 0, movingAction);
  if (target.type === 'root') { setSelectedLine([targetIndex], 'action'); }
  else { setSelectedLine([...target.loopPath, targetIndex], 'action'); state.expandedLoopPathKeys.add(pathKey(target.loopPath)); }
  return true;
}

function resolveInsertTargetAfterSelection() {
  if (!Array.isArray(state.selectedActionPath) || !state.selectedActionPath.length) return { type: 'root', index: state.editorRows.length };
  return getParentInsertTarget(state.selectedActionPath, 1);
}

function toggleCommentForPath(path, options = {}) {
  const silent = Boolean(options.silent);
  const shouldKeepInlineEditor = !state.batchCommentMode;
  const info = getActionAndContainerByPath(path);
  if (!info) { if (!silent) showToast('动作已失效，请重新选择'); return false; }
  const current = info.action;
  const cmd = String(current[0] ?? '').trim().toLowerCase();
  if (cmd === 'note') {
    const restored = getRecoverableActionFromNoteText(current[1]);
    if (!restored) { if (!silent) showToast('该注释不包含可恢复动作'); return false; }
    info.container[info.index] = restored;
    setSelectedLine(path, 'action');
    fillActionEditorByAction(restored);
    state.inlineEditingPathKey = shouldKeepInlineEditor ? pathKey(path) : null;
    if (!silent) showToast('已恢复动作');
    return true;
  }
  const fromLoop = isLoopAction(current);
  info.container[info.index] = makeRecoverableNoteFromAction(current);
  if (fromLoop) clearExpandedLoopKeysByPrefix(path);
  setSelectedLine(path, 'action');
  fillActionEditorByAction(info.container[info.index]);
  state.inlineEditingPathKey = shouldKeepInlineEditor ? pathKey(path) : null;
  if (!silent) showToast('已注释当前动作');
  return true;
}

function updateCurrentActionFromEditor(options = {}) {
  const silent = Boolean(options.silent);
  if (!Array.isArray(state.selectedActionPath) || !state.selectedActionPath.length) { if (!silent) showToast('请先在右侧列表中选择一个动作'); return; }
  const info = getActionAndContainerByPath(state.selectedActionPath);
  if (!info) { if (!silent) showToast('选中动作已失效，请重新选择'); return; }
  const existing = info.action;
  const fromLoop = isLoopAction(existing);
  const toType = q('#actionType').value;
  if (fromLoop && toType !== 'loop') {
    if (silent) return;
    const ok = window.confirm('当前是 loop 动作，改成其他类型会丢失 loop 内部动作。是否继续？');
    if (!ok) return;
  }
  const next = buildActionFromInputs({ existingAction: existing });
  info.container[info.index] = next;
  if (fromLoop && !isLoopAction(next)) clearExpandedLoopKeysByPrefix(state.selectedActionPath);
  renderActionList();
  if (!silent) showToast('当前动作已修改');
}

function formatActionLabel(action, expanded) {
  const cmd = String(action[0] ?? '').trim().toLowerCase();
  if (cmd === 'wait') return `wait ${parseNumber(action[1], 0)}ms`;
  if (cmd === 'view') { const vec = Array.isArray(action[1]) ? action[1] : [0, 0]; return `view [${parseNumber(vec[0], 0)}, ${parseNumber(vec[1], 0)}] ${Math.max(1, parseNumber(action[2], 50))}ms`; }
  if (cmd === 'import') return `import ${String(action[1] ?? '').trim() || '(空路径)'}`;
  if (cmd === 'note') { const noteText = String(action[1] ?? '').trim(); const restored = getRecoverableActionFromNoteText(noteText); if (restored) return `// [可恢复] ${formatActionLabel(restored, false)}`; return `// ${noteText}`; }
  if (cmd === 'loop') { const count = Math.max(1, parseNumber(action[1], 1)); const block = Array.isArray(action[2]) ? action[2] : []; return expanded ? `loop x${count}（展开，共${block.length} 条）` : `loop x${count}（收起，共${block.length} 条）`; }
  if (['kd', 'ku', 'md', 'mu'].includes(cmd)) return `${cmd} '${String(action[1] ?? '')}' ${Math.max(0, parseNumber(action[2], 50))}ms`;
  return JSON.stringify(action);
}

function buildActionRenderLines(actions, parentPath = [], depth = 0, lines = []) {
  actions.forEach((action, index) => {
    const path = [...parentPath, index];
    if (isLoopAction(action)) {
      const expanded = state.expandedLoopPathKeys.has(pathKey(path));
      lines.push({ kind: 'action', path, depth, action, isLoopHead: true, expanded });
      if (expanded) {
        const block = Array.isArray(action[2]) ? action[2] : [];
        if (!block.length) lines.push({ kind: 'loop_empty', path, depth: depth + 1, action });
        else buildActionRenderLines(block, path, depth + 1, lines);
        lines.push({ kind: 'loop_end', path, depth, action });
      }
      return;
    }
    lines.push({ kind: 'action', path, depth, action, isLoopHead: false, expanded: false });
  });
  return lines;
}

function getDropTargetFromLine(line) {
  if (line.kind === 'loop_end') { const loop = getActionAtPath(line.path); const block = isLoopAction(loop) ? loop[2] : []; return { type: 'loop', loopPath: [...line.path], index: block.length }; }
  if (line.kind === 'loop_empty') return { type: 'loop', loopPath: [...line.path], index: 0 };
  if (line.kind === 'action' && line.isLoopHead && line.expanded) return { type: 'loop', loopPath: [...line.path], index: 0 };
  return getParentInsertTarget(line.path, 1);
}

function getInlineEditorValues(action) {
  const cmd = String(action[0]).trim().toLowerCase();
  if (cmd === 'view') { const vec = Array.isArray(action[1]) ? action[1] : [0, 0]; return { type: cmd, arg1: `${parseNumber(vec[0], 0)},${parseNumber(vec[1], 0)}`, arg2: String(Math.max(1, parseNumber(action[2], 50))) }; }
  if (cmd === 'wait') return { type: cmd, arg1: String(Math.max(0, parseNumber(action[1], 50))), arg2: '' };
  if (cmd === 'loop') return { type: cmd, arg1: String(Math.max(1, parseNumber(action[1], 1))), arg2: '' };
  if (cmd === 'import' || cmd === 'note') return { type: cmd, arg1: String(action[1] ?? ''), arg2: '' };
  if (['kd', 'ku', 'md', 'mu'].includes(cmd)) return { type: cmd, arg1: String(action[1] ?? getDefaultForType(cmd).arg1), arg2: String(Math.max(0, parseNumber(action[2], 50))) };
  return { type: cmd, arg1: '', arg2: '' };
}

function appendInlineEditorRow(list, line, lineKey) {
  const action = line.action;
  const values = getInlineEditorValues(action);
  const ui = getActionFormUi(values.type);
  const editorLi = document.createElement('li');
  editorLi.className = 'action-inline-editor';
  editorLi.dataset.inlineEditorFor = lineKey;
  const idxStub = document.createElement('span');
  idxStub.className = 'action-index';
  idxStub.textContent = '';
  const body = document.createElement('div');
  body.className = 'action-inline-editor-body';
  const row1 = document.createElement('div');
  row1.className = ui.showArg2 ? 'inline-edit-grid' : 'inline-edit-grid single';
  const arg1Wrap = document.createElement('div');
  arg1Wrap.className = 'inline-edit-cell';
  const arg1Label = document.createElement('label');
  arg1Label.className = 'inline-edit-label';
  arg1Label.textContent = ui.arg1Label || '参数1';
  const arg1Input = document.createElement('input');
  arg1Input.type = 'text';
  arg1Input.value = values.arg1;
  arg1Input.placeholder = ui.arg1Placeholder || '';
  arg1Wrap.appendChild(arg1Label);
  arg1Wrap.appendChild(arg1Input);
  row1.appendChild(arg1Wrap);
  let arg2Input = null;
  if (ui.showArg2) {
    const arg2Wrap = document.createElement('div');
    arg2Wrap.className = 'inline-edit-cell';
    const arg2Label = document.createElement('label');
    arg2Label.className = 'inline-edit-label';
    arg2Label.textContent = ui.arg2Label || '参数2';
    arg2Input = document.createElement('input');
    arg2Input.type = 'text';
    arg2Input.value = values.arg2;
    arg2Input.placeholder = ui.arg2Placeholder || '';
    arg2Wrap.appendChild(arg2Label);
    arg2Wrap.appendChild(arg2Input);
    row1.appendChild(arg2Wrap);
  }
  const actions = document.createElement('div');
  actions.className = 'inline-actions inline-edit-actions';
  const btnApply = document.createElement('button');
  btnApply.type = 'button';
  btnApply.className = 'primary inline-edit-btn';
  btnApply.textContent = '应用修改';
  actions.appendChild(btnApply);
  const currentCmd = String(action[0] ?? '').trim().toLowerCase();
  const recoverable = currentCmd === 'note' ? getRecoverableActionFromNoteText(action[1]) : null;
  if (currentCmd !== 'note' || recoverable) {
    const btnToggle = document.createElement('button');
    btnToggle.type = 'button';
    btnToggle.className = 'inline-edit-btn';
    btnToggle.textContent = currentCmd === 'note' ? '恢复动作' : '注释动作';
    actions.appendChild(btnToggle);
    btnToggle.addEventListener('click', (e) => { e.stopPropagation(); const ok = toggleCommentForPath(line.path, { silent: false }); if (ok) renderActionList(); });
  }
  body.appendChild(row1);
  body.appendChild(actions);
  const applyToMainForm = () => { q('#actionType').value = values.type; updateActionFormUiForType(values.type); q('#actionArg1').value = arg1Input.value; q('#actionArg2').value = arg2Input ? arg2Input.value : ''; setSelectedLine(line.path, 'action'); };
  arg1Input.addEventListener('input', () => applyToMainForm());
  if (arg2Input) arg2Input.addEventListener('input', () => applyToMainForm());
  const keepEditing = () => { state.inlineEditingPathKey = lineKey; setSelectedLine(line.path, 'action'); };
  arg1Input.addEventListener('focus', keepEditing);
  if (arg2Input) arg2Input.addEventListener('focus', keepEditing);
  btnApply.addEventListener('click', (e) => { e.stopPropagation(); applyToMainForm(); updateCurrentActionFromEditor({ silent: true }); state.inlineEditingPathKey = lineKey; renderActionList(); });
  editorLi.addEventListener('click', (e) => { e.stopPropagation(); keepEditing(); });
  editorLi.appendChild(idxStub);
  editorLi.appendChild(body);
  list.appendChild(editorLi);
}

function renderActionList() {
  const list = q('#actionList');
  list.innerHTML = '';
  const lines = buildActionRenderLines(state.editorRows, [], 0, []);
  lines.forEach((line, lineIndex) => {
    const li = document.createElement('li');
    const lineKey = pathKey(line.path);
    const active = Array.isArray(state.selectedActionPath) && pathKey(state.selectedActionPath) === lineKey && state.selectedLineKind === line.kind;
    li.classList.toggle('active', active);
    li.classList.toggle('editing', !state.batchCommentMode && line.kind === 'action' && state.inlineEditingPathKey === lineKey);
    if (line.kind === 'action' && line.isLoopHead) li.classList.add('loop-head');
    if (line.kind === 'loop_end') li.classList.add('loop-end');
    if (line.kind === 'loop_empty') li.classList.add('loop-empty');
    li.dataset.lineKey = lineKey;
    li.dataset.lineKind = line.kind;
    li.draggable = line.kind === 'action' || line.kind === 'loop_end';
    li.addEventListener('click', () => {
      if (state.batchCommentMode && line.kind === 'action') { state.inlineEditingPathKey = null; const ok = toggleCommentForPath(line.path, { silent: false }); if (ok) renderActionList(); return; }
      setSelectedLine(line.path, line.kind);
      const selected = getActionAtPath(line.path);
      if (selected) fillActionEditorByAction(selected);
      renderActionList();
    });
    li.addEventListener('dblclick', (e) => { if (state.batchCommentMode) return; if (line.kind !== 'action') return; if (e.target instanceof Element && e.target.closest('.loop-toggle')) return; e.stopPropagation(); state.inlineEditingPathKey = lineKey; setSelectedLine(line.path, 'action'); const selected = getActionAtPath(line.path); if (selected) fillActionEditorByAction(selected); renderActionList(); });
    li.addEventListener('dragstart', (e) => { state.draggedActionPath = [...line.path]; e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/action-path', JSON.stringify(line.path)); });
    li.addEventListener('dragend', () => { state.draggedActionPath = null; li.classList.remove('drag-over'); });
    li.addEventListener('dragover', (e) => { e.preventDefault(); li.classList.add('drag-over'); });
    li.addEventListener('dragleave', () => { li.classList.remove('drag-over'); });
    li.addEventListener('drop', (e) => {
      e.preventDefault();
      li.classList.remove('drag-over');
      const target = getDropTargetFromLine(line);
      const macroPath = e.dataTransfer.getData('text/macro-path') || e.dataTransfer.getData('text/plain');
      if (macroPath && macroPath.toLowerCase().endsWith('.json')) { insertActionAtTarget(['import', macroPath], target); renderActionList(); showToast(`已插入 import: ${macroPath}`); return; }
      if (!Array.isArray(state.draggedActionPath)) return;
      const moved = moveActionToTarget(state.draggedActionPath, target);
      if (moved) renderActionList();
      state.draggedActionPath = null;
    });
    const idxEl = document.createElement('span');
    idxEl.className = 'action-index';
    idxEl.textContent = String(lineIndex + 1);
    const textWrap = document.createElement('span');
    textWrap.className = 'action-text';
    const indent = document.createElement('span');
    indent.className = 'action-indent';
    indent.style.width = `${line.depth * 14}px`;
    textWrap.appendChild(indent);
    if (line.kind === 'action' && line.isLoopHead) {
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'loop-toggle';
      toggle.textContent = line.expanded ? '▼' : '▶';
      toggle.addEventListener('click', (e) => { e.stopPropagation(); const key = pathKey(line.path); if (state.expandedLoopPathKeys.has(key)) state.expandedLoopPathKeys.delete(key); else state.expandedLoopPathKeys.add(key); renderActionList(); });
      toggle.addEventListener('dblclick', (e) => { e.stopPropagation(); const key = pathKey(line.path); if (state.expandedLoopPathKeys.has(key)) state.expandedLoopPathKeys.delete(key); else state.expandedLoopPathKeys.add(key); renderActionList(); });
      textWrap.appendChild(toggle);
      textWrap.appendChild(document.createTextNode(formatActionLabel(line.action, line.expanded)));
    } else if (line.kind === 'loop_end') {
      textWrap.appendChild(document.createTextNode('↳ loop_end'));
    } else if (line.kind === 'loop_empty') {
      textWrap.appendChild(document.createTextNode('(loop 内暂无动作，可拖拽动作到这里)'));
    } else {
      textWrap.appendChild(document.createTextNode(formatActionLabel(line.action, false)));
    }
    li.appendChild(idxEl);
    li.appendChild(textWrap);
    list.appendChild(li);
    if (!state.batchCommentMode && line.kind === 'action' && state.inlineEditingPathKey === lineKey) appendInlineEditorRow(list, line, lineKey);
  });
}

function refreshBatchCommentButton() {
  const btn = q('#btnBatchComment');
  const list = q('#actionList');
  if (list) list.classList.toggle('batch-comment-mode', state.batchCommentMode);
  if (!btn) return;
  btn.textContent = `批量注释: ${state.batchCommentMode ? '开' : '关'}`;
  btn.classList.toggle('active', state.batchCommentMode);
}

async function loadMacroToEditor(path) {
  const data = await apiCall('read_macro', path);
  state.editorRows = normalizeMacroRows(data.rows);
  state.expandedLoopPathKeys = new Set();
  state.inlineEditingPathKey = null;
  if (state.editorRows.length) { setSelectedLine([0], 'action'); fillActionEditorByAction(state.editorRows[0]); }
  else { setSelectedLine(null, 'action'); ensureActionFormDefaultsForType(q('#actionType').value || 'kd', true); }
  state.selectedMacro = path;
  q('#selectedMacroPath').value = path;
  renderMacroList();
  renderEditorMacroBrowser();
  renderActionList();
}

function renderEditorMacroBrowser() {
  const list = q('#editorMacroList');
  renderMacroTreeList({
    container: list,
    tree: state.macroTree,
    viewId: 'editor',
    selectedPath: null,
    onSelect: (path) => { loadMacroToEditor(path).catch((err) => showToast(err.message)); },
  });
}

async function toggleEditorRecording() {
  if (state.editorRecording) {
    try {
      const ret = await apiCall('editor_record_stop');
      state.editorRecording = false;
      q('#btnEditorRecord').textContent = '录制';
      q('#btnEditorRecord').classList.remove('recording');
      const actions = ret.actions || [];
      if (actions.length) {
        actions.forEach((a) => { state.editorRows.push(normalizeAction(a)); });
        renderActionList();
        showToast(`录制完成，已追加 ${actions.length} 个动作`);
      } else {
        showToast('录制结束，未捕获动作');
      }
    } catch (err) {
      showToast(`停止录制失败: ${err.message}`);
    }
    return;
  }
  try {
    await apiCall('editor_record_start');
    state.editorRecording = true;
    q('#btnEditorRecord').textContent = '停止录制';
    q('#btnEditorRecord').classList.add('recording');
    showToast('录制已开始，按键/鼠标操作将被记录');
  } catch (err) {
    showToast(`启动录制失败: ${err.message}`);
  }
}

window._onEditorRecordEvent = function (payload) {
  if (!state.editorRecording) return;
  const action = normalizeAction([payload.cmd, payload.key, payload.prev_delay_ms || 0]);
  state.editorRows.push(action);
  renderActionList();
};

window._onEditorRecordStop = function () {
  state.editorRecording = false;
  const btn = q('#btnEditorRecord');
  if (btn) { btn.textContent = '录制'; btn.classList.remove('recording'); }
};

async function refreshMacros() {
  const keyword = q('#macroFilter').value.trim();
  try {
    const data = await apiCall('list_macro_tree', keyword);
    state.macros = data.items || [];
    state.macroTree = data.tree || { name: '宏', path: '宏', folders: [], files: [] };
  } catch (err) {
    state.macros = [];
    state.macroTree = { name: '宏', path: '宏', folders: [], files: [] };
  }
  if (state.selectedMacro && !state.macros.some((m) => m.path === state.selectedMacro)) {
    state.selectedMacro = null;
    q('#selectedMacroPath').value = '';
  }
  renderMacroList();
  renderEditorMacroBrowser();
}

function syncRuntimeProfileUI() {
  q('#macroSpeedFactor').value = String(state.runtimeProfile.speed_factor ?? 1);
  q('#macroRandomMin').value = String(state.runtimeProfile.random_min_ms ?? 0);
  q('#macroRandomMax').value = String(state.runtimeProfile.random_max_ms ?? 0);
  q('#btnMacroRandomToggle').textContent = `随机延迟: ${state.runtimeProfile.random_enabled ? '开' : '关'}`;
  q('#btnLowCpuModeToggle').textContent = `CPU低占用: ${state.runtimeProfile.low_cpu_enabled ? '开' : '关'}`;
  const timePeriodBtn = q('#btnTimePeriodToggle');
  timePeriodBtn.textContent = `时器分辨率(1): ${state.runtimeProfile.low_cpu_time_period ? '开' : '关'}`;
  timePeriodBtn.style.display = state.runtimeProfile.low_cpu_enabled ? '' : 'none';
}

async function refreshMacroRuntimeProfile() {
  const data = await apiCall('get_macro_runtime_profile');
  state.runtimeProfile = {
    speed_factor: data.speed_factor,
    random_enabled: data.random_enabled,
    random_min_ms: data.random_min_ms,
    random_max_ms: data.random_max_ms,
    low_cpu_enabled: Boolean(data.low_cpu_enabled),
    low_cpu_time_period: Boolean(data.low_cpu_time_period),
  };
  syncRuntimeProfileUI();
}

async function applyMacroRuntimeProfile() {
  const payload = {
    speed_factor: parseNumber(q('#macroSpeedFactor').value, 1),
    random_enabled: Boolean(state.runtimeProfile.random_enabled),
    random_min_ms: parseNumber(q('#macroRandomMin').value, 0),
    random_max_ms: parseNumber(q('#macroRandomMax').value, 0),
    low_cpu_enabled: Boolean(state.runtimeProfile.low_cpu_enabled),
    low_cpu_time_period: Boolean(state.runtimeProfile.low_cpu_time_period),
  };
  const ret = await apiCall('update_macro_runtime_profile', payload);
  state.runtimeProfile = {
    speed_factor: ret.speed_factor,
    random_enabled: ret.random_enabled,
    random_min_ms: ret.random_min_ms,
    random_max_ms: ret.random_max_ms,
    low_cpu_enabled: Boolean(ret.low_cpu_enabled),
    low_cpu_time_period: Boolean(ret.low_cpu_time_period),
  };
  syncRuntimeProfileUI();
  showToast('执行参数已应用');
}

function renderBindings(items) {
  const list = q('#bindingList');
  list.innerHTML = '';
  items.forEach((row) => {
    const li = document.createElement('li');
    li.classList.toggle('running', Number(row.live_count || 0) > 0);

    const left = document.createElement('div');
    left.className = 'binding-left';
    const macroPaths = Array.isArray(row.macro_paths) && row.macro_paths.length
      ? row.macro_paths
      : (row.macro_path ? [row.macro_path] : []);
    const macroDisplay = macroPaths.join(' + ');
    const statusText = Number(row.live_count || 0) > 0
      ? `运行中 ${row.live_count}`
      : Number(row.stopping_count || 0) > 0
        ? '停止中'
        : '空闲';
    left.textContent = `${row.trigger} -> ${macroDisplay} | repeat=${row.repeat} | ${row.running_press_mode} | ${statusText}`;

    const actions = document.createElement('div');
    actions.className = 'inline-actions binding-actions';

    const btnRun = document.createElement('button');
    btnRun.textContent = '触发';
    btnRun.addEventListener('click', async (e) => {
      e.stopPropagation();
      await apiCall('trigger_macro', row.trigger);
      showToast(`已触发: ${row.trigger}`);
      refreshBindings();
    });

    const btnUnbind = document.createElement('button');
    btnUnbind.className = 'danger';
    btnUnbind.textContent = '解绑';
    btnUnbind.addEventListener('click', async (e) => {
      e.stopPropagation();
      await apiCall('unbind_macro', row.trigger);
      showToast(`已解绑: ${row.trigger}`);
      refreshBindings();
    });

    actions.appendChild(btnRun);
    actions.appendChild(btnUnbind);
    li.appendChild(left);
    li.appendChild(actions);
    list.appendChild(li);
  });
}

async function refreshBindings() {
  const data = await apiCall('list_bindings');
  renderBindings(data.items || []);
}

async function refreshSnapshot() {
  try {
    const data = await apiCall('get_dashboard_snapshot');
    q('#statActive').textContent = String(data.active_macros || 0);
    q('#statPaused').textContent = data.global_paused ? '是' : '否';
    q('#btnGlobalPause').textContent = data.global_paused ? '关闭全局暂停' : '开启全局暂停';
    q('#btnGlobalPause').classList.toggle('active-glow', !!data.global_paused);
  } catch (err) {
    console.error(err);
  }
}

async function refreshListenerButtonState() {
  try {
    const data = await apiCall('get_listener_state');
    q('#btnStartListeners').textContent = data.running ? '关闭全局宏监听' : '启动全局宏监听';
    q('#btnStartListeners').classList.toggle('active-glow', !!data.running);
  } catch (err) {
    console.error(err);
  }
}

async function pollConsole() {
  if (state.pollConsoleBusy) return;
  state.pollConsoleBusy = true;
  try {
    const data = await apiCall('poll_console', state.consoleLastId, 120);
    const entries = data.entries || [];
    if (!entries.length) return;
    const pre = q('#consoleOutput');
    entries.forEach((item) => {
      pre.textContent += `[${item.ts}] ${item.text}\n`;
      state.consoleLineCount += 1;
    });
    state.consoleLastId = data.latest_id || state.consoleLastId;
    if (state.consoleLineCount > 4000) {
      const lines = pre.textContent.split('\n');
      const tail = lines.slice(-3200).join('\n');
      pre.textContent = tail;
      state.consoleLineCount = tail.split('\n').length;
    }
    pre.scrollTop = pre.scrollHeight;
  } catch (err) {
    console.error(err);
  } finally {
    state.pollConsoleBusy = false;
  }
}

async function clearConsole() {
  await apiCall('clear_console');
  state.consoleLastId = 0;
  state.consoleLineCount = 0;
  q('#consoleOutput').textContent = '';
  showToast('控制台已清空');
}

async function popoutConsole() {
  try {
    const result = await apiCall('open_console_popout');
    if (!result.ok) showToast(result.error || '打开弹出窗口失败');
  } catch (err) {
    showToast('打开弹出窗口失败: ' + (err.message || err));
  }
}

async function renderGlobalParams() {
  const container = q('#paramsContainer');
  const configPathEl = q('#paramsConfigPath');
  const data = await apiCall('get_global_params');
  container.innerHTML = '';

  if (configPathEl) {
    configPathEl.textContent = `当前配置文件: ${data.config_path || '未知'}`;
  }

  const tierTitle = { basic: '基础参数', advanced: '高级参数', debug: '未开放参数' };

  const createTierHost = (tier, titleText, count) => {
    if (tier === 'advanced' || tier === 'debug') {
      const details = document.createElement('details');
      details.className = 'param-tier-fold';
      details.open = false;
      const summary = document.createElement('summary');
      summary.textContent = `${titleText} (${count})`;
      details.appendChild(summary);
      const body = document.createElement('div');
      body.className = 'param-tier-body';
      details.appendChild(body);
      return { host: details, body };
    }
    const title = document.createElement('div');
    title.className = 'param-tier-title';
    title.textContent = `${titleText} (${count})`;
    const body = document.createElement('div');
    body.className = 'param-tier-body';
    const frag = document.createDocumentFragment();
    frag.appendChild(title);
    frag.appendChild(body);
    return { host: frag, body };
  };

  Object.entries(data.sections).forEach(([sectionName, sectionData]) => {
    const rows = Array.isArray(sectionData.rows) ? sectionData.rows : [];
    const block = document.createElement('div');
    block.className = 'param-group';
    const title = document.createElement('h4');
    title.textContent = sectionData.title || sectionName;
    block.appendChild(title);

    ['basic', 'advanced', 'debug'].forEach((tier) => {
      if (tier === 'debug' && !state.showDebugParams) return;
      const tierRows = rows.filter((r) => (r.tier || 'basic') === tier);
      if (!tierRows.length) return;
      const { host, body } = createTierHost(tier, tierTitle[tier] || tier, tierRows.length);
      block.appendChild(host);

      tierRows.forEach((field) => {
        const item = document.createElement('div');
        item.className = 'param-item';
        item.dataset.fieldId = field.field_id;

        const head = document.createElement('div');
        head.className = 'param-head';

        const labelWrap = document.createElement('div');
        labelWrap.className = 'param-label-wrap';

        const label = document.createElement('span');
        label.className = 'param-label-cn';
        label.textContent = field.label;
        labelWrap.appendChild(label);

        const fallbackGuide = PARAM_GUIDE_FALLBACK[field.field_id] || {};
        const desc = field.desc || fallbackGuide.desc || '';
        const recommend = field.recommend || fallbackGuide.recommend || '';
        const example = field.example || fallbackGuide.example || '';

        const tip = document.createElement('div');
        tip.className = 'param-hover-tip';
        tip.innerHTML = [
          `<div><strong>变量名</strong>: ${escapeHtml(field.key)}</div>`,
          desc ? `<div><strong>说明</strong>: ${escapeHtml(desc)}</div>` : '',
          recommend ? `<div><strong>建议</strong>: ${escapeHtml(recommend)}</div>` : '',
          example ? `<div><strong>示例</strong>: ${escapeHtml(example)}</div>` : '',
        ].filter(Boolean).join('');
        labelWrap.appendChild(tip);

        if (field.hint) {
          const hintEl = document.createElement('div');
          hintEl.className = 'param-hint-line';
          hintEl.textContent = field.hint;
          labelWrap.appendChild(hintEl);
        }

        if (!HIDE_DEFAULT_FIELD_IDS.has(field.field_id)) {
          const defaultEl = document.createElement('div');
          defaultEl.className = 'param-default';
          defaultEl.textContent = `默认: ${normalizeParamTextValue(field.default)}`;
          labelWrap.appendChild(defaultEl);
        }
        head.appendChild(labelWrap);

        let input;
        if (field.type === 'bool') {
          const switchWrap = document.createElement('label');
          switchWrap.className = 'switch';
          input = document.createElement('input');
          input.type = 'checkbox';
          input.checked = Boolean(field.value);
          const slider = document.createElement('span');
          slider.className = 'switch-slider';
          switchWrap.appendChild(input);
          switchWrap.appendChild(slider);
          head.appendChild(switchWrap);
        } else if (Array.isArray(field.options) && field.options.length) {
          input = document.createElement('select');
          input.className = 'param-input';
          field.options.forEach((opt) => {
            const op = document.createElement('option');
            op.value = String(opt);
            op.textContent = String(opt);
            op.selected = String(field.value) === String(opt);
            input.appendChild(op);
          });
          head.appendChild(input);
        } else {
          if (field.type === 'list' || field.type === 'json' || field.type === 'set') {
            input = document.createElement('textarea');
            input.className = 'param-input param-textarea';
            input.rows = 3;
            input.value = normalizeParamTextValue(field.value);
          } else {
            input = document.createElement('input');
            input.className = 'param-input';
            input.type = field.type === 'int' || field.type === 'float' ? 'number' : 'text';
            if (field.type === 'float') input.step = '0.01';
            input.value = normalizeParamTextValue(field.value);
          }
          head.appendChild(input);
        }

        input.dataset.paramSection = sectionName;
        input.dataset.paramKey = field.key;
        input.dataset.paramType = field.type;
        input.dataset.fieldId = field.field_id;
        input.dataset.dependsOn = JSON.stringify(field.depends_on || []);
        input.dataset.paramLabel = field.label;
        input.dataset.currentValue = JSON.stringify(field.value);
        input.addEventListener('change', () => applyParamDependencies());
        input.addEventListener('input', () => applyParamDependencies());

        item.appendChild(head);

        if (field.field_id === 'executor.RANDOM_DELAY_ADJUST_RULES_BY_DELAY_MS') {
          const tools = document.createElement('div');
          tools.className = 'inline-actions param-inline-tools';
          const btnFill = document.createElement('button');
          btnFill.type = 'button';
          btnFill.textContent = '填入推荐分档';
          btnFill.addEventListener('click', () => {
            input.value = JSON.stringify(RECOMMENDED_RANDOM_DELAY_RULES, null, 2);
            applyParamDependencies();
          });
          tools.appendChild(btnFill);
          item.appendChild(tools);
        }

        body.appendChild(item);
      });
    });

    container.appendChild(block);
  });

  applyParamDependencies();
}

function readTypedInputValue(input) {
  const type = input.dataset.paramType;
  if (type === 'bool') return input.checked;
  if (type === 'int') return Number.parseInt(input.value || '0', 10) || 0;
  if (type === 'float') return Number(input.value || '0') || 0;
  return input.value;
}

function checkDependency(dep, valuesById) {
  const target = `${dep.section}.${dep.key}`;
  const expected = Object.prototype.hasOwnProperty.call(dep, 'value') ? dep.value : true;
  return String(valuesById[target]) === String(expected);
}

function applyParamDependencies() {
  const inputs = qa('[data-param-key]');
  const valuesById = {};
  inputs.forEach((input) => {
    valuesById[input.dataset.fieldId] = readTypedInputValue(input);
  });
  inputs.forEach((input) => {
    const deps = JSON.parse(input.dataset.dependsOn || '[]');
    const enabled = deps.every((dep) => checkDependency(dep, valuesById));
    input.disabled = !enabled;
    const row = input.closest('.param-item');
    if (row) row.classList.toggle('disabled', !enabled);
  });
}

async function saveGlobalParams() {
  const payload = {};
  const parseStructured = (rawText, type) => {
    const text = String(rawText ?? '').trim();
    if (!text) {
      if (type === 'json') return {};
      return [];
    }
    if (text.startsWith('[') || text.startsWith('{')) {
      const parsed = JSON.parse(text);
      if (type === 'json' && (typeof parsed !== 'object' || parsed === null)) {
        throw new Error('JSON 参数必须是对象或数组');
      }
      if ((type === 'list' || type === 'set') && !Array.isArray(parsed)) {
        throw new Error('列表参数必须是 JSON 数组');
      }
      return parsed;
    }
    if (type === 'json') throw new Error('JSON 参数请使用对象格式，如 {"key": "value"}');
    return text.split(',').map((s) => s.trim()).filter(Boolean);
  };

  const parseByType = (input) => {
    const type = input.dataset.paramType;
    const currentValue = JSON.parse(input.dataset.currentValue || 'null');
    const text = String(input.value ?? '').trim();
    if (type === 'bool') return input.checked;
    if (type === 'int') {
      if (!text) return Number.parseInt(currentValue, 10) || 0;
      const value = Number.parseInt(text, 10);
      if (!Number.isFinite(value)) throw new Error('整数格式错误');
      return value;
    }
    if (type === 'float') {
      if (!text) return Number(currentValue) || 0;
      const value = Number(text);
      if (!Number.isFinite(value)) throw new Error('数字格式错误');
      return value;
    }
    if (type === 'list') return parseStructured(text, 'list');
    if (type === 'set') return parseStructured(text, 'set');
    if (type === 'json') return parseStructured(text, 'json');
    return input.value;
  };

  qa('[data-param-key]').forEach((input) => {
    const section = input.dataset.paramSection;
    const key = input.dataset.paramKey;
    if (!payload[section]) payload[section] = {};
    try {
      payload[section][key] = parseByType(input);
    } catch (err) {
      const label = input.dataset.paramLabel || key;
      throw new Error(`参数"${label}"格式错误: ${err.message}`);
    }
  });

  await apiCall('update_global_params', payload);
  await renderGlobalParams();
  showToast('参数已保存并写入配置');
}

async function importGlobalParams() {
  const selected = await apiCall('choose_param_import_file');
  if (selected.canceled) return;
  if (!window.confirm(`导入参数将覆盖 config，是否继续？\n${selected.path}`)) return;
  await apiCall('import_global_params', selected.path);
  await renderGlobalParams();
  showToast('参数导入成功，已覆盖配置');
}

async function exportGlobalParams() {
  const selected = await apiCall('choose_param_export_file');
  if (selected.canceled) return;
  const ret = await apiCall('export_global_params', selected.path);
  showToast(`参数已导出: ${ret.path}`);
}

async function resetGlobalParamsToDefault() {
  if (!window.confirm('确认恢复默认参数并覆盖 config 吗？')) return;
  if (!window.confirm('请再次确认：恢复默认参数后无法撤销。')) return;
  await apiCall('reset_global_params_to_default');
  await renderGlobalParams();
  showToast('默认参数已恢复');
}

var _extraInitDone = false;

function initExtraTab() {
  if (_extraInitDone) return;
  _extraInitDone = true;

  var grid = document.getElementById('extraGrid');
  if (!grid) return;

  grid.addEventListener('click', function (e) {
    var card = e.target.closest('.extra-card');
    if (!card) return;
    var action = card.dataset.action;
    if (!action) return;
    if (action === 'check-env') handleCheckEnv();
    else if (action === 'sys-info') handleSysInfo();
    else if (action === 'driver-mgmt') handleDriverMgmt();
    else if (action === 'restart-admin') handleRestartAdmin();
    else if (action === 'features') handleFeatures();
    else if (action === 'shortcuts') handleShortcuts();
    else if (action === 'copyright') handleCopyright();
  });

  var btnCheck = document.getElementById('btnCheckDriver');
  var btnInstall = document.getElementById('btnInstallDriver');
  var btnUninstall = document.getElementById('btnUninstallDriver');
  if (btnCheck) btnCheck.addEventListener('click', refreshDriverStatus);
  if (btnInstall) btnInstall.addEventListener('click', installDriver);
  if (btnUninstall) btnUninstall.addEventListener('click', uninstallDriver);
}

function showPanel(panelId) {
  var result = document.getElementById('extraResult');
  var driver = document.getElementById('driverPanel');
  if (result) result.style.display = 'none';
  if (driver) driver.style.display = 'none';
  if (panelId) {
    var el = document.getElementById(panelId);
    if (el) el.style.display = 'block';
  }
}

function esc(str) {
  if (!str) return '';
  str = String(str);
  str = str.replace(/&/g, '&amp;');
  str = str.replace(/</g, '&lt;');
  str = str.replace(/>/g, '&gt;');
  str = str.replace(/"/g, '&quot;');
  return str;
}

function buildTable(rows) {
  var html = '<table><tbody>';
  for (var i = 0; i < rows.length; i++) {
    html += '<tr><th>' + esc(rows[i][0]) + '</th><td>' + rows[i][1] + '</td></tr>';
  }
  html += '</tbody></table>';
  return html;
}

async function handleCheckEnv() {
  showPanel('extraResult');
  var result = document.getElementById('extraResult');
  result.innerHTML = '<p><span class="loading-spinner"></span>正在检查环境...</p>';
  try {
    var data = await apiCall('check_environment');
    if (!data || !data.ok) {
      result.innerHTML = '<p class="fail">检查失败: ' + (data && data.message || '未知错误') + '</p>';
      return;
    }
    var r = data.results;
    var pkgStatus = r.packages.missing.length === 0
      ? '<span class="ok">已全部安装</span> (' + r.packages.installed.length + ' 个)'
      : '<span class="fail">缺失: ' + r.packages.missing.join(', ') + '</span>';
    var dxgiStatus = r.dxgi.available
      ? '<span class="ok">可用</span>'
      : '<span class="warn">不可用</span>' + (r.dxgi.warning ? ' (' + esc(r.dxgi.warning) + ')' : '');
    var drvStatus = r.interception_driver.loaded
      ? '<span class="ok">已加载</span>'
      : '<span class="fail">未加载</span>' + (r.interception_driver.warning ? ' (' + esc(r.interception_driver.warning) + ')' : '');
    var dllStatus = r.interception_dll.exists
      ? '<span class="ok">已找到</span> (' + esc(r.interception_dll.path) + ')'
      : '<span class="fail">未找到</span>' + (r.interception_dll.path ? ' (期望路径: ' + esc(r.interception_dll.path) + ')' : '');
    result.innerHTML =
      '<h3>环境检查结果</h3>' +
      buildTable([
        ['Python 版本', '<span class="' + (r.python.ok ? 'ok' : 'fail') + '">' + esc(r.python.version) + '</span>' + (r.python.warning ? ' <span class="warn">' + esc(r.python.warning) + '</span>' : '')],
        ['Python 路径', esc(r.python.executable)],
        ['操作系统', esc(r.system.os)],
        ['架构', esc(r.system.arch) + ' · ' + esc(r.system.machine)],
        ['管理员权限', r.system.is_admin ? '<span class="ok">是</span>' : '<span class="warn">否</span>'],
        ['Interception DLL', dllStatus],
        ['Interception 驱动', drvStatus],
        ['DXGI 截图', dxgiStatus],
        ['依赖包', pkgStatus],
      ]);
    if (r.packages.missing.length > 0) {
      result.innerHTML +=
        '<div class="extra-actions" style="margin-top:12px">' +
        '<button id="btnInstallMissing" class="primary">一键安装缺失依赖</button>' +
        '</div>';
      var btnInstallMissing = document.getElementById('btnInstallMissing');
      if (btnInstallMissing) {
        btnInstallMissing.addEventListener('click', handleInstallMissing);
      }
    }
  } catch (e) {
    result.innerHTML = '<p class="fail">检查出错: ' + esc(e.message || String(e)) + '</p>';
  }
}

async function handleInstallMissing() {
  var btn = document.getElementById('btnInstallMissing');
  if (btn) { btn.disabled = true; btn.textContent = '正在安装...'; }
  try {
    var data = await apiCall('install_missing_packages');
    if (data && data.ok) {
      showToast(data.message || '安装完成');
      handleCheckEnv();
    } else {
      showToast('安装失败: ' + (data && data.message || '未知错误'));
      if (btn) { btn.disabled = false; btn.textContent = '一键安装缺失依赖'; }
    }
  } catch (e) {
    showToast('安装出错: ' + (e.message || String(e)));
    if (btn) { btn.disabled = false; btn.textContent = '一键安装缺失依赖'; }
  }
}

async function handleSysInfo() {
  showPanel('extraResult');
  var result = document.getElementById('extraResult');
  result.innerHTML = '<p><span class="loading-spinner"></span>正在获取系统信息...</p>';
  try {
    var data = await apiCall('get_system_info');
    if (!data || !data.ok) {
      result.innerHTML = '<p class="fail">获取失败: ' + (data && data.message || '未知错误') + '</p>';
      return;
    }
    var monitorRows = (data.monitors || []).map(function (m) {
      return (m.is_primary ? '★ ' : '  ') + m.name + ' (' + m.width + 'x' + m.height + ')';
    }).join('<br>') || '无';
    result.innerHTML =
      '<h3>系统信息</h3>' +
      buildTable([
        ['操作系统', esc(data.os)],
        ['架构', esc(data.arch)],
        ['Python 版本', esc(data.python)],
        ['Python 路径', esc(data.executable)],
        ['程序目录', esc(data.app_dir)],
        ['显示器', monitorRows],
      ]);
  } catch (e) {
    result.innerHTML = '<p class="fail">获取出错: ' + esc(e.message || String(e)) + '</p>';
  }
}

async function handleDriverMgmt() {
  showPanel('driverPanel');
  await refreshDriverStatus();
}

async function refreshDriverStatus() {
  var status = document.getElementById('driverStatus');
  status.innerHTML = '<p><span class="loading-spinner"></span>正在检查驱动状态...</p>';
  try {
    var data = await apiCall('check_environment');
    if (!data || !data.ok) {
      status.innerHTML = '<p class="fail">检查失败</p>';
      return;
    }
    var r = data.results;
    var dllOk = r.interception_dll.exists;
    var drvOk = r.interception_driver.loaded;
    status.innerHTML = '<table>' +
      '<tr><th>Interception DLL</th><td>' + (dllOk ? '<span class="ok">已找到</span>' : '<span class="fail">未找到</span>') + '</td></tr>' +
      '<tr><th>DLL 路径</th><td>' + esc(r.interception_dll.path || '无') + '</td></tr>' +
      '<tr><th>驱动状态</th><td>' + (drvOk ? '<span class="ok">已加载</span>' : '<span class="fail">未加载</span>' + (r.interception_driver.warning ? ' (' + esc(r.interception_driver.warning) + ')' : '')) + '</td></tr>' +
      '<tr><th>管理员权限</th><td>' + (r.system.is_admin ? '<span class="ok">是</span>' : '<span class="warn">否（安装驱动需管理员权限）</span>') + '</td></tr>' +
      '</table>';
    if (!dllOk && !drvOk) {
      status.innerHTML += '<p class="warn" style="margin-top:8px">驱动不可用，请先安装 Interception 驱动（需管理员权限）</p>';
    }
  } catch (e) {
    status.innerHTML = '<p class="fail">检查出错: ' + esc(e.message || String(e)) + '</p>';
  }
}

async function installDriver() {
  if (!confirm('安装 Interception 驱动需要管理员权限，点击确认后将弹出 UAC 窗口。')) return;
  try {
    var data = await apiCall('install_interception_driver');
    if (data && data.ok) showToast(data.message || '已请求安装');
    else showToast('安装失败: ' + (data && data.message || '未知错误'));
  } catch (e) {
    showToast('安装出错: ' + (e.message || String(e)));
  }
}

async function uninstallDriver() {
  if (!confirm('卸载 Interception 驱动需要管理员权限，确认后将弹出 UAC 窗口。')) return;
  try {
    var data = await apiCall('uninstall_interception_driver');
    if (data && data.ok) showToast(data.message || '已请求卸载');
    else showToast('卸载失败: ' + (data && data.message || '未知错误'));
  } catch (e) {
    showToast('卸载出错: ' + (e.message || String(e)));
  }
}

async function handleRestartAdmin() {
  showPanel('extraResult');
  var result = document.getElementById('extraResult');
  result.innerHTML =
    '<h3>管理员重启</h3>' +
    '<p>将以管理员权限重新启动程序。当前窗口会自动关闭。</p>' +
    '<button id="btnRestartAdmin" class="primary" style="margin-top:8px">确认重启为管理员</button>';
  var btn = document.getElementById('btnRestartAdmin');
  if (btn) {
    btn.addEventListener('click', async function () {
      try {
        var data = await apiCall('restart_as_admin');
        if (data && data.ok) showToast(data.message || '正在重启...');
        else showToast('重启失败: ' + (data && data.message || '未知错误'));
      } catch (e) {
        showToast('重启出错: ' + (e.message || String(e)));
      }
    });
  }
}

async function handleFeatures() {
  showPanel('extraResult');
  var result = document.getElementById('extraResult');
  result.innerHTML = '<p><span class="loading-spinner"></span>加载功能列表...</p>';
  try {
    var data = await apiCall('get_feature_list');
    if (!data || !data.ok) {
      result.innerHTML = '<p class="fail">加载失败</p>';
      return;
    }
    var items = (data.features || []).map(function (f) {
      return '<tr><td><i class="' + esc(f.icon) + '" style="color:var(--accent);margin-right:6px"></i>' + esc(f.name) + '</td><td>' + esc(f.desc) + '</td></tr>';
    }).join('');
    result.innerHTML = '<h3>功能一览</h3><table><thead><tr><th>模块</th><th>说明</th></tr></thead><tbody>' + items + '</tbody></table>';
  } catch (e) {
    result.innerHTML = '<p class="fail">加载出错: ' + esc(e.message || String(e)) + '</p>';
  }
}

function handleShortcuts() {
  showPanel('extraResult');
  var result = document.getElementById('extraResult');
  result.innerHTML =
    '<h3>快捷键速查</h3>' +
    '<h4 style="margin:12px 0 6px;color:var(--accent)">全局控制</h4>' +
    '<table><thead><tr><th>快捷键</th><th>功能</th><th>说明</th></tr></thead><tbody>' +
    '<tr><td><kbd>F8</kbd></td><td>全局暂停/恢复</td><td>暂停或恢复所有运行中的宏</td></tr>' +
    '<tr><td><kbd>ESC</kbd></td><td>停止全部宏</td><td>立即停止所有运行中的宏</td></tr>' +
    '</tbody></table>' +
    '<p class="hint" style="margin-top:12px">快捷键可在「全局参数」面板中自定义配置。</p>';
}

async function handleCopyright() {
  showPanel('extraResult');
  var result = document.getElementById('extraResult');
  var versionStr = '3.1.0';
  try {
    var hdata = await apiCall('health');
    if (hdata && hdata.version) versionStr = hdata.version;
  } catch (_) {}
  result.innerHTML =
    '<h3>软件著作</h3>' +
    '<table>' +
    '<tr><th>项目名称</th><td>Macro Forge Lite</td></tr>' +
    '<tr><th>版本</th><td>v' + esc(versionStr) + '</td></tr>' +
    '<tr><th>用途</th><td>高精度宏执行器</td></tr>' +
    '<tr><th>核心技术</th><td>Python · pywebview · Interception 驱动 · DXGI 截图</td></tr>' +
    '<tr><th>许可</th><td>保留所有权利</td></tr>' +
    '</table>' +
    '<p class="hint" style="margin-top:12px">Interception 驱动为第三方开源组件，版权归其作者所有。</p>';
}

async function switchTab(tabName) {
  state.currentTab = tabName;
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
  if (tabName === 'editor') {
    await refreshMacros().catch(() => {});
    renderEditorMacroBrowser();
    renderActionList();
  }
  if (tabName === 'extra') {
    initExtraTab();
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

function bindMacroActions() {
  q('#btnRefreshMacros').addEventListener('click', () => {
    refreshMacros()
      .then(() => showToast('宏列表已刷新'))
      .catch((err) => showToast(err.message));
  });

  q('#macroFilter').addEventListener('input', () => {
    refreshMacros().catch((err) => showToast(err.message));
  });

  q('#btnMacroRandomToggle').addEventListener('click', () => {
    state.runtimeProfile.random_enabled = !state.runtimeProfile.random_enabled;
    syncRuntimeProfileUI();
  });

  q('#btnLowCpuModeToggle').addEventListener('click', () => {
    state.runtimeProfile.low_cpu_enabled = !state.runtimeProfile.low_cpu_enabled;
    syncRuntimeProfileUI();
  });

  q('#btnTimePeriodToggle').addEventListener('click', () => {
    state.runtimeProfile.low_cpu_time_period = !state.runtimeProfile.low_cpu_time_period;
    syncRuntimeProfileUI();
  });

  q('#btnApplyRuntimeProfile').addEventListener('click', () => {
    applyMacroRuntimeProfile().catch((err) => showToast(err.message));
  });

  q('#btnCreateMacro').addEventListener('click', async () => {
    const name = window.prompt('输入新宏文件名', '新建宏.json');
    if (!name) return;
    const res = await apiCall('create_macro', '宏/录制宏', name);
    showToast(`已创建: ${res.path}`);
    await refreshMacros();
  });

  q('#btnDeleteMacro').addEventListener('click', async () => {
    if (!state.selectedMacro) return showToast('请先选择一个宏文件');
    if (!window.confirm(`确认删除 ${state.selectedMacro} ?`)) return;
    await apiCall('delete_macro', state.selectedMacro);
    showToast('已删除宏文件');
    state.selectedMacro = null;
    await refreshMacros();
    await refreshBindings();
  });

  q('#btnCaptureKey').addEventListener('click', async () => {
    showToast('请在 8 秒内按下键盘或鼠标侧键');
    const res = await apiCall('capture_next_binding', 8);
    if (res.canceled) {
      showToast('采集超时，未捕获输入');
      return;
    }
    q('#bindTrigger').value = res.key || '';
    showToast(`已捕获: ${res.key}`);
  });

  q('#btnBindMacro').addEventListener('click', async () => {
    const macroPath = state.selectedMacro || q('#selectedMacroPath').value.trim();
    if (!macroPath) return showToast('请先选择宏文件');
    const trigger = q('#bindTrigger').value.trim();
    const repeat = parseNumber(q('#bindRepeat').value, 1);
    const mode = q('#bindMode').value;
    if (!trigger) return showToast('请输入触发键');
    const ret = await apiCall('bind_macro', trigger, macroPath, repeat, mode);
    if (ret.already_bound) {
      showToast(`已存在同名绑定: ${trigger}`);
    } else if (ret.replaced_existing && !ret.multi_bind_enabled) {
      showToast(`已覆盖触发键原绑定并重新绑定: ${trigger}`);
    } else if (ret.append) {
      showToast(`已追加到触发键: ${trigger}`);
    } else {
      showToast(`绑定成功: ${trigger}`);
    }
    await refreshBindings();
  });

  q('#btnRunNow').addEventListener('click', async () => {
    const trigger = q('#bindTrigger').value.trim();
    if (!trigger) return showToast('请先输入触发键');
    await apiCall('trigger_macro', trigger);
    showToast(`已触发 ${trigger}`);
    refreshBindings();
  });

  q('#btnStartListeners').addEventListener('click', async () => {
    const ret = await apiCall('toggle_global_listeners');
    q('#btnStartListeners').textContent = ret.running ? '关闭全局宏监听' : '启动全局宏监听';
    q('#btnStartListeners').classList.toggle('active-glow', !!ret.running);
    showToast(ret.running ? '全局监听已启动' : '全局监听已关闭');
  });

  q('#btnGlobalPause').addEventListener('click', async () => {
    const ret = await apiCall('toggle_global_pause');
    q('#btnGlobalPause').textContent = ret.paused ? '关闭全局暂停' : '开启全局暂停';
    q('#btnGlobalPause').classList.toggle('active-glow', !!ret.paused);
    showToast(ret.paused ? '全局暂停已开启' : '全局暂停已解除');
    await refreshSnapshot();
  });

  q('#btnStopAll').addEventListener('click', async () => {
    await apiCall('stop_all_macros');
    showToast('已停止全部宏');
    await refreshBindings();
  });

  q('#btnImportFolder').addEventListener('click', async () => {
    const pick = await apiCall('choose_import_folder');
    if (pick.canceled) return;
    const ret = await apiCall('import_macros_from_folder', pick.path);
    showToast(`已导入 ${ret.count} 个宏文件`);
    await refreshMacros();
  });
}

function bindParamsActions() {
  q('#btnReloadParams').addEventListener('click', () => {
    renderGlobalParams()
      .then(() => showToast('参数已刷新'))
      .catch((err) => showToast(err.message));
  });

  q('#btnSaveParamsTop').addEventListener('click', () => {
    saveGlobalParams().catch((err) => showToast(err.message));
  });

  q('#btnSaveParamsBottom').addEventListener('click', () => {
    saveGlobalParams().catch((err) => showToast(err.message));
  });

  q('#btnImportParams').addEventListener('click', () => {
    importGlobalParams().catch((err) => showToast(err.message));
  });

  q('#btnExportParams').addEventListener('click', () => {
    exportGlobalParams().catch((err) => showToast(err.message));
  });

  q('#btnResetParams').addEventListener('click', () => {
    resetGlobalParamsToDefault().catch((err) => showToast(err.message));
  });

  q('#btnToggleDebugParams').addEventListener('click', () => {
    state.showDebugParams = !state.showDebugParams;
    q('#btnToggleDebugParams').textContent = `显示未开放参数: ${state.showDebugParams ? '开' : '关'}`;
    renderGlobalParams().catch((err) => showToast(err.message));
  });
}

function bindConsoleActions() {
  q('#btnClearConsole').addEventListener('click', async () => { await clearConsole(); });
  q('#btnPopoutConsole').addEventListener('click', () => { popoutConsole(); });
}

function bindEditorActions() {
  q('#btnRefreshEditorMacroBrowser').addEventListener('click', async () => {
    await refreshMacros();
    showToast('编辑区宏文件夹已刷新');
  });

  q('#btnBatchComment')?.addEventListener('click', () => {
    state.batchCommentMode = !state.batchCommentMode;
    if (state.batchCommentMode) {
      state.inlineEditingPathKey = null;
      showToast('批量注释模式已开启：点击动作注释，点击可恢复注释可恢复动作');
    } else {
      showToast('批量注释模式已关闭');
    }
    refreshBatchCommentButton();
    renderActionList();
  });

  q('#btnEditorCreate').addEventListener('click', async () => {
    const folder = q('#editorFolder').value.trim() || '宏/录制宏';
    const fileName = q('#editorNewName').value.trim() || '新建宏.json';
    const ret = await apiCall('create_macro', folder, fileName);
    state.selectedMacro = ret.path;
    state.editorRows = [];
    state.expandedLoopPathKeys = new Set();
    state.inlineEditingPathKey = null;
    setSelectedLine(null, 'action');
    ensureActionFormDefaultsForType(q('#actionType').value || 'kd', true);
    renderActionList();
    await refreshMacros();
    showToast(`已创建: ${ret.path}`);
  });

  q('#btnEditorRename').addEventListener('click', async () => {
    if (!state.selectedMacro) return showToast('请先选择一个宏');
    const newName = q('#editorNewName').value.trim();
    if (!newName) return showToast('请输入新文件名');
    const ret = await apiCall('rename_macro', state.selectedMacro, newName);
    state.selectedMacro = ret.path;
    q('#selectedMacroPath').value = ret.path;
    showToast('重命名完成');
    await refreshMacros();
    await refreshBindings();
  });

  q('#actionType').addEventListener('change', () => {
    switchActionType(q('#actionType').value);
  });

  q('#btnInsertBelow').addEventListener('click', () => {
    try {
      const row = buildActionFromInputs();
      const target = resolveInsertTargetAfterSelection();
      insertActionAtTarget(row, target);
      renderActionList();
    } catch (err) { showToast(err.message); }
  });

  q('#btnAppendAction').addEventListener('click', () => {
    try {
      const row = buildActionFromInputs();
      insertActionAtTarget(row, { type: 'root', index: state.editorRows.length });
      renderActionList();
    } catch (err) { showToast(err.message); }
  });

  q('#btnUpdateAction').addEventListener('click', () => {
    try {
      updateCurrentActionFromEditor();
      state.inlineEditingPathKey = pathKey(state.selectedActionPath);
    } catch (err) { showToast(err.message); }
  });

  q('#btnDeleteAction').addEventListener('click', () => {
    if (!Array.isArray(state.selectedActionPath) || !state.selectedActionPath.length) { showToast('请先选择一个动作'); return; }
    const info = getActionAndContainerByPath(state.selectedActionPath);
    if (!info) { showToast('选中动作已失效，请重新选择'); return; }
    const removedPath = [...state.selectedActionPath];
    info.container.splice(info.index, 1);
    state.inlineEditingPathKey = null;
    clearExpandedLoopKeysByPrefix(removedPath);
    if (info.container.length > 0) {
      const nextIndex = Math.min(info.index, info.container.length - 1);
      const nextPath = [...removedPath.slice(0, -1), nextIndex];
      setSelectedLine(nextPath, 'action');
      const selected = getActionAtPath(nextPath);
      if (selected) fillActionEditorByAction(selected);
    } else if (!removedPath.slice(0, -1).length) {
      setSelectedLine(null, 'action');
      ensureActionFormDefaultsForType(q('#actionType').value || 'kd', true);
    } else {
      setSelectedLine(removedPath.slice(0, -1), 'action');
      const selected = getActionAtPath(removedPath.slice(0, -1));
      if (selected) fillActionEditorByAction(selected);
    }
    renderActionList();
  });

  q('#btnSaveEditor').addEventListener('click', async () => {
    if (!state.selectedMacro) return showToast('请先在宏列表里选择文件');
    await apiCall('save_macro', state.selectedMacro, state.editorRows);
    showToast('宏文件已保存');
    await refreshMacros();
  });

  q('#btnReloadEditor').addEventListener('click', async () => {
    if (!state.selectedMacro) return showToast('请先选择宏');
    await loadMacroToEditor(state.selectedMacro);
    showToast('已重新加载');
  });

  q('#btnEditorRecord').addEventListener('click', () => {
    toggleEditorRecording().catch((err) => showToast(err.message));
  });

  const actionList = q('#actionList');
  if (actionList) {
    actionList.addEventListener('dragover', (e) => { e.preventDefault(); });
    actionList.addEventListener('drop', (e) => {
      const macroPath = e.dataTransfer.getData('text/macro-path') || e.dataTransfer.getData('text/plain');
      e.preventDefault();
      if (macroPath && macroPath.toLowerCase().endsWith('.json')) {
        insertActionAtTarget(['import', macroPath], { type: 'root', index: state.editorRows.length });
        renderActionList();
        showToast(`已追加 import: ${macroPath}`);
        return;
      }
      if (Array.isArray(state.draggedActionPath)) {
        const moved = moveActionToTarget(state.draggedActionPath, { type: 'root', index: state.editorRows.length });
        if (moved) renderActionList();
      }
      state.draggedActionPath = null;
    });
  }

  document.addEventListener('click', (e) => {
    if (!state.inlineEditingPathKey) return;
    const target = e.target;
    if (!(target instanceof Element)) return;
    const editingRow = q(`#actionList li[data-line-key="${state.inlineEditingPathKey}"][data-line-kind="action"]`);
    if (editingRow && editingRow.contains(target)) return;
    const editingPanel = q(`#actionList li[data-inline-editor-for="${state.inlineEditingPathKey}"]`);
    if (editingPanel && editingPanel.contains(target)) return;
    if (target.closest('#actionType') || target.closest('#actionArg1') || target.closest('#actionArg2') || target.closest('#btnUpdateAction') || target.closest('#btnInsertBelow') || target.closest('#btnAppendAction') || target.closest('#btnDeleteAction')) return;
    const editingPath = keyToPath(state.inlineEditingPathKey);
    if (editingPath && editingPath.length) { setSelectedLine(editingPath, 'action'); updateCurrentActionFromEditor({ silent: true }); }
    state.inlineEditingPathKey = null;
    renderActionList();
  }, true);
}

function startPolling() {
  if (state.pollTimerId) return;
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

async function bootstrap() {
  if (state.bootstrapDone) return;
  state.bootstrapDone = true;

  try { bindTabs(); } catch(e) { console.error('bindTabs error:', e); }
  try { bindTopbarToggle(); } catch(e) { console.error('bindTopbarToggle error:', e); }
  try { bindParamsActions(); } catch(e) { console.error('bindParamsActions error:', e); }
  try { bindMacroActions(); } catch(e) { console.error('bindMacroActions error:', e); }
  try { bindEditorActions(); } catch(e) { console.error('bindEditorActions error:', e); }
  try { bindConsoleActions(); } catch(e) { console.error('bindConsoleActions error:', e); }

  await waitForApi();

  try {
    await switchTab('macro');
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
