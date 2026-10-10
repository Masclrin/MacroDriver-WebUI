import { state } from './core/state.js';
import { q } from './core/dom.js';
import { apiCall } from './core/api.js';

export async function refreshSnapshot() {
  try {
    const data = await apiCall('get_dashboard_snapshot');
    q('#statActive').textContent = String(data.active_macros || 0);
    q('#statPaused').textContent = data.global_paused ? '是' : '否';
    const pauseLabel = q('#btnGlobalPause').querySelector('.btn-label');
    if (pauseLabel) pauseLabel.textContent = data.global_paused ? '关闭全局暂停 ⏸' : '开启全局暂停 ▶';
    q('#btnGlobalPause').classList.toggle('pause-active', !!data.global_paused);

    const rec = data.recording || {};
    q('#statRec').textContent = rec.is_recording ? '录制中' : rec.is_armed ? '已布防' : '空闲';
    q('#statRecCount').textContent = `${rec.action_count || 0} / ${rec.track_count || 0}`;
  } catch (err) {
    console.error(err);
  }
  await refreshEngineSummary();
}

export async function refreshEngineSummary() {
  const profileEl = q('#statProfile');
  const standbyEl = q('#statStandby');
  if (!profileEl && !standbyEl) return;
  try {
    const data = await apiCall('get_engine_summary');
    if (profileEl) {
      profileEl.textContent = data.precision_profile_label || data.precision_profile || '—';
      profileEl.title = `精度/占用档位: ${data.precision_profile || '—'}\n进程优先级: ${data.process_priority_now || '—'}`
        + `\n共享帧缓存有效期: ${data.frame_cache_ttl_ms > 0 ? data.frame_cache_ttl_ms + ' ms' : '档位默认'}`;
    }
    if (standbyEl) {
      let text;
      if (!data.standby_enabled) {
        text = '已关闭';
      } else if (data.standby_available === false) {
        text = '不可用(回退)';
      } else if (data.standby_available === true) {
        text = '已加载';
      } else {
        text = '已启用';
      }
      standbyEl.textContent = text;
      standbyEl.classList.toggle('warn-text', data.standby_enabled && data.standby_available === false);
      standbyEl.title = 'Standby 工业级精度引擎(全局开关)\n'
        + `全局开关: ${data.standby_enabled ? '开' : '关'}\n`
        + `native 扩展: ${data.standby_available === true ? '已加载' : data.standby_available === false ? '未加载(将回退 Python 路径)' : '未知'}\n`
        + '节点级可在自动化编辑器「调用宏」节点内用 Standby引擎 下拉单独覆盖';
    }
  } catch (err) {
    if (profileEl) profileEl.textContent = '—';
    if (standbyEl) standbyEl.textContent = '—';
  }
}

export async function refreshListenerButtonState() {
  try {
    const data = await apiCall('get_listener_state');
    const listenLabel = q('#btnStartListeners').querySelector('.btn-label');
    if (listenLabel) listenLabel.textContent = data.running ? '关闭全局宏监听 ◉' : '启动全局宏监听 ○';
    q('#btnStartListeners').classList.toggle('primary', !!data.running);
    q('#btnStartListeners').classList.toggle('primary-dim', !data.running);
    q('#btnStartListeners').classList.toggle('active-glow', !!data.running);
  } catch (err) {
    console.error(err);
  }
  
}
