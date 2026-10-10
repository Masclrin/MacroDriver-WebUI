import { state } from '../core/state.js';
import { q } from '../core/dom.js';
import { parseNumber, parseDelay, pathKey, isRawRow, getRecoverableActionFromNoteText } from './action-model.js';
import { setSelectedLine, getActionAtPath, getActionAndContainerByPath } from './action-ops.js';
import { getDefaultForType, getActionFormUi, updateActionFormUiForType, fillActionEditorByAction } from './action-form.js';
import { RECOVERABLE_NOTE_PREFIX } from '../core/constants.js';
import { apiCall } from '../core/api.js';
import { updateBpVisual } from './bp-visual.js';

export function startInlineEdit(view, path, renderViewList) {
  if (state.batchCommentMode) return;
  const action = getActionAtPath(view, path);
  if (!action) return;
  setSelectedLine(view, path, 'action');
  fillActionEditorByAction(action);
  view.inlineEditingPathKey = pathKey(path);
  renderViewList(view);
}

export function getInlineEditorValues(action) {
  if (isRawRow(action)) {
    return { type: 'custom', arg1: String(action.__raw ?? ''), arg2: '' };
  }
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
    return { type: cmd, arg1: String(parseDelay(action[1], 50)), arg2: '' };
  }
  if (cmd === 'move_to') {
    return {
      type: cmd,
      arg1: `${parseNumber(action[1], 0)},${parseNumber(action[2], 0)}`,
      arg2: String(Math.max(0, parseNumber(action[3], 150))),
    };
  }
  if (cmd === 'scroll') {
    return { type: cmd, arg1: String(parseNumber(action[1], 0)), arg2: '' };
  }
  if (cmd === 'loop') {
    return { type: cmd, arg1: String(Math.max(1, parseNumber(action[1], 1))), arg2: '' };
  }
  if (cmd === 'import' || cmd === 'note') {
    return { type: cmd, arg1: String(action[1] ?? ''), arg2: '' };
  }
  if (cmd === 'ext') {
    const args = Array.isArray(action) ? action.slice(2) : [];
    return { type: cmd, arg1: String(action[1] ?? ''), arg2: args.length ? JSON.stringify(args) : '' };
  }
  if (['kd', 'ku', 'md', 'mu'].includes(cmd)) {
    return {
      type: cmd,
      arg1: String(action[1] ?? getDefaultForType(cmd).arg1),
      arg2: String(parseDelay(action[2], 50)),
    };
  }
  // 未识别指令 → 以"自定义原文"编辑
  return { type: 'custom', arg1: JSON.stringify(action), arg2: '' };
}

