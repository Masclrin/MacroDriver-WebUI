@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

echo ========================================================
echo 宏驱动 WebUI 一键安装与启动（管理员）
echo ========================================================

:: ───────────────────────────────────────────────────────────
:: 0. 管理员权限检查
:: ───────────────────────────────────────────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 请右键本文件，选择"以管理员身份运行"。
    pause
    exit /b 1
)

:: ───────────────────────────────────────────────────────────
:: 1. 路径定义与文件检查
:: ───────────────────────────────────────────────────────────
set "BIN_DIR=%~dp0"
for %%I in ("%BIN_DIR%..") do set "ROOT_DIR=%%~fI"
set "REQ_FILE=%BIN_DIR%requirements.txt"
set "INS_EXE=%ROOT_DIR%\Interception\command line installer\install-interception.exe"
set "APP_PY=%ROOT_DIR%\webui_app.py"

if not exist "%REQ_FILE%" (
    echo [错误] 未找到依赖文件：%REQ_FILE%
    pause & exit /b 1
)
if not exist "%INS_EXE%" (
    echo [错误] 未找到驱动安装器：%INS_EXE%
    pause & exit /b 1
)
if not exist "%APP_PY%" (
    echo [错误] 未找到 WebUI 入口：%APP_PY%
    pause & exit /b 1
)

cd /d "%ROOT_DIR%"

:: ───────────────────────────────────────────────────────────
:: 2. 自动发现 Python（多策略回退）
:: ───────────────────────────────────────────────────────────
echo [信息] 正在检测 Python 环境...

set "PYTHON_CMD="

:: ---- 策略 A：按优先级依次尝试 PATH 中的命令 ----
::    优先使用 py launcher（能自动选最新版），
::    回退到 python / python3
for %%C in (
    "py -3"
    "py"
    "python"
    "python3"
) do (
    if not defined PYTHON_CMD (
        for /f "tokens=1,*" %%A in (%%C) do (
            where %%A >nul 2>&1
            if !errorlevel! equ 0 (
                :: 验证版本号 ≥ 3
                for /f "delims=" %%V in ('%%C --version 2^>^&1') do (
                    set "VER_LINE=%%V"
                )
                echo !VER_LINE! | findstr /i "Python 3" >nul 2>&1
                if !errorlevel! equ 0 (
                    set "PYTHON_CMD=%%C"
                    echo [检测到] !VER_LINE!  命令: !PYTHON_CMD!
                )
            )
        )
    )
)

:: ---- 策略 B：搜索常见安装路径 ----
if not defined PYTHON_CMD (
    echo [信息] PATH 中未找到 Python 3，正在搜索常见安装路径...
    set "CANDIDATES="
    for %%P in (
	"%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
	"%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
	"%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python38\python.exe"
        "%ProgramFiles%\Python314\python.exe"
        "%ProgramFiles%\Python313\python.exe"
        "%ProgramFiles%\Python312\python.exe"
        "%ProgramFiles%\Python311\python.exe"
        "%ProgramFiles%\Python310\python.exe"
        "%ProgramFiles%\Python39\python.exe"
        "%ProgramFiles%\Python38\python.exe"
        "%ProgramFiles(x86)%\Python314\python.exe"
        "%ProgramFiles(x86)%\Python313\python.exe"
        "%ProgramFiles(x86)%\Python312\python.exe"
        "%ProgramFiles(x86)%\Python311\python.exe"
        "%ProgramFiles(x86)%\Python310\python.exe"
        "%ProgramFiles(x86)%\Python39\python.exe"
        "%ProgramW6432%\Python314\python.exe"
        "%ProgramW6432%\Python313\python.exe"
        "%ProgramW6432%\Python312\python.exe"
        "%ProgramW6432%\Python311\python.exe"
        "%ProgramW6432%\Python310\python.exe"
        "%ProgramW6432%\Python39\python.exe"
        "C:\Python314\python.exe"
        "C:\Python313\python.exe"
        "C:\Python312\python.exe"
        "C:\Python311\python.exe"
        "C:\Python310\python.exe"
        "C:\Python39\python.exe"
        "C:\Python38\python.exe"
    ) do (
        if not defined PYTHON_CMD (
            if exist %%P (
                for /f "delims=" %%V in ('%%P --version 2^>^&1') do (
                    set "VER_LINE=%%V"
                )
                echo !VER_LINE! | findstr /i "Python 3" >nul 2>&1
                if !errorlevel! equ 0 (
                    set "PYTHON_CMD=%%~P"
                    echo [检测到] !VER_LINE!  路径: !PYTHON_CMD!
                )
            )
        )
    )
)

