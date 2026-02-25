@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [SmartHome Gateway] Starting...
python gateway.py
pause
