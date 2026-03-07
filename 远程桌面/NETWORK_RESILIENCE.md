# 网络自愈体系 (Network Resilience)

> **核心理念**：利用多手机+多SIM卡+单PC+多Agent，构建四层防线，任何单点断连自动恢复。

## 架构总览

```
Layer 4: Agent互监心跳
  PC Guardian ←心跳→ Phone A (SS)
       ↕                ↕
  Phone B (SS) ←心跳→ Phone C (SS)
  → 任一Agent断线秒级感知

Layer 3: 公网隧道弹性
  Cloudflare Tunnel ← 进程监控 → 自动重启
  → 链路切换后隧道自动重建

Layer 2: 本地网络弹性 (PC↔手机)
  USB (最可靠) → WiFi (同路由器) → ADB over WiFi
  → 路由器挂了USB照样通

Layer 1: 互联网路径冗余 (PC→Internet)
  家庭宽带 → USB共享 → WiFi热点(不同运营商)
  → 宽带断了，手机4G/5G自动接管
```

## 资源清单

| 资源 | 角色 | 备注 |
|------|------|------|
| PC (Windows) | 协调中枢 | 运行Guardian守护进程 |
| 手机A (主力机) | 备份链路1 + USB共享 | 通过USB物理连接，最低延迟 |
| 手机B (副机) | 备份链路2 + WiFi热点 | 不同运营商SIM卡 |
| 手机C (备用机) | 备份链路3 + 最后防线 | 又一个运营商 |
| 家庭宽带 | 主链路 | 有线以太网/WiFi |
| 多张SIM卡 | 运营商冗余 | 移动/联通/电信 覆盖不同基站 |

## 文件清单

| 文件 | 功能 |
|------|------|
| `构建部署/network_guardian.py` | 核心守护进程：监控+切换+恢复+心跳 |
| `构建部署/phone_fleet.py` | 多手机舰队管理：扫描+评分+共享控制+诊断 |
| `构建部署/network_guardian_config.json` | 配置文件（首次运行自动生成） |
| `手机操控库/phone_lib.py` | 单机弹性层（已有：discover+heartbeat+recovery） |

## 快速开始

### 1. 首次配置（自动检测）

```powershell
cd 构建部署
python network_guardian.py --setup
```

自动检测：
- 网络适配器（以太网/WiFi/USB共享）
- ADB连接的手机（型号/运营商/SIM/电量）
- 互联网连通性
- Cloudflare Tunnel

生成 `network_guardian_config.json`，按需编辑。

### 2. 启动守护

```powershell
# 前台运行（推荐调试时用）
python network_guardian.py

# 后台守护
python network_guardian.py --daemon
```

### 3. 查看状态

```powershell
python network_guardian.py --status
python phone_fleet.py                  # 所有手机状态
python phone_fleet.py --diagnose       # 断网诊断
```

### 4. 手动操作

```powershell
python network_guardian.py --failover usb      # 切USB共享
python network_guardian.py --failover hotspot   # 切WiFi热点
python network_guardian.py --restore            # 恢复主链路

python phone_fleet.py --tether                 # 启用最优手机共享
python phone_fleet.py --stop-tether            # 关闭所有共享
```

## 自动切换流程

```
正常状态
  │
  ├─ 每5秒 ping 4个目标 (8.8.8.8, 1.1.1.1, 223.5.5.5, 119.29.29.29)
  │  → 至少2个通过 = 正常
  │
  ├─ 连续3次失败
  │  │
  │  ├─ 选最优手机（评分：电量>信号>连接方式>SIM>运营商）
  │  │
  │  ├─ 优先USB共享（延迟最低）
  │  │  ├─ ADB启用RNDIS
  │  │  ├─ Windows自动识别适配器
  │  │  ├─ 设置adapter metric: 备份=5, 主链路=9999
  │  │  └─ 验证 → 成功 = 切换完成
  │  │
  │  ├─ USB失败 → 尝试WiFi热点
  │  │  ├─ ADB启用热点
  │  │  ├─ 等待Windows连接
  │  │  └─ 验证 → 成功/失败
  │  │
  │  └─ 所有手机失败 → 错误状态，持续重试
  │
  └─ 备份模式中
     ├─ 继续监控备份链路
     ├─ 每30秒探测主链路恢复
     ├─ 主链路恢复 → 切回主链路
     │  ├─ 恢复adapter metric
     │  ├─ 关闭手机共享
     │  └─ 重启隧道
     └─ 备份也断 → 立即尝试其他手机
```

