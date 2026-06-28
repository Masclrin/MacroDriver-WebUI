import { showToast } from '../app/toast.js';

export function browseMacroPath(nodeId, key) {
  var propKey = key || 'path';
  if (window.pywebview && window.pywebview.api && window.pywebview.api.list_macro_tree) {
    window.pywebview.api.list_macro_tree('').then(function(res) {
      var treeData = (res && res.tree) ? res.tree : (res && res.items ? res.items : null);
      if (treeData) {
        showMacroTreePicker(nodeId, treeData, propKey);
      } else {
        showToast('未找到宏文件', 'warn');
      }
    }).catch(function() { showToast('无法访问宏目录', 'err'); });
  } else if (window.pywebview && window.pywebview.api && window.pywebview.api.list_macros) {
    window.pywebview.api.list_macros().then(function(res) {
      var items = (res && res.items) ? res.items : (res && res.data ? res.data : []);
      if (items && items.length > 0) {
        showMacroPicker(nodeId, items, propKey);
      } else {
        showToast('未找到宏文件', 'warn');
      }
    }).catch(function() { showToast('无法访问宏目录', 'err'); });
  } else {
    showToast('需要后端支持以浏览宏文件', 'inf');
  }
}

export function showMacroTreePicker(nodeId, treeData, propKey) {
  var modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.innerHTML =
    '<div class="modal-content" style="width:420px;max-height:520px">' +
      '<div class="modal-header"><span>选择宏</span><button class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()"><i class="fa-solid fa-xmark"></i></button></div>' +
      '<div class="modal-body" style="padding:8px;max-height:420px;overflow-y:auto">' +
        '<ul id="macro-tree-picker-list" style="list-style:none;padding:0;margin:0"></ul>' +
      '</div>' +
    '</div>';
  document.body.appendChild(modal);

  var listContainer = modal.querySelector('#macro-tree-picker-list');
  if (listContainer && window.renderMacroTreeList) {
    window.renderMacroTreeList({
      container: listContainer,
      tree: treeData,
      viewId: 'auto-macro-picker',
      selectedPath: null,
      openedPath: null,
      onSelect: function(path) {
        var node = window.AutomationCore.lgGraphObj ? window.AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
        if (node) {
          node.properties[propKey] = path;
          window.AutomationProperty.render(node);
          window.AutomationCore.refreshNode(node);
        }
        modal.remove();
      },
      onFill: function(path) {
        var node = window.AutomationCore.lgGraphObj ? window.AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
        if (node) {
          node.properties[propKey] = path;
          window.AutomationProperty.render(node);
          window.AutomationCore.refreshNode(node);
        }
        modal.remove();
      }
    });
  } else {
    listContainer.innerHTML = '<div style="padding:12px;color:var(--txt3);text-align:center">宏树组件未加载</div>';
  }
  modal.addEventListener('click', function(e) { if (e.target === modal) modal.remove(); });
}

export function browseFolderPath(nodeId, key) {
  var propKey = key || 'template_folder';
  if (window.pywebview && window.pywebview.api && window.pywebview.api.choose_folder) {
    window.pywebview.api.choose_folder().then(function(res) {
      if (res && res.ok && res.data && res.data.path) {
        var node = window.AutomationCore.lgGraphObj ? window.AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
        if (node) {
          node.properties[propKey] = res.data.path;
          if (window.AutomationProperty) AutomationProperty.render(node);
          if (window.AutomationCore.refreshNode) window.AutomationCore.refreshNode(node);
        }
      }
    }).catch(function() { showToast('无法打开文件夹选择器', 'err'); });
  } else {
    showToast('需要后端支持以浏览文件夹', 'inf');
  }
}

export function browseTemplatePath(nodeId, key) {
  var propKey = key || 'template_path';
  if (window.pywebview && window.pywebview.api && window.pywebview.api.list_templates) {
    window.pywebview.api.list_templates().then(function(res) {
      if (res && res.ok && res.data && res.data.length > 0) {
        showTemplatePicker(nodeId, res.data, propKey);
      } else {
        showToast('未找到模板图片，请将图片放入"图片模板"文件夹', 'warn');
      }
    }).catch(function() { showToast('无法访问模板目录', 'err'); });
  } else {
    showToast('需要后端支持以浏览模板图片', 'inf');
  }
}

