"""Live extraction of Windsurf model system, credit state, and auth status.
Reads current state.vscdb + workbench JS to produce real-time model intelligence."""
import sqlite3, json, os, base64, sys, struct

DB_PATH = os.path.expandvars(r'%APPDATA%\Windsurf\User\globalStorage\state.vscdb')
JS_PATH = r'D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js'

def extract_state():
    """Extract all auth/model/credit data from state.vscdb"""
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found")
        return {}
    
    conn = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True)
    cur = conn.cursor()
    results = {}
    
    # 1. Cached Plan Info
    print("=" * 60)
    print("1. CACHED PLAN INFO")
    print("=" * 60)
    cur.execute("SELECT value FROM ItemTable WHERE key='windsurf.settings.cachedPlanInfo'")
    row = cur.fetchone()
    if row:
        plan = json.loads(row[0])
        results['planInfo'] = plan
        print(json.dumps(plan, indent=2))
    
    # 2. Current User
    print("\n" + "=" * 60)
    print("2. CURRENT USER")
    print("=" * 60)
    cur.execute("SELECT value FROM ItemTable WHERE key='codeium.windsurf-windsurf_auth'")
    row = cur.fetchone()
    if row:
        results['currentUser'] = row[0]
        print(f"User: {row[0]}")
    
    # 3. User Usage Records
    print("\n" + "=" * 60)
    print("3. USER USAGE RECORDS")
    print("=" * 60)
    cur.execute("SELECT key, value FROM ItemTable WHERE key LIKE 'windsurf_auth-%'")
    for k, v in cur.fetchall():
        results[k] = v[:500]
        print(f"  {k} = {v[:500]}")
    
    # 4. Auth Status - Command Models (THE GOLD)
    print("\n" + "=" * 60)
    print("4. AUTH STATUS - COMMAND MODELS & CREDITS")
    print("=" * 60)
    cur.execute("SELECT value FROM ItemTable WHERE key='windsurfAuthStatus'")
    row = cur.fetchone()
    if row:
        auth = json.loads(row[0])
        results['authKeys'] = list(auth.keys())
        
        # API Key
        ak = auth.get('apiKey', '')
        print(f"apiKey: {ak[:25]}...{ak[-8:]}" if len(ak) > 33 else f"apiKey: {ak}")
        results['apiKey_prefix'] = ak[:25] if ak else ''
        
        # Proto size
        pb = auth.get('userStatusProtoBinaryBase64', '')
        if pb:
            decoded = base64.b64decode(pb)
            print(f"userStatusProto: {len(pb)} chars base64 = {len(decoded)} bytes decoded")
            results['protoSize'] = len(decoded)
        
        # Command Models (most important!)
        cmds = auth.get('allowedCommandModelConfigs', [])
        print(f"\nCommand Models ({len(cmds)}):")
        print(f"{'Name':<40} {'Enum':<8} {'Cost':<6} {'Type':<20}")
        print("-" * 80)
        model_list = []
        for cm in cmds:
            name = cm.get('displayName', '?')
            enum_val = cm.get('modelUid', '?')
            cost = cm.get('creditMultiplier', '?')
            mtype = cm.get('modelType', '?')
            reasoning = cm.get('reasoningEffort', '')
            print(f"  {name:<38} {str(enum_val):<8} {str(cost):<6}x {str(mtype):<20} {reasoning}")
            model_list.append({
                'name': name, 'enum': enum_val, 'cost': cost,
                'type': mtype, 'reasoning': reasoning,
                'raw': cm
            })
        results['commandModels'] = model_list
        
        # All model configs (not just command)
        all_models = auth.get('allowedModelConfigs', [])
        if all_models:
            print(f"\nAll Allowed Models ({len(all_models)}):")
            free_models = [m for m in all_models if m.get('creditMultiplier', 1) == 0]
            low_models = [m for m in all_models if m.get('creditMultiplier', 1) == 0.5]
            mid_models = [m for m in all_models if m.get('creditMultiplier', 1) == 1]
            high_models = [m for m in all_models if m.get('creditMultiplier', 1) > 1]
            
            print(f"  FREE (0x): {len(free_models)}")
            for m in free_models[:15]:
                print(f"    - {m.get('displayName','?')} (enum={m.get('modelUid','?')})")
            
            print(f"  LOW (0.5x): {len(low_models)}")
            for m in low_models[:10]:
                print(f"    - {m.get('displayName','?')}")
            
            print(f"  STANDARD (1x): {len(mid_models)}")
            for m in mid_models[:10]:
                print(f"    - {m.get('displayName','?')}")
            
            print(f"  HIGH (>1x): {len(high_models)}")
            for m in high_models[:15]:
                print(f"    - {m.get('displayName','?')} ({m.get('creditMultiplier','?')}x)")
            
            results['allModels'] = {
                'total': len(all_models),
                'free': [{'name': m.get('displayName'), 'enum': m.get('modelUid')} for m in free_models],
                'low': [{'name': m.get('displayName'), 'cost': m.get('creditMultiplier')} for m in low_models],
                'mid': [{'name': m.get('displayName')} for m in mid_models],
                'high': [{'name': m.get('displayName'), 'cost': m.get('creditMultiplier')} for m in high_models],
            }
        
        # Cascade-specific settings
        print("\n" + "=" * 60)
        print("5. CASCADE / AGENT SETTINGS")
        print("=" * 60)
        for key in ['cascadeSettings', 'windsurfConfigurations', 'defaultCascadeModel',
                     'selectedCommandModel', 'lastUsedModel', 'modelPreferences']:
            val = auth.get(key)
            if val:
                if isinstance(val, str) and len(val) > 200:
                    print(f"  {key}: ({len(val)} chars)")
                else:
                    print(f"  {key}: {json.dumps(val)[:300]}")
                results[key] = str(val)[:500]
    
    # 5. VIP status
    print("\n" + "=" * 60)
    print("6. VIP / EXTENSION STATUS")
    print("=" * 60)
    cur.execute("SELECT value FROM ItemTable WHERE key='windsurf-vip-official.windsurf-vip-v2'")
    row = cur.fetchone()
    if row:
        print(f"VIP data: {row[0][:300]}")
        results['vip'] = row[0][:300]
    else:
        print("No VIP data")
    
    # 6. Secret auth URLs
    print("\n" + "=" * 60)
    print("7. AUTH SERVER URLs")
    print("=" * 60)
    cur.execute("SELECT key, length(value) FROM ItemTable WHERE key LIKE 'secret://%'")
    for k, sz in cur.fetchall():
        print(f"  {k} ({sz}B)")
    
    conn.close()
    return results

