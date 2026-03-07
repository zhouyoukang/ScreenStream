"""Isolate: quick test pattern + scenario = pass or fail?"""
import sys, time
sys.path.insert(0, '.')
from chat_engine import VoxtaSignalR

SCENARIO_ID = "53958F45-47BE-40D1-D2EB-DD5B476769FA"

def run_test(label, scenario_id=None):
    print(f"\n{'='*50}")
    print(f"  {label}")
    print(f"{'='*50}")

    sr = VoxtaSignalR()
    welcome = sr.connect()
    print(f"Connected: {welcome.get('voxtaServerVersion', '?')}")

    chars = sr.load_characters()
    target = [c for c in chars if c.get('name') == '香草'][0]

    # start_chat (exactly like quick test, optionally with scenario)
    if scenario_id:
        result = sr.start_chat(target['id'], scenario_id=scenario_id)
    else:
        result = sr.start_chat(target['id'])
    rtype = result.get('$type', '') if result else 'None'
    print(f"Chat: {rtype} session={sr.session_id}")

    # Drain greeting (exactly like quick test)
    greeting_msg_id = None
    for msg in sr._recv(timeout=8):
        if msg.get('$type') == 'replyEnd':
            greeting_msg_id = msg.get('messageId')
            break
    print(f"  Greeting drained, msgId={greeting_msg_id[:12] if greeting_msg_id else 'None'}...")

    # Ack (exactly like quick test)
    if greeting_msg_id:
        sr.acknowledge_playback(greeting_msg_id)
        for msg in sr._recv(timeout=3):
            pass
    print("  Ack done")

    # Send (exactly like quick test - using send_message)
    sr.send_message("你好喵，今天开心吗？")

    # Collect (exactly like quick test)
    reply_text = ''
    got_reply = False
    for msg in sr._recv(timeout=20):
        t = msg.get('$type', '')
        if t == 'replyChunk':
            reply_text += msg.get('text', '')
        elif t == 'replyEnd':
            got_reply = True
            break
        elif t == 'replyGenerating':
            print("  [generating...]")

    if got_reply and reply_text:
        print(f"PASS: {len(reply_text)} chars")
        print(f"Reply: {reply_text[:100]}")
    else:
        print(f"FAIL: got_reply={got_reply}, len={len(reply_text)}")

    sr.stop_chat()
    sr.disconnect()
    return got_reply and bool(reply_text)

# Test 1: No scenario (should pass like quick test)
r1 = run_test("Test 1: No scenario", scenario_id=None)
time.sleep(2)

# Test 2: With scenario
r2 = run_test("Test 2: With Voxta UI scenario", scenario_id=SCENARIO_ID)

print(f"\nSummary: NoScenario={'PASS' if r1 else 'FAIL'} | WithScenario={'PASS' if r2 else 'FAIL'}")
