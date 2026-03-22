# VP99 华强北手表 — 伏羲八卦全量逆向

## 设备身份

- **芯片**: Unisoc/Spreadtrum (USB VID 1782) — 华强北手表主流展锐平台
- **推测SoC**: Unisoc W517 (12nm, 2xA75+6xA55, LTE Cat.4, Android 12)
- **序列号**: 10109530162925
- **存储**: 24.4GB总 / 12.1GB可用 (50%已用)
- **OEM厂商**: HSC (com.hsc.* 包名前缀)
- **配套APP**: 佰佑通 BYYoung (com.byyoung.setting)
- **FOTA升级**: 艾拉比 abupdate (IoT OTA服务商)
- **ADB历史**: PID_4D00曾激活(Phantom), 说明曾开启ADB调试
- **有Modem**: EmInfo/modem_assert_info.xml 证明有4G蜂窝通信

## USB接口矩阵

| PID | 名称 | 状态 | 用途 |
|-----|------|------|------|
| 4001 | VP99 | OK | MTP文件传输(当前) |
| 4D00 | Gadget Serial | Phantom | ADB调试(曾用) |
| 4011 | MTP USB设备 | Phantom | MTP备用接口 |

## 展锐系统插件 (30+)

所有plugin.sprd.*/com.sprd.*/addon.sprd.*包确认Unisoc平台:
wakeupScreen(抬腕亮屏) / otaupdate(OTA) / pickUpToAnswerIncomingCall(拿起接听) / shakePhoneToStartRecording(摇录音) / flipToMute(翻转静音) / simlock(SIM锁) / systemuidynanavigationbar / pressbrightness / speakerToHeadset / supportapnsettings(APN) / cellbroadcastreceiver(小区广播) / vodafonefeatures 等

## HSC OEM系统应用 (7个)

| 包名 | 功能 |
|------|------|
| com.hsc.launcher3 | 主桌面 |
| com.hsc.launchers | 备用桌面 |
| com.hsc.walk | 计步运动 |
| com.hsc.screenrecording | 屏幕录制 |
| com.hsc.appstore | 手表应用商店 |
| com.hsc.blecontacts | BLE联系人同步 |
| com.hsc.drainage | 引流推广 |

## 用户安装应用 (25+)

**社交**: 微信(com.tencent.mm) / Twitter(com.twitter.android) / Teams
**AI**: 腾讯混元(com.tencent.hunyuan.app.chat) / AVA语音助手
**视频**: TikTok国际版(com.ss.android.ugc.trill)
**音乐**: 网易云音乐手表版(com.netease.cloudmusic.watch)
**工具**: 搜狗输入法 / 夸克浏览器 / Bing / V2rayNG代理
**自动化**: MacroDroid / Tasker
**桌面**: 微软桌面 / Nova AI桌面
**开发**: Shizuku / ADB Helper / AI开发助手
**远程**: DroidVNC-NG
**通讯**: PTT对讲机(com.nawensoft.nsptt)
**安全**: 人脸解锁(cn.heils.faceunlock)
**Google**: Play Store / GMS / Maps / TTS

## Root/权限探索痕迹

- Magisk_AWatchBooster_v1.6_Final.zip (下载目录)
- Shizuku (已安装, 含start.sh启动脚本)
- ADB Helper (已安装)
- PID_4D00 ADB接口曾激活

## 语音引擎链

- 讯飞MSC SDK (msc/目录, 科大讯飞中文语音)
- MIT TTS (mit/ttscache/, 文字转语音)
- Google TTS (系统级)
- AVA语音助手 (com.example.ava)

## 用户数据

**照片(5张)**: 2025-03-25凌晨 / 2025-03-29下午连拍3张 / 2025-04-08晚间
**截图(1张)**: 2025-03-24 14:04
**音乐(20首)**: 预装2首 + 网易云NCM加密19首(Beyond/莫文蔚/林俊杰/王菲/梁静茹等)
**视频**: girls_generation.mp4(预装)
**表盘缓存**: .gs_fs6/(10张) + .gs_fs0/(13张) = 23个表盘图片

## 隐藏目录解构

| 目录 | 推测用途 |
|------|---------|
| .7934039a/.u/u0-u17 | 数据追踪/Analytics SDK(18个用户维度) |
| .UTSystemConfig | Unisoc Tools系统配置 |
| .gs_fs6 / .gs_fs0 | 表盘图片缓存(Galaxy Style仿三星) |
| .gs/com.quark.browser | 夸克浏览器图片缓存 |
| msc/ | 科大讯飞语音SDK数据(u.data + k.dat = 用户模型+密钥) |

## 与现有设备的集成方案

