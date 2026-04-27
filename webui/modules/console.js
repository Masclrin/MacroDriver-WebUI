import { state } from './core/state.js';
import { q, showToast } from './core/dom.js';
import { apiCall } from './core/api.js';

function maybeToastStatusFromConsole(text) {
  const line = String(text || '').trim();
  if (!line.startsWith('>>> [状态]')) return;

  const mapping = [
    { key: 'stop', raw: '>>> [状态] 已停止录制', toast: '录制已停止（快捷键）' },
    { key: 'clear', raw: '>>> [状态] 已清空录制缓存', toast: '录制缓存已清空（快捷键）' },
    { key: 'arm', raw: '>>> [状态] 已布防', toast: '录制已布防（快捷键）' },
    { key: 'start', raw: '>>> [状态] 开始录制', toast: '录制已开始' },
  ];

  const hit = mapping.find((item) => line.startsWith(item.raw));
  if (!hit) return;

  const now = Date.now();
  const lastTs = Number(state.statusToastTs[hit.key] || 0);
  if (now - lastTs < 450) return;
  state.statusToastTs[hit.key] = now;
  showToast(hit.toast, 1800);
}

export async function pollConsole() {
  if (state.pollConsoleBusy) return;
  state.pollConsoleBusy = true;
  try {
    const data = await apiCall('poll_console', state.consoleLastId, 120);
    const entries = data.entries || [];
    if (!entries.length) return;

    const pre = q('#consoleOutput');
    entries.forEach((item) => {
      pre.textContent += `[${item.ts}] ${item.text}\n`;
      state.consoleLineCount += 1;
      maybeToastStatusFromConsole(item.text);
    });
    state.consoleLastId = data.latest_id || state.consoleLastId;

    if (state.consoleLineCount > 4000) {
      const lines = pre.textContent.split('\n');
      const tail = lines.slice(-3200).join('\n');
      pre.textContent = tail;
      state.consoleLineCount = tail.split('\n').length;
    }

    pre.scrollTop = pre.scrollHeight;
  } catch (err) {
    console.error(err);
  } finally {
    state.pollConsoleBusy = false;
  }
}

export async function clearConsole() {
  await apiCall('clear_console');
  state.consoleLastId = 0;
  state.consoleLineCount = 0;
  q('#consoleOutput').textContent = '';
  showToast('控制台已清空');
}
