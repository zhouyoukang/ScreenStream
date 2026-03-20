"""Deep analysis of Windsurf credit system, Continue mechanism, and bypass paths"""
import re, json

JS = r'D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js'
js = open(JS, 'r', encoding='utf-8').read()

# 1. AutoContinue enum values
print('=== AUTO CONTINUE ENUM ===')
for a in sorted(set(re.findall(r'AUTO_CONTINUE_ON_MAX_GENERATOR_INVOCATIONS_\w+', js))):
    print(f'  {a}')

# 2. AutoContinue config context (how it's set/read)
print('\n=== AUTO CONTINUE USAGE ===')
seen = set()
for m in re.finditer(r'.{0,120}autoContinueOnMax.{0,180}', js):
    s = m.group().strip()[:280]
    h = hash(s[:80])
    if h not in seen:
        print(f'  {s}\n---')
        seen.add(h)

# 3. Max generator invocations
print('\n=== MAX GENERATOR INVOCATIONS ===')
seen2 = set()
for m in re.finditer(r'.{0,100}maxGenerator.{0,150}', js):
    s = m.group().strip()[:250]
    h = hash(s[:70])
    if h not in seen2:
        print(f'  {s}')
        seen2.add(h)

# 4. Credit cost per conversation/turn (look for numeric assignments)
print('\n=== CREDIT COST NUMBERS ===')
for m in re.finditer(r'(promptCreditsUsed|flowCreditsUsed|creditCost|cascadeCost|acuCost)\s*[:=]\s*\d+', js):
    print(f'  {m.group()[:100]}')

# 5. Model cost tier mapping (find enum value -> tier associations)
print('\n=== COST TIER ENUM VALUES ===')
tiers = re.findall(r'MODEL_COST_TIER_(\w+)(?:\s*[:=]\s*(\d+))?', js)
seen_t = {}
for name, val in tiers:
    if val and name not in seen_t:
        seen_t[name] = val
for k, v in sorted(seen_t.items()):
    print(f'  MODEL_COST_TIER_{k} = {v}')

# 6. Windsurf settings keys related to cascade/model/continue
print('\n=== WINDSURF SETTINGS KEYS ===')
skeys = set()
for m in re.finditer(r'"(windsurf\.[a-zA-Z._]+)"', js):
    v = m.group(1)
    if any(k in v.lower() for k in ['cascade','model','continue','step','turn','limit','credit','auto','flow']):
        skeys.add(v)
for k in sorted(skeys):
    print(f'  {k}')

# 7. Plan refresh / cache invalidation logic
print('\n=== PLAN REFRESH LOGIC ===')
seen3 = set()
for m in re.finditer(r'.{0,80}(refreshPlan|updatePlan|syncPlan|fetchPlan|getPlanInfo|cachedPlan).{0,120}', js):
    s = m.group().strip()[:200]
    h = hash(s[:60])
    if h not in seen3:
        print(f'  {s}')
        seen3.add(h)
    if len(seen3) > 8:
        break
