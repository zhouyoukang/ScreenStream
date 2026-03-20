@echo off
chcp 65001 >nul
echo ============================================================
echo  WU 一键修复 v1.0
echo  修复: hosts + CA证书 + WU代理 + Windsurf配置
echo ============================================================
echo.

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] 需要管理员权限，正在提权...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~f0\"' -Verb RunAs"
    exit /b
)

echo [1/5] 修复 hosts...
findstr /c:"127.65.43.21 server.self-serve.windsurf.com" %windir%\System32\drivers\etc\hosts >nul 2>&1
if %errorLevel% neq 0 (
    echo 127.65.43.21 server.self-serve.windsurf.com>> %windir%\System32\drivers\etc\hosts
    echo   + server.self-serve.windsurf.com
)
findstr /c:"127.65.43.21 server.codeium.com" %windir%\System32\drivers\etc\hosts >nul 2>&1
if %errorLevel% neq 0 (
    echo 127.65.43.21 server.codeium.com>> %windir%\System32\drivers\etc\hosts
    echo   + server.codeium.com
)
ipconfig /flushdns >nul
echo   DNS已刷新

echo [2/5] 安装 CA 证书...
if exist "%APPDATA%\windsurf-unlimited\certs\ca.crt" (
    certutil -addstore Root "%APPDATA%\windsurf-unlimited\certs\ca.crt" >nul 2>&1
    echo   MITM CA已安装
) else (
    echo   [!] CA证书文件不存在
)

echo [3/5] 检查 WU 代理...
tasklist /fi "IMAGENAME eq WindsurfUnlimited.exe" /fo csv /nh | findstr /i "WindsurfUnlimited" >nul 2>&1
if %errorLevel% neq 0 (
    echo   WU未运行，正在启动...
    start "" "%LOCALAPPDATA%\Programs\WindsurfUnlimited\WindsurfUnlimited.exe"
    timeout /t 8 /nobreak >nul
    echo   WU已启动
) else (
    echo   WU已运行
)

echo [4/5] 修复 Windsurf 配置...
python -c "import json;p=r'%APPDATA%\Windsurf\User\settings.json';s=json.load(open(p));c=False;exec('if s.get(\"http.proxyStrictSSL\")!=False:s[\"http.proxyStrictSSL\"]=False;c=True');exec('if s.get(\"http.proxySupport\")!=\"off\":s[\"http.proxySupport\"]=\"off\";c=True');open(p,'w').write(json.dumps(s,indent=2));print('  配置已修复' if c else '  配置已正确')" 2>nul || echo   [!] Python不可用

echo [5/5] 运行 E2E 验证...
python "e:\道\道生一\一生二\Windsurf无限额度\wu_guardian.py" --e2e 2>nul || echo   [!] E2E测试失败

echo.
echo ============================================================
echo  修复完成! 如仍有问题请运行:
echo  python wu_guardian.py --fix
echo  python wu_guardian.py --daemon
echo ============================================================
pause
