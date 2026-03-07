# 🔧 故障排查指南 - Troubleshooting Guide

## 📋 快速诊断

遇到问题时，按照以下顺序检查：

1. ✅ **Dashboard能否打开** → 基础连接问题
2. ✅ **Entity是否显示** → 实体可用性问题
3. ✅ **功能能否使用** → 配置或权限问题
4. ✅ **性能是否正常** → 优化问题

---

## 🚨 常见问题诊断树

### 问题1: Dashboard完全无法加载

**症状**: 
- 白屏或空白页面
- 浏览器显示错误
- 无限加载

**诊断步骤**:

```
1. 检查Home Assistant是否运行
   → 浏览器访问: http://YOUR_HA_IP:8123
   → 能访问首页？
      ✅ 是 → 继续步骤2
      ❌ 否 → 问题A: HA服务未运行

2. 检查Dashboard配置
   → 开发者工具 → YAML → 检查配置
   → 有错误？
      ✅ 无错误 → 继续步骤3
      ❌ 有错误 → 问题B: YAML语法错误

3. 检查浏览器控制台
   → F12 → Console → 查看错误
   → 有JavaScript错误？
      ✅ 无错误 → 继续步骤4
      ❌ 有错误 → 问题C: 自定义组件问题

4. 清除缓存
   → Ctrl + Shift + R (强制刷新)
   → 问题解决？
      ✅ 是 → 完成
      ❌ 否 → 问题D: 配置文件位置错误
```

#### 问题A: HA服务未运行

**原因**: Home Assistant进程停止或崩溃

**解决方案**:
```bash
# 检查服务状态
systemctl status home-assistant

# 启动服务
systemctl start home-assistant

# 查看日志
journalctl -u home-assistant -f
```

#### 问题B: YAML语法错误

**原因**: 配置文件语法不正确

**解决方案**:
1. 使用YAML验证器: https://www.yamllint.com/
2. 检查常见错误:
   - ❌ 使用Tab缩进 → ✅ 改用空格
   - ❌ 冒号后没有空格 → ✅ 添加空格
   - ❌ 引号不匹配 → ✅ 检查引号
3. 查看HA日志定位错误行:
   ```bash
   # 配置 → 系统 → 日志
   # 搜索: "Invalid config"
   ```

#### 问题C: 自定义组件问题

**原因**: Mushroom Cards或Card Mod未安装

**解决方案**:
```bash
# 检查HACS是否已安装
配置 → HACS → 前端

# 必需组件:
1. Mushroom Cards
2. Card Mod

# 安装方法:
HACS → 前端 → 搜索 → 安装 → 重启HA
```

#### 问题D: 配置文件位置错误

**原因**: Dashboard配置文件路径不对

**解决方案**:
1. 确认文件位置:
   ```
   /config/lovelace/mobile-dashboard-enhanced.yaml
   ```
2. 在HA中添加Dashboard:
   ```
   配置 → 仪表板 → 添加仪表板
   → 使用YAML配置
   → 路径: /config/lovelace/mobile-dashboard-enhanced.yaml
   ```

---

### 问题2: Entity显示"不可用"

**症状**:
- 卡片显示灰色
- 提示"unavailable"或"unknown"
- 功能无法使用

**诊断步骤**:

```
1. 检查Entity是否存在
   → 开发者工具 → 状态 → 搜索entity_id
   → 能找到？
      ✅ 是 → 继续步骤2
      ❌ 否 → 问题E: Entity不存在

2. 检查Entity状态
   → 状态是"unavailable"？
      ✅ 是 → 问题F: 设备离线
      ❌ 否，是"unknown" → 问题G: 集成配置错误

3. 检查集成状态
   → 配置 → 设备与服务 → 查看集成
   → 集成正常？
      ✅ 是 → 问题H: 临时通信问题
      ❌ 否 → 问题I: 集成需重新配置
```

#### 问题E: Entity不存在

**原因**: 配置中使用的entity_id在系统中不存在

**解决方案**:

**方法1**: 查找正确的entity_id
```bash
# 开发者工具 → 状态 → 搜索设备名称
# 例如: 搜索"灯"找到 light.bedroom_light

# 替换配置中的entity_id
entity: switch.sonoff_10022dede9_1
# 改为你的
entity: light.bedroom_light
```