def extract_js_models():
    """Extract model credit multiplier mapping from JS"""
    if not os.path.exists(JS_PATH):
        print(f"\nJS not found at {JS_PATH}")
        return {}
    
    import re
    js = open(JS_PATH, 'r', encoding='utf-8').read()
    print(f"\n{'='*60}")
    print(f"8. JS MODEL ENUM EXTRACTION ({len(js)//1024//1024}MB)")
    print("=" * 60)
    
    # Extract creditMultiplier assignments near model names
    # Pattern: something like {modelUid: 359, displayName: "SWE-1.5", creditMultiplier: 0}
    multipliers = re.findall(r'creditMultiplier\s*[:=]\s*(\d+(?:\.\d+)?)', js)
    print(f"  creditMultiplier values found: {sorted(set(multipliers))}")
    
    # SWE models specifically
    swe_mentions = re.findall(r'SWE[_-]?\d[\w.-]*', js)
    print(f"  SWE model mentions: {sorted(set(swe_mentions))[:20]}")
    
    # Model dispatch / delegation patterns
    delegate_patterns = re.findall(r'(?:delegat|dispatch|rout|forward|proxy|relay)\w*(?:Model|Agent|Task|Request)', js, re.I)
    print(f"  Delegation patterns: {sorted(set(delegate_patterns))[:10]}")
    
    # Agent/Cascade request mechanism
    agent_patterns = re.findall(r'(?:getChatMessage|getCompletions|sendCascade|cascadeRequest|agentRequest|toolCall|mcpCall)\w*', js)
    print(f"  Agent request patterns: {sorted(set(agent_patterns))[:15]}")
    
    return {'multiplier_values': sorted(set(multipliers))}

if __name__ == '__main__':
    print("WINDSURF LIVE MODEL INTELLIGENCE EXTRACTION")
    print(f"Time: {__import__('datetime').datetime.now()}")
    print(f"DB: {DB_PATH}")
    print(f"JS: {JS_PATH}")
    print()
    
    state = extract_state()
    js_data = extract_js_models()
    
    # Save results
    out = {**state, **js_data, '_timestamp': str(__import__('datetime').datetime.now())}
    outfile = os.path.join(os.path.dirname(__file__), '_live_model_data.json')
    with open(outfile, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n=== SAVED TO {outfile} ===")
