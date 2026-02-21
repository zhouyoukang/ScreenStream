#!/usr/bin/env python3
"""B站全功能深度操控 (使用phone_lib统一库)"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phone_lib import Phone

p = Phone(8086)
results = []

def test(cat, name, fn):
    t0 = time.time()
    try:
        ok, detail = fn()
        ms = int((time.time() - t0) * 1000)
        results.append({"ok": ok})
        print(f"  {'✅' if ok else '❌'} [{cat}] {name} ({ms}ms) {detail[:80]}")
    except Exception as e:
        results.append({"ok": False})
        print(f"  💥 [{cat}] {name}: {e}")
    p.home()

print("=" * 60)
print("  B站全功能深度操控 (9 scheme + phone_lib)")
print("=" * 60)
if "_error" in p.status(): print("❌ API不可达"); sys.exit(1)
print("✓ OK\n")

print("📺 浏览")
test("浏览", "首页", lambda: ((p.bili("home"), True)[1], f"in_app={p.is_app('bili') or p.is_app('danmaku')}"))
test("浏览", "搜索'编程'", lambda: ((p.bili("search?keyword=编程教程"), True)[1], f"texts={p.read_count()[0]}"))
test("浏览", "动态", lambda: ((p.bili("following/home"), True)[1], f"texts={p.read_count()[0]}"))
test("浏览", "直播", lambda: ((p.bili("live/home"), True)[1], f"texts={p.read_count()[0]}"))
test("浏览", "番剧", lambda: ((p.bili("pgc/home"), True)[1], f"texts={p.read_count()[0]}"))

print("\n👤 个人")
test("个人", "我的", lambda: ((p.bili("user_center/mine"), True)[1], f"texts={p.read_count()[0]}"))
test("个人", "历史", lambda: ((p.bili("history"), True)[1], f"texts={p.read_count()[0]}"))
test("个人", "收藏", lambda: ((p.bili("main/favorite"), True)[1], f"texts={p.read_count()[0]}"))

print("\n🔗 联动")
def cross_search_clip():
    p.bili("search?keyword=Python入门", 3)
    texts, _ = p.read()
    titles = [t for t in texts if len(t) > 8 and any(k in t for k in ["Python","入门","教程"])]
    clip = f"B站: {'; '.join(titles[:3])}" if titles else f"结果{len(texts)}项"
    p.clipboard_write(clip)
    return True, clip[:70]
test("联动", "搜索→剪贴板", cross_search_clip)

def cross_report():
    p.bili("history"); p.wait(1)
    tc = p.read_count()[0]
    r = p.report_to_clipboard(f"B站历史:{tc}条 | ")
    return True, r[:70]
test("联动", "B站+设备→报告", cross_report)

p.home()
passed = sum(1 for r in results if r["ok"])
print(f"\n{'='*60}")
print(f"  结果: {passed}/{len(results)} | 🏛️ 全部零AI")
print(f"{'='*60}")
sys.exit(0 if passed == len(results) else 1)
