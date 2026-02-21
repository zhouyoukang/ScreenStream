#!/usr/bin/env python3
"""验证phone_lib高频日常函数"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phone_lib import Phone

p = Phone(8086)
ok = 0; total = 0

def test(name, fn):
    global ok, total
    total += 1
    try:
        result = fn()
        ok += 1
        print(f"  OK {name}: {str(result)[:80]}")
    except Exception as e:
        print(f"  FAIL {name}: {e}")
    p.home()

print("=== phone_lib 高频日常函数验证 ===\n")

# 1. 每日巡检
test("daily_check", lambda: p.daily_check())

# 2. 快捷函数
test("quick_pay_scan", lambda: p.quick_pay_scan())
test("quick_pay_code", lambda: p.quick_pay_code())
test("quick_express", lambda: p.quick_express())
test("quick_navigate('咖啡')", lambda: p.quick_navigate("咖啡"))
test("quick_search_video('AI')", lambda: p.quick_search_video("AI"))
test("quick_bill", lambda: p.quick_bill())

# 3. 通知智能分类
test("check_notifications_smart", lambda: p.check_notifications_smart())

# 4. 状态报告→剪贴板
test("report_to_clipboard", lambda: p.report_to_clipboard("test: "))

print(f"\n=== {ok}/{total} passed ===")
