# 需求全景图 v2 — 大模块详情（S22-S42）

> 续上文 NEEDS_v2_大模块.md | 本文件含 S22-S42 + 中模块22个

## 总览表（续）

| # | 模块 | 领域 | ⭐ | 工期 |
|---|------|------|----|------|
| S22 | 视频制作监视器 | 视频 | - | 1-2周 |
| S23 | 延时摄影/定格动画 | 视频 | - | 1周 |
| S24 | 手机作PC游戏手柄 | 输入 | ⭐ | 2周 |
| S25 | MIDI/DAW控制器 | 音乐 | - | 1-2周 |
| S26 | 演示遥控/提词器 | 效率 | ⭐ | 1周 |
| S27 | 遥控无人机/机器人 | IoT | - | 1-2周 |
| S28 | 对讲机PTT | 通信 | ⭐ | 1周 |
| S29 | 离线Mesh通信 | 通信 | - | 3-4周 |
| S30 | 聊天/白板协作 | 协作 | ⭐ | 1-2周 |
| S31 | 教室设备管理 | 教育 | ⭐ | 2-3周 |
| S32 | 在线家教/培训 | 教育 | ⭐ | 1-2周 |
| S33 | 远程文件管理 | 效率 | ⭐⭐ | 1周 |
| S34 | 远程备份恢复 | 效率 | ⭐ | 1-2周 |
| S35 | 家长控制系统 | 生活 | ⭐ | 2-3周 |
| S36 | GPS位置共享 | 生活 | ⭐ | 1-2周 |
| S37 | 卡拉OK歌词 | 娱乐 | - | 1周 |
| S38 | 健身运动显示 | 生活 | - | 1周 |
| S39 | 手机测试农场 | 企业 | ⭐ | 2-3周 |
| S40 | POS收银终端 | 企业 | - | 3-4周 |
| S41 | 网络诊断工具 | 工具 | ⭐ | 1-2周 |
| S42 | 远程医疗辅助 | 医疗 | - | 2-3周 |

---

## E. 输入/控制扩展

### S22. 视频制作监视器
**场景**：手机作摄像机外接监视器，色彩预览+安全框
**实现**：Camera流+叠加安全框(Action/Title Safe矩形)→色彩直方图(Canvas绘RGB)→峰值对焦(Sobel边缘)→斑马纹(过曝高亮)

