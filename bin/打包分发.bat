@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

echo ========================================================
echo   宏驱动控制台 - 打包分发脚本
echo   生成可分发的压缩包（排除开发文件）
echo ========================================================
echo.

set "BIN_DIR=%~dp0"
for %%I in ("%BIN_DIR%..") do set "ROOT_DIR=%%~fI"
set "OUTPUT_DIR=%BIN_DIR%dist"

if exist "%OUTPUT_DIR%" (
    echo [清理] 删除旧的输出目录...
    rmdir /s /q "%OUTPUT_DIR%"
)

echo [1/5] 创建输出目录结构...
mkdir "%OUTPUT_DIR%\宏驱动 WebUI"
mkdir "%OUTPUT_DIR%\宏驱动 WebUI\宏\导入宏"
mkdir "%OUTPUT_DIR%\宏驱动 WebUI\宏\录制宏"
mkdir "%OUTPUT_DIR%\宏驱动 WebUI\宏\预设宏"
mkdir "%OUTPUT_DIR%\宏驱动 WebUI\自动化脚本"

echo [2/5] 复制核心文件...

xcopy /e /i /q /y "%ROOT_DIR%\bridge" "%OUTPUT_DIR%\宏驱动 WebUI\bridge"
xcopy /e /i /q /y "%ROOT_DIR%\automation" "%OUTPUT_DIR%\宏驱动 WebUI\automation"
xcopy /e /i /q /y "%ROOT_DIR%\engine" "%OUTPUT_DIR%\宏驱动 WebUI\engine"
xcopy /e /i /q /y "%ROOT_DIR%\recorder" "%OUTPUT_DIR%\宏驱动 WebUI\recorder"
xcopy /e /i /q /y "%ROOT_DIR%\macro_io" "%OUTPUT_DIR%\宏驱动 WebUI\macro_io"
xcopy /e /i /q /y "%ROOT_DIR%\core" "%OUTPUT_DIR%\宏驱动 WebUI\core"
xcopy /e /i /q /y "%ROOT_DIR%\plugins" "%OUTPUT_DIR%\宏驱动 WebUI\plugins"
xcopy /e /i /q /y "%ROOT_DIR%\webui" "%OUTPUT_DIR%\宏驱动 WebUI\webui"
xcopy /e /i /q /y "%ROOT_DIR%\Interception" "%OUTPUT_DIR%\宏驱动 WebUI\Interception"
xcopy /e /i /q /y "%ROOT_DIR%\bin" "%OUTPUT_DIR%\宏驱动 WebUI\bin"
xcopy /e /i /q /y "%ROOT_DIR%\docs" "%OUTPUT_DIR%\宏驱动 WebUI\docs"

echo [3/5] 复制示例文件（预设宏 + 自动化脚本）...
if exist "%ROOT_DIR%\宏\预设宏\*.json" (
    xcopy /q /y "%ROOT_DIR%\宏\预设宏\*.json" "%OUTPUT_DIR%\宏驱动 WebUI\宏\预设宏\"
    echo   - 预设宏已复制
) else (
    echo   - 预设宏目录为空，跳过
)
if exist "%ROOT_DIR%\自动化脚本\*.json" (
    xcopy /q /y "%ROOT_DIR%\自动化脚本\*.json" "%OUTPUT_DIR%\宏驱动 WebUI\自动化脚本\"
    echo   - 自动化脚本已复制
) else (
    echo   - 自动化脚本目录为空，跳过
)
if exist "%ROOT_DIR%\自动化脚本\*.auto.json" (
    xcopy /q /y "%ROOT_DIR%\自动化脚本\*.auto.json" "%OUTPUT_DIR%\宏驱动 WebUI\自动化脚本\"
)

echo [4/5] 复制根目录文件...
copy /y "%ROOT_DIR%\webui_app.py" "%OUTPUT_DIR%\宏驱动 WebUI\"
copy /y "%ROOT_DIR%\宏执行框架3.2.py" "%OUTPUT_DIR%\宏驱动 WebUI\"
copy /y "%ROOT_DIR%\start.bat" "%OUTPUT_DIR%\宏驱动 WebUI\"
copy /y "%ROOT_DIR%\3_启动webui.bat" "%OUTPUT_DIR%\宏驱动 WebUI\"
copy /y "%ROOT_DIR%\README.md" "%OUTPUT_DIR%\宏驱动 WebUI\"
copy /y "%ROOT_DIR%\CHANGELOG.md" "%OUTPUT_DIR%\宏驱动 WebUI\"
copy /y "%ROOT_DIR%\.gitignore" "%OUTPUT_DIR%\宏驱动 WebUI\"

echo [5/5] 清理 __pycache__ 目录...
for /d /r "%OUTPUT_DIR%" %%d in (__pycache__) do (
    if exist "%%d" (
        rmdir /s /q "%%d"
    )
)

echo.
echo ========================================================
echo   打包完成！
echo ========================================================
echo.
echo 输出目录: %OUTPUT_DIR%\宏驱动 WebUI
echo.
echo 下一步:
echo   1. 手动检查输出目录内容
echo   2. 右键输出目录 -^> 压缩为 ZIP 或 7z
echo   3. 或使用命令:
echo      powershell Compress-Archive -Path "%OUTPUT_DIR%\宏驱动 WebUI" -DestinationPath "%OUTPUT_DIR%\MacroDriver_WebUI_v3.2.0.zip"
echo.
pause
