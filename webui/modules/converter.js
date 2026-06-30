import { apiCall, showToast } from './app-core.js';

var _initDone = false;

export function initConverterTab() {
  if (_initDone) return;
  _initDone = true;
  _bindEvents();
}

// ── 工具 ──────────────────────────────────────────────────────────

function q(id) { return document.getElementById(id); }

var _FMT_LABELS = {
  auto: '自动识别', webui: 'WebUI JSON（ms）', webui_frame: 'WebUI 帧数 Nf',
  razer: 'Razer Synapse XML', razer3: 'Razer Synapse 3 XML', razer4: 'Razer Synapse 4 XML',
  logitech: '罗技 G HUB Lua', logitech_ghub: '罗技 G HUB Lua', logitech_lgs: '罗技 LGS Lua',
  ahk: 'AutoHotkey v1', ahk_v2: 'AutoHotkey v2',
  xmouse: 'X-Mouse Button Control (.xmbcs)', xmouse_dsl: 'X-Mouse DSL 字符串',
  generic_json: '通用录制 JSON', cstruct: 'C 数组',
  unknown: '未知格式',
};

function fmtLabel(fmt) { return _FMT_LABELS[fmt] || fmt; }

function getInput() {
  var el = q('cvtInput');
  return el ? el.value.trim() : '';
}

function getSrcFmt() {
  var el = q('cvtSrcFmt');
  return el ? el.value : 'auto';
}

function setOutput(text, status) {
  var out = q('cvtOutput');
  var st = q('cvtStatus');
  if (out) out.value = text || '';
  if (st) st.textContent = status || '';
}

function setDetectHint(fmt) {
  var el = q('cvtDetectResult');
  if (el) el.textContent = fmt ? ('已识别格式：' + fmtLabel(fmt)) : '';
}

function btnLock(id, lockText) {
  var b = q(id);
  if (b) { b.disabled = true; b._orig = b.textContent; b.textContent = lockText || '处理中...'; }
}

function btnUnlock(id) {
  var b = q(id);
  if (b) { b.disabled = false; if (b._orig) b.textContent = b._orig; }
}

// ── 事件绑定 ───────────────────────────────────────────────────────

function _bindEvents() {
  var b;

  b = q('btnCvtDetect');
  if (b) b.addEventListener('click', handleDetect);

  b = q('btnCvtToWebUI');
  if (b) b.addEventListener('click', handleToWebUI);

  b = q('btnCvtToExternal');
  if (b) b.addEventListener('click', handleToExternal);

  b = q('btnCvtReframe');
  if (b) b.addEventListener('click', handleReframe);

  b = q('btnCvtCopy');
  if (b) b.addEventListener('click', handleCopy);

  b = q('btnCvtDownload');
  if (b) b.addEventListener('click', handleDownload);

  b = q('btnCvtUseAsInput');
  if (b) b.addEventListener('click', handleUseAsInput);
}

// ── 操作处理 ───────────────────────────────────────────────────────

async function handleDetect() {
  var text = getInput();
  if (!text) { showToast('请先输入宏文本'); return; }
  try {
    var data = await apiCall('converter_detect', text);
    setDetectHint(data.format);
    if (data.format && data.format !== 'unknown') {
      var sel = q('cvtSrcFmt');
      if (sel) sel.value = data.format;
    }
    showToast('格式: ' + fmtLabel(data.format));
  } catch (e) {
    showToast('检测失败: ' + e.message);
  }
}

async function handleToWebUI() {
  var text = getInput();
  if (!text) { showToast('请先输入宏文本'); return; }
  var srcFmt = getSrcFmt();
  var modeEl = q('cvtToWebUIMode');
  var mode = modeEl ? modeEl.value : 'webui';
  var fps = parseInt((q('cvtToWebUIFps') || {}).value || '60') || 60;
  btnLock('btnCvtToWebUI', '转换中...');
  try {
    var data = await apiCall('converter_convert', text, srcFmt, mode, fps, false);
    var hint = '✓ 转换成功';
    if (data.detected_fmt && srcFmt === 'auto') hint += '  (识别为 ' + fmtLabel(data.detected_fmt) + ')';
    if (data.warnings && data.warnings.length) hint += '\n⚠ ' + data.warnings.join('\n⚠ ');
    setOutput(data.output, hint);
    setDetectHint(data.detected_fmt);
  } catch (e) {
    setOutput('', '✗ ' + e.message);
    showToast('转换失败: ' + e.message);
  } finally {
    btnUnlock('btnCvtToWebUI');
  }
}

