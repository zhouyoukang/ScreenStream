@echo off
chcp 65001 >nul
echo ========================================
echo   语音唤醒服务启动脚本
echo   Home Assistant Voice Wake Services
echo ========================================
echo.

set DOCKER="C:\Program Files\Docker\Docker\resources\bin\docker.exe"

echo [1/5] 检查 Docker 服务状态...
%DOCKER% info >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker 未运行，请先启动 Docker Desktop
    pause
    exit /b 1
)
echo ✅ Docker 正在运行

echo.
echo [2/5] 启动 Whisper 语音识别服务 (端口 10300)...
%DOCKER% start romantic_colden 2>nul
if errorlevel 1 (
    echo ⚠️ romantic_colden 容器不存在或启动失败，尝试创建新容器...
    %DOCKER% run -d --name wyoming-whisper-main -p 10300:10300 ^
        --restart unless-stopped ^
        -v "D:\homeassistant\wyoming-data:/data" ^
        rhasspy/wyoming-whisper --model small --language zh
) else (
    echo ✅ Whisper 主服务已启动 (romantic_colden)
)

echo.
echo [3/5] 启动 Whisper 备用服务 (端口 10310)...
%DOCKER% start kind_knuth 2>nul
if errorlevel 1 (
    echo ⚠️ kind_knuth 启动失败
) else (
    echo ✅ Whisper 备用服务已启动 (kind_knuth)
)

echo.
echo [4/5] 启动 OpenWakeWord 唤醒词检测服务...
%DOCKER% start custom_wake 2>nul
echo ✅ custom_wake (端口 10400)
%DOCKER% start wake_zh 2>nul
echo ✅ wake_zh (端口 10443)

echo.
echo [5/5] 启动 Piper TTS 语音合成服务 (端口 10200)...
%DOCKER% start vibrant_hamilton 2>nul
if errorlevel 1 (
    echo ⚠️ vibrant_hamilton 启动失败
) else (
    echo ✅ Piper TTS 已启动
)

echo.
echo ========================================
echo   服务状态检查
echo ========================================
timeout /t 5 /nobreak >nul

echo.
echo 正在运行的语音服务:
%DOCKER% ps --filter "name=romantic_colden" --filter "name=kind_knuth" --filter "name=custom_wake" --filter "name=wake_zh" --filter "name=vibrant_hamilton" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo.
echo ========================================
echo   下一步操作
echo ========================================
echo.
echo 如果 Home Assistant 中语音识别不工作，请：
echo 1. 打开 HA → 设置 → 设备与服务 → 添加集成
echo 2. 搜索 "Wyoming" 并添加
echo 3. 添加以下服务：
echo    - Whisper STT: 192.168.31.141:10300
echo    - OpenWakeWord: 192.168.31.141:10400 (已配置)
echo    - OpenWakeWord: 192.168.31.141:10443 (已配置)
echo    - Piper TTS: 192.168.31.141:10200 (可选)
echo.
echo 4. 然后在 设置 → 语音助手 中配置管道
echo.
pause
