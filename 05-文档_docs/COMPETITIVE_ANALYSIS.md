# ScreenStream 竞品对标 + 能力缺口 + 多软件联动方案

> 生成：2026-02-21 | 基于：24轮全网搜索 + 项目能力矩阵 + 国内用户场景分析

---

## 一、核心定位

**ScreenStream 独特价值**：唯一同时具备「开源免费 + 纯Web界面 + 118+ API + AI Brain + 宏系统」的手机远程控制方案。

| 维度 | ScreenStream | 竞品最强者 |
|------|-------------|-----------|
| 开源免费 | ✅ MIT | scrcpy (Apache) |
| 不限品牌 | ✅ 所有Android | Phone Link (限三星) |
| 纯Web界面 | ✅ 浏览器即可 | AirDroid (需客户端) |
| API数量 | 118+ | scrcpy: 0 / AirDroid: ~15 |
| AI能力 | ✅ View树/语义点击/NLP | 无竞品有AI |
| 宏系统 | ✅ 远程可编程 | Tasker有但不能远程 |
| 文件管理 | ✅ 12个API | AirDroid有 |
| 功能密度 | 150+ | scrcpy ~50 / AirDroid ~30 |

---

## 二、国内同类软件生态全景

### A. 远程控制类

| 软件 | 定位 | 优势 | 劣势 | 与ScreenStream关系 |
|------|------|------|------|-------------------|
| **scrcpy** | 开源投屏+控制 | 低延迟、ADB直连、录制 | 无API、无AI、无Web界面 | **互补**：scrcpy做高性能投屏，SS做智能控制 |
| **向日葵** | 国内远控第一 | P2P跨网、企业级、品牌信任 | 收费、限速、广告 | **对标**：SS用开源+免费抢占 |
| **ToDesk** | 国内远控新锐 | 流畅、易用、免费额度大 | 安卓控安卓体验一般 | **对标**：SS功能更强 |
| **AirDroid** | 国际安卓管理 | 多功能(SMS/通话/文件) | 免费版限制多 | **学习**：SS缺SMS/通话 |
| **Total Control** | 企业群控 | 多设备同屏、批量操作 | 收费、需USB | **学习**：SS缺多设备 |
| **Vysor** | Chrome投屏 | 简单、跨平台 | 免费版低画质 | **替代**：SS完全替代 |

### B. 自动化类

| 软件 | 定位 | 优势 | 劣势 | 与ScreenStream关系 |
|------|------|------|------|-------------------|
| **Tasker** | 安卓自动化王者 | 事件触发、变量、插件生态 | 学习曲线陡、不能远程 | **联动**：Tasker触发→调SS API |
| **Auto.js** | JS脚本自动化 | 开源、JS语法、选择器强 | 停更、无远程 | **替代**：SS的AI Brain+宏更强 |
| **Hamibot** | 云端自动化 | 云管理、脚本市场 | 收费、依赖云 | **学习**：SS可加脚本市场 |
| **触动精灵** | 商业自动化 | 成熟、企业用 | 收费、需root | **替代**：SS免费+免root |
| **MacroDroid** | 轻量自动化 | 可视化、易用 | 功能少 | **替代**：SS宏系统更强 |

### C. 开发测试类

| 软件 | 定位 | 与ScreenStream关系 |
|------|------|-------------------|
| **Appium** | 自动化测试框架 | SS的API可作为Appium的轻量替代 |
| **uiautomator2** | Python自动化 | SS的phone_lib.py类似定位 |
| **weditor** | UI Inspector | SS的/viewtree API可替代 |
| **adb** | 底层工具 | SS封装了adb无法做到的操作(AccessibilityService) |

---

## 三、核心能力缺口（按ROI排序）

### 🔴 P0 — 高价值缺口（阻碍用户选择SS的关键原因）

