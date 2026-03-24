# 一生二 · 状态面板（STATUS）

> 道生一，一生二，二生三，三生万物。
> 最后更新：2026-03-24（**ScreenStream 四项根因修复 · /key keycode · /stream/start AgentBridge · /settings去假 · 网关幂等 · 128/128全通**）
## 0) 权威入口

| 文件 | 用途 |
|------|------|
| `STATUS.md` | 本文件 — 项目全景（冷启首读） |
| `核心架构.md` | ScreenStream核心架构（6模块/118+API/构建部署） |
| `AGENT_GUIDE.md` | DaoOne v2.0 — 全设备统一入口 |
| `.windsurf/rules/workspace.md` | 道层always-on（凭据+安全+冷启） |
| `凭据中心.md` + `secrets.env` | 凭据索引+实际值 |
| 各子项目 `_AGENT_GUIDE.md` | 按需发现（安全管理/quest3等） |

## 1) 全景统计

| 维度 | 数量 |
|------|------|
| Gradle模块 | 6个（app/common/mjpeg/rtsp/webrtc/input） |
| Python Hub服务 | 道生一:8880 + 卫星Hub（见下表） |
| Rules / Skills / Workflows | 见 `.windsurf/` 目录 |
| AGENT_GUIDE | 各项目目录（Agent按需发现） |
| MCP Server | 4活跃(context7/github/playwright/tavily) + 4禁用(chrome-devtools/gitee/dispatch/user-input) · 路径：`.windsurf/` |

## 2) 核心成果

### 无感切号 v6.3.0 全感知号池引擎 (VSIX + Agent Hub)

- **范式转换**: 用户是号池不是单个账号 — 统一额度·自动轮转·实时监控·无感切换
- VSIX: 6文件(src/5+media/panel.js) | 12命令 | 6配置项 | 54账号号池
- **Agent Hub v1.0 (:9870)**: Python HTTP后端，20+ API端点，任意Agent无感管理
  - 本机 E2E 35/35 PASS | 远程179 E2E 35/35 PASS | Dashboard SPA
  - API: pool/status, pool/rotate, pool/refresh, account/CRUD, batch, fingerprint, quota, proxy, logs
  - 与VSIX共享账号数据文件，互不冲突
- 号池引擎: _poolTick自适应轮询(45s/8s) + selectOptimal最优选号 + shouldSwitch自动判断
- 4层注入: S0=idToken直传 → S1=OTAT → S2=apiKey → S3=DB直写(state.vscdb)
- 全感知监测: 8+context key + cachedPlanInfo监测(30s) + 15s延迟 + OutputChannel日志化
- 多窗口协调: 窗口注册+30s心跳+90s死亡检测+账号隔离
- 参考: `无感切号/FIRST_PRINCIPLES.md`

### 号池管理端 v1.4.0（:19881 Hub + VSIX）

- **纯管理员端VSIX**: LAN-only Hub(:19881) + 分知加密 + 多池统管 + 热部署
- 4源文件(src/) + 2前端(media/) | 云端96账号 + 设备+W资源+P2P
- E2E: 14/14本地PASS + 6/6云端PASS（overview/accounts/users/devices/payments/audit）
- v1.4.0安全加固: timing-safe HMAC + XFF禁信 + 64KB体限 + localhost速率豁免 + Nonce清理
- v1.4.0修复: 移除_patchHubHandler监听器泄漏 + 热重载dispose + enroll格式修复
- v1.4.0功能: 真实用户列表 + 池详情子视图 + 危险操作确认框 + toast分色

### ScreenStream核心（6模块 118+ API）

- 端口：Gateway:8080 MJPEG:8081 RTSP:8082 WebRTC:8083 Input:8084
- 安全加固完成：XSS/路径穿越/资源泄漏/PIN全修复
- **E2E四路径 128/128(100%)** — Nginx/FRP/ADB直连/网关 全通
- 损之又损: phone_gateway.py 620→381行(-39%) / input模块Compose剥离 / 构建21s→10s
- frpc localIP: 192.168.31.40→127.0.0.1(ADB forward自适应，不依赖WiFi子网)

### 道生一 DaoOne v2.0（:8880）

- 单文件/零依赖/全设备统一入口，E2E 15/15 PASS
- 12设备 + 15 Hub自动发现 (security:9877/wisdom:9876新入) + Hub API透传

