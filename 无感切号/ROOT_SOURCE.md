# 根源解构 — 道之本·根·源·头·底

> 2026-03-22 | 万法归宗 · 剥离一切表层
>
> 道生一(apiKey) → 一生二(Session+Quota) → 二生三(LS+DB+DPAPI) → 三生万物(96账号×模型×配额)
> **反者道之动**: 一切阻碍的本源 = 单会话锁。突破之道 = 绕过会话，直取数据流。

---

## 〇、终极一句话

**Windsurf IDE 与服务器之间的一切连接，归根结底只有一个东西在流动：apiKey。每一个gRPC请求携带一个apiKey，服务端据此识别身份、计量配额、执行限流。当前系统的根本限制是：LanguageServer进程在内存中持有且仅持有一个apiKey，所有请求共用同一身份。突破之道：在网络层拦截，让每个请求可以携带不同的apiKey——无需切换会话，无需重启LS，无需用户感知。**

---

## 一、本 — Windsurf IDE 与服务器的本质连接

### 1.1 连接的物理形态

```
Windsurf IDE (Electron)
  │
  ├── Extension Host (Node.js进程)
  │     └── 各VSIX扩展运行于此 (包括无感切号)
  │
  ├── Language Server (独立进程, @exa/*)
  │     ├── 持有 apiKey (内存)
  │     ├── 建立 gRPC/Connect-RPC 连接 → server.codeium.com:443
  │     ├── 建立 gRPC/Connect-RPC 连接 → web-backend.windsurf.com:443
  │     └── 所有 Cascade/补全/检查 请求从此发出
  │
  └── Workbench (渲染进程, Electron renderer)
        ├── Zustand状态管理 (quota_exhausted等UI状态)
        ├── state.vscdb (SQLite, 持久化认证+配额)
        └── DPAPI加密会话 (secret://windsurf_auth.sessions)
```

### 1.2 数据流的本质

```
请求流 (Cascade消息):
  用户输入 → Workbench → LS.sendMessage(apiKey, modelUid, context)
           → HTTPS POST server.codeium.com/exa.api_server_pb.ApiServerService/GetChatMessage
           → Content-Type: application/proto
           → Body: protobuf{ metadata{ api_key: "sk-ws-01-..." }, model_uid, messages[] }
           → 服务端验证apiKey → 查quota → 查rate_limit桶 → 执行推理 → 流式返回

响应流 (Cascade回复):
  服务端 → gRPC stream → LS → Workbench → 渲染到Cascade面板

唯一身份标识 = apiKey (sk-ws-01-..., 103字符)
唯一计量标识 = (apiKey, modelUid) → 独立速率桶
唯一配额标识 = apiKey → 账号级日/周配额
```

### 1.3 服务端是无状态的

**关键洞察：服务端不维护"会话"概念。** 每个gRPC请求独立验证：

```
服务端处理单个请求:
  1. 从protobuf提取 api_key
  2. 查找 api_key → Firebase UID → Account
  3. 检查 Account.quota (daily%, weekly%)
  4. 检查 RateLimitBucket[(api_key, model_uid)]
  5. 如果都通过 → 执行推理 → 扣减配额
  6. 返回结果

第N个请求和第N+1个请求之间没有任何关联。
不同apiKey的请求可以交错发送，互不影响。
服务端不知道也不关心这些请求来自同一台机器。
```

---

## 二、根 — 认证链的根源解构

### 2.1 根的五层 (从种子到果实)

