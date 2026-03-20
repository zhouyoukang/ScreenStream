"""Deep extraction of Windsurf credit system, Continue mechanism, turn limits, and model multipliers.
Reads state.vscdb + workbench.desktop.main.js to produce complete analysis."""
import sqlite3, json, os, re, sys

# === Phase 1: Local State (state.vscdb) ===
def extract_local_state():
    db = os.path.expandvars(r'%APPDATA%\Windsurf\User\globalStorage\state.vscdb')
    print(f'=== LOCAL STATE ({db}) ===')
    print(f'Exists: {os.path.exists(db)}')
    if not os.path.exists(db):
        return {}
    
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    results = {}
    
    # Get ALL keys
    cur.execute("SELECT key FROM ItemTable")
    all_keys = [r[0] for r in cur.fetchall()]
    
    # Filter relevant keys
    relevant = [k for k in all_keys if any(x in k.lower() for x in 
        ['credit','usage','plan','prompt','cascade','continue','model','auto','tier','capacity','limit','session','turn'])]
    
    print(f'\nTotal keys: {len(all_keys)}, Relevant: {len(relevant)}')
    
    for k in sorted(relevant):
        cur.execute("SELECT value FROM ItemTable WHERE key=?", (k,))
        row = cur.fetchone()
        if row:
            val = row[0]
            try:
                parsed = json.loads(val)
                results[k] = parsed
                val_str = json.dumps(parsed)[:300]
            except Exception:
                results[k] = val
                val_str = str(val)[:300]
            print(f'  {k} = {val_str}')
    
    # Special: cachedPlanInfo
    cur.execute("SELECT value FROM ItemTable WHERE key='windsurf.settings.cachedPlanInfo'")
    row = cur.fetchone()
    if row:
        plan = json.loads(row[0])
        results['_planInfo'] = plan
        print(f'\n=== CACHED PLAN INFO ===')
        print(json.dumps(plan, indent=2)[:2000])
    
    conn.close()
    return results

