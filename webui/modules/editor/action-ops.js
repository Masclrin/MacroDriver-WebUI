import { parseNumber, pathKey, isLoopAction, cloneAction } from './action-model.js';

export { parseNumber, pathKey, keyToPath, isLoopAction, cloneAction } from './action-model.js';

// 所有操作都以「编辑器视图 view」为作用域。
// view 形状（由 editor/index.js 创建）：
//   { id, el, listEl, tabId, rows[], selectedActionPath, selectedLineKind,
//     expandedLoopPathKeys:Set, inlineEditingPathKey, scrollTop }
// 这样同一份代码可同时服务最多 3 个并排小窗口，互不干扰。

function rowsOf(view) {
  return view && Array.isArray(view.rows) ? view.rows : [];
}

export function getActionAndContainerByPath(view, path) {
  if (!Array.isArray(path) || !path.length) return null;
  let container = rowsOf(view);

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

export function getActionAtPath(view, path) {
  const found = getActionAndContainerByPath(view, path);
  return found ? found.action : null;
}

export function getParentInsertTarget(view, path, offset = 0) {
  if (!Array.isArray(path) || !path.length) {
    return { type: 'root', index: rowsOf(view).length };
  }

  const parentPath = path.slice(0, -1);
  const index = path[path.length - 1] + offset;
  if (!parentPath.length) {
    return { type: 'root', index };
  }

  return { type: 'loop', loopPath: parentPath, index };
}

export function getContainerForTarget(view, target) {
  if (!target) return null;
  if (target.type === 'root') return rowsOf(view);
  if (target.type === 'loop') {
    const loopAction = getActionAtPath(view, target.loopPath);
    if (!isLoopAction(loopAction)) return null;
    return loopAction[2];
  }
  return null;
}

export function isPathPrefix(prefix, full) {
  if (!Array.isArray(prefix) || !Array.isArray(full) || prefix.length > full.length) return false;
  return prefix.every((part, idx) => part === full[idx]);
}

export function clearExpandedLoopKeysByPrefix(view, path) {
  const prefix = pathKey(path);
  if (!prefix || !view || !view.expandedLoopPathKeys) return;
  Array.from(view.expandedLoopPathKeys).forEach((key) => {
    if (key === prefix || key.startsWith(`${prefix}.`)) {
      view.expandedLoopPathKeys.delete(key);
    }
  });
}

export function setSelectedLine(view, path, kind = 'action') {
  if (!view) return;
  view.selectedActionPath = Array.isArray(path) ? [...path] : null;
  view.selectedLineKind = kind;
}

export function insertActionAtTarget(view, action, target) {
  const container = getContainerForTarget(view, target);
  if (!Array.isArray(container)) {
    throw new Error('插入目标无效');
  }

  const insertIndex = Math.max(0, Math.min(parseNumber(target.index, container.length), container.length));
  container.splice(insertIndex, 0, cloneAction(action));

  if (target.type === 'root') {
    setSelectedLine(view, [insertIndex], 'action');
  } else {
    setSelectedLine(view, [...target.loopPath, insertIndex], 'action');
    view.expandedLoopPathKeys.add(pathKey(target.loopPath));
  }
}

export function moveActionToTarget(view, sourcePath, target, showToast) {
  const source = getActionAndContainerByPath(view, sourcePath);
  if (!source) return false;

  if (target.type === 'loop' && isPathPrefix(sourcePath, target.loopPath)) {
    showToast('不能将 loop 拖入它自己的循环体');
    return false;
  }

  const targetContainer = getContainerForTarget(view, target);
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
    setSelectedLine(view, [targetIndex], 'action');
  } else {
    setSelectedLine(view, [...target.loopPath, targetIndex], 'action');
    view.expandedLoopPathKeys.add(pathKey(target.loopPath));
  }
  return true;
}

export function resolveInsertTargetAfterSelection(view) {
  if (!Array.isArray(view?.selectedActionPath) || !view.selectedActionPath.length) {
    return { type: 'root', index: rowsOf(view).length };
  }
  return getParentInsertTarget(view, view.selectedActionPath, 1);
}
