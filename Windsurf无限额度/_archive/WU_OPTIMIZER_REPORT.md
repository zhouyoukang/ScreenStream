# WU 全维度诊断报告
> 时间: 2026-03-12T17:39:11.564025
> 评分: 14.0/17 (82%)

## 诊断结果

| 状态 | 卦 | 检查项 | 详情 |
|------|-----|--------|------|
| ✅ | ☰ | WU安装 | 180MB |
| ✅ | ☰ | WU进程 | 4个进程运行中 |
| ✅ | ☰ | MITM代理 | 127.65.43.21:443 监听中 |
| ✅ | ☰ | 会话状态 | 天卡 | 剩余22.0h | https://windsurf-unlimited.chaogei.top |
| ✅ | ☷ | hosts劫持 | 127.65.43.21 → server.self-serve.windsurf.com, server.codeium.com |
| ❌ | ☷ | CA证书 | WU MITM CA未安装 |
| ✅ | ☷ | portproxy | 无冲突规则 |
| ✅ | ☷ | Windsurf进程 | 13个进程 |
| ⚠️ | ☲ | 积分查询 | API失败: HTTP Error 403: Forbidden |
| ⚠️ | ☳ | TLS握手 | 14ms | 证书异常: unknown |
| ✅ | ☳ | DNS server.self-serve.wi | → 127.65.43.21 ✓ |
| ✅ | ☳ | DNS server.codeium.com | → 127.65.43.21 ✓ |
| ❌ | ☳ | WU后端 | HTTP Error 403: Forbidden |
| ✅ | ☴ | main.js补丁 | 已补丁 (asar=31,793,343B vs orig=31,791,271B) |
| ✅ | ☶ | proxyStrictSSL | false (MITM兼容) |
| ✅ | ☶ | proxySupport | off (不干扰MITM) |
| ✅ | ☶ | user_settings.pb | 82,516B (WU管理detect_proxy) |

## ❌ 错误

- CA证书: WU MITM CA未安装
- WU后端: HTTP Error 403: Forbidden

## ⚠️ 警告

- 积分查询: API失败: HTTP Error 403: Forbidden
- TLS握手: 14ms | 证书异常: unknown

## 📋 优化建议

### 立即执行
1. 如果天卡已过期 → WU界面续费或切换卡密
2. 运行 `python wu_patch_asar.py` → 注入429重试+增加重试次数
3. Windsurf模型切换到 **SWE-1.6** (0积分消耗)

### 长期优化
4. 运行 `python wu_optimizer.py --monitor` 持续监控
5. 避免使用 Claude Opus 4.6 thinking (5-10x积分消耗)
6. 开启 AutoContinue + 0x模型 = 零成本续接