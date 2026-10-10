# 更新日志

所有项目更新都会记录在此文件中。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范。

---

## [未发布]

> 详见 `docs/防跳秒与窗口选择修复说明.md`、`docs/真DXGI与绑核顶栏修复说明.md`

### 变更（测试点入口改版：只保留「点行号」一个入口）

- **删除**动作行左侧原本单独占一列的 `action-bp`（○/●）按钮。它每行都占位、
  又只有顶层行可用，视觉噪声大而功能冷门。
- **唯一入口 = 点行号**：`action-index` 直接承担测试点开关——
  - 未标记：普通行号外观（零噪声）；
  - 已标记：数字**浅橘黄底 + 深色字**，一眼看出哪些行是测试点；
  - 点击行号即**立即**切换（仅顶层动作行可点，子行行号不可点）。
- 双击展开的内联编辑面板**不再有**「设为测试点」按钮，「注释动作 / 恢复动作」按钮
  回到面板右下角原位（`inline-editor.js`）。
- **修复：点击行号后高亮不实时刷新**。原因是 `action-list-render.js` 用
  `export { updateBpVisual } from './bp-visual.js'` 再导出，这只建立"再导出"而
  **不产生本地绑定**，点击回调里调用 `updateBpVisual(...)` 会抛
  `ReferenceError: updateBpVisual is not defined`，异常又打断了后续重绘，
  所以只有重载宏 / 双击（触发整表重建）才看起来"同步上了"。
  现改为顶部 `import { updateBpVisual } from './bp-visual.js'` + `export { updateBpVisual }`。
- **高亮配色改用独立的 `--bp-*` 变量，不再复用 `--warn`**（`--warn` 在亮色主题下是深棕
  `#9a6700`，当背景块很难看）：
  - 暗色主题：`--bp-bg: rgba(255,190,85,.85)` 浅橘黄底 + `--bp-fg: #2a1c06` 近黑字；
  - 亮色主题：`--bp-bg: #ffe0b0` 浅橘黄底 + `--bp-fg: #7a4a00` 深棕字。
- **修复：暗色主题下已标记行号 hover 变透明导致看不清**。原先 hover 规则把背景改成
  近乎透明的 `rgba(255,190,85,.35)`，与深色背景糊在一起；现在已标记项的 hover
  改为**加深**（`--bp-bg-hover`），文字色保持深色，任何状态下都清晰。
- 动作列表网格由 `18px 30px 1fr` 收为 `30px 1fr`，右侧动作文本可视宽度增加。
- 测试点标记仍归属**文档（标签页）**，不改文件内容、不影响脏标记。

### 新增（T1-4 测试点：从测试点运行到下一个测试点）

- 每个顶层动作行左侧可点出**测试点**（●）；标记归属**文档（标签页）**，切换小窗不丢。
  默认不可见，行 hover / 选中时才显现，避免每行都是 ○ 的噪声。
- 新增工具栏按钮 **「测试点运行」**：从"当前选中行所在/之后的第一个测试点"执行到
  "下一个测试点"（没有则到末尾）。
- 后端新增 `run_macro_slice(rel_path, from_index, to_index)`（`macro_io/parser.py`）：
  切出顶层行 → 写到**源文件同目录**的临时宏（保证 `import` 相对路径可解析）→ 交给
  `宏执行框架3.2.py::run_macro_file_once()` 执行 → **加载/编译完成后立即删除临时文件**。
  执行线程注册进 `active_macros`，因此**「停止全部宏 / 全局暂停」对测试运行同样有效**。
- `_list_macro_files` 跳过 `.`/`__` 开头的文件，测试临时宏不会出现在宏列表里。

### 新增（T2-2 ext 指令描述符 + 通用可视化表单）

- `宏执行框架3.2.py` 新增 `EXT_COMMAND_SPECS` / `register_ext_command(spec)` / `list_ext_commands()`；
  `register_ext_handler(name, handler, spec=None)` 支持同时声明描述符。
- **描述符与处理器分离**：插件可只声明描述符（计划中/尚未安装），界面照样能编辑。
- 内置 `ext.echo`（仅打印参数、无副作用）用于**验证 ext 通道**；
  另外注册了 `fps.lock` / `net.set` / `frame.sim` 的**仅描述符**（`planned: true`，`has_handler: false`）。
- 前端新增 `webui/modules/editor/ext-commands.js`：**一份渲染器**驱动所有 ext 指令的参数表单
  （类型 `string / number / bool / enum / slider`）；插件新增指令**无需改前端**。
  动作插入器选 `ext` 时：指令名变成下拉框 + 参数按描述符生成；无描述符时回退为原始参数输入框。

### 新增（T2-3 插件 ext 注册钩子）

- `PluginManager.apply_ext_hooks()`：
  - `manifest.json` 可选 `"ext_commands": [ {描述符} ]` → 只声明描述符；
  - `backend.py` 可选 `def register_ext(api)` → `api.register_handler(name, handler, spec=None)` /
    `api.register_command(spec)`。
  - 可重复调用（幂等）；旧引擎尚未就绪时静默跳过，由 `list_ext_commands` 在引擎就绪后补做。
- 新增桥接 API `list_ext_commands()`（`bridge/plugin_api.py`）。

### 新增（无头截图自检修复 + 诊断开关）

- `tools/shot.sh` **每次使用全新的 Chrome profile**：此前复用 profile 会命中 **HTTP 缓存**，
  截到旧 ES 模块代码（表现为"改动没生效"），排查成本很高。
