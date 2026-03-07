# 手机软路由 — Android手机作为VPN网关共享翻墙

> 将Android手机变成软路由/VPN网关，让连接热点的所有设备自动走代理翻墙上网。

## 目录

- [核心概念](#核心概念)
- [方案总览](#方案总览)
- [方案一：Root + box4magisk（推荐·最强）](#方案一root--box4magisk推荐最强)
- [方案二：Root + VPNHotspot](#方案二root--vpnhotspot)
- [方案三：免Root + HTTP/SOCKS代理服务器](#方案三免root--httpsocks代理服务器)
- [方案四：免Root + Clash/sing-box + 手动代理](#方案四免root--clashsing-box--手动代理)
- [方案五：免Root + tun2socks + Wi-Fi Direct](#方案五免root--tun2socks--wi-fi-direct)
- [方案六：USB Tethering + 电脑中转](#方案六usb-tethering--电脑中转)
- [方案七：WireGuard旅行路由器模式](#方案七wireguard旅行路由器模式)
- [工具生态全景](#工具生态全景)
- [GitHub开源项目索引](#github开源项目索引)
- [硬件需求与兼容性](#硬件需求与兼容性)
- [问题诊断与解决](#问题诊断与解决)
- [安全与法律风险](#安全与法律风险)
- [我的环境适配](#我的环境适配)

---

## 核心概念

### 为什么手机热点不自动共享VPN？

Android系统设计上，**热点流量走独立的网络栈**，不经过VPN的TUN虚拟网卡。这是Google有意为之的安全设计：

```
正常流程:
  手机App → TUN(VPN) → 代理服务器 → 互联网  ✅ 走VPN

热点流量:
  连接设备 → Wi-Fi热点接口(ap0/wlan1) → 移动数据(rmnet0) → 互联网  ❌ 绕过VPN
```

### 解决思路

| 思路 | 原理 | 需要Root |
|------|------|---------|
| **iptables/nftables转发** | 将热点接口流量强制路由到TUN | ✅ |
| **透明代理** | 在内核层拦截所有流量转发到代理 | ✅ |
| **代理服务器** | 手机开HTTP/SOCKS服务，客户端手动配代理 | ❌ |
| **Wi-Fi Direct隧道** | tun2socks建立隧道绕过热点限制 | ❌ |
| **USB网络共享+电脑** | 手机VPN流量通过USB共享给电脑 | ❌ |

---

## 方案总览

| # | 方案 | Root | 难度 | 透明度 | 稳定性 | 推荐度 |
|---|------|------|------|--------|--------|--------|
| 1 | **box4magisk** (sing-box/clash/xray) | ✅ | ⭐⭐⭐ | 全透明 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 2 | **VPNHotspot** (iptables转发) | ✅ | ⭐⭐ | 全透明 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 3 | **Every Proxy/Postern** (代理服务器) | ❌ | ⭐ | 需手动配 | ⭐⭐⭐ | ⭐⭐⭐ |
| 4 | **Clash/sing-box + 局域网代理** | ❌ | ⭐⭐ | 需手动配 | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| 5 | **tun2socks + Wi-Fi Direct** | ❌ | ⭐⭐⭐⭐ | 全透明 | ⭐⭐ | ⭐⭐ |
| 6 | **USB Tethering + 电脑** | ❌ | ⭐⭐ | 半透明 | ⭐⭐⭐ | ⭐⭐ |
| 7 | **WireGuard旅行路由器** | ❌ | ⭐⭐⭐ | 全透明 | ⭐⭐⭐⭐ | ⭐⭐⭐ |

---

## 方案一：Root + box4magisk（推荐·最强）

### 概述
在Root后的Android设备上运行 sing-box/clash/v2ray/xray 作为**系统级透明代理**，所有流量（包括热点流量）自动走代理。

### 项目信息
- **GitHub**: [CHIZI-0618/box4magisk](https://github.com/CHIZI-0618/box4magisk)
- **描述**: Use sing-box, clash, v2ray, xray tunnel proxy on Android devices
- **支持内核**: sing-box / clash.meta / v2ray / xray
- **原理**: Magisk模块 + iptables/nftables TPROXY透明代理

### 前置条件
1. 手机已解锁Bootloader
2. 已刷入 **Magisk** (推荐 v26.0+) 或 **KernelSU**
3. 有可用的代理节点配置

### 安装步骤
```bash
# 1. 下载box4magisk模块zip
# GitHub Releases: https://github.com/CHIZI-0618/box4magisk/releases

# 2. Magisk Manager → 模块 → 从本地安装 → 选择zip

# 3. 重启手机

# 4. 放入配置文件
# sing-box: /data/adb/box/sing-box/config.json
# clash:    /data/adb/box/clash/config.yaml
# v2ray:    /data/adb/box/v2ray/config.json
# xray:     /data/adb/box/xray/config.json

# 5. 编辑设置
# /data/adb/box/settings.ini
#   bin_name="sing-box"  # 选择内核
#   network_mode="tproxy" # 透明代理模式: redirect/tproxy/mixed/tun

# 6. 启动/停止
su -c /data/adb/box/scripts/box.service start
su -c /data/adb/box/scripts/box.service stop
```

### 关键配置 (sing-box 透明代理示例)
```json
{
  "inbounds": [
    {
      "type": "tproxy",
      "tag": "tproxy-in",
      "listen": "::",
      "listen_port": 9898,
      "sniff": true,
      "sniff_override_destination": true
    }
  ],
  "outbounds": [
    {
      "type": "shadowsocks",
      "tag": "proxy",
      "server": "YOUR_SERVER",
      "server_port": 443,
      "method": "chacha20-ietf-poly1305",
      "password": "YOUR_PASSWORD"
    },
    { "type": "direct", "tag": "direct" },
    { "type": "block", "tag": "block" }
  ],
  "route": {
    "rules": [
      { "geoip": ["cn"], "outbound": "direct" },
      { "geosite": ["cn"], "outbound": "direct" }
    ],
    "final": "proxy"
  }
}
```

### 热点共享原理
box4magisk 通过 iptables/nftables 规则将**所有网络接口**（包括 `ap0`/`wlan1` 热点接口）的流量重定向到透明代理端口。连接热点的设备**无需任何配置**，自动走代理。

### 优点
- 全透明，连接设备零配置
- 支持4种代理内核，灵活切换
- 支持分流规则（国内直连/国外代理）
- 开机自启，后台运行
- 社区活跃，持续更新

### 缺点
- 需要Root（Magisk/KernelSU）
- 部分手机解锁Bootloader后失去保修
- 部分银行App检测Root需要隐藏

---

## 方案二：Root + VPNHotspot

### 概述
在已有VPN连接的基础上，通过iptables规则将热点流量转发到VPN接口。

### 项目信息
- **GitHub**: [Mygod/VPNHotspot](https://github.com/Mygod/VPNHotspot)
- **Play Store**: 有上架
- **要求**: Root + Android 5.0+

### 工作原理
```
连接设备 → Wi-Fi热点(ap0) → iptables MASQUERADE → tun0(VPN) → 代理服务器 → 互联网
```

### 使用步骤
1. 安装 VPNHotspot App
2. 授予Root权限
3. 先启动VPN（如Clash for Android / V2rayNG / sing-box）
4. 开启手机热点
5. 在VPNHotspot中选择"VPN热点共享"
6. 连接设备连接热点即可

### 配合使用的VPN客户端
| App | 协议 | 推荐度 |
|-----|------|--------|
| **Clash Meta for Android (CFA)** | SS/SSR/VMess/VLESS/Trojan/Hysteria | ⭐⭐⭐⭐⭐ |
| **sing-box (SFA)** | 全协议 | ⭐⭐⭐⭐⭐ |
| **V2rayNG** | VMess/VLESS/Trojan/SS | ⭐⭐⭐⭐ |
| **NekoBox** | 全协议（基于sing-box） | ⭐⭐⭐⭐ |
| **WireGuard** | WireGuard | ⭐⭐⭐ |

### 另一个fork
- **GitHub**: [ljorge705/VPNHotspot](https://github.com/ljorge705/VPNHotspot)
- 专注于配置iptables规则，更精简

---

## 方案三：免Root + HTTP/SOCKS代理服务器

### 概述
在手机上运行代理客户端 + HTTP/SOCKS代理服务器，让同一热点下的其他设备手动配置代理来翻墙。

### 方案A: Clash for Android 局域网代理

Clash for Android 原生支持开启局域网HTTP代理：

```yaml
# Clash配置中启用局域网访问
allow-lan: true
bind-address: "*"
mixed-port: 7890  # HTTP+SOCKS5混合端口
```

**步骤**:
1. 安装 Clash for Android / Clash Meta for Android
2. 导入订阅配置
3. 配置中设置 `allow-lan: true`
4. 启动Clash
5. 开启手机热点
6. 查看手机在热点网络的IP（通常 192.168.43.1）
7. 其他设备连接热点后，设置代理: `192.168.43.1:7890`

### 方案B: sing-box (SFA) 局域网代理

```json
{
  "inbounds": [
    {
      "type": "mixed",
      "tag": "mixed-in",
      "listen": "0.0.0.0",
      "listen_port": 7890
    }
  ]
}
```

### 方案C: Every Proxy

- **Play Store**: 搜索 "Every Proxy"
- 一键开启 HTTP/SOCKS4/SOCKS5 代理服务器
- 无需配置代理客户端（但只转发，不翻墙）
- 需配合VPN客户端使用

### 方案D: Postern

- 支持开启SOCKS5代理服务器
- 支持per-app代理规则
- 可作为前置代理链

### 客户端配置指南

**Windows**:
```
设置 → 网络和Internet → 代理 → 手动设置代理
地址: 192.168.43.1  端口: 7890
```

**macOS**:
```
系统偏好设置 → 网络 → Wi-Fi → 高级 → 代理
HTTP代理/SOCKS代理: 192.168.43.1:7890
```

**iOS**:
```
设置 → Wi-Fi → 已连接网络(i) → 配置代理 → 手动
服务器: 192.168.43.1  端口: 7890
```

**Linux**:
```bash
export http_proxy=http://192.168.43.1:7890
export https_proxy=http://192.168.43.1:7890
export all_proxy=socks5://192.168.43.1:7890
```

**Android**:
```
设置 → Wi-Fi → 已连接网络 → 代理 → 手动
主机名: 192.168.43.1  端口: 7890
```

### 优缺点
- ✅ 免Root
- ✅ 简单可靠
- ❌ 客户端需手动配代理
- ❌ 部分App不走系统代理（如游戏、某些国产App）
- ❌ 不支持UDP代理（HTTP代理模式下）

---

## 方案四：免Root + Clash/sing-box + 手动代理

### 概述
这是方案三的增强版，使用更成熟的代理客户端，支持分流规则。

### 推荐App

| App | 内核 | 特点 | 下载 |
|-----|------|------|------|
| **Clash Meta for Android** | mihomo | 完善的分流规则 | GitHub |
| **SFA (sing-box for Android)** | sing-box | 新一代，全协议 | GitHub/Play |
| **NekoBox for Android** | sing-box | UI友好 | GitHub |
| **V2rayNG** | v2ray | 成熟稳定 | GitHub/Play |
| **Surfboard** | 自研 | Surge兼容 | Play |
| **Hiddify** | sing-box | 多平台 | GitHub |

### 关键配置要点

1. **开启局域网访问** (`allow-lan: true`)
2. **混合端口** (`mixed-port: 7890`)
3. **DNS劫持** (可选，解决DNS泄露)
4. **分流规则** (国内直连，减少不必要的代理流量)

---

## 方案五：免Root + tun2socks + Wi-Fi Direct

### 概述
通过Wi-Fi Direct建立设备间连接，使用tun2socks隧道绕过Android热点限制。

### 项目信息
- **GitHub**: [nestchao/Hotspot-Bypass-VPN-Unlimited-Hotspot](https://github.com/nestchao/Hotspot-Bypass-VPN-Unlimited-Hotspot)
- **描述**: 无需Root，通过Wi-Fi Direct + tun2socks实现无限热点共享
- **支持**: Windows + Android

### 原理
```
Android手机(VPN开启)
  ↓ Wi-Fi Direct
Windows电脑
  ↓ tun2socks (将SOCKS代理转为虚拟网卡)
  ↓ 虚拟网卡路由
所有流量走VPN
```

### 限制
- 目前主要支持 Windows 客户端
- Wi-Fi Direct 连接不如热点稳定
- 延迟略高

---

## 方案六：USB Tethering + 电脑中转

### 概述
手机开启USB网络共享，电脑通过手机的VPN连接上网。

### 步骤
1. 手机开启VPN（Clash/V2rayNG等）
2. USB连接电脑
3. 手机设置 → 更多连接 → USB网络共享 → 开启
4. 电脑自动获取IP，通过手机网络上网

### 注意
- **Android 10+**: USB Tethering 通常**会**走VPN通道（与Wi-Fi热点不同）
- 但部分厂商ROM可能有差异
- 可用 `ip route` 验证路由是否经过 tun0

### 验证方法
```bash
# 电脑端检查
curl ifconfig.me  # 应显示代理服务器IP而非运营商IP

# 手机端检查 (需adb)
adb shell ip route show table all | grep tun
```

---

## 方案七：WireGuard旅行路由器模式

### 概述
将手机配置为WireGuard VPN网关，其他设备通过热点连接后自动走WireGuard隧道。

### 项目信息
- **GitHub**: [kchetty100/MyTravelRouter](https://github.com/kchetty100/MyTravelRouter)
- **描述**: Android VPN Router App with WireGuard Support
- **技术栈**: Jetpack Compose + Material3

### 适用场景
- 旅行时共享VPN给多设备
- 酒店/咖啡厅公共Wi-Fi安全加密
- 远程办公VPN共享

---

## 工具生态全景

### 代理客户端（在手机上运行代理）

| 工具 | 协议 | Root | 特点 |
|------|------|------|------|
| **Clash Meta for Android** | SS/VMess/VLESS/Trojan/Hysteria/TUIC | ❌ | 规则分流，allow-lan |
| **SFA (sing-box)** | 全协议 | ❌ | 新一代，性能强 |
| **V2rayNG** | V2Ray全族 | ❌ | 成熟稳定 |
| **NekoBox** | sing-box内核 | ❌ | UI友好 |
| **Surfboard** | SS/VMess/Trojan | ❌ | Surge兼容 |
| **Hiddify** | sing-box内核 | ❌ | 多平台统一 |
| **SagerNet** | 全协议 | ❌ | 已停更但仍可用 |

### 热点共享工具（让热点流量走代理）

| 工具 | Root | 原理 | 透明度 |
|------|------|------|--------|
| **box4magisk** | ✅ | 系统级透明代理(TPROXY) | 全透明 |
| **VPNHotspot** | ✅ | iptables MASQUERADE | 全透明 |
| **Every Proxy** | ❌ | HTTP/SOCKS代理服务器 | 需手动配 |
| **Postern** | ❌ | SOCKS5代理服务器 | 需手动配 |
| **NetShare** | ❌ | 创建代理热点 | 需手动配 |

### 系统级工具（Root后使用）

| 工具 | 用途 |
|------|------|
| **Magisk** | Root管理器，模块框架 |
| **KernelSU** | 内核级Root，更难被检测 |
| **LSPosed** | Xposed框架，可Hook系统 |
| **AFWall+** | iptables防火墙GUI |
| **Termux** | Android终端模拟器 |

---

## GitHub开源项目索引

| 项目 | ⭐ | 用途 | 链接 |
|------|---|------|------|
| **box4magisk** | 高 | Magisk模块，sing-box/clash/v2ray/xray透明代理 | [CHIZI-0618/box4magisk](https://github.com/CHIZI-0618/box4magisk) |
| **VPNHotspot** | 高 | Root后共享VPN到热点 | [Mygod/VPNHotspot](https://github.com/Mygod/VPNHotspot) |
| **proxy-share-vpn** | 新 | 免Root共享VPN/SOCKS5到热点 | [leninkhaidem/proxy-share-vpn](https://github.com/leninkhaidem/proxy-share-vpn) |
| **Hotspot-Bypass** | 新 | Wi-Fi Direct + tun2socks免Root方案 | [nestchao/Hotspot-Bypass-VPN-Unlimited-Hotspot](https://github.com/nestchao/Hotspot-Bypass-VPN-Unlimited-Hotspot) |
| **MyTravelRouter** | - | WireGuard旅行路由器 | [kchetty100/MyTravelRouter](https://github.com/kchetty100/MyTravelRouter) |
| **sing-box** | 极高 | 新一代代理内核 | [SagerNet/sing-box](https://github.com/SagerNet/sing-box) |
| **mihomo** | 极高 | Clash Meta内核 | [MetaCubeX/mihomo](https://github.com/MetaCubeX/mihomo) |
| **v2ray-core** | 极高 | V2Ray内核 | [v2fly/v2ray-core](https://github.com/v2fly/v2ray-core) |
| **Xray-core** | 极高 | Xray内核(V2Ray超集) | [XTLS/Xray-core](https://github.com/XTLS/Xray-core) |
| **ClashMetaForAndroid** | 高 | Clash Meta安卓客户端 | [MetaCubeX/ClashMetaForAndroid](https://github.com/MetaCubeX/ClashMetaForAndroid) |
| **v2rayNG** | 高 | V2Ray安卓客户端 | [2dust/v2rayNG](https://github.com/2dust/v2rayNG) |
| **hiddify-app** | 高 | 多平台sing-box客户端 | [hiddify/hiddify-app](https://github.com/hiddify/hiddify-app) |
| **NekoBoxForAndroid** | 高 | sing-box安卓客户端 | [MatsuriDayo/NekoBoxForAndroid](https://github.com/MatsuriDayo/NekoBoxForAndroid) |
| **tun2socks** | 高 | TUN→SOCKS隧道 | [xjasonlyu/tun2socks](https://github.com/xjasonlyu/tun2socks) |

---

## 硬件需求与兼容性

### 推荐手机配置

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| **处理器** | 骁龙625+ | 骁龙7系/8系 |
| **内存** | 3GB | 6GB+ |
| **Android版本** | 7.0+ | 10.0+ |
| **电池** | 3000mAh | 5000mAh+ |
| **散热** | - | 金属后盖/散热背夹 |

### 推荐用作软路由的手机（二手性价比）

| 手机 | 参考价 | 优势 | Root难度 |
|------|--------|------|---------|
| **小米/Redmi系列** | ¥200-800 | 解锁友好，Magisk支持好 | ⭐ 简单 |
| **一加系列** | ¥300-1000 | 解锁无等待，类原生 | ⭐ 简单 |
| **Pixel系列** | ¥500-1500 | 原生Android，Root最方便 | ⭐ 最简单 |
| **三星S系列** | ¥300-800 | 硬件好但Knox会熔断 | ⭐⭐⭐ 困难 |
| **华为/荣耀** | ¥200-500 | 不推荐，无法解锁BL | ❌ 极困难 |

### 兼容性矩阵

| Android版本 | 热点 | VPN | iptables | box4magisk | VPNHotspot |
|-------------|------|-----|----------|-----------|------------|
| 7.0-8.1 | ✅ | ✅ | ✅ | ⚠️ 旧版 | ✅ |
| 9.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 10.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 11.0 | ✅ | ✅ | ✅/nft | ✅ | ✅ |
| 12.0+ | ✅ | ✅ | nftables | ✅ | ✅ |
| 13.0+ | ✅ | ✅ | nftables | ✅ | ✅ |
| 14.0+ | ✅ | ✅ | nftables | ✅ | ⚠️ 需更新 |

---

## 问题诊断与解决

### 🔴 P0: 热点连接设备无法上网

**症状**: 设备连上热点但无法访问任何网站

**诊断链**:
1. 手机本身能否翻墙？ → 不能则先修代理配置
2. 代理是否开启 `allow-lan`？ → Clash/sing-box配置检查
3. 手机热点IP是否正确？ → 通常 `192.168.43.1`
4. 客户端代理配置是否正确？ → IP+端口检查
5. 防火墙是否拦截？ → 关闭手机端防火墙测试

### 🔴 P0: Root方案热点流量仍不走代理

**症状**: 已安装box4magisk/VPNHotspot但热点流量绕过代理

**解决**:
```bash
# 检查iptables规则是否生效
su -c iptables -t nat -L -n | grep -i tproxy
su -c iptables -t mangle -L -n | grep -i tproxy

# 检查box4magisk状态
su -c /data/adb/box/scripts/box.service status

# 检查网络接口
su -c ip link show | grep -E "ap0|wlan1|swlan0"

# 重启box4magisk
su -c /data/adb/box/scripts/box.service restart
```

### 🟡 P1: 速度慢/延迟高

**可能原因**:
1. **手机CPU负荷高** → 关闭其他App，检查CPU温度
2. **代理节点慢** → 切换节点
3. **加密开销** → 使用更高效的协议（Hysteria2 > VLESS > VMess）
4. **热点带宽限制** → 部分运营商限制热点速度
5. **连接设备过多** → 减少连接设备数

### 🟡 P1: 手机发热严重

**解决**:
1. 使用散热背夹/风扇
2. 降低屏幕亮度或关屏运行
3. 关闭不必要的后台App
4. 使用更高效的代理协议
5. 保持通风，避免放在被子/枕头上

### 🟡 P1: 耗电快

**解决**:
1. 外接充电宝/电源（24小时运行必备）
2. 开启省电模式但排除代理App
3. 关闭手机屏幕
4. 使用Termux + cron定时重启代理（防内存泄漏）

### 🟡 P2: 运营商检测热点被限速

**原理**: 运营商通过TTL值检测热点共享
- 手机直接流量 TTL=64
- 热点转发流量 TTL=63（经过一跳）

**解决 (Root)**:
```bash
# iptables修改TTL值
su -c iptables -t mangle -A POSTROUTING -o rmnet+ -j TTL --ttl-set 64
```

### 🟢 P3: DNS泄露

**症状**: 翻墙后访问被墙网站仍然解析到国内IP

**解决**:
```yaml
# Clash配置DNS
dns:
  enable: true
  listen: 0.0.0.0:53
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  nameserver:
    - https://dns.google/dns-query
    - https://1.1.1.1/dns-query
  fallback:
    - tls://8.8.8.8:853
```

### 🟢 P3: 部分App不走系统代理

**原因**: 某些App（游戏、国产App）使用自有DNS/直连，不走系统代理设置

**解决**:
1. Root方案（box4magisk）天然解决 — 透明代理拦截所有流量
2. 免Root方案需使用TUN模式（VPN模式），而非HTTP代理模式

---

## 安全与法律风险

### ⚠️ 法律风险
1. **中国大陆**: 使用VPN翻墙属于灰色地带，个人使用一般不追究，但商业运营/大规模分享可能面临法律风险
2. **Root手机**: 可能触发银行App安全检测，导致无法使用
3. **运营商**: 大流量热点共享可能违反运营商协议

### 🔒 安全建议
1. 代理配置文件不要泄露（含服务器IP和密码）
2. 热点设置强密码（WPA3优先）
3. 限制热点连接设备数
4. 定期更新代理客户端和系统
5. 使用加密DNS防止泄露

---

## 我的环境适配

### 现有资源
- **Clash for Windows (台式机)**: 已在 `clash-agent/` 运行，端口7890
- **阿里云服务器**: aiotvr.xyz，可部署代理服务端
- **手机**: OPPO Reno4 SE (WK555X5DF65PPR4L, 软路由), OPPO Reno4 (54ea19ff, 主力)

### 推荐方案

**场景1: 当前方案（免Root，已验证可用）**
```
OPPO Reno4 SE (192.168.31.95)
  → V2rayNG v2.0.13 + Trojan + allow-lan
  → SOCKS5代理: 192.168.31.95:10808
  → 电脑安装SwitchyOmega或curl -x socks5://
  → HK出口 206.237.119.226, 延时105ms
```

**场景2: 目标方案（Root，全透明）**
```
OPPO Reno4 SE (BL已解锁, Magisk已装)
  → patch boot.img → 激活Root
  → 安装box4magisk 或 执行hotspot_vpn.sh
  → 开启热点
  → 所有设备零配置自动翻墙
  → 外接电源24小时运行
```

**场景3: 旅行临时（免Root快速）**
```
任意Android手机
  → V2rayNG / Clash Meta
  → 导入订阅
  → 开启热点
  → 笔记本设置代理
```

---

## 快速决策树

```
你的手机能Root吗？
├── 能Root
│   ├── 想要全透明（连接设备零配置）？
│   │   ├── 是 → 方案一: box4magisk（最强方案）
│   │   └── 否 → 方案二: VPNHotspot（更简单）
│   └── 
└── 不能/不想Root
    ├── 只给1-2台设备用？
    │   ├── 是 → 方案三/四: Clash allow-lan（最简单）
    │   └── 否（多设备且要全透明）
    │       ├── 有Windows电脑？ → 方案五: tun2socks
    │       └── USB连接可以？ → 方案六: USB Tethering
    └──
```

---

## 附录A: 实机部署验证报告 (2026-03-05)

### 测试环境

| 项目 | 值 |
|------|-----|
| 手机 | OPPO Reno4 SE (PEAM00), Android 12, ColorOS |
| Magisk | v27.0 已装（su不可用，boot未patch） |
| WiFi | 192.168.31.95 (周老板的WiFi, 5GHz AC 433Mbps) |
| 代理客户端 | V2rayNG v2.0.13 (arm64) |
| 代理协议 | Trojan + TLS |
| 节点 | HK01: R2.tube-cat.com:9125, SNI=hk.catxstar.com |
| 电脑 | Windows, 同WiFi 192.168.31.x |

### 部署步骤（免Root方案，实际执行）

```bash
# 1. 下载V2rayNG并安装
adb install v2rayNG_2.0.13_arm64-v8a.apk

# 2. 从Clash配置提取115个Trojan节点
# 生成 trojan://password@server:port?sni=xxx&allowInsecure=1#name 格式

# 3. 在V2rayNG中手动添加Trojan服务器
#    - 服务器: R2.tube-cat.com:9125
#    - 密码: [trojan password]
#    - TLS: tls, SNI: hk.catxstar.com

# 4. 设置 → 允许来自局域网的连接 ✅
# 5. 启动VPN服务 → 授权VPN连接

# 6. 电脑验证（SOCKS5代理）
curl -x socks5://192.168.31.95:10808 https://www.google.com
```

### 测试结果

| 测试项 | 结果 | 延时 |
|--------|------|------|
| V2rayNG连接测试 | ✅ 成功 | 105ms |
| 出口IP | 206.237.119.226 (HK) | - |
| 电脑→Google | ✅ HTTP 200 | 0.65s |
| 电脑→YouTube | ✅ HTTP 200 | 0.93s |
| 电脑→GitHub | ✅ HTTP 200 | 0.79s |

### allow-lan代理端口

| 端口 | 协议 | 状态 |
|------|------|------|
| 10808 | SOCKS5 | ✅ OPEN (0.0.0.0) |
| 10809 | HTTP | ❌ CLOSED |

> **注**: V2rayNG 2.x allow-lan默认只开SOCKS5端口10808，HTTP端口未开。
> 电脑端需使用SOCKS5代理，或在V2rayNG设置中手动开启HTTP代理。

### 电脑端配置方式

**Windows系统代理**（仅支持HTTP，需V2rayNG开HTTP端口）:
```
设置 → 网络和Internet → 代理 → 手动设置
地址: 192.168.31.95  端口: 10809
```

**浏览器SOCKS5代理**（推荐，已验证可用）:
- Chrome: 安装 SwitchyOmega 扩展 → SOCKS5 → 192.168.31.95:10808
- Firefox: 设置 → 网络 → SOCKS5 → 192.168.31.95:10808

**命令行**:
```bash
# curl
curl -x socks5://192.168.31.95:10808 https://target.com

# git
git config --global http.proxy socks5://192.168.31.95:10808

# npm
npm config set proxy socks5://192.168.31.95:10808

# PowerShell (需要模块)
Invoke-WebRequest -Uri "https://target.com" -Proxy "socks5://192.168.31.95:10808"
```

### 发现的问题与解决方案

| # | 问题 | 原因 | 解决方案 |
|---|------|------|---------|
| 1 | Magisk已装但su不可用 | boot镜像未patch | 需在Magisk App中patch boot.img并刷入 |
| 2 | V2rayNG intent导入节点失败 | UrlSchemeActivity未处理 | 改用手动添加[Trojan]方式 |
| 3 | 文件选择器找不到txt | 文件分类过滤 | 直接手动输入节点信息 |
| 4 | ICMP ping不通 | Trojan代理只转发TCP | 正常现象，用HTTP测试验证 |
| 5 | HTTP代理端口10809未开 | V2rayNG 2.x默认行为 | 用SOCKS5:10808替代，或设置中开启 |
| 6 | 密码输入多余字符 | ADB input text输入偏移 | 手动清除重输 |

### 结论

**免Root方案（V2rayNG allow-lan）已验证可用**：
- ✅ 手机VPN翻墙正常（105ms延时，HK出口）
- ✅ 电脑通过SOCKS5代理翻墙正常（Google/YouTube/GitHub全通）
- ⚠️ 非透明代理，每台设备需手动配置SOCKS5代理
- ⚠️ 仅TCP流量，不支持ICMP/UDP（部分游戏可能不工作）
- 💡 若需透明代理（连接设备零配置），需先完成Magisk boot patch获取Root权限
