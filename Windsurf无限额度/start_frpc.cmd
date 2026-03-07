@echo off
title FRP Client - CFW Proxy Tunnel
echo ========================================
echo   FRP Client - CFW Proxy Tunnel
echo   台式机CFW:443 → 阿里云:18443
echo ========================================
echo.

set FRPC_DIR=d:\道\道生一\一生二\远程桌面\frp
set FRPC_EXE=d:\道\道生一\一生二\阿里云服务器\frpc.exe
set FRPC_CONF=%FRPC_DIR%\frpc.toml

if not exist "%FRPC_EXE%" (
    echo [ERROR] frpc.exe not found at %FRPC_EXE%
    pause
    exit /b 1
)

if not exist "%FRPC_CONF%" (
    echo [ERROR] frpc.toml not found at %FRPC_CONF%
    pause
    exit /b 1
)

echo [INFO] Starting frpc with config: %FRPC_CONF%
echo [INFO] FRP Server: 60.205.171.100:7000
echo [INFO] Tunnels: cfw_proxy(443→18443), rdp(3389→13389), ...
echo.

"%FRPC_EXE%" -c "%FRPC_CONF%"

echo.
echo [WARN] frpc exited. Press any key to restart...
pause
goto :eof
