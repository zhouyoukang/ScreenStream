@echo off
REM 透明gRPC代理 — 道法自然
REM 自动启动代理 + Windsurf
title WAM Transparent Proxy

REM 启动透明代理(后台)
start /min "WAM Proxy" node "D:\道\道生一\一生二\无感切号\scripts\transparent_proxy.js" serve

REM 等待代理启动
timeout /t 2 /nobreak >nul

REM 设置环境变量
set HTTPS_PROXY=http://127.0.0.1:19443
set NODE_EXTRA_CA_CERTS=D:\道\道生一\一生二\无感切号\data\certs\ca.crt
set NODE_TLS_REJECT_UNAUTHORIZED=0

REM 启动Windsurf
start "" "D:\Windsurf\Windsurf.exe"

echo.
echo [OK] 透明代理(:19443) + Windsurf 已启动
echo [OK] 96个apiKey已就绪，所有请求将自动路由到最优账号
echo.
pause
