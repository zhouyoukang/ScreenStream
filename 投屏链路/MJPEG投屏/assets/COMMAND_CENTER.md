# Command Center 架构索引

## 源文件（3个，全在本模块内）

| 文件 | 用途 | 说明 |
|------|------|------|
| `voice.html` | UI结构+CSS样式 | 纯HTML，不含JS逻辑，防止IDE格式化破坏 |
| `voice.js` | 全部交互逻辑 | 独立JS文件，5s仪表盘刷新+宏+功能面板 |
| `../mjpeg/internal/HttpServer.kt` | 服务端路由 | 改了2处：加载voice.js + GET路由 |

## 运行时数据（手机端）

| 数据 | 位置 | 说明 |
|------|------|------|
| 宏列表 | `/data/data/.../files/macros.json` | 10个预设宏，通过API创建 |

## 访问地址

- 手机本地：`http://<device-ip>:<port>/voice.html`（端口由 MJPEG 设置决定，默认 8081）
- PC端（ADB转发）：`http://127.0.0.1:<port>/voice.html`
- 端口探测：dev-deploy.ps1 会自动扫描 8080-8099

## 实时仪表盘（每5秒自动刷新）

- 电池% + 充电动画⚡ + 电池条
- 网络类型 + 连接状态
- 通知数量徽标
- 前台APP名称
- LIVE脉冲指示器 + 刷新计数器#N
- 最后操作反馈

## 功能分类（30+）

- **Device**: 设备详情/电池/通知/读屏幕/前台APP/应用列表/剪贴板
- **Navigation**: 桌面/返回/最近/通知栏/快捷设置
- **System**: 音量±/亮度±/手电筒/唤醒/锁屏/旋转/静音/截图/找手机
- **AI**: View树/关弹窗/窗口信息
- **Interactive**: 点击目标/输入文字/打开APP
- **Macros**: 10个预设宏自动加载

## 依赖的后端API（无需修改）

- `反向控制/输入路由/InputRoutes.kt`
- `反向控制/输入服务/InputService.kt`
- `反向控制/宏系统/MacroEngine.kt`
