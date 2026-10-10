// ext 附加指令：描述符驱动的通用参数表单（T2-2）
//
// 后端 list_ext_commands() 返回描述符数组，每项形如：
//   { name, label, description, planned?, has_handler, plugin?,
//     args: [ { name, label, type:"string|number|bool|enum|slider",
//               default, min, max, step, options, description } ] }
// 前端只写这一份渲染器，任何插件新增的 ext 指令都会自动获得可视化参数编辑。
import { apiCall } from '../core/api.js';

let _cache = null;

export async function loadExtCommands(force = false) {
  if (_cache && !force) return _cache;
  try {
    const res = await apiCall('list_ext_commands');
    const items = (res && (res.items || (res.data && res.data.items))) || [];
    _cache = Array.isArray(items) ? items : [];
  } catch (err) {
    // 失败时不要清掉已有缓存（例如静态预览已灌入描述符）
    if (!_cache) _cache = [];
  }
  return _cache;
}

export function getExtCommandsCached() {
  return _cache || [];
}

// 仅用于无后端静态预览：直接灌入一份描述符，便于查看 ext 表单 UI
export function setExtCommandsForPreview(list) {
  _cache = Array.isArray(list) ? list : [];
  return _cache;
}

export function findExtCommand(name) {
  return (_cache || []).find((c) => c.name === name) || null;
}

// 生成参数表单到 container；任何输入变化都会调用 onChange()
export function renderExtArgs(container, spec, values, onChange) {
  if (!container) return;
  container.innerHTML = '';

  const args = (spec && spec.args) || [];
  if (!args.length) {
    const hint = document.createElement('div');
    hint.className = 'ext-args-hint';
    hint.textContent = spec && spec.planned
      ? '该指令尚未提供参数（等待插件实现）'
      : '该指令无参数';
    container.appendChild(hint);
    return;
  }

  const grid = document.createElement('div');
  grid.className = 'ext-args-grid';

  args.forEach((a, i) => {
    const cell = document.createElement('div');
    cell.className = 'ext-arg-cell';

    const lab = document.createElement('label');
    lab.className = 'ext-arg-label';
    lab.textContent = a.label || a.name;
    if (a.description) lab.title = a.description;
    cell.appendChild(lab);

    const cur = values && values[i] !== undefined ? values[i] : a.default;
    let input;

    if (a.type === 'bool') {
      input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = !!cur;
      input.addEventListener('change', () => onChange && onChange());
    } else if (a.type === 'enum') {
      input = document.createElement('select');
      (a.options || []).forEach((o) => {
        const opt = document.createElement('option');
        opt.value = o;
        opt.textContent = o;
        input.appendChild(opt);
      });
      input.value = cur === undefined || cur === null ? String(a.default ?? '') : String(cur);
      input.addEventListener('change', () => onChange && onChange());
    } else if (a.type === 'number' || a.type === 'slider') {
      input = document.createElement('input');
      input.type = 'number';
      if (a.min !== undefined) input.min = a.min;
      if (a.max !== undefined) input.max = a.max;
      if (a.step !== undefined) input.step = a.step;
      input.value = cur === undefined || cur === null ? (a.default ?? 0) : cur;
      input.addEventListener('input', () => onChange && onChange());
    } else {
      input = document.createElement('input');
      input.type = 'text';
      input.value = cur === undefined || cur === null ? String(a.default ?? '') : String(cur);
      input.addEventListener('input', () => onChange && onChange());
    }

    input.dataset.extArgIndex = String(i);
    cell.appendChild(input);
    grid.appendChild(cell);
  });

  container.appendChild(grid);
}

// 从表单读回参数数组（顺序与 spec.args 一致）
export function readExtArgs(container, spec) {
  const args = (spec && spec.args) || [];
  const out = [];
  if (!container) return out;

  args.forEach((a, i) => {
    const el = container.querySelector(`[data-ext-arg-index="${i}"]`);
    if (!el) return;
    if (a.type === 'bool') {
      out.push(!!el.checked);
    } else if (a.type === 'number' || a.type === 'slider') {
      const n = parseFloat(el.value);
      out.push(Number.isFinite(n) ? n : (a.default ?? 0));
    } else {
      out.push(el.value);
    }
  });
  return out;
}
