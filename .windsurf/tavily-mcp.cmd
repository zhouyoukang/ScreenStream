@echo off
REM Tavily MCP: Web search without VPN (China direct access)
REM Free tier: 1000 searches/month — https://app.tavily.com/
REM Auto-load from secrets.env if not set
if "%TAVILY_API_KEY%"=="" (
    for /f "tokens=1,* delims==" %%a in ('findstr /r "^TAVILY_API_KEY=" "D:\道\道生一\一生二\secrets.env" 2^>nul') do set "TAVILY_API_KEY=%%b"
)
if "%TAVILY_API_KEY%"=="" echo ERROR: Set TAVILY_API_KEY in secrets.env or env var (get free key at https://app.tavily.com/) && exit /b 1
node "%APPDATA%\npm\node_modules\tavily-mcp\build\index.js" %*
