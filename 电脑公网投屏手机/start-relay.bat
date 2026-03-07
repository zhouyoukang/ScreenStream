@echo off
chcp 65001 >nul
title Desktop Cast Relay Server
echo ╔══════════════════════════════════════╗
echo ║  Desktop Cast Relay Server :9802     ║
echo ╚══════════════════════════════════════╝
echo.

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js 18+
    pause
    exit /b 1
)

REM Install dependencies
if not exist "%~dp0node_modules" (
    echo Installing dependencies...
    cd /d "%~dp0"
    npm install --omit=dev
)

node "%~dp0server.js"
pause
