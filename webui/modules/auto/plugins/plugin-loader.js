import { showToast } from '../app/toast.js';
import { renderToolbox, addNodeToCenter } from '../ui/toolbox-renderer.js';

var _pluginLoadRetries = 0;

export function loadPlugins() {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.list_plugins) {
    if (_pluginLoadRetries < 20) {
      _pluginLoadRetries++;
      setTimeout(loadPlugins, 300);
    }
    return;
  }
  _pluginLoadRetries = 0;

  var pluginExpand = document.getElementById('plugin-expand');
  if (!pluginExpand) return;

  var headerEl = pluginExpand.querySelector('.plugin-header');
  pluginExpand.innerHTML = '';
  if (headerEl) pluginExpand.appendChild(headerEl);

  var loadingEl = document.createElement('div');
  loadingEl.className = 'plugin-loading';
  loadingEl.style.cssText = 'padding:8px 10px;font-size:11px;color:var(--txt3);display:flex;align-items:center;gap:6px';
  loadingEl.innerHTML = '<i class="fa-solid fa-spinner fa-spin" style="font-size:10px"></i><span>正在加载插件...</span>';
  pluginExpand.appendChild(loadingEl);

  _cleanupPluginNodes();

  window.pywebview.api.list_plugins().then(function(res) {
    var plugins = [];
    if (res && res.ok && res.data) {
      plugins = res.data;
    } else if (res && Array.isArray(res)) {
      plugins = res;
    } else if (res && !res.ok && res.error) {
      loadingEl.innerHTML = '<i class="fa-solid fa-circle-exclamation" style="color:#ef4444;font-size:10px"></i><span style="color:#ef4444">加载失败: ' + res.error + '</span>';
      showToast('插件列表加载失败: ' + res.error, 'err');
      return;
    }

    if (!plugins || !plugins.length) {
      loadingEl.innerHTML = '<i class="fa-solid fa-puzzle-piece" style="font-size:10px"></i><span>暂无可用插件</span>';
      return;
    }

    var loaded = 0;
    var failed = 0;
    var chain = Promise.resolve();
    for (var i = 0; i < plugins.length; i++) {
      (function(plugin) {
        chain = chain.then(function() {
          return window.pywebview.api.get_plugin_node_js(plugin.id).then(function(jsRes) {
            var jsContent = null;
            if (jsRes && jsRes.ok && jsRes.data && jsRes.data.content) {
              jsContent = jsRes.data.content;
            } else if (jsRes && typeof jsRes === 'string') {
              jsContent = jsRes;
            } else if (jsRes && !jsRes.ok && jsRes.error) {
              failed++;
              var errItem = document.createElement('div');
              errItem.className = 'sb-tool-item';
              errItem.style.opacity = '0.5';
              errItem.innerHTML = '<i class="fa-solid fa-triangle-exclamation" style="color:#ef4444"></i><span>' + plugin.name + ' (加载失败)</span>';
              errItem.title = jsRes.error;
              pluginExpand.appendChild(errItem);
              return;
            }
            if (!jsContent) {
              failed++;
              return;
            }
            try {
              window.__plugin_nodes__ = null;
              var fn = new Function(jsContent + '\nif(typeof __plugin_nodes__!=="undefined"){window.__plugin_nodes__=__plugin_nodes__;}');
              fn();
              var nodes = window.__plugin_nodes__;
              if (!nodes || typeof nodes !== 'object') {
                console.error('[PluginLoader] 插件', plugin.id, '未导出 __plugin_nodes__');
                failed++;
                var errItem2 = document.createElement('div');
                errItem2.className = 'sb-tool-item';
                errItem2.style.opacity = '0.5';
                errItem2.innerHTML = '<i class="fa-solid fa-triangle-exclamation" style="color:#ef4444"></i><span>' + plugin.name + ' (格式错误)</span>';
                errItem2.title = '未导出 __plugin_nodes__';
                pluginExpand.appendChild(errItem2);
                return;
              }

              window.AutomationNodes.registerPluginNodes(nodes);

              for (var nk in nodes) {
                if (!nodes.hasOwnProperty(nk)) continue;
                var def = nodes[nk];
                var item = document.createElement('div');
                item.className = 'sb-tool-item';
                item.draggable = true;
                item.title = '拖拽添加' + def.display_name;
                item.innerHTML = '<i class="' + (def.icon || 'fa-solid fa-puzzle-piece') +
                  '" style="color:' + (def.color || '#a855f7') + '"></i><span>' +
                  def.display_name + '</span>';
                item.addEventListener('dragstart', (function(nt) {
                  return function(e) {
                    e.dataTransfer.setData('text/plain', nt);
                    e.dataTransfer.setData('node-type', nt);
                    e.dataTransfer.effectAllowed = 'copy';
                  };
                })(nk));
                item.addEventListener('dblclick', (function(nt) {
                  return function() { addNodeToCenter(nt); };
                })(nk));
                pluginExpand.appendChild(item);
              }
              loaded++;
            } catch(e) {
              console.error('[PluginLoader] 插件', plugin.id, 'node.js 执行错误:', e);
              failed++;
              var errItem3 = document.createElement('div');
              errItem3.className = 'sb-tool-item';
              errItem3.style.opacity = '0.5';
              errItem3.innerHTML = '<i class="fa-solid fa-triangle-exclamation" style="color:#ef4444"></i><span>' + plugin.name + ' (执行错误)</span>';
              errItem3.title = e.message;
              pluginExpand.appendChild(errItem3);
              showToast('插件 ' + plugin.id + ' 加载失败: ' + e.message, 'err');
            }
          }).catch(function(err) {
            failed++;
            console.error('[PluginLoader] get_plugin_node_js 异常:', plugin.id, err);
          });
        });
      })(plugins[i]);
    }

    chain.then(function() {
      if (loadingEl && loadingEl.parentNode) {
        loadingEl.remove();
      }
      renderToolbox();
      if (loaded > 0) {
        showToast('已加载 ' + loaded + ' 个插件' + (failed > 0 ? '，' + failed + ' 个失败' : ''), failed > 0 ? 'warn' : 'ok');
      } else if (failed > 0) {
        showToast('所有插件加载失败', 'err');
      }
    });
  }).catch(function(err) {
    console.error('[PluginLoader] list_plugins 失败:', err);
    if (loadingEl && loadingEl.parentNode) {
      loadingEl.innerHTML = '<i class="fa-solid fa-circle-exclamation" style="color:#ef4444;font-size:10px"></i><span style="color:#ef4444">插件列表获取失败</span>';
    }
    showToast('插件列表获取失败', 'err');
  });
}

function _cleanupPluginNodes() {
  var defs = window.AutomationNodes._nodeDefs;
  var cats = window.AutomationNodes._categories;
  var toRemove = [];
  for (var k in defs) {
    if (defs.hasOwnProperty(k) && k.startsWith('plugin/')) {
      toRemove.push(k);
    }
  }
  for (var i = 0; i < toRemove.length; i++) {
    delete defs[toRemove[i]];
  }
  if (cats.plugin) {
    cats.plugin.nodes = [];
  }
  if (window.pywebview && window.pywebview.api && window.pywebview.api.unregister_plugin_nodes) {
    window.pywebview.api.unregister_plugin_nodes();
  }
}
