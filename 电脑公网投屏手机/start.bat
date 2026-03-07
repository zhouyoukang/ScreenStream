@echo off
chcp 65001 >nul
title Desktop Cast Provider
echo ╔══════════════════════════════════════╗
echo ║  电脑公网投屏手机 — Desktop Cast     ║
echo ╚══════════════════════════════════════╝
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

REM Install dependencies if needed
pip show mss >nul 2>&1 || pip install mss Pillow websocket-client websockets pyautogui pyperclip -q

REM Mode selection
echo [1] Relay mode (via relay server, supports public network)
echo [2] P2P Direct mode (LAN only, no relay needed)
set /p MODE="Select mode (1/2): "

if "%MODE%"=="2" (
    python "%~dp0desktop.py" --direct --fps 10 --quality 60 --scale 50
) else (
    REM Default: public relay. Change to ws://localhost:9802 for local testing
    python "%~dp0desktop.py" --relay wss://aiotvr.xyz/desktop/ --fps 10 --quality 60 --scale 50
)

pause
