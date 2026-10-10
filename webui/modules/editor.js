import { state } from './core/state.js';
import { q, qa, showToast } from './core/dom.js';
import { apiCall } from './core/api.js';
import { renderMacroTreeList } from './macro-tree.js';
import {
  ACTION_FORM_DEFAULTS,
  ACTION_FORM_UI,
  RECOVERABLE_NOTE_PREFIX,
} from './core/constants.js';

function parseNumber(text, fallback = 0) {
  const n = Number(text);
  return Number.isFinite(n) ? n : fallback;
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
  } catch (_err) {
    return null;
  }
}

function makeRecoverableNoteFromAction(action) {
  return ['note', `${RECOVERABLE_NOTE_PREFIX}${JSON.stringify(action)}`];
}

function isLoopAction(action) {
  return Array.isArray(action)
    && action.length >= 3
    && String(action[0]).trim().toLowerCase() === 'loop'
    && Array.isArray(action[2]);
}

function normalizeAction(action) {
  if (!Array.isArray(action) || !action.length) {
    return ['wait', 50];
  }

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

  if (cmd === 'wait') {
    return ['wait', Math.max(0, parseNumber(action[1], 50))];
  }

  if (cmd === 'import') {
    return ['import', String(action[1] ?? '').trim()];
  }

  if (cmd === 'note') {
    return ['note', String(action[1] ?? '').trim()];
  }

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
    if (depth === path.length - 1) {
      return { container, index, action: container[index] };
    }

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
  if (!Array.isArray(path) || !path.length) {
    return { type: 'root', index: state.editorRows.length };
  }

  const parentPath = path.slice(0, -1);
  const index = path[path.length - 1] + offset;
  if (!parentPath.length) {
    return { type: 'root', index };
  }

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
    if (key === prefix || key.startsWith(`${prefix}.`)) {
      state.expandedLoopPathKeys.delete(key);
    }
  });
}

function setSelectedLine(path, kind = 'action') {
  state.selectedActionPath = Array.isArray(path) ? [...path] : null;
  state.selectedLineKind = kind;
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

  if (arg2Wrap) {
    arg2Wrap.style.display = ui.showArg2 ? '' : 'none';
  }
  if (arg1Wrap) {
    arg1Wrap.style.gridColumn = ui.showArg2 ? '' : '2 / 4';
  }
  if (row) {
    row.classList.toggle('single-arg', !ui.showArg2);
  }
}

function ensureActionFormDefaultsForType(type, force = false) {
  const defaults = getDefaultForType(type);
  const arg1 = q('#actionArg1');
  const arg2 = q('#actionArg2');
  updateActionFormUiForType(type);
  if (force || !arg1.value.trim()) arg1.value = defaults.arg1;
  if (force || !arg2.value.trim()) arg2.value = defaults.arg2;
}

function fillActionEditorByAction(action) {
  if (!Array.isArray(action) || !action.length) return;
  const type = String(action[0]).trim().toLowerCase();
  q('#actionType').value = type;
  updateActionFormUiForType(type);

  if (type === 'wait') {
    q('#actionArg1').value = String(action[1] ?? 50);
    q('#actionArg2').value = '';
    return;
  }

  if (type === 'view') {
    const vec = Array.isArray(action[1]) ? action[1] : [0, 0];
    q('#actionArg1').value = `${parseNumber(vec[0], 0)},${parseNumber(vec[1], 0)}`;
    q('#actionArg2').value = String(action[2] ?? 50);
    return;
  }

  if (type === 'loop') {
    q('#actionArg1').value = String(Math.max(1, parseNumber(action[1], 1)));
    q('#actionArg2').value = '';
    return;
  }

  if (type === 'import') {
    q('#actionArg1').value = String(action[1] ?? '');
    q('#actionArg2').value = '';
    return;
  }

  if (type === 'note') {
    q('#actionArg1').value = String(action[1] ?? '');
    q('#actionArg2').value = '';
    return;
  }

  if (['kd', 'ku', 'md', 'mu'].includes(type)) {
    q('#actionArg1').value = String(action[1] ?? getDefaultForType(type).arg1);
    q('#actionArg2').value = String(action[2] ?? 50);
    return;
  }

  ensureActionFormDefaultsForType(type, true);
}