### S23. 延时摄影/定格动画工作站
**场景**：定时拍照→合成延时视频；定格动画Onion Skin
**实现**：定时Camera拍照(Handler)→帧序列→MediaCodec逐帧编码合成。Onion Skin=叠加上一帧半透明预览。远程触发快门
**参考**：[Stop Motion Studio](https://www.cateater.com/)

### S24. 手机作PC游戏手柄 ⭐
**场景**：没有手柄时，手机变PC虚拟游戏手柄
**实现**：手机端渲染虚拟摇杆/按钮→WebSocket发手柄事件→PC端模拟XInput/vJoy虚拟手柄。陀螺仪映射方向盘(赛车游戏)
**参考**：[Phone2Pad](https://aileck.itch.io/phone2pad)、[vJoy](https://sourceforge.net/projects/vjoystick/)

### S25. MIDI/DAW控制器
**场景**：音乐人用手机当推子/旋钮控制音乐制作软件
**实现**：前端渲染可配置推子/旋钮/XY Pad→输出MIDI消息→WebSocket/WebMIDI发PC→MIDI桥接(loopMIDI)→DAW接收
**参考**：[TouchOSC](https://hexler.net/touchosc)、WebMIDI API

### S26. 演示遥控器/提词器 ⭐
**场景**：演讲时手机当翻页器+提词器
**实现**：遥控=发送上下页键到PC(HTTP调用)；提词器=滚动文本+语音识别自动跟踪(SpeechRecognizer)
**参考**：PromptSmart、Unified Remote

### S27. 遥控无人机/机器人
**场景**：WebSocket控制Arduino/树莓派机器人，手机查看FPV画面
**实现**：ScreenStream作FPV显示端(接收RTSP流)→触控/陀螺仪→WebSocket控制指令→ESP32/树莓派接收执行
**参考**：ArduPilot、ROS

---

## F. 通信与社交

### S28. 对讲机PTT ⭐
**场景**：团队工地/活动现场，手机当对讲机按住说话
**实现**：WebRTC音频通道→PTT按钮(按住录音松开发送)→广播同组设备。Opus编码低带宽。局域网直连，跨网需S02
**参考**：[Zello](https://zello.com/)

### S29. 离线Mesh网络通信
**场景**：灾难/户外无信号，手机间蓝牙/WiFi Direct组网
**实现**：WiFi Direct P2P发现→BLE广播→消息多跳转发(路由表+TTL)→端到端加密。每台手机既是节点又是中继
**参考**：[Bridgefy](https://bridgefy.me/)、[Briar](https://briarproject.org/)

### S30. 实时聊天/白板协作 ⭐
**场景**：远程投屏同时文字/语音沟通+共享白板
**实现**：WebSocket文字聊天(已有基础)→Canvas共享白板(标注层升级)→多用户光标同步→语音WebRTC DataChannel

---

## G. 教育与培训

### S31. 教室设备管理/MDM ⭐
**场景**：老师管理全班学生平板→锁屏/推链接/监看屏幕
**实现**：所有学生装ScreenStream→教师端Dashboard显示所有设备缩略图(MJPEG低帧率)→批量命令(锁屏/推URL/安装APP)→DeviceOwner API深度锁定
**参考**：[STF](https://github.com/DeviceFarmer/stf)、Securly Classroom、Apple Classroom

### S32. 在线家教/远程培训 ⭐
**场景**：老师手机演示操作→学生实时看+标注+互动
**实现**：现有投屏+标注基础→标注工具增强(颜色/形状/文字/激光笔/步骤编号①②③)→语音通道→录制回放(已有)

---

## H. 生活与效率

### S33. 远程文件管理器 ⭐⭐
**场景**：浏览器中浏览/上传/下载/管理手机所有文件
**实现**：REST API: /files/list(目录)、/files/download、/files/delete、/files/rename、/files/move→前端双面板文件管理器(拖拽+缩略图)
**参考**：AirDroid Web、[filebrowser](https://github.com/filebrowser/filebrowser)

### S34. 远程备份恢复 ⭐
**场景**：远程备份手机联系人/短信/照片/应用列表到PC
**实现**：API暴露ContactsProvider/SmsProvider数据→选择性备份→打包ZIP下载。APK导出(PackageManager)
**参考**：Syncthing、Google Backup

### S35. 家长控制系统 ⭐
**场景**：限制孩子手机使用时间、应用、内容
**实现**：UsageStatsManager统计→每日限额→超时锁屏→应用黑白名单(DevicePolicyManager)→使用报告Dashboard→GPS追踪
**参考**：Google Family Link

### S36. GPS位置共享/追踪 ⭐
**场景**：家人实时位置共享、跑步轨迹、物流追踪
**实现**：GPS定时采样→WebSocket推坐标→前端Leaflet地图标注→历史轨迹回放→围栏报警(复用S08)
**参考**：[OwnTracks](https://github.com/owntracks/android)

### S37. 卡拉OK歌词显示
**场景**：手机投屏到大屏，滚动歌词，Party用
**实现**：LRC歌词解析→时间轴同步滚动→全屏歌词模式→MIC输入(WebRTC)→混音(Web Audio API)

### S38. 健身运动显示器
**场景**：手机固定跑步机/单车，显示运动数据+教练视频
**实现**：传感器读取(步数/加速计/心率BLE)→HIIT计时器(工作/休息交替)→统计Dashboard→远程教练模式(投屏+Camera叠加)

---

## I. 企业与专业

### S39. 手机测试农场 ⭐
**场景**：测试团队浏览器远程操作几十台手机做APP测试
**实现**：每台装ScreenStream→中央管理服务器注册设备→Dashboard设备列表+状态→点击进入远程控制(前端全复用)→批量APK安装→自动化脚本(宏系统)
**参考**：[STF](https://github.com/DeviceFarmer/stf) — STF需USB，ScreenStream用WiFi更灵活

### S40. POS收银终端
**场景**：小商户用手机/平板当收银机
**实现**：NFC HCE模拟→扫码收款(Camera读QR)→商品管理+库存(SQLite)→蓝牙热敏打印(ESC/POS协议)→日报表
**参考**：Square、Stripe Tap to Pay

### S41. 网络诊断工具箱 ⭐
**场景**：运维/开发在手机上Ping/Traceroute/端口扫描/WiFi分析
**实现**：后端API: /net/ping(InetAddress.isReachable)、/net/traceroute(逐跳TTL)、/net/portscan(Socket测试)、/net/wifi(WifiManager)、/net/speedtest(下载测速)
**参考**：[Fing](https://www.fing.com/)、Network Analyzer

### S42. 远程医疗辅助
**场景**：医生远程查看患者手机健康数据/照片，指导操作
**实现**：投屏+标注(已有)→HIPAA安全层(E2E加密+审计日志)→健康数据集成(Google Fit API)→视频通话+标注(WebRTC+Canvas)
**参考**：Splashtop Healthcare
