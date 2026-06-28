import { apiCall, showToast } from './app-core.js';

var _initDone = false;

export function initExtraTab() {
  if (_initDone) return;
  _initDone = true;

  var grid = document.getElementById('extraGrid');
  if (!grid) return;

  grid.addEventListener('click', function (e) {
    var card = e.target.closest('.extra-card');
    if (!card) return;
    var action = card.dataset.action;
    if (!action) return;

    if (action === 'check-env') handleCheckEnv();
    else if (action === 'sys-info') handleSysInfo();
    else if (action === 'driver-mgmt') handleDriverMgmt();
    else if (action === 'restart-admin') handleRestartAdmin();
    else if (action === 'features') handleFeatures();
    else if (action === 'shortcuts') handleShortcuts();
    else if (action === 'copyright') handleCopyright();
  });

  var btnCheck = document.getElementById('btnCheckDriver');
  var btnInstall = document.getElementById('btnInstallDriver');
  var btnUninstall = document.getElementById('btnUninstallDriver');
  if (btnCheck) btnCheck.addEventListener('click', refreshDriverStatus);
  if (btnInstall) btnInstall.addEventListener('click', installDriver);
  if (btnUninstall) btnUninstall.addEventListener('click', uninstallDriver);
}

function showPanel(panelId) {
  var result = document.getElementById('extraResult');
  var driver = document.getElementById('driverPanel');
  if (result) result.style.display = 'none';
  if (driver) driver.style.display = 'none';
  if (panelId) {
    var el = document.getElementById(panelId);
    if (el) el.style.display = 'block';
  }
}

// ── 环境检查 ───────────────────────────────────

async function handleCheckEnv() {
  showPanel('extraResult');
  var result = document.getElementById('extraResult');
  result.innerHTML = '<p><span class="loading-spinner"></span>正在检查环境...</p>';

  try {
    var data = await apiCall('check_environment');
    if (!data || !data.ok) {
      result.innerHTML = '<p class="fail">检查失败: ' + (data && data.message || '未知错误') + '</p>';
      return;
    }
    var r = data.results;
    var pkgStatus = r.packages.missing.length === 0
      ? '<span class="ok">已全部安装</span> (' + r.packages.installed.length + ' 个)'
      : '<span class="fail">缺失: ' + r.packages.missing.join(', ') + '</span>';

    var dxgiStatus = r.dxgi.available
      ? '<span class="ok">可用</span>'
      : '<span class="warn">不可用</span>' + (r.dxgi.warning ? ' (' + esc(r.dxgi.warning) + ')' : '');

    var drvStatus = r.interception_driver.loaded
      ? '<span class="ok">已加载</span>'
      : '<span class="fail">未加载</span>' + (r.interception_driver.warning ? ' (' + esc(r.interception_driver.warning) + ')' : '');

    var dllStatus = r.interception_dll.exists
      ? '<span class="ok">已找到</span> (' + esc(r.interception_dll.path) + ')'
      : '<span class="fail">未找到</span>' + (r.interception_dll.path ? ' (期望路径: ' + esc(r.interception_dll.path) + ')' : '');

    result.innerHTML =
      '<h3>环境检查结果</h3>' +
      buildTable([
        ['Python 版本', '<span class="' + (r.python.ok ? 'ok' : 'fail') + '">' + esc(r.python.version) + '</span>' + (r.python.warning ? ' <span class="warn">' + esc(r.python.warning) + '</span>' : '')],
        ['Python 路径', esc(r.python.executable)],
        ['操作系统', esc(r.system.os)],
        ['架构', esc(r.system.arch) + ' · ' + esc(r.system.machine)],
        ['管理员权限', r.system.is_admin ? '<span class="ok">是</span>' : '<span class="warn">否</span>'],
        ['Interception DLL', dllStatus],
        ['Interception 驱动', drvStatus],
        ['DXGI 截图', dxgiStatus],
        ['依赖包', pkgStatus],
      ]);

    if (r.packages.missing.length > 0) {
      result.innerHTML +=
        '<div class="extra-actions" style="margin-top:12px">' +
        '<button id="btnInstallMissing" class="primary">一键安装缺失依赖</button>' +
        '</div>';
      var btnInstallMissing = document.getElementById('btnInstallMissing');
      if (btnInstallMissing) {
        btnInstallMissing.addEventListener('click', handleInstallMissing);
      }
    }
  } catch (e) {
    result.innerHTML = '<p class="fail">检查出错: ' + esc(e.message || String(e)) + '</p>';
  }
}

async function handleInstallMissing() {
  var btn = document.getElementById('btnInstallMissing');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '正在安装...';
  }
  try {
    var data = await apiCall('install_missing_packages');
    if (data && data.ok) {
      showToast(data.message || '安装完成');
      handleCheckEnv();
    } else {
      showToast('安装失败: ' + (data && data.message || '未知错误'));
      if (btn) { btn.disabled = false; btn.textContent = '一键安装缺失依赖'; }
    }
  } catch (e) {
    showToast('安装出错: ' + (e.message || String(e)));
    if (btn) { btn.disabled = false; btn.textContent = '一键安装缺失依赖'; }
  }
}

