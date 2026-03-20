# Windsurf Login Helper v5.0.20 完全逆向报告

## 插件位置
`C:\Users\Administrator\.windsurf\extensions\undefined_publisher.windsurf-login-helper-5.0.20\`

## 核心架构

### 文件结构
| 文件 | 行数 | 职责 |
|------|------|------|
| `extension.js` | 433行 | 入口：状态栏+切换命令+积分刷新 |
| `loginViewProvider.js` | 3111行 | 核心：认证+积分+账号管理+WebView UI |
| `accountPickerProvider.js` | 163行 | 快速切换面板(未启用) |

### API服务器
| URL | 职责 |
|-----|------|
| `https://168666okfa.xyz/firebase/login` | Firebase登录代理(域名白名单过滤) |
| `https://168666okfa.xyz/windsurf/auth-token` | GetOneTimeAuthToken代理 |
| `https://168666okfa.xyz/windsurf/plan-status` | GetPlanStatus代理(积分查询) |
| `https://168666okfa.xyz/api/account-rules` | 域名白名单规则API |
| `https://168666okfa.xyz/api/notice` | 公告+版本检查 |
| `https://okk.fw720.com/api/verify.php` | 卡密验证 |
| `https://okk.fw720.com/api/get-accounts.php` | 卡密提取账号 |
| `https://okk.fw720.com/api/notice.php` | 公告 |

### 原始限制机制 (已全部突破)

#### 1. 默认密码 `a1234561`
- **位置**: `loginViewProvider.js:1033` (后端) + webview JS (前端)
- **机制**: 添加账号时若不指定密码，默认`a1234561`；前端自动拼接`----a1234561`

#### 2. 域名白名单 `@icloud.com`
- **本地规则**: `loginViewProvider.js:1020-1024` + `1342-1344`
  ```js
  allowed_domains: ['@icloud.com'],
  allowed_passwords: ['a1234561']
  ```
- **服务端规则**: `168666okfa.xyz/api/account-rules` 返回动态白名单
- **双重验证**: `validateAccountWithAPI()` 先本地后API

#### 3. 代理服务器域名过滤
- `168666okfa.xyz/firebase/login` 会返回 `DOMAIN_NOT_ALLOWED` 拒绝非白名单域名

### 登录流程
```
1. Firebase Login (代理168666okfa.xyz) → idToken
2. GetOneTimeAuthToken (代理) → authToken (30-60字符)
3. 写入认证文件 → windsurf-auth.json + cascade-auth.json
4. GetPlanStatus (代理) → protobuf解析积分 (0x30=used, 0x40=total)
5. 注入token → vscode.commands (windsurf/cascade相关auth/token命令)
```

### Protobuf积分解析
```
Field 6 (0x30): usedCredits * 100 (varint)
Field 8 (0x40): totalCredits * 100 (varint)
remaining = totalCredits - usedCredits
```

### 数据存储
- **账号文件**: `%APPDATA%\Windsurf\User\globalStorage\windsurf-login-accounts.json`
- **Token缓存**: `%APPDATA%\Windsurf\User\globalStorage\windsurf-token-cache.json`
- **认证文件**: `windsurf-auth.json` + `cascade-auth.json` (同目录)
- **Token过期**: 50分钟/账号

## 突破修改清单 (8处)

| # | 位置 | 修改 |
|---|------|------|
| 1 | `validateAccountWithAPI` | 直接返回`{valid:true}` 绕过域名白名单 |
| 2 | `handleAddAccount` | 支持`email:password` `email password` `email\tpassword` `email----password`多格式 |
| 3 | `handleLogin` DOMAIN_NOT_ALLOWED | Firebase官方API直连fallback (`identitytoolkit.googleapis.com`) |
| 4 | `getCreditsOnly` | 代理失败→Firebase直连fallback |
| 5 | `performLogin` | 代理失败→Firebase直连fallback |
| 6 | `refreshAccountCreditsAndUpdateList` | 代理失败→Firebase直连fallback |
| 7 | webview textarea placeholder | 更新提示文本显示多格式支持 |
| 8 | webview addBtn onclick | 移除前端`----a1234561`强制拼接 |

### Firebase官方API Key
`AIzaSyDKm6GGxMJfCbNf-k0kPytiGLaqFJpeSac` (Windsurf/Codeium的Firebase项目)

## 使用方法

### 添加自定义账号 (任何域名+任何密码)
在插件侧边栏输入框中输入:
```
ronebu15431@yahoo.com:@Gu4NUsF2HIp0S
```
支持格式:
- `email----password` (原格式)
- `email:password` (新增)
- `email password` (新增，空格分隔)
- `email` (纯邮箱，使用默认密码a1234561)

### 生效方式
修改后需**重启Windsurf**或**Reload Window**使扩展重新加载。

## 已知限制/不足
1. **代理服务器单点**: 所有API经168666okfa.xyz，该服务宕机则积分查询/auth-token获取失败
2. **Firebase API Key硬编码**: 如Windsurf更换Firebase项目，直连将失效
3. **无代理配置**: 插件不支持设置HTTP代理(对于需要VPN的环境)
4. **Token注入不稳定**: 依赖vscode命令名匹配，Windsurf更新可能改变命令名
5. **积分解析脆弱**: 在protobuf末尾30字节搜索0x30/0x40，可能误匹配