function buildActionFromInputs(options = {}) {
  const existingAction = options.existingAction || null;
  const type = q('#actionType').value;
  const arg1 = q('#actionArg1').value.trim();
  const arg2 = q('#actionArg2').value.trim();

  if (type === 'wait') {
    const ms = Math.max(0, parseNumber(arg1 || '50', 50));
    return ['wait', ms];
  }

  if (type === 'view') {
    const [dxText = '0', dyText = '0'] = (arg1 || '0,0').split(',');
    const dx = parseNumber(dxText, 0);
    const dy = parseNumber(dyText, 0);
    const dur = Math.max(1, parseNumber(arg2 || '50', 50));
    return ['view', [dx, dy], dur];
  }

  if (type === 'import') {
    if (!arg1) throw new Error('import 需要子宏路径');
    return ['import', arg1];
  }

  if (type === 'note') {
    if (!arg1) throw new Error('note 注释内容不能为空');
    return ['note', arg1];
  }

  if (type === 'loop') {
    const count = Math.max(1, parseNumber(arg1 || '1', 1));
    const block = isLoopAction(existingAction) ? cloneAction(existingAction[2]) : [];
    return ['loop', count, block];
  }

  if (['kd', 'ku', 'md', 'mu'].includes(type)) {
    const fallbackKey = getDefaultForType(type).arg1;
    const key = arg1 || fallbackKey;
    const delay = Math.max(0, parseNumber(arg2 || '50', 50));
    return [type, key, delay];
  }

  throw new Error('未知动作类型');
}

function insertActionAtTarget(action, target) {
  const container = getContainerForTarget(target);
  if (!Array.isArray(container)) {
    throw new Error('插入目标无效');
  }

  const insertIndex = Math.max(0, Math.min(parseNumber(target.index, container.length), container.length));
  container.splice(insertIndex, 0, cloneAction(action));

  if (target.type === 'root') {
    setSelectedLine([insertIndex], 'action');
  } else {
    setSelectedLine([...target.loopPath, insertIndex], 'action');
    state.expandedLoopPathKeys.add(pathKey(target.loopPath));
  }
}

function moveActionToTarget(sourcePath, target) {
  const source = getActionAndContainerByPath(sourcePath);
  if (!source) return false;

  if (target.type === 'loop' && isPathPrefix(sourcePath, target.loopPath)) {
    showToast('不能将 loop 拖入它自己的循环体');
    return false;
  }

  const targetContainer = getContainerForTarget(target);
  if (!Array.isArray(targetContainer)) return false;

  let targetIndex = Math.max(0, Math.min(parseNumber(target.index, targetContainer.length), targetContainer.length));
  const movingAction = source.action;

  if (source.container === targetContainer && source.index < targetIndex) {
    targetIndex -= 1;
  }
  if (source.container === targetContainer && source.index === targetIndex) {
    return false;
  }

  source.container.splice(source.index, 1);
  targetContainer.splice(targetIndex, 0, movingAction);

  if (target.type === 'root') {
    setSelectedLine([targetIndex], 'action');
  } else {
    setSelectedLine([...target.loopPath, targetIndex], 'action');
    state.expandedLoopPathKeys.add(pathKey(target.loopPath));
  }
  return true;
}

function resolveInsertTargetAfterSelection() {
  if (!Array.isArray(state.selectedActionPath) || !state.selectedActionPath.length) {
    return { type: 'root', index: state.editorRows.length };
  }

  if (state.selectedLineKind === 'loop_end') {
    return getParentInsertTarget(state.selectedActionPath, 1);
  }

  return getParentInsertTarget(state.selectedActionPath, 1);
}

