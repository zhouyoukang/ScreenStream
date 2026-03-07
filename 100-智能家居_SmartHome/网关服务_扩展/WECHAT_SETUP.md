# 微信公众号建立操作指南

> 从零到上线的完整操作手册。按顺序执行，每步都有验证点。

---

## 一、注册微信公众号

### 方式A：测试号（推荐，零门槛，5分钟搞定）

1. 打开 https://mp.weixin.qq.com/debug/cgi-bin/sandbox
2. 用微信扫码登录
3. 登录后页面显示：
   - **appID**（如 `wx1234567890abcdef`）
   - **appsecret**（如 `abcdef1234567890abcdef1234567890`）
4. **记录这两个值**，后面要填入 `config.json`

> 测试号功能齐全：自定义菜单、模板消息、语音识别、用户管理、二维码。
> 限制：最多100个关注者，无认证标识，无支付能力。

### 方式B：正式订阅号（需企业/个人实名）

1. 打开 https://mp.weixin.qq.com/
2. 点击右上角「立即注册」→ 选「订阅号」
3. 填写邮箱、密码、管理员微信扫码
4. 选择类型：个人（无认证费）/ 企业（300元/年认证费）
5. 提交后等待审核（1-3个工作日）
6. 审核通过后，进入后台 → 设置与开发 → 基本配置 → 获取 AppID 和 AppSecret

### 方式C：正式服务号（企业专用，功能最全）

- 需要企业营业执照 + 300元/年认证费
- 支持：模板消息推送、微信支付、OAuth网页授权、九宫格菜单
- 注册流程同方式B，选「服务号」

---

## 二、配置服务器（Gateway 端）

### 2.1 编辑 config.json

```json
{
  "wechat": {
    "enabled": true,
    "token": "smarthome2026",
    "appid": "wx5b3f8f863e6bb71a",
    "appsecret": "你的appsecret",
    "auto_menu": true
  }
}
```

字段说明：
- **token**: 自定义字符串（英文字母+数字，3-32位），用于微信服务器验证。随便写，但要和微信后台填的一致。当前使用: `smarthome2026`
- **appid / appsecret**: 从微信后台获取（步骤一中记录的值）。
- **auto_menu**: 启动时自动创建智能家居菜单（💡控制 / 🎬场景 / 📊更多）。

### 2.2 启动 Gateway

```bash
cd 智能家居/网关服务
python gateway.py --port 8900
```

启动日志应显示 `WeChat` 在已连接后端列表中：
```
Gateway ready: MiCloud(...) + Mina(...) + WeChat
```

### 2.3 本地验证

```bash
# 检查微信模块状态
curl http://localhost:8900/wx/status
# 应返回: {"enabled": true, "token_set": true, "appid": "wx12345...", "router_ready": true, "api_ready": true, ...}
```

---

## 三、公网暴露（让微信服务器能访问你的 Gateway）

### 方式A：通过阿里云 Nginx 反代（推荐，稳定）

**前提**: 已有 aiotvr.xyz 域名 + 阿里云服务器 + FRP 穿透

#### 3.1 笔记本端：确保 FRP 客户端转发 8900 端口

在 frpc.toml 中添加（如果还没有）：

```toml
[[proxies]]
name = "gateway"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8900
remotePort = 18900
```

重启 frpc 使配置生效。

#### 3.2 阿里云端：Nginx 添加 /wx 反代

SSH 到阿里云服务器，编辑 Nginx 配置：

```bash
ssh aliyun
sudo nano /www/server/panel/vhost/nginx/aiotvr.xyz.conf
```

在 `server` 块内（443端口那个）添加：

```nginx
    # 微信公众号消息接口
    location /wx {
        proxy_pass http://127.0.0.1:18900/wx;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 10s;
    }
```

重载 Nginx：

```bash
sudo nginx -t && sudo nginx -s reload
```

#### 3.3 验证公网可达

```bash
curl https://aiotvr.xyz/wx/status
# 应返回 JSON（同本地验证结果）
```

### 方式B：Cloudflare Tunnel（临时/备用）

```bash
# 一键启动 Gateway + Tunnel
start_wechat.bat
```

Cloudflare 会输出一个临时 URL（如 `https://xxx-xxx.trycloudflare.com`），用这个 URL 配置微信后台。
**注意**: 每次重启 URL 会变，不适合长期使用。

### 方式C：固定 Cloudflare Tunnel（推荐备选）

```bash
# 创建命名隧道（一次性）
cloudflared tunnel create smart-home
cloudflared tunnel route dns smart-home wx.你的域名.com

# 启动
cloudflared tunnel run --url http://localhost:8900 smart-home
```

---

## 四、微信后台配置

### 4.1 配置服务器 URL

#### 测试号

1. 打开测试号管理页面
2. 在「接口配置信息」区域：
   - **URL**: `https://aiotvr.xyz/wx`（或你的公网地址 + `/wx`）
   - **Token**: `smarthome2026`（与 config.json 中一致，全小写）
3. 点击「提交」→ 显示「配置成功」✅

#### 正式号

1. 登录 https://mp.weixin.qq.com/
2. 设置与开发 → 基本配置 → 服务器配置
3. 点击「修改配置」：
   - **URL**: `https://aiotvr.xyz/wx`
   - **Token**: `smarthome2026`
   - **EncodingAESKey**: 点「随机生成」
   - **消息加解密方式**: 选「明文模式」（简单）或「安全模式」（推荐正式环境）
