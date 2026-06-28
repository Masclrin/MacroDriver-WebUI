@echo off
chcp 65001 >nul

:: ========================================================
:: 宏驱动 WebUI - 直接启动脚本
:: ========================================================

:: 切换到脚本所在目录（项目根目录）
cd /d "%~dp0"

:: 检查 Python 命令是否存在
set "PY_CMD="
where py >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"
if not defined PY_CMD (
    where python >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)
if not defined PY_CMD (
    echo [错误] 未找到 Python 命令。
    echo        请先运行 bin\1_管理员安装全部并启动WebUI.bat 进行环境配置。
    pause
    exit /b 1
)

:: 启动 WebUI
echo [信息] Python 命令: %PY_CMD%
echo [信息] 工作目录:   %CD%
echo [启动] 正在启动宏驱动 WebUI...
%PY_CMD% "webui_app.py"
set "_EXIT=%errorlevel%"
echo.
if %_EXIT% neq 0 (
    echo [错误] 启动失败，退出码: %_EXIT%
    echo        请先运行 bin\1_管理员安装全部并启动WebUI.bat 进行环境配置。
) else (
    echo [完成] WebUI 已正常退出。
)
pause