# === Phase 2: JS Analysis (workbench.desktop.main.js) ===
def extract_js_logic():
    js_path = r'D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js'
    print(f'\n=== JS ANALYSIS ({js_path}) ===')
    if not os.path.exists(js_path):
        print('NOT FOUND')
        return {}
    
    js = open(js_path, 'r', encoding='utf-8').read()
    print(f'Size: {len(js):,} chars ({len(js)//1024//1024}MB)')
    results = {}
    
    # 1. AutoContinue enum
    print('\n--- AutoContinue Enum ---')
    ac_enums = sorted(set(re.findall(r'AutoContinueOnMaxGeneratorInvocations\.(\w+)', js)))
    print(f'  Values: {ac_enums}')
    results['autoContinue_enums'] = ac_enums
    
    # 2. maxGeneratorInvocations - find the numeric value
    print('\n--- Max Generator Invocations ---')
    for m in re.finditer(r'maxGeneratorInvocations\s*[:=]\s*(\d+)', js):
        print(f'  maxGeneratorInvocations = {m.group(1)}')
        results['maxGeneratorInvocations_default'] = int(m.group(1))
    
    # Also find where it's used in conditions
    mgi_ctx = re.findall(r'.{0,80}maxGeneratorInvocations.{0,120}', js)
    unique_ctx = set()
    for c in mgi_ctx:
        s = c.strip()[:200]
        h = hash(s[:60])
        if h not in unique_ctx and len(unique_ctx) < 8:
            unique_ctx.add(h)
            print(f'  CTX: {s}')
    
    # 3. Credit multiplier / model cost
    print('\n--- Credit Multiplier ---')
    cm = re.findall(r'.{0,60}(creditMultiplier|credit_multiplier).{0,100}', js)
    seen = set()
    for c in cm[:10]:
        s = c.strip()[:180]
        h = hash(s[:50])
        if h not in seen:
            print(f'  {s}')
            seen.add(h)
    
    # 4. Per-prompt credit cost (how credits are deducted)
    print('\n--- Credit Deduction Logic ---')
    deduct = re.findall(r'.{0,80}(promptCreditsUsed|usedPromptCredits|deductCredit|consumeCredit|spendCredit).{0,120}', js)
    seen2 = set()
    for d in deduct[:10]:
        s = d.strip()[:200]
        h = hash(s[:50])
        if h not in seen2:
            print(f'  {s}')
            seen2.add(h)
    
    # 5. Turn counting / step counting
    print('\n--- Turn/Step Counting ---')
    turns = re.findall(r'.{0,60}(turnCount|stepCount|numTurns|numSteps|currentStep|currentTurn|generatorInvocation).{0,100}', js)
    seen3 = set()
    for t in turns[:12]:
        s = t.strip()[:200]
        h = hash(s[:50])
        if h not in seen3:
            print(f'  {s}')
            seen3.add(h)
    
    # 6. Continue mechanism - what triggers it
    print('\n--- Continue Trigger ---')
    cont = re.findall(r'.{0,80}(showContinue|triggerContinue|continueGeneration|continueCascade|autoContinue).{0,120}', js)
    seen4 = set()
    for c in cont[:10]:
        s = c.strip()[:200]
        h = hash(s[:50])
        if h not in seen4:
            print(f'  {s}')
            seen4.add(h)
    
    # 7. Session/conversation limits
    print('\n--- Session Limits ---')
    sess = re.findall(r'.{0,60}(maxMessages|messagesRemaining|activeSessions|sessionLimit|conversationLimit).{0,100}', js)
    seen5 = set()
    for s_item in sess[:10]:
        s = s_item.strip()[:200]
        h = hash(s[:50])
        if h not in seen5:
            print(f'  {s}')
            seen5.add(h)
    
    # 8. Model cost tier mapping
    print('\n--- Model Cost Tiers ---')
    tiers = {}
    for m in re.finditer(r'MODEL_COST_TIER_(\w+)\s*[:=]\s*(\d+)', js):
        tiers[m.group(1)] = int(m.group(2))
    for k,v in sorted(tiers.items()):
        print(f'  MODEL_COST_TIER_{k} = {v}')
    results['cost_tiers'] = tiers
    
    # 9. Free models (0 credit cost)
    print('\n--- Free/Low-Cost Models ---')
    free = re.findall(r'.{0,40}(LITE_FREE|SWE_1|creditMultiplier\s*[:=]\s*0).{0,80}', js)
    seen6 = set()
    for f in free[:10]:
        s = f.strip()[:200]
        h = hash(s[:50])
        if h not in seen6:
            print(f'  {s}')
            seen6.add(h)
    
    # 10. Reasoning effort / level (affects cost)
    print('\n--- Reasoning Effort ---')
    reason = re.findall(r'.{0,50}(reasoningEffort|reasoningLevel|REASONING_EFFORT|thinkingBudget).{0,100}', js)
    seen7 = set()
    for r_item in reason[:8]:
        s = r_item.strip()[:200]
        h = hash(s[:50])
        if h not in seen7:
            print(f'  {s}')
            seen7.add(h)
    
    return results

# === Phase 3: Windsurf Version ===
def get_version():
    pj = r'D:\Windsurf\resources\app\product.json'
    if os.path.exists(pj):
        with open(pj, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f'\n=== WINDSURF VERSION ===')
        print(f'  version: {data.get("version")}')
        print(f'  commit: {data.get("commit","?")[:12]}')
        print(f'  date: {data.get("date","?")}')
        return data
    return {}

if __name__ == '__main__':
    ver = get_version()
    state = extract_local_state()
    js_data = extract_js_logic()
    
    # Save combined results
    out = {'version': ver, 'state': {k: str(v)[:500] for k,v in state.items()}, 'js': js_data}
    with open('_deep_credit_results.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, default=str, ensure_ascii=False)
    print(f'\n=== RESULTS SAVED to _deep_credit_results.json ===')
