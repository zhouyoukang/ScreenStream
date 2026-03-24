# 无感切号 · 万法归宗 v3.11.0

## 身份

号池引擎+透明代理+热重载。用户是号池不是单账号。
VSIX(6源文件15命令5配置)+Hub:9870+透明代理:19443+管理端中继:19881。
三模式号池源(本地/云端/混合) · 透明代理apiKey路由 · 活水永续 · 热重载零中断。
**道之隔离**: 云端连接全部归管理端。客户端不知云端URL，仅与本机管理端通信。

## 边界

- ✅ `src/`(6源文件) + `media/panel.html`(模板) + `media/panel.js`(渲染+交互)
- ✅ `scripts/transparent_proxy.js` — 透明代理v3.0(活水永续+F30配额+自适应桶)
- ✅ `scripts/hot-deploy.js` — 热部署v4.0(双写归一·永不重载·watch模式)
- ✅ `scripts/fortress.js` — 堡垒混淆(12层防护)
- ✅ `FIRST_PRINCIPLES.md` + `ROOT_SOURCE.md` — 本源知识
- 🚫 `scripts/`其余仅开发用，不打包进VSIX
- 🚫 `backend/` — 空目录(Python后端canonical位置: `Windsurf无限额度/`)

## 入口

- VSIX侧边栏: 号池面板(webview)
- Hub API: http://127.0.0.1:9870/health
- Dashboard: http://127.0.0.1:9870/dashboard
- 透明代理: http://127.0.0.1:19443/api/deep
- 实时配额: http://127.0.0.1:19443/api/quota (或 :9870/api/proxy/quota)
- 热重载状态: http://127.0.0.1:9870/api/hot/snapshot
- 原理: `FIRST_PRINCIPLES.md` + `ROOT_SOURCE.md`

## 铁律

1. 认证链: Firebase→idToken→provideAuthTokenToAuthProvider→session→GetPlanStatus
2. 4层注入: S0=idToken直传→S1=OTAT→S2=apiKey→S3=DB直写
3. 号池引擎: Session Pool全账号预认证 + Capacity Matrix并行L5探测
4. 三模式号池源: poolSource=local|cloud|hybrid (设置项wam.poolSource)
5. 禁止新建.js文件 — src/6个 + media/panel.js = 7个文件是上限
6. 模板架构: webviewProvider计算数据JSON → panel.html模板注入 → panel.js前端渲染
7. 云端隔离: `cloudPool.js`只连`127.0.0.1:19881`，永不直连公网。路径混淆，无法推断业务。
8. 透明代理v3.0: refreshToken每45min续命 + F30实时配额扣减 + 自适应桶校准
9. 代理自动启动: extension.js activate → 检测:19443 → 离线则spawn → 降级到WAM
10. 热重载v4.0: 双写归一(hot dir即时+install dir持久) · `npm run hot`=唯一命令 · 永不需要重载窗口
11. v13.0切后验证: _seamlessSwitch切后立即验证额度(缓存+API双检) → 耗尽则标记+紧急重轮转 · round-robin跳过已知耗尽账号
12. v14.0 Opus防护升级: 服务端窗口缩至~10min(实测9m22s) → ALL_OPUS预算=1条即切 + 窗口12min + 冷却720s + 响应式切换budget guard联动 + 模型感知选号(findBestForModel) + 切后Opus model验证
16. v16.0 自动重试+热链自愈: rate limit→自动retry(1.2s) + L5探测3s阈值 + hot-deploy语法防护 + IPC管道自愈
17. v3.6.0 万法归宗·9虫修复: handler补全+_scheduleRender+切号漏调+热重载快照+作用域修正+配置补全+版本同步
18. v3.6.1 为道日损: 8208→7807行(-4.9%) 模型守卫统一+常量归一+装饰移除+重复提取+注释折叠
19. v3.7.0 去芜留菁: panel.js增量DOM+防抖300ms+轻量hash dedup+cloudPool超时5s+keep-alive+退避+VSIX瘦身(22MB→416KB)
20. v3.8.0 锚定本源: 去除L3降级偏离(仅纯账号轮转,不降级模型) + 防连锁限流(切号后冷却窗口防止多账号连锁触发) + 锚定本源模型(用户选什么模型就用什么模型)
21. v3.9.0 无感续传·根因修复: 5处切号路径缺失autoRetry的根因修复(Gate4/G1G2/cachedPlan/L5-G4/L5-default) + _scheduleAutoRetry升级为多重重试引擎(3次退避1.5→3→6s+UI错误清除+验证闭环) + _clearRateLimitUI自动清除context key+通知残留 + 无感续传拦截器(_startSeamlessInterceptor 1s快扫第二感知通道) + 对话-账号映射追踪 + Hub API端点(/api/seamless-stats, /api/conversation-map)
22. v3.10.0 道法自然·根因修复: 5处根因修复 — RC1拦截器升级为切号触发器(1s检测→切号+重试,不再仅清UI) + RC2 FAST_KEYS增加3个配额键(chatQuotaExceeded/windsurf.quotaExceeded/rateLimitExceeded) + RC3 _classifyRateLimit识别gRPC FAILED_PRECONDITION(code 9日配额耗尽) + RC4低额自适应加速(quota<20%自动boost 45s→8s轮询) + RC5 RATE_LIMIT_PATTERNS增加3个模式(Failed precondition/quota exhausted/daily usage quota)
22.1 v3.10.1 云端修复·checkHealth后刷新面板: 4处根因全修 — [fix1] setPoolSource切换云端模式时checkHealth()是fire-and-forget导致面板渲染时_online仍为false → .then(()=>refreshPanel()) [fix2] 启动3s健康检查完成后补刷面板 [fix3] _doRefreshPool点刷新时重检云端 [fix3b] fix3的云端检查被放在early-return之后(纯云模式无本地账号时跳过) → 移至early-return之前+加_refreshPanel() | E2E测试: 72/72通过(_e2e_wam_test.js)
23. v3.11.0 Opus 4.6底层解构·根因修复: 新实测T1M窗口22m13s(1333s) | RC-A QUOTA_FAST_KEYS增加windsurf.messageRateLimited/cascade.rateLimited/windsurf.rateLimited(per-model限流也触发切号+重试,原仅清UI) | RC-B 透明代理WINDOW_MS 12min→25min(覆盖22m13s实测值+余量) | RC-C 代理自适应校准从3次降至1次(速学首次即生效)

