import { state } from './core/state.js';
import { q, qa, showToast } from './core/dom.js';
import { apiCall } from './core/api.js';
import { normalizeParamTextValue, escapeHtml } from './core/text.js';
import {
  PARAM_GUIDE_FALLBACK,
  RECOMMENDED_RANDOM_DELAY_RULES,
  HIDE_DEFAULT_FIELD_IDS,
} from './core/constants.js';

export async function renderGlobalParams() {
  const container = q('#paramsContainer');
  const configPathEl = q('#paramsConfigPath');
  const data = await apiCall('get_global_params');

  container.innerHTML = '';

  if (configPathEl) {
    configPathEl.textContent = `当前配置文件: ${data.config_path || '未知'}`;
  }

  const tierTitle = {
    basic: '基础参数',
    advanced: '高级参数',
    debug: '未开放参数',
  };

  const createTierHost = (tier, titleText, count) => {
    if (tier === 'advanced' || tier === 'debug') {
      const details = document.createElement('details');
      details.className = 'param-tier-fold';
      details.open = false;

      const summary = document.createElement('summary');
      summary.textContent = `${titleText} (${count})`;
      details.appendChild(summary);

      const body = document.createElement('div');
      body.className = 'param-tier-body';
      details.appendChild(body);
      return { host: details, body };
    }

    const title = document.createElement('div');
    title.className = 'param-tier-title';
    title.textContent = `${titleText} (${count})`;

    const body = document.createElement('div');
    body.className = 'param-tier-body';

    const frag = document.createDocumentFragment();
    frag.appendChild(title);
    frag.appendChild(body);
    return { host: frag, body };
  };

  Object.entries(data.sections).forEach(([sectionName, sectionData]) => {
    const rows = Array.isArray(sectionData.rows) ? sectionData.rows : [];
    const block = document.createElement('div');
    block.className = 'param-group';

    const title = document.createElement('h4');
    title.textContent = sectionData.title || sectionName;
    block.appendChild(title);

    ['basic', 'advanced', 'debug'].forEach((tier) => {
      if (tier === 'debug' && !state.showDebugParams) return;
      const tierRows = rows.filter((r) => (r.tier || 'basic') === tier);
      if (!tierRows.length) return;

      const { host, body } = createTierHost(tier, tierTitle[tier] || tier, tierRows.length);
      block.appendChild(host);

      tierRows.forEach((field) => {
        const item = document.createElement('div');
        item.className = 'param-item';
        item.dataset.fieldId = field.field_id;

        const head = document.createElement('div');
        head.className = 'param-head';

        const labelWrap = document.createElement('div');
        labelWrap.className = 'param-label-wrap';

        const label = document.createElement('span');
        label.className = 'param-label-cn';
        label.textContent = field.label;
        labelWrap.appendChild(label);

        const fallbackGuide = PARAM_GUIDE_FALLBACK[field.field_id] || {};
        const desc = field.desc || fallbackGuide.desc || '';
        const recommend = field.recommend || fallbackGuide.recommend || '';
        const example = field.example || fallbackGuide.example || '';

        const tip = document.createElement('div');
        tip.className = 'param-hover-tip';
        tip.innerHTML = [
          `<div><strong>变量名</strong>: ${escapeHtml(field.key)}</div>`,
          desc ? `<div><strong>说明</strong>: ${escapeHtml(desc)}</div>` : '',
          recommend ? `<div><strong>建议</strong>: ${escapeHtml(recommend)}</div>` : '',
          example ? `<div><strong>示例</strong>: ${escapeHtml(example)}</div>` : '',
        ].filter(Boolean).join('');
        labelWrap.appendChild(tip);

        if (field.hint) {
          const hintEl = document.createElement('div');
          hintEl.className = 'param-hint-line';
          hintEl.textContent = field.hint;
          labelWrap.appendChild(hintEl);
        }

        if (!HIDE_DEFAULT_FIELD_IDS.has(field.field_id)) {
          const defaultEl = document.createElement('div');
          defaultEl.className = 'param-default';
          defaultEl.textContent = `默认: ${normalizeParamTextValue(field.default)}`;
          labelWrap.appendChild(defaultEl);
        }
        head.appendChild(labelWrap);

        let input;
        if (field.type === 'bool') {
          const switchWrap = document.createElement('label');
          switchWrap.className = 'switch';
          input = document.createElement('input');
          input.type = 'checkbox';
          input.checked = Boolean(field.value);
          const slider = document.createElement('span');
          slider.className = 'switch-slider';
          switchWrap.appendChild(input);
          switchWrap.appendChild(slider);
          head.appendChild(switchWrap);
        } else if (Array.isArray(field.options) && field.options.length) {
          input = document.createElement('select');
          input.className = 'param-input';
          field.options.forEach((opt) => {
            const op = document.createElement('option');
            op.value = String(opt);
            op.textContent = String(opt);
            op.selected = String(field.value) === String(opt);
            input.appendChild(op);
          });
          head.appendChild(input);
        } else {
          if (field.type === 'list' || field.type === 'json' || field.type === 'set') {
            input = document.createElement('textarea');
            input.className = 'param-input param-textarea';
            input.rows = 3;
            input.value = normalizeParamTextValue(field.value);
          } else {
            input = document.createElement('input');
            input.className = 'param-input';
            input.type = field.type === 'int' || field.type === 'float' ? 'number' : 'text';
            if (field.type === 'float') input.step = '0.01';
            input.value = normalizeParamTextValue(field.value);
          }
          head.appendChild(input);
        }

        input.dataset.paramSection = sectionName;
        input.dataset.paramKey = field.key;
        input.dataset.paramType = field.type;
        input.dataset.fieldId = field.field_id;
        input.dataset.dependsOn = JSON.stringify(field.depends_on || []);
        input.dataset.paramLabel = field.label;
        input.dataset.currentValue = JSON.stringify(field.value);
        input.addEventListener('change', () => applyParamDependencies());
        input.addEventListener('input', () => applyParamDependencies());

        item.appendChild(head);

        if (field.field_id === 'executor.RANDOM_DELAY_ADJUST_RULES_BY_DELAY_MS') {
          const tools = document.createElement('div');
          tools.className = 'inline-actions param-inline-tools';

          const btnFill = document.createElement('button');
          btnFill.type = 'button';
          btnFill.textContent = '填入推荐分档';
          btnFill.addEventListener('click', () => {
            input.value = JSON.stringify(RECOMMENDED_RANDOM_DELAY_RULES, null, 2);
            applyParamDependencies();
          });
          tools.appendChild(btnFill);
          item.appendChild(tools);
        }

        body.appendChild(item);
      });
    });

    container.appendChild(block);
  });

  applyParamDependencies();
}

