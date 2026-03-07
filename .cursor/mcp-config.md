# Cursor MCP 配置

> Cursor MCP Server配置
> 参考 Windsurf 配置，保留必要的MCP服务

## MCP Servers

| Server | 状态 | 用途 |
|--------|------|------|
| chrome-devtools | 可选 | CDP连接Chrome调试 |
| playwright | 可选 | 浏览器自动化 |
| context7 | 可选 | 库文档查询 |

## 使用方式

在Cursor Settings → Extensions → MCP中配置。

## 与Windsurf的关系

Cursor和Windsurf共享MCP服务配置，修改其一不影响另一个。
建议在Windsurf中配置好MCP，Cursor按需启用。