export function showTemplatePicker(nodeId, templates, propKey) {
  var modal = document.createElement('div');
  modal.className = 'modal-overlay';
  var listHtml = '';
  for (var i = 0; i < templates.length; i++) {
    listHtml += '<div class="cx-i" data-path="' + templates[i].path + '" style="padding:10px 14px">' + templates[i].name + '</div>';
  }
  modal.innerHTML =
    '<div class="modal-content" style="width:400px;max-height:500px">' +
      '<div class="modal-header"><span>选择模板图片</span><button class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()"><i class="fa-solid fa-xmark"></i></button></div>' +
      '<div class="modal-body" style="padding:4px 0;max-height:380px;overflow-y:auto">' + listHtml + '</div>' +
    '</div>';
  document.body.appendChild(modal);
  var pathItems = modal.querySelectorAll('[data-path]');
  for (var j = 0; j < pathItems.length; j++) {
    pathItems[j].addEventListener('click', function() {
      var node = window.AutomationCore.lgGraphObj ? window.AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
      if (node) {
        node.properties[propKey] = this.dataset.path;
        window.AutomationProperty.render(node);
        window.AutomationCore.refreshNode(node);
      }
      modal.remove();
    });
  }
  modal.addEventListener('click', function(e) { if (e.target === modal) modal.remove(); });
}

export function showMacroPicker(nodeId, macros, propKey) {
  var modal = document.createElement('div');
  modal.className = 'modal-overlay';
  var listHtml = '';
  for (var i = 0; i < macros.length; i++) {
    listHtml += '<div class="cx-i" data-path="' + macros[i].path + '" style="padding:10px 14px">' + macros[i].name + '</div>';
  }
  modal.innerHTML =
    '<div class="modal-content" style="width:400px;max-height:500px">' +
      '<div class="modal-header"><span>选择宏文件</span><button class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()"><i class="fa-solid fa-xmark"></i></button></div>' +
      '<div class="modal-body" style="padding:4px 0;max-height:380px;overflow-y:auto">' + listHtml + '</div>' +
    '</div>';
  document.body.appendChild(modal);
  var pathItems = modal.querySelectorAll('[data-path]');
  for (var j = 0; j < pathItems.length; j++) {
    pathItems[j].addEventListener('click', function() {
      var node = window.AutomationCore.lgGraphObj ? window.AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
      if (node) {
        node.properties[propKey] = this.dataset.path;
        window.AutomationProperty.render(node);
        window.AutomationCore.refreshNode(node);
      }
      modal.remove();
    });
  }
  modal.addEventListener('click', function(e) { if (e.target === modal) modal.remove(); });
}

export function browseWindowList(nodeId, paramKey) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_window_list) {
    window.pywebview.api.get_window_list().then(function(res) {
      if (res && res.ok && res.data && res.data.length > 0) {
        showWindowPicker(nodeId, paramKey, res.data);
      } else {
        showToast('未找到可见窗口', 'warn');
      }
    }).catch(function() { showToast('无法获取窗口列表', 'err'); });
  } else {
    showToast('需要后端支持以选择窗口', 'inf');
  }
}

export function showWindowPicker(nodeId, paramKey, windows) {
  var modal = document.createElement('div');
  modal.className = 'modal-overlay';
  var listHtml = '';
  for (var i = 0; i < windows.length; i++) {
    var w = windows[i];
    var displayText = w.title + ' [' + w.class_name + ']';
    listHtml += '<div class="cx-i" data-hwnd="' + w.hwnd + '" data-hwnd-title="' + w.title.replace(/"/g, '&quot;') + '" style="padding:8px 14px;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="' + displayText.replace(/"/g, '&quot;') + '">' + displayText + '</div>';
  }
  modal.innerHTML =
    '<div class="modal-content" style="width:450px;max-height:500px">' +
      '<div class="modal-header"><span>选择窗口</span><button class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()"><i class="fa-solid fa-xmark"></i></button></div>' +
      '<div class="modal-body" style="padding:4px 0;max-height:380px;overflow-y:auto">' + listHtml + '</div>' +
    '</div>';
  document.body.appendChild(modal);
  var items = modal.querySelectorAll('[data-hwnd-title]');
  for (var j = 0; j < items.length; j++) {
    items[j].addEventListener('click', function() {
      var node = window.AutomationCore.lgGraphObj ? window.AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
      if (node) {
        node.properties[paramKey] = this.dataset.hwnd;
        window.AutomationProperty.render(node);
        window.AutomationCore.refreshNode(node);
      }
      modal.remove();
    });
  }
  modal.addEventListener('click', function(e) { if (e.target === modal) modal.remove(); });
}

export function browseProgramFile(nodeId, paramKey) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.choose_program_file) {
    window.pywebview.api.choose_program_file().then(function(res) {
      var fullPath = null;
      if (res && res.ok && !res.canceled) {
        if (res.data && res.data.path) { fullPath = res.data.path; }
        else if (res.path) { fullPath = res.path; }
      }
      if (fullPath) {
        var node = window.AutomationCore.lgGraphObj ? window.AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
        if (node) {
          node.properties[paramKey] = fullPath;
          var lastSlash = Math.max(fullPath.lastIndexOf('/'), fullPath.lastIndexOf('\\'));
          if (lastSlash > 0 && node.properties.work_dir !== undefined) {
            node.properties.work_dir = fullPath.substring(0, lastSlash);
          }
          window.AutomationProperty.render(node);
          window.AutomationCore.refreshNode(node);
        }
      }
    }).catch(function() { showToast('无法打开文件选择器', 'err'); });
  } else {
    showToast('需要后端支持以选择程序文件', 'inf');
  }
}

