@echo off
chcp 65001 >nul
title VAM-agent 统一启动器
color 0A

echo ════════════════════════════════════════════════════════════
echo     VAM-agent 统一启动器 (修正版 2026-03-04)
echo ════════════════════════════════════════════════════════════
echo.

set "VAM_ROOT=F:\vam1.22"
set "VAM_EXE=%VAM_ROOT%\VAM版本\vam1.22.1.0\VaM.exe"
set "VOXTA_EXE=%VAM_ROOT%\Voxta\Active\Voxta.DesktopApp.exe"
set "TEXTGEN_DIR=%VAM_ROOT%\text-generation-webui"
set "EDGETTS_SCRIPT=%VAM_ROOT%\EdgeTTS\voxta_edge_tts_server.py"

echo 启动顺序: EdgeTTS → TextGen → Voxta → VaM
echo.

:: ── Step 1: EdgeTTS Server (端口5050) ──
echo [1/4] 启动 Edge-TTS 服务器...
if exist "%EDGETTS_SCRIPT%" (
    start "EdgeTTS" /min cmd /k "cd /d %VAM_ROOT%\EdgeTTS && python voxta_edge_tts_server.py"
    echo   ✓ EdgeTTS → http://localhost:5050
    timeout /t 3 >nul
) else (
    echo   ✗ 跳过: 未找到 %EDGETTS_SCRIPT%
)

:: ── Step 2: Text Generation WebUI (端口7860 + API 5000) ──
echo [2/4] 启动 Text Generation WebUI...
if exist "%TEXTGEN_DIR%\start_windows.bat" (
    start "TextGen" cmd /k "cd /d %TEXTGEN_DIR% && start_windows.bat"
    echo   ✓ TextGen → http://localhost:7860 (API: :5000)
    echo   ⏳ 等待模型加载 (约30-60秒)...
    timeout /t 10 >nul
) else (
    echo   ✗ 跳过: 未找到 text-generation-webui
)

:: ── Step 3: Voxta (端口5384) ──
echo [3/4] 启动 Voxta AI 引擎...
if exist "%VOXTA_EXE%" (
    start "Voxta" "%VOXTA_EXE%"
    echo   ✓ Voxta → http://localhost:5384
    timeout /t 5 >nul
) else (
    echo   ✗ 跳过: 未找到 Voxta
    echo   ⚠ 旧路径 Voxta相关\voxta1.42 已失效, 正确路径: Voxta\Active\
)

:: ── Step 4: VaM (可选) ──
echo [4/4] 启动 VaM...
if exist "%VAM_EXE%" (
    choice /C YN /T 10 /D Y /M "  是否启动VaM? (Y=启动, N=跳过, 10秒后自动启动)"
    if errorlevel 2 (
        echo   ⊘ 跳过 VaM
    ) else (
        start "" "%VAM_EXE%"
        echo   ✓ VaM 已启动
    )
) else (
    echo   ✗ 跳过: 未找到 VaM.exe
)

echo.
echo ════════════════════════════════════════════════════════════
echo   服务地址:
echo     EdgeTTS:  http://localhost:5050/health
echo     TextGen:  http://localhost:7860
echo     Voxta:    http://localhost:5384
echo     VaM:      桌面应用
echo ════════════════════════════════════════════════════════════
echo.
echo   集成链路: VaM ←→ Voxta ←→ TextGen/EdgeTTS
echo   Voxta配置: 在Voxta Web UI中设置LLM指向 http://localhost:5000/v1/
echo              TTS指向 http://localhost:5050/v1/audio/speech
echo.
pause
