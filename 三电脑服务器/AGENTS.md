# 三电脑服务器 Agent指令

## 目录用途
三机韧性架构的**唯一真相源** + **全景资源注册表** — 40+服务·11台设备·20个Dashboard的统一中枢。

## 快速启动
```powershell
python 三电脑服务器/resource_registry.py          # Portal :9000
python 三电脑服务器/resource_registry.py --probe   # CLI全景探测
.\三电脑服务器\台式机141\start_all_hubs.ps1 -List  # 查看Hub状态
.\三电脑服务器\台式机141\start_all_hubs.ps1 -All   # 启动全部Hub
```

## 关键约束
- **台式机141**: 白天8-23点在线，晚上断电
- **笔记本179**: 24h在线，偶尔重启
- **阿里云**: 基本永驻
- **资源注册表**: :9000 注册全部服务，Portal八卦Dashboard

## 修改规则
- 修改配置后必须同步到对应机器
- 新增Hub服务 → 同时更新 `resource_registry.py` REGISTRY + `start_all_hubs.ps1` HUBS
- 笔记本文件通过SMB: `\\192.168.31.179\E$\道\道生一\一生二\`
- 台式机frpc: `D:\道\道生一\一生二\远程桌面\frp\frpc.toml`
- 阿里云SSH: `ssh aliyun`

## 文件说明
| 文件 | 用途 | 部署位置 |
|------|------|---------|
| README.md | 架构全景文档 | 本地参考 |
| resource_registry.py | ★全景资源注册表+探测+API | 台式机141 :9000 |
| portal.html | ★统一Portal八卦Dashboard | 由registry serve |
| 笔记本179/Caddyfile | Caddy配置 | 179: E:\笔记本服务器\ |
| 笔记本179/watchdog.ps1 | 健康+自愈 | 179: E:\笔记本服务器\ |
| 笔记本179/frpc-laptop.toml | FRP客户端 | 179: E:\远程桌面\frp\ |
| 笔记本179/maintenance.html | 503维护页 | 179: E:\笔记本服务器\www\static\ |
| 台式机141/frpc-desktop.toml | FRP客户端 | 141: D:\远程桌面\frp\ |
| 台式机141/start_all_hubs.ps1 | ★一键启动全部Hub | 141本地执行 |
| 阿里云/nginx-routes.md | Nginx路由参考 | 只读参考 |
