# AGENTS.md — Windsurf无限额度

## 目录用途
Windsurf IDE额度优化研究。包含深度逆向分析报告、VM部署脚本、代理证书。

## 关键文件
| 文件 | 用途 | 修改风险 |
|------|------|---------|
| `patch_windsurf.py` | 客户端补丁v3.1 (15项补丁) | 🟡中 — 版本敏感 |
| `deploy_vm.ps1` | VM部署脚本v4.0 | 🟡中 |
| `CodeFreeWindsurf_深度逆向报告.md` | 逆向分析文档 | 🟢低 — 只读参考 |
| `审计报告.md` | 五感审计报告 | �低 — 记录文档 |
| `windsurf_proxy_ca.cer` | 代理CA证书 | 🔴高 — 安全敏感 |

## 与其他项目关系
- **完全独立**: 无跨项目依赖
- **参考价值**: 为 `.windsurf/` 配置体系提供背景知识

## Agent操作规则
- 证书文件不可随意分发
- `patch_windsurf.py` 的补丁字符串与Windsurf版本强绑定，升级后需验证
- 补丁操作前自动备份(.bak)，可 `--restore` 还原
- 补丁目标: `D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js`
