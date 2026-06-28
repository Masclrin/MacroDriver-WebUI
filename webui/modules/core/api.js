export async function apiCall(method, ...args) {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api[method]) {
    throw new Error(`API 不可用: ${method}`);
  }
  const result = await window.pywebview.api[method](...args);
  if (!result || result.ok === false) {
    const message = result && result.error ? result.error : `调用失败: ${method}`;
    const detail = result && result.detail ? String(result.detail) : '';
    throw new Error(detail ? `${message}: ${detail}` : message);
  }
  return result;
}
