import { state } from '../core/state.js';
import { q, showToast } from '../core/dom.js';
import { pathKey, isLoopAction, isRawRow, formatActionLabel, cloneAction } from './action-model.js';
import { getActionAtPath, getParentInsertTarget, setSelectedLine, getActionAndContainerByPath, getContainerForTarget, clearExpandedLoopKeysByPrefix, insertActionAtTarget, moveActionToTarget } from './action-ops.js';
import { fillActionEditorByAction, buildActionFromInputs, ensureActionFormDefaultsForType } from './action-form.js';
import { toggleCommentForPath } from './comment-ops.js';
import { startInlineEdit, appendInlineEditorRow } from './inline-editor.js';
import { updateBpVisual } from './bp-visual.js';

// 每个列表 DOM 对应的「行数据」映射（行数据含路径与动作引用）
const lineDataByList = new WeakMap();

// 纯函数版渲染行（不依赖视图，loop 一律折叠）——保留供外部复用
export function buildActionRenderLines(actions, parentPath = [], depth = 0, lines = []) {
  (Array.isArray(actions) ? actions : []).forEach((action, index) => {
    const path = [...parentPath, index];
    lines.push({
      kind: 'action',
      path,
      depth,
      action,
      isLoopHead: isLoopAction(action),
      expanded: false,
    });
  });
  return lines;
}

// 展开 import 动作（作用于指定 view）
export function expandImportAction(view, path, expandedActions) {
  const found = getActionAndContainerByPath(view, path);
  if (!found) return;
  const { container, index } = found;
  container.splice(index, 1);
  expandedActions.forEach((action, i) => {
    container.splice(index + i, 0, cloneAction(action));
  });
  setSelectedLine(view, [index], 'action');
  showToast(`已展开 ${Math.max(0, expandedActions.length - 2)} 个动作`);
}

// 按 view 的展开状态生成渲染行
function buildLines(view) {
  const lines = [];
  const walk = (actions, parentPath, depth) => {
    actions.forEach((action, index) => {
      const path = [...parentPath, index];
      if (isLoopAction(action)) {
        const expanded = view.expandedLoopPathKeys.has(pathKey(path));
        lines.push({ kind: 'action', path, depth, action, isLoopHead: true, expanded });
        if (expanded) {
          const block = Array.isArray(action[2]) ? action[2] : [];
          if (!block.length) {
            lines.push({ kind: 'loop_empty', path, depth: depth + 1, action });
          } else {
            walk(block, path, depth + 1);
          }
          lines.push({ kind: 'loop_end', path, depth, action });
        }
        return;
      }
      lines.push({ kind: 'action', path, depth, action, isLoopHead: false, expanded: false });
    });
  };
  walk(Array.isArray(view.rows) ? view.rows : [], [], 0);
  return lines;
}

function getDropTargetFromLine(view, line) {
  if (line.kind === 'loop_end') {
    const loop = getActionAtPath(view, line.path);
    const block = isLoopAction(loop) ? loop[2] : [];
    return { type: 'loop', loopPath: [...line.path], index: block.length };
  }
  if (line.kind === 'loop_empty') {
    return { type: 'loop', loopPath: [...line.path], index: 0 };
  }
  if (line.kind === 'action' && line.isLoopHead && line.expanded) {
    return { type: 'loop', loopPath: [...line.path], index: 0 };
  }
  return getParentInsertTarget(view, line.path, 1);
}

export function updateCurrentActionFromEditor(options = {}) {
  const view = options.view || (typeof state.getFocusedView === 'function' ? state.getFocusedView() : null);
  const silent = Boolean(options.silent);
  if (!view) return;
  if (!Array.isArray(view.selectedActionPath) || !view.selectedActionPath.length) {
    if (!silent) showToast('请先在动作列表中选择一个动作');
    return;
  }

  const info = getActionAndContainerByPath(view, view.selectedActionPath);
  if (!info) {
    if (!silent) showToast('选中动作已失效，请重新选择');
    return;
  }

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

  if (fromLoop && !isLoopAction(next)) {
    clearExpandedLoopKeysByPrefix(view, view.selectedActionPath);
  }

  renderViewList(view);
  if (!silent) showToast('当前动作已修改');
}

