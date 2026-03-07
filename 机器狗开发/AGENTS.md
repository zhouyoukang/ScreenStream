# AGENTS.md — 机器狗开发

## 项目概述

宇树Go1四足机器人控制项目。支持两种通信路径：
1. **网络控制** — 通过WiFi/以太网连接Go1主控，MQTT/SSH控制高层运动
2. **RS485直控** — 绕过主控直接驱动电机，低层力矩/位置/速度控制

## 技术栈

- **语言**: Python 3.9+
- **网络通信**: MQTT (paho-mqtt) + SSH + UDP摄像头流
- **RS485通信**: 5Mbps (pyserial), 自定义32字节数据包 + CRC32校验
- **视觉**: OpenCV (摄像头流接收)
- **仿真**: MuJoCo 3.5.0 (Go1官方模型, DeepMind mujoco_menagerie)
- **硬件**: Go1机器人 + USB-RS485适配器(U2D2/CH343)

## 关键文件

| 文件 | 用途 | 修改风险 |
|------|------|---------|
| `gooddawg/build_a_packet.py` | 核心协议库 | 🔴高 — CRC/校准常量不可随意改 |
| `gooddawg/example_cartesian_arm.py` | IK控制示例 | 🟡中 — 含硬件相关增益参数 |
| `gooddawg/calibration/` | 角度标定 | 🔴高 — 标定数据设备相关 |
| `电机测试/` | 调试脚本集 | 🟢低 — 独立测试脚本 |
| `YushuTech参考/` | 只读参考 | 🟢低 — 不修改 |
| `go1_test.py` | 一键全功能诊断(T1-T7) | 🟢低 — 独立测试脚本 |
| `go1_control.py` | 统一MQTT控制入口(交互式+动作+LED) | 🟢低 |
| `go1_sim.py` | MuJoCo仿真 v2.1 (7步态+IMU+Gym+地形+--json/--quiet) | 🟡中 — 物理参数关联 |
| `go1_brain.py` | Agent中枢大脑 v2.0 (五感→情感→决策→执行+HTTP API) | 🟡中 — 依赖sim+control |
| `go1_rl.py` | RL集成模块 (Gymnasium环境+PPO训练+策略推理, 13/13 PASS) | 🟡中 — 依赖refs/ |
| `_brain_test.py` | v2.0全链路测试 (37项, 五感+情感+交互+空间+健康) | 🟢低 |

## 操作约束

### 安全铁律
1. **发送电机命令前必须确认电源电压(23-25V)** — 低压brownout可能损坏电机
2. **Kp值从小开始(≤4)** — 过大Kp会导致电机剧烈振荡
3. **每次测试结束必须发送停止命令** (`Kp=0, Kd=0, tau=0`)
4. **禁止同时向多个电机发送高增益命令** — 总线饱和风险

### 串口规则
- Windows默认端口: `COM5` (CH343 USB-RS485)
- Linux默认端口: `/dev/ttyUSB0`
- 波特率固定 `5000000`，不可改
- 串口被占用时: 重启电脑或设备管理器禁用/启用

### 标定数据
`build_a_packet.py` 中 `build_a_packet()` 函数的位置校准常量是**设备相关**的：
- Motor 0: `pos_to_hex(-0.242287*q + 0.131417)`
- Motor 1: `pos_to_hex(-0.235337*q + 0.459373-0.03)`
- Motor 2: `pos_to_hex(0.379897*q + -0.120322)`

更换电机后需重新标定（运行 `calibration/` 下的脚本）。

## 外部资源

