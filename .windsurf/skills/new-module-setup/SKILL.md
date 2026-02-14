---
name: new-module-setup
description: 在ScreenStream项目中创建新模块或新的子功能目录。当需要添加新模块、新协议支持、或重组项目结构时触发。
---

## 新模块检查清单

### 1. 目录结构
```
<编号>-<中文名>_<英文名>/
├── AGENTS.md           ← 必须创建：模块专属AI指令
├── build.gradle.kts    ← Gradle模块配置
└── src/
    └── main/
        ├── kotlin/     ← Kotlin源码
        └── AndroidManifest.xml
```

### 2. Gradle 注册
在 `settings.gradle.kts` 中添加:
```kotlin
include(":<module-name>")
project(":<module-name>").projectDir = file("<目录路径>")
```

### 3. AGENTS.md 模板
```markdown
# <模块名称>

## 核心职责
<一句话描述>

## 关键文件
- `<file1>` — <说明>

## 关键约束
- <约束1>
- <约束2>

## 与其他模块的关系
- <依赖/被依赖关系>
```

### 4. 端口分配（如需HTTP服务）
当前已占用: 8080-8084
新端口从 8085 开始分配，必须在 `project-structure` 规则中登记。

### 5. 文档更新
- `05-文档_docs/MODULES.md` — 添加新模块说明
- `05-文档_docs/README.md` — 更新项目概览