:: ---- 策略 C：通过 PowerShell 查询注册表 / AppX ----
if not defined PYTHON_CMD (
    echo [信息] 常见路径未找到，尝试通过 PowerShell 查询系统信息...
    for /f "usebackq delims=" %%F in (
        'powershell -NoProfile -Command ^
            "$p = $null;" ^
            "try { $p = (Get-Command python -ErrorAction SilentlyContinue).Source } catch {};" ^
            "if (-not $p) {" ^
            "  $regPaths = @(\"HKLM:\SOFTWARE\Python\PythonCore\",\"HKCU:\SOFTWARE\Python\PythonCore\");" ^
            "  foreach ($r in $regPaths) {" ^
            "    if (Test-Path $r) {" ^
            "      $latest = (Get-ChildItem $r | Sort-Object Name -Descending | Select-Object -First 1).Name;" ^
            "      $exe = Join-Path $r $latest \"InstallPath\" \"python.exe\";" ^
            "      if (Test-Path $exe) { $p = $exe; break }" ^
            "    }" ^
            "  }" ^
            "};" ^
            "if (-not $p) {" ^
            "  $appx = Get-AppxPackage *Python* -ErrorAction SilentlyContinue | Select-Object -First 1;" ^
            "  if ($appx) { $p = Join-Path $appx.InstallLocation \"python.exe\" }" ^
            "};" ^
            "if ($p) { Write-Output $p }" 2^>nul'
    ) do (
        if exist %%F (
            for /f "delims=" %%V in ('%%F --version 2^>^&1') do (
                set "VER_LINE=%%V"
            )
            echo !VER_LINE! | findstr /i "Python 3" >nul 2>&1
            if !errorlevel! equ 0 (
                set "PYTHON_CMD=%%F"
                echo [检测到] !VER_LINE!  路径: !PYTHON_CMD!
            )
        )
    )
)

:: ---- 最终判断 ----
if not defined PYTHON_CMD (
    echo.
    echo [错误] 未能找到 Python 3。
    echo        已尝试以下策略：
    echo          1. PATH 中的 py / python / python3 命令
    echo          2. 常见安装目录扫描
    echo          3. PowerShell 注册表与 Microsoft Store 查询
    echo.
    echo        请确认已安装 Python 3.8+ 并将其添加到系统 PATH，
    echo        或手动修改本脚本中 set "PYTHON_CMD=..." 指向你的 python.exe。
    pause
    exit /b 1
)

:: ───────────────────────────────────────────────────────────
:: 3. 安装 Python 依赖
:: ───────────────────────────────────────────────────────────
echo.
echo [1/3] 安装 Python 依赖...
%PYTHON_CMD% -m pip install -r "%REQ_FILE%"
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败。
    pause & exit /b 1
)

:: ───────────────────────────────────────────────────────────
:: 4. 安装 Interception 驱动
:: ───────────────────────────────────────────────────────────
echo.
echo [2/3] 安装 Interception 驱动...
"%INS_EXE%" /install
if %errorlevel% neq 0 (
    echo [错误] 驱动安装失败，请确认管理员权限与系统兼容性。
    pause & exit /b 1
)

:: ───────────────────────────────────────────────────────────
:: 5. 启动 WebUI
:: ───────────────────────────────────────────────────────────
echo.
echo [3/3] 启动 WebUI...
%PYTHON_CMD% "%APP_PY%"
if %errorlevel% neq 0 (
    echo [错误] WebUI 启动失败，请检查 Python 版本与依赖安装结果。
    pause & exit /b 1
)

echo.
echo [完成] WebUI 已正常退出。
exit /b 0

