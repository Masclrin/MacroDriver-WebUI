@echo off
chcp 65001 >nul
setlocal

net session >nul 2>&1
if %errorlevel% neq 0 (
  echo [错误] 请右键本文件，选择“以管理员身份运行”。
  pause
  exit /b 1
)

set "BIN_DIR=%~dp0"
for %%I in ("%BIN_DIR%..") do set "ROOT_DIR=%%~fI"
set "INS_DIR=%ROOT_DIR%\Interception\command line installer"
set "INS_EXE=%INS_DIR%\install-interception.exe"

if not exist "%INS_EXE%" (
  echo [错误] 未找到驱动安装器：
  echo %INS_EXE%
  pause
  exit /b 1
)

cd /d "%INS_DIR%"
echo [1/2] 安装 Interception 驱动...
"%INS_EXE%" /install
if errorlevel 1 (
  echo.
  echo 驱动安装失败，请确认当前命令窗已管理员权限。
  pause
  exit /b 1
)
echo.
echo 驱动安装完成，请重启电脑后再启动宏。
pause
exit /b 0
