@echo off
cd /d "%~dp0"
if not exist .env (
    echo [ERROR] .env not found. Copy .env.example to .env and fill in your tokens.
    pause
    exit /b 1
)
pip install -r requirements.txt -q
python gateway.py
pause
