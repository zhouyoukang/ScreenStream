"""CFW v2.0.4/v2.0.5 深度逆向提取工具"""
import ctypes
import ctypes.wintypes as wt
import struct
import json
import re
import sys
import os
import subprocess

# Windows API
kernel32 = ctypes.windll.kernel32
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wt.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
    ]

MEM_COMMIT = 0x1000
PAGE_READABLE = 0x02 | 0x04 | 0x20 | 0x40 | 0x80  # various read-allowed flags

def find_cfw_pid():
    """Find CFW process PID"""
    result = subprocess.run(
        ['powershell', '-c', 
         "(Get-Process | Where-Object { $_.ProcessName -match 'CodeFree' }).Id"],
        capture_output=True, text=True
    )
    pid_str = result.stdout.strip()
    if pid_str:
        return int(pid_str)
    return None

def is_readable(protect):
    """Check if memory protection allows reading"""
    # PAGE_READONLY=0x02, PAGE_READWRITE=0x04, PAGE_WRITECOPY=0x08,
    # PAGE_EXECUTE_READ=0x20, PAGE_EXECUTE_READWRITE=0x40, PAGE_EXECUTE_WRITECOPY=0x80
    readable = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}
    p = protect & 0xFF
    return p in readable

def extract_memory_strings(pid, patterns, max_results=300):
    """Extract strings matching patterns from process memory"""
    handle = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not handle:
        err = ctypes.get_last_error()
        print(f"ERROR: Cannot open process {pid} (err={err}, need admin)")
        return []
    
    results = []
    address = 0
    mbi = MEMORY_BASIC_INFORMATION()
    mbi_size = ctypes.sizeof(mbi)
    
    regions_scanned = 0
    regions_skipped = 0
    total_bytes = 0
    
    while kernel32.VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(mbi), mbi_size):
        if mbi.State == MEM_COMMIT and mbi.RegionSize and mbi.RegionSize < 100 * 1024 * 1024:
            if is_readable(mbi.Protect):
                buf = (ctypes.c_char * mbi.RegionSize)()
                bytes_read = ctypes.c_size_t(0)
                if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(mbi.BaseAddress), buf, mbi.RegionSize, ctypes.byref(bytes_read)):
                    data = bytes(buf[:bytes_read.value])
                    total_bytes += len(data)
                    regions_scanned += 1
                    
                    for pattern in patterns:
                        pat_bytes = pattern.encode('utf-8') if isinstance(pattern, str) else pattern
                        idx = 0
                        while True:
                            idx = data.find(pat_bytes, idx)
                            if idx == -1:
                                break
                            # Extract context around match
                            start = max(0, idx - 30)
                            end = min(len(data), idx + len(pat_bytes) + 300)
                            chunk = data[start:end]
                            # Clean to printable
                            clean = ''.join(c if 32 <= ord(c) < 127 else ' ' for c in chunk.decode('utf-8', errors='replace'))
                            clean = ' '.join(clean.split())  # collapse whitespace
                            if len(clean) > 10 and clean not in results:
                                results.append(clean)
                            if len(results) >= max_results:
                                break
                            idx += len(pat_bytes)
                    if len(results) >= max_results:
                        break
        
        if mbi.BaseAddress is None or mbi.RegionSize is None:
            break
        address = (mbi.BaseAddress or 0) + (mbi.RegionSize or 0)
        if address <= 0 or address >= 0x7FFFFFFFFFFF:
            break
    
    kernel32.CloseHandle(handle)
    print(f"Scanned {regions_scanned} regions, {total_bytes/1024/1024:.1f} MB")
    return results

