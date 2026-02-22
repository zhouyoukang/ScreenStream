@echo off
cd /d "%~dp0"
echo ============================================
echo  Smart Home Gateway + WeChat + Tunnel
echo ============================================

if not exist config.json (
    echo [ERROR] config.json not found.
    pause
    exit /b 1
)

pip install -r requirements.txt -q 2>nul

echo.
echo [1/2] Starting Gateway on port 8900...
start "Gateway" cmd /c "python gateway.py --port 8900"
timeout /t 5 /nobreak >nul

echo [2/2] Starting Cloudflare Tunnel...
echo     (Wait for public URL to appear below)
echo.
cloudflared tunnel --url http://localhost:8900
pause
