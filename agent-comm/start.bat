@echo off
REM One-click start for Agent Communication Dashboard
REM Usage: double-click this file or run from terminal

SET SCRIPT_DIR=%~dp0

echo ============================================
echo   Agent Communication Dashboard
echo ============================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH.
    echo Install Python 3.8+ and add to PATH.
    pause
    exit /b 1
)

echo Starting Dashboard...
echo Config: %SCRIPT_DIR%config.json
echo.
python "%SCRIPT_DIR%core\dashboard.py" %*
