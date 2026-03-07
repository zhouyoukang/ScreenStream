"""CFW v2.0.4 Runtime Memory Extraction - Simplified"""
import ctypes
import ctypes.wintypes as wt
import struct
import json
import re
import sys
import os
import subprocess
import base64

# Use WinDLL with last error tracking
k32 = ctypes.WinDLL('kernel32', use_last_error=True)

class MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_ulonglong),
        ("AllocationBase", ctypes.c_ulonglong),
        ("AllocationProtect", wt.DWORD),
        ("_pad1", wt.DWORD),
        ("RegionSize", ctypes.c_ulonglong),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
        ("_pad2", wt.DWORD),
    ]

PROCESS_ALL_ACCESS = 0x1F0FFF
MEM_COMMIT = 0x1000
READABLE = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}

def get_pid():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq CodeFreeWindsurf*', '/FO', 'CSV', '/NH'],
                       capture_output=True, text=True)
    for line in r.stdout.strip().split('\n'):
        if 'CodeFree' in line:
            parts = line.strip('"').split('","')
            return int(parts[1])
    return None

def scan_memory(pid):
    """Scan process memory for interesting strings"""
    h = k32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not h:
        err = ctypes.get_last_error()
        print(f"OpenProcess failed: error {err}")
        # Try with less access
        h = k32.OpenProcess(0x0410, False, pid)  # VM_READ | QUERY_INFO
        if not h:
            print(f"OpenProcess fallback also failed: {ctypes.get_last_error()}")
            return [], [], []

    print(f"Process handle: {h}")
    
    mbi = MBI()
    addr = 0
    all_strings = []
    json_objs = []
    jwt_tokens = []
    
    regions = 0
    readable_regions = 0
    total_read = 0
    
    # Patterns to search for
    str_patterns = [
        b'"proxy_mode"', b'"email"', b'"running"', b'"active_mappings"',
        b'"session_cost"', b'"request_count"', b'"mitm_detected"',
        b'"proxy_port"', b'"security_clean"', b'"target_host"',
        b'"relay_blocked"', b'"input_tokens"', b'"output_tokens"',
        b'windsurf.pro', b'relay-', b'x-relay-token',
        b'"license"', b'47.108.', b'156.225.', b'103.149.',
        b'server.self-serve', b'"ad_messages"', b'"relay_stale"',
    ]
    
    jwt_re = re.compile(rb'eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}')
    
    while True:
        ret = k32.VirtualQueryEx(h, ctypes.c_ulonglong(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if ret == 0:
            break
        
        regions += 1
        
        if (mbi.State == MEM_COMMIT and 
            (mbi.Protect & 0xFF) in READABLE and
            0 < mbi.RegionSize < 64 * 1024 * 1024):
            
            readable_regions += 1
            buf = (ctypes.c_char * mbi.RegionSize)()
            nread = ctypes.c_ulonglong(0)
            
            if k32.ReadProcessMemory(h, ctypes.c_ulonglong(mbi.BaseAddress), buf, mbi.RegionSize, ctypes.byref(nread)):
                data = bytes(buf[:nread.value])
                total_read += len(data)
                
                # Search patterns
                for pat in str_patterns:
                    pos = 0
                    while True:
                        pos = data.find(pat, pos)
                        if pos == -1:
                            break
                        start = max(0, pos - 40)
                        end = min(len(data), pos + 400)
                        chunk = data[start:end]
                        clean = ''.join(c if 32 <= ord(c) < 127 else '|' for c in chunk.decode('utf-8', errors='replace'))
                        # Remove excessive separators
                        clean = re.sub(r'\|{3,}', ' ... ', clean)
                        if len(clean) > 15:
                            all_strings.append(clean.strip())
                        pos += len(pat)
                        if len(all_strings) > 500:
                            break
                
                # Search JSON
                for key in [b'"proxy_mode"', b'"active_mappings"', b'"email"']:
                    pos = data.find(key)
                    if pos >= 0:
                        # Find { before
                        bstart = data.rfind(b'{', max(0, pos - 1000), pos)
                        if bstart >= 0:
                            depth = 0
                            for i in range(bstart, min(len(data), bstart + 5000)):
                                if data[i:i+1] == b'{': depth += 1
                                elif data[i:i+1] == b'}': depth -= 1
                                if depth == 0:
                                    raw = data[bstart:i+1].replace(b'\x00', b'')
                                    try:
                                        obj = json.loads(raw)
                                        if isinstance(obj, dict) and len(obj) > 3:
                                            json_objs.append(obj)
                                    except:
                                        pass
                                    break
                
                # Search JWT
                for m in jwt_re.finditer(data):
                    tok = m.group().decode('ascii', errors='ignore')
                    if tok not in jwt_tokens:
                        jwt_tokens.append(tok)
        
        next_addr = mbi.BaseAddress + mbi.RegionSize
        if next_addr <= addr:
            break
        addr = next_addr
        if addr > 0x7FFFFFFFFFFF:
            break
    
    k32.CloseHandle(h)
    print(f"Regions total: {regions}, readable: {readable_regions}, bytes read: {total_read/1024/1024:.1f} MB")
    return all_strings, json_objs, jwt_tokens

def decode_jwt(token):
    parts = token.split('.')
    if len(parts) != 3:
        return None
    payload = parts[1] + '=' * (4 - len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload))
    except:
        return None

def main():
    pid = get_pid()
    if not pid:
        print("CFW not running!")
        return
    
    print(f"=== CFW Deep RE - PID {pid} ===\n")
    
    strings, jsons, jwts = scan_memory(pid)
    
    # Deduplicate strings
    seen = set()
    unique_strings = []
    for s in strings:
        key = s[:80]
        if key not in seen:
            seen.add(key)
            unique_strings.append(s)
    
    print(f"\n{'='*60}")
    print(f"RESULTS: {len(unique_strings)} strings, {len(jsons)} JSON objects, {len(jwts)} JWTs")
    print(f"{'='*60}\n")
    
    if unique_strings:
        print("--- Interesting Strings (top 100) ---")
        for s in unique_strings[:100]:
            print(f"  {s[:250]}")
    
    if jsons:
        print("\n--- JSON State Objects ---")
        for obj in jsons[:5]:
            print(json.dumps(obj, indent=2, ensure_ascii=False)[:800])
            print()
    
    if jwts:
        print(f"\n--- JWT Tokens ({len(jwts)} total) ---")
        client_n = relay_n = other_n = 0
        for t in jwts[:5]:
            p = decode_jwt(t)
            if p:
                typ = p.get('type', 'unknown')
                if typ == 'client': client_n += 1
                elif typ == 'relay': relay_n += 1
                else: other_n += 1
                # Mask sensitive
                safe = dict(p)
                for k in ['key', 'd', 'dc']:
                    if k in safe and isinstance(safe[k], str) and len(safe[k]) > 8:
                        safe[k] = safe[k][:6] + '...'
                print(f"  [{typ}] {json.dumps(safe)}")
        # Count all
        for t in jwts[5:]:
            p = decode_jwt(t)
            if p:
                typ = p.get('type', 'unknown')
                if typ == 'client': client_n += 1
                elif typ == 'relay': relay_n += 1
                else: other_n += 1
        print(f"\n  Total: client={client_n} relay={relay_n} other={other_n}")
    
    # Relay key extraction
    relay_keys = set()
    for s in strings:
        for m in re.finditer(r'relay-[0-9a-f]{16}', s):
            relay_keys.add(m.group())
    if relay_keys:
        print(f"\n--- Relay API Keys ({len(relay_keys)}) ---")
        for k in sorted(relay_keys):
            print(f"  {k}")
    
    # Binary comparison
    print("\n--- Binary Versions ---")
    for ver, path in [
        ('v2.0.3', r'D:\浏览器下载\7011772699590802 (1)\CodeFreeWindsurf-x64-2.0.3.exe'),
        ('v2.0.4', r'D:\Desktop\CodeFreeWindsurf-x64-2.0.4.exe'),
        ('v2.0.5', r'D:\浏览器下载\4231772777854000\CodeFreeWindsurf-x64-2.0.5.exe'),
    ]:
        if os.path.exists(path):
            sz = os.path.getsize(path)
            print(f"  {ver}: {sz:,} bytes ({sz/1024/1024:.2f} MB)")

if __name__ == '__main__':
    main()
