@echo off
echo 设置Python虚拟环境以测试Go1电机...
echo ===============================

REM 检查Python是否存在
where python > nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Python未安装或不在PATH中
    exit /b 1
)

REM 创建虚拟环境
echo 创建虚拟环境...
python -m venv go1_venv

REM 激活虚拟环境
echo 激活虚拟环境...
call go1_venv\Scripts\activate.bat

REM 安装必要的库
echo 安装必要的库...
pip install pyserial

echo 环境设置完成!
echo 可以使用 go1_venv\Scripts\activate.bat 来激活该环境

REM 保持命令窗口打开
cmd /k 