@echo off
chcp 65001 >nul 2>&1
title CFW 共享关闭 — 笔记本179
color 0C

echo.
echo   CFW 一键关闭 + 恢复官方模式 (笔记本179)
echo   关闭CFW + 清理hosts/env/补丁 + 移除portproxy
echo.

:: 调用统一控制脚本: 禁用CFW，回归官方
powershell -NoProfile -ExecutionPolicy Bypass -File "E:\道\道生一\一生二\Windsurf无限额度\cfw_control.ps1" -Action off

echo.
echo   现在可以直接启动Windsurf使用官方服务
echo   如需深度清理(含Root CA): 运行 cfw_control.ps1 -Action restore
echo.
pause
