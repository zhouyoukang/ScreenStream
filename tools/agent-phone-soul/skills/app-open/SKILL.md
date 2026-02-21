---
description: 打开指定APP。当需要启动手机上的任何应用程序时触发。支持中英文APP名、包名、通用类型。
---

# 打开APP

## 触发条件
- 用户要求打开特定APP（"打开微信"、"open calculator"）
- 任务流程中需要切换到某个APP

## 执行步骤

### Step 1: 查询 Memory 中的已知启动方式
搜索 Memory：`[APP名] intent launch`
- 如果有记录 → 直接使用已知 Intent，跳到 Step 3

### Step 2: 确定启动 Intent

**路径 A: 通用类型**（设置/相机/浏览器/电话）
```
POST /intent {"action": "android.settings.SETTINGS"}           ← 设置
POST /intent {"action": "android.media.action.IMAGE_CAPTURE"}  ← 相机
POST /intent {"action": "android.intent.action.DIAL"}          ← 拨号
POST /intent {"action": "android.intent.action.VIEW", "data": "https://www.baidu.com"}  ← 浏览器
```

**路径 B: 已知包名**
```
POST /intent {"action": "android.intent.action.MAIN", "package": "com.tencent.mm"}
```

**路径 C: 按APP名搜索**
```
GET /apps
```
在返回的应用列表中搜索匹配的 label（中文名/英文名）
找到包名后 → 路径 B

**路径 D: 使用自然语言命令（兜底）**
```
POST /command {"command": "打开<APP名>"}
```

### Step 3: 等待APP启动
```
GET /wait?text=<APP标志性文字>&timeout=5000
```
- 标志性文字：APP 名称、主页标题、首屏关键词
- 如果不确定标志性文字：等待 2s 后直接 observe

### Step 4: 验证
```
GET /foreground
```
- 返回的包名是否是目标APP → 成功
- 不是目标APP → 可能启动失败或被弹窗覆盖
  - 尝试 POST /dismiss → 再次检查 foreground

### Step 5: 记录经验
成功后记录到 Memory：
```
## [APP名] 启动方式
- 包名：com.xxx.xxx
- Intent：{action, data, package, ...}
- 标志性文字：[首屏关键词]
- 设备：[型号]
- 验证日期：[日期]
```

## APP 名称 → 包名 常见映射

这些是初始知识，实际以 GET /apps 查询为准：

| 名称 | 常见包名 |
|------|---------|
| 微信 | com.tencent.mm |
| 支付宝 | com.eg.android.AlipayGeetest |
| QQ | com.tencent.mobileqq |
| 淘宝 | com.taobao.taobao |
| 抖音 | com.ss.android.ugc.aweme |
| 百度地图 | com.baidu.BaiduMap |
| 高德地图 | com.autonavi.minimap |
| 美团 | com.sankuai.meituan |
| 饿了么 | me.ele |
| 京东 | com.jingdong.app.mall |

> 注意：这些包名可能因版本/地区不同而变化。始终以 GET /apps 的实际结果为准。

## 常见失败原因

- APP 未安装 → GET /apps 确认，告知用户
- Intent 被 OEM 安全策略拦截 → 尝试路径 C/D
- APP 启动后立即弹出权限请求/更新提示 → POST /dismiss 处理
- APP 首次启动有引导页 → 可能需要多次 find-click("跳过"/"下一步"/"我知道了")
