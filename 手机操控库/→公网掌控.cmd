@echo off
chcp 65001 >nul
title 手机公网掌控 · 道法自然
echo.
echo ══════════════════════════════════════════════
echo   📱 手机公网掌控 · 一键启动
echo ══════════════════════════════════════════════
echo.

cd /d "%~dp0"

:: 1. 启动手机端frpc (通过ADB)
echo [1/3] 启动手机端frpc直连阿里云...
D:\platform-tools\adb.exe -s 158377ff shell "su -c 'ps -A | grep frpc'" | findstr /i "frpc" >nul 2>&1
if %errorlevel% neq 0 (
    D:\platform-tools\adb.exe -s 158377ff shell "su -c 'nohup /data/data/com.tools.frp/files/bin/frpc -c /data/local/tmp/frpc_aliyun/frpc.toml > /data/local/tmp/frpc_aliyun/frpc.log 2>&1 &'"
    timeout /t 3 /nobreak >nul
    echo   ✅ 手机frpc已启动
) else (
    echo   ✅ 手机frpc已在运行
)

:: 2. 启动公网网关
echo [2/3] 启动公网网关(:28084)...
python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:28084/gw/health',timeout=2)" >nul 2>&1
if %errorlevel% neq 0 (
    start /min "PhoneGateway" python phone_gateway.py --no-auth --heartbeat 30
    timeout /t 3 /nobreak >nul
    echo   ✅ 网关已启动
) else (
    echo   ✅ 网关已在运行(health OK)
)

:: 3. 验证
echo [3/3] 验证连接...
python -c "import urllib.request,json; r=urllib.request.urlopen('http://127.0.0.1:28084/gw/health',timeout=3); d=json.loads(r.read().decode()); print(f'  手机: {d[\"active_path\"]} → {d[\"phone_status\"].get(\"connected\",\"?\")}'); print(f'  五感: inputEnabled={d[\"phone_status\"].get(\"inputEnabled\",\"?\")}')"

echo.
echo ══════════════════════════════════════════════
echo   公网访问路径:
echo   ① https://aiotvr.xyz/input/*  (Nginx→FRP→手机WiFi)
echo   ② http://60.205.171.100:38084 (手机FRP直连)
echo   ③ http://127.0.0.1:28084      (本地网关)
echo ══════════════════════════════════════════════
echo.
pause
