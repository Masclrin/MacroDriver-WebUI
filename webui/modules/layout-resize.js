// 可拖拽分栏：给 2 列网格（.grid-2）在中间插入一条竖直拖拽条，
// 拖动时左右两张卡片联动收缩/扩张；双击拖拽条恢复默认比例。
// 结果按容器持久化到 localStorage。

export function enableResizableGrid(gridEl, options = {}) {
  if (!gridEl) return false;
  if (gridEl.dataset.splitterReady === '1') return true;

  const children = Array.from(gridEl.children).filter((el) => el.nodeType === 1);
  if (children.length !== 2) return false;

  // 窄屏为单列布局，不启用分栏
  if (window.innerWidth <= 700) return false;

  gridEl.dataset.splitterReady = '1';
  gridEl.classList.add('with-splitter');

  const splitter = document.createElement('div');
  splitter.className = 'grid-splitter';
  splitter.title = '拖动调整左右宽度（双击恢复默认）';
  gridEl.insertBefore(splitter, children[1]);

  const MIN = options.min || 240;
  const SPLITTER_W = 6;
  const key = options.storageKey || `ui_split_${gridEl.id || 'grid'}`;

  const gapOf = () => parseFloat(getComputedStyle(gridEl).columnGap) || 12;

  const apply = (left, right) => {
    gridEl.style.setProperty('--split-l', `${Math.round(left)}px`);
    gridEl.style.setProperty('--split-r', `${Math.round(right)}px`);
  };

  const totalUsable = () => gridEl.clientWidth - SPLITTER_W - gapOf() * 2;

  const restore = () => {
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(key) || 'null'); } catch (e) { saved = null; }
    if (saved && Number.isFinite(saved.l)) {
      const total = totalUsable();
      const left = Math.max(MIN, Math.min(saved.l, total - MIN));
      apply(left, Math.max(MIN, total - left));
      return true;
    }
    return false;
  };
  restore();

  let dragging = false;

  splitter.addEventListener('pointerdown', (e) => {
    dragging = true;
    splitter.classList.add('dragging');
    try { splitter.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
    e.preventDefault();
  });

  splitter.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    const rect = gridEl.getBoundingClientRect();
    const gap = gapOf();
    const total = rect.width - SPLITTER_W - gap * 2;
    let left = e.clientX - rect.left - gap - SPLITTER_W / 2;
    left = Math.max(MIN, Math.min(left, total - MIN));
    apply(left, Math.max(MIN, total - left));
  });

  const end = () => {
    if (!dragging) return;
    dragging = false;
    splitter.classList.remove('dragging');
    try {
      const l = parseFloat(getComputedStyle(gridEl).getPropertyValue('--split-l'));
      if (Number.isFinite(l)) localStorage.setItem(key, JSON.stringify({ l }));
    } catch (e) { /* ignore */ }
  };
  splitter.addEventListener('pointerup', end);
  splitter.addEventListener('pointercancel', end);

  // 双击恢复默认 1:1.18
  splitter.addEventListener('dblclick', () => {
    gridEl.style.removeProperty('--split-l');
    gridEl.style.removeProperty('--split-r');
    try { localStorage.removeItem(key); } catch (e) { /* ignore */ }
  });

  // 窗口变化时重新钳制，避免卡片被挤到最小宽以下
  let ro = null;
  try {
    ro = new ResizeObserver(() => {
      if (dragging) return;
      const total = totalUsable();
      if (total <= MIN * 2) return;
      const style = getComputedStyle(gridEl);
      let left = parseFloat(style.getPropertyValue('--split-l'));
      if (!Number.isFinite(left)) return;
      left = Math.max(MIN, Math.min(left, total - MIN));
      apply(left, Math.max(MIN, total - left));
    });
    ro.observe(gridEl);
  } catch (e) { /* ignore */ }

  return true;
}
