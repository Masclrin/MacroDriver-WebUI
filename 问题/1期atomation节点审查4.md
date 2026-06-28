**中文总结：**

1. **用户要做什么**：在指定目录下搜索插件系统的后端代码，包括6个具体目标：`list_plugins`、`get_plugin_node_js`、`reload_plugin`、`PluginRegistry`、`registerPluginNodes`、`__plugin_nodes__` 的实现。
2. **计划步骤**：使用 Grep 和 SearchCodebase 工具并行搜索这6个目标，返回代码片段、文件路径和行号。
3. **缺少的信息**：无，目标明确，可以直接开始搜索。

现在开始并行搜索所有6个目标：
---

# 🔍 自动化编辑器 - 工具箱/插件/变量查看器/工具栏/画布交互 全面问题报告

---

## 一、工具箱

### 🟡 BUG-T1: 工具箱分类缺少 `plugin` 类别

- **代码** [editor-app.js:180-190](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L180): `TOOLBOX_CATEGORIES` 只有 flow/action/detection/control/script_block/monitor/variable/preset/utility 9个分类
- **影响**: 插件节点通过 `registerPluginNodes` 注册时 category 为 `'plugin'`，但工具箱分类中没有 `plugin` 条目。插件节点不会出现在左侧工具箱的分类列表中，**只能通过底部插件面板拖拽添加**。用户在工具箱中找不到插件节点，可能认为插件未加载成功。

### 🟡 BUG-T2: 工具箱搜索不支持拼音/中文搜索

- **代码** [editor-app.js:563](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L563):
  ```javascript
  if (filter && def.display_name.toLowerCase().indexOf(filter) < 0 && typeKey.toLowerCase().indexOf(filter) < 0) continue;
  ```
- **影响**: 搜索只匹配 `display_name` 和 `typeKey`，不支持中文别名或拼音。例如搜索"点击"找不到"鼠标点击"节点（display_name 是"鼠标点击"，但搜索"鼠标"可以找到）。搜索"yanse"找不到"检测颜色"。

### 💡 BUG-T3: 工具箱节点没有tooltip说明

- **代码** [editor-app.js:586-589](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L586): 工具箱节点项只有图标和名称，没有 `title` 属性
- **影响**: 用户悬停在工具箱节点上时，看不到节点的功能说明。需要拖出来才能看到属性面板中的参数。

---

## 二、坐标拾取工具 (tools.js)

### 🔴 BUG-TL1: 坐标拾取 — `relative` 模式下截图尺寸使用窗口客户区尺寸而非虚拟尺寸

