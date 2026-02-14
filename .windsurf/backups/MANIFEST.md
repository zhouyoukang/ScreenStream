# 配置备份清单（MANIFEST）

> 最后备份时间：2026-02-13 11:10
> 用途：IDE 重启/规则丢失时，AI 可从此处恢复关键配置文件

## 备份内容

### rules/ — 项目规则备份（6 个文件）
| 文件 | 原始路径 | 说明 |
|------|---------|------|
| soul.md | `.windsurf/rules/soul.md` | AI 思维内核 + 全流程开发思维 |
| execution-engine.md | `.windsurf/rules/execution-engine.md` | 执行引擎 + 开发管线协议 |
| project-structure.md | `.windsurf/rules/project-structure.md` | 项目结构映射 |
| kotlin-android.md | `.windsurf/rules/kotlin-android.md` | Kotlin/Android 规则 |
| frontend-html.md | `.windsurf/rules/frontend-html.md` | 前端开发规则 |
| build-deploy.md | `.windsurf/rules/build-deploy.md` | 构建部署流程 |

### global/ — 全局规则备份
| 文件 | 原始路径 |
|------|---------|
| global_rules.md | `~/.codeium/windsurf/memories/global_rules.md` |

## 恢复方法

### 项目规则恢复
```
复制 .windsurf/backups/rules/*.md → .windsurf/rules/
```

### 全局规则恢复
```
复制 .windsurf/backups/global/global_rules.md → ~/.codeium/windsurf/memories/global_rules.md
```

### 其他恢复源
- 升级包：`e:\windsurf-intelligence-pack\`
- 全局 Skills 模板：`~/.codeium/windsurf/skills/project-init/templates/`
- Memory 系统：搜索相关 Memory 获取内容指引

## 备份更新策略
- 规则文件有重大修改时，AI 应主动更新备份
- 使用 `/health-check` 工作流验证备份与原文件一致性
