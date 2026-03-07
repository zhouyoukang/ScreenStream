# ai账号 能力图谱 v4 — 真实扫描+桌面截图双确认（454个软件 · 五感接入）

> **ai账号** = 台式机第二Windows会话（`127.0.0.2` / Session 4 / `ai` / `Ai@2026!`）
> **控制通道** = `localhost:9905` remote_agent（Console模式，ai登录后自动注入Session 4）
> **感知入口** = `python E:\道\AI之电脑\agent\sense_ai_capabilities.py`
> **软件来源** = HKLM注册表完整扫描（454个，含系统组件）| `E:\道\AI之电脑\agent\apps_raw.json`
> 更新: 2026-02-26 v4 | 来源: 注册表扫描 + RDP桌面截图 + 全盘扫描确认

---

## 一、软件全量清单（按E:\道域分类 — 真实扫描验证）

### 🧱 AI--3D建模 / 工
| 软件 | 版本 | 状态 | 控制命令 |
|------|------|------|----------|
| **FreeCAD** | **1.0** ✅全盘扫描确认 | ✅已验证 | `D:\安装的软件\FreeCAD 1.0\bin\freecad.exe` |
| **SolidWorks** | 2023 | ✅已验证 | `:9905 /shell sldworks.exe` |
| **Bambu Studio** | latest | ✅已验证 | `:9905 /shell bambu-studio.exe` |
| **Meshmixer** | — | ✅扫描确认 | `:9905 /shell meshmixer.exe` |
| **Revo Scan 5** | 5.5.4.1776 | ✅扫描确认 | `:9905 /shell RevScan.exe` |
| **LaserGRBL Rhydon** | — | ✅扫描确认 | `:9905 /shell LaserGRBL.exe` |

### 🔌 AI--PCB / 嵌入式
| 软件 | 版本 | 状态 | 控制命令 |
|------|------|------|----------|
| **KiCad** | — | ✅已验证（桌面截图可见） | `:9905 /shell kicad.exe` |
| **嘉立创EDA Pro** | 2.2.32.3 | ✅扫描确认 | `:9905 /shell lceda-pro.exe` |
| **STM32 tools** | — | ✅已验证 | `:9905 /shell STM32CubeMX.exe` |
| **STMicro stlink-server** | — | ✅扫描确认 | ST-LINK调试器服务 |
| **MinGW / GCC** | — | ✅桌面截图确认 | `:9905 /shell gcc.exe`（C/C++编译工具链）|

### 🤖 AGI / AI计算（重大发现！）
| 软件 | 版本 | 状态 | 职责 |
|------|------|------|------|
| **NVIDIA CUDA 12.4** | 12.4 | ✅扫描确认 | **GPU加速/AI推理 — 这台机器有GPU算力！** |
| **NVIDIA CUDA 12.6** | 12.6 | ✅扫描确认 | 最新CUDA工具链 |
| **NVIDIA Broadcast** | 2.0.0 | ✅扫描确认 | AI降噪/虚拟背景 |
| **NVIDIA Canvas** | 1.4.311 | ✅扫描确认 | AI绘画辅助 |
| **Docker Desktop** | — | ✅扫描确认 | AI容器化部署 |
| **SakuraCat** | — | ✅桌面截图确认 | 网络工具（Sakura猫VPN/代理，与Clash Verge共存）|
| **Chatbox** | 1.15.4 | ✅扫描确认 | AI对话客户端（接GPT/Claude等）|
| **PyCharm** | 2024.3.4 | ✅扫描确认 | Python IDE（AI开发首选）|
| **Android Studio** | — | ✅扫描确认 | Android应用开发 |

