# Agent行为指令 · agent公网管理电脑

> 本目录是"Agent通过公网管理所有电脑"的**统一索引+测试中心**。

## 目录定位

- **本目录**: 全景索引 + E2E测试脚本 + 测试结果
- **核心代码**: `远程桌面/remote-hub/` (server.js, page.js, brain.js, remote_hub.py)
- **统一中枢**: `agent操作电脑/` (hub.py, probe.py)
- **远程桌面**: `远程桌面/` (remote_agent.py, 55+ API)

## 操作规则

1. **只读优先**: 先读README.md了解全景，再操作
2. **不移动文件**: 核心代码在各自源目录，本目录只做索引
3. **测试先行**: 修改任何远程管理代码后，运行 `_e2e_test.ps1` 验证
4. **凭据安全**: 密码见 `secrets.env`，禁止硬编码到任何文件

## 快速操作

```powershell
# 运行E2E测试 (22项, 五感覆盖)
pwsh -NoProfile -File "_e2e_test.ps1"

# 健康检查
curl.exe -sk "https://aiotvr.xyz/agent/health"

# Python SDK
python -c "import sys; sys.path.insert(0,r'd:\道\道生一\一生二\远程桌面\remote-hub'); from remote_hub import RemoteHub; print(RemoteHub().health())"
```

## 关联目录

| 目录 | 用途 | 何时查看 |
|------|------|----------|
| `远程桌面/remote-hub/` | Node.js服务端+前端 | 修改远程中枢 |
| `远程桌面/双机保护手册.md` | 铁律13条+守护体系 | 操作台式机前必读 |
| `远程桌面/` | Python全能Agent(55+API) | 需要截屏/键鼠/Shell |
| `agent操作电脑/` | 14系统统一中枢 | 需要统一入口 |
| `远程桌面/rdp/` | RDP/Shadow/恢复 | 需要RDP连接 |
| `双电脑互联/agent操作电脑/AI_COMPUTER_CONTROL.md` | 全球30+项目对标 | 技术选型/演进 |
| `.windsurf/skills/remote-hub/` | 远程中枢操作技能 | API端点速查 |
