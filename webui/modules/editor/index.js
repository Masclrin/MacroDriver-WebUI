import { state } from '../core/state.js';
import { q, showToast } from '../core/dom.js';
import { apiCall } from '../core/api.js';
import { renderMacroTreeList } from '../macro-tree.js';
import { normalizeMacroRows, pathKey, keyToPath, cloneAction } from './action-model.js';
import { setSelectedLine, insertActionAtTarget, moveActionToTarget, resolveInsertTargetAfterSelection, getActionAndContainerByPath, getActionAtPath, clearExpandedLoopKeysByPrefix } from './action-ops.js';
import { fillActionEditorByAction, buildActionFromInputs, ensureActionFormDefaultsForType, switchActionType } from './action-form.js';
import { renderActionList, refreshBatchCommentButton, updateCurrentActionFromEditor, initActionListEvents } from './action-list-render.js';

export { renderActionList };
export { loadMacroToEditor, renderEditorMacroBrowser, bindEditorActions };

async function loadMacroToEditor(path) {
  if (state.editorLoadAbortController) {
    state.editorLoadAbortController.abort();
  }
  const controller = new AbortController();
  state.editorLoadAbortController = controller;

  try {
    const data = await apiCall('read_macro', path);
    if (controller.signal.aborted) return;

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
  } finally {
    if (state.editorLoadAbortController === controller) {
      state.editorLoadAbortController = null;
    }
  }
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
  initActionListEvents();
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
    const inputName = q('#editorNewName').value.trim();
    if (!inputName) return showToast('请输入新文件名');
    const folder = q('#editorFolder').value.trim() || '宏/录制宏';
    const newName = await generateUniqueFileName(folder, inputName);

    const ret = await apiCall('rename_macro', state.selectedMacro, newName);
    state.selectedMacro = ret.path;
    q('#selectedMacroPath').value = ret.path;
    showToast('重命名完成');
    const { refreshMacros, refreshBindings } = await import('../macro-bind.js');
    await refreshMacros();
    await refreshBindings();
  });

  q('#btnDeleteEditorMacro').addEventListener('click', async () => {
    if (!state.selectedMacro) return showToast('请先选择一个宏');
    if (!window.confirm(`确认删除 ${state.selectedMacro} ?`)) return;
    if (!window.confirm(`再次确认：将永久删除 ${state.selectedMacro}，此操作不可恢复！`)) return;

    await apiCall('delete_macro', state.selectedMacro);
    showToast('已删除宏文件');
    state.selectedMacro = null;
    state.editorRows = [];
    q('#selectedMacroPath').value = '';
    setSelectedLine(null, 'action');
    ensureActionFormDefaultsForType(q('#actionType').value || 'kd', true);
    renderActionList();
    const { refreshMacros, refreshBindings } = await import('../macro-bind.js');
    await refreshMacros();
    await refreshBindings();
  });

  q('#btnMoveMacro').addEventListener('click', async () => {
    if (!state.selectedMacro) return showToast('请先选择一个宏');
    const targetFolder = q('#editorFolder').value.trim() || '宏/录制宏';

    const ret = await apiCall('move_macro', state.selectedMacro, targetFolder);
    state.selectedMacro = ret.path;
    q('#selectedMacroPath').value = ret.path;
    showToast('移动完成');
    const { refreshMacros, refreshBindings } = await import('../macro-bind.js');
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
    } catch (err) {
      showToast(err.message);
    }
  });

  q('#btnAppendAction').addEventListener('click', () => {
    try {
      const row = buildActionFromInputs();
      insertActionAtTarget(row, { type: 'root', index: state.editorRows.length });
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

  const btnRecord = q('#btnEditorRecord');
  if (btnRecord) {
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
        try {
          await apiCall('editor_record_stop');
        } catch (err) {
          showToast(`停止录制失败: ${err.message}`);
        }
        state.editorRecording = false;
        applyRecordButtonUi();
      } else {
        try {
          const ret = await apiCall('editor_record_start');
          if (ret.already_recording) {
            showToast('录制已在进行中');
            return;
          }
          state.editorRecording = true;
          state.editorRecordInsertIndex = null;
          state.editorRecordInsertedCount = 0;
          if (Array.isArray(state.selectedActionPath) && state.selectedActionPath.length) {
            const target = resolveInsertTargetAfterSelection();
            if (target.type === 'root') {
              state.editorRecordInsertIndex = target.index;
            } else if (target.type === 'loop') {
              state.editorRecordInsertIndex = { loopPath: target.loopPath, index: target.index };
            }
          } else {
            state.editorRecordInsertIndex = state.editorRows.length;
          }
          state.editorRecordBuffer = [];
          applyRecordButtonUi();
          showToast('录制已开始，键鼠操作将被记录');
        } catch (err) {
          showToast(`启动录制失败: ${err.message}`);
        }
      }
    });

    window._onEditorRecordEvent = function(payload) {
      if (!state.editorRecording) return;
      try {
        const data = typeof payload === 'string' ? JSON.parse(payload) : payload;
        const { cmd, key, prev_delay_ms } = data;

        if (prev_delay_ms > 0 && state.editorRecordInsertedCount > 0) {
          const container = getContainerForRecordTarget();
          if (container) {
            const prevIdx = getInsertIndexForRecord() - 1;
            if (prevIdx >= 0 && prevIdx < container.length) {
              const prevAction = container[prevIdx];
              if (prevAction && prevAction[0] in { kd: 1, ku: 1, md: 1, mu: 1 }) {
                prevAction[2] = prev_delay_ms;
              }
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
          setSelectedLineByRecordIndex(container);
          renderActionList();
        }
      } catch (e) {
        console.error('_onEditorRecordEvent error:', e);
      }
    };

    window._onEditorRecordStop = function(payload) {
      if (!state.editorRecording) return;
      state.editorRecording = false;
      applyRecordButtonUi();

      try {
        const container = getContainerForRecordTarget();
        if (container) {
          // 仅剔除最后一对左键单击（md left + mu left），
          // 用于消除点击“停止”按钮时多录入的一次左键点击。
          // 使用 if 而非 while，避免误伤用户在停止前故意做的左键收尾连击。
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

          if (state.editorRecordInsertedCount > 0) {
            const lastValidIdx = getInsertIndexForRecord() - 1;
            if (lastValidIdx >= 0 && lastValidIdx < container.length) {
              const idx = state.editorRecordInsertIndex;
              if (idx === null || idx === undefined) {
                setSelectedLine([lastValidIdx], 'action');
              } else if (typeof idx === 'number') {
                setSelectedLine([idx + state.editorRecordInsertedCount - 1], 'action');
              } else if (idx.loopPath) {
                setSelectedLine([...idx.loopPath, idx.index + state.editorRecordInsertedCount - 1], 'action');
              }
            }
          }
        }

        const data = typeof payload === 'string' ? JSON.parse(payload) : payload;
        const tailDelay = data?.tail_delay_ms || 0;

        if (tailDelay > 0 && state.editorRecordInsertedCount > 0) {
          const cont = getContainerForRecordTarget();
          if (cont) {
            const prevIdx = getInsertIndexForRecord() - 1;
            if (prevIdx >= 0 && prevIdx < cont.length) {
              const prevAction = cont[prevIdx];
              if (prevAction && prevAction[0] in { kd: 1, ku: 1, md: 1, mu: 1 }) {
                prevAction[2] = tailDelay;
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
      renderActionList();
      showToast('录制已停止');
    };

    function getContainerForRecordTarget() {
      const idx = state.editorRecordInsertIndex;
      if (idx === null || idx === undefined) return state.editorRows;
      if (typeof idx === 'number') return state.editorRows;
      if (idx.loopPath) {
        const loopAction = getActionAtPath(idx.loopPath);
        if (loopAction && Array.isArray(loopAction[2])) return loopAction[2];
      }
      return state.editorRows;
    }

    function getInsertIndexForRecord() {
      const idx = state.editorRecordInsertIndex;
      const count = state.editorRecordInsertedCount || 0;
      if (idx === null || idx === undefined) return state.editorRows.length;
      if (typeof idx === 'number') return idx + count;
      if (idx.loopPath) return idx.index + count;
      return state.editorRows.length;
    }

    function setSelectedLineByRecordIndex(container) {
      const idx = state.editorRecordInsertIndex;
      const count = state.editorRecordInsertedCount || 0;
      if (count <= 0) return;
      const lastInserted = count - 1;
      if (idx === null || idx === undefined) {
        setSelectedLine([state.editorRows.length - 1], 'action');
      } else if (typeof idx === 'number') {
        setSelectedLine([idx + lastInserted], 'action');
      } else if (idx.loopPath) {
        setSelectedLine([...idx.loopPath, idx.index + lastInserted], 'action');
      }
    }
  }
}
