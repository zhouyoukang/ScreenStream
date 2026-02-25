#!/bin/bash
###############################################################################
# Linux 远程桌面一键部署脚本 (xrdp + XFCE4)
#
# 目标：让 Windows 用户用 mstsc.exe 直连阿里云Linux，获得桌面体验
# 支持：Ubuntu 18/20/22/24, Debian 10/11/12, CentOS 7/8/9, Alibaba Cloud Linux
#
# 用法：
#   chmod +x xrdp-setup.sh
#   sudo ./xrdp-setup.sh
#
# 功能：安装XFCE4桌面 + xrdp + 中文支持 + 输入法 + fail2ban + 性能优化
###############################################################################

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${CYAN}[STEP]${NC} $1"; }
log_title() { echo -e "\n${BLUE}════════════════════════════════════════${NC}"; echo -e "${BLUE}  $1${NC}"; echo -e "${BLUE}════════════════════════════════════════${NC}\n"; }

# ====================== 权限检查 ======================
if [ "$EUID" -ne 0 ]; then
    log_error "请用 root 权限运行: sudo $0"
    exit 1
fi

# ====================== 检测发行版 ======================
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO_ID="$ID"; DISTRO_VERSION="$VERSION_ID"; DISTRO_NAME="$PRETTY_NAME"
    elif [ -f /etc/redhat-release ]; then
        DISTRO_ID="centos"; DISTRO_VERSION=$(grep -oP '\d+' /etc/redhat-release | head -1)
        DISTRO_NAME=$(cat /etc/redhat-release)
    else
        log_error "无法检测发行版"; exit 1
    fi

    case "$DISTRO_ID" in
        alinux|alibabacloud|aliyun) DISTRO_FAMILY="rhel" ;;
        centos|rhel|rocky|alma|fedora) DISTRO_FAMILY="rhel" ;;
        ubuntu|linuxmint|pop|debian) DISTRO_FAMILY="debian" ;;
        *) log_warn "未知发行版 $DISTRO_ID，尝试 debian 方式..."; DISTRO_FAMILY="debian" ;;
    esac

    log_info "检测到: $DISTRO_NAME (family=$DISTRO_FAMILY)"
}

