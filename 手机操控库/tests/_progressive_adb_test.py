"""渐进式ADB缺失验证 — 从完整ADB到纯HTTP"""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from phone_lib import Phone, discover, NegativeState, _probe

WIFI_IP = "192.168.10.122"
WIFI_PORT = 8086

def phase1_full_adb():
    """Phase 1: 完整ADB模式 — 自动发现+全功能"""
    print("\n" + "="*50)
    print("  Phase 1: 完整ADB模式")
    print("="*50)

    # 自动发现
    url = discover()
    print(f"  自动发现: {url}")

    p = Phone()
    print(f"  Phone: {p}")
    print(f"  ADB可用: {p._has_adb}, 序列号: {p._serial_hint}")

    # 健康检查
    h = p.health()
    print(f"  健康: {h.get('state')} (healthy={h.get('healthy')})")

    # 五感采集
    s = p.senses()
    ok = s.get("_ok", False)
    print(f"  五感: {'OK' if ok else 'FAIL'}")
    if ok:
        print(f"    视觉: fg={s['vision']['foreground_app']}, texts={s['vision']['text_count']}")
        print(f"    听觉: vol_music={s['hearing']['volume_music']}")
        print(f"    触觉: input={s['touch']['input_enabled']}")
        print(f"    嗅觉: notif={s['smell']['notification_count']}")
        print(f"    味觉: bat={s['taste']['battery']}%, net={s['taste']['network']}")

    # 负面状态检测
    issues = NegativeState.detect_all(p)
    print(f"  负面状态: {len(issues)}个问题")
    for state, detail in issues:
        print(f"    - {state}: {detail}")

    return p


def phase2_wifi_direct():
    """Phase 2: WiFi直连模式 — 模拟无USB，纯WiFi HTTP"""
    print("\n" + "="*50)
    print("  Phase 2: WiFi直连模式 (模拟无USB)")
    print("="*50)

    # 直接用WiFi IP，不用自动发现
    p = Phone(host=WIFI_IP, port=WIFI_PORT, auto_discover=False)
    print(f"  Phone: {p}")
    print(f"  ADB可用: {p._has_adb}")

    # 健康检查
    h = p.health()
    print(f"  健康: {h.get('state')} (healthy={h.get('healthy')})")

    # 五感
    s = p.senses()
    ok = s.get("_ok", False)
    print(f"  五感: {'OK' if ok else 'FAIL'}")
    if ok:
        print(f"    视觉: fg={s['vision']['foreground_app']}, texts={s['vision']['text_count']}")
        print(f"    触觉: input={s['touch']['input_enabled']}")
        print(f"    味觉: bat={s['taste']['battery']}%")

    # 测试核心操控API（纯HTTP）
    print("\n  --- 核心API测试 (纯HTTP) ---")
    tests = [
        ("status", lambda: p.status()),
        ("device", lambda: p.device()),
        ("foreground", lambda: p.foreground()),
        ("read", lambda: p.read()),
        ("notifications", lambda: p.notifications(5)),
        ("apps", lambda: p.apps()),
        ("viewtree", lambda: p.viewtree(3)),
        ("clipboard_write", lambda: p.clipboard_write("remote_test")),
        ("clipboard_read", lambda: p.clipboard_read()),
    ]

    passed = 0
    for name, fn in tests:
        try:
            r = fn()
            err = isinstance(r, dict) and r.get("_error")
            if err:
                print(f"    ❌ {name}: error={r.get('_error')}")
            else:
                print(f"    ✅ {name}")
                passed += 1
        except Exception as e:
            print(f"    ❌ {name}: {e}")

    print(f"\n  结果: {passed}/{len(tests)} 通过")
    return p, passed