**方法2**: 使用验证脚本
```bash
python check-minimal-entities.py
# 会列出所有不存在的entity
```

**方法3**: 移除不存在的entity
```yaml
# 从配置文件中删除或注释掉
# - entity: switch.non_existent_device
```

#### 问题F: 设备离线

**原因**: 物理设备断电、断网或故障

**解决方案**:
1. **检查设备供电**
   - 确认设备已接电
   - 检查电源开关

2. **检查网络连接**
   - 设备是否在同一网络
   - Wi-Fi信号是否正常
   - 路由器是否正常

3. **重启设备**
   - 断电等待10秒
   - 重新上电
   - 等待设备启动（30-60秒）

4. **重新配对**（如果重启无效）
   - 删除集成
   - 重新添加设备
   - 按照配对流程操作

#### 问题G: 集成配置错误

**原因**: 集成配置不完整或错误

**解决方案**:
```bash
1. 重新加载集成
   配置 → 设备与服务 → 选择集成 → ⋮ → 重新加载

2. 检查集成配置
   配置 → 设备与服务 → 选择集成 → 配置
   → 检查IP地址、密码等

3. 查看集成日志
   配置 → 系统 → 日志 → 搜索集成名称
   → 查找错误信息

4. 重新配置集成
   → 删除集成
   → 重新添加
   → 重新配置参数
```

#### 问题H: 临时通信问题

**原因**: 网络抖动或设备暂时无响应

**解决方案**:
```bash
# 等待几分钟自动恢复
# 或强制刷新
开发者工具 → 服务 → homeassistant.reload_config_entry
```

---

### 问题3: 场景脚本不执行

**症状**:
- 点击场景按钮无反应
- 场景执行但设备没变化
- 日志显示错误

**诊断步骤**:

```bash
1. 检查Script是否存在
   → 开发者工具 → 服务 → 搜索"script.xxx"
   → 能找到？
      ✅ 是 → 继续步骤2
      ❌ 否 → 问题J: Script未定义

2. 手动测试Script
   → 开发者工具 → 服务
   → 服务: script.turn_on
   → 目标: script.home_mode
   → 调用服务
   → 有反应？
      ✅ 是 → 问题K: Dashboard配置问题
      ❌ 否 → 问题L: Script逻辑错误

3. 检查设备权限
   → 配置 → 用户 → 查看权限
   → 有控制权限？
      ✅ 是 → 继续步骤4
      ❌ 否 → 问题M: 权限不足

4. 查看执行日志
   → 配置 → 系统 → 日志
   → 搜索脚本名称
   → 有错误？
      ✅ 无 → 完成
      ❌ 有 → 根据错误信息处理
```

#### 问题J: Script未定义

**原因**: scripts.yaml中没有定义该脚本

**解决方案**:
```yaml
# 编辑 scripts.yaml
home_mode:
  alias: 回家模式
  sequence:
    - service: switch.turn_on
      target:
        entity_id: switch.sonoff_10022dede9_1

# 重新加载
开发者工具 → YAML → 重新加载脚本
```

#### 问题K: Dashboard配置问题

**原因**: Dashboard中的service调用配置错误

**解决方案**:
```yaml
# 检查配置
tap_action:
  action: call-service
  service: script.turn_on  # 正确
  service_data:
    entity_id: script.home_mode  # entity_id正确

# 常见错误:
# ❌ service: script.home_mode  # 错误
# ✅ service: script.turn_on   # 正确
```

#### 问题L: Script逻辑错误

**原因**: Script中的服务调用或entity_id错误

**解决方案**:
```yaml
# 检查scripts.yaml
home_mode:
  sequence:
    # 确保entity_id存在
    - service: switch.turn_on
      target:
        entity_id: switch.EXISTING_ENTITY  # 必须存在

    # 使用条件检查
    - condition: state
      entity_id: switch.xxx
      state: 'off'
    - service: switch.turn_on
      target:
        entity_id: switch.xxx
```

---

### 问题4: Dashboard加载很慢

**症状**:
- 打开dashboard需要5秒以上
- 切换视图卡顿
- 手机上特别慢

**诊断步骤**:

