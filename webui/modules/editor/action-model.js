export function parseNumber(text, fallback = 0) {
  const n = Number(text);
  return Number.isFinite(n) ? n : fallback;
}

export function isFrameDelay(raw) {
  return typeof raw === 'string' && /^\d+f$/i.test(raw.trim());
}
export function parseDelay(raw, fallback = 50) {
  if (isFrameDelay(raw)) return raw.trim().toLowerCase();
  const n = Number(raw);
  return Number.isFinite(n) && n >= 0 ? n : fallback;
}
export function formatDelay(delay) {
  if (isFrameDelay(delay)) return `${delay.trim().toLowerCase()}帧`;
  return `${Math.max(0, Number(delay) || 0)}ms`;
}

export function pathKey(path) {
  return Array.isArray(path) ? path.join('.') : '';
}

export function keyToPath(key) {
  if (!key) return null;
  return String(key)
    .split('.')
    .filter((part) => part.length > 0)
    .map((part) => Number.parseInt(part, 10))
    .filter((num) => Number.isInteger(num) && num >= 0);
}

export function cloneAction(action) {
  return JSON.parse(JSON.stringify(action));
}

// 未被识别的原始行（解析层无法还原为指令数组时保留原文，便于直接编辑/修复）。
// 内存形态：{ __raw: "<原始文本>" }；保存时原样写回，绝不因无法解析而丢失内容。
export function isRawRow(row) {
  return !!row && typeof row === 'object' && !Array.isArray(row) && typeof row.__raw === 'string';
}

export function makeRawRow(text) {
  return { __raw: String(text == null ? '' : text) };
}

export function isLoopAction(action) {
  return Array.isArray(action)
    && action.length >= 3
    && String(action[0]).trim().toLowerCase() === 'loop'
    && Array.isArray(action[2]);
}

export function normalizeAction(action) {
  if (isRawRow(action)) {
    return { __raw: String(action.__raw) };
  }
  if (!Array.isArray(action) || !action.length) {
    return ['wait', 50];
  }

  const cmd = String(action[0]).trim().toLowerCase();

  if (cmd === 'loop') {
    const count = Math.max(1, parseNumber(action[1], 1));
    const block = Array.isArray(action[2]) ? action[2].map((row) => normalizeAction(row)) : [];
    return ['loop', count, block];
  }

  if (cmd === 'view') {
    const vec = Array.isArray(action[1]) ? action[1] : [0, 0];
    return ['view', [parseNumber(vec[0], 0), parseNumber(vec[1], 0)], Math.max(1, parseNumber(action[2], 50))];
  }

  if (cmd === 'move_to') {
    return ['move_to', parseNumber(action[1], 0), parseNumber(action[2], 0), Math.max(0, parseNumber(action[3], 150))];
  }

  if (cmd === 'scroll') {
    return ['scroll', parseNumber(action[1], 0)];
  }

  if (cmd === 'ext') {
    return ['ext', String(action[1] ?? '').trim(), ...action.slice(2)];
  }

  if (cmd === 'wait') {
    return ['wait', parseDelay(action[1], 50)];
  }

  if (cmd === 'import') {
    return ['import', String(action[1] ?? '').trim()];
  }

  if (cmd === 'note') {
    return ['note', String(action[1] ?? '').trim()];
  }

  if (['kd', 'ku', 'md', 'mu'].includes(cmd)) {
    const fallbackKey = cmd === 'md' || cmd === 'mu' ? 'left' : 'w';
    return [cmd, String(action[1] ?? fallbackKey), parseDelay(action[2], 50)];
  }

  return cloneAction(action);
}

export function normalizeMacroRows(rows) {
  if (!Array.isArray(rows)) return [];
  return rows
    .filter((row) => Array.isArray(row) || isRawRow(row))
    .map((row) => normalizeAction(row));
}

export function formatActionLabel(action, expanded) {
  if (isRawRow(action)) {
    const text = String(action.__raw).trim();
    return `⚠ 原文（未识别）：${text.length > 120 ? text.slice(0, 120) + '…' : text}`;
  }
  const cmd = String(action[0] ?? '').trim().toLowerCase();

  if (cmd === 'wait') {
    return `wait ${formatDelay(action[1])}`;
  }
  if (cmd === 'view') {
    const vec = Array.isArray(action[1]) ? action[1] : [0, 0];
    return `view [${parseNumber(vec[0], 0)}, ${parseNumber(vec[1], 0)}] ${Math.max(1, parseNumber(action[2], 50))}ms`;
  }
  if (cmd === 'move_to') {
    return `move_to (${parseNumber(action[1], 0)}, ${parseNumber(action[2], 0)}) ${Math.max(0, parseNumber(action[3], 150))}ms`;
  }
  if (cmd === 'scroll') {
    return `scroll ${parseNumber(action[1], 0)}`;
  }
  if (cmd === 'ext') {
    const args = Array.isArray(action) ? action.slice(2) : [];
    const argsText = args.length
      ? ' ' + args.map((a) => (typeof a === 'string' ? a : JSON.stringify(a))).join(' ')
      : '';
    return `ext › ${String(action[1] ?? '')}${argsText}`;
  }
  if (cmd === 'import') {
    return `import ${String(action[1] ?? '').trim() || '(空路径)'}`;
  }
  if (cmd === 'note') {
    const noteText = String(action[1] ?? '').trim();
    const restored = getRecoverableActionFromNoteText(noteText);
    if (restored) {
      return `// [可恢复] ${formatActionLabel(restored, false)}`;
    }
    return `// ${noteText}`;
  }
  if (cmd === 'loop') {
    const count = Math.max(1, parseNumber(action[1], 1));
    const block = Array.isArray(action[2]) ? action[2] : [];
    return expanded
      ? `loop x${count}（展开，共${block.length} 条）`
      : `loop x${count}（收起，共${block.length} 条）`;
  }
  if (['kd', 'ku', 'md', 'mu'].includes(cmd)) {
    return `${cmd} '${String(action[1] ?? '')}' ${formatDelay(action[2])}`;
  }

  return JSON.stringify(action);
}

export function getRecoverableActionFromNoteText(text, RECOVERABLE_NOTE_PREFIX) {
  const raw = String(text ?? '').trim();
  if (!raw.startsWith(RECOVERABLE_NOTE_PREFIX)) return null;

  const payload = raw.slice(RECOVERABLE_NOTE_PREFIX.length).trim();
  if (!payload) return null;

  try {
    const parsed = JSON.parse(payload);
    if (!Array.isArray(parsed) || !parsed.length) return null;
    if (String(parsed[0] ?? '').trim().toLowerCase() === 'note') return null;
    return normalizeAction(parsed);
  } catch (_err) {
    return null;
  }
}

export function makeRecoverableNoteFromAction(action, RECOVERABLE_NOTE_PREFIX) {
  return ['note', `${RECOVERABLE_NOTE_PREFIX}${JSON.stringify(action)}`];
}
