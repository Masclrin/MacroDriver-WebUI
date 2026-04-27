@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

echo ========================================================
echo 宏驱动 WebUI - 快速启动
echo ========================================================

:: ───────────────────────────────────────────────────────────
:: 0. 路径定义
:: ───────────────────────────────────────────────────────────
set "ROOT_DIR=%~dp0"
set "BIN_DIR=%ROOT_DIR%bin"
set "REQ_FILE=%BIN_DIR%requirements.txt"
set "APP_PY=%ROOT_DIR%webui_app.py"
set "CONFIG_FILE=%ROOT_DIR%webui_param_config.json"

:: ───────────────────────────────────────────────────────────
:: 1. 环境检测 - 自动发现 Python
:: ───────────────────────────────────────────────────────────
echo [信息] 正在检测 Python 环境...

set "PYTHON_CMD="

:: 策略A：尝试 PATH 中的命令
for %%C in ("py -3" "py" "python" "python3") do (
    if not defined PYTHON_CMD (
        where %%C >nul 2>&1
        if !errorlevel! equ 0 (
            for /f "delims=" %%V in ('%%C --version 2^>^&1') do (
                echo %%V | findstr /i "Python 3" >nul 2>&1
                if !errorlevel! equ 0 (
                    set "PYTHON_CMD=%%C"
                    echo [检测到] %%V  命令: !PYTHON_CMD!
                )
            )
        )
    )
)

:: 策略B：搜索常见安装路径
if not defined PYTHON_CMD (
    echo [信息] 尝试搜索常见 Python 安装路径...
    for %%P in (
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
        "%ProgramFiles%\Python312\python.exe"
        "%ProgramFiles%\Python311\python.exe"
        "%ProgramFiles%\Python310\python.exe"
    ) do (
        if not defined PYTHON_CMD (
            if exist %%P (
                for /f "delims=" %%V in ('%%P --version 2^>^&1') do (
                    echo %%V | findstr /i "Python 3" >nul 2>&1
                    if !errorlevel! equ 0 (
                        set "PYTHON_CMD=%%~P"
                        echo [检测到] %%V  路径: !PYTHON_CMD!
                    )
                )
            )
        )
    )
)

:: 最终判断
if not defined PYTHON_CMD (
    echo.
    echo [错误] 未能找到 Python 3。
    echo        请确认已安装 Python 3.10+ 并添加到系统 PATH。
    echo        或运行 bin\1_管理员安装全部并启动WebUI.bat 进行完整安装。
    pause
    exit /b 1
)

:: ───────────────────────────────────────────────────────────
:: 2. 依赖检查 - 判断是否需要安装
:: ───────────────────────────────────────────────────────────
echo.
echo [检查] 验证 Python 依赖...

:: 简单检查：尝试导入关键包
%PYTHON_CMD% -c "import webview" >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] 检测到依赖未安装，开始安装...
    %PYTHON_CMD% -m pip install -r "%REQ_FILE%"
    if %errorlevel% neq 0 (
        echo [错误] 依赖安装失败，请尝试以管理员身份运行。
        pause
        exit /b 1
    )
    echo [完成] 依赖安装成功。
) else (
    echo [通过] 依赖检查通过。
)

:: ───────────────────────────────────────────────────────────
:: 3. 配置文件检查
:: ───────────────────────────────────────────────────────────
if not exist "%CONFIG_FILE%" (
    echo [警告] 配置文件不存在，将在首次运行时自动创建。
)

:: ───────────────────────────────────────────────────────────
:: 4. 启动 WebUI
:: ───────────────────────────────────────────────────────────
echo.
echo [启动] 正在启动宏驱动 WebUI...
echo [提示] 按 Ctrl+C 可安全退出程序
echo ========================================================
echo.

:: 使用 start 命令在新窗口中运行，便于 Ctrl+C 优雅退出
start "宏驱动 WebUI" cmd /k "cd /d "%ROOT_DIR%" && %PYTHON_CMD% "%APP_PY%""

:: 等待2秒让窗口启动
timeout /t 2 /nobreak >nul

echo [成功] WebUI 已启动！
echo [访问] 请在新打开的"宏驱动 WebUI"窗口中查看
echo.
exit /b 0
