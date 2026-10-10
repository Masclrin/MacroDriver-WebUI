import { state } from '../core/state.js';
import { q } from '../core/dom.js';
import { parseNumber, isLoopAction, cloneAction } from './action-model.js';
import { ACTION_FORM_DEFAULTS, ACTION_FORM_UI } from '../core/constants.js';

export function getDefaultForType(type) {
  return ACTION_FORM_DEFAULTS[type] || ACTION_FORM_DEFAULTS.wait;
}

export function getActionFormUi(type) {
  return ACTION_FORM_UI[type] || ACTION_FORM_UI.wait;
}

export function updateActionFormUiForType(type) {
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

export function ensureActionFormDefaultsForType(type, force = false) {
  const defaults = getDefaultForType(type);
  const arg1 = q('#actionArg1');
  const arg2 = q('#actionArg2');
  updateActionFormUiForType(type);
  if (force || !arg1.value.trim()) arg1.value = defaults.arg1;
  if (force || !arg2.value.trim()) arg2.value = defaults.arg2;
}

export function fillActionEditorByAction(action) {
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

export function buildActionFromInputs(options = {}) {
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
