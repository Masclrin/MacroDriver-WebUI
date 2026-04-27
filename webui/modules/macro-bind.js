import { state } from './core/state.js';
import { q, qa, showToast } from './core/dom.js';
import { apiCall } from './core/api.js';
import { renderMacroTreeList } from './macro-tree.js';

function parseNumber(text, fallback = 0) {
  const n = Number(text);
  return Number.isFinite(n) ? n : fallback;
}

function syncRuntimeProfileUI() {
  q('#macroSpeedFactor').value = String(state.runtimeProfile.speed_factor ?? 1);
  q('#macroRandomMin').value = String(state.runtimeProfile.random_min_ms ?? 0);
  q('#macroRandomMax').value = String(state.runtimeProfile.random_max_ms ?? 0);
  q('#btnMacroRandomToggle').textContent = `随机延迟: ${state.runtimeProfile.random_enabled ? '开' : '关'}`;
  q('#btnLowCpuModeToggle').textContent = `CPU低占用: ${state.runtimeProfile.low_cpu_enabled ? '开' : '关'}`;
  const timePeriodBtn = q('#btnTimePeriodToggle');
  timePeriodBtn.textContent = `时器分辨率(1): ${state.runtimeProfile.low_cpu_time_period ? '开' : '关'}`;
  timePeriodBtn.style.display = state.runtimeProfile.low_cpu_enabled ? '' : 'none';
}

export async function refreshMacroRuntimeProfile() {
  const data = await apiCall('get_macro_runtime_profile');
  state.runtimeProfile = {
    speed_factor: data.speed_factor,
    random_enabled: data.random_enabled,
    random_min_ms: data.random_min_ms,
    random_max_ms: data.random_max_ms,
    low_cpu_enabled: Boolean(data.low_cpu_enabled),
    low_cpu_time_period: Boolean(data.low_cpu_time_period),
  };
  syncRuntimeProfileUI();
}

async function applyMacroRuntimeProfile() {
  const payload = {
    speed_factor: parseNumber(q('#macroSpeedFactor').value, 1),
    random_enabled: Boolean(state.runtimeProfile.random_enabled),
    random_min_ms: parseNumber(q('#macroRandomMin').value, 0),
    random_max_ms: parseNumber(q('#macroRandomMax').value, 0),
    low_cpu_enabled: Boolean(state.runtimeProfile.low_cpu_enabled),
    low_cpu_time_period: Boolean(state.runtimeProfile.low_cpu_time_period),
  };
  const ret = await apiCall('update_macro_runtime_profile', payload);
  state.runtimeProfile = {
    speed_factor: ret.speed_factor,
    random_enabled: ret.random_enabled,
    random_min_ms: ret.random_min_ms,
    random_max_ms: ret.random_max_ms,
    low_cpu_enabled: Boolean(ret.low_cpu_enabled),
    low_cpu_time_period: Boolean(ret.low_cpu_time_period),
  };
  syncRuntimeProfileUI();
  showToast('执行参数已应用');
}

export function renderMacroList() {
  const list = q('#macroList');
  renderMacroTreeList({
    container: list,
    tree: state.macroTree,
    viewId: 'macro',
    selectedPath: state.selectedMacro,
    openedPath: null,
    onSelect: (path) => {
      state.selectedMacro = path;
      q('#selectedMacroPath').value = path;
      q('#simplifyInput').value = path;
      renderMacroList();
      if (state.onSelectMacroForEditor) {
        state.onSelectMacroForEditor(path).catch((err) => showToast(err.message));
      }
    },
  });
}

export async function refreshMacros() {
  const keyword = q('#macroFilter').value.trim();
  try {
    const data = await apiCall('list_macro_tree', keyword);
    state.macros = data.items || [];
    state.macroTree = data.tree || { name: '宏', path: '宏', folders: [], files: [] };
  } catch (err) {
    state.macros = [];
    state.macroTree = { name: '宏', path: '宏', folders: [], files: [] };
  }

  if (state.selectedMacro && !state.macros.some((m) => m.path === state.selectedMacro)) {
    state.selectedMacro = null;
    q('#selectedMacroPath').value = '';
  }

  renderMacroList();

  const { renderEditorMacroBrowser } = await import('./editor.js');
  const { renderRecordMacroBrowser } = await import('./recorder.js');
  renderEditorMacroBrowser();
  renderRecordMacroBrowser();
}

function renderBindings(items) {
  const list = q('#bindingList');
  list.innerHTML = '';

  items.forEach((row) => {
    const li = document.createElement('li');
    li.classList.toggle('running', Number(row.live_count || 0) > 0);

    const left = document.createElement('div');
    left.className = 'binding-left';
    const macroPaths = Array.isArray(row.macro_paths) && row.macro_paths.length
      ? row.macro_paths
      : (row.macro_path ? [row.macro_path] : []);
    const macroDisplay = macroPaths.join(' + ');
    const statusText = Number(row.live_count || 0) > 0
      ? `运行中 ${row.live_count}`
      : Number(row.stopping_count || 0) > 0
        ? '停止中'
        : '空闲';
    left.textContent = `${row.trigger} -> ${macroDisplay} | repeat=${row.repeat} | ${row.running_press_mode} | ${statusText}`;

    const actions = document.createElement('div');
    actions.className = 'inline-actions binding-actions';

    const btnRun = document.createElement('button');
    btnRun.textContent = '触发';
    btnRun.addEventListener('click', async (e) => {
      e.stopPropagation();
      await apiCall('trigger_macro', row.trigger);
      showToast(`已触发: ${row.trigger}`);
      refreshBindings();
    });

    const btnUnbind = document.createElement('button');
    btnUnbind.className = 'danger';
    btnUnbind.textContent = '解绑';
    btnUnbind.addEventListener('click', async (e) => {
      e.stopPropagation();
      await apiCall('unbind_macro', row.trigger);
      showToast(`已解绑: ${row.trigger}`);
      refreshBindings();
    });

    actions.appendChild(btnRun);
    actions.appendChild(btnUnbind);

    li.appendChild(left);
    li.appendChild(actions);
    list.appendChild(li);
  });
}