function readTypedInputValue(input) {
  const type = input.dataset.paramType;
  if (type === 'bool') return input.checked;
  if (type === 'int') return Number.parseInt(input.value || '0', 10) || 0;
  if (type === 'float') return Number(input.value || '0') || 0;
  return input.value;
}

function checkDependency(dep, valuesById) {
  const target = `${dep.section}.${dep.key}`;
  const expected = Object.prototype.hasOwnProperty.call(dep, 'value') ? dep.value : true;
  return String(valuesById[target]) === String(expected);
}

function applyParamDependencies() {
  const inputs = qa('[data-param-key]');
  const valuesById = {};
  inputs.forEach((input) => {
    valuesById[input.dataset.fieldId] = readTypedInputValue(input);
  });

  inputs.forEach((input) => {
    const deps = JSON.parse(input.dataset.dependsOn || '[]');
    const enabled = deps.every((dep) => checkDependency(dep, valuesById));
    input.disabled = !enabled;
    const row = input.closest('.param-item');
    if (row) row.classList.toggle('disabled', !enabled);
  });
}

async function saveGlobalParams() {
  const payload = {};

  const parseStructured = (rawText, type) => {
    const text = String(rawText ?? '').trim();
    if (!text) {
      if (type === 'json') return {};
      return [];
    }

    if (text.startsWith('[') || text.startsWith('{')) {
      const parsed = JSON.parse(text);
      if (type === 'json' && (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed))) {
        throw new Error('JSON 参数必须是对象');
      }
      if ((type === 'list' || type === 'set') && !Array.isArray(parsed)) {
        throw new Error('列表参数必须是 JSON 数组');
      }
      return parsed;
    }

    if (type === 'json') {
      throw new Error('JSON 参数请使用对象格式，如 {"key": "value"}');
    }

    return text.split(',').map((s) => s.trim()).filter(Boolean);
  };

  const parseByType = (input) => {
    const type = input.dataset.paramType;
    const currentValue = JSON.parse(input.dataset.currentValue || 'null');
    const text = String(input.value ?? '').trim();

    if (type === 'bool') return input.checked;
    if (type === 'int') {
      if (!text) return Number.parseInt(currentValue, 10) || 0;
      const value = Number.parseInt(text, 10);
      if (!Number.isFinite(value)) throw new Error('整数格式错误');
      return value;
    }
    if (type === 'float') {
      if (!text) return Number(currentValue) || 0;
      const value = Number(text);
      if (!Number.isFinite(value)) throw new Error('数字格式错误');
      return value;
    }
    if (type === 'list') return parseStructured(text, 'list');
    if (type === 'set') return parseStructured(text, 'set');
    if (type === 'json') return parseStructured(text, 'json');
    return input.value;
  };

  qa('[data-param-key]').forEach((input) => {
    const section = input.dataset.paramSection;
    const key = input.dataset.paramKey;

    if (!payload[section]) payload[section] = {};

    try {
      payload[section][key] = parseByType(input);
    } catch (err) {
      const label = input.dataset.paramLabel || key;
      throw new Error(`参数"${label}"格式错误: ${err.message}`);
    }
  });

  await apiCall('update_global_params', payload);
  await renderGlobalParams();
  showToast('参数已保存并写入配置');

  // 同步自动化编辑器热键
  try {
    if (payload.automation_editor) {
      var cfg = {};
      if (payload.automation_editor.HOTKEY_ENABLED !== undefined) cfg.enabled = payload.automation_editor.HOTKEY_ENABLED;
      if (payload.automation_editor.HOTKEY_RUN !== undefined) cfg.run = payload.automation_editor.HOTKEY_RUN;
      if (payload.automation_editor.HOTKEY_PAUSE !== undefined) cfg.pause = payload.automation_editor.HOTKEY_PAUSE;
      if (payload.automation_editor.HOTKEY_STOP !== undefined) cfg.stop = payload.automation_editor.HOTKEY_STOP;
      if (payload.automation_editor.HOTKEY_FULLSCREEN !== undefined) cfg.fullscreen = payload.automation_editor.HOTKEY_FULLSCREEN;
      if (Object.keys(cfg).length > 0) {
        var existing = JSON.parse(localStorage.getItem('editor_hotkeys') || '{}');
        Object.assign(existing, cfg);
        localStorage.setItem('editor_hotkeys', JSON.stringify(existing));
        if (window._autoEditor && window._autoEditor._loadEditorHotkeys) {
          window._autoEditor._loadEditorHotkeys();
        }
      }
    }
  } catch (e) {}
}

