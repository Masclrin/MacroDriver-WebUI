@echo off
setlocal
chcp 65001 >nul

echo ========================================================
echo [修复] Interception 驱动安装工具
echo ========================================================

net session >nul 2>&1
if %errorlevel% neq 0 (
  echo [错误] 请右键“以管理员身份运行”此脚本。
  pause
  exit /b 1
)

set "BIN_DIR=%~dp0"
for %%I in ("%BIN_DIR%..") do set "ROOT_DIR=%%~fI"
set "INS=%ROOT_DIR%\Interception\command line installer\install-interception.exe"

if not exist "%INS%" (
  echo [错误] 未找到安装器：
  echo %INS%
  pause
  exit /b 1
)

echo [步骤2/2] 安装 Interception 驱动...
"%INS%" /install

echo.
echo [完成] 驱动重置已执行。
echo.
pause
exit /b 0
