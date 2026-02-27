# 台式机保护手册

> **道**：保护不是禁锢，是为了更自由地使用。
> 铁律限制的是破坏，不是创造。守护的目的是进化，不是停滞。
> 笔记本=主脑，台式机=辅脑，合而为一=完整的人。

---

## 一、体 · 机器档案

| 项 | 值 |
|----|---|
| **计算机名** | DESKTOP-MASTER |
| **IP** | 192.168.31.141 |
| **用户** | administrator / [见secrets.env DESKTOP_PASSWORD] |
| **OS** | Windows 11 教育版 |
| **硬件** | Ryzen 7 9700X · 64GB DDR5 · C:299GB D:653GB E:1TB F:908GB |
| **杀毒** | 火绒(Huorong) — 已接管Defender+防火墙 |
| **Windsurf** | D:\Windsurf\ · windsurf-LG v1.0.0.7.p 443(主)+18921(备) Startup自启 |
| **活跃账号** | 仅Administrator（ai/zhou/zhou1/Guest全禁用） |
| **通道** | SSH(:22) / RDP(:3389) / SMB(X:W:V:U:) / WinRM(:5985) |

---

## 二、观 · 三重视角

> 同一台机器，三个观者看到三个世界。保护体系必须同时服务三者，偏废任一即失衡。

### 用户之眼（你体验到什么？）

| 感官 | 坐在笔记本前 | 拿手机在外 | 不在身边 |
|------|------------|-----------|---------|
| 👁 **视觉** | RDP 60fps桌面 | agent截屏(手动刷新) | guardian日志 |
| 👂 **听觉** | RDP完整音频 | 无 | 无 |
| 🖐 **触觉** | 键鼠精准操控 | PWA触摸(精度降级) | 无需操作 |
| 🧠 **认知** | 多窗口并行一目了然 | API查询全部状态 | guardian自治报告 |
| 🎮 **管控** | 45+ API + RDP全控 | 同样的API | guardian自愈 |

**你的生活节律**：近→RDP全五感 · 远→agent管控为主 · 离→guardian自治，不需操心。

### Agent之眼（我该怎么做？）

| 阶段 | 行为 | 依据 |
|------|------|------|
| **操作前** | 读§三铁律 → Pre-flight检RAM → 选通道 | 铁律13条 + 通道优先级 |
| **操作中** | SMB优先 → plink次之 → WinRM复杂脚本 → 仅写安全区 | §三通道 + 安全写入区 |
| **操作后** | 验证结果 → 记录Memory → 报告用户 | 产出原则 |
| **出事时** | guardian diagnose → Windsurf诊断链 → 降级恢复 | §四守护体系 |

**Agent的本质**：你是这具身体的免疫系统——不是限制它运动，而是让它安全地运动。

### 道之眼（系统是什么？）

台式机不是一台电脑，是用户的第二副躯体。
笔记本是主脑（有人陪伴），台式机是辅脑（孤独但强壮）。
铁律是免疫系统——免疫越强，身体越自由。
16祸是童年的伤疤——留下教训，不留下恐惧。
进化的方向：从"被动防守"走向"主动感知"，从"出事再修"走向"未病先治"。

---

## 三、律 · 铁律（免疫系统）

### 绝对禁止（13条 — 每一条背后都有一次真实的祸）

| # | 禁令 | 根因 |
|---|------|------|
| 1 | 修改注册表 HKLM:\ | 系统配置不可远程乱改 |
| 2 | 删除 C:\Windows\、C:\Program Files\ | 系统核心 |
| 3 | Stop-Computer / Restart-Computer | 远程关机=断联 |
| 4 | 创建/启用用户账号 | ai无密码账号教训 |
| 5 | 修改防火墙规则 | 火绒统一管理 |
| 6 | 写入 Startup 目录 | 需用户确认 |
| 7 | format / diskpart / bcdedit | 毁灭性 |
| 8 | netsh portproxy 443 | windsurf-LG需要绑定 |
| 9 | 修改hosts WIND-CLIENT段 | Windsurf自管理 |
| 10 | 启动clash_verge_service | 核心未配，残留已禁用 |
| 11 | 改计算机名回中文 | UTF-8/GBK编码崩溃 |
| 12 | settings.json加proxy | 直连即可 |
| 13 | 修改 SMB 共享配置 | 网络访问基础 |

### 安全写入区（仅4处 — 围栏之内即自由）