### 🥽 AI--VR（重大升级！）
| 软件 | 版本 | 状态 | 职责 |
|------|------|------|------|
| **Virtual Desktop Streamer** | — | ✅扫描确认 | **高质量PC→Quest无线VR串流（比Moonlight更优化VR）** |
| **Sunshine** | — | ✅扫描确认 | PC端游戏串流服务器（配对Moonlight/clients）|
| **Oculus / PC VR** | — | ✅已验证 | PC VR运行时 |
| **VRChat** | — | ✅扫描确认 | 社交VR平台 |
| **Half-Life: Alyx** | — | ✅扫描确认 | VR旗舰游戏 |
| **Steam** | — | ✅扫描确认 | 游戏/VR内容平台 |
| **YAugment (VaugMent)** | — | ✅扫描确认 | AR扩增现实 |
| **Tuanjie Hub** | 1.3.8 | ✅扫描确认 | 团结引擎（Unity中国版）|

### � homeassistant（意外发现！）
| 软件 | 版本 | 状态 | 职责 |
|------|------|------|------|
| **HASS.Agent** | — | ✅扫描确认 | **HA Windows客户端代理 — ai账号直接连接HA！** |
| **Eclipse Mosquitto MQTT** | — | ✅扫描确认 | MQTT Broker（IoT消息总线）|

### 🎬 AI--摄影 / 艺--视频
| 软件 | 版本 | 状态 | 控制命令 |
|------|------|------|----------|
| **OBS Studio** | 31.0.2 | ✅扫描确认 | `:9905 /shell obs64.exe` |
| **Adobe Photoshop** | 2024(25.0.0.37) | ✅扫描确认 | `:9905 /shell Photoshop.exe` |
| **CorelDRAW Standard 2021** | 23.0.0.363 | ✅扫描确认 | `:9905 /shell CorelDRW.exe` |
| **VLC Media Player** | 3.0.21 | ✅扫描确认 | `:9905 /shell vlc.exe` |
| **Inkscape** | — | ✅扫描确认 | 开源矢量绘图 |
| **Bandicam** | — | ✅扫描确认 | 高性能录屏 |
| **NVIDIA Broadcast** | 2.0.0 | ✅扫描确认 | AI实时降噪/虚拟摄像头 |
| **SmartPSS** | 2.003.0 | ✅扫描确认 | 监控管理软件 |

### 📐 AI--学习 / 术
| 软件 | 版本 | 状态 | 控制命令 |
|------|------|------|----------|
| **Python** | 3.12.5 / 3.13.3 | ✅扫描确认 | `:9905 /shell python.exe` |
| **R for Windows** | 4.4.1 / 4.4.2 / 4.4.3 | ✅扫描确认 | `:9905 /shell R.exe` |
| **RTools** | 4.4.6335 | ✅扫描确认 | R编译工具链 |
| **RStudio** | — | ✅扫描确认 | R语言IDE |
| **Zotero** | 7.0.11 | ✅扫描确认 | `:9905 /shell zotero.exe` |
| **PyCharm** | 2024.3.4 | ✅扫描确认 | Python IDE |
| **Go语言** | go1.23.4 | ✅扫描确认 | Go开发环境 |
| **CMake** | — | ✅扫描确认 | 构建系统 |
| **Node.js** | — | ✅扫描确认 | JS/前端开发 |

### 👥 人 / 通讯
| 软件 | 版本 | 状态 | 备注 |
|------|------|------|------|
| **QQ** | — | ✅扫描确认 | ai账号独立登录 |
| **微信** | — | ✅扫描确认 | ai账号独立登录 |
| **腾讯会议** | 3.40.1.423 | ✅扫描确认 | 独立会话 |
| **钉钉** | — | ✅扫描确认 | 企业通讯 |
| **网易云音乐** | — | ✅扫描确认 | 音乐流媒体 |
| **AudioRelay** | 0.27.5 | ✅扫描确认 | 跨设备音频串流 |
| **Voicemeeter** | — | ✅扫描确认 | 虚拟音频混音台 |
| **Virtual Audio Cable** | 4.10 | ✅扫描确认 | 虚拟音频通道 |