```bash
1. 检查entity数量
   → 开发者工具 → 状态
   → entity总数？
      < 100 → 正常，继续步骤2
      100-500 → 较多，考虑优化
      > 500 → 过多，需要优化

2. 检查网络速度
   → 测试延迟: ping HA服务器
   → 延迟多少？
      < 50ms → 正常
      50-200ms → 较慢
      > 200ms → 很慢，需优化网络

3. 检查设备性能
   → 在电脑上测试
   → 电脑上快吗？
      ✅ 快 → 问题N: 移动端性能
      ❌ 慢 → 问题O: 服务器或配置性能

4. 检查浏览器
   → 使用Chrome测试
   → Chrome快吗？
      ✅ 快 → 问题P: 浏览器兼容性
      ❌ 慢 → 配置问题
```

#### 问题N: 移动端性能

**原因**: 移动设备性能较低

**解决方案**:
```yaml
# 使用minimal版本
mobile-dashboard-minimal.yaml

# 或优化enhanced版本:
1. 移除不常用的卡片
2. 减少动画效果
3. 使用条件显示
4. 关闭自动刷新
```

#### 问题O: 服务器或配置性能

**原因**: HA服务器负载高或配置复杂

**解决方案**:
```bash
# 1. 检查服务器负载
# CPU使用率
配置 → 系统监控 → CPU使用率

# 2. 优化配置
# 减少不必要的entity
# 禁用不用的集成
# 清理历史数据

# 3. 升级硬件
# 增加内存
# 使用SSD
```

#### 问题P: 浏览器兼容性

**原因**: 浏览器版本过旧或不兼容

**解决方案**:
```bash
# 推荐浏览器:
✅ Chrome/Edge (最佳)
✅ Safari (iOS)
⚠️ Firefox (部分功能可能有问题)
❌ IE (不支持)

# 更新浏览器到最新版本
```

---

## 🔍 高级诊断工具

### 工具1: Entity验证脚本

```bash
# 检查所有entity是否存在
python check-minimal-entities.py

# 输出:
# ✓ 正常: X个
# ✗ 不存在: Y个
# ⚠ 不可用: Z个
```

### 工具2: 场景测试脚本

```bash
# 测试所有场景脚本
python test-scene-scripts.py

# 输出:
# 每个脚本的执行时间
# 设备状态变化
# 错误信息
```

### 工具3: HA日志分析

```bash
# 实时查看日志
配置 → 系统 → 日志

# 过滤技巧:
# 搜索"error" - 查找所有错误
# 搜索"warning" - 查找警告
# 搜索entity_id - 查找特定设备问题
```

---

## 📝 诊断信息收集

寻求帮助时，请提供以下信息：

```markdown
### 环境信息
- HA版本: 
- 安装方式: (HAOS/Container/Core)
- 操作系统: 
- Dashboard版本: (minimal/enhanced)

### 问题描述
- 问题现象: 
- 出现时间: 
- 重现步骤: 
- 错误信息: 

### 已尝试的解决方法
- 

### 相关配置
```yaml
# 粘贴相关配置片段
```

### 日志信息
```
# 粘贴相关日志
```
```

---

## 🆘 获取帮助

### 自助资源
1. [用户指南](USER_GUIDE.md)
2. [FAQ](FAQ.md)
3. [配置示例](CONFIGURATION_EXAMPLES.md)

### 社区支持
1. Home Assistant中文论坛
2. GitHub Issues
3. Discord频道

### 提问技巧
- ✅ 描述清楚问题现象
- ✅ 提供完整的错误信息
- ✅ 说明已尝试的方法
- ✅ 附上相关配置
- ❌ 不要只说"不工作"

---

## 💡 预防措施

### 定期维护
```bash
# 每周
- 检查日志错误
- 清理过期数据
- 更新集成

# 每月
- 备份配置
- 检查设备状态
- 更新HA版本

# 重要操作前
- 备份配置
- 测试环境验证
- 准备回滚方案
```

### 最佳实践
1. **渐进式添加** - 一次添加一个功能，测试后再继续
2. **版本控制** - 使用Git管理配置
3. **定期备份** - 使用自动备份脚本
4. **文档记录** - 记录修改和原因

---

**记住**: 90%的问题都可以通过查看日志解决！🔍

Happy troubleshooting! 🛠️
