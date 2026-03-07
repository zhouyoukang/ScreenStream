"""测试 health() 和 senses() 对 OnePlus 的行为"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from phone_lib import Phone, NegativeState

p = Phone(port=18084, auto_discover=False, heartbeat_sec=0)
print("Phone:", p, "serial:", p._serial_hint)

# Step 1: NegativeState.detect
state, detail = NegativeState.detect(p)
print(f"detect: state={state}, detail={detail}")

# Step 2: health
h = p.health()
print(f"health state: {h.get('state')}")
print(f"health healthy: {h.get('healthy')}")
if "senses" in h:
    senses = h["senses"]
    print(f"senses _ok: {senses.get('_ok')}")
    for k in ["vision", "hearing", "touch", "smell", "taste"]:
        if k in senses:
            print(f"  {k}: {str(senses[k])[:100]}")

# Step 3: breaker status
print(f"breaker: state={p._breaker._state}, failures={p._breaker._failures}")

# Step 4: post-health API call
s = p.status()
has_err = "_error" in s
print(f"status after health: error={has_err}, data={str(s)[:80]}")

# Step 5: senses standalone
print("\n--- senses() standalone ---")
try:
    ss = p.senses()
    print(f"senses _ok: {ss.get('_ok')}")
    for k in ["vision", "hearing", "touch", "smell", "taste"]:
        if k in ss:
            print(f"  {k}: {str(ss[k])[:120]}")
except Exception as e:
    print(f"senses error: {e}")
