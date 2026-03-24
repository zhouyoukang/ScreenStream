@echo off
chcp 65001 >nul
title 万法归宗 · 无感切号 v5.0
color 0A

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   万法归宗 v5.0 · 道法自然 · 注入即生效  ║
echo  ╚══════════════════════════════════════════╝
echo.
echo  [1] 一键部署 (hot+patch+verify, 推荐)
echo  [2] 热部署+监视     (npm run hot:watch)
echo  [3] 打包VSIX        (npm run package)
echo  [4] 堡垒混淆        (npm run fortress)
echo  [5] 透明代理启动     (→透明代理启动.cmd)
echo  [0] 退出
echo.
set /p choice=请选择: 

if "%choice%"=="1" (
    cd /d "%~dp0"
    echo.
    echo  === Step 1/2: workbench.js 补丁 ===
    python "%~dp0..\Windsurf无限额度\ws_repatch.py"
    echo.
    echo  === Step 2/2: 热部署 (双写+信号+自愈) ===
    call npm run hot
    echo.
    echo  万法归宗 · 完成
) else if "%choice%"=="2" (
    cd /d "%~dp0"
    call npm run hot:watch
) else if "%choice%"=="3" (
    cd /d "%~dp0"
    call npm run package
) else if "%choice%"=="4" (
    cd /d "%~dp0"
    call npm run fortress
) else if "%choice%"=="5" (
    call "%~dp0→透明代理启动.cmd"
) else if "%choice%"=="0" (
    exit /b
) else (
    echo 无效选择
)
pause
