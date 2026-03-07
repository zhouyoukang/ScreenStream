# 手机软路由 — OPPO Reno4 SE

> 将OPPO Reno4 SE变成软路由/VPN网关，让所有设备通过它翻墙上网。

## 当前状态

| 项目 | 状态 |
|------|------|
| 设备 | OPPO Reno4 SE (PEAM00), Android 12 |
| ADB | `D:\platform-tools\adb.exe -s WK555X5DF65PPR4L` |
| WiFi IP | 192.168.31.95 |
| V2rayNG | ✅ v2.0.13, Trojan+TLS, HK出口 206.237.119.226 |
| SOCKS5 | ✅ `192.168.31.95:10808` (allow-lan) |
| Root | ❌ Magisk v27.0已装, boot未patch |

## 快速使用

```bash
# 电脑通过SOCKS5代理翻墙
curl -x socks5://192.168.31.95:10808 https://www.google.com

# 浏览器: 安装SwitchyOmega → SOCKS5 → 192.168.31.95:10808

# 一键验证全链路
powershell -File verify.ps1
```

## 文件说明

| 文件 | 用途 |
|------|------|
| `verify.ps1` | 一键验证全链路(6项检查) |
| `proxy.ps1` | Windows系统代理开关(on/off/status/test) |
| `root.ps1` | Root激活脚本(extract→patch→flash→verify) |
| `hotspot_vpn.sh` | 透明代理热点(Root后使用) |
| `payload-dumper-go.exe` | 固件boot.img提取工具 |
| `v2rayNG.apk` | V2rayNG安装包 |
| `nodes.txt` | 节点配置(不跟踪git) |
| `README_FULL.md` | 7种方案完整参考文档(756行) |

## 方案路线图

```
当前: V2rayNG allow-lan (免Root, 需手动配代理)
     ↓ patch boot.img
目标: Root + 透明代理 (零配置, 所有设备自动翻墙)
```

## Root激活步骤

1. 下载PEAM00 stock firmware (.zip含payload.bin)
2. `.\root.ps1 extract` — 提取boot.img
3. `.\root.ps1 patch` — Magisk App中patch boot.img
4. `.\root.ps1 flash` — fastboot刷入patched boot
5. `.\root.ps1 verify` — 验证su可用
6. 推送并执行 `hotspot_vpn.sh` — 启用透明代理
