import { updateStatusBar } from './ui-utils.js';

var _sidebarLeftWidth = 208;
var _sidebarRightWidth = 264;
var _sidebarLeftCollapsed = false;
var _sidebarRightCollapsed = false;
var _sidebarLeftPrevWidth = 208;
var _sidebarRightPrevWidth = 264;

export function initSidebarResize() {
  var sbLeft = document.getElementById('sb-l');
  var sbRight = document.getElementById('sb-r');
  var rszLeft = document.getElementById('sb-l-rsz');
  var rszRight = document.getElementById('sb-r-rsz');
  if (!sbLeft || !sbRight || !rszLeft || !rszRight) return;

  function startResize(rszEl, side, evt) {
    var startX = 0, startWidth = 0, targetEl = null;
    if (side === 'left') {
      if (_sidebarLeftCollapsed) return;
      startX = evt.clientX;
      startWidth = sbLeft.offsetWidth;
      targetEl = sbLeft;
    } else {
      if (_sidebarRightCollapsed) return;
      startX = evt.clientX;
      startWidth = sbRight.offsetWidth;
      targetEl = sbRight;
    }
    rszEl.classList.add('active');
    function onMove(e) {
      if (side === 'left') {
        var newW = Math.max(150, Math.min(400, startWidth + e.clientX - startX));
        targetEl.style.width = newW + 'px';
        targetEl.style.setProperty('--sb-l-w', newW + 'px');
        _sidebarLeftWidth = newW;
        _sidebarLeftPrevWidth = newW;
      } else {
        var newW = Math.max(200, Math.min(500, startWidth - (e.clientX - startX)));
        targetEl.style.width = newW + 'px';
        targetEl.style.setProperty('--sb-r-w', newW + 'px');
        _sidebarRightWidth = newW;
        _sidebarRightPrevWidth = newW;
      }
    }
    function onUp() {
      rszEl.classList.remove('active');
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      try { localStorage.setItem('sb_left_width', _sidebarLeftWidth); } catch(e) {}
      try { localStorage.setItem('sb_right_width', _sidebarRightWidth); } catch(e) {}
      _repositionMinimap();
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  rszLeft.addEventListener('mousedown', function(e) { e.preventDefault(); startResize(rszLeft, 'left', e); });
  rszRight.addEventListener('mousedown', function(e) { e.preventDefault(); startResize(rszRight, 'right', e); });

  try {
    var lw = localStorage.getItem('sb_left_width');
    if (lw) { var lwVal = parseInt(lw); if (lwVal >= 150 && lwVal <= 400) { sbLeft.style.width = lwVal + 'px'; sbLeft.style.setProperty('--sb-l-w', lwVal + 'px'); _sidebarLeftWidth = lwVal; _sidebarLeftPrevWidth = lwVal; } }
    var rw = localStorage.getItem('sb_right_width');
    if (rw) { var rwVal = parseInt(rw); if (rwVal >= 200 && rwVal <= 500) { sbRight.style.width = rwVal + 'px'; sbRight.style.setProperty('--sb-r-w', rwVal + 'px'); _sidebarRightWidth = rwVal; _sidebarRightPrevWidth = rwVal; } }
  } catch(e) {}
}

export function initSidebarToggle() {
  var sbLeft = document.getElementById('sb-l');
  var sbRight = document.getElementById('sb-r');
  var toggleLeft = document.getElementById('sb-l-toggle');
  var toggleRight = document.getElementById('sb-r-toggle');
  if (!sbLeft || !sbRight || !toggleLeft || !toggleRight) return;

  try {
    var lc = localStorage.getItem('sb_left_collapsed');
    if (lc === '1') {
      _sidebarLeftCollapsed = true;
      _sidebarLeftPrevWidth = sbLeft.offsetWidth || 208;
      var lw = sbLeft.offsetWidth || 208;
      sbLeft.style.left = '-' + lw + 'px';
      sbLeft.classList.add('collapsed');
      toggleLeft.querySelector('i').className = 'fa-solid fa-angles-right';
    }
  } catch(e) {}
  try {
    var rc = localStorage.getItem('sb_right_collapsed');
    if (rc === '1') {
      _sidebarRightCollapsed = true;
      _sidebarRightPrevWidth = sbRight.offsetWidth || 264;
      var rw = sbRight.offsetWidth || 264;
      sbRight.style.right = '-' + rw + 'px';
      sbRight.classList.add('collapsed');
      toggleRight.querySelector('i').className = 'fa-solid fa-angles-left';
      setTimeout(_repositionMinimap, 220);
    }
  } catch(e) {}

  toggleLeft.addEventListener('click', function() {
    _sidebarLeftCollapsed = !_sidebarLeftCollapsed;
    if (_sidebarLeftCollapsed) {
      _sidebarLeftPrevWidth = sbLeft.offsetWidth || _sidebarLeftPrevWidth;
      var w = sbLeft.offsetWidth || 208;
      sbLeft.style.left = '-' + w + 'px';
      sbLeft.classList.add('collapsed');
      toggleLeft.querySelector('i').className = 'fa-solid fa-angles-right';
    } else {
      sbLeft.classList.remove('collapsed');
      sbLeft.style.left = '0';
      sbLeft.style.width = _sidebarLeftPrevWidth + 'px';
      sbLeft.style.setProperty('--sb-l-w', _sidebarLeftPrevWidth + 'px');
      _sidebarLeftWidth = _sidebarLeftPrevWidth;
      toggleLeft.querySelector('i').className = 'fa-solid fa-angles-left';
    }
    try { localStorage.setItem('sb_left_collapsed', _sidebarLeftCollapsed ? '1' : '0'); } catch(e) {}
  });

    toggleRight.addEventListener('click', function() {
    _sidebarRightCollapsed = !_sidebarRightCollapsed;
    if (_sidebarRightCollapsed) {
      _sidebarRightPrevWidth = sbRight.offsetWidth || _sidebarRightPrevWidth;
      var w = sbRight.offsetWidth || 264;
      sbRight.style.right = '-' + w + 'px';
      sbRight.classList.add('collapsed');
      toggleRight.querySelector('i').className = 'fa-solid fa-angles-left';
    } else {
      sbRight.classList.remove('collapsed');
      sbRight.style.right = '0';
      sbRight.style.width = _sidebarRightPrevWidth + 'px';
      sbRight.style.setProperty('--sb-r-w', _sidebarRightPrevWidth + 'px');
      _sidebarRightWidth = _sidebarRightPrevWidth;
      toggleRight.querySelector('i').className = 'fa-solid fa-angles-right';
    }
    try { localStorage.setItem('sb_right_collapsed', _sidebarRightCollapsed ? '1' : '0'); } catch(e) {}
    setTimeout(_repositionMinimap, 220);
  });
}

export function _repositionMinimap() {
  var mm = document.getElementById('mm');
  var sbRight = document.getElementById('sb-r');
  if (!mm || !sbRight) return;
  var isCollapsed = sbRight.classList.contains('collapsed');
  var rightOffset = isCollapsed ? 10 : (Math.max(sbRight.offsetWidth, 200) + 10);
  mm.style.right = rightOffset + 'px';
}

export function updateMinimap() {
  window.AutomationCore.updateMinimap();
}

export var _isFullscreen = false;

export function toggleFullscreen() {
  _isFullscreen = !_isFullscreen;
  var btn = document.getElementById('btn-fullscreen');
  try {
    var parentDoc = window.parent.document;
    var iframe = parentDoc.getElementById('automationFrame');
    if (_isFullscreen) {
      iframe.style.position = 'fixed';
      iframe.style.top = '0';
      iframe.style.left = '0';
      iframe.style.width = '100vw';
      iframe.style.height = '100vh';
      iframe.style.zIndex = '99999';
      iframe.style.border = 'none';
      if (btn) btn.innerHTML = '<i class="fa-solid fa-down-left-and-up-right-to-center"></i>';
      if (btn) btn.title = '退出全屏';
    } else {
      iframe.style.position = '';
      iframe.style.top = '';
      iframe.style.left = '';
      iframe.style.width = '100%';
      iframe.style.height = '100%';
      iframe.style.zIndex = '';
      iframe.style.border = 'none';
      if (btn) btn.innerHTML = '<i class="fa-solid fa-up-right-and-down-left-from-center"></i>';
      if (btn) btn.title = '全屏';
    }
  } catch (e) {
    var editorRoot = document.getElementById('app');
    if (_isFullscreen) {
      editorRoot.style.position = 'fixed';
      editorRoot.style.top = '0';
      editorRoot.style.left = '0';
      editorRoot.style.width = '100vw';
      editorRoot.style.height = '100vh';
      editorRoot.style.zIndex = '99999';
      if (btn) btn.innerHTML = '<i class="fa-solid fa-down-left-and-up-right-to-center"></i>';
      if (btn) btn.title = '退出全屏';
    } else {
      editorRoot.style.position = '';
      editorRoot.style.top = '';
      editorRoot.style.left = '';
      editorRoot.style.width = '';
      editorRoot.style.height = '';
      editorRoot.style.zIndex = '';
      if (btn) btn.innerHTML = '<i class="fa-solid fa-up-right-and-down-left-from-center"></i>';
      if (btn) btn.title = '全屏';
    }
  }
  setTimeout(function() {
    window.AutomationCore.refreshAllConnections();
    updateMinimap();
  }, 100);
}

export function fitView() {
  var nodes = window.AutomationCore.getNodes();
  if (nodes.length === 0) {
    window.AutomationCore.zoomReset();
    return;
  }
  var minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
  for (var i = 0; i < nodes.length; i++) {
    var n = nodes[i];
    minX = Math.min(minX, n.pos[0]);
    minY = Math.min(minY, n.pos[1]);
    maxX = Math.max(maxX, n.pos[0] + (n.size[0] || 220));
    maxY = Math.max(maxY, n.pos[1] + (n.size[1] || 100));
  }
  var cvArea = document.getElementById('cv-area');
  var cvW = cvArea.clientWidth;
  var cvH = cvArea.clientHeight;
  var pad = 80;
  var gw = maxX - minX + pad * 2;
  var gh = maxY - minY + pad * 2;
  var scale = Math.min(cvW / gw, cvH / gh, 2);
  scale = Math.max(0.15, Math.min(3, scale));
  var cx = (minX + maxX) / 2;
  var cy = (minY + maxY) / 2;
  var offX = cvW / 2 - cx * scale;
  var offY = cvH / 2 - cy * scale;
  window.AutomationCore.setViewport(offX, offY, scale);
  window.AutomationCore.refreshAllConnections();

  updateStatusBar();
  updateMinimap();
}