export function renderViewList(view) {
  const list = view && view.listEl;
  if (!list) return;

  const scrollTop = list.scrollTop;
  list.innerHTML = '';
  const map = new Map();
  lineDataByList.set(list, map);

  const lines = buildLines(view);
  const frag = document.createDocumentFragment();

  lines.forEach((line, lineIndex) => {
    const li = document.createElement('li');
    const lineKey = pathKey(line.path);
    const active = Array.isArray(view.selectedActionPath)
      && pathKey(view.selectedActionPath) === lineKey
      && view.selectedLineKind === line.kind;

    li.classList.toggle('active', active);
    li.classList.toggle('editing', !state.batchCommentMode && line.kind === 'action' && view.inlineEditingPathKey === lineKey);
    if (line.kind === 'action' && line.isLoopHead) li.classList.add('loop-head');
    if (line.kind === 'loop_end') li.classList.add('loop-end');
    if (line.kind === 'loop_empty') li.classList.add('loop-empty');
    if (line.kind === 'action' && isRawRow(line.action)) li.classList.add('raw-line');
    li.dataset.lineKey = lineKey;
    li.dataset.lineKind = line.kind;
    li.draggable = line.kind === 'action' || line.kind === 'loop_end';

    map.set(`${lineKey}:${line.kind}`, line);

    // 行号即"测试点开关"（仅顶层动作行可设）：
    //   已是测试点 → 数字背景高亮；非测试点 → 保持普通行号外观。
    // 不再单独占用一列按钮，默认也不显示 ○/● 噪声。
    const idxEl = document.createElement('span');
    idxEl.className = 'action-index';
    idxEl.textContent = String(lineIndex + 1);
    if (line.kind === 'action' && line.depth === 0) {
      const on = !!(view.breakpoints && view.breakpoints.has(lineKey));
      idxEl.classList.add('bp-toggle');
      idxEl.classList.toggle('on', on);
      idxEl.title = on
        ? `第 ${lineIndex + 1} 行已是测试点 —— 点击取消`
        : `把第 ${lineIndex + 1} 行设为测试点（可从测试点运行到此）`;
      idxEl.dataset.bpPath = lineKey;
    }

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

    if (!state.batchCommentMode && line.kind === 'action' && view.inlineEditingPathKey === lineKey) {
      appendInlineEditorRow(view, frag, line, lineKey, {
        toggleCommentForPath,
        renderViewList,
        updateCurrentActionFromEditor,
        expandImportAction,
      });
    }
  });

  list.appendChild(frag);
  list.scrollTop = scrollTop;

  if (typeof state.onViewRendered === 'function') state.onViewRendered(view);
}

function lineDataFromLi(list, li) {
  if (!list || !li || !li.dataset.lineKey) return null;
  const map = lineDataByList.get(list);
  if (!map) return null;
  return map.get(`${li.dataset.lineKey}:${li.dataset.lineKind}`) || null;
}

// drag 事件的 e.target 可能是**文本节点**（Chrome 会把拖拽起点报成文字节点），
// 直接调 .closest 会抛 "closest is not a function"。统一先取最近的 Element。
function elFrom(target) {
  if (target instanceof Element) return target;
  if (target && target.parentElement) return target.parentElement;
  return null;
}

// 仅就地更新选中高亮（**不重建列表**，避免打断双击/拖拽）
export function updateSelectionHighlight(view) {
  const list = view && view.listEl;
  if (!list) return;
  const key = Array.isArray(view.selectedActionPath) ? pathKey(view.selectedActionPath) : '';
  list.querySelectorAll('li').forEach((li) => {
    if (li.classList.contains('action-inline-editor')) return;
    const on = !!key && li.dataset.lineKey === key && li.dataset.lineKind === view.selectedLineKind;
    li.classList.toggle('active', on);
  });
}

// 就地更新"测试点"标记（不重建列表）—— 实现在 bp-visual.js，此处再导出以兼容旧调用
export { updateBpVisual };