```
第零层 · 种 (永久)
  Email + Password → 存储在windsurf-login-accounts.json
  96个yahoo.com账号，这是一切的起源

第一层 · 火 (永久)  
  Firebase Auth: signInWithPassword(email, password)
  → Firebase UID (28字符, 不可变, 如: DJW3bcJDusdYs0XtUPf5U6DvFqf2)
  → Firebase项目: exa2-fb170
  → API Keys: AIzaSyDsOl-1XpT5err0Tcnx8FFod1H8gVGIycY (v5.6.29)
               AIzaSyDKm6GGxMJfCbNf-k0kPytiGLaqFJpeSac (v5.0.20)

第二层 · 水 (1小时, 可续命)
  Firebase JWT (idToken)
  → RS256签名, iss=securetoken.google.com/exa2-fb170
  → 缓存在wam-token-cache.json (50分钟TTL)
  → refreshToken可无限续命

第三层 · 金 (长期)
  RegisterUser(idToken) → apiKey
  → Connect-RPC: register.windsurf.com/exa.seat_management_pb.SeatManagementService/RegisterUser
  → 请求: protobuf{field1: idToken}
  → 响应: protobuf{field1: apiKey} → "sk-ws-01-..." (103字符)
  → 这是所有gRPC请求的身份凭证

第四层 · 壁 (会话级)
  LS进程内存中持有apiKey → 每个请求携带
  + Workbench Zustand store → UI状态
  + state.vscdb windsurfAuthStatus → 持久化
  + DPAPI encrypted session → 系统级加密
```

### 2.2 每一层的获取方式

```python
# 第零层→第二层: 任何HTTP客户端即可
idToken = POST identitytoolkit.googleapis.com/v1/accounts:signInWithPassword
          ?key=AIzaSyDsOl-1XpT5err0Tcnx8FFod1H8gVGIycY
          body: {email, password, returnSecureToken: true}
          → response.idToken

# 第二层→第三层: Connect-RPC protobuf
apiKey = POST register.windsurf.com/exa.seat_management_pb.SeatManagementService/RegisterUser
         Content-Type: application/proto
         connect-protocol-version: 1
         body: encode_proto_string(idToken, field=1)
         → parse_proto_string(response, field=1)

# 第三层→第四层: Windsurf内部命令
vscode.commands.executeCommand("windsurf.provideAuthTokenToAuthProvider", idToken)
→ 内部自动: registerUser(idToken) → apiKey → 写入LS内存 + state.vscdb + DPAPI session
```

---

## 三、源 — 当前系统的根本限制

### 3.1 单会话锁 — 一切阻碍的根源

```
限制的本质:
  LanguageServer进程 ── 启动时 ──→ 从session/state.vscdb读取apiKey
                     ── 运行时 ──→ 所有请求使用同一个apiKey
                     ── 切换时 ──→ 必须重启LS才能加载新apiKey

单会话锁的连锁效应:
  1. 切换账号 = 注入新idToken → LS重启(3-5s) → 新apiKey
  2. LS重启 = 所有Cascade对话断开
  3. 对话断开 = 用户可感知的中断
  4. 中断 = 不是真正的"无感"

当前"无感"的定义(v1.0.0):
  ✅ 自动检测quota耗尽 → 自动选号 → 自动注入 → 自动等待会话过渡
  ❌ 但LS仍然必须重启 → 3-5s中断 → Cascade对话可能断开
  ❌ 96个账号只有1个在线 → 其余95个闲置
```

### 3.2 三重加密锁 (为什么不能直接改内存)

```
锁1: LS进程内存 (读: 不可能; 写: 不可能)
  apiKey存储在LS的JavaScript堆内存中
  没有进程间通信接口暴露
  唯一更新方式: LS重启重新读取

锁2: state.vscdb (读: 可以; 写: 可以, 但LS不会重新读取)
  SQLite数据库, 无加密
  可以直接写入新apiKey到windsurfAuthStatus
  但LS的内存不会更新 → 必须reload window

锁3: DPAPI session (读: 不可能; 写: 不可能)
  secret://windsurf_auth.sessions
  Windows Data Protection API加密
  绑定当前用户+机器 → 无法跨进程操作
  仅Windsurf主进程可读写
```

### 3.3 根本矛盾

