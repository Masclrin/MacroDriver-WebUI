'use strict';

// "调用宏" 节点的动作块编辑器
//
// 旧实现有两个致命问题：
//   1) 它读写 node.properties.actions —— 这个属性既不在节点定义里，
//      执行器也根本不读它（执行器读的是 path 指向的宏文件），所以永远是空列表；
//   2) 它用的指令集（left_click / key_press / ...）与真实宏指令
//      （kd / ku / md / mu / view / move_to / scroll / wait / loop / import）完全对不上。
//
// 现在：直接读写节点 path 指向的 .json 宏文件，并使用真实宏指令集做可视化编辑。
import { normalizeMacroRows } from '../../editor/action-model.js';

var KEY_DATALIST_ID = 'block-editor-key-list';
var KEY_SUGGESTIONS = [
  'w', 'a', 's', 'd', 'q', 'e', 'r', 'f', 'g', 'z', 'x', 'c', 'v',
  '1', '2', '3', '4', '5', '6',
  'space', 'enter', 'tab', 'shift', 'ctrl', 'alt', 'esc',
  'f1', 'f2', 'f3', 'f4',
  'up', 'down', 'left', 'right',
];

// 指令 → 展示名 + 参数描述
var KIND_SPECS = {
  kd:      { label: '按下按键 (kd)',        cls: 'key' },
  ku:      { label: '抬起按键 (ku)',        cls: 'key' },
  md:      { label: '按下鼠标 (md)',        cls: 'mouse' },
  mu:      { label: '抬起鼠标 (mu)',        cls: 'mouse' },
  wait:    { label: '等待 (wait)',          cls: 'wait' },
  view:    { label: '视角移动 (view)',      cls: 'view' },
  move_to: { label: '移动到坐标 (move_to)', cls: 'move' },
  scroll:  { label: '滚轮 (scroll)',        cls: 'scroll' },
  import:  { label: '导入子宏 (import)',    cls: 'import' },
  loop:    { label: '循环 (loop)',          cls: 'loop' },
  ext:     { label: '附加指令 (ext)',       cls: 'ext' },
  custom:  { label: '自定义原文 (custom)',  cls: 'raw' },
  note:    { label: '注释 (note)',          cls: 'note' },
};
var KIND_ORDER = ['kd', 'ku', 'md', 'mu', 'wait', 'view', 'move_to', 'scroll', 'import', 'ext', 'loop', 'custom', 'note'];

// 未识别/未解析的原文行：{ __raw: "<原文>" }（与宏编辑器保持一致的判定）
function isRawRow(row) {
  return !!row && typeof row === 'object' && !Array.isArray(row) && typeof row.__raw === 'string';
}

function kindOf(row) {
  if (isRawRow(row)) return 'custom';
  return String((Array.isArray(row) && row[0]) || 'wait').trim().toLowerCase();
}

function defaultRow(kind) {
  switch (kind) {
    case 'kd': case 'ku': return [kind, 'w', 50];
    case 'md': case 'mu': return [kind, 'left', 50];
    case 'wait': return ['wait', 100];
    case 'view': return ['view', [100, 0], 80];
    case 'move_to': return ['move_to', 960, 540, 150];
    case 'scroll': return ['scroll', 120];
    case 'import': return ['import', ''];
    case 'loop': return ['loop', 2, [['wait', 100]]];
    case 'ext': return ['ext', 'domain.action', 0];
    case 'custom': return { __raw: '["自定义", 0]' };
    case 'note': return ['note', ''];
    default: return ['wait', 100];
  }
}

function kindLabel(kind) {
  return (KIND_SPECS[kind] && KIND_SPECS[kind].label) || (kind + '（未识别）');
}

function cloneRow(row) {
  try { return JSON.parse(JSON.stringify(row)); } catch (e) { return defaultRow(kindOf(row)); }
}

function api() {
  return (window.pywebview && window.pywebview.api) ? window.pywebview.api : null;
}

function toast(msg, type) {
  if (window._autoEditor && typeof window._autoEditor.showToast === 'function') {
    window._autoEditor.showToast(msg, type || 'inf');
  } else {
    console.log('[动作块]', msg);
  }
}

