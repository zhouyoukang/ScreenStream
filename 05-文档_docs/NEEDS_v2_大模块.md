# 需求全景图 v2 — 大模块详情（S01-S21）

> 42个大模块 | 每个含实现路径预测 | 本文件覆盖 S01-S21
> S22-S42 见 NEEDS_v2_大模块续.md

## 总览表

| # | 模块 | 领域 | ⭐ | 工期 |
|---|------|------|----|------|
| S01 | 远程家庭协助 | 远程 | ⭐⭐⭐ | 3-4周 |
| S02 | 跨网P2P基础设施 | 基础 | ⭐⭐⭐ | 3-4周 |
| S03 | 手机对手机控制 | 远程 | ⭐⭐ | 1-2周 |
| S04 | 多人协作控制 | 协作 | ⭐ | 1-2周 |
| S05 | WoL远程唤醒PC | 远程 | ⭐ | 3天 |
| S06 | 通知消息中心 | 效率 | ⭐⭐⭐ | 2周 |
| S07 | 防盗追踪系统 | 安全 | ⭐⭐⭐ | 3-4周 |
| S08 | 地理围栏报警 | 安全 | ⭐ | 1周 |
| S09 | SIM卡更换报警 | 安全 | ⭐ | 3-5天 |
| S10 | 安防监控摄像头 | 复用 | ⭐⭐ | 1-2周 |
| S11 | 婴儿/宠物监控 | 复用 | ⭐⭐ | 1周 |
| S12 | 行车记录仪 | 复用 | ⭐ | 1-2周 |
| S13 | 数码相框 | 复用 | ⭐ | 3-5天 |
| S14 | 数字标牌Kiosk | 企业 | ⭐ | 1-2周 |
| S15 | 手机作服务器 | 复用 | ⭐ | 1周 |
| S16 | VR投屏控制 | VR | ⭐⭐ | 3-4周 |
| S17 | AR标注覆层 | AR | ⭐ | 3天-3周 |
| S18 | AR室内导航 | AR | - | 3-4周 |
| S19 | 手机作摄像头 | 视频 | ⭐⭐ | 3天-3周 |
| S20 | 手机第二屏幕 | 视频 | ⭐⭐ | 4-6周 |
| S21 | 直播推流 | 视频 | ⭐ | 1-2周 |

---

## A. 远程连接与协助

