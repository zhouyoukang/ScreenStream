@echo off
chcp 65001 >nul 2>&1
title CFW 共享启动 — 笔记本179
color 0A

echo.
echo   CFW 共享一键启动 (笔记本179)
echo   启用CFW模式 + LAN共享 + FRP公网
echo.

:: 调用统一控制脚本: 启用CFW + LAN共享
powershell -NoProfile -ExecutionPolicy Bypass -File "E:\道\道生一\一生二\Windsurf无限额度\cfw_control.ps1" -Action on
powershell -NoProfile -ExecutionPolicy Bypass -File "E:\道\道生一\一生二\Windsurf无限额度\cfw_control.ps1" -Action lan-on

echo.
pause
