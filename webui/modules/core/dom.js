let _toastTimer = null;

export function q(selector) {
  return document.querySelector(selector);
}

export function qa(selector) {
  return Array.from(document.querySelectorAll(selector));
}

export function showToast(text, timeout = 2800) {
  const box = q('#toast');
  box.textContent = text;
  box.classList.remove('hidden');
  if (_toastTimer) {
    clearTimeout(_toastTimer);
  }
  _toastTimer = setTimeout(() => {
    box.classList.add('hidden');
    _toastTimer = null;
  }, timeout);
}

let _importPanelTimer = null;

export function showImportResultPanel(data) {
  let panel = q('#importResultPanel');
  if (!panel) {
    panel = document.createElement('div');
    panel.id = 'importResultPanel';
    panel.className = 'import-result-panel';
    document.body.appendChild(panel);
  }

  if (_importPanelTimer) {
    clearTimeout(_importPanelTimer);
    _importPanelTimer = null;
  }

  const results = data.results || [];
  const successCount = data.success_count || 0;
  const skippedCount = data.skipped_count || 0;
  const failedCount = data.failed_count || 0;

  const statusIcon = { success: '\u2705', skipped: '\u26a0\ufe0f', failed: '\u274c' };
  const statusLabel = { success: '\u6210\u529f', skipped: '\u8df3\u8fc7', failed: '\u5931\u8d25' };

  let html = '<div class="import-result-header">';
  html += '<span>\u591a\u683c\u5f0f\u5bfc\u5165\u7ed3\u679c</span>';
  html += '<button class="import-result-close" onclick="document.getElementById(\'importResultPanel\').classList.add(\'hidden\')">\u2715</button>';
  html += '</div>';

  html += '<ul class="import-result-list">';
  for (const r of results) {
    const icon = statusIcon[r.status] || '\u2753';
    const label = statusLabel[r.status] || r.status;
    html += `<li class="import-result-item import-result-${r.status}">`;
    html += `<span class="import-result-icon">${icon}</span>`;
    html += `<span class="import-result-file">${r.file}</span>`;
    html += `<span class="import-result-label">${label}</span>`;
    if (r.message) {
      html += `<span class="import-result-msg">${r.message}</span>`;
    }
    html += '</li>';
  }
  html += '</ul>';

  html += '<div class="import-result-summary">';
  html += `\u6210\u529f ${successCount} \u4e2a\uff0c\u8df3\u8fc7 ${skippedCount} \u4e2a\uff0c\u5931\u8d25 ${failedCount} \u4e2a`;
  html += '</div>';

  panel.innerHTML = html;
  panel.classList.remove('hidden');

  _importPanelTimer = setTimeout(() => {
    panel.classList.add('hidden');
    _importPanelTimer = null;
  }, 8000);
}
