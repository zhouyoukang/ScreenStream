# AGENT_GUIDE.md — 安全管理统一中枢

## 核心: security_hub.py (:9877)

一个Hub、一个端口、一个Dashboard。凭据+备份+审计+逆向 四合一。

### Agent获取凭据 (非阻塞，推荐)

```python
# Python — 零阻塞, 多Agent并行安全
import urllib.request, json
val = json.loads(urllib.request.urlopen("http://127.0.0.1:9877/api/get?key=DESKTOP_PASSWORD").read())["value"]

# 批量获取
data = json.loads(urllib.request.urlopen("http://127.0.0.1:9877/api/batch?keys=DESKTOP_USER,DESKTOP_PASSWORD").read())
```

```powershell
# PowerShell
(Invoke-RestMethod http://127.0.0.1:9877/api/get?key=DESKTOP_PASSWORD).value
```

### 铁律

1. **禁止** Memory存储实际密码/Token值 (只存键名)
2. **禁止** git tracked文件写入明文凭据
3. **禁止** 终端 `Get-Content secrets.env` (134行会阻塞终端, 用HTTP API)
4. **新增凭据**: secrets.env + 凭据中心.md 同步更新
5. **使用后不缓存**: 从API读取, 用完即弃

### API端点 (30+)

| 端点 | 用途 |
|------|------|
| `/api/get?key=KEY` | 获取单个凭据值 |
| `/api/batch?keys=K1,K2` | 批量获取 |
| `/api/search?q=query` | 搜索凭据键名 |
| `/api/keys` | 列出所有键名 |
| `/api/sections` | 按分区列出 |
| `/api/health` | 综合健康评分(凭据+备份+审计) |
| `/api/status` | Hub状态 |
| `/api/backup` | 六层备份健康详情 |
| `/api/audit` | 安全审计(泄露检测+一致性) |
| `/api/audit/log` | 访问审计日志 |
| `/api/reverse` | 逆向数据库(206+凭据) |
| `/api/reverse/summary` | 逆向摘要 |
| `/api/export/safe` | 脱敏导出 |
| `/api/export` | 完整导出(慎用) |
| `/api/reload` | 热重载secrets.env |
| `/api/immune/health` | 七层全景诊断(评分/等级/26种错误) |
| `/api/immune/taxonomy` | 完整错误分类学(症状/根因/机制/触发/影响/修复) |
| `/api/immune/wheel` | 转法轮(观→行→验→省→改→升) |
| `/api/immune/diagnose?layer=L0` | 单层诊断(L0-L6) |
| `/api/immune/heal` | 执行可自动修复的问题 |
| `/api/immune/history` | 诊断历史 |
| `/api/immune/status` | 免疫系统状态 |

### 备份六层

| 层 | 路径 | 类型 |
|----|------|------|
| E | E:\道\道生一\一生二 | 源 |
| D | D:\道\道生一\一生二 | 实时镜像 |
| F | F:\一生二备份 | 完整备份 |
| N | N:\一生二备份 | 网络镜像 |
| H | H:\一生二关键备份 | USB关键 |
| LAPTOP | 192.168.31.179 | 远程WinRM |

### 启动

```bash
python 安全管理/security_hub.py          # 启动Hub :9877
python 安全管理/_e2e_security_hub.py     # E2E验证 32/32
```

### 智慧部署器 (windsurf_wisdom.py, :9876)

核心智慧一键部署到任何Windsurf工作区。2规则+7技能+2工作流 = 11个泛化模板。

```bash
python 安全管理/windsurf_wisdom.py catalog              # 列出11个可用智慧
python 安全管理/windsurf_wisdom.py scan /path/to/ws     # 扫描目标工作区
python 安全管理/windsurf_wisdom.py diff /path/to/ws     # 差异对比
python 安全管理/windsurf_wisdom.py inject /path/to/ws   # 注入(含自动备份)
python 安全管理/windsurf_wisdom.py inject --overwrite    # 覆盖注入
python 安全管理/windsurf_wisdom.py inject --keys=kernel,protocol  # 选择性注入
python 安全管理/windsurf_wisdom.py rollback              # 回退到注入前
python 安全管理/windsurf_wisdom.py serve                 # HTTP API :9876
```

| 智慧模板 | 类型 | 描述 |
|---------|------|------|
| kernel | 规则 | 执行内核：注意力锚点+执行协议+故障恢复+进化律 |
| protocol | 规则 | 思维协议：感受→解构→转法轮→涅槃门+铁律 |
| error-diagnosis | 技能 | 系统化错误诊断：收集→分类→修复→验证 |
| code-quality | 技能 | 代码分析·审查·重构三合一，八维框架 |
| git-smart-commit | 技能 | 智能Git：分析变更→规范message→提交推送 |
| terminal-recovery | 技能 | 终端卡死诊断：7类模式+五感降级恢复链 |
| search-and-learn | 技能 | 搜索学习：context7+tavily+github多源策略 |
| security-check | 技能 | 安全检查：凭据扫描+代码审计+部署安全 |
| browser-control | 技能 | 浏览器Agent统御：决策树+九律+Token管控 |
| review | 工作流 | 代码审查：9维度深度review |
| 循环 | 工作流 | 转法轮深度循环：观→行→验→省→改→升→涅槃 |

**via security_hub**: `/api/wisdom/catalog`, `/api/wisdom/scan`, `/api/wisdom/diff`, `/api/wisdom/backups`

### 文件清单

| 文件 | 用途 | 状态 |
|------|------|------|
| `security_hub.py` | **统一中枢** :9877 (凭据+备份+审计+免疫+智慧+Dashboard) | ★核心 |
| `windsurf_wisdom.py` | **智慧部署器** :9876 (11模板+泛化+备份回退) E2E 60/60 | ★核心 |
| `windsurf_immune.py` | **七层免疫引擎** :9879 (26种错误+自愈) | ★核心 |
| `_e2e_wisdom.py` | 智慧部署器E2E (60项) | ★验证 |
| `_e2e_security_hub.py` | Hub E2E测试 (32项) | ★验证 |
| `pre_commit_hook.py` | Git pre-commit 防泄露 | ★安全 |
| `_deep_reverse.py` | 全维度逆向引擎 | 工具 |
| `_deep_reverse_db.json` | 逆向数据库 (206+凭据) | 数据 |
