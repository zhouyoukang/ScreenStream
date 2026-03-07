"""Diagnostic: replicate EXACT working test pattern with voxta.signalr"""
import sys, time
sys.path.insert(0, r"d:\道\道生一\一生二\VAM-agent")
from voxta.signalr import VoxtaSignalR

sr = VoxtaSignalR()
welcome = sr.connect()
print(f"Connected: Voxta {welcome.get('voxtaServerVersion','?')}")

chars = sr.load_characters()
match = [c for c in chars if c.get('name') == '香草']
cid = match[0]['id']

result = sr.start_chat(cid)
print(f"Chat: {result.get('$type','')} session={sr.session_id}")

# === EXACT working test pattern (NO break on replyEnd) ===
print("\n--- Greeting: working test pattern (no break) ---")
greeting_msg_id = None
t0 = time.time()
for msg in sr._recv(timeout=8):
    t = msg.get('$type', '')
    elapsed = time.time() - t0
    print(f"  [{elapsed:.1f}s] {t}")
    if t == 'replyEnd':
        greeting_msg_id = msg.get('messageId')
print(f"  Greeting drain done in {time.time()-t0:.1f}s, msgId={'found' if greeting_msg_id else 'MISSING'}")

if greeting_msg_id:
    sr.acknowledge_playback(greeting_msg_id)
    for msg in sr._recv(timeout=3):
        t = msg.get('$type', '')
        elapsed = time.time() - t0
        print(f"  [{elapsed:.1f}s] post-ack: {t}")
print("  Playback acknowledged")

# === Send + collect (also exact working pattern) ===
print("\n--- Send + collect ---")
sr.send_message("你好香草，今天心情怎么样？")
t0 = time.time()
reply_text = ''
got_reply = False
for msg in sr._recv(timeout=20):
    t = msg.get('$type', '')
    elapsed = time.time() - t0
    if t == 'replyChunk':
        reply_text += msg.get('text', '')
        print(f"  [{elapsed:.1f}s] replyChunk +{len(msg.get('text',''))}c")
    elif t == 'replyEnd':
        got_reply = True
        print(f"  [{elapsed:.1f}s] replyEnd")
        break
    else:
        print(f"  [{elapsed:.1f}s] {t}")

if got_reply:
    print(f"  PASS: {len(reply_text)} chars")
    print(f"  Text: {reply_text[:150]}")
else:
    print(f"  FAIL: no replyEnd, text_len={len(reply_text)}")

sr.stop_chat()
sr.disconnect()
print("\nDone")
