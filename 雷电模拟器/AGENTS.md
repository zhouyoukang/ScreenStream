# 雷电模拟器 · Agent操作手册

> 统一管理工作区13个手机相关项目的模拟器测试/开发/部署/验证全流程。

## 安装信息

| 项 | 值 |
|----|-----|
| 路径 | `D:\leidian\LDPlayer9\` |
| 版本 | 9.0.75.01 |
| ADB | `D:\leidian\LDPlayer9\adb.exe` |
| Console | `D:\leidian\LDPlayer9\dnconsole.exe` |
| 主机 | VT=1, RTX 4070 SUPER, Ryzen 7 9700X, 61.6GB RAM |

## VM虚拟机清单

| Index | 名称 | 型号 | 厂商 | 分辨率 | Root | ADB Serial | 角色 |
|-------|------|------|------|--------|------|------------|------|
| 0 | 雷电模拟器 | V1916A | vivo | 1920×1080@280 | ❌ | emulator-5554 | 通用主控 |
| 1 | 20241702221结束 | — | — | 540×960@240 | ❌ | — | 归档(跑步) |
| 2 | 2024170280320km | DLT-A0 | blackshark | 540×960@240 | ❌ | — | 归档(跑步) |
| 3 | 开发测试1 | V1824A | vivo | 540×960@240 | ✅ | emulator-5560 | SS-投屏主控 |
| 4 | 开发测试2 | PCLM10 | OPPO | 540×960@240 | ❌ | emulator-5562 | PWA-Web测试 |
| 5 | 开发测试 | NX629J | nubia | 540×960@240 | ❌ | emulator-5564 | 采集-自动化 |

## 项目 → 虚拟机映射 (13项目)

| 项目 | VM | 需SS | 关键端口 | 测试方式 |
|------|-----|------|---------|---------|
| ScreenStream | VM[3] | ✅ | 8080,8084 | APK构建→安装→投屏→Input API |
| 手机操控库 | VM[3] | ✅ | 8084 | PhoneLib Python→Input API |
| 公网投屏 | VM[3] | ✅ | 8080,8081 | MJPEG投屏→公网Relay |
| 亲情远程 | VM[3] | ✅ | 8080,8083,8084 | WebRTC P2P连接 |
| 手机软路由 | VM[3] | ❌ | 10808 | V2rayNG SOCKS5代理 |
| 二手书手机端 | VM[4] | ❌ | — | Chrome打开PWA |
| 电脑公网投屏手机 | VM[4] | ❌ | 9803 | Viewer端浏览器测试 |
| 智能家居 | VM[4] | ❌ | — | Web控制面板 |
| 微信公众号 | VM[4] | ❌ | — | Web面板测试 |
| 手机购物订单 | VM[5] | ✅ | 8084 | ADB UI自动化采集 |
| ORS6-VAM抖音同步 | VM[5] | ❌ | — | 抖音网页+节拍检测 |
| agent-phone-control | VM[5] | ✅ | 8084 | Agent远程操控 |

## 端口映射方案

```
VM[3] SS-投屏主控:
  localhost:18080 → emulator:8080 (Gateway)
  localhost:18084 → emulator:8084 (Input)
  localhost:18081 → emulator:8081 (MJPEG)
  localhost:18083 → emulator:8083 (WebRTC)

VM[4] PWA-Web测试:
  localhost:28080 → emulator:8080
  localhost:28084 → emulator:8084

VM[5] 采集-自动化:
  localhost:38080 → emulator:8080
  localhost:38084 → emulator:8084
```

## VM Controller — 浏览器MCP般操控VM

> **推荐**: 所有VM操作优先使用 `vm_controller.py`，提供与browser MCP对等的API。

### 核心命令 (浏览器MCP对照)

```powershell
# === 感知 (= browser_snapshot / take_screenshot) ===
python 雷电模拟器/vm_controller.py list                    # 列出所有VM (= list_pages)
python 雷电模拟器/vm_controller.py status                  # 全景状态
python 雷电模拟器/vm_controller.py snapshot 3              # UI快照 (= browser_snapshot)
python 雷电模拟器/vm_controller.py read 3                  # 屏幕文字
python 雷电模拟器/vm_controller.py screenshot 3            # 截屏 (= take_screenshot)
python 雷电模拟器/vm_controller.py info 3                  # VM详情 (= select_page)

