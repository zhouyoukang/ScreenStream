@echo off
cd /d "d:\道\道生一\一生二\电脑公网投屏手机"
echo Starting P2P server at %date% %time% > p2p_run.log
python -u desktop.py --direct --port 9803 >> p2p_run.log 2>&1
echo Exit code: %errorlevel% >> p2p_run.log
echo Server stopped at %date% %time% >> p2p_run.log