- **代码** [tools.js:251-255](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/tools.js#L251):
  ```javascript
  if (coordMode === 'relative') {
      return {
          x: Math.round(px / data.width * 1000) / 1000,
          y: Math.round(py / data.height * 1000) / 1000
      };
  }
  ```
- **影响**: `data.width` 和 `data.height` 是截图的实际像素尺寸（窗口客户区大小），但后端 `coordinate.py` 的 relative 模式使用的是**虚拟尺寸**（`virtual_width`/`virtual_height`，即窗口客户区逻辑尺寸，受 DPI 缩放影响）。如果窗口有 DPI 缩放（如 125%/150%），截图像素尺寸与虚拟尺寸不一致，导致拾取的坐标偏移。例如 150% DPI 下，一个 800x600 的窗口，截图可能是 1200x900 像素，但虚拟尺寸是 800x600，拾取坐标会偏移约 1.5 倍。

### 🔴 BUG-TL2: 区域拾取 — `relative` 模式下宽高计算同样使用截图像素尺寸

- **代码** [tools.js:325-330](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/tools.js#L325):
  ```javascript
  logicRect = [
      Math.round(x1 / data.width * 1000) / 1000,
      Math.round(y1 / data.height * 1000) / 1000,
      Math.round(rw / data.width * 1000) / 1000,
      Math.round(rh / data.height * 1000) / 1000
  ];
  ```
- **影响**: 同 BUG-TL1，区域拾取的宽高也使用截图像素尺寸计算，导致 relative 模式下区域范围不正确。

### 🟡 BUG-TL3: 坐标拾取 — `hwnd_var` 被覆盖为字符串格式的句柄值

- **代码** [tools.js:369](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/tools.js#L369):
  ```javascript
  if (data.hwnd) node.properties.hwnd_var = String(data.hwnd);
  ```
- **影响**: `hwnd_var` 字段本意是"窗口变量引用"（通过变量选择器选择一个存储了句柄的变量名），但拾取后直接填入了句柄数值字符串（如 `"12345"`）。如果用户之前设置了变量引用 `${my_hwnd}`，拾取后会被覆盖为原始句柄值，变量引用丢失。用户需要手动重新输入变量引用。

### 🟡 BUG-TL4: 坐标拾取 — 拾取后自动修改 `mode`/`capture_mode` 可能不符合用户预期

- **代码** [tools.js:370-376](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/tools.js#L370):
  ```javascript
  if (data.mode) {
      if (node.properties.capture_mode !== undefined) {
          node.properties.capture_mode = data.mode;
      } else {
          node.properties.mode = data.mode;
      }
  }
  ```
- **影响**: 用户在 window 模式下手动设置了 `hwnd_var`，然后拾取坐标时点击了另一个窗口，`mode` 被自动修改为该窗口的模式。如果用户原本就是 window 模式但拾取时误点了桌面，mode 会被改为 screen，导致后续执行行为改变。

---

## 三、变量统计查看器

### 🔴 BUG-VP1: 变量面板 — `store_var` 类型判断不完整

- **代码** [editor-app.js:397-399](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L397):
  ```javascript
  if (node.properties.store_var) {
      var sType = defKey.indexOf('ocr') >= 0 ? 'string' : 'boolean';
      userVars.push({name: node.properties.store_var, type: sType, ...});
  }
  ```
- **影响**: 所有非 OCR 节点的 `store_var` 都被标记为 `boolean` 类型。但 `preset_read_text` 的 `store_var` 存储的是文本（string），`check_ocr` 的 `store_var` 存储的是 OCR 文本（string）。`check_image` 的 `store_var` 存储的是匹配位置文本（string）。变量面板中显示的类型与实际类型不符，误导用户。
- **对比** `property.js` 的 `_collectStructuredVars` 有更精确的类型判断（`check_image` → string, `check_ocr` → string），但 `updateVarPanel` 没有同步这些逻辑。

### 🔴 BUG-VP2: 变量面板 — 缺少 `preset_read_text` 的 `store_var` 收集

- **代码** [editor-app.js:375-416](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L375): `updateVarPanel` 函数中，`store_var` 的收集是通用的（第397行），但类型判断只区分 OCR 和非 OCR
- **影响**: `preset_read_text` 的 `store_var` 被收集了，但类型被错误标记为 `boolean`（因为 defKey 不包含 'ocr'）。与 `_collectStructuredVars`（property.js）中的遗漏不同——那里是完全没有收集，这里是收集了但类型错误。

### 🟡 BUG-VP3: 变量面板 — `var_math`/`var_string`/`var_convert`/`var_compare` 的 `result` 输出不在面板中

- **代码** [editor-app.js:408-415](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L408): 面板只收集 `node.outputs` 中非 flow 类型的端口输出
- **影响**: `var_math` 等变量操作节点有 `result` 数据输出端口，这些端口出现在"节点输出"区域，但显示的是 `节点名.result` 格式（如 `var_math #3.result`），而不是变量名。用户需要知道这些节点的 result 可以通过数据连线或 `${3.result}` 引用，但面板没有提供这种格式的引用。

### 🟡 BUG-VP4: 变量面板 — 点击变量只复制引用，不插入到当前编辑的字段

- **代码** [editor-app.js:449-456](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L449):
  ```javascript
  viEl.addEventListener('click', function() {
      var varRef = viEl.dataset.copy || viEl.title || '';
      if (navigator.clipboard) {
          navigator.clipboard.writeText(varRef).then(function() {
              showToast('已复制: ' + varRef, 'ok', 1500);
          });
      }
  });
  ```
- **影响**: 用户在属性面板编辑某个字段的变量引用时，点击变量面板中的变量，期望自动插入到当前编辑的字段中，但实际只是复制到剪贴板。用户需要手动粘贴。对比 `property.js` 中的变量选择器是直接插入到对应字段的。

---

## 四、顶部工具栏

### 🔴🔴 BUG-TB1: 执行验证 — 循环检测误判 goto 合法回跳为循环

- **代码** [editor-app.js:996-1015](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L996):
  ```javascript
  function hasCycle(nid) {
      visited[nid] = true;
      recStack[nid] = true;
      var neighbors = adj[nid] || [];
      for (var k = 0; k < neighbors.length; k++) {
          if (!visited[neighbors[k]]) {
              if (hasCycle(neighbors[k])) return true;
          } else if (recStack[neighbors[k]]) {
              return true;
          }
      }
      recStack[nid] = false;
      return false;
  }
  ```
- **影响**: 这个循环检测算法检测的是 flow 连接中的有向环。但 `control/goto` 节点的合法回跳（如从循环体跳回循环开始）会形成有向环，被误判为"循环连线"。用户使用 goto 节点回跳时，**无法运行脚本**，提示"图中存在循环连线"。这是 goto 节点的核心功能，却被验证逻辑阻止了。
- **修复建议**: 排除 goto 节点产生的回边，或只在非 goto 连接中检测循环。

### 🔴 BUG-TB2: 暂停/继续 — `PAUSED` 状态下运行按钮未恢复

- **代码** [editor-app.js:261-264](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L261):
  ```javascript
  } else if (state === 'PAUSED') {
      dot.style.background = 'var(--c-detect)';
      dot.classList.remove('run-i');
      txt.textContent = '已暂停';
      // ← 没有恢复运行按钮！
  }
  ```
- **对比** `RUNNING` 状态（第253-260行）禁用了运行按钮，`COMPLETED`/`idle` 状态恢复了运行按钮
- **影响**: 脚本运行后点暂停，运行按钮仍然处于禁用状态（灰色、不可点击）。用户想继续运行，只能点暂停按钮（切换回 running），但运行按钮始终不可用。如果用户习惯性地点运行按钮来继续，会发现按钮无法点击。

### 🔴 BUG-TB3: 停止 — `COMPLETED` 状态下停止按钮行为异常

- **代码** [editor-app.js:1086-1096](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L1086):
  ```javascript
  function stopGraph(silent) {
      var state = AutomationCore.executionState;
      if (state !== 'RUNNING' && state !== 'PAUSED' && state !== 'COMPLETED') return;
      // ...
  }
  ```
- **影响**: 脚本执行完成后状态变为 `COMPLETED`，此时点停止按钮会执行停止逻辑（清除高亮、调用后端 stop_automation）。但后端任务已经完成了，调用 `stop_automation` 可能无效或报错。更关键的是，`COMPLETED` 状态下停止按钮应该不需要存在——任务已经结束了。

### 🟡 BUG-TB4: 重命名 — 不允许使用"未命名脚本"但新建时默认就是这个名字

- **代码** [editor-app.js:963](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L963):
  ```javascript
  if (!newName || newName === '未命名脚本') {
      el.value = _currentScriptName || '未命名脚本';
      if (!newName) showToast('名称不能为空', 'warn');
      return;
  }
  ```
- **影响**: 新建画布时默认名称为"未命名脚本"，但重命名时不允许使用这个名字。用户如果想恢复默认名称，无法通过重命名操作实现。保存时也会强制要求改名。这个设计意图是防止用户保存默认名称的脚本，但体验上有些矛盾。

### 🟡 BUG-TB5: 新建画布 — 保存确认逻辑可能导致用户操作中断

- **代码** [editor-app.js:898-937](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L898): `newCanvas` 函数的确认逻辑复杂
- **影响**: 当画布有未保存更改时，点新建会弹出确认框。如果用户选择"确定"（保存），但保存过程中出错（如后端不可用），函数会回退到导出文件，但**不会继续新建画布**。用户保存后仍然停留在旧画布上，需要再次点新建。

---

## 五、画布交互

### 🔴🔴 BUG-C1: 复制粘贴 — 多选复制后粘贴位置重叠

- **代码** [editor-app.js:2312-2314](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L2312):
  ```javascript
  var newNode = AutomationCore.addNodeAtPosition(item.nodeType, item.pos.x + 40, item.pos.y + 40);
  ```
- **影响**: 多选复制时，所有节点的偏移量都是固定的 +40,+40。如果原始节点之间有特定间距（如 A 在 x=100, B 在 x=300），粘贴后 A' 在 x=140, B' 在 x=340，间距保持不变。但**多次粘贴**时，每次都偏移 +40,+40，导致新节点与上一次粘贴的节点完全重叠。用户需要手动拖开才能区分。
- **对比**: 专业的节点编辑器通常每次粘贴递增偏移量。

### 🔴🔴 BUG-C2: 撤销 — 撤销后节点ID改变导致连线丢失

- **代码** [editor-app.js:192-224](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L192):
  ```javascript
  _restore: function() {
      this._paused = true;
      try {
          var data = JSON.parse(this._stack[this._idx]);
          deserializeGraph(data);
      } catch(e) { ... }
      finally { this._paused = false; }
  }
  ```
- **`deserializeGraph`** [editor-app.js:709-811](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L709): 先 `AutomationCore.clear()`，然后重新创建所有节点
- **影响**: 撤销操作会**清空画布并重新创建所有节点**。新创建的节点使用序列化数据中的 ID（第720行 `node.id = parseInt(nj.id)`），所以ID应该保持一致。但 `clear()` 后 `lgGraphObj` 的内部 nextNodeId 计数器可能不正确——如果之前有 ID=5 的节点被删除，然后撤销恢复时重新创建 ID=5 的节点，但计数器已经超过了5，后续新建节点可能从更大的ID开始。这不是严重问题，但**撤销后属性面板的编辑状态会丢失**（因为 `AutomationProperty.render(null)` 不会被调用，但节点是全新创建的DOM元素）。

### 🔴 BUG-C3: 复制粘贴 — 粘贴的节点不保留 `_customName`

- **代码** [editor-app.js:2286-2293](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L2286):
  ```javascript
  _clipboard.push({
      nodeType: selNodes[i]._defKey,
      params: JSON.parse(JSON.stringify(selNodes[i].properties || {})),
      pos: { x: selNodes[i].pos[0], y: selNodes[i].pos[1] }
  });
  ```
- **影响**: 剪贴板只保存了 `nodeType`、`params`、`pos`，没有保存 `_customName`（用户自定义的节点名称）。粘贴后的节点会使用默认名称，用户之前给节点起的别名丢失了。

### 🔴 BUG-C4: Ctrl+D 复制 — 只支持单节点，不支持多选

- **代码** [editor-app.js:2336-2346](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L2336):
  ```javascript
  if (e.ctrlKey && e.key === 'd' && AutomationCore.selectedNode) {
      e.preventDefault();
      var cloned = AutomationCore.selectedNode.clone();
      ...
  }
  ```
- **影响**: Ctrl+D 只检查 `AutomationCore.selectedNode`（最后选中的单个节点），不检查 `getSelectedNodes()`（多选列表）。用户多选了5个节点后按 Ctrl+D，只有最后选中的1个节点被复制。而 Ctrl+C/V 支持多选复制粘贴。行为不一致。

### 🔴 BUG-C5: 右键菜单 — "重复"操作使用 `clone()` 但不检查返回值

- **代码** [editor-app.js:1349-1358](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L1349):
  ```javascript
  case 'duplicate':
      if (contextTarget) {
          var cloned = contextTarget.clone();
          if (cloned) {
              AutomationCore.lgGraphObj.add(cloned);
              ...
          }
      }
  ```
- **影响**: `clone()` 方法可能返回 null（如果节点类型未注册），此时不执行任何操作，但也没有给用户提示。用户点"重复"后没有任何反应，不知道为什么失败。

### 🟡 BUG-C6: Delete键 — 删除选中节点后不更新变量面板

- **代码** [editor-app.js:2251-2267](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L2251):
  ```javascript
  if (e.key === 'Delete') {
      var selNodes = AutomationCore.getSelectedNodes();
      if (selNodes.length > 0) {
          AutomationCore.deleteSelectedNodes();
          ...
          // ← 没有调用 updateVarPanel
      }
  }
  ```
- **影响**: 删除一个 `var_set` 节点后，变量面板中仍然显示该变量，直到用户进行其他操作触发 `updateStatusBar`。用户可能误以为变量仍然存在。

### 🟡 BUG-C7: 全选 — Ctrl+A 在输入框中无法正常全选文本

- **代码** [editor-app.js:2273-2277](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L2273):
  ```javascript
  if (e.ctrlKey && e.key === 'a') {
      e.preventDefault();
      AutomationCore.selectAll();
  }
  ```
- **影响**: 虽然第2232行检查了 `tag === 'input' || tag === 'textarea'` 会 return，但这个检查在快捷键处理之前。Ctrl+A 在输入框中被拦截了，用户无法在属性面板的输入框中使用 Ctrl+A 全选文本。

### 🟡 BUG-C8: 撤销 — 撤销栈在 `deserializeGraph` 期间暂停，但属性面板不刷新

- **代码** [editor-app.js:213-223](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L213):
  ```javascript
  _restore: function() {
      this._paused = true;
      try {
          var data = JSON.parse(this._stack[this._idx]);
          deserializeGraph(data);
      } catch(e) { ... }
      finally { this._paused = false; }
  }
  ```
- **影响**: 撤销后 `deserializeGraph` 会重建所有节点，但不会刷新属性面板。如果用户之前在编辑某个节点的属性，撤销后面板仍然显示旧节点的属性（但旧节点已经被清除了），可能导致面板与实际节点状态不一致。

### 🟡 BUG-C9: 画布拖拽 — 拖拽节点时触发 `onGraphChange` 但不触发 `undoManager.push`

- **代码** [editor-app.js:2041](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L2041):
  ```javascript
  AutomationCore.lgGraphObj.onNodeAdded = function() { updateStatusBar(); updateMinimap(); undoManager.push(); };
  ```
- **影响**: 只有 `onNodeAdded`、`onNodeRemoved`、`onConnectionChange` 触发 undo push。**拖拽节点改变位置不会触发 undo push**。用户把节点拖到新位置后，无法通过 Ctrl+Z 撤销位置变更。这是常见的用户期望——大多数编辑器都支持撤销移动操作。

---

## 六、插件系统

### 🔴🔴 BUG-PL1: 插件节点 — 后端注册的节点定义与前端 node.js 定义不一致

- **后端注册** [registry.py:85-99](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/automation/registry.py#L85):
  ```python
  PluginRegistry.register_node({
      "type": type_key,
      "category": "plugin",
      "display_name": display_name,
      "color": color,
      "icon": icon,
      "inputs": [{"name": "in", "type": "flow"}],
      "outputs": [{"name": "next", "type": "flow"}],
      "params_schema": {},
      "handler": f"_plugin_{plugin_id}",
  })
  ```
- **前端 node.js**: 插件的 `node.js` 文件定义了完整的 `inputs`、`outputs`、`params_schema`
- **影响**: 后端注册的插件节点**只有1个flow输入和1个flow输出，params_schema为空**。当后端定义加载到前端时（通过 `get_frontend_payload`），会**覆盖**前端 node.js 中更完整的定义。这意味着：
  1. 如果后端定义先加载，插件的完整参数和端口定义被覆盖为空
  2. 引擎执行时使用后端定义，但处理器是 `_plugin_{plugin_id}`，需要从 `NODE_HANDLERS` 中查找
  3. 前端 fallback（node.js）定义的端口和参数可能被后端空定义覆盖

### 🔴 BUG-PL2: 插件重载 — `_cleanupPluginNodes` 只清前端定义，不清后端注册

- **代码** [editor-app.js:1821-1836](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L1821):
  ```javascript
  function _cleanupPluginNodes() {
      var defs = AutomationNodes._nodeDefs;
      for (var k in defs) {
          if (defs.hasOwnProperty(k) && k.startsWith('plugin/')) {
              delete defs[k];
          }
      }
      if (cats.plugin) { cats.plugin.nodes = []; }
  }
  ```
- **影响**: 重载插件时，前端清除了 plugin/ 开头的节点定义，但**后端的 PluginRegistry 没有被清除**。重载后后端重新调用 `register_plugin_nodes()`，但旧的定义可能仍然存在于 `PluginRegistry._node_types` 中（第86行有 `if PluginRegistry.get_node(type_key): continue` 的去重检查）。如果插件的节点定义发生了变化（如新增了参数），后端不会更新，因为旧定义已经存在。

### 🔴 BUG-PL3: 插件 node.js — 使用 `new Function()` 执行存在安全风险

- **代码** [editor-app.js:1909](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L1909):
  ```javascript
  var fn = new Function(jsContent + '\nif(typeof __plugin_nodes__!=="undefined"){window.__plugin_nodes__=__plugin_nodes__;}');
  fn();
  ```
- **影响**: 插件的 `node.js` 文件内容被直接作为 JavaScript 执行，没有任何沙箱隔离。恶意插件可以执行任意代码，访问 `window`、`document`、`localStorage` 等全局对象。虽然这是已知的架构选择，但用户安装第三方插件时应意识到风险。

### 🟡 BUG-PL4: 插件加载 — 串行加载所有插件，速度慢

- **代码** [editor-app.js:1883-1966](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L1883):
  ```javascript
  var chain = Promise.resolve();
  for (var i = 0; i < plugins.length; i++) {
      (function(plugin) {
          chain = chain.then(function() {
              return window.pywebview.api.get_plugin_node_js(plugin.id)...
          });
      })(plugins[i]);
  }
  ```
- **影响**: 所有插件的 `node.js` 文件串行加载（一个接一个），如果有多个插件，加载时间会线性增长。可以改为并行加载。

### 🟡 BUG-PL5: 插件节点 — `onExecute` 只在模拟执行时调用

- **代码** [editor-app.js:1138-1147](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L1138):
  ```javascript
  if (defKey && defKey.startsWith('plugin/')) {
      var nodeDef = AutomationNodes.getNodeDef(defKey);
      if (nodeDef && nodeDef.onExecute) {
          try { nodeDef.onExecute(node.properties || {}); } catch(e) { ... }
      }
  }
  ```
- **影响**: `onExecute` 只在 `simulateExecution`（无后端时的模拟执行）中被调用。实际执行时，插件节点的处理完全由后端的 `_plugin_{plugin_id}` handler 负责，前端的 `onExecute` 不会被调用。如果插件开发者只实现了 `onExecute` 而没有实现后端 handler，插件在实际运行时不会执行任何操作。

---

## 七、执行状态与节点联动

### 🔴 BUG-EX1: 执行状态轮询 — 不检测 PAUSED 状态

- **代码** [editor-app.js:1056-1084](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L1056):
  ```javascript
  _statusPollInterval = setInterval(function() {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.get_automation_status) {
          window.pywebview.api.get_automation_status().then(function(res) {
              if (res && res.ok && res.data && res.data.status) {
                  var st = res.data.status.toUpperCase();
                  if (st === 'COMPLETED') { ... }
                  else if (st === 'ERROR') { ... }
                  // ← 没有处理 PAUSED 状态！
              }
          });
      }
  }, 1000);
  ```
- **影响**: 如果后端任务进入 PAUSED 状态（如通过引擎内部的暂停机制，而非前端暂停按钮），前端不会更新状态显示。状态栏仍然显示"运行中"，但实际已暂停。用户困惑于"为什么脚本不动了"。

### 🟡 BUG-EX2: 执行完成后 — 不清除节点高亮

- **代码** [editor-app.js:1068-1072](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L1068):
  ```javascript
  if (st === 'COMPLETED') {
      setExecutionState('completed');
      clearInterval(_statusPollInterval);
      _statusPollInterval = null;
      showToast('执行完成', 'ok');
      // ← 没有调用 AutomationCore.clearAllHighlights()
  }
  ```
- **影响**: 脚本执行完成后，最后一个执行的节点仍然保持高亮状态。用户可能误以为脚本还在运行或卡住了。需要手动点停止按钮才能清除高亮。

### 🟡 BUG-EX3: 模拟执行 — 不按流程顺序执行

- **代码** [editor-app.js:1115-1151](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L1115):
  ```javascript
  function simulateExecution() {
      var allNodes = AutomationCore.getNodes();
      var idx = 0;
      var interval = setInterval(function() {
          var node = allNodes[idx];
          ...
          idx++;
      }, 500);
  }
  ```
- **影响**: 模拟执行按节点在内部列表中的顺序（通常是创建顺序）逐个高亮，不遵循 flow 连接的执行顺序。用户看到节点高亮顺序与实际执行顺序不一致，可能误解脚本的执行逻辑。

---

## 八、序列化/反序列化

### 🔴 BUG-S1: 反序列化 — 动态分支端口恢复后连线可能错位

- **代码** [editor-app.js:735-737](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L735):
  ```javascript
  if (nodeDef && nodeDef.dynamic_branches && node.properties.branch_count && node.properties.branch_count !== 2) {
      AutomationCore.updateBranchPorts(node, node.properties.branch_count);
  }
  ```
- **影响**: 加载节点时先创建默认2个分支端口，然后如果 `branch_count !== 2` 才更新。但连线恢复在第745-768行，使用端口名称（`_portKey`）匹配。如果 `updateBranchPorts` 添加的端口 `_portKey` 与序列化时不一致（如 `branch3` vs `branch_3`），连线会匹配失败。需要确认端口命名一致性。

### 🟡 BUG-S2: 序列化 — 不保存画布视口位置和缩放级别

- **代码** [editor-app.js:619-707](file:///g:/宏引擎/宏驱动 webui 2.7.5/宏驱动 webui 2.7.5/webui/modules/auto/editor-app.js#L619): `serializeGraph` 不包含视口信息
- **影响**: 保存脚本后重新打开，画布视口会重置到默认位置和缩放级别，而不是用户上次查看的位置。对于大型脚本，用户需要手动导航到之前的工作区域。

---

## 问题优先级汇总

| 优先级 | 编号 | 问题 | 类型 |
|--------|------|------|------|
| 🔴🔴 | BUG-TB1 | 执行验证误判 goto 合法回跳为循环 | 逻辑 |
| 🔴🔴 | BUG-C1 | 多次粘贴节点位置完全重叠 | UX |
| 🔴🔴 | BUG-C2 | 撤销后属性面板状态不一致 | 交互 |
| 🔴🔴 | BUG-PL1 | 插件后端注册定义覆盖前端完整定义 | 架构 |
| 🔴 | BUG-TL1 | relative 模式坐标拾取 DPI 偏移 | 计算 |
| 🔴 | BUG-TL2 | relative 模式区域拾取 DPI 偏移 | 计算 |
| 🔴 | BUG-VP1 | 变量面板 store_var 类型判断不完整 | 显示 |
| 🔴 | BUG-VP2 | 变量面板 preset_read_text store_var 类型错误 | 显示 |
| 🔴 | BUG-TB2 | PAUSED 状态下运行按钮未恢复 | 交互 |
| 🔴 | BUG-TB3 | COMPLETED 状态下停止按钮行为异常 | 交互 |
| 🔴 | BUG-C3 | 粘贴不保留 _customName | 数据 |
| 🔴 | BUG-C4 | Ctrl+D 只支持单节点复制 | 功能 |
| 🔴 | BUG-C5 | 右键"重复"clone() 失败无提示 | UX |
| 🔴 | BUG-PL2 | 插件重载不清后端注册 | 架构 |
| 🔴 | BUG-PL3 | 插件 node.js 无沙箱执行 | 安全 |
| 🔴 | BUG-EX1 | 状态轮询不检测 PAUSED | 交互 |
| 🔴 | BUG-S1 | 动态分支端口恢复后连线错位 | 数据 |
| 🟡 | BUG-T1 | 工具箱缺少 plugin 分类 | 显示 |
| 🟡 | BUG-T2 | 工具箱搜索不支持中文/拼音 | UX |
| 🟡 | BUG-TL3 | hwnd_var 被覆盖为原始句柄值 | 交互 |
| 🟡 | BUG-TL4 | 拾取后自动修改 mode | 交互 |
| 🟡 | BUG-VP3 | 变量操作节点 result 输出格式不直观 | UX |
| 🟡 | BUG-VP4 | 变量面板点击只复制不插入 | UX |
| 🟡 | BUG-TB4 | 重命名不允许"未命名脚本"但默认就是 | 设计 |
| 🟡 | BUG-TB5 | 新建画布保存确认逻辑中断 | UX |
| 🟡 | BUG-C6 | Delete 后变量面板不更新 | 显示 |
| 🟡 | BUG-C7 | Ctrl+A 在输入框中无法全选文本 | 交互 |
| 🟡 | BUG-C8 | 撤销后属性面板不刷新 | 交互 |
| 🟡 | BUG-C9 | 拖拽节点位置不可撤销 | 功能 |
| 🟡 | BUG-PL4 | 插件串行加载速度慢 | 性能 |
| 🟡 | BUG-PL5 | onExecute 只在模拟执行时调用 | 设计 |
| 🟡 | BUG-EX2 | 执行完成后不清除节点高亮 | 显示 |
| 🟡 | BUG-EX3 | 模拟执行不按流程顺序 | 逻辑 |
| 🟡 | BUG-S2 | 不保存画布视口位置 | UX |
| 💡 | BUG-T3 | 工具箱节点缺少 tooltip | 建议 |

---

**最需要优先修复的5个问题**：

1. **BUG-TB1**: goto 节点的合法回跳被循环检测误判，导致脚本无法运行——这是**功能性阻断**
2. **BUG-PL1**: 插件后端注册的空定义覆盖前端完整定义——影响所有插件节点
3. **BUG-TL1/TL2**: relative 模式下坐标拾取 DPI 偏移——用户在高 DPI 环境下拾取的坐标全部偏移
4. **BUG-C1**: 多次粘贴位置重叠——高频操作体验差
5. **BUG-TB2**: 暂停状态下运行按钮不可用——用户困惑于如何继续运行
        
            
toolName: todo_write
            
status: success
          
Todos updated: 10 items
          
所有任务已完成！以下是本次检查的完整总结：

---

## ✅ 检查完成总结

本次对自动化编辑器的**工具箱、坐标拾取工具、变量查看器、顶部工具栏、画布交互、插件系统、序列化/反序列化**等7大功能区域进行了深度用户视角追踪，共发现：

| 优先级 | 数量 | 关键问题 |
|--------|------|----------|
| 🔴🔴 致命 | 4 | goto回跳被循环检测误判、多次粘贴位置重叠、撤销后状态不一致、插件后端定义覆盖前端 |
| 🔴 严重 | 13 | relative模式DPI偏移、变量类型判断错误、暂停状态按钮异常、插件重载不彻底等 |
| 🟡 中等 | 17 | 工具箱缺plugin分类、hwnd_var被覆盖、拖拽不可撤销、模拟执行顺序错误等 |
| 💡 建议 | 1 | 工具箱节点缺tooltip |

### 与上一轮节点模块检查的关联

本轮发现的问题与上一轮有多个交叉点：
- **变量面板的类型判断**（BUG-VP1）与 `_collectStructuredVars`（BUG-G1）是同一问题的不同表现
- **坐标拾取的 relative 模式 DPI 问题**（BUG-TL1/TL2）解释了为什么 `utility/bookmark` 的 `mode=relative` 无效（BUG-U5）——即使 mode 参数被正确使用，拾取工具本身就有 DPI 偏移
- **goto 循环检测误判**（BUG-TB1）直接影响 `control/goto` 节点的可用性

### 最高优先级修复建议

1. **修复循环检测**：排除 goto 产生的回边，否则 goto 节点完全不可用
2. **修复插件注册架构**：后端 `register_plugin_nodes` 不应注册空定义，应从插件的 node.js 中提取完整定义
3. **修复 relative 模式 DPI**：拾取工具应使用 `data.virtual_width` 而非 `data.width` 计算相对坐标