async function handleToExternal() {
  var text = getInput();
  if (!text) { showToast('请先输入宏文本'); return; }
  var srcFmt = getSrcFmt();
  var dstFmtEl = q('cvtDstFmt');
  var rawDst = dstFmtEl ? dstFmtEl.value : 'razer4';

  // 解析格式令牌 → 底层格式 + 版本参数
  var dstFmt = rawDst;
  var ahkV2 = false;
  var synapseVersion = 4;
  var logitechGhub = true;

  if (rawDst === 'razer3') { dstFmt = 'razer'; synapseVersion = 3; }
  else if (rawDst === 'razer4') { dstFmt = 'razer'; synapseVersion = 4; }
  else if (rawDst === 'logitech_ghub') { dstFmt = 'logitech'; logitechGhub = true; }
  else if (rawDst === 'logitech_lgs') { dstFmt = 'logitech'; logitechGhub = false; }
  else if (rawDst === 'ahk_v2') { dstFmt = 'ahk'; ahkV2 = true; }

  var fps = parseInt((q('cvtDstFps') || {}).value || '60') || 60;
  btnLock('btnCvtToExternal', '转换中...');
  try {
    var data = await apiCall('converter_convert', text, srcFmt, dstFmt, fps, ahkV2, synapseVersion, logitechGhub);
    var hint = '✓ 转换成功';
    if (data.detected_fmt && srcFmt === 'auto') hint += '  (识别为 ' + fmtLabel(data.detected_fmt) + ')';
    if (data.warnings && data.warnings.length) hint += '\n⚠ ' + data.warnings.join('\n⚠ ');
    setOutput(data.output, hint);
    setDetectHint(data.detected_fmt);
  } catch (e) {
    setOutput('', '✗ ' + e.message);
    showToast('转换失败: ' + e.message);
  } finally {
    btnUnlock('btnCvtToExternal');
  }
}

async function handleReframe() {
  var text = getInput();
  if (!text) { showToast('请先输入帧数格式的 WebUI JSON'); return; }
  var srcFps = parseInt((q('cvtSrcFps') || {}).value || '60') || 60;
  var dstFps = parseInt((q('cvtDstFps2') || {}).value || '144') || 144;
  if (srcFps === dstFps) { showToast('源帧率和目标帧率相同，无需转换'); return; }
  btnLock('btnCvtReframe', '转换中...');
  try {
    var data = await apiCall('converter_reframe', text, srcFps, dstFps);
    setOutput(data.output, '✓ 帧率重采样完成  ' + srcFps + 'fps → ' + dstFps + 'fps');
  } catch (e) {
    setOutput('', '✗ ' + e.message);
    showToast('重采样失败: ' + e.message);
  } finally {
    btnUnlock('btnCvtReframe');
  }
}

function handleCopy() {
  var out = q('cvtOutput');
  if (!out || !out.value) { showToast('输出为空'); return; }
  if (navigator.clipboard) {
    navigator.clipboard.writeText(out.value).then(function () {
      showToast('已复制到剪贴板');
    }).catch(function () { _fallbackCopy(out); });
  } else {
    _fallbackCopy(out);
  }
}

function _fallbackCopy(el) {
  el.select();
  try { document.execCommand('copy'); showToast('已复制'); } catch (e) { showToast('复制失败'); }
}

function handleDownload() {
  var out = q('cvtOutput');
  if (!out || !out.value) { showToast('输出为空'); return; }
  var rawDst = (q('cvtDstFmt') || {}).value || 'razer4';
  var extMap = {
    razer: '.xml', razer3: '.xml', razer4: '.xml',
    logitech: '.lua', logitech_ghub: '.lua', logitech_lgs: '.lua',
    ahk: '.ahk', ahk_v2: '.ahk',
    xmouse: '.xmbcs', xmouse_dsl: '.txt',
  };
  var ext = extMap[rawDst] || '.json';
  var blob = new Blob([out.value], { type: 'text/plain;charset=utf-8' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url; a.download = 'macro_converted' + ext;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function handleUseAsInput() {
  var out = q('cvtOutput');
  var inp = q('cvtInput');
  if (!out || !out.value) { showToast('输出为空'); return; }
  if (inp) inp.value = out.value;
  var sel = q('cvtSrcFmt');
  if (sel) sel.value = 'webui';
  setDetectHint('webui');
  showToast('结果已移入输入框，源格式已切换为 WebUI JSON');
}