export function browseWindowTitle(nodeId, paramKey) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_window_list) {
    window.pywebview.api.get_window_list().then(function(res) {
      if (res && res.ok && res.data && res.data.length > 0) {
        showWindowTitlePicker(nodeId, paramKey, res.data);
      } else {
        showToast('未找到可见窗口', 'warn');
      }
    }).catch(function() { showToast('无法获取窗口列表', 'err'); });
  } else {
    showToast('需要后端支持以选择窗口', 'inf');
  }
}

export function showWindowTitlePicker(nodeId, paramKey, windows) {
  var modal = document.createElement('div');
  modal.className = 'modal-overlay';
  var listHtml = '<div style="padding:8px 14px"><input type="text" id="window-title-search" placeholder="搜索窗口标题..." style="width:100%;padding:6px 10px;background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--rs);color:var(--txt);font-size:12px;outline:none;box-sizing:border-box"></div>';
  listHtml += '<div id="window-title-list" style="max-height:340px;overflow-y:auto">';
  for (var i = 0; i < windows.length; i++) {
    var w = windows[i];
    var displayText = w.title + ' [' + w.class_name + ']';
    listHtml += '<div class="cx-i" data-window-title="' + w.title.replace(/"/g, '&quot;') + '" style="padding:8px 14px;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer" title="' + displayText.replace(/"/g, '&quot;') + '">' + displayText + '</div>';
  }
  listHtml += '</div>';
  modal.innerHTML =
    '<div class="modal-content" style="width:480px;max-height:500px">' +
      '<div class="modal-header"><span>选择窗口</span><button class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()"><i class="fa-solid fa-xmark"></i></button></div>' +
      '<div class="modal-body" style="padding:4px 0">' + listHtml + '</div>' +
    '</div>';
  document.body.appendChild(modal);
  var searchInput = modal.querySelector('#window-title-search');
  var listContainer = modal.querySelector('#window-title-list');
  if (searchInput && listContainer) {
    searchInput.addEventListener('input', function() {
      var keyword = this.value.toLowerCase();
      var items = listContainer.querySelectorAll('[data-window-title]');
      for (var j = 0; j < items.length; j++) {
        var title = (items[j].dataset.windowTitle || '').toLowerCase();
        items[j].style.display = title.indexOf(keyword) >= 0 ? '' : 'none';
      }
    });
    searchInput.focus();
  }
  var items = modal.querySelectorAll('[data-window-title]');
  for (var j = 0; j < items.length; j++) {
    items[j].addEventListener('click', function() {
      var node = window.AutomationCore.lgGraphObj ? window.AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
      if (node) {
        node.properties[paramKey] = this.dataset.windowTitle;
        window.AutomationProperty.render(node);
        window.AutomationCore.refreshNode(node);
      }
      modal.remove();
    });
  }
  modal.addEventListener('click', function(e) { if (e.target === modal) modal.remove(); });
}

