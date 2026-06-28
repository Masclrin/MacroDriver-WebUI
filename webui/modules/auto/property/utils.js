'use strict';

window.AutomationProperty = window.AutomationProperty || {};

window.AutomationProperty._showToast = function(msg) {
    var toast = document.createElement('div');
    toast.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:var(--bg-raised,#1e293b);color:var(--txt1,#f1f5f9);padding:8px 20px;border-radius:8px;font-size:13px;z-index:999999;box-shadow:0 4px 16px rgba(0,0,0,0.4);border:1px solid var(--border,#334155)';
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(function() { toast.remove(); }, 2000);
};
