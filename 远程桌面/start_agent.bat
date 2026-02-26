@echo off
chcp 65001 >nul
netstat -ano | findstr ":9903.*LISTENING" >nul 2>&1
if %ERRORLEVEL%==0 (
    echo remote_agent already running, skipping
    exit /b 0
)
cd /d E:\道\道生一\一生二\远程桌面
start /b "" python remote_agent.py --port 9903
echo remote_agent started
