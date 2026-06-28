
## 插件系统设计文档

### 一、概述

为自动化编辑器引入**约定式插件系统**，使第三方开发者无需修改原代码即可开发、部署插件节点。插件通过独立文件夹存放，后端动态扫描加载，前端通过统一接口获取节点定义并注册。

### 二、目录结构

```
宏驱动 webui 2.5/
  plugins/                          ← 插件根目录（新增）
    notify/                         ← 消息提示插件
      manifest.json                 ← 插件清单（必须）
      node.js                       ← 节点前端定义（必须）
      backend.py                    ← 后端逻辑（可选）
      icon.svg                      ← 自定义图标（可选）
    email/                          ← 发送邮件插件
      manifest.json
      node.js
      backend.py
    screen-record/                  ← 视频录屏插件
      manifest.json
      node.js
      backend.py
    replay/                         ← 精彩回放插件
      manifest.json
      node.js
      backend.py
```

### 三、文件规范

#### 3.1 manifest.json（必须）

```json
{
  "id": "notify",
  "name": "消息提示",
  "version": "1.0.0",
  "author": "作者名",
  "description": "在屏幕右下角弹出消息提示，支持自定义音效",
  "icon": "fa-solid fa-bell",
  "color": "#a855f7",
  "nodes": ["notify"],
  "backend": "backend.py",
  "minAppVersion": "2.5"
}
```

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| id | string | ✅ | 插件唯一标识，与文件夹名一致 |
| name | string | ✅ | 显示名称 |
| version | string | ✅ | 语义化版本号 |
| author | string | ❌ | 作者 |
| description | string | ❌ | 插件描述 |
| icon | string | ❌ | FontAwesome 图标类名，默认 `fa-solid fa-puzzle-piece` |
| color | string | ❌ | 节点主色，默认 `#a855f7` |
| nodes | string[] | ✅ | 本插件提供的节点 ID 列表（不含 `plugin/` 前缀） |
| backend | string | ❌ | 后端文件名，存在则加载 |
| minAppVersion | string | ❌ | 最低应用版本要求 |

#### 3.2 node.js（必须）

导出一个 `nodes` 对象，键为 `plugin/{id}` 格式的节点类型，值与现有 `AutomationNodes._nodeDefs` 格式一致，额外支持以下扩展字段：

```javascript
var nodes = {
  'plugin/notify': {
    display_name: '消息提示',
    color: '#a855f7',
    category: 'plugin',
    icon: 'fa-solid fa-bell',
    inputs: [{name:'in', type:'flow'}],
    outputs: [{name:'next', type:'flow'}],
    params_schema: {
      title:    {type:'string', label:'标题', default:'提示', varRef:true},
      message:  {type:'string', label:'内容', default:'操作完成', varRef:true},
      sound:    {type:'enum', label:'音效', default:'default',
                 options:['default','info','success','warning','error','none']},
      duration: {type:'number', label:'显示时长(ms)', default:3000},
      position: {type:'enum', label:'位置', default:'bottom-right',
                 options:['bottom-right','bottom-left','top-right','top-left','center']}
    },
    // ---- 插件扩展字段 ----
    onExecute: function(params) {
      // 前端侧即时效果（弹窗、音效等）
      // params = 节点属性值的深拷贝
      if (window.AutomationEvents && AutomationEvents.showNotifyPopup) {
        AutomationEvents.showNotifyPopup(params);
      }
    },
    backendAction: 'show',       // 对应 backend.py 的 action 名
    renderProperty: null         // 自定义属性面板渲染函数（可选）
  }
};
// 必须赋值给全局变量，后端读取后前端 new Function() 执行
var __plugin_nodes__ = nodes;
```

| 扩展字段 | 类型 | 说明 |
|----------|------|------|
| onExecute | Function | 前端执行回调，节点被触发时调用，参数为节点属性 |
| backendAction | string | 对应后端 action 名，执行引擎调用后端时使用 |
| renderProperty | Function\|null | 自定义属性面板渲染，签名为 `function(container, node, onChange)` |

#### 3.3 backend.py（可选）