export function browseProcessList(nodeId, paramKey) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_process_list) {
    window.pywebview.api.get_process_list().then(function(res) {
      if (res && res.ok && res.data && res.data.length > 0) {
        showProcessPicker(nodeId, paramKey, res.data);
      } else {
        showToast('未找到运行中的进程', 'warn');
      }
    }).catch(function() { showToast('无法获取进程列表', 'err'); });
  } else {
    showToast('需要后端支持以选择进程', 'inf');
  }
}

export function showProcessPicker(nodeId, paramKey, processes) {
  var modal = document.createElement('div');
  modal.className = 'modal-overlay';
  var listHtml = '<div style="padding:8px 14px"><input type="text" id="process-search" placeholder="搜索进程名..." style="width:100%;padding:6px 10px;background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--rs);color:var(--txt);font-size:12px;outline:none;box-sizing:border-box"></div>';
  listHtml += '<div id="process-list" style="max-height:340px;overflow-y:auto">';
  for (var i = 0; i < processes.length; i++) {
    var p = processes[i];
    listHtml += '<div class="cx-i" data-process-name="' + p.name.replace(/"/g, '&quot;') + '" style="padding:8px 14px;font-size:12px;display:flex;justify-content:space-between;cursor:pointer"><span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1">' + p.name + '</span><span style="color:var(--txt3);font-size:10px;flex-shrink:0;margin-left:8px">PID: ' + p.pid + '</span></div>';
  }
  listHtml += '</div>';
  modal.innerHTML =
    '<div class="modal-content" style="width:420px;max-height:500px">' +
      '<div class="modal-header"><span>选择进程</span><button class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()"><i class="fa-solid fa-xmark"></i></button></div>' +
      '<div class="modal-body" style="padding:4px 0">' + listHtml + '</div>' +
    '</div>';
  document.body.appendChild(modal);
  var searchInput = modal.querySelector('#process-search');
  var listContainer = modal.querySelector('#process-list');
  if (searchInput && listContainer) {
    searchInput.addEventListener('input', function() {
      var keyword = this.value.toLowerCase();
      var items = listContainer.querySelectorAll('[data-process-name]');
      for (var j = 0; j < items.length; j++) {
        var name = (items[j].dataset.processName || '').toLowerCase();
        items[j].style.display = name.indexOf(keyword) >= 0 ? '' : 'none';
      }
    });
    searchInput.focus();
  }
  var items = modal.querySelectorAll('[data-process-name]');
  for (var j = 0; j < items.length; j++) {
    items[j].addEventListener('click', function() {
      var node = window.AutomationCore.lgGraphObj ? window.AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
      if (node) {
        node.properties[paramKey] = this.dataset.processName;
        window.AutomationProperty.render(node);
        window.AutomationCore.refreshNode(node);
      }
      modal.remove();
    });
  }
  modal.addEventListener('click', function(e) { if (e.target === modal) modal.remove(); });
}

export function runPreview(defKey, nodeId) {
  var node = window.AutomationCore.lgGraphObj ? window.AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
  if (!node) return;
  var area = document.getElementById('preview-area');
  if (!area) return;
  area.innerHTML = '<span style="color:var(--txt3)">正在预览...</span>';

  if (window.pywebview && window.pywebview.api) {
    var params = node.properties;
    if (defKey.indexOf('check_color') >= 0 || defKey.indexOf('monitor_color') >= 0) {
      window.pywebview.api.preview_color(
        params.mode,
        JSON.stringify(params.rect || [0,0,10,10]),
        params.hwnd_var || '',
        params.target_color || '#FF0000',
        parseFloat(params.tolerance) || 10,
        params.check_mode || 'contain',
        params.sample_mode || 'center',
        parseFloat(params.area_ratio_threshold) || 0.5
      )
        .then(function(res) {
          if (res && res.ok && res.data) {
            var d = res.data;
            var html = '<div style="text-align:center">';
            html += '<div style="display:flex;align-items:center;gap:8px;justify-content:center;margin-bottom:4px">';
            html += '<div style="width:24px;height:24px;border-radius:4px;background:' + (d.center_color || '#000') + ';border:1px solid var(--border)" title="中心点颜色"></div>';
            html += '<span style="font-family:var(--fmo);font-size:12px;color:var(--txt)">中心: ' + (d.center_color || 'N/A') + '</span>';
            html += '</div>';
            html += '<div style="display:flex;align-items:center;gap:8px;justify-content:center;margin-bottom:4px">';
            html += '<div style="width:24px;height:24px;border-radius:4px;background:' + (d.mean_color || '#000') + ';border:1px solid var(--border)" title="平均色"></div>';
            html += '<span style="font-family:var(--fmo);font-size:12px;color:var(--txt)">平均: ' + (d.mean_color || 'N/A') + '</span>';
            html += '</div>';
            if (d.check_found !== undefined) {
              var modeLabel = {'contain':'包含匹配','change':'变化检测','area':'面积占比'}[d.check_mode] || d.check_mode;
              var foundColor = d.check_found ? 'var(--green)' : 'var(--red)';
              var foundText = d.check_found ? '匹配' : '不匹配';
              html += '<div style="border-top:1px solid var(--border);padding-top:6px;margin-top:4px">';
              html += '<div style="font-size:11px;color:var(--txt2);margin-bottom:2px">' + modeLabel + '检测结果</div>';
              html += '<div style="display:flex;align-items:center;gap:6px;justify-content:center">';
              if (d.actual_color) {
                html += '<div style="width:18px;height:18px;border-radius:3px;background:' + d.actual_color + ';border:1px solid var(--border)" title="实际检测色"></div>';
              }
              html += '<span style="color:' + foundColor + ';font-weight:600;font-size:13px">' + foundText + '</span>';
              html += '<span style="font-size:11px;color:var(--txt2)">(差值: ' + d.diff + ')</span>';
              html += '</div></div>';
            }
            html += '</div>';
            area.innerHTML = html;
          } else {
            area.innerHTML = '<span style="color:var(--red)">' + ((res && res.error) || '预览失败') + '</span>';
          }
        })
        .catch(function(err) { area.innerHTML = '<span style="color:var(--red)">' + (err.message || err) + '</span>'; });
    } else if (defKey.indexOf('check_ocr') >= 0 || defKey.indexOf('monitor_ocr') >= 0) {
      window.pywebview.api.preview_ocr(params.mode, JSON.stringify(params.rect || [0,0,100,30]), params.hwnd_var || '', params.engine || 'rapidocr')
        .then(function(res) {
          if (res && res.ok && res.data) {
            var d = res.data;
            area.innerHTML = '<div style="text-align:center">' +
              '<div style="font-family:var(--fmo);font-size:14px;color:var(--txt)">' + (d.text || '(空)') + '</div>' +
              '<div style="font-size:11px;color:var(--txt2);margin-top:4px">置信度: ' + (d.confidence ? (d.confidence * 100).toFixed(1) : '-') + '%</div>' +
            '</div>';
          } else {
            area.innerHTML = '<span style="color:var(--red)">' + ((res && res.error) || '预览失败') + '</span>';
          }
        })
        .catch(function(err) { area.innerHTML = '<span style="color:var(--red)">' + (err.message || err) + '</span>'; });
    } else if (defKey.indexOf('preset_find_click') >= 0 || defKey.indexOf('check_image') >= 0) {
      var tplPath = params.template_path || '';
      if (!tplPath) {
        area.innerHTML = '<span style="color:var(--txt2)">请先选择模板图片</span>';
        return;
      }
      window.pywebview.api.preview_image_match(
        params.mode || 'screen',
        JSON.stringify(params.rect || [0,0,0,0]),
        params.hwnd_var || '',
        tplPath,
        parseFloat(params.threshold) || 0.8,
        params.method || 'tm_ccoeff_normed',
        params.multi_match || false,
        parseInt(params.pyramid_levels) || 2
      )
        .then(function(res) {
          if (res && res.ok && res.data) {
            var d = res.data;
            var html = '<div style="text-align:center">';
            var foundColor = d.found ? 'var(--green)' : 'var(--red)';
            var foundText = d.found ? '匹配成功' : '未匹配';
            html += '<div style="font-weight:600;font-size:14px;color:' + foundColor + '">' + foundText + '</div>';
            html += '<div style="font-size:12px;color:var(--txt2);margin-top:4px">匹配度: ' + (d.score * 100).toFixed(1) + '% / 阈值: ' + (d.threshold * 100).toFixed(0) + '%</div>';
            if (d.found) {
              html += '<div style="font-size:11px;color:var(--txt2);margin-top:2px">位置: (' + d.match_x + ', ' + d.match_y + ')</div>';
              if (d.match_count > 1) {
                html += '<div style="font-size:11px;color:var(--txt2)">匹配数: ' + d.match_count + '</div>';
              }
            }
            html += '</div>';
            area.innerHTML = html;
          } else {
            area.innerHTML = '<span style="color:var(--red)">' + ((res && res.error) || '预览失败') + '</span>';
          }
        })
        .catch(function(err) { area.innerHTML = '<span style="color:var(--red)">' + (err.message || err) + '</span>'; });
    } else if (defKey.indexOf('preset_read_text') >= 0) {
      window.pywebview.api.preview_read_text(
        params.mode || 'screen',
        JSON.stringify(params.rect || [0,0,100,30]),
        params.hwnd_var || '',
        params.read_mode || 'all'
      )
        .then(function(res) {
          if (res && res.ok && res.data) {
            var d = res.data;
            var html = '<div style="text-align:center">';
            html += '<div style="font-family:var(--fmo);font-size:14px;color:var(--txt)">' + (d.text || '(空)') + '</div>';
            html += '<div style="font-size:11px;color:var(--txt2);margin-top:4px">置信度: ' + (d.confidence ? (d.confidence * 100).toFixed(1) : '-') + '%</div>';
            if (d.raw_number) {
              html += '<div style="font-size:11px;color:var(--txt2)">数字: ' + d.raw_number + '</div>';
            }
            html += '</div>';
            area.innerHTML = html;
          } else {
            area.innerHTML = '<span style="color:var(--red)">' + ((res && res.error) || '预览失败') + '</span>';
          }
        })
        .catch(function(err) { area.innerHTML = '<span style="color:var(--red)">' + (err.message || err) + '</span>'; });
    } else if (defKey.indexOf('check_digits') >= 0) {
      window.pywebview.api.preview_digits(
        params.mode || 'screen',
        JSON.stringify(params.rect || [0,0,0,0]),
        params.hwnd_var || '',
        params.binary_method || 'otsu',
        params.split_method || 'contour',
        parseInt(params.split_width) || 0,
        params.template_folder || '',
        params.template_sets || '',
        params.match_method || 'auto',
        parseFloat(params.threshold) || 0.8
      )
        .then(function(res) {
          if (res && res.ok && res.data) {
            var d = res.data;
            var methodLabel = {'contour':'轮廓分割','projection':'投影分割(抗噪)','fixed_width':'等宽分割(对位)'}[params.split_method] || '轮廓分割';
            var html = '<div style="text-align:center">';

            // Top banner: recognized digit string
            if (d.templates_loaded && d.digit_string !== undefined) {
              html += '<div style="font-size:22px;font-weight:700;letter-spacing:4px;padding:8px 0;color:var(--accent,#3b82f6);font-family:Consolas,monospace">'
                + (d.digit_string || '—') + '</div>';
              html += '<div style="font-size:11px;color:var(--txt2);margin-bottom:6px">'
                + '分割: ' + methodLabel + ' | 切出 ' + d.segment_count + ' 块'
                + ' | 匹配: ' + (params.match_method === 'hamming' ? '汉明' : (params.match_method === 'template' ? '模板' : '自动'))
                + ' | 阈值: ' + (parseFloat(params.threshold) || 0.8).toFixed(1)
                + '</div>';
            } else {
              html += '<div style="font-size:22px;font-weight:700;letter-spacing:4px;padding:8px 0;color:var(--txt2);font-family:Consolas,monospace">—</div>';
              html += '<div style="font-size:11px;color:var(--txt2);margin-bottom:6px">分割: ' + methodLabel + ' | 切出 ' + d.segment_count + ' 块</div>';
              if (d.template_error) {
                html += '<div style="font-size:10px;color:var(--orange,#f59e0b);margin-bottom:4px">⚠ ' + d.template_error + '</div>';
              }
            }

            if (d.visualization_b64) {
              html += '<img src="data:image/jpeg;base64,' + d.visualization_b64 + '" style="max-width:100%;border-radius:4px;border:1px solid var(--border);margin-top:4px" alt="分割预览">';
            }

            // Per-segment details
            if (d.digit_matches && d.digit_matches.length > 0) {
              html += '<div style="font-size:10px;color:var(--txt3);margin-top:6px;text-align:left;max-height:100px;overflow-y:auto">';
              for (var mi = 0; mi < d.digit_matches.length; mi++) {
                var m = d.digit_matches[mi];
                var bg = m.digit >= 0 ? 'var(--bg-card,#1e293b)' : 'rgba(239,68,68,0.15)';
                var digitLabel = m.digit >= 0 ? String(m.digit) : '?';
                html += '<span style="display:inline-block;margin:1px 2px;padding:0 4px;background:' + bg
                  + ';border-radius:2px;font-family:Consolas,monospace">'
                  + '#' + mi + ' <b>' + digitLabel + '</b>';
                if (m.digit >= 0) {
                  html += ' <span style="color:var(--txt3)">' + m.score.toFixed(2) + '</span>';
                  if (m.font) html += ' ' + m.font;
                } else if (m.note) {
                  html += ' <span style="color:var(--red)">' + m.note + '</span>';
                }
                html += '</span>';
              }
              html += '</div>';
            }

            html += '</div>';
            area.innerHTML = html;
          } else {
            area.innerHTML = '<span style="color:var(--red)">' + ((res && res.error) || '预览失败') + '</span>';
          }
        })
        .catch(function(err) { area.innerHTML = '<span style="color:var(--red)">' + (err.message || err) + '</span>'; });
    } else {
      area.innerHTML = '<span style="color:var(--txt3)">此节点暂不支持预览</span>';
    }
  } else {
    setTimeout(function() {
      area.innerHTML = '<div style="text-align:center;color:var(--txt3)">需要后端支持</div>';
    }, 500);
  }
}

export function browseScriptPath(nodeId, key) {
  var propKey = key || 'script_path';
  if (window.pywebview && window.pywebview.api && window.pywebview.api.list_auto_scripts) {
    window.pywebview.api.list_auto_scripts().then(function(res) {
      var scripts = [];
      if (res && res.ok && res.data) {
        scripts = res.data;
      }
      if (scripts.length > 0) {
        showScriptPicker(nodeId, scripts, propKey);
      } else {
        showToast('未找到自动化脚本', 'warn');
      }
    }).catch(function() { showToast('无法获取脚本列表', 'err'); });
  } else {
    showToast('需要后端支持以浏览脚本', 'inf');
  }
}

export function showScriptPicker(nodeId, scripts, propKey) {
  var modal = document.createElement('div');
  modal.className = 'modal-overlay';
  var listHtml = '<div style="padding:8px 14px"><input type="text" id="script-search" placeholder="搜索脚本..." style="width:100%;padding:6px 10px;background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--rs);color:var(--txt);font-size:12px;outline:none;box-sizing:border-box"></div>';
  listHtml += '<div id="script-list" style="max-height:340px;overflow-y:auto">';
  for (var i = 0; i < scripts.length; i++) {
    var s = scripts[i];
    var displayName = s.name || s.path || '';
    listHtml += '<div class="cx-i" data-script-path="' + (s.path || '').replace(/"/g, '&quot;') + '" style="padding:8px 14px;font-size:12px;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="' + (s.path || '').replace(/"/g, '&quot;') + '">' + displayName + '</div>';
  }
  listHtml += '</div>';
  modal.innerHTML =
    '<div class="modal-content" style="width:450px;max-height:500px">' +
      '<div class="modal-header"><span>选择子脚本</span><button class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()"><i class="fa-solid fa-xmark"></i></button></div>' +
      '<div class="modal-body" style="padding:4px 0">' + listHtml + '</div>' +
    '</div>';
  document.body.appendChild(modal);

  var searchInput = modal.querySelector('#script-search');
  var listContainer = modal.querySelector('#script-list');
  if (searchInput && listContainer) {
    searchInput.addEventListener('input', function() {
      var keyword = this.value.toLowerCase();
      var items = listContainer.querySelectorAll('[data-script-path]');
      for (var j = 0; j < items.length; j++) {
        var path = (items[j].dataset.scriptPath || '').toLowerCase();
        items[j].style.display = path.indexOf(keyword) >= 0 ? '' : 'none';
      }
    });
    searchInput.focus();
  }

  var items = modal.querySelectorAll('[data-script-path]');
  for (var j = 0; j < items.length; j++) {
    items[j].addEventListener('click', function() {
      var node = window.AutomationCore.lgGraphObj ? window.AutomationCore.lgGraphObj.getNodeById(nodeId) : null;
      if (node) {
        node.properties[propKey] = this.dataset.scriptPath;
        window.AutomationProperty.render(node);
        window.AutomationCore.refreshNode(node);
      }
      modal.remove();
    });
  }
  modal.addEventListener('click', function(e) { if (e.target === modal) modal.remove(); });
}