4. 点击「提交」→ 成功后点击「启用」

### 4.2 开启语音识别（测试号默认开启）

正式号需要：
1. 设置与开发 → 接口权限 → 找到「语音识别」
2. 确认已获得该权限（认证后自动获得）

### 4.3 关注测试号

1. 测试号页面右侧有二维码
2. 用微信扫码关注
3. 发送 `帮助` → 应收到功能列表回复

---

## 五、功能验证清单

| # | 测试 | 发送内容 | 预期回复 |
|---|------|----------|----------|
| 1 | 帮助 | `帮助` | 功能列表 |
| 2 | 设备状态 | `状态` | 设备列表+在线状态 |
| 3 | 开灯 | `打开灯带` | 🟢 灯带: 已打开 |
| 4 | 关灯 | `关灯` | ⚡ 关灯 执行中... |
| 5 | 场景 | `回家模式` | 🎬 回家 执行中... |
| 6 | 舒适意图 | `太冷了` | 🌡️ 已开启电热毯 |
| 7 | TTS | `说 你好` | 🔊 已播报: 你好 |
| 8 | 语音 | 长按录音说"开灯" | 💡 已开灯 |
| 9 | 菜单点击 | 点「全部关闭」按钮 | ⚡ 全部关闭 执行中... |
| 10 | 自然语言 | `帮我把风扇关了` | ⚪ 风扇: 已关闭 |

---

## 六、管理 API 速查

Gateway 启动后可用以下 API 管理公众号：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/wx/status` | 模块状态（token/api/router） |
| GET | `/wx/menu` | 查询当前菜单 |
| POST | `/wx/menu` | 创建/更新菜单（无body=默认智能家居菜单） |
| DELETE | `/wx/menu` | 删除菜单 |
| GET | `/wx/users` | 关注者列表（含前20个用户详情） |
| GET | `/wx/user/{openid}` | 单个用户信息 |
| POST | `/wx/send` | 发送客服消息 `{"openid":"...","content":"..."}` |
| POST | `/wx/template` | 发送模板消息 |
| GET | `/wx/templates` | 已添加的模板列表 |
| GET | `/wx/qrcode` | 生成带参数二维码 |

### 示例

```bash
# 查看菜单
curl http://localhost:8900/wx/menu

# 手动同步默认菜单
curl -X POST http://localhost:8900/wx/menu

# 查看关注者
curl http://localhost:8900/wx/users

# 生成二维码
curl "http://localhost:8900/wx/qrcode?scene=smart_home&permanent=true"

# 发消息给用户
curl -X POST http://localhost:8900/wx/send \
  -H "Content-Type: application/json" \
  -d '{"openid":"用户的openid","content":"灯已自动关闭 💡"}'
```

---

## 七、菜单结构

Gateway 启动时自动创建的菜单（`auto_menu: true`）：

```
💡 控制
  ├── 全部关闭
  ├── 开灯
  ├── 关灯
  ├── 开风扇
  └── 关风扇

🎬 场景
  ├── 回家模式
  ├── 睡眠模式
  ├── 离家模式
  ├── 工作模式
  └── 观影模式

📊 更多
  ├── 设备状态
  ├── 帮助
  └── 控制面板 → https://aiotvr.xyz
```

自定义菜单修改方式：
1. 编辑 `wechat_api.py` 中的 `SMART_HOME_MENU` 常量
2. 重启 Gateway（auto_menu=true 自动同步）
3. 或调用 `POST /wx/menu` 传入自定义 JSON

---

## 八、故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| 微信后台「配置失败」 | URL不可达 / Token不一致 | 检查公网可达性 + token匹配 |
| 发消息无回复 | Gateway未启动 / FRP断开 | 检查 `curl https://aiotvr.xyz/wx/status` |
| 「该公众号暂时无法提供服务」 | Gateway返回超时(>5秒) | 检查 micloud 连接 |
| 菜单不显示 | 需取关再关注 / 5分钟缓存 | 取关→重新关注 |
| access_token 获取失败 | appid/appsecret错误 / IP白名单 | 检查配置，测试号无IP限制 |
| 语音无法识别 | 未开启语音识别权限 | 正式号需认证后开启 |
| 模板消息发送失败 | 未添加模板 / openid错误 | 先在后台添加模板 |

---

## 九、安全建议

1. **config.json 不要提交到 Git**（已在 .gitignore 中）
2. **appsecret 不要泄露**（等同于公众号密码）
3. **建议开启 IP 白名单**（正式号，限制 API 调用来源 IP）
4. **使用 HTTPS**（aiotvr.xyz 已有 Let's Encrypt 证书）
5. **定期检查关注者列表**（`GET /wx/users`），发现异常及时处理

---

## 十、Nginx 反代配置参考

```nginx
# /www/server/panel/vhost/nginx/aiotvr.xyz.conf
# 在 server { listen 443 ssl; ... } 块内添加：

    # 微信公众号消息接口（FRP穿透到笔记本Gateway:8900）
    location /wx {
        proxy_pass http://127.0.0.1:18900/wx;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 10s;
        proxy_connect_timeout 5s;
    }

    # 微信管理API（可选，建议仅内网访问）
    location /wx/ {
        proxy_pass http://127.0.0.1:18900/wx/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
```

> **注意**: 微信要求服务器在 5 秒内响应，否则会重试 3 次。
> `proxy_read_timeout 10s` 留足余量，实际响应应在 2 秒内。
