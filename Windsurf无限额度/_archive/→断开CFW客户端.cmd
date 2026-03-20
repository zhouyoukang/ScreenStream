@echo off
chcp 65001 >nul 2>&1
title CFW Client Disconnect + Official Mode
color 0C

echo.
echo   CFW Client Disconnect (Desktop 141)
echo   Remove portproxy + hosts -> Official Windsurf mode
echo.

:: 1. Remove portproxy
echo   [1/3] Remove portproxy...
netsh interface portproxy delete v4tov4 listenaddress=127.0.0.1 listenport=443 >nul 2>&1
echo   OK: portproxy removed

:: 2. Remove hosts entries (so DNS resolves to real Codeium servers)
echo   [2/3] Clean hosts...
powershell -NoProfile -Command "$h='C:\Windows\System32\drivers\etc\hosts';$c=Get-Content $h -Raw;$c=$c -replace '(?m)^\s*127\.0\.0\.1\s+server\.self-serve\.windsurf\.com\s*$\r?\n?','';$c=$c -replace '(?m)^\s*127\.0\.0\.1\s+server\.codeium\.com\s*$\r?\n?','';$c=$c -replace '(?s)\r?\n?# >>> CFW-MANAGED-START.*?# <<< CFW-MANAGED-END\r?\n?','';[IO.File]::WriteAllText($h,$c,[Text.UTF8Encoding]::new($false));Write-Host '  OK: hosts cleaned'"

:: 3. Clear env vars (session only - Machine level unchanged for easy re-enable)
echo   [3/3] Clear session env...
set SSL_CERT_FILE=
set NODE_EXTRA_CA_CERTS=
set NODE_TLS_REJECT_UNAUTHORIZED=
echo   OK: session env cleared

echo.
echo   ══════════════════════════════════════════
echo   Official mode ready!
echo   Launch Windsurf DIRECTLY (no Windsurf_Proxy.cmd):
echo     D:\Windsurf\Windsurf.exe
echo.
echo   Re-connect CFW: run CFW-Client-ON.cmd
echo   ══════════════════════════════════════════
echo.
pause
