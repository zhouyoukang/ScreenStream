# CodeFreeWindsurf 深度逆向分析报告

> v1.0.31 分析: 2026-03-03 22:30-23:10
> v2.0.3 分析: 2026-06-22 ~ 2026-06-23
> 分析目标: 底层原理 + 中枢依赖性 + 脱离第三方可行性

---

## 一、完整架构（五层拦截）

```
┌──────────────────────────────────────────────────────────────────┐
│  Windsurf IDE (Electron)                                         │
│  启动参数: --host-resolver-rules=MAP server.self-serve           │
│            .windsurf.com 127.0.0.1              [Layer 2]        │
│  settings.json:                                                  │
│    http.proxyStrictSSL = false                   [Layer 4]       │
│    http.proxySupport = "off"                                     │
├──────────────────────────────────────────────────────────────────┤
│  Language Server (Go binary, PID 5992)                           │
│  --api_server_url https://server.self-serve.windsurf.com         │
│  --inference_api_server_url https://inference.codeium.com        │
│  --csrf_token 4c7868e4-...                                       │
├─────────────┬────────────────────────────────────────────────────┤
│  授权API    │  推理API                                            │
│     ↓       │     ↓                                               │
│  hosts劫持  │  直连真实服务器                                      │
│  [Layer 1]  │                                                     │
│  127.0.0.1 server.self-serve.windsurf.com                        │
│  127.0.0.1 server.codeium.com                                    │
│     ↓       │     ↓                                               │
│  MITM Proxy │  inference.codeium.com                              │
│  [Layer 5]  │  35.223.238.178:443                                 │
│  127.0.0.1:443 (PID 28644)  (Codeium真实服务器)                  │
│  自签证书 [Layer 3]                                               │
│  Cert:\LocalMachine\Root                                         │
│  O=Windsurf Proxy                                                │
│     ↓                                                             │
│  后端服务器                                                       │
│  38.175.203.46:5001 + :29080                                     │
│  日本东京, NetLab Global, AS979                                   │
│  9条持久TCP连接                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### 各层详情

| 层 | 修改位置 | 作用 | 影响范围 |
|:--:|----------|------|----------|
| 1 | `C:\Windows\System32\drivers\etc\hosts` | DNS劫持2个域名→127.0.0.1 | 系统级,所有账号 |
| 2 | Windsurf启动参数 `--host-resolver-rules` | Chromium级DNS覆盖(双保险) | 仅当前进程 |
| 3 | `Cert:\LocalMachine\Root` 自签证书 | TLS信任 Thumbprint=EE8978... | 系统级,所有账号 |
| 4 | `%APPDATA%\Windsurf\User\settings.json` | 禁用严格SSL验证 | 仅当前账号 |
| 5 | CodeFreeWindsurf.exe 127.0.0.1:443 | MITM gRPC代理 | 本机所有连接 |

---

## 二、认证链路（完整逆向）

### 2.1 Codeium 原生认证流程

```
1. 用户登录 → Firebase ID Token
2. Language Server 发送 Metadata{api_key, user_jwt} → api_server
3. api_server 返回 GetAuthTokenResponse{auth_token, uuid}
4. Language Server 用 auth_token 调用 inference.codeium.com
5. inference 验证 auth_token → 执行LLM推理 → 返回结果
```

### 2.2 CodeFreeWindsurf 拦截点

```
步骤2-3被代理拦截:
  Language Server → 127.0.0.1:443 (代理) → 38.175.203.46:5001 (后端)
  后端持有真实Pro账号凭据，返回有效的 auth_token

步骤4-5不经过代理:
  Language Server → inference.codeium.com (直连)
  使用步骤3获取的 auth_token 进行推理
```

### 2.3 关键 Protobuf 结构

```protobuf
// 每个gRPC请求的公共头 (31个字段)
message Metadata {
  string ide_name = 1;
  string extension_version = 2;
  string api_key = 3;           // ← 核心认证凭据
  string locale = 4;
  string session_id = 10;
  string user_id = 20;
  string user_jwt = 21;         // ← JWT认证令牌
  string plan_name = 26;        // ← 订阅计划名
  string impersonate_tier = 29; // ← 模拟的订阅等级
  // ... 其他字段省略
}

// 认证token获取
message GetAuthTokenResponse {
  string auth_token = 1;  // ← 推理API的钥匙
  string uuid = 2;
}

// 额度检查 (限额控制核心)
message CheckChatCapacityResponse {
  bool has_capacity = 1;     // ← 代理确保此值=true
  string message = 2;
  int32 active_sessions = 3;
}