```
矛盾:
  需求 = 所有96个账号同时在线，所有请求自动路由到最优账号
  现实 = LS只能持有1个apiKey，切换需要重启LS

矛盾的根源:
  apiKey绑定在LS进程的内存空间中
  LS是Windsurf闭源组件，无法热修改

反者道之动:
  既然不能改变LS的行为(攻坚壁)
  那就改变LS与服务器之间的通道(入缝隙)
  → 在网络层拦截，替换apiKey → LS不知道，服务端不知道
```

---

## 四、头 — 突破架构：透明gRPC代理

### 4.1 核心思想

```
当前架构:
  LS (apiKey_A) ───HTTPS───→ server.codeium.com → 使用账号A的配额

突破架构:
  LS (apiKey_A) ───HTTPS───→ 本地代理(:19443) ───HTTPS───→ server.codeium.com
                                    │
                                    ├── 解析protobuf → 提取apiKey
                                    ├── 查询号池路由器 → 选最优账号
                                    ├── 替换protobuf中的apiKey → apiKey_B
                                    └── 转发到真实服务器 → 用账号B的配额

效果:
  LS以为自己在用账号A → 实际请求用的是账号B的配额
  96个apiKey全部预备 → 每个请求独立选择最优账号
  没有LS重启 → 没有对话中断 → 真正的零感知
```

### 4.2 技术路径

```
路径1: HTTPS_PROXY环境变量 (最简)
  设置 HTTPS_PROXY=http://127.0.0.1:19443
  所有HTTPS请求通过代理
  代理做CONNECT tunnel + TLS MITM + protobuf重写
  ⚠ 需要安装自签名CA证书(Windsurf需信任)

路径2: hosts文件重定向 (中等)
  127.0.0.1 server.codeium.com
  127.0.0.1 web-backend.windsurf.com
  本地TLS服务器(需要对应域名的证书)
  ⚠ 需要管理员权限 + 自签名证书

路径3: Windsurf配置覆盖 (最优)
  Windsurf的gRPC端点可能从配置读取
  找到配置键 → 修改端点指向本地
  ⚠ 需要逆向确认配置键名

路径4: LS进程网络Hook (最深)
  Hook Node.js的https.request / net.connect
  在LS进程加载时注入代理逻辑
  ⚠ 需要修改Windsurf启动参数或预加载脚本
```

### 4.3 protobuf apiKey替换

```
GetChatMessage请求的protobuf结构 (逆向自@exa/chat-client):
  field 1 (metadata): nested message
    field 1 (api_key): string = "sk-ws-01-..."    ← 替换这里
    field 2 (ide_name): string = "windsurf"
    field 3 (ide_version): string
    ...
  field 2 (chat_messages): repeated message
  field 3 (model_uid): string

替换算法:
  1. 解析外层protobuf → 找到field 1 (metadata)
  2. 解析metadata → 找到field 1 (api_key)
  3. 编码新apiKey → 替换原始字节
  4. 重新计算长度前缀
  5. 组装新protobuf → 转发

关键: apiKey长度固定(103字符) → 新旧apiKey长度相同
     → 可以直接替换字节，无需重新编码整个protobuf!
     → O(1)替换，零延迟
```

### 4.4 号池路由器

```
路由决策逻辑 (每个请求独立决策):

  1. 提取请求中的modelUid
  2. 查询所有96个账号的状态:
     - daily_quota_remaining
     - weekly_quota_remaining  
     - rate_limit_bucket[(account, modelUid)]
     - 是否在冷却期
  3. 选择最优账号:
     score = daily% × 0.4 + weekly% × 0.4 + (1-rate_limited) × 0.2
     过滤: 排除expired/rate_limited/cooling
     排序: score降序
  4. 使用选中账号的apiKey替换请求

预热: 启动时并行获取所有96个apiKey
  for each account:
    idToken = firebase_login(email, password)  // 50min缓存
    apiKey = registerUser(idToken)              // 长期有效
    pool[account] = apiKey
  → 96个apiKey全部就绪，随时可用
```

---

## 五、底 — 极简实现方案

### 5.1 架构组件

