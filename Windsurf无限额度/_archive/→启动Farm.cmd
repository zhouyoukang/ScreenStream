@echo off
chcp 65001 >nul
title Windsurf Account Farm
echo ============================================
echo   Windsurf Account Farm v2.0
echo ============================================
echo.
echo Commands:
echo   1. test-email       - Test Mail.tm API
echo   2. register          - Register 1 account
echo   3. register --count N - Register N accounts
echo   4. status            - Show account pool
echo   5. reset-fingerprint - Reset device fingerprint
echo   6. activate EMAIL    - Activate account
echo.

if "%1"=="" (
    set /p CMD="Enter command: "
) else (
    set CMD=%*
)

cd /d "%~dp0"
python windsurf_farm.py %CMD%
echo.
pause