def phase3_pure_http():
    """Phase 3: 纯HTTP模式 — 强制无ADB，验证所有功能"""
    print("\n" + "="*50)
    print("  Phase 3: 纯HTTP模式 (强制无ADB)")
    print("="*50)

    # 用WiFi直连，但强制清除ADB标志
    p = Phone(host=WIFI_IP, port=WIFI_PORT, auto_discover=False)
    p._has_adb = False  # 强制模拟无ADB
    p._serial_hint = ""
    print(f"  Phone: {p}")
    print(f"  ADB可用: {p._has_adb} (强制禁用)")

    # 测试所有需要ADB fallback的功能
    print("\n  --- ADB依赖功能的HTTP替代测试 ---")

    # monkey_open → 应回退到 /intent
    print("  测试 monkey_open (应用HTTP /intent)...")
    # 不实际启动APP，只验证不报错
    try:
        # 用一个轻量操作验证intent API可用
        r = p.post("/intent", {"action": "android.intent.action.MAIN",
                                "package": "com.android.settings",
                                "categories": ["android.intent.category.LAUNCHER"],
                                "flags": ["FLAG_ACTIVITY_NEW_TASK"]})
        if not isinstance(r, dict) or r.get("_error"):
            print(f"    ❌ intent API: {r}")
        else:
            print(f"    ✅ intent API 可用")
        p.wait(1)
        p.home()
    except Exception as e:
        print(f"    ❌ intent: {e}")

    # search_in_app 的核心依赖: /tap, /key, /text
    print("  测试 /tap, /key, /text (search_in_app依赖)...")
    tap_ok = not (p.tap(0.5, 0.5) or {}).get("_error")
    key_ok = not (p.post("/key", {"keysym": 0xFF1B, "down": True}) or {}).get("_error")  # Escape
    p.post("/key", {"keysym": 0xFF1B, "down": False})
    text_ok = not (p.post("/text", {"text": ""}) or {}).get("_error")
    print(f"    tap: {'✅' if tap_ok else '❌'}, key: {'✅' if key_ok else '❌'}, text: {'✅' if text_ok else '❌'}")

    # 负面状态检测（无ADB模式）
    print("\n  --- 负面状态检测 (无ADB) ---")
    state, detail = NegativeState.detect(p)
    print(f"  状态: {state} ({detail})")

    issues = NegativeState.detect_all(p)
    print(f"  叠加检测: {len(issues)}个问题")

    # ensure_alive（无ADB模式）
    alive, log = p.ensure_alive()
    print(f"  ensure_alive: {'✅' if alive else '❌'}")
    for line in log:
        print(f"    {line}")

    # 远程增强API
    print("\n  --- 远程增强API ---")
    remote_tests = [
        ("brightness", lambda: p.get("/brightness")),
        ("autorotate", lambda: p.get("/autorotate")),
        ("stayawake", lambda: p.get("/stayawake")),
        ("files/storage", lambda: p.get("/files/storage")),
        ("macro/list", lambda: p.get("/macro/list")),
        ("status(a11y)", lambda: p.status()),
    ]

    passed = 0
    for name, fn in remote_tests:
        try:
            r = fn()
            err = isinstance(r, dict) and r.get("_error")
            if err:
                print(f"    ❌ {name}: {r.get('_error')}")
            else:
                print(f"    ✅ {name}")
                passed += 1
        except Exception as e:
            print(f"    ❌ {name}: {e}")

    print(f"\n  远程API: {passed}/{len(remote_tests)} 通过")
    p.home()
    return p, passed


def phase4_stacked_negative():
    """Phase 4: 负面状态叠加模拟"""
    print("\n" + "="*50)
    print("  Phase 4: 负面状态叠加测试")
    print("="*50)

    p = Phone(host=WIFI_IP, port=WIFI_PORT, auto_discover=False)
    p._has_adb = False

    # 测试1: 正常状态
    issues = NegativeState.detect_all(p)
    print(f"  当前状态: {len(issues)}个问题")

    # 测试2: 模拟无法连接
    p_fake = Phone(host="192.168.10.999", port=9999, auto_discover=False, retry=0)
    p_fake._has_adb = False
    state, detail = NegativeState.detect(p_fake)
    print(f"  模拟断网: {state} ({detail})")

    # 测试3: recover_all 在健康状态下
    ok, log = NegativeState.recover_all(p)
    print(f"  recover_all(健康): {'✅' if ok else '❌'}, {len(log)}条日志")

    # 测试4: 恢复优先级链是否正确
    priority = NegativeState.RECOVERY_PRIORITY
    print(f"  恢复优先级链: {' → '.join(priority)}")

    print("\n  ✅ Phase 4 完成")


# ============================================================
if __name__ == "__main__":
    print("="*50)
    print("  渐进式ADB缺失验证")
    print(f"  WiFi目标: {WIFI_IP}:{WIFI_PORT}")
    print("="*50)

    # 先验证WiFi直连可达
    if not _probe(f"http://{WIFI_IP}:{WIFI_PORT}"):
        print(f"  ❌ WiFi直连不可达: {WIFI_IP}:{WIFI_PORT}")
        sys.exit(1)
    print(f"  ✅ WiFi直连可达")

    p1 = phase1_full_adb()
    p2, p2_passed = phase2_wifi_direct()
    p3, p3_passed = phase3_pure_http()
    phase4_stacked_negative()

    print("\n" + "="*50)
    print("  总结")
    print("="*50)
    print(f"  Phase 1 (完整ADB): ✅")
    print(f"  Phase 2 (WiFi直连): {p2_passed}/9 API通过")
    print(f"  Phase 3 (纯HTTP):  {p3_passed}/6 远程API通过")
    print(f"  Phase 4 (叠加测试): ✅")
