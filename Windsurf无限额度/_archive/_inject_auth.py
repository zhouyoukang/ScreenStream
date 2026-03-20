"""Inject laptop's working auth state into desktop's state.vscdb"""
import sqlite3, json

# Source: laptop's working auth (extracted)
AUTH_DATA = {
    "windsurfAuthStatus": None,  # Will be read from laptop db
    "codeium.windsurf-windsurf_auth": None,
    "windsurf.settings.cachedPlanInfo": None,
}

def read_laptop_auth():
    """Read auth from laptop's state.vscdb"""
    db = r"C:\Users\zhouyoukang\AppData\Roaming\Windsurf\User\globalStorage\state.vscdb"
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    keys_to_copy = [
        "windsurfAuthStatus",
        "codeium.windsurf-windsurf_auth",
        "windsurf.settings.cachedPlanInfo",
        "workbench.view.extension.windsurf-accounts-v2.state.hidden",
    ]
    # Also copy windsurf_auth-* entries for current session
    cur.execute("SELECT key, value FROM ItemTable")
    all_rows = cur.fetchall()
    result = {}
    current_name = None
    for k, v in all_rows:
        if k == "codeium.windsurf-windsurf_auth":
            current_name = v
        if k in keys_to_copy:
            result[k] = v
    # Copy current session entries
    if current_name:
        for k, v in all_rows:
            if k.startswith(f"windsurf_auth-{current_name}"):
                result[k] = v
    conn.close()
    return result, current_name

def inject_desktop_auth(auth_data):
    """Inject auth into desktop's state.vscdb"""
    db = r"C:\Users\Administrator\AppData\Roaming\Windsurf\User\globalStorage\state.vscdb"
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    injected = 0
    for key, value in auth_data.items():
        # Check if key exists
        cur.execute('SELECT COUNT(*) FROM ItemTable WHERE key=?', (key,))
        exists = cur.fetchone()[0] > 0
        if exists:
            cur.execute('UPDATE ItemTable SET value=? WHERE key=?', (value, key))
            print(f"  UPDATE: {key} = {str(value)[:100]}")
        else:
            cur.execute('INSERT INTO ItemTable (key, value) VALUES (?, ?)', (key, value))
            print(f"  INSERT: {key} = {str(value)[:100]}")
        injected += 1
    conn.commit()
    conn.close()
    return injected

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--inject":
        # Running on desktop - read auth data from stdin (JSON)
        import json as j
        data = j.loads(sys.stdin.read())
        count = inject_desktop_auth(data)
        print(f"\nInjected {count} auth entries into desktop state.vscdb")
    else:
        # Running on laptop - extract auth
        auth, name = read_laptop_auth()
        print(f"Current session: {name}")
        print(f"Entries: {len(auth)}")
        for k, v in auth.items():
            print(f"  {k} = {str(v)[:120]}")
        # Output as JSON for piping
        print("\n--- JSON ---")
        print(json.dumps(auth))