function toggleCommentForPath(path, options = {}) {
  const silent = Boolean(options.silent);
  const shouldKeepInlineEditor = !state.batchCommentMode;
  const info = getActionAndContainerByPath(path);
  if (!info) {
    if (!silent) showToast('动作已失效，请重新选择');
    return false;
  }

  const current = info.action;
  const cmd = String(current[0] ?? '').trim().toLowerCase();

  if (cmd === 'note') {
    const restored = getRecoverableActionFromNoteText(current[1]);
    if (!restored) {
      if (!silent) showToast('该注释不包含可恢复动作');
      return false;
    }
    info.container[info.index] = restored;
    setSelectedLine(path, 'action');
    fillActionEditorByAction(restored);
    state.inlineEditingPathKey = shouldKeepInlineEditor ? pathKey(path) : null;
    if (!silent) showToast('已恢复动作');
    return true;
  }

  const fromLoop = isLoopAction(current);
  info.container[info.index] = makeRecoverableNoteFromAction(current);
  if (fromLoop) {
    clearExpandedLoopKeysByPrefix(path);
  }
  setSelectedLine(path, 'action');
  fillActionEditorByAction(info.container[info.index]);
  state.inlineEditingPathKey = shouldKeepInlineEditor ? pathKey(path) : null;
  if (!silent) showToast('已注释当前动作');
  return true;
}

function updateCurrentActionFromEditor(options = {}) {
  const silent = Boolean(options.silent);
  if (!Array.isArray(state.selectedActionPath) || !state.selectedActionPath.length) {
    if (!silent) showToast('请先在右侧列表中选择一个动作');
    return;
  }

  const info = getActionAndContainerByPath(state.selectedActionPath);
  if (!info) {
    if (!silent) showToast('选中动作已失效，请重新选择');
    return;
  }

  const existing = info.action;
  const fromLoop = isLoopAction(existing);
  const toType = q('#actionType').value;

  if (fromLoop && toType !== 'loop') {
    if (silent) {
      return;
    }
    const ok = window.confirm('当前是 loop 动作，改成其他类型会丢失 loop 内部动作。是否继续？');
    if (!ok) return;
  }

  const next = buildActionFromInputs({ existingAction: existing });
  info.container[info.index] = next;

  if (fromLoop && !isLoopAction(next)) {
    clearExpandedLoopKeysByPrefix(state.selectedActionPath);
  }

  renderActionList();
  if (!silent) showToast('当前动作已修改');
}

function formatActionLabel(action, expanded) {
  const cmd = String(action[0] ?? '').trim().toLowerCase();

  if (cmd === 'wait') {
    return `wait ${parseNumber(action[1], 0)}ms`;
  }
  if (cmd === 'view') {
    const vec = Array.isArray(action[1]) ? action[1] : [0, 0];
    return `view [${parseNumber(vec[0], 0)}, ${parseNumber(vec[1], 0)}] ${Math.max(1, parseNumber(action[2], 50))}ms`;
  }
  if (cmd === 'import') {
    return `import ${String(action[1] ?? '').trim() || '(空路径)'}`;
  }
  if (cmd === 'note') {
    const noteText = String(action[1] ?? '').trim();
    const restored = getRecoverableActionFromNoteText(noteText);
    if (restored) {
      return `// [可恢复] ${formatActionLabel(restored, false)}`;
    }
    return `// ${noteText}`;
  }
  if (cmd === 'loop') {
    const count = Math.max(1, parseNumber(action[1], 1));
    const block = Array.isArray(action[2]) ? action[2] : [];
    return expanded
      ? `loop x${count}（展开，共${block.length} 条）`
      : `loop x${count}（收起，共${block.length} 条）`;
  }
  if (['kd', 'ku', 'md', 'mu'].includes(cmd)) {
    return `${cmd} '${String(action[1] ?? '')}' ${Math.max(0, parseNumber(action[2], 50))}ms`;
  }

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
        if (!block.length) {
          lines.push({ kind: 'loop_empty', path, depth: depth + 1, action });
        } else {
          buildActionRenderLines(block, path, depth + 1, lines);
        }
        lines.push({ kind: 'loop_end', path, depth, action });
      }
      return;
    }

    lines.push({ kind: 'action', path, depth, action, isLoopHead: false, expanded: false });
  });
  return lines;
}

