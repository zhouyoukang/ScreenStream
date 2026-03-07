# ❓ 常见问题解答 (FAQ)

## 📋 目录

- [安装和部署](#安装和部署)
- [配置问题](#配置问题)
- [设备控制](#设备控制)
- [场景和自动化](#场景和自动化)
- [性能问题](#性能问题)
- [移动端访问](#移动端访问)
- [AI功能](#ai功能)
- [错误排查](#错误排查)

---

## 安装和部署

### Q: 如何安装这个移动端UI？

**A**: 按照以下步骤：

1. 复制配置文件到HA配置目录
```bash
cp mobile-dashboard-enhanced.yaml /config/lovelace/
```

2. 通过HA UI添加dashboard
```
设置 → 仪表板 → 添加仪表板 → 从YAML创建
路径: /config/lovelace/mobile-dashboard-enhanced.yaml
```

3. 刷新浏览器

详细步骤见 [DEPLOYMENT_GUIDE_TESTED.md](DEPLOYMENT_GUIDE_TESTED.md)

---

### Q: 安装后Dashboard显示空白怎么办？

**A**: 可能的原因和解决方法：

1. **YAML语法错误**
   ```bash
   # 检查配置
   开发者工具 → YAML → 检查配置
   ```

2. **文件路径错误**
   - 确保文件在正确位置
   - 检查路径拼写

3. **缓存问题**
   ```bash
   Ctrl + Shift + R  # Windows
   Cmd + Shift + R   # Mac
   ```

4. **查看日志**
   ```bash
   设置 → 系统 → 日志
   搜索: "lovelace"
   ```

---

### Q: 需要安装哪些集成？

**A**: 必需集成：

**核心**（必须）:
- ✅ Mushroom Cards（HACS）
- ✅ Card Mod（HACS）
- ✅ 你的设备集成（Sonoff, EcoFlow等）

**可选**（增强功能）:
- ⚠️ MiGPT（AI功能）
- ⚠️ System Monitor（性能监控）
- ⚠️ Speedtest（网速测试）

安装指南：[INTEGRATION_INSTALLATION_GUIDE.md](INTEGRATION_INSTALLATION_GUIDE.md)

---

## 配置问题

### Q: Entity ID和我的不一样怎么办？

**A**: 需要替换为你的entity ID：

1. **查找你的entity**
   ```bash
   开发者工具 → 状态 → 搜索设备名称
   ```

2. **替换配置文件中的entity_id**
   ```yaml
   # 查找
   switch.sonoff_10022dede9_1
   # 替换为
   switch.YOUR_SWITCH_ID
   ```

3. **批量替换（Linux/Mac）**
   ```bash
   sed -i 's/OLD_ENTITY/NEW_ENTITY/g' mobile-dashboard-enhanced.yaml
   ```

---

### Q: 如何自定义颜色和图标？

**A**: 编辑YAML配置：

**修改图标**:
```yaml
icon: mdi:lightbulb  # 改为你想要的图标
# 图标库: https://materialdesignicons.com/
```

**修改颜色**:
```yaml
icon_color: green  # 改为: red, blue, amber等
# 或使用条件:
icon_color: >-
  {{ 'green' if is_state('switch.xxx', 'on') else 'grey' }}
```

---

### Q: 如何添加新设备到Dashboard？

**A**: 在合适位置添加卡片：

```yaml
# 在设备控制区域添加
- type: custom:mushroom-entity-card
  entity: switch.NEW_DEVICE  # 你的entity
  name: 新设备
  icon: mdi:device-icon
  tap_action:
    action: toggle
```

重新加载dashboard即可。

---

## 设备控制

### Q: 点击设备按钮没有反应？

**A**: 检查以下几点：

1. **Entity是否存在**
   ```bash
   开发者工具 → 状态 → 搜索entity
   ```

2. **Entity是否可用**
   - 状态不应该是"unavailable"或"unknown"

3. **设备是否在线**
   - 检查设备连接状态
   - 重启设备

4. **查看日志**
   ```bash
   设置 → 系统 → 日志
   # 查找错误信息
   ```

---

### Q: 设备状态更新延迟？

**A**: 可能原因：

1. **轮询间隔**
   - 某些集成更新较慢
   - 等待1-5秒

2. **网络延迟**
   - 检查Wi-Fi信号
   - 靠近路由器测试

3. **集成问题**
   ```bash
   # 重新加载集成
   设置 → 设备与服务 → 集成 → 重新加载
   ```

**优化方法**:
- 使用WebSocket（HA默认）
- 减少轮询集成
- 升级网络设备

---

### Q: "全部关闭"按钮不能关闭所有设备？

**A**: 检查配置：

```yaml
# 确保包含所有要关闭的entity
service_data:
  entity_id:
    - switch.device1
    - switch.device2
    - switch.device3
    # 添加所有设备
```

或使用区域：
```yaml
service_data:
  area_id: living_room
```

---

## 场景和自动化

### Q: 场景按钮点击后没有执行？

**A**: 排查步骤：

1. **Script是否存在**
   ```bash
   开发者工具 → 服务
   搜索: script.home_mode
   # 应该能找到
   ```

2. **手动测试Script**
   ```bash
   开发者工具 → 服务
   服务: script.turn_on
   目标: script.home_mode
   点击"调用服务"
   ```

3. **查看scripts.yaml**
   ```yaml
   # 确保包含scene定义
   home_mode:
     sequence:
       - service: switch.turn_on
         target:
           entity_id: switch.xxx
   ```

4. **重新加载Scripts**
   ```bash
   开发者工具 → YAML → 重新加载脚本
   ```

---

### Q: 如何创建新的场景模式？

**A**: 步骤：

1. **编辑scripts.yaml**
   ```yaml
   my_custom_scene:
     alias: 我的自定义场景
     sequence:
       - service: switch.turn_on
         target:
           entity_id: switch.device1
       - service: light.turn_on
         target:
           entity_id: light.device2
         data:
           brightness: 128
   ```

2. **重新加载scripts**

3. **添加到Dashboard**
   ```yaml
   - type: custom:mushroom-template-card
     primary: 我的场景
     icon: mdi:star
     icon_color: yellow
     tap_action:
       action: call-service
       service: script.turn_on
       service_data:
         entity_id: script.my_custom_scene
   ```

---

### Q: 场景执行时间太长？

**A**: 优化方法：

1. **使用并行执行**
   ```yaml
   sequence:
     - parallel:
         - service: switch.turn_on
           target:
             entity_id: switch.device1
         - service: switch.turn_on
           target:
             entity_id: switch.device2
   ```

2. **减少延迟**
   ```yaml
   # 移除不必要的delay
   - delay: 00:00:02  # 删除或减少
   ```

3. **检查设备响应**
   - 某些设备响应慢
   - 考虑更换或优化

---

## 性能问题

### Q: Dashboard加载很慢？

**A**: 优化建议：

1. **减少entity数量**
   - 只显示常用设备
   - 移除不用的卡片

2. **优化图片和资源**
   - 压缩图标
   - 减少自定义样式

3. **使用条件显示**
   ```yaml
   - type: conditional
     conditions:
       - entity: xxx
         state: 'on'
     card:
       # 只在条件满足时显示
   ```

4. **清除缓存**
   ```bash
   Ctrl + Shift + Delete
   # 清除所有缓存和cookie
   ```

目标: <2秒加载时间

---

### Q: 手机上很卡顿？

**A**: 移动端优化：

1. **使用enhanced而非optimized版本**
   - enhanced版本已优化移动端

2. **减少动画**
   ```yaml
   # 移除复杂的card_mod样式
   # 简化动画效果
   ```

3. **关闭后台应用**
   - 释放内存
   - 提升性能

4. **使用原生App**
   - Home Assistant Companion App
   - 性能更好

---

### Q: 电池消耗太快？

**A**: 省电技巧：

1. **减少更新频率**
   ```yaml
   # 配置中减少轮询
   scan_interval: 60  # 增加间隔
   ```

2. **使用PWA而非浏览器**
   - 添加到主屏幕
   - 后台更节能

3. **关闭不用的集成**
   - 禁用实时更新
   - 按需开启

4. **降低屏幕亮度**
   - 使用夜间模式
   - 自动亮度

---

## 移动端访问

### Q: 如何在手机上访问？

**A**: 三种方式：

**方式1: 浏览器访问**
```
http://YOUR_HA_IP:8123
# 或 https://YOUR_DOMAIN
```

**方式2: PWA安装**
```
浏览器 → 菜单 → 添加到主屏幕
```

**方式3: 官方App**
```
下载: Home Assistant Companion
iOS: App Store
Android: Google Play
```

推荐使用PWA或App。

---

### Q: 外网无法访问？

**A**: 配置远程访问：

**选项1: Nabu Casa（推荐）**
- 最安全简单
- $6.5/月
- 自动HTTPS

**选项2: VPN**
- WireGuard
- OpenVPN
- 安全稳定

**选项3: DuckDNS + Let's Encrypt**
- 免费
- 需要配置

**不推荐**:
- ❌ 直接端口转发（不安全）

---

### Q: PWA安装后没有图标？

**A**: 检查：

1. **manifest.json**
   - 确保配置正确

2. **HTTPS必需**
   - PWA需要HTTPS
   - 配置SSL证书

3. **浏览器兼容性**
   - Chrome/Edge: ✅
   - Safari: ✅
   - Firefox: ⚠️ 部分支持

4. **重新安装**
   - 卸载PWA
   - 清除缓存
   - 重新添加

---

## AI功能

### Q: AI助手页面显示"离线"？

**A**: 检查：

1. **MiGPT集成是否安装**
   ```bash
   设置 → 设备与服务 → 集成
   查找: MiGPT
   ```

2. **服务是否运行**
   ```bash
   # 检查entity状态
   binary_sensor.migpt_service_status
   # 应该是"on"
   ```

3. **重启MiGPT**
   ```bash
   # 在集成页面重启
   # 或重启Home Assistant
   ```

如果未安装，可以隐藏AI页面或安装MiGPT。

---

### Q: 语音命令不工作？

**A**: 排查：

1. **小爱音箱配置**
   - 确保已绑定
   - 网络连接正常

2. **MiGPT配置**
   - API密钥正确
   - 服务运行中

3. **测试简单命令**
   - "打开灯"
   - "关闭灯"

4. **查看日志**
   ```bash
   # 查看MiGPT日志
   # 找到错误原因
   ```

---

### Q: 如何添加自定义语音命令？

**A**: 配置MiGPT：

1. **编辑MiGPT配置**
2. **添加intent**
3. **关联service**
4. **测试命令**

具体配置参考MiGPT文档。

---

## 错误排查

### Q: "Entity not found"错误？

**A**: 解决方案：

1. **检查entity是否存在**
   ```bash
   开发者工具 → 状态 → 搜索
   ```

2. **Entity ID拼写**
   - 区分大小写
   - 检查下划线和点

3. **集成是否加载**
   ```bash
   设置 → 设备与服务
   # 确保集成正常
   ```

4. **移除或替换**
   - 如果entity确实不存在
   - 从配置中移除
   - 或替换为其他entity

---

### Q: "Invalid config"错误？

**A**: YAML语法检查：

1. **使用在线验证**
   - https://www.yamllint.com/

2. **检查缩进**
   - 使用空格，不要Tab
   - 保持一致缩进

3. **检查特殊字符**
   - 引号是否匹配
   - 冒号后有空格

4. **逐步回滚**
   - 注释新增部分
   - 找到问题行

---

### Q: 功耗/电量显示为0或unavailable？

**A**: 检查传感器：

1. **设备是否在线**
   - 检查Sonoff/EcoFlow连接

2. **集成状态**
   ```bash
   设置 → 设备与服务
   # 查看集成错误
   ```

3. **重新加载集成**
   ```bash
   # 点击集成 → 重新加载
   ```

4. **查看entity历史**
   ```bash
   # 开发者工具 → 状态
   # 点击entity查看历史
   ```

---

## 🔍 还有问题？

### 获取帮助的步骤

1. **查看文档**
   - [用户指南](USER_GUIDE.md)
   - [部署指南](DEPLOYMENT_GUIDE_TESTED.md)
   - [性能优化](PERFORMANCE_REALITY.md)

2. **检查日志**
   ```bash
   设置 → 系统 → 日志
   # 复制错误信息
   ```

3. **搜索社区**
   - Home Assistant中文论坛
   - GitHub Issues
   - Discord

4. **提供信息**
   - HA版本
   - 错误信息
   - 配置片段
   - 重现步骤

---

## 💡 提示

**记住**：
- 📖 先查文档
- 🔍 查看日志
- 🧪 隔离测试
- 📝 记录步骤
- 🤝 寻求帮助

**大部分问题都可以通过查看日志解决！**

---

**祝你使用顺利！** 🎉