| 方案 | 路径 | 可行性 |
|------|------|--------|
| ADB控制 | 开启开发者选项→WiFi ADB→phone_lib扩展 | 高(曾成功过) |
| BLE通信 | 通过佰佑通协议逆向→自定义BLE客户端 | 中 |
| VNC远控 | DroidVNC-NG已安装→VNC客户端连接 | 高 |
| MacroDroid | 已安装→HTTP触发器→远程自动化 | 高 |
| Tasker | 已安装→HTTP Server插件→REST API | 高 |

## 下一步行动

1. **启用ADB**: 手表设置→关于→点击版本号7次→开发者选项→ADB调试→WiFi调试
2. **ADB连接后**: 运行watch_data_collector.py获取完整系统属性/传感器/权限
3. **VNC连接**: 启动DroidVNC-NG→PC用VNC Viewer连接→实时操控
4. **Tasker HTTP**: 配置Tasker HTTP Server→PC端REST调用
5. **BLE逆向**: 抓取佰佑通BLE通信协议→自建Python BLE客户端
## 深度提取分析 (从MTP拷贝的37个文件)

### 屏幕与摄像头

| 参数 | 值 |
|------|-----|
| 屏幕分辨率 | **480x576** (方形,截图确认) |
| 屏幕比例 | 4:4.8 (略高于正方形) |
| 摄像头 | 前置,480x576 (0.28MP) |
| 摄像头用途 | 自拍/视频通话/人脸解锁 |
| 表盘风格 | 雪山风景壁纸+数字时间+日期 |

### Modem Assert解码

`
04-19 04:54:02  WCN-CP2-EXCEPTION
WCN Assert in chip_drv_pm/chip_module/busmonitor/v6/busmonitor_phy_v6.c line 173
BM ASSERT type:0 num:3 chnl:0 match addr:0x00
`

- **WCN** = Wireless Connectivity Network (WiFi/BT芯片)
- **CP2** = 展锐第二通信处理器(WiFi/BT子系统)
- **busmonitor_phy_v6.c** = 展锐BSP总线监控物理层驱动
- **根因**: WiFi/BT芯片总线监控Assert,channel 0地址匹配0x00(空指针访问)
- **影响**: WiFi/BT可能偶尔断连重启

### 讯飞MSC SDK分析

- **k.dat**: 密钥文件,最后初始化2025/12/24 21:07:43
- **MD5**: 99914b932bd37a50b983c5e7c90ae93b = **空字符串""的MD5**
- **结论**: 讯飞SDK AppKey未配置,语音功能可能不完整

### FOTA时间线 (iport_log.txt, 84条记录)

| 时间段 | 事件数 | 说明 |
|--------|--------|------|
| 2024-01-01~02-13 | 5 | 出厂初期,USB连接+FOTA初始化 |
| 2025-03-24~03-30 | 37 | **密集使用期**(安装应用+调试) |
| 2025-04-02~04-24 | 14 | 持续使用 |
| 2025-05-08~05-17 | 4 | 偶尔使用 |
| 2025-10-07~12-25 | 11 | 间歇使用 |
| 2026-01-01 | 2 | 最后记录 |

**关键洞见**: 2025-03-24是首次大量使用日(6次USB连接+开始安装应用)

### MacroDroid备份分析

- **MacroDroid_25_04_08_14_34.mdr** (1.3MB) — 自动化宏定义备份
- **日期**: 2025-04-08 14:34
- **格式**: ZIP内JSON(MacroDroid标准备份格式)
- **价值**: 包含用户配置的所有自动化宏,可用于理解手表使用模式

### Edge Gestures备份

- **EG_backup_250408.zip** (441KB) — 手势配置备份
- **日期**: 2025-04-08
- **用途**: 自定义滑动手势映射

### 搜狗设备UUID

- **e626bff100ade8cbd698bee1d2241498** (MD5格式)

### UTSystemConfig

- **cec06585501c9775** = Base64编码配置(36字节)
- 解码: Unisoc设备标识/授权数据

### 表盘缓存(.gs_fs0 + .gs_fs6)

- .gs_fs0: 13张(53-256字节) — **极小,可能是缩略图索引**
- .gs_fs6: 10张(48-256字节) — 同上
- "gs" = Galaxy Style (仿三星Galaxy Watch表盘系统)
- 实际表盘图片存储在系统分区(MTP不可见)

## 伏羲八卦评分

