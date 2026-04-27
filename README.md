# 🎮 MacroDriver WebUI

<!-- 徽章 -->

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![pywebview](https://img.shields.io/badge/pywebview-5.1-orange.svg)

</div>

---

## 📖 项目简介

**MacroDriver WebUI** 是一款基于 Python + pywebview 的本地宏驱动控制台，提供可视化宏编辑、录制、轨迹化简和精确执行功能。无需浏览器，直接运行即可在本地实现高精度键盘鼠标自动化。

### 项目亮点

1. 模块化Mixins设计 ： MacroBridge 通过多重继承组合8个功能Mixin，职责清晰，便于扩展
2. 双输入驱动兼容 ：同时支持SendInput（兼容性）和Interception（精准度）两种输入模式
3. PID Boost + 线程亲和 ：执行宏时可提升进程优先级并绑定CPU核心，确保低延时
4. 实时控制台输出 ：通过 RingConsole 和 TeeStream 实现控制台内容实时推送到Web UI
5. 单宏精度优化：WinAPI+忙等 高精度睡眠；Interception 实现内核级输入注入；宏执行延迟补偿
6. 轨迹化简 ：支持Ramer-Douglas-Peucker算法对录制轨迹进行压缩
7. 配置中心化 ：通过 webui_param_config.json 统一管理所有运行时参数

---

## ✨ 功能特性

- 🎯 **可视化编辑器** - 图形化宏编辑界面，拖拽式节点操作
- 📝 **宏录制系统** - 3D轨迹录制，支持按键+移动同步
- ✂️ **轨迹化简** - Ramer-Douglas-Peucker 算法压缩冗余轨迹点
- ⌨️ **双输入模式** - SendInput（兼容）与 Interception（精准）双驱动支持
- ⚡ **精度优化** - PID Boost、CPU核心绑定、低延时执行
- 🎛️ **实时控制台** - 控制台输出实时推送至 WebUI
- ⌨️🎹 **热键控制** - 多热键支持宏运行/暂停/停止
- 🔧 **参数配置** - 统一的 JSON 配置文件管理运行时参数
- 📊 **延时补偿** - PI控制器 + 前馈算法补偿系统延迟

---

## 🛠️ 技术栈

| 层级               | 技术                                                 | 说明              |
| ------------------ | ---------------------------------------------------- | ----------------- |
| **UI框架**   | [pywebview 5.1](https://github.com/r0x0r/pywebview)     | 桌面 WebView 窗口 |
| **前端**     | 原生 JavaScript + HTML5                              | 无框架，轻量高效  |
| **后端**     | Python 3.10+                                         | 核心业务逻辑      |
| **输入驱动** | [Interception](https://github.com/oblitum/Interception) | 底层键盘鼠标模拟  |
| **OCR识别**  | [RapidOCR](https://github.com/RapidAI/RapidOCR)         | 快速跨平台 OCR    |
| **图像处理** | OpenCV 4.9                                           | 图像检测与处理    |

---

## 🚀 快速开始

### 环境要求

- Windows 10/11 (64-bit)
- Python 3.10+ (建议 3.12)
- 管理员权限（全局需要，否则无法安装驱动或在部分游戏中进行覆盖操作）

### 安装步骤

1. **克隆项目**

   ```
   ```
2. **安装依赖**

   ```bash
   cd bin
   .\安装依赖_l.bat
   ```

   或手动安装：

   ```bash
   pip install -r bin/requirements.txt
   ```
3. **安装 Interception 驱动**（需要管理员权限）

   ```bash
   cd bin
   右键 "安装驱动_管理员运行_l.bat" → 以管理员身份运行
   ```

### 运行项目

[见启动脚本](#)

| 脚本                                    | 说明                           |
| --------------------------------------- | ------------------------------ |
| `start.bat`                           | 一键启动（推荐，自动检测环境） |
| `3_启动webui.bat`                     | 直接启动 WebUI                 |
| `bin/1_管理员安装全部并启动WebUI.bat` | 完整安装 + 启动（管理员）      |

> ⚠️ **首次使用需要管理员权限** 运行驱动安装脚本。安装后若输入异常，请重启电脑。

---

## 📁 项目架构

```
macro-driver-webui/
├── webui/                  # 前端资源（HTML/CSS/JS）
│   ├── modules/            # 模块化 JS
│   │   ├── auto/           # 可视化编辑器核心
│   │   ├── core/           # 公共工具
│   │   └── editor/         # 编辑器 UI
│   ├── index.html          # 主页面
│   └── automation_editor.html  # 自动化编辑器
├── bridge/                 # 后端 API 桥接层（8个Mixin）
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
├── bin/                    # 批处理脚本与依赖
├── Interception/           # 驱动文件
└── webui_app.py            # 应用入口
```

---

## 📂 核心模块说明

| 模块                   | 路径                        | 功能描述                                            |
| ---------------------- | --------------------------- | --------------------------------------------------- |
| **宏执行引擎**   | `automation/engine.py`    | ExecContext 执行上下文，支持暂停/停止/变量/延时补偿 |
| **自动化编译器** | `automation/compiler.py`  | 将 JSON 执行树编译为可执行的 ExecGraph              |
| **输入驱动层**   | `engine/`                 | SendInput/Interception 双模式，支持 PID Boost       |
| **宏录制系统**   | `recorder/recorder_3d.py` | 3D 轨迹录制，支持按键+轨迹同步                      |
| **WebUI 桥接**   | `bridge/*.py`             | 8 个 Mixin 提供参数/录制/宏管理/自动化 API          |

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

### 开发环境设置

```bash

# 安装依赖
pip install -r bin/requirements.txt

# 创建功能分支
git checkout -b feat/your-feature-name
```

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

**提交示例：**

```bash
git commit -m "feat: 添加宏批量导入功能"
git commit -m "fix: 修复录制时轨迹丢失问题"
```

### Pull Request 流程

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

---

## 📄 许可证

代码仅供参考学习，不可商用！All rights reserved

---

<div align="center">

Made with ❤️ for Genshin automation

</div>
