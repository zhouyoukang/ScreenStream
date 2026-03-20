# WindsurfUnlimited v1.5.6 深度逆向报告
> 生成时间: 2026-03-12 16:53:20
> 诊断评分: 10.5/19 (55%)

## 一、完整架构逆向

### 1.1 技术栈
| 组件 | 技术 | 说明 |
|------|------|------|
| 框架 | Electron + electron-builder | Tauri风格,非Tauri |
| 前端 | React 18 + Zustand 5 + Lucide Icons | SPA |
| 后端 | Node.js http2.createSecureServer | HTTP/2 TLS MITM |
| 加密 | AES-256-GCM + HMAC-SHA256 | 客户端↔服务端全加密 |
| 证书 | node-forge RSA 2048 + 自签CA | 动态生成 |
| 代理 | SOCKS5 + HTTP Proxy Agent | 支持上游代理 |
| 更新 | GitHub Release (chaogei/windsurf-unlimited) | electron-updater |

### 1.2 五层MITM架构
```
┌─────────────────────────────────────────────────────┐
│  Layer 1: hosts劫持                                  │
│  127.65.43.21 server.self-serve.windsurf.com        │
│  127.65.43.21 server.codeium.com                    │
│  标记: # windsurf-mitm-proxy                        │
├─────────────────────────────────────────────────────┤
│  Layer 2: CA证书信任                                 │
│  CN=Windsurf MITM CA, O=Local Proxy                 │
│  安装到 cert:\LocalMachine\Root                    │
├─────────────────────────────────────────────────────┤
│  Layer 3: HTTP/2 TLS MITM服务器                      │
│  127.65.43.21:443 (node http2.createSecureServer)   │
│  自签server.crt (SAN=两个域名)                       │
├─────────────────────────────────────────────────────┤
│  Layer 4: Windsurf settings.json                     │
│  http.proxyStrictSSL=false                           │
│  http.proxySupport=off                               │
├─────────────────────────────────────────────────────┤
│  Layer 5: Windsurf user_settings.pb                  │
│  detect_proxy=1 (protobuf field 34)                  │
│  自动修改Windsurf的protobuf二进制设置                 │
└─────────────────────────────────────────────────────┘
```

### 1.3 数据流
```
Windsurf Language Server
  ↓ gRPC (server.self-serve.windsurf.com:443)
  ↓ DNS解析→127.65.43.21 (hosts劫持)
  ↓ TLS握手(WU自签CA)
WU MITM Proxy (127.65.43.21:443)
  ├─ /RecordAnalytics等8类 → 直接返回200空(节省积分)
  ├─ /GetChatMessage,/GetCompletions → 流式代理
  │   ↓ AES-256-GCM加密 + HMAC签名
  │   ↓ POST chaogei.top/api/v1/stream-proxy
  │   ↓ 服务端持有真Pro账号→调用Codeium API
  │   ↓ 流式响应SSE逐帧解密→转发给Windsurf
  └─ 其他gRPC → 普通代理
      ↓ POST chaogei.top/api/v1/proxy
      ↓ 服务端统一处理→返回

inference.codeium.com (推理) → 直连(不经过代理)
  ↓ 使用代理获取的auth_token
  ↓ Codeium真实推理服务器
```

### 1.4 加密协议
| 组件 | 算法 | 密钥来源 |
|------|------|---------|
| 请求加密 | AES-256-GCM (12B IV + 16B AuthTag) | client_secret SHA256 |
| 请求签名 | HMAC-SHA256 | client_secret |
| 响应验证 | HMAC-SHA256签名验证 + AES-GCM解密 | client_secret |
| API Key | 从state.vscdb提取Windsurf apiKey | 本地读取 |
| 协议版本 | "2" | 硬编码 |

### 1.5 Telemetry过滤(积分节省)
以下8类请求被WU直接拦截返回200,不消耗积分:
1. `/RecordAnalytics`
2. `/RecordCortexTrajectory`
3. `/RecordCortexTrajectoryStep`
4. `/RecordAsyncTelemetry`
5. `/RecordStateInitialization`
6. `/RecordCortexExecutionMeta`
7. `/RecordCortexGeneratorMeta`
8. `/RecordTrajectorySegment`

