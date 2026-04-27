import { state } from '../core/state.js';
import { parseNumber, pathKey, isLoopAction, cloneAction } from './action-model.js';

export { parseNumber, pathKey, keyToPath, isLoopAction, cloneAction } from './action-model.js';

export function getActionAndContainerByPath(path) {
  if (!Array.isArray(path) || !path.length) return null;
  let container = state.editorRows;

  for (let depth = 0; depth < path.length; depth += 1) {
    const index = path[depth];
    if (!Array.isArray(container) || index < 0 || index >= container.length) return null;
    if (depth === path.length - 1) {
      return { container, index, action: container[index] };
    }

    const action = container[index];
    if (!isLoopAction(action)) return null;
    container = action[2];
  }

  return null;
}

export function getActionAtPath(path) {
  const found = getActionAndContainerByPath(path);
  return found ? found.action : null;
}

export function getParentInsertTarget(path, offset = 0) {
  if (!Array.isArray(path) || !path.length) {
    return { type: 'root', index: state.editorRows.length };
  }

  const parentPath = path.slice(0, -1);
  const index = path[path.length - 1] + offset;
  if (!parentPath.length) {
    return { type: 'root', index };
  }

  return { type: 'loop', loopPath: parentPath, index };
}

export function getContainerForTarget(target) {
  if (!target) return null;
  if (target.type === 'root') return state.editorRows;
  if (target.type === 'loop') {
    const loopAction = getActionAtPath(target.loopPath);
    if (!isLoopAction(loopAction)) return null;
    return loopAction[2];
  }
  return null;
}

export function isPathPrefix(prefix, full) {
  if (!Array.isArray(prefix) || !Array.isArray(full) || prefix.length > full.length) return false;
  return prefix.every((part, idx) => part === full[idx]);
}

export function clearExpandedLoopKeysByPrefix(path) {
  const prefix = pathKey(path);
  if (!prefix) return;
  Array.from(state.expandedLoopPathKeys).forEach((key) => {
    if (key === prefix || key.startsWith(`${prefix}.`)) {
      state.expandedLoopPathKeys.delete(key);
    }
  });
}

export function setSelectedLine(path, kind = 'action') {
  state.selectedActionPath = Array.isArray(path) ? [...path] : null;
  state.selectedLineKind = kind;
}

export function insertActionAtTarget(action, target) {
  const container = getContainerForTarget(target);
  if (!Array.isArray(container)) {
    throw new Error('插入目标无效');
  }

  const insertIndex = Math.max(0, Math.min(parseNumber(target.index, container.length), container.length));
  container.splice(insertIndex, 0, cloneAction(action));

  if (target.type === 'root') {
    setSelectedLine([insertIndex], 'action');
  } else {
    setSelectedLine([...target.loopPath, insertIndex], 'action');
    state.expandedLoopPathKeys.add(pathKey(target.loopPath));
  }
}

export function moveActionToTarget(sourcePath, target, showToast) {
  const source = getActionAndContainerByPath(sourcePath);
  if (!source) return false;

  if (target.type === 'loop' && isPathPrefix(sourcePath, target.loopPath)) {
    showToast('不能将 loop 拖入它自己的循环体');
    return false;
  }

  const targetContainer = getContainerForTarget(target);
  if (!Array.isArray(targetContainer)) return false;

  let targetIndex = Math.max(0, Math.min(parseNumber(target.index, targetContainer.length), targetContainer.length));
  const movingAction = source.action;

  if (source.container === targetContainer && source.index < targetIndex) {
    targetIndex -= 1;
  }
  if (source.container === targetContainer && source.index === targetIndex) {
    return false;
  }

  source.container.splice(source.index, 1);
  targetContainer.splice(targetIndex, 0, movingAction);

  if (target.type === 'root') {
    setSelectedLine([targetIndex], 'action');
  } else {
    setSelectedLine([...target.loopPath, targetIndex], 'action');
    state.expandedLoopPathKeys.add(pathKey(target.loopPath));
  }
  return true;
}

export function resolveInsertTargetAfterSelection() {
  if (!Array.isArray(state.selectedActionPath) || !state.selectedActionPath.length) {
    return { type: 'root', index: state.editorRows.length };
  }

  if (state.selectedLineKind === 'loop_end') {
    return getParentInsertTarget(state.selectedActionPath, 1);
  }

  return getParentInsertTarget(state.selectedActionPath, 1);
}
