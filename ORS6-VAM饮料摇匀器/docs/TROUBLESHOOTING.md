# 常见问题排查

## 连接问题

### ESP32无法识别

**症状**: 设备管理器看不到COM口

**排查**:

1. 确认USB线是**数据线** (非纯充电线)
2. 安装驱动:
   - CP210x: [Silicon Labs](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers)
   - CH340: [WCH](http://www.wch.cn/download/CH341SER_EXE.html)
3. 换USB口 (优先使用主板直连口)
4. 检查ESP32 LED是否亮起

### 串口连接失败

```python
# 列出所有可用端口
python tools/servo_test.py --list-ports

# 指定端口测试
python tools/servo_test.py -p COM5 -i
```

### WiFi连接不上

1. ESP32首次启动会创建WiFi AP: `TCode_xxxxx`
2. 连接后配置WiFi: `192.168.4.1`
3. 确认电脑和ESP32在同一局域网
4. 防火墙放行UDP端口8000

## 运动问题

### 舵机不动

1. 检查电源 (5V 10A+，舵机需要大电流)
2. 检查舵机信号线连接
3. 发送 `D2` 查询设备信息
4. 发送 `L05000I2000` 测试单轴

### 舵机抖动/噪音

1. 电源不足 — 升级电源功率
2. 舵机齿轮磨损 — 更换舵机
3. 信号线干扰 — 远离电源线
4. PWM频率不匹配 — 检查固件配置

### 运动方向反了

```python
# 使用校准工具
python tools/calibrate.py -p COM5

# 或在VaM桥接配置中反转
config = BridgeConfig(invert_axes=["L0", "R0"])
```

### 行程范围不对

1. 固件Web配置页调整轴范围
2. 校准工具: `python tools/calibrate.py`
3. VaM桥接: 调整 `position_scale`

## VaM集成问题

### ToySerialController找不到串口

1. 确认VaM以管理员权限运行
2. 关闭其他占用串口的程序
3. 重启VaM

### VaM动作延迟大

1. 使用USB Serial (最低延迟)
2. VaM设置: 降低物理帧率
3. 增加ToySerialController平滑值
4. WiFi模式: 使用5GHz频段

### AgentBridge连接失败

1. 确认AgentBridge插件加载 (VaM日志检查)
2. 确认端口8084可访问: `curl http://127.0.0.1:8084/api/v1/health`
3. 防火墙放行

## Funscript问题

### 脚本加载失败

1. 检查JSON格式 (用编辑器验证)
2. 确认文件编码为UTF-8
3. 检查actions数组不为空

### 多轴不同步

1. 确认文件命名正确:
   - `video.funscript` (L0)
   - `video.surge.funscript` (L1)
   - `video.twist.funscript` (R0)
2. 检查所有文件时间线一致

---

## 更多资源

- [GITHUB_RESOURCES.md](GITHUB_RESOURCES.md) — GitHub生态资源索引
- [EROSCRIPTS_RESOURCES.md](EROSCRIPTS_RESOURCES.md) — EroScripts社区资源 (设备/播放器/工具/硬件购买)
- [TCODE_REFERENCE.md](TCODE_REFERENCE.md) — TCode协议参考
- [EroScripts论坛](https://discuss.eroscripts.com) — 社区技术支持
