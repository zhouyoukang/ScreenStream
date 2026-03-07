"""Verbose: capture ALL message content between greeting and send with scenario"""
import sys, time, json
sys.path.insert(0, '.')
from chat_engine import VoxtaSignalR

SCENARIO_ID = "53958F45-47BE-40D1-D2EB-DD5B476769FA"

sr = VoxtaSignalR()
welcome = sr.connect()
chars = sr.load_characters()
target = [c for c in chars if c.get('name') == '香草'][0]

result = sr.start_chat(target['id'], scenario_id=SCENARIO_ID)
print(f"Session: {sr.session_id}")

# Drain greeting - capture ALL messages
print("\n--- GREETING PHASE ---")
msg_id = None
for msg in sr._recv(timeout=10):
    t = msg.get('$type', '')
    if t == 'replyEnd':
        msg_id = msg.get('messageId')
        print(f"  replyEnd msgId={msg_id[:12]}")
        # DON'T break - keep draining to see what comes after
    elif t == 'replyChunk':
        print(f"  replyChunk: {msg.get('text','')[:40]}")
    else:
        # Print full message for non-reply types
        compact = {k: v for k, v in msg.items() if v is not None and v != '' and v != [] and v != {}}
        print(f"  {t}: {json.dumps(compact, ensure_ascii=False, default=str)[:200]}")

# Ack
print("\n--- ACK PHASE ---")
if msg_id:
    sr.acknowledge_playback(msg_id)
    print("  Sent ack")

# Drain post-ack - capture ALL
print("\n--- POST-ACK DRAIN (5s) ---")
for msg in sr._recv(timeout=5):
    t = msg.get('$type', '')
    compact = {k: v for k, v in msg.items() if v is not None and v != '' and v != [] and v != {}}
    print(f"  {t}: {json.dumps(compact, ensure_ascii=False, default=str)[:200]}")

# Send message directly (no drain)
print("\n--- SENDING ---")
sr._send({
    "$type": "send",
    "sessionId": sr.session_id,
    "text": "你好喵",
    "doReply": True,
    "doCharacterActionInference": False,
})
print("  Sent (actionInference=False)")

# Wait for reply
print("\n--- REPLY PHASE (20s) ---")
reply = ''
for msg in sr._recv(timeout=20):
    t = msg.get('$type', '')
    if t == 'replyChunk':
        reply += msg.get('text', '')
        print(f"  replyChunk: {msg.get('text','')[:40]}")
    elif t == 'replyEnd':
        print(f"  replyEnd!")
        break
    else:
        compact = {k: v for k, v in msg.items() if v is not None and v != '' and v != [] and v != {}}
        print(f"  {t}: {json.dumps(compact, ensure_ascii=False, default=str)[:200]}")

print(f"\nResult: {'PASS' if reply else 'FAIL'} | {len(reply)} chars")
if reply:
    print(f"Reply: {reply[:100]}")

sr.stop_chat()
sr.disconnect()
