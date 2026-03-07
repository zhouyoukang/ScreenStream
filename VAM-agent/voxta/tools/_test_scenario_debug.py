"""Debug: isolate scenario vs action inference as failure cause"""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from chat_engine import VoxtaSignalR

SCENARIO_ID = "53958F45-47BE-40D1-D2EB-DD5B476769FA"
MSG = "你好喵，今天开心吗？"

def test(label, scenario_id=None, use_flags=False, action_inference=True):
    print(f"\n{'='*60}")
    print(f"  TEST: {label}")
    print(f"  scenario={bool(scenario_id)} flags={use_flags} actionInf={action_inference}")
    print(f"{'='*60}")

    sr = VoxtaSignalR()
    welcome = sr.connect()
    chars = sr.load_characters()
    target = [c for c in chars if c.get('name') == '香草'][0]

    kwargs = {"scenario_id": scenario_id} if scenario_id else {}
    sr.start_chat(target['id'], **kwargs)

    # Drain greeting (fast)
    msg_id = None
    for m in sr._recv(timeout=8):
        if m.get('$type') == 'replyEnd':
            msg_id = m.get('messageId')
            break

    if msg_id:
        sr.acknowledge_playback(msg_id)
        for _ in sr._recv(timeout=2):
            pass

    if use_flags:
        sr.set_flags("emotes")
        time.sleep(0.3)

    # Send directly (bypass send_message's internal drain)
    sr._send({
        "$type": "send",
        "sessionId": sr.session_id,
        "text": MSG,
        "doReply": True,
        "doCharacterActionInference": action_inference,
    })

    # Collect reply with verbose logging
    chunks = []
    actions = []
    reply_ended = False
    start = time.time()

    while time.time() - start < 30:
        for m in sr._recv(timeout=3):
            t = m.get('$type', '')
            if t == 'replyChunk':
                chunks.append(m.get('text', ''))
            elif t == 'replyEnd':
                reply_ended = True
            elif t == 'replyGenerating':
                elapsed = time.time() - start
                print(f"  [{elapsed:.1f}s] replyGenerating")
            elif t == 'replyStart':
                elapsed = time.time() - start
                print(f"  [{elapsed:.1f}s] replyStart")
            elif t in ('action', 'appTrigger'):
                actions.append(m.get('value', '') or m.get('name', ''))
            elif t in ('error', 'chatSessionError'):
                print(f"  ERROR: {m.get('message','')}")
                reply_ended = True
            # Ignore other types
        if reply_ended:
            # Wait briefly for trailing actions
            for m in sr._recv(timeout=3):
                t = m.get('$type', '')
                if t in ('action', 'appTrigger'):
                    actions.append(m.get('value', '') or m.get('name', ''))
            break

    text = ''.join(chunks)
    status = "PASS" if text else "FAIL"
    print(f"  Result: {status} | {len(text)} chars | actions={actions}")
    if text:
        print(f"  Reply: {text[:100]}")

    sr.stop_chat()
    sr.disconnect()
    return bool(text)

# Run 4 combinations
results = {}
results['A'] = test("No scenario, no flags", scenario_id=None, use_flags=False, action_inference=False)
results['B'] = test("No scenario, WITH action inference", scenario_id=None, use_flags=False, action_inference=True)
results['C'] = test("WITH scenario, no flags, no action inf", scenario_id=SCENARIO_ID, use_flags=False, action_inference=False)
results['D'] = test("WITH scenario, WITH flags, WITH action inf", scenario_id=SCENARIO_ID, use_flags=True, action_inference=True)

print(f"\n{'='*60}")
print("  SUMMARY")
print(f"{'='*60}")
for k, v in results.items():
    print(f"  [{k}] {'PASS' if v else 'FAIL'}")
