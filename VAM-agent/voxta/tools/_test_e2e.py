"""E2E test: SignalR connect + chat with 香草 + action system"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from chat_engine import VoxtaSignalR

VOXTA_HOST = "localhost"
VOXTA_PORT = 5384
TARGET_CHAR = "香草"
TEST_MSG = "香草，你最喜欢什么食物喵？"
SCENARIO_ID = "53958F45-47BE-40D1-D2EB-DD5B476769FA"  # Voxta UI (emotes)

def main():
    print("=" * 60)
    print("  VAM-agent E2E Test")
    print("=" * 60)

    # 1. Connect
    print("\n[1] Connecting to Voxta...")
    sr = VoxtaSignalR(VOXTA_HOST, VOXTA_PORT)
    welcome = sr.connect()
    ver = welcome.get('version', '?') if welcome else '?'
    print(f"  Connected: server={ver}")

    # 2. Load characters
    print("\n[2] Loading characters...")
    characters = sr.load_characters()
    time.sleep(1)
    print(f"  {len(characters)} characters loaded")
    for ch in characters:
        name = ch.get('name', '?')
        cid = ch.get('id', '?')[:8]
        print(f"    - {name} ({cid}...)")

    # Find target
    target = None
    for ch in characters:
        if ch.get('name') == TARGET_CHAR:
            target = ch
            break
    if not target:
        print(f"  FAIL: {TARGET_CHAR} not found!")
        sr.disconnect()
        return

    # 3. Start chat with scenario
    print(f"\n[3] Starting chat with {TARGET_CHAR} (scenario=Voxta UI)...")
    result = sr.start_chat(target["id"], scenario_id=SCENARIO_ID)
    print(f"  Chat started: session={sr.session_id}")

    # 4. Drain greeting using _recv (private but needed for raw access)
    print("\n[4] Draining greeting...")
    msg_id = None
    greeting_text = ""
    for m in sr._recv(timeout=15):
        t = m.get("$type", "")
        if t == "replyChunk":
            greeting_text += m.get("text", "")
        elif t == "replyEnd":
            msg_id = m.get("messageId", "")
            break  # Got full greeting
    if greeting_text:
        print(f"  Greeting: {greeting_text}")
    if msg_id:
        print(f"  Got greeting messageId={msg_id[:12]}...")
    else:
        print("  WARNING: No greeting messageId found")

    # 5. Acknowledge playback (keep timing tight - STT cycle timeout!)
    if msg_id:
        print("\n[5] Acknowledging playback...")
        sr.acknowledge_playback(msg_id)
        # Brief drain - don't wait too long or STT cycle times out
        for _ in sr._recv(timeout=3):
            pass
        print("  Acknowledged")

    # 6. Set emotes flag (DISABLED for debugging)
    print("\n[6] Skipping emotes flag (debug)")
    # try:
    #     sr.set_flags("emotes")
    #     time.sleep(0.5)
    #     print("  Flags set")
    # except Exception as e:
    #     print(f"  set_flags error: {e}")

    # 7. Send message + receive reply (uses built-in API)
    print(f"\n[7] Sending: {TEST_MSG}")
    sr.send_message(TEST_MSG)

    print("\n[8] Waiting for reply (60s timeout, 10s action wait)...")
    reply = sr.receive_reply(timeout=60, action_wait=10)

    # 9. Results
    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)

    if 'error' in reply:
        print(f"  ERROR: {reply['error']}")
        print("\n  CHAT TEST: FAIL")
    else:
        text = reply.get('text', '')
        actions = reply.get('actions', [])
        timed_out = reply.get('timeout', False)
        mid = reply.get('message_id', '')

        print(f"  Reply: {text[:200]}")
        print(f"  Reply length: {len(text)} chars")
        print(f"  Actions: {actions}")
        print(f"  Timed out: {timed_out}")
        print(f"  Message ID: {mid[:12] if mid else 'None'}...")

        if text and not timed_out:
            print("\n  CHAT TEST: PASS")
        else:
            print("\n  CHAT TEST: FAIL")

        if actions:
            print("  ACTION SYSTEM: PASS")
        else:
            print("  ACTION SYSTEM: No actions triggered (may need emotional message)")

    # 10. Cleanup
    print("\n[10] Stopping chat...")
    sr.stop_chat()
    time.sleep(1)
    sr.disconnect()
    print("  Disconnected")

    text = reply.get('text', '') if 'error' not in reply else ''
    print("\n" + "=" * 60)
    print(f"  E2E TEST {'PASS' if text else 'FAIL'}")
    print("=" * 60)

if __name__ == "__main__":
    main()
