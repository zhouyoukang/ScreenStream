# 安全管理统一中枢

> 反者道之动，弱者道之用。一个Hub、一个端口、一个Dashboard。

## 架构

```
安全管理/
├── security_hub.py      ★ 统一中枢 :9877 (30+ API, 8-Tab Dashboard)
├── windsurf_immune.py   ★ 免疫系统 (7层26种错误分类+诊断+自愈+转法轮)
├── security_tray.py     ★ 系统托盘监控器 (7种通知)
├── _e2e_security_hub.py ★ E2E测试 (32/32 PASS)
├── pre_commit_hook.py   ★ Git pre-commit hook (已安装)
├── _AGENT_GUIDE.md      ★ Agent操作指南
├── _deep_reverse.py       全维度逆向引擎
├── pc_login_helper.py     PC登录辅助
└── _archive/              8个已归档legacy文件

secrets.env   (项目根)  ← 唯一真相源 (gitignored, 134键)
凭据中心.md   (项目根)  ← 结构索引 (git tracked)
```

## 免疫系统 (windsurf_immune.py)

> 从一周开发历程中提炼所有错误的底层原理逆向分析，构建七层诊断+自愈引擎。

### 七层错误模型

| 层 | 卦 | 名称 | 错误数 | 代表性错误 |
|----|-----|------|--------|-----------|
| L0 | ☷坤 | 文件系统污染 | 4 | UTF-8 binary污染(5800+/session), GBK mojibake路径, 大文件溢出 |
| L1 | ☲离 | Language Server | 4 | gRPC INVALID_ARGUMENT, fireSupercompleteV2, implicit cache膨胀 |
| L2 | ☳震 | 认证层 | 3 | Token类型错误(idToken vs authToken), Chunked编码, Relay封锁 |
| L3 | ☴巽 | 限流层 | 3 | Rate Limit(per-account频率), Quota耗尽, 容量限制 |
| L4 | ☵坎 | 网络层 | 4 | 代理端口错配(7890/7897), CFW TLS不兼容, FRP断连 |
| L5 | ☶艮 | MCP层 | 4 | MCP密钥不同步, CMD路径错误(D:→E:), 黄点/离线 |
| L6 | ☱兑 | 系统层 | 4 | 完整性校验失败(热补丁28KB), CMD弹窗, Session 0隔离 |

### 免疫系统API (通过security_hub :9877集成)

| 端点 | 用途 |
|------|------|
| `/api/immune/health` | 七层全景诊断(评分/等级) |
| `/api/immune/taxonomy` | 完整错误分类学(26种错误的症状/根因/机制/触发/影响/修复) |
| `/api/immune/wheel` | 转法轮(观→行→验→省→改→升) |
| `/api/immune/diagnose?layer=L0` | 单层诊断 |
| `/api/immune/heal` | 执行可自动修复的问题 |
| `/api/immune/history` | 诊断历史 |
| `/api/immune/status` | 免疫系统状态 |

## 健康状态 (2026-03-20)

| 指标 | 值 |
|------|-----|
| 安全评分 | **100/100 (S)** |
| 免疫评分 | **73/100 (B)** — 七层诊断 |
| 凭据总数 | 134键 (24分区) |
| 备份健康 | 100% (6/6层同步) |
| 审计问题 | 0 critical, 0 warning, 2 info |
| E2E | security_hub **32/32 PASS** + wisdom 60/60 |
| 持久化 | schtask Password LogonType (Session 0, 零弹窗) |

## 备份六层

| 层 | 卦 | 状态 | secrets同步 |
|----|----|------|------------|
| E: 主工作区 | ☰乾 | ✅ 在线 | ✅ 同步 |
| D: 实时镜像 | ☷坤 | ✅ 在线 | ✅ 同步 |
| F: 完整备份 | ☲离 | ✅ 在线 | ✅ 同步 |
| N: 网络镜像 | ☳震 | ⚠ 离线 | — |
| H: USB备份 | ☴巽 | ✅ 在线 | ✅ 同步 |
| 笔记本 | ☵坎 | ✅ WinRM | ✅ 已同步 |

## 铁律

1. **R1**: Memory禁止存储实际密码/Token值
2. **R2**: git tracked文件禁止明文凭据
3. **R3**: 新增凭据必须同时更新 secrets.env + 凭据中心.md
4. **R4**: 修改凭据只改 secrets.env 一处
5. **R5**: Agent用HTTP API读凭据，不用Get-Content (会阻塞终端)

## Agent凭据获取

```python
# 推荐: HTTP API (非阻塞, 多Agent并行安全)
import urllib.request, json
val = json.loads(urllib.request.urlopen("http://127.0.0.1:9877/api/get?key=KEY").read())["value"]
```

```powershell
# PowerShell
(Invoke-RestMethod http://127.0.0.1:9877/api/get?key=KEY).value
```

## 安全防护

| 防护层 | 机制 | 状态 |
|--------|------|------|
| Git防泄露 | pre-commit hook (熵检测+正则+凭据值匹配) | ✅ 已安装 |
| .gitignore | secrets.env + backups排除 | ✅ |
| 审计 | quick_audit() 实时检测 | ✅ |
| 文件监控 | 5s轮询auto-reload + toast/Web通知 | ✅ |
| 备份 | 六层SHA256指纹校验 | ✅ |
| 笔记本同步 | WinRM自动同步 | ✅ |

## 启动

```bash
python 安全管理/security_hub.py      # Hub :9877 (schtask自动启动)
pythonw 安全管理/security_tray.py    # 系统托盘 (Startup自动启动)
# Dashboard: http://127.0.0.1:9877/
```

## 系统托盘 (security_tray.py)

- **图标**: 右下角圆形评分等级图标 (S绿/A蓝/B黄/C红/离线灰)
- **Tooltip**: 评分/凭据/备份/审计 实时状态
- **右键菜单**: 打开Dashboard | 当前状态 | 备份检查 | 重载凭据 | 启动Hub | 退出
- **轮询**: 每30秒查询Hub API
- **通知触发**: Hub离线/恢复 | 凭据变更 | 评分下降 | 备份异常 | 审计严重 | MCP减少/恢复
- **持久化**: Startup快捷方式 → VBS静默包装 → pythonw

## Dashboard功能

- **总览**: 评分/凭据/备份/审计/逆向 一览
- **凭据**: 24分区索引 + 每键一键复制 + 搜索
- **备份**: 六层详情 + 磁盘用量 + 指纹校验
- **审计**: 安全检查 + 问题详情
- **日志**: 访问审计日志
- **Windsurf**: MCP服务器状态 + Rules/Skills/Workflows/Hooks全景
- **统计**: 热门凭据Top20 + Agent活跃度 + 从未使用凭据
- **快捷键**: 1-7切Tab, R刷新
- **自动重连**: 断线后指数退避重试(3s→60s)
- **Web通知**: 凭据变更/评分下降浏览器推送

## Legacy文件 (已归档到 _archive/)

password_hub.py | backup_engine.py | sync_check.py | _verify.py
secrets_manager.py | audit.py | service_hub.py | phone_hub.py

---

*统一中枢 v3.0: 2026-03-20 | E2E: 32/32 | 健康: 100/S | Dashboard: 8-Tab*