function getDropTargetFromLine(line) {
  if (line.kind === 'loop_end') {
    const loop = getActionAtPath(line.path);
    const block = isLoopAction(loop) ? loop[2] : [];
    return { type: 'loop', loopPath: [...line.path], index: block.length };
  }

  if (line.kind === 'loop_empty') {
    return { type: 'loop', loopPath: [...line.path], index: 0 };
  }

  if (line.kind === 'action' && line.isLoopHead && line.expanded) {
    return { type: 'loop', loopPath: [...line.path], index: 0 };
  }

  return getParentInsertTarget(line.path, 1);
}

function startInlineEdit(path) {
  if (state.batchCommentMode) return;
  const action = getActionAtPath(path);
  if (!action) return;
  setSelectedLine(path, 'action');
  fillActionEditorByAction(action);
  state.inlineEditingPathKey = pathKey(path);
  renderActionList();
}

function getInlineEditorValues(action) {
  const cmd = String(action[0] ?? '').trim().toLowerCase();
  if (cmd === 'view') {
    const vec = Array.isArray(action[1]) ? action[1] : [0, 0];
    return {
      type: cmd,
      arg1: `${parseNumber(vec[0], 0)},${parseNumber(vec[1], 0)}`,
      arg2: String(Math.max(1, parseNumber(action[2], 50))),
    };
  }
  if (cmd === 'wait') {
    return { type: cmd, arg1: String(Math.max(0, parseNumber(action[1], 50))), arg2: '' };
  }
  if (cmd === 'loop') {
    return { type: cmd, arg1: String(Math.max(1, parseNumber(action[1], 1))), arg2: '' };
  }
  if (cmd === 'import' || cmd === 'note') {
    return { type: cmd, arg1: String(action[1] ?? ''), arg2: '' };
  }
  if (['kd', 'ku', 'md', 'mu'].includes(cmd)) {
    return {
      type: cmd,
      arg1: String(action[1] ?? getDefaultForType(cmd).arg1),
      arg2: String(Math.max(0, parseNumber(action[2], 50))),
    };
  }
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

    btnToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const ok = toggleCommentForPath(line.path, { silent: false });
      if (ok) {
        renderActionList();
      }
    });
  }

  body.appendChild(row1);
  body.appendChild(actions);

  const applyToMainForm = () => {
    q('#actionType').value = values.type;
    updateActionFormUiForType(values.type);
    q('#actionArg1').value = arg1Input.value;
    q('#actionArg2').value = arg2Input ? arg2Input.value : '';
    setSelectedLine(line.path, 'action');
  };

  arg1Input.addEventListener('input', () => {
    applyToMainForm();
  });
  if (arg2Input) {
    arg2Input.addEventListener('input', () => {
      applyToMainForm();
    });
  }

  const keepEditing = () => {
    state.inlineEditingPathKey = lineKey;
    setSelectedLine(line.path, 'action');
  };

  arg1Input.addEventListener('focus', keepEditing);
  if (arg2Input) arg2Input.addEventListener('focus', keepEditing);

  btnApply.addEventListener('click', (e) => {
    e.stopPropagation();
    applyToMainForm();
    updateCurrentActionFromEditor({ silent: true });
    state.inlineEditingPathKey = lineKey;
    renderActionList();
  });

  editorLi.addEventListener('click', (e) => {
    e.stopPropagation();
    keepEditing();
  });

  editorLi.appendChild(idxStub);
  editorLi.appendChild(body);
  list.appendChild(editorLi);
}

export function renderActionList() {
  const list = q('#actionList');
  list.innerHTML = '';

  const lines = buildActionRenderLines(state.editorRows, [], 0, []);
  lines.forEach((line, lineIndex) => {
    const li = document.createElement('li');
    const lineKey = pathKey(line.path);
    const active = Array.isArray(state.selectedActionPath)
      && pathKey(state.selectedActionPath) === lineKey
      && state.selectedLineKind === line.kind;

    li.classList.toggle('active', active);
    li.classList.toggle('editing', !state.batchCommentMode && line.kind === 'action' && state.inlineEditingPathKey === lineKey);
    if (line.kind === 'action' && line.isLoopHead) li.classList.add('loop-head');
    if (line.kind === 'loop_end') li.classList.add('loop-end');
    if (line.kind === 'loop_empty') li.classList.add('loop-empty');
    li.dataset.lineKey = lineKey;
    li.dataset.lineKind = line.kind;

    li.draggable = line.kind === 'action' || line.kind === 'loop_end';

    li.addEventListener('click', () => {
      if (state.batchCommentMode && line.kind === 'action') {
        state.inlineEditingPathKey = null;
        const ok = toggleCommentForPath(line.path, { silent: false });
        if (ok) {
          renderActionList();
        }
        return;
      }

      setSelectedLine(line.path, line.kind);
      const selected = getActionAtPath(line.path);
      if (selected) fillActionEditorByAction(selected);
      renderActionList();
    });

    li.addEventListener('dblclick', (e) => {
      if (state.batchCommentMode) return;
      if (line.kind !== 'action') return;
      if (e.target instanceof Element && e.target.closest('.loop-toggle')) {
        return;
      }
      e.stopPropagation();
      startInlineEdit(line.path);
    });

    li.addEventListener('dragstart', (e) => {
      state.draggedActionPath = [...line.path];
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/action-path', JSON.stringify(line.path));
    });

    li.addEventListener('dragend', () => {
      state.draggedActionPath = null;
      li.classList.remove('drag-over');
    });

    li.addEventListener('dragover', (e) => {
      e.preventDefault();
      li.classList.add('drag-over');
    });

    li.addEventListener('dragleave', () => {
      li.classList.remove('drag-over');
    });

    li.addEventListener('drop', (e) => {
      e.preventDefault();
      li.classList.remove('drag-over');

      const target = getDropTargetFromLine(line);
      const macroPath = e.dataTransfer.getData('text/macro-path') || e.dataTransfer.getData('text/plain');
      if (macroPath && macroPath.toLowerCase().endsWith('.json')) {
        insertActionAtTarget(['import', macroPath], target);
        renderActionList();
        showToast(`已插入 import: ${macroPath}`);
        return;
      }

      if (!Array.isArray(state.draggedActionPath)) return;
      const moved = moveActionToTarget(state.draggedActionPath, target);
      if (moved) {
        renderActionList();
      }

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
      toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        const key = pathKey(line.path);
        if (state.expandedLoopPathKeys.has(key)) {
          state.expandedLoopPathKeys.delete(key);
        } else {
          state.expandedLoopPathKeys.add(key);
        }
        renderActionList();
      });
      toggle.addEventListener('dblclick', (e) => {
        e.stopPropagation();
        const key = pathKey(line.path);
        if (state.expandedLoopPathKeys.has(key)) {
          state.expandedLoopPathKeys.delete(key);
        } else {
          state.expandedLoopPathKeys.add(key);
        }
        renderActionList();
      });
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

    if (!state.batchCommentMode && line.kind === 'action' && state.inlineEditingPathKey === lineKey) {
      appendInlineEditorRow(list, line, lineKey);
    }
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

export async function loadMacroToEditor(path) {
  const data = await apiCall('read_macro', path);
  state.editorRows = normalizeMacroRows(data.rows);
  state.expandedLoopPathKeys = new Set();
  state.inlineEditingPathKey = null;

  if (state.editorRows.length) {
    setSelectedLine([0], 'action');
    fillActionEditorByAction(state.editorRows[0]);
  } else {
    setSelectedLine(null, 'action');
    ensureActionFormDefaultsForType(q('#actionType').value || 'kd', true);
  }

  state.selectedMacro = path;
  q('#selectedMacroPath').value = path;
  const { renderMacroList } = await import('./macro-bind.js');
  renderMacroList();
  renderEditorMacroBrowser();
  renderActionList();
}

export function renderEditorMacroBrowser() {
  const list = q('#editorMacroList');
  renderMacroTreeList({
    container: list,
    tree: state.macroTree,
    viewId: 'editor',
    selectedPath: null,
    openedPath: state.selectedMacro,
    onSelect: (path) => {
      loadMacroToEditor(path).catch((err) => showToast(err.message));
    },
  });
}

export function bindEditorActions() {
  state.onSelectMacroForEditor = loadMacroToEditor;
  state.renderEditorMacroBrowser = renderEditorMacroBrowser;
  state.renderRecordMacroBrowser = async () => {};
  state.renderActionList = renderActionList;

  q('#btnRefreshEditorMacroBrowser').addEventListener('click', async () => {
    const { refreshMacros } = await import('./macro-bind.js');
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
    const { refreshMacros } = await import('./macro-bind.js');
    await refreshMacros();
    showToast(`已创建: ${ret.path}`);
  });

  q('#btnEditorRename').addEventListener('click', async () => {
    if (!state.selectedMacro) return showToast('请先选择一个宏');
    const newName = q('#editorRenameName').value.trim();
    if (!newName) return showToast('请输入新文件名');

    const ret = await apiCall('rename_macro', state.selectedMacro, newName);
    state.selectedMacro = ret.path;
    q('#selectedMacroPath').value = ret.path;
    showToast('重命名完成');
    const { refreshMacros, refreshBindings } = await import('./macro-bind.js');
    await refreshMacros();
    await refreshBindings();
  });

  q('#actionType').addEventListener('change', () => {
    ensureActionFormDefaultsForType(q('#actionType').value, true);
  });

  q('#btnInsertBelow').addEventListener('click', () => {
    try {
      const row = buildActionFromInputs();
      const target = resolveInsertTargetAfterSelection();
      insertActionAtTarget(row, target);
      state.inlineEditingPathKey = pathKey(state.selectedActionPath);
      renderActionList();
    } catch (err) {
      showToast(err.message);
    }
  });

  q('#btnAppendAction').addEventListener('click', () => {
    try {
      const row = buildActionFromInputs();
      insertActionAtTarget(row, { type: 'root', index: state.editorRows.length });
      state.inlineEditingPathKey = pathKey(state.selectedActionPath);
      renderActionList();
    } catch (err) {
      showToast(err.message);
    }
  });

  q('#btnUpdateAction').addEventListener('click', () => {
    try {
      updateCurrentActionFromEditor();
      state.inlineEditingPathKey = pathKey(state.selectedActionPath);
    } catch (err) {
      showToast(err.message);
    }
  });

  q('#btnDeleteAction').addEventListener('click', () => {
    if (!Array.isArray(state.selectedActionPath) || !state.selectedActionPath.length) {
      showToast('请先选择一个动作');
      return;
    }

    const info = getActionAndContainerByPath(state.selectedActionPath);
    if (!info) {
      showToast('选中动作已失效，请重新选择');
      return;
    }

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
    const { refreshMacros } = await import('./macro-bind.js');
    await refreshMacros();
  });

  q('#btnReloadEditor').addEventListener('click', async () => {
    if (!state.selectedMacro) return showToast('请先选择宏');
    await loadMacroToEditor(state.selectedMacro);
    showToast('已重新加载');
  });

  const actionList = q('#actionList');
  if (actionList) {
    actionList.addEventListener('dragover', (e) => {
      e.preventDefault();
    });

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
        if (moved) {
          renderActionList();
        }
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

    if (target.closest('#actionType')
      || target.closest('#actionArg1')
      || target.closest('#actionArg2')
      || target.closest('#btnUpdateAction')
      || target.closest('#btnInsertBelow')
      || target.closest('#btnAppendAction')
      || target.closest('#btnDeleteAction')) {
      return;
    }

    const editingPath = keyToPath(state.inlineEditingPathKey);
    if (editingPath && editingPath.length) {
      setSelectedLine(editingPath, 'action');
      updateCurrentActionFromEditor({ silent: true });
    }
    state.inlineEditingPathKey = null;
    renderActionList();
  }, true);
}