- `index.html` 新增诊断开关 `?p_diag=1`：把未捕获错误写进 `<title>`，配合 `--dump-dom` 可直接读出
  （本轮就是靠它定位到"模块未导出 `refreshExtForm`"其实是缓存问题）。
- `ext-commands.js` 在加载失败时**不再清空已有缓存**，避免静态预览灌入的描述符被异步失败覆盖。

### 新增（文档）

- `docs/standby长尾优化开关速查.md`：把散落在长文里的实测结论整理成速查表 ——
  **PRIORITY / TIMER 是收益项；MMCSS 单独开在长间隔下 +679% 灾难性劣化，必须与 PRIORITY 同开关**；
  已拒绝的进程 affinity / 2-worker rescue 一并列出。
- `docs/后续高难项说明-T3.md`：T3-2 / T3-4 / T3-5 / T3-6 的「是什么 / 怎么实现 / 有什么用 / 影响与风险」，
  含建议实施顺序与"会不会劣化项目"的判断。
- `docs/交接文档.md`：项目定位、本轮改动、**必须知道的 7 条约定与坑**、自检方法、待办、文件索引。
- `bridge/metadata.py`：`STANDBY_PS_*` 四个开关的提示补上实测数字与 MMCSS 配对警告。

### 新增（无头 Chrome 截图自检 —— 不再需要人工逐条核对）

- 新增 `tools/shot.sh`：用本机 Chrome 的 `--headless=new --screenshot` 对 WebUI 截图，
  无需 pywebview、无需人工核对。用法：`bash tools/shot.sh "<url>" "<out.png>" [w] [h] [budget]`。
- 静态预览新增 **URL 预设参数**（仅无后端时生效）：
  `?p_tab=editor|macro|...`、`?p_panes=1..3`、`?p_sidebar=collapsed`、`?p_topbar=collapsed`、
  `?p_op=reorder-last-first|insert-front|insert-mid`（用于自检小窗排序/插入位置）。
  带 `p_*` 参数时不再弹"静态预览"提示，截图更干净。
- 自检样张输出到 `artifacts/preview/`（如 `12_editor_3panes_h.png`、`14_reorder_last_first.png`）。

### 修复（动作编辑小窗高度 / 滚动）

- **小窗原先会被内容撑开（选中宏后整份宏被"全部打开"）**：`.editor-pane` 固定 `min-height: 260px`
  而 `.editor-panes` 只设了 `max-height`，内容短则塌、长则把整页拉长。
  现改为 `.editor-panes { height: calc(100vh - 245px); }`，小窗按视口高度撑开，
  **每个小窗各自独立滚动条**（`.editor-pane .action-list` 覆盖 `.list` 的 max-height 并自带细滚动条样式）。

### 修复（折叠态 brand-mark 尺寸不一致）

- 折叠侧栏时 `brand-mark` 由 32×32 调整为 **40×40 / 圆角 11px**，与折叠后的 tab 快捷按钮**同高同圆角**。

### 新增（小窗排列：拖动标题栏换位 + 按落点插入新窗）

- **拖动小窗标题栏**即可调整小窗排列位置（`computePaneInsertIndex` 按鼠标横坐标落在哪个窗的左/右半区判定），
  拖动中有 `.dragging` 半透明与 `.reorder-target` 目标高亮。
- **把标签拖到小窗区域新建小窗时，按落点决定新窗位置**（不再一律追加到末尾）。
- 小窗标题栏 `cursor: grab`，`×` 关闭按钮不参与拖动。

### 修复（编辑器批量问题 —— 根因多为"点击后整表重建"）

- **控制台 `action-list-render.js: e.target.closest is not a function`**：拖拽类事件的 `e.target`
  可能是**文本节点**（Chrome 会把拖拽起点报成文字节点）。新增 `elFrom(target)` 统一取最近 `Element`，
  所有 `closest` 调用改走它。
- **双击快捷编辑 / 展开 import / 行内原文编辑全部失效**：点击处理器每次都 `renderViewList()` **整表重建**，
  导致双击的第二次点击落在**新 DOM** 上，`dblclick` 根本不会触发（重命名同理）。
  现在点击只做**就地高亮**（`updateSelectionHighlight`）与**就地收起内联编辑器**
  （`removeInlineEditorInPlace`），不再重建 DOM；`dblclick` 恢复正常。
- **选中动作没有高亮**：高亮规则是 `.list li.active`，而新建小窗的 `<ul>` 只给了 `action-list`、
  **漏了 `list` 类** → 高亮与 hover 都不生效。已补上 `list` 类。
- **双击标签重命名未生效**：除上面的重建问题外，标签点击也会重建标签栏。
  现在 `activateTab` 只做**就地高亮** `syncTabBarActive()`；重命名改为**事件委托**绑定在
  `#editorTabBar` 上（标签栏重建后依然有效）。

### 修复（跨小窗拖拽的落点）

- 原先跨窗格拖拽一律 `view.rows.push(...)`（**只能落到最底部**）。现在按**鼠标所在动作行**计算落点
  （`getDropTargetFromLine`），与同窗拖拽一致，支持插入到指定位置/循环体内；
  并同时高亮目标窗格与目标行，给出落点反馈。

### 调整（小窗行为按需改版）