def extract_json_objects(pid):
    """Extract complete JSON objects from process memory"""
    handle = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not handle:
        return []
    
    json_objects = []
    address = 0
    mbi = MEMORY_BASIC_INFORMATION()
    mbi_size = ctypes.sizeof(mbi)
    
    while kernel32.VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(mbi), mbi_size):
        if mbi.State == MEM_COMMIT and mbi.RegionSize < 50 * 1024 * 1024:
            prot = mbi.Protect & 0xFF
            if prot in (0x02, 0x04, 0x20, 0x40, 0x80, 0x06, 0x08):
                buf = (ctypes.c_char * mbi.RegionSize)()
                bytes_read = ctypes.c_size_t(0)
                if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(mbi.BaseAddress), buf, mbi.RegionSize, ctypes.byref(bytes_read)):
                    data = bytes(buf[:bytes_read.value])
                    text = data.decode('utf-8', errors='replace')
                    
                    # Find JSON objects with known CFW keys
                    for key in ['"proxy_mode"', '"active_mappings"', '"email"', '"relay_key"', '"license_key"']:
                        idx = 0
                        while True:
                            idx = text.find(key, idx)
                            if idx == -1:
                                break
                            # Find enclosing braces
                            brace_start = text.rfind('{', max(0, idx - 500), idx)
                            if brace_start >= 0:
                                depth = 0
                                for i in range(brace_start, min(len(text), brace_start + 5000)):
                                    if text[i] == '{': depth += 1
                                    elif text[i] == '}': depth -= 1
                                    if depth == 0:
                                        candidate = text[brace_start:i+1]
                                        # Clean nulls
                                        candidate = candidate.replace('\x00', '')
                                        try:
                                            obj = json.loads(candidate)
                                            if isinstance(obj, dict) and len(obj) > 3:
                                                json_objects.append(obj)
                                        except:
                                            pass
                                        break
                            idx += len(key)
                    
                    if len(json_objects) >= 20:
                        break
        
        if mbi.BaseAddress is None or mbi.RegionSize is None:
            break
        address = (mbi.BaseAddress or 0) + (mbi.RegionSize or 0)
        if address <= 0 or address >= 0x7FFFFFFFFFFF:
            break
    
    kernel32.CloseHandle(handle)
    return json_objects

def extract_jwt_tokens(pid):
    """Extract JWT tokens from process memory"""
    handle = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not handle:
        return []
    
    tokens = []
    address = 0
    mbi = MEMORY_BASIC_INFORMATION()
    mbi_size = ctypes.sizeof(mbi)
    
    jwt_pattern = re.compile(rb'eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}')
    
    while kernel32.VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(mbi), mbi_size):
        if mbi.State == MEM_COMMIT and mbi.RegionSize < 50 * 1024 * 1024:
            prot = mbi.Protect & 0xFF
            if prot in (0x02, 0x04, 0x20, 0x40, 0x80, 0x06, 0x08):
                buf = (ctypes.c_char * mbi.RegionSize)()
                bytes_read = ctypes.c_size_t(0)
                if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(mbi.BaseAddress), buf, mbi.RegionSize, ctypes.byref(bytes_read)):
                    data = bytes(buf[:bytes_read.value])
                    for m in jwt_pattern.finditer(data):
                        token = m.group().decode('ascii', errors='ignore')
                        if token not in tokens:
                            tokens.append(token)
                    if len(tokens) >= 100:
                        break
        
        if mbi.BaseAddress is None or mbi.RegionSize is None:
            break
        address = (mbi.BaseAddress or 0) + (mbi.RegionSize or 0)
        if address <= 0 or address >= 0x7FFFFFFFFFFF:
            break
    
    kernel32.CloseHandle(handle)
    return tokens

