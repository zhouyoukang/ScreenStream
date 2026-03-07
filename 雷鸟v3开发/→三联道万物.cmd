@echo off
cd /d "%~dp0"
echo.
echo 道生一，一生二，二生三，三生万物
echo.
echo [检查三体] wireless_config设备发现...
python wireless_config.py --detect
echo.
echo [启动三联道]
python san_lian.py --run
pause
