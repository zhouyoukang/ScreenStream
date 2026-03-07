"""Debug: what messages arrive during start_chat with scenario?"""
import sys, time, json
sys.path.insert(0, '.')
from chat_engine import VoxtaSignalR

SCENARIO_ID = "53958F45-47BE-40D1-D2EB-DD5B476769FA"

sr = VoxtaSignalR()
welcome = sr.connect()
print(f"Connected: {welcome.get('voxtaServerVersion','?')}")

chars = sr.load_characters()
target = [c for c in chars if c.get('name') == '香草'][0]
print(f"Target: {target['name']} ({target['id'][:8]})")

# Send startChat manually, then observe ALL messages
sr._send({
    "$type": "startChat",
    "characterIds": [target['id']],
    "contextKey": "VAM-agent/Base",
    "scenarioId": SCENARIO_ID,
})

print("\nWaiting for messages (30s)...")
start = time.time()
msg_count = 0
for msg in sr._recv(timeout=30):
    elapsed = time.time() - start
    t = msg.get('$type', '')
    sid = msg.get('sessionId', '')
    # Show type + key fields
    extra = ''
    if t == 'replyChunk':
        extra = f" text={msg.get('text','')[:30]}"
    elif t == 'replyEnd':
        extra = f" messageId={msg.get('messageId','')[:12]}"
    elif t in ('chatStarted', 'chatStarting'):
        extra = f" sessionId={sid}"
    elif t == 'error':
        extra = f" message={msg.get('message','')}"
    
    msg_count += 1
    print(f"  [{elapsed:5.1f}s] #{msg_count:02d} {t}{extra}")
    
    if msg_count >= 50:
        print("  (max messages reached)")
        break

print(f"\nTotal: {msg_count} messages in {time.time()-start:.1f}s")
print(f"session_id = {sr.session_id}")

sr.stop_chat()
sr.disconnect()