# ====================== 环境诊断 ======================
get_server_info() {
    log_title "服务器环境诊断"

    PUBLIC_IP=$(curl -s --connect-timeout 5 http://ifconfig.me 2>/dev/null || \
                curl -s --connect-timeout 5 http://icanhazip.com 2>/dev/null || echo "未知")
    TOTAL_RAM=$(free -m | awk '/^Mem:/{print $2}')
    CPU_CORES=$(nproc)
    DISK_FREE=$(df -h / | awk 'NR==2{print $4}')

    echo "  公网 IP:    $PUBLIC_IP"
    echo "  CPU 核心:   $CPU_CORES"
    echo "  内存:       ${TOTAL_RAM}MB"
    echo "  磁盘剩余:   $DISK_FREE"
    echo "  发行版:     $DISTRO_NAME"
    echo ""

    [ "$TOTAL_RAM" -lt 1024 ] && log_warn "内存仅 ${TOTAL_RAM}MB，XFCE最低建议1GB，可能卡顿"

    DISK_FREE_MB=$(df -m / | awk 'NR==2{print $4}')
    if [ "$DISK_FREE_MB" -lt 3000 ]; then
        log_error "磁盘剩余不足3GB (当前 ${DISK_FREE})，需要约2-3GB空间"
        exit 1
    fi
}

# ====================== Debian/Ubuntu 系安装 ======================
install_debian() {
    log_step "更新包索引..."
    apt-get update -qq

    log_step "安装 XFCE4 桌面环境..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        xfce4 xfce4-goodies xfce4-terminal dbus-x11 x11-xserver-utils \
        --no-install-recommends

    log_step "安装 xrdp..."
    apt-get install -y xrdp

    log_step "安装中文支持..."
    apt-get install -y fonts-wqy-zenhei fonts-wqy-microhei fonts-noto-cjk locales im-config

    # 输入法
    if apt-cache show fcitx5 &>/dev/null; then
        apt-get install -y fcitx5 fcitx5-chinese-addons fcitx5-frontend-gtk3 2>/dev/null || \
        apt-get install -y fcitx fcitx-pinyin 2>/dev/null || log_warn "输入法安装失败"
    else
        apt-get install -y fcitx fcitx-pinyin 2>/dev/null || log_warn "输入法安装失败"
    fi

    log_step "安装常用工具..."
    apt-get install -y firefox-esr 2>/dev/null || apt-get install -y firefox 2>/dev/null || true
    apt-get install -y thunar mousepad xarchiver curl wget htop nano --no-install-recommends 2>/dev/null || true

    # 中文locale
    sed -i 's/# zh_CN.UTF-8 UTF-8/zh_CN.UTF-8 UTF-8/' /etc/locale.gen 2>/dev/null || true
    locale-gen zh_CN.UTF-8 2>/dev/null || true
    apt-get clean
}

# ====================== RHEL/CentOS 系安装 ======================
install_rhel() {
    if command -v dnf &>/dev/null; then PKG_MGR="dnf"; else PKG_MGR="yum"; fi
    $PKG_MGR install -y epel-release 2>/dev/null || true

    log_step "安装 XFCE4 桌面环境..."
    $PKG_MGR groupinstall -y "Xfce" 2>/dev/null || \
    $PKG_MGR install -y xfce4-session xfwm4 xfce4-panel xfdesktop xfce4-terminal thunar 2>/dev/null || \
    { log_error "XFCE安装失败"; $PKG_MGR groupinstall -y "MATE Desktop" 2>/dev/null || true; }

    log_step "安装 xrdp..."
    $PKG_MGR install -y xrdp

    log_step "安装中文支持..."
    $PKG_MGR install -y wqy-zenhei-fonts wqy-microhei-fonts google-noto-sans-cjk-fonts 2>/dev/null || true
    $PKG_MGR install -y ibus ibus-libpinyin 2>/dev/null || true
    $PKG_MGR install -y firefox curl wget htop nano 2>/dev/null || true
    localedef -i zh_CN -f UTF-8 zh_CN.UTF-8 2>/dev/null || true
    $PKG_MGR clean all 2>/dev/null || true
}

# ====================== 配置 xrdp ======================
configure_xrdp() {
    log_title "配置 xrdp 远程桌面服务"

    getent group ssl-cert &>/dev/null && usermod -aG ssl-cert xrdp

    # XFCE启动脚本
    if [ -f /etc/xrdp/startwm.sh ]; then
        cp /etc/xrdp/startwm.sh /etc/xrdp/startwm.sh.bak
        cat > /etc/xrdp/startwm.sh << 'STARTWM'
#!/bin/sh
if [ -r /etc/default/locale ]; then . /etc/default/locale; export LANG LANGUAGE; fi
unset DBUS_SESSION_BUS_ADDRESS
unset XDG_RUNTIME_DIR
export LANG=zh_CN.UTF-8
export LC_ALL=zh_CN.UTF-8
export GTK_IM_MODULE=fcitx
export QT_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
exec startxfce4
STARTWM
        chmod +x /etc/xrdp/startwm.sh
    fi

    # 优化xrdp配置
    if [ -f /etc/xrdp/xrdp.ini ]; then
        cp /etc/xrdp/xrdp.ini /etc/xrdp/xrdp.ini.bak
        sed -i 's/^max_bpp=.*/max_bpp=24/' /etc/xrdp/xrdp.ini
        sed -i 's/^xserverbpp=.*/xserverbpp=24/' /etc/xrdp/xrdp.ini
        sed -i 's/^port=.*/port=3389/' /etc/xrdp/xrdp.ini
        sed -i 's/^crypt_level=.*/crypt_level=high/' /etc/xrdp/xrdp.ini
    fi

    # 修复 PolicyKit 弹窗
    mkdir -p /etc/polkit-1/localauthority/50-local.d/
    cat > /etc/polkit-1/localauthority/50-local.d/45-allow-colord.pkla << 'POLKIT'
[Allow Colord all Users]
Identity=unix-user:*
Action=org.freedesktop.color-manager.create-device;org.freedesktop.color-manager.create-profile;org.freedesktop.color-manager.delete-device;org.freedesktop.color-manager.delete-profile;org.freedesktop.color-manager.modify-device;org.freedesktop.color-manager.modify-profile
ResultAny=no
ResultInactive=no
ResultActive=yes
POLKIT

    cat > /etc/polkit-1/localauthority/50-local.d/46-allow-update-repo.pkla << 'POLKIT2'
[Allow Package Management all Users]
Identity=unix-user:*
Action=org.freedesktop.packagekit.system-sources-refresh
ResultAny=no
ResultInactive=no
ResultActive=yes
POLKIT2

    systemctl enable xrdp
    systemctl restart xrdp

    if systemctl is-active --quiet xrdp; then
        log_info "xrdp 服务启动成功"
    else
        log_error "xrdp 启动失败！"; systemctl status xrdp --no-pager -l; exit 1
    fi
}

# ====================== 用户配置 ======================
setup_user() {
    log_title "用户配置"
    for HOME_DIR in /home/*/; do
        USERNAME=$(basename "$HOME_DIR")
        if id "$USERNAME" &>/dev/null; then
            echo "startxfce4" > "${HOME_DIR}/.xsession"
            chown "$USERNAME":"$USERNAME" "${HOME_DIR}/.xsession"
            chmod +x "${HOME_DIR}/.xsession"
            log_info "已为用户 $USERNAME 配置 XFCE 会话"
        fi
    done
    echo "startxfce4" > /root/.xsession && chmod +x /root/.xsession
    log_warn "xrdp 需要密码登录，如无密码请运行: sudo passwd <用户名>"
}

# ====================== 防火墙 ======================
configure_firewall() {
    log_title "防火墙配置"
    command -v ufw &>/dev/null && { ufw allow 3389/tcp comment "xrdp"; ufw allow 22/tcp comment "SSH"; }
    command -v firewall-cmd &>/dev/null && systemctl is-active --quiet firewalld && \
        { firewall-cmd --permanent --add-port=3389/tcp; firewall-cmd --reload; }
    command -v iptables &>/dev/null && ! iptables -L INPUT -n | grep -q "3389" && \
        iptables -I INPUT -p tcp --dport 3389 -j ACCEPT 2>/dev/null || true

    log_warn "重要！请在阿里云控制台开放安全组: TCP 3389"
}

# ====================== 安全加固 ======================
security_hardening() {
    log_title "安全加固"
    if [ "$DISTRO_FAMILY" = "debian" ]; then
        apt-get install -y fail2ban 2>/dev/null || log_warn "fail2ban安装失败"
    else
        $PKG_MGR install -y fail2ban 2>/dev/null || log_warn "fail2ban安装失败"
    fi

    if command -v fail2ban-client &>/dev/null; then
        cat > /etc/fail2ban/jail.d/xrdp.conf << 'JAIL'
[xrdp]
enabled = true
port = 3389
filter = xrdp
logpath = /var/log/xrdp.log
maxretry = 5
bantime = 3600
findtime = 600
JAIL
        cat > /etc/fail2ban/filter.d/xrdp.conf << 'FILTER'
[Definition]
failregex = .*xrdp_mm_process_login_response.*login failed for user.*from <HOST>
ignoreregex =
FILTER
        systemctl enable fail2ban 2>/dev/null; systemctl restart fail2ban 2>/dev/null
        log_info "fail2ban 已启用"
    fi
}

# ====================== 性能优化 ======================
optimize_performance() {
    log_title "性能优化"
    for svc in cups cups-browsed avahi-daemon bluetooth ModemManager; do
        systemctl disable "$svc" 2>/dev/null; systemctl stop "$svc" 2>/dev/null
    done || true

    mkdir -p /etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/
    cat > /etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml << 'XFWM'
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfwm4" version="1.0">
  <property name="general" type="empty">
    <property name="use_compositing" type="bool" value="false"/>
    <property name="box_move" type="bool" value="true"/>
    <property name="box_resize" type="bool" value="true"/>
    <property name="cycle_draw_frame" type="bool" value="false"/>
    <property name="theme" type="string" value="Default"/>
  </property>
</channel>
XFWM
    [ -f /etc/xrdp/sesman.ini ] && sed -i 's/^LogLevel=.*/LogLevel=WARNING/' /etc/xrdp/sesman.ini 2>/dev/null
    log_info "已禁用桌面特效以提升远程体验"
}

# ====================== 完成信息 ======================
print_info() {
    log_title "安装完成！"
    echo -e "${GREEN}连接方法: Win+R → mstsc → ${PUBLIC_IP}:3389${NC}"
    echo ""
    echo "  xrdp:  $(systemctl is-active xrdp)"
    echo "  端口:  $(ss -tlnp | grep 3389 | awk '{print $4}' | head -1 || echo '未监听')"
    echo ""
    echo "  设密码: sudo passwd <用户名>"
    echo "  查日志: sudo journalctl -u xrdp -n 50"
    echo "  重启:   sudo systemctl restart xrdp"
    echo ""
    log_warn "确保阿里云安全组已开放 TCP 3389！"
}

# ====================== 主流程 ======================
main() {
    log_title "Linux 远程桌面一键部署 (xrdp + XFCE4)"
    detect_distro
    get_server_info
    [ "$DISTRO_FAMILY" = "debian" ] && install_debian || install_rhel
    configure_xrdp
    setup_user
    configure_firewall
    security_hardening
    optimize_performance
    print_info
}

main "$@"