- **默认只有 1 个小窗**，且**默认不打开任何标签**（标签栏为空时给出提示）。
- 打开/点击标签 → 装入**当前聚焦小窗**（替换其内容），不再自动增加小窗。
- **新增小窗**改为：把**标签页拖到小窗区域**（`card card-panes`）即可新建，最多 3 个。
- **小窗可关闭**：标题栏右侧 `×`（与标题同行）；关掉最后一个会自动补一个空小窗，
  该窗上的标签仍保留在标签栏中，可再次点开或拖出。

### 修复（折叠功能失效 —— 顶栏与侧栏都点不动）

- **根因**：UI 绑定被**重复执行**。`pywebviewready` 会调用 `bootstrap()`，而 `DOMContentLoaded`
  的兜底分支也会绑定同一批按钮，于是同一按钮被 `addEventListener` **两次** →
  点一次触发两次 `classList.toggle`，等于没变（表现为"折叠失效"）。
- 新增 **幂等绑定** `bindOnce(name, fn)`（`app.js`），所有 UI 绑定统一走它，
  并用集合去重。顶栏折叠、侧栏折叠、标签、编辑器、宏绑定、参数、录制、控制台按钮全部生效一次且仅一次。

### 新增（动作编辑小窗：最多 3 个并排，可同时编辑）

- 编辑器重构为 **标签(tab，数量不限) + 小窗(view，最多 3 个)** 两层模型：
  - `state.editorTabs`：文档，持有 `rows`（内容真相源）、保存快照、脏标记；
  - `state.editorViews`：小窗，持有 DOM 与显示/选择/展开/内联编辑状态，并绑定一个 tab。
- **每个小窗内可独立编辑**（选择、loop 展开、双击内联编辑、行内原文编辑、拖拽排序），互不干扰。
- 顶部标签栏**数量不限**；点击某个标签 → 该标签内容装入**当前聚焦小窗**；
  打开新宏时优先放入空窗/新建窗，超过 3 个后替换当前小窗内容。
- **跨小窗拖拽**动作（拖到另一个小窗即搬过去）；聚焦小窗高亮边框；小窗标题显示宏名与未保存 ●。
- 左侧「文件操作 / 动作插入器」与「重新加载 / 保存」作用于**当前聚焦小窗 / 当前标签**。
- 编辑器各子模块（`action-ops` / `action-list-render` / `inline-editor` / `comment-ops`）
  已改为**按视图实例**调用，为并排多窗提供支撑。

### 修复（编辑器报 "Uncaught Error: 未知动作类型"）

- `buildActionFromInputs` 原对未知类型直接 `throw new Error('未知动作类型')`。
  现在**未知类型不再抛错**，而是落为**原文行**（`{__raw: 文本}`），可直接编辑、保存原样写回。
- `fillActionEditorByAction`：遇到未识别指令/原文行时，表单自动切到新增的
  **`custom（自定义原文）`** 类型并回填原文，不再让表单与列表脱节。

### 新增（"自定义"原文行插入 —— 宏编辑器与"调用宏"节点动作编辑器一致）

- 动作类型下拉新增 **`custom（自定义原文）`**：插入后可填任意原始内容——
  合法 JSON 数组则结构化为指令（如 `["ext","fps.lock",30]`），否则原样保留为原文行。
- **"调用宏"节点动作编辑器（`block-editor.js`）逻辑对齐宏编辑器**：
  - 新增 `ext`、`custom` 两种指令，并把 `isRawRow` 判定、`kindOf`、`defaultRow`、
    `_changeKind`、参数渲染全部对齐（原先遇到 `{__raw}` 行会因 `kindOf` 取 `row[0]` 而**退化成一个 wait 行**，内容被污染）；
  - 未识别指令仍保留"原始 JSON"输入框，可直接改写。

### 修复（"宽度调整"占版面）

- 分栏改为**更窄**：拖拽条 6px → 4px，列间距 12px → 6px，
  右侧动作区默认占比提高（`minmax(400px,1.3fr)`），两张卡片更紧凑。

### 新增（附加宏指令 ext —— 命名空间隔离的内联扩展点）

- **新增 `ext` 附加指令语法**：`["ext", "<域>.<动作>", <参数...>]`。用于把"内核不负责、由插件或
  外部工具执行"的动作（帧率切换 / 联网状态 / 帧数模拟…）以内联文本指令写进同一份宏文件。
- **`宏执行框架3.2.py` 新增扩展点**：`register_ext_handler(name, handler)` /
  `unregister_ext_handler` / `list_ext_handlers()` + 模块级 `EXT_HANDLERS` 注册表。
  `compile_macro` 增加 `ext` 分支：命中注册表即执行，未注册则**告警并跳过**（不再静默）。
- **不影响核心时间线（关键约束）**：ext 动作延时恒为 `0.0`，且**不参与随机延迟修正
  （`calc_adjusted_delay_seconds`）与误差补偿**（PI / 前馈控制器对 `ext` 直接返回 0），
  因此插入任意条 ext 都不会位移 `kd/ku/md/mu` 等核心动作的时间线。
- **不再静默丢弃未知指令**：`compile_macro` 遇到完全无法识别的指令会告警一次
  （原文由 parser 层保留，可在编辑器修复）。

### 新增（未识别行"原文保留"，杜绝保存丢数据）

- `macro_io/parser.py`：`load_macro_rows_with_notes` 对**解析失败**或**顶层非数组**的行，
  不再 `continue` 丢弃，改为保留 `{"__raw": "<原文>"}`；`save_macro_rows_with_notes`
  原样写回（自动去掉原文残留的行尾逗号后统一补逗号）。往返一致，内容不丢。