### Python卫星Hub矩阵

| Hub | 端口 | 状态 |
|-----|------|------|
| **无感切号Agent Hub** | **:9870** | **✅ 35/35 E2E (双机部署)** |
| ORS6饮料摇匀器 | :41927 | ✅ |
| 万物中枢 | :8808 | ✅ |
| 双电脑互联 | :8809 | ✅ |
| UI操控 | :8819 | ✅ |
| Agent军火库 | :8840 | ✅ 58/58 E2E |
| 认知系统 | :8850 | ✅ |
| Quest3 Unified | :8863 | ✅ 36/37 E2E |
| Quest3 Ops | :8864 | ✅ |
| 拓竹3D打印 | :8870 | ✅ |
| 亲情远程 | :9860 | ✅ 49/49 E2E |
| 安全中枢 | :9877 | ✅ 凭据API+Dashboard (sentinel/guardian已停用) |
| Windsurf智慧 | :9876 | ✅ 82/82 E2E (v2.0, 26模板) |
| Windsurf深度监控 | :9878 | ✅ 12/12 E2E (v1.0, 七层错误分类学) |
| 虚拟仿真 | :9500 | ✅ 74+ API |
| Windsurf管理 | :9999 | ✅ |
| OpenClaw | :18880 | ✅ |

### Windsurf逆向 + 无限额度工具矩阵

| 工具 | 路径 | 用途 |
|------|------|------|
| windsurf_doctor.py | WindSurf逆向/ | 六层配置诊断+自动修复 |
| windsurf_reverse_hub.py | WindSurf逆向/ | 逆向中枢(状态/模型/问答) |
| credit_toolkit.py | Windsurf无限额度/ | 配额监控/模型成本/SWE委派/Dashboard:19910 |
| patch_continue_bypass.py | Windsurf无限额度/ | maxGen+AutoContinue解锁 |
| patch_rate_limit_bypass.py | Windsurf无限额度/ | UI限流解锁 |
| telemetry_reset.py | Windsurf无限额度/ | 设备指纹重置 |
| _deep_reverse_v9.py | Windsurf无限额度/ | proto+模型+配额提取引擎 |
| DEEP_QUOTA_MECHANISM_v9.md | Windsurf无限额度/ | ★十七章900行终极逆向(107模型/七层计费/死代码) |

### 安全管理体系 v6.0 (阴阳架构)

```
安全管理/
├── security_hub.py      ★ 统一中枢 :9877 (凭据+备份+审计+生态感知+Dashboard)
├── windsurf_monitor.py  ★ 深度监控 :9878 (日志尾随+错误分类+进程探测+Agent API)
├── security_tray.py     ★ 系统托盘 v2.0 (Hub看门狗+开机自启)
├── workspace_guardian.py   工作区守护 (供hub调用)
├── windsurf_wisdom.py     智慧部署器 :9876 (26模板+备份回退)
└── _archive/                旧安全系统归档 (sentinel/immune/guard)
```

| 指标 | 值 |
|------|-----|
| security_hub | ✅ :9877 v6.0 凭据API+生态感知(17 Hub探测)+Dashboard |
| windsurf_monitor | ✅ :9878 12/12 E2E (七层错误分类学+日志尾随+进程探测) |
| windsurf_wisdom | ✅ :9876 82/82 E2E (v2.0, 26模板) |
| security_tray | ✅ v2.0 Hub看门狗+开机自启 |
| workspace_guardian | ✅ 关键文件完整性+根目录白名单 |
| sentinel/immune | ❌ 已归档 (2026-03-20) |

### 规则体系

- 道+器+术三层架构 (Global Rules + workspace.md + skills/workflows)
- 转法轮：观→行→验→省→改→升→涅槃门

## 3) 风险与护栏

- 端口/入口/鉴权策略属于架构级决策：必须先落 ADR 再改代码
- 构建/签名/发布：禁止隐式改动除非任务明确要求
- **全局配置修改铁律**：影响评估 → 备份 → 验证
- **Zone 0冻结**：禁修改 ~/.codeium/windsurf/（hooks.json/mcp_config.json），唯一例外：MCP故障修复
- **安全体系**：hub(:9877)+monitor(:9878)+wisdom(:9876)+tray+guardian活跃，sentinel/immune已归档
