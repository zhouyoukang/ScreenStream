# Windsurf Farm v5.0 深度逆向研究报告

> 2026-03-12 18:20 | 引擎:['camoufox', 'drission', 'playwright'] | 12账号 1182积分

## 核心架构
```
Camoufox(Firefox C++反检测,~90%) → DrissionPage(Chrome+turnstilePatch,~85%) → Playwright(JS注入,~60%)
```

## 积分系统 (2026-03)
| Plan | 积分 | 0x模型(∞) | GPT-4.1(0.25x) | Claude(1x) |
|------|------|-----------|----------------|------------|
| Free | 25/月 | SWE+Gemini无限 | 100次/月 | 25次/月 |
| Trial | 100/14天 | SWE+Gemini无限 | 400次 | 100次 |
| Pro | 500/月 | SWE+Gemini无限 | 2000次/月 | 500次/月 |

## Turnstile方案矩阵
| 方案 | 成本 | 成功率 | 全自动 |
|------|------|--------|--------|
| Camoufox+humanize | 免费 | ~90%+ | ✅ |
| turnstilePatch+DrissionPage | 免费 | ~85% | ✅ |
| CapSolver API | $1.45/1K | ~99% | ✅ |
| Playwright+stealth | 免费 | ~60% | ✅ |

## 系统状态
- 引擎: ['camoufox', 'drission', 'playwright']
- turnstilePatch: READY
- 账号池: 12账号 1182积分