```python
# -*- coding: utf-8 -*-
"""
插件后端规范：
1. 必须定义 register() 函数，返回 action 列表
2. 必须定义 execute(action, params, context) 函数，处理具体逻辑
3. context 提供全局能力注入
"""

def register():
    """声明本插件支持的 action 列表"""
    return [
        {"action": "show", "description": "显示消息提示"},
    ]


def execute(action, params, context):
    """
    统一执行入口

    Args:
        action: str - 动作名，与 register() 中声明的一致
        params: dict - 前端传来的参数
        context: PluginContext - 全局能力上下文

    Returns:
        dict - {"ok": True, "data": ...} 或 {"ok": False, "error": "..."}
    """
    if action == "show":
        # 可通过 context 向前端推送事件
        context.emit("plugin_notify", {
            "title": params.get("title", "提示"),
            "message": params.get("message", ""),
            "sound": params.get("sound", "default"),
            "duration": params.get("duration", 3000),
            "position": params.get("position", "bottom-right"),
        })
        return {"ok": True}

    return {"ok": False, "error": f"未知动作: {action}"}
```

#### 3.4 PluginContext（上下文对象）

后端框架注入，提供全局能力：

```python
class PluginContext:
    def __init__(self, logger, event_bus, emit_fn):
        self.logger = logger          # 日志器，写入统一日志
        self.event_bus = event_bus    # 事件总线，可订阅/发布事件
        self._emit_fn = emit_fn       # 向前端推送的函数

    def emit(self, event_name, data):
        """向前端推送事件，前端通过 window._automationEvents 接收"""
        self._emit_fn(event_name, data)

    def log(self, level, message):
        """写日志"""
        self.logger.log(level, f"[plugin] {message}")
```

### 四、加载流程

```
┌─────────────────────────────────────────────────────────────┐
│                        后端启动                              │
│  1. 扫描 plugins/ 目录                                       │
│  2. 逐个读取 manifest.json                                   │
│  3. 若存在 backend.py:                                       │
│     a. importlib 动态加载                                    │
│     b. 调用 register() 获取 actions                          │
│     c. 注册到 PluginManager                                  │
│  4. 提供 API: list_plugins() → 返回所有插件信息               │
│  5. 提供 API: get_plugin_node_js(plugin_id) → 返回 node.js  │
│  6. 提供 API: call_plugin(plugin_id, action, params)         │
│     → 路由到对应 backend.py 的 execute()                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                        前端初始化                             │
│  1. 调用 list_plugins() 获取插件列表                         │
│  2. 逐个调用 get_plugin_node_js(id) 获取 node.js 内容       │
│  3. new Function(js_content)() 执行，获取 __plugin_nodes__  │
│  4. 注册到 AutomationNodes._nodeDefs                        │
│  5. 在工具箱"插件"展开面板中动态添加插件项                    │
│  6. 注册 onExecute 回调到事件系统                            │
└─────────────────────────────────────────────────────────────┘
```

### 五、生命周期与错误隔离

```python
# 后端 PluginManager 核心逻辑
class PluginManager:
    _plugins = {}       # {plugin_id: {"manifest": ..., "module": ..., "actions": ...}}
    _context = None

    @classmethod
    def scan(cls, plugins_dir):
        """扫描并加载所有插件"""
        for folder in sorted(plugins_dir.iterdir()):
            if not folder.is_dir():
                continue
            manifest_path = folder / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text("utf-8"))
                plugin_id = manifest["id"]
                entry = {"manifest": manifest, "module": None, "actions": []}

                backend_path = folder / manifest.get("backend", "backend.py")
                if backend_path.exists():
                    module = cls._load_backend(plugin_id, backend_path)
                    actions = module.register()
                    entry["module"] = module
                    entry["actions"] = actions

                cls._plugins[plugin_id] = entry
            except Exception as e:
                # 单个插件加载失败不影响其他插件
                print(f"[PluginManager] 插件 {folder.name} 加载失败: {e}")
                continue

    @classmethod
    def _load_backend(cls, plugin_id, path):
        """动态加载后端模块，隔离命名空间"""
        module_name = f"_plugin_{plugin_id}"
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    @classmethod
    def execute(cls, plugin_id, action, params):
        """统一执行路由，带错误隔离"""
        entry = cls._plugins.get(plugin_id)
        if not entry or not entry["module"]:
            return {"ok": False, "error": f"插件 {plugin_id} 未加载或无后端"}
        try:
            return entry["module"].execute(action, params, cls._context)
        except Exception as e:
            return {"ok": False, "error": f"插件 {plugin_id} 执行错误: {e}"}

    @classmethod
    def reload(cls, plugin_id):
        """重新加载单个插件"""
        entry = cls._plugins.get(plugin_id)
        if not entry:
            return False
        folder = PLUGINS_DIR / plugin_id
        # 移除旧模块
        old_module_name = f"_plugin_{plugin_id}"
        if old_module_name in sys.modules:
            del sys.modules[old_module_name]
        # 重新扫描
        cls._plugins.pop(plugin_id, None)
        cls._load_single(folder)
        return True
```

