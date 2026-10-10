export const PARAM_GUIDE_FALLBACK = {
};

export const RECOMMENDED_RANDOM_DELAY_RULES = [
  { min: 0, max: 199, fixed_ms: 3 },
  { min: 200, max: 800, fixed_ms: 6 },
];

export const HIDE_DEFAULT_FIELD_IDS = new Set([
  'recorder.ALLOWED_KEYS',
  'executor.EXEC_SPEED_FACTOR',
  'executor.MACRO_RELOAD_KEY',
]);

export const ACTION_FORM_DEFAULTS = {
  kd: { arg1: 'w', arg2: '50' },
  ku: { arg1: 'w', arg2: '50' },
  md: { arg1: 'left', arg2: '50' },
  mu: { arg1: 'left', arg2: '50' },
  wait: { arg1: '50', arg2: '' },
  view: { arg1: '0,0', arg2: '50' },
  move_to: { arg1: '960,540', arg2: '150' },
  scroll: { arg1: '120', arg2: '' },
  loop: { arg1: '1', arg2: '' },
  import: { arg1: '', arg2: '' },
  ext: { arg1: 'fps.lock', arg2: '30' },
  custom: { arg1: '["自定义", 0]', arg2: '' },
  note: { arg1: '备注', arg2: '' },
};

export const ACTION_FORM_UI = {
  kd: { arg1Label: '按键', arg2Label: '延迟(ms/帧)', arg1Placeholder: '如 w / space / 1', arg2Placeholder: '50 或 2f', showArg2: true },
  ku: { arg1Label: '按键', arg2Label: '延迟(ms/帧)', arg1Placeholder: '如 w / space / 1', arg2Placeholder: '50 或 2f', showArg2: true },
  md: { arg1Label: '鼠标键', arg2Label: '延迟(ms/帧)', arg1Placeholder: '如 left / right / middle', arg2Placeholder: '50 或 2f', showArg2: true, arg1Options: ['left', 'right', 'middle'] },
  mu: { arg1Label: '鼠标键', arg2Label: '延迟(ms/帧)', arg1Placeholder: '如 left / right / middle', arg2Placeholder: '50 或 2f', showArg2: true, arg1Options: ['left', 'right', 'middle'] },
  wait: { arg1Label: '等待(ms/帧)', arg2Label: '', arg1Placeholder: '如 50 或 2f', arg2Placeholder: '', showArg2: false },
  view: { arg1Label: '位移(dx,dy)', arg2Label: '时长(ms)', arg1Placeholder: '如 120,-35', arg2Placeholder: '50', showArg2: true },
  move_to: { arg1Label: '目标坐标(X,Y)', arg2Label: '时长(ms)', arg1Placeholder: '如 960,540', arg2Placeholder: '150', showArg2: true },
  scroll: { arg1Label: '滚动量', arg2Label: '', arg1Placeholder: '正=上滚 / 负=下滚', arg2Placeholder: '', showArg2: false },
  loop: { arg1Label: '循环次数', arg2Label: '', arg1Placeholder: '>= 1', arg2Placeholder: '', showArg2: false },
  import: { arg1Label: '子宏路径', arg2Label: '', arg1Placeholder: '如 宏/录制宏/示例.json', arg2Placeholder: '', showArg2: false },
  ext: { arg1Label: '附加指令名', arg2Label: '参数', arg1Placeholder: '如 fps.lock / net.set', arg2Placeholder: '空格分隔 或 JSON 数组，如 30 或 ["weak"]', showArg2: true },
  custom: { arg1Label: '原始内容（JSON 数组 / 任意文本）', arg2Label: '', arg1Placeholder: '如 ["ext","fps.lock",30]，或任意原文', arg2Placeholder: '', showArg2: false },
  note: { arg1Label: '注释内容', arg2Label: '', arg1Placeholder: '输入注释文本（无需输入 //）', arg2Placeholder: '', showArg2: false },
};

export const RECOVERABLE_NOTE_PREFIX = '@action ';
