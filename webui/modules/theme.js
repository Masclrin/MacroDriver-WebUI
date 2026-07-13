import { apiCall } from './core/api.js';

const THEME_KEY = 'ui_theme';
const THEME_LIGHT = 'light';
const THEME_DARK = 'dark';

export function applyTheme(isLight) {
  const root = document.documentElement;
  root.classList.toggle('theme-light', !!isLight);
  try {
    localStorage.setItem(THEME_KEY, isLight ? THEME_LIGHT : THEME_DARK);
  } catch (e) {}
  notifyAutomationEditor(isLight);
}

export function readLocalTheme() {
  try {
    return localStorage.getItem(THEME_KEY) === THEME_LIGHT;
  } catch (e) {
    return false;
  }
}

function notifyAutomationEditor(isLight) {
  try {
    const frame = document.getElementById('automationFrame');
    if (frame && frame.contentWindow) {
      frame.contentWindow.postMessage({
        source: 'macro-forge-host',
        type: 'theme-change',
        theme: isLight ? THEME_LIGHT : THEME_DARK,
      }, '*');
    }
  } catch (e) {}
}

export async function initThemeFromServer() {
  try {
    const data = await apiCall('get_global_params');
    const webuiSection = data && data.sections && data.sections.webui;
    if (!webuiSection) return;
    const row = (webuiSection.rows || []).find((r) => r.key === 'UI_THEME_LIGHT');
    if (!row) return;
    applyTheme(Boolean(row.value));
  } catch (e) {}
}