前端错误隔离：
```javascript
// 加载插件 node.js 时的错误隔离
function loadPluginNodeJS(pluginId, jsContent) {
    try {
        var fn = new Function(jsContent);
        fn();
        var nodes = window.__plugin_nodes__;
        if (!nodes || typeof nodes !== 'object') {
            console.error('[PluginLoader] 插件', pluginId, '未导出 __plugin_nodes__');
            return null;
        }
        return nodes;
    } catch (e) {
        console.error('[PluginLoader] 插件', pluginId, 'node.js 执行错误:', e);
        showToast('插件 ' + pluginId + ' 加载失败: ' + e.message, 'err');
        return null;
    }
}
```

### 六、需要修改和新增的文件

#### 6.1 新增文件

| 文件 | 说明 |
|------|------|
| `plugins/` 目录 | 插件根目录 |
| `plugins/notify/manifest.json` | 消息提示插件清单 |
| `plugins/notify/node.js` | 消息提示节点前端定义 |
| `plugins/notify/backend.py` | 消息提示后端（可选，此插件可无后端） |
| `bridge/plugin_api.py` | 插件系统 API Mixin（list_plugins, get_plugin_node_js, call_plugin, reload_plugin） |
| `core/plugin_manager.py` | 插件管理器（扫描、加载、执行路由、上下文注入） |
| `core/plugin_context.py` | PluginContext 类定义 |

#### 6.2 需修改文件

| 文件 | 修改内容 |
|------|---------|
| `webui_app.py` | MacroBridge 继承 PluginApiMixin，初始化时调用 PluginManager.scan() |
| `bridge/__init__.py` | 如有需要，导出 PluginApiMixin |
| `automation/registry.py` | register_builtin_nodes() 中增加对插件节点的注册支持 |
| `automation/engine.py` | ExecContext 中处理 `plugin/*` 类型节点时路由到 PluginManager.execute() |
| `webui/modules/auto/editor-app.js` | 新增 `loadPlugins()` 函数，初始化时加载插件；工具箱插件面板动态渲染；刷新按钮支持 |
| `webui/modules/auto/nodes.js` | 新增 `registerPluginNodes(nodes)` 方法，将插件节点合并到 _nodeDefs |
| `webui/modules/auto/events-handlers.js` | 新增通用 `onPluginEvent(data)` 处理，根据 event_name 分发到插件 onExecute |
| `webui/automation_editor.html` | 插件面板中添加刷新按钮 |

#### 6.3 修改详情

**`webui_app.py`**：
```python
# 新增导入
from bridge.plugin_api import PluginApiMixin

class MacroBridge(
    MacroBridgeBase,
    ParamsApiMixin,
    RecorderApiMixin,
    MacroFileApiMixin,
    MacroBindingApiMixin,
    ListenerApiMixin,
    MacroSimplifyApiMixin,
    AutomationApiMixin,
    PluginApiMixin,          # ← 新增
):
    def __init__(self):
        super().__init__()
        if _has_automation:
            self._init_automation()
        self._init_plugins()  # ← 新增
```

**`bridge/plugin_api.py`**（新增）：
```python
class PluginApiMixin:
    def _init_plugins(self):
        from core.plugin_manager import PluginManager
        from core.paths import BASE_DIR
        plugins_dir = BASE_DIR / "plugins"
        PluginManager.scan(plugins_dir)

    def list_plugins(self):
        from core.plugin_manager import PluginManager
        return PluginManager.list_all()

    def get_plugin_node_js(self, plugin_id):
        from core.plugin_manager import PluginManager
        return PluginManager.get_node_js(plugin_id)

    def call_plugin(self, plugin_id, action, params=None):
        from core.plugin_manager import PluginManager
        return PluginManager.execute(plugin_id, action, params or {})

    def reload_plugin(self, plugin_id):
        from core.plugin_manager import PluginManager
        return PluginManager.reload(plugin_id)
```

