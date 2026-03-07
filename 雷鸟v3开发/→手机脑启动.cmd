@echo off
cd /d "%~dp0"
echo.
echo 道生一，一生二，二生三，三生万物
echo 手机=脑  眼镜=器  PC=梯（临时）
echo.
echo [步骤1] 请在手机Termux中运行:
echo   python ~/phone_server.py
echo.
echo [检查设备] wireless_config设备发现...
python wireless_config.py --detect
echo.
echo [步骤2] PC桥接层启动中...
python shou_ji_nao.py --run
pause