| # | 缺口 | 竞品参考 | 影响 | 实现难度 |
|---|------|---------|------|---------|
| 1 | **跨网P2P连接** | 向日葵/ToDesk | 目前仅局域网或需手动端口转发 | 🔴高(需STUN/TURN) |
| 2 | **多设备管理** | Total Control/AirDroid | 只能控一台设备 | 🟡中(前端多标签) |
| 3 | **通知回复** | AirDroid/KDE Connect | 只能读通知，不能操作 | 🟡中(RemoteInput API) |

### 🟡 P1 — 中价值缺口（提升竞争力）

| # | 缺口 | 竞品参考 | 影响 | 实现难度 |
|---|------|---------|------|---------|
| 4 | **短信收发** | AirDroid | 无法远程收发短信 | 🟡中 |
| 5 | **远程摄像头** | AirDroid/Alfred Camera | 无法访问摄像头 | 🟡中 |
| 6 | **通话管理** | AirDroid | 无法远程拨号/接听 | 🟡中 |
| 7 | **事件驱动触发器** | Tasker/MacroDroid | 宏只能手动/定时 | 🟡中 |
| 8 | **双向剪贴板实时同步** | scrcpy/KDE Connect | 当前需手动获取 | 🟢低 |

### 🟢 P2 — 快速增强（可立即实施）

| # | 缺口 | 说明 | 实现难度 |
|---|------|------|---------|
| 9 | **国内APP快速操作预设** | 微信/支付宝/抖音/淘宝一键操作 | 🟢低(前端) |
| 10 | **多软件联动接口** | 与Tasker/n8n/Auto.js联动的标准化接口 | 🟢低(文档+示例) |
| 11 | **中文输入法增强** | 搜狗/百度输入法兼容优化 | 🟢低 |
| 12 | **ADB命令Web代理** | 通过API执行shell命令 | 🟢低(已有Intent API) |

---

## 四、多软件联动方案

### 4.1 与 scrcpy 联动（互补模式）

```
scrcpy（低延迟投屏+录制）  +  ScreenStream（智能控制+自动化）
         ↓                              ↓
    USB直连高性能画面              HTTP API远程控制+AI
```

**使用场景**：开发者用scrcpy看高清画面，同时用SS的API做自动化测试

**联动方法**：
```bash
# 终端1：scrcpy高性能投屏
scrcpy --max-size=1920 --bit-rate=8M

# 终端2：ScreenStream API自动化
curl http://127.0.0.1:8086/findclick -d '{"text":"登录"}'
curl http://127.0.0.1:8086/screen/text
```

### 4.2 与 Tasker 联动（事件触发模式）

```
Tasker（事件检测）  →  HTTP Request  →  ScreenStream API（执行动作）
  ↑                                           ↓
  └──── ScreenStream /notifications/read ←────┘
```

**Tasker Profile 示例**：
```
Profile: 收到微信消息自动截屏
  Trigger: Notification(app=com.tencent.mm)
  Action: HTTP Request
    URL: http://localhost:8086/screenshot
    Method: POST
```

### 4.3 与 n8n 联动（工作流自动化）

```
n8n Workflow:
  Trigger(定时/Webhook) → ScreenStream API → 数据处理 → 通知/存储
```

**示例工作流**：
- 每小时检查手机电量 → 低于20%发邮件提醒
- 监控特定APP通知 → 转发到Telegram
- 定时截屏 → OCR提取数据 → 写入Excel

### 4.4 与 Python/Auto.js 联动（脚本自动化）

```python
# phone_lib.py 已封装所有API
from phone_lib import PhoneAPI

phone = PhoneAPI("http://127.0.0.1:8086")

# 微信自动化示例
phone.open_app("com.tencent.mm")
phone.wait_for("微信", timeout=5)
phone.find_click("搜索")
phone.type_text("张三")
phone.find_click("张三")
phone.type_text("你好，这是自动发送的消息")
phone.find_click("发送")
```

### 4.5 与智能家居联动（场景自动化）