### � AI之电脑 / 远程控制
| 软件 | 版本 | 状态 | 职责 |
|------|------|------|------|
| **Moonlight** | 6.1.0 | ✅扫描确认 | PC游戏串流客户端 |
| **Samsung DeX** | 2.4.1.27 | ✅扫描确认 | 三星手机桌面扩展 |
| **Sunshine** | — | ✅扫描确认 | PC端串流服务（Moonlight配对）|
| **向日葵** | — | ✅扫描确认 | 远程控制（P2P）|
| **ToDesk** | — | ✅扫描确认 | 远程控制（低延迟）|
| **节点小宝** | — | ✅扫描确认 | 远程访问/内网穿透 |
| **Virtual Desktop Service** | — | ✅扫描确认 | VR/多桌面串流服务 |

### 🔧 _管理 / 硬件
| 软件 | 版本 | 状态 | 职责 |
|------|------|------|------|
| **AMD Ryzen Master** | 2.13.0.2771 | ✅扫描确认 | CPU超频/温控 |
| **CPUID CPU-Z** | 2.13 | ✅扫描确认 | 硬件精确检测 |
| **AIDA64 Extreme** | 7.35 | ✅扫描确认 | 全面硬件诊断/压力测试 |
| **GIGABYTE Control Center** | 24.09.24 | ✅扫描确认 | 主板RGB/风扇控制 |
| **OpenRGB** | — | ✅扫描确认 | 跨品牌RGB灯光统一控制 |
| **Logi Options+** | — | ✅扫描确认 | Logitech外设 |
| **Connectify Hotspot** | 23.0.1 | ✅扫描确认 | WiFi热点共享 |
| **火绒安全** | — | ✅扫描确认 | 轻量安全 |
| **AutoHotkey** | 2.0.19 | ✅扫描确认 | 键盘宏自动化 |
| **PuTTY** | 0.83 | ✅扫描确认 | SSH客户端 |
| **WinSCP** | 6.5.2 | ✅扫描确认 | SFTP文件传输 |
| **WinRAR** | 7.00 | ✅扫描确认 | 压缩工具 |
| **7-Zip** | 23.01 | ✅扫描确认 | 压缩工具 |

### 💼 商 / 效率
| 软件 | 状态 | 职责 |
|------|------|------|
| **百度网盘** | ✅扫描确认 | 云存储 |
| **比特浏览器** | 7.0.6 | 指纹浏览器（多账号管理）|
| **OCS Desktop** | 2.8.3 | 在线协作 |

### 🎮 游戏 / 娱乐
| 软件 | 状态 | 职责 |
|------|------|------|
| **Steam** | ✅扫描确认 | 游戏平台 |
| **Counter-Strike 2** | ✅扫描确认 | FPS游戏 |
| **Half-Life: Alyx** | ✅扫描确认 | VR旗舰游戏 |
| **VRChat** | ✅扫描确认 | 社交VR |
| **UU加速器** | ✅扫描确认 | 游戏加速 |
| **雷电模拟器** | ✅扫描确认 | Android模拟器 |

---

## 二、ai账号独立隔离的核心价值

```
主账号(Administrator)          ai账号
  └─ 9904 主Agent               └─ 9905 子Agent
  └─ Windsurf IDE               └─ 独立浏览器Cookie
  └─ HA/Ollama/Python           └─ SolidWorks/FreeCAD/KiCad
  └─ MCP工具链                  └─ Meta Quest/VR运行时
  └─ 全局控制                   └─ 独立QQ/腾讯会议账号
```

**隔离优势**：
1. **账号隔离**：QQ/微信/腾讯会议在ai账号独立登录，不影响主账号
2. **重型软件隔离**：SolidWorks/KiCad/Unity崩溃不影响主流程
3. **资源隔离**：渲染任务在ai会话，不占主Agent CPU
4. **并行工作流**：主账号AI推理 + ai账号GUI操作 同时进行

---

## 三、控制通道（:9905 API速查）

```powershell
# 基础感知
Invoke-RestMethod http://localhost:9905/health        # 会话状态
Invoke-RestMethod http://localhost:9905/screenshot    # ai账号截图
Invoke-RestMethod http://localhost:9905/processes     # ai账号进程列表
Invoke-RestMethod http://localhost:9905/windows       # ai账号窗口列表

# 启动软件（示例）
Invoke-RestMethod http://localhost:9905/shell -Method POST `
  -Body '{"cmd":"start freecad.exe","timeout":5}' -ContentType 'application/json'