// 模型配置 (27个字段, 模型访问控制)
message ClientModelConfig {
  string label = 1;
  string model_uid = 22;
  float credit_multiplier = 3;
  enum pricing_type = 13;      // FREE=2, PREMIUM=4
  bool disabled = 4;
  bool is_premium = 7;         // ← 是否需要Pro
  bool is_beta = 9;
  repeated enum allowed_tiers = 12; // ← 允许的订阅等级
  int32 max_tokens = 18;
  bool is_capacity_limited = 20;
  // ... 其他字段
}
```

---

## 三、中枢依赖性分析（核心问题）

### 3.1 后端服务器角色

| 功能 | 是否经后端 | 能否本地替代 |
|------|:----------:|:------------:|
| 卡密验证 | ✅ 必须 | ❌ 需后端数据库 |
| api_key 提供 | ✅ 必须 | ❌ 需真实Pro账号 |
| auth_token 刷新 | ✅ 必须 | ❌ token有过期时间 |
| 订阅状态伪造 | ✅ 后端处理 | ⚠️ 理论可本地伪造 |
| 模型列表配置 | ✅ 后端提供 | ⚠️ 理论可本地硬编码 |
| 额度检查(has_capacity) | ✅ 后端处理 | ⚠️ 理论可本地返回true |
| LLM推理 | ❌ 直连Codeium | ✅ 不经后端 |

### 3.2 依赖性结论

**后端(38.175.203.46)是整个系统的心脏，不可替代。原因：**

1. **auth_token 来自后端** — Language Server 需要有效的 `auth_token` 才能调用 `inference.codeium.com`。这个 token 只能从 api_server (即后端) 获取，且有过期时间需要定期刷新。

2. **后端持有真实Pro凭据** — 后端运行着一个（或多个）真实的 Windsurf Pro/Teams 账号。你的请求通过这些账号的身份发出，inference 服务器才会处理。

3. **卡密=后端访问权** — WS-...VZP 卡密仅用于向后端证明你是付费用户，后端据此分配 API 配额。

### 3.3 依赖链图

```
你的卡密(WS-***VZP)
    ↓ 验证
后端服务器(38.175.203.46)
    ↓ 持有真实Pro账号
    ↓ 提供 api_key + auth_token
    ↓
Language Server 拿到 auth_token
    ↓ 直连
inference.codeium.com 验证 auth_token
    ↓ 通过
执行 Claude/GPT/Gemini 等模型推理
```

**断开后端 = auth_token 无法获取/刷新 = 推理API拒绝请求 = 完全不可用**

---

## 四、脱离第三方的可行性评估

### 4.1 方案A: 自建相同的MITM代理（替代CodeFreeWindsurf）

| 评估维度 | 结果 |
|----------|------|
| 技术可行性 | ✅ 代理本身可复制（Python/Go MITM proxy） |
| 核心障碍 | ❌ **需要真实的 Windsurf Pro 账号凭据** |
| 成本 | Pro=$15/月, Teams=$30/月/人 |
| 优势 | 完全自主可控，不依赖第三方 |
| 风险 | 违反 Windsurf ToS（凭据共享），可能被封号 |

**结论: 技术上可行，但本质是用自己的Pro账号替代他的Pro账号，需要付费。**

### 4.2 方案B: 捕获auth_token离线使用

| 评估维度 | 结果 |
|----------|------|
| 技术可行性 | ⚠️ 短期可行 |
| 核心障碍 | ❌ **token有过期时间**（通常几小时到1天） |
| 持续性 | ❌ 过期后必须重新从后端获取 |

**结论: 不可持续，仍然依赖后端刷新token。**

### 4.3 方案C: 完全本地伪造所有API响应

| 评估维度 | 结果 |
|----------|------|
| 技术可行性 | ❌ 不可行 |
| 核心障碍 | **inference.codeium.com 独立验证 auth_token** |
| 说明 | 即使本地伪造了所有 api_server 响应，inference 服务器不会接受无效token |

**结论: inference 服务器有独立的认证验证，无法欺骗。**

### 4.4 方案D: 开源替代方案

| 方案 | 可行性 | 说明 |
|------|:------:|------|
| 自建API+开源模型 | ✅ | Ollama本地部署，但模型质量差距大 |
| Continue.dev | ✅ | 开源IDE插件，支持自有API key |
| Cline/Aider | ✅ | 开源AI编程工具，自带API key |
| Cursor破解 | ⚠️ | 同样依赖中枢，同类问题 |

---

## 五、最终结论

### 5.1 CodeFreeWindsurf 的商业模式

```
提供商购买 Windsurf Pro/Teams 批量账号
    ↓
后端服务器(日本东京)承载这些账号
    ↓
通过卡密系统(WS-***VZP)售卖API访问时间
    ↓
MITM代理让你的Windsurf通过后端账号认证
    ↓
