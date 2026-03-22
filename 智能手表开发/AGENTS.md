# 智能手表开发

**设备**: VP99 华强北智能手表 · Android 8.1 · Unisoc展锐 K15 · 3GB RAM
**IP**: 192.168.31.41 · **序列号**: 10109530162925
**Hub**: http://localhost:8841 (watch_hub.py)

## 核心三件

| 文件 | 职责 |
|------|------|
| watch_hub.py | Hub中枢 :8841 — MacroDroid控制 + VNC探测 + 端口扫描 + REST API |
| watch_dashboard.html | 八卦Dashboard 8页SPA (Hub的 `/` 路由) |
| watch_breakthrough.py | ADB突破引擎 — 探测/物理操作指南/持续监控/ADB后自动配置 |

## 通道

| 通道 | 端口 | 状态 |
|------|------|------|
| MacroDroid HTTP | :8080 | ✅ `GET /{ha}?cmd=open_wechat` (8个命令) |
| USB MTP | USB | ✅ VID:1782 PID:4001 |
| VNC | :5900 | ⏳ 需手表启动DroidVNC-NG |
| ADB | :5555 | ❌ HSC固件屏蔽开发者模式 |

## MacroDroid命令

`open_wechat` `open_alipay` `open_taobao` `open_doubao` `open_amap` `open_mijia` `mute` `vibrate`

## Hub API

```
GET /                          Dashboard
GET /api/health                健康检查
GET /api/status                快速状态
GET /api/sense                 全景感知(八卦评分)
GET /api/device                设备档案
GET /api/apps                  已安装应用
GET /api/commands              可用命令列表
GET /api/macrodroid/health     MacroDroid健康
GET /api/macrodroid/logs?n=100 系统日志
GET /api/macrodroid/wifi       WiFi扫描
GET /api/macrodroid/macros     宏活动
GET /api/vnc/probe             VNC探测
GET /api/ports                 TCP端口扫描
GET /api/cmd?cmd=X             执行命令
GET /api/breakthrough          突破路径状态
```

## ADB突破 (优先级)

1. Activity Launcher — Play商店安装→打开DevelopmentSettings (3分钟)
2. 拨号码 `*#*#592411#*#*` (30秒)
3. 佰佑通APP BLE配对 (5分钟)
4. VNC远控→手动开发者选项
5. SPD深刷 spd_dump (高级)

运行 `python watch_breakthrough.py --guide` 查看完整指南

## 约束

- 开发者模式被HSC固件屏蔽 (版本号点击14次无反应)
- 展锐WCN子系统有WiFi Assert崩溃 (偶尔断连)
- MacroDroid需ADB授权: `pm grant com.arlosoft.macrodroid android.permission.WRITE_SECURE_SETTINGS`
