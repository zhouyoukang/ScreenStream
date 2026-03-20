#!/usr/bin/env python3
"""探测当前Windsurf + WU完整状态"""
import sqlite3, json, os, time

def probe():
    results = {}
    
    # 1. WU Session
    session_file = os.path.join(os.environ.get('APPDATA',''), 'windsurf-unlimited', 'session.json')
    if os.path.exists(session_file):
        with open(session_file) as f:
            s = json.load(f)
        exp = s.get('expires_at', 0)
        remaining = exp - time.time()
        results['wu_session'] = {
            'card_type': s.get('card_type_label', '?'),
            'client_id': s.get('client_id', '')[:20] + '...',
            'expires': time.ctime(exp),
            'remaining_hours': round(remaining / 3600, 1),
            'server': s.get('server_url', ''),
            'status': s.get('status', '')
        }
        print(f"WU Session: {s.get('card_type_label')} | Expires: {time.ctime(exp)} | Remaining: {remaining/3600:.1f}h | Status: {s.get('status')}")
    else:
        print("WU Session: NOT FOUND")
    
    # 2. Windsurf Auth
    db_path = os.path.join(os.environ.get('APPDATA',''), 'Windsurf', 'User', 'globalStorage', 'state.vscdb')
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        
        auth_row = conn.execute("SELECT value FROM ItemTable WHERE key='windsurfAuthStatus'").fetchone()
        if auth_row:
            d = json.loads(auth_row[0])
            api_key = d.get('apiKey', '')
            models = d.get('allowedCommandModelConfigsProtoBinaryBase64', [])
            print(f"Auth: API Key={api_key[:25]}... | Models={len(models)} command configs")
        
        plan_row = conn.execute("SELECT value FROM ItemTable WHERE key='windsurf.settings.cachedPlanInfo'").fetchone()
        if plan_row:
            p = json.loads(plan_row[0])
            u = p.get('usage', {})
            print(f"Plan: {p.get('planName')} | Messages: {u.get('usedMessages',0)}/{u.get('messages',0)} | Grace: {p.get('gracePeriodStatus')}")
            end_ts = p.get('endTimestamp', 0)
            if end_ts:
                from datetime import datetime
                print(f"Plan Expires: {datetime.fromtimestamp(end_ts/1000)}")
            results['plan'] = p
        
        conn.close()
    
    # 3. Storage.json fingerprints
    storage_path = os.path.join(os.environ.get('APPDATA',''), 'Windsurf', 'User', 'globalStorage', 'storage.json')
    if os.path.exists(storage_path):
        with open(storage_path) as f:
            st = json.load(f)
        machine_id = st.get('telemetry.machineId', '')[:16]
        service_id = st.get('storage.serviceMachineId', '')[:16]
        print(f"Fingerprint: machineId={machine_id}... | serviceId={service_id}...")
    
    # 4. Account pools
    for pool_file in ['_account_pool.json', '_farm_accounts.json', '_farm_accounts_v5.json']:
        fp = os.path.join(os.path.dirname(__file__), '..', pool_file)
        if os.path.exists(fp):
            with open(fp, encoding='utf-8') as f:
                data = json.load(f)
            accs = data.get('accounts', data) if isinstance(data, dict) else data
            statuses = {}
            for a in accs:
                s = a.get('status', '?')
                statuses[s] = statuses.get(s, 0) + 1
            print(f"Pool {pool_file}: {len(accs)} accounts | {statuses}")
    
    # 5. WU process check
    import subprocess
    try:
        out = subprocess.check_output('tasklist /fi "IMAGENAME eq WindsurfUnlimited.exe" /fo csv /nh',
                                       shell=True, encoding='utf-8', errors='replace')
        wu_count = out.count('WindsurfUnlimited.exe')
        print(f"WU Processes: {wu_count}")
    except:
        print("WU Processes: CHECK FAILED")
    
    # 6. Hosts check
    try:
        with open(r'C:\Windows\System32\drivers\etc\hosts') as f:
            hosts = f.read()
        mitm_ok = '127.65.43.21 server.self-serve.windsurf.com' in hosts
        codeium_ok = '127.65.43.21 server.codeium.com' in hosts
        print(f"Hosts: MITM={'OK' if mitm_ok else 'MISSING'} | Codeium={'OK' if codeium_ok else 'MISSING'}")
    except:
        print("Hosts: CHECK FAILED")

if __name__ == '__main__':
    probe()
