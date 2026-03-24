@echo off
chcp 65001 >nul 2>&1
echo.
echo ═══════════════════════════════════
echo   号池管理端 · 一推到底构建
echo ═══════════════════════════════════
echo.

cd /d "%~dp0"

echo [1/4] 安装依赖...
call npm install --silent 2>nul
if errorlevel 1 (
    echo   依赖已存在, 继续...
)

echo [2/4] 构建VSIX...
call npx vsce package --no-dependencies --allow-missing-repository --skip-license -o pool-admin.vsix
if errorlevel 1 (
    echo   ✗ 构建失败
    pause
    exit /b 1
)

echo [3/4] 安装到Windsurf...
if exist "D:\Windsurf\bin\windsurf.cmd" (
    call "D:\Windsurf\bin\windsurf.cmd" --install-extension pool-admin.vsix --force
    echo   ✓ 已安装
) else (
    echo   ✗ Windsurf未找到, 请手动安装: pool-admin.vsix
)

echo [4/4] 热部署到 ~/.pool-admin-hot/ ...
call node scripts/hot-deploy.js

echo.
echo ═══════════════════════════════════
echo   ✓ 完成! Ctrl+Shift+P → Restart Extension Host
echo ═══════════════════════════════════
echo.
