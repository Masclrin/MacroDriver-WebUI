@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

set "LOG=%~dp0诊断结果.txt"
echo 诊断开始 %date% %time% > "%LOG%"

:: --- 管理员检查 ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [失败] 未以管理员身份运行 >> "%LOG%"
) else (
    echo [OK] 管理员权限确认 >> "%LOG%"
)

:: --- 路径 ---
set "BIN_DIR=%~dp0"
for %%I in ("%BIN_DIR%..") do set "ROOT_DIR=%%~fI"
echo [路径] BIN_DIR=%BIN_DIR% >> "%LOG%"
echo [路径] ROOT_DIR=%ROOT_DIR% >> "%LOG%"

:: --- 关键文件 ---
set "REQ_FILE=%BIN_DIR%requirements.txt"
set "INS_EXE=%ROOT_DIR%\Interception\command line installer\install-interception.exe"
set "APP_PY=%ROOT_DIR%\webui_app.py"

if exist "%REQ_FILE%" (echo [OK] requirements.txt >> "%LOG%") else (echo [缺失] %REQ_FILE% >> "%LOG%")
if exist "%INS_EXE%" (echo [OK] install-interception.exe >> "%LOG%") else (echo [缺失] %INS_EXE% >> "%LOG%")
if exist "%APP_PY%" (echo [OK] webui_app.py >> "%LOG%") else (echo [缺失] %APP_PY% >> "%LOG%")

:: --- Python ---
where py >nul 2>&1
if !errorlevel! equ 0 (
    for /f "delims=" %%V in ('py -3 --version 2^>^&1') do echo [OK] Python: %%V >> "%LOG%"
) else (
    echo [失败] py 命令未找到 >> "%LOG%"
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "delims=" %%V in ('python --version 2^>^&1') do echo [OK] python: %%V >> "%LOG%"
    ) else (
        echo [失败] python 命令也未找到 >> "%LOG%"
    )
)

:: --- pip 依赖 ---
py -3 -c "import webview" >nul 2>&1
if !errorlevel! equ 0 (echo [OK] webview 已安装 >> "%LOG%") else (echo [缺少] webview 未安装 >> "%LOG%")
py -3 -c "import interception" >nul 2>&1
if !errorlevel! equ 0 (echo [OK] interception 已安装 >> "%LOG%") else (echo [缺少] interception 未安装 >> "%LOG%")

:: --- 简单启动测试 ---
echo [测试] 尝试启动 webui_app.py（5秒后自动结束）... >> "%LOG%"
cd /d "%ROOT_DIR%"
start /b py -3 "%APP_PY%" > "%BIN_DIR%启动日志.txt" 2>&1
timeout /t 5 /nobreak >nul
taskkill /f /im py.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
echo [测试] 启动日志已保存 >> "%LOG%"

:: --- 合并启动日志 ---
echo. >> "%LOG%"
echo === 启动日志 === >> "%LOG%"
type "%BIN_DIR%启动日志.txt" >> "%LOG%"

echo. >> "%LOG%"
echo 诊断完成 >> "%LOG%"

echo 诊断完成！结果保存在：
echo %LOG%
echo.
type "%LOG%"
pause
