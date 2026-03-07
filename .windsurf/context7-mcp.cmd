@echo off
REM Context7 MCP: direct node execution (bypasses npx timeout)
node "%APPDATA%\npm\node_modules\@upstash\context7-mcp\dist\index.js" %*