```
ScreenStream API  ←→  Home Assistant  ←→  米家/涂鸦设备
     ↓                      ↓                    ↓
  手机操控面板          自动化规则            灯/开关/传感器
```

---

## 五、国内核心场景自动化预设

### 场景1：微信自动化
| 操作 | API调用链 |
|------|----------|
| 打开微信 | `/intent {action:"android.intent.action.MAIN", package:"com.tencent.mm"}` |
| 扫一扫 | 打开微信 → `/findclick {text:"发现"}` → `/findclick {text:"扫一扫"}` |
| 发消息给X | 打开微信 → `/findclick {text:"搜索"}` → `/text {text:"X"}` → `/findclick {text:"X"}` |
| 发朋友圈 | 打开微信 → `/findclick {text:"发现"}` → `/findclick {text:"朋友圈"}` |

### 场景2：支付宝自动化
| 操作 | API调用链 |
|------|----------|
| 打开支付宝 | `/intent {package:"com.eg.android.AlipayGphone"}` |
| 付款码 | 打开支付宝 → `/findclick {text:"付钱"}` |
| 扫一扫 | 打开支付宝 → `/findclick {text:"扫一扫"}` |
| 蚂蚁森林 | 打开支付宝 → `/findclick {text:"蚂蚁森林"}` |

### 场景3：抖音自动化
| 操作 | API调用链 |
|------|----------|
| 打开抖音 | `/intent {package:"com.ss.android.ugc.aweme"}` |
| 刷视频 | `/scroll {direction:"up"}` (循环) |
| 点赞 | `/doubletap {nx:0.5, ny:0.5}` |
| 搜索 | `/findclick {text:"搜索"}` → `/text {text:"关键词"}` |

### 场景4：办公自动化
| 操作 | API调用链 |
|------|----------|
| 打开钉钉 | `/intent {package:"com.alibaba.android.rimet"}` |
| 钉钉打卡 | 打开钉钉 → `/findclick {text:"工作台"}` → `/findclick {text:"考勤打卡"}` |
| 打开企业微信 | `/intent {package:"com.tencent.wework"}` |

---

## 六、实施路线图

### Phase 1：快速增强（1-2天，前端+文档）
- [ ] 国内APP快捷操作面板（index.html Alt+4扩展）
- [ ] 多软件联动使用指南
- [ ] phone_lib.py 添加国内APP自动化示例
- [ ] 中文输入法兼容测试+修复

### Phase 2：核心API增强（3-5天，后端）
- [ ] 通知回复API（RemoteInput）
- [ ] 双向剪贴板WebSocket实时同步
- [ ] 事件驱动宏触发器（通知/应用切换/定时）

### Phase 3：多设备管理（1-2周）
- [ ] 前端多设备标签页
- [ ] 设备发现（mDNS/广播）
- [ ] 批量命令分发

### Phase 4：跨网连接（2-4周，需基础设施）
- [ ] WebRTC P2P信令服务
- [ ] STUN/TURN中继
- [ ] 无人值守模式

---

## 七、ScreenStream在生态中的终极定位

```
┌─────────────────────────────────────────────┐
│              ScreenStream 生态定位             │
├─────────────────────────────────────────────┤
│                                             │
│   [投屏层]  scrcpy ← 高性能互补 → SS投屏      │
│   [控制层]  SS 118+ API = 最强开源控制层        │
│   [智能层]  SS AI Brain = 唯一带AI的投屏工具   │
│   [自动化]  Tasker/n8n ← 事件触发 → SS宏引擎   │
│   [企业级]  SS多设备 → Total Control替代       │
│   [远程层]  SS P2P → 向日葵/ToDesk开源替代     │
│                                             │
│   最终形态：开源版 AirDroid + AI Brain        │
│   = 手机的 "操作系统级远程接口"                │
│                                             │
└─────────────────────────────────────────────┘
```

**核心判断**：ScreenStream不应只做投屏，应成为**手机的通用远程控制平台**——任何人/AI/脚本/工作流都能通过HTTP API完整操控Android设备。