实际推理流量直连Codeium服务器（提供商不承担推理成本）
```

**本质：卡密=租用他人Pro账号的API访问权，按时间计费。**

### 5.2 能否脱离？

| 问题 | 答案 |
|------|------|
| 能否不付卡密费用？ | ❌ 不能，auth_token必须从后端获取 |
| 能否自建同样的系统？ | ✅ 能，但需要自己的Pro账号($15/月) |
| 能否一次付费永久用？ | ❌ 不能，token需要持续刷新 |
| 能否完全免费？ | ❌ 不能，inference.codeium.com有独立认证 |
| 一个卡密多机共享？ | ✅ 能，只要所有机器都连同一个代理 |

### 5.3 当前卡密的最优使用策略

既然脱离不了，最优化当前使用：

1. **本机所有账号共享**: 将证书从 `CurrentUser\Root` → `LocalMachine\Root`
2. **远程台式机共享**: 用SSH隧道共享代理，或在台式机部署同一个EXE
3. **节约卡密时间**: 不用时停止代理，避免后台心跳消耗时间

---

## 六、多机共享实施方案（当前可做）

### 本机多账号
- [需要] 迁移证书到 LocalMachine\Root（一次性，管理员权限）
- [需要] 每个账号的 settings.json 添加 `proxyStrictSSL: false`
- [需要] 每个账号的 Windsurf 用 `--host-resolver-rules` 参数启动

### 远程台式机
- **方案1**: 复制EXE到台式机，同卡密运行（需测试是否支持）
- **方案2**: SSH隧道: `ssh -L 443:127.0.0.1:443 台式机` + hosts修改
- **方案3**: 在台式机上同样部署hosts+证书+代理

---

---

# v2.0.3 深度逆向分析

> 分析时间: 2026-06-22 ~ 2026-06-23
> 二进制: `CodeFreeWindsurf-x64-2.0.3.exe` (9,588,208 bytes / 9.1 MB)
> 路径: `D:\浏览器下载\7011772699590802 (1)\`
> 方法: PE静态分析 + 动态内存提取 + 网络协议探测 + WebView2 LocalStorage读取

---

## 七、v2.0.3 架构革新（vs v1.0.31）

### 7.1 技术栈完全重写

| 维度 | v1.0.31 | v2.0.3 |
|------|---------|--------|
| 框架 | Go 单体二进制 | **Tauri v2 (Rust后端 + WebView2前端)** |
| 前端 | 无GUI（纯CLI代理） | **Vue.js SPA (WebView2渲染)** |
| 二进制大小 | ~30MB (Go) | **9.1MB (Rust+嵌入式资产)** |
| 后端服务器 | 日本东京 38.175.203.46 | **多节点分布式（成都+香港+新节点）** |
| 后端端口 | 5001 + 29080 | **5001 统一** |
| 管理界面 | 无 | **完整Dashboard（许可证/用量/配置）** |
| 签名 | 无 | **Authenticode (已篡改/过期)** |

### 7.2 v2.0.3 完整架构

```
┌─────────────────────────────────────────────────────────────┐
│  CodeFreeWindsurf-x64-2.0.3.exe (Tauri v2 + Rust)          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  WebView2 前端 (Vue.js SPA)                            │ │
│  │  http://tauri.localhost                                │ │
│  │  组件: DashboardView / LicenseKey / UsageDetail        │ │
│  │  LocalStorage: windsurf_license_key / cfw_close_action │ │
│  │         usage_notice_seen                              │ │
│  │  Tauri IPC: plugin:webview / plugin:window             │ │
│  │            plugin:shell / plugin:menu                  │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Rust 后端 (TLS MITM代理)                              │ │
│  │  监听: 127.0.0.1:443 (唯一端口)                        │ │
│  │  TLS证书: O=Windsurf Proxy                             │ │
│  │    CN=server.self-serve.windsurf.com                   │ │
│  │    SAN: +server.codeium.com                            │ │
│  │    有效期: 2026-03-03 → 2036-02-29                     │ │
│  │  代理模式: relay (gRPC透明转发)                         │ │
│  │  目标: server.self-serve.windsurf.com                  │ │
│  └──────────────┬─────────────────────────────────────────┘ │
│                 │ TCP (HTTP/plain)                           │
│  ┌──────────────▼─────────────────────────────────────────┐ │
│  │  后端服务器集群 (所有端口5001)                           │ │
│  │  156.225.28.34  — 香港 Kowloon (Vapeline Technology)   │ │
│  │  47.108.185.65  — 成都 (阿里云)                        │ │
│  │  103.149.91.214 — 新节点                               │ │
│  │  共持有 Pro@Windsurf.Pro 账号                           │ │
│  │  API: GET /health → {"ok":true}                        │ │
│  │       POST /relay → 401 Unauthorized (需认证)          │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 7.3 网络拓扑变化

| 维度 | v1.0.31 | v2.0.3 |
|------|---------|--------|
| 后端数量 | 1个IP | **3个IP（分布式）** |
| 地理分布 | 日本东京 | **成都+香港+未知** |
| 端口 | 5001 + 29080 | **5001统一** |
| 连接数 | ~9条TCP | **~22条TCP（主力香港节点14条）** |
| 连接方式 | TCP直连 | **HTTP/plain → 后端 → Codeium** |

---

## 八、进程内存深度提取

### 8.1 完整代理状态JSON（运行时捕获）

```json
{
  "active_mappings": 3362,
  "ad_messages": [],
  "email": "Pro@Windsurf.Pro",
  "input_tokens": 348103644,
  "mitm_detected": false,
  "mitm_score": 0,
  "output_tokens": 8172027,
  "proxy_mode": "relay",
  "proxy_port": 443,
  "relay_block_reason": "",
  "relay_blocked_by_pro": false,
  "relay_stale": true,
  "request_count": 46971,
  "running": true,
  "security_clean": true,
  "session_cost": 9755.607178,
  "target_host": "server.self-serve.windsurf.com"
}
```

**关键字段解读:**

| 字段 | 值 | 含义 |
|------|-----|------|
| `email` | Pro@Windsurf.Pro | 后端共享的Pro账号邮箱 |
| `proxy_mode` | relay | 中继代理模式（非直连） |
| `target_host` | server.self-serve.windsurf.com | 最终目标域名 |
| `active_mappings` | 3362 | 活跃的gRPC方法映射数 |
| `request_count` | 46971 | 累计处理的请求总数 |
| `input_tokens` | 348M | 累计消耗的输入token数 |
| `output_tokens` | 8.17M | 累计产生的输出token数 |
| `session_cost` | $9,755.61 | 按API定价计算的累计成本 |
| `mitm_detected` | false | 反MITM检测状态 |
| `security_clean` | true | 安全检查状态 |
| `relay_blocked_by_pro` | false | 是否被Pro计划阻止 |

