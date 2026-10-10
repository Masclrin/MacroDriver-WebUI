import { state } from '../core/state.js';
import { q } from '../core/dom.js';
import { parseNumber, parseDelay, isLoopAction, cloneAction, isRawRow } from './action-model.js';
import { ACTION_FORM_DEFAULTS, ACTION_FORM_UI } from '../core/constants.js';
import { getExtCommandsCached, findExtCommand, renderExtArgs, readExtArgs } from './ext-commands.js';

// ── ext 指令：描述符驱动的参数表单 ─────────────────────────────
function extNamesFromCache() {
  return getExtCommandsCached().map((c) => c.name);
}

export function readExtValuesFromForm() {
  const nameEl = q('#actionArg1');
  const name = nameEl ? String(nameEl.value || '').trim() : '';
  const spec = findExtCommand(name);
  const area = q('#extArgsArea');

  if (spec && Array.isArray(spec.args) && spec.args.length) {
    return { name, args: readExtArgs(area, spec) };
  }
  // 无描述符 → 用原始参数输入框
  const raw = q('#extRawArgs');
  let args = [];
  if (raw) {
    const s = String(raw.value || '').trim();
    if (s) {
      if (s.startsWith('[')) {
        try { const arr = JSON.parse(s); if (Array.isArray(arr)) args = arr; } catch (_e) { args = []; }
      }
      if (!args.length) {
        args = s.split(/\s+/).map((t) => (/^-?\d+(\.\d+)?$/.test(t) ? Number(t) : t));
      }
    }
  }
  return { name, args };
}

export function setupExtForm(options = {}) {
  const arg1 = q('#actionArg1');
  const arg2Wrap = q('#actionArg2Wrap');
  const arg1Label = q('#actionArg1Label');
  const arg2Label = q('#actionArg2Label');
  const area = q('#extArgsArea');
  const row = arg1 && arg1.closest('.field-row.triple');

  if (arg1Label) arg1Label.textContent = '附加指令名';
  if (arg2Label) arg2Label.textContent = '';
  if (arg2Wrap) arg2Wrap.style.display = 'none';
  if (row) row.classList.add('single-arg');
  if (arg1 && arg1.parentElement) arg1.parentElement.style.gridColumn = '2 / 4';

  const names = extNamesFromCache();
  const needSelect = names.length > 0;
  const preserved = options.name !== undefined ? String(options.name) : (arg1 ? arg1.value : '');

  const isSelect = arg1 && arg1.tagName.toLowerCase() === 'select';
  if (needSelect) {
    if (!isSelect) {
      const sel = document.createElement('select');
      sel.id = 'actionArg1';
      names.forEach((n) => {
        const o = document.createElement('option');
        o.value = n;
        o.textContent = n;
        sel.appendChild(o);
      });
      arg1.replaceWith(sel);
    } else {
      arg1.innerHTML = '';
      names.forEach((n) => {
        const o = document.createElement('option');
        o.value = n;
        o.textContent = n;
        arg1.appendChild(o);
      });
    }
  } else if (isSelect) {
    const inp = document.createElement('input');
    inp.id = 'actionArg1';
    inp.type = 'text';
    inp.placeholder = '如 ext.echo（暂无已注册指令，可直接手填）';
    arg1.replaceWith(inp);
  }

  const nameEl = q('#actionArg1');
  if (needSelect) {
    nameEl.value = names.includes(preserved) ? preserved : names[0];
  } else if (preserved !== undefined) {
    nameEl.value = preserved;
  }
  nameEl.onchange = () => {
    setupExtForm({ name: q('#actionArg1').value });
    if (typeof state.onExtArgsChanged === 'function') state.onExtArgsChanged();
  };

  if (!area) return;
  area.hidden = false;
  area.innerHTML = '';

  const name = String(nameEl.value || '').trim();
  const spec = findExtCommand(name);

  if (spec && Array.isArray(spec.args) && spec.args.length) {
    renderExtArgs(area, spec, options.values || [], () => {
      if (typeof state.onExtArgsChanged === 'function') state.onExtArgsChanged();
    });
  } else {
    if (spec && spec.planned) {
      const hint = document.createElement('div');
      hint.className = 'ext-args-hint';
      hint.textContent = `「${spec.label || name}」尚未提供处理器（等待插件实现），参数可先留空。`;
      area.appendChild(hint);
    }
    const wrap = document.createElement('div');
    wrap.className = 'ext-arg-cell';
    const lab = document.createElement('label');
    lab.className = 'ext-arg-label';
    lab.textContent = '参数（空格分隔 或 JSON 数组）';
    const inp = document.createElement('input');
    inp.type = 'text';
    inp.id = 'extRawArgs';
    inp.placeholder = '如 30 或 ["weak"]';
    wrap.appendChild(lab);
    wrap.appendChild(inp);
    area.appendChild(wrap);
  }
}