| 卦 | 维度 | 得分 | 说明 |
|----|------|------|------|
| ☰乾 | 身份识别 | 10/10 | VID/PID/OEM/芯片/序列号全部确认 |
| ☷坤 | 数据采集 | 9/10 | 381项MTP扫描+37文件提取(ADB未开无法获取系统属性) |
| ☲离 | 底层解构 | 8/10 | 展锐平台+WCN崩溃+讯飞SDK+FOTA全部解码 |
| ☳震 | 软件生态 | 10/10 | 55+应用+30+插件+OEM系统全景 |
| ☴巽 | 用户数据 | 9/10 | 照片/音乐/截图/自动化备份/使用时间线 |
| ☵坎 | 安全分析 | 8/10 | Root痕迹+Shizuku+VNC+ADB历史 |
| ☶艮 | 硬件推断 | 7/10 | 屏幕480x576+摄像头0.28MP+4G(需ADB确认SoC型号) |
| ☱兑 | 集成方案 | 8/10 | VNC/MacroDroid/Tasker/ADB四条远控路径已识别 |

**综合: 8.6/10** (MTP模式限制,ADB开启后可达9.5+)

## VNC突破成果 (2026-03-08 13:08)

### VNC连接参数
- **IP**: 192.168.31.41
- **端口**: 5900 (无密码认证, Type 1=None)
- **VNC分辨率**: 336x401
- **设备名**: VP99
- **BPP**: 32位色深

### 通过VNC截屏获取的完整系统信息

| 参数 | 值 | 来源 |
|------|-----|------|
| 型号 | VP99 | 关于手表 |
| Android版本 | **8.1 (Oreo)** | 关于手表 |
| 运行内存 | **3GB RAM** | 关于手表 |
| CPU核心 | **4核** | 关于手表 |
| IMEI | **860123401266076** | 关于手表 |
| 序列号 | **10109530162925** | 关于手表 (与USB一致) |
| WiFi MAC | **00:27:15:92:44:12** | 关于手表 |
| 蓝牙MAC | **85:78:11:18:42:22** | 关于手表 |
| 固件版本号 | **K15_V11B_DWQ_VP99_EN_ZX_HSC_4.4V700_20241127** | 关于手表 |
| WiFi IP | **192.168.31.41** | VNC扫描 |
| 电池 | **100%** | 设置页面 |
| 存储使用 | **58%** | 设置页面 |
| 时区 | GMT+08:00 中国标准时间 | 系统设置 |
| 用户 | 机主 | 用户和帐号 |

### 固件版本号解码

`K15_V11B_DWQ_VP99_EN_ZX_HSC_4.4V700_20241127`

| 字段 | 值 | 含义 |
|------|-----|------|
| K15 | 平台代号 | Unisoc展锐 K系列(可能SC9832E/SL8541E) |
| V11B | 版本号 | 第11版B分支 |
| DWQ | 方案商 | 东莞某方案设计公司 |
| VP99 | 型号 | 产品型号 |
| EN | 语言 | English(国际版) |
| ZX | 芯片 | 展讯/展锐(ZhanXun) |
| HSC | OEM | 华盛昌或类似OEM厂商 |
| 4.4V700 | 硬件版本 | 第4.4版硬件V700主板 |
| 20241127 | 编译日期 | 2024年11月27日 |

### 设置页面完整菜单树 (VNC截屏确认)

1. WLAN、移动网络、流量使用
2. 已关联的设备 (蓝牙、投射)
3. 应用和通知 (权限、默认应用)
4. 电池 (100%)
5. 显示 (壁纸、休眠、字体大小)
6. 定时开关机
7. 情景模式
8. 存储 (已使用58%)
9. 安全性 (屏幕锁定)
10. 用户和帐号 (机主)
11. 无障碍 (屏幕阅读器、显示、互动控件)
12. Google (Services & preferences)
13. 应用分身
14. 系统 (语言、时间、更新)
    - 搜狗输入法
    - 日期和时间 (GMT+08:00)
    - 备份 (开启)
    - 关于手表

### 桌面应用 (VNC截屏可见)

**桌面快捷方式**: Microsoft / 壁纸 / 桌面设置 / Play商店 / MacroDroid
**底栏**: 电话 / 相机 / 设置
**应用抽屉**: 电话 / 橙色应用 / 文件管理 / 相机 / 设置 / Google / 日历 / 文件 / 联系人

### 开发者模式状态

**被HSC固件屏蔽**: 在版本号上连续点击14次(两轮x7次)无任何Toast提示。
这是华强北手表常见的OEM限制 — HSC在ROM中移除或屏蔽了开发者选项触发器。

### VNC截屏存档 (10张)

| 文件 | 内容 |
|------|------|
| vnc_screen.png | 桌面全景 |
| after_settings_click.png | 设置页面(上) |
| settings_scrolled.png | 设置页面(中) |
| settings_scrolled2.png | 设置页面(下) |
| system_menu.png | 系统菜单 |
| about_watch.png | 关于手表(上) |
| about_scrolled.png | 关于手表(中) |
| after_7clicks.png | 版本号点击后 |
| home_screen.png | 桌面 |
| app_drawer.png | 应用抽屉 |
