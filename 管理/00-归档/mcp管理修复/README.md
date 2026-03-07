# MCP 管理修复

> 唯一真相源：MCP配置、诊断、修复的完整知识库
> 2026-02-27 三祸 → 2026-03-04 五祸 → 2026-03-05 八祸根治 → 2026-03-06 九祸(npx超时) → 2026-03-08 伏羲全审计

## 九祸根治

| # | 祸 | 症状 | 根因 | 修复 |
|---|-----|------|------|------|
| 1 | **BOM** | 0 MCPs（全部消失） | PS `[Encoding]::UTF8` 写BOM → hujson解析失败 | `[UTF8Encoding]::new($false)` |
| 2 | **npx** | 新窗口0 MCPs | Windows `spawn()` 不解析 `.cmd` | `"command": "npx.cmd"` |
| 3 | **${env:}** | GitHub `pipe closed` | 插值传字面量，认证失败 | 移除插值，系统env继承 |
| 4 | **fetch代理** | GitHub `fetch failed` | undici不使用HTTP_PROXY | `NODE_OPTIONS=--require bootstrap.js` |
| 5 | **Playwright** | `icu_util.cc` 崩溃 | 缺`--browser chromium`→用旧系统Chrome | 加参数 + 代理env + install |
| 6 | **env感染** | GitHub/Playwright黄点 | `env`段中的`NODE_OPTIONS`感染npx所有子进程 | cmd.exe wrapper绕过npx |
| 7 | **gzip腐败** | GitHub API返回乱码 | bootstrap.js不处理gzip/chunked → 二进制当UTF-8解析 | `Accept-Encoding: identity` |
| 8 | **代理干扰CDP** | Playwright黄点 | `HTTPS_PROXY`干扰Playwright本地CDP连接 | 移除Playwright的env段 |
| 9 | **npx超时** | 3/4红灯(deadline exceeded) | `npx -y pkg@latest`首次~105秒，超60秒超时 | 全局安装+wrapper脚本绕过npx |

**万法归宗**：有`env`段的MCP全部黄点，无`env`段的全部绿点。`env`引入外部依赖(Clash/bootstrap.js)，任一失效→MCP STDIO握手超时。npx引入网络依赖，首次/更新检查超时→全局安装+直接node执行。

## 标准配置 (v4 — 全局安装+wrapper脚本)

`~/.codeium/windsurf/mcp_config.json`（4个MCP，~15%上下文税）：

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "cmd.exe",
      "args": ["/c", "C:\\temp\\chrome-devtools-mcp.cmd"],
      "disabled": false
    },
    "context7": {
      "command": "cmd.exe",
      "args": ["/c", "C:\\temp\\context7-mcp.cmd"],
      "disabled": false
    },
    "github": {
      "command": "cmd.exe",
      "args": ["/c", "C:\\temp\\github-mcp.cmd"],
      "disabled": false
    },
    "playwright": {
      "command": "cmd.exe",
      "args": ["/c", "C:\\temp\\playwright-mcp.cmd"],
      "disabled": false
    }
  }
}
```

**已移除**：
- `fetch`：弹窗硬编码无法关闭，IWR替代
- `sequential-thinking`：导致对话中断（Windsurf不稳定）

**关键变更**：
- **v1→v2**: GitHub `npx+env` → `cmd.exe` wrapper; Playwright移除`env`段
- **v2→v3**: 移除fetch(禁用)+sequential-thinking(中断), 6→4个MCP
- **v3→v4**: 全部4个MCP改为`cmd.exe`+wrapper脚本（绕过npx超时），初始化<2秒
- **原则**: 不在`env`段放代理设置，代理逻辑封装在wrapper脚本中; ☶艮·知止（每增1MCP≈+3-5%上下文税）

**前置条件**：`GITHUB_PERSONAL_ACCESS_TOKEN` 系统环境变量 · Clash:7890运行 · `C:\temp\github-proxy-bootstrap.js` 存在 · UTF-8无BOM · 4个MCP包已全局安装(`npm i -g chrome-devtools-mcp @upstash/context7-mcp @playwright/mcp @modelcontextprotocol/server-github`)

## GitHub fetch代理原理

Node.js native `fetch`（undici引擎）**不使用** `HTTP_PROXY` 环境变量。`bootstrap.js` v3 通过 `node --require` 注入，使用 undici `ProxyAgent`（连接池+TLS+自动重试）：

```text
HTTPS请求 → undici ProxyAgent → Clash:7890 CONNECT tunnel → TLS握手 → 响应
```

**v3架构**：`github-mcp.cmd` → Clash预检+自动启动 → `node --require bootstrap.js server.js`

关键文件：
- `C:\temp\github-proxy-bootstrap.js`（运行时副本）
- `C:\temp\github-mcp.cmd`（运行时wrapper）
- `.windsurf/github-proxy-bootstrap.js`（源码）
- `.windsurf/github-mcp.cmd`（wrapper源码）

**陷阱**：

- bootstrap路径不能含中文（`--require` 解析失败）
- 必须设默认 `User-Agent`（GitHub API拒绝无UA请求）
- Clash需 `mode=rule` + 代理节点可达（非DIRECT）
- **禁止** `NODE_OPTIONS=--require`（会感染npx/npm等所有Node.js子进程）
- localhost/127.0.0.1请求自动跳过代理（防止干扰本地服务）
- v3用undici ProxyAgent，不再需要`Accept-Encoding: identity`（v2陷阱已消除）

## Playwright 浏览器管理

```powershell
# 安装/更新（需代理）
$env:HTTPS_PROXY='http://127.0.0.1:7890'; npx.cmd -y playwright install chromium

