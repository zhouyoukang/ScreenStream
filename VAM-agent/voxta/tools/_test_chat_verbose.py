"""Verbose chat test - traces all SignalR messages"""
import sys, time
sys.path.insert(0, '.')
from chat_engine import VoxtaSignalR

sr = VoxtaSignalR()
welcome = sr.connect()
if not welcome:
    print("FAIL: connect"); sys.exit(1)
print(f"Connected to Voxta {welcome.get('voxtaServerVersion', '?')}")

chars = sr.load_characters()
target = sys.argv[1] if len(sys.argv) > 1 else '香草'
match = [c for c in chars if c.get('name') == target]
if not match:
    print(f"FAIL: {target} not found"); sys.exit(1)

cid = match[0]['id']
print(f"\n=== Starting chat with {target} ({cid[:8]}...) ===")
result = sr.start_chat(cid)
rtype = result.get('$type', '')
print(f"Chat result: {rtype}")
if 'error' in rtype.lower():
    import json
    print(f"Error: {json.dumps(result, ensure_ascii=False, default=str)[:500]}")
    sys.exit(1)

# Phase 1: Drain ALL greeting messages with verbose logging
print("\n=== Phase 1: Greeting drain (verbose) ===")
msg_count = 0
greeting_msg_id = None
for msg in sr._recv(timeout=8):
    t = msg.get('$type', '')
    text = msg.get('text', '')
    mid = msg.get('messageId', '')
    extra = f" text={text[:60]}" if text else ''
    if mid:
        extra += f" msgId={mid[:12]}"
    print(f"  [{msg_count}] {t}{extra}")
    if t == 'replyEnd' and mid:
        greeting_msg_id = mid
    msg_count += 1
print(f"  Total: {msg_count} messages in greeting phase")

# Phase 2: Acknowledge greeting playback (critical - server blocks until this is sent)
print("\n=== Phase 2: Acknowledge greeting playback ===")
if greeting_msg_id:
    print(f"  Acknowledging messageId={greeting_msg_id[:12]}...")
    sr.acknowledge_playback(greeting_msg_id)
    print("  Acknowledged")
else:
    print("  WARNING: No greeting messageId found!")

# Phase 2b: Short drain for stragglers
print("\n=== Phase 2b: Post-ack drain ===")
for msg in sr._recv(timeout=3):
    t = msg.get('$type', '')
    print(f"  straggler: {t}")

# Phase 3: Send message
print("\n=== Phase 3: Sending message ===")
msg_text = "你好，今天天气怎么样？"
print(f"  Sending: {msg_text}")
sr.send_message(msg_text)
print("  send_message() returned")

# Phase 4: Collect reply with verbose logging
print("\n=== Phase 4: Waiting for reply (20s timeout) ===")
reply_text = ''
got_reply = False
msg_count = 0
for msg in sr._recv(timeout=20):
    t = msg.get('$type', '')
    text = msg.get('text', '')
    extra = f" text={text[:80]}" if text else ''
    print(f"  [{msg_count}] {t}{extra}")
    msg_count += 1
    if t == 'replyChunk':
        reply_text += text
    elif t == 'replyEnd':
        got_reply = True
        break

print(f"\n=== Result ===")
if got_reply and reply_text:
    print(f"PASS: Reply ({len(reply_text)} chars): {reply_text[:200]}")
else:
    print(f"FAIL: got_reply={got_reply}, text_len={len(reply_text)}, msgs_received={msg_count}")

sr.stop_chat()
sr.disconnect()
