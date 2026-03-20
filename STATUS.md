# 一生二 · 状态面板（STATUS）

> 道生一，一生二，二生三，三生万物。
> 最后更新：2026-03-20（**无感切号 v5.5.0** 82E2E+导入+O(n²)修复 | wisdom v1.1 16模板+72E2E | security v3.3+credit）

## 0) 权威入口

| 文件 | 用途 |
|------|------|
| `AGENT_GUIDE.md` | DaoOne v2.0 操作指令（根级） |
| `.windsurf/DASHBOARD.md` | 道法术器四层架构全景 |
| `核心架构.md` → `05-文档_docs/FEATURES.md` | SS核心文档链 |
| `.windsurf/rules/` | 2个Always-On规则（kernel.md + protocol.md） |
| `.windsurf/skills/` | 32个项目技能 |
| `凭据中心.md` + `secrets.env` | 凭据索引+实际值 |

## 1) 全景统计

| 维度 | 数量 |
|------|------|
| 根目录 | 70个真实目录 + 1个Junction |
| AGENT_GUIDE.md | 60+个（随项目增长） |
| Gradle模块 | 6个（app/common/mjpeg/rtsp/webrtc/input） |
| Python Hub服务 | 16个（道生一:8880 + 15卫星Hub） |
| Rules | 2 Always-On（kernel.md + protocol.md） |
| Skills | 32个 |
| Workflows | 13个 |
| Memory | 道法术三层自足，按需AGENT_GUIDE |
| MCP Server | 6个（context7/github/gitee/playwright/tavily/chrome-devtools） |
| 设备舰队 | 15台（3手机+2电脑+VR+AR+手表+3D打印机+IoT） |

## 2) 核心成果

### ScreenStream核心（6模块 118+ API）

- 端口：Gateway:8080 MJPEG:8081 RTSP:8082 WebRTC:8083 Input:8084
- 安全加固完成：XSS/路径穿越/资源泄漏/PIN全修复

### 道生一 DaoOne v2.0（:8880）

- 单文件/零依赖/全设备统一入口，E2E 15/15 PASS
- 12设备 + 15 Hub自动发现 (security:9877/wisdom:9876新入) + Hub API透传

### Python卫星Hub矩阵

| Hub | 端口 | 状态 |
|-----|------|------|
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
| 安全中枢 | :9877 | ✅ 37/37 E2E (v3.3+credit+免疫) |
| Windsurf智慧 | :9876 | ✅ 72/72 E2E (v1.1, 16模板) |
| 虚拟仿真 | :9500 | ✅ 74+ API |
| Windsurf管理 | :9999 | ✅ |
| OpenClaw | :18880 | ✅ |

### 规则体系 v17.2

- 道法两层全Always-On（长对话不衰退）
- 本能层9条 + 铁律6条 + 反模式5个
- 转法轮：观→行→验→省→改→升→涅槃门

## 3) 2026-03-18 清理

| 操作 | 详情 |
|------|------|
| 残余文件归档 | 5文件+3压缩包→管理/_root_cleanup_20260318 |
| 空目录删除 | vp99_mtp_extract, vp99_reverse_extracted, .kotlin, .playwright |
| 冗余Junction删除 | 构建部署, 用户界面, 配置管理（内部自指） |
| vp99_payload归档 | 2文件→管理/_root_cleanup_20260318 |

## 4) 风险与护栏

- 端口/入口/鉴权策略属于架构级决策：必须先落 ADR 再改代码
- 构建/签名/发布：禁止隐式改动除非任务明确要求
- **全局配置修改铁律**：影响评估 → 备份 → 验证
- **Zone 0冻结**：禁修改 ~/.codeium/windsurf/（hooks.json/mcp_config.json），唯一例外：MCP故障修复
