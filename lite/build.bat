@echo off
chcp 65001 >nul
setlocal

set "PROJECT_ROOT=%~dp0.."
set "SPEC_FILE=%~dp0lite.spec"
set "DIST_DIR=%~dp0dist"
set "BUILD_DIR=%~dp0build"

echo ============================================
echo   宏驱动精简版 - PyInstaller 打包脚本
echo ============================================
echo.

where pyinstaller >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [错误] 未找到 pyinstaller，正在安装...
    pip install pyinstaller
    if %ERRORLEVEL% neq 0 (
        echo [错误] pyinstaller 安装失败，请手动运行: pip install pyinstaller
        pause
        exit /b 1
    )
)

echo [1/3] 清理旧的构建文件...
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"

echo [2/3] 开始打包...
pyinstaller --noconfirm --clean --distpath "%DIST_DIR%" --workpath "%BUILD_DIR%" "%SPEC_FILE%"
if %ERRORLEVEL% neq 0 (
    echo.
    echo [错误] 打包失败！请检查上方错误信息。
    pause
    exit /b 1
)

echo [3/3] 复制宏文件目录...
if exist "%DIST_DIR%\宏驱动精简版\宏" rmdir /s /q "%DIST_DIR%\宏驱动精简版\宏"
xcopy "%PROJECT_ROOT%\宏" "%DIST_DIR%\宏驱动精简版\宏" /E /I /Y

echo.
echo ============================================
echo   打包完成！
echo   输出目录: %DIST_DIR%\宏驱动精简版\
echo.
echo   使用方法:
echo   1. 宏文件已自动复制到 "宏" 文件夹
echo   2. 双击 "宏驱动精简版.exe" 启动
echo   3. 在界面中绑定热键并启动监听
echo ============================================
echo.
pause
