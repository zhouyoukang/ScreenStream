@echo off
REM Auto-detect Python and run bridge_agent.py with all arguments
REM This script should be placed where Agents can call it (e.g. project root or PATH)

SET SCRIPT_DIR=%~dp0
SET BRIDGE=%SCRIPT_DIR%bridge_agent.py

where python >nul 2>nul
if %errorlevel% equ 0 (
    python "%BRIDGE%" %*
) else (
    where python3 >nul 2>nul
    if %errorlevel% equ 0 (
        python3 "%BRIDGE%" %*
    ) else (
        echo {"error": "Python not found in PATH. Install Python 3.8+ and add to PATH."}
    )
)
