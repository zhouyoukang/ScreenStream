# 密码管理中枢 — 凭据安全的统一治理

> 道生一(secrets.env)，一生二(凭据中心.md索引)，二生三(Agent协议)，三生万物(所有项目安全引用)。

## 架构总览

```
密码管理/
├── README.md          ← 本文件：全景审计 + 架构说明
├── AGENTS.md          ← Agent操作本目录的指令
├── audit.py           ← 自动化审计脚本（检测泄露+一致性）
└── sync_check.py      ← 双机secrets.env同步检查

凭据中心.md  (项目根)   ← 结构索引（git tracked，无实际值）
secrets.env  (项目根)   ← 实际值（gitignored，唯一真相源）
```

## 四层架构（道·法·术·器）

| 层 | 文件 | 角色 | Git |
|----|------|------|-----|
| **道** | 本README | 哲学原则 + 审计报告 | tracked |
| **法** | `凭据中心.md` | 结构索引 + Agent协议 | tracked |
| **术** | `secrets.env` | 实际凭据值 | **gitignored** |
| **器** | `audit.py` | 自动化检测工具 | tracked |

## 铁律五条（R1-R5）

- **R1**: Memory禁止存储实际密码/Token值（只存键名引用）
- **R2**: git tracked文件禁止明文凭据（用`[见secrets.env KEY]`替代）
- **R3**: 新增凭据必须同时更新 `secrets.env` + `凭据中心.md`
- **R4**: 修改凭据只改 `secrets.env` 一处
- **R5**: 项目级secrets文件(如secrets.toml)必须从secrets.env读取，不独立维护值

## 伏羲八卦全景审计报告

*审计时间: 本次会话 | 审计范围: 全工作区*

### ☰乾·总览

| 指标 | 值 |
|------|-----|
| secrets.env 凭据总数 | ~60+ 键值对 |
| 凭据中心.md 索引条目 | 20个section |
| 项目级secrets文件 | 2个 (secrets.env, 阿里云secrets.toml) |
| 引用凭据的Python文件 | 85+ |

### ☲离·发现的问题

#### 🔴 Critical (已修复)

| # | 问题 | 文件 | 修复方式 |
|---|------|------|---------|
| C1 | 统一密码明文泄露 | `agent公网管理电脑/_e2e_test.ps1` L23 | → 从secrets.env动态读取 |
| C2 | 三创赛登录密码泄露 | `国创赛项目/README.md` L50 | → `[见secrets.env]`引用 |
| C3 | 三创赛登录密码泄露 | `国创赛项目/网络资源汇编.md` L145 | → `[见secrets.env]`引用 |
| C4 | 审计报告含原始密码 | `远程桌面/REMOTE_CONTROL_AUDIT.md` L177 | → `[硬编码密码]`脱敏 |

#### 🟡 Warning (架构层面)

| # | 问题 | 说明 |
|---|------|------|
| W1 | secrets.toml冗余 | `阿里云服务器/secrets.toml` 独立维护FRP凭据，应从secrets.env读取 |
| W2 | config.json分散 | `智能家居/网关服务/config.json` 含微信凭据（已gitignored，风险可控） |

#### 🟢 Good Practice

| # | 实践 | 说明 |
|---|------|------|
| G1 | secrets.env已gitignore | ✅ 根.gitignore已包含 |
| G2 | 凭据中心.md结构完整 | ✅ 20个section覆盖所有系统 |
| G3 | Agent协议已定义 | ✅ 铁律5条 + Python/PS模板 |
| G4 | 环境变量路径已设 | ✅ SECRETS_ENV_PATH 用户环境变量 |

### ☳震·多Agent并行本质需求分析

#### 核心矛盾

```
多Agent并行 × 凭据共享 = 冲突风险
```

**Worktree架构下的凭据问题**：
- 每个worktree是独立目录 → 各有独立的`secrets.env`副本
- Git不同步gitignored文件 → 新worktree缺少secrets.env
- 多Agent同时读secrets.env → 无冲突（只读操作）
- 多Agent同时改secrets.env → 需串行（但极少发生）

#### 解决方案（已实现 + 建议）

| 层面 | 方案 | 状态 |
|------|------|------|
| **环境变量** | `SECRETS_ENV_PATH` 指向固定路径 | ✅ 已实现 |
| **Agent协议** | 铁律5条 + 读取模板 | ✅ 已实现 |
| **Worktree** | 新worktree自动symlink secrets.env | 🔲 建议 |
| **审计** | audit.py 定期扫描泄露 | ✅ 本次创建 |
| **双机同步** | SMB共享 + sync_check.py | ✅ 本次创建 |

#### 多Agent凭据读取流程

```
Agent需要凭据
    │
    ├─ 1. 读 凭据中心.md → 了解有哪些键
    │
    ├─ 2. 读 secrets.env → 获取实际值
    │     优先: $env:SECRETS_ENV_PATH
    │     备选: 项目根/secrets.env
    │
    ├─ 3. 使用后不存入Memory
    │
    └─ 4. 代码中用 os.environ/dotenv 引用
```

### ☵坎·风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| secrets.env意外提交 | 低 | 高 | .gitignore + pre-commit hook |
| 新文件硬编码密码 | 中 | 中 | audit.py定期扫描 |
| worktree缺secrets.env | 中 | 低 | SECRETS_ENV_PATH环境变量 |
| 双机secrets.env不同步 | 中 | 低 | sync_check.py |

### ☶艮·涅槃门验证

| 判据 | 状态 |
|------|------|
| **苦灭**: 4处密码泄露已修复？ | ✅ |
| **新苦**: 修复引入新问题？ | ✅ 无 |
| **熵减**: 系统更整洁？ | ✅ 统一治理点 |
| **智增**: 洞见已记录？ | ✅ 本文件 |

---

*创建: 本次审计 | 维护: 发现新问题时更新*
