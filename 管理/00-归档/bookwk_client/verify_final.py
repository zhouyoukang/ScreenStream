# -*- coding: utf-8 -*-
"""端到端验证：用正确的API客户端测试全部已验证端点"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, ".")
from bookwk_api import BookWKClient

c = BookWKClient()
r = c.login_password("3183561752", "3183561752")

results = {}
tests = [
    ("get_user_info",       lambda: c.get_user_info()),
    ("get_user_list",       lambda: c.get_user_list()),
    ("get_courses",         lambda: c.get_courses()),
    ("get_courses_filter",  lambda: c.get_courses_with_filter()),
    ("get_favorites",       lambda: c.get_favorites()),
    ("get_agent_levels",    lambda: c.get_agent_levels()),
    ("get_logs",            lambda: c.get_logs()),
    ("get_help_list",       lambda: c.get_help_list()),
    ("set_user_notice",     lambda: c.set_user_notice()),
    ("call(userinfo)",      lambda: c.call("userinfo")),
]

print(f"\n{'API':25s} {'Status':8s} {'Keys/Info'}")
print("-" * 70)
for name, func in tests:
    try:
        r = func()
        code = r.get("code", "?")
        if code == 1:
            data_keys = [k for k in r.keys() if k not in ("code", "msg")]
            info = f"keys={data_keys}" if len(data_keys) <= 6 else f"{len(data_keys)} keys"
            if "data" in r and isinstance(r["data"], list):
                info = f"list[{len(r['data'])}]"
            print(f"  {name:23s} {'OK':8s} {info}")
            results[name] = "OK"
        else:
            print(f"  {name:23s} {'FAIL':8s} code={code} msg={r.get('msg','')[:50]}")
            results[name] = f"FAIL({code})"
    except Exception as e:
        print(f"  {name:23s} {'ERROR':8s} {str(e)[:50]}")
        results[name] = f"ERROR"

ok = sum(1 for v in results.values() if v == "OK")
total = len(results)
print(f"\n=== Result: {ok}/{total} APIs working ===")

# Summary of user account
ui = c.get_user_info()
if ui.get("code") == 1:
    print(f"\n=== Account Summary ===")
    print(f"  UID:    {ui['uid']}")
    print(f"  User:   {ui['user']}")
    print(f"  Money:  {ui['money']} 元")
    print(f"  Rate:   {ui['addprice']} (顶级代理)")
    print(f"  Orders: {ui['dd']}")
    print(f"  Subs:   {ui['zcz']} 下级用户")
    print(f"  Upper:  {ui['sjuser']}")

# Course summary
courses = c.get_courses()
if courses.get("code") == 1:
    data = courses["data"]
    print(f"\n=== Course Catalog ({len(data)} courses) ===")
    for item in data[:8]:
        print(f"  [{item['cid']:>6s}] {item['name'][:30]:30s} ¥{item['price']:.2f}")
    if len(data) > 8:
        print(f"  ... +{len(data)-8} more")
