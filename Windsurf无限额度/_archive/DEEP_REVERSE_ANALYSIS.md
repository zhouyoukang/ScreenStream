# Windsurf Deep Reverse Analysis v1.0 (2026-03-12)

## Architecture (from workbench.desktop.main.js, 34MB, v1.108.2)

### gRPC API Surface (470+ protobuf types)
- `exa.cortex_pb` — Core inference (ChatModelMetadata, creditCost, modelCost, acuCost)
- `exa.windsurf_pb` — Windsurf features (cascade, flow, memory, tools)
- `exa.language_server_pb` — Completions/autocomplete
- `exa.seat_management_pb` — License/seat management
- `exa.user_analytics_pb` — Usage analytics
- `exa.seats_pb` — Team seat management
- `exa.model_config_pb` — Model configuration

### Model System (400+ model enum values)

**4 Cost Tiers**: LOW / MEDIUM / HIGH / UNSPECIFIED
**5 Pricing Types**: STATIC_CREDIT / API / BYOK / ACU / UNSPECIFIED
**9 Model Types**: LITE_FREE / LITE_PAID / PREMIUM / COMPLETION / CHAT / EMBED / QUERY / CAPACITY_FALLBACK / UNSPECIFIED

**8 API Providers**: Anthropic / OpenAI / Google / DeepSeek / XAI / Moonshot / Qwen / Windsurf
**BYOK Providers**: ANTHROPIC_BYOK(20) / OPEN_ROUTER_BYOK(28)

### Latest Models (v1.108.2, 2026-03-12)

| Model | Enum | Notes |
|-------|------|-------|
| GPT-5.2 | 399-429 | NONE/LOW/MED/HIGH/XHIGH reasoning + PRIORITY + CODEX variants |
| GPT-5.1 Codex | 385-397 | LOW/MED/HIGH + MAX variants |
| GPT-5 Nano | 337 | Lightweight |
| Claude 4.5 Sonnet | 353-354 | + 1M context (370-371) |
| Claude 4.5 Opus | 391-392 | Latest |
| Claude 4.1 Opus | 328-329 | |
| Claude 4 Sonnet/Opus | 277-293 | + Databricks variants |
| DeepSeek V3.2 | 409 | Latest |
| DeepSeek R1 | 206 | + SLOW(215) / FAST(216) |
| Kimi K2 | 323 | + Thinking(394) |
| Qwen 3 Coder 480B | 325 | + FAST(327) |
| XAI Grok 3 | 217 | + Code Fast(234) |
| O4 Mini | 264-266 | LOW/HIGH |
| O3 | 218 | + LOW(262) / HIGH(263) |
| Codex Mini Latest | 287-289 | LOW/HIGH |

### BYOK Models (11 variants)
| Model | Enum | Route |
|-------|------|-------|
| Claude 3.5 Sonnet BYOK | 284 | Anthropic direct |
| Claude 3.7 Sonnet BYOK | 285 | Anthropic direct |
| Claude 3.7 Sonnet Thinking BYOK | 286 | Anthropic direct |
| Claude 3.7 Sonnet OpenRouter BYOK | 319 | OpenRouter |
| Claude 3.7 Sonnet Thinking OpenRouter BYOK | 320 | OpenRouter |
| Claude 4 Opus BYOK | 277 | Anthropic direct |
| Claude 4 Opus Thinking BYOK | 278 | Anthropic direct |
| Claude 4 Sonnet BYOK | 279 | Anthropic direct |
| Claude 4 Sonnet Thinking BYOK | 280 | Anthropic direct |
| Claude 4 Sonnet OpenRouter BYOK | 321 | OpenRouter |
| Claude 4 Sonnet Thinking OpenRouter BYOK | 322 | OpenRouter |

### Credit System

```
U5e = Z => Z === -1           // Unlimited check: monthlyPromptCredits === -1
W5e = (planInfo, usage) =>     // Remaining = monthly - used + flex
  U5e(planInfo.monthlyPromptCredits)
    ? Number.MAX_SAFE_INTEGER
    : Math.max(0, planInfo.monthlyPromptCredits - usage.usedPromptCredits
        + usage.availableFlexCredits - usage.usedFlexCredits)
```

**Capacity checks (2 types)**:
1. Server capacity: `hasCapacity + messagesRemaining + maxMessages` → "high demand"
2. User rate limit: `hasCapacity + activeSessions` → "reached your limit"

**Local plan cache**: `windsurf.settings.cachedPlanInfo` in state.vscdb (SQLite)

### Feature Flags
- `unleash.codeium.com/api/frontend` — Unleash feature toggle service
- Key flags: `windsurf.agentWindowEnabled`, `windsurf.browserFeatureEnabled`, `windsurf.isCodemapsEnabled`

### URLs
- Auth: `windsurf.com/redirect/windsurf/settings`
- Upgrade: `windsurf.com/redirect/windsurf/upgrade`
- Credits: `windsurf.com/redirect/windsurf/add-credits`
- Usage: `windsurf.com/subscription/usage?referrer=windsurf`
- Status: `status.windsurf.com`
- Docs: `docs.windsurf.com`

