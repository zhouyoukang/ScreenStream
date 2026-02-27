@echo off
chcp 65001 >nul 2>&1
title 道 — 智能体系

:: 防止重复启动
set PORT=9090
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING" 2^>nul') do (
    echo [道] 已在运行 (PID %%a)，打开浏览器...
    start "" "http://localhost:%PORT%"
    goto :eof
)

:: 启动（pythonw无控制台窗口，托盘常驻）
set SCRIPT=%~dp0dashboard-server.py
start "" "C:\Program Files\Python311\pythonw.exe" "%SCRIPT%"

:: 等待启动
timeout /t 2 /nobreak >nul

:: 验证
curl.exe -s -m 3 http://localhost:%PORT%/ >nul 2>&1
if %errorlevel%==0 (
    echo [道] 已启动 http://localhost:%PORT%
    start "" "http://localhost:%PORT%"
) else (
    echo [道] 启动失败，尝试前台模式...
    python "%SCRIPT%" --no-tray
)