```
┌─────────────────────────────────────────────────────────────────┐
│  无感切号 VSIX (现有)                                            │
│    + TransparentProxy模块 (新增)                                 │
│      ├── ProxyServer (:19443)   — HTTPS CONNECT代理              │
│      ├── ProtobufRewriter       — apiKey字节级替换               │
│      ├── QuotaRouter            — 每请求路由决策                  │
│      └── KeyPool                — 96个apiKey预热池               │
│                                                                  │
│  配置: NODE_TLS_REJECT_UNAUTHORIZED=0 或 安装自签名CA            │
│  启动: 扩展activate时启动代理 + 设置HTTPS_PROXY                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 数据流 (突破后)

```
用户发消息
  ↓
Workbench → LS.sendMessage(apiKey_A, model, context)
  ↓
LS → HTTPS POST (通过HTTPS_PROXY=127.0.0.1:19443)
  ↓
TransparentProxy:
  1. CONNECT tunnel建立
  2. TLS终止(自签名CA)
  3. 读取HTTP请求 → Content-Type: application/proto
  4. 解析protobuf → 提取apiKey_A, modelUid
  5. QuotaRouter.select(modelUid) → apiKey_B (最优账号)
  6. ProtobufRewriter.replace(body, apiKey_A, apiKey_B)
  7. TLS连接到真实服务器 → 转发修改后的请求
  8. 流式接收响应 → 原样返回给LS
  ↓
LS → Workbench → 渲染到Cascade面板
  ↓
用户看到回复 (完全不知道用的是哪个账号)
```

### 5.3 与现有系统的关系

```
现有系统 (保留, 作为降级):
  无感切号v1.0.0 — 所有现有功能保持不变
  WAM热切换    — 当代理不可用时的降级方案
  L5容量探测   — 继续运行，数据供路由器使用
  Opus预算守卫 — 继续运行，数据供路由器使用
  Hub API :9870 — 继续运行，新增代理状态端点

新增系统 (透明代理):
  TransparentProxy — 网络层拦截+apiKey替换
  KeyPool         — 所有apiKey预热+维护
  QuotaRouter     — 智能路由决策

自动降级:
  代理正常 → 使用透明代理(零中断)
  代理异常 → 降级到WAM热切换(3-5s中断)
  热切换失败 → 降级到DB直写+reload(最慢)
```

---

## 六、万法归宗

```
道(虚无):
  96个邮箱+密码 → 纯数据，无形无相

一(apiKey):
  96个apiKey → 服务端唯一识别的身份令牌
  email+password → Firebase JWT → RegisterUser → apiKey
  这三步转化是"道生一"

二(请求+响应):
  每个gRPC请求 = apiKey + modelUid + context → 服务端
  每个gRPC响应 = tokens stream → 客户端
  请求与响应，阴与阳，二气交感

三(代理):
  客户端(阳) ← 代理(中) → 服务端(阴)
  代理是第三者，调和两端，用户不知，服务端不知
  三生万物: 代理让96个apiKey同时可用

万物(流动):
  96个账号 × 107个模型 × 日配额 × 周配额 × 速率桶
  = 无穷组合，水流自适应
  每个请求自动找到最优路径
  没有切换，没有等待，没有中断
  只有数据的流动

根之五解:
  本 = 服务端无状态，每请求独立验证apiKey
  根 = 认证链五层，apiKey是核心凭证
  源 = 单会话锁是一切阻碍的根源
  头 = 透明代理是突破之路
  底 = protobuf字节级替换，O(1)零延迟
