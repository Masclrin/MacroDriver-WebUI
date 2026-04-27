export function parseNumber(text, fallback = 0) {
  const n = Number(text);
  return Number.isFinite(n) ? n : fallback;
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

export function isLoopAction(action) {
  return Array.isArray(action)
    && action.length >= 3
    && String(action[0]).trim().toLowerCase() === 'loop'
    && Array.isArray(action[2]);
}

export function normalizeAction(action) {
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

  if (cmd === 'wait') {
    return ['wait', Math.max(0, parseNumber(action[1], 50))];
  }

  if (cmd === 'import') {
    return ['import', String(action[1] ?? '').trim()];
  }

  if (cmd === 'note') {
    return ['note', String(action[1] ?? '').trim()];
  }

  if (['kd', 'ku', 'md', 'mu'].includes(cmd)) {
    const fallbackKey = cmd === 'md' || cmd === 'mu' ? 'left' : 'w';
    return [cmd, String(action[1] ?? fallbackKey), Math.max(0, parseNumber(action[2], 50))];
  }

  return cloneAction(action);
}

export function normalizeMacroRows(rows) {
  if (!Array.isArray(rows)) return [];
  return rows.filter((row) => Array.isArray(row)).map((row) => normalizeAction(row));
}

export function formatActionLabel(action, expanded) {
  const cmd = String(action[0] ?? '').trim().toLowerCase();

  if (cmd === 'wait') {
    return `wait ${parseNumber(action[1], 0)}ms`;
  }
  if (cmd === 'view') {
    const vec = Array.isArray(action[1]) ? action[1] : [0, 0];
    return `view [${parseNumber(vec[0], 0)}, ${parseNumber(vec[1], 0)}] ${Math.max(1, parseNumber(action[2], 50))}ms`;
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
    return `${cmd} '${String(action[1] ?? '')}' ${Math.max(0, parseNumber(action[2], 50))}ms`;
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
