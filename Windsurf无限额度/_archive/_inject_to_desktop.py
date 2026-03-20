"""Inject auth payload into desktop state.vscdb. Run on desktop."""
import sqlite3, json, sys

payload = r"C:\ProgramData\_auth_payload.json"
db = r"C:\Users\Administrator\AppData\Roaming\Windsurf\User\globalStorage\state.vscdb"

data = json.load(open(payload, encoding="utf-8"))
conn = sqlite3.connect(db)
cur = conn.cursor()
n = 0
for key, value in data.items():
    cur.execute("SELECT COUNT(*) FROM ItemTable WHERE key=?", (key,))
    if cur.fetchone()[0] > 0:
        cur.execute("UPDATE ItemTable SET value=? WHERE key=?", (value, key))
        print(f"  UPD: {key[:80]}")
    else:
        cur.execute("INSERT INTO ItemTable (key, value) VALUES (?, ?)", (key, value))
        print(f"  INS: {key[:80]}")
    n += 1
conn.commit()
conn.close()
print(f"\nInjected {n} entries into desktop state.vscdb")
