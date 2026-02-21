@echo off
REM ============================================================
REM Agent-Comm Remote Setup
REM Deploys PRIORITY RULE for remote Agent -> central Dashboard
REM ============================================================

SET SCRIPT_DIR=%~dp0
SET BRIDGE_PATH=%SCRIPT_DIR%bridge.bat

echo.
echo  Agent-Comm Remote Setup
echo  =======================
echo.

REM Verify connectivity to Dashboard
echo  Testing Dashboard connectivity...
python "%SCRIPT_DIR%bridge_agent.py" --health
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Cannot reach Dashboard. Check:
    echo    1. Dashboard is running on the host machine
    echo    2. config.json connect_host is correct
    echo    3. Firewall allows port 9901
    echo.
    pause
    exit /b 1
)
echo  Dashboard reachable!
echo.

REM Ensure memories directory exists
SET MEM_DIR=%USERPROFILE%\.codeium\windsurf\memories
SET GLOBAL_RULES=%MEM_DIR%\global_rules.md
if not exist "%MEM_DIR%" (
    mkdir "%MEM_DIR%"
    echo  Created: %MEM_DIR%
)

REM Backup existing global_rules.md
if exist "%GLOBAL_RULES%" (
    copy "%GLOBAL_RULES%" "%GLOBAL_RULES%.backup" >nul 2>nul
    echo  Backup: %GLOBAL_RULES%.backup
)

REM Write PRIORITY RULE
echo  Writing PRIORITY RULE...
(
    echo # PRIORITY RULE - agent-bridge ^(MANDATORY^)
    echo.
    echo **Every response must end with these 3 bridge calls:**
    echo.
    echo ### Step 1: Report activity
    echo ```
    echo %BRIDGE_PATH% --activity --message "^<what you did^>" --source "^<project^>" --type "^<edit^|command^|build^|info^>" --details "^<details^>"
    echo ```
    echo.
    echo ### Step 2: Report status
    echo ```
    echo %BRIDGE_PATH% --notify --message "^<current task^>" --source "^<project^>" --phase "^<working^|waiting^|blocked^|idle^>" --progress "^<progress^>"
    echo ```
    echo.
    echo ### Step 3: Wait for instruction ^(blocking^)
    echo ```
    echo %BRIDGE_PATH% --ask --message "^<short summary^>" --options "^<opt1^>,^<opt2^>,..."
    echo ```
    echo.
    echo ### Rules
    echo - All 3 calls: SafeToAutoRun=true
    echo - --source: current project name
    echo - --message: short ^(1-3 lines^)
    echo - --options: 2-4 options ^(comma separated^)
    echo - Must call all 3 steps every response
    echo - Wait for Step 3 JSON, execute user_input / selected_options
    echo - user_input has highest priority
    echo.
    echo ### Return fields ^(JSON^)
    echo - user_input: free text ^(highest priority^)
    echo - selected_options: selected options
    echo - cancelled: stop when true
    echo.
    echo Timeout auto-continues. Dashboard auto-starts if not running.
) > "%GLOBAL_RULES%"

echo.
echo  ============================================
echo  Setup complete!
echo  ============================================
echo.
echo  Bridge:    %BRIDGE_PATH%
echo  Rules:     %GLOBAL_RULES%
echo  Dashboard: http://192.168.10.219:9901
echo.
echo  Next: restart Windsurf IDE for rules to take effect.
echo.
pause