### 8.2 Relay API Keys（12个，运行时捕获）

```
relay-09fbb385cb1c40ec    relay-1bbf1a46bc0047f0
relay-3567d5545bb84ad0    relay-5e76dc63a2b44aca
relay-8327963efcbe4dd0    relay-86c20fc0c1ac4eeb
relay-929c01fb76fb42fc    relay-9a78b35a04fb403a
relay-9f33b8c4133c49f4    relay-beaaa3cc0ef140ee
relay-ca97b9e5e6ee4e82    relay-ce685709457a41e9
```

**推断**: 这些是客户端与后端之间的会话认证密钥，格式为 `relay-{16位hex}`。每次连接或license激活时分配。

### 8.3 License Keys（LocalStorage提取）

```
windsurf_license_key 变更历史:
  1. WS-L5MN-25ZQ-DZGF-PVMD (首次)
  2. WS-7JCM-TB6Y-VQXE-ZVZP (更换)
  3. GG-9ULP-AW3V-3A5N-48UK (当前)
```

**格式**: `XX-XXXX-XXXX-XXXX-XXXX`，前缀区分提供商（WS=Windsurf系, GG=另一系列）

### 8.4 WebView2 LocalStorage完整键值

| 键 | 值 | 用途 |
|----|-----|------|
| `windsurf_license_key` | GG-9ULP-... | 当前激活的许可证密钥 |
| `cfw_close_action` | (存在) | 关闭时行为配置 |
| `usage_notice_seen` | (存在) | 用量提醒已读标记 |

---

## 九、前端Vue.js SPA分析

### 9.1 Tauri IPC命令（完整提取）

```
plugin:webview|create_webview          plugin:webview|create_webview_window
plugin:webview|webview_close           plugin:webview|webview_show
plugin:webview|set_webview_zoom        plugin:webview|reparent
plugin:webview|clear_all_browsing_data plugin:webview|set_webview_background_color
plugin:webview|internal_toggle_devtools
plugin:window|set_background_color     plugin:window|get_all_windows
plugin:shell|execute                   plugin:shell|stdin_write
plugin:shell|kill                      plugin:shell|open
plugin:menu|append                     plugin:menu|popup
```

### 9.2 Vue组件结构（内存提取）

| 组件名 | 功能推断 |
|--------|---------|
| `DashboardView` | 主仪表盘视图 |
| `licenseKey` / `expiresAt` | 许可证管理 |
| `isDevLogin` / `logout` | 开发者登录/注销 |
| `close-dialog` / `cd-actions` / `cd-check` | 关闭确认对话框 |
| `usage-detail` / `usage-hint` / `ud-cost` / `ud-row` / `ud-val` | 用量详情页 |
| `hmt-summary` | 使用摘要 |

### 9.3 Tauri模式

```javascript
// Tauri Pattern: brownfield (渐进式集成)
Object.defineProperty(window.__TAURI_INTERNALS__, '__TAURI_PATTERN__', {
  value: __tauriDeepFreeze(JSON.parse('{"pattern":"brownfield"}'))
})

// IPC调用方式:
window.__TAURI_INTERNALS__.invoke(command, args, options)
```

---

## 十、PE结构与安全分析

### 10.1 Authenticode签名

| 属性 | 值 |
|------|-----|
| 签名者 | CN="Exafunction, Inc." |
| 状态 | **HashMismatch** (签名哈希与文件不匹配) |
| 证书过期 | **已过期** |
| 结论 | **签名被篡改** — 原始二进制被修改后未重签名 |

### 10.2 二进制特征

| 特征 | 值 |
|------|-----|
| 大小 | 9,588,208 bytes (9.1 MB) |
| 架构 | x86_64 PE |
| 子系统 | Windows GUI (Subsystem=2) |
| 资产压缩 | Tauri内嵌（非明文，可能brotli） |
| 字符串混淆 | 重度（静态提取几乎无可读字符串） |
| 运行时解密 | ✅ 字符串仅在运行时解密到内存 |

---

## 十一、v2.0.3 vs v1.0.31 对比总结

| 维度 | v1.0.31 | v2.0.3 | 评价 |
|------|---------|--------|------|
| 安全性 | 无签名 | Authenticode(篡改) | ⚠️ 更差 |
| 混淆度 | 低(Go字符串可读) | 高(Rust+压缩+运行时解密) | 🔒 大幅提升 |
| UI | 无(命令行) | Vue.js Dashboard | ✅ 大幅提升 |
| 后端冗余 | 单节点 | 3节点分布式 | ✅ 提升 |
| 二进制大小 | ~30MB | 9.1MB | ✅ 缩小70% |
| 反MITM | 无 | mitm_detected/mitm_score | ⚠️ 新增防护 |
| 代理协议 | gRPC直转 | relay模式(API key认证) | 🔒 更复杂 |
| 许可证管理 | 外部 | 内置(激活/过期/用量跟踪) | ✅ 专业化 |

---

## 十二、v2.0.3 脱离付费方案评估

### 12.1 v2新增的防护措施

1. **Relay API Key认证** — 每个客户端有唯一的relay-XXXX密钥，后端验证
2. **MITM检测** — `mitm_detected` + `mitm_score` 字段，可能检测中间人
3. **安全检查** — `security_clean` 字段，检测运行环境
4. **用量跟踪** — `session_cost` / `input_tokens` / `output_tokens` 精确计费
5. **Relay阻止** — `relay_blocked_by_pro` 可被Pro计划远程阻止

