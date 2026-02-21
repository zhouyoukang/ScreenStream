# Worktree 多Agent实践指南

> ScreenStream_v2 项目的多Agent并行开发操作手册
> 创建时间：2026-02-20

---

## 一、核心概念（30秒理解）

Worktree = 项目的智能副本。每个 Cascade 对话在自己的副本里工作，改完后合并回来。

```
你的主工作区 (ScreenStream_v2/)
  │
  ├── 你自己 → 正常开发，不受干扰
  │
  ├── Cascade A (Worktree) → 在副本1里改 Input 模块
  ├── Cascade B (Worktree) → 在副本2里改 Streaming 模块
  └── Cascade C (Worktree) → 在副本3里修 Bug
      │
      └── 各自完成后 → 逐个点 Merge → 合并回主工作区
```

**物理隔离**：Agent A 改不到 Agent B 的文件，因为它们在不同目录。
**Git 合并**：冲突在你点 Merge 时解决，不是在编辑时互相踩。

---

## 二、操作步骤

### 2.1 启动一个 Worktree 对话

1. 在 Cascade 面板左上角点 **"+"** 新建对话
2. **在发送任何消息之前**，在输入框底部右下角找到模式切换
3. 切换到 **"Worktree"** 模式
4. 然后发送你的任务指令

> ⚠️ 重要：模式只能在对话开始时选择，中途不能切换。先切模式再发消息。

### 2.2 给 Agent 明确的任务范围

好的任务指令：
```
帮我在 InputRoutes.kt 中添加一个 /api/macro/list 端点，
返回所有已保存的宏列表。参考现有的 /api/input/* 端点格式。
```

不好的任务指令：
```
帮我改进项目
```

**原则**：任务越明确，Worktree 里的改动越干净，合并越容易。

### 2.3 查看进度

- 每个 Worktree 对话独立运行，你可以在 Cascade 面板顶部下拉菜单切换查看
- Agent 会通过 cunzhi 弹窗汇报进度（exe 直调，每次必弹）
- 你的主工作区文件不受影响，可以继续自己的工作

### 2.4 合并改动

当 Agent 完成任务后：
1. Cascade 对话中会出现 **"Merge"** 按钮
2. 点击 Merge
3. 如果无冲突 → 自动合并到主工作区
4. 如果有冲突 → Git 标准冲突标记出现，你手动解决

**合并顺序建议**：
- 逐个合并，不要同时 Merge 多个 Worktree
- 每次 Merge 后检查一下改动是否合理
- 有问题可以 git revert

### 2.5 清理

- Windsurf 自动清理老的 Worktree（每个工作区最多 20 个）
- 删除 Cascade 对话会自动删除对应 Worktree
- 手动查看：在终端运行 `git worktree list`

---

## 三、并行模式推荐

### 模式 A：你 + 1个 Agent（最常用）

```
你：在主工作区做主要开发
Agent A (Worktree)：做一个独立子任务（如修 Bug、加测试、写文档）
→ Agent 完成后 Merge 回来
```

适合：日常开发，Agent 做辅助工作

### 模式 B：多 Agent 并行（功能开发）

```
你：在主工作区做架构设计/代码审查
Agent A (Worktree)：做 Input 模块的新功能
Agent B (Worktree)：做前端 index.html 的对应 UI
→ 分别完成后，先 Merge A，再 Merge B
```

适合：大功能开发，可以拆成独立模块的任务

### 模式 C：探索/实验

```
Agent A (Worktree)：用方案 A 实现某功能
Agent B (Worktree)：用方案 B 实现同一功能
→ 你比较两个结果，Merge 更好的那个，丢弃另一个
```

适合：不确定最佳方案时，让两个 Agent 同时尝试

---

## 四、ScreenStream_v2 特定注意事项

### 4.1 构建（Gradle）

- **同时只有一个 Agent 可以构建**（共享 Gradle daemon）
- 推荐：让 Agent 只写代码，**你在主工作区统一构建**
- 如果 Agent 需要构建验证，确保同一时间只有一个在构建

### 4.2 部署（ADB）

- **同时只有一个 Agent 可以操作手机**
- 推荐：部署统一在主工作区执行 `dev-deploy.ps1`
- Agent 可以写代码但不推送到手机

### 4.3 共享关键文件

以下文件可能被多个 Agent 同时修改：
- `build.gradle.kts` / `settings.gradle.kts`
- `libs.versions.toml`
- `InputRoutes.kt`（路由注册）
- `index.html`（前端入口）

**处理方式**：每个 Worktree 有自己的副本，冲突在 Merge 时解决。
**最佳实践**：给不同 Agent 分配不同模块的任务，减少共享文件冲突。

### 4.4 Worktree Setup Hook

项目已配置 `post_setup_worktree` 钩子（`hooks/setup_worktree.py`），
创建 Worktree 时自动复制 `local.properties` 和 `google-services.json`（如果存在）。

---

## 五、常见问题

### Q: Worktree 里能构建 APK 吗？
A: 可以，但同时只能有一个构建。推荐让 Agent 只写代码，你统一构建。

### Q: Agent 能看到其他 Agent 的改动吗？
A: 不能。每个 Worktree 是独立副本。只有 Merge 到主分支后才可见。

### Q: 冲突怎么办？
A: Git 标准冲突解决。Merge 时 Windsurf 会提示冲突文件，你手动选择保留哪个。

### Q: 磁盘空间够吗？
A: Worktree 共享 git 对象库，额外空间主要是工作文件。ScreenStream 项目不大，20 个 Worktree 完全可控。

### Q: 能不能让 Agent 只修改特定目录？
A: 通过任务指令约束（"只修改 040-反向控制_Input/ 目录"）。
   如果需要物理强制，可以配置 `pre_write_code` hook 做 zone guard（见 docs/CUNZHI_V4_DESIGN.md）。

### Q: Worktree 和普通 git branch 有什么区别？
A: Branch 是版本控制概念（共享工作目录），Worktree 是文件系统概念（独立工作目录 + 独立分支）。
   两个 branch 切换需要 stash/checkout，两个 Worktree 同时存在不需要切换。

---

## 六、快速参考

| 操作 | 怎么做 |
|------|--------|
| 新建 Worktree 对话 | Cascade "+" → 底部切 Worktree → 发消息 |
| 查看所有 Worktree | 终端：`git worktree list` |
| 合并改动 | Cascade 对话中点 "Merge" |
| 查看 Worktree 在 SCM | settings: `git.showWindsurfWorktrees: true` |
| 手动删除 Worktree | `git worktree remove <path>` |
| 清理无效 Worktree | `git worktree prune` |
