@echo off
chcp 65001 >nul
REM 透明gRPC代理 — 道法自然
title WAM Transparent Proxy v3.8

REM 启动透明代理(后台)
start /min "WAM Proxy" node "%~dp0scripts\transparent_proxy.js" serve

REM 等待代理启动
timeout /t 2 /nobreak >nul

REM 设置环境变量
set HTTPS_PROXY=http://127.0.0.1:19443
set NODE_EXTRA_CA_CERTS=%~dp0data\certs\ca.crt
set NODE_TLS_REJECT_UNAUTHORIZED=0

REM 查找Windsurf.exe
set "WS="
for %%d in (D E C) do (
    if exist "%%d:\Windsurf\Windsurf.exe" set "WS=%%d:\Windsurf\Windsurf.exe"
)
if defined WS (
    start "" "%WS%"
) else (
    echo [WARN] 未找到Windsurf.exe，请手动启动
)

echo.
echo [OK] 透明代理(:19443) 已启动
echo.
pause
