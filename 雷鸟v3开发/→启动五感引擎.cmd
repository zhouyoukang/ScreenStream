@echo off
cd /d "%~dp0"
echo.
echo [RayNeo V3] 设备发现(wireless_config)...
python wireless_config.py --detect
echo.
echo [RayNeo V3] 启动五感引擎...
python rayneo_五感.py --run
pause
