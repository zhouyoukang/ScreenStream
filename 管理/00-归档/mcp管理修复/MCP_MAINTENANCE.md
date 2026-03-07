# MCP 维护手册

> 2026-03-06 第九祸修复完整记录。本文件为后续MCP维护的操作手册。

## 一、本次修复全流程（时间线）

```
01:00 诊断 → 读mcp_config.json/README/mcp-manager.py → 识别4个MCP状态
01:10 根因 → Windsurf日志分析 → npx.cmd首次运行~105秒 > 60秒超时
01:15 方案 → 全局安装MCP包 + wrapper脚本(绕过npx) + VBScript热刷新
01:20 修复F1 → github-proxy-bootstrap.js腐败行修复
01:22 修复F2 → github-mcp.cmd代理端口 7897→7890
01:25 修复F3 → npm i -g chrome-devtools-mcp @upstash/context7-mcp @playwright/mcp
01:28 修复F4 → 创建4个wrapper .cmd脚本(C:\temp\ + .windsurf\)
01:30 修复F5 → mcp_config.json全部改为cmd.exe+wrapper
01:35 热刷新 → 尝试Python ctypes SendKeys(失败) → PostMessage(失败) → windsurf --add-mcp(部分成功)
01:41 热刷新 → VBScript AppActivate+SendKeys ✅ → github/context7/playwright绿灯
01:42 修复F6 → chrome-devtools入口错误 cli.js→index.js(匹配package.json bin)
01:48 二次刷新 → VBScript → chrome-devtools v0.18.1初始化成功 → 4/4绿灯
01:50 测试 → context7(resolve-library-id) ✅ → playwright(navigate+snapshot) ✅
01:51 修复F7 → Clash:7890离线 → GeoIP.dat/GeoSite.dat从fastly.jsdelivr.net下载
01:55 测试 → github(search_repositories) ✅ → 全部4/4功能验证
01:58 记录 → Memory创建 + README更新(九祸+v4配置)
```

## 二、九祸速查表

| # | 祸名 | 症状 | 一句话修复 |
|---|------|------|-----------|
| 1 | BOM | 0 MCPs | `[UTF8Encoding]::new($false)` 写配置 |
| 2 | npx | 新窗口0 MCPs | `npx.cmd` 不是 `npx` |
| 3 | ${env:} | GitHub pipe closed | 移除PS插值，用系统env |
| 4 | fetch代理 | GitHub fetch failed | `--require bootstrap.js` |
| 5 | Playwright | icu_util崩溃 | `--browser chromium` |
| 6 | env感染 | 黄点 | wrapper脚本绕过npx |
| 7 | gzip腐败 | API乱码 | `Accept-Encoding: identity` |
| 8 | 代理干扰CDP | Playwright黄点 | 移除env段的HTTPS_PROXY |
| 9 | npx超时 | 3/4红灯 | 全局安装+wrapper脚本 |

## 三、核心文件清单

### 3.1 运行时文件（C:\temp\ — 被mcp_config.json引用）

| 文件 | 用途 | 入口点 |
|------|------|--------|
| `chrome-devtools-mcp.cmd` | DevTools MCP启动器 | `chrome-devtools-mcp/build/src/index.js --isolated` |
| `context7-mcp.cmd` | Context7 MCP启动器 | `@upstash/context7-mcp/dist/index.js` |
| `playwright-mcp.cmd` | Playwright MCP启动器 | `@playwright/mcp/cli.js --headless --isolated` |
| `github-mcp.cmd` | GitHub MCP启动器 | `server-github/dist/index.js` (带代理) |
| `github-proxy-bootstrap.js` | GitHub fetch代理补丁 | undici ProxyAgent → Clash:7890 |

### 3.2 源码副本（.windsurf/ — git tracked）

同名文件在 `d:\道\道生一\一生二\.windsurf\` 目录，与C:\temp\保持同步。

### 3.3 配置文件

| 文件 | 路径 | 作用 |
|------|------|------|
| mcp_config.json | `~/.codeium/windsurf/mcp_config.json` | **权威配置**（Zone 0） |
| mcp.json | `%APPDATA%\Windsurf\User\mcp.json` | CLI注入配置（--add-mcp写入） |
| keybindings.json | `%APPDATA%\Windsurf\User\keybindings.json` | Ctrl+Alt+Shift+M = refreshMcpServers |

## 四、常用维护操作

### 4.1 检查MCP状态

```powershell
# 方法1: 日志（最可靠）
$logDir = Get-ChildItem "$env:APPDATA\Windsurf\logs" -Directory | Sort-Object Name -Descending | Select-Object -First 1
Get-ChildItem $logDir.FullName -Recurse -Filter "Windsurf.log" |
  ForEach-Object { Select-String -Path $_.FullName -Pattern "MCP.*initialized|MCP.*Failed" } |
  Select-Object -Last 10