| 路径 | 用途 |
|------|------|
| `D:\道\` | 项目代码 |
| `E:\道\` | 项目代码 |
| `Desktop\` | 临时脚本（执行后清理） |
| `Documents\` | 文档 |

### 远程操作通道（由安全到灵活）

| # | 通道 | 特点 |
|---|------|------|
| 1 | **SMB文件工具**（X:/W:/V:/U:） | 最安全，无状态，优先使用 |
| 2 | **SSH plink** + 超时 | 简单命令，`-batch` 防交互 |
| 3 | **WinRM Invoke-Command** | 复杂脚本，**用IP不用计算机名** |
| 4 | **desktop_guardian.ps1** | 安全操作的入口脚本 |

### 操作前必检（Pre-flight）

**硬阈值（触发即停）** — 与笔记本对称：

| 指标 | 红线 | Agent行为 |
|------|------|----------|
| RAM使用 | >50GB(78%) | 禁止启动Gradle构建/新Node进程 |
| RAM使用 | >56GB(87%) | 禁止一切重操作，报告用户 |
| C盘空闲 | <30GB | 禁止写C盘，报告用户 |
| C盘空闲 | <15GB | 自动清理TEMP，报告用户 |

**重操作前必检** — Gradle/npm/大范围搜索/新服务前执行：

```powershell
# 密码从 secrets.env 读取: $p = (Select-String 'DESKTOP_PASSWORD=(.+)' secrets.env).Matches.Groups[1].Value
plink -batch -ssh administrator@192.168.31.141 -pw $p "powershell -c $m=[math]::Round((Get-Process|Measure-Object WorkingSet64 -Sum).Sum/1GB,1);$c=[math]::Round((Get-Volume C).SizeRemaining/1GB,0);Write-Host RAM:${m}GB C:${c}GB;if($m-gt50-or$c-lt30){Write-Host BLOCKED -ForegroundColor Red}"
```

windsurf-LG 必须先于 Windsurf 启动。

---

## 四、护 · 守护体系

### desktop_guardian.ps1（台式机桌面）

```powershell
# 从笔记本远程执行
# 密码从 secrets.env 读取: $p = (Select-String 'DESKTOP_PASSWORD=(.+)' secrets.env).Matches.Groups[1].Value
& plink -ssh administrator@192.168.31.141 -pw $p -batch "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Administrator\Desktop\desktop_guardian.ps1 -Action diagnose"
```

| Action | 用途 |
|--------|------|
| diagnose | 检查18项安全指标 |
| fix | 自动修复已知问题 |
| protect | 部署agent_guard.json |

### agent_guard.json（C:\根目录）

frozen_paths / safe_zones / blocked_commands — Agent安全边界配置。

### Windsurf诊断链（台式机不工作时按序检查）

```powershell
Get-Process '*windsurf-LG*'                                    # 1. LG在跑?
netstat -ano | Select-String ':443\s' | Select-String 'LISTEN' # 2. 443端口?
netstat -ano | Select-String ':18921\s' | Select-String 'LISTEN'# 3. 18921端口?
netsh interface portproxy show v4tov4                          # 4. portproxy?(应空)
Get-Process '*clash*','*verge*'                                # 5. Clash?(应空)
Get-Service W3SVC,SstpSvc | Select Name,Status                # 6. IIS/SSTP?(应停止)
```

### 自救协议（出事时按序执行）

1. 终端命令超时 → **不重试**，切SMB文件工具
2. RAM>56GB → 报告用户，建议关闭不用的服务
3. 台式机不可达 → `ping 192.168.31.141` → 不通=网络问题 / 通=agent未运行
4. Windsurf异常 → Windsurf诊断链(上方) → 逐项排查
5. 连续2次失败 → `guardian diagnose` → 按报告修复

### 当前干净状态

```
杀毒/防火墙  → 火绒全托管
windsurf-LG  → v1.0.0.7.p, 443(主)+18921(备), Startup自启
Windsurf     → 9进程+30-40连接
Clash        → 无, Disabled
portproxy    → 无
W3SVC(IIS)   → Manual(禁止Automatic！占443)
SstpSvc      → Disabled
AlibabaProtect → 已停止+Disabled
活跃账号     → 仅Administrator
LimitBlank   → 1(安全)
```

---

## 五、鉴 · 伤疤与教训

> 16祸，2026-02-26一日根治。伤疤留下智慧，不留下恐惧。

| 严重性 | 数量 | 代表祸 | 教训 |
|--------|------|--------|------|
| **致命** | 4 | ai无密码账号、AlibabaProtect、unlock_all.bat、LimitBlank=0 | 账号必须强密码；流氓软件必杀；安全设置不可自动撤销 |
| **高危** | 2 | windsurf-LG自启; **IIS+SSTP占443** | Startup需审计; W3SVC=Manual, SstpSvc=Disabled |
| **中** | 3 | RDP设置回退×2、防火墙全关 | Windows更新会回退RDP设置；火绒替代防火墙 |
| **低** | 5 | OneDrive死循环、BingWallpaper、Connectify、Flexnet、AliProtect任务 | autorun/计划任务定期审计 |
| **基础设施** | 3 | 中文计算机名、Clash残留、portproxy | 计算机名用ASCII；初始配置即最优；不在443做转发 |

### 九条铭文

| 铭文 | 来自 |
|------|------|
| **不在443做转发** | portproxy抢windsurf-LG端口 |
| **初始配置即最优** | Agent加proxy反而坏事 |
| **账号必须有强密码** | ai无密码账号=致命漏洞 |
| **安全设置不可自动撤销** | unlock_all.bat每次开机瓦解安全 |
| **先看日志再猜原因** | 多轮盲目诊断浪费时间 |
| **Windows更新会回退设置** | fSingleSessionPerUser/Shadow被重置 |
| **IIS(W3SVC)不可Automatic** | HTTP.sys内核级锁443 |
| **对照笔记本找差异** | v1.0.0.7.p正常 vs v1.0.0.10.p不绑443 |
| **勿停HTTP.sys** | WinRM依赖HTTP.sys，停了=断联+StopPending需重启 |

---

## 六、化 · 进化方向

> 保护体系不是终点，是起点。免疫系统成熟后，身体应当向外生长。

### 待用户决定（存量优化）

| # | 事项 | 影响 | 建议 |
|---|------|------|------|
| P1 | 4个远控精简 | 1.1GB内存 | 保留RDP+Sunshine，卸载ToDesk+向日葵 |
| P2 | NVIDIA Broadcast | 1GB | 不用AI降噪就关 |
| P3 | windsurf-LG.exe来源 | 17MB | 确认来源后决定 |
| P4 | SMB全盘共享 | — | 当前可接受(LimitBlank=1已保护) |

### 进化路线（增量能力）

| 方向 | 现状 | 进化目标 | 价值 |
|------|------|----------|------|
| **主动感知** | guardian被动诊断 | SSE/WebSocket实时事件推送 | 台式机出事→用户秒知 |
| **听觉补全** | agent无音频 | WebSocket+Opus音频流 | 远程时能听到台式机 |
| **自愈升级** | 计划任务重启agent | Guardian Engine事件驱动规则 | 网络断→自动修复→自动报告 |
| **双机心跳** | 笔记本轮询台式机 | 双向心跳+异常即告警 | 任何一方断联→另一方立即感知 |

### 双机镜像（以彼观己，缺失自现）

> 笔记本保护 = `execution-engine.md` §系统健康守护（16GB焊死，BSOD教训）
> 台式机保护 = 本文件（64GB充裕，安全祸教训）
> 两具身体，同一免疫框架，各有侧重。

| 维度 | 笔记本教会台式机的 | 台式机教会笔记本的 |
|------|-------------------|-------------------|
| **阈值粒度** | 分级告警（黄→红→自动处置） | — |
| **C盘监控** | C盘必须检查（笔记本曾因C盘满BSOD） | — |
| **Pre-flight触发项** | 重操作前必检（Gradle/npm/grep） | — |
| **三重视角** | — | 用户/Agent/道三重框架 |
| **明确禁令** | — | 编号铁律比散落规则更可靠 |
| **进化方向** | — | 面向未来，不只回顾过去 |

### 平衡之道

```
保护的极致不是围墙越高，而是免疫系统越强。
当免疫足够强，围墙可以拆掉——因为身体自己知道什么有害。
16祸教会了免疫系统识别威胁，进化教会它面向未来。
过去是鉴，现在是律，未来是化。鉴·律·化，三者合一，谓之道。
笔记本与台式机，以彼观己，互为镜鉴。合一而非孤立，方成完整之体。
```