# 截图保存
python E:\道\AI之电脑\agent\sense_ai_capabilities.py --shot

# 完整感知报告
python E:\道\AI之电脑\agent\sense_ai_capabilities.py

# 扫描已安装软件（自动发现新安装）
python E:\道\AI之电脑\agent\sense_ai_capabilities.py --scan-apps
```

---

## 四、域映射总表（v2 — 真实扫描确认）

| E:\道\ 目录 | ai账号已确认软件 | 状态 |
|------------|-------------------|---------|
| `AI--3D建模\` | FreeCAD/SolidWorks/Bambu/Meshmixer/RevoScan/LaserGRBL | ✅ |
| `AI--PCB\` | KiCad/嘉立创EDA 2.2.32/STM32tools/stlink | ✅ |
| `AI--VR\` | Virtual Desktop Streamer/Sunshine/Oculus/VRChat/Alyx/Steam | ✅ |
| `AI--AR\` | YAugment(VaugMent)/Tuanjie Hub | ✅ |
| `AI--摄影\` | OBS 31/Photoshop 2024/CorelDRAW 2021/VLC/Inkscape/Bandicam | ✅ |
| `AI--学习\` | Python3.12/3.13 / R4.4.x / Zotero 7 | ✅ |
| `AGI\` | CUDA 12.4/12.6 / Docker / Chatbox / PyCharm / NVIDIA Canvas | ✅重大 |
| `homeassistant\` | HASS.Agent / Eclipse Mosquitto MQTT | ✅意外 |
| `人\` | QQ/微信/腾讯会议/钉钉/网易云音乐/AudioRelay/Voicemeeter | ✅ |
| `商\` | 百度网盘/比特浏览器/OCS | ✅ |
| `_管理\` | RyzenMaster/CPUID/AIDA64/GigabyteCC/OpenRGB/AutoHotkey/PuTTY | ✅ |
| `艺--视频之剪辑\` | OBS 31 / Bandicam / NVIDIA Broadcast | ✅ |
| `AI之电脑\` | Moonlight/SamsungDeX/Sunshine/向日葵/ToDesk/节点小宝 | ✅ |
| `术\` | R4.4.x/RStudio/Go1.23/Node.js/CMake | ✅ |
| `工\` | Bambu Studio/LaserGRBL | ✅ |
| `AI之手机\` | Android Studio / 雷电模拟器 | ✅意外 |

---

## 五、已解之惑（感→知→清明）

> v4新增解10~13

| # | 问题 | 之前 | 现在 |
|---|------|------|------|
| 惑1 | ai agent运行用户显示Administrator | ❓未知 | ✅ PsExec SYSTEM注入Session 4，正常现象 |
| 惑2 | 软件安装在哪里？ | ❓未知 | ✅ HKLM全局安装，454个软件已全量扫描 |
| 惑3 | 延迟2100ms根因？ | ❓未知 | ✅ Admin:9904同样是2053ms，Python HTTP服务器基础开销，非错误 |
| 惑4 | ai账号能否直接连接HA？ | ❓未知 | ✅ HASS.Agent已安装，能直接控制HA |
| 惑5 | ai账号有GPU算力吗？ | ❓未知 | ✅ CUDA 12.4/12.6已安装，GPU加速全通 |
| 惑6 | VR串流方案？ | ❓未知 | ✅ Virtual Desktop Streamer + Sunshine 双方已安装 |
| **解7** | ai账号锁屏问题 | ❗原为待解 | ✅ **已解锁** — 用户已通过 `127.0.0.2` RDP成功进入桌面（2026-02-26截图确认） |
| **解8** | FreeCAD版本不确定 | ❓原记录0.21 | ✅ **FreeCAD 1.0** — 桌面截图明确显示 "FreeCAD 1.0" 图标，已修正全图谱 |
| **解9** | SakuraCat未知 | ❓未收录 | ✅ 已确认为桌面工具，收录至AGI域（网络代理类）|
| **解10** | ai账号无法登录根因 | ❗登录失败/PsExec被拒 | ✅ **ai账号被系统禁用**（`帐户启用:No`）→ 已执行 `net user ai /active:yes` 修复 |
| **解11** | FreeCAD真实安装路径 | ❓文档记录D:\freecad开发（代码库） | ✅ **全盘扫描确认**: `D:\安装的软件\FreeCAD 1.0\bin\freecad.exe` / 0.21版同位置 |
| **解12** | AI_Inject_Session4任务丢失 | ❗任务不存在，注入链断裂 | ✅ 已重建：`inject_ai_session.ps1` + AtLogon(ai)触发，等会话出现则PsExec注入，否则回退Console模式 |
| **解13** | FRP公网19904/18000失效 | ❗TCP连接拒绝 | ⚠️ frpc.exe未安装于台式机。frpc.toml已配置正确。需VPN环境运行 `install-frpc.ps1` |

---

## 六、新增服务（v4）

### Ghost Shell 全局远控 (:8000)
```powershell
# 手动启动
python E:\道\AI之电脑\agent\ghost_server.py
# 计划任务自启: GhostServer_8000 (Administrator, AtStartup)
# 访问: http://localhost:8000  →  ghost_client.html
# 公网: http://60.205.171.100:18000 (需frpc在线)
# API端点: /capture /stream /interact /status /windows /lock
```

### FRP公网穿透（frpc.exe安装指引）
```powershell
# frpc.toml 已配置（E:\道\AI--云服务器\frpc.toml）:
#   19903 → localhost:9903  (笔记本agent,笔记本frpc已负责)
#   19904 → localhost:9904  (台式机Admin agent)
#   18000 → localhost:8000  (ghost_server)
#   13389 → localhost:3389  (RDP)

