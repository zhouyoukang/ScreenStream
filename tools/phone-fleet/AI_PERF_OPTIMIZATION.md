# AI操控手机 — 反应时间与长链稳定性优化

> **一句话**：从全球开源项目+工程实践中提炼6项延迟优化+4项稳定性优化，
> 全部实现到phone_lib.py中，零外部依赖，向后兼容。
>
> 生成时间：2026-02-26 | 数据源：GitHub搜索 + StackOverflow + 学术论文 + 自有代码分析

---

## 一、延迟瓶颈诊断（优化前）

| # | 瓶颈 | 根因 | 影响 | 优化后 |
|---|------|------|------|--------|
| 1 | **每次HTTP新建TCP连接** | `urllib.request.urlopen`硬编码`Connection:close` | +3ms(USB) / +50ms(WiFi) / +100ms(Tailscale) 每次 | ✅ keep-alive连接池 |
| 2 | **senses()串行4次HTTP** | 顺序调用screen/text→deviceinfo→status→notifications | 4×50ms=200ms | ✅ 并行GET(~50ms) |
| 3 | **固定sleep过长** | home()等0.8s, open_app()等2s, 都是worst-case估计 | 累计浪费数秒 | ✅ wait_for()自适应等待 |
| 4 | **默认timeout=15s** | 所有请求统一15s超时 | 手机断联时等待过久 | ✅ GET=5s, POST=10s |
| 5 | **线性retry延迟** | `delay = retry_delay * (attempt+1)` | 重试间隔不合理 | ✅ 指数退避+jitter |
| 6 | **discover()串行扫描** | 20端口×5层=最多100次探测 | 最差30s | ⚠️ 未改(首次连接,非热路径) |

## 二、稳定性问题诊断（优化前）

| # | 问题 | 根因 | 影响 | 优化后 |
|---|------|------|------|--------|
| 1 | **无熔断器** | 手机断联时每次操作都等timeout+retry | 浪费45s(3×15s) | ✅ CircuitBreaker |
| 2 | **无操作日志** | 长链失败后无法定位哪步出错 | 调试困难 | ✅ op_log |
| 3 | **无链式执行** | 多步操作无失败策略 | 中间步失败整条崩溃 | ✅ chain() |
| 4 | **无性能诊断** | 无法知道连接池/熔断器/延迟状态 | 盲目优化 | ✅ perf_stats() |

---

## 三、已实现的优化（6项）

### 3.1 HTTP连接池 keep-alive（_HttpPool）

**原理**：`urllib.request`每次请求都发送`Connection: close`，强制关闭TCP连接。
下次请求需重新3次握手(SYN→SYN-ACK→ACK)。`http.client.HTTPConnection`默认keep-alive，
复用已建立的TCP连接，省去握手开销。

**预期加速**：
| 连接方式 | 每次省 | 20次连续操作省 |
|----------|--------|--------------|
| USB localhost | ~3ms | ~60ms |
| WiFi直连 | ~5-20ms | ~100-400ms |
| Tailscale | ~50-100ms | ~1-2s |

**实现**：`_HttpPool`类，线程安全，自动重连，统计复用率。

### 3.2 并行五感采集（senses parallel=True）

**原理**：`senses()`需要4个GET请求的数据。串行执行时间=sum(4个请求)。
并行执行时间=max(4个请求)。使用`ThreadPoolExecutor`实现真并行。

**预期加速**：~4x（200ms → 50ms）

**实现**：`_batch_get()`用`ThreadPoolExecutor`并行GET，`senses(parallel=True)`默认启用。
`senses(parallel=False)`保持旧行为兼容。

### 3.3 自适应等待（wait_for）

**原理**：固定`time.sleep(0.8)`总是等最长时间。`wait_for()`轮询条件函数，
条件一满足就立即返回，平均等待时间大幅缩短。

**使用示例**：
```python
# 旧: 固定等800ms
p.home(); p.wait(0.8)

# 新: 一到桌面就返回(通常100-300ms)
p.post("/home")
p.wait_for(lambda: p.foreground() == "launcher", timeout=2)
```

### 3.4 智能超时（GET=5s, POST=10s）

**原理**：GET请求通常是只读查询，响应快(10-50ms)。POST可能涉及屏幕操作，
需要更长。旧代码统一15s，新代码按方法类型自动设置。

### 3.5 指数退避+jitter

**原理**：旧代码线性退避`delay = 1.0 * (attempt+1)`，间隔1s, 2s, 3s。
新代码指数退避`delay = 1.0 * 2^attempt + random(0, 0.3)`，间隔~1.3s, ~2.3s, ~4.3s。
jitter防止多客户端同时重试(thundering herd)。

