# Windsurf 官方速率限制完整逆向架构

> 逆向源: workbench.desktop.main.js v1.108.2 (32.7MB)
> 日期: 2026-03-12

## 一、双重限速架构

每次发送消息前**串行执行**两层检查：

```
Layer 1: CheckChatCapacity → 模型级容量(高负载时触发)
Layer 2: CheckUserMessageRateLimit → 用户级速率(始终检查)
```

### 1.1 CheckChatCapacityResponse (protobuf)
| 字段 | 类型 | 说明 |
|------|------|------|
| has_capacity | bool | 模型是否有容量 |
| message | string | 错误消息 |
| active_sessions | int32 | 当前活跃会话数 |

触发条件: `model.isCapacityLimited === true`
错误: "We're currently facing high demand for this model."

### 1.2 CheckUserMessageRateLimitResponse (protobuf)
| 字段 | 类型 | 说明 |
|------|------|------|
| has_capacity | bool | 是否还有配额 |
| message | string | 错误消息 |
| messages_remaining | int32 | 剩余消息数 |
| max_messages | int32 | 最大消息数限制 |
| resets_in_seconds | int64 | **冷却倒计时(秒)** |

始终检查，维度: **用户×模型**
错误: "You have reached your message limit for this model."

## 二、冷却机制

### 2.1 冷却触发
1. `messages_remaining <= 0` — 消息配额用尽
2. `active_sessions >= max` — 并发过多
3. `hourly_requests >= limit` — 每小时频率超限
4. 服务端负载 → `isCapacityLimited=true` — 全局降级

### 2.2 冷却恢复
- 等待 `resets_in_seconds` 秒(服务端精确下发)
- 切换未限速模型
- **切换未限速账号** ← 核心绕过

### 2.3 Trial vs Pro 差异
| 维度 | Trial | Pro |
|------|-------|-----|
| 消息速率 | **严格**(低maxMessages) | 宽松 |
| 冷却时间 | **长**(大resetsInSeconds) | 短 |
| 容量优先 | 低优先 | 高优先 |
| 并发会话 | 限制 | 更多 |
| hourly限制 | 严格 | 宽松 |

## 三、设备指纹(5维)

存储: `%APPDATA%\Windsurf\User\globalStorage\storage.json`

| 指纹 | 来源 | 风险 |
|------|------|------|
| telemetry.machineId | 注册表MachineGuid SHA256 | 硬件绑定 |
| telemetry.macMachineId | MAC+hostname SHA256 | 网络绑定 |
| telemetry.devDeviceId | 随机UUID | 可重置 |
| telemetry.sqmId | 随机UUID | 可重置 |
| storage.serviceMachineId | 随机UUID,持久化 | 可重置 |

### 3.1 关联检测风险
| 行为 | 风险 |
|------|------|
| 同设备切换账号不重置指纹 | 🔴高 |
| 同IP多账号 | 🟡中 |
| WU Pro token后切回Trial | 🔴高(设备被关联) |

## 四、creditMultiplier体系

| 模型 | 乘数 | 说明 |
|------|------|------|
| SWE-1/1.5/1.6 | **0** | 免费无限 |
| LITE_FREE | **0** | 免费 |
| Claude Sonnet 4 | 1 | 标准 |
| Claude Sonnet 4.5 | **3** | 高消耗 |
| Claude Opus 4.x | 3-5 | 极高 |

## 五、auth_token生命周期

```
1. 用户登录 → Firebase ID Token
2. Language Server: GetAuthToken(api_key, user_jwt) → auth_token
3. auth_token TTL ≈ 2小时
4. 过期后自动刷新
5. inference.codeium.com用auth_token验证每个请求
6. 服务端通过auth_token追踪: 用户身份+计划类型+usage
```

## 六、WU v1.5.6 MITM架构(对比)

| 维度 | WU做法 | 效果 |
|------|--------|------|
| hosts | 127.65.43.21 → 两个域名 | 拦截auth请求 |
| MITM代理 | HTTP/2 TLS on 127.65.43.21:443 | 替换auth_token |
| 后端 | chaogei.top(Pro账号池) | 返回Pro token |
| 加密 | AES-256-GCM+HMAC | 防篡改 |
| Telemetry过滤 | 8类请求直接200 | 节省配额 |
| detect_proxy | 自动修改protobuf field34 | 确保代理生效 |

### 6.1 WU限速根因
WU后端使用**共享Pro账号池**，多个用户共享同一批Pro账号：
- 每个Pro账号有**独立速率限制**(maxMessages/小时)
- 多用户并发→单账号快速触发限速→冷却
- 冷却期间该账号不可用→需切换下一个
- 账号池耗尽→全部冷却→所有用户受影响

## 七、绕过方案

### 7.1 账号池轮换(核心方案)
维护10+个独立账号，自动检测限速→切换→冷却追踪→恢复使用

### 7.2 指纹隔离(防关联)
每次切换账号前重置5个UUID，避免设备关联导致连坐

### 7.3 模型降级(减少触发)
优先使用SWE-1.6(0乘数)，减少触发用户级限速

### 7.4 请求优化(减少频率)
精简规则/Memory/MCP降低每次token量，减少请求频率
