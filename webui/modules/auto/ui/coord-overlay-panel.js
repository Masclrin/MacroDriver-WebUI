import { showToast } from '../app/toast.js';

var _visible = false;
var _paused = false;
var _refreshTimer = null;
var _refreshInterval = 200;
var _currentImage = null;
var _statusCache = null;
var _windowList = [];
var _refreshing = false;

function _api() {
  if (window.pywebview && window.pywebview.api) return window.pywebview.api;
  return null;
}

function _getGraphJson() {
  try {
    if (window.AutomationApp && window.AutomationApp.serializeGraph) {
      var data = window.AutomationApp.serializeGraph();
      if (data) return typeof data === 'string' ? data : JSON.stringify(data);
    }
    if (window.AutomationCore && window.AutomationCore.lgGraphObj) {
      return JSON.stringify(window.AutomationCore.lgGraphObj.serialize());
    }
  } catch (e) {
    console.warn('[coord-overlay] serializeGraph error:', e);
  }
  return null;
}

export function initCoordOverlay() {
  var btnCoord = document.getElementById('btn-coord-overlay');
  var cofClose = document.getElementById('cof-close');
  var cofMinimize = document.getElementById('cof-minimize');
  var cofHeader = document.getElementById('cof-header');
  var cofRefreshBtn = document.getElementById('cof-refresh-btn');
  var cofPauseBtn = document.getElementById('cof-pause-btn');
  var cofCaptureMethod = document.getElementById('cof-capture-method');
  var cofWindowSelect = document.getElementById('cof-window-select');

  if (btnCoord) {
    btnCoord.addEventListener('click', function() {
      if (_visible) { closePanel(); } else { openPanel(); }
    });
  }

  if (cofClose) {
    cofClose.addEventListener('click', function() { closePanel(); });
  }

  if (cofMinimize) {
    cofMinimize.addEventListener('click', function() {
      var panel = document.getElementById('coord-overlay-float');
      if (panel) panel.classList.toggle('minimized');
      var icon = cofMinimize.querySelector('i');
      if (icon) {
        icon.className = panel.classList.contains('minimized') ? 'fa-solid fa-angle-up' : 'fa-solid fa-angle-down';
      }
    });
  }

  if (cofHeader) {
    var dragging = false, startX, startY, startLeft, startTop;
    cofHeader.addEventListener('mousedown', function(e) {
      if (e.target.closest('button') || e.target.closest('select')) return;
      dragging = true; startX = e.clientX; startY = e.clientY;
      var panel = document.getElementById('coord-overlay-float');
      var rect = panel.getBoundingClientRect();
      startLeft = rect.left; startTop = rect.top;
      e.preventDefault();
    });
    document.addEventListener('mousemove', function(e) {
      if (!dragging) return;
      var panel = document.getElementById('coord-overlay-float');
      panel.style.left = (startLeft + e.clientX - startX) + 'px';
      panel.style.top = (startTop + e.clientY - startY) + 'px';
      panel.style.right = '';
    });
    document.addEventListener('mouseup', function() { dragging = false; });
  }

  if (cofRefreshBtn) {
    cofRefreshBtn.addEventListener('click', function() { doRefresh(); });
  }

  if (cofPauseBtn) {
    cofPauseBtn.addEventListener('click', function() {
      _paused = !_paused;
      var icon = cofPauseBtn.querySelector('i');
      if (icon) {
        icon.className = _paused ? 'fa-solid fa-play' : 'fa-solid fa-pause';
      }
      cofPauseBtn.title = _paused ? '继续' : '暂停';
    });
  }

  if (cofCaptureMethod) {
    cofCaptureMethod.addEventListener('change', function() {
      updateStatus();
      doRefresh();
    });
  }

  if (cofWindowSelect) {
    cofWindowSelect.addEventListener('change', function() {
      var captureMethod = document.getElementById('cof-capture-method');
      if (captureMethod && captureMethod.value === 'dxgi' && (this.value === '-1' || this.value === '')) {
        var statusText = document.getElementById('cof-status-text');
        if (statusText) statusText.textContent = 'DXGI不支持全部显示器，使用MSS';
      }
      doRefresh();
    });
  }
}

export function openPanel() {
  var panel = document.getElementById('coord-overlay-float');
  if (!panel) return;
  panel.classList.add('visible');
  panel.classList.remove('minimized');
  _visible = true;
  _paused = false;

  var cvArea = document.getElementById('cv-area');
  if (cvArea) {
    var rect = cvArea.getBoundingClientRect();
    if (!panel.style.left || panel.style.left === '0px') {
      panel.style.left = (rect.right - 440) + 'px';
      panel.style.top = (rect.top + 10) + 'px';
      panel.style.right = '';
    }
  }

  updateStatus();
  startRefresh();
}

export function closePanel() {
  var panel = document.getElementById('coord-overlay-float');
  if (!panel) return;
  panel.classList.remove('visible');
  panel.classList.remove('minimized');
  _visible = false;
  stopRefresh();

  var api = _api();
  if (api && api.stop_coord_overlay_dxgi) {
    api.stop_coord_overlay_dxgi().catch(function() {});
  }
}

function startRefresh() {
  stopRefresh();
  doRefresh();
  _refreshTimer = setInterval(function() {
    if (!_paused && _visible) doRefresh();
  }, _refreshInterval);
}

