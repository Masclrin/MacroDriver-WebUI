# MacroDriver WebUI

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-green.svg)
![Version](https://img.shields.io/badge/Version-3.2.0-orange.svg)

</div>

---

## 项目简介

**MacroDriver WebUI** 是一款基于 Python + pywebview 的本地宏驱动控制台，提供可视化宏编辑、录制、轨迹化简和精确执行功能。无需浏览器，直接运行即可在本地实现高精度键盘鼠标自动化。

### 项目亮点

1. 模块化Mixins设计 ： MacroBridge 通过多重继承组合8个功能Mixin，职责清晰，便于扩展
2. 双输入驱动兼容 ：同时支持SendInput（兼容性）和Interception（精准度）两种输入模式
3. PID Boost + 线程亲和 ：执行宏时可提升进程优先级并绑定CPU核心，确保低延时
4. 实时控制台输出 ：通过 RingConsole 和 TeeStream 实现控制台内容实时推送到Web UI
5. 单宏精度优化：WinAPI+忙等 高精度睡眠；Interception 实现内核级输入注入；宏执行延迟补偿；native standby引擎绕过python
6. 轨迹化简 ：支持Ramer-Douglas-Peucker算法对录制轨迹进行压缩
7. 配置中心化 ：通过 webui_param_config.json 统一管理所有运行时参数
8. 可视化节点编辑器 ：拖拽式自动化流程搭建，支持 Fork/Join/Race 并发控制

---

## 功能特性

- **可视化编辑器** - 图形化宏编辑界面，拖拽式节点操作
- **宏录制系统** - 3D轨迹录制，支持按键+移动同步
- **轨迹化简** - Ramer-Douglas-Peucker 算法压缩冗余轨迹点
- **双输入模式** - SendInput（兼容）与 Interception（精准）双驱动支持
- **精度优化** - PID Boost、CPU核心绑定、native standby自旋、低延时执行
- **实时控制台** - 控制台输出实时推送至 WebUI
- **热键控制** - 多热键支持宏运行/暂停/停止
- **参数配置** - 统一的 JSON 配置文件管理运行时参数
- **延时补偿** - PI控制器 + 前馈算法补偿系统延迟
- **插件系统** - 支持自定义插件扩展节点功能
- **检测能力** - 图像匹配、颜色检测、OCR文字识别
- **宏格式转换** - 支持 Razer/Logitech/AHK/XMouse 等格式互转，WebUI/通用JSON/C数组导入，帧延迟格式导出

---

## 技术栈

| 层级               | 技术                                                 | 说明              |
| ------------------ | ---------------------------------------------------- | ----------------- |
| **UI框架**   | [pywebview 5.1](https://github.com/r0x0r/pywebview)     | 桌面 WebView 窗口 |
| **前端**     | 原生 JavaScript + HTML5                              | 无框架，轻量高效  |
| **后端**     | Python 3.10+                                         | 核心业务逻辑      |
| **输入驱动** | [Interception](https://github.com/oblitum/Interception) | 底层键盘鼠标模拟  |
| **OCR识别**  | [RapidOCR](https://github.com/RapidAI/RapidOCR)         | 快速跨平台 OCR    |
| **图像处理** | OpenCV 4.9+                                          | 图像检测与处理    |

---

## 快速开始

### 环境要求

- Windows 10/11 (64-bit)
- Python 3.10+ (建议 3.12)
- 管理员权限（全局需要，否则无法安装驱动或在部分游戏中进行覆盖操作）

### 安装步骤

1. **下载并解压** 项目压缩包

2. **安装依赖**

   双击运行 `bin\安装依赖_l.bat`

   或手动安装：

   ```bash
   pip install -r bin/requirements.txt
   ```

3. **安装 Interception 驱动**（需要管理员权限）

   右键 `bin\安装驱动_管理员运行_l.bat` → 以管理员身份运行

4. **启动程序**

   双击 `start.bat`

### 启动脚本说明

| 脚本                                    | 说明                           |
| --------------------------------------- | ------------------------------ |
| `start.bat`                           | 一键启动（推荐，自动检测环境，首次运行引导） |
| `3_启动webui.bat`                     | 直接启动 WebUI（跳过环境检测） |
| `bin/1_管理员安装全部并启动WebUI.bat` | 完整安装 + 启动（管理员）      |
| `bin/安装依赖_l.bat`                  | 仅安装 Python 依赖             |
| `bin/安装驱动_管理员运行_l.bat`       | 仅安装 Interception 驱动       |
| `bin/重置Interception驱动.bat`        | 卸载并重新安装驱动             |

> 首次使用需要管理员权限运行驱动安装脚本。安装后若输入异常，请重启电脑。
> 键盘急救：运行 `bin\键盘急救修复.py`

---

## 项目架构

```
macro-driver-webui/
├── webui/                  # 前端资源（HTML/CSS/JS）
│   ├── modules/            # 模块化 JS
│   │   ├── auto/           # 可视化编辑器核心
│   │   ├── core/           # 公共工具
│   │   ├── editor/         # 编辑器 UI
│   │   └── converter.js    # 宏格式转换器前端
│   ├── index.html          # 主页面
│   └── automation_editor.html  # 自动化编辑器
├── bridge/                 # 后端 API 桥接层（8个Mixin）
│   └── converter_api.py    # 格式转换 API
├── macro_converter.py      # 多格式宏转换器（导入/导出）
├── automation/             # 宏执行引擎
│   ├── engine.py           # 执行上下文与调度
│   ├── compiler.py         # 宏编译为执行图
│   ├── registry.py         # 节点注册表
│   ├── handlers/           # 动作/控制/检测处理器
│   ├── nodes/              # 节点定义
│   └── detection/          # 图像/颜色/OCR 检测
├── engine/                 # 底层输入控制
│   ├── input_sendinput.py  # SendInput 模式
│   └── input_interception.py # Interception 模式
├── recorder/               # 宏录制与轨迹化简
├── macro_io/               # 宏文件解析
├── core/                   # 公共基础服务
├── plugins/                # 插件目录
├── bin/                    # 批处理脚本与依赖
├── Interception/           # 驱动文件
├── docs/                   # 文档
└── webui_app.py            # 应用入口
```

---

## 核心模块说明

| 模块                   | 路径                        | 功能描述                                            |
| ---------------------- | --------------------------- | --------------------------------------------------- |
| **宏执行引擎**   | `automation/engine.py`    | ExecContext 执行上下文，支持暂停/停止/变量/延时补偿 |
| **自动化编译器** | `automation/compiler.py`  | 将 JSON 执行树编译为可执行的 ExecGraph              |
| **输入驱动层**   | `engine/`                 | SendInput/Interception 双模式，支持 PID Boost       |
| **宏录制系统**   | `recorder/recorder_3d.py` | 3D 轨迹录制，支持按键+轨迹同步                      |
| **WebUI 桥接**   | `bridge/*.py`             | 8 个 Mixin 提供参数/录制/宏管理/自动化 API          |
| **插件系统**     | `core/plugin_manager.py`  | 插件扫描、加载、执行、事件推送                      |
| **宏格式转换器** | `macro_converter.py`      | 多格式宏导入解析与导出，支持帧延迟转换              |

---

## 分发与打包

### 项目大小参考

| 内容 | 大小 |
|------|------|
| 项目源码（核心） | ~2.7 MB |
| 含 Interception 驱动 | ~3.5 MB |
| 压缩包（7z/zip） | ~2-3 MB |
| PyInstaller 打包（含依赖） | ~300-400 MB |
| PyInstaller 打包压缩后 | ~150-200 MB |

### 压缩包分发（推荐）

压缩包分发体积小（~3 MB），用户需自行安装 Python 和依赖。分发时应保留以下文件/目录：

**必须保留：**
- `webui_app.py` - 应用入口
- `start.bat` - 一键启动脚本
- `3_启动webui.bat` - 直接启动脚本
- `bridge/` - 后端 API 桥接层
- `automation/` - 宏执行引擎
- `engine/` - 输入驱动
- `recorder/` - 录制系统
- `macro_io/` - 宏文件解析
- `core/` - 公共基础服务
- `plugins/` - 插件目录
- `webui/` - 前端资源
- `Interception/` - 驱动文件
- `bin/` - 批处理脚本与依赖列表
- `docs/` - 文档
- `宏执行框架3.2.py` - 旧格式宏执行引擎
- `macro_converter.py` - 宏格式转换器

**应排除：**
- `存档内容/` - 开发存档，非运行必需
- `问题/` - Bug 审查记录，非运行必需
- `图片模板/` - 自动化设计，图片，数字匹配模板
- `__pycache__/` - Python 缓存
- `.vscode/` - IDE 配置
- `webui_param_config.json` - 用户本地配置（运行时自动生成）
- `.first_run_done` - 首次运行标记（运行时自动生成）
- `宏/` - 用户数据（分发时保留空目录结构即可）
- `自动化脚本/` - 用户数据（分发时保留空目录结构即可）

### PyInstaller 打包

如需打包为独立可执行文件：

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name MacroDriver webui_app.py
```

> 注意：打包后体积约 300-400 MB（含 OpenCV、NumPy、ONNX Runtime 等依赖）。如需减小体积，可考虑排除不需要的模块或使用虚拟环境精简依赖。

---

## 贡献指南

欢迎提交 Issue 和 Pull Request！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

### Git 提交规范

遵循 **Angular 规范**：

| 类型          | 说明      | 示例                                      |
| ------------- | --------- | ----------------------------------------- |
| `feat:`     | 新功能    | `feat: 添加宏轨迹化简功能`              |
| `fix:`      | Bug 修复  | `fix: 修复 Interception 驱动兼容性问题` |
| `docs:`     | 文档更新  | `docs: 更新 README 安装说明`            |
| `style:`    | 代码格式  | `style: 格式化前端 JS 代码`             |
| `refactor:` | 重构      | `refactor: 重构自动化编译器`            |
| `perf:`     | 性能优化  | `perf: 优化延时补偿算法`                |
| `test:`     | 测试相关  | `test: 添加编译器单元测试`              |
| `chore:`    | 构建/工具 | `chore: 更新 requirements.txt`          |

---

## 主要贡献者

| 贡献者 | 角色 |
| --- | --- |
| [@Masclrin](https://github.com/Masclrin) | 项目创建者 & 核心开发者 |
| [@moudai202](https://github.com/moudai202) | 核心贡献者 |
| [@alice9716](https://github.com/alice9716) | 核心贡献者 |

---

## 许可证

本项目保留所有权利。Interception 驱动为第三方开源组件，版权归其作者所有。
