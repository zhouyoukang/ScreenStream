# 号池管理端 v1.6.0

## 身份
公网号池统管VSIX。LAN-only管理Hub + 分知加密 + 多池统管 + 热部署 + **云端推送 + 安全防护**。
4源文件(src/) + 2前端(media/) + 1热部署(scripts/).
**回归本源**: 纯管理员端——云池账号/用户/支付/设备/审计/**推送管理/威胁情报/远程管理**。用户端功能已迁移至Windsurf小助手。

## 边界
- src/extension.js — 入口+Hub(:19881)+_G.hubHandler热重载委托+命令注册+客户端中继(/api/v1/*)
- src/lanGuard.js — LAN安全层(子网绑定/设备注册/会话/审计链/速率限制/定时清理)
- src/poolManager.js — 多池统管(分知加密+DIRECT:直传/outbound-only/CRUD+输入验证+P2P confirm/reject/create/stats+客户端relay pay-init/status)
- src/adminPanel.js — Webview管理面板(消息→Hub API代理, 30s超时, handleExtRoute热重载委托)
- media/admin.js — 前端交互(6子标签+池详情子页+真实用户列表+确认对话框+彩色toast)
- media/panel.html — 面板HTML模板(紫色渐变主题, 卡片布局, stat网格)
- scripts/hot-deploy.js — 热部署(--inject写入安装目录, --signal触发热重载)

## 入口
- VSIX侧边栏: 管理面板(webview, 3标签: 云池/设备/审计, 云池内含远程管理子标签)
- Hub API: http://127.0.0.1:19881/api/health
- Dashboard: http://127.0.0.1:19881/dashboard

## Hub API端点 (12/12 E2E PASS)
| 端点 | 方法 | 认证 | 说明 |
|---|---|---|---|
| /api/health | GET | 无 | Hub健康检查 |
| /api/enroll | POST | LAN | 设备注册+获取session(已注册则刷新session) |
| /api/overview | GET | session | 全池总览(聚合所有云池admin/overview) |
| /api/pools | GET | session | 本地池列表 |
| /api/pools/add | POST | session | 添加云池(name/url/adminKeyHalf/hmacSecret) |
| /api/pools/remove | POST | session | 删除云池(poolId) |
| /api/pools/:id/overview | GET | session | 单池总览(→云端/api/admin/overview) |
| /api/pools/:id/accounts | GET | session | 单池账号(→云端/api/admin/accounts) |
| /api/pools/:id/users | GET | session | 单池用户(→云端/api/admin/users) |
| /api/pools/:id/payments | GET | session | 单池支付(→云端/api/admin/payments) |
| /api/pools/:id/health | GET | session | 单池健康(→云端/api/health) |
| /api/pools/:id/public | GET | session | 单池公开数据(→云端/api/public/pool) |
| /api/pools/:id/confirm | POST | session | 确认支付(→云端/api/admin/confirm) |
| /api/pools/:id/reject | POST | session | 拒绝支付(→云端/api/admin/reject) |
| /api/pools/:id/cloud-devices | GET | session | 云端设备(→云端/api/admin/devices) |
| /api/pools/:id/cloud-p2p | GET | session | P2P订单(→云端/api/admin/p2p-orders) |
| /api/payment-stats | GET | session | P2P支付统计(全池汇总: p2p/w_pool/revenue) |
| /api/p2p/confirm | POST | session | 确认P2P订单+充值W积分(orderId/poolId) |
| /api/p2p/reject | POST | session | 拒绝P2P订单(orderId/poolId) |
| /api/p2p/create | POST | session | 管理员创建P2P订单(device_id/w_credits/method/auto_confirm) |
| /api/pools/:id/cloud-pool-enhanced | GET | session | 增强池数据+W资源 |
| /api/v1/activate | POST | relay-HMAC | 客户端激活(→云端/api/device/activate) |
| /api/v1/pay-init | POST | relay-HMAC | 客户端发起P2P支付(→云端/api/p2p/init) |
| /api/v1/pay-status | GET | relay-HMAC | 客户端查询支付状态(→云端/api/p2p/status) |
| /api/v1/remote-pending | GET | relay-HMAC | 客户端轮询待审批远程请求 |
| /api/v1/remote-respond | POST | relay-HMAC | 客户端响应远程请求(允许/拒绝) |
| /api/devices | GET | session | LAN已注册设备 |
| /api/devices/revoke | POST | session | 撤销设备 |
| /api/audit | GET | session | 审计日志 |
| /api/lan/status | GET | session | LAN状态 |
| /api/machine-info | GET | session | 本机身份信息 |
| /api/cloud-status | GET | session | 云端聚合状态(W资源/设备/策略) |
| /api/set-strategy | POST | session | 消费策略(local-first/cloud-first) |

## 远程管理 API (v1.5.0 新增)
| 端点 | 方法 | 认证 | 说明 |
|---|---|---|---|
| /api/remote/request | POST | session | 创建远程管理请求(需客户端审批) |
| /api/remote/status | GET | session | 查询远程请求状态(pending/approved/denied) |
| /api/remote/devices | GET | session | 获取可远程管理设备列表 |

远程管理安全机制: 管理员发起→内存存储→客户端15s轮询→VS Code弹窗确认(modal)→用户明确允许/拒绝→审计记录。5min超时自动过期。
允许操作: diagnose|config_check|cache_clear|plugin_status|network_test|reset_binding|custom

## 推送管理 API (v1.3.0 新增)
| 端点 | 方法 | 认证 | 说明 |
|---|---|---|---|
| /api/push/list | GET | session | 获取所有推送指令列表 |
| /api/push/create | POST | session | 创建推送指令(→云端/api/admin/push) |
| /api/push/revoke | POST | session | 撤销推送指令(→云端/api/admin/push/revoke) |
| /api/security/events | GET | session | 获取安全事件+IP信誉(→云端/api/admin/security-events) |
| /api/security/block | POST | session | 封禁/解封IP(→云端/api/admin/ip-block) |

推送类型: config_update | announcement | force_refresh | version_gate | kill_switch | security_patch | custom
推送机制: 管理员创建→云端存储→用户心跳拉取→自动执行。HMAC签名防篡改。

## 安全架构 v2.1 (道之防·万法归宗)
```
L1 网络层: Hub仅监听127.0.0.1, 禁信X-Forwarded-For(防伪LAN绕过)
L2 设备层: 硬件指纹注册 + HMAC认证(timing-safe比较)
L3 会话层: 时间窗口轮转 + Nonce防重放 + 定时清理(60s/120s)
L4 知识层: 分知加密(stored_half + machine_identity)
L5 传输层: HMAC签名(outbound到云池) + 64KB body大小限制
L6 混淆层: Fortress 12层反逆向
L7 审计层: 哈希链日志 + 异常封禁(localhost豁免)
L8 推送层: 签名推送指令 + 版本门控 + 紧急停止
L9 情报层: IP信誉评分 + 安全事件追踪 + 威胁仪表盘
L10 输入层: URL格式/协议验证 + 名称HTML过滤 + 长度截断
L11 远程层: 客户端审批制(modal弹窗) + 5min超时 + 操作白名单 + 审计记录
```

## 云池连接 (已验证)
- URL: `https://aiotvr.xyz/pool`
- Admin Key模式: `DIRECT:` 前缀直传 | 默认HMAC(half, machineIdentity)
- 凭据: secrets.env → CLOUD_POOL_ADMIN_KEY / CLOUD_POOL_HMAC_SECRET
- 云端: cloud_pool_server.py v3.0 (96账号, SQLite, 设备+W资源+P2P)
- 源码: `Windsurf无限额度/030-云端号池_CloudPool/cloud_pool_server.py`

## 客户端中继 API (/api/v1/* — 混淆路径)
| 本地路径 | 方法 | 云端转发 | 说明 |
|---|---|---|---|
| /api/v1/ping | GET | /api/health | 连接检查 |
| /api/v1/status | GET | /api/ext/pool | 号池状态 |
| /api/v1/acquire | GET | /api/ext/pull | 拉取账号 |
| /api/v1/inject | GET | /api/ext/pull-blob | 拉取auth blob |
| /api/v1/signal | POST | /api/ext/heartbeat | 心跳上报 |
| /api/v1/report | POST | /api/ext/push | 健康数据推送 |
| /api/v1/reclaim | POST | /api/ext/release | 归还账号 |
| /api/v1/metric | GET | /api/public/pool-enhanced | 增强池数据 |
| /api/v1/me-status | GET | /api/admin/devices→查本机 | 本机激活状态+W额度 |
| /api/activate-device | POST | localhost-trusted | 激活设备(免session,向后兼容) |

认证: 机器指纹派生HMAC(`HMAC-SHA256(machineId, 'wam-relay-v1')`)，双端独立计算，无存储无传输。
请求头: `x-ts`(时间戳) + `x-nc`(nonce) + `x-sg`(签名) + `x-di`(deviceId)。60s时间窗口。

## 热重载架构
- Hub server handler通过 `_G.hubHandler` 委托, 热重载时自动替换
- 热触发: `~/.pool-admin-hot/.reload` 文件变更 | poolAdmin.hotReload命令
- 热重载范围: lanGuard.js + poolManager.js + adminPanel.js + media/* + Hub handler
- 状态持久化: pools.enc(AES加密) + lan_guard.enc + audit.log
- 配置: `~/.pool-admin/` 目录

## 铁律
1. Hub绑定127.0.0.1, LAN Guard负责认证
2. 分知加密: admin_key = HMAC(stored_half, machine_identity) 或 DIRECT:key
3. 设备注册: 仅LAN内设备, 重复注册返回新session
4. 会话有限: 15分钟过期, Nonce防重放
5. 审计链: 哈希链不可篡改, 所有操作可追溯
6. Outbound-only: 管理密钥永不外传, 仅本机向云池发请求
7. 禁止新建.js文件: src/4个 + media/2个(admin.js+panel.html) = 上限

## v1.6.0 变更日志 (2026-03-23)
- **功能**: 限流防护(Rate Limit Guard)——从根本上消除Rate Limit等待1小时问题
- **原理**: 客户端上报限流事件→自动释放账号→推送force_refresh切换新账号→冷却期追踪
- **新端点**: `/api/v1/rate-limit-report`(客户端中继) + `/api/ratelimit/*`(管理员API)
- **UI**: 云池模式新增"限流防护"子标签——状态/配置/冷却中账号/手动切换/事件日志
- **配置**: 冷却时长(默认65min) + 预警阈值(默认D%<85%) + 自动切换开关

### 限流防护 API
| 端点 | 方法 | 认证 | 说明 |
|---|---|---|---|
| /api/v1/rate-limit-report | POST | relay-HMAC | 客户端上报限流事件→自动切换 |
| /api/ratelimit/status | GET | session | 限流状态+冷却列表+事件日志 |
| /api/ratelimit/config | POST | session | 配置冷却时长/预警阈值/开关 |
| /api/ratelimit/clear | POST | session | 手动清除指定账号冷却 |
| /api/ratelimit/trigger-switch | POST | session | 手动强制触发账号切换 |

## v1.5.0 变更日志 (2026-03-23)
- **功能**: 远程设备管理(云池→远程管理子标签)——管理员可远程操控任意客户端电脑
- **安全**: 客户端审批制——所有远程操作VS Code弹窗确认(modal), 用户必须明确允许
- **安全**: 操作白名单(7种)——diagnose/config_check/cache_clear/plugin_status/network_test/reset_binding/custom
- **安全**: 远程请求5min超时自动过期 + 每设备最多10待审批请求
- **修复**: 客户端激活走/api/v1/activate中继(HMAC认证)——之前直连/api/device/activate被session auth拦截
- **修复**: /api/activate-device移至session检查之前(localhost-trusted)——向后兼容旧客户端
- **新增**: /api/v1/me-status端点——客户端查询本机激活状态+W额度(poolManager.extDeviceStatus)
- **新增**: adminPanel._getCloudStatus返回machine_code字段——客户端显示本机识别码
- **迁移**: 公网远程直连从client迁至admin端, client仅保留审批轮询

## v1.4.0 变更日志 (2026-03-23)
- **安全**: timing-safe HMAC比较防时序攻击, 禁信XFF头防LAN绕过, 64KB body大小限制防DoS
- **安全**: localhost豁免速率限制/失败封禁(修复 webview自锁死BUG)
- **安全**: Nonce/会话定时清理(60s/120s)防内存泄漏
- **安全**: 池名称HTML过滤+URL协议验证(防XSS+无效URL)
- **修复**: 移除adminPanel._patchHubHandler——之前删除全部HTTP listener再重加导致泄漏
- **修复**: 热重载前先dispose旧实例(清定时器+保存状态)再创建新实例
- **修复**: enroll端点返回sessionId字符串(而非对象)
- **功能**: 云端用户标签显示真实用户列表(从池API拉取)
- **功能**: 池详情视图(点击详情→账号列表+用户列表+返回按钮)
- **UX**: 危险操作确认对话框(删除池/撤销设备/紧急停止/撤销推送)
- **UX**: toast红绿分色(成功绿色/失败红色)

## 前端页面结构 (media/admin.js)
- **云池**(mode=cloud): 账号(含池详情子视图)/用户(真实列表)/支付(含确认拒绝)/云设备/**远程管理**/推送管理/云池
- **设备**(mode=local): LAN设备列表+撤销 / 云池配置(CRUD+验证)
- **审计**(mode=hybrid): 哈希链审计日志 / 威胁情报(IP封禁) / 安全状态
- 危险操作: confirm()对话框保护(删除池/撤销设备/kill_switch/撤销推送)
- CSS: panel.html定义紫色渐变主题, 卡片布局, stat网格

## 关联
| 方向 | 项目 | 说明 |
|---|---|---|
| 上游 | Windsurf小助手 | 用户端VSIX(完全隔离) |
| 下游 | cloud_pool_server.py | 公网云池服务端(aiotvr.xyz/pool) |
| 下游 | 阿里云服务器 | 60.205.171.100 / aiotvr.xyz |
| 逆向 | Windsurf无限额度 | 逆向知识支撑 |

## 陷阱
- Hub端口冲突: 19881被占用时自动+1
- 分知密钥: 换机器后需重新配置adminKeyHalf, 或用DIRECT:前缀
- LAN变更: WiFi切换后LAN IP变化, Hub需热重载
- 会话过期: 15分钟无操作需重新认证(enroll自动刷新)
- 云端超时: 阿里云HTTPS查询可能需10-20s, 超时已设30s
- 路由顺序: cloud-forward匹配必须在通用pool action之前
- extension.js变更需Extension Host重启(热重载仅覆盖子模块)
- 云端管理端点返回403: 检查服务端 CLOUD_POOL_ADMIN_KEY 环境变量是否匹配 secrets.env
