@echo off
chcp 65001 >nul 2>&1
title CFW 客户端启动 — 台式机141
color 0A

echo.
echo   ══════════════════════════════════════════
echo   CFW 客户端一键启动 (台式机141)
echo   连接笔记本179 CFW共享 + 启动Windsurf
echo   ══════════════════════════════════════════
echo.

:: ═══ 配置 ═══
set LAPTOP_IP=192.168.31.179
set LAPTOP_PORT=443
set WAN_HOST=60.205.171.100
set WAN_PORT=443

:: ═══ 1. 检测笔记本CFW是否可达 ═══
echo   [1/4] 检测 CFW 服务...
set TARGET_HOST=
set TARGET_PORT=

:: 优先LAN
powershell -NoProfile -Command "try{$t=New-Object Net.Sockets.TcpClient;$a=$t.BeginConnect('%LAPTOP_IP%',%LAPTOP_PORT%,$null,$null);if($a.AsyncWaitHandle.WaitOne(3000)){$t.EndConnect($a);$t.Close();exit 0}else{$t.Close();exit 1}}catch{exit 1}" >nul 2>&1
if %errorlevel%==0 (
    set TARGET_HOST=%LAPTOP_IP%
    set TARGET_PORT=%LAPTOP_PORT%
    echo   ✓ LAN直连: %LAPTOP_IP%:%LAPTOP_PORT%
    goto :STEP2
)

:: 尝试公网
powershell -NoProfile -Command "try{$t=New-Object Net.Sockets.TcpClient;$a=$t.BeginConnect('%WAN_HOST%',%WAN_PORT%,$null,$null);if($a.AsyncWaitHandle.WaitOne(5000)){$t.EndConnect($a);$t.Close();exit 0}else{$t.Close();exit 1}}catch{exit 1}" >nul 2>&1
if %errorlevel%==0 (
    set TARGET_HOST=%WAN_HOST%
    set TARGET_PORT=%WAN_PORT%
    echo   ✓ 公网连接: %WAN_HOST%:%WAN_PORT%
    goto :STEP2
)

echo   [ERROR] 笔记本CFW不可达 (LAN:%LAPTOP_IP%:%LAPTOP_PORT% 公网:%WAN_HOST%:%WAN_PORT%)
echo   请确认笔记本已运行 →启动CFW共享.cmd
pause
exit /b 1

:: ═══ 2. 设置 portproxy ═══
:STEP2
echo.
echo   [2/4] 设置 portproxy (127.0.0.1:443 -^> %TARGET_HOST%:%TARGET_PORT%)
netsh interface portproxy delete v4tov4 listenaddress=127.0.0.1 listenport=443 >nul 2>&1
netsh interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=443 connectaddress=%TARGET_HOST% connectport=%TARGET_PORT%
if %errorlevel%==0 (
    echo   ✓ portproxy 已设置
) else (
    echo   [ERROR] portproxy 设置失败 (需管理员权限)
    pause
    exit /b 1
)

:: ═══ 3. 验证hosts ═══
echo.
echo   [3/4] 验证 hosts...
findstr /C:"server.self-serve.windsurf.com" C:\Windows\System32\drivers\etc\hosts >nul 2>&1
if %errorlevel%==0 (
    echo   ✓ hosts 已配置
) else (
    echo   添加 hosts 条目...
    echo 127.0.0.1 server.self-serve.windsurf.com >> C:\Windows\System32\drivers\etc\hosts
    echo 127.0.0.1 server.codeium.com >> C:\Windows\System32\drivers\etc\hosts
    echo   ✓ hosts 已添加
)

:: ═══ 4. 启动 Windsurf ═══
echo.
echo   [4/4] 启动 Windsurf...
set WS_EXE=
if exist "D:\Windsurf\Windsurf.exe" set "WS_EXE=D:\Windsurf\Windsurf.exe"
if "%WS_EXE%"=="" if exist "%LOCALAPPDATA%\Programs\Windsurf\Windsurf.exe" set "WS_EXE=%LOCALAPPDATA%\Programs\Windsurf\Windsurf.exe"
if "%WS_EXE%"=="" if exist "C:\Program Files\Windsurf\Windsurf.exe" set "WS_EXE=C:\Program Files\Windsurf\Windsurf.exe"

if "%WS_EXE%"=="" (
    echo   [WARN] Windsurf.exe 未找到，portproxy已设置，请手动启动Windsurf
    goto :DONE
)

set SSL_CERT_FILE=C:\ProgramData\cfw_server_cert.pem
set NODE_EXTRA_CA_CERTS=C:\ProgramData\cfw_server_cert.pem
set NODE_TLS_REJECT_UNAUTHORIZED=0
start "" "%WS_EXE%" "--host-resolver-rules=MAP server.self-serve.windsurf.com 127.0.0.1,MAP server.codeium.com 127.0.0.1"
echo   ✓ Windsurf 已启动 (%WS_EXE%)

:DONE
echo.
echo   ══════════════════════════════════════════
echo   CFW 客户端已启动!
echo   模式: %TARGET_HOST%:%TARGET_PORT%
echo   ══════════════════════════════════════════
echo.
pause
