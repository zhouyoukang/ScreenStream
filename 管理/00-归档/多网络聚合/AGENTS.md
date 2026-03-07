# 多网络聚合 — AI Agent 操作手册

> 多手机流量聚合，网络差环境下实现较好网络服务。

## 目录结构

```
多网络聚合/
├── README.md          # 完整方案文档（7种方案+硬件清单+决策树）
└── AGENTS.md          # 本文件
```

## 核心方案速查

| 方案 | 聚合类型 | 适用场景 | 关键词 |
|------|---------|---------|--------|
| Speedify | 真聚合(商业) | 快速部署 | `speedify.com` |
| OpenMPTCProuter | 真聚合(开源) | 长期部署 | `openmptcprouter`, MPTCP, OpenWrt |
| dispatch-proxy | 负载均衡 | 临时使用 | `npm`, SOCKS5, Node.js |
| OpenWrt+mwan3 | 负载均衡 | 路由器级 | `opkg install mwan3` |
| Windows原生 | 负载均衡 | 最简方案 | 路由表, metric |
| Linux bonding | 真聚合(内核) | Linux环境 | `modprobe bonding` |
| 商业硬件 | 真聚合 | 企业级 | GlocalMe, Mushroom |

## 关联项目

- `手机软路由/` — 单手机VPN网关共享（互补关系）
- `clash-agent/` — Clash代理管理
- `阿里云服务器/` — VPS资源（可部署MPTCP服务端）

## Agent操作指南

### 快速验证手机USB Tethering

```powershell
# 列出所有网络适配器（插入手机USB Tethering后）
Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | Format-Table Name, InterfaceIndex, LinkSpeed

# 查看手机分配的IP
Get-NetIPAddress -InterfaceAlias "以太网*" | Where-Object { $_.AddressFamily -eq 'IPv4' }
```

### dispatch-proxy 快速启动

```powershell
# 安装
npm install -g dispatch-proxy

# 列出接口
dispatch list

# 启动聚合（自动检测所有接口）
dispatch start
# 代理地址: SOCKS5://127.0.0.1:1080
```

## 审计摘要

- **创建日期**: 2026-07
- **状态**: 方案研究阶段（资源整合完成，未实施）
- **笔记本搜索**: C/D/E三盘均无直接相关文件
- **已有基础**: `手机软路由/` 项目（单手机VPN共享已验证可用）
