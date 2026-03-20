@echo off
chcp 65001 >nul 2>&1
title Windsurf [PUBLIC CHAIN via aiotvr.xyz]

echo.
echo   ══════════════════════════════════════════
echo   Windsurf PUBLIC CHAIN Mode
echo   Route: Desktop → aiotvr.xyz:443 → FRP → Laptop CFW → Codeium
echo   ══════════════════════════════════════════
echo.

set SSL_CERT_FILE=C:\ProgramData\cfw_server_cert.pem
set NODE_EXTRA_CA_CERTS=C:\ProgramData\cfw_server_cert.pem
set NODE_TLS_REJECT_UNAUTHORIZED=0

:: 公网直连模式：--host-resolver-rules 将 windsurf 域名直接映射到 aiotvr.xyz 公网IP
:: 完全绕过本地 hosts 和 portproxy，模拟公网客户端行为
start "" "D:\Windsurf\Windsurf.exe" "--host-resolver-rules=MAP server.self-serve.windsurf.com 60.205.171.100,MAP server.codeium.com 60.205.171.100"

echo   Windsurf launched via PUBLIC chain (aiotvr.xyz)
echo.
