@echo off
chcp 65001 >nul
setlocal

set "APP_DIR=%~dp0"
set "EXE_PATH=%APP_DIR%宏驱动精简版.exe"

if not exist "%EXE_PATH%" (
    echo [错误] 未找到 宏驱动精简版.exe
    echo 请确认此文件与 bat 文件在同一目录下。
    pause
    exit /b 1
)

start "" "%EXE_PATH%"
