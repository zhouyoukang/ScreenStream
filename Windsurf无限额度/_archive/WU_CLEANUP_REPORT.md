# WU无限额度 深度逆向+清理报告 (2026-03-12)

> 万法归宗·道本自然。去除一切多余配置，恢复Windsurf官方连接。

## 一、WU v1.5.6 MITM架构完整逆向

### 处理链路图
```
┌─ Windsurf (D:\Windsurf\Windsurf.exe v1.108.2) ──────────────────┐
│  尝试连接: server.codeium.com / server.self-serve.windsurf.com    │
└────────────────────────┬─────────────────────────────────────────┘
                         ↓ DNS解析
┌─ hosts文件劫持 ──────────────────────────────────────────────────┐
│  127.65.43.21 server.codeium.com                                  │
│  127.65.43.21 server.self-serve.windsurf.com                      │
│  # windsurf-mitm-proxy                                            │
└────────────────────────┬─────────────────────────────────────────┘
                         ↓ TLS连接 → 127.65.43.21:443
┌─ WU MITM Proxy (WindsurfUnlimited.exe 内置代理) ────────────────┐
│  监听: 127.65.43.21:443                                          │
│  CA证书: "O=Local Proxy, CN=Windsurf MITM CA"                    │
│    Thumbprint: CDFA1CDD50E00120F3E55CAB97F944371B8830B1          │
│    Expires: 2036-03-12 (安装在Cert:\LocalMachine\Root)           │
│  服务端证书: certs/server.crt (由CA签名)                          │
│  → 解密TLS → 注入无限额度 → 重加密                               │
└────────────────────────┬─────────────────────────────────────────┘
                         ↓ 代理转发
┌─ WU后端: https://windsurf-unlimited.chaogei.top ────────────────┐
│  → 转发至真实Codeium API (修改plan/credits信息)                   │
│  → 天卡模式: device_id=DESKTOP-MASTER-win32-13661d9498a9         │
│  → 积分: 820/5000                                                │
└──────────────────────────────────────────────────────────────────┘

★ 致命问题: WU停止时(已停止状态)
   Windsurf → 127.65.43.21:443 → SYN_SENT(无监听) → 连接超时
   → Gradle LSP失败 → "Initializing Gradle Language Server" 卡死
   → Codeium功能全部不可用
```

### WU在系统中的10项痕迹

