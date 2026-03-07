"""Verify PATTERN_LIBRARY against ayvajs JS original"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from tcode.tempest_stroke import TempestStroke, PATTERN_LIBRARY

print(f"Total patterns: {len(PATTERN_LIBRARY)}")

# Test instantiation of every pattern
errors = []
for name in PATTERN_LIBRARY:
    try:
        ts = TempestStroke(name, bpm=60)
        pos = ts.get_positions(0)
        pos2 = ts.get_positions(0.5)
        # Verify positions are in valid range (normalized 0-1)
        for axis, val in pos.items():
            if not (-0.01 <= val <= 1.01):
                errors.append(f"{name}/{axis} t=0: {val} out of range")
        for axis, val in pos2.items():
            if not (-0.01 <= val <= 1.01):
                errors.append(f"{name}/{axis} t=0.5: {val} out of range")
    except Exception as e:
        errors.append(f"{name}: {e}")

# Spot-check: static axes (from==to) must return exact value
static_checks = [
    ("left-right-tease", "L0", 0.9),   # static at 0.9
    ("forward-back-tease", "L0", 0.9),  # static at 0.9
    ("forward-back-grind", "L0", 0.0),  # static at 0
    ("grind-circular", "L0", 0.0),      # static at 0
    ("grind-vortex", "L0", 0.0),        # static at 0
    ("tease-orbit-right", "L0", 0.9),   # static at 0.9
    ("tease-left-right-rock", "L0", 0.8),  # static at 0.8
    ("tease-up-down-circle-right", "R2", 0.8),  # static at 0.8
]

spot_pass = 0
for name, axis, expected in static_checks:
    ts = TempestStroke(name, bpm=60)
    pos0 = ts.get_positions(0).get(axis, -1)
    pos1 = ts.get_positions(1).get(axis, -1)
    if abs(pos0 - expected) < 0.001 and abs(pos1 - expected) < 0.001:
        spot_pass += 1
    else:
        errors.append(f"STATIC {name}/{axis}: expected {expected} at t=0,1, got {pos0:.4f},{pos1:.4f}")

# Spot-check: moving axes direction (from < to means value increases 0->0.5)
dir_checks = [
    ("orbit-tease", "L0", "up"),     # from=0.8, to=1
    ("orbit-tease", "L2", "up"),     # from=0.1, to=0.9
    ("orbit-tease", "R2", "up"),     # from=0.1, to=0.9
    ("tease-down-back", "L0", "up"), # from=0.8, to=1
    ("tease-down-back", "R2", "down"), # from=0.9, to=0.3
    ("long-stroke-1", "L1", "down"), # from=0.8, to=0.2, phase=1
    ("down-forward", "L0", "up"),    # from=0, to=1
]

for name, axis, direction in dir_checks:
    ts = TempestStroke(name, bpm=60)
    v0 = ts.get_positions(0).get(axis, 0.5)
    v05 = ts.get_positions(0.5).get(axis, 0.5)
    if direction == "up" and v05 > v0:
        spot_pass += 1
    elif direction == "down" and v05 < v0:
        spot_pass += 1
    else:
        errors.append(f"DIR {name}/{axis}: expected {direction}, v0={v0:.3f} v0.5={v05:.3f}")

total_checks = len(static_checks) + len(dir_checks)
print(f"Spot checks: {spot_pass}/{total_checks} pass")

if errors:
    print(f"\nERRORS ({len(errors)}):")
    for e in errors:
        print(f"  {e}")
else:
    print("ALL CHECKS PASSED")

# Also verify no R0 axis (invalid for TCode)
for name, data in PATTERN_LIBRARY.items():
    if "R0" in data:
        print(f"WARNING: {name} has R0 axis (not standard TCode)")

print(f"\nPattern list: {sorted(PATTERN_LIBRARY.keys())}")