# 浏览器目录
$env:LOCALAPPDATA\ms-playwright\
```

**不加 `--browser chromium`** → Playwright用系统Chrome（`AppData\Local\Google\Chrome\Application\chrome.exe`），版本不匹配会ICU崩溃。

## GitHub MCP 功能验证 (2026-03-04)

**22/24 通过 (91.7%)** · 测试仓库 `zhouyoukang/mcp-test-repo`

| 类别 | 功能 | 状态 |
|------|------|:----:|
| 搜索 | search_repositories / users / code / issues | 4/4 ✅ |
| 查询 | get_file_contents / list_commits / issues / PRs | 4/4 ✅ |
| 仓库 | create_repository / create_branch / push_files / create_or_update_file | 4/4 ✅ |
| Issue | create_issue / get_issue | 2/2 ✅ |
| Issue | add_issue_comment / update_issue | 0/2 ❌ |
| PR | create_PR / get_PR / files / comments / reviews / status | 6/6 ✅ |
| PR | create_review(COMMENT) / merge_PR(squash) | 2/2 ✅ |
| 其他 | fork_repository / update_pull_request_branch | 2/2 ✅ |

**❌ 2个失败**：Fine-grained PAT缺Issues写权限 → GitHub Settings补充即可

**限制**：不能APPROVE自己的PR · `search_issues`必须含`is:issue`

## GitHub MCP 备用方案 (2026-03-08)

当GitHub MCP不可用时（Clash挂了/代理超时/PAT过期），Agent可通过`github-fallback.ps1`降级调用GitHub REST API：

```powershell
# 健康检查
powershell -ExecutionPolicy Bypass -File "mcp管理修复\github-fallback.ps1" health

# 搜索仓库
powershell -ExecutionPolicy Bypass -File "mcp管理修复\github-fallback.ps1" search-repos "query" -n 5

# 获取文件
powershell -ExecutionPolicy Bypass -File "mcp管理修复\github-fallback.ps1" get-file owner/repo path/to/file

# 列出Issues/PRs/Commits
powershell -ExecutionPolicy Bypass -File "mcp管理修复\github-fallback.ps1" list-issues owner/repo
powershell -ExecutionPolicy Bypass -File "mcp管理修复\github-fallback.ps1" list-prs owner/repo
powershell -ExecutionPolicy Bypass -File "mcp管理修复\github-fallback.ps1" list-commits owner/repo -n 5

