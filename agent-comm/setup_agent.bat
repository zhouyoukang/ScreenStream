@echo off
REM ============================================================
REM Agent-Comm: One-click setup for any Windsurf IDE instance
REM Creates E:\bridge.bat redirect + deploys PRIORITY RULE
REM ============================================================

SET SCRIPT_DIR=%~dp0
SET BRIDGE_SRC=%SCRIPT_DIR%core\bridge_agent.py
SET BRIDGE_ROOT=E:\bridge.bat

echo.
echo  Agent-Comm Setup
echo  ================
echo.

REM Step 1: Create E:\bridge.bat redirect if missing
if not exist "%BRIDGE_ROOT%" (
    echo  Creating %BRIDGE_ROOT% ...
    (
        echo @echo off
        echo REM Redirects to agent-comm v2.0 bridge
        echo SET BRIDGE_DIR=%SCRIPT_DIR%core
        echo.
        echo where python ^>nul 2^>nul
        echo if %%errorlevel%% equ 0 ^(
        echo     python "%%BRIDGE_DIR%%\bridge_agent.py" %%*
        echo ^) else ^(
        echo     where python3 ^>nul 2^>nul
        echo     if %%errorlevel%% equ 0 ^(
        echo         python3 "%%BRIDGE_DIR%%\bridge_agent.py" %%*
        echo     ^) else ^(
        echo         echo {"error": "Python not found in PATH"}
        echo     ^)
        echo ^)
    ) > "%BRIDGE_ROOT%"
    echo  Created: %BRIDGE_ROOT%
) else (
    echo  E:\bridge.bat already exists, skipping.
)

REM Step 2: Ensure memories directory exists
SET MEM_DIR=%USERPROFILE%\.codeium\windsurf\memories
SET GLOBAL_RULES=%MEM_DIR%\global_rules.md
if not exist "%MEM_DIR%" (
    mkdir "%MEM_DIR%"
    echo  Created: %MEM_DIR%
)

REM Step 3: Backup existing global_rules.md
if exist "%GLOBAL_RULES%" (
    for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set dt=%%I
    set BACKUP=%GLOBAL_RULES%.backup_%dt:~0,8%_%dt:~8,6%
    copy "%GLOBAL_RULES%" "%GLOBAL_RULES%.backup" >nul 2>nul
    echo  Backup: %GLOBAL_RULES%.backup
)

REM Step 4: Write complete PRIORITY RULE
echo  Writing PRIORITY RULE to global_rules.md ...
(
    echo # PRIORITY RULE - agent-bridge ^(MANDATORY^)
    echo.
    echo **Every response must end with these 3 bridge calls:**
    echo.
    echo ### Step 1: Report activity
    echo ```
    echo E:\bridge.bat --activity --message "^<what you did^>" --source "^<project^>" --type "^<edit^|command^|build^|info^>" --details "^<files or commands^>"
    echo ```
    echo.
    echo ### Step 2: Report status
    echo ```
    echo E:\bridge.bat --notify --message "^<current task^>" --source "^<project^>" --phase "^<working^|waiting^|blocked^|idle^>" --progress "^<progress^>"
    echo ```
    echo.
    echo ### Step 3: Wait for instruction ^(blocking^)
    echo ```
    echo E:\bridge.bat --ask --message "^<short summary^>" --options "^<opt1^>,^<opt2^>,..."
    echo ```
    echo.
    echo ### Rules
    echo - All 3 calls must set SafeToAutoRun=true
    echo - --source: use current project name
    echo - --message: keep short ^(1-3 lines^)
    echo - --options: 2-4 dynamic options ^(comma separated^)
    echo - Must call all 3 steps every response, never skip
    echo - Wait for Step 3 JSON, execute user_input / selected_options
    echo - user_input has highest priority
    echo.
    echo ### Return fields ^(JSON^)
    echo - user_input: free text instruction ^(highest priority^)
    echo - selected_options: user selected options
    echo - cancelled: stop current work when true
    echo.
    echo Timeout auto-continues. Dashboard auto-starts if not running.
) > "%GLOBAL_RULES%"

echo.
echo  ============================================
echo  Setup complete!
echo  ============================================
echo.
echo  Bridge:  %BRIDGE_ROOT%
echo  Rules:   %GLOBAL_RULES%
echo  Dashboard: http://127.0.0.1:9901
echo.
echo  Next: restart Windsurf IDE for rules to take effect.
echo.
pause
