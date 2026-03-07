/**
 * MCP Auth State 导出工具
 * 
 * 用途：登录目标网站 → 导出Cookie/localStorage为auth.json
 *       供 Playwright MCP --storage-state 加载，实现Agent继承登录态
 * 
 * 用法：node mcp-auth-export.js [url] [output]
 *   例：node mcp-auth-export.js https://github.com auth-github.json
 *       node mcp-auth-export.js https://taobao.com auth-taobao.json
 * 
 * 流程：1. 打开有头浏览器 → 2. 你手动登录 → 3. 按Enter → 4. 导出auth.json
 *       之后 Playwright MCP 用 --storage-state auth.json 即可继承登录态
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const url = process.argv[2] || 'https://github.com';
const output = process.argv[3] || 'auth-state.json';
const outputPath = path.resolve(output);

async function main() {
  console.log(`\n🌐 正在打开浏览器，请手动登录: ${url}`);
  console.log(`📦 登录完成后，回到终端按 Enter 导出认证状态\n`);

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(url, { waitUntil: 'domcontentloaded' });

  // 等待用户手动登录
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  await new Promise(resolve => rl.question('✅ 登录完成？按 Enter 导出...', resolve));
  rl.close();

  // 导出存储状态
  const state = await context.storageState();
  fs.writeFileSync(outputPath, JSON.stringify(state, null, 2), 'utf-8');

  const cookies = state.cookies?.length || 0;
  const origins = state.origins?.length || 0;
  console.log(`\n✅ 已导出到: ${outputPath}`);
  console.log(`   Cookies: ${cookies} 个, LocalStorage origins: ${origins} 个`);
  console.log(`\n💡 使用方法:`);
  console.log(`   Playwright MCP: npx @playwright/mcp --headless --storage-state "${outputPath}"`);
  console.log(`   或在 mcp_config.json 中配置 args: ["--storage-state", "${outputPath}"]`);

  await browser.close();
}

main().catch(err => {
  console.error('❌ 错误:', err.message);
  process.exit(1);
});
