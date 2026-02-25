# 浏览器Agent统御术 (Browser Agent Mastery)

> Agent操作卡片。知识详见 `文档/BROWSER_MCP_MULTI_AGENT_RESEARCH.md`。

## 触发条件
- Agent需操控浏览器（导航/提取/填表/截图/调试）
- 多Agent并行操作浏览器
- 前端E2E验证 / 网页数据提取

## 六律（铁律，无条件遵守）

| # | 铁律 | 解决 |
|---|------|------|
| R1 | Playwright `--headless`（已配置） | 焦点 |
| R2 | 同一对话Playwright和DevTools不同时用 | 并发 |
| R3 | DevTools: `list_pages`→`select_page`→操作→不切换 | 并发 |
| R4 | DevTools禁止写操作pageId=0（用户活跃Tab） | 侵犯 |
| R5 | 内存>85%禁新Playwright；用完即`browser_close` | 资源 |
| R6 | DevTools按page+type过滤console | 听觉 |

## Token管控（优先级）

`browser_run_code`(30-800字符) **>** `browser_snapshot`(5K-50K) **>** `take_screenshot`(最后手段)

### L1 精准提取代码模板（首选）
```javascript
// browser_run_code: 100K tokens → <1K
async (page) => {
  return await page.evaluate(() => {
    return [...document.querySelectorAll('.target')].slice(0, 5).map(el => ({
      title: el.querySelector('.title')?.textContent?.trim(),
      value: el.querySelector('.value')?.textContent?.trim()
    }));
  });
}
```

### IWR命令行模板（零弹窗，已入allowlist）
```powershell
(Invoke-WebRequest -Uri "<URL>" -UseBasicParsing).Content `
  -replace '<script[^>]*>[\s\S]*?</script>','' -replace '<[^>]+>',' ' -replace '\s+',' '
```

## 模式速查

| 模式 | 流程 |
|------|------|
| **A E2E验证** | `navigate` → `snapshot` → `click/type` → `snapshot` → (需要时)`screenshot` |
| **B 数据采集** | 静态→IWR \| SPA→`navigate` → `browser_run_code` |
| **C 调试页面** | DevTools `list_pages` → `select_page` → `take_snapshot` → `list_console_messages` |
| **D 多步自动化** | `navigate` → 循环(`snapshot`→`click/fill`→`wait_for`) → `run_code`提取 |
| **E 跨设备联动** | SS `/intent`→`/screen/text` + Playwright `navigate`→`run_code` + remote_agent `/clipboard` |

## Playwright 三模式

| 模式 | 命令行 | 用途 |
|------|--------|------|
| **Isolated**（默认） | `--headless` | E2E/采集，关闭即销毁 |
| **Persistent** | `--user-data-dir ./data` | 保留Cookie的长期自动化 |
| **Storage State** | `--storage-state auth.json` | 继承登录态不污染profile |
