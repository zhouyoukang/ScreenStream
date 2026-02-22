# 智能家居控制中心 (SmartHome Gateway)

> **独立项目** — 可由专属 Agent 独立开发，无需触碰 ScreenStream Android 代码。

## 项目边界

| 维度 | 值 |
|------|-----|
| **目录** | `智能家居/` |
| **语言** | Python 3.10+ / FastAPI |
| **端口** | 8900 |
| **入口** | `网关服务/gateway.py` |
| **前端** | `网关服务/dashboard.html` |
| **配置** | `网关服务/config.json` (gitignored) |

## 可修改文件（本项目 Agent 的权限范围）

```
智能家居/
├── 网关服务/
│   ├── gateway.py             ← 主网关 FastAPI (路由+编排)
│   ├── micloud_backend.py     ← 小米云 MIoT RPC
│   ├── ewelink_backend.py     ← 易微联 CoolKit v2
│   ├── ha_backend.py          ← Home Assistant REST
│   ├── mina_backend.py        ← 小米音箱 Mina API
│   ├── tuya_backend.py        ← 涂鸦 Cloud API
│   ├── wechat_handler.py      ← 微信公众号命令路由
│   ├── dashboard.html         ← Web 仪表盘
│   ├── config.example.json    ← 配置模板
│   ├── requirements.txt       ← 依赖
│   ├── verify_platforms.py    ← 平台验证
│   ├── test_wechat.py         ← 离线测试
│   ├── test_wx_live.py        ← 在线测试
│   ├── test_wx_commands.py    ← 命令覆盖测试
│   ├── start.bat / start_wechat.bat
│   └── ...新增文件自由创建
├── NEEDS_ANALYSIS.md          ← 需求分析
└── README.md                  ← 项目文档
```

## 禁止修改（属于其他项目）

- `反向控制/输入路由/InputRoutes.kt` — ScreenStream 路由（需协调）
- `投屏链路/MJPEG投屏/assets/index.html` — ScreenStream 前端
- `手机操控库/` `远程桌面/` 下任何文件
- `.windsurf/rules/` `.windsurf/skills/`

## 与其他项目的集成点

| 集成 | 方向 | 文件 | 说明 |
|------|------|------|------|
| ScreenStream 路由 | SS→本项目 | `InputRoutes.kt` `/smarthome/*` | SS 前端通过这些路由代理到 :8900 |
| ScreenStream 前端 | SS→本项目 | `index.html` Alt+Shift+H 面板 | 面板代码在 SS 前端中 |
| ADB reverse | 运维 | `adb reverse tcp:8900 tcp:8900` | 手机端访问 PC 网关 |

> **跨项目修改协议**：如需修改 InputRoutes.kt 或 index.html 中的 SmartHome 相关代码，
> 必须在根目录 `AGENTS.md` 的「跨项目变更日志」中记录，通知 ScreenStream Agent。

## 独立开发流程

```powershell
# 1. 启动（无需编译 Android）
cd 智能家居/网关服务
pip install -r requirements.txt
python gateway.py

# 2. 验证
curl http://127.0.0.1:8900/
curl http://127.0.0.1:8900/devices
python verify_platforms.py

# 3. 测试
python test_wechat.py          # 离线 11 项
python test_wx_live.py         # 在线 8 项
python test_wx_commands.py     # 全品类 20 项

# 4. 微信公网测试
start_wechat.bat               # Gateway + Cloudflare Tunnel
```

## 共享资源

| 资源 | 冲突风险 | 协调方式 |
|------|---------|---------|
| 端口 8900 | 低（独占） | 本项目专用 |
| MiCloud 凭据 | 无 | config.json 本地 |
| ADB reverse | 中 | 与 ScreenStream Agent 共享设备时需协调 |

## 架构要点

- **后端模块化**：gateway.py 只做路由编排，每个平台一个 `*_backend.py`
- **凭据三级链**：L1 config直填 → L2 自缓存 → L3 HA回退
- **音箱核心洞察**：一台在线音箱 > 十个平台API（语音代理路径最强）
- **微信入口**：POST /wx 接收消息 → WeChatCommandRouter 解析 → 设备控制/场景/TTS

## 对话结束选项

> 任务完成后，AI 必须调用 `ask_user_question` 从以下选项中选取 4 个最相关的：

| label | description |
|-------|-------------|
| 启动网关验证 | python gateway.py + curl验证API端点正常 |
| 运行测试套件 | 执行test_wechat/test_wx_live/test_wx_commands全套测试 |
| 继续开发功能 | 继续完善网关路由/平台后端/微信命令 |
| 更新仪表盘 | 改进dashboard.html的设备卡片/场景/TTS交互 |
| 更新文档提交 | 更新README/NEEDS_ANALYSIS + git commit |
| 微信公网测试 | 启动Cloudflare Tunnel进行端到端公网验证 |
