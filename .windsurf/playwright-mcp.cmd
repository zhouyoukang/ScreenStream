@echo off
REM Playwright MCP: direct node execution (bypasses npx timeout)
REM --headless --isolated --browser chromium
node "%APPDATA%\npm\node_modules\@playwright\mcp\cli.js" --headless --isolated --browser chromium %*
