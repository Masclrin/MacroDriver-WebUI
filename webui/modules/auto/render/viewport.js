'use strict';

import { _s } from '../core/state.js';

var _mmBounds = null;

function _updateViewport() {
    if (!_s._viewportEl) return;
    _s._viewportEl.style.transform = 'translate(' + _s._vpOffset.x + 'px,' + _s._vpOffset.y + 'px) scale(' + _s._vpScale + ')';
}

function _setZoom(newScale, centerX, centerY) {
    var r = _s._canvasArea.getBoundingClientRect();
    var cx = centerX !== undefined ? centerX : r.width / 2;
    var cy = centerY !== undefined ? centerY : r.height / 2;
    var oldScale = _s._vpScale;
    _s._vpScale = Math.max(0.15, Math.min(3, newScale));
    var ratio = _s._vpScale / oldScale;
    _s._vpOffset.x = cx - (cx - _s._vpOffset.x) * ratio;
    _s._vpOffset.y = cy - (cy - _s._vpOffset.y) * ratio;
    _updateViewport();
    _updateMinimap();
}

function _updateMinimap() {
    var mmCv = document.getElementById('minimap-canvas');
    if (!mmCv) return;
    var dpr = window.devicePixelRatio || 1;
    var w = 160, h = 100;
    mmCv.width = Math.floor(w * dpr);
    mmCv.height = Math.floor(h * dpr);
    var ctx = mmCv.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = 'rgba(10,14,20,0.92)';
    ctx.fillRect(0, 0, w, h);

    var hasContent = _s._nodeList.length > 0 || _s._annotations.length > 0 || _s._groups.length > 0;
    if (!hasContent) { _mmBounds = null; return; }
    var minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
    for (var i = 0; i < _s._nodeList.length; i++) {
        var n = _s._nodeList[i];
        minX = Math.min(minX, n.pos[0]);
        minY = Math.min(minY, n.pos[1]);
        maxX = Math.max(maxX, n.pos[0] + (n.size[0] || 200));
        maxY = Math.max(maxY, n.pos[1] + (n.size[1] || 80));
    }
    for (var ai = 0; ai < _s._annotations.length; ai++) {
        var an = _s._annotations[ai];
        minX = Math.min(minX, an.pos[0]);
        minY = Math.min(minY, an.pos[1]);
        maxX = Math.max(maxX, an.pos[0] + 120);
        maxY = Math.max(maxY, an.pos[1] + 40);
    }
    for (var gi = 0; gi < _s._groups.length; gi++) {
        var gp = _s._groups[gi];
        minX = Math.min(minX, gp.pos[0]);
        minY = Math.min(minY, gp.pos[1]);
        maxX = Math.max(maxX, gp.pos[0] + gp.size[0]);
        maxY = Math.max(maxY, gp.pos[1] + gp.size[1]);
    }
    var pad = 60;
    minX -= pad; minY -= pad; maxX += pad; maxY += pad;
    var gw = Math.max(1, maxX - minX);
    var gh = Math.max(1, maxY - minY);
    var s = Math.min(w / gw, h / gh) * 0.85;
    var ox = (w - gw * s) / 2;
    var oy = (h - gh * s) / 2;

    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineWidth = 0.5;
    for (var j = 0; j < _s._connections.length; j++) {
        var c = _s._connections[j];
        var fn = _s._nodes[c.origin_id], tn = _s._nodes[c.target_id];
        if (!fn || !tn) continue;
        ctx.beginPath();
        ctx.moveTo(ox + (fn.pos[0] - minX + (fn.size[0] || 200) / 2) * s, oy + (fn.pos[1] - minY + 20) * s);
        ctx.lineTo(ox + (tn.pos[0] - minX + (tn.size[0] || 200) / 2) * s, oy + (tn.pos[1] - minY + 20) * s);
        ctx.stroke();
    }

    for (var k = 0; k < _s._nodeList.length; k++) {
        var nd = _s._nodeList[k];
        ctx.fillStyle = nd._accentColor || '#718096';
        ctx.globalAlpha = 0.6;
        ctx.fillRect(ox + (nd.pos[0] - minX) * s, oy + (nd.pos[1] - minY) * s,
            Math.max(3, (nd.size[0] || 200) * s), Math.max(2, (nd.size[1] || 80) * s));
    }
    ctx.globalAlpha = 1;

    for (var gi2 = 0; gi2 < _s._groups.length; gi2++) {
        var gp2 = _s._groups[gi2];
        ctx.fillStyle = gp2.color || '#3b82f6';
        ctx.globalAlpha = 0.25;
        ctx.fillRect(ox + (gp2.pos[0] - minX) * s, oy + (gp2.pos[1] - minY) * s,
            Math.max(3, gp2.size[0] * s), Math.max(2, gp2.size[1] * s));
    }
    ctx.globalAlpha = 1;

    for (var ai2 = 0; ai2 < _s._annotations.length; ai2++) {
        var an2 = _s._annotations[ai2];
        ctx.fillStyle = an2.color || '#fbbf24';
        ctx.globalAlpha = 0.85;
        ctx.fillRect(ox + (an2.pos[0] - minX) * s, oy + (an2.pos[1] - minY) * s,
            Math.max(3, 120 * s), Math.max(2, 40 * s));
    }
    ctx.globalAlpha = 1;

    var areaR = _s._canvasArea.getBoundingClientRect();
    var viewW = areaR.width / _s._vpScale;
    var viewH = areaR.height / _s._vpScale;
    var vx = ox + (-_s._vpOffset.x / _s._vpScale - minX) * s;
    var vy = oy + (-_s._vpOffset.y / _s._vpScale - minY) * s;
    var vw = viewW * s;
    var vh = viewH * s;
    ctx.strokeStyle = 'rgba(255,255,255,0.6)';
    ctx.lineWidth = 1;
    ctx.strokeRect(vx, vy, vw, vh);

    _mmBounds = { minX: minX, minY: minY, maxX: maxX, maxY: maxY, gw: gw, gh: gh, s: s, ox: ox, oy: oy, w: w, h: h };
}

function _navigateMinimap(mx, my) {
    if (!_mmBounds || !_s._canvasArea) return;
    var b = _mmBounds;
    var mmCv = document.getElementById('minimap-canvas');
    if (!mmCv) return;
    var rect = mmCv.getBoundingClientRect();
    var px = (mx - rect.left) / rect.width * b.w;
    var py = (my - rect.top) / rect.height * b.h;
    var localX = (px - b.ox) / b.s + b.minX;
    var localY = (py - b.oy) / b.s + b.minY;
    var areaR = _s._canvasArea.getBoundingClientRect();
    _s._vpOffset.x = areaR.width / 2 - localX * _s._vpScale;
    _s._vpOffset.y = areaR.height / 2 - localY * _s._vpScale;
    _updateViewport();
    _updateMinimap();
}

export { _updateViewport, _setZoom, _updateMinimap, _navigateMinimap };
