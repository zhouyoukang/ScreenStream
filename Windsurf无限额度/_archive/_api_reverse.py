"""Reverse engineer Windsurf Cascade API: model selection, request dispatch, SWE delegation"""
import re

JS = r'D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js'
js = open(JS, 'r', encoding='utf-8').read()

def search(label, pattern, limit=12):
    print(f'\n{"="*70}')
    print(label)
    print("="*70)
    hits = re.findall(pattern, js)
    seen = set()
    for h in hits[:limit*2]:
        s = h.strip()[:250]
        hh = hash(s[:80])
        if hh not in seen and len(seen) < limit:
            print(f'  {s}')
            seen.add(hh)
    if not seen:
        print('  (none found)')
    return len(seen)

# 1. Core cascade input API
search('1. sendCascadeInput MECHANISM',
       r'.{0,100}sendCascadeInput.{0,150}')

# 2. Model selection for cascade
search('2. CASCADE MODEL SELECTION',
       r'.{0,80}(?:selectedCommandModel|commandModelUid|cascadeModel|currentModel|modelForCascade|modelSelection).{0,120}')

# 3. SWE delegation  
search('3. SWE DELEGATION',
       r'.{0,80}(?:SWE|swe_1|MODEL_SWE|sweAgent|sweModel|delegat).{0,120}')

# 4. Agent window / conversation creation
search('4. AGENT WINDOW / NEW CONVERSATION',
       r'.{0,60}(?:agentWindow|newConversation|openCascade|startCascade|createConversation).{0,120}')

# 5. gRPC/protobuf service methods
search('5. gRPC SERVICE METHODS',
       r'.{0,40}(?:GetChatMessage|GetCompletions|SendCascade|CheckCapacity|CheckUserMessage).{0,120}')

# 6. Model switching at runtime
search('6. RUNTIME MODEL SWITCH',
       r'.{0,80}(?:switchModel|changeModel|setCommandModel|updateModel|selectModel).{0,120}')

# 7. Conversation/session protobuf
search('7. CONVERSATION PROTOBUF',
       r'.{0,60}(?:conversationId|sessionId|cascadeId|threadId).{0,100}', limit=8)

# 8. Auth token in request
search('8. AUTH TOKEN IN REQUEST',
       r'.{0,60}(?:auth_token|authToken|bearerToken|apiKey).{0,100}', limit=8)

# 9. Tool call dispatch (MCP-like)
search('9. TOOL CALL DISPATCH',
       r'.{0,60}(?:toolCall|mcpCall|toolExecution|executeToolCall).{0,100}')

# 10. Windsurf internal command IDs for cascade
search('10. CASCADE COMMAND IDS',
       r'.{0,40}(?:windsurf\.cascade|windsurf\.chat|windsurf\.prioritized).{0,80}')

# 11. Model cost calculation at request time
search('11. MODEL COST AT REQUEST TIME',
       r'.{0,80}(?:creditCost|acuCost|modelCost|calculateCost|deductCredit|costPerMessage).{0,100}')

# 12. Inference server URLs
print(f'\n{"="*70}')
print('12. INFERENCE URLs')
print("="*70)
urls = re.findall(r'"(https?://[^"]+)"', js)
inf_urls = [u for u in urls if any(k in u for k in ['inference','codeium.com','windsurf.com/api'])]
for u in sorted(set(inf_urls))[:15]:
    print(f'  {u}')
