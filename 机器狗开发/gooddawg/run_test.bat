@echo off
echo 宇树Go1电机测试工具
echo ===========================================
echo.

REM 默认电机ID为4
set MOTOR_ID=4

REM 检查是否提供了电机ID参数
if not "%1"=="" (
    set MOTOR_ID=%1
)

echo 将使用电机ID: %MOTOR_ID%
echo 按任意键开始测试，或按Ctrl+C取消...
pause > nul

echo.
echo 开始测试...
python example_dead_simple.py %MOTOR_ID%

echo.
echo 测试完成
pause 