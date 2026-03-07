# 多网络聚合 — 多手机流量叠加实现网络加速

> **道德经·三生万物**：一部手机是线路，多部手机聚合成管道。
>
> 核心场景：网络环境差（农村/山区/展会/旅行/户外直播），靠**多部手机的蜂窝流量叠加**实现较好的网络服务。

## 目录

- [核心概念](#核心概念)
- [方案总览](#方案总览)
- [方案一：Speedify（商业·最简单）](#方案一speedify商业最简单)
- [方案二：OpenMPTCProuter（开源·最强）](#方案二openmptcprouter开源最强)
- [方案三：dispatch-proxy（轻量·Windows/Mac）](#方案三dispatch-proxy轻量windowsmac)
- [方案四：OpenWrt + mwan3（路由器级）](#方案四openwrt--mwan3路由器级)
- [方案五：Windows原生网络桥接 + 负载均衡](#方案五windows原生网络桥接--负载均衡)
- [方案六：Linux bonding/teaming](#方案六linux-bondingteaming)
- [方案七：商业硬件聚合设备](#方案七商业硬件聚合设备)
- [GitHub开源项目索引](#github开源项目索引)
- [硬件需求清单](#硬件需求清单)
- [我的环境适配](#我的环境适配)
- [快速决策树](#快速决策树)
- [与手机软路由项目的关系](#与手机软路由项目的关系)

---

## 核心概念

### 什么是网络聚合？

将**多条互联网连接**的带宽合并使用，实现：
- **带宽叠加**：3部手机各10Mbps → 合并近30Mbps
- **故障切换(Failover)**：一条断了自动切另一条
- **负载均衡**：多条线路分担流量，降低单线路压力
- **降低延迟**：智能选择最快链路传输

### 聚合 vs 负载均衡 vs Failover

| 模式 | 原理 | 单连接加速 | 总带宽提升 | 复杂度 |
|------|------|-----------|-----------|--------|
| **带宽聚合(Bonding)** | 将数据包拆分到多条链路，重组 | ✅ | ✅ | ⭐⭐⭐⭐ |
| **负载均衡(Load Balance)** | 不同连接走不同链路 | ❌ | ✅ | ⭐⭐ |
| **故障切换(Failover)** | 主线路断了切备用 | ❌ | ❌ | ⭐ |
| **MPTCP** | TCP层多路径传输，单连接真聚合 | ✅ | ✅ | ⭐⭐⭐⭐⭐ |

### 为什么用手机？

- **随处有信号**：4G/5G覆盖广，即使偏远地区也有基站
- **多SIM/多运营商**：移动+联通+电信各一部，避免单运营商拥塞
- **成本低**：闲置旧手机+流量卡 = 几乎零成本
- **便携**：不需要额外硬件（路由器/CPE）

### 连接方式

```
多部手机如何连到一台电脑/路由器？

方式1: USB Tethering（最稳定，推荐）
  手机A ──USB──┐
  手机B ──USB──├── 电脑/路由器 ── 聚合软件 ── 互联网
  手机C ──USB──┘

方式2: WiFi（无线，便携）
  手机A ──WiFi热点──┐
  手机B ──WiFi热点──├── 电脑(多WiFi网卡) ── 聚合软件
  手机C ──WiFi热点──┘

方式3: 以太网适配器（高端，稳定）
  手机A ──USB转以太网──┐
  手机B ──USB转以太网──├── 交换机 ── 路由器(OpenWrt)
  手机C ──USB转以太网──┘
```

---

## 方案总览

| # | 方案 | 类型 | 聚合模式 | 单连接加速 | 难度 | 成本 | 推荐度 |
|---|------|------|---------|-----------|------|------|--------|
| 1 | **Speedify** | 商业软件 | 真聚合(Bonding) | ✅ | ⭐ | $$$月费 | ⭐⭐⭐⭐ |
| 2 | **OpenMPTCProuter** | 开源(OpenWrt) | 真聚合(MPTCP) | ✅ | ⭐⭐⭐⭐⭐ | 需VPS | ⭐⭐⭐⭐⭐ |
| 3 | **dispatch-proxy** | 开源(Node.js) | 负载均衡 | ❌ | ⭐⭐ | 免费 | ⭐⭐⭐ |
| 4 | **OpenWrt+mwan3** | 开源(路由器) | 负载均衡/Failover | ❌ | ⭐⭐⭐⭐ | 需路由器 | ⭐⭐⭐⭐ |
| 5 | **Windows原生** | 系统内置 | 负载均衡 | ❌ | ⭐⭐⭐ | 免费 | ⭐⭐ |
| 6 | **Linux bonding** | 系统内置 | 真聚合(L2) | ✅ | ⭐⭐⭐⭐ | 免费 | ⭐⭐⭐ |
| 7 | **商业硬件** | 硬件设备 | 真聚合 | ✅ | ⭐ | $$$$ | ⭐⭐⭐ |

---

## 方案一：Speedify（商业·最简单）

### 概述
Speedify是商业VPN+Channel Bonding软件，能将多条网络连接（WiFi+蜂窝+以太网+USB Tethering）**真正聚合**成一条高速通道。

### 原理
```
手机A(USB Tethering) ──┐                    ┌── Speedify云服务器 ── 互联网
手机B(USB Tethering) ──├── Speedify客户端 ──┤   (数据包重组)
WiFi ──────────────────┘   (数据包拆分)     └──
```

### 平台支持
- Windows / macOS / Linux / Android / iOS

### 优点
- **开箱即用**：安装→自动检测所有网络接口→一键聚合
- **真聚合**：单个下载也能叠加带宽（如3×10Mbps≈25Mbps）
- **智能冗余**：重要包同时走多条线路，丢包自动重传
- **移动优化**：专门优化蜂窝网络的高延迟/抖动

### 缺点
- **月费**：免费版限2GB/月，付费$14.99/月（家庭版$22.49/月）
- **依赖云服务器**：数据走Speedify服务器中转，增加延迟
- **中国大陆可能受限**：服务器可能被墙

### 使用方法
```
1. 多部手机开启USB Tethering，连接电脑
2. 安装Speedify → 自动识别所有网络接口
3. 设置模式：
   - Speed: 最大化带宽（推荐）
   - Redundant: 最大化可靠性（直播/会议推荐）
   - Streaming: 流媒体优化
4. 完成！浏览器/所有App自动使用聚合网络
```

### 替代品
- **Connectify Dispatch** (Windows) — 负载均衡（非真聚合），$29.98一次性
- **Mushroom Network Truffle** — 硬件聚合设备

---

## 方案二：OpenMPTCProuter（开源·最强）

### 概述
OpenMPTCProuter是基于OpenWrt的开源多路径TCP聚合方案。利用MPTCP协议将多条WAN线路的带宽**真正聚合**，需要一台VPS作为聚合服务器。

### 架构
```
手机A(USB Tethering) ──┐                         ┌── VPS聚合服务器
手机B(USB Tethering) ──├── OpenWrt路由器 ── MPTCP ┤   (OpenMPTCProuter Server)
手机C(USB Tethering) ──┘   (多WAN口)              └── 互联网
```

### 组件
- **客户端**：OpenWrt路由器（x86/树莓派/软路由）刷OpenMPTCProuter固件
- **服务端**：VPS运行聚合服务（接收多条MPTCP子流，合并后转发）

### GitHub项目
- **主项目**: [ysurac/openmptcprouter](https://github.com/ysurac/openmptcprouter)
- **服务端**: [ysurac/openmptcprouter-vps](https://github.com/ysurac/openmptcprouter-vps)
- **固件下载**: [GitHub Releases](https://github.com/ysurac/openmptcprouter/releases)

### 硬件需求
| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| 路由器/软路由 | 树莓派3B | x86小主机(J4125) / 树莓派4B |
| USB网卡(多口) | USB 2.0 Hub | USB 3.0 Hub + 以太网适配器 |
| VPS服务器 | 1核1G | 2核2G+ (带宽充足) |

### 部署步骤

#### 服务端 (VPS)
```bash
# 在VPS上一键安装OpenMPTCProuter Server
wget -O - https://www.openmptcprouter.com/server/debian-x86_64.sh | sh

# 安装后获取密钥
cat /root/openmptcprouter_config.txt
```

#### 客户端 (OpenWrt路由器)
```
1. 下载OpenMPTCProuter固件（选择对应硬件平台）
2. 刷入路由器/软路由
3. 访问 http://192.168.100.1 (默认管理地址)
4. 设置 → OpenMPTCProuter → 填入VPS IP和密钥
5. 网络 → 接口 → 添加多个WAN接口（每个手机USB一个）
6. 完成！所有下游设备自动使用聚合网络
```

### 手机USB Tethering作为WAN

```
# OpenWrt中为每部手机创建WAN接口
# 手机通过USB Tethering后会出现 usb0, usb1, usb2 等网卡

# /etc/config/network
config interface 'wan1'
    option proto 'dhcp'
    option ifname 'usb0'      # 手机A

config interface 'wan2'
    option proto 'dhcp'
    option ifname 'usb1'      # 手机B

config interface 'wan3'
    option proto 'dhcp'
    option ifname 'usb2'      # 手机C
```

### 优点
- **完全开源免费**（除VPS费用）
- **真正的带宽聚合**（MPTCP协议级别）
- **路由器级部署**：下游设备零配置
- **支持手机USB Tethering作为WAN**
- **故障自动切换**
- **可用阿里云VPS**（已有aiotvr.xyz服务器）

### 缺点
- **需要VPS**（阿里云2核2G约¥60/月）
- **配置复杂**（OpenWrt经验）
- **需要额外硬件**（软路由/树莓派）
- **MPTCP对UDP无效**（仅TCP聚合）

---

## 方案三：dispatch-proxy（轻量·Windows/Mac）

### 概述
dispatch-proxy是一个Node.js编写的轻量SOCKS5代理，将流量按**轮询(Round-Robin)**分发到多个网络接口。不需要服务器，本机即可运行。

### GitHub
- [alexkirsz/dispatch-proxy](https://github.com/alexkirsz/dispatch-proxy)

### 安装使用
```bash
# 安装
npm install -g dispatch-proxy

# 列出所有网络接口
dispatch list

# 启动（自动使用所有接口）
dispatch start

# 指定接口和权重
dispatch start 192.168.42.1 192.168.43.1 10.0.0.1
# 带权重: dispatch start 192.168.42.1@3 192.168.43.1@2

# 默认监听 SOCKS5://127.0.0.1:1080
# 浏览器/系统设置代理到此地址即可
```

### 原理
```
浏览器请求A ── dispatch-proxy ── 接口1(手机A) ── 互联网
浏览器请求B ──     (轮询)     ── 接口2(手机B) ── 互联网
浏览器请求C ──                ── 接口3(手机C) ── 互联网
```

### 优点
- **极简**：一条命令启动
- **免费开源**
- **无需服务器/VPS**
- **跨平台**：Windows/macOS/Linux

### 缺点
- **负载均衡而非聚合**：单个连接不加速（下载一个大文件还是走单条线路）
- **SOCKS5代理**：需要应用支持代理设置
- **无智能切换**：某条线路断了不会自动failover
- **项目较老**：最后更新2020年

### 增强替代
- **cntlm** — HTTP代理+负载均衡
- **3proxy** — 多功能代理服务器，支持负载均衡

---

## 方案四：OpenWrt + mwan3（路由器级）

### 概述
在OpenWrt路由器上使用mwan3插件实现多WAN负载均衡和故障切换。手机通过USB Tethering作为多条WAN线路。

### 与方案二的区别
| | OpenMPTCProuter | mwan3 |
|---|---|---|
| 聚合方式 | MPTCP真聚合 | IP层负载均衡 |
| 单连接加速 | ✅ | ❌ |
| 需要VPS | ✅ | ❌ |
| 复杂度 | 高 | 中 |

### 配置示例
```bash
# 安装mwan3
opkg update
opkg install mwan3 luci-app-mwan3

# /etc/config/mwan3
config interface 'wan1'
    option enabled '1'
    list track_ip '8.8.8.8'
    option reliability '1'
    option count '1'
    option timeout '2'
    option interval '5'
    option down '3'
    option up '3'

config interface 'wan2'
    option enabled '1'
    list track_ip '8.8.4.4'
    # ... 同上

config member 'wan1_m1'
    option interface 'wan1'
    option metric '1'
    option weight '1'

config member 'wan2_m1'
    option interface 'wan2'
    option metric '1'
    option weight '1'

config policy 'balanced'
    list use_member 'wan1_m1'
    list use_member 'wan2_m1'

config rule 'default_rule'
    option dest_ip '0.0.0.0/0'
    option use_policy 'balanced'
```

### 适用场景
- 不想租VPS，只要负载均衡
- 多个连接同时在用（多人办公/多设备）
- 需要Failover保障

---

## 方案五：Windows原生网络桥接 + 负载均衡

### 概述
Windows可以通过网络桥接和路由表操作实现多网卡负载均衡。无需额外软件。

### 方法A: 网络桥接
```powershell
# 1. 多部手机USB Tethering连接电脑
# 2. 控制面板 → 网络连接 → 选中所有手机网卡 → 右键 → 桥接
# 注意：桥接适用于让多设备共享，不能叠加带宽
```

### 方法B: 路由表 + 度量值
```powershell
# 查看所有网络接口
Get-NetAdapter | Format-Table Name, InterfaceIndex, Status, LinkSpeed

# 设置多个默认路由，相同度量值 = 负载均衡
route add 0.0.0.0 mask 0.0.0.0 192.168.42.129 metric 10 if <手机A接口号>
route add 0.0.0.0 mask 0.0.0.0 192.168.43.129 metric 10 if <手机B接口号>

# Windows会对不同连接自动负载均衡（基于目标IP hash）
```

### 方法C: ForceBindIP + 多进程
```powershell
# 将不同应用绑定到不同网络接口
# ForceBindIP.exe <IP> <程序路径>
ForceBindIP.exe 192.168.42.129 "C:\Program Files\Chrome\chrome.exe"
ForceBindIP.exe 192.168.43.129 "C:\Program Files\Firefox\firefox.exe"
```

### 局限
- 只能负载均衡（按连接分发），不能聚合单连接
- 需要手动维护路由表
- Windows对多默认路由支持不稳定

---

## 方案六：Linux bonding/teaming

### 概述
Linux内核原生支持网卡bonding，可将多个网络接口绑定为一个逻辑接口。配合手机USB Tethering可实现聚合。

### bonding模式
| Mode | 名称 | 说明 | 聚合 |
|------|------|------|------|
| 0 | balance-rr | 轮询 | ✅ |
| 1 | active-backup | 主备 | ❌ |
| 2 | balance-xor | XOR hash | ✅ |
| 3 | broadcast | 广播 | ❌ |
| 4 | 802.3ad | LACP | ✅(需交换机) |
| 5 | balance-tlb | 自适应发送 | ✅ |
| 6 | balance-alb | 自适应收发 | ✅ |

### 配置示例 (mode 0: 轮询)
```bash
# 加载bonding模块
modprobe bonding mode=0 miimon=100

# 创建bond接口
ip link add bond0 type bond mode balance-rr

# 添加手机USB网卡
ip link set usb0 master bond0
ip link set usb1 master bond0
ip link set usb2 master bond0

# 启用
ip link set bond0 up
dhclient bond0
```

### 注意
- **mode 0 (balance-rr)** 可能导致TCP包乱序，需要对端支持
- 手机USB Tethering网卡（usb0等）可能需要额外驱动
- 建议配合VPN隧道使用（隧道内做bonding避免乱序问题）

---

## 方案七：商业硬件聚合设备

### 蘑菇加速器/GlocalMe类设备
- **多SIM卡槽**：支持2-8张SIM卡同时在线
- **硬件聚合**：内置芯片做带宽叠加
- **便携**：充电宝大小
- **代表产品**：
  - GlocalMe G4 Pro (2SIM + eSIM)
  - 华为Mobile WiFi 3 Pro
  - 蒲公英4G工业路由器

### Mushroom Networks Truffle
- **专业级**：4×WAN口真聚合
- **价格**：$500-2000+
- **适用**：企业/直播团队

### 5G CPE + 多卡设备
- **华为5G CPE Pro 2** (H122-373)
- **中兴MC801A**
- 配合**多SIM卡方案**（双卡路由器/外接多SIM适配器）

### DIY硬件方案
```
推荐配置（低成本高效）:
├── 软路由: 畅网N5105 / J4125小主机 (¥300-600)
├── USB Hub: 有源USB 3.0 7口集线器 (¥50)
├── 手机: 2-4部闲置旧手机 (免费)
├── 流量卡: 移动/联通/电信各一张 (¥20-50/月/张)
├── 固件: OpenMPTCProuter / OpenWrt + mwan3 (免费)
└── VPS: 阿里云/腾讯云轻量应用 (¥40-60/月，方案二需要)

总成本: ¥400-700一次性 + ¥60-200/月流量
```

---

## GitHub开源项目索引

### 核心聚合项目

| 项目 | Stars | 用途 | 链接 |
|------|-------|------|------|
| **OpenMPTCProuter** | 3K+ | MPTCP真聚合路由器固件 | [ysurac/openmptcprouter](https://github.com/ysurac/openmptcprouter) |
| **OpenMPTCProuter VPS** | 500+ | 聚合服务端一键部署 | [ysurac/openmptcprouter-vps](https://github.com/ysurac/openmptcprouter-vps) |
| **dispatch-proxy** | 900+ | Node.js SOCKS5负载均衡 | [alexkirsz/dispatch-proxy](https://github.com/alexkirsz/dispatch-proxy) |
| **mptcp** | Linux内核 | MultiPath TCP内核实现 | [multipath-tcp/mptcp](https://github.com/multipath-tcp/mptcp) |

### 多WAN/负载均衡

| 项目 | 用途 | 链接 |
|------|------|------|
| **mwan3** | OpenWrt多WAN策略路由 | [openwrt/packages/.../mwan3](https://github.com/openwrt/packages) |
| **Netifyd** | 网络接口检测/DPI | [netify-fwk/netifyd](https://github.com/netify-fwk/netifyd) |
| **badvpn** | tun2socks隧道 | [ambrop72/badvpn](https://github.com/ambrop72/badvpn) |

### USB Tethering相关

| 项目 | 用途 | 链接 |
|------|------|------|
| **gnirehtet** | Android反向tethering(PC网络→手机) | [Genymobile/gnirehtet](https://github.com/Genymobile/gnirehtet) |
| **USB_ModeSwitch** | USB设备模式切换(3G/4G dongle) | [linux-usb-gadgets](https://github.com/nicman23/usb_modeswitch) |
| **adb-tethering** | 通过ADB启用USB Tethering | (adb shell svc usb setFunctions rndis) |

### VPN隧道 (用于聚合层)

| 项目 | 用途 | 链接 |
|------|------|------|
| **WireGuard** | 高性能VPN隧道 | [WireGuard/wireguard-go](https://github.com/WireGuard/wireguard-go) |
| **Shadowsocks** | SOCKS5代理 | [shadowsocks/shadowsocks-libev](https://github.com/shadowsocks/shadowsocks-libev) |
| **sing-box** | 多协议代理平台 | [SagerNet/sing-box](https://github.com/SagerNet/sing-box) |
| **Hysteria2** | 基于QUIC的代理(UDP优化) | [apernet/hysteria](https://github.com/apernet/hysteria) |

### 流媒体/直播专用

| 项目 | 用途 | 链接 |
|------|------|------|
| **SRT** | Secure Reliable Transport | [Haivision/srt](https://github.com/Haivision/srt) |
| **RIST** | 可靠网络传输协议 | [libRIST](https://code.videolan.org/rist/librist) |
| **Zixi** | 商业级直播聚合 | (商业) |

---

## 硬件需求清单

### 基础方案（dispatch-proxy，最低成本）
| 物品 | 数量 | 参考价 | 备注 |
|------|------|--------|------|
| 手机 | 2-3部 | 免费(闲置) | 能开USB Tethering即可 |
| 流量卡 | 2-3张 | ¥20-50/张/月 | 建议不同运营商 |
| USB线 | 2-3条 | ¥10 | 支持数据传输 |
| USB Hub | 1个 | ¥30-50 | 有源Hub推荐 |

### 进阶方案（OpenMPTCProuter）
| 物品 | 数量 | 参考价 | 备注 |
|------|------|--------|------|
| 软路由/小主机 | 1台 | ¥300-600 | J4125/N5105，2+网口 |
| 手机 | 2-4部 | 免费(闲置) | USB Tethering |
| 流量卡 | 2-4张 | ¥20-50/张/月 | 不同运营商 |
| USB Hub | 1个 | ¥50 | 有源USB 3.0 |
| VPS | 1台 | ¥40-60/月 | 带宽充足(可用阿里云) |
| 网线 | 若干 | ¥10 | 连接下游设备 |

### 已有资源（可直接利用）
| 资源 | 状态 | 备注 |
|------|------|------|
| OPPO Reno4 SE | ✅ V2rayNG运行中 | USB Tethering可用 |
| OnePlus NE2210 | ✅ ScreenStream | 可同时USB Tethering |
| Samsung Note20 Ultra | ✅ | 有SIM卡 |
| Samsung Tab S7+ | ✅ | WiFi Only |
| 阿里云VPS | ✅ aiotvr.xyz | 可部署MPTCP服务端 |
| 台式机(64GB RAM) | ✅ | 可作为聚合网关 |

---

## 我的环境适配

### 场景1: 户外/旅行（最简方案）
```
OPPO Reno4 SE ──USB Tethering──┐
OnePlus NE2210 ──USB Tethering──├── 笔记本电脑
                               │   dispatch-proxy
                               │   SOCKS5://127.0.0.1:1080
                               └── 所有应用通过代理使用聚合网络
```
**操作步骤**:
1. 两部手机插上USB线，开启USB Tethering
2. `npm install -g dispatch-proxy`
3. `dispatch start` → 自动检测所有手机网卡
4. 浏览器设置SOCKS5代理 `127.0.0.1:1080`

### 场景2: 固定场所（中等方案）
```
OPPO ──USB──┐
OnePlus ──USB──├── 台式机(Windows)
Samsung ──USB──┘   Speedify / Windows路由表
                   → 下游设备通过台式机网络共享
```

### 场景3: 长期部署（最强方案）
```
OPPO ──USB──┐
OnePlus ──USB──├── 软路由(OpenMPTCProuter)
Samsung ──USB──┘   ↕ MPTCP隧道
                   阿里云VPS(openmptcprouter-vps)
                   → 下游所有设备零配置自动聚合
```

### 与翻墙结合
```
多手机流量聚合 + 翻墙代理 = 双重增强

方案A: 先聚合再翻墙
  手机×3 → 聚合网关 → Clash/V2rayNG → 互联网

方案B: 翻墙内含聚合
  手机×3(各自运行V2rayNG) → USB Tethering → 电脑聚合代理出口
  (每部手机自带翻墙，聚合后既叠加带宽又翻墙)

方案C: OpenMPTCProuter + VPS翻墙
  手机×3 → OpenMPTCProuter → MPTCP → 海外VPS(自带翻墙出口)
  (一举两得：带宽聚合 + 翻墙)
```

---

## 快速决策树

```
你的核心需求是什么？
│
├── 只要可靠性（一条断了自动切）
│   └── 方案4: OpenWrt + mwan3 (Failover模式)
│
├── 要叠加带宽（单个下载更快）
│   ├── 愿意花钱？
│   │   ├── 是 → 方案1: Speedify（最简单）
│   │   └── 否 → 方案2: OpenMPTCProuter（需VPS+软路由）
│   └──
│
├── 只要多个连接同时用就好（不需要单连接加速）
│   ├── 有路由器/OpenWrt？
│   │   ├── 是 → 方案4: mwan3
│   │   └── 否 → 方案3: dispatch-proxy（一条命令）
│   └──
│
└── 户外直播/实时传输
    ├── 预算充足 → 方案7: 商业聚合设备 + SRT协议
    └── 预算有限 → 方案2: OpenMPTCProuter + VPS
```

---

## 与手机软路由项目的关系

本项目(`多网络聚合/`)与`手机软路由/`互补：

| 维度 | 手机软路由 | 多网络聚合 |
|------|----------|-----------|
| **核心目标** | 翻墙共享 | 带宽叠加 |
| **手机数量** | 1部 | 2-4部 |
| **解决问题** | 网络访问受限 | 网络速度/稳定性差 |
| **可结合** | ✅ 聚合后的出口走翻墙代理 | ✅ 翻墙代理跑在聚合网络上 |

**最佳组合**：多手机流量聚合(本项目) + OPPO翻墙网关(手机软路由) = 在网络差的环境下既有速度又能翻墙。

---

## 参考资源

- [OpenMPTCProuter官网](https://www.openmptcprouter.com/)
- [Speedify官网](https://speedify.com/)
- [OpenWrt mwan3文档](https://openwrt.org/docs/guide-user/network/ip/multiwan/mwan3)
- [MPTCP Linux内核文档](https://www.multipath-tcp.org/)
- [dispatch-proxy GitHub](https://github.com/alexkirsz/dispatch-proxy)
- [Android USB Tethering + Linux bonding](https://wiki.archlinux.org/title/Network_bridge)
