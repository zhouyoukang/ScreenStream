"""Quick non-interactive chat test via Voxta SignalR"""
import sys, time
sys.path.insert(0, '.')
from chat_engine import VoxtaSignalR

sr = VoxtaSignalR()
welcome = sr.connect()
if not welcome:
    print("FAIL: SignalR connect failed"); sys.exit(1)
print(f"Connected to Voxta {welcome.get('voxtaServerVersion', '?')}")

chars = sr.load_characters()
print(f"Characters: {len(chars)}")
# Try multiple characters
test_names = ['George', '香草', '小雅']
target = sys.argv[1] if len(sys.argv) > 1 else test_names[0]
match = [c for c in chars if c.get('name') == target]
if not match:
    print(f"FAIL: {target} not found"); sys.exit(1)

cid = match[0]['id']
print(f"Starting chat with {target} ({cid[:8]}...)")
result = sr.start_chat(cid)
if not result:
    print("FAIL: start_chat returned None"); sys.exit(1)
rtype = result.get('$type', '')
print(f"Chat result: {rtype} session={sr.session_id}")
if 'error' in rtype.lower():
    import json
    print(f"Error details: {json.dumps(result, ensure_ascii=False, default=str)[:500]}")
    sys.exit(1)

# Drain greeting and capture messageId for playback ack
print("Draining greeting...")
greeting_msg_id = None
for msg in sr._recv(timeout=8):
    t = msg.get('$type', '')
    if t == 'replyEnd':
        greeting_msg_id = msg.get('messageId')
print("  Greeting drained")

# Acknowledge playback (server blocks new input until this is sent)
if greeting_msg_id:
    sr.acknowledge_playback(greeting_msg_id)
    for msg in sr._recv(timeout=3):
        pass  # drain post-ack messages
print("  Playback acknowledged")

# Send test message
print("Sending: 你好香草，今天心情怎么样？")
sr.send_message("你好香草，今天心情怎么样？")

# Collect reply
reply_text = ''
got_reply = False
for msg in sr._recv(timeout=20):
    t = msg.get('$type', '')
    if t == 'replyChunk':
        chunk = msg.get('text', '')
        reply_text += chunk
    elif t == 'replyEnd':
        got_reply = True
        break

if got_reply and reply_text:
    print(f"PASS: Reply received ({len(reply_text)} chars)")
    print(f"Reply: {reply_text[:200]}")
else:
    print(f"FAIL: got_reply={got_reply}, text_len={len(reply_text)}")

sr.stop_chat()
sr.disconnect()
print("Test complete")
