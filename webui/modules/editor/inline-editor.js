import { state } from '../core/state.js';
import { q } from '../core/dom.js';
import { parseNumber, pathKey, isLoopAction, getRecoverableActionFromNoteText } from './action-model.js';
import { setSelectedLine, getActionAtPath } from './action-ops.js';
import { getDefaultForType, getActionFormUi, updateActionFormUiForType, fillActionEditorByAction, buildActionFromInputs } from './action-form.js';
import { RECOVERABLE_NOTE_PREFIX } from '../core/constants.js';

export function startInlineEdit(path, renderActionList) {
  if (state.batchCommentMode) return;
  const action = getActionAtPath(path);
  if (!action) return;
  setSelectedLine(path, 'action');
  fillActionEditorByAction(action);
  state.inlineEditingPathKey = pathKey(path);
  renderActionList();
}

export function getInlineEditorValues(action) {
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

export function appendInlineEditorRow(list, line, lineKey, callbacks) {
  const { toggleCommentForPath, renderActionList, updateCurrentActionFromEditor } = callbacks;
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
  const recoverable = currentCmd === 'note' ? getRecoverableActionFromNoteText(action[1], RECOVERABLE_NOTE_PREFIX) : null;
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