def decode_jwt_payload(token):
    """Decode JWT payload (no verification)"""
    import base64
    parts = token.split('.')
    if len(parts) != 3:
        return None
    payload = parts[1]
    # Add padding
    payload += '=' * (4 - len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except:
        return None

def main():
    pid = find_cfw_pid()
    if not pid:
        print("ERROR: CFW process not found")
        sys.exit(1)
    
    print(f"=== CFW Deep Reverse Engineering ===")
    print(f"PID: {pid}")
    print()
    
    # Phase 1: Extract known-key strings
    print("--- Phase 1: Memory String Extraction ---")
    patterns = [
        '"proxy_mode"', '"relay_key"', '"email"', '"running"',
        '"security_clean"', '"active_mappings"', '"session_cost"',
        '"request_count"', '"mitm_detected"', '"proxy_port"',
        '"relay_blocked"', '"target_host"', 'windsurf.pro',
        'x-relay-token', 'X-Device-Code', 'X-Session-Token',
        'relay-', '"license"', '"version"', '"node"',
        '"input_tokens"', '"output_tokens"', '"ad_messages"',
        'server.self-serve', 'server.codeium', '47.108.',
        '156.225.', '103.149.', 'inference.codeium',
    ]
    strings = extract_memory_strings(pid, patterns, max_results=200)
    print(f"Found {len(strings)} unique string matches")
    for s in strings[:80]:
        print(f"  {s[:200]}")
    
    # Phase 2: Extract JSON state objects
    print("\n--- Phase 2: JSON State Objects ---")
    json_objs = extract_json_objects(pid)
    print(f"Found {len(json_objs)} JSON objects")
    for obj in json_objs[:10]:
        print(json.dumps(obj, indent=2, ensure_ascii=False)[:500])
        print("---")
    
    # Phase 3: JWT Token extraction
    print("\n--- Phase 3: JWT Tokens ---")
    tokens = extract_jwt_tokens(pid)
    print(f"Found {len(tokens)} JWT tokens")
    
    client_jwts = []
    relay_jwts = []
    other_jwts = []
    
    for t in tokens:
        payload = decode_jwt_payload(t)
        if payload:
            typ = payload.get('type', '')
            if typ == 'client':
                client_jwts.append(payload)
            elif typ == 'relay':
                relay_jwts.append(payload)
            else:
                other_jwts.append(payload)
    
    print(f"  Client JWTs: {len(client_jwts)}")
    print(f"  Relay JWTs: {len(relay_jwts)}")
    print(f"  Other JWTs: {len(other_jwts)}")
    
    if client_jwts:
        print("\n  Sample Client JWT:")
        sample = client_jwts[0]
        # Mask sensitive data
        if 'key' in sample:
            sample['key'] = sample['key'][:6] + '...' + sample['key'][-4:]
        print(f"    {json.dumps(sample, indent=4)}")
    
    if relay_jwts:
        print(f"\n  Relay JWT count: {len(relay_jwts)}")
        sample = relay_jwts[0]
        if 'd' in sample and len(str(sample['d'])) > 20:
            sample['d'] = str(sample['d'])[:30] + '...[truncated]'
        print(f"    {json.dumps(sample, indent=4)}")
    
    if other_jwts:
        print("\n  Other JWT samples:")
        for oj in other_jwts[:3]:
            print(f"    {json.dumps(oj, indent=4)[:300]}")
    
    # Phase 4: Relay API key extraction
    print("\n--- Phase 4: Relay API Keys ---")
    relay_pattern_strings = [s for s in strings if 'relay-' in s.lower()]
    relay_keys = set()
    for s in relay_pattern_strings:
        for m in re.finditer(r'relay-[0-9a-f]{16}', s):
            relay_keys.add(m.group())
    print(f"Found {len(relay_keys)} relay keys:")
    for k in sorted(relay_keys):
        print(f"  {k}")
    
    # Phase 5: Version comparison info
    print("\n--- Phase 5: Binary Size Comparison ---")
    versions = {
        'v2.0.3': r'D:\浏览器下载\7011772699590802 (1)\CodeFreeWindsurf-x64-2.0.3.exe',
        'v2.0.4': r'D:\Desktop\CodeFreeWindsurf-x64-2.0.4.exe',
        'v2.0.5': r'D:\浏览器下载\4231772777854000\CodeFreeWindsurf-x64-2.0.5.exe',
    }
    for ver, path in versions.items():
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  {ver}: {size:,} bytes ({size/1024/1024:.2f} MB)")
    
    # Summary
    print("\n=== SUMMARY ===")
    print(f"Process: CFW v2.0.4 PID {pid}")
    print(f"Memory strings: {len(strings)}")
    print(f"JSON objects: {len(json_objs)}")
    print(f"JWT tokens: {len(tokens)} (client:{len(client_jwts)} relay:{len(relay_jwts)} other:{len(other_jwts)})")
    print(f"Relay keys: {len(relay_keys)}")

if __name__ == '__main__':
    main()
