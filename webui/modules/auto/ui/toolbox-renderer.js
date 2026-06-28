import { TOOLBOX_CATEGORIES } from '../app/config.js';
import { showToast } from '../app/toast.js';
import { updateStatusBar, undoManager } from './ui-utils.js';
import { updateMinimap } from './sidebar.js';

export function renderToolbox(filterText) {
  var container = document.getElementById('toolbox-categories');
  container.innerHTML = '';
  var filter = (filterText || '').toLowerCase().trim();
  var nodeDefs = window.AutomationNodes._nodeDefs;

  for (var ci = 0; ci < TOOLBOX_CATEGORIES.length; ci++) {
    var cat = TOOLBOX_CATEGORIES[ci];
    var catNodes = [];
    for (var typeKey in nodeDefs) {
      if (!nodeDefs.hasOwnProperty(typeKey)) continue;
      var def = nodeDefs[typeKey];
      if (def.category !== cat.id) continue;
      if (filter && def.display_name.toLowerCase().indexOf(filter) < 0 && typeKey.toLowerCase().indexOf(filter) < 0) {
        var pinyin = (window.AutomationNodes && window.AutomationNodes._pinyinMap) ? window.AutomationNodes._pinyinMap[typeKey] : '';
        if (!pinyin || pinyin.toLowerCase().indexOf(filter) < 0) continue;
      }
      catNodes.push({ type: typeKey, def: def });
    }

    if (catNodes.length === 0 && filter) continue;

    var catEl = document.createElement('div');
    catEl.className = 'sb-c' + (cat.id === 'utility' || cat.id === 'control' ? ' col' : '');

    var header = document.createElement('div');
    header.className = 'sb-ch';
    header.innerHTML =
      '<span class="cd" style="width:8px;height:8px;border-radius:2px;background:' + cat.color + ';display:inline-block;flex-shrink:0"></span>' +
      '<span style="flex:1">' + cat.name + '</span>' +
      '<span style="font-size:9px;color:var(--txt3);font-family:var(--fmo)">' + catNodes.length + '</span>' +
      '<i class="fa-solid fa-chevron-down ca"></i>';
    header.addEventListener('click', function() { this.parentElement.classList.toggle('col'); });

    var nodesEl = document.createElement('div');
    nodesEl.className = 'sb-ci';

    for (var ni = 0; ni < catNodes.length; ni++) {
      var item = document.createElement('div');
      item.className = 'sb-ni';
      item.dataset.nodeType = catNodes[ni].type;
      item.title = catNodes[ni].def.display_name + ' (' + catNodes[ni].type + ')';
      var iconClass = catNodes[ni].def.icon || 'fa-solid fa-circle';
      item.innerHTML = '<i class="' + iconClass + '" style="color:' + catNodes[ni].def.color + '"></i><span>' + catNodes[ni].def.display_name + '</span>';
      item.draggable = true;
      item.addEventListener('dragstart', (function(nt) {
        return function(e) {
          e.dataTransfer.setData('text/plain', nt);
          e.dataTransfer.setData('node-type', nt);
          e.dataTransfer.effectAllowed = 'copy';
        };
      })(catNodes[ni].type));
      item.addEventListener('dblclick', (function(nt) {
        return function() { addNodeToCenter(nt); };
      })(catNodes[ni].type));
      nodesEl.appendChild(item);
    }

    catEl.appendChild(header);
    catEl.appendChild(nodesEl);
    container.appendChild(catEl);
  }
}

export function addNodeToCenter(nodeType) {
  var node = window.AutomationCore.addNodeAtCenter(nodeType);
  if (!node) { showToast('未知节点类型: ' + nodeType, 'err'); return; }
  window.AutomationCore.selectNode(node);
  updateStatusBar();
  updateMinimap();
  undoManager.push();
}