## 关联

| 方向 | 项目             | 说明                                  |
| ---- | ---------------- | ------------------------------------- |
| 纳管 | 安全管理         | extension_manager.py                  |
| 逆向 | Windsurf无限额度 | 逆向知识支撑(QUOTA_SYSTEM/RATE_LIMIT) |
| 中继 | 号池管理端       | 管理端中继 `127.0.0.1:19881/api/v1/*` (机器指纹HMAC, 路径混淆) |

## 陷阱

- WAM限流: 频繁切换触发rate limit，需等待cooldown
- Opus窗口: v14.0观测~10min("Resets in: 9m22s"), v15.0观测~40min(claude-opus-4.6: "Resets in: 39m2s"), **v3.11观测~22min(claude-opus-4-6-thinking-1m: "Resets in: 22m13s"=1333s)** — 不同变体窗口不同，budget=1每条即切是唯一可靠防线
- 冷却时间必须>=实际重置时间: v14.0用720s→v15.0用2400s，否则账号提前重置触发新一轮rate limit循环
- state.vscdb直写(S3)是最后手段，优先S0/S1
- poolSource与routingMode是两个独立维度，不要混淆
- 激活必须走/api/v1/activate中继路径(HMAC认证)，不可直连/api/device/activate(会被session auth拦截)
- 远程管理已迁移到管理端，客户端只做审批轮询，不主动发起远程连接
- 透明代理需先warmup(含refreshToken) → 否则45min后活水断流
- hot-deploy用PowerShell写JS时,模板字符串反引号被PowerShell吃掉 → 必须用字符串拼接替代模板字面量,或用Node.js脚本写入
- hot-deploy失败→watcher死→Hub离线: 恢复路径=IPC管道`\\.\pipe\*-main-sock`发`{type:'restartExtensionHost'}`(4字节LE长度头+JSON)
- keypool.json含敏感凭证(apiKey+refreshToken) → 已gitignore
- **Hub:9870离线根因**: 若hot-dir中存在旧版extension.js(缺少某函数如`_detectCascadeTabs`)，activation抛异常被catch后继续运行但Hub/watcher均未初始化 → IPC重启无效(不重载磁盘) → 唯一解: Windsurf命令面板执行`wam.hotReload`或重载窗口(Ctrl+Shift+P → Reload Window)
- **透明代理手动启动**: `→透明代理启动.cmd`或`node scripts/transparent_proxy.js serve`(需先`warmup`预热keypool)。HTTPS_PROXY必须在Windsurf启动前设置方可生效。
