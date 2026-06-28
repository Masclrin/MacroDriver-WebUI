任务已完成！以下是交付文档：

---

### 【功能描述】

为自动化编辑器引入约定式插件系统，使第三方开发者无需修改原代码即可开发、部署插件节点。插件通过独立文件夹存放，后端动态扫描加载，前端通过统一接口获取节点定义并注册到编辑器中。

### 【业务正常流时序】

1. **应用启动** → 后端 `PluginManager.scan()` 扫描 `plugins/` 目录，加载各插件的 `manifest.json` 和可选的 `backend.py`，注册到 `PluginRegistry`
2. **编辑器初始化** → 前端调用 `list_plugins()` 获取插件列表 → 逐个调用 `get_plugin_node_js(id)` 获取 `node.js` 内容 → `new Function()` 执行后注册到 `AutomationNodes._nodeDefs` → 在插件面板动态渲染可拖拽项
3. **用户使用插件节点** → 从插件面板拖拽到画布 → 属性面板自动渲染 `params_schema` → 运行时引擎路由到 `_handle_plugin_node()` → 调用后端 `PluginManager.execute()` 或前端 `onExecute` 回调

### 【相关代码】

**新增文件：**

- [core/plugin_context.py](file:///g:/宏引擎/宏驱动 webui 2.5/core/plugin_context.py) — PluginContext 上下文类，提供 `emit()` 向前端推送事件和 `log()` 写日志
- [core/plugin_manager.py](file:///g:/宏引擎/宏驱动 webui 2.5/core/plugin_manager.py) — PluginManager 核心类，`scan()`/`list_all()`/`get_node_js()`/`execute()`/`reload()`/`get_manifest()`/`_emit_to_window()`
- [bridge/plugin_api.py](file:///g:/宏引擎/宏驱动 webui 2.5/bridge/plugin_api.py) — PluginApiMixin，暴露 `list_plugins`/`get_plugin_node_js`/`call_plugin`/`reload_plugin` 四个前端 API
- [plugins/notify/manifest.json](file:///g:/宏引擎/宏驱动 webui 2.5/plugins/notify/manifest.json) — 消息提示插件清单
- [plugins/notify/node.js](file:///g:/宏引擎/宏驱动 webui 2.5/plugins/notify/node.js) — 消息提示节点前端定义（含 `onExecute` 回调）

**修改文件：**

- [webui_app.py](file:///g:/宏引擎/宏驱动 webui 2.5/webui_app.py) — MacroBridge 继承 PluginApiMixin，`__init__` 中调用 `_init_plugins()`
- [automation/engine.py](file:///g:/宏引擎/宏驱动 webui 2.5/automation/engine.py) — 新增 `_handle_plugin_node()` 函数，`_execute_node()` 中对 `plugin/*` 类型节点路由到此函数
- [automation/registry.py](file:///g:/宏引擎/宏驱动 webui 2.5/automation/registry.py) — 新增 `register_plugin_nodes()` 函数，在 `register_builtin_nodes()` 末尾调用
- [webui/modules/auto/nodes.js](file:///g:/宏引擎/宏驱动 webui 2.5/webui/modules/auto/nodes.js) — 新增 `registerPluginNodes()` 方法，移除硬编码的 `plugin/notify` fallback 定义
- [webui/modules/auto/events-handlers.js](file:///g:/宏引擎/宏驱动 webui 2.5/webui/modules/auto/events-handlers.js) — 新增 `onPluginEvent` 事件入口和 `handlePluginEvent()` 通用处理方法
- [webui/modules/auto/editor-app.js](file:///g:/宏引擎/宏驱动 webui 2.5/webui/modules/auto/editor-app.js) — 新增 `loadPlugins()` 函数、刷新按钮绑定、`initEditor` 末尾调用 `loadPlugins()`，`simulateExecution` 中改为通用插件 `onExecute` 调用
- [webui/automation_editor.html](file:///g:/宏引擎/宏驱动 webui 2.5/webui/automation_editor.html) — 插件面板替换为带刷新按钮的动态容器，移除硬编码的 `btn-plugin-notify`

### 【体验自检清单】

| 检查项 | 处理方式 |
|--------|---------|
| **状态感知** | `loadPlugins()` 中每个插件加载失败有 `showToast` 提示；刷新按钮点击后立即提示"正在重新加载插件" |
| **异常宽容** | 后端 `PluginManager` 每个插件加载用 try-catch 隔离，单个失败不影响其他；前端 `new Function()` 执行 node.js 用 try-catch 包裹，失败有 Toast 提示 |
| **边缘场景防御** | 插件列表为空时 `loadPlugins` 直接 return；`__plugin_nodes__` 未导出时有 console.error 提示；`get_plugin_node_js` 返回 null 时跳过 |
| **交互闭环** | 刷新按钮点击 → Toast 提示 → 插件重新加载 → 面板动态更新；插件加载失败 → Toast 错误提示 |