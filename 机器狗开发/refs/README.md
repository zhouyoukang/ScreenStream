# Go1 开源资源索引

> 从GitHub整合的Unitree Go1优质开源项目。Agent可直接引用这些代码。

## 项目清单

| 目录 | 来源 | 星数 | 价值 | 用途 |
|------|------|------|------|------|
| `free-dog-sdk/` | [Bin4ry/free-dog-sdk](https://github.com/Bin4ry/free-dog-sdk) | 218★ | 极高 | 纯Python UDP SDK (替代C++ unitree_legged_sdk) |
| `go1pylib/` | [chinmaynehate/go1pylib](https://github.com/chinmaynehate/go1pylib) | 10★ | 极高 | MQTT高层控制库 (async运动/LED/模式) |
| `setup-guide/` | [geyang/unitree-go1-setup-guide](https://github.com/geyang/unitree-go1-setup-guide) | 21★ | 高 | Go1内部网络架构+SSH配置+部署指南 |
| `mujoco-menagerie/` | [google-deepmind/mujoco_menagerie](https://github.com/google-deepmind/mujoco_menagerie) | 1800+★ | 极高 | Go1 MuJoCo官方模型 (URDF+STL+scene.xml) |
| `unitree-ros2-sim/` | [Atharva-05/unitree_ros2_sim](https://github.com/Atharva-05/unitree_ros2_sim) | 46★ | 高 | Go1 Gazebo ROS2仿真 (URDF+导航+控制器) |
| `maestro-mujoco/` | [despargy/maestro_mujoco](https://github.com/despargy/maestro_mujoco) | 17★ | 中 | MuJoCo四足滑面控制 (Go2, OTD算法) |
| `go1-voice-control/` | [Raviteja-T/Unitree-Go1-Voice-Control](https://github.com/Raviteja-T/Unitree-Go1-Voice-Control) | 16★ | 中 | Go1语音控制 (C++ legged_sdk v3.5.1) |
| `legged-mpc/` | [zha0ming1e/legged_mpc_control](https://github.com/zha0ming1e/legged_mpc_control) | 64★ | 高 | MPC四足控制器 (Go1 URDF+Gazebo+Docker) |

## free-dog-sdk (纯Python UDP SDK)

通过UDP直接与Go1通信，无需C++ SDK编译。支持高层和低层控制。

**核心库 `ucl/`:**

| 文件 | 功能 |
|------|------|
| `unitreeConnection.py` | UDP连接管理 (WiFi/有线，高/低层模式) |
| `highCmd.py` | 高层命令构建 (步态/速度/姿态/LED) |
| `highState.py` | 高层状态解析 (BMS/IMU/FootForce) |
| `lowCmd.py` | 低层命令构建 (单电机力矩/位置/速度) |
| `lowState.py` | 低层状态解析 (12电机角度/速度/力矩) |
| `common.py` | 工具函数 (CRC/hex转换/版本解码) |
| `complex.py` | 复合数据结构 (motorCmd/IMU/LED/BMS) |
| `enums.py` | 枚举定义 (MotorModeHigh/GaitType/SpeedLevel) |

**示例脚本:**

| 脚本 | 功能 | 模式 |
|------|------|------|
| `walk.py` | 行走+姿态+站立演示 | 高层 |
| `pushups.py` | 俯卧撑动作 | 高层 |
| `rotate.py` | 原地旋转 | 高层 |
| `position.py` | 单电机位置控制 | 低层 |
| `velocity.py` | 单电机速度控制 | 低层 |
| `torque.py` | 单电机力矩控制 | 低层 |

**连接方式:**

```python
from ucl.unitreeConnection import unitreeConnection, HIGH_WIFI_DEFAULTS, HIGH_WIRED_DEFAULTS
# WiFi连接 (192.168.12.1:8082)
conn = unitreeConnection(HIGH_WIFI_DEFAULTS)
# 有线连接 (192.168.123.161:8082)
conn = unitreeConnection(HIGH_WIRED_DEFAULTS)
```

**依赖:** `numpy`

## go1pylib (MQTT高层控制库)

基于paho-mqtt的async控制库，提供简洁的运动/LED/模式API。

**核心 `src/go1pylib/`:**

| 文件 | 功能 |
|------|------|
| `go1.py` | 主控制类 Go1 (19个运动方法+LED+模式) |
| `mqtt/client.py` | MQTT客户端 (连接/断开/发布/订阅) |
| `mqtt/state.py` | 机器人状态数据结构 |
| `mqtt/handler.py` | 消息处理器 |
| `mqtt/topics.py` | MQTT主题定义 |
| `mqtt/receivers/` | BMS/Robot状态接收器 |

**运动API (async):**

```python
from go1pylib import Go1, Go1Mode
dog = Go1()
dog.init()
dog.set_mode(Go1Mode.WALK)
await dog.go_forward(speed=0.25, duration_ms=2000)
await dog.turn_left(speed=0.5, duration_ms=1000)
dog.set_led_color(255, 0, 0)  # 红色LED
```

**示例脚本:**

| 脚本 | 功能 |
|------|------|
| `move_forward.py` | 前进运动 |
| `dance.py` | 舞蹈动作序列 |
| `square.py` | 正方形路径 |
| `led_control.py` | LED灯光控制 |
| `avoid_obstacles.py` | 避障演示 |
| `get_state.py` | 读取机器人状态 |
| `move_joints.py` | 关节控制 |

**依赖:** `paho-mqtt`, `numpy`, `events`

## setup-guide (Go1内部网络架构)

MIT提供的Go1设置指南，揭示内部4台电脑架构。

**Go1内部电脑:**

| 主机 | IP | 用户 | 用途 |
|------|-----|------|------|
| Raspberry Pi | 192.168.123.161 | pi | 主控/WiFi AP/互联网代理 |
| Jetson Nano A | 192.168.123.13 | unitree | 头部摄像头 |
| Jetson Nano B | 192.168.123.14 | unitree | 机身 |
| Jetson Xavier NX | 192.168.123.15 | unitree | 推理计算 |

**关键信息:**
- SSH密码: `123`, 用户名: `unitree` (Pi用`pi`)
- WiFi模块每次关机后需手动`sudo ifconfig wlan0 up`
- 有线连接: PC需配置`192.168.123.162/24`
- 高层UDP端口: `8082`, 低层UDP端口: `8007`, 监听端口: `8090`

## 已有资源 (不在refs/中)

| 目录 | 来源 | 星数 |
|------|------|------|
| `gooddawg/` | [imcnanie/gooddawg](https://github.com/imcnanie/gooddawg) | 18★ |
| `gooddawg/unitree_crc/` | [aatb-ch/unitree_crc](https://github.com/aatb-ch/unitree_crc) | 23★ |
| `YushuTech参考/` | [MAVProxyUser/YushuTechUnitreeGo1](https://github.com/MAVProxyUser/YushuTechUnitreeGo1) | 440★ |
| `E:\unitree\unitree_legged_sdk-3.8.0` | [unitreerobotics/unitree_legged_sdk](https://github.com/unitreerobotics/unitree_legged_sdk) | 401★ |

## RL仿真与训练 (Phase 6, 2026-03-05)

| 目录 | 来源 | 星数 | 价值 | 用途 |
|------|------|------|------|------|
| `quadruped-rl-locomotion/` | [nimazareian/quadruped-rl-locomotion](https://github.com/nimazareian/quadruped-rl-locomotion) | 123★ | **核心** | Go1 Gymnasium MuJoCo环境 + 28个PPO预训练模型 |
| `rl_sar/` | [fan-ziqi/rl_sar](https://github.com/fan-ziqi/rl_sar) | 1161★ | 极高 | 多机器人RL sim2sim部署 + 15个PyTorch策略权重 |
| `unitree-go2-mjx-rl/` | [maugli-1/unitree-go2-mjx-rl](https://github.com/maugli-1/unitree-go2-mjx-rl) | 19★ | 高 | MuJoCo XLA(JAX) GPU加速RL训练 |
| `unitree-mujoco/` | [unitreerobotics/unitree_mujoco](https://github.com/unitreerobotics/unitree_mujoco) | 官方 | 极高 | Unitree官方MuJoCo仿真器 (Go2/G1/H1模型) |
| `GenLoco/` | [HybridRobotics/GenLoco](https://github.com/HybridRobotics/GenLoco) | — | 高 | 10机器人泛化步态控制(含Go1), PyBullet, URDF+策略 |
| `DRLoco/` | [rgalljamov/DRLoco](https://github.com/rgalljamov/DRLoco) | — | 中 | DeepMimic+MuJoCo+Stable-Baselines3运动模仿 |

### quadruped-rl-locomotion (核心RL环境)

Go1 Gymnasium环境，**已验证与MuJoCo 3.5.0兼容** (obs shape 48维 vs 旧版45维)。

**架构:**
```
Go1MujocoEnv (gymnasium.MujocoEnv)
  ├── 控制模式: torque / position
  ├── 观测空间: 48维 (3线速度+3角速度+3重力投影+3目标速度+12关节位+12关节速+12上次动作)
  ├── 动作空间: 12维 (4腿×3关节)
  ├── 奖励函数: 速度跟踪+脚步韵律+健康+多项惩罚
  ├── 终止条件: 倾倒/超时(15秒)
  └── 训练: PPO (Stable-Baselines3)
```

**预训练模型 (28个):**
- Position控制: 10M/20M/30M iterations, 正常/快速步伐
- Torque控制: 5M/13M iterations, 稳定行走
- 所有模型路径: `models/<timestamp>/best_model.zip`

**使用:**
```python
from go1_rl import Go1GymEnv, RLPolicy
env = Go1GymEnv(ctrl_type="torque")
policy = RLPolicy("refs/quadruped-rl-locomotion/models/.../best_model.zip")
obs, _ = env.reset()
action = policy.predict(obs)  # 自动处理obs shape兼容
```

### rl_sar (多机器人RL策略)

**策略权重 (15个PyTorch .pt):**

| 机器人 | 策略 | 大小 |
|--------|------|------|
| A1 | legged_gym | 4.5MB |
| B2 | robot_lab | 769KB |
| G1 | locomotion(29dof) + charleston + dance + gangnam_style | 1-2MB |
| Go2 | himloco + robot_lab | 769KB-1MB |

注: ROS/C++为主, Python策略推理需自行适配。

### unitree-mujoco (官方仿真器)

**支持机器人:** Go2, G1, H1, B2 (无Go1, Go1已停产)
**Python仿真:** `simulate_python/unitree_mujoco.py` — 线程化MuJoCo仿真+Viewer
**地形工具:** `terrain_tool/` — 高度场地形生成

### GenLoco (泛化步态控制)

支持10种四足机器人(含Go1)的零样本迁移步态控制。

**Go1资源:**
- URDF: `robot_descriptions/go1_description/urdf/go1.urdf`
- 控制器: `motion_imitation/robots/go1.py` (PyBullet)
- 预训练策略: pace + spin + inverse (TensorFlow .zip)

## 预训练模型总览 (46个)

| 来源 | 框架 | 数量 | 机器人 |
|------|------|------|--------|
| quadruped-rl-locomotion | Stable-Baselines3 (PPO) | 28 | Go1 |
| rl_sar | PyTorch | 15 | A1/B2/G1/Go2/GR1 |
| GenLoco | TensorFlow | 3 | 多机器人(含Go1) |

快速列出: `python go1_rl.py --models`

## 兼容性矩阵

| 项目 | MuJoCo 3.5.0 | Windows | 无需实机 | Go1支持 | 测试结果 |
|------|:---:|:---:|:---:|:---:|------|
| quadruped-rl-locomotion | ✅ | ✅ | ✅ | ✅ | 13/13 PASS |
| rl_sar | ⚠️ ROS | ⚠️ | ✅ | ❌ (A1/Go2) | 权重可用 |
| unitree-go2-mjx-rl | ✅ MJX | ✅ | ✅ | ❌ (Go2) | 未测 |
| unitree-mujoco | ✅ | ✅ | ✅ | ❌ (Go2/G1/H1) | 参考代码 |
| GenLoco | ❌ PyBullet | ✅ | ✅ | ✅ | URDF+策略 |
| DRLoco | ✅ | ✅ | ✅ | ❌ (双足) | 参考框架 |

## 新发现高价值资源 (2026-06 GitHub搜索)

### Tier 1 — Go1直接相关 + 高星

| 项目 | 星数 | 类型 | 价值 | 说明 |
|------|------|------|------|------|
| [Improbable-AI/walk-these-ways](https://github.com/Improbable-AI/walk-these-ways) | 1286★ | RL Sim2Real | **极高** | MIT Go1专用! Isaac Gym + legged_gym + rsl_rl, PPO训练+Go1实机部署, CoRL 2022论文 |
| [LeCAR-Lab/dial-mpc](https://github.com/LeCAR-Lab/dial-mpc) | 941★ | MPC | **极高** | ICRA 2025 Best Paper Finalist! 训练无关MPC, JAX/Brax, 全阶力矩控制, 已支持Go2 Sim2Real |
| [silvery107/rl-mpc-locomotion](https://github.com/silvery107/rl-mpc-locomotion) | 924★ | RL+MPC | **极高** | RL预测MPC权重, 支持Go1/A1/Aliengo, Python MPC实现, Isaac Gym训练 |
| [PMY9527/QUAD-MPC-SIM-HW](https://github.com/PMY9527/QUAD-MPC-SIM-HW) | 61★ | MPC | 高 | Go1/A1 MPC sim+real验证, 基于Unitree Guide FSM, Gazebo仿真 |
| [ImDipsy/cpg_go1_simulation](https://github.com/ImDipsy/cpg_go1_simulation) | 11★ | CPG | 高 | Go1 CPG神经网络步态生成, MuJoCo仿真, 中枢模式发生器 |
| [muye1202/quadruped_locomotion_project](https://github.com/muye1202/quadruped_locomotion_project) | 41★ | 视觉RL | 高 | Go1视觉运动RL策略, 训练+部署管线 |
| [TextZip/go1-rl-kit](https://github.com/TextZip/go1-rl-kit) | 25★ | RL部署 | 中 | Go1 Edu RL部署工具包, Isaac Gym策略→实机 |

### Tier 2 — 四足生态 + 高星框架

| 项目 | 星数 | 类型 | 价值 | 说明 |
|------|------|------|------|------|
| [curieuxjy/Awesome_Quadrupedal_Robots](https://github.com/curieuxjy/Awesome_Quadrupedal_Robots) | 1028★ | 索引 | 高 | 四足机器人论文/项目/硬件大全 |
| [apexrl/awesome-rl-for-legged-locomotion](https://github.com/apexrl/awesome-rl-for-legged-locomotion) | 164★ | 索引 | 高 | RL四足运动控制论文索引 |
| [Argo-Robot/quadrupeds_locomotion](https://github.com/Argo-Robot/quadrupeds_locomotion) | 221★ | 教程 | 高 | 从零训练四足行走RL教程, 图文并茂 |
| [ouguangjun/legkilo-dataset](https://github.com/ouguangjun/legkilo-dataset) | 70★ | 数据集 | 中 | Go1腿部运动学数据集(关节编码器+IMU+LiDAR) |
| [legubiao/quadruped_ros2_control](https://github.com/legubiao/quadruped_ros2_control) | 474★ | ROS2 | 中 | ROS2四足控制+sim2real |
| [snt-arg/unitree_ros](https://github.com/snt-arg/unitree_ros) | 55★ | ROS2 | 中 | ROS2 Go1控制包 |

### Tier 3 — 传感器与导航

| 项目 | 星数 | 类型 | 价值 | 说明 |
|------|------|------|------|------|
| [unitreerobotics/UnitreecameraSDK](https://github.com/unitreerobotics/UnitreecameraSDK) | 105★ | 相机 | 高 | Go1官方相机SDK (C++, 需在Go1上编译) |
| [ngmor/unitree_nav](https://github.com/ngmor/unitree_nav) | 46★ | SLAM | 高 | Go1 + RS-Helios LiDAR + Nav2 SLAM导航 |
| [aatb-ch/go1_republisher](https://github.com/aatb-ch/go1_republisher) | 21★ | ROS | 中 | Go1相机/IMU/里程计→ROS话题发布 |
| [MAVProxyUser/YushuTechUnitreeGo1](https://github.com/MAVProxyUser/YushuTechUnitreeGo1) | 440★ | 参考 | 高 | Go1深度逆向/开发笔记 (已在YushuTech参考/) |

### Tier 4 — 通用四足框架 (参考)

| 项目 | 星数 | 类型 | 说明 |
|------|------|------|------|
| [PetoiCamp/OpenCat-Quadruped-Robot](https://github.com/PetoiCamp/OpenCat-Quadruped-Robot) | 4654★ | 框架 | 开源四足STEM教育框架 |
| [Nate711/StanfordDoggoProject](https://github.com/Nate711/StanfordDoggoProject) | 2505★ | 硬件 | Stanford Doggo开源四足 |
| [chvmp/champ](https://github.com/chvmp/champ) | 2180★ | 控制 | MIT Cheetah I实现 |
| [ToanTech/py-apple-quadruped-robot](https://github.com/ToanTech/py-apple-quadruped-robot) | 1209★ | 全栈 | 中文低成本全套四足方案 |
| [nicrusso7/rex-gym](https://github.com/nicrusso7/rex-gym) | 1084★ | Gym | SpotMicro OpenAI Gym环境 |
| [ethz-adrl/towr](https://github.com/ethz-adrl/towr) | 1046★ | 优化 | 轻量C++轨迹优化 (ETH) |
| [robomechanics/quad-sdk](https://github.com/robomechanics/quad-sdk) | 913★ | SDK | CMU四足敏捷软件工具 |
| [OpenQuadruped/spot_mini_mini](https://github.com/OpenQuadruped/spot_mini_mini) | 912★ | Sim2Real | Bezier曲线步态+域随机化 |
| [robot-descriptions/awesome-robot-descriptions](https://github.com/robot-descriptions/awesome-robot-descriptions) | 1411★ | URDF/MJCF | 机器人描述文件大全 |

### 整合优先级建议

**推荐克隆到refs/:**
1. `walk-these-ways` — Go1 RL黄金标准, 但需Isaac Gym (~2GB), 可只取策略代码
2. `cpg_go1_simulation` — Go1 CPG, MuJoCo兼容, 体积小
3. `QUAD-MPC-SIM-HW` — Go1 MPC, 可参考FSM架构

**推荐引用不克隆:**
- `dial-mpc` — JAX生态, 与当前PyTorch栈不同
- `rl-mpc-locomotion` — 需Isaac Gym, 可参考Python MPC实现
- Awesome列表 — 作为资源发现入口

### 已评估未整合 (上轮)

| 项目 | 星数 | 原因 |
|------|------|------|
| unitreerobotics/unitree_ros2_to_real | 79★ | ROS2专用 |
| anujjain-dev/unitree-go2-ros2 | 218★ | Go2 ROS2，Go1不直接适用 |
| botbotrobotics/BotBrain | 104★ | 通用机器人框架，非Go1专用 |
| pietrodardano/RL_Dog | 28★ | Isaac Sim RL，Windows路径不兼容 |
| Bireflection/ai3603_legged_gym | 17★ | Isaac Gym课程作业 |
| gaiyi7788/awesome-legged-locomotion-learning | 470★ | 元资源列表(已从中发现GenLoco等) |
