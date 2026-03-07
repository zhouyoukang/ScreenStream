# 三界隔离 — 实施状态 (2026-02-25)

## 账号架构

| 账号 | 角色 | 状态 | 密码 | 组 |
|------|------|------|------|-----|
| **zhouyoukang** | 天界·主账号 | 启用 | (原密码) | Administrators |
| **windsurf-test** | 地界·双子账号 | 启用 | 0066 (快速切换) | RDP Users, Remote Mgmt Users |
| 32286 | — | **禁用** | [见secrets.env] | — |
| AIOTVR | — | **禁用** | [见secrets.env] | — |
| 周 | — | **禁用** | [见secrets.env] | — |
| Guest | — | **禁用** | — | — |

> 密保问题答案均为: 龙游

## 地界环境配置

| 项目 | 状态 | 详情 |
|------|------|------|
| PATH | ✅ | ADB + Windsurf + Git 已加入用户PATH |
| ANDROID_HOME | ✅ | E:\道\道生一\一生二\构建部署\android-sdk |
| Git config | ✅ | user=windsurf-agent, safe.directory已配 |
| Windsurf IDE | ✅ | settings.json已配(深色主题, [AGENT]窗口标题) |
| 桌面快捷方式 | ✅ | ScreenStream / Terminal / 返回天界 / 三界状态 |
| JDK 17 | ✅ | Temurin 17.0.18, JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot |

## 共享数据层 (人界)

| 路径 | 权限 | 状态 |
|------|------|------|
| E:\道\ | Authenticated Users: Modify | ✅ |
| E:\github\ | Authenticated Users: Modify | ✅ |
| SMB C/D/E | 全盘共享 | ✅ |
| Git | E:\道\道生一\一生二 | ✅ |

## 连接通道状态

| 通道 | 状态 | 说明 |
|------|------|------|
| **快速用户切换** | ✅ | tsdiscon.exe / Win+L / Ctrl+Alt+Del |
| RDP本地连接 | ⚠️ | rdpwrap.dll已hook, 但mstsc客户端崩溃(兼容性问题) |
| WinRM远程执行 | ❌ | PSSession endpoint无法启动主机进程 (已知问题) |
| RDP凭据 | ✅ | 已保存到cmdkey (TERMSRV/127.0.0.1) |

### 使用方法

```
进入地界: Win+L → 选windsurf-test → 密码 0066
返回天界: Win+L → 选zhouyoukang
两个会话同时保活，切换瞬间完成
```

## 系统级工具链 (12/12 全绿)

| 工具 | 版本 |
|------|------|
| Git | 2.50.1 |
| Python | 3.11.4 |
| Node | 24.13.0 |
| npm | 11.6.2 (D:\npm.cmd) |
| JDK | Temurin 17.0.18 |
| ADB | 1.0.41 (system PATH) |
| Windsurf | D:\Windsurf |
| pwsh | 7.5.4 |
| Docker | 27.5.1 |
| ssh | OpenSSH 9.5p2 |
| curl | 8.16.0 |
| Gradle | gradlew.bat |

## 待修复项

### WinRM PSRemoting (优先级: 低)
- 症状: "WSMan无法启动主机进程"
- 已尝试: Enable-PSRemoting in pwsh+powershell.exe
- 不影响核心功能(快速用户切换+RDP均可用)

## 工具清单 (12文件)

```
构建部署/三界隔离/
  地界.rdp         — RDP连接文件 (双击连接)
  enter.ps1        — 智能进入 (auto/rdp/switch)
  enter.cmd        — 双击锁屏切换
  return.ps1       — 地界切回天界
  status.ps1/cmd   — 三界状态面板
  init-agent.ps1   — 地界首次环境初始化
  save-cred.ps1    — 保存RDP凭据
  remote-exec.ps1  — 远程执行 (待WinRM修复后可用)
  AGENTS.md        — Agent指令
  README.md        — 架构文档
  STATUS.md        — 本文件
```
