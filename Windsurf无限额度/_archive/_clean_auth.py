"""Clean Windsurf auth cache from state.vscdb + Local Storage"""
import sqlite3, os, shutil, glob

# 1. Clean state.vscdb
db = r"C:\Users\Administrator\AppData\Roaming\Windsurf\User\globalStorage\state.vscdb"
bak = db + ".bak_auth_clean"
if not os.path.exists(bak):
    shutil.copy2(db, bak)
    print(f"Backup: {bak}")

conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f"Tables: {tables}")

deleted = 0
for t in tables:
    try:
        cur.execute(f'SELECT key FROM "{t}"')
        keys = [r[0] for r in cur.fetchall()]
        auth_words = ["auth", "apikey", "token", "account", "email", "login",
                      "session", "fauth", "credential", "user", "plan"]
        auth_keys = [k for k in keys if any(x in k.lower() for x in auth_words)]
        for k in auth_keys:
            cur.execute(f'SELECT value FROM "{t}" WHERE key=?', (k,))
            val = cur.fetchone()
            preview = str(val[0])[:120] if val else "NULL"
            print(f"  DEL {t}.{k} = {preview}")
            cur.execute(f'DELETE FROM "{t}" WHERE key=?', (k,))
            deleted += 1
    except Exception as e:
        print(f"Skip {t}: {e}")

conn.commit()
conn.close()
print(f"\nDeleted {deleted} auth entries from state.vscdb")

# 2. Clean Local Storage leveldb
ls_dir = r"C:\Users\Administrator\AppData\Roaming\Windsurf\Local Storage\leveldb"
if os.path.isdir(ls_dir):
    bak2 = ls_dir + "_bak"
    if not os.path.exists(bak2):
        shutil.copytree(ls_dir, bak2)
        print(f"\nBackup Local Storage: {bak2}")
    for f in glob.glob(os.path.join(ls_dir, "*.ldb")) + glob.glob(os.path.join(ls_dir, "*.log")):
        try:
            data = open(f, "rb").read()
            text = data.decode("utf-8", errors="ignore")
            if any(x in text for x in ["toknij", "lpbest", "apiKey", "authToken", "sk-ws-"]):
                os.remove(f)
                print(f"  Removed: {os.path.basename(f)} (contained auth data)")
        except Exception as e:
            print(f"  Skip {os.path.basename(f)}: {e}")
    print("Local Storage cleaned")

# 3. Clean Cookies
cookies = r"C:\Users\Administrator\AppData\Roaming\Windsurf\Network\Cookies"
if os.path.exists(cookies):
    os.remove(cookies)
    print("Cookies removed")
cj = cookies + "-journal"
if os.path.exists(cj):
    os.remove(cj)

print("\nDone! Restart Windsurf via Windsurf_Proxy.cmd")
