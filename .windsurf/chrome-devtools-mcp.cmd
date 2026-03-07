@echo off
REM Chrome DevTools MCP: direct node execution (bypasses npx timeout)
REM --isolated creates temporary profile, auto-cleaned on close
node "%APPDATA%\npm\node_modules\chrome-devtools-mcp\build\src\index.js" --isolated %*
