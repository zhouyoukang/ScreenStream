import sqlite3, sys

db = r'C:\Users\zhouyoukang\AppData\Roaming\Windsurf\User\globalStorage\state.vscdb'
conn = sqlite3.connect(db)
cur = conn.cursor()

# List tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)

# Search for URL/web/approval related keys
keywords = ['url', 'web', 'fetch', 'approv', 'allow', 'autoExec', 'turbo', 'cascade.command', 'terminal.level']
for t in tables:
    try:
        conditions = " OR ".join([f"key LIKE '%{k}%'" for k in keywords])
        cur.execute(f"SELECT key FROM {t} WHERE {conditions}")
        rows = cur.fetchall()
        if rows:
            print(f"\n=== {t} ({len(rows)} matches) ===")
            for r in rows[:30]:
                print(f"  {r[0]}")
    except Exception as e:
        print(f"Error on {t}: {e}")

conn.close()
