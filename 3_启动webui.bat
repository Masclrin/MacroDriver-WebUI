@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY_CMD="
where py >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"
if not defined PY_CMD (
    where python >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)
if not defined PY_CMD (
    echo [Error] Python not found.
    echo Please run bin\1_install.bat first.
    pause
    exit /b 1
)

echo [Info] Python: %PY_CMD%
echo [Info] Dir:    %CD%
echo [Start] Launching WebUI...
%PY_CMD% "webui_app.py"
set "_EXIT=%errorlevel%"
echo.
if %_EXIT% neq 0 (
    echo [Error] Launch failed, exit code: %_EXIT%
) else (
    echo [Done] WebUI exited normally.
)
pause
