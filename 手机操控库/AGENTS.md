# 手机操控库 · Agent公网全掌控

## 身份
phone_lib.py是唯一ADB/连接真理源。90+ SS HTTP API封装+认知系统Hub:8850+Agent服务总线26能力+**公网网关:28084**。

## 边界
- ✅ 本目录所有.py/.html/.cmd文件
- 🚫 phone_lib.py的ADB自动检测链不可硬编码

## 入口
- **公网**: `https://aiotvr.xyz/input/<API路径>` (Nginx→FRP→手机WiFi)
- 网关: `python phone_gateway.py` (:28084, 认证+自愈+多路径)
- Hub: `python cognitive_system.py serve` (:8850, 15 API)
- 库: `from phone_lib import Phone; p=Phone(url="https://aiotvr.xyz/input")` (公网)
- 一键: `→公网掌控.cmd` (启动网关+手机frpc+验证)

## 公网架构 (四路径冗余 · 全通)

| 路径 | 链路 | 延迟 | 依赖 | E2E |
|------|------|------|------|------|
| ① Nginx公网 | aiotvr.xyz/input → FRP:18084 → 台式机WiFi代理 → 手机:8084 | 50-200ms | 台式机+FRP | 29/32 |
| ② 手机FRP直达 | 60.205.171.100:38084 → 手机frpc → 手机:8084 | 50-150ms | 手机frpc | **32/32** ✅ |
| ③ 本地网关 | 127.0.0.1:28084 → WiFi → 手机:8084 | 1-5ms | 台式机同LAN | **32/32** ✅ |
| ④ WiFi直达 | 192.168.31.40:8084 | 1-5ms | 同LAN | **32/32** ✅ |

> 四路径全通: **128/128 (100%)** 2026-03-24

## 铁律
1. **phone_lib.py是唯一ADB真理源** — 所有文件通过它获取ADB能力
2. OnePlus已Root → Root优先(L0 su -c)，UI自动化为降级
3. 零硬编码：ADB路径/Serial/连接方式全自动适配
4. **公网优先路径①** — Agent远程操控用 `https://aiotvr.xyz/input/`
5. **去台式机依赖用路径②** — `http://60.205.171.100:38084/` 手机直达AI云

## 关联
| 方向 | 项目 | 说明 |
|---|---|---|
| 上游 | 反向控制 | 封装118+ SS HTTP API |
| 消费 | 亲情远程/quest3 | Phone类被多项目复用 |
| 数据 | _cognitive_data/ | 496 App统一数据库 |
| FRP | 三电脑服务器 | frpc-desktop.toml: phone_ss/phone_input/phone_gateway |
| 手机FRP | /data/local/tmp/frpc_aliyun/ | frpc.toml: 手机直连阿里云 |

## SS全能力矩阵 (120+端点 · 15组 · v33)

| 组 | 端点数 | 核心能力 | 公网验证 |
|---|---|---|---|
| 输入 | 13 | tap/swipe/key/text/home/back/lock | ✅ |
| 系统 | 6 | wake/power/screenshot/splitscreen/brightness | ✅ |
| 手势 | 4 | longpress/doubletap/scroll/pinch | ✅ |
| APP | 15 | openapp/openurl/killapp/apps/foreground/clipboard | ✅ |
| AI脑 | 7 | viewtree/windowinfo/findclick/findnodes/settext/screen/text | ✅ |
| 媒体硬件 | 9 | media/findphone/vibrate/flashlight/dnd/volume/autorotate | ✅ |
| 文件 | 12 | storage/list/read/download/search/mkdir/delete/rename/move/copy/upload | ✅ |
| 宏 | 10+ | list/create/run/run-inline/stop/triggers | ✅ |
| 智能家居 | 7 | status/devices/control/scenes/quick | ✅ |
| 平台 | 5 | command/command/stream/intent/wait/notifications | ✅ |
| Shell | 4 | shell/system/info/processes/properties | ✅ |
| 包管理 | 2 | packages/packages/{pkg} | ✅ |
| 元信息 | 4 | capabilities/digest/a11y/status | ✅ |

## 开机自启

- **frpc**: Magisk service.d `/data/adb/service.d/phone_agent_boot.sh`
- **ScreenStream**: 同脚本 `am start` 启动SS→回桌面
- **无障碍服务**: 系统级注册，开机自动恢复

## 查找手机 (find_my_phone.py · 万法归宗)

六大能力 — `from find_my_phone import FindMyPhone; fmp = FindMyPhone()`

| 能力 | 方法 | 底层机制 |
|------|------|----------|
| 定位 | `fmp.locate()` | `dumpsys location` → GPS/Fused/Network + WiFi BSSID + 基站CellID |
| 告警 | `fmp.alert()` | `findphone()` + `flashlight()` + `vibrate()` + 最大音量 + 亮屏 |
| 锁护 | `fmp.lock(msg)` / `fmp.wipe("YES_WIPE_NOW")` | `settings put secure lock_screen_owner_info` + `lock()` |
| 追踪 | `fmp.track_start()` / `fmp.track_once(server_url)` | Traccar/OsmAnd协议 HTTP GET + 本地 `_track_log.jsonl` |
| 反制 | `fmp.sim_check()` / `fmp.sim_watch_start()` / `fmp.stealth_photo()` | `getprop gsm.sim.*` + `screencap` |
| 存活 | `fmp.deploy_boot_script()` | Magisk `/data/adb/service.d/find_my_phone_boot.sh` |
| 综合 | `fmp.status()` / `fmp.emergency()` | 一键全状态 / 丢失时一键全执行 |

- **一键**: `→查找手机.cmd` (交互菜单)
- **CLI**: `python find_my_phone.py emergency` (公网: `--url https://aiotvr.xyz/input`)
- **开机日志**: `/sdcard/.find_my_phone_log.txt`

## 陷阱
- 微信等反无障碍App: observe()返回blind=true时降级ADB坐标点击
- QQ NT数据库: SQLCipher加密，key=`wy65ioGG`，需Root提取
- apps列表/文件搜索公网可能超时(数据量大)，本地无此问题
- 四路径E2E: `python _e2e_supreme.py --all` → **128/128通过(100%)** 2026-03-24
- ADB冲突陷阱: `adb -s 54ea19ff forward --remove tcp:28084`否则网关被劫持
- Nginx修复: `proxy_http_version 1.1; proxy_set_header Connection "";` 减延11s到2.6s
- E2E修复: requests.Session() SSL复用 + proxies={”no_proxy”:”*”}绕过Clash winreg代理
- 网关修复: allow_reuse_address + serve_forever自愈復重启 + _ensure_gateway()前置检测
- frpc两端心跳: heartbeatInterval=30 heartbeatTimeout=90 poolCount=2/3