function stopRefresh() {
  if (_refreshTimer) {
    clearInterval(_refreshTimer);
    _refreshTimer = null;
  }
}

function doRefresh() {
  if (_refreshing) return;
  var api = _api();
  if (!api || !api.capture_coordinate_overlay) return;

  _refreshing = true;
  var graphJson = _getGraphJson();
  var captureMethod = document.getElementById('cof-capture-method');
  var method = captureMethod ? captureMethod.value : 'mss';
  var windowSelect = document.getElementById('cof-window-select');
  var monitorIndex = -1;
  if (windowSelect && windowSelect.value) {
    var val = parseInt(windowSelect.value, 10);
    if (!isNaN(val) && val >= 0) monitorIndex = val;
  }

  api.capture_coordinate_overlay(graphJson, method, null, monitorIndex).then(function(res) {
    _refreshing = false;
    if (!res || !res.ok || !res.data) {
      var statusText = document.getElementById('cof-status-text');
      if (statusText && res && res.msg) statusText.textContent = res.msg;
      return;
    }
    var data = res.data;
    _currentImage = data.image;
    renderImage(data);

    var statusDot = document.getElementById('cof-status-dot');
    var statusText = document.getElementById('cof-status-text');
    if (statusDot) {
      statusDot.style.background = data.is_black ? '#f87171' : '#4ade80';
    }
    if (statusText) {
      statusText.textContent = data.capture_method || method;
      if (data.is_black) {
        statusText.textContent += ' (黑屏!)';
        statusText.style.color = '#f87171';
      } else {
        statusText.style.color = '';
      }
    }

    var info = document.getElementById('cof-info');
    if (info) {
      var parts = [data.width + 'x' + data.height, 'DPI:' + (data.dpi_scale || 1).toFixed(2)];
      if (data.monitor_count > 1) parts.push(data.monitor_count + '显示器');
      if (data.node_count !== undefined) parts.push(data.node_count + '节点');
      info.textContent = parts.join(' ');
    }

    var overlayCount = document.getElementById('cof-overlay-count');
    if (overlayCount) {
      overlayCount.textContent = (data.overlay_count || 0) + '个坐标';
    }

    var wrap = document.getElementById('cof-image-wrap');
    var existing = wrap ? wrap.querySelector('.cof-black-warn') : null;
    if (existing) existing.remove();
    if (data.is_black && wrap) {
      var warn = document.createElement('div');
      warn.className = 'cof-black-warn';
      warn.textContent = '黑屏! 截图源可能无法捕获此窗口';
      wrap.appendChild(warn);
    }
  }).catch(function(err) {
    _refreshing = false;
    console.warn('[coord-overlay] refresh error:', err);
  });
}

function renderImage(data) {
  var canvas = document.getElementById('cof-canvas');
  if (!canvas || !data.image) return;

  var img = new Image();
  img.onload = function() {
    canvas.width = img.width;
    canvas.height = img.height;
    var ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);
  };
  img.src = 'data:image/jpeg;base64,' + data.image;
}

function updateStatus() {
  var api = _api();
  if (!api || !api.get_capture_source_status) return;

  api.get_capture_source_status().then(function(res) {
    if (!res || !res.ok || !res.data) return;
    _statusCache = res.data;

    var captureMethod = document.getElementById('cof-capture-method');
    if (captureMethod) {
      var dxgiOption = captureMethod.querySelector('option[value="dxgi"]');
      if (dxgiOption) {
        if (!res.data.dxgi_available) {
          dxgiOption.disabled = true;
          dxgiOption.textContent = 'DXGI (不可用)';
          if (captureMethod.value === 'dxgi') captureMethod.value = 'mss';
        } else {
          dxgiOption.disabled = false;
          dxgiOption.textContent = 'DXGI';
        }
      }
      var bitbltOption = captureMethod.querySelector('option[value="bitblt"]');
      if (bitbltOption) {
        bitbltOption.disabled = false;
        bitbltOption.textContent = 'BitBlt';
      }
    }

    var windowSelect = document.getElementById('cof-window-select');
    if (windowSelect && res.data.monitors) {
      var prevVal = windowSelect.value;
      windowSelect.innerHTML = '';
      var allOpt = document.createElement('option');
      allOpt.value = '-1';
      allOpt.textContent = '全部显示器';
      windowSelect.appendChild(allOpt);
      for (var i = 0; i < res.data.monitors.length; i++) {
        var m = res.data.monitors[i];
        var opt = document.createElement('option');
        opt.value = String(m.index);
        opt.textContent = '显示器' + (m.index + 1) + ' ' + m.width + 'x' + m.height;
        windowSelect.appendChild(opt);
      }
      if (prevVal) {
        var matchOpt = windowSelect.querySelector('option[value="' + prevVal + '"]');
        if (matchOpt) windowSelect.value = prevVal;
      }
    }

    var statusText = document.getElementById('cof-status-text');
    if (statusText && !_currentImage) {
      var parts = [];
      if (res.data.mss_available) parts.push('mss:OK');
      else parts.push('mss:FAIL');
      if (res.data.bitblt_available) parts.push('BitBlt:OK');
      else parts.push('BitBlt:FAIL');
      if (res.data.dxgi_available) parts.push('DXGI:OK');
      else parts.push('DXGI:FAIL');
      statusText.textContent = parts.join(' ');
    }
  }).catch(function() {});
}