### 1.6 vs CFW v2.0.5 对比
| 维度 | WU v1.5.6 | CFW v2.0.5 |
|------|-----------|------------|
| 框架 | Electron | Tauri/Rust 9.2MB |
| MITM IP | 127.65.43.21 | 127.0.0.1 |
| 后端 | chaogei.top(中国) | 38.175.203.46(日本) |
| 认证 | 卡密制(天卡/月卡) | 授权码(免费) |
| 积分 | 5000/天卡 | 无限制 |
| 加密 | AES-256-GCM+HMAC | 直接gRPC转发 |
| Telemetry | 8类过滤 | 全部转发 |
| detect_proxy | 自动修改protobuf | 不处理 |
| 安全软件检测 | ✅ 主动检测10种 | ❌ |
| 代理软件检测 | ✅ 检测20种 | ❌ |
| hosts备份 | ✅ .mitm_backup | ❌ |

## 二、限速/请求失败根因分析

### 2.1 积分耗尽 (52/5000)
- 天卡5000积分 ≈ 每个gRPC请求消耗≥1积分
- 高消耗模型(Claude Opus 4.6) × 大系统提示(15K tokens) = 快速消耗
- 每次Continue = 新请求 = 新积分消耗
- **解决**: 切换Windsurf模型到SWE-1.6 (creditMultiplier=0)

### 2.2 portproxy冲突
- 旧CFW portproxy: 127.0.0.1:443→192.168.31.179:443
- svchost.exe(IP Helper)占用127.0.0.1:443
- **解决**: 删除旧portproxy规则

### 2.3 多证书冲突
- 发现5个Root CA证书(WU+CFW旧+自建代理)
- TLS握手时可能选择错误证书
- **解决**: 清理旧证书,仅保留WU的MITM CA

## 三、诊断结果

**评分: 10.5/19 (55%)**

| 状态 | 检查项 | 详情 |
|------|--------|------|
| ✅ | WU安装 | 180MB @ C:\Users\Administrator\AppData\Local\Programs\WindsurfUnlimited |
| ❌ | WU进程 | 未运行 |
| ✅ | WU会话 | 天卡 | 剩余22.8h | https://windsurf-unlimited.chaogei.top |
| ✅ | 设备ID | DESKTOP-MASTER-win32-13661d9498a9 |
| ✅ | WU证书 | 5个文件 @ C:\Users\Administrator\AppData\Roaming\windsurf-unlimited\certs |
| ❌ | WU代理监听 | 127.65.43.21:443 未监听 |
| ⚠️ | 端口冲突 | 127.0.0.1:443 被 svchost.exe(PID 5548) 占用 |
| ❌ | TLS握手 | 失败: [WinError 10061] 由于目标计算机积极拒绝，无法连接。 |
| ❌ | DNS server.self-serve.windsur | → 34.49.14.144 (应为127.65.43.21) |
| ❌ | DNS server.codeium.com | → 35.223.238.178 (应为127.65.43.21) |
| ❌ | WU hosts标记 | 缺失 |
| ❌ | WU hosts IP | 127.65.43.21不在hosts中 |
| ⚠️ | 证书检查 | PowerShell执行失败: Command 'powershell -Command "Get-ChildItem cert:\LocalMachine\Root | Where-Object { $_.Subject -match 'MITM|Windsurf|Proxy|Local' } | Select-Object Subject, Thumbprint, NotAfter | ConvertTo-Json"' returned non-zero exit status 1. |
| ⚠️ | portproxy冲突 | 127.0.0.1       443         192.168.31.179  443 |
| ✅ | proxyStrictSSL | false (MITM兼容) |
| ✅ | proxySupport | off (不干扰MITM) |
| ✅ | user_settings.pb | 82519B (WU自动管理detect_proxy) |
| ✅ | Windsurf进程 | 13个进程 |
| ✅ | 积分分析 | 建议已生成 |

### ❌ 错误
- WU进程: 未运行
- WU代理监听: 127.65.43.21:443 未监听
- TLS握手: 失败: [WinError 10061] 由于目标计算机积极拒绝，无法连接。
- DNS server.self-serve.windsur: → 34.49.14.144 (应为127.65.43.21)
- DNS server.codeium.com: → 35.223.238.178 (应为127.65.43.21)
- WU hosts标记: 缺失
- WU hosts IP: 127.65.43.21不在hosts中

### ⚠️ 警告
- 端口冲突: 127.0.0.1:443 被 svchost.exe(PID 5548) 占用
- 证书检查: PowerShell执行失败: Command 'powershell -Command "Get-ChildItem cert:\LocalMachine\Root | Where-Object { $_.Subject -match 'MITM|Windsurf|Proxy|Local' } | Select-Object Subject, Thumbprint, NotAfter | ConvertTo-Json"' returned non-zero exit status 1.
- portproxy冲突: 127.0.0.1       443         192.168.31.179  443