export function appendInlineEditorRow(view, list, line, lineKey, callbacks) {
  const { toggleCommentForPath, renderViewList, updateCurrentActionFromEditor } = callbacks;
  const action = line.action;

  // 未识别/未解析的原文行：提供原始文本直接编辑（保存时原样写回）
  if (isRawRow(action)) {
    appendRawEditorRow(view, list, line, lineKey, { renderViewList });
    return;
  }

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
  const arg1Options = Array.isArray(ui.arg1Options) && ui.arg1Options.length > 0 ? ui.arg1Options : null;
  let arg1Input;
  if (arg1Options) {
    arg1Input = document.createElement('select');
    arg1Options.forEach((opt) => {
      const option = document.createElement('option');
      option.value = opt;
      option.textContent = opt;
      arg1Input.appendChild(option);
    });
    arg1Input.value = arg1Options.includes(values.arg1) ? values.arg1 : arg1Options[0];
  } else {
    arg1Input = document.createElement('input');
    arg1Input.type = 'text';
    arg1Input.value = values.arg1;
    arg1Input.placeholder = ui.arg1Placeholder || '';
  }
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
  const recoverable = currentCmd === 'note' ? getRecoverableActionFromNoteText(action[1], RECOVERABLE_NOTE_PREFIX) : null;

  let btnExpand = null;
  let expandConfirmed = false;
  if (currentCmd === 'import') {
    btnExpand = document.createElement('button');
    btnExpand.type = 'button';
    btnExpand.className = 'inline-edit-btn';
    btnExpand.style.background = 'rgba(255, 190, 85, 0.75)';
    btnExpand.style.color = '#1a2d3e';
    btnExpand.textContent = '展开动作';
    actions.appendChild(btnExpand);

    btnExpand.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!expandConfirmed) {
        expandConfirmed = true;
        btnExpand.textContent = '确认展开';
        btnExpand.style.background = 'rgba(230, 126, 34, 0.85)';
        return;
      }
      const macroPath = arg1Input.value.trim();
      if (!macroPath) return;
      try {
        const data = await apiCall('read_macro', macroPath);
        const importedRows = Array.isArray(data?.rows) ? data.rows : [];
        if (importedRows.length === 0) {
          alert('子宏内容为空');
          return;
        }
        const expandedActions = [
          ['note', `展开自: ${macroPath}`],
          ...importedRows,
          ['note', '组件结尾'],
        ];
        if (typeof callbacks.expandImportAction === 'function') {
          callbacks.expandImportAction(view, line.path, expandedActions);
        }
        view.inlineEditingPathKey = null;
        renderViewList(view);
      } catch (err) {
        alert(`展开失败: ${err.message}`);
      }
    });
  }

  if (currentCmd !== 'note' || recoverable) {
    const btnToggle = document.createElement('button');
    btnToggle.type = 'button';
    btnToggle.className = 'inline-edit-btn';
    btnToggle.textContent = currentCmd === 'note' ? '恢复动作' : '注释动作';
    actions.appendChild(btnToggle);

    btnToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const ok = toggleCommentForPath(view, line.path, { silent: false });
      if (ok) renderViewList(view);
    });
  }

  // 测试点开关：仅顶层动作行可设（与行号点击等价，这里给一个显式入口）
  if (line.depth === 0) {
    const btnBp = document.createElement('button');
    btnBp.type = 'button';
    btnBp.className = 'inline-edit-btn inline-edit-bp';

    const syncBpBtn = () => {
      const on = !!(view.breakpoints && view.breakpoints.has(lineKey));
      btnBp.textContent = on ? '● 取消测试点' : '○ 设为测试点';
      btnBp.classList.toggle('on', on);
      btnBp.title = on
        ? '取消后本行不再作为测试点运行区间起点'
        : '设为测试点后，可用「测试点运行」从本行跑到下一个测试点';
    };
    syncBpBtn();

    btnBp.addEventListener('click', (e) => {
      e.stopPropagation();
      if (!view.breakpoints) view.breakpoints = new Set();
      if (view.breakpoints.has(lineKey)) view.breakpoints.delete(lineKey);
      else view.breakpoints.add(lineKey);
      syncBpBtn();
      updateBpVisual(view);
      const tab = typeof state.tabOfView === 'function' ? state.tabOfView(view) : null;
      if (tab) tab.dirty = false; // 测试点不写入文件，不影响脏标记
    });
    actions.appendChild(btnBp);
  }

  body.appendChild(row1);
  body.appendChild(actions);

  const applyToMainForm = () => {
    q('#actionType').value = values.type;
    updateActionFormUiForType(values.type);
    q('#actionArg1').value = arg1Input.value;
    q('#actionArg2').value = arg2Input ? arg2Input.value : '';
    setSelectedLine(view, line.path, 'action');
    if (typeof state.onFocusView === 'function') state.onFocusView(view);
  };

  arg1Input.addEventListener('input', () => { applyToMainForm(); });
  if (arg2Input) arg2Input.addEventListener('input', () => { applyToMainForm(); });

  const keepEditing = () => {
    view.inlineEditingPathKey = lineKey;
    setSelectedLine(view, line.path, 'action');
    if (typeof state.onFocusView === 'function') state.onFocusView(view);
  };

  arg1Input.addEventListener('focus', keepEditing);
  if (arg2Input) arg2Input.addEventListener('focus', keepEditing);

  btnApply.addEventListener('click', (e) => {
    e.stopPropagation();
    applyToMainForm();
    updateCurrentActionFromEditor({ silent: true, view });
    view.inlineEditingPathKey = lineKey;
    renderViewList(view);
  });

  editorLi.addEventListener('click', (e) => { e.stopPropagation(); keepEditing(); });

  editorLi.appendChild(idxStub);
  editorLi.appendChild(body);
  list.appendChild(editorLi);
}

// 未识别行的原始文本编辑器
function appendRawEditorRow(view, list, line, lineKey, { renderViewList }) {
  const editorLi = document.createElement('li');
  editorLi.className = 'action-inline-editor action-inline-editor-raw';
  editorLi.dataset.inlineEditorFor = lineKey;

  const idxStub = document.createElement('span');
  idxStub.className = 'action-index';
  idxStub.textContent = '';

  const body = document.createElement('div');
  body.className = 'action-inline-editor-body';

  const hint = document.createElement('div');
  hint.className = 'inline-edit-label';
  hint.textContent = '未识别的行 · 可直接编辑原始内容（保存时原样写回，不会被丢弃）';
  body.appendChild(hint);

  const ta = document.createElement('textarea');
  ta.className = 'raw-line-editor';
  ta.rows = 3;
  ta.value = String(line.action.__raw ?? '');
  body.appendChild(ta);

  const actions = document.createElement('div');
  actions.className = 'inline-actions inline-edit-actions';

  const btnApply = document.createElement('button');
  btnApply.type = 'button';
  btnApply.className = 'primary inline-edit-btn';
  btnApply.textContent = '应用修改';
  btnApply.addEventListener('click', (e) => {
    e.stopPropagation();
    const found = getActionAndContainerByPath(view, line.path);
    if (found) {
      found.container[found.index] = { __raw: ta.value };
    }
    view.inlineEditingPathKey = null;
    renderViewList(view);
  });
  actions.appendChild(btnApply);
  body.appendChild(actions);

  const keepEditing = () => {
    view.inlineEditingPathKey = lineKey;
    setSelectedLine(view, line.path, 'action');
    if (typeof state.onFocusView === 'function') state.onFocusView(view);
  };
  editorLi.addEventListener('click', (e) => { e.stopPropagation(); keepEditing(); });

  editorLi.appendChild(idxStub);
  editorLi.appendChild(body);
  list.appendChild(editorLi);
}