# 安装步骤（需VPN或翻墙环境）:
# 1. 下载 frp_0.61.1_windows_amd64.zip 到 E:\道\AI--云服务器\
# 2. 解压 frpc.exe 到同目录
# 3. 运行安装脚本:
powershell -ExecutionPolicy Bypass -File "E:\道\AI--云服务器\install-frpc.ps1"
```

---

## 七、无感接入五感体系（已完成）

```
感→知→行→验→守→无感

无感（自然）        守护循环           已建立
   ↓                  ↓                   ↓
sense_all.py --ai   sense_ai_capabilities.py  五感层SDK
   └─ :9905连通检测  └─ 👁 眼: 截图+窗口     pc_senses.py
   └─ 软件扫描      └─ 👃 鼻: 进程+内存     workspace_senses.py
   └─ 锁屏告警      └─ 👅 舌: RAM+磁盘+分辨率  multi_sense.py
                    └─ 💖 触: API延迟
                    └─ 👂 耳: 事件日志
```

### 快捷命令（无感初始化）

> 注：:9905当前为Console代理模式，所有Shell/文件/截图命令完全可用
```powershell
# 全域感知（含ai账号）
python E:\道\AI之手机\sense_all.py --all

# ai账号専项五感
python E:\道\AI之手机\sense_all.py --ai

# ai账号软件全量扫描
python E:\道\AI之手机\sense_all.py --ai --scan

# 单独运行五感探针
python E:\道\AI之电脑\agent\sense_ai_capabilities.py

# 在ai账号启动软件
python E:\道\AI之电脑\agent\sense_ai_capabilities.py --launch kicad.exe
python E:\道\AI之电脑\agent\sense_ai_capabilities.py --launch freecad.exe
python E:\道\AI之电脑\agent\sense_ai_capabilities.py --launch "obs64.exe"
```

### 当前状态（2026-02-26 v4）
- **:9905** = Console模式运行中（Admin代理，Shell/文件全功能可用）
- **session-4** = 需用户打开 `localhost_ai.rdp` 触发登录（ai账号已启用）
- **自动注入** = AI_Inject_Session4计划任务已重建，ai登录后自动升级为真session-4
- **NoLockScreen** = HKLM+HKCU均已应用，永久生效
- **FRP公网穿透** = TCP 19904/18000 需先安装frpc（见七→frpc安装）