# 方法2: mcp-manager.py
python mcp管理修复/mcp-manager.py status
```

### 4.2 无感热刷新MCP

```powershell
# VBScript方式（最可靠，无需手动操作）
$vbs = @'
Set WshShell = CreateObject("WScript.Shell")
WScript.Sleep 200
If WshShell.AppActivate("Windsurf") Then
    WScript.Sleep 500
    WshShell.SendKeys "^%+m"
    WScript.Echo "OK"
Else
    WScript.Echo "FAIL: Windsurf window not found"
End If
'@
[System.IO.File]::WriteAllText("$env:TEMP\mcp_refresh.vbs", $vbs)
cscript.exe //NoLogo "$env:TEMP\mcp_refresh.vbs"
```

### 4.3 修复Clash（GeoIP缺失）

```powershell
# 症状: clash-meta启动但端口未监听，日志报"can't download GeoIP.dat"
# 原因: 鸡生蛋问题——需代理下载，但代理本身未启动
$dir = "d:\道\道生一\一生二\clash-agent"
Invoke-WebRequest -Uri "https://fastly.jsdelivr.net/gh/Loyalsoldier/v2ray-rules-dat@release/geoip.dat" -OutFile "$dir\GeoIP.dat" -UseBasicParsing -TimeoutSec 30
Invoke-WebRequest -Uri "https://fastly.jsdelivr.net/gh/Loyalsoldier/v2ray-rules-dat@release/geosite.dat" -OutFile "$dir\GeoSite.dat" -UseBasicParsing -TimeoutSec 30
# 然后重启clash-meta
Stop-Process -Name "clash-meta" -Force -ErrorAction SilentlyContinue
Start-Process -FilePath "$dir\clash-meta.exe" -ArgumentList "-f","$dir\clash-config.yaml","-d","$dir" -WindowStyle Hidden
```

### 4.4 重建wrapper脚本（MCP包更新后）

```powershell
# 查看包的bin入口（更新后可能变化）
$pkgs = @(
    @{name="chrome-devtools-mcp"; path="chrome-devtools-mcp"},
    @{name="context7-mcp"; path="@upstash\context7-mcp"},
    @{name="playwright-mcp"; path="@playwright\mcp"},
    @{name="server-github"; path="@modelcontextprotocol\server-github"}
)
foreach ($pkg in $pkgs) {
    $pkgJson = "$env:APPDATA\npm\node_modules\$($pkg.path)\package.json"
    $json = Get-Content $pkgJson -Raw | ConvertFrom-Json
    Write-Host "$($pkg.name): bin=$($json.bin)"
}
```

### 4.5 全局更新MCP包

```powershell
# 设置代理（需要Clash运行）
$env:HTTPS_PROXY = "http://127.0.0.1:7890"
$env:HTTP_PROXY = "http://127.0.0.1:7890"
npm update -g chrome-devtools-mcp @upstash/context7-mcp @playwright/mcp @modelcontextprotocol/server-github
# 更新后检查bin入口是否变化（见4.4）
```

## 五、热刷新方法对比（踩坑记录）

| 方法 | 结果 | 原因 |
|------|------|------|
| Python ctypes SendKeys | ❌ | Electron窗口聚焦被Windows安全策略阻止 |
| ctypes PostMessage WM_KEYDOWN | ❌ | Electron不处理Win32消息 |
| ctypes SendInput + AttachThreadInput | ❌ | 按键发送到错误窗口 |
| `windsurf --add-mcp` CLI | ⚠️ | 写入mcp.json成功，但中文路径JSON编码问题 |
| **VBScript AppActivate+SendKeys** | **✅** | WScript.Shell绕过安全策略，最可靠 |

## 六、诊断命令速查

```powershell
# MCP进程检查
Get-Process -Name "node" | Where-Object { $_.CommandLine -match "mcp|context7|playwright|github|devtools" }

# Clash代理状态
Test-NetConnection -ComputerName 127.0.0.1 -Port 7890 -WarningAction SilentlyContinue -InformationLevel Quiet

