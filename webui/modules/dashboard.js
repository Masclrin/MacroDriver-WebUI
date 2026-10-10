import { state } from './core/state.js';
import { q } from './core/dom.js';
import { apiCall } from './core/api.js';

export async function refreshSnapshot() {
  try {
    const data = await apiCall('get_dashboard_snapshot');
    q('#statActive').textContent = String(data.active_macros || 0);
    q('#statPaused').textContent = data.global_paused ? '是' : '否';

    const rec = data.recording || {};
    q('#statRec').textContent = rec.is_recording ? '录制中' : rec.is_armed ? '已布防' : '空闲';
    q('#statRecCount').textContent = `${rec.action_count || 0} / ${rec.track_count || 0}`;
  } catch (err) {
    console.error(err);
  }
}

export async function refreshListenerButtonState() {
  try {
    const data = await apiCall('get_listener_state');
    q('#btnStartListeners').textContent = data.running ? '关闭全局宏监听' : '启动全局宏监听';
  } catch (err) {
    console.error(err);
  }
}