// ── 系统信息 ───────────────────────────────────

async function handleSysInfo() {
  showPanel('extraResult');
  var result = document.getElementById('extraResult');
  result.innerHTML = '<p><span class="loading-spinner"></span>正在获取系统信息...</p>';

  try {
    var data = await apiCall('get_system_info');
    if (!data || !data.ok) {
      result.innerHTML = '<p class="fail">获取失败: ' + (data && data.message || '未知错误') + '</p>';
      return;
    }
    var monitorRows = (data.monitors || []).map(function (m) {
      return (m.is_primary ? '★ ' : '  ') + m.name + ' (' + m.width + 'x' + m.height + ')';
    }).join('<br>') || '无';

    result.innerHTML =
      '<h3>系统信息</h3>' +
      buildTable([
        ['操作系统', esc(data.os)],
        ['架构', esc(data.arch)],
        ['Python 版本', esc(data.python)],
        ['Python 路径', esc(data.executable)],
        ['程序目录', esc(data.app_dir)],
        ['显示器', monitorRows],
      ]);
  } catch (e) {
    result.innerHTML = '<p class="fail">获取出错: ' + esc(e.message || String(e)) + '</p>';
  }
}

// ── 驱动管理 ───────────────────────────────────

async function handleDriverMgmt() {
  showPanel('driverPanel');
  await refreshDriverStatus();
}

async function refreshDriverStatus() {
  var status = document.getElementById('driverStatus');
  status.innerHTML = '<p><span class="loading-spinner"></span>正在检查驱动状态...</p>';
  try {
    var data = await apiCall('check_environment');
    if (!data || !data.ok) {
      status.innerHTML = '<p class="fail">检查失败</p>';
      return;
    }
    var r = data.results;
    var dllOk = r.interception_dll.exists;
    var drvOk = r.interception_driver.loaded;
    status.innerHTML = '<table>' +
      '<tr><th>Interception DLL</th><td>' + (dllOk ? '<span class="ok">已找到</span>' : '<span class="fail">未找到</span>') + '</td></tr>' +
      '<tr><th>DLL 路径</th><td>' + esc(r.interception_dll.path || '无') + '</td></tr>' +
      '<tr><th>驱动状态</th><td>' + (drvOk ? '<span class="ok">已加载</span>' : '<span class="fail">未加载</span>' + (r.interception_driver.warning ? ' (' + esc(r.interception_driver.warning) + ')' : '')) + '</td></tr>' +
      '<tr><th>管理员权限</th><td>' + (r.system.is_admin ? '<span class="ok">是</span>' : '<span class="warn">否（安装驱动需管理员权限）</span>') + '</td></tr>' +
      '</table>';
    if (!dllOk && !drvOk) {
      status.innerHTML += '<p class="warn" style="margin-top:8px">驱动不可用，请先安装 Interception 驱动（需管理员权限）</p>';
    }
  } catch (e) {
    status.innerHTML = '<p class="fail">检查出错: ' + esc(e.message || String(e)) + '</p>';
  }
}

async function installDriver() {
  if (!confirm('安装 Interception 驱动需要管理员权限，点击确认后将弹出 UAC 窗口。')) return;
  try {
    var data = await apiCall('install_interception_driver');
    if (data && data.ok) {
      showToast(data.message || '已请求安装');
    } else {
      showToast('安装失败: ' + (data && data.message || '未知错误'));
    }
  } catch (e) {
    showToast('安装出错: ' + (e.message || String(e)));
  }
}

async function uninstallDriver() {
  if (!confirm('卸载 Interception 驱动需要管理员权限，确认后将弹出 UAC 窗口。')) return;
  try {
    var data = await apiCall('uninstall_interception_driver');
    if (data && data.ok) {
      showToast(data.message || '已请求卸载');
    } else {
      showToast('卸载失败: ' + (data && data.message || '未知错误'));
    }
  } catch (e) {
    showToast('卸载出错: ' + (e.message || String(e)));
  }
}

// ── 管理员重启 ──────────────────────────────────

async function handleRestartAdmin() {
  showPanel('extraResult');
  var result = document.getElementById('extraResult');
  result.innerHTML =
    '<h3>管理员重启</h3>' +
    '<p>将以管理员权限重新启动程序。当前窗口会自动关闭。</p>' +
    '<button id="btnRestartAdmin" class="primary" style="margin-top:8px">确认重启为管理员</button>';

  var btn = document.getElementById('btnRestartAdmin');
  if (btn) {
    btn.addEventListener('click', async function () {
      try {
        var data = await apiCall('restart_as_admin');
        if (data && data.ok) {
          showToast(data.message || '正在重启...');
        } else {
          showToast('重启失败: ' + (data && data.message || '未知错误'));
        }
      } catch (e) {
        showToast('重启出错: ' + (e.message || String(e)));
      }
    });
  }
}

// ── 功能一览 ───────────────────────────────────

