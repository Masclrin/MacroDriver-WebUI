export function normalizeParamTextValue(v) {
  if (Array.isArray(v) || (typeof v === 'object' && v !== null)) {
    return JSON.stringify(v);
  }
  return String(v ?? '');
}

export function escapeHtml(text) {
  return String(text ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}