- 前端 `action-model.js` 新增 `isRawRow` / `makeRawRow`；`normalizeMacroRows` 不再过滤掉原文行；
  `formatActionLabel` 对原文行显示"⚠ 原文（未识别）：…"。
- 前端 `inline-editor.js` 新增原文行编辑器：双击未识别行 → 直接编辑原始文本 → 应用修改。

### 新增（宏编辑页多标签 + 可拖拽分栏）

- **多标签（最多 3 个）**：从宏文件夹点击文件即在新标签打开（已打开则激活）。支持切换、关闭
  （有未保存修改会二次确认）、**双击标签名重命名（改文件名，走 `rename_macro`）**、
  **跨标签拖拽动作**、未保存脏标记（●）。
  存储：`state.editorTabs` / `activeEditorTabId`。活动标签的 `rows` 与 `state.editorRows`
  是**同一引用**，其余编辑模块无需改动。
- **重新加载 / 保存仅作用于当前活动标签**（原为全局唯一文档）。
- **节点编辑按钮改按活动标签**：新建→新标签打开；删除/移动/重命名→作用当前标签并同步标签栏。
- **可拖拽分栏**：新增 `webui/modules/layout-resize.js`，在宏编辑页 2 列网格中间插入竖直拖拽条，
  拖动时左右卡片联动收缩，比例持久化到 localStorage，双击拖拽条恢复默认。

### 修复（"调用宏"节点动作编辑器读取失败 —— 能存不能读）

- **根因**：`block-editor.js` 检查 `res.data.rows`，而 `read_macro` 返回的是**扁平结构**
  `{ok, path, rows}`（`core/response.ok`），`res.data` 恒为 `undefined` → 被判为"读取失败：未知错误"；
  保存只校验 `res.ok` 故一直正常。已改为读取 `res.rows`。

### 修复（宏编辑器动作类型补全）

- 宏编辑页 `#actionType` 与 `ACTION_FORM_DEFAULTS/UI` **原先缺失 `move_to` 与 `scroll`**
  （这两类动作只能以原始 JSON 显示、无法可视化编辑）。现补全：
  `move_to` → 目标坐标(X,Y) + 时长；`scroll` → 滚动量。`normalizeAction` / `formatActionLabel` /
  内联编辑器同步适配。
- 新增 `ext（附加指令）` 动作类型与参数编辑（参数支持空格分隔或 JSON 数组）。

### 新增（侧栏折叠 + 图标化快捷按钮）

- **点击 `brand-mark` 折叠/展开左侧 sidebar**（状态持久化到 localStorage）。
- 折叠后各 **tab 按钮**与 **sidebar-foot 按钮**收窄为**小型快捷按钮**（仅图标），
  保留原有 `.active` / `primary` / `pause-active` 等状态配色，功能照常可用；`brand-mark` 同步缩小。
- 为 8 个 tab 与 3 个底部功能按钮设计**内置 SVG 图标**（不依赖 FontAwesome CDN，
  离线可用；原本 `index.html` 引用的 `fa-solid` 图标类实际未加载任何图标资源）。
- `dashboard.js` / `macro-bind.js` 改为更新按钮内 `.btn-label` 文本，避免 `textContent`
  覆盖掉图标。

### 修复（顶栏折叠态仍偏高）

- `.topbar.collapsed` 由 `padding:4px 36px 4px 10px; min-height:30px` 收紧为
  `padding:0 28px 0 8px; min-height:18px`，折叠按钮同步缩小（22→18px）。

### 修复（自动化节点 `target_task` 下拉误导）

- `target_task` 的 `nodeRef` 原先同时列出 `调用宏(异步)` 与**同步阻塞**的 `执行子脚本`，
  但后者不注册进 `TaskPool`，`停止/暂停指定任务` 对其无效。现仅保留
  `script_block/call_script_async`。

### 新增回归测试

- `automation/tests/test_ext_and_raw_rows.py` —— 原文行保留与往返、ext 注册/未注册/零延时。
  运行：`python -m automation.tests.test_ext_and_raw_rows`

### 新增（静态预览）

- 无 pywebview 环境时（例如直接用浏览器打开 `webui/index.html`）也会绑定纯前端交互
  （侧栏折叠、顶栏折叠、标签栏、分栏拖拽）并以示例标签填充编辑页，便于纯 UI 预览与设计评审。

### 新增（真 DXGI 截图 —— 不再依赖 comtypes 的 type library）

- **新增 `automation/detection/dxgi_duplication.py`**：用**纯 ctypes 按虚表调用**实现真正的
  DXGI Desktop Duplication（`CreateDXGIFactory1 → EnumAdapters1 → EnumOutputs →
  QI(IDXGIOutput1) → DuplicateOutput`；`D3D11CreateDevice → CreateTexture2D(staging)`；
  `AcquireNextFrame → QI(ID3D11Texture2D) → CopyResource → Map/Unmap → ReleaseFrame`）。
  DXGI/D3D11 的 type library 不属于标准 Windows 组件，comtypes 路线必然拿到
  `TYPE_E_CANTLOADLIBRARY`，因此此前"DXGI 截图源"实际一直是**每帧一次全屏 BitBlt**
  （窗口化可用，独占全屏只能取到黑屏）。现在无需任何 type library。
