@echo off
chcp 65001 >nul 2>&1
title ADB Bridge - 公网远程配置
color 0A

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   ADB Bridge 一键启动器                      ║
echo  ║   让网页远程配置你的手机                      ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: ─── 检查Python ───
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] 未检测到 Python
    echo      请先安装 Python 3.8+: https://python.org
    echo      安装时勾选 "Add Python to PATH"
    pause
    exit /b 1
)
echo  [√] Python 已安装

:: ─── 检查websocket-client ───
python -c "import websocket" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [*] 正在安装 websocket-client ...
    pip install websocket-client -q
    if %errorlevel% neq 0 (
        echo  [!] 安装失败，请手动运行: pip install websocket-client
        pause
        exit /b 1
    )
)
echo  [√] websocket-client 已就绪

:: ─── 检查ADB ───
where adb >nul 2>&1
if %errorlevel% neq 0 (
    if exist "D:\platform-tools\adb.exe" (
        set "PATH=D:\platform-tools;%PATH%"
    ) else if exist "C:\platform-tools\adb.exe" (
        set "PATH=C:\platform-tools;%PATH%"
    ) else if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
        set "PATH=%LOCALAPPDATA%\Android\Sdk\platform-tools;%PATH%"
    ) else (
        echo  [!] 未检测到 ADB (Android 平台工具)
        echo      请下载: https://developer.android.com/tools/releases/platform-tools
        echo      解压到 D:\platform-tools\ 或 C:\platform-tools\
        pause
        exit /b 1
    )
)
echo  [√] ADB 已就绪

:: ─── 检查手机连接 ───
adb devices | findstr "device" | findstr /v "List" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [!] 未检测到手机连接
    echo      请确认:
    echo      1. 手机通过USB连接电脑
    echo      2. 手机已开启USB调试
    echo      3. 手机上已授权此电脑调试
    echo.
    echo  按任意键继续启动（无手机模式）...
    pause >nul
)

:: ─── 查找adb-bridge.py ───
set "BRIDGE=%~dp0adb-bridge.py"
if not exist "%BRIDGE%" (
    echo  [!] 未找到 adb-bridge.py
    echo      请将此脚本放在 adb-bridge.py 同目录下
    pause
    exit /b 1
)

:: ─── 启动公网模式 ───
echo.
echo  ════════════════════════════════════════════════
echo   正在启动公网模式...
echo  ════════════════════════════════════════════════
echo.
python "%BRIDGE%" --public
pause
