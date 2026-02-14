---
description: 编写和运行测试。当需要为代码添加测试、验证功能正确性、或提高测试覆盖率时触发。
---

# /test — 测试工作流

## Phase 1: 分析测试需求

1. 确定测试类型：
   - **单元测试** — 单个函数/类
   - **集成测试** — 模块间交互
   - **端到端测试** — 完整用户流程
   - **回归测试** — Bug 修复后防止复发

2. 确定测试框架（根据项目技术栈）：
   | 语言 | 框架 | 运行命令 |
   |------|------|---------|
   | Kotlin/Java | JUnit5 + MockK | `./gradlew test` |
   | TypeScript | Jest / Vitest | `npm test` |
   | Python | pytest | `pytest -v` |
   | Go | testing | `go test ./...` |

## Phase 2: 编写测试

**AAA 模式**（Arrange → Act → Assert）：

```kotlin
@Test
fun `should return error when input is empty`() {
    // Arrange
    val service = MyService()
    val input = ""
    // Act
    val result = service.process(input)
    // Assert
    assertTrue(result.isFailure)
}
```

**必须覆盖的场景**：
- ✅ Happy path（正常路径）
- ✅ 边界条件（空值、零、最大值、空集合）
- ✅ 错误路径（异常输入、权限不足、网络失败）
- ✅ 并发场景（如适用）

**命名规范**：`should_[预期行为]_when_[条件]`

## Phase 3: 运行测试

// turbo
执行项目的测试命令，分析结果：
- 全部通过 → Phase 4
- 有失败 → 分析原因，修复代码或测试

## Phase 4: 总结

```
## 测试结果
- **新增测试**: N 个
- **覆盖场景**: happy path / 边界 / 错误 / 并发
- **运行结果**: 全部通过 / N 个失败
```
