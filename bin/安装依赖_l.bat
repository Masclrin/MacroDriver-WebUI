@echo off
chcp 65001 >nul
setlocal

set "BIN_DIR=%~dp0"
for %%I in ("%BIN_DIR%..") do set "ROOT_DIR=%%~fI"

cd /d "%ROOT_DIR%"

set "REQ_FILE=%BIN_DIR%requirements.txt"
if not exist "%REQ_FILE%" (
  echo [错误] 未找到依赖文件：%REQ_FILE%
  pause
  exit /b 1
)

echo [1/2] 安装 Python 依赖...
py -3 -m pip install -r "%REQ_FILE%"
if errorlevel 1 (
  echo.
  echo 依赖安装失败，请确认已安装 Python 与 pip。
  echo 若仍失败，可尝试：python -m pip install -r "%REQ_FILE%"
  pause
  exit /b 1
)
echo.
echo 依赖安装完成。
pause
exit /b 0
