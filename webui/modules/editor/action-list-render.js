import { state } from '../core/state.js';
import { q, showToast } from '../core/dom.js';
import { pathKey, isLoopAction, formatActionLabel, keyToPath } from './action-model.js';
import { getActionAtPath, getParentInsertTarget, setSelectedLine, getActionAndContainerByPath, clearExpandedLoopKeysByPrefix, insertActionAtTarget, moveActionToTarget } from './action-ops.js';
import { fillActionEditorByAction, buildActionFromInputs, ensureActionFormDefaultsForType } from './action-form.js';
import { toggleCommentForPath } from './comment-ops.js';
import { startInlineEdit, appendInlineEditorRow } from './inline-editor.js';

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

  renderActionList();
  if (!silent) showToast('当前动作已修改');
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
      startInlineEdit(line.path, renderActionList);
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
      const moved = moveActionToTarget(state.draggedActionPath, target, showToast);
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
      appendInlineEditorRow(list, line, lineKey, {
        toggleCommentForPath,
        renderActionList,
        updateCurrentActionFromEditor,
      });
    }
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
