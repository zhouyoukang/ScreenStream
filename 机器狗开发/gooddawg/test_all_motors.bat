@echo off
echo 宇树Go1电机测试工具 - 测试所有电机
echo ===========================================
echo.

echo 此脚本将依次测试电机ID 0-12
echo 每个电机测试10秒，可随时按Ctrl+C终止
echo.
echo 按任意键开始测试，或关闭窗口取消...
pause > nul

for /L %%i in (0,1,12) do (
    echo.
    echo ===========================================
    echo 测试电机ID: %%i
    echo ===========================================
    
    REM 创建临时Python脚本
    echo import build_a_packet as bp > temp_test.py
    echo import time, math, sys >> temp_test.py
    echo. >> temp_test.py
    echo print("测试电机ID: %%i") >> temp_test.py
    echo ser = bp.configure_serial("COM5") >> temp_test.py
    echo start_time = time.time() >> temp_test.py
    echo try: >> temp_test.py
    echo     while time.time() - start_time < 10: >> temp_test.py
    echo         q = math.sin(time.time()*2)*0.2 >> temp_test.py
    echo         bp.send_packet(ser, bp.build_a_packet(id=%%i, q=q, dq=0.0, Kp=4, Kd=0.3, tau=0.0)) >> temp_test.py
    echo         bp.read_and_update_motor_data(ser) >> temp_test.py
    echo         print(f"\r时间: {time.time() - start_time:.1f}s, 位置: {q:.4f}", end="") >> temp_test.py
    echo         time.sleep(0.01) >> temp_test.py
    echo     print("\n电机测试完成") >> temp_test.py
    echo finally: >> temp_test.py
    echo     ser.close() >> temp_test.py
    
    REM 运行临时脚本
    python temp_test.py
    
    REM 删除临时脚本
    del temp_test.py
    
    echo.
    echo 电机ID %%i 测试完成
    echo 按任意键测试下一个电机，或按Ctrl+C终止...
    pause > nul
)

echo.
echo 所有电机测试完成
pause 