- **官方SDK**: `E:\unitree\unitree_legged_sdk-3.8.0\` (C++/Python, Go1 UDP通信)
- **电机资料**: `E:\unitree\GO-M8010-6 资料包\` (3D模型+手册)
- **教程视频**: `E:\unitree\GO-M8010-6电机使用教程\` (~670MB)
- **Go1凭据**: `secrets.env` → `GO1_IP`, `GO1_USER`, `GO1_SSH_KEY`

## 资源来源

| 目录 | 来源 | 拉取方式 |
|------|------|---------|
| `gooddawg/` | 笔记本 `E:\道\Lab\Experiments\机器狗维修研究\宇树go1电机\gooddawg\` | SMB |
| `电机测试/` | 笔记本 `E:\道\Lab\Experiments\机器狗维修研究\电机单独测试\` | SMB |
| `YushuTech参考/` | 笔记本 `E:\道\Lab\Experiments\机器狗\YushuTechUnitreeGo1-main\` | SMB |
| `gooddawg/unitree_crc/` | 笔记本 `...\宇树go1电机\unitree_crc\` | SMB |
| `refs/free-dog-sdk/` | [Bin4ry/free-dog-sdk](https://github.com/Bin4ry/free-dog-sdk) (218★) | GitHub API |
| `refs/go1pylib/` | [chinmaynehate/go1pylib](https://github.com/chinmaynehate/go1pylib) (10★) | GitHub API |
| `refs/setup-guide/` | [geyang/unitree-go1-setup-guide](https://github.com/geyang/unitree-go1-setup-guide) (21★) | GitHub API |
| `refs/mujoco-menagerie/` | [google-deepmind/mujoco_menagerie](https://github.com/google-deepmind/mujoco_menagerie) (1800+★) | GitHub API |
| `refs/unitree-ros2-sim/` | [Atharva-05/unitree_ros2_sim](https://github.com/Atharva-05/unitree_ros2_sim) (46★) | GitHub API |
| `refs/maestro-mujoco/` | [despargy/maestro_mujoco](https://github.com/despargy/maestro_mujoco) (17★) | GitHub API |
| `refs/go1-voice-control/` | [Raviteja-T/Unitree-Go1-Voice-Control](https://github.com/Raviteja-T/Unitree-Go1-Voice-Control) (16★) | GitHub API |
| `refs/legged-mpc/` | [zha0ming1e/legged_mpc_control](https://github.com/zha0ming1e/legged_mpc_control) (64★) | GitHub API |
| `refs/quadruped-rl-locomotion/` | [nicklashansen/tdmpc2](https://github.com/rohanpsingh/LearningHumanoidWalking) Go1 RL Gym+28个PPO (123★) | GitHub API |
| `refs/rl_sar/` | [fan-ziqi/rl_sar](https://github.com/fan-ziqi/rl_sar) 多机器人 RL sim2sim (1161★) | GitHub API |
| `refs/unitree-go2-mjx-rl/` | MuJoCo XLA GPU加速RL训练 (19★) | GitHub API |
| `refs/unitree-mujoco/` | 官方Unitree MuJoCo仿真器 (Go2/G1/H1) | GitHub API |
| `refs/GenLoco/` | [HybridRobotics/GenLoco](https://github.com/HybridRobotics/GenLoco) 多机器人泛化步态 | GitHub API |
| `refs/DRLoco/` | DeepMimic+MuJoCo+SB3运动模仿 | GitHub API |

### 网络连接规则

- Go1 WiFi SSID: `Unitree_Go116748A`, 密码: `00000000`
- Go1默认IP: `192.168.12.1`, MQTT端口: `1883`, SSH用户: `pi`
- 有线连接需手动配置电脑以太网IP为 `192.168.12.100/24`
- **测试前先运行 `python go1_test.py --skip-motor`** 确认网络连通

### MQTT控制主题

| 主题 | 用途 | 示例 |
|------|------|------|
| `controller/action` | 动作指令 | `standUp`, `standDown`, `walk`, `jumpYaw` |
| `controller/stick` | 遥杆控制(4xfloat32) | `struct.pack('ffff', lx, rx, ry, ly)` |
| `controller/run` | 运行模式 | `ok` |
| `programming/code` | 远程代码执行 | Python代码字符串 |
| `programming/action` | 代码执行控制 | `start`, `stop` |
| `face_light/color` | LED灯光 | `bytes([r,g,b])` |

## 已修复问题 (2026-03-04)

**代码质量修复 (Phase 1):**
1. **`example_dead_simple.py` SyntaxError** — 第二个`try`块缩进错误（在`except`内部）→ 修正缩进
2. **硬编码Linux端口** — `example_*.py` 固定 `/dev/ttyUSB0` → 改为平台自动检测
3. **`interpret_signed_angle` 返回字符串** — 长度校验失败时返回字符串而非异常 → 改为 `raise ValueError`
4. **`motor_id=4` 无反馈** — 默认ID超出motor_data范围(0-2) → 改为默认ID=0
5. **f-string格式化None** — `{angle:.4f}` 当angle为None时崩溃 → 提前判断
6. **缺少`__init__.py`** — gooddawg无法作为包导入 → 创建
7. **`__pycache__`误拷贝** — 清理

**网络通信修复 (Phase 2):**
8. **`MQTT_remote.py` 转义错误** — `\x00\x00\x00x00` 缺少反斜杠 → 修正为 `\x00\x00\x00\x00`
9. **`requirements.txt` 不完整** — 缺少 `paho-mqtt` 和 `opencv-python` → 补全
10. **创建 `go1_test.py`** — 一键诊断脚本(T1-T7)，覆盖Ping/SSH/MQTT/摄像头/电机

**仿真环境 (Phase 3, 2026-03-05):**
11. **创建 `go1_sim.py` v2.1** — MuJoCo仿真器: 7步态 + IMU + Gym RL + 地形 + `--json`/`--quiet` Agent适配
12. **Go1物理参数集成** — 从legged-mpc提取足端位置/步态频率/速度限制/关节力矩等
13. **创建 `go1_control.py`** — 统一MQTT控制入口(12动作+LED+交互式控制台)
14. **GitHub生态穷尽搜索** — 7批搜索覆盖SLAM/导航/视觉/RL/远程/Web，整合了8个高价值项目

**Agent中枢大脑 (Phase 4, 2026-03-05):**
15. **创建 `go1_brain.py` v1.0** — Agent中枢: 感知(IMU+姿态分类+稳定性) → 决策(优先级行为树) → 执行(sim/real双后端)
16. **6个行为系统** — RecoverBehavior(跌倒恢复) + BalanceBehavior(平衡纠正) + PatrolBehavior(自主巡逻) + DanceBehavior(舞蹈序列) + ExploreBehavior(随机探索) + StandBehavior(默认)
17. **Agent命令接口** — `brain.command("gait trot 5")` / `--json --cmd` / `--status` 程序化调用
18. **go1_sim.py v2.1审计修复** — 6个问题: 临时文件泄漏/无quiet/无json/未用变量/quiet逻辑反转/地形print泄漏

**AI大脑 v2.0 (Phase 5, 2026-03-05):**
19. **五感感知系统** — VisionData(障碍物+地形粗糙度) + AudioEvent(声音事件) + 电量/温度/情感状态注入PerceptionState
20. **情感引擎 EmotionEngine** — 8种情绪(calm/happy/curious/alert/tired/scared/excited/lonely) + 事件触发的状态转移 + LED颜色映射 + 能量/社交需求系统
21. **空间地图 SpatialMap** — 10m×10m栅格(0.2m分辨率) + 覆盖率跟踪 + 障碍物标记
22. **健康监测 HealthMonitor** — 电量消耗模拟 + 温度监控 + 里程统计 + 故障诊断
23. **持久记忆 DogMemory** — .go1_memory.json + 地点记忆 + 统计数据(跑步/跌倒/里程)
24. **5个新行为** — FollowBehavior(跟随) + GuardBehavior(警戒) + PlayBehavior(玩耍) + GreetBehavior(问候) + RestBehavior(休息) → 总行为文11个
25. **安全行为中断** — recover/balance/rest(priority≥70) 可中断任何强制行为
26. **人机交互** — say命令(语音回应) + hear()自然语言入口 + 18个中文关键词映射
27. **HTTP API BrainAPIServer** — :8085端口, GET(/status/report/health/emotion/map/memory) + POST(/cmd/say) + CORS
28. **Bug修复** — total_falls计数每 tick重复→只计单次; 安全行为无法中断强制行为→优先级检查
29. **测试升级** — _brain_test.py v2.0: 12组×37项全通过 (MuJoCo 3.5.0)

**RL仿真集成 (Phase 6, 2026-03-05):**
30. **GitHub生态穷尽搜索Ⅱ** — 6个新项目: quadruped-rl-locomotion(123★) + rl_sar(1161★) + unitree-go2-mjx-rl + unitree-mujoco(官方) + GenLoco(Go1支持) + DRLoco
31. **创建 `go1_rl.py`** — RL集成模块: Go1GymEnv(Gymnasium包装) + RLTrainer(PPO训练管线) + RLPolicy(策略加载+obs兼容) + find_pretrained_models(扫描46个模型)
32. **MuJoCo 3.5.0兼容性** — 解决Unicode路径限制(自动复制到ASCII temp) + obs shape不匹配(48 vs 45, 自动截断/填充)
33. **全链路验证** — go1_rl.py --test: 13/13 PASS (环境创建+随机策略+预训练PPO加载+推理+项目盘点)
34. **预训练模型库** — 46个模型(28个SB3 PPO Go1 + 15个PyTorch rl_sar + 3个GenLoco TF)
35. **refs/资源库** — 扩展到8→14个开源项目, 覆盖控制/仿真/RL/语音/视觉/步态全链路

**八卦辩证审计 + 一体化集成 (Phase 7, 2026-03-05):**
36. **Go1Env Gymnasium升级** — step()返回5值(obs,r,terminated,truncated,info) + reset()返回(obs,info) + 分离_is_terminated/_is_truncated
37. **死依赖清理** — 移除未使用的events/imageio + requirements.txt分组(核心/仿真/视觉/RL)
38. **文档修复** — README.md "屖"→"嗅" + 以太网IP双模式说明(直连12.x vs Mesh 123.x) + AGENTS.md补全RL refs来源
39. **端口冲突修复** — go1_control.py UDP_HIGH_PORT 8082→8086 (避免RTSP冲突)
40. **Go1Env重复标注** — go1_sim.py::Go1Env添加轻量版注释 + 指向go1_rl.py::Go1GymEnv
41. **统一CLI `go1.py`** — 一个命令控制所有模块(sim/brain/rl/control/test/status) + 系统总览(依赖/文件/模型/端口)
42. **Brain-RL桥接** — RLBehavior类: 加载PPO策略→仿真状态→48维obs→策略推理→12维action→控制机器人 + `rl`命令接口

**代码审计 + 资源整合 (Phase 8, 2026-06):**
43. **🔴 足端位置不对称Bug** — go1_sim.py GO1_PARAMS foot_pos: FL.y=0.12/FR.y=-0.17交叉错误 → 统一为±0.13m对称
44. **🔴 FollowBehavior方向Bug** — go1_brain.py: 只沿vx前进(vy=0,yaw=0) → 计算目标方向角+分解vx/vy+yaw转向控制
45. **GitHub资源整合Ⅲ** — 4批搜索60+项目, 筛选30+高价值项目分4层(Tier1 Go1直接相关/Tier2生态框架/Tier3传感导航/Tier4通用参考), 更新refs/README.md
46. **发现关键新资源** — walk-these-ways(1286★,Go1 RL Sim2Real黄金标准) + dial-mpc(941★,ICRA 2025) + rl-mpc-locomotion(924★,Go1 MPC) + cpg_go1_simulation(Go1 CPG MuJoCo)

**Dashboard虚拟仿真控制台重写 (Phase 9, 2026-06):**
47. **🔵 Dashboard全面中文化重写** — dashboard.html 528行→350+行, 全英文→全中文UI, 复用智能家居/桌面投屏/ORS6暗色主题模式
48. **新增10项功能** — ①WASD键盘行走控制 ②自然语言输入框+发送 ③API端点可配置 ④步态时长滑块 ⑤地形选择器(平地/粗糙/台阶/斜坡) ⑥2D空间地图Canvas可视化 ⑦关节角度显示 ⑧触摸旋转支持 ⑨尾巴摇摆动画 ⑩中文情感/姿态映射
49. **E2E测试套件** — _e2e_dashboard_test.py(14/14 API) + _e2e_browser_test.py(75/75 HTML结构+中文UI+3D+CSS+API+命令+新功能)
50. **E2E测试修复** — T7-Dashboard检查"Go1 Agent Dashboard"→"Go1"+"控制台"(匹配新中文标题)
51. **🔴 PNAME姿态映射不完整** — Playwright实测发现`fallen_side`显示原始英文 → 补全4个姿态: 侧翻/前扑/后仰/未知 + JNAMES关节中文名
52. **🔴 关节角度显示"--"** — API未返回joint_positions → PerceptionState添加字段 + SimBackend从sim.get_state()["joint_pos"]填充12个关节角 + Dashboard按腿组显示FR/FL/RR/RL

**实机连接诊断 (Phase 10, 2026-03-05):**
53. **双网并存方案** — 以太网连路由器上网(192.168.31.55) + WLAN连Go1 WiFi(192.168.12.251), 零干扰双网
54. **WiFi 5G优先问题** — 笔记本适配器Preferred Band=5G first, Go1 AP在5GHz ch165但间歇性不可见 → 断开WLAN强制全频段扫描后连接成功
55. **go1_test.py 6/6 PASS** — Ping(1ms)/SSH(OpenSSH 7.9p1)/MQTT(10主题)/TCP(6端口)/Stick全通过, 摄像头UDP无数据(WARN)
56. **SSH深度收集 39/41** — 发现硬件=Pi CM4 Rev 1.0, OS=Debian 10 buster, 内核=5.4.81-rt45-v8+ PREEMPT_RT, SSH密码=123
57. **🔴🔴 根因: eth0 NO-CARRIER** — 内部以太网物理断开, dmesg报`failed to get enet clock`, 所有内部板(Nano/MCU)不可达 → robot/state全零, bms全零, 无摄像头, 无电机控制, SportMode `[Wait] for check`
58. **诊断报告** — GO1_DIAG_REPORT.md (完整8项问题清单+网络拓扑+MQTT主题+系统信息+建议操作)

**实机诊断续 + Bug修复 (Phase 11, 2026-03-05 18:00):**
59. **🔴 FollowBehavior崩溃** — `ps.yaw` AttributeError → PerceptionState无`yaw`属性,只有`yaw_deg` → 修改为`math.radians(ps.yaw_deg)` (37/37 PASS)
60. **eth0软件重启无效** — SSH执行`sudo ip link set eth0 down/up` → 仍NO-CARRIER, dmesg确认物理层问题
61. **系统时钟已修复** — 之前2021年,现确认2026-03-05 18:07 CST正确
62. **rc-local已修复** — `systemctl --failed`返回0,GPIO 18冲突已解决
63. **全套测试通过** — go1_test.py 6/6 + _brain_test.py 37/37 + go1_rl.py 13/13 = 56/56 PASS

**Go1联网+NTP+全验证 (Phase 12, 2026-03-05 19:15):**
64. **Mosquitto日志权限修复** — 重启后mosquitto.service失败(Unable to open log file) → mkdir+chown+restart = MQTT恢复
65. **🟢 Go1通过笔记本上网** — ip route add default via 192.168.12.251 + Windows WLAN IP Forwarding + dnsmasq上游DNS(8.8.8.8/223.5.5.5) → ping 8.8.8.8/pool.ntp.org全通
66. **NTP同步恢复** — 10+服务器连接, *ntp8.flashdance(stratum 2)为主源, 时钟精确
67. **eth0硬件故障确认** — 排线重连+完全重启Go1后仍NO-CARRIER, genet为builtin模块不可热重载 → 排线/交换机/PHY物理损坏
68. **USB-Ethernet替代方案** — USB Hub Port1-3空闲, 可插RTL8153/AX88179适配器配置192.168.123.x绕过eth0
69. **Dashboard E2E 14/14 PASS** — GET(status/health/emotion/map/memory/report/dashboard)+POST(cmd×5+say) 全通
70. **总测试: 64/64 PASS** — test(5)+brain(37)+RL(13)+dashboard(14)=69, 扣除MQTT初始化延迟WARN

**Phase 13 全面审计+Dashboard增强 (2026-03-06):**
71. **☷坤·熵减** — .gitignore添加诊断JSON(4个)+terrain_*.xml临时文件
72. **🔴 WASD键盘控制无效** — dashboard发送`velocity`命令但brain无handler → 新增`velocity`命令(vx/vy/yaw_rate/duration)
73. **🔴 2D地图不渲染** — SpatialMap.summary()未返回cell数组 → 新增grid_size+visited[]+obstacle_cells[]
74. **🔴 terrain_type存错对象** — `self.perception.terrain_type`设在PerceptionProcessor上 → 改为`self._terrain_type`存brain, sense()注入PerceptionState
75. **🟡 walk命令忽略vx** — GaitBehavior("trot")不使用速度参数 → 改为execute_velocity(vx,0,0,dur)
76. **🟡 speed命令无效** — sim.dt不影响model.opt.timestep → 直接修改model.opt.timestep
77. **🟡 PWA ServiceWorker失败** — data URI注册在浏览器中始终被拒 → 移除无效代码
78. **☳震·3D关节动画** — upd3D()从joint_positions驱动腿部tP/cP旋转, 替代静态站姿
79. **☳震·情绪尾巴** — 尾巴摇摆幅度由emotion状态驱动(happy/excited=0.6, 其他=0.3)
80. **☳震·地形显示** — 3D视口底栏增加当前地形类型(T:flat/rough/stairs/slope)
81. **☳震·WASD提示完善** — 添加Q/E转向键提示

**Phase 14 E2E Agent测试 + Bug修复 (2026-03-05):**
82. **🔴 emotion命令不更新状态** — EmotionEngine.process_event只处理trigger事件(pet/fall等), 不处理直接情感名 → 新增happy/alert/curious/excited/calm/scared/lonely直接映射
83. **🔴 terrain rough MuJoCo崩溃** — mj_stackAlloc stack overflow: 40个box碰撞复杂度过高 → 减至15个+contype=0/conaffinity=1+nstack=2000000
84. **🔴 switch_terrain无回滚** — 新sim初始化失败后旧sim丢失 → crash-safe原子交换(先创建验证新sim, 失败恢复旧sim)
85. **🟡 输入框双重say** — doSay()始终prepend "say ", 用户输入"say 乖"变成"say say 乖" → 正则检测已知命令verb, 匹配则直传
86. **☳震·Agent E2E全覆盖** — 24项功能Playwright验证: stand/sit/stop/status + trot/walk/dance/pace/bound + patrol/explore/greet/guard/play + happy/alert/curious + flat/rough/stairs/slope + speed2x + WASD(W) + remember/memory/health

**Phase 15 实机深度诊断·网线直连 (2026-03-06):**
87. **☰乾·网线直连成功** — 绕过Pi故障eth0, PC(192.168.123.200)直连内部交换机, MCU(.10)+Nano(.13/.14/.15)全部alive
88. **☷坤·3板SSH全量扫描** — 系统信息/进程/网络/USB/摄像头/autostart 全部采集→`_go1_board_scan.json`
89. **☵坎·MCU原始UDP读取** — 发送LowCmd(614B)到MCU:8007, 收到LowState(820B), 解析电机角度/BMS
90. **☲离·缺腿诊断确认** — **FL(前左)腿缺失**: motor[3]hip=0°+motor[4]thigh=0°(断开), motor[5]calf=-41°(残留); RL_calf=0°(可能损坏)
91. **☳震·内部架构完整映射** — .13=头部(超声波+UART+faceLED+wsaudio:8765), .14=身体(mqttControlNode AI+SDK), .15=尾部(空闲)
92. **☴巽·5摄像头确认** — .13(video0+1,camera1), .14(video0+1,camera3+4), .15(video0,camera5)
93. **☶艮·Pi完全隔离** — 从所有Nano和PC均不可达, ARP=INCOMPLETE, 无WiFi, 无替代路径
94. **☱兑·诊断报告** — GO1_DIAG_REPORT.md Phase 2节(~160行): 拓扑/板子/USB/摄像头/进程/电机/问题清单/修复方案

**Phase 16 Pi救援 + PC替代Pi (2026-03-06):**
95. **☰乾·Pi完全失联确认** — WiFi AP消失(Phase 1可见→现不可见), 13项探测全dead, Pi断电或内核崩溃
96. **☷坤·全方位探测** — PC/Nano→Pi ping/TCP/ARP/子网扫描/WiFi/UART/USB全路径封死, 无任何替代连接
97. **☵坎·MQTT重定向** — 3板iptables DNAT: `192.168.123.161:1883→127.0.0.1:1883`, mqttControlNode连接本地broker
98. **☲离·PC→MCU直连UDP** — PC(192.168.123.200)直接发LowCmd→MCU(.10):8007, 820B LowState, <1ms延迟
99. **☳震·IMU解析突破** — 确认offset=10: quaternion[0.976,-0.015,-0.003,-0.216] |q|=1.0000, RPY=[-1.6°,-0.7°,-24.9°]
100. **☴巽·LowState完整布局** — head(0-1)/IMU(10-61)/motors(96-479,32B×12)/footForce(480-487)/BMS+CRC(488-819)
101. **☶艮·时钟同步+wsaudio清理** — 3板时钟→2026年, wsaudio已停(CPU恢复正常), 电池36%→45%(充电中)
102. **☱兑·诊断报告Phase 3** — GO1_DIAG_REPORT.md追加~95行: 13项探测/MQTT重定向/IMU布局/问题清单更新/物理检查指南

**Phase 17 虚拟仿真优化·熵减清理 (2026-03-06):**
103. **☲离·全目录审计** — 6核心py(go1/brain/sim/rl/control/test) + 14refs(全有内容) + 42电机测试 + 20个_临时文件
104. **☷坤·熵减清理** — .gitignore新增`_*.py`/`_*.json`覆盖20个诊断临时文件; 删除1B空文件`电机测试/direct_motor_control.c`
105. **☵坎·dashboard.html升级4项** — ①WASD节流防洪(200ms间隔+busy锁) ②髋关节动画(12关节全驱动,新增hP层) ③地形3D可视化(setTerrain3D粗糙/台阶/斜坡地面变形+变色) ④地形自动同步(RS._lastTerrain脏检查)
106. **☳震·go1_brain.py修复** — Dashboard HTML响应添加CORS+Cache-Control头(跨域访问+热刷新)
107. **☱兑·E2E全链路验证** — Brain API :8085全7端点200✅ + 5个POST命令✅ + Playwright浏览器dashboard渲染✅ + 小跑步态+粗糙地形交互✅

**Phase 18 第三方动作系统集成·refs整合 (2026-03-06):**
108. **☲离·refs扫描** — 识别4个可集成库: free-dog-sdk(walk/pushups/rotate) + go1pylib(dance/square/move_joints) + unitree-mujoco(MuJoCo仿真) + quadruped-rl-locomotion(RL步态)
109. **☳震·SimBackend.execute_pose** — 身体姿态控制(lean/twist/look/extend→12关节偏移): hip差动=侧倾, hip前后差动=扭转, thigh前后差动=俯仰, thigh+calf均匀=伸展
110. **☳震·PoseBehavior+DemoBehavior** — 姿态行为类(1.5s自动回归stand) + 演示序列类(walk/dance/pushup/square 4套预设, 整合free-dog-sdk+go1pylib动作原语)
111. **☵坎·命令扩展** — `pose lean twist look extend [dur]` + `demo <walk|dance|pushup|square>` + hear()自然语言映射(抬头/低头/侧倾/扭转/蹲下/站高/演示/表演/正方形)
112. **☲离·Dashboard升级** — 🎭姿态控制面板(8按钮: 左倾/右倾/左扭/右扭/抬头/低头/蹲低/站高) + 🎬动作演示面板(4按钮: 走路秀/舞蹈秀/俯卧撑秀/正方形)
113. **☴巽·BNAME修复** — 新增pose_cmd→姿态/demo_cmd→演示/gait_cmd→步态/rl_policy→RL策略; doSay verb列表补充pose|demo
114. **☱兑·E2E验证11/11** — API 9命令全ok✅ + Playwright 8按钮+文本输入✅ + 行为中文显示✅ + 情感/关节/地图联动✅ + 无回归✅
