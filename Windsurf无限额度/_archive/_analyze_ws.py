"""Windsurf JS Deep Architecture Analysis - surgical extraction"""
import re, sys

JS_PATH = r'D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js'

def main():
    js = open(JS_PATH, 'r', encoding='utf-8').read()
    print(f'JS_SIZE: {len(js):,} chars ({len(js)//1024//1024}MB)')

    # 1. Protobuf type names = gRPC API surface
    protos = sorted(set(re.findall(r'"(exa\.\w+_pb\.\w+)"', js)))
    print(f'\n=== PROTOBUF TYPES ({len(protos)}) ===')
    for p in protos:
        print(f'  {p}')

    # 2. Model enums with values (find numeric assignments)
    print('\n=== MODEL COST TIERS ===')
    for m in re.finditer(r'MODEL_COST_TIER_(\w+)(?:\s*[:=]\s*(\d+))?', js):
        print(f'  {m.group(0)[:80]}')

    # 3. Model pricing types
    print('\n=== MODEL PRICING TYPES ===')
    for m in re.finditer(r'MODEL_PRICING_TYPE_(\w+)(?:\s*[:=]\s*(\d+))?', js):
        name = m.group(0)[:80]
        if name not in seen_pricing:
            print(f'  {name}')
            seen_pricing.add(name)

    # 4. Model types (free/paid/premium)
    print('\n=== MODEL TYPES ===')
    seen = set()
    for m in re.finditer(r'MODEL_TYPE_(\w+)', js):
        v = m.group(0)
        if v not in seen:
            print(f'  {v}')
            seen.add(v)

    # 5. BYOK / OpenRouter / Custom
    print('\n=== CUSTOM MODEL SUPPORT ===')
    print(f'  BYOK: {len(re.findall("BYOK|byok", js))} mentions')
    print(f'  OpenRouter: {len(re.findall("[Oo]pen[Rr]outer", js))} mentions')
    print(f'  vLLM: {len(re.findall("vllm|VLLM|vLLM", js))} mentions')
    
    # 6. gRPC/inference URLs
    urls = sorted(set(re.findall(r'"(https?://[^"]{5,80})"', js)))
    codeium_urls = [u for u in urls if 'codeium' in u or 'windsurf' in u or 'exa' in u]
    print(f'\n=== CODEIUM/WINDSURF URLS ({len(codeium_urls)}) ===')
    for u in codeium_urls:
        print(f'  {u}')

    # 7. Credit logic (the U5e unlimited check + surrounding)
    print('\n=== CREDIT LOGIC ===')
    m = re.search(r'const (U\w{2,3})=(\w)=>\2===-1', js)
    if m:
        pos = m.start()
        snippet = js[pos:pos+500].replace('\n', ' ')
        print(f'  Unlimited check: {snippet[:300]}')

    # 8. hasCapacity check
    print('\n=== CAPACITY CHECK ===')
    caps = re.findall(r'.{0,50}hasCapacity.{0,80}', js)
    seen_cap = set()
    for c in caps[:10]:
        s = c.strip()[:120]
        if s not in seen_cap:
            print(f'  {s}')
            seen_cap.add(s)

    # 9. Plan validation / tier check
    print('\n=== PLAN/TIER VALIDATION ===')
    tiers = re.findall(r'.{0,60}(isFreeTier|teamsTier|planType|WindsurfPlanType).{0,80}', js)
    seen_t = set()
    for t in tiers[:10]:
        s = t.strip()[:140]
        if s not in seen_t:
            print(f'  {s}')
            seen_t.add(s)

    # 10. Model selection / switching logic
    print('\n=== MODEL SELECTION ===')
    sel = re.findall(r'.{0,60}(selectModel|modelSelector|switchModel|setModel|chooseModel).{0,80}', js)
    print(f'  Model selection mentions: {len(sel)}')
    seen_s = set()
    for s in sel[:8]:
        v = s.strip()[:140]
        if v not in seen_s:
            print(f'  {v}')
            seen_s.add(v)

seen_pricing = set()

if __name__ == '__main__':
    main()