**`automation/engine.py`** — ExecContext 节点执行路由中增加：
```python
# 在 _execute_node 方法中
if node_type.startswith("plugin/"):
    plugin_id = node_type.split("/", 1)[1]
    action = node_def.get("backendAction", "execute")
    result = PluginManager.execute(plugin_id, action, node.properties)
    if not result.get("ok"):
        self.errors.append(result.get("error", "插件执行失败"))
```

**`webui/modules/auto/editor-app.js`** — 新增插件加载：
```javascript
function loadPlugins() {
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.list_plugins) return;
    window.pywebview.api.list_plugins().then(function(res) {
        var plugins = (res && res.items) ? res.items : (res && res.data ? res.data : []);
        if (!plugins || !plugins.length) return;
        var pluginExpand = document.getElementById('plugin-expand');
        if (!pluginExpand) return;
        pluginExpand.innerHTML = '';
        var loaded = 0;
        for (var i = 0; i < plugins.length; i++) {
            (function(plugin) {
                window.pywebview.api.get_plugin_node_js(plugin.id).then(function(jsRes) {
                    var jsContent = (jsRes && jsRes.content) ? jsRes.content : null;
                    if (!jsContent) return;
                    try {
                        var fn = new Function(jsContent);
                        fn();
                        var nodes = window.__plugin_nodes__;
                        if (!nodes) return;
                        for (var typeKey in nodes) {
                            if (!nodes.hasOwnProperty(typeKey)) continue;
                            AutomationNodes._nodeDefs[typeKey] = nodes[typeKey];
                        }
                        // 在插件面板中添加拖拽项
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
                            pluginExpand.appendChild(item);
                        }
                        loaded++;
                    } catch(e) {
                        console.error('[PluginLoader]', plugin.id, e);
                    }
                });
            })(plugins[i]);
        }
    });
}
```

### 七、插件开发示例

#### 消息提示插件（纯前端）

`plugins/notify/manifest.json`：
```json
{
  "id": "notify",
  "name": "消息提示",
  "version": "1.0.0",
  "icon": "fa-solid fa-bell",
  "color": "#a855f7",
  "nodes": ["notify"]
}
```

`plugins/notify/node.js`：
```javascript
var nodes = {
  'plugin/notify': {
    display_name: '消息提示', color: '#a855f7', category: 'plugin',
    icon: 'fa-solid fa-bell',
    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
    params_schema: {
      title:    {type:'string', label:'标题', default:'提示', varRef:true},
      message:  {type:'string', label:'内容', default:'操作完成', varRef:true},
      sound:    {type:'enum', label:'音效', default:'default',
                 options:['default','info','success','warning','error','none']},
      duration: {type:'number', label:'显示时长(ms)', default:3000},
      position: {type:'enum', label:'位置', default:'bottom-right',
                 options:['bottom-right','bottom-left','top-right','top-left','center']}
    },
    onExecute: function(params) {
      if (window.AutomationEvents && AutomationEvents.showNotifyPopup) {
        AutomationEvents.showNotifyPopup(params);
      }
    }
  }
};
var __plugin_nodes__ = nodes;
```

#### 发送邮件插件（含后端）

`plugins/email/manifest.json`：
```json
{
  "id": "email",
  "name": "发送邮件",
  "version": "1.0.0",
  "icon": "fa-solid fa-envelope",
  "color": "#06b6d4",
  "nodes": ["send_email"],
  "backend": "backend.py"
}
```

`plugins/email/node.js`：
```javascript
var nodes = {
  'plugin/email': {
    display_name: '发送邮件', color: '#06b6d4', category: 'plugin',
    icon: 'fa-solid fa-envelope',
    inputs: [{name:'in',type:'flow'}], outputs: [{name:'next',type:'flow'}],
    params_schema: {
      to:      {type:'string', label:'收件人', default:'', varRef:true},
      subject: {type:'string', label:'主题', default:'', varRef:true},
      body:    {type:'string', label:'正文', default:'', varRef:true},
      smtp:    {type:'string', label:'SMTP服务器', default:'smtp.qq.com'},
      port:    {type:'number', label:'端口', default:465},
      account: {type:'string', label:'发件账号', default:''},
      password:{type:'string', label:'授权码', default:''}
    },
    backendAction: 'send'
  }
};
var __plugin_nodes__ = nodes;
```

