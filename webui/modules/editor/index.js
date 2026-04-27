import { state } from '../core/state.js';
import { q, showToast } from '../core/dom.js';
import { apiCall } from '../core/api.js';
import { renderMacroTreeList } from '../macro-tree.js';
import { normalizeMacroRows, pathKey, keyToPath } from './action-model.js';
import { setSelectedLine, insertActionAtTarget, moveActionToTarget, resolveInsertTargetAfterSelection, getActionAndContainerByPath, getActionAtPath, clearExpandedLoopKeysByPrefix } from './action-ops.js';
import { fillActionEditorByAction, buildActionFromInputs, ensureActionFormDefaultsForType } from './action-form.js';
import { renderActionList, refreshBatchCommentButton, updateCurrentActionFromEditor } from './action-list-render.js';

export { renderActionList };
export { loadMacroToEditor, renderEditorMacroBrowser, bindEditorActions };

async function loadMacroToEditor(path) {
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
  const { renderMacroList } = await import('../macro-bind.js');
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
    openedPath: state.selectedMacro,
    onSelect: (path) => {
      loadMacroToEditor(path).catch((err) => showToast(err.message));
    },
  });
}

function bindEditorActions() {
  state.onSelectMacroForEditor = loadMacroToEditor;
  state.renderEditorMacroBrowser = renderEditorMacroBrowser;
  state.renderRecordMacroBrowser = async () => {};
  state.renderActionList = renderActionList;

  q('#btnRefreshEditorMacroBrowser').addEventListener('click', async () => {
    const { refreshMacros } = await import('../macro-bind.js');
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
    const { refreshMacros } = await import('../macro-bind.js');
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
    const { refreshMacros, refreshBindings } = await import('../macro-bind.js');
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
    const { refreshMacros } = await import('../macro-bind.js');
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
        const moved = moveActionToTarget(state.draggedActionPath, { type: 'root', index: state.editorRows.length }, showToast);
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