- **启动自检**：`_selftest_pipeline()` 用一张已知图案的小纹理实测
  「建纹理 → CopyResource → Map 读回」整条通路，只有内容能正确搬回才启用原生 DXGI ——
  避免"DuplicateOutput 成功、取帧也返回 S_OK 但帧恒为全零（画面全黑）"的机器上
  让所有检测节点看到全黑画面（那比回退 BitBlt 更糟）。不通过则打印明确警告并回退 BitBlt。
- 设备改为**绑定到拥有该输出的适配器**（`pAdapter` + `DriverType=UNKNOWN`）：混合显卡下
  用默认适配器会出现 `DuplicateOutput` 成功但 `AcquireNextFrame` 永远超时。
- `automation/detection/dxgi_capture.py`：comtypes 不可用时先尝试原生 DXGI，再退 BitBlt。

### 修复（宏绑核 `OverflowError: int too long to convert`）

- **根因**：`GetCurrentThread` 被声明为 `restype=HANDLE`（返回 64 位 `0xFFFF...FFFE`），
  而 `SetThreadAffinityMask` **没有声明 argtypes**，ctypes 按 32 位 int 传参 →
  `argument 1: OverflowError`。即使不报错，句柄被截断后该调用也会返回 0 失败，
  而旧代码不检查返回值，日志照样打印"→ CPU n"——**绑核一直是坏的**。
- 补声明 `SetThreadAffinityMask` / `GetProcessAffinityMask`（`DWORD_PTR` 用 `c_size_t`）。
- `set_thread_affinity()` 改为**返回 bool**：索引非法 / 不在进程允许的核集合内 / 系统调用失败
  → `False`（同一警告只打印一次），调用方据此区分"已绑核 / 绑定失败"。
- `clear_thread_affinity()` 改为恢复**进程亲和掩码**，而不是 `(1<<cpu_count)-1`。

### 修复（浅色主题顶栏状态条布局）

- `.status-grid` 从固定 `repeat(4, …)` 网格改为 `flex + wrap`：**窗口够宽一行放 6 枚状态块，
  变窄自动折行**（原来固定 4 列、6 块必然折两行且不随窗口变化）。
- `.pill` 改单行胶囊（标签 11px + 数值 13px、内边距 4px 11px）：顶栏高度约 140px → **约 43px**。
- 顶栏右侧留出 36px 给折叠按钮（原按钮会压在最后一枚状态块上）；折叠按钮垂直居中，
  折叠态加 `min-height` 避免退化成几像素细条。

### 修复（插件「防跳秒」常见不触发 —— 根因：坐标退化）

- **失效窗口句柄 / 窗口最小化会让检测区域变成零面积。** `mode=relative` 时，
  `hwnd` 失效（游戏重启后变量里残留旧句柄）→ `GetClientRect` 返回 `(0,0,0,0)`；
  窗口最小化 → `ClientToScreen` 返回 `(-32000,-32000)`。换算后黑屏/亮屏/点击区域**全部为
  零面积**：黑屏/亮屏检测恒为 `False`，点击区域 `rx<=mx<=rx+rw` 恒不成立 —— 表现为
  **插件完全不触发且无任何日志**（外置脚本用屏幕绝对坐标，故不受影响）。
- 现在 `_resolve_region()` 做三级兜底：正常解析 → 退化时按**屏幕尺寸**换算（等价外置脚本
  绝对方案）→ 仍不可用则把框选值当**屏幕绝对像素**（兼容"切换模式后未重新框选"）；
  全部失败时**立即报错返回**，不再静默空转。句柄另经 `IsWindow` + `IsIconic` 校验。
- 已排除"坐标偏"与"全屏截图 vs 区域截图"两种猜测：实测两者内容一致（差异仅来自画面变化）。

### 修复（亮屏检测超时 / 恢复帧率）

- 亮屏超时补发 RTSS 恢复键**原本已有**；本次强化为：截图通道连续失败（≈0.5s）时
  **立即按超时处理并恢复帧率**（原先最多白等满 `bright_timeout`，期间游戏一直锁帧）。
- 统一恢复路径：亮屏确认 / 亮屏超时 / 截图失效 / 停止 / 异常，**每一次锁帧都必有一次恢复**。

### 修复（DXGI / 截图源）

- **真 Desktop Duplication 不可用时不再含糊**：`comtypes.gen` 缺 `DXGI`/`D3D11`、
  `GetModule` 报 `TYPE_E_CANTLOADLIBRARY` 时会退化为"全屏 BitBlt"（独占全屏只能取黑屏），
  现打出明确提示。新增插件参数「自带DXGI采集」（默认开）：无「截图源」节点时插件自建全屏采集，
  不再依赖"截图源是否启用"。
- **DXGI 取帧缺陷修复**：原用 `MAP_FLAG_DO_NOT_WAIT` 映射上一帧且不校验 `Map` 的 HRESULT、
  失败时不 `Unmap`，导致经常取不到新帧/拿到陈旧帧。改为阻塞 `Map` + 校验 HRESULT +
  `finally` 保证 `Unmap`（与外置脚本一致，每帧新鲜有效）。
- **回退模式限速**：实测全屏 BitBlt ≈19ms/帧，回退模式下按默认 60fps 会占用 >100% 单核，
  现把回退模式运行帧率上限压到 20fps（不改变用户请求值，避免反复重启采集）。

### 修复（「选择窗口」提示「未找到可见窗口」）

- 后端枚举实测正常（17~18 个窗口，<1ms），失败面在调用链异常/序列化/时序。加固
  `get_window_list`：回调所有分支 `return True`、句柄改用 `c_void_p`（避免 32 位截断）、
  清洗标题中的孤立代理字符（避免 `json.dumps` 抛错导致整个接口失败）、结果为空时放宽重试一次。
