import { state } from './core/state.js';
import { q, qa, showToast } from './core/dom.js';
import { apiCall } from './core/api.js';
import { renderMacroTreeList } from './macro-tree.js';

function parseNumber(text, fallback = 0) {
  const n = Number(text);
  return Number.isFinite(n) ? n : fallback;
}

function normalizeHotkeyName(raw) {
  return String(raw ?? '').trim().toLowerCase();
}

function ensureRecordServiceRunning(actionLabel = '该操作') {
  if (state.recordServiceRunning) return true;
  showToast(`请先启动录制监听，再执行${actionLabel}`);
  return false;
}

function applyRecordButtonUi() {
  const btn = q('#btnStartRecSvc');
  if (!btn) return;

  const running = Boolean(state.recordServiceRunning);
  btn.textContent = running ? '关闭录制监听' : '启动录制监听';
  btn.classList.toggle('success', running);
}

function applyRecordHotkeyTooltips() {
  const hk = state.recordHotkeys;
  const fmt = (key) => (key ? `快捷键: ${key}` : '快捷键: 已关闭');

  const btnStart = q('#btnStartRecSvc');
  const btnArm = q('#btnArmRec');
  const btnStop = q('#btnStopRec');
  const btnSave = q('#btnSaveRec');
  const btnClear = q('#btnClearRec');

  if (btnStart) btnStart.title = `切换录制监听服务。${fmt(hk.toggle_service)}`;
  if (btnArm) btnArm.title = `开始录制布防。${fmt(hk.arm)}`;
  if (btnStop) btnStop.title = `停止录制。${fmt(hk.stop)}`;
  if (btnSave) btnSave.title = `保存录制结果。${fmt(hk.save)}`;
  if (btnClear) btnClear.title = `清空录制缓存。${fmt(hk.clear)}`;
}

export async function refreshRecordControls() {
  try {
    const [svc, hk] = await Promise.all([
      apiCall('get_recorder_service_state'),
      apiCall('get_record_hotkeys'),
    ]);
    state.recordServiceRunning = Boolean(svc.running);
    state.recordHotkeys = {
      toggle_service: normalizeHotkeyName(hk.toggle_service),
      arm: normalizeHotkeyName(hk.arm),
      stop: normalizeHotkeyName(hk.stop),
      save: normalizeHotkeyName(hk.save),
      clear: normalizeHotkeyName(hk.clear),
    };
    applyRecordButtonUi();
    applyRecordHotkeyTooltips();
  } catch (err) {
    console.error(err);
  }
}

function setRecordPathInput(path) {
  const target = q(`#${state.activeRecordPathInput}`) || q('#simplifyInput');
  if (!target) return;
  target.value = path;
  target.dispatchEvent(new Event('change'));
}

export function renderRecordMacroBrowser() {
  const list = q('#recordMacroList');
  renderMacroTreeList({
    container: list,
    tree: state.macroTree,
    viewId: 'record',
    selectedPath: null,
    openedPath: null,
    onFill: (path) => {
      setRecordPathInput(path);
      showToast(`已填入路径: ${path}`);
    },
  });
}

export function bindRecorderActions() {
  q('#btnStartRecSvc').addEventListener('click', async () => {
    if (state.recordServiceRunning) {
      await apiCall('stop_recorder_service');
      state.recordServiceRunning = false;
      applyRecordButtonUi();
      showToast('录制监听已关闭');
      return;
    }

    await apiCall('start_recorder_service');
    state.recordServiceRunning = true;
    applyRecordButtonUi();
    showToast('录制监听已启动');
  });

  q('#btnArmRec').addEventListener('click', async () => {
    if (!ensureRecordServiceRunning('开始录制')) return;
    const mode = q('#recordStartMode').value;
    const delay = parseNumber(q('#recordDelay').value, 0.2);
    await apiCall('arm_recording', mode, delay);
    showToast('录制已布防');
  });

  q('#btnStopRec').addEventListener('click', async () => {
    if (!ensureRecordServiceRunning('停止录制')) return;
    await apiCall('stop_recording');
    showToast('录制已停止');
  });

  q('#btnSaveRec').addEventListener('click', async () => {
    if (!ensureRecordServiceRunning('保存录制')) return;
    const targets = await apiCall('get_recording_output_targets');
    const existsAndHasContent = (targets.items || []).filter((item) => item.has_content);
    if (existsAndHasContent.length) {
      const msg = existsAndHasContent
        .map((item) => `${item.path} (${item.row_count} 条)`).join('\n');
      const ok = window.confirm(`将覆盖以下已有录制文件:\n${msg}\n\n是否继续保存？`);
      if (!ok) return;
    }
    await apiCall('save_recording');
    showToast('录制结果已保存');
    const { refreshMacros } = await import('./macro-bind.js');
    await refreshMacros();
  });

  q('#btnClearRec').addEventListener('click', async () => {
    if (!ensureRecordServiceRunning('清空缓存')) return;
    await apiCall('clear_recording_buffer');
    showToast('录制缓存已清空');
  });

  q('#btnSimplify').addEventListener('click', async () => {
    const inputPath = q('#simplifyInput').value.trim();
    const outputPath = q('#simplifyOutput').value.trim();
    const preset = q('#presetSelect').value;
    if (!inputPath || !outputPath) return showToast('请填写输入与输出路径');

    const ret = await apiCall('simplify_macro_with_preset', inputPath, outputPath, preset);
    showToast(`化简完成: ${ret.path}`);
    const { refreshMacros } = await import('./macro-bind.js');
    await refreshMacros();
  });

  q('#btnMerge').addEventListener('click', async () => {
    const actionPath = q('#mergeAction').value.trim();
    const trackPath = q('#mergeTrack').value.trim();
    const outputPath = q('#mergeOutput').value.trim();
    const preset = q('#presetSelect').value;

    if (!actionPath || !trackPath || !outputPath) {
      return showToast('请填写动作宏、轨迹宏和输出路径');
    }

    const ret = await apiCall('merge_action_track_with_preset', actionPath, trackPath, outputPath, preset);
    showToast(`合并完成: ${ret.path}`);
    const { refreshMacros } = await import('./macro-bind.js');
    await refreshMacros();
  });

  q('#btnRefreshRecordMacroBrowser').addEventListener('click', async () => {
    const { refreshMacros } = await import('./macro-bind.js');
    await refreshMacros();
    showToast('录制区宏文件夹已刷新');
  });

  qa('.record-path-input').forEach((input) => {
    input.addEventListener('focus', () => {
      state.activeRecordPathInput = input.id;
    });

    input.addEventListener('dragover', (e) => {
      e.preventDefault();
      input.classList.add('drop-over');
    });

    input.addEventListener('dragleave', () => {
      input.classList.remove('drop-over');
    });

    input.addEventListener('drop', (e) => {
      e.preventDefault();
      input.classList.remove('drop-over');
      const macroPath = e.dataTransfer.getData('text/macro-path') || e.dataTransfer.getData('text/plain');
      if (!macroPath) return;
      input.value = macroPath;
      input.dispatchEvent(new Event('change'));
      showToast(`已填入路径: ${macroPath}`);
    });
  });
}
