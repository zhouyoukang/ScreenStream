@echo off
REM Agent-Comm Remote Bridge - connects to central Dashboard
SET SCRIPT_DIR=%~dp0

where python >nul 2>nul
if %errorlevel% equ 0 (
    python "%SCRIPT_DIR%bridge_agent.py" %*
) else (
    where python3 >nul 2>nul
    if %errorlevel% equ 0 (
        python3 "%SCRIPT_DIR%bridge_agent.py" %*
    ) else (
        echo {"error": "Python not found in PATH. Install Python 3.8+"}
    )
)
