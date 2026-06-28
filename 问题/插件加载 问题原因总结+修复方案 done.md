## 问题总结

### 根本原因

前端 JS 上下文隔离问题 ——自动化编辑器运行在 `<iframe>` 中（ index.html 第 323 行），而后端 PluginManager._emit_to_window() 通过 window.evaluate_js() 执行 JavaScript 时，操作的是 主窗口 （index.html）的 JS 上下文，而非 iframe 内部的上下文。

因此 window._automationEvents 在主窗口中根本不存在，导致后端 emit 的事件无法到达前端处理函数。

在用户侧展示的就是插件有加载，但无法正确使用的情况

### 修复方式

在 [events-handlers.js](file:///c:\Users\1\Downloads\宏驱动 webui 2.6\webui\modules\auto\events-handlers.js#L47-L50) 的 init() 末尾添加了 iframe → parent 的同步：

```
if (window.parent && window.parent !== 
window) {
    window.parent._automationEvents = 
    window._automationEvents;
}
```

这样后端 evaluate_js 在主窗口执行时，就能通过 window.parent._automationEvents 访问到 iframe 内部的事件处理器。
