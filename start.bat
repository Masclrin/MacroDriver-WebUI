@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

echo ========================================================
echo   宏驱动控制台 MacroDriver WebUI v3.1
echo   高精度宏录制、编辑与自动化执行
echo ========================================================
echo.

:: ───────────────────────────────────────────────────────────
:: 0. 路径定义
:: ───────────────────────────────────────────────────────────
set "ROOT_DIR=%~dp0"
set "BIN_DIR=%ROOT_DIR%bin"
set "REQ_FILE=%BIN_DIR%requirements.txt"
set "APP_PY=%ROOT_DIR%webui_app.py"
set "CONFIG_FILE=%ROOT_DIR%webui_param_config.json"
set "FIRST_RUN_MARKER=%ROOT_DIR%.first_run_done"

:: ───────────────────────────────────────────────────────────
:: 1. 首次运行提示
:: ───────────────────────────────────────────────────────────
if not exist "%FIRST_RUN_MARKER%" (
    echo [首次运行] 检测到首次启动，显示快速指南...
    echo.
    echo   ┌──────────────────────────────────────────────────┐
    echo   │  快速上手指南                                      │
    echo   │                                                    │
    echo   │  1. 首次使用需安装 Interception 驱动（管理员权限）  │
    echo   │     右键 bin\安装驱动_管理员运行_l.bat             │
    echo   │     选择"以管理员身份运行"                         │
    echo   │                                                    │
    echo   │  2. 驱动安装后若键盘鼠标无响应，请重启电脑          │
    echo   │                                                    │
    echo   │  3. 键盘急救：运行 bin\键盘急救修复.py             │
    echo   │                                                    │
    echo   │  4. 快捷键速查：                                   │
    echo   │     F8  = 全局暂停/恢复    ESC = 停止全部宏        │
    echo   │     F1  = 运行自动化      F7  = 暂停自动化        │
    echo   │                                                    │
    echo   │  5. 详细说明见 docs\使用说明书.md                  │
    echo   └──────────────────────────────────────────────────┘
    echo.
    echo 按任意键继续启动，或关闭窗口取消...
    pause >nul
    echo.>"%FIRST_RUN_MARKER%"
)

:: ───────────────────────────────────────────────────────────
:: 2. 环境检测 - 自动发现 Python
:: ───────────────────────────────────────────────────────────
echo [信息] 正在检测 Python 环境...

set "PYTHON_CMD="

for %%C in ("py -3" "py" "python" "python3") do (
    if not defined PYTHON_CMD (
        for /f "tokens=1,*" %%A in ("%%C") do (
            where %%A >nul 2>&1
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
)

if not defined PYTHON_CMD (
    echo [信息] 尝试搜索常见 Python 安装路径...
    for %%P in (
        "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
        "%ProgramFiles%\Python314\python.exe"
        "%ProgramFiles%\Python313\python.exe"
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

if not defined PYTHON_CMD (
    echo.
    echo [错误] 未能找到 Python 3。
    echo        请确认已安装 Python 3.10+ 并添加到系统 PATH。
    echo        或运行 bin\1_管理员安装全部并启动WebUI.bat 进行完整安装。
    echo.
    echo        Python 下载地址: https://www.python.org/downloads/
    echo        安装时请勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

:: ───────────────────────────────────────────────────────────
:: 3. 依赖检查
:: ───────────────────────────────────────────────────────────
echo.
echo [检查] 验证 Python 依赖...

%PYTHON_CMD% -c "import webview" >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] 检测到依赖未安装，开始安装...
    echo         这可能需要几分钟，请耐心等待...
    %PYTHON_CMD% -m pip install -r "%REQ_FILE%"
    if !errorlevel! neq 0 (
        echo [错误] 依赖安装失败，请尝试以管理员身份运行。
        pause
        exit /b 1
    )
    echo [完成] 依赖安装成功。
) else (
    echo [通过] 依赖检查通过。
)

:: ───────────────────────────────────────────────────────────
:: 4. 配置文件检查
:: ───────────────────────────────────────────────────────────
if not exist "%CONFIG_FILE%" (
    echo [信息] 首次运行，配置文件将在启动时自动创建。
)

:: ───────────────────────────────────────────────────────────
:: 5. 确保用户数据目录存在
:: ───────────────────────────────────────────────────────────
if not exist "%ROOT_DIR%宏" mkdir "%ROOT_DIR%宏"
if not exist "%ROOT_DIR%宏\导入宏" mkdir "%ROOT_DIR%宏\导入宏"
if not exist "%ROOT_DIR%宏\录制宏" mkdir "%ROOT_DIR%宏\录制宏"
if not exist "%ROOT_DIR%宏\预设宏" mkdir "%ROOT_DIR%宏\预设宏"
if not exist "%ROOT_DIR%自动化脚本" mkdir "%ROOT_DIR%自动化脚本"

:: ───────────────────────────────────────────────────────────
:: 6. 启动 WebUI
:: ───────────────────────────────────────────────────────────
echo.
echo [启动] 正在启动宏驱动控制台...
echo        按 Ctrl+C 可安全退出程序
echo ========================================================
echo.

%PYTHON_CMD% "%APP_PY%"

if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出。
    echo        常见原因：
    echo          - 依赖未完整安装，请运行 bin\安装依赖_l.bat
    echo          - Interception 驱动未安装，请运行 bin\安装驱动_管理员运行_l.bat
    echo          - 如键盘鼠标无响应，请重启电脑或运行 bin\键盘急救修复.py
    echo.
    pause
)
