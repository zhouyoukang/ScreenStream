@echo off
REM ============================================================
REM Agent-Comm: One-click setup for any Windsurf IDE instance
REM Run this script to connect your IDE to the central Dashboard
REM ============================================================

SET SCRIPT_DIR=%~dp0
SET RULES_TEMPLATE=%SCRIPT_DIR%config\agent_rules_template.md
SET BRIDGE_PATH=%SCRIPT_DIR%core\bridge.bat

echo.
echo  Agent-Comm Setup
echo  ================
echo.
echo  This will configure your Windsurf IDE to connect to the
echo  central Agent Dashboard for multi-agent orchestration.
echo.
echo  Bridge path: %BRIDGE_PATH%
echo.

REM Check if global_rules.md exists
SET GLOBAL_RULES=%USERPROFILE%\.codeium\windsurf\memories\global_rules.md
if not exist "%USERPROFILE%\.codeium\windsurf\memories" (
    mkdir "%USERPROFILE%\.codeium\windsurf\memories"
)

REM Generate the PRIORITY RULE with actual bridge path
echo # PRIORITY RULE - agent-bridge (MANDATORY) > "%GLOBAL_RULES%.agent-comm"
echo. >> "%GLOBAL_RULES%.agent-comm"
echo **Every response must end with a bridge call:** >> "%GLOBAL_RULES%.agent-comm"
echo. >> "%GLOBAL_RULES%.agent-comm"
echo ``` >> "%GLOBAL_RULES%.agent-comm"
echo %BRIDGE_PATH% --ask --message "<summary>" --options "<opt1>,<opt2>,..." >> "%GLOBAL_RULES%.agent-comm"
echo ``` >> "%GLOBAL_RULES%.agent-comm"
echo. >> "%GLOBAL_RULES%.agent-comm"
echo Rules: SafeToAutoRun=true, --message short, --options 2-4 items >> "%GLOBAL_RULES%.agent-comm"
echo Wait for JSON response, execute user_input or selected_options >> "%GLOBAL_RULES%.agent-comm"

echo.
echo  Generated: %GLOBAL_RULES%.agent-comm
echo.
echo  To activate, append this content to your global_rules.md:
echo    type "%GLOBAL_RULES%.agent-comm" >> "%GLOBAL_RULES%"
echo.
echo  Or review it first:
echo    notepad "%GLOBAL_RULES%.agent-comm"
echo.
pause