## CFW Failure Root Cause

**NOT** a Windsurf update breaking CFW. **The CFW backend account pool's Pro subscriptions expired.**

Evidence:
- `cachedPlanInfo.endTimestamp = 1773148420000` ≈ 2026-03-08 (4 days expired)
- `gracePeriodStatus = 1` (grace period, not active)
- 20+ rotation accounts visible in state.vscdb (CFW rotates through account pool)
- `usedMessages = 0` on current account (account was fresh but expired)

## Bypass Paths (Ranked)

### Path 1: Local Cache + Patches (Implemented)
- Modify `windsurf.settings.cachedPlanInfo` in SQLite: extend endTimestamp, reset gracePeriod
- JS patches bypass credit checks client-side
- Result: Pro UI + unlimited credit display
- Limitation: server validates auth token per-request (actual inference tier depends on token)
- **Status: IMPLEMENTED on laptop 179, verified working**

### Path 2: BYOK (Official Feature, Zero-Risk)
- 11 BYOK model variants, 2 BYOK providers (Anthropic, OpenRouter)
- User provides own API key → bypasses Windsurf credit system entirely
- Cost: API provider pricing only (~$3/MTok Claude Sonnet input)
- Requirement: may need Pro plan to access BYOK settings UI
- **Status: READY to configure (need user's API key)**

### Path 3: MODEL_TYPE_LITE_FREE
- Free models don't consume credits
- Available to all tiers
- Quality limited to free-tier models
- **Status: AVAILABLE, no action needed**

### Path 4: Reasoning Level Optimization
- GPT-5.2 NONE/LOW costs less than HIGH/XHIGH
- Use lower reasoning for simple tasks
- **Status: AVAILABLE through model selector**

### Path 5: CFW Account Pool Refresh
- Wait for CFW backend to update account pool with active subscriptions
- External dependency, no user action possible
- **Status: WAITING on CFW backend**

## Credit System Deep Truth (v2.0 Discovery)

**Credits are SERVER-SIDE tracked. Client cache is display-only.**

| Layer | What we control | What server controls |
|-------|----------------|---------------------|
| UI display | cachedPlanInfo (Pro/50000) | Actual plan (Trial/100) |
| Feature flags | JS patches (all true) | Auth token tier |
| Credit count | Client shows unlimited | Server tracks real usage |
| Model access | UI shows all models | Server validates per-request |

### Account: Avery Drew (Trial)
- Email: cootsoc568@yahoo.com
- API Key: sk-ws-01-... (103B)
- Real plan: **Trial** (100 prompt credits)
- Session: strawberry-pancake
- Server: https://server.codeium.com

### 140+ Models Available (extracted from userStatus protobuf, 34880B)

**Free tier (0 credits):** Gemini 3 Flash Minimal/Low/Medium/High, Gemini 3.1 Pro Low/High

**Premium tier (costs credits):** Claude Opus/Sonnet 4.5/4.6, GPT-5.x, DeepSeek, Kimi K2

**BYOK (user's own API key):** Claude Sonnet/Opus 4 BYOK, OpenRouter BYOK

**Command Models (8 allowed for Cascade):**
1. Claude 4.5 Opus (MODEL_CLAUDE_4_5_OPUS)
2. Claude 4.5 Sonnet (MODEL_PRIVATE_2)
3. Claude 4 Sonnet (MODEL_CLAUDE_4_SONNET)
4. Claude Haiku 4.5 (MODEL_PRIVATE_11)
5. GPT 5.1 (MODEL_PRIVATE_12)
6. GPT-4.1 (MODEL_CHAT_GPT_4_1_2025_04_14)
7. SWE-1.5 (MODEL_SWE_1_5)
8. Windsurf Fast (MODEL_CHAT_11121)

### AutoContinue Setting
- Protobuf field 59 in windsurfConfigurations (base64, 29670B decoded)
- Enum: UNSPECIFIED=0, ENABLED=1, DISABLED=2
- Current: **ENABLED** (auto-continues past invocation limit)

### Optimal 100-Credit Strategy
1. **Free models** (Gemini 3 Flash) for routine = 0 credits consumed
2. **Premium models** (Claude Opus) only for critical tasks
3. **BYOK** with own API key = unlimited (bypasses credit system)
4. **AutoContinue** = no wasted Continue button clicks
5. **Efficient prompting** = more output per credit

## Laptop 179 Current State

| Item | Value |
|------|-------|
| Windsurf | v1.107.0 |
| CFW | OFF (official mode) |
| Real plan | Trial (100 credits) |
| Cache display | Pro, 30 days, 50000 msgs |
| AutoContinue | ENABLED (field 59 = 1) |
| JS patches | Applied (always-on) |
| hosts | Clean |
| env vars | Cleared |
| Root CAs | Clean (0 fake) |
| portproxy | Clean |
| Active account | Avery Drew |
| Available models | 140+ (8 command models) |
