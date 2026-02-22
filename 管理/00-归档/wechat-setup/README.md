# 微信公众号 — 智能家居控制入口

## 当前状态
- **代码**: 完成 (wechat_handler.py 422行)
- **测试**: 39/39 全部通过 (离线11 + 在线8 + 全品类20)
- **注册**: 待扫码（测试号页面: mp.weixin.qq.com/debug/cgi-bin/sandbox）

## 关联文件
| 文件 | 作用 |
|------|------|
| `100-.../07-.../wechat_handler.py` | 消息处理（命令解析+设备控制+场景宏+TTS+语音代理） |
| `100-.../07-.../config.json` | Gateway 配置（wechat段，token已设，appid待填） |
| `100-.../07-.../test_wechat.py` | 离线单元测试 (11项) |
| `100-.../07-.../test_wx_live.py` | 在线路由测试 (8项) |
| `100-.../07-.../test_wx_commands.py` | 全品类命令覆盖 (20项) |
| `100-.../07-.../start_wechat.bat` | 一键启动 Gateway + Cloudflare Tunnel |

## 注册流程
```bash
# 1. 浏览器打开测试号页面，微信扫码
https://mp.weixin.qq.com/debug/cgi-bin/sandbox?t=sandbox/login

# 2. 获取 appid/appsecret，填入 config.json 的 wechat 段

# 3. 启动 Gateway + Tunnel
cd 100-智能家居_SmartHome/07-网关服务_Gateway && start_wechat.bat

# 4. 在测试号页面配置: URL=公网URL/wx  Token=smarthome2026

# 5. 验证
python test_wx_live.py https://xxx.trycloudflare.com
```

## 2026-02-22 Bug修复
| Bug | 根因 | 修复 |
|-----|------|------|
| "关闭摄像头"解析为"闭摄像头" | `set`无序迭代，短关键词"关"先于"关闭"匹配 | `sorted(keywords, key=len, reverse=True)` |
| "全部关闭"超时10s+ | `quick_action`同步遍历24设备(多数离线) | 改为`asyncio.create_task`后台执行 |
| httpx测试脚本全部502 | 系统代理127.0.0.1:7897拦截本地请求 | `NO_PROXY=127.0.0.1,localhost` |

## 测试号 vs 正式号
| 特性 | 测试号 | 订阅号(个人) | 服务号(企业) |
|------|--------|-------------|-------------|
| 注册 | 扫码即得 | 身份证 | 营业执照 |
| API权限 | 全部 | 基础 | 全部 |
| 关注人数 | 100人 | 无限 | 无限 |
| **适用** | **开发测试** | 内容发布 | 商业服务 |

> 智能家居场景用测试号完全够用（个人/家庭使用，不需要群发）。
