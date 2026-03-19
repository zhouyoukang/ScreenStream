# Windsurf无限额度 · Agent操作指令 (清理后 v5.0)

> **2026-03-12: WU已彻底卸载，台式机141恢复Windsurf官方直连。**
> 此目录为逆向研究归档，不再有活跃的无限额度服务。

## 台式机141 当前状态
| 组件 | 状态 | 说明 |
|------|------|------|
| Windsurf v1.108.2 | ✅ 官方直连 | `D:\Windsurf\`, proxySupport=override |
| Vortex Helper :7890 | ✅ 运行中 | 正常翻墙代理(非无限额度工具) |
| WindsurfUnlimited | ⛔ **已卸载** | App+Roaming+Guardian全删 |
| JS Patches | ⚠️ 仍在 | 仅cosmetic,不影响官方连接 |

## Agent操作
- **验证清理状态**: `powershell -File "Windsurf无限额度\verify_clean.ps1"`
- **JS补丁还原**: `python patch_windsurf.py --restore`
- **JS补丁验证**: `python patch_windsurf.py --verify`

## 关键配置
| 配置 | 值 | 说明 |
|------|-----|------|
| `proxySupport` | `"override"` | Windsurf通过Vortex系统代理访问Codeium |
| `proxyStrictSSL` | `true` | 标准TLS验证(无MITM) |
| Git proxy | `127.0.0.1:7890` | 全局+GitHub-specific |

## 铁律
- **proxySupport必须"override"** (Vortex依赖系统代理)
- **代理端口 = 7890** (Vortex), 非7897
- **禁止手动运行wu_guardian.py** (WU已卸载,guardian无目标)
- hosts文件只保留localhost,禁止添加codeium/windsurf劫持
- SSL_CERT_FILE和NODE_TLS_REJECT_UNAUTHORIZED禁止设置