### S01. 远程家庭协助 ⭐⭐⭐
**场景**：帮远方父母配手机、解决问题——"看到并操控"对方屏幕
**实现**：WebRTC(已有基础)+公共TURN(coturn)做跨网穿透；被控端ScreenStream自启+信令握手→DataChannel传指令+视频回传
**参考**：[RustDesk](https://github.com/rustdesk/rustdesk)架构、TeamViewer Host、小米远程协助
**前置**：S02(P2P基础设施)

### S02. 跨网P2P基础设施 ⭐⭐⭐
**场景**：所有"不在同一WiFi也能连"功能的底层
**实现**：自建轻量信令服务器(Node.js/Go)→设备注册→NAT检测→STUN打洞→TURN中继。设备ID体系(9位数字)。可部署Fly.io/Railway免费层
**参考**：[RustDesk Server](https://github.com/rustdesk/rustdesk-server)、[pion/turn](https://github.com/pion/turn)、Tailscale
**说明**：这是S01/S03/S06/S28等多个模块的前置

### S03. 手机对手机远程控制 ⭐⭐
**场景**：用你的Android直接控制另一台Android
**实现**：两台都装ScreenStream→A端WebView加载B端index.html→触控事件转发。局域网直连已可行，跨网需S02
**参考**：AirMirror、scrcpy OTG模式

### S04. 协作式多人远程控制
**场景**：IT团队多人排查同一设备、老师+学生共看
**实现**：现有MJPEG已支持多客户端→新增WebSocket广播光标位置(每用户不同颜色)→控制权令牌机制(谁持token谁操作)

### S05. WoL远程唤醒PC
**场景**：人在外面，手机远程开启家里电脑
**实现**：Web前端输入MAC地址→后端发Magic Packet(UDP广播ff×6+MAC×16)→局域网唤醒。跨网需S02中继
**参考**：[WoL Android](https://github.com/nicholassm/wake-on-lan)、TeamViewer WoL

### S06. 跨设备通知消息中心 ⭐⭐⭐
**场景**：电脑浏览器上看手机通知、回微信/短信、接来电
**实现**：NotificationListenerService捕获通知→WebSocket推送→前端通知卡片。回复用RemoteInput API。短信SmsManager。来电PhoneStateListener
**参考**：[KDE Connect](https://github.com/KDE/kdeconnect-kde)、Pushbullet、Phone Link

### S07. 手机防盗追踪系统 ⭐⭐⭐
**场景**：手机丢失/被偷→远程定位+拍照+锁定+擦除
**实现**：DeviceAdmin API→后台Service定时GPS上报→远程指令(SMS/HTTP)触发拍照/锁定/响铃/擦除。解锁失败3次自拍+邮件。SIM更换TelephonyManager检测
**参考**：[Prey](https://github.com/prey/prey-android-client)、Cerberus功能设计

### S08. 地理围栏报警
**场景**：孩子/老人离开安全区域自动通知、贵重物品移动报警
**实现**：GeofencingClient设置虚拟围栏→进出触发BroadcastReceiver→推送通知。前端地图画圆设置围栏(Leaflet.js)
**参考**：Google Geofencing API、Life360

### S09. SIM卡更换报警
**场景**：手机被盗换SIM→自动发新号码+位置到预设联系人
**实现**：开机BroadcastReceiver检查ICCID变化→SMS发送(新号码+GPS)→自动锁屏

---

## B. 设备复用（旧手机新生）

### S10. 安防监控摄像头 ⭐⭐
**场景**：旧手机变家庭/店铺监控，手机随时查看
**实现**：Camera流(已有)→移动侦测(帧差法比较连续帧像素差)→触发录制+推通知→夜间自动开IR(手电筒API)→前端加历史回放
**参考**：[IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam)、[Frigate NVR](https://frigate.video/)

### S11. 婴儿/宠物监控 ⭐⭐
**场景**：旧手机放婴儿房，另一台手机/电脑实时看+听
**实现**：S10基础+双向音频(WebRTC音频通道)+声音检测(分贝阈值触发报警)+温度显示(BatteryManager)+夜灯模式(屏幕暖色光)

### S12. 行车记录仪
**场景**：旧手机变行车记录仪，GPS轨迹+碰撞检测
**实现**：Camera连续录制+GPS轨迹叠加(SRT字幕)→加速度传感器碰撞检测(阈值触发保存关键片段)→循环存储(满删旧)
**参考**：AutoBoy、DailyRoads

### S13. 数码相框/环境显示
**场景**：旧手机/平板变桌面相框+时钟+天气
**实现**：全屏Web→轮播本地/云照片→叠加时钟+天气Widget(天气API)→常亮+自动亮度→定时开关屏(AlarmManager)
**参考**：[DAKboard](https://dakboard.com/)、Google Nest Hub

### S14. 数字标牌/Kiosk展示
**场景**：手机固定在店铺前台，展示广告/菜单/排号
**实现**：Kiosk模式(DeviceOwner锁定单APP+禁导航栏)+定时内容切换(HTML轮播)+远程内容管理(HTTP API上传)
**参考**：[Fully Kiosk Browser](https://www.fully-kiosk.com/)、[MagicMirror²](https://github.com/MagicMirrorOrg/MagicMirror)

### S15. 手机作为服务器
**场景**：旧手机24h运行，托管网站/API/文件服务
**实现**：现有HTTP Server扩展→静态文件托管+简易API框架+文件共享(WebDAV)+Git仓库(可选)。前端管理界面控制启停
**参考**：[Termux](https://github.com/termux/termux-app)、KSWEB

---

## C. VR/AR/扩展现实

### S16. VR投屏与控制 ⭐⭐
**场景**：手机投屏到Quest 3/Pico 4，VR中虚拟大屏玩手游
**实现**：WebXR API(Quest浏览器原生支持)→Three.js渲染3D空间+浮动平面→现有MJPEG/H264流作纹理贴图→VR手柄射线碰撞→映射触控坐标→发送InputService
**参考**：[ALVR](https://github.com/alvr-org/ALVR)、[A-Frame](https://aframe.io/)、Spatial Phone

### S17. AR标注覆层
**场景**：维修工程师远程指导→在实景画面上画箭头/标注
**实现**：手机Camera流+前端Canvas标注层(已有基础)→标注坐标WebSocket实时同步→接收端叠加渲染。3D锚点需ARCore
**参考**：Acty AR Remote Assist、TeamViewer AR

### S18. AR室内导航
**场景**：商场/医院/展馆，手机摄像头+AR箭头指引方向
**实现**：ARCore Augmented Images/Cloud Anchors→预设路径点→渲染3D箭头叠加Camera Preview。需预采集空间数据
**参考**：[ARway](https://www.arway.ai/)、Google Maps AR

---

## D. 摄像头与视频

### S19. 手机作为电脑摄像头 ⭐⭐
**场景**：手机4800万摄像头替代USB摄像头，视频会议/直播
**实现**：方案A: OBS虚拟摄像头插件(读MJPEG流，最快3天)；方案B: Windows DirectShow虚拟摄像头驱动(C++，2-3周)；方案C: NDI协议输出(广播行业标准)
**参考**：[DroidCam](https://www.dev47apps.com/)、[OBS Virtual Camera](https://github.com/Fenrirthviti/obs-virtual-cam)

### S20. 手机作为第二屏幕 ⭐⭐
**场景**：旧手机/平板变电脑扩展显示器
**实现**：Windows端Indirect Display Driver(IDD, C++ WDM)创建虚拟显示器→DXGI Desktop Duplication捕获→H264编码→发送手机解码。触控回传走InputService
**参考**：[SpaceDesk](https://www.spacedesk.net/)、[IddSampleDriver](https://github.com/roshkins/IddSampleDriver)

### S21. 直播推流平台
**场景**：手机画面+摄像头→推流到B站/抖音/YouTube/Twitch
**实现**：现有H264编码流→封装RTMP→推送到直播平台ingest URL。前端加推流设置面板(RTMP URL+Stream Key)。可选叠加层(文字/Logo/PiP)
**参考**：[Larix Broadcaster](https://softvelum.com/larix/)、librtmp

