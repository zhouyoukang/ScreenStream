@echo off
cd /d "%~dp0"
echo.
echo ╔══════════════════════════════════════╗
echo ║  RayNeo V3 管理中枢 · 道统万物       ║
echo ╚══════════════════════════════════════╝
echo.
echo   HTTP: http://localhost:8800/
echo   WS:   ws://localhost:8801
echo.
echo [检查设备] wireless_config设备发现...
python wireless_config.py --detect
echo.
python rayneo_dashboard.py
pause
