@echo off
chcp 65001 >nul 2>&1
title CFW 启动器
color 0A

echo.
echo   CFW 启动器 — 笔记本本机
echo.

:: 检测443端口
set PORT_PID=
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:443" ^| findstr "LISTENING"') do set PORT_PID=%%a

if "%PORT_PID%"=="" goto :START_CFW

tasklist /fi "PID eq %PORT_PID%" /fo csv /nh | findstr /i "CodeFreeWindsurf" >nul 2>&1
if %errorlevel%==0 (
    echo   CFW 已在运行 (PID %PORT_PID%) ✓
    goto :VERIFY
)

echo   443 被 PID %PORT_PID% 占用，清理中...
taskkill /F /PID %PORT_PID% >nul 2>&1
timeout /t 2 /nobreak >nul

:START_CFW
:: 查找CFW（笔记本路径）
set CFW_EXE=
if exist "C:\temp\cfw\CodeFreeWindsurf-x64-2.0.5.exe" (
    set "CFW_EXE=C:\temp\cfw\CodeFreeWindsurf-x64-2.0.5.exe"
)
if "%CFW_EXE%"=="" (
    for /f "delims=" %%f in ('dir /b /o-d "C:\temp\cfw\CodeFreeWindsurf*.exe" 2^>nul') do (
        if "!CFW_EXE!"=="" set "CFW_EXE=C:\temp\cfw\%%f"
    )
)
if "%CFW_EXE%"=="" (
    echo   [ERROR] C:\temp\cfw\ 下未找到 CodeFreeWindsurf exe
    pause
    exit /b 1
)

echo   启动: %CFW_EXE%
start "" "%CFW_EXE%"

:: 等待绑定443
set N=0
:WAIT
timeout /t 2 /nobreak >nul
set /a N+=1
netstat -ano | findstr "127.0.0.1:443" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 goto :VERIFY
if %N% geq 15 (
    echo   [TIMEOUT] CFW 30s 未绑定 443
    pause
    exit /b 1
)
echo   等待... (%N%/15)
goto :WAIT

:VERIFY
echo.
findstr /C:"server.self-serve.windsurf.com" C:\Windows\System32\drivers\etc\hosts >nul 2>&1 && echo   ✓ hosts || echo   ✗ hosts 缺失
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:443" ^| findstr "LISTENING"') do echo   ✓ CFW PID %%a
if exist "D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js" (
    findstr /C:"Pro Ultimate" "D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js" >nul 2>&1 && echo   ✓ 补丁 || echo   ✗ 补丁未生效
)
echo.
echo   启动完成
echo.
pause
