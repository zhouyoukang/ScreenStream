# Windsurf 无限畅享 — 阿里云授权中枢

> 道生一(☰乾): 阿里云为唯一授权中枢
> 一生二(☱兑): 中枢 + CFW代理源
> 二生三(☲离): 中枢 + 代理 + 部署脚本
> 三生万物: 任意数量客户端接入，不受环境限制

## 核心突破

**问题**: CFW授权码绑定单台电脑的设备码(dc)，无法多机使用。

**解决**: 所有电脑通过阿里云中枢连接同一台台式机的CFW → 设备码唯一 → 单机绑定被架构性突破。

## 架构

```
任意电脑 Windsurf
    │ ① hosts劫持 → 127.0.0.1
    │ ② portproxy 127.0.0.1:443 → aiotvr.xyz:18443
    ▼
☰ 阿里云授权中枢 (aiotvr.xyz)
    │ ③ FRP隧道 :18443 → 台式机:443
    │ ④ 授权中枢面板 :18800 (/hub/)
    ▼
台式机 CFW代理 (:443)  ← 设备码固定，所有客户端共享
    │ ⑤ CFW后端 (香港/成都)
    ▼
inference.codeium.com  ← auth_token验证 → 推理执行

┌─────────────────────────────────────────────────────┐
│ 客户端五层拦截 (每台电脑自动配置)                      │
│  ① hosts → 127.0.0.1                                │
│  ② TLS自签证书 (系统信任 + SSL_CERT_FILE)             │
│  ③ settings.json (proxyStrictSSL=false)              │
│  ④ portproxy → aiotvr.xyz:18443 (阿里云FRP)          │
│  ⑤ 客户端JS补丁 (15处, 额度/Enterprise全解锁)        │
│  + Guardian守护 (自动patch + 健康检查 + 开机自启)      │
│  + Windsurf_Proxy.cmd (Chromium DNS覆盖启动)          │
└─────────────────────────────────────────────────────┘
```

## 一键部署 (任意Windows电脑)

管理员PowerShell，一行命令：

```powershell
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; irm https://aiotvr.xyz/agent/deploy-vm.ps1 | iex
```

部署完成后，双击桌面「Windsurf_Proxy.cmd」启动Windsurf即可。

## 本地操作

```powershell
# 本地一键部署 (台式机/笔记本, 管理员权限)
python deploy_local.py

# 健康检查
python deploy_local.py --check
python windsurf_guardian.py --check

# 补丁管理
python patch_windsurf.py           # 应用补丁
python patch_windsurf.py --verify  # 验证
python patch_windsurf.py --restore # 恢复

# 守护进程
python windsurf_guardian.py --install  # 注册开机自启

# E2E全链路测试
python _e2e_test.py
```

## 文件清单

```
Windsurf无限额度/
├── 阿里云授权中枢
│   ├── auth_hub.py                授权中枢服务 (Python3, 部署在阿里云)
│   └── deploy_hub.sh              中枢部署脚本 (systemd + Nginx)
│
├── 客户端核心
│   ├── patch_windsurf.py          客户端补丁 v3.1 (11静态+4正则=15处)
│   ├── deploy_vm.ps1              远程VM一键部署 v4.0 (10步, 公网)
│   ├── deploy_local.py            本地一键部署 v1.0 (7步, LAN)
│   ├── windsurf_guardian.py       守护进程 (自动patch+代理failover)
│   └── windsurf_proxy.py          自建gRPC代理 (Free-tier备用)
│
├── 证书
│   ├── windsurf_proxy_ca.pem      CA证书 (10年有效期)
│   ├── windsurf_proxy_ca.key      CA私钥
│   └── windsurf_proxy_ca.cer      DER格式证书
│
├── 测试
│   └── _e2e_test.py               E2E测试 (27项)
│
├── 文档
│   ├── README.md                  本文件 (统一架构)
│   ├── AGENTS.md                  Agent操作指引
│   ├── DEPENDENCY_AUDIT.md        依赖链真相 (六大强限制)
│   └── CodeFreeWindsurf_深度逆向报告.md  逆向工程报告
│
└── 运行时 (gitignored)
    ├── .guardian_state.json / guardian.log
    └── static/                    中枢静态文件目录
```

## 补丁清单 (15处)

| # | 类型 | 目标 | 效果 |
|---|------|------|------|
| 1 | Static | U5e 额度检查 | 永远返回true (无限额度) |
| 2 | Static | hasCapacity 容量检查 | 永远通过 |
| 3 | Static | 额度不足提示 | 预设为已关闭 |
| 4 | Static | planName 元数据 | 强制"Pro Ultimate" |
| 5 | Static | isEnterprise/hasPaidFeatures | 强制true (×3) |
| 6 | Static | Premium模型 | fastMode+stickyPremium+forge |
| 7 | Static | Premium命令模型 | premiumCommand+tabToJump |
| 8 | Static | Cascade Pro | webSearch/autoRun/commitMsg等5项 |
| 9 | Static | 社交/共享 | shareConversations+background |
| 10 | Static | 浏览器 | browserEnabled=true |
| 11 | Static | gRPC Metadata | impersonateTier="ENTERPRISE_SAAS" |
| 12 | Regex | hasCapacity | 适配变量名变化 |
| 13 | Regex | 额度警告重置 | 拦截dismiss状态重置 |
| 14 | Regex | planName | 适配变量名变化 |
| 15 | Regex | isFreeTier | teamsTier===UNSPECIFIED→false |

## 依赖链真相

> 详见 `DEPENDENCY_AUDIT.md`

```
Windsurf → CFW本地代理 → CFW后端(香港) → Codeium
```

- **15个客户端补丁 = UI化妆品** — 真正的Pro能力来自CFW后端的auth_token
- **auth_token有2h TTL** — CFW必须持续运行刷新
- **设备码绑定** — CFW绑定运行它的机器，其他机器通过网络共享
- **降级方案**: CFW不可用时 → 自建代理(Free-tier) + 补丁(隐藏限制UI)

## 部署状态

| 节点 | 状态 | 说明 |
|------|------|------|
| 阿里云中枢 | ✅ | FRP隧道18443 open, /hub/ 面板 |
| 台式机CFW | ✅ | CFW v2.0.5 :443, Guardian守护 |
| 笔记本 | ✅ | LAN直连台式机 57ms |
| 远程VM | ✅ | portproxy→aiotvr.xyz:18443 |
| 授权中枢面板 | 🆕 | https://aiotvr.xyz/hub/ |

## 还原（卸载）

```powershell
# 管理员PowerShell (远程VM):
netsh interface portproxy delete v4tov4 listenaddress=127.0.0.1 listenport=443
schtasks /Delete /TN "WindsurfPortProxy" /F
schtasks /Delete /TN "DaoRemoteAgent" /F
[Environment]::SetEnvironmentVariable("SSL_CERT_FILE", $null, "Machine")
certutil -delstore Root EE8978E69E0CFE3FBD6FFD7E511BE6337A2FC4F7
# 手动: 编辑hosts删除windsurf/codeium两行, 删除桌面Windsurf_Proxy.cmd

# 本地机器:
python windsurf_guardian.py --uninstall
python patch_windsurf.py --restore
```

## 底层原理

详见 `CodeFreeWindsurf_深度逆向报告.md` — CFW v1→v2.0.5逆向、JWT双Token、HS256签名、gRPC协议、Protobuf结构。