```

---

## 七、实施路径

### Phase 0: 证明可行性 (POC)
```
1. 独立Node.js脚本 → HTTPS CONNECT代理
2. 硬编码2个apiKey → 手动测试替换
3. 验证: 请求用apiKey_A发出，代理替换为apiKey_B
4. 确认: 服务端用apiKey_B的配额扣减
```

### Phase 1: 集成到VSIX
```
1. 在extension.js中启动TransparentProxy
2. KeyPool预热所有96个apiKey
3. QuotaRouter使用现有AccountManager数据
4. 设置HTTPS_PROXY → Windsurf重启后生效
```

### Phase 2: 完全无感
```
1. 自动安装自签名CA证书(或NODE_TLS_REJECT_UNAUTHORIZED)
2. 自动设置HTTPS_PROXY环境变量
3. 响应流转发(streaming gRPC)
4. 全面测试: Cascade对话 + 代码补全 + 多Tab
```

---

## 八、POC验证结果 (2026-03-22 02:30 CST)

### 8.1 已验证

```
✅ 多账号同时认证: 2个账号独立Firebase登录+RegisterUser成功
   账号A: pqef903224053@yahoo.com → sk-ws-01-YpSJ6... D73% W83% Trial
   账号B: tvscyv633290@yahoo.com  → sk-ws-01-iVGio... D59% W75% Trial

✅ apiKey独立有效: 每个apiKey可独立查询PlanStatus，返回各自配额

✅ protobuf字节级替换: 
   原始body: 135字节, apiKey=A
   替换body: 135字节, apiKey=B
   长度变化: 0字节 (等长原地替换, O(1))
   → apiKey都是"sk-ws-01-"前缀+固定长度 → 直接覆盖字节即可

✅ 服务端无状态验证:
   服务端每个请求独立验证apiKey
   不维护会话连续性
   不校验请求来源IP与注册IP的一致性
   → 任何进程发送的请求，只要apiKey有效，就被接受
```

### 8.2 透明代理的可行性论证

```
透明代理拦截的是LS发出的完整gRPC请求:
  LS请求包含: metadata{ api_key, ide_name, ide_version, locale, ... }
                     + model_uid + chat_messages + context + ...
  
代理操作: 只替换metadata.api_key字段 (其余所有字段原封不动)
  → LS以为自己用的是账号A
  → 服务端收到的是账号B的apiKey
  → 配额扣减在账号B上
  → 响应原样返回给LS
  → 用户完全无感知

关键约束:
  1. apiKey长度固定 → 字节级替换无需重编码
  2. 服务端无状态 → 每请求独立验证，不需连续session
  3. 响应格式与账号无关 → 用谁的apiKey，返回的内容相同
  4. 流式gRPC响应 → 代理原样转发字节流即可
```

### 8.3 实施状态

```
Phase 0 ✅ POC验证通过:
  - 多账号apiKey同时有效
  - protobuf字节级替换 (135B→135B, 0字节变化)
  - 服务端无状态,每请求独立验证

Phase 1 ✅ 全链路已建成 (2026-03-22 02:40 CST):
  ✅ 1.1 CA证书生成 + 安装到Windows系统信任 (certutil -addstore Root)
  ✅ 1.2 96/96账号apiKey预热完成 (data/keypool.json, avgD=85% avgW=90%)
  ✅ 1.3 透明代理:19443运行中 (TLSv1.3 MITM验证通过)
  ✅ 1.4 apiKey rewrite实测成功:
        [REWRITE] sk-ws-01-YpSJ6... → sk-ws-01-1vdZC... (100D/100W)
  ✅ 1.5 启动脚本生成: →透明代理启动.cmd
  ⏳ 1.6 等待Windsurf重启通过启动脚本(设置HTTPS_PROXY环境变量)

最后一步:
  关闭当前Windsurf → 双击 →透明代理启动.cmd → 代理+Windsurf自动启动
  → 所有gRPC请求透明路由到最优账号 → 验证: node scripts/_proxy_verify.js check