# MCP日志实时监控
$log = (Get-ChildItem "$env:APPDATA\Windsurf\logs" -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName
Get-ChildItem $log -Recurse -Filter "Windsurf.log" | ForEach-Object {
    Get-Content $_.FullName -Tail 50 -Wait | Select-String "MCP"
}

# 配置文件完整性
Get-Content "$env:USERPROFILE\.codeium\windsurf\mcp_config.json" | python -m json.tool

# Wrapper脚本验证（不启动MCP，只检查入口文件存在）
@("chrome-devtools-mcp","context7-mcp","playwright-mcp","github-mcp") | ForEach-Object {
    $cmd = "C:\temp\$_.cmd"
    $exists = Test-Path $cmd
    Write-Host "${_}: exists=$exists"
}
```

## 七、架构图

```
Windsurf (Electron)
  ├─ mcp_config.json (4个MCP定义)
  │    └─ command: "cmd.exe" /c "C:\temp\*.cmd"
  │
  ├─ chrome-devtools-mcp.cmd → node index.js --isolated
  │    └─ 全局安装: %APPDATA%\npm\node_modules\chrome-devtools-mcp\
  │
  ├─ context7-mcp.cmd → node dist/index.js
  │    └─ 全局安装: %APPDATA%\npm\node_modules\@upstash\context7-mcp\
  │
  ├─ playwright-mcp.cmd → node cli.js --headless --isolated --browser chromium
  │    └─ 全局安装: %APPDATA%\npm\node_modules\@playwright\mcp\
  │    └─ 浏览器: %LOCALAPPDATA%\ms-playwright\chromium-*\
  │
  └─ github-mcp.cmd → node --require bootstrap.js dist/index.js
       ├─ 全局安装: %APPDATA%\npm\node_modules\@modelcontextprotocol\server-github\
       ├─ 代理: github-proxy-bootstrap.js → undici ProxyAgent
       └─ 网络: Clash:7890 → GitHub API
            └─ GeoIP.dat + GeoSite.dat (从fastly.jsdelivr.net预下载)
```

## 八、Wrapper脚本源码

### chrome-devtools-mcp.cmd
```batch
@echo off
REM Chrome DevTools MCP: direct node execution (bypasses npx timeout)
REM --isolated creates temporary profile, auto-cleaned on close
node "%APPDATA%\npm\node_modules\chrome-devtools-mcp\build\src\index.js" --isolated %*
```

### context7-mcp.cmd
```batch
@echo off
REM Context7 MCP: direct node execution (bypasses npx timeout)
node "%APPDATA%\npm\node_modules\@upstash\context7-mcp\dist\index.js" %*
```

### playwright-mcp.cmd
```batch
@echo off
REM Playwright MCP: direct node execution (bypasses npx timeout)
REM --headless --isolated --browser chromium
node "%APPDATA%\npm\node_modules\@playwright\mcp\cli.js" --headless --isolated --browser chromium %*
```

### github-mcp.cmd
```batch
@echo off
REM GitHub MCP v2: direct node execution (bypasses npx to avoid NODE_OPTIONS infection)
REM Token loaded from environment variable GITHUB_PERSONAL_ACCESS_TOKEN
if "%GITHUB_PERSONAL_ACCESS_TOKEN%"=="" echo ERROR: Set GITHUB_PERSONAL_ACCESS_TOKEN env var first && exit /b 1
REM Route through Clash proxy for GitHub API access
set HTTPS_PROXY=http://127.0.0.1:7890
set HTTP_PROXY=http://127.0.0.1:7890
REM Run server directly with proxy bootstrap (only this process gets fetch patch)
node --require "C:/temp/github-proxy-bootstrap.js" "%APPDATA%\npm\node_modules\@modelcontextprotocol\server-github\dist\index.js" %*
```

### github-proxy-bootstrap.js
```javascript
// Bootstrap: route Node.js native fetch through HTTP proxy
// v3: Uses undici ProxyAgent (connection pooling, proper TLS, auto-retry)
const PROXY = process.env.HTTPS_PROXY || process.env.HTTP_PROXY || 'http://127.0.0.1:7890';

if (PROXY) {
  try {
    const path = require('path');
    const npmGlobal = path.join(process.env.APPDATA || '', 'npm', 'node_modules');
    const { ProxyAgent, setGlobalDispatcher } = require(path.join(npmGlobal, 'undici'));
    const agent = new ProxyAgent({
      uri: PROXY,
      requestTls: { timeout: 30000 },
      connect: { timeout: 15000 },
    });
    setGlobalDispatcher(agent);
  } catch (e) {
    try {
      const { EnvHttpProxyAgent, setGlobalDispatcher } = require('undici');
      setGlobalDispatcher(new EnvHttpProxyAgent());
    } catch (e2) {
      process.stderr.write(`[github-proxy-bootstrap] WARNING: proxy setup failed: ${e.message}\n`);
    }
  }
}
```

## 九、mcp_config.json 标准配置 (v4)

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

## 十、前置依赖

```powershell
# 1. Node.js 全局MCP包
npm i -g chrome-devtools-mcp @upstash/context7-mcp @playwright/mcp @modelcontextprotocol/server-github undici

# 2. Playwright浏览器
$env:HTTPS_PROXY='http://127.0.0.1:7890'; npx.cmd -y playwright install chromium

# 3. GitHub PAT（系统环境变量）
[System.Environment]::SetEnvironmentVariable("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_xxx", "User")

# 4. Clash代理（需GeoIP.dat/GeoSite.dat）
# 见第四节 4.3

# 5. Windsurf快捷键绑定
# %APPDATA%\Windsurf\User\keybindings.json 中需包含:
# { "key": "ctrl+alt+shift+m", "command": "codeium.refreshMcpServers" }
```
