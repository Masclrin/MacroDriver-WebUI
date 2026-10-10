// 测试点标记的「就地刷新」（不重建列表）。
// 单独成文件，避免 action-list-render ↔ inline-editor 之间形成循环导入。
export function updateBpVisual(view) {
  const list = view && view.listEl;
  if (!list) return;
  list.querySelectorAll('.action-index.bp-toggle[data-bp-path]').forEach((el) => {
    const on = !!(view.breakpoints && view.breakpoints.has(el.dataset.bpPath));
    el.classList.toggle('on', on);
    const n = el.textContent;
    el.title = on
      ? `第 ${n} 行已是测试点 —— 点击取消`
      : `把第 ${n} 行设为测试点（可从测试点运行到此）`;
  });
}