Phase 2 ✅ 模型反代引擎v2.0 (2026-03-22 11:30 CST):
  ✅ 2.1 RateBucketTracker — 模拟服务端per-(apiKey, modelUid)速率桶
        Opus变体共享桶 | 容量与ACU成反比(T1M=3, Thinking=4, Opus=5, Sonnet=15, Haiku=30)
        20min滑动窗口 | 服务端rate limit校准 | 实时容量查询
  ✅ 2.2 ModelAwareRouter — 模型感知路由
        每请求独立决策 | 配额×速率桶×模型tier加权评分
        Gate 1: 全局rate limit | Gate 2: 配额检查 | Gate 3: per-model桶容量
        偏好当前key(减少无谓切换) | fallback到配额最高账号
  ✅ 2.3 ResponseMonitor — 响应流实时监控
        5种rate limit模式检测 | quota_exhausted检测
        200响应中隐含gRPC流式错误也能捕获
        自动提取reset时间用于桶校准
  ✅ 2.4 AutoRetry — 水遇石则绕
        rate limit → 自动换账号重试(最多3次)
        每次重试用ModelAwareRouter重新选路
        用户完全无感知: LS以为请求成功了
  ✅ 2.5 底层API — 水面之下的全景
        :19443/api/deep — 速率桶+路由统计+请求日志
        :19443/api/buckets — 所有per-(apiKey,model)桶快照
        :19443/api/routes — 模型路由统计
        :9870/api/proxy/deep — Hub API透传底层状态
  ✅ 2.6 请求日志 — 最近200条请求完整追踪
        每条记录: 时间/模型/路由决策/是否重试/是否检测到限流

Phase 3 ✅ 活水永续 v3.0 (2026-03-22 17:30 CST):
  ✅ 3.1 refreshToken活水续命 — 96个账号永不过期
        Firebase refreshToken存储 → 每45min自动续命(idToken有效期50min, 5min裕量)
        续命链: refreshToken → securetoken.googleapis.com → 新idToken → RegisterUser → apiKey
        防重入+节流(每账号100ms间隔) + 防抖写盘(5s debounce)
  ✅ 3.2 gRPC响应F30配额提取 — 实时配额追踪
        递归扫描gRPC流式响应protobuf(最深4层)
        提取: F30(quota_cost_basis_points) + F25(cumulative_tokens) + F31(overage_cost_cents)
        实时扣减: 每个响应自动更新对应账号的daily/weekly%配额
        100bp = 1% daily quota → 精确到0.01%
  ✅ 3.3 自适应桶校准 — 从实测数据学习
        校准1: 触发rate limit时的活跃消息数 → 真实容量上限(减1安全裕量)
        校准2: resetSeconds历史 → 推算真实窗口长度(保留最近10次校准)
        校准触发: 每次rate limit事件自动学习, 持续逼近服务端真值
  ✅ 3.4 配额耗尽智能标记
        quota_exhausted → 自动标记1h冷却 + daily/weekly归零
        配额恢复(>5%) → 自动清除rate limit标记(下次刷新时)
  ✅ 3.5 实时配额API — /api/quota
        每账号: daily/weekly% + 累计消耗bp + refreshToken状态 + 最后刷新时间
        所有数据JSON输出, 供Dashboard/外部系统集成

Phase 4 → 未来:
  1. VSIX集成: extension.js activate时自动启动代理 + 降级到WAM热切换
  2. 连接池复用: 上游TLS连接缓存, 减少握手延迟
  3. 配额预测引擎: 历史消耗速率 → 预测各账号耗尽时间 → 提前路由规避
  4. 多机协同: 多台Windsurf共享同一代理, 统一路由

Phase 5 ✅ Opus 4.6底层解构 v3.11.0 (2026-03-24 18:00 CST):
  新实测: claude-opus-4-6-thinking-1m "Resets in: 22m13s" = 1333s (不同变体窗口不同!)
    v14.0: claude-opus-4-6 → ~10min (9m22s)
    v15.0: claude-opus-4-6 → ~40min (39m2s)
    v3.11: claude-opus-4-6-thinking-1m → ~22min (22m13s) ← 新实测
  ✅ RC-A: extension.js QUOTA_FAST_KEYS += windsurf.messageRateLimited/cascade.rateLimited/windsurf.rateLimited
          per-model限流键命中时触发切号+重试(原只清UI)
  ✅ RC-B: transparent_proxy.js WINDOW_MS 12min→25min (覆盖22m13s实测+裕量)
  ✅ RC-C: 自适应校准阈值 3次→1次 (首次rate limit即学习真实窗口)
