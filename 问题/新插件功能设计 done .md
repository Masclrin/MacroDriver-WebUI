## 插件架构讨论

当前的"插件"实现只是硬编码在原代码中的，完全没有做到插件应有的**可插拔、便携、独立开发**特性。下面是我的方案建议：

### 核心思路：约定式插件目录 + 动态加载

```
webui/
  plugins/                    ← 插件根目录
    notify/                   ← 消息提示插件
      manifest.json           ← 插件描述文件（必须）
      node.js                 ← 节点定义（必须）
      icon.svg                ← 自定义图标（可选）
      backend.py              ← 后端逻辑（可选）
    email/                    ← 发送邮件插件
      manifest.json
      node.js
      backend.py
    screen-record/            ← 视频录屏插件
      manifest.json
      node.js
      backend.py
    replay/                   ← 精彩回放插件
      manifest.json
      node.js
      backend.py
```

### manifest.json 规范

```json
{
  "id": "notify",
  "name": "消息提示",
  "version": "1.0.0",
  "author": "xxx",
  "description": "在屏幕右下角弹出消息提示",
  "icon": "fa-solid fa-bell",
  "color": "#a855f7",
  "nodes": ["notify"],
  "backend": "backend.py"
}
```

### node.js 规范

每个插件导出一个节点定义数组，格式与现有 `AutomationNodes._nodeDefs` 完全一致：

```javascript
// plugins/notify/node.js
export const nodes = {
  'plugin/notify': {
    display_name: '消息提示',
    color: '#a855f7',
    category: 'plugin',
    icon: 'fa-solid fa-bell',
    inputs: [{name:'in',type:'flow'}],
    outputs: [{name:'next',type:'flow'}],
    params_schema: {
      title: {type:'string', label:'标题', default:'提示', varRef:true},
      message: {type:'string', label:'内容', default:'操作完成', varRef:true},
      sound: {type:'enum', label:'音效', default:'default', 
              options:['default','info','success','warning','error','none']},
      duration: {type:'number', label:'显示时长(ms)', default:3000},
      position: {type:'enum', label:'位置', default:'bottom-right',
                 options:['bottom-right','bottom-left','top-right','top-left','center']}
    },
    // 插件独有的：执行时调用的前端处理函数
    onExecute: function(params) {
      // 前端侧的即时效果（如弹窗、音效）
      AutomationEvents.showNotifyPopup(params);
    },
    // 后端API调用（可选）
    backendAction: 'plugin_notify'
  }
};
```

### 加载流程

1. **后端扫描** `plugins/` 目录，读取每个子目录的 `manifest.json`
2. 后端提供 API `list_plugins()` → 返回所有插件的 manifest 列表
3. 前端在初始化时调用 `list_plugins()`，然后**动态 import** 每个插件的 `node.js`
4. 将插件节点注册到 `AutomationNodes._nodeDefs` 中
5. 在工具箱的"插件"展开面板中动态添加插件项

### 关键设计决策需要讨论

| 问题 | 选项A | 选项B |
|------|-------|-------|
| **前端加载方式** | 后端返回 node.js 内容，前端 eval/Function | 前端动态 `import('./plugins/xxx/node.js')` |
| **后端交互** | 每个插件提供独立 .py，后端自动注册为 API | 插件统一调用 `call_plugin(id, action, params)` |
| **安全隔离** | 插件运行在沙箱中，限制 API 访问 | 信任所有本地插件，无沙箱 |
| **UI扩展** | 仅支持节点类型扩展 | 支持自定义属性面板渲染 |

### 我的推荐

考虑到你的场景（本地应用、pywebview、个人/小团队开发）：

- **前端加载**：推荐后端读取 `node.js` 内容返回给前端，前端用 `new Function()` 执行。因为 `import()` 在 file:// 协议下有限制，而 pywebview 可能不总是启用了本地 HTTP 服务
- **后端交互**：推荐统一入口 `call_plugin(plugin_id, action, params)`，后端动态加载插件的 `.py` 文件并调用对应方法。这样不需要为每个插件注册独立 API
- **安全**：本地应用无需沙箱，信任所有插件
- **UI扩展**：初期仅支持节点定义扩展，后续可支持自定义属性面板渲染函数

### 你提到的插件实现思路

| 插件 | 前端行为 | 后端行为 |
|------|---------|---------|
| **消息提示** | 弹窗+音效 | 无需后端 |
| **发送邮件** | 无特殊UI | SMTP发送 |
| **启动录屏** | 状态指示 | 调用录屏API（如OBS/PPT录屏） |
| **结束录屏** | 状态指示 | 停止录屏 |
| **精彩回放** | 回放预览 | 调用回放缓冲API |

---

你觉得这个方案怎么样？有哪些地方需要调整？比如：
1. 你更倾向于前端动态 import 还是后端返回内容前端执行？
2. 后端插件 .py 的加载方式你有偏好吗？
3. 是否需要支持插件的热重载（开发时修改文件后自动刷新）？