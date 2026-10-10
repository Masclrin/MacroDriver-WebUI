import { state } from '../core/state.js';
import { showToast } from '../core/dom.js';
import { RECOVERABLE_NOTE_PREFIX } from '../core/constants.js';
import { getRecoverableActionFromNoteText, makeRecoverableNoteFromAction, isLoopAction, pathKey } from './action-model.js';
import { getActionAndContainerByPath, setSelectedLine, clearExpandedLoopKeysByPrefix } from './action-ops.js';
import { fillActionEditorByAction } from './action-form.js';

export { getRecoverableActionFromNoteText, makeRecoverableNoteFromAction } from './action-model.js';

export function toggleCommentForPath(path, options = {}) {
  const silent = Boolean(options.silent);
  const shouldKeepInlineEditor = !state.batchCommentMode;
  const info = getActionAndContainerByPath(path);
  if (!info) {
    if (!silent) showToast('动作已失效，请重新选择');
    return false;
  }

  const current = info.action;
  const cmd = String(current[0] ?? '').trim().toLowerCase();

  if (cmd === 'note') {
    const restored = getRecoverableActionFromNoteText(current[1], RECOVERABLE_NOTE_PREFIX);
    if (!restored) {
      if (!silent) showToast('该注释不包含可恢复动作');
      return false;
    }
    info.container[info.index] = restored;
    setSelectedLine(path, 'action');
    fillActionEditorByAction(restored);
    state.inlineEditingPathKey = shouldKeepInlineEditor ? pathKey(path) : null;
    if (!silent) showToast('已恢复动作');
    return true;
  }

  const fromLoop = isLoopAction(current);
  info.container[info.index] = makeRecoverableNoteFromAction(current, RECOVERABLE_NOTE_PREFIX);
  if (fromLoop) {
    clearExpandedLoopKeysByPrefix(path);
  }
  setSelectedLine(path, 'action');
  fillActionEditorByAction(info.container[info.index]);
  state.inlineEditingPathKey = shouldKeepInlineEditor ? pathKey(path) : null;
  if (!silent) showToast('已注释当前动作');
  return true;
}
