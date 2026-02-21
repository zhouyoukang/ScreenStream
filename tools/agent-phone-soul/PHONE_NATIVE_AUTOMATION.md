# 手机本地自动化方案（零外部依赖）

> Agent 不是核心需求。手机本身稳定运行自动化才是核心需求。
> Agent 只是一次性配置工具。配置完成后，手机独立运行。

## 设计原则

1. **离线可用**：无网络时所有核心功能正常
2. **零PC依赖**：手机单独就能完成一切
3. **跨品牌通用**：Samsung/OPPO/小米/华为/vivo 统一方案
4. **语音可触发**：用户说话即可操控
5. **状态可恢复**：任何异常后自动恢复到已知良好状态

## 跨品牌自动化入口映射

| 品牌 | 内置自动化 | 包名 | 状态 |
|------|-----------|------|------|
| Samsung | Bixby Routines | com.samsung.android.app.routines | ✅已验证 |
| OPPO/OnePlus | 智能侧边栏 | com.coloros.smartsidebar | 待验证 |
| 小米/Redmi | 场景 | com.xiaomi.smarthome | 待验证 |
| 华为/荣耀 | 智慧生活 | com.huawei.smarthome | 待验证 |
| vivo | Jovi | com.vivo.assistant | 待验证 |
| 通用 | MacroDroid | com.arlosoft.macrodroid | ✅已验证 |
| 通用 | Tasker | net.dinglisch.android.taskerm | ✅已验证 |

## 核心自动化模板（离线可用）

### 模板1：低电量自动省电
```
触发：电池 < 20%
动作：
  - 降低亮度到最低
  - 关闭WiFi（如不需要）
  - 关闭蓝牙
  - 关闭同步
  - 推送通知"已进入省电模式"
恢复触发：充电开始
恢复动作：恢复原始设置
```
**实现方式**：
- Shell脚本: `agent_battery_check.sh`（已注入双设备）
- Tasker: Battery Level trigger + Shell Command action
- Bixby Routines: 电池条件 + 多个动作

### 模板2：充电时勿扰
```
触发：开始充电 + 时间22:00-07:00
动作：
  - 开启勿扰模式
  - 降低媒体音量
恢复触发：拔电 或 时间07:00
恢复动作：关闭勿扰，恢复音量
```

### 模板3：快速启动常用APP
```
触发：语音指令 或 手势 或 快捷方式
动作：
  - "打开微信" → 启动 com.tencent.mm
  - "打开支付宝" → 启动 com.eg.android.AlipayGphone
  - "打开淘宝" → 启动 com.taobao.taobao
  - "打开地图" → 启动 com.autonavi.minimap
```
**实现方式**：直接创建桌面快捷方式 或 语音助手映射

### 模板4：定时健康提醒
```
触发：每2小时
动作：推送通知"休息一下，站起来活动"
条件约束：仅在 09:00-22:00
```

### 模板5：自动WiFi管理
```
触发A：离开家（WiFi断开）→ 关闭WiFi省电
触发B：到达家（检测到家庭WiFi）→ 自动连接
实现：地理围栏 或 WiFi SSID 匹配
```

## Shell脚本库（已注入，离线可用）

### agent_battery_check.sh（已部署到双设备）
```bash
#!/system/bin/sh
bat=$(dumpsys battery | grep level | tr -dc 0-9)
if [ $bat -lt 20 ]; then
  cmd notification post -S bigtext -t AgentAlert agent_low_bat "Battery low: ${bat}%"
fi
```

### agent_status_report.sh（待部署）
```bash
#!/system/bin/sh
bat=$(dumpsys battery | grep level | tr -dc 0-9)
mem=$(cat /proc/meminfo | grep MemAvailable | awk '{print int($2/1024)}')
temp=$(cat /sys/class/thermal/thermal_zone0/temp)
temp_c=$((temp/1000))
msg="Battery:${bat}% Mem:${mem}MB Temp:${temp_c}C"
cmd notification post -S bigtext -t "Status" agent_status "$msg"
```

### agent_silent_mode.sh（待部署）
```bash
#!/system/bin/sh
# 参数: on/off
if [ "$1" = "on" ]; then
  input keyevent KEYCODE_VOLUME_MUTE
  cmd notification post -S bigtext -t Agent agent_silent "Silent mode ON"
else
  input keyevent KEYCODE_VOLUME_MUTE
  cmd notification post -S bigtext -t Agent agent_silent "Silent mode OFF"
fi
```

## 语音触发方案

### 方案A：手机内置语音助手
- Samsung: "Hey Bixby, run routine [name]"
- 小米: "小爱同学, [指令]"
- OPPO: "小布小布, [指令]"
- 通用: Google Assistant Routines

### 方案B：Tasker AutoVoice 插件
- 自定义语音指令 → 触发Tasker任务
- 离线可用（本地语音识别）

### 方案C：快捷方式+Widget
- 桌面Widget一键触发
- 锁屏快捷方式
- 通知栏快捷按钮

## 稳定性保障

### 异常恢复机制
```
每次自动化执行前 → 记录当前状态快照
执行后 → 验证状态变化
异常 → 自动回滚到快照状态
```

### 持久化
- Shell脚本存储在 /sdcard/Download/agent/（不会被清理）
- Tasker/MacroDroid配置持久化在APP数据中
- Bixby Routines持久化在系统中

### 离线保障
所有核心自动化均在手机本地运行：
- Shell脚本：纯本地，零网络依赖
- Tasker/MacroDroid：本地引擎，零网络依赖
- Bixby Routines：系统级，零网络依赖
- 唯一需要网络的场景：云端AI推理（L2-L3任务）

## 迁移性

### 配置导出
```
Tasker: XML导出 → 新手机导入
MacroDroid: JSON导出 → 新手机导入
Shell脚本: 文件复制（ADB push）
Bixby Routines: Samsung账号同步
```

### Agent一键部署
Agent（配置阶段）→ 检测手机品牌 → 选择对应自动化入口 → 注入配置
→ 手机独立运行（运行阶段）

## 核心洞察

**Agent 是建筑师，不是管家。**
建筑师设计好房子就可以离开。管家需要一直在场。
我们要的是建筑师模式：一次配置，永久受益。

**手机是用户的，不是Agent的。**
所有自动化都应该"属于"手机，不是"依赖"Agent。
即使Agent永远不再出现，手机上的自动化仍然正常运行。