- 前端 `browseWindowList` / `browseWindowTitle`：失败或为空时**自动重试 2 次（150ms）**
  （等价把用户"点开别的窗口再点回来"的绕行办法自动化），仍失败则弹出**手动填写句柄/标题**兜底。

### 新增回归测试

- `plugins/anti_jump/test_backend.py` —— 坐标退化兜底 +「每一次锁帧必有对应恢复」六个流程场景。
  运行：`python plugins/anti_jump/test_backend.py`

---

## [v3.3.2] - 2026-10-05

### 新增

- **宽松 JSON 解析器 `lenient_json.py`** —— 容忍宏文件里 `//` `/* */` 注释、
  **动作结尾多余的逗号**、**两条动作之间漏写的逗号**（含 loop 内最后一条子动作）。
  只覆盖 JSON 子集（数组/对象/字符串/数字/布尔/null），合法 JSON 的解析结果与标准解析完全一致。

### 修复（宏加载/编辑的逗号兼容）

- **宏执行**：`load_macro_recursive` 原用 `remove_comments + json.loads`，用户手工编辑
  产生的"结尾多逗号 / 少逗号"会让整份宏加载失败。改为宽松解析。
- **宏编辑器读取**：`macro_io.parser._tokenize_macro_top_level` 在两条动作之间漏写逗号时
  会把相邻动作**合并成一个 token**（随后解析失败被静默丢弃）。改为"顶层值配对闭合即结束本 token"，
  并改用宽松解析；注释仍按原有行为保留为 `note` 行。读写 round-trip 稳定。
- **导入/导出**：`macro_converter._load_json_with_comments` / `_parse_jsonc_str` /
  格式探测探针均改用宽松解析。
- **轨迹化简工具**：`recorder.simplify_tool.load_macro` 改用宽松解析。

### 修复（"调用宏"节点的动作编辑模块）

- 旧 `AutomationBlockEditor` 读写的是 `node.properties.actions` —— 该属性既不在节点定义里，
  执行器也**从不读取**（执行读的是 `path` 指向的宏文件），因此永远是空列表；
  且其指令集（`left_click` / `key_press` …）与**真实宏指令**（`kd`/`ku`/`md`/`mu`/`view`/
  `move_to`/`scroll`/`wait`/`loop`/`import`/`note`）完全不一致。
- 现已重写：**直接读取/写回节点 `path` 指向的 .json 宏文件**（`read_macro` / `save_macro`），
  使用真实宏指令集做可视化增删改与排序，支持 **loop 嵌套子动作**、毫秒/帧延迟（`2f`）、
  按键名补全、注释(note)编辑；保存后写回宏文件（脚本编译缓存按 mtime 失效，立即生效）。

### 说明（"调用宏(异步)"随流程图结束而终止 —— 属既定设计，未修改）

- 反馈过"异步节点不执行宏"。核查后确认：这是**流程到达结束节点即终止全部**的既定设计
  （`flow/end` 会 `stop_event.set()` + `task_pool.stop_all()`，`execute_graph` 收尾同样 `stop_all()`），
  节点本身执行正常。**曾按"缺陷"改动过该逻辑（结束节点不再停任务 + 收尾等待异步完成），已回退**，
  保持原设计不变。
- 因此：若流程图在启动异步宏后很快走到结束节点，后台异步宏会被立即终止 —— 这是预期行为。
  如需异步宏真正跑完，流程图应在异步宏执行期间保持运行（例如用「条件循环 / 等待条件」占住主流程，
  或用「动作控制 → 暂停指定任务 / 恢复指定任务」等显式控制），而不是让主流程直接走到结束。

### 新增回归测试

- `automation/tests/test_lenient_macro_json.py` —— 5 项：逗号问题容忍、合法 JSON 结果一致、
  macro_io 读取与 round-trip、化简工具读取、导入导出读取。运行：
  `python -m automation.tests.test_lenient_macro_json`

---

## [v3.3.1] - 2026-10-05

### 用户体验改造：状态机 / 序列检测（面向用户层重做）

- **`序列检测` 更名为 `多条件检测`** —— 原名暗示"按顺序检测"，实际语义是
  "所有条件同时满足才放行"（AND 门闸），名实不符是最大困惑源。现更名并在描述里写清语义。
- **状态机 `states` 改为可视化「阶段列表」编辑器** —— 不再手写 `待机→攻击→冷却`，
  改为可添加/删除/上下移动的列表；节点内仍以只读文本显示执行顺序。
- **`fail_state` 改为「失败回退阶段」下拉框** —— 从阶段列表中选择，不再手填阶段名；
  若当前值不在阶段列表中，面板直接给出橙色提示（原先会被运行时静默忽略）。
- 存储格式保持不变（仍是 `→` 连接的字符串），旧脚本、后端、图序列化完全兼容。

### 修复（状态机 / 多条件检测）

- **状态机未连接 cond 时无限死等** —— 旧实现 `cond` 为空时 `cond_val=None`，
  进入永久 sleep 轮询（表现为"卡死"）。现在明确报错并直接放行 `done`。
- **状态机 cond 为假时忙等 100% CPU** —— 旧实现在 `fail_state` 分支不 sleep，
  紧循环重跑检测节点抢 CPU（违反"不抢占游戏 CPU"约束）。现在等待类分支一律
  `precise_sleep(poll_interval)`；实测等待 0.5s 的 CPU 占用比 ≈ 6%（此前接近满载）。
