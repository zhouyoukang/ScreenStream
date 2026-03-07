@echo off
title 道 · 远程中枢
echo ============================================
echo   道 · 远程中枢
echo   五感连接远方 · 大脑分析万象
echo ============================================
echo.

:: 启动 Node.js 服务器
echo [1/1] 启动远程中枢服务器...
cd /d %~dp0remote-agent
node server.js

echo.
echo 服务已退出。
pause >nul