# === 操作 (= browser_click / browser_type / browser_press_key) ===
python 雷电模拟器/vm_controller.py click 3 "设置"          # 点击 (= browser_click)
python 雷电模拟器/vm_controller.py tap 3 0.5 0.3           # 坐标点击
python 雷电模拟器/vm_controller.py type 3 "hello"          # 输入 (= browser_type)
python 雷电模拟器/vm_controller.py key 3 HOME              # 按键 (= browser_press_key)
python 雷电模拟器/vm_controller.py swipe 3 up              # 滑动
python 雷电模拟器/vm_controller.py back 3                  # 返回 (= browser_navigate_back)

# === 导航 (= browser_navigate) ===
python 雷电模拟器/vm_controller.py launch 3 com.android.chrome  # 启动APP
python 雷电模拟器/vm_controller.py url 3 "https://example.com"  # 打开URL
python 雷电模拟器/vm_controller.py shell 3 "ls /sdcard"         # shell (= browser_evaluate)
python 雷电模拟器/vm_controller.py wait 3 "登录成功" --timeout 10  # 等待文字

# === 运维 ===
python 雷电模拟器/vm_controller.py health 3                # 健康检查
python 雷电模拟器/vm_controller.py senses 3                # 五感采集
python 雷电模拟器/vm_controller.py apps 3                  # 已安装应用
python 雷电模拟器/vm_controller.py install 3 path.apk      # 安装APK
python 雷电模拟器/vm_controller.py forward 3               # 端口映射
python 雷电模拟器/vm_controller.py logcat 3 --filter SS    # 日志
```

### Python SDK (Agent直接import)

```python
from vm_client import vm, vm_for, fleet

# ★ 智能选择 (自动选开发测试VM, 永远不默认到VM[0]初始模拟器)
vm().snapshot()            # 自动选运行中的开发测试VM
vm().click("设置")         # 无需记忆index
vm().health()              # 健康检查

# ★ 项目感知路由
vm_for("ScreenStream").snapshot()    # → VM[3]
vm_for("手机购物订单").shell("ls")    # → VM[5]
vm_for("二手书手机端").read()         # → VM[4]

# 指定VM (需要精确控制时)
vm(3).snapshot()           # UI快照 (含可点击元素列表)
vm(3).read()               # 屏幕文字
vm(3).screenshot()         # 截屏保存到文件

# 操作
vm().click("设置")         # 点击元素
vm().tap(0.5, 0.3)        # 坐标点击
vm().type_text("hello")   # 输入文字
vm().key("ENTER")         # 按键
vm().swipe("up")          # 滑动

# 导航
vm().launch_app("com.android.chrome")
vm().open_url("https://example.com")
vm().shell("ls /sdcard")
vm().wait_for("登录成功", timeout=10)

# 运维
vm().health()              # 健康检查
vm().senses()              # 五感采集
fleet.list_all()           # 列出所有VM
fleet.status()             # 全景状态
fleet.dev_vm()             # 获取默认开发测试VM
fleet.vm_for("项目名")     # 项目感知选择
```

### 传统命令 (ld_manager.py, 仅管理用)

```powershell
python 雷电模拟器/ld_manager.py --status    # 全景状态
python 雷电模拟器/ld_manager.py --health     # 健康检查
python 雷电模拟器/ld_manager.py --ports setup # 端口映射
```

## Agent行为规则

0. **🔴 默认开发测试VM**: **禁止默认使用VM[0]初始模拟器**。无指定时自动选择"开发测试"VM(index 5/3/4)。用`vm()`无参数或`vm_for("项目名")`自动路由。
1. **优先vm_controller**: 所有VM操作优先使用vm_controller.py，提供browser MCP对等API
2. **优先模拟器**: 所有手机测试优先使用LDPlayer模拟器，不依赖实体机
3. **VM对应**: 严格按项目→VM映射表操作，不混用
4. **端口规范**: 使用规划的端口映射(18xxx/28xxx/38xxx)，避免冲突
5. **ADB路径**: 始终使用 `D:\leidian\LDPlayer9\adb.exe`，不用系统PATH的adb
6. **安装APK**: 模拟器用 `adb install -r -t`，无需OPPO的push+pm绕过
7. **SS限制**: 模拟器内SS的MediaProjection需手动授权(首次)；未授权时ss_alive=False但ss_partial=True
8. **Root**: VM[3]已开Root，可直接用于需要root的操作
9. **Android 9**: LDPlayer 9仅支持Android 9(API 28)，某些新API不可用
10. **x86_64**: 模拟器是x86_64架构，arm-only的APK无法安装
11. **三层降级**: ScreenStream API → ADB uiautomator → ADB shell (自动降级，无需Agent关心)
12. **多Agent安全**: 不同Agent可同时操控不同VM，各VMPhone实例独立无共享状态
