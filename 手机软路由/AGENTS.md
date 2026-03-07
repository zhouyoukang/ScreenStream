# 手机软路由 — Agent操作指令

> Agent操作此目录时自动加载。

## 目录用途
OPPO Reno4 SE 翻墙网关，V2rayNG + Trojan + SOCKS5 allow-lan。BL已解锁，Magisk v27.0已装，Root待激活。ScreenStream已装(PhoneLib全操控可用)。

## 设备状态 (2026-03-06 实测)

| 设备 | ADB序列号 | 型号 | Android | V2rayNG | Root |
|------|-----------|------|---------|---------|------|
| OPPO Reno4 SE | WK555X5DF65PPR4L | PEAM00 | 12 | ✅ v2.0.13 | ⏳ BL解锁+Magisk装,boot未patch |
| OPPO Reno4 | 54ea19ff | PCHM30 | 11 | ✅ 已装 | ❌ |
| LDPlayer开发测试 | emulator-5560 | V1824A | 9 | ✅ 已装 | ✅ uid=0 |

### 当前可用代理
- **SOCKS5**: `192.168.31.95:10808` (allow-lan, 全接口监听)
- **HTTP**: 未开启 (需在V2rayNG设置中手动开启端口10809)

## 关键文件
- `README.md` — 项目概览+当前状态+快速使用+Root路线图
- `README_FULL.md` — 完整7方案百科参考(756行)
- `proxy.ps1` — Windows一键代理切换脚本（on/off/status/test）
- `verify.ps1` — 自动化验证脚本（设备+代理+网络6项检测）
- `root.ps1` — Root激活脚本（extract→patch→flash→verify）
- `auto_root.py` — mtkclient全自动Root(extract→patch→flash→verify,需BROM模式)
- `hotspot_vpn.sh` — 透明代理脚本（iptables NAT，Root后推到手机执行）
- `payload-dumper-go.exe` — 固件boot.img提取工具(v1.3.0)
- `nodes.txt` — Trojan节点（**禁止git跟踪**，115个节点）
- `v2rayNG.apk` — 安装包 (arm64)

## Agent操作规范
1. **凭据安全**: 不在tracked文件中写入服务器地址/密码，节点信息见 `nodes.txt`
2. **Root路径**: BL已解锁，Magisk已装，需patch boot.img激活Root → `root.ps1`
3. **方案优先级**: 透明代理(Root+iptables) > V2rayNG allow-lan > Clash allow-lan
4. **ADB诊断**: 用 `D:\platform-tools\adb.exe -s WK555X5DF65PPR4L` 操作Reno4 SE
5. **PhoneLib**: `Phone(host='192.168.31.95', port=8084)` → 全操控(read/click/home/senses)
6. **OPPO APK安装**: `adb push /data/local/tmp/ && pm install -r -t` 绕过UI拦截
7. **V2rayNG远程启动**: `am start -n com.v2ray.ang/.ui.MainActivity` 后用 `POST /tap {"x":948,"y":2160}` 点FAB按钮连接VPN
8. **ScreenStream Input API**: `http://192.168.31.95:8084/` — tap/swipe/text/home/back/viewtree等

### ADB快速诊断
```powershell
# 设备连接
D:\platform-tools\adb.exe devices
# 代理端口
D:\platform-tools\adb.exe -s WK555X5DF65PPR4L shell "netstat -tlnp | grep -E '10808|10809'"
# 手机IP
D:\platform-tools\adb.exe -s WK555X5DF65PPR4L shell "ip addr show wlan0 | grep inet"
# VPN隧道
D:\platform-tools\adb.exe -s WK555X5DF65PPR4L shell "ip addr show tun0"
# 代理测试
curl.exe -x socks5://192.168.31.95:10808 https://www.google.com -m 10
```

### LDPlayer模拟器VPN全链路 (2026-03-07验证)

**VM[3] (开发测试1)** — V2rayNG + SOCKS5 + allow-lan 全链路已通
- **ADB**: `emulator-5560` | **wlan0**: `192.168.31.174` (桥接PC LAN)
- **V2rayNG**: 115节点已导入, HK01连接, tun0=10.10.14.1/30
- **SOCKS5**: `:::10808` (全接口, allow-lan) | 出口IP: 206.237.119.226 (HK)
- **Root**: ✅ uid=0

```powershell
# 一键管理 (推荐)
.\emu_vpn.ps1 status   # 7项状态检测
.\emu_vpn.ps1 start    # 启动VM+V2rayNG+VPN+端口转发
.\emu_vpn.ps1 test     # E2E测试(ExitIP+Google+GitHub+PC隔离)
.\emu_vpn.ps1 setup    # 初始化(Root+推送nodes+安装V2rayNG)

# 手动操作
D:\leidian\LDPlayer9\ldconsole.exe modify --name "开发测试1" --root 1
D:\leidian\LDPlayer9\adb.exe -s emulator-5560 forward tcp:10808 tcp:10808
curl.exe -x socks5://192.168.31.174:10808 https://api.ipify.org
```

**LDPlayer热点限制**: VirtualBox无WiFi AP硬件，无法创建热点。替代方案：
- ✅ LAN SOCKS5代理: 任何192.168.31.x设备 → `socks5://192.168.31.174:10808`
- ✅ ADB端口转发: PC本机 → `socks5://127.0.0.1:10808`
- ✅ 不干扰PC网络: 代理为可选使用，不修改PC路由表

## 验证结果 (2026-03-07)
| 项目 | 真机(PEAM00) | LDPlayer VM[3] |
|------|-------------|----------------|
| VPN连接 | ✅ HK出口 | ✅ HK01 (206.237.119.226) |
| SOCKS5 allow-lan | ✅ 192.168.31.95:10808 | ✅ 192.168.31.174:10808 |
| tun0隧道 | ✅ | ✅ 10.10.14.1/30 |
| Google访问 | ✅ | ✅ HTTP 200 |
| PC网络隔离 | — | ✅ PC IP ≠ 代理IP |
| 热点 | ❌ 需Root | ❌ VirtualBox无AP硬件 |
| 透明代理 | ❌ 需Root | ✅ emu_proxy.sh (可选) |
| emu_vpn.ps1 | — | ✅ 全自动管理 |

## 关联资源
- `clash-agent/` — PC端Clash代理管理（节点源相同）
- `手机操控库/` — PhoneLib手机控制
- `阿里云服务器/` — 可部署代理服务端
