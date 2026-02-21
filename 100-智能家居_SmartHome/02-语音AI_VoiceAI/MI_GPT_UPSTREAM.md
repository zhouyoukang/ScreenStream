# mi-gpt 上游项目参考

> 源项目: `e:\mi-gpt-4.2.0\` | GitHub: `idootop/mi-gpt`
> 原版MiGPT，Node.js/TypeScript实现

## 定位

MIGPT-Easy的上游灵感来源。将小爱音箱接入ChatGPT的开源项目。

## 核心特性

- AI问答（接入大模型）
- 角色扮演（自定义人设）
- 流式响应
- 长短期记忆
- 自定义TTS（豆包音色）
- 智能家居Agent（规划中）

## 技术栈

- **运行时**: Node.js / Docker
- **语言**: TypeScript
- **数据库**: Prisma ORM
- **包管理**: pnpm

## 与MIGPT-Easy的差异

| 维度 | mi-gpt (上游) | MIGPT-Easy (用户版) |
|------|--------------|-------------------|
| 语言 | TypeScript/Node.js | Python |
| 多设备 | 单设备 | 多设备同控 |
| HA集成 | 规划中 | 已实现 |
| GUI | 无 | 图形化配置 |
| 多模型 | 主要OpenAI | 10+模型支持 |
| 自动切换 | 手动 | NLP自动判断 |

## 参考价值

- 流式对话的实现思路
- 小米服务API的对接方式
- TTS引擎集成
- 未来Agent架构设计

## 相关文档

- `e:\mi-gpt-4.2.0\docs\` — 完整文档目录
- `e:\mi-gpt-4.2.0\assets\pdf\` — 教程PDF
