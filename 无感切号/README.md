# Windsurf小助手 v3.8.0

> 道法自然 · 锚定本源 · 纯账号轮转 · 不降级模型 · 防连锁限流

## 核心

- **号池引擎**: 96账号自动轮转，切换在rate limit之前发生
- **透明代理**: `:19443` protobuf级apiKey替换，LS零感知
- **L5容量探测**: gRPC CheckUserMessageRateLimit，服务端真值
- **三模式号池**: 本地 / 云端 / 混合(本地优先+云端补充)
- **指纹热重置**: 切号前轮转6维设备指纹
- **热重载**: `npm run hot` 零重启部署

## 安装

```bash
windsurf --install-extension windsurf-assistant.vsix --force
```

## 使用

- 侧边栏 **Windsurf小助手** → 号池面板
- `Ctrl+Shift+P` → `Windsurf小助手` 查看15个命令
- Hub: `http://127.0.0.1:9870/health`
- 透明代理: `http://127.0.0.1:19443/api/deep`

## 文件结构

```
src/                    6源文件(extension·auth·account·webview·fingerprint·cloud)
media/                  panel.html + panel.js + icon.svg
scripts/                transparent_proxy.js · hot-deploy.js · fortress.js
```

## License

MIT
