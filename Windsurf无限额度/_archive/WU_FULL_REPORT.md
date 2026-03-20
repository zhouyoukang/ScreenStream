# WindsurfUnlimited v1.5.6 完全逆向+修复报告

> 生成时间: 2026-03-12 18:30
> E2E: **10/10 PASS (100%)**
> 补丁: **5/5 APPLIED**

## 一、发现并修复的5层问题链

| # | 问题 | 严重 | 根因 | 修复 | 状态 |
|---|------|------|------|------|------|
| P1 | hosts缺失MITM条目 | 🔴 | WU停止代理时清除了hosts但重启后未恢复 | 写入`127.65.43.21`→2域名+DNS刷新 | ✅ |
| P2 | CA证书未安装 | 🔴 | Root store中无Windsurf MITM CA | `certutil -addstore Root ca.crt` | ✅ |
| P3 | WU代理443停止监听 | 🔴 | WU主进程在但HTTP/2服务器已退出 | kill+relaunch WU | ✅ |
| P4 | 429不在重试列表 | 🔴 | `Pn=new Set([502,503,504...])` 缺429 | 注入429到Set | ✅ |
| P5 | 线性退避+3次重试 | 🟡 | `ft=3` + `1e3*(u+1)` | ft=6+指数退避+抖动 | ✅ |

## 二、WU v1.5.6 完整架构

### 2.1 五层MITM架构
```
Layer 1: hosts劫持
  127.65.43.21 server.self-serve.windsurf.com
  127.65.43.21 server.codeium.com

Layer 2: CA证书 (CN=Windsurf MITM CA, O=Local Proxy)
  cert:\LocalMachine\Root

Layer 3: HTTP/2 TLS MITM (node http2.createSecureServer)
  127.65.43.21:443

Layer 4: Windsurf settings.json
  http.proxyStrictSSL=false, http.proxySupport=off

Layer 5: user_settings.pb
  detect_proxy=1 (protobuf field 34)
```

### 2.2 数据流
```
Windsurf gRPC → DNS(hosts)→127.65.43.21 → TLS(MITM CA)
  → WU MITM Proxy
    ├─ Telemetry(8类) → 直接200(省积分)
    ├─ GetChatMessage/GetCompletions → AES-GCM加密 → chaogei.top/stream-proxy
    └─ 其他gRPC → chaogei.top/proxy
  → 后端持有Pro账号 → Codeium API → 流式响应解密 → Windsurf
```

### 2.3 加密协议
| 组件 | 算法 | 密钥来源 |
|------|------|---------|
| 请求加密 | AES-256-GCM (12B IV + 16B AuthTag) | client_secret SHA256 |
| 请求签名 | HMAC-SHA256 | client_secret |
| 协议版本 | "2" | 硬编码 |

### 2.4 重试机制 (补丁后)
| 参数 | 补丁前 | 补丁后 |
|------|--------|--------|
| 可重试状态码 | 502,503,504,520-524 | **+429** |
| 最大重试次数 | 3 | **6** |
| 退避策略 | 线性 1s×n | **指数 2^n + 随机0-2s, max 30s** |
| 流式超时 | 180s | **300s** |
| 普通超时 | 10s | **30s** |

### 2.5 Telemetry过滤(8类)
RecordAnalytics / CortexTrajectory / CortexTrajectoryStep / AsyncTelemetry / StateInitialization / CortexExecutionMeta / CortexGeneratorMeta / TrajectorySegment

### 2.6 限速根因分析
1. **hosts缺失** → gRPC直连官方 → 使用Trial凭据 → 严格限速
2. **429不重试** → 一次限速即失败 → 用户感知"请求失败"
3. **线性退避太短** → 429冷却期内重试 → 连续失败
4. **后端账号池轮换** → chaogei.top持有多个Pro账号 → 偶尔某账号被限速
5. **积分耗尽** → 天卡5000积分/天 → 高消耗模型快速耗尽

## 三、已创建工具

| 文件 | 功能 | 用法 |
|------|------|------|
| `wu_guardian.py` | 持久化守护(hosts/CA/进程/443/TLS/gRPC/E2E) | `--fix` `--daemon` `--e2e` |
| `→WU一键修复.cmd` | 一键修复所有问题(管理员) | 双击运行 |
| `wu_patch_asar.py` | main.js 5项补丁(429/重试/退避/超时) | `--check` 或直接运行 |
| `wu_deep_reverse.py` | 8维全景诊断+报告 | `--fix` `--report` |
| `wu_optimizer.py` | 全维度优化器 | `--fix` `--monitor` |

## 四、持久化保护

| 机制 | 详情 |
|------|------|
| schtask `WU_Guardian` | ONLOGON/HIGHEST, daemon模式120s巡检 |
| hosts守护 | 自动检测+恢复MITM条目 |
| CA证书守护 | 自动检测+安装 |
| WU进程守护 | crash检测+自动重启 |
| 443端口守护 | MITM监听检测+WU重启 |

## 五、E2E验证 (10/10)

| 测试 | 结果 |
|------|------|
| T1-hosts | ✅ 2域名OK |
| T2-DNS | ✅ 全部→127.65.43.21 |
| T3-WU进程 | ✅ 4个进程 |
| T4-TCP:443 | ✅ LISTENING |
| T5-TLS握手 | ✅ TLSv1.3 13ms |
| T6-CA证书 | ✅ MITM CA已安装 |
| T7-WU会话 | ✅ 天卡 21.2h |
| T8-WS配置 | ✅ proxyStrictSSL=false |
| T9-gRPC流量 | ✅ 10条ESTABLISHED |
| T10-Windsurf | ✅ 13个进程 |

## 六、使用指南

### 日常使用
WU运行中 → Windsurf正常使用 → 无需额外操作

### 出现问题时
```
双击 →WU一键修复.cmd       # 一键修复所有问题
python wu_guardian.py --e2e  # 10项E2E诊断
python wu_guardian.py --fix  # 全景诊断+修复
```

### WU更新后
```
python wu_patch_asar.py      # 重新应用5项补丁
python wu_guardian.py --fix  # 验证修复
```

### 天卡到期
在WU界面续费或切换卡密

### 积分优化
- Windsurf模型切换到 **SWE-1.6** (creditMultiplier=0, 免费无限)
- 避免 Claude Opus 4.5 thinking (3-5x积分消耗)
- 开启 AutoContinue + 0x模型 = 零成本
