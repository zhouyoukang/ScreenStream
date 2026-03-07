@echo off
REM GitHub MCP v3: direct node execution (bypasses npx to avoid NODE_OPTIONS infection)
REM Token loaded from environment variable GITHUB_PERSONAL_ACCESS_TOKEN
if "%GITHUB_PERSONAL_ACCESS_TOKEN%"=="" echo ERROR: Set GITHUB_PERSONAL_ACCESS_TOKEN env var first && exit /b 1

REM Pre-check: Clash proxy must be running for GitHub API access in China
REM Use PowerShell Test-NetConnection (fast, no external deps)
powershell -NoProfile -Command "exit ([int](-not (Test-NetConnection -ComputerName 127.0.0.1 -Port 7890 -WarningAction SilentlyContinue -InformationLevel Quiet)))"
if %ERRORLEVEL% NEQ 0 (
    REM Attempt auto-start Clash from known path
    if exist "D:\道\道生一\一生二\clash-agent\clash-meta.exe" (
        start "" /B "D:\道\道生一\一生二\clash-agent\clash-meta.exe" -f "D:\道\道生一\一生二\clash-agent\clash-config.yaml" -d "D:\道\道生一\一生二\clash-agent"
        timeout /t 3 /nobreak >nul
    )
)

REM Route through Clash proxy for GitHub API access
set HTTPS_PROXY=http://127.0.0.1:7890
set HTTP_PROXY=http://127.0.0.1:7890
REM Run server directly with proxy bootstrap (only this process gets fetch patch)
node --require "C:/temp/github-proxy-bootstrap.js" "%APPDATA%\npm\node_modules\@modelcontextprotocol\server-github\dist\index.js" %*
