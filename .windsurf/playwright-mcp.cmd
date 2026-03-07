@echo off
REM ============================================================
REM Playwright MCP v4.1: Multi-Agent Isolation Edition
REM ============================================================
REM Architecture: Each Cascade gets its own STDIO process
REM   ? own Node.js ? own Chromium ? own BrowserContext
REM   ? CDP port auto-assigned (findFreePort)
REM   ? --isolated = temp profile (no disk state)
REM   ? --headless = no focus conflicts
REM ============================================================
REM Config: C:\temp\playwright-mcp-config.json
REM   - viewport 1280x720 (consistent rendering)
REM   - action timeout 10s (prevent stuck)
REM   - navigation timeout 30s
REM   - Chromium args: disable-gpu/dev-shm/sync/translate
REM ============================================================

node "%APPDATA%\npm\node_modules\@playwright\mcp\cli.js" --config "C:\temp\playwright-mcp-config.json" %*