export async function refreshBindings() {
  const data = await apiCall('list_bindings');
  renderBindings(data.items || []);
}

export function bindMacroActions() {
  q('#btnRefreshMacros').addEventListener('click', () => {
    refreshMacros()
      .then(() => showToast('宏列表已刷新'))
      .catch((err) => showToast(err.message));
  });

  q('#macroFilter').addEventListener('input', () => {
    refreshMacros().catch((err) => showToast(err.message));
  });

  q('#btnMacroRandomToggle').addEventListener('click', () => {
    state.runtimeProfile.random_enabled = !state.runtimeProfile.random_enabled;
    syncRuntimeProfileUI();
  });

  q('#btnLowCpuModeToggle').addEventListener('click', () => {
    state.runtimeProfile.low_cpu_enabled = !state.runtimeProfile.low_cpu_enabled;
    syncRuntimeProfileUI();
  });

  q('#btnTimePeriodToggle').addEventListener('click', () => {
    state.runtimeProfile.low_cpu_time_period = !state.runtimeProfile.low_cpu_time_period;
    syncRuntimeProfileUI();
  });

  q('#btnApplyRuntimeProfile').addEventListener('click', () => {
    applyMacroRuntimeProfile().catch((err) => showToast(err.message));
  });

  q('#btnCreateMacro').addEventListener('click', async () => {
    const name = window.prompt('输入新宏文件名', '新建宏.json');
    if (!name) return;
    const res = await apiCall('create_macro', '宏/录制宏', name);
    showToast(`已创建: ${res.path}`);
    await refreshMacros();
  });

  q('#btnDeleteMacro').addEventListener('click', async () => {
    if (!state.selectedMacro) return showToast('请先选择一个宏文件');
    if (!window.confirm(`确认删除 ${state.selectedMacro} ?`)) return;

    await apiCall('delete_macro', state.selectedMacro);
    showToast('已删除宏文件');
    state.selectedMacro = null;
    state.editorRows = [];
    if (state.renderActionList) state.renderActionList();
    await refreshMacros();
    await refreshBindings();
  });

  q('#btnCaptureKey').addEventListener('click', async () => {
    showToast('请在 8 秒内按下键盘或鼠标侧键');
    const res = await apiCall('capture_next_binding', 8);
    if (res.canceled) {
      showToast('采集超时，未捕获输入');
      return;
    }
    q('#bindTrigger').value = res.key || '';
    showToast(`已捕获: ${res.key}`);
  });

  q('#btnBindMacro').addEventListener('click', async () => {
    const macroPath = state.selectedMacro || q('#selectedMacroPath').value.trim();
    if (!macroPath) return showToast('请先选择宏文件');

    const trigger = q('#bindTrigger').value.trim();
    const repeat = parseNumber(q('#bindRepeat').value, 1);
    const mode = q('#bindMode').value;
    if (!trigger) return showToast('请输入触发键');

    const ret = await apiCall('bind_macro', trigger, macroPath, repeat, mode);
    if (ret.already_bound) {
      showToast(`已存在同名绑定: ${trigger}`);
    } else if (ret.replaced_existing && !ret.multi_bind_enabled) {
      showToast(`已覆盖触发键原绑定并重新绑定: ${trigger}`);
    } else if (ret.append) {
      showToast(`已追加到触发键: ${trigger}`);
    } else {
      showToast(`绑定成功: ${trigger}`);
    }
    await refreshBindings();
  });

  q('#btnRunNow').addEventListener('click', async () => {
    const trigger = q('#bindTrigger').value.trim();
    if (!trigger) return showToast('请先输入触发键');
    await apiCall('trigger_macro', trigger);
    showToast(`已触发 ${trigger}`);
    refreshBindings();
  });

  q('#btnStartListeners').addEventListener('click', async () => {
    const ret = await apiCall('toggle_global_listeners');
    q('#btnStartListeners').textContent = ret.running ? '关闭全局宏监听' : '启动全局宏监听';
    showToast(ret.running ? '全局监听已启动' : '全局监听已关闭');
  });

  q('#btnGlobalPause').addEventListener('click', async () => {
    const ret = await apiCall('toggle_global_pause');
    showToast(ret.paused ? '全局暂停已开启' : '全局暂停已解除');
    const { refreshSnapshot } = await import('./dashboard.js');
    await refreshSnapshot();
  });

  q('#btnStopAll').addEventListener('click', async () => {
    await apiCall('stop_all_macros');
    showToast('已停止全部宏');
    await refreshBindings();
  });

  q('#btnImportFolder').addEventListener('click', async () => {
    const pick = await apiCall('choose_import_folder');
    if (pick.canceled) return;

    const ret = await apiCall('import_macros_from_folder', pick.path);
    showToast(`已导入 ${ret.count} 个宏文件`);
    await refreshMacros();
  });
}
