'use strict';

export var _portNameMap = {
    in: '执行', out: '输出', next: '下一步', body: '循环体',
    done: '完成', true: '是', false: '否', cond: '条件',
    trigger: '触发', timeout: '超时', completed: '完成',
    interrupted: '中断', match: '匹配', no: '不匹配',
    result: '结果', val: '值', met: '满足', pass: '通过', fail: '失败',
    branch1: '分支1', branch2: '分支2', branch3: '分支3', branch4: '分支4',
    branch5: '分支5', branch6: '分支6', branch7: '分支7', branch8: '分支8'
};

export var _portTypeColors = {
    flow: '#94a3b8',
    boolean: '#ef4444',
    number: '#22c55e',
    string: '#60a5fa',
    any: '#94a3b8'
};

export var _annotationPresetColors = [
    { color: '#fbbf24', name: '黄色', bg: 'linear-gradient(135deg,rgba(251,191,36,.72),rgba(251,191,36,.58))' },
    { color: '#22c55e', name: '绿色', bg: 'linear-gradient(135deg,rgba(34,197,94,.72),rgba(34,197,94,.58))' },
    { color: '#3b82f6', name: '蓝色', bg: 'linear-gradient(135deg,rgba(59,130,246,.72),rgba(59,130,246,.58))' },
    { color: '#f97316', name: '橙色', bg: 'linear-gradient(135deg,rgba(249,115,22,.72),rgba(249,115,22,.58))' },
    { color: '#a855f7', name: '紫色', bg: 'linear-gradient(135deg,rgba(168,85,247,.72),rgba(168,85,247,.58))' },
    { color: '#ef4444', name: '红色', bg: 'linear-gradient(135deg,rgba(239,68,68,.72),rgba(239,68,68,.58))' },
    { color: '#06b6d4', name: '青色', bg: 'linear-gradient(135deg,rgba(6,182,212,.72),rgba(6,182,212,.58))' },
    { color: '#94a3b8', name: '灰色', bg: 'linear-gradient(135deg,rgba(148,163,184,.72),rgba(148,163,184,.58))' }
];

export var _groupPresetColors = [
    { color: '#3b82f6', name: '蓝色', bg: 'rgba(59,130,246,.08)' },
    { color: '#22c55e', name: '绿色', bg: 'rgba(34,197,94,.08)' },
    { color: '#f97316', name: '橙色', bg: 'rgba(249,115,22,.08)' },
    { color: '#a855f7', name: '紫色', bg: 'rgba(168,85,247,.08)' },
    { color: '#ef4444', name: '红色', bg: 'rgba(239,68,68,.08)' },
    { color: '#eab308', name: '黄色', bg: 'rgba(234,179,8,.08)' },
    { color: '#06b6d4', name: '青色', bg: 'rgba(6,182,212,.08)' },
    { color: '#64748b', name: '灰色', bg: 'rgba(100,116,139,.08)' }
];
