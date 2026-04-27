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
