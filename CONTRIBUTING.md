# 贡献指南

感谢你关注 MacroDriver WebUI 项目！欢迎参与协同开发。

---

## 开发环境设置

### 1. 克隆仓库

```bash
git clone https://github.com/Masclrin/macro-webui.git
cd macro-webui
```

### 2. 安装依赖

```bash
pip install -r bin/requirements.txt
```

### 3. 验证环境

```bash
python webui_app.py
```

---

## Git 提交规范

本项目使用 **Angular 规范** 进行 Git 提交信息格式化。

### 提交类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `feat:` | 新功能 | `feat: 添加宏批量导入功能` |
| `fix:` | Bug 修复 | `fix: 修复录制时轨迹丢失问题` |
| `docs:` | 文档更新 | `docs: 更新 README 安装说明` |
| `style:` | 代码格式（不影响功能） | `style: 格式化前端 JS 代码` |
| `refactor:` | 重构（不影响功能） | `refactor: 重构自动化编译器` |
| `perf:` | 性能优化 | `perf: 优化延时补偿算法` |
| `test:` | 测试相关 | `test: 添加编译器单元测试` |
| `chore:` | 构建/工具/依赖 | `chore: 更新 requirements.txt` |
| `ci:` | CI 配置 | `ci: 添加 GitHub Actions` |

### 提交示例

```bash
# 添加新功能
git commit -m "feat: 添加宏导出为 JSON 功能"

# 修复 Bug
git commit -m "fix: 修复 Interception 驱动在 Win11 上加载失败的问题"

# 更新文档
git commit -m "docs: 补充快速开始章节的故障排除说明"

# 重构代码
git commit -m "refactor: 重构 bridge 模块，提取公共基类"

# 性能优化
git commit -m "perf: 优化轨迹化简算法，减少 CPU 占用"
```

### 提交格式要求

- 使用中文描述（简体）
- 标题不超过 50 字
- 标题后不加句号
- 描述与标题之间空一行
- 描述可多行，说明 **what** 和 **why**，不说明 **how**

---

## 分支开发流程

本项目为私有仓库，协作者直接在仓库内创建分支进行开发。

### 1. 克隆仓库

```bash
git clone https://github.com/Masclrin/macro-webui.git
cd macro-webui
```

### 2. 创建功能分支

```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/issue-description
```

### 3. 开发与提交

```bash
# 进行你的更改...
git add .
git commit -m "feat: 添加你的新功能"
```

### 4. 同步主分支最新代码

```bash
git checkout main
git pull origin main
git checkout feature/your-feature-name
git rebase main
```

### 5. 推送分支

```bash
git push origin feature/your-feature-name
```

### 6. 创建 Pull Request

1. 访问仓库页面：https://github.com/Masclrin/macro-webui
2. 点击 **Pull requests** → **New pull request**
3. 选择你的分支作为 compare，`main` 作为 base
4. 填写 PR 标题和描述
5. 点击 **Create pull request**

### PR 描述模板（推荐）

```markdown
## 描述
简要说明这个 PR 解决了什么问题。

## 检查清单
- [ ] 代码已测试
- [ ] 遵循代码规范
- [ ] 提交信息符合规范
- [ ] 文档已更新（如需要）

## 相关 Issue
Fixes #123
```

---

## 关于宏文件

`宏/` 目录下的宏配置文件在首次克隆后即被 Git 停止追踪。这意味着：

- 你本地的宏修改不会被 Git 记录
- `git pull` 不会覆盖你的本地宏文件
- 如需获取共享宏更新，请与仓库管理员联系

---

## 发现 Bug？

请提交 **Issue** 并包含以下信息：

- 清晰的标题和描述
- 复现步骤
- 预期行为 vs 实际行为
- Python 版本、操作系统版本
- 相关日志或截图

---

## 建议新功能？

欢迎提交 **Issue** 或 **Discussion**，描述你的想法和使用场景。

---

<div align="center">

感谢你的贡献！

</div>