## 手机备份评分算法

| 维度 | 分值 | 逻辑 |
|------|------|------|
| 基础 | 50 | 所有手机起点 |
| 电量>50% | +20 | 高电量优先 |
| 电量20-50% | +10 | 中等 |
| 电量<10% | -20 | 低电量惩罚 |
| 充电中 | +5 | 不用担心电量 |
| USB连接 | +15 | 最可靠链路 |
| WiFi可达 | +10 | 次选 |
| SIM就绪 | +10 | 有移动数据能力 |
| 移动数据开启 | +10 | 可以共享 |
| 5G | +5 | 最快 |
| 4G/LTE | +3 | 够用 |
| 信号>-70dBm | +10 | 强信号 |
| 信号-85~-70 | +7 | 中等 |
| SS存活 | +5 | Agent可控 |

## 心跳服务

Guardian启动后在 `http://0.0.0.0:9800` 提供HTTP接口：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/heartbeat` | GET | 心跳响应 |
| `/status` | GET | 完整状态（含所有Agent） |
| `/agents` | GET | 所有已知Agent状态 |
| `/failover` | POST | 触发链路切换 `{"method":"usb"}` |
| `/restore` | POST | 恢复主链路 |

手机ScreenStream通过 `/status` 接口自动被探测，无需额外配置。

## 断网诊断

```powershell
python phone_fleet.py --diagnose
```

自动判断：

| PC | 手机4G | 诊断 | 建议 |
|----|--------|------|------|
| ✅ | ✅ | 一切正常 | - |
| ❌ | ✅ | PC宽带断，手机正常 | USB共享 或 重启路由器 |
| ❌ | ❌(WiFi) | 路由器/ISP故障 | 重启路由器→手机切4G共享→联系ISP |
| ❌ | ❌(全部) | 区域性断网 | 检查SIM→等待恢复 |
| ✅ | ❌ | 手机问题 | 检查手机WiFi/SIM |

## 配置说明

`network_guardian_config.json` 关键字段：

```jsonc
{
  "ping_targets": ["8.8.8.8", "1.1.1.1", "223.5.5.5", "119.29.29.29"],
  "ping_consensus": 2,        // 至少N个通过=正常
  "check_interval_sec": 5,    // 检测间隔
  "fail_threshold": 3,        // 连续N次失败才切换（防抖动）
  "recovery_check_sec": 30,   // 主链路恢复探测间隔
  "cooldown_sec": 60,         // 切换冷却期

  "phones": [
    {
      "name": "Samsung S23U",
      "serial": "",            // ADB序列号
      "tether_method": "usb",  // usb | hotspot
      "carrier": "移动",
      "priority": 1
    }
  ],

  "tunnel": {
    "enabled": false,          // 是否监控隧道
    "command": "cloudflared tunnel --url http://localhost:8080",
    "restart_on_failover": true
  },

  "heartbeat": {
    "enabled": true,
    "port": 9800
  }
}
```

## 与现有系统的关系

```
network_guardian.py (新)
  ├── 调用 phone_fleet.py 选最优手机
  ├── 管理 Windows 适配器优先级
  ├── 监控 cloudflared 进程
  └── HTTP 心跳服务 :9800

phone_fleet.py (新)
  ├── ADB 采集手机信息
  ├── 评分选最优备份
  └── 控制 USB共享/WiFi热点

phone_lib.py (已有，不修改)
  ├── 单机 discover() 多层探测
  ├── 心跳 + 负面状态恢复
  └── ScreenStream API 封装

remote-tunnel-setup.ps1 (已有，不修改)
  └── 手动启动 Cloudflare/FRP 隧道
```

## 注意事项

1. **管理员权限**：`Set-NetIPInterface` 修改适配器metric需要管理员权限
2. **USB共享兼容性**：不同手机品牌RNDIS支持不同，Samsung最好，OPPO/vivo可能需要手动开启
3. **热点密码**：默认热点密码 `guardian12345`，可在配置中修改
4. **流量消耗**：备份模式通过手机4G/5G，注意流量套餐
5. **ADB必需**：USB共享控制依赖ADB，确保手机开启USB调试
6. **多设备ADB**：多手机同时USB连接时，Guardian自动按序列号区分