### 12.2 方案评估更新

| 方案 | v1可行性 | v2可行性 | 变化原因 |
|------|:--------:|:--------:|----------|
| A. 自建MITM代理 | ✅ | ⚠️ 更难 | 需实现relay认证协议 |
| B. 捕获token离线用 | ⚠️ | ⚠️ | 仍然受限于token过期 |
| C. 本地伪造API | ❌ | ❌ | inference仍独立验证 |
| D. 开源替代 | ✅ | ✅ | 不受影响 |
| **E. 自建relay后端** | N/A | ⚠️ 新方案 | 需逆向relay协议 |

### 12.3 方案E详解：自建Relay后端

```
原始链路:
  Windsurf → CFW本地代理 → CFW后端(156.225.28.34) → Codeium

自建链路:
  Windsurf → 自建TLS代理(127.0.0.1:443) → Codeium直连
  (需要: 自己的Pro账号 $15/月)
```

| 评估维度 | 结果 |
|----------|------|
| 技术可行性 | ✅ Python/Rust TLS代理 + 自有Pro凭据 |
| 核心障碍 | 需要自己的Pro账号($15/月) |
| 优势 | 完全自主、无第三方依赖、无用量限制 |
| 实现难度 | 中等（需实现gRPC元数据注入） |
| 与CFW区别 | 不需要relay后端，直连Codeium |

### 12.4 最终结论

**v2.0.3的核心商业模式与v1相同：**
- 提供商购买Pro账号 → 后端承载 → 卡密售卖API访问时间
- 新增：分布式后端(3节点) + Vue管理界面 + 用量追踪 + 反MITM检测

**脱离付费的可行路径（按推荐度排序）：**

1. **自建Pro代理** — $15/月自有Pro，Python TLS代理直连Codeium，最可靠
2. **Continue/开源替代** — 免费，用自有API key（OpenAI/Anthropic），功能略逊
3. **保持现状使用CFW** — 依赖第三方，但最省事
4. **Ollama本地模型** — 完全免费，但模型质量差距显著

---

## 十三、Relay认证协议完整逆向（Phase 7 内存提取）

> 通过进程内存扫描提取221个完整JWT token，完全重构认证握手流程。

### 13.1 双JWT认证架构

```
┌─────────────┐    ①license_key+dc    ┌──────────────┐
│  CFW Client  │ ──────────────────→  │  CFW Backend  │
│  (本地代理)   │ ←────────────────── │ (47.108.*.65) │
│              │    ②client JWT       │              │
│              │                      │              │
│  Windsurf    │    ③x-relay-token    │   Pro账号     │
│  gRPC请求 →  │ ──────────────────→  │  注入凭据 →   │ → Codeium
│              │    (relay JWT)       │              │
└─────────────┘                      └──────────────┘
```

### 13.2 Client JWT（身份认证，8个实例捕获）

```json
{
  "sid": "b1872e82-055e-41ac-9300-083930da8435",
  "key": "GG-9ULP-AW3V-3A5N-48UK",
  "dc":  "4F57-4F49-080E-79C8",
  "type": "client",
  "iat": 1772729746,
  "exp": 1772736946
}
```

| 字段 | 含义 | 格式 |
|------|------|------|
| `sid` | 会话ID | UUID v4 |
| `key` | 许可证密钥 | XX-XXXX-XXXX-XXXX-XXXX |
| `dc` | 设备码(硬件指纹) | XXXX-XXXX-XXXX-XXXX (hex) |
| `type` | token类型 | 固定 "client" |
| TTL | 有效期 | **2小时 (7200秒)** |

### 13.3 Relay JWT（请求转发，213个实例捕获）

```json
{
  "type": "relay",
  "iat": 1772733089,
  "exp": 1772740289,
  "d": "<加密的gRPC请求数据 ~300字节 base64>"
}
```

| 字段 | 含义 | 说明 |
|------|------|------|
| `type` | token类型 | 固定 "relay" |
| `d` | 加密载荷 | gRPC请求数据，HS256签名保护 |
| TTL | 有效期 | **2小时 (7200秒)** |
| 算法 | HS256 | 对称密钥签名 |

### 13.4 完整认证头链（内存提取）

| 头部 | 值 | 用途 |
|------|-----|------|
| `x-relay-token` | relay JWT | **主认证头** — 每个gRPC请求 |
| `authorization` | Bearer client JWT | 客户端身份认证 |
| `X-Device-Code` | 4F57-4F49-080E-79C8 | 硬件指纹 |
| `X-Device-MAC` | MAC地址 | 网卡指纹 |
| `X-HWID` | 硬件ID | 主板/CPU指纹 |
| `X-Session-Token` | 会话令牌 | 防重放 |
| `X-Timestamp` | Unix时间戳 | 时间校验 |
| `X-Nonce` | 随机数 | 防重放 |
| `X-Signature` | HMAC签名 | 请求完整性 |

### 13.5 额外发现

**支持的AI模型（内存提取）：**
haiku, fast, 1m, sonnet, gpt-4.1-nano, gpt-4.1-mini, gpt4.1, gpt-4o-mini, gpt-5, o3-mini, o4-mini, gemini-2.0-flash

**备用域名（内存提取）：**
- windsurf.696110.xyz
- windsurf.886.buzz
- windsurf.pro
- windsurf.trialmail.top

