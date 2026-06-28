export function showToast(msg, type, duration) {
  type = type || 'inf';
  duration = duration || 3000;
  var container = document.getElementById('toast-c');
  var icons = { ok: 'fa-solid fa-check-circle', err: 'fa-solid fa-exclamation-circle', inf: 'fa-solid fa-info-circle', warn: 'fa-solid fa-triangle-exclamation' };
  var toast = document.createElement('div');
  toast.className = 'toast ' + type;
  toast.innerHTML = '<i class="' + (icons[type] || icons.inf) + '"></i><span>' + msg + '</span>';
  container.appendChild(toast);
  setTimeout(function() {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all .15s ease';
    setTimeout(function() { toast.remove(); }, 150);
  }, duration);
}
