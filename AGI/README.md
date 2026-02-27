# 道 — 智能体系管理中心

> 道生一，一生二，二生三，三生万物。
> 一处观之，一处管之，以至于无感。

## 启动

```powershell
python AGI/dashboard-server.py          # 前台+托盘（推荐）
pythonw AGI/dashboard-server.py         # 后台+托盘（无控制台窗口）
python AGI/dashboard-server.py --no-tray # 纯HTTP（无托盘）
```
→ http://localhost:9090

### 系统托盘
启动后☯太极图标出现在系统托盘区：
- **双击** → 打开浏览器仪表盘
- **右键** → 菜单：观·打开 / 开机自启(勾选切换) / 止·退出
- **关闭控制台** → 托盘仍在，服务不中断
- **崩溃** → 自动重启（最多10次）
- **开机自启** → 勾选后写入Startup目录（pythonw无窗口启动）

## 天 · 人 · 地

```
天 ☰ — 全局级（~/.codeium/windsurf/）
 ├── 天律  全局规则 (88行)
 ├── 五器  MCP (3通/2寂)
 ├── 天钩  全局Hooks (虚无=安)
 ├── 天术  全局Skills (13)
 └── 设    IDE Settings

人 ☴ — 项目级（.windsurf/）
 ├── 律 6  Rules (3常+2感+1机)
 ├── 术 13 Skills (全部有具)
 ├── 法 10 Workflows
 └── 钩 2  Hooks (Python)

地 ☷ — 目录级
 └── 德 18 AGENTS.md
```

## 道家五感

| 感 | 出处 | 实现 |
|----|------|------|
| **观** | 观其妙 《道德经》一 | 水墨色调 + 八卦符号 + 随机名句 |
| **听** | 大音希声 《道德经》四一 | 呼吸脉冲 + 30s静默自观 + 淡入通知 |
| **嗅** | 知常曰明 《道德经》一六 | 风险预警「祸兮福之所倚」 |
| **触** | 无为而无不为 《道德经》四八 | 点击观→编辑→Ctrl+S存 |
| **味** | 冲气以为和 《道德经》四二 | 10项气衡检查 ●实/○虚 |

## 命名

| 道 | 技术 | 意 |
|----|------|---|
| 律 | Rules | 天网恢恢，疏而不失 |
| 术 | Skills | 道生之，德畜之 |
| 法 | Workflows | 道法自然 |
| 德 | AGENTS.md | 上德不德，是以有德 |
| 器 | MCP | 五器辩证 |
| 气 | 健康检查 | 冲气以为和 |
| 常 | always_on | 知常曰明 |
| 感 | glob | 感应而动 |
| 机 | model | 应机而发 |
| 通 | 启用 | 气通则和 |
| 寂 | 禁用 | 寂然不动 |

## 本次成果

### Skills审计修复（13个）
- 4个ADB路径修正（旧→当前项目路径）
- 4个补充YAML frontmatter
- adb-device-debug 47→146行（+WiFi ADB/OEM拦截/多设备）
- browser-agent-mastery R5修正（删除过时内存阈值）
- api-testing增强（+WiFi直连/phone_lib/端口修正）
- feature-development InputSettings路径修正

### 全景管理体系
- `.windsurf/DASHBOARD.md` — 三层架构树文档
- `.windsurf/skills/README.md` — Skills全景索引
- `.windsurfrules` — 准确计数（AGENTS 18, MCP 3通/2寂）

### Web仪表盘
- `AGI/dashboard-server.py` — 道家水墨美学，单文件Python+内嵌HTML
- 后端API: zone0/zone1/zone2/health/risks/file/file-save
- 前端: 自动刷新/Toast通知/风险预警/文件编辑/健康检查

### 数据验证
| 指标 | 值 |
|------|---|
| 气·和 | 10/10 |
| 律 | 6 |
| 术(13/13具) | ✔ |
| 法 | 10 |
| 德 | 18 |
| 天术 | 13+1归档 |
| 器 | 3通/2寂 |

## 文件

| 文件 | 用途 |
|------|------|
| `start.bat` | **一键启动**（双击即用，防重复，自动打开浏览器） |
| `dashboard-server.py` | Web仪表盘(:9090) + 系统托盘 |
| `README.md` | 本文件 |
| `AGENTS.md` | 目录级Agent指令 |
