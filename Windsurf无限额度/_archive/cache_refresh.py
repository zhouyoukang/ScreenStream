"""
Windsurf Plan Cache Refresh — Zero-invasion local bypass
Modifies windsurf.settings.cachedPlanInfo in state.vscdb to maintain Pro status.
Run periodically or on-demand. No network requests, no server interaction.

Usage:
    python cache_refresh.py              # Refresh cache (+30 days, Pro, 50000 credits)
    python cache_refresh.py --status     # Show current cache status
    python cache_refresh.py --days 60    # Custom duration
"""
import sqlite3, json, time, sys, os

DB_PATHS = [
    os.path.expandvars(r'%APPDATA%\Windsurf\User\globalStorage\state.vscdb'),
    os.path.expandvars(r'%USERPROFILE%\AppData\Roaming\Windsurf\User\globalStorage\state.vscdb'),
]

CACHE_KEY = 'windsurf.settings.cachedPlanInfo'

def find_db():
    for p in DB_PATHS:
        if os.path.isfile(p):
            return p
    return None

def get_plan(conn):
    cur = conn.cursor()
    cur.execute("SELECT value FROM ItemTable WHERE key=?", (CACHE_KEY,))
    row = cur.fetchone()
    return json.loads(row[0]) if row else None

def set_plan(conn, plan):
    cur = conn.cursor()
    cur.execute("UPDATE ItemTable SET value=? WHERE key=?", (json.dumps(plan), CACHE_KEY))
    if cur.rowcount == 0:
        cur.execute("INSERT INTO ItemTable (key, value) VALUES (?, ?)", (CACHE_KEY, json.dumps(plan)))
    conn.commit()

def make_pro_plan(days=30):
    now_ms = int(time.time() * 1000)
    return {
        "planName": "Pro",
        "startTimestamp": now_ms - (30 * 86400000),
        "endTimestamp": now_ms + (days * 86400000),
        "usage": {
            "duration": 1,
            "messages": 50000,
            "flowActions": 50000,
            "flexCredits": 0,
            "usedMessages": 0,
            "usedFlowActions": 0,
            "usedFlexCredits": 0,
            "remainingMessages": 50000,
            "remainingFlowActions": 50000,
            "remainingFlexCredits": 0
        },
        "hasBillingWritePermissions": True,
        "gracePeriodStatus": 0
    }

def show_status(plan):
    if not plan:
        print("  NO cached plan info found")
        return
    now = time.time() * 1000
    days_left = (plan['endTimestamp'] - now) / 86400000
    usage = plan.get('usage', {})
    print(f"  Plan: {plan['planName']}")
    print(f"  Status: {'ACTIVE' if plan.get('gracePeriodStatus', 1) == 0 else 'GRACE PERIOD'}")
    print(f"  Days left: {days_left:.1f}")
    print(f"  Messages: {usage.get('remainingMessages', '?')}/{usage.get('messages', '?')} remaining")
    print(f"  Flow actions: {usage.get('remainingFlowActions', '?')}/{usage.get('flowActions', '?')} remaining")
    print(f"  Used: {usage.get('usedMessages', 0)} msgs, {usage.get('usedFlowActions', 0)} flows")

def main():
    db_path = find_db()
    if not db_path:
        print("ERROR: state.vscdb not found")
        sys.exit(1)

    days = 30
    status_only = False
    for arg in sys.argv[1:]:
        if arg == '--status':
            status_only = True
        elif arg == '--days':
            pass
        elif arg.isdigit():
            days = int(arg)
    if '--days' in sys.argv:
        idx = sys.argv.index('--days')
        if idx + 1 < len(sys.argv):
            days = int(sys.argv[idx + 1])

    conn = sqlite3.connect(db_path)
    current = get_plan(conn)

    if status_only:
        print("=== Current Plan Cache ===")
        show_status(current)
        conn.close()
        return

    print(f"DB: {db_path}")
    print("\n=== BEFORE ===")
    show_status(current)

    new_plan = make_pro_plan(days)
    set_plan(conn, new_plan)

    print(f"\n=== AFTER (+{days} days) ===")
    show_status(get_plan(conn))
    print("\nRestart Windsurf to apply changes.")

    conn.close()

if __name__ == '__main__':
    main()
