@echo off
chcp 65001 > nul
echo ========================================
echo   MiGPT Home Assistant 集成 - 一键部署
echo ========================================
echo.

:: 检查Python环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到Python环境，请先安装Python
    pause
    exit /b 1
)

:: 设置颜色
color 0A

echo [1/5] 检查Home Assistant配置目录...
set "HA_CONFIG=%USERPROFILE%\.homeassistant"

if not exist "%HA_CONFIG%" (
    echo [提示] 未找到默认配置目录，请输入您的Home Assistant配置目录：
    set /p HA_CONFIG="配置目录路径: "
)

if not exist "%HA_CONFIG%" (
    echo [错误] 配置目录不存在: %HA_CONFIG%
    pause
    exit /b 1
)

echo [✓] 配置目录: %HA_CONFIG%
echo.

echo [2/5] 创建custom_components目录...
if not exist "%HA_CONFIG%\custom_components" (
    mkdir "%HA_CONFIG%\custom_components"
    echo [✓] 已创建custom_components目录
) else (
    echo [✓] custom_components目录已存在
)
echo.

echo [3/5] 备份现有xiaomi_mibot集成（如果存在）...
if exist "%HA_CONFIG%\custom_components\xiaomi_mibot" (
    set "BACKUP_DIR=%HA_CONFIG%\custom_components\xiaomi_mibot_backup_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
    set "BACKUP_DIR=%BACKUP_DIR: =0%"
    echo [提示] 发现现有xiaomi_mibot集成
    move "%HA_CONFIG%\custom_components\xiaomi_mibot" "!BACKUP_DIR!" >nul
    echo [✓] 已备份到: !BACKUP_DIR!
) else (
    echo [✓] 无需备份
)
echo.

echo [4/5] 复制xiaomi_mibot集成文件...
xcopy /E /I /Y "config\custom_components\xiaomi_mibot" "%HA_CONFIG%\custom_components\xiaomi_mibot\" >nul
if %errorlevel% neq 0 (
    echo [错误] 文件复制失败
    pause
    exit /b 1
)
echo [✓] 集成文件已复制
echo.

echo [5/5] 验证安装...
if exist "%HA_CONFIG%\custom_components\xiaomi_mibot\manifest.json" (
    echo [✓] manifest.json 存在
) else (
    echo [✗] manifest.json 缺失
    goto :error
)

if exist "%HA_CONFIG%\custom_components\xiaomi_mibot\__init__.py" (
    echo [✓] __init__.py 存在
) else (
    echo [✗] __init__.py 缺失
    goto :error
)

if exist "%HA_CONFIG%\custom_components\xiaomi_mibot\core\chatbot.py" (
    echo [✓] chatbot.py 存在
) else (
    echo [✗] chatbot.py 缺失
    goto :error
)

echo.
echo ========================================
echo   ✓ 安装完成！
echo ========================================
echo.
echo 📋 下一步操作：
echo.
echo 1. 重启 Home Assistant
echo    - 方式1: 在界面中点击"重启"按钮
echo    - 方式2: 使用命令 ha core restart
echo.
echo 2. 添加集成
echo    - 进入: 设置 → 设备与服务 → 添加集成
echo    - 搜索: Xiaomi MiBot 或 小米
echo.
echo 3. 配置集成（三步配置）
echo    - 步骤1: 输入小米账号和密码
echo    - 步骤2: 配置AI API密钥
echo    - 步骤3: 选择小爱音箱设备
echo.
echo 📖 详细使用指南: 
echo    查看 📖MiGPT使用指南_完整版.md
echo.
echo 🎯 快速测试:
echo    service: xiaomi_mibot.send_message
echo    data:
echo      message: "你好，MiGPT测试成功！"
echo.
pause
exit /b 0

:error
echo.
echo ========================================
echo   ✗ 安装失败
echo ========================================
echo.
echo 请检查：
echo 1. 源文件是否完整
echo 2. 是否有足够的权限
echo 3. 路径是否正确
echo.
pause
exit /b 1