### 3.6 熔断器（_CircuitBreaker）

**原理**：连续3次失败后进入`open`状态，后续请求立即返回`circuit_open`错误（0ms），
不再浪费时间等超时。cooldown 10秒后进入`half_open`，允许一次试探请求。
成功则恢复`closed`，失败则继续`open`。

**效果**：手机断联时，从"每次操作等15s"变为"第4次起立即失败(0ms)"。

---

## 四、已实现的稳定性增强（4项）

### 4.1 操作日志（op_log）

每次HTTP请求自动记录`(timestamp, "GET /status", True, 12.3ms)`。
最多保留500条，超过时保留最近250条。

**使用**：`p.perf_stats()` 返回日志摘要。

### 4.2 链式执行（chain）

多步操作的稳定执行框架：
```python
results = p.chain([
    ("回桌面", lambda: p.home()),
    ("打开微信", lambda: p.monkey_open("com.tencent.mm")),
    ("点发现", lambda: p.click("发现")),
    ("读屏幕", lambda: p.read()),
], on_fail='skip')  # skip=跳过失败继续 | stop=失败停止 | retry=重试一次

# 每步记录: (name, ok, result, elapsed_seconds)
for name, ok, result, elapsed in results:
    print(f"{'✅' if ok else '❌'} {name}: {elapsed:.3f}s")
```

### 4.3 性能诊断（perf_stats）

一键获取所有性能指标：
```python
stats = p.perf_stats()
# {
#   "pool": {"reused": 45, "created": 3, "errors": 0},
#   "breaker": "closed",
#   "op_total": 48, "op_ok": 47, "op_fail": 1,
#   "avg_ms_recent20": 12.3,
#   "recent": [("GET /status", True, 11.2), ...]
# }
```

### 4.4 连接池自动重连

`_HttpPool`在检测到连接断开时自动创建新连接（最多1次重试），
对调用者透明。统计`errors`字段记录重连次数。

---

## 五、全球技术精华来源

| 技术 | 来源 | 我们的实现 |
|------|------|-----------|
| HTTP keep-alive | StackOverflow + urllib3文档 | `_HttpPool` (http.client) |
| Circuit Breaker | Portkey.ai + Netflix Hystrix模式 | `_CircuitBreaker` |
| Exponential backoff + jitter | OpenAI latency guide + AWS best practices | `_http()` retry逻辑 |
| Parallel sensing | Google ADK ParallelAgent | `_batch_get()` + `senses(parallel=True)` |
| Adaptive wait | UiPath Healing Agent | `wait_for()` |
| Operation chain | IBM STRATUS undo-and-retry | `chain()` |
| Performance observability | Sparkco retry logic + Portkey metrics | `perf_stats()` + `_op_log` |

---

## 六、测试矩阵

| 测试 | 文件 | 内容 |
|------|------|------|
| § 1 | `tests/perf_test.py` | 连接池 vs urllib 对比基准 |
| § 2 | 同上 | 并行 vs 串行 senses 对比 |
| § 3 | 同上 | Phone._http 连接池效果 |
| § 4 | 同上 | 熔断器行为验证 |
| § 5 | 同上 | 长链执行 + 失败策略 |
| § 6 | 同上 | 自适应等待验证 |
| § 7 | 同上 | 操作日志验证 |
| § 8 | 同上 | 50次高速连续请求压测 |

运行：`python tests/perf_test.py --port 8084`

---

## 七、向后兼容保证

| 变更 | 兼容性 |
|------|--------|
| `_http()` 改用连接池 | ✅ 返回值完全相同 |
| 默认timeout 15s→5s/10s | ⚠️ 极慢网络可能需要显式设timeout |
| retry改指数退避 | ✅ 行为更合理 |
| `senses(parallel=True)` | ✅ 默认并行，`parallel=False`回退串行 |
| 新增方法 | ✅ 纯additive，不影响现有代码 |
| 熔断器 | ✅ 透明集成，3次失败后短路 |
| 操作日志 | ✅ 自动记录，无需额外调用 |

---

## 八、文档链

- `手机操控库/phone_lib.py` — 核心库（所有优化已集成）
- `手机操控库/tests/perf_test.py` — 性能基准测试（8节）
- `文档/AI_PHONE_CONTROL.md` — AI操控手机全景图
- `文档/AI_COMPUTER_CONTROL.md` — AI操作电脑全景图

---

*汇总自：7次全球搜索 + phone_lib 1009行代码分析 + 6项延迟优化 + 4项稳定性增强*
*先增再减，再增再简，取之于精华，归之于总。*
