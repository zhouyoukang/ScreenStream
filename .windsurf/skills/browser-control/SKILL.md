---
name: browser-control
description: 浏览器Agent效率统御。当Agent需操控浏览器、多Agent并行浏览器操作、前端E2E验证时自动触发。
triggers:
  - Agent需操控浏览器（导航/提取/填表/截图/调试）
  - 多Agent并行操作浏览器
  - 前端E2E验证 / 网页数据提取
---

# 浏览器Agent效率统御术 (Browser Agent Efficiency Mastery)

> **核心洞见**: `browser_run_code`比`browser_snapshot`效率高**30x**(1,500 vs 45,000 chars)。
> 详见 `05-文档_docs/BROWSER_AGENT_EFFICIENCY_REPORT.md`。

## 决策树（每次浏览器操作前必查）

```
需要浏览器操作?
├── 静态页面内容? → tavily_extract / IWR (不启动浏览器)
├── SPA/JS渲染?
│   ├── 知道选择器? → browser_run_code (一次调用完成全流程)
│   └── 不知道选择器? → browser_snapshot (一次) → 确定选择器 → browser_run_code
└── 需要交互(填表/点击)?
    └── browser_run_code (navigate+fill+click+extract 一次调用)
```

## 触发条件
- Agent需操控浏览器（导航/提取/填表/截图/调试）
- 多Agent并行操作浏览器
- 前端E2E验证 / 网页数据提取

## 九律（铁律，无条件遵守）

| # | 铁律 | 解决 |
|---|------|------|
| R1 | Playwright `--headless`（已配置） | 焦点 |
| R2 | 同一对话Playwright和DevTools不同时用 | 并发 |
| R3 | DevTools: `list_pages`→`select_page`→操作→不切换 | 并发 |
| R4 | DevTools禁止写操作pageId=0（用户活跃Tab） | 侵犯 |
| R5 | 用完即`browser_close`（释放资源） | 资源 |
| R6 | DevTools按page+type过滤console | 听觉 |
| R7 | DevTools `--isolated`（**已配置**，临时profile） | 多实例 |
| R8 | `select_page`+操作必须**原子化** | 竞态 |
| R9 | DevTools同时打开页面≤5个 | 断连 |

## Token管控（优先级 — E2E实测数据 2026-03-16）

| 方法 | 响应大小 | 有效信息比 | 适用场景 |
|------|---------|-----------|---------|
| `browser_run_code` | **~1,500 chars** | ~95% | **首选** SPA/交互/提取 |
| `tavily_extract` | ~2,000 chars | ~60% | 静态页面内容 |
| IWR/PowerShell | ~200 chars | ~30% | 快速可达性检查 |
| `browser_snapshot` | ~45,000 chars | ~3% | **仅**不知选择器时用一次 |
| `take_screenshot` | 图片bytes | N/A | 最后手段/视觉验证 |

### P1 全流程一次调用（navigate+交互+提取）

```javascript
// browser_run_code: 一次调用完成 navigate+fill+click+extract
async (page) => {
  await page.goto('https://target.com/search');
  await page.fill('#query', 'search term');
  await page.click('button[type=submit]');
  await page.waitForSelector('.results');
  return await page.evaluate(() => {
    return [...document.querySelectorAll('.result')].slice(0, 10).map(el => ({
      title: el.querySelector('.title')?.textContent?.trim(),
      link: el.querySelector('a')?.href
    }));
  });
}
```

### P2 精准提取（页面已加载）

```javascript
// browser_run_code: 从已加载页面提取结构化数据
async (page) => {
  return await page.evaluate(() => {
    return [...document.querySelectorAll('.item')].slice(0, 5).map(el => ({
      title: el.querySelector('.title')?.textContent?.trim(),
      value: el.querySelector('.value')?.textContent?.trim()
    }));
  });
}
```

### P3 IWR命令行（静态页面，零浏览器）

```powershell
(Invoke-WebRequest -Uri "<URL>" -UseBasicParsing).Content `
  -replace '<script[^>]*>[\s\S]*?</script>','' -replace '<[^>]+>',' ' -replace '\s+',' '
```

## 模式速查

| 模式 | 流程 |
|------|------|
| **A 数据采集** | 静态→`tavily_extract`/IWR \| SPA→`browser_run_code`(P1全流程) |
| **B E2E验证** | `navigate`→`run_code`检查→(失败时)`snapshot`定位→`run_code`修复 |
| **C 调试页面** | DevTools `list_pages`→`select_page`→`take_snapshot`→`list_console_messages` |
| **D 多步自动化** | `browser_run_code` P1模板(一次调用navigate+fill+click+extract) |
| **E 跨设备联动** | SS `/intent`→`/screen/text` + Playwright `run_code` + remote_agent `/clipboard` |

## 多Agent冲突防护（R7-R8）

> 根因：`#selectedPage`全局单指针，多Agent共享→五感劫持
> 详见 `05-文档_docs/BROWSER_MCP_MULTI_AGENT_RESEARCH.md` §十一

| 场景 | 方案 | 要点 |
|------|------|------|
| **多Cascade并行** | Worktree天然隔离 | 每Cascade独立MCP进程✅ |
| **单Cascade多Tab** | `isolatedContext` | `new_page({isolatedContext:"myCtx"})` |
| **多Agent需浏览器** | 优先Playwright | 无全局状态问题 |
| **select_page后操作** | R8原子化 | select后下一调用**必须**是操作，不可插入其他工具 |

### isolatedContext用法
```javascript
// 创建独立Cookie/Storage的页面
new_page({ url: "https://a.com", isolatedContext: "taskA" })
new_page({ url: "https://b.com", isolatedContext: "taskB" })
// 各Context的Cookie/localStorage互不影响
```

## Playwright 三模式

| 模式 | 命令行 | 用途 |
|------|--------|------|
| **Isolated**（默认） | `--headless` | E2E/采集，关闭即销毁 |
| **Persistent** | `--user-data-dir ./data` | 保留Cookie的长期自动化 |
| **Storage State** | `--storage-state auth.json` | 继承登录态不污染profile |