- **状态机新增单阶段超时 `stage_timeout_ms`** —— 某阶段一直等不到 cond 为真时，
  可按超时=失败处理（回退/前进），避免无出口的等待。
- **状态机失败语义理顺** —— `fail_state` 留空时，cond 为假改为"停在当前阶段等待"
  （原为"失败也强制前进"，与直觉相反）；填了 `fail_state` 则回退到该阶段。
- **`fail_state` 填错不再静默** —— 名字不在阶段列表时给出告警日志（运行时）与面板提示。
- **多条件检测未接 cond 时立即 fail** —— 旧实现会白等到最大重试次数耗尽（默认约 10 秒）；
  现在立即报错走 `fail`。
- **多条件检测新增 `timeout_ms`** —— 直接以"总超时"表达最长等待，不再只能靠
  `max_retries × poll_interval` 换算。

### 参数与 UI 一致性

- 两个节点的全部参数补齐独立 `label` 与通俗 `description`（此前后端不提供 label，
  前端会退化为把 description 当 label 显示）；新增 `stage_list` / `stage_ref`
  两种参数渲染类型（`property/renderers.js`、`core/utils.js` 内联显示、
  `property/events.js` 绑定）。

### 新增回归测试

- `automation/tests/test_control_nodes.py` —— 8 项，覆盖：状态机未接 cond 不死等、
  顺序推进、等待时不忙等（CPU 占用比断言）、阶段超时、失败回退；
  多条件检测未接 cond 快速失败、全真 pass、关闭重试立即 fail、timeout_ms 生效。
  运行：`python -m automation.tests.test_control_nodes`

### 遗留（未改，供后续决策）

- `调用宏(异步)` 被"动作控制→停止指定任务"终止后，`TaskPool` worker 会把状态
  无条件覆写回 `completed`（`automation/engine.py`），导致走"完成"分支而非"中断"分支。
- `动作控制` / 监视器的 `target_task` 下拉把同步阻塞的 `执行子脚本` 也列为可选项，
  但该节点不注册进 `TaskPool`，`stop_task/pause_task` 对它无效。
- ESC（旧引擎 `STOP_MACRO_KEY`）无法终止"调用宏"节点启动的子宏（两套监听互不相通）。

---

## [v3.3.0] - 2026-10-05

### 新增功能

- **精度/占用档位（Precision Profile）** — 统一入口 `PRECISION_PROFILE`，
  一键联动 15 项参数：`latency_first`(延迟优先) / `balanced`(均衡) / `cpu_saver`(低占用) / `custom`(自定义)。
  新增 `core/precision_profile.py`
- **进程优先级档位化且可恢复** — 新增 `PROCESS_PRIORITY_TIER`、`set/restore_process_priority()`，
  解决此前进程被抬到 HIGH_PRIORITY_CLASS 后永不恢复、持续抢占游戏 CPU 的问题
- **共享帧缓存** — 同一循环迭代内多个检测节点复用一次截图（实测 5 次全屏检测 91.3ms → 15.9ms）
- **热键冲突检测** — 新增 `get_hotkey_conflicts()` API，可报出 F8 三方冲突、F7/F10 双方冲突
- 新增 `automation/tests/test_engine_realtime.py` 回归测试（6 项）
- 新增 `docs/项目需求与持续开发目标.md`

### 修复（Critical）

- `goto` 循环只能执行一圈（跳转时仅重置目标节点，中间节点仍带 executed 标记）
- `goto` 循环导致递归栈随圈数线性增长，约 500 圈后 RecursionError
  改为 `_GotoSignal` 解栈 + 顶层 trampoline，2000 圈无溢出
- 检测结果默认 100ms 陈旧缓存且跨循环迭代永不失效 → 默认改为 `disabled`，循环迭代强制失效
- DXGI `_pool_desc_key` 应为 `_staging_desc_key`，导致硬件采集 100% 不可用并静默回退 BitBlt
- 前端调用不存在的 `get_node_defs`（正确名 `get_node_definitions`）→ 插件重载后节点定义永不刷新
- 保存对话框返回值取 `result[0]` → 宏导出路径变成单个字符（如 "C"）
- 配置非原子写 + 损坏时被默认值静默覆盖 → 原子替换 + 隔离 `.corrupt-*.bak` 备份
- 中止宏后普通按键与鼠标中键卡死 → 新增按下跟踪 `release_tracked_inputs()`
- `move_to` 从屏幕原点 (0,0) 插值 → 改为从当前光标位置插值（原会导致视角瞬移）

### 修复（性能 / High）

- `_execute_flow` 每次转移 O(M) 全量扫 `check_results`（死代码）→ 300 节点链 0.91ms，与规模解耦
- `_reset_body_nodes` O(M×B) 嵌套扫描 → 降为 O(M)
- 检测缓存判定移到截图之前（原先先付 13.7ms 截图再丢弃）
- `frame_diff` 固定阈值 2.0 在大区域+小目标场景永久漏检 → 改为按 ROI 面积自适应
- 分支绑核 `4 + index` 在 4/6 核机器越界 → 按实际 CPU 拓扑倒序分配
- 监视器暂停期间仍全速截图/OCR → 暂停时停止检测

### 修复（Medium）

