import { state } from '../core/state.js';
import { q, showToast } from '../core/dom.js';
import { pathKey, isLoopAction, formatActionLabel, keyToPath, cloneAction } from './action-model.js';
import { getActionAtPath, getParentInsertTarget, setSelectedLine, getActionAndContainerByPath, clearExpandedLoopKeysByPrefix, insertActionAtTarget, moveActionToTarget } from './action-ops.js';
import { fillActionEditorByAction, buildActionFromInputs, ensureActionFormDefaultsForType } from './action-form.js';
import { toggleCommentForPath } from './comment-ops.js';
import { startInlineEdit, appendInlineEditorRow } from './inline-editor.js';

const lineDataMap = new Map();
let eventsInitialized = false;
let rafId = 0;

// 展开 import 动作：将 import 替换为子宏的完整动作序列
function expandImportAction(path, expandedActions) {
  const found = getActionAndContainerByPath(path);
  if (!found) return;
  const { container, index } = found;
  // 删除原 import 动作
  container.splice(index, 1);
  // 在该位置插入展开后的动作序列
  expandedActions.forEach((action, i) => {
    container.splice(index + i, 0, cloneAction(action));
  });
  // 选中新插入的第一个动作
  setSelectedLine([index], 'action');
  showToast(`已展开 ${expandedActions.length - 2} 个动作`);
}

export function buildActionRenderLines(actions, parentPath = [], depth = 0, lines = []) {
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

  scheduleRender();
  if (!silent) showToast('当前动作已修改');
}

export function scheduleRender() {
  if (rafId) return;
  rafId = requestAnimationFrame(() => {
    rafId = 0;
    renderActionList();
  });
}

export function selectLineVisual() {
  const list = q('#actionList');
  if (!list) return;

  const prev = list.querySelector('li.active');
  if (prev) prev.classList.remove('active');

  if (Array.isArray(state.selectedActionPath) && state.selectedActionPath.length) {
    const key = pathKey(state.selectedActionPath);
    const next = list.querySelector(`li[data-line-key="${key}"][data-line-kind="${state.selectedLineKind}"]`);
    if (next) next.classList.add('active');
  }
}

export function renderActionList() {
  if (rafId) {
    cancelAnimationFrame(rafId);
    rafId = 0;
  }

  const list = q('#actionList');
  list.innerHTML = '';
  lineDataMap.clear();

  const lines = buildActionRenderLines(state.editorRows, [], 0, []);
  const frag = document.createDocumentFragment();

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

    lineDataMap.set(`${lineKey}:${line.kind}`, line);

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
    frag.appendChild(li);

    if (!state.batchCommentMode && line.kind === 'action' && state.inlineEditingPathKey === lineKey) {
      appendInlineEditorRow(frag, line, lineKey, {
        toggleCommentForPath,
        renderActionList,
        updateCurrentActionFromEditor,
        expandImportAction,
      });
    }
  });

  list.appendChild(frag);
}

function getLineDataFromLi(li) {
  if (!li || !li.dataset.lineKey) return null;
  return lineDataMap.get(`${li.dataset.lineKey}:${li.dataset.lineKind}`) || null;
}

export function initActionListEvents() {
  if (eventsInitialized) return;
  const list = q('#actionList');
  if (!list) return;
  eventsInitialized = true;

  list.addEventListener('click', (e) => {
    const toggle = e.target.closest('.loop-toggle');
    if (toggle) {
      const li = toggle.closest('li');
      const lineData = getLineDataFromLi(li);
      if (!lineData) return;
      const key = pathKey(lineData.path);
      if (state.expandedLoopPathKeys.has(key)) {
        state.expandedLoopPathKeys.delete(key);
      } else {
        state.expandedLoopPathKeys.add(key);
      }
      renderActionList();
      return;
    }

    const li = e.target.closest('li');
    if (!li || li.classList.contains('action-inline-editor')) return;
    const lineData = getLineDataFromLi(li);
    if (!lineData) return;

    if (state.batchCommentMode && lineData.kind === 'action') {
      state.inlineEditingPathKey = null;
      const ok = toggleCommentForPath(lineData.path, { silent: false });
      if (ok) renderActionList();
      return;
    }

    setSelectedLine(lineData.path, lineData.kind);
    const selected = getActionAtPath(lineData.path);
    if (selected) fillActionEditorByAction(selected);
    selectLineVisual();
  });

  list.addEventListener('dblclick', (e) => {
    if (state.batchCommentMode) return;
    if (e.target.closest('.loop-toggle')) return;

    const li = e.target.closest('li');
    if (!li || li.classList.contains('action-inline-editor')) return;
    const lineData = getLineDataFromLi(li);
    if (!lineData || lineData.kind !== 'action') return;

    startInlineEdit(lineData.path, renderActionList);
  });

  list.addEventListener('dragstart', (e) => {
    const li = e.target.closest('li');
    const lineData = getLineDataFromLi(li);
    if (!lineData) return;

    state.draggedActionPath = [...lineData.path];
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/action-path', JSON.stringify(lineData.path));
  });

  list.addEventListener('dragend', (e) => {
    const li = e.target.closest('li');
    if (li) li.classList.remove('drag-over');
    state.draggedActionPath = null;
  });

  list.addEventListener('dragover', (e) => {
    e.preventDefault();
    const li = e.target.closest('li');
    if (li) li.classList.add('drag-over');
  });

  list.addEventListener('dragleave', (e) => {
    const li = e.target.closest('li');
    if (li) li.classList.remove('drag-over');
  });

  list.addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();

    const li = e.target.closest('li');
    const lineData = getLineDataFromLi(li);

    if (lineData) {
      li.classList.remove('drag-over');
      const target = getDropTargetFromLine(lineData);
      const macroPath = e.dataTransfer.getData('text/macro-path') || e.dataTransfer.getData('text/plain');
      if (macroPath && macroPath.toLowerCase().endsWith('.json')) {
        insertActionAtTarget(['import', macroPath], target);
        renderActionList();
        showToast(`已插入 import: ${macroPath}`);
        return;
      }

      if (Array.isArray(state.draggedActionPath)) {
        const moved = moveActionToTarget(state.draggedActionPath, target, showToast);
        if (moved) renderActionList();
      }

      state.draggedActionPath = null;
      return;
    }

    const macroPath = e.dataTransfer.getData('text/macro-path') || e.dataTransfer.getData('text/plain');
    if (macroPath && macroPath.toLowerCase().endsWith('.json')) {
      insertActionAtTarget(['import', macroPath], { type: 'root', index: state.editorRows.length });
      renderActionList();
      showToast(`已追加 import: ${macroPath}`);
      return;
    }

    if (Array.isArray(state.draggedActionPath)) {
      const moved = moveActionToTarget(state.draggedActionPath, { type: 'root', index: state.editorRows.length }, showToast);
      if (moved) renderActionList();
    }

    state.draggedActionPath = null;
  });
}

export function refreshBatchCommentButton() {
  const btn = q('#btnBatchComment');
  const list = q('#actionList');
  if (list) list.classList.toggle('batch-comment-mode', state.batchCommentMode);
  if (!btn) return;
  btn.textContent = `批量注释: ${state.batchCommentMode ? '开' : '关'}`;
  btn.classList.toggle('active', state.batchCommentMode);
}

export { updateCurrentActionFromEditor };