// 就地收起内联编辑器（不重建列表）
function removeInlineEditorInPlace(view) {
  const list = view && view.listEl;
  if (!list) return;
  const el = list.querySelector('li.action-inline-editor[data-inline-editor-for]');
  if (el) el.remove();
  const cur = list.querySelector('li.editing');
  if (cur) cur.classList.remove('editing');
  view.inlineEditingPathKey = null;
}

// 在窗格容器上做一次事件委托（支持动态增删窗格）
export function initPaneContainerEvents(container, resolveView) {
  if (!container || container.dataset.paneEventsReady === '1') return;
  container.dataset.paneEventsReady = '1';

  const viewOf = (target) => {
    const paneEl = target instanceof Element ? target.closest('.editor-pane') : null;
    return paneEl ? resolveView(paneEl) : null;
  };

  container.addEventListener('click', (e) => {
    const view = viewOf(e.target);
    if (!view) return;
    if (typeof state.onFocusView === 'function') state.onFocusView(view);
    const list = view.listEl;
    const tel = elFrom(e.target);

    // 行号 = 测试点开关（点击切换，不再单独占一列按钮）
    const bpEl = tel && tel.closest('.action-index.bp-toggle');
    if (bpEl && bpEl.dataset.bpPath) {
      if (!view.breakpoints) view.breakpoints = new Set();
      const k = bpEl.dataset.bpPath;
      if (view.breakpoints.has(k)) view.breakpoints.delete(k);
      else view.breakpoints.add(k);
      updateBpVisual(view);
      return;
    }

    const toggle = tel && tel.closest('.loop-toggle');
    if (toggle) {
      const lineData = lineDataFromLi(list, toggle.closest('li'));
      if (!lineData) return;
      const key = pathKey(lineData.path);
      if (view.expandedLoopPathKeys.has(key)) view.expandedLoopPathKeys.delete(key);
      else view.expandedLoopPathKeys.add(key);
      renderViewList(view);
      return;
    }

    const li = tel && tel.closest('li');
    if (!li || li.classList.contains('action-inline-editor')) return;
    const lineData = lineDataFromLi(list, li);
    if (!lineData) return;

    if (state.batchCommentMode && lineData.kind === 'action') {
      view.inlineEditingPathKey = null;
      const ok = toggleCommentForPath(view, lineData.path, { silent: false });
      if (ok) renderViewList(view);
      return;
    }

    // 切到别的行时**就地**收起内联编辑器（不重建 DOM，避免打断双击 → 内联编辑/重命名失效）
    if (view.inlineEditingPathKey && view.inlineEditingPathKey !== pathKey(lineData.path)) {
      updateCurrentActionFromEditor({ silent: true, view });
      removeInlineEditorInPlace(view);
    }

    setSelectedLine(view, lineData.path, lineData.kind);
    const selected = getActionAtPath(view, lineData.path);
    if (selected) fillActionEditorByAction(selected);
    updateSelectionHighlight(view);
  });

  container.addEventListener('dblclick', (e) => {
    if (state.batchCommentMode) return;
    const tel = elFrom(e.target);
    if (!tel || tel.closest('.loop-toggle')) return;
    const view = viewOf(e.target);
    if (!view) return;
    const li = tel.closest('li');
    if (!li || li.classList.contains('action-inline-editor')) return;
    const lineData = lineDataFromLi(view.listEl, li);
    if (!lineData || lineData.kind !== 'action') return;
    if (typeof state.onFocusView === 'function') state.onFocusView(view);
    startInlineEdit(view, lineData.path, renderViewList);
  });

  container.addEventListener('dragstart', (e) => {
    const view = viewOf(e.target);
    if (!view) return;
    const tel = elFrom(e.target);
    const li = tel && tel.closest('li');
    const lineData = lineDataFromLi(view.listEl, li);
    if (!lineData) return;
    state.draggedActionPath = [...lineData.path];
    state.draggedViewId = view.id;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/action-path', JSON.stringify(lineData.path));
  });

  container.addEventListener('dragend', (e) => {
    const tel = elFrom(e.target);
    const li = tel && tel.closest('li');
    if (li) li.classList.remove('drag-over');
    container.querySelectorAll('li.drag-over').forEach((n) => n.classList.remove('drag-over'));
    document.querySelectorAll('.editor-pane.drop-target').forEach((p) => p.classList.remove('drop-target'));
  });

  container.addEventListener('dragover', (e) => {
    const view = viewOf(e.target);
    if (!view) return;
    if (!Array.isArray(state.draggedActionPath)) return;
    e.preventDefault();
    const tel = elFrom(e.target);
    if (tel && tel.closest('.loop-toggle')) return;

    // 跨窗格时高亮整个窗格，同时仍高亮鼠标所在动作行给出落点反馈
    if (state.draggedViewId && state.draggedViewId !== view.id) {
      const paneEl = tel && tel.closest('.editor-pane');
      if (paneEl) paneEl.classList.add('drop-target');
    }
    const li = tel && tel.closest('li');
    if (li && !li.classList.contains('action-inline-editor')) {
      container.querySelectorAll('li.drag-over').forEach((n) => { if (n !== li) n.classList.remove('drag-over'); });
      li.classList.add('drag-over');
    }
  });

  container.addEventListener('dragleave', (e) => {
    const tel = elFrom(e.target);
    const li = tel && tel.closest('li');
    if (li) li.classList.remove('drag-over');
    const paneEl = tel && tel.closest('.editor-pane');
    if (paneEl && !paneEl.contains(e.relatedTarget)) paneEl.classList.remove('drop-target');
  });

  container.addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const view = viewOf(e.target);
    if (!view) return;
    container.querySelectorAll('li.drag-over').forEach((n) => n.classList.remove('drag-over'));
    document.querySelectorAll('.editor-pane.drop-target').forEach((p) => p.classList.remove('drop-target'));

    const tel = elFrom(e.target);
    const li = tel && tel.closest('li');
    const lineData = li ? lineDataFromLi(view.listEl, li) : null;
    const dropTarget = lineData ? getDropTargetFromLine(view, lineData) : { type: 'root', index: view.rows.length };

    // 从宏文件夹拖入 → 插入 import
    const macroPath = e.dataTransfer.getData('text/macro-path') || '';
    if (macroPath && macroPath.toLowerCase().endsWith('.json') && !Array.isArray(state.draggedActionPath)) {
      insertActionAtTarget(view, ['import', macroPath], dropTarget);
      renderViewList(view);
      showToast(`已插入 import: ${macroPath}`);
      return;
    }

    if (!Array.isArray(state.draggedActionPath)) return;

    // 跨窗格：按鼠标所在位置的落点插入（与同窗一致），而不是一律追加到末尾
    if (state.draggedViewId && state.draggedViewId !== view.id) {
      const srcView = typeof state.findView === 'function' ? state.findView(state.draggedViewId) : null;
      if (srcView) {
        const info = getActionAndContainerByPath(srcView, state.draggedActionPath);
        if (info) {
          const moved = cloneAction(info.action);
          info.container.splice(info.index, 1);

          const container2 = getContainerForTarget(view, dropTarget);
          if (Array.isArray(container2)) {
            const idx = Math.max(0, Math.min(dropTarget.index, container2.length));
            container2.splice(idx, 0, moved);
            if (dropTarget.type === 'loop') view.expandedLoopPathKeys.add(pathKey(dropTarget.loopPath));
          } else {
            view.rows.push(moved);
          }

          srcView.inlineEditingPathKey = null;
          state.draggedActionPath = null;
          state.draggedViewId = null;
          renderViewList(srcView);
          renderViewList(view);
          showToast('已移动到另一个窗格');
          return;
        }
      }
    }

    const moved = moveActionToTarget(view, state.draggedActionPath, dropTarget, showToast);
    if (moved) renderViewList(view);
    state.draggedActionPath = null;
    state.draggedViewId = null;
  });
}

export function refreshBatchCommentButton() {
  const btn = q('#btnBatchComment');
  if (Array.isArray(state.editorViews)) {
    state.editorViews.forEach((v) => {
      if (v.listEl) v.listEl.classList.toggle('batch-comment-mode', state.batchCommentMode);
    });
  }
  if (!btn) return;
  btn.textContent = `批量注释: ${state.batchCommentMode ? '开' : '关'}`;
  btn.classList.toggle('active', state.batchCommentMode);
}

// 兼容旧调用名
export const renderActionList = renderViewList;
