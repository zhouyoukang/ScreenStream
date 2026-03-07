#!/bin/bash

# MiGPT Home Assistant 集成 - 一键部署脚本 (Linux/Mac)

set -e

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "  MiGPT Home Assistant 集成 - 一键部署"
echo "========================================"
echo ""

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[错误] 未找到Python环境，请先安装Python3${NC}"
    exit 1
fi

echo -e "${GREEN}[1/5] 检查Home Assistant配置目录...${NC}"

# 检测Home Assistant配置目录
if [ -d "$HOME/.homeassistant" ]; then
    HA_CONFIG="$HOME/.homeassistant"
elif [ -d "/config" ]; then
    HA_CONFIG="/config"
else
    echo -e "${YELLOW}[提示] 未找到默认配置目录，请输入您的Home Assistant配置目录：${NC}"
    read -p "配置目录路径: " HA_CONFIG
fi

if [ ! -d "$HA_CONFIG" ]; then
    echo -e "${RED}[错误] 配置目录不存在: $HA_CONFIG${NC}"
    exit 1
fi

echo -e "${GREEN}[✓] 配置目录: $HA_CONFIG${NC}"
echo ""

echo -e "${GREEN}[2/5] 创建custom_components目录...${NC}"
if [ ! -d "$HA_CONFIG/custom_components" ]; then
    mkdir -p "$HA_CONFIG/custom_components"
    echo -e "${GREEN}[✓] 已创建custom_components目录${NC}"
else
    echo -e "${GREEN}[✓] custom_components目录已存在${NC}"
fi
echo ""

echo -e "${GREEN}[3/5] 备份现有xiaomi_mibot集成（如果存在）...${NC}"
if [ -d "$HA_CONFIG/custom_components/xiaomi_mibot" ]; then
    BACKUP_DIR="$HA_CONFIG/custom_components/xiaomi_mibot_backup_$(date +%Y%m%d_%H%M%S)"
    echo -e "${YELLOW}[提示] 发现现有xiaomi_mibot集成${NC}"
    mv "$HA_CONFIG/custom_components/xiaomi_mibot" "$BACKUP_DIR"
    echo -e "${GREEN}[✓] 已备份到: $BACKUP_DIR${NC}"
else
    echo -e "${GREEN}[✓] 无需备份${NC}"
fi
echo ""

echo -e "${GREEN}[4/5] 复制xiaomi_mibot集成文件...${NC}"
cp -r "config/custom_components/xiaomi_mibot" "$HA_CONFIG/custom_components/"
if [ $? -ne 0 ]; then
    echo -e "${RED}[错误] 文件复制失败${NC}"
    exit 1
fi
echo -e "${GREEN}[✓] 集成文件已复制${NC}"
echo ""

echo -e "${GREEN}[5/5] 验证安装...${NC}"
MISSING_FILES=0

if [ -f "$HA_CONFIG/custom_components/xiaomi_mibot/manifest.json" ]; then
    echo -e "${GREEN}[✓] manifest.json 存在${NC}"
else
    echo -e "${RED}[✗] manifest.json 缺失${NC}"
    MISSING_FILES=1
fi

if [ -f "$HA_CONFIG/custom_components/xiaomi_mibot/__init__.py" ]; then
    echo -e "${GREEN}[✓] __init__.py 存在${NC}"
else
    echo -e "${RED}[✗] __init__.py 缺失${NC}"
    MISSING_FILES=1
fi

if [ -f "$HA_CONFIG/custom_components/xiaomi_mibot/core/chatbot.py" ]; then
    echo -e "${GREEN}[✓] chatbot.py 存在${NC}"
else
    echo -e "${RED}[✗] chatbot.py 缺失${NC}"
    MISSING_FILES=1
fi

echo ""

if [ $MISSING_FILES -eq 1 ]; then
    echo "========================================"
    echo -e "  ${RED}✗ 安装失败${NC}"
    echo "========================================"
    echo ""
    echo "请检查："
    echo "1. 源文件是否完整"
    echo "2. 是否有足够的权限"
    echo "3. 路径是否正确"
    echo ""
    exit 1
fi

echo "========================================"
echo -e "  ${GREEN}✓ 安装完成！${NC}"
echo "========================================"
echo ""
echo "📋 下一步操作："
echo ""
echo "1. 重启 Home Assistant"
echo "   - Docker: docker restart homeassistant"
echo "   - 服务: sudo systemctl restart home-assistant"
echo "   - HAOS: 在界面中点击'重启'按钮"
echo ""
echo "2. 添加集成"
echo "   - 进入: 设置 → 设备与服务 → 添加集成"
echo "   - 搜索: Xiaomi MiBot 或 小米"
echo ""
echo "3. 配置集成（三步配置）"
echo "   - 步骤1: 输入小米账号和密码"
echo "   - 步骤2: 配置AI API密钥"
echo "   - 步骤3: 选择小爱音箱设备"
echo ""
echo "📖 详细使用指南:" 
echo "   查看 📖MiGPT使用指南_完整版.md"
echo ""
echo "🎯 快速测试:"
echo "   service: xiaomi_mibot.send_message"
echo "   data:"
echo "     message: '你好，MiGPT测试成功！'"
echo ""








