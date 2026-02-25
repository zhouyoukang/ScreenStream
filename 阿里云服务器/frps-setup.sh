#!/bin/bash
# FRP Server 一键安装脚本 — 粘贴到阿里云ECS网页终端执行
# ECS: 60.205.171.100 (华北2北京, Ubuntu 24.04)
#
# 用法：
#   bash frps-setup.sh                          # 使用默认密码
#   bash frps-setup.sh --token MyToken123       # 自定义FRP认证Token
#   bash frps-setup.sh --dashboard-pwd MyPwd    # 自定义控制台密码

set -e

# ====================== 参数解析 ======================
FRP_VERSION="0.61.1"
FRP_TOKEN="${FRP_TOKEN:-请替换为你的FRP认证Token}"
FRP_DASHBOARD_PWD="${FRP_DASHBOARD_PWD:-请替换为控制台密码}"
SSH_PUBKEY="${SSH_PUBKEY:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --token) FRP_TOKEN="$2"; shift 2 ;;
        --dashboard-pwd) FRP_DASHBOARD_PWD="$2"; shift 2 ;;
        --ssh-key) SSH_PUBKEY="$2"; shift 2 ;;
        --version) FRP_VERSION="$2"; shift 2 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

# 检查占位符
if [[ "$FRP_TOKEN" == *"请替换"* ]]; then
    echo "错误：请设置FRP Token"
    echo "  方式1: export FRP_TOKEN='你的密码' && bash frps-setup.sh"
    echo "  方式2: bash frps-setup.sh --token '你的密码'"
    exit 1
fi

echo "============================================"
echo "  FRP Server 一键安装"
echo "  版本: $FRP_VERSION"
echo "============================================"

# ====================== SSH公钥 ======================
if [ -n "$SSH_PUBKEY" ]; then
    echo "=== Step 1: 添加SSH公钥 ==="
    mkdir -p ~/.ssh && chmod 700 ~/.ssh
    grep -qF "$SSH_PUBKEY" ~/.ssh/authorized_keys 2>/dev/null || echo "$SSH_PUBKEY" >> ~/.ssh/authorized_keys
    chmod 600 ~/.ssh/authorized_keys
    echo "SSH公钥已添加"
else
    echo "=== Step 1: 跳过SSH公钥（未提供） ==="
fi

# ====================== 下载FRP ======================
echo "=== Step 2: 下载FRP $FRP_VERSION ==="
cd /opt
if [ ! -f "frp_${FRP_VERSION}_linux_amd64.tar.gz" ]; then
    # 优先国内镜像，失败则GitHub
    wget -q "https://ghfast.top/https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_amd64.tar.gz" 2>/dev/null \
    || wget -q "https://mirror.ghproxy.com/https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_amd64.tar.gz" 2>/dev/null \
    || wget -q "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_amd64.tar.gz"
fi
tar xzf "frp_${FRP_VERSION}_linux_amd64.tar.gz"
ln -sfn "/opt/frp_${FRP_VERSION}_linux_amd64" /opt/frp
echo "FRP已下载到 /opt/frp"

# ====================== 配置frps ======================
echo "=== Step 3: 配置frps ==="
cat > /opt/frp/frps.toml << EOF
bindPort = 7000

webServer.addr = "0.0.0.0"
webServer.port = 7500
webServer.user = "admin"
webServer.password = "${FRP_DASHBOARD_PWD}"

auth.method = "token"
auth.token = "${FRP_TOKEN}"

# TLS加密（建议开启）
transport.tls.force = false

# 日志
log.to = "/var/log/frps.log"
log.level = "info"
log.maxDays = 7
EOF
echo "frps.toml已配置"

# ====================== systemd服务 ======================
echo "=== Step 4: 创建systemd服务 ==="
cat > /etc/systemd/system/frps.service << 'EOF'
[Unit]
Description=FRP Server
After=network.target

[Service]
Type=simple
ExecStart=/opt/frp/frps -c /opt/frp/frps.toml
Restart=always
RestartSec=5
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable frps
systemctl start frps
echo "frps服务已启动"

# ====================== 验证 ======================
echo "=== Step 5: 验证 ==="
sleep 2
systemctl status frps --no-pager -l
echo ""
echo "============================================"
PUBLIC_IP=$(curl -s --connect-timeout 5 http://ifconfig.me 2>/dev/null || echo "60.205.171.100")
echo "FRP Server 安装完成！"
echo "  公网IP:     $PUBLIC_IP"
echo "  绑定端口:   7000"
echo "  控制台:     http://$PUBLIC_IP:7500"
echo "  控制台账号: admin"
echo ""
echo "下一步：在家里电脑配置 frpc.toml 并启动 frpc"
echo "============================================"