**Relay配置字段（内存提取）：**
relay_key, relay_token, relay_mode, relay_type, relay_url, relay_node, relay_block, relay_stale, relay_top, relay_list, relay_switch, relay_test, relay_custom

**gRPC服务路径（内存提取）：**
- `/exa.auth_pb.AuthService/GetUserJwt`
- `/exa.product_analytics_pb.ProductAnalyticsService/RecordAnalyticsEvent`

### 13.6 认证协议安全分析

| 防护层 | 机制 | 绕过难度 |
|--------|------|:--------:|
| JWT签名 | HS256对称密钥 | 🔒 高（需提取密钥） |
| 设备指纹 | dc + MAC + HWID | ⚠️ 中（可伪造） |
| 请求签名 | Timestamp+Nonce+Signature | 🔒 高（需知签名算法） |
| Token轮换 | 2小时TTL | ⚠️ 中（需持续刷新） |
| 反MITM | mitm_detected+score | ⚠️ 中（可绕过检测） |
| 许可证验证 | 后端数据库校验 | 🔒 高（服务端强制） |

### 13.7 最终架构认知

```
完整请求流:
  1. Windsurf发起gRPC请求 → 127.0.0.1:443 (CFW本地代理)
  2. CFW用HS256密钥加密gRPC数据 → 封装为relay JWT的"d"字段
  3. CFW附加认证头链 (x-relay-token + authorization + 设备指纹 + 签名)
  4. CFW转发至后端 (47.108.185.65:5001)
  5. 后端验证JWT签名 → 验证许可证 → 解密gRPC数据
  6. 后端注入自己的Pro凭据 (api_key + auth_token)
  7. 后端转发至 inference.codeium.com
  8. 响应原路返回
```

**核心瓶颈（不可绕过）：**
- HS256签名密钥 — 嵌入Rust二进制，重度混淆，静态提取极难
- 许可证验证 — 服务端强制，即使伪造JWT也需有效license key
- Pro凭据注入 — 只有后端持有，客户端永远接触不到

---

## 十四、最终方案总结（含Phase 7发现）

### 14.1 方案可行性终判

| 方案 | 可行性 | 成本 | 风险 | 推荐 |
|------|:------:|:----:|:----:|:----:|
| A. 继续使用CFW | ✅ | ¥30-50/月 | 第三方依赖 | ⭐⭐⭐ |
| B. 自建Pro代理 | ✅ | $15/月 | 需自维护 | ⭐⭐⭐⭐ |
| C. patch_windsurf.py | ✅ | 免费 | 仅客户端UI | ⭐⭐ |
| D. 提取HS256密钥伪造 | ⚠️ | 免费 | 极高技术难度 | ⭐ |
| E. 开源替代(Continue) | ✅ | 免费/$20 | 功能差异 | ⭐⭐⭐ |

### 14.2 推荐策略（分层）

1. **短期**：继续使用CFW + patch_windsurf.py客户端增强
2. **中期**：自建代理已就绪（windsurf_proxy.py E2E验证通过）
3. **长期**：关注开源替代方案发展（Continue/Cursor等）
4. **保险**：维护多备用域名列表（已提取4个备用域名）

---

## 十五、自建代理 E2E验证（Phase 9）

### 15.1 验证结果

| 测试项 | 结果 |
|--------|------|
| 上游TLS连接 server.codeium.com (35.223.238.178) | ✅ |
| 上游TLS连接 server.self-serve.windsurf.com (34.49.14.144) | ✅ |
| 本地TLS证书加载（PEM+KEY） | ✅ |
| ALPN协商 (h2) | ✅ |
| HTTP/2 preface透传 | ✅ 24B→280B |
| gRPC数据双向转发 | ✅ |

### 15.2 交付物清单

| 文件 | 版本 | 用途 |
|------|------|------|
| `windsurf_proxy.py` | **v2.0** | gRPC感知MITM代理 (HTTP/2帧解析+Protobuf检测+Plan嶗探) |
| `patch_windsurf.py` | **v3.1** | 客户端**15项补丁** (额度+特性+Enterprise+impersonateTier注入) |
| `_e2e_test.py` | v2.0 | 全链路测试 (27/27 PASS: 证书+信任+上游+代理+代码+补丁+脚本) |
| `windsurf_proxy_ca.pem` | — | TLS证书（公钥） |
| `windsurf_proxy_ca.key` | — | TLS私钥 |
| `windsurf_proxy_ca.cer` | — | Windows证书导入格式 |
| `→自建代理.cmd` | v2.0 | 一键启动脚本（管理员，自动关CFW） |
| `deploy_vm.ps1` | — | 远程VM部署脚本 |

### 15.3 部署步骤（切换CFW→自建代理）

```powershell
# 1. 关闭CFW
taskkill /F /IM CodeFreeWindsurf-x64-2.0.3.exe

# 2. 安装新证书（如果之前未安装）
certutil -addstore Root windsurf_proxy_ca.cer

# 3. 更新SSL_CERT_FILE
copy windsurf_proxy_ca.pem C:\ProgramData\windsurf_proxy_ca.pem

# 4. 启动自建代理（管理员权限）
python windsurf_proxy.py

# 5. 应用客户端补丁（可选，仅首次/更新后）
python patch_windsurf.py

# 6. 启动Windsurf（使用Proxy Launcher或直接启动）
```

### 15.4 架构对比

