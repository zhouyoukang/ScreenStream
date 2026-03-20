#!/usr/bin/env python3
"""底层功能全量测试 — Windsurf账号切换基础设施"""
import sqlite3, json, os, sys, hashlib, uuid
from pathlib import Path
from datetime import datetime, timezone

WS_APPDATA = Path(os.environ.get('APPDATA', '')) / 'Windsurf'
WS_STORAGE = WS_APPDATA / 'User' / 'globalStorage' / 'storage.json'
WS_STATE_DB = WS_APPDATA / 'User' / 'globalStorage' / 'state.vscdb'
POOL_FILE = Path(__file__).parent.parent / '_account_pool.json'

results = []

def test(name, func):
    try:
        ok, detail = func()
        status = "PASS" if ok else "FAIL"
        results.append((name, status, detail))
        print(f"  {'✅' if ok else '❌'} {name}: {detail}")
    except Exception as e:
        results.append((name, "ERROR", str(e)))
        print(f"  💥 {name}: {e}")

# ============ Test 1: 路径存在性 ============
def t01():
    exists = WS_APPDATA.exists()
    return exists, f"APPDATA={WS_APPDATA} exists={exists}"
test("T01_appdata_exists", t01)

def t02():
    exists = WS_STORAGE.exists()
    return exists, f"storage.json exists={exists} size={WS_STORAGE.stat().st_size if exists else 0}B"
test("T02_storage_json", t02)

def t03():
    exists = WS_STATE_DB.exists()
    return exists, f"state.vscdb exists={exists} size={WS_STATE_DB.stat().st_size if exists else 0}B"
test("T03_state_vscdb", t03)

# ============ Test 2: 遥测指纹读取 ============
def t04():
    data = json.loads(WS_STORAGE.read_text('utf-8'))
    keys = ['telemetry.machineId', 'telemetry.macMachineId', 'telemetry.devDeviceId',
            'telemetry.sqmId', 'storage.serviceMachineId']
    found = {k: data.get(k, '<missing>') for k in keys}
    set_count = sum(1 for v in found.values() if v != '<missing>')
    return set_count >= 3, f"{set_count}/5 telemetry keys set"
test("T04_telemetry_keys", t04)

# ============ Test 3: state.vscdb 认证键 ============
def t05():
    conn = sqlite3.connect(str(WS_STATE_DB))
    cur = conn.cursor()
    cur.execute("SELECT key FROM ItemTable")
    all_keys = [r[0] for r in cur.fetchall()]
    conn.close()
    ws_keys = [k for k in all_keys if 'windsurf' in k.lower() or 'auth' in k.lower() 
               or 'codeium' in k.lower() or 'plan' in k.lower()]
    return True, f"total={len(all_keys)} windsurf-related={len(ws_keys)}: {ws_keys[:10]}"
test("T05_vscdb_keys", t05)

def t06():
    conn = sqlite3.connect(str(WS_STATE_DB))
    cur = conn.cursor()
    cur.execute("SELECT value FROM ItemTable WHERE key='windsurfAuthStatus'")
    row = cur.fetchone()
    conn.close()
    if not row:
        return False, "windsurfAuthStatus not found"
    data = json.loads(row[0])
    email = data.get('email', '?')
    api_key = data.get('apiKey', '')
    plan = data.get('planName', '?')
    return True, f"email={email} plan={plan} apiKey={api_key[:20]}..."
test("T06_auth_status", t06)

def t07():
    conn = sqlite3.connect(str(WS_STATE_DB))
    cur = conn.cursor()
    cur.execute("SELECT value FROM ItemTable WHERE key='windsurf.settings.cachedPlanInfo'")
    row = cur.fetchone()
    conn.close()
    if not row:
        return False, "cachedPlanInfo not found"
    data = json.loads(row[0])
    plan = data.get('planName', '?')
    usage = data.get('usage', {})
    msgs = usage.get('usedMessages', 0)
    total = usage.get('messages', 0)
    remaining = usage.get('remainingMessages', 0)
    return True, f"plan={plan} used={msgs}/{total} remaining={remaining}"
test("T07_cached_plan", t07)

# ============ Test 4: 账号池完整性 ============
def t08():
    pool = json.loads(POOL_FILE.read_text('utf-8'))
    total = len(pool['accounts'])
    untested = sum(1 for a in pool['accounts'] if a['status'] == 'untested')
    terminated = sum(1 for a in pool['accounts'] if a['status'] == 'terminated')
    cooling = sum(1 for a in pool['accounts'] if a['status'] == 'cooling')
    return total >= 13, f"total={total} untested={untested} cooling={cooling} terminated={terminated}"
test("T08_account_pool", t08)

# ============ Test 5: 指纹生成 ============
def t09():
    fp = {
        "telemetry.machineId": hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        "telemetry.macMachineId": hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        "telemetry.devDeviceId": str(uuid.uuid4()),
        "telemetry.sqmId": str(uuid.uuid4()).replace('-', ''),
        "storage.serviceMachineId": str(uuid.uuid4())
    }
    valid = all(len(v) > 10 for v in fp.values())
    return valid, f"5 fingerprints generated, all valid={valid}"
test("T09_fingerprint_gen", t09)

# ============ Test 6: Windsurf进程检测 ============
def t10():
    import subprocess
    out = subprocess.check_output(
        'tasklist /fi "IMAGENAME eq Windsurf.exe" /fo csv /nh',
        shell=True, encoding='utf-8', errors='replace'
    )
    running = 'Windsurf.exe' in out
    count = out.count('Windsurf.exe')
    return True, f"running={running} processes={count}"
test("T10_windsurf_process", t10)

# ============ Test 7: storage.json可写性(不实际写入) ============
def t11():
    writable = os.access(str(WS_STORAGE), os.W_OK)
    return writable, f"storage.json writable={writable}"
test("T11_storage_writable", t11)

def t12():
    writable = os.access(str(WS_STATE_DB), os.W_OK)
    return writable, f"state.vscdb writable={writable}"
test("T12_vscdb_writable", t12)

# ============ Test 8: 完整的vscdb认证键枚举 ============
def t13():
    conn = sqlite3.connect(str(WS_STATE_DB))
    cur = conn.cursor()
    cur.execute("SELECT key, length(value) FROM ItemTable WHERE key LIKE '%windsurf%' OR key LIKE '%Windsurf%' OR key LIKE '%codeium%' OR key LIKE '%Codeium%'")
    rows = cur.fetchall()
    conn.close()
    details = [(k, sz) for k, sz in rows]
    return len(details) > 0, f"{len(details)} keys: " + ", ".join(f"{k}({sz}B)" for k, sz in details[:15])
test("T13_all_windsurf_keys", t13)

# ============ Summary ============
print(f"\n{'='*60}")
passed = sum(1 for _, s, _ in results if s == "PASS")
failed = sum(1 for _, s, _ in results if s == "FAIL")
errors = sum(1 for _, s, _ in results if s == "ERROR")
print(f"结果: {passed} PASS / {failed} FAIL / {errors} ERROR / {len(results)} TOTAL")