var BlockEditor = {
  _node: null,
  _rows: [],
  _path: '',
  _bodyEl: null,
  _statusEl: null,
  _modal: null,

  // ---------- 打开 ----------
  open: function(node) {
    if (!node) return;
    this._node = node;
    this._path = String(node.properties.path || '').trim();
    this._rows = [];

    if (this._modal) { this._modal.remove(); this._modal = null; }
    this._buildShell();

    if (!this._path) {
      this._setStatus('该节点还没有选择宏文件，请先在属性面板的「旧JSON宏文件路径」里选择一个 .json 宏，再点“编辑动作块”。', 'warn');
      return;
    }
    this._loadFile();
  },

  _buildShell: function() {
    var modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.id = 'block-editor-modal';

    var content = document.createElement('div');
    content.className = 'modal-content';
    content.style.cssText = 'width:74%;max-width:920px;max-height:84vh;display:flex;flex-direction:column';

    var header = document.createElement('div');
    header.className = 'modal-header';
    header.innerHTML = '<span><i class="fa-solid fa-pen-to-square" style="margin-right:6px"></i>编辑动作块：'
      + (this._path ? this._esc(this._path) : '未选择宏文件') + '</span>';
    var closeBtn = document.createElement('button');
    closeBtn.className = 'modal-close';
    closeBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
    closeBtn.addEventListener('click', function() { modal.remove(); BlockEditor._modal = null; });
    header.appendChild(closeBtn);
    content.appendChild(header);

    var status = document.createElement('div');
    status.className = 'block-editor-status';
    status.style.cssText = 'padding:6px 14px;font-size:12px;color:var(--txt3)';
    this._statusEl = status;
    content.appendChild(status);

    var body = document.createElement('div');
    body.className = 'modal-body';
    body.style.cssText = 'overflow:auto;padding:10px 14px;flex:1;min-height:200px';
    this._bodyEl = body;
    content.appendChild(body);

    var footer = document.createElement('div');
    footer.className = 'modal-footer';
    footer.style.cssText = 'display:flex;align-items:center;gap:8px;padding:10px 14px;border-top:1px solid var(--border)';

    var addSelect = document.createElement('select');
    addSelect.style.cssText = 'padding:5px 8px;background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--rs);color:var(--txt);font-size:12px';
    for (var i = 0; i < KIND_ORDER.length; i++) {
      var k = KIND_ORDER[i];
      var opt = document.createElement('option');
      opt.value = k;
      opt.textContent = KIND_SPECS[k].label;
      addSelect.appendChild(opt);
    }
    footer.appendChild(addSelect);

    var addBtn = document.createElement('button');
    addBtn.className = 'prop-btn outline';
    addBtn.innerHTML = '<i class="fa-solid fa-plus"></i> 添加动作';
    addBtn.addEventListener('click', function() {
      if (!BlockEditor._path) { toast('请先选择宏文件', 'warn'); return; }
      BlockEditor._rows.push(defaultRow(addSelect.value));
      BlockEditor._render();
    });
    footer.appendChild(addBtn);

    var reloadBtn = document.createElement('button');
    reloadBtn.className = 'prop-btn outline';
    reloadBtn.innerHTML = '<i class="fa-solid fa-rotate"></i> 重新读取';
    reloadBtn.title = '放弃未保存的修改，重新从宏文件读取';
    reloadBtn.addEventListener('click', function() { BlockEditor._loadFile(); });
    footer.appendChild(reloadBtn);

    var spacer = document.createElement('span');
    spacer.style.flex = '1';
    footer.appendChild(spacer);

    var saveBtn = document.createElement('button');
    saveBtn.className = 'prop-btn accent-outline';
    saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> 保存到宏文件';
    saveBtn.addEventListener('click', function() { BlockEditor._saveFile(); });
    footer.appendChild(saveBtn);

    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'prop-btn outline';
    cancelBtn.textContent = '取消';
    cancelBtn.addEventListener('click', function() { modal.remove(); BlockEditor._modal = null; });
    footer.appendChild(cancelBtn);

    content.appendChild(footer);
    modal.appendChild(content);
    modal.addEventListener('click', function(e) { if (e.target === modal) { modal.remove(); BlockEditor._modal = null; } });
    document.body.appendChild(modal);
    this._modal = modal;

    if (!document.getElementById(KEY_DATALIST_ID)) {
      var dl = document.createElement('datalist');
      dl.id = KEY_DATALIST_ID;
      for (var s = 0; s < KEY_SUGGESTIONS.length; s++) {
        var o = document.createElement('option');
        o.value = KEY_SUGGESTIONS[s];
        dl.appendChild(o);
      }
      document.body.appendChild(dl);
    }
  },

  _setStatus: function(text, type) {
    if (!this._statusEl) return;
    var color = type === 'warn' ? '#f59e0b' : (type === 'err' ? 'var(--red)' : 'var(--txt3)');
    this._statusEl.style.color = color;
    this._statusEl.innerHTML = text;
  },

  _loadFile: async function() {
    if (!this._path) { this._render(); return; }
    var a = api();
    if (!a || !a.read_macro) {
      this._setStatus('后端不可用，无法读取宏文件。', 'err');
      this._render();
      return;
    }
    this._setStatus('正在读取 ' + this._esc(this._path) + ' …');
    try {
      var res = await a.read_macro(this._path);
      // 注意：read_macro 返回的是**扁平结构** {ok, path, rows}（core/response.ok），
      // 不是 {ok, data:{rows}}。此前误判 res.data 导致"读取失败：未知错误"，
      // 而保存只校验 res.ok 故一直正常 —— 表现为"能存不能读"。
      if (res && res.ok) {
        this._rows = normalizeMacroRows(res.rows || []);
        var n = this._rows.length;
        this._setStatus('已读取 <b>' + this._esc(this._path) + '</b>，共 ' + n + ' 条顶层动作。修改后点“保存到宏文件”写回。');
      } else {
        this._rows = [];
        this._setStatus('读取失败：' + this._esc((res && res.error) || '未知错误')
          + '（若路径不在项目宏目录内，请用属性面板的路径选择器重新选择）', 'err');
      }
    } catch (e) {
      this._rows = [];
      this._setStatus('读取异常：' + this._esc(String(e)), 'err');
    }
    this._render();
  },

  _saveFile: async function() {
    if (!this._path) { toast('请先选择宏文件', 'warn'); return; }
    var a = api();
    if (!a || !a.save_macro) { toast('后端不可用，无法保存', 'err'); return; }
    try {
      var res = await a.save_macro(this._path, this._rows);
      if (res && res.ok) {
        toast('已保存到宏文件：' + this._path, 'ok');
        if (this._modal) { this._modal.remove(); this._modal = null; }
      } else {
        toast('保存失败：' + ((res && res.error) || '未知错误'), 'err');
      }
    } catch (e) {
      toast('保存异常：' + String(e), 'err');
    }
  },

  // ---------- 渲染 ----------
  _render: function() {
    if (!this._bodyEl) return;
    var scrollTop = this._bodyEl.scrollTop;
    this._bodyEl.innerHTML = '';
    if (this._rows.length === 0) {
      var empty = document.createElement('div');
      empty.style.cssText = 'text-align:center;padding:36px 20px;color:var(--txt3);font-size:13px';
      empty.innerHTML = '<i class="fa-solid fa-list" style="font-size:24px;opacity:.3;display:block;margin-bottom:8px"></i>'
        + (this._path ? '这个宏还没有动作，点下方“添加动作”开始编写' : '请先选择宏文件');
      this._bodyEl.appendChild(empty);
    } else {
      this._renderList(this._rows, [], this._bodyEl);
    }
    this._bodyEl.scrollTop = scrollTop;
  },

  _renderList: function(rows, parentPath, container) {
    for (var i = 0; i < rows.length; i++) {
      this._renderRow(rows[i], parentPath.concat([i]), container);
    }
  },

  _renderRow: function(row, path, container) {
    var self = this;
    var kind = kindOf(row);
    var depth = path.length - 1;

    var rowEl = document.createElement('div');
    rowEl.className = 'be-row';
    rowEl.style.cssText = 'display:flex;align-items:flex-start;gap:6px;padding:6px 8px;margin:3px 0 3px '
      + (depth * 18) + 'px;background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--rs)';

    var idxEl = document.createElement('span');
    idxEl.style.cssText = 'font-family:var(--fmo);font-size:11px;color:var(--txt3);min-width:20px;text-align:right;padding-top:6px';
    idxEl.textContent = path.join('.');
    rowEl.appendChild(idxEl);

    var typeSel = document.createElement('select');
    typeSel.style.cssText = 'padding:4px 6px;font-size:12px;background:var(--bg-raised);border:1px solid var(--border);border-radius:var(--rs);color:var(--txt);flex-shrink:0';
    for (var t = 0; t < KIND_ORDER.length; t++) {
      var k = KIND_ORDER[t];
      var o = document.createElement('option');
      o.value = k;
      o.textContent = kindLabel(k);
      if (k === kind) o.selected = true;
      typeSel.appendChild(o);
    }
    if (KIND_ORDER.indexOf(kind) < 0) {
      var ox = document.createElement('option');
      ox.value = kind;
      ox.textContent = kindLabel(kind);
      ox.selected = true;
      typeSel.appendChild(ox);
    }
    typeSel.addEventListener('change', function() { self._changeKind(path, typeSel.value); });
    rowEl.appendChild(typeSel);

    var paramsEl = document.createElement('div');
    paramsEl.style.cssText = 'display:flex;flex-wrap:wrap;align-items:center;gap:6px;flex:1;min-width:0';
    this._renderParams(row, path, kind, paramsEl);
    rowEl.appendChild(paramsEl);

    var tools = document.createElement('div');
    tools.style.cssText = 'display:flex;gap:3px;flex-shrink:0';
    tools.appendChild(this._mkToolBtn('fa-chevron-up', '上移', path[path.length - 1] === 0, function() {
      self._move(path, -1);
    }));
    tools.appendChild(this._mkToolBtn('fa-chevron-down', '下移', false, function() {
      self._move(path, 1);
    }));
    tools.appendChild(this._mkToolBtn('fa-trash-can', '删除', false, function() {
      self._remove(path);
    }));
    rowEl.appendChild(tools);

    container.appendChild(rowEl);

    if (kind === 'loop' && Array.isArray(row[2])) {
      var childWrap = document.createElement('div');
      childWrap.style.cssText = 'margin:2px 0 6px ' + (depth * 18 + 26) + 'px;padding-left:8px;border-left:2px solid var(--border-lt,var(--border))';
      this._renderList(row[2], path, childWrap);
      if (row[2].length === 0) {
        var hint = document.createElement('div');
        hint.style.cssText = 'font-size:11px;color:var(--txt3);padding:4px 0';
        hint.textContent = '（循环体为空）';
        childWrap.appendChild(hint);
      }
      var addChild = document.createElement('button');
      addChild.className = 'prop-btn outline';
      addChild.style.cssText = 'margin:2px 0 4px;padding:2px 8px;font-size:11px';
      addChild.innerHTML = '<i class="fa-solid fa-plus"></i> 添加子动作';
      addChild.addEventListener('click', function() {
        if (!Array.isArray(row[2])) row[2] = [];
        row[2].push(defaultRow('wait'));
        self._render();
      });
      childWrap.appendChild(addChild);
      container.appendChild(childWrap);
    }
  },

  _renderParams: function(row, path, kind, container) {
    var self = this;
    function txt(value, onChange, placeholder, extraStyle) {
      var inp = document.createElement('input');
      inp.type = 'text';
      inp.value = (value === undefined || value === null) ? '' : String(value);
      inp.placeholder = placeholder || '';
      inp.style.cssText = 'padding:4px 6px;font-size:12px;background:var(--bg-raised);border:1px solid var(--border);border-radius:var(--rs);color:var(--txt);width:110px;' + (extraStyle || '');
      inp.addEventListener('input', function() { onChange(inp.value); });
      return inp;
    }
    function num(value, onChange, width) {
      var inp = document.createElement('input');
      inp.type = 'number';
      inp.value = (value === undefined || value === null) ? 0 : value;
      inp.style.cssText = 'padding:4px 6px;font-size:12px;background:var(--bg-raised);border:1px solid var(--border);border-radius:var(--rs);color:var(--txt);width:' + (width || 78) + 'px';
      inp.addEventListener('input', function() {
        var v = parseFloat(inp.value);
        onChange(Number.isFinite(v) ? v : 0);
      });
      return inp;
    }
    function label(text) {
      var l = document.createElement('span');
      l.style.cssText = 'font-size:11px;color:var(--txt3)';
      l.textContent = text;
      return l;
    }
    function delayInput(value, onChange) {
      return txt(value, function(v) {
        var s = String(v).trim();
        if (/^\d+\s*[fF]$/.test(s)) { onChange(s.replace(/\s+/g, '').toLowerCase()); return; }
        var n = parseFloat(s);
        onChange(Number.isFinite(n) ? n : 0);
      }, '毫秒 或 2f');
    }
    function setIdx(i, v) { row[i] = v; }

    if (kind === 'kd' || kind === 'ku') {
      container.appendChild(label('按键'));
      container.appendChild(txt(row[1], function(v) { setIdx(1, v.trim()); }, '如 w / space / shift', 'width:96px'));
      container.appendChild(label('延迟'));
      container.appendChild(delayInput(row[2], function(v) { setIdx(2, v); }));
      return;
    }
    if (kind === 'md' || kind === 'mu') {
      var sel = document.createElement('select');
      sel.style.cssText = 'padding:4px 6px;font-size:12px;background:var(--bg-raised);border:1px solid var(--border);border-radius:var(--rs);color:var(--txt)';
      ['left', 'right', 'middle'].forEach(function(bn) {
        var o = document.createElement('option');
        o.value = bn;
        o.textContent = bn;
        if (String(row[1]) === bn) o.selected = true;
        sel.appendChild(o);
      });
      sel.addEventListener('change', function() { setIdx(1, sel.value); });
      container.appendChild(label('鼠标键'));
      container.appendChild(sel);
      container.appendChild(label('延迟'));
      container.appendChild(delayInput(row[2], function(v) { setIdx(2, v); }));
      return;
    }
    if (kind === 'wait') {
      container.appendChild(label('等待'));
      container.appendChild(delayInput(row[1], function(v) { setIdx(1, v); }));
      return;
    }
    if (kind === 'view') {
      var vec = Array.isArray(row[1]) ? row[1] : [0, 0];
      container.appendChild(label('dx'));
      container.appendChild(num(vec[0], function(v) { vec[0] = v; row[1] = vec; }));
      container.appendChild(label('dy'));
      container.appendChild(num(vec[1], function(v) { vec[1] = v; row[1] = vec; }));
      container.appendChild(label('时长(ms)'));
      container.appendChild(num(row[2], function(v) { setIdx(2, v); }));
      return;
    }
    if (kind === 'move_to') {
      container.appendChild(label('X'));
      container.appendChild(num(row[1], function(v) { setIdx(1, v); }));
      container.appendChild(label('Y'));
      container.appendChild(num(row[2], function(v) { setIdx(2, v); }));
      container.appendChild(label('时长(ms)'));
      container.appendChild(num(row[3], function(v) { setIdx(3, v); }));
      return;
    }
    if (kind === 'scroll') {
      container.appendChild(label('滚动量'));
      container.appendChild(num(row[1], function(v) { setIdx(1, v); }));
      container.appendChild(label('(正=上滚, 负=下滚)'));
      return;
    }
    if (kind === 'import') {
      container.appendChild(label('子宏路径'));
      container.appendChild(txt(row[1], function(v) { setIdx(1, v); }, '相对当前宏目录，如 连招/起手.json', 'width:320px'));
      return;
    }
    if (kind === 'loop') {
      container.appendChild(label('循环次数'));
      container.appendChild(num(row[1], function(v) { setIdx(1, Math.max(1, Math.round(v) || 1)); }, 70));
      container.appendChild(label('次'));
      return;
    }
    if (kind === 'note') {
      container.appendChild(label('注释文字'));
      container.appendChild(txt(row[1], function(v) { setIdx(1, v); }, '不会被执行', 'width:320px'));
      return;
    }
    if (kind === 'ext') {
      container.appendChild(label('附加指令名'));
      container.appendChild(txt(row[1], function(v) { setIdx(1, v); }, '如 fps.lock / net.set', 'width:170px'));
      var extArgs = Array.isArray(row) ? row.slice(2) : [];
      container.appendChild(label('参数'));
      container.appendChild(txt(extArgs.length ? JSON.stringify(extArgs) : '', function(v) {
        var s = String(v).trim();
        var parsed = null;
        if (s) { try { parsed = JSON.parse(s); } catch (e) { parsed = null; } }
        if (!Array.isArray(parsed)) parsed = s ? s.split(/\s+/).map(function(tok) { return /^-?\d+(\.\d+)?$/.test(tok) ? Number(tok) : tok; }) : [];
        row.length = 2;
        for (var i = 0; i < parsed.length; i++) row.push(parsed[i]);
      }, 'JSON 数组 或 空格分隔', 'width:200px'));
      return;
    }
    if (kind === 'custom' || isRawRow(row)) {
      container.appendChild(label('原文'));
      container.appendChild(txt(isRawRow(row) ? row.__raw : JSON.stringify(row), function(v) {
        row.__raw = String(v);
      }, '任意原文 / JSON 数组（保存时原样写回）', 'flex:1;min-width:200px'));
      return;
    }
    // 未识别指令：给出原始 JSON 编辑
    container.appendChild(label('原始'));
    container.appendChild(txt(JSON.stringify(row), function(v) {
      try { var parsed2 = JSON.parse(v); if (Array.isArray(parsed2)) { self._replaceRow(path, parsed2); } } catch (e) { /* 输入中 */ }
    }, 'JSON 数组', 'width:320px'));
  },

  _mkToolBtn: function(icon, title, disabled, onClick) {
    var b = document.createElement('button');
    b.className = 'prop-btn outline';
    b.style.cssText = 'padding:3px 6px;font-size:11px' + (disabled ? ';opacity:.3' : '');
    b.disabled = !!disabled;
    b.title = title;
    b.innerHTML = '<i class="fa-solid ' + icon + '"></i>';
    b.addEventListener('click', onClick);
    return b;
  },

  // ---------- 数据结构操作 ----------
  _rowAt: function(path) {
    var list = this._rows;
    var row = null;
    for (var i = 0; i < path.length; i++) {
      if (!Array.isArray(list)) return null;
      row = list[path[i]];
      if (row === undefined) return null;
      if (i < path.length - 1) list = row[2];
    }
    return row;
  },

  _childList: function(parentPath) {
    if (!parentPath.length) return this._rows;
    var row = this._rowAt(parentPath);
    return (row && Array.isArray(row[2])) ? row[2] : null;
  },

  _replaceRow: function(path, newRow) {
    var parentPath = path.slice(0, -1);
    var list = this._childList(parentPath);
    if (!list) return;
    list[path[path.length - 1]] = newRow;
    this._render();
  },

  _changeKind: function(path, kind) {
    var row = this._rowAt(path);
    if (!row) return;
    var old = kindOf(row);

    // 切到"自定义原文"：把当前内容原样转为可编辑原文
    if (kind === 'custom') {
      this._replaceRow(path, { __raw: isRawRow(row) ? row.__raw : JSON.stringify(row) });
      return;
    }
    // 原文行切回普通指令：直接换成默认值（原文已不可结构化）
    if (isRawRow(row)) {
      this._replaceRow(path, defaultRow(kind));
      return;
    }

    var def = defaultRow(kind);
    // 同族指令（kd↔ku、md↔mu）保留原有参数，其它直接换默认值
    var sameKey = (old === 'kd' || old === 'ku') && (kind === 'kd' || kind === 'ku');
    var sameMouse = (old === 'md' || old === 'mu') && (kind === 'md' || kind === 'mu');
    if (sameKey) { def[1] = row[1]; def[2] = row[2]; }
    else if (sameMouse) { def[1] = row[1]; def[2] = row[2]; }
    this._replaceRow(path, def);
  },

  _remove: function(path) {
    var parentPath = path.slice(0, -1);
    var list = this._childList(parentPath);
    if (!list) return;
    list.splice(path[path.length - 1], 1);
    this._render();
  },

  _move: function(path, delta) {
    var parentPath = path.slice(0, -1);
    var list = this._childList(parentPath);
    if (!list) return;
    var i = path[path.length - 1];
    var j = i + delta;
    if (j < 0 || j >= list.length) return;
    var tmp = list[i];
    list[i] = list[j];
    list[j] = tmp;
    this._render();
  },

  _esc: function(s) {
    return String(s === undefined || s === null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  },
};

export const AutomationBlockEditor = BlockEditor;
window.AutomationBlockEditor = BlockEditor;
