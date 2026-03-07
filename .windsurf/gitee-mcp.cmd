@echo off
REM Gitee MCP: GitHub alternative without VPN (China direct access)
REM 29 tools: repos, PRs, issues, users, notifications
REM Get token: https://gitee.com/profile/personal_access_tokens
REM Auto-load from secrets.env if not set
if "%GITEE_ACCESS_TOKEN%"=="" (
    for /f "tokens=1,* delims==" %%a in ('findstr /r "^GITEE_ACCESS_TOKEN=" "D:\道\道生一\一生二\secrets.env" 2^>nul') do set "GITEE_ACCESS_TOKEN=%%b"
)
if "%GITEE_ACCESS_TOKEN%"=="" echo ERROR: Set GITEE_ACCESS_TOKEN in secrets.env or env var (get token at https://gitee.com/profile/personal_access_tokens) && exit /b 1
node "%APPDATA%\npm\node_modules\@gitee\mcp-gitee\bin\index.js" %*
