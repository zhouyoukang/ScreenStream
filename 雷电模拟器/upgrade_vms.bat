@echo off
chcp 65001 >nul
echo ═══════════════════════════════════════════════
echo   雷电模拟器 VM配置升级脚本
echo   需要先停止所有VM再执行
echo ═══════════════════════════════════════════════
echo.

set DN=D:\leidian\LDPlayer9\dnconsole.exe

echo [1/6] 停止所有运行中的VM...
%DN% quitall
timeout /t 5 /nobreak >nul

echo [2/6] 升级 VM[0] 雷电模拟器 → 4核4GB 1080p
%DN% modify --index 0 --cpu 4 --memory 4096 --resolution 1080,1920,280
echo.

echo [3/6] 升级 VM[3] 开发测试1 → SS-投屏主控 2核2GB 720p Root
%DN% rename --index 3 --title "SS-投屏主控"
%DN% modify --index 3 --cpu 2 --memory 2048 --resolution 720,1280,320 --root 1
echo.

echo [4/6] 升级 VM[4] 开发测试2 → PWA-Web测试 2核2GB 720p
%DN% rename --index 4 --title "PWA-Web测试"
%DN% modify --index 4 --cpu 2 --memory 2048 --resolution 720,1280,320
echo.

echo [5/6] 升级 VM[5] 开发测试 → 采集-自动化 2核2GB 720p
%DN% rename --index 5 --title "采集-自动化"
%DN% modify --index 5 --cpu 2 --memory 2048 --resolution 720,1280,320
echo.

echo [6/6] 重新启动关键VM...
%DN% launch --index 0
timeout /t 3 /nobreak >nul
%DN% launch --index 3
timeout /t 3 /nobreak >nul
%DN% launch --index 4
timeout /t 3 /nobreak >nul
%DN% launch --index 5
timeout /t 10 /nobreak >nul

echo.
echo ═══════════════════════════════════════════════
echo   升级完成！验证:
echo ═══════════════════════════════════════════════
%DN% list2

echo.
echo 执行端口映射...
python "%~dp0ld_manager.py" --ports setup

echo.
echo 健康检查...
python "%~dp0ld_manager.py" --health

pause