export function hideExtForm() {
  const area = q('#extArgsArea');
  if (area) { area.hidden = true; area.innerHTML = ''; }
  const el = q('#actionArg1');
  if (el) el.onchange = null;
  const row = el && el.closest('.field-row.triple');
  if (row) row.classList.remove('single-arg');
}

// 描述符异步加载完成后刷新（仅当当前类型是 ext 时）
export function refreshExtForm() {
  const t = q('#actionType');
  if (t && t.value === 'ext') setupExtForm();
}

export function getDefaultForType(type) {
  return ACTION_FORM_DEFAULTS[type] || ACTION_FORM_DEFAULTS.wait;
}

// 解析 ext 动作的参数文本：优先按 JSON 数组；否则按空白分隔，数字自动转 number
export function parseExtArgs(text) {
  const s = String(text == null ? '' : text).trim();
  if (!s) return [];
  if (s.startsWith('[')) {
    try {
      const arr = JSON.parse(s);
      if (Array.isArray(arr)) return arr;
    } catch (_err) {
      // 非法 JSON → 退回空白分隔
    }
  }
  return s.split(/\s+/).map((tok) => (/^-?\d+(\.\d+)?$/.test(tok) ? Number(tok) : tok));
}

export function getActionFormUi(type) {
  return ACTION_FORM_UI[type] || ACTION_FORM_UI.wait;
}

export function updateActionFormUiForType(type) {
  // ext：使用描述符驱动的专用表单
  if (type === 'ext') {
    setupExtForm();
    return;
  }
  hideExtForm();

  const ui = getActionFormUi(type);
  const arg1Wrap = q('#actionArg1Wrap');
  const arg2Wrap = q('#actionArg2Wrap');
  const arg1Label = q('#actionArg1Label');
  const arg2Label = q('#actionArg2Label');
  const arg2 = q('#actionArg2');
  const row = arg1Wrap?.closest('.field-row.triple');

  if (arg1Label) arg1Label.textContent = ui.arg1Label || '参数1';
  if (arg2Label) arg2Label.textContent = ui.arg2Label || '参数2';

  // 根据 ui.arg1Options 动态切换 #actionArg1 为 input 或 select
  // md/mu 只有 left/right/middle 三个按键，用下拉选择栏更合适
  const needSelect = Array.isArray(ui.arg1Options) && ui.arg1Options.length > 0;
  const oldArg1 = q('#actionArg1');
  const isSelect = oldArg1 && oldArg1.tagName.toLowerCase() === 'select';
  const preservedValue = oldArg1 ? oldArg1.value : '';

  if (oldArg1) {
    if (needSelect && !isSelect) {
      const select = document.createElement('select');
      select.id = 'actionArg1';
      ui.arg1Options.forEach((opt) => {
        const option = document.createElement('option');
        option.value = opt;
        option.textContent = opt;
        select.appendChild(option);
      });
      oldArg1.replaceWith(select);
    } else if (!needSelect && isSelect) {
      const input = document.createElement('input');
      input.id = 'actionArg1';
      input.type = 'text';
      input.placeholder = ui.arg1Placeholder || '';
      oldArg1.replaceWith(input);
    } else if (!needSelect && oldArg1.placeholder !== undefined) {
      oldArg1.placeholder = ui.arg1Placeholder || '';
    }
  }

  const arg1 = q('#actionArg1');
  if (arg1) {
    if (needSelect) {
      arg1.value = ui.arg1Options.includes(preservedValue) ? preservedValue : ui.arg1Options[0];
    } else {
      arg1.value = preservedValue;
    }
  }

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

const ACTION_TYPE_GROUPS = { kd: 'key', ku: 'key', md: 'mouse', mu: 'mouse' };

export function switchActionType(newType) {
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

export function ensureActionFormDefaultsForType(type, force = false) {
  // ext 的参数由 setupExtForm 管理，不能再用 arg1/arg2 默认值覆盖
  if (type === 'ext') {
    updateActionFormUiForType('ext');
    state._lastActionTypeGroupKey = type;
    return;
  }
  const defaults = getDefaultForType(type);
  updateActionFormUiForType(type);
  // updateActionFormUiForType 可能替换了 #actionArg1（input↔select），需重新获取
  const arg1 = q('#actionArg1');
  const arg2 = q('#actionArg2');
  if (force || !arg1.value.trim()) arg1.value = defaults.arg1;
  if (force || !arg2.value.trim()) arg2.value = defaults.arg2;
  state._lastActionTypeGroupKey = type;
}

export function fillActionEditorByAction(action) {
  if (!Array.isArray(action) && !isRawRow(action)) return;

  // 未识别的原文行 → 用 custom（自定义原文）承载
  if (isRawRow(action)) {
    q('#actionType').value = 'custom';
    updateActionFormUiForType('custom');
    q('#actionArg1').value = String(action.__raw ?? '');
    q('#actionArg2').value = '';
    state._lastActionTypeGroupKey = 'custom';
    return;
  }

  const type = String(action[0]).trim().toLowerCase();
  q('#actionType').value = type;
  updateActionFormUiForType(type);
  state._lastActionTypeGroupKey = type;

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

  if (type === 'move_to') {
    q('#actionArg1').value = `${parseNumber(action[1], 0)},${parseNumber(action[2], 0)}`;
    q('#actionArg2').value = String(action[3] ?? 150);
    return;
  }

  if (type === 'scroll') {
    q('#actionArg1').value = String(action[1] ?? 120);
    q('#actionArg2').value = '';
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

  if (type === 'ext') {
    setupExtForm({
      name: String(action[1] ?? ''),
      values: Array.isArray(action) ? action.slice(2) : [],
    });
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

  // 未识别指令 → 以 custom（自定义原文）编辑，避免"未知动作类型"报错
  q('#actionType').value = 'custom';
  updateActionFormUiForType('custom');
  q('#actionArg1').value = JSON.stringify(action);
  q('#actionArg2').value = '';
  state._lastActionTypeGroupKey = 'custom';
}

export function buildActionFromInputs(options = {}) {
  const existingAction = options.existingAction || null;
  const type = q('#actionType').value;
  const arg1 = q('#actionArg1').value.trim();
  const arg2 = q('#actionArg2').value.trim();

  if (type === 'wait') {
    return ['wait', parseDelay(arg1 || '50', 50)];
  }

  if (type === 'view') {
    const [dxText = '0', dyText = '0'] = (arg1 || '0,0').split(',');
    const dx = parseNumber(dxText, 0);
    const dy = parseNumber(dyText, 0);
    const dur = Math.max(1, parseNumber(arg2 || '50', 50));
    return ['view', [dx, dy], dur];
  }

  if (type === 'move_to') {
    const [xText = '0', yText = '0'] = (arg1 || '0,0').split(',');
    const x = parseNumber(xText, 0);
    const y = parseNumber(yText, 0);
    const dur = Math.max(1, parseNumber(arg2 || '150', 150));
    return ['move_to', x, y, dur];
  }

  if (type === 'scroll') {
    return ['scroll', parseNumber(arg1 || '120', 120)];
  }

  if (type === 'import') {
    if (!arg1) throw new Error('import 需要子宏路径');
    return ['import', arg1];
  }

  if (type === 'ext') {
    const { name, args } = readExtValuesFromForm();
    if (!name) throw new Error('请选择或填写 ext 指令名（如 ext.echo）');
    return ['ext', name, ...args];
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
    const delay = parseDelay(arg2 || '50', 50);
    return [type, key, delay];
  }

  if (type === 'custom') {
    return buildCustomAction(arg1);
  }

  // 未知类型：不抛错，落为原文行（原文可直接编辑、保存原样写回）
  return buildCustomAction(arg1 || type);
}

// 把"自定义"文本转成动作：
//   合法 JSON 数组 → 结构化指令；否则 → 原文行 {__raw: 文本}
export function buildCustomAction(text) {
  const s = String(text == null ? '' : text).trim();
  if (!s) throw new Error('自定义内容不能为空');
  if (s.startsWith('[') || s.startsWith('{')) {
    try {
      const parsed = JSON.parse(s);
      if (Array.isArray(parsed) && parsed.length) return parsed;
    } catch (_err) {
      // 非法 JSON → 按原文保留
    }
  }
  return { __raw: s };
}
