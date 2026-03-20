#!/usr/bin/env python3
"""深度分析Windsurf认证结构"""
import sqlite3, json, os
from pathlib import Path

WS_STATE_DB = Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'globalStorage' / 'state.vscdb'
WS_STORAGE = Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'globalStorage' / 'storage.json'

print("=" * 60)
print("Windsurf 认证结构深度分析")
print("=" * 60)

# 1. windsurfAuthStatus 结构
conn = sqlite3.connect(str(WS_STATE_DB))
cur = conn.cursor()

cur.execute("SELECT value FROM ItemTable WHERE key='windsurfAuthStatus'")
row = cur.fetchone()
if row:
    data = json.loads(row[0])
    print(f"\n[1] windsurfAuthStatus ({len(row[0])}B)")
    print(f"    顶层键: {list(data.keys())}")
    for k, v in data.items():
        if isinstance(v, str) and len(v) > 100:
            print(f"    {k}: {v[:60]}... ({len(v)}chars)")
        elif isinstance(v, dict):
            print(f"    {k}: dict({list(v.keys())[:8]})")
        elif isinstance(v, list):
            print(f"    {k}: list[{len(v)}]")
        else:
            print(f"    {k}: {v}")

# 2. cachedPlanInfo 完整内容
cur.execute("SELECT value FROM ItemTable WHERE key='windsurf.settings.cachedPlanInfo'")
row = cur.fetchone()
if row:
    plan = json.loads(row[0])
    print(f"\n[2] cachedPlanInfo ({len(row[0])}B)")
    print(f"    完整内容: {json.dumps(plan, indent=4)}")

# 3. 所有windsurf_auth相关键
cur.execute("SELECT key, length(value), substr(value,1,200) FROM ItemTable WHERE key LIKE '%windsurf_auth%' OR key LIKE '%auth%session%'")
rows = cur.fetchall()
print(f"\n[3] Auth相关键 ({len(rows)}个)")
for k, sz, preview in rows:
    print(f"    {k} ({sz}B): {preview[:80]}...")

# 4. secret:// 键（凭据存储）
cur.execute("SELECT key, length(value) FROM ItemTable WHERE key LIKE 'secret://%'")
rows = cur.fetchall()
print(f"\n[4] Secret键 ({len(rows)}个)")
for k, sz in rows:
    print(f"    {k} ({sz}B)")

# 5. windsurfConfigurations 
cur.execute("SELECT value FROM ItemTable WHERE key='windsurfConfigurations'")
row = cur.fetchone()
if row:
    cfg = json.loads(row[0]) if row[0].startswith('{') or row[0].startswith('[') else row[0]
    if isinstance(cfg, dict):
        print(f"\n[5] windsurfConfigurations ({len(row[0])}B)")
        print(f"    顶层键: {list(cfg.keys())[:15]}")
    elif isinstance(cfg, str):
        print(f"\n[5] windsurfConfigurations ({len(row[0])}B): {cfg[:200]}...")

# 6. storage.json 完整遥测结构
data = json.loads(WS_STORAGE.read_text('utf-8'))
telemetry_keys = [k for k in data.keys() if 'telemetry' in k.lower() or 'storage.service' in k.lower() or 'machine' in k.lower()]
print(f"\n[6] storage.json 遥测键 ({len(telemetry_keys)}个)")
for k in sorted(telemetry_keys):
    v = data[k]
    if isinstance(v, str) and len(v) > 40:
        print(f"    {k}: {v[:40]}...")
    else:
        print(f"    {k}: {v}")

# 7. windsurf-vip 
cur.execute("SELECT key, length(value), substr(value,1,200) FROM ItemTable WHERE key LIKE '%vip%'")
rows = cur.fetchall()
print(f"\n[7] VIP相关键 ({len(rows)}个)")
for k, sz, preview in rows:
    print(f"    {k} ({sz}B): {preview[:120]}...")

conn.close()

# 8. 检查Credential Manager中的Windsurf凭据
import subprocess
try:
    out = subprocess.check_output('cmdkey /list', shell=True, encoding='utf-8', errors='replace')
    ws_creds = [l.strip() for l in out.split('\n') if 'windsurf' in l.lower() or 'codeium' in l.lower()]
    print(f"\n[8] Windows凭据管理器 ({len(ws_creds)}条)")
    for c in ws_creds:
        print(f"    {c}")
    if not ws_creds:
        print("    (无Windsurf相关凭据)")
except:
    print("\n[8] Windows凭据管理器: 读取失败")

print(f"\n{'='*60}")
print("分析完成")