async function importGlobalParams() {
  const selected = await apiCall('choose_param_import_file');
  if (selected.canceled) return;
  if (!window.confirm(`导入参数将覆盖 config，是否继续？\n${selected.path}`)) return;

  await apiCall('import_global_params', selected.path);
  await renderGlobalParams();
  showToast('参数导入成功，已覆盖配置');
}

async function exportGlobalParams() {
  const selected = await apiCall('choose_param_export_file');
  if (selected.canceled) return;
  const ret = await apiCall('export_global_params', selected.path);
  showToast(`参数已导出: ${ret.path}`);
}

async function resetGlobalParamsToDefault() {
  if (!window.confirm('确认恢复默认参数并覆盖 config 吗？')) return;
  if (!window.confirm('请再次确认：恢复默认参数后无法撤销。')) return;

  await apiCall('reset_global_params_to_default');
  await renderGlobalParams();
  showToast('默认参数已恢复');
}

export function bindParamsActions() {
  q('#btnReloadParams').addEventListener('click', () => {
    renderGlobalParams()
      .then(() => showToast('参数已刷新'))
      .catch((err) => showToast(err.message));
  });

  q('#btnSaveParamsTop').addEventListener('click', () => {
    saveGlobalParams().catch((err) => showToast(err.message));
  });

  q('#btnSaveParamsBottom').addEventListener('click', () => {
    saveGlobalParams().catch((err) => showToast(err.message));
  });

  q('#btnImportParams').addEventListener('click', () => {
    importGlobalParams().catch((err) => showToast(err.message));
  });

  q('#btnExportParams').addEventListener('click', () => {
    exportGlobalParams().catch((err) => showToast(err.message));
  });

  q('#btnResetParams').addEventListener('click', () => {
    resetGlobalParamsToDefault().catch((err) => showToast(err.message));
  });

  q('#btnToggleDebugParams').addEventListener('click', () => {
    state.showDebugParams = !state.showDebugParams;
    q('#btnToggleDebugParams').textContent = `显示未开放参数: ${state.showDebugParams ? '开' : '关'}`;
    renderGlobalParams().catch((err) => showToast(err.message));
  });
}