async function handleFeatures() {
  showPanel('extraResult');
  var result = document.getElementById('extraResult');
  result.innerHTML = '<p><span class="loading-spinner"></span>加载功能列表...</p>';

  try {
    var data = await apiCall('get_feature_list');
    if (!data || !data.ok) {
      result.innerHTML = '<p class="fail">加载失败</p>';
      return;
    }
    var items = (data.features || []).map(function (f) {
      return '<tr><td><i class="' + esc(f.icon) + '" style="color:var(--accent);margin-right:6px"></i>' + esc(f.name) + '</td><td>' + esc(f.desc) + '</td></tr>';
    }).join('');
    result.innerHTML = '<h3>功能一览</h3><table><thead><tr><th>模块</th><th>说明</th></tr></thead><tbody>' + items + '</tbody></table>';
  } catch (e) {
    result.innerHTML = '<p class="fail">加载出错: ' + esc(e.message || String(e)) + '</p>';
  }
}

// ── 快捷键速查 ─────────────────────────────────

function handleShortcuts() {
  showPanel('extraResult');
  var result = document.getElementById('extraResult');
  result.innerHTML =
    '<h3>快捷键速查</h3>' +
    '<h4 style="margin:12px 0 6px;color:var(--accent)">全局控制</h4>' +
    '<table><thead><tr><th>快捷键</th><th>功能</th><th>说明</th></tr></thead><tbody>' +
    '<tr><td><kbd>F8</kbd></td><td>全局暂停/恢复</td><td>暂停或恢复所有运行中的宏</td></tr>' +
    '<tr><td><kbd>ESC</kbd></td><td>停止全部宏</td><td>立即停止所有运行中的宏</td></tr>' +
    '</tbody></table>' +
    '<h4 style="margin:16px 0 6px;color:var(--accent)">自动化编辑器</h4>' +
    '<table><thead><tr><th>快捷键</th><th>功能</th><th>说明</th></tr></thead><tbody>' +
    '<tr><td><kbd>F6</kbd></td><td>运行自动化</td><td>运行当前编辑的自动化脚本</td></tr>' +
    '<tr><td><kbd>F7</kbd></td><td>暂停/恢复</td><td>暂停或恢复当前运行的自动化</td></tr>' +
    '<tr><td><kbd>F8</kbd></td><td>停止自动化</td><td>停止当前运行的自动化</td></tr>' +
    '<tr><td><kbd>F11</kbd></td><td>全屏切换</td><td>切换编辑器全屏模式</td></tr>' +
    '</tbody></table>' +
    '<h4 style="margin:16px 0 6px;color:var(--accent)">录制系统</h4>' +
    '<table><thead><tr><th>快捷键</th><th>功能</th><th>说明</th></tr></thead><tbody>' +
    '<tr><td><kbd>F7</kbd></td><td>开始录制</td><td>进入录制就绪状态</td></tr>' +
    '<tr><td><kbd>F8</kbd></td><td>停止录制</td><td>停止当前录制</td></tr>' +
    '<tr><td><kbd>F9</kbd></td><td>保存录制</td><td>保存录制结果</td></tr>' +
    '<tr><td><kbd>F10</kbd></td><td>清空缓存</td><td>清空录制缓存数据</td></tr>' +
    '</tbody></table>' +
    '<p class="hint" style="margin-top:12px">快捷键可在「全局参数」面板中自定义配置。</p>';
}

// ── 软件著作 ───────────────────────────────────

async function handleCopyright() {
  showPanel('extraResult');
  var result = document.getElementById('extraResult');

  var versionStr = '3.1.0';
  try {
    var hdata = await apiCall('health');
    if (hdata && hdata.version) versionStr = hdata.version;
  } catch (_) {}

  result.innerHTML =
    '<h3>软件著作</h3>' +
    '<table>' +
    '<tr><th>项目名称</th><td>宏驱动控制台 (Macro Forge)</td></tr>' +
    '<tr><th>版本</th><td>v' + esc(versionStr) + '</td></tr>' +
    '<tr><th>用途</th><td>高精度宏录制、编辑与自动化执行</td></tr>' +
    '<tr><th>核心技术</th><td>Python · pywebview · Interception 驱动 · DXGI 截图</td></tr>' +
    '<tr><th>许可</th><td>保留所有权利</td></tr>' +
    '</table>' +
    '<p class="hint" style="margin-top:12px">Interception 驱动为第三方开源组件，版权归其作者所有。</p>';
}

// ── 工具函数 ───────────────────────────────────

function buildTable(rows) {
  var html = '<table><tbody>';
  for (var i = 0; i < rows.length; i++) {
    html += '<tr><th>' + esc(rows[i][0]) + '</th><td>' + rows[i][1] + '</td></tr>';
  }
  html += '</tbody></table>';
  return html;
}

function esc(str) {
  if (!str) return '';
  str = String(str);
  str = str.replace(/&/g, '&amp;');
  str = str.replace(/</g, '&lt;');
  str = str.replace(/>/g, '&gt;');
  str = str.replace(/"/g, '&quot;');
  return str;
}