- 分支被取消后状态被覆写为 `completed`（可导致 Join 提前放行、被取消分支"赢得" Race）
- `loop_while`/`wait_cond`/`seq_check`/`state_machine` 不响应分支取消信号
- `CaptureManager` 无锁，并发迭代会抛 `Set changed size during iteration` → 加 RLock
- OCR 缓存命中时原地修改并返回同一 dict → 返回副本

### 修复 / 完善（参数与 UI 一致性）

- **共享帧缓存对「阻塞轮询检测」的副作用** —— 持续等待（wait=true）的检测节点
  以及监视器，此前可能连续命中同一帧导致"实时检测"退化为"盯旧画面"。
  现在轮询每轮调用 `_invalidate_frame()` 强制取新帧；共享帧缓存只服务于
  「同一轮遍历里多个检测节点复用一次截图」。新增回归用例实测：
  未作废 8 轮看到旧帧 7 次 → 每轮作废后 0 次
- **参数页枚举中文化** —— `bridge/metadata.py` 为全部枚举参数补充 `display_names`，
  参数行下发给前端，下拉框显示「延迟优先(最低延迟/占用高) (latency_first)」而非裸英文串
- **「快捷键速查」按真实配置渲染** —— 原为硬编码 F8/ESC/F6/F7/F11，
  与实际配置（编辑器运行=F1、暂停=F7、停止=F8、全屏=F10）严重不符且无视冲突。
  改为读取 `get_hotkey_conflicts().flat` 渲染，并高亮标注冲突按键
- **热键冲突检测上线 UI** —— 全局参数页新增「热键冲突检测」按钮与结果面板；
  `get_hotkey_conflicts()` 增补 `flat` 扁平绑定清单
- **顶栏常显引擎状态** —— 新增「精度档位」「Standby 引擎」两枚状态指示
  （新增 `get_engine_summary()`）。Standby 开关开着但 native 扩展未加载时会高亮告警，
  避免用户误以为在用高精度引擎
- **前端兜底节点定义对齐后端** —— `webui/modules/auto/core/nodes.js` 中
  `cache_strategy` 默认值 `time_interval` → `disabled`（3 处），
  消除静态预览/API 异常时注入陈旧缓存的隐患
- **「功能一览」补充新能力条目**（精度/占用档位、热键冲突检测）

---

## [v3.2.0] - 2026-06-28

### 新增功能

- 项目正式迁移至 GitHub 私有仓库，支持多人协同开发
- 完善项目文档与贡献指南

---

## [v2.8.0] - 2026-05-10

### 新增功能

- 启动时显示版本号、Python 版本、平台信息 Banner
- `health` API 返回完整环境信息（Python/平台/pywebview/OpenCV/NumPy/ONNX Runtime 版本）
- 额外功能页新增「快捷键速查」卡片，分类展示全局/编辑器/录制热键
- 版权信息页版本号改为从 API 动态获取
- `kbd` 标签样式支持（快捷键展示）

### 改进

- 自动化编辑器节点系统完善（8 期审查全部通过）
- 图片匹配帧差缓存策略已实现
- 编译缓存、轮询间隔可配置等待办功能已全部完成
- goto 在分支内的已知缺陷已修复
- 监视器分支中 goto 编译期警告机制已实现

---

## [v1.0.0] - 2026-04-27

### 首发版本

欢迎使用 MacroDriver WebUI！这是项目的首个正式版本。

### 新增功能

#### 核心功能

- 可视化宏编辑器 - 图形化编辑界面，支持拖拽式节点操作
- 3D 宏录制系统 - 支持按键与轨迹同步录制
- 轨迹化简工具 - Ramer-Douglas-Peucker 算法压缩轨迹
- 双输入驱动模式 - SendInput（兼容模式）与 Interception（精准模式）

#### 执行引擎

- 高精度执行 - 单宏微秒级延时控制，OCR识别毫秒级
- PI 延时补偿 - PI 控制器 + 前馈算法补偿系统延迟
- PID Boost - 执行时自动提升进程优先级
- CPU 核心绑定 - 支持绑定指定 CPU 核心执行宏

#### 用户界面

- 实时控制台 - 后端日志实时推送至 WebUI
- 热键系统 - F5 运行 / F6 暂停 / F7 停止
- 参数配置面板 - JSON 统一管理所有运行时参数
- 宏管理 - 宏的导入、导出、编辑、删除

#### 检测能力

- 图像检测 - 基于 OpenCV 的图像匹配
- 颜色检测 - 屏幕指定坐标颜色识别
- OCR 识别 - 基于 RapidOCR 的文字识别

### 技术特性

- Python 3.10+ 后端核心
- pywebview 5.1 桌面窗口框架
- 原生 JavaScript 前端（无框架依赖）
- 模块化 Mixin 架构 - 8 个功能 Mixin 便于扩展
- Interception 驱动 - 底层键盘鼠标模拟

### 包含模块

| 模块            | 说明               |
| --------------- | ------------------ |
| `bridge/`     | WebUI API 桥接层   |
| `automation/` | 宏执行引擎与编译器 |
| `engine/`     | 底层输入控制       |
| `recorder/`   | 宏录制与轨迹处理   |
| `macro_io/`   | 宏文件解析         |
| `core/`       | 公共基础服务       |

### 快速启动

1. 安装 Python 依赖：`pip install -r bin/requirements.txt`
2. 安装 Interception 驱动（管理员权限）
3. 运行：`python webui_app.py`

---

**注意**：此为 Windows 专用项目，需要 Windows 10/11 系统。
