@echo off
cd /d "%~dp0"
if not exist config.json (
    echo [ERROR] config.json not found. Create it from the template in README.md.
    pause
    exit /b 1
)
pip install -r requirements.txt -q
python gateway.py %*
pause
