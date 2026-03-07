@echo off
chcp 65001 >nul 2>&1
title Network Guardian
cd /d "%~dp0\.."
echo.
echo  ========================================
echo   Network Guardian - 网络自愈守护进程
echo  ========================================
echo.
echo  [1] 启动守护       [2] 查看状态
echo  [3] 手机舰队       [4] 断网诊断
echo  [5] 手动切换USB    [6] 恢复主链路
echo  [0] 退出
echo.
set /p choice="请选择: "

if "%choice%"=="1" (
    echo.
    echo 正在启动 Guardian...
    python 构建部署\network_guardian.py
)
if "%choice%"=="2" (
    python 构建部署\network_guardian.py --status
    pause
)
if "%choice%"=="3" (
    python 构建部署\phone_fleet.py
    pause
)
if "%choice%"=="4" (
    python 构建部署\phone_fleet.py --diagnose
    pause
)
if "%choice%"=="5" (
    python 构建部署\network_guardian.py --failover usb
    pause
)
if "%choice%"=="6" (
    python 构建部署\network_guardian.py --restore
    pause
)
if "%choice%"=="0" exit
