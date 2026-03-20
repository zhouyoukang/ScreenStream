# Windsurf 速率限制突破策略 v1.0

> 基于 workbench.desktop.main.js v1.108.2 + WU v1.5.6 app.asar 完整逆向
> 2026-03-12

## 核心发现

### 1. 限速100%在服务端

客户端代码 `if(!1)` = `if(false)` — 限速检查结果**永不阻断**客户端。
真正限速发生在 `inference.codeium.com` 基于 `auth_token` 做服务端限制。

### 2. WU不重试429

WU可重试码: `502,503,504,520,521,522,523,524`
**429(Too Many Requests)不在列表** → 限速直接透传给用户。

### 3. 冷却由服务端控制

`resets_in_seconds` 字段由服务端下发，客户端无法修改。
唯一绕过：**切换auth_token(换账号)**。

## 突破方案矩阵 (按ROI排序)

### 方案A: 账号池轮换 ⭐⭐⭐⭐⭐ (核心方案)

**原理**: 每个Windsurf账号有独立速率限制池。账号A限速→切到账号B。

**工具**: `switch_account.py` + `windsurf_account_pool.py`

**操作流程**:
```
1. 当前账号限速 → 运行: python switch_account.py --mark-cool 当前邮箱
2. 自动切换 → 运行: python switch_account.py
3. 脚本自动: 关闭Windsurf → 重置指纹 → 清缓存 → 提示新号登录
4. 启动Windsurf → 登录新账号 → 继续使用
```

**关键**: 每次切换必须重置设备指纹(防跨账号关联)

**效果**: 11个账号轮换，假设每个账号2h冷却，7个可用 = 永不断档

### 方案B: 模型降级 ⭐⭐⭐⭐ (立即生效)

**原理**: 不同模型有独立限速池+不同creditMultiplier。

| 模型 | 乘数 | 限速 | 建议 |
|------|------|------|------|
| SWE-1.6 | 0 | 最宽松 | 日常首选 |
| SWE-1.5 | 0 | 宽松 | 备选 |
| Claude Sonnet 4 | 1 | 中等 | 需要高质量时 |
| Claude Opus 4.x | 3-5 | 严格 | 仅关键任务 |

**操作**: Windsurf左下角模型选择器 → 切换到SWE-1.6

### 方案C: 自建MITM代理 ⭐⭐⭐ (脱离WU依赖)

**原理**: 复制WU的MITM架构但增强:
- 自管理账号池(不依赖chaogei.top)
- 429自动重试+退避
- 多账号auth_token轮换(同一代理内)

**现有资产**: `windsurf_proxy.py` v2.0 已具备基础MITM能力

**增强点**:
1. 从WU逆向的加密协议中提取auth_token获取逻辑
2. 实现多账号token池
3. 增加429→等待→重试逻辑
4. 实现服务端限速检测→自动切换token

### 方案D: patch增强 ⭐⭐⭐ (客户端优化)

**原理**: 已有15项补丁，可增强:
1. hasCapacity永远true ✅ (已有)
2. 限速消息拦截→不显示给用户
3. 自动重试被限速的请求
4. maxGeneratorInvocations提升(减少Continue)

**工具**: `patch_windsurf.py` v3.1

### 方案E: BYOK ⭐⭐⭐⭐ (终极方案)

**原理**: 自带API Key完全绕过Windsurf积分+限速系统。

| Provider | 模型 | 成本 |
|----------|------|------|
| Anthropic | Claude 4 Sonnet BYOK | ~$3/MTok |
| OpenRouter | Claude 4 Sonnet BYOK | 市场价 |

**前提**: 需要Anthropic/OpenRouter API Key

## 立即执行清单

### 第一优先(5分钟内)
1. **模型切到SWE-1.6**: 0积分消耗+最宽松限速
2. **确认当前账号状态**: `python windsurf_account_pool.py`

### 第二优先(遇到限速时)
3. **标记当前号冷却**: `python switch_account.py --mark-cool 当前邮箱`
4. **一键切换**: `python switch_account.py`
5. **登录新号**: 按提示的邮箱/密码登录

### 第三优先(长期)
6. **测试未测试账号**: 逐个登录7个未测试账号，记录其计划类型
7. **累积冷却数据**: 记录每个号的冷却时间，优化轮换策略
8. **考虑BYOK**: 如有Anthropic Key，配置BYOK彻底绕过

## 冷却时间估算

基于行为观察(非精确数据，需实测校准):

| 账号类型 | 估算冷却 | 触发条件 |
|----------|---------|---------|
| Trial(高频) | 1-4h | ~20-50消息/h |
| Trial(低频) | 30m-1h | ~10-20消息/h |
| Pro(高频) | 30m-2h | ~50-100消息/h |
| Pro(低频) | 10-30m | ~20-50消息/h |

**需实测**: 每次限速时记录时间+账号+模型，积累精确冷却数据。

## 问题-方案映射

| 问题 | 根因 | 方案 |
|------|------|------|
| 限速无法请求 | auth_token被服务端限制 | 账号池轮换(A) |
| 积分快速耗尽 | 高乘数模型+大prompt | 模型降级(B) |
| WU不重试429 | 429不在重试列表 | 自建代理(C) |
| 切号后仍限速 | 设备指纹关联 | 指纹重置(A内含) |
| WU积分耗尽 | 天卡5000有限 | 切SWE-1.6(0消耗) |
| 所有号都冷却 | 账号池不够 | 增加账号+BYOK(E) |

## 文件清单

| 文件 | 用途 |
|------|------|
| `windsurf_account_pool.py` | 账号池管理(11号+状态+冷却) |
| `switch_account.py` | 一键切换(关WS+重置指纹+清缓存) |
| `wu_deep_reverse.py` | WU诊断器(8维+修复+报告) |
| `patch_windsurf.py` | JS客户端补丁(15项) |
| `telemetry_reset.py` | 设备指纹重置 |
| `_account_pool.json` | 账号池状态持久化 |
| `WINDSURF_RATE_LIMIT_ARCHITECTURE.md` | 完整逆向架构 |
| `BREAKTHROUGH_STRATEGY.md` | 本文档 |
