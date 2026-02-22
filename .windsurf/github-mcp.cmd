@echo off
REM Token loaded from environment variable GITHUB_PERSONAL_ACCESS_TOKEN
if "%GITHUB_PERSONAL_ACCESS_TOKEN%"=="" echo ERROR: Set GITHUB_PERSONAL_ACCESS_TOKEN env var first && exit /b 1
npx -y @modelcontextprotocol/server-github %*