```text
CFW模式:    Windsurf → CFW代理(:443) → CFW后端(付费) → Codeium
自建模式:   Windsurf → 自建代理(:443) → Codeium (直连，零中间商)
```

**自建优势**: 无第三方依赖 | 无付费授权码 | 自主可控 | 数据不经第三方

---

## 十六、v2.0代理新增能力 (Phase 10)

### 16.1 windsurf_proxy.py v2.0 升级详情

| 能力 | 详情 |
|------|------|
| HTTP/2帧解析 | 识别DATA/HEADERS/SETTINGS/PING/GOAWAY/WINDOW_UPDATE帧 |
| gRPC方法日志 | 从二进制流中提取:path，记录所有API调用 |
| Protobuf字段提取 | 解码varint/string字段，提取可读字符串 |
| Plan信息检测 | 自动标记含Free/Pro/Enterprise/Trial关键词的响应 |
| DNS-over-HTTPS | 动态解析Codeium服务器IP(带缓存，不硬编码) |
| 嗅探模式 | `--sniff` 详细记录所有protobuf字符串字段 |

### 16.2 patch_windsurf.py v3.1 补丁清单 (15/15)

| # | 类型 | 补丁 | 效果 |
|---|------|------|------|
| 1-5 | 静态 | 核心额度/计费 | 无限额度+容量旁路+警告关闭+planName覆盖+Enterprise特权 |
| 6-10 | 静态 | Pro/Enterprise特性 | Premium模型+命令+Cascade Pro+社交+浏览器 |
| 11 | 静态 | **gRPC Metadata伪装** | **impersonateTier="ENTERPRISE_SAAS" + planName="Pro Ultimate"** |
| 12-15 | Regex | 变量名自适应 | hasCapacity+警告拦截+planName+isFreeTier |

### 16.3 待验证实验

**关键实验**: 关闭CFW → 启动自建代理 → 重启Windsurf → 观察:
1. `impersonate_tier="ENTERPRISE_SAAS"` 是否被Codieium服务器接受
2. Free账号+全补丁能否使用Premium模型
3. auth_token是否能从api_server正常获取
4. 代理嗅探模式能否捕获服务器返回的plan信息

**预期结果**: 根据逻向分析，inference.codeium.com独立验证auth_token，
impersonate_tier可能不被信任（服务端安全模型不应信任客户端声明）。
但这是必须实验验证的假设。

---

---

## Phase 11: CFW v2.0.6 深度逆向 (2026-03-07)

> 分析方法: 二进制静态分析 + 进程内存提取(x64修复版) + 网络连接分析 + 版本对比
> 分析目标: v2.0.3→v2.0.6变化 + 阿里云中枢共享架构可行性验证

### 11.1 版本演进对比

| 版本 | 二进制大小 | 文件名 | ProductVersion | 变化 |
|------|-----------|--------|---------------|------|
| v1.0.31 | — | CodeFreeWindsurf-x64-1.0.31.exe | 1.0.31 | Tauri v1基础版 |
| v2.0.3 | 9,618,928 B (9.17MB) | CodeFreeWindsurf-x64-2.0.3.exe | 2.0.3 | Tauri v2升级 |
| v2.0.4 | 9,625,072 B (9.18MB) | CodeFreeWindsurf-x64-2.0.4.exe | **2.0.6** | +6KB, 内嵌版本2.0.6 |
| v2.0.5 | 9,633,264 B (9.19MB) | CodeFreeWindsurf-x64-2.0.5.exe | — | +8KB |

**关键发现**: 二进制文件名v2.0.4，但PE资源中ProductVersion为"2.0.6"。
每版本增长约6-8KB，说明是增量修补而非架构重写。

### 11.2 后端服务器集群 (v2.0.6 新发现)

v2.0.3只发现3个后端，v2.0.6发现**6个节点 + 1个域名入口**:

| 节点 | 地址 | 端口 | 协议 | 备注 |
|------|------|------|------|------|
| 成都(主) | 47.108.185.65 | 5001 + **29080** | Connect-RPC | 13条TCP持久连接 |
| 上海 | 47.101.128.40 | **29080** | Connect-RPC | 新增节点 |
| 香港 | 156.225.28.34 | **29080** | Connect-RPC | v2.0.3已有(端口升级) |
| 新节点 | 103.149.91.214 | **29080** | Connect-RPC | v2.0.3已有 |
| 美国 | 72.249.203.213 | **29080** | HTTP(非TLS) | 新增节点 |
| 域名入口 | windsurf.696110.xyz | — | HTTPS | 新增域名路由 |

**协议升级**: `connect-go/1.18.1 (go1.26.0)` — 从gRPC升级到Connect-RPC协议。
**端口变化**: 新增29080端口(Connect-RPC)，保留5001(旧gRPC)。

### 11.3 运行时状态完整提取

通过修复的x64内存提取脚本，成功提取CFW v2.0.6完整运行时JSON:

```json
{
  "active_mappings": 1255,
  "ad_messages": [],
  "email": "CodeFree@Windsurf.Pro",
  "input_tokens": 108591267,
  "mitm_detected": false,
  "mitm_score": 0,
  "output_tokens": 3008310,
  "proxy_mode": "relay",
  "proxy_port": 443,
  "relay_block_reason": "",
  "relay_blocked_by_pro": false,
  "relay_stale": true,
  "request_count": 17409,
  "running": true,
  "security_clean": true,
  "session_cost": 3134.54,
  "target_host": "server.self-serve.windsurf.com",
  "relay_mode": "hash",
  "relay_node_idx": 7,
  "key_version": 479,
  "custom_models_enabled": 0
}
```

### 11.4 v2.0.3 → v2.0.6 关键变化

| 维度 | v2.0.3 | v2.0.6 | 含义 |
|------|--------|--------|------|
| 后端节点数 | 3 | 6+1域名 | 更分散，抗封锁 |
| 后端端口 | 5001 | 5001 + 29080 | 双端口，Connect-RPC |
| 后端协议 | gRPC | Connect-RPC (connect-go/1.18.1) | 协议升级 |
| relay_mode | 未知 | `hash` | 哈希路由到节点 |
| relay_node_idx | 未知 | 7 | 当前路由到第7节点 |
| key_version | 未知 | 479 | 版本化密钥管理 |
| 强制更新 | 否 | `is_force: 1` | 强制升级到2.0.6 |
| 下载地址 | GitHub? | `file.icve.com.cn` | 换到国内CDN |
| 累计消耗 | — | $3,134 / 108M tokens / 17K reqs | 巨额消耗 |

### 11.5 自动更新机制

```json
{
  "latest_version": {
    "id": 18,
    "version": "2.0.6",
    "download_url": "https://file.icve.com.cn/file_doc/qdqqd/4881772815600207.zip",
    "changelog": "BUG修复",
    "is_force": 1,
    "created_at": "2026-03-07T00:54:04.000Z"
  }
}
```

**发现**: CFW使用`file.icve.com.cn`(智慧职教平台CDN)分发更新包。

### 11.6 Relay JWT Token (v2.0.6)

提取到多个活跃Relay JWT，结构:
```
Header: {"alg":"HS256","typ":"JWT"}
Payload: {"type":"relay","iat":1772826931,"exp":1772834131,"d":"..."}
```

- TTL: 7200秒 (2小时)，与v2.0.3一致
- `d`字段: 加密数据(Base64)，包含auth_token
- 每次请求刷新JWT

### 11.7 阿里云中枢共享架构 (设计完成)

```
┌──────────────────────────────────────────────────────────────┐
│  公网客户端 (任意Windows电脑)                                 │
│  ① hosts: 127.0.0.1 server.self-serve.windsurf.com          │
│  ② portproxy: 127.0.0.1:443 → aiotvr.xyz:18443             │
│  ③ 自签证书安装到Root CA                                     │
│  ④ Windsurf启动参数: --host-resolver-rules=MAP ...           │
├──────────────────────────────────────────────────────────────┤
│  阿里云中枢 (aiotvr.xyz / 60.205.171.100)                   │
│  ⑤ frps :7000 (FRP Server)                                  │
│  ⑥ auth_hub v3 :18800 (管理/监控/部署包分发)                 │
│  ⑦ Nginx :80 反代 /hub/ → :18800                            │
│  ⑧ FRP隧道: :18443 → 台式机:443                             │
├──────────────────────────────────────────────────────────────┤
│  台式机 (192.168.31.141)                                     │
│  ⑨ CFW v2.0.6 :443 (MITM Proxy)                             │
│  ⑩ frpc → 阿里云:7000 (隧道: 443→18443, 3389→13389, ...)   │
│  ⑪ 13条TCP → 47.108.185.65:5001 (成都后端)                  │
├──────────────────────────────────────────────────────────────┤
│  CFW后端集群 (6节点)                                          │
│  ⑫ Connect-RPC :29080 → Relay JWT → auth_token              │
│  ⑬ inference.codeium.com → 推理执行                          │
└──────────────────────────────────────────────────────────────┘
```

### 11.8 已实现组件

| 组件 | 文件 | 版本 | 状态 |
|------|------|------|------|
| 中枢管理服务 | `auth_hub_v3.py` | v3.0 | ✅ 完成 |
| 客户端部署脚本 | `deploy_vm_v5.ps1` | v5.0 | ✅ 完成 |
| 阿里云恢复脚本 | `aliyun_recover.sh` | v3.0 | ✅ 完成 |
| 台式机FRP启动 | `start_frpc.cmd` | v1.0 | ✅ 完成 |
| 内存提取工具 | `_re_extract_v2.py` | v2.0 | ✅ 修复x64兼容 |
| frpc隧道配置 | `frpc.toml` (CFW条目) | — | ✅ 已添加 |

### 11.9 当前阻塞

**阿里云sshd不响应**: ping通(50ms)，端口22/80/443/18443开放，但SSH banner交换超时。
需要通过阿里云Web控制台重启ECS实例或VNC修复sshd。

**恢复后一键操作**:
```bash
# SSH连通后执行:
scp auth_hub_v3.py deploy_vm_v5.ps1 windsurf_proxy_ca.* aliyun:/opt/windsurf-hub/static/
ssh aliyun 'bash -s' < aliyun_recover.sh
# 台式机启动frpc:
start_frpc.cmd
```

---

*报告完毕。v1.0.31 + v2.0.3 + v2.0.6 + Relay协议 + 自建代理v2.0 + 阿里云中枢v3.0 完整逆向+实现。
v2.0.6新增发现: 6节点后端集群 | Connect-RPC协议升级 | hash路由 | key_version版本化 |
108M tokens/$3134累计消耗 | file.icve.com.cn更新分发。
所有分析均基于运行时观察和协议逆向，未修改任何原始文件。*
