"""Extract BYOK settings keys and model routing from Windsurf JS"""
import re

JS = r'D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js'
js = open(JS, 'r', encoding='utf-8').read()

# 1. All windsurf.* settings keys related to models/keys/providers
print('=== WINDSURF MODEL/KEY SETTINGS ===')
ws = set()
for m in re.finditer(r'["\x27](windsurf\.[a-zA-Z._]{3,80})["\x27]', js):
    v = m.group(1)
    if any(k in v.lower() for k in ['model','key','api','provider','custom','byok','cascade.','chat.','command','autocomplete']):
        ws.add(v)
for s in sorted(ws):
    print(f'  {s}')

# 2. BYOK-specific config patterns
print('\n=== BYOK API KEY CONFIG ===')
seen = set()
for m in re.finditer(r'.{0,80}(apiKey|providerKey|byokKey|anthropicKey|openRouterKey|openaiKey).{0,120}', js):
    s = m.group().strip()[:200]
    h = hash(s[:60])
    if h not in seen:
        print(f'  {s}')
        seen.add(h)
    if len(seen) > 15:
        break

# 3. Full BYOK model list with enum values
print('\n=== COMPLETE BYOK MODEL ENUM ===')
byok_models = re.findall(r'MODEL_(\w+_BYOK)(?:=(\d+))?', js)
seen_bm = set()
for name, val in byok_models:
    if name not in seen_bm:
        print(f'  MODEL_{name} = {val if val else "?"}')
        seen_bm.add(name)

# 4. Non-BYOK model enum (for comparison - what's available without BYOK)
print('\n=== KEY NON-BYOK MODELS (chat/cascade) ===')
all_models = re.findall(r'MODEL_(CLAUDE_\w+|GPT_\w+|DEEPSEEK_\w+|GEMINI_\w+|QWEN_\w+|GROK_\w+|KIMI_\w+|CODEX_\w+|CHAT_O\w+)(?:=(\d+))?', js)
seen_m = set()
for name, val in all_models:
    if name not in seen_m and 'BYOK' not in name:
        print(f'  MODEL_{name} = {val if val else "?"}')
        seen_m.add(name)

# 5. Credit cost per model (find assignments)
print('\n=== CREDIT COST LOGIC ===')
cost_logic = re.findall(r'.{0,60}(creditCost|modelCost|acuCost).{0,100}', js)
seen_c = set()
for c in cost_logic[:10]:
    s = c.strip()[:180]
    h = hash(s[:50])
    if h not in seen_c:
        print(f'  {s}')
        seen_c.add(h)

# 6. Conversation/message limits
print('\n=== CONVERSATION LIMITS ===')
limits = re.findall(r'.{0,60}(maxMessages|messagesRemaining|conversationLimit|sessionLimit|activeSessions|maxConversation).{0,100}', js)
seen_l = set()
for l in limits[:10]:
    s = l.strip()[:180]
    h = hash(s[:50])
    if h not in seen_l:
        print(f'  {s}')
        seen_l.add(h)

# 7. Feature flag / unleash
print('\n=== FEATURE FLAGS (UNLEASH) ===')
flags = re.findall(r'["\x27](windsurf[._]\w{3,50})["\x27]', js)
flag_set = set()
for f in flags:
    if any(k in f.lower() for k in ['enable','disable','flag','toggle','feature','gate','allow','limit','tier']):
        flag_set.add(f)
for f in sorted(flag_set)[:20]:
    print(f'  {f}')