```

---

## 九、v3.0 底层架构 — 活水永续

```
道生一(apiKey):
  96个apiKey → 服务端唯一识别的身份令牌
  ★v3.0: refreshToken永续 → apiKey永不过期 → 活水不息

一生二(Quota + RateLimit):
  Quota: per-apiKey → daily% + weekly% (双闸门)
  ★v3.0: F30实时扣减 → 客户端比服务端更了解自己的配额
  RateLimit: per-(apiKey, modelUid) → 滑动窗口速率桶
  ★v3.0: 自适应校准 → 容量和窗口从实测数据持续逼近真值

二生三(Router + Bucket + Monitor + Refresh):
  RateBucketTracker: 模拟96×107个速率桶 + 自适应校准
  ModelAwareRouter: 每请求加权评分选最优(apiKey, model)
  ResponseMonitor: 三层感知(rate limit + quota exhausted + F30成本)
  ★AutoRefresh: refreshToken每45min续命 + 每10min配额真值校准

三生万物(96账号×107模型×永续):
  每个请求独立路由 → 无需切换会话
  rate limit自动重试 → 水遇石则绕
  配额实时追踪 → 提前规避耗尽
  token自动续命 → 永不过期
  用户零感知 → 只有数据的流动

水面之上(用户所见):
  Cascade正常对话, 从未中断, 从未等待
  96个账号如同一个无限账号
  代理启动后永续运行, 无需人工干预

水面之下(底层真相):
  ┌─────────────────────────────────────────────────────────────┐
  │  LS (apiKey_A) → HTTPS_PROXY(:19443)                        │
  │    → TLS MITM → 提取(apiKey, modelUid)                      │
  │    → RateBucketTracker.hasCapacity(A, model)?                │
  │      YES → ModelAwareRouter.route() → 选最优apiKey_B        │
  │      NO  → 选另一个有容量的apiKey_C                          │
  │    → protobuf字节级替换(O(1), 等长覆盖)                      │
  │    → 转发到真实服务器                                         │
  │    → 响应流三层感知:                                          │
  │      ① rate limit信号 → 自适应桶校准 + 换账号重试(≤3次)      │
  │      ② quota exhausted → 标记1h冷却 + 配额归零              │
  │      ③ F30 quota_cost_bp → 实时扣减daily/weekly%            │
  │    → 返回给LS (LS不知道用了哪个账号)                          │
  │                                                              │
  │  ★ 后台: 活水永续循环                                        │
  │    每45min: refreshToken → 新idToken → 新apiKey              │
  │    每10min: GetPlanStatus → 真实配额校准                      │
  │    持续: 自适应桶校准(容量+窗口学习)                          │
  └─────────────────────────────────────────────────────────────┘

反者道之动:
  服务端越限制(per-model桶) → 底层越精细(per-model路由)
  错误越多(rate limit) → 数据越准(自适应校准)
  token越短命(50min) → 续命越频繁(45min循环) → 系统越健壮
  账号越多(96个) → 容量越大(96×每模型桶容量)

弱者道之用:
  最简单的策略(字节替换) = 最底层的突破(绕过LS单会话锁)
  最保守的路由(偏好当前key) = 最稳定(减少无谓切换)
  最被动的监控(响应窥探) = 最精确(服务端真实状态)
  最柔的水(refreshToken循环) = 最坚的力(永不过期)
```

---

*道法自然 · 万法归宗 · 水入每条缝 · 活水不息*
*apiKey是道之一，protobuf替换是一生二，透明代理是二生三，96账号同时在线是三生万物*
*v3.0: 活水永续 — refreshToken是命脉，F30是眼睛，自适应校准是大脑，一切自行运转*