| # | 类型 | 位置 | 作用 | 危害性 |
|---|------|------|------|--------|
| 1 | **hosts劫持** | `C:\Windows\System32\drivers\etc\hosts` | DNS重定向到127.65.43.21 | 🔴致命: WU停止→官方全断 |
| 2 | **MITM CA证书** | `Cert:\LocalMachine\Root` | 信任WU伪造的TLS证书 | 🔴致命: 安全漏洞 |
| 3 | **WU应用** | `%APPDATA%\Local\Programs\WindsurfUnlimited\` | 180MB Electron fork | 🟡占用空间 |
| 4 | **WU Roaming** | `%APPDATA%\Roaming\windsurf-unlimited\` | certs/proxy/session/cache | 🟡残留数据 |
| 5 | **WU_Guardian** | 计划任务 `pythonw wu_guardian.py --daemon` | LogonTrigger守护进程 | 🔴会复活WU |
| 6 | **WU Start Menu** | `Windsurf Unlimited.lnk` | 启动WU的快捷方式 | 🟡误启动风险 |
| 7 | **Windsurf_Proxy.cmd** | 桌面 | 旧CFW时代启动器(注入SSL覆盖+host-resolver) | 🔴破坏官方连接 |
| 8 | **ProgramData证书** | `cfw_server_cert.pem` + `windsurf_proxy_ca.pem` | 旧CFW/WU证书残留 | 🟡垃圾文件 |
| 9 | **WU内部证书** | `windsurf-unlimited\certs\` | ca.crt/ca.key/server.crt/server.key | 🟡MITM密钥对 |
| 10 | **System Proxy** | ProxyEnable=1, 127.0.0.1:7890 | Vortex Helper系统代理 | ✅正常(非WU) |

## 二、三套无限额度系统对比

| 系统 | 原理 | 状态 | 依赖 |
|------|------|------|------|
| **WindsurfUnlimited v1.5.6** | MITM代理+hosts劫持 | ⛔已清理 | chaogei.top后端+天卡 |
| **CFW v2.0.5** | 独立Electron应用+证书注入 | ⛔已归档(笔记本) | CFW后端(香港) |
| **JS Patches (15处)** | 客户端UI修改 | ⚠️仍在 | 仅cosmetic,不提供实际额度 |
| **Vortex Helper** | Clash内核代理(正常翻墙) | ✅运行中 | 非无限额度工具,正常代理 |

### JS补丁真相
> **JS patches alone do NOT provide unlimited credits!**
> - 补丁 = 客户端UI修改(显示"Pro Ultimate")
> - 服务端认证 = 独立层 → 原版Windsurf发送请求到Codeium → 无有效订阅则`permission_denied`
> - 补丁对官方连接**无害** — 仅影响UI显示

## 三、已执行清理操作 (2026-03-12 21:30 CST)

| Step | 操作 | 状态 | 验证 |
|------|------|------|------|
| 1 | 禁用WU_Guardian计划任务 | ✅ | `Get-ScheduledTask WU_Guardian → Disabled` |
| 2 | 杀死WU进程(4个) | ✅ | `Get-Process WindsurfUnlimited → 0` |
| 3 | 重写hosts文件(仅保留localhost) | ✅ | `127.0.0.1 localhost` + `::1 localhost` |
| 4 | 删除MITM CA证书 | ✅ | `Cert:\LocalMachine\Root` 无MITM残留 |
| 5 | 刷新DNS缓存 | ✅ | `ipconfig /flushdns` |
| 6 | 删除WU Start Menu快捷方式 | ✅ | `Windsurf Unlimited.lnk` 已删除 |
| 7 | 删除WU_Guardian计划任务 | ✅ | `Unregister-ScheduledTask` |
| 8 | 禁用Windsurf_Proxy.cmd | ✅ | 重命名为`.DISABLED` |
| 9 | 删除ProgramData证书文件 | ✅ | `cfw_server_cert.pem` + `windsurf_proxy_ca.pem` 已删除 |
| 10 | SSL环境变量验证 | ✅ | Machine级无SSL_CERT_FILE/NODE_EXTRA_CA_CERTS |

## 四、连接验证结果

| 测试 | 结果 | 说明 |
|------|------|------|
| DNS: server.codeium.com | ✅ 35.223.238.178 | 真实Google Cloud IP |
| DNS: server.self-serve.windsurf.com | ✅ 34.49.14.144 | 真实Google Cloud IP |
| curl via Vortex(7890) → codeium | ✅ HTTP 404 (3.7s) | TLS成功(404=无根页面正常) |
| curl via Vortex(7890) → self-serve | ✅ HTTP 404 (3.6s) | TLS成功 |

## 五、当前正确架构

```
Windsurf (D:\Windsurf\v1.108.2)
  ↓ settings.json: proxySupport="override"
  ↓ 使用系统代理
Vortex Helper (:7890, Clash内核)
  ↓ 香港/日本/台湾节点 (IEPL/中转)
  ↓ 正常HTTPS转发(无MITM)
真实Codeium服务器 (35.223.238.178 / 34.49.14.144)
  ↓ 标准TLS验证
  ↓ 根据账号订阅状态返回额度
```

### Windsurf settings.json 关键配置
- `http.proxySupport: "override"` — 使用系统代理 ✅
- `http.proxyStrictSSL: true` — 验证TLS证书 ✅

### 系统代理
- `ProxyEnable: 1`, `ProxyServer: 127.0.0.1:7890` — Vortex Helper ✅

## 六、未清理项(可选)

| 项目 | 原因 | 建议 |
|------|------|------|
| WU应用(~180MB) | 用户可能未来想用 | 可通过卸载器删除 |
| WU Roaming数据 | 含session/cache | 可安全删除 |
| JS补丁(15处) | 仅cosmetic,无害 | 保留(不影响官方连接) |
| Vortex Helper | 正常翻墙工具,非WU | 必须保留(中国访问Codeium) |

## 七、恢复操作(如需重新启用WU)

```powershell
# 1. 恢复hosts
Add-Content C:\Windows\System32\drivers\etc\hosts "127.65.43.21 server.codeium.com"
Add-Content C:\Windows\System32\drivers\etc\hosts "127.65.43.21 server.self-serve.windsurf.com"
# 2. 重新安装MITM CA
Import-Certificate -FilePath "$env:APPDATA\windsurf-unlimited\certs\ca.crt" -CertStoreLocation Cert:\LocalMachine\Root
# 3. 启动WU
Start-Process "$env:LOCALAPPDATA\Programs\WindsurfUnlimited\WindsurfUnlimited.exe"
```