`plugins/email/backend.py`：
```python
import smtplib
from email.mime.text import MIMEText

def register():
    return [{"action": "send", "description": "发送邮件"}]

def execute(action, params, context):
    if action != "send":
        return {"ok": False, "error": f"未知动作: {action}"}
    try:
        msg = MIMEText(params.get("body", ""), "plain", "utf-8")
        msg["Subject"] = params.get("subject", "")
        msg["From"] = params.get("account", "")
        msg["To"] = params.get("to", "")
        with smtplib.SMTP_SSL(params.get("smtp", "smtp.qq.com"), int(params.get("port", 465))) as s:
            s.login(params.get("account", ""), params.get("password", ""))
            s.send_message(msg)
        context.log("info", f"邮件已发送至 {params.get('to')}")
        return {"ok": True}
    except Exception as e:
        context.log("error", f"邮件发送失败: {e}")
        return {"ok": False, "error": str(e)}
```

#### 录屏插件（长时任务 + 状态推送）

`plugins/screen-record/backend.py`：
```python
import subprocess
import threading

_recorder_process = None

def register():
    return [
        {"action": "start", "description": "开始录屏"},
        {"action": "stop", "description": "停止录屏"},
    ]

def execute(action, params, context):
    global _recorder_process
    if action == "start":
        # 启动录屏进程（示例用 ffmpeg）
        output = params.get("output", "recording.mp4")
        _recorder_process = subprocess.Popen(
            ["ffmpeg", "-f", "gdigrab", "-i", "desktop", output],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        # 异步监控，完成后通知前端
        def _watch():
            _recorder_process.wait()
            context.emit("plugin_screen_record", {"status": "stopped"})
        threading.Thread(target=_watch, daemon=True).start()
        context.log("info", "录屏已开始")
        return {"ok": True}

    elif action == "stop":
        if _recorder_process:
            _recorder_process.terminate()
            _recorder_process = None
        context.log("info", "录屏已停止")
        return {"ok": True}

    return {"ok": False, "error": f"未知动作: {action}"}
```

### 八、前端刷新按钮

在插件展开面板头部添加刷新按钮：

```html
<div class="sb-tool-expand" id="plugin-expand" style="display:none">
  <div style="display:flex;align-items:center;padding:2px 10px;gap:6px">
    <span style="font-size:10px;color:var(--txt3);flex:1">可用插件</span>
    <button class="prop-btn outline" id="btn-reload-plugins"
            style="padding:2px 8px;font-size:10px" title="重新加载插件">
      <i class="fa-solid fa-rotate"></i>
    </button>
  </div>
  <!-- 插件项动态插入 -->
</div>
```

### 九、执行引擎集成

当自动化引擎执行到 `plugin/*` 类型节点时：

```
1. 检查 node_def.onExecute 是否存在
   → 存在：在前端调用 onExecute(params)（通过事件推送触发）
2. 检查 node_def.backendAction 是否存在
   → 存在：调用 PluginManager.execute(plugin_id, action, params)
3. 两者可同时存在（前端即时反馈 + 后端持久逻辑）
```

### 十、总结：改动清单

| 序号 | 操作 | 文件/目录 | 说明 |
|------|------|-----------|------|
| 1 | 新增 | `plugins/` | 插件根目录 |
| 2 | 新增 | `plugins/notify/` | 消息提示插件完整示例 |
| 3 | 新增 | `core/plugin_manager.py` | 插件管理器（扫描/加载/执行/重载） |
| 4 | 新增 | `core/plugin_context.py` | PluginContext 上下文类 |
| 5 | 新增 | `bridge/plugin_api.py` | 前端 API 接口 Mixin |
| 6 | 修改 | `webui_app.py` | 继承 PluginApiMixin，初始化插件 |
| 7 | 修改 | `automation/engine.py` | 执行路由增加 plugin/* 节点处理 |
| 8 | 修改 | `automation/registry.py` | 支持插件节点注册 |
| 9 | 修改 | `webui/modules/auto/editor-app.js` | 新增 loadPlugins()，动态渲染插件面板，刷新按钮 |
| 10 | 修改 | `webui/modules/auto/nodes.js` | 新增 registerPluginNodes() |
| 11 | 修改 | `webui/modules/auto/events-handlers.js` | 新增 onPluginEvent 通用处理 |
| 12 | 修改 | `webui/automation_editor.html` | 插件面板添加刷新按钮，移除硬编码的 plugin/notify |

---