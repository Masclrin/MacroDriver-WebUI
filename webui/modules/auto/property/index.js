'use strict';

import './utils.js';
import './renderers.js';
import './interactions.js';
import './var-selector.js';
import './events.js';
import { _escapeHtml } from '../core/utils.js';
import { _annotationPresetColors, _groupPresetColors } from '../core/constants.js';

var _pe = _escapeHtml;

window.AutomationProperty._renderColorSwatches = function(presetColors, activeBg, colorAttr, bgAttr) {
    var html = '';
    for (var i = 0; i < presetColors.length; i++) {
        var pc = presetColors[i];
        var isActive = activeBg === pc.bg;
        html += '<div style="width:24px;height:24px;border-radius:4px;cursor:pointer;border:2px solid ' + (isActive ? 'var(--acc)' : 'transparent') + ';box-sizing:border-box;transition:all .15s;flex-shrink:0;background:' + pc.color + '" ' + colorAttr + '="' + pc.color + '" ' + bgAttr + '="' + pc.bg + '" title="' + pc.name + '"></div>';
    }
    return html;
};

window.AutomationProperty._currentNode = null;

window.AutomationProperty.render = function(node) {
    this._currentNode = node;
    if (node && window._screenDpiScale !== null && !window._dpiScaleReady && window._ensureScreenDpiScale) {
        window._ensureScreenDpiScale();
    }
    console.log('[VAR_LIST] render called node=' + (node ? node.id : 'null') + ' type=' + (node ? (node._defKey || node.type) : ''));
    var container = document.getElementById('property-panel-content');
    if (!container) return;
    this._container = container;

    if (!node) {
        container.innerHTML = '<div class="empty-hint"><i class="fa-regular fa-hand-pointer" style="gap: 14px;"></i><span>选择节点查看属性</span></div>';
        return;
    }

    var def = window.AutomationNodes ? AutomationNodes.getNodeDef(node._defKey || node.type) : null;
    var schema = def ? def.params_schema : {};

    var html = '';

    html += '<div class="prop-node-header">' +
        '<div class="prop-node-color" style="background:' + (def ? def.color : '#888') + '"></div>' +
        '<div>' +
          '<div class="prop-node-title">' + (node.title || (def ? def.display_name : node.type)) + '</div>' +
          '<div class="prop-node-type">' + (node._defKey || node.type) + ' #' + node.id + '</div>' +
        '</div>' +
      '</div>';

    var coordParams = [];
    var mainParams = [];
    for (var key in schema) {
        if (!schema.hasOwnProperty(key)) continue;
        var s = schema[key];
        if (s.coordRef || s.coordMode) {
            coordParams.push([key, s]);
        } else {
            mainParams.push([key, s]);
        }
    }

    if (coordParams.length > 0) {
        html += this._renderGroup('坐标', coordParams, node);
    }
    if (mainParams.length > 0) {
        html += this._renderGroup('参数', mainParams, node);
    }

    var defKey = node._defKey || node.type || '';
    if (defKey.indexOf('check_color') >= 0 || defKey.indexOf('check_ocr') >= 0 || defKey.indexOf('check_image') >= 0 || defKey.indexOf('check_digits') >= 0 || defKey.indexOf('monitor_color') >= 0 || defKey.indexOf('monitor_ocr') >= 0 || defKey.indexOf('preset_find_click') >= 0 || defKey.indexOf('preset_read_text') >= 0) {
        html += '<div class="prop-group">' +
            '<div class="prop-group-header"><i class="fa-solid fa-chevron-down arrow"></i> 实时预览</div>' +
            '<div class="prop-group-body">' +
              '<div class="prop-preview" id="preview-area"><span>点击预览查看结果</span></div>' +
              '<div class="prop-btn-row">' +
                '<button class="prop-btn accent-outline" onclick="window._autoEditor.runPreview(\'' + defKey + '\', ' + node.id + ')">' +
                  '<i class="fa-solid fa-bolt"></i> 预览' +
                '</button>' +
              '</div>' +
            '</div>' +
          '</div>';
    }

    if (defKey.indexOf('call_script') >= 0) {
        html += '<div class="prop-group">' +
            '<div class="prop-group-header"><i class="fa-solid fa-chevron-down arrow"></i> 动作编辑</div>' +
            '<div class="prop-group-body">' +
              '<div class="prop-btn-row">' +
                '<button class="prop-btn accent-outline" onclick="window.AutomationBlockEditor.open(AutomationCore.lgGraphObj.getNodeById(' + node.id + '))">' +
                  '<i class="fa-solid fa-pen"></i> 编辑动作块' +
                '</button>' +
              '</div>' +
            '</div>' +
          '</div>';
    }

    container.innerHTML = html;

    this._bindEvents(container, node, schema);

    container.querySelectorAll('.prop-group-header').forEach(function(h) {
        h.addEventListener('click', function() { this.classList.toggle('collapsed'); });
    });
};

window.AutomationProperty.renderAnnotation = function(an) {
    this._currentNode = null;
    this._currentAnnotation = an;
    this._currentGroup = null;
    var container = document.getElementById('property-panel-content');
    if (!container) return;

    var html = '';
    html += '<div class="prop-node-header">' +
        '<div class="prop-node-color" style="background:' + (an.color || '#fbbf24') + '"></div>' +
        '<div>' +
          '<div class="prop-node-title">注释</div>' +
          '<div class="prop-node-type">#' + an.id + '</div>' +
        '</div>' +
      '</div>';

    html += '<div class="prop-group">' +
        '<div class="prop-group-header"><i class="fa-solid fa-chevron-down arrow"></i> 内容</div>' +
        '<div class="prop-group-body">';

    html += '<div class="prop-field">' +
        '<label class="prop-field-label">文本内容</label>' +
        '<textarea data-key="text" rows="3" style="width:100%;resize:vertical;background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--rs);padding:6px 8px;color:var(--txt);font-size:12px;font-family:var(--fmo);outline:none;transition:border-color var(--t)">' + _pe(an.text || '') + '</textarea>' +
      '</div>';

    html += '<div class="prop-field">' +
        '<label class="prop-field-label">颜色</label>' +
        '<div style="display:flex;gap:4px;flex-wrap:wrap">';
    html += this._renderColorSwatches(_annotationPresetColors, an.bgColor, 'data-color', 'data-bg');
    html += '</div></div>';

    html += '<div class="prop-field">' +
        '<label class="prop-field-label" style="display:flex;align-items:center;gap:8px">折叠<input type="checkbox" id="prop-an-collapsed" ' + (an.collapsed ? 'checked' : '') + ' style="accent-color:var(--acc);cursor:pointer"></label>' +
      '</div>';

    html += '</div></div>';

    html += '<div class="prop-group">' +
        '<div class="prop-group-header"><i class="fa-solid fa-chevron-down arrow"></i> 位置</div>' +
        '<div class="prop-group-body">';
    html += '<div class="prop-field"><label class="prop-field-label">X</label><input type="number" data-key="posX" value="' + Math.round(an.pos[0]) + '" style="width:100%"></div>';
    html += '<div class="prop-field"><label class="prop-field-label">Y</label><input type="number" data-key="posY" value="' + Math.round(an.pos[1]) + '" style="width:100%"></div>';
    html += '</div></div>';

    html += '<div style="padding:10px 14px 14px"><button class="prop-btn outline" style="width:100%;justify-content:center" onclick="if(window.AutomationCore)window.AutomationCore.removeAnnotation(' + an.id + ');if(window.AutomationProperty)AutomationProperty.render(null);"><i class="fa-solid fa-trash-can"></i> 删除注释</button></div>';

    container.innerHTML = html;

    container.querySelectorAll('.prop-group-header').forEach(function(h) {
        h.addEventListener('click', function() { this.classList.toggle('collapsed'); });
    });

    container.querySelector('textarea[data-key="text"]').addEventListener('input', function() {
        an.text = this.value;
        if (an._domEl) {
            an._domEl.querySelector('.an-t').textContent = an.text;
        }
        AutomationCore._notifyGraphChange();
    });

    container.querySelectorAll('[data-color]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            an.color = this.dataset.color;
            an.bgColor = this.dataset.bg;
            if (an._domEl) {
                an._domEl.style.background = an.bgColor;
            }
            container.querySelectorAll('[data-color]').forEach(function(b) { b.style.borderColor = 'transparent'; });
            this.style.borderColor = 'var(--acc)';
            AutomationCore._notifyGraphChange();
        });
        if (an.bgColor === btn.dataset.bg) {
            btn.style.borderColor = 'var(--acc)';
        }
    });

    container.querySelector('#prop-an-collapsed').addEventListener('change', function() {
        an.collapsed = this.checked;
        if (an._domEl) {
            an._domEl.classList.toggle('collapsed', an.collapsed);
            var toggleEl = an._domEl.querySelector('.an-toggle');
            if (toggleEl) {
                toggleEl.innerHTML = an.collapsed ? '<i class="fa-solid fa-expand"></i>' : '<i class="fa-solid fa-compress"></i>';
            }
        }
        AutomationCore._notifyGraphChange();
    });

    container.querySelector('input[data-key="posX"]').addEventListener('change', function() {
        an.pos[0] = parseFloat(this.value) || 0;
        if (an._domEl) an._domEl.style.left = an.pos[0] + 'px';
        AutomationCore._notifyGraphChange();
    });
    container.querySelector('input[data-key="posY"]').addEventListener('change', function() {
        an.pos[1] = parseFloat(this.value) || 0;
        if (an._domEl) an._domEl.style.top = an.pos[1] + 'px';
        AutomationCore._notifyGraphChange();
    });
};

window.AutomationProperty.renderGroup = function(gp) {
    this._currentNode = null;
    this._currentAnnotation = null;
    this._currentGroup = gp;
    var container = document.getElementById('property-panel-content');
    if (!container) return;

    var html = '';
    html += '<div class="prop-node-header">' +
        '<div class="prop-node-color" style="background:' + (gp.color || '#3b82f6') + '"></div>' +
        '<div>' +
          '<div class="prop-node-title">分组</div>' +
          '<div class="prop-node-type">#' + gp.id + '</div>' +
        '</div>' +
      '</div>';

    html += '<div class="prop-group">' +
        '<div class="prop-group-header"><i class="fa-solid fa-chevron-down arrow"></i> 内容</div>' +
        '<div class="prop-group-body">';

    html += '<div class="prop-field">' +
        '<label class="prop-field-label">标题</label>' +
        '<input type="text" data-key="title" value="' + _pe(gp.title || '') + '" style="width:100%">' +
      '</div>';

    html += '<div class="prop-field">' +
        '<label class="prop-field-label">颜色</label>' +
        '<div style="display:flex;gap:4px;flex-wrap:wrap">';
    html += this._renderColorSwatches(_groupPresetColors, gp.bgColor, 'data-gp-color', 'data-gp-bg');
    html += '</div></div>';

    html += '</div></div>';

    html += '<div class="prop-group">' +
        '<div class="prop-group-header"><i class="fa-solid fa-chevron-down arrow"></i> 位置和大小</div>' +
        '<div class="prop-group-body">';
    html += '<div class="prop-field"><label class="prop-field-label">X</label><input type="number" data-key="posX" value="' + Math.round(gp.pos[0]) + '" style="width:100%"></div>';
    html += '<div class="prop-field"><label class="prop-field-label">Y</label><input type="number" data-key="posY" value="' + Math.round(gp.pos[1]) + '" style="width:100%"></div>';
    html += '<div class="prop-field"><label class="prop-field-label">宽度</label><input type="number" data-key="sizeW" value="' + Math.round(gp.size[0]) + '" style="width:100%"></div>';
    html += '<div class="prop-field"><label class="prop-field-label">高度</label><input type="number" data-key="sizeH" value="' + Math.round(gp.size[1]) + '" style="width:100%"></div>';
    html += '</div></div>';

    html += '<div style="padding:10px 14px 14px"><button class="prop-btn outline" style="width:100%;justify-content:center" onclick="if(window.AutomationCore)window.AutomationCore.removeGroup(' + gp.id + ');if(window.AutomationProperty)AutomationProperty.render(null);"><i class="fa-solid fa-trash-can"></i> 删除分组</button></div>';

    container.innerHTML = html;

    container.querySelectorAll('.prop-group-header').forEach(function(h) {
        h.addEventListener('click', function() { this.classList.toggle('collapsed'); });
    });

    container.querySelector('input[data-key="title"]').addEventListener('input', function() {
        gp.title = this.value;
        if (gp._domEl) {
            gp._domEl.querySelector('.gp-t').textContent = gp.title;
        }
        AutomationCore._notifyGraphChange();
    });

    container.querySelectorAll('[data-gp-color]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            gp.color = this.dataset.gpColor;
            gp.bgColor = this.dataset.gpBg;
            if (gp._domEl) {
                gp._domEl.style.setProperty('--gp-color', gp.color);
                gp._domEl.style.setProperty('--gp-bg', gp.bgColor);
                gp._domEl.style.background = gp.bgColor;
            }
            container.querySelectorAll('[data-gp-color]').forEach(function(b) { b.style.borderColor = 'transparent'; });
            this.style.borderColor = 'var(--acc)';
            AutomationCore._notifyGraphChange();
        });
        if (gp.bgColor === btn.dataset.gpBg) {
            btn.style.borderColor = 'var(--acc)';
        }
    });

    container.querySelector('input[data-key="posX"]').addEventListener('change', function() {
        gp.pos[0] = parseFloat(this.value) || 0;
        if (gp._domEl) gp._domEl.style.left = gp.pos[0] + 'px';
        AutomationCore._notifyGraphChange();
    });
    container.querySelector('input[data-key="posY"]').addEventListener('change', function() {
        gp.pos[1] = parseFloat(this.value) || 0;
        if (gp._domEl) gp._domEl.style.top = gp.pos[1] + 'px';
        AutomationCore._notifyGraphChange();
    });
    container.querySelector('input[data-key="sizeW"]').addEventListener('change', function() {
        gp.size[0] = Math.max(140, parseFloat(this.value) || 300);
        if (gp._domEl) gp._domEl.style.width = gp.size[0] + 'px';
        AutomationCore._notifyGraphChange();
    });
    container.querySelector('input[data-key="sizeH"]').addEventListener('change', function() {
        gp.size[1] = Math.max(100, parseFloat(this.value) || 200);
        if (gp._domEl) gp._domEl.style.height = gp.size[1] + 'px';
        AutomationCore._notifyGraphChange();
    });
};

export const AutomationProperty = window.AutomationProperty;
