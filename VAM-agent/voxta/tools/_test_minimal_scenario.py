"""Minimal: scenario + greeting + ack + send (no flags, no extra drain)"""
import sys, time
sys.path.insert(0, '.')
from chat_engine import VoxtaSignalR

SCENARIO_ID = "53958F45-47BE-40D1-D2EB-DD5B476769FA"

sr = VoxtaSignalR()
welcome = sr.connect()
chars = sr.load_characters()
target = [c for c in chars if c.get('name') == '香草'][0]

# Start chat with scenario
result = sr.start_chat(target['id'], scenario_id=SCENARIO_ID)
print(f"Session: {sr.session_id}")

# Drain greeting (exactly like quick test)
msg_id = None
for msg in sr._recv(timeout=8):
    if msg.get('$type') == 'replyEnd':
        msg_id = msg.get('messageId')
        break
print(f"Greeting msgId: {msg_id[:12] if msg_id else 'None'}")

# Ack
if msg_id:
    sr.acknowledge_playback(msg_id)
    for _ in sr._recv(timeout=3):
        pass
print("Ack done")

# NO flags, NO extra drain — go straight to send
print("Sending message...")
sr.send_message("你好喵，今天开心吗？")

# Collect reply
reply = ''
got = False
for msg in sr._recv(timeout=30):
    t = msg.get('$type', '')
    if t == 'replyChunk':
        reply += msg.get('text', '')
    elif t == 'replyEnd':
        got = True
        break
    elif t == 'replyGenerating':
        print("  [generating]")

print(f"Result: {'PASS' if got and reply else 'FAIL'} | {len(reply)} chars")
if reply:
    print(f"Reply: {reply[:100]}")

sr.stop_chat()
sr.disconnect()
