@echo off
title Dao Remote Agent + FRP
cd /d "%~dp0"

:: Set environment
set PORT=3002
set PUBLIC_URL=aiotvr.xyz/agent

:: Start FRP tunnel (background)
start "FRP-Tunnel" /min "C:\Temp\frp_real_extract\frp_0.61.2_windows_amd64\frpc.exe" -c "%~dp0frpc.toml"

:: Wait for FRP to connect
timeout /t 3 /nobreak >nul

:: Start Node.js server (foreground)
node server.js

:: If server exits, also kill FRP
taskkill /fi "WINDOWTITLE eq FRP-Tunnel" /f >nul 2>&1