# 创建Issue
powershell -ExecutionPolicy Bypass -File "mcp管理修复\github-fallback.ps1" create-issue owner/repo "title" "body"
```

**架构**：`curl.exe` + Clash代理（自动检测） + GitHub PAT（系统环境变量）
**降级链**：GitHub MCP → github-fallback.ps1(curl+proxy) → 手动浏览器

## 铁律

```powershell
# 写配置的唯一正确方式
[System.IO.File]::WriteAllText($path, $json, [System.Text.UTF8Encoding]::new($false))
```

- **command**：Windows必须 `npx.cmd`（GitHub例外，用`cmd.exe`+wrapper）
- **env**：尽量不用！代理设置放wrapper脚本，不放`env`段（万法归宗教训）
- **bootstrap路径**：不含中文，放 `C:\temp\`
- **配置生效**：优先用 `mcp-manager.py`（自动刷新），否则 `Ctrl+Shift+P` → `Developer: Reload Window`
- **全局安装GitHub MCP**：`npm install -g @modelcontextprotocol/server-github`（wrapper需要）

## 运行时MCP管理器

Windsurf运行中完成MCP添加/删除/修复，**无需Reload Window**：

```powershell
python mcp管理修复/mcp-manager.py status        # 全面健康检查(九祸+配置+进程+网络)
python mcp管理修复/mcp-manager.py list          # 列出所有MCP服务器
python mcp管理修复/mcp-manager.py catalog       # 显示可用模板(12个)
python mcp管理修复/mcp-manager.py add memory     # 添加服务器(自动刷新)
python mcp管理修复/mcp-manager.py remove memory  # 删除服务器
python mcp管理修复/mcp-manager.py disable fetch  # 禁用服务器
python mcp管理修复/mcp-manager.py fix            # 九祸自动修复
python mcp管理修复/mcp-manager.py refresh        # 触发Windsurf刷新
```

**原理**：发现Windsurf双配置架构 + `--add-mcp` CLI命令：

| 配置 | 路径 | 用途 |
|------|------|------|
| 旧配置 | `~/.codeium/windsurf/mcp_config.json` | 手动管理 |
| 新配置 | `%APPDATA%/Windsurf/User/mcp.json` | `--add-mcp`写入，触发运行时刷新 |

- `windsurf --add-mcp '{"name":"x","command":"node"}'` → 写入mcp.json并触发RefreshMcpServers
- Windsurf合并两个文件，新配置优先
- 修改mcp_config.json不会自动刷新（无文件监听）

**市面调研**：tool-cli(zerocore-ai) / mcp-manager(nstebbins) / MCP-Manager(muzahirabbas)
本工具优势：八祸自动修复 + 代理感知 + 双配置管理 + 无感刷新

## 监测

```powershell
python mcp管理修复/mcp-manager.py status        # 全面健康检查(九祸+配置+进程+网络)
python mcp管理修复/mcp-manager.py refresh       # 触发Windsurf无感刷新(Ctrl+Alt+Shift+M)
```

## 辨别真假错误

| 日志关键字 | MCP相关？ |
|-----------|:---------:|
| `Shell integration FAILED` / `proxy GetCompletions EOF` | ❌ 无关 |
| `RefreshMcpServers.*failed` / `invalid character '\ufeff'` | ✅ 真错误 |
| `icu_util.cc Invalid file descriptor` | ✅ Playwright浏览器问题 |
| `fetch failed` (GitHub MCP) | ✅ 代理/bootstrap问题 |

```powershell
# 快速检查最近10分钟MCP错误
Get-ChildItem "$env:APPDATA\Windsurf\logs" -Recurse -Filter "Windsurf.log" |
  Where-Object { $_.LastWriteTime -gt (Get-Date).AddMinutes(-10) -and $_.Length -gt 0 } |
  ForEach-Object { Select-String -Path $_.FullName -Pattern "RefreshMcpServers.*failed|icu_util|fetch failed" }
```
