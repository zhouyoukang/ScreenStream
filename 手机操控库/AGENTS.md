# 手机操控库 (PhoneLib)

> **独立项目** — 可由专属 Agent 独立开发，是 ScreenStream HTTP API 的 Python 客户端封装。

## 项目边界

| 维度 | 值 |
|------|-----|
| **目录** | `手机操控库/` |
| **语言** | Python 3.8+ (零外部依赖) |
| **端口** | 无（纯客户端库） |
| **入口** | `phone_lib.py` → `Phone` 类 |

## 可修改文件

```
手机操控库/
├── phone_lib.py           ← 核心库：Phone 类 (零依赖，纯 urllib)
│                             支持远程连接/自动发现/心跳/负面状态恢复
├── remote_setup.py        ← 远程操控一键启动（发现→连接→五感→Web UI）
├── remote_assist.py       ← 远程家庭协助工具（交互式CLI+18个命令+8场景）
├── five_senses.py         ← 五感批量采集（多APP UI/a11y/activity dump）
├── parse_orders.py        ← 订单解析（淘宝/京东/当当 结构化提取）
├── shopping_records.py    ← 购物记录汇总采集
├── scan_book_orders.py    ← 二手书订单扫描
├── collect_v3.py          ← UI采集 v3（深度滚动+增量）
├── family_setup_guide.md  ← 家人端设置指南（发给家人的5分钟教程）
├── family_phones.json     ← 家人手机配置（自动生成，--add 管理）
├── FINDINGS.md            ← 实测发现 P1-P29 + 远程架构发现
├── README.md              ← 项目文档
├── .gitignore             ← 排除 xml/txt dump + 五感采集临时文件
└── tests/
    ├── standalone_test.py ← 36 项 L0/L1 原始 HTTP 验证
    ├── agent_demo.py      ← 5 个多步 Agent 任务
    ├── complex_scenarios.py ← 5 场景 43 步联动
    └── remote_test.py     ← 远程五感端到端验证（8节）
```

## 禁止修改

- `反向控制/` — ScreenStream 后端（API 提供方）
- `投屏链路/` — ScreenStream 前端
- `智能家居/` — SmartHome 项目
- `远程桌面/` — RemoteDesktop 项目

## 与其他项目的集成点

| 集成 | 方向 | 说明 |
|------|------|------|
| ScreenStream API | 本项目→SS | Phone 类封装 SS 的 70+ HTTP API |
| ADB forward | 运维 | `adb forward tcp:8086 tcp:8086` 建立 PC→手机通道 |
| agent-phone-control | Skill | `.windsurf/skills/agent-phone-control/` 使用本库 |

> **API 变更协议**：ScreenStream Agent 修改 InputRoutes.kt 增删 API 时，
> 应在根目录 `AGENTS.md` 的「跨项目变更日志」中记录，PhoneLib Agent 据此同步更新 Phone 类。

## 独立开发流程

```powershell
# 前置：ScreenStream 必须已部署到手机并运行
adb devices                                    # 确认设备连接
adb forward tcp:8084 tcp:8084                  # 端口转发
curl -s http://127.0.0.1:8084/status           # 确认 API 可达

# 开发
python -c "from phone_lib import Phone; p=Phone(port=8084, auto_discover=False); print(p.status())"

# 测试
python tests/standalone_test.py --port 8084    # 36 项
python tests/agent_demo.py --port 8084         # 5 项
python tests/complex_scenarios.py --port 8084  # 5 场景
```

## 共享资源

| 资源 | 冲突风险 | 协调方式 |
|------|---------|---------|
| ScreenStream API | 高 | 测试时会占用手机前台，与 SS Agent 部署冲突 |
| ADB 设备 | 高 | 与 SS Agent 共享，测试时需协调 |
| 端口 8084 | 低 | 可用 --port 参数切换 |

## 架构要点

- **零依赖**：纯 `urllib` + `json`，不引入 requests/httpx
- **远程弹性**：USB/WiFi/Tailscale/公网穿透四层连接，自动发现+心跳+重试+负面状态恢复
- **纯HTTP模式**：所有功能（含APP启动/搜索）均有HTTP替代，无ADB亦可全功能操控
- **五感架构**：vision/hearing/touch/smell/taste，`p.senses()` 一次采集
- **负面状态矩阵**：7种故障自动检测+恢复，支持多故障叠加按优先级链处理
- **四层金字塔**：L0 原子 API(70%) → L1 组合(20%) → L2 LLM(8%) → L3 Agent(2%)
- **findByText 同时搜索 text + contentDescription**，100% 成功率

## 对话结束选项

> 任务完成后调用 `ask_user_question`，从下表选 4 个最贴合的：

| label | description |
|-------|-------------|
| 跑测试看结果 | 执行36项+5场景测试验证效果 |
| 扩展操控能力 | 添加新API封装或优化现有方法 |
| 同步上游变更 | 跟进后端新增API的封装 |
| 跑复杂场景 | 5场景43步联动验证 |
| 收工提交 | 记录成果 + git commit |
