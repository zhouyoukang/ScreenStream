@echo off
chcp 65001 >nul 2>&1
title Windsurf Self-Hosted Proxy v2.0

echo.
echo   ╔══════════════════════════════════════════════╗
echo   ║  Windsurf 自建代理 v2.0                      ║
echo   ║  gRPC感知 + 响应解析 + Plan检测              ║
echo   ╚══════════════════════════════════════════════╝
echo.

:: 检查管理员权限（端口443需要）
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo   [!] 需要管理员权限（端口443）
    echo   [!] 右键 → 以管理员身份运行
    pause
    exit /b 1
)

:: 检查CFW是否在运行
netstat -ano -p TCP 2>nul | findstr "127.0.0.1:443.*LISTEN" >nul 2>&1
if %errorLevel% equ 0 (
    echo   [!] 端口 443 已被占用
    for /f "tokens=5" %%a in ('netstat -ano -p TCP ^| findstr "127.0.0.1:443.*LISTEN"') do (
        set "CFW_PID=%%a"
        for /f "tokens=1" %%b in ('tasklist /fi "PID eq %%a" /fo csv /nh 2^>nul') do (
            echo   [!] 占用进程: %%b (PID: %%a^)
        )
    )
    echo.
    choice /C YN /M "   是否终止占用进程并启动自建代理? (Y/N)"
    if errorlevel 2 (
        echo   [*] 已取消
        pause
        exit /b 1
    )
    echo   [*] 终止 PID %CFW_PID%...
    taskkill /F /PID %CFW_PID% >nul 2>&1
    timeout /t 2 /nobreak >nul
    echo   [✓] 端口已释放
    echo.
)

:: 启动代理
cd /d "%~dp0"
echo   [*] 启动自建代理...
echo.
python windsurf_proxy.py %*
pause
