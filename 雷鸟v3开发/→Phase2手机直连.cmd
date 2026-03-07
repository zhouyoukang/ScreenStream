@echo off
cd /d "%~dp0"
echo.
echo ╔══════════════════════════════════════════════════╗
echo ║  Phase 2: 手机直连眼镜 (脱PC)                    ║
echo ║  将此脚本和 phone_relay.py 复制到手机Termux      ║
echo ╚══════════════════════════════════════════════════╝
echo.
echo 前置条件:
echo   1. 手机Termux已安装 python + android-tools
echo   2. phone_server.py 正在运行 (端口8765)
echo   3. 眼镜已连接家庭WiFi
echo.
echo 在Termux中运行:
echo   python phone_relay.py
echo.
echo 或指定眼镜IP:
echo   python phone_relay.py --glass-ip 192.168.31.116
echo.
echo [PC端测试] 下面在PC上模拟运行Phase 2...
python phone_relay.py --status
pause
