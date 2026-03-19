# 手机卡共享 · Agent指令

## 快速命令
```bash
python 05-整合中枢/sim_share_hub.py              # 启动中枢 :8890
python 05-整合中枢/sim_share_hub.py --scan        # 扫描所有设备
python 05-整合中枢/sim_share_hub.py --status      # 查看状态
.\05-整合中枢\deploy.ps1                          # 一键部署(检查+启动)
→一键部署.cmd                                     # 双击启动
```

## 文件清单
| 文件 | 职责 |
|------|------|
| `README.md` | 总纲·八卦架构·设备矩阵 |
| `_AGENT_GUIDE.md` | Agent操作指令(本文件) |
| `方案总览.md` | 8种方案对比·3条推荐路径 |
| `→一键部署.cmd` | 双击启动中枢 |
| `01-短信共享/README.md` | ☷坤·SmsForwarder+合宙硬件+SMS Gateway |
| `02-电话共享/README.md` | ☰乾·呼叫转移+eSIM+VoIP+Asterisk |
| `03-流量共享/README.md` | ☲离·热点+V2Ray+USB+NetShare |
| `04-硬件方案/README.md` | ☵坎·合宙Air780E+osmo-remsim+eSIM+蓝牙SIM |
| `05-整合中枢/sim_share_hub.py` | ★核心中枢(:8890) Webhook+MQTT+Dashboard |
| `05-整合中枢/config.py` | 设备配置(主卡机+4台从机) |
| `05-整合中枢/deploy.ps1` | 一键部署脚本(ADB检查+端口转发+启动) |
| `05-整合中枢/sms_monitor.py` | ADB SMS/Call实时监控器(零配置零UI) |
| `05-整合中枢/sim_share_app.html` | ★PWA移动端8Tab应用(脱离PC/公网穿透) |
| `06-开源资源/README.md` | ☱兑·50+开源项目索引 |

## API端点 (:8890)
| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/` | Dashboard |
| GET | `/api/health` | 健康检查 |
| GET | `/api/status` | 全状态(设备+短信+来电) |
| GET | `/api/probe` | 探测所有设备 |
| GET | `/api/sms/history` | 短信历史 |
| GET | `/api/call/history` | 来电历史 |
| GET | `/api/devices` | 设备列表 |
| POST | `/api/sms` | SmsForwarder Webhook接收 |
| POST | `/api/call` | 来电通知Webhook |
| POST | `/api/send_sms` | 远程发短信(via主卡机ADB) |

## 修改规则
- 新增方案须更新 `方案总览.md`
- 新增脚本须更新本文件文件表
- 涉及凭据用 `secrets.env` 管理
- 端口8890固定，禁止冲突
