"""
CFW v2.0.6 深度逆向提取工具 v2.0
修复: 使用ctypes.c_ulonglong替代c_void_p解决x64地址问题
"""
import ctypes
import ctypes.wintypes as wt
import struct
import json
import re
import sys
import os
import subprocess
import base64

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# 64-bit compatible MEMORY_BASIC_INFORMATION
class MEMORY_BASIC_INFORMATION64(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_ulonglong),
        ("AllocationBase", ctypes.c_ulonglong),
        ("AllocationProtect", wt.DWORD),
        ("__alignment1", wt.DWORD),
        ("RegionSize", ctypes.c_ulonglong),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
        ("__alignment2", wt.DWORD),
    ]

MEM_COMMIT = 0x1000
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
READABLE = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}

# Properly declare VirtualQueryEx for 64-bit
kernel32.VirtualQueryEx.argtypes = [
    wt.HANDLE, ctypes.c_ulonglong,
    ctypes.POINTER(MEMORY_BASIC_INFORMATION64), ctypes.c_ulonglong
]
kernel32.VirtualQueryEx.restype = ctypes.c_ulonglong

kernel32.ReadProcessMemory.argtypes = [
    wt.HANDLE, ctypes.c_ulonglong,
    ctypes.c_void_p, ctypes.c_ulonglong,
    ctypes.POINTER(ctypes.c_ulonglong)
]
kernel32.ReadProcessMemory.restype = wt.BOOL

kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenProcess.restype = wt.HANDLE


def find_cfw_pid():
    r = subprocess.run(
        ['tasklist', '/FI', 'IMAGENAME eq CodeFreeWindsurf*', '/FO', 'CSV', '/NH'],
        capture_output=True, text=True
    )
    for line in r.stdout.strip().split('\n'):
        if 'CodeFree' in line:
            parts = line.strip('"').split('","')
            if len(parts) >= 2:
                return int(parts[1])
    return None


def scan_memory(pid, patterns, max_results=300):
    """Scan process memory for string patterns"""
    handle = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not handle:
        err = ctypes.get_last_error()
        print(f"ERROR: OpenProcess failed (pid={pid}, err={err})")
        print("  需要管理员权限运行此脚本")
        return [], [], []

    results = []
    json_objects = []
    jwt_tokens = []
    mbi = MEMORY_BASIC_INFORMATION64()
    mbi_size = ctypes.c_ulonglong(ctypes.sizeof(mbi))
    address = ctypes.c_ulonglong(0)
    
    regions_scanned = 0
    total_bytes = 0
    jwt_re = re.compile(rb'eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}')

    while kernel32.VirtualQueryEx(handle, address, ctypes.byref(mbi), mbi_size):
        if (mbi.State == MEM_COMMIT and 
            mbi.RegionSize > 0 and 
            mbi.RegionSize < 100 * 1024 * 1024 and
            (mbi.Protect & 0xFF) in READABLE):
            
            buf = (ctypes.c_char * mbi.RegionSize)()
            bytes_read = ctypes.c_ulonglong(0)
            
            if kernel32.ReadProcessMemory(handle, ctypes.c_ulonglong(mbi.BaseAddress), 
                                          buf, ctypes.c_ulonglong(mbi.RegionSize), 
                                          ctypes.byref(bytes_read)):
                data = bytes(buf[:bytes_read.value])
                total_bytes += len(data)
                regions_scanned += 1
                
                # String pattern search
                for pat in patterns:
                    pat_b = pat.encode('utf-8') if isinstance(pat, str) else pat
                    idx = 0
                    while True:
                        idx = data.find(pat_b, idx)
                        if idx == -1:
                            break
                        start = max(0, idx - 30)
                        end = min(len(data), idx + len(pat_b) + 300)
                        chunk = data[start:end].decode('utf-8', errors='replace')
                        clean = ''.join(c if 32 <= ord(c) < 127 else ' ' for c in chunk)
                        clean = ' '.join(clean.split())
                        if len(clean) > 10 and clean not in results:
                            results.append(clean)
                        if len(results) >= max_results:
                            break
                        idx += len(pat_b)
                
                # JSON object extraction
                text = data.decode('utf-8', errors='replace')
                for key in ['"proxy_mode"', '"active_mappings"', '"email"', 
                           '"relay_key"', '"license_key"', '"version"']:
                    idx = 0
                    while True:
                        idx = text.find(key, idx)
                        if idx == -1:
                            break
                        bs = text.rfind('{', max(0, idx - 500), idx)
                        if bs >= 0:
                            depth = 0
                            for i in range(bs, min(len(text), bs + 5000)):
                                if text[i] == '{': depth += 1
                                elif text[i] == '}': depth -= 1
                                if depth == 0:
                                    candidate = text[bs:i+1].replace('\x00', '')
                                    try:
                                        obj = json.loads(candidate)
                                        if isinstance(obj, dict) and len(obj) > 3:
                                            json_objects.append(obj)
                                    except:
                                        pass
                                    break
                        idx += len(key)
                
                # JWT extraction
                for m in jwt_re.finditer(data):
                    token = m.group().decode('ascii', errors='ignore')
                    if token not in jwt_tokens:
                        jwt_tokens.append(token)

        next_addr = mbi.BaseAddress + mbi.RegionSize
        if next_addr <= address.value or next_addr > 0x7FFFFFFFFFFF:
            break
        address = ctypes.c_ulonglong(next_addr)

    kernel32.CloseHandle(handle)
    print(f"Scanned {regions_scanned} regions, {total_bytes/1024/1024:.1f} MB")
    return results, json_objects, jwt_tokens


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
    pid = find_cfw_pid()
    if not pid:
        print("ERROR: CFW process not found")
        sys.exit(1)

    print(f"=== CFW v2.0.6 Deep Reverse Engineering v2 ===")
    print(f"PID: {pid}")
    print(f"Python: {sys.version}")
    print(f"Arch: {ctypes.sizeof(ctypes.c_void_p)*8}-bit")
    print()

    patterns = [
        '"proxy_mode"', '"relay_key"', '"email"', '"running"',
        '"security_clean"', '"active_mappings"', '"session_cost"',
        '"request_count"', '"mitm_detected"', '"proxy_port"',
        '"relay_blocked"', '"target_host"', '"license"', '"version"',
        '"input_tokens"', '"output_tokens"', '"backend"',
        'x-relay-token', 'X-Device-Code', 'X-Session-Token',
        'server.self-serve', 'server.codeium', 'inference.codeium',
        '47.108.', '156.225.', '103.149.',
        'windsurf.pro', 'connect-rpc', 'grpc-status',
    ]

    strings, json_objs, jwt_tokens = scan_memory(pid, patterns)

    print(f"\n--- Phase 1: Memory Strings ({len(strings)}) ---")
    for s in strings[:60]:
        print(f"  {s[:200]}")

    print(f"\n--- Phase 2: JSON Objects ({len(json_objs)}) ---")
    seen = set()
    for obj in json_objs[:15]:
        key = json.dumps(sorted(obj.keys()))
        if key not in seen:
            seen.add(key)
            print(json.dumps(obj, indent=2, ensure_ascii=False)[:600])
            print("---")

    print(f"\n--- Phase 3: JWT Tokens ({len(jwt_tokens)}) ---")
    client_jwts, relay_jwts, other_jwts = [], [], []
    for t in jwt_tokens:
        p = decode_jwt(t)
        if p:
            typ = p.get('type', '')
            if typ == 'client': client_jwts.append(p)
            elif typ == 'relay': relay_jwts.append(p)
            else: other_jwts.append(p)

    print(f"  Client: {len(client_jwts)} | Relay: {len(relay_jwts)} | Other: {len(other_jwts)}")
    
    if client_jwts:
        sample = dict(client_jwts[0])
        for k in ['key', 'd', 'token']:
            if k in sample and len(str(sample[k])) > 20:
                sample[k] = str(sample[k])[:15] + '...[redacted]'
        print(f"\n  Client JWT sample:\n    {json.dumps(sample, indent=4)[:500]}")
    
    if relay_jwts:
        sample = dict(relay_jwts[0])
        for k in ['d', 'key', 'token']:
            if k in sample and len(str(sample[k])) > 20:
                sample[k] = str(sample[k])[:15] + '...[redacted]'
        print(f"\n  Relay JWT sample:\n    {json.dumps(sample, indent=4)[:500]}")

    # Phase 4: Binary comparison
    print(f"\n--- Phase 4: Binary Comparison ---")
    versions = {
        'v1.0.31': r'D:\浏览器下载\8291772382640798\CodeFreeWindsurf-x64-1.0.31.exe',
        'v2.0.3': r'D:\浏览器下载\7011772699590802 (1)\CodeFreeWindsurf-x64-2.0.3.exe',
        'v2.0.4': r'D:\Desktop\CodeFreeWindsurf-x64-2.0.4.exe',
        'v2.0.5': r'D:\浏览器下载\4231772777854000\CodeFreeWindsurf-x64-2.0.5.exe',
    }
    for ver, path in versions.items():
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  {ver}: {size:,} bytes ({size/1024/1024:.2f} MB)")

    # Phase 5: Network connections
    print(f"\n--- Phase 5: Network (PID {pid}) ---")
    r = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
    for line in r.stdout.split('\n'):
        if str(pid) in line and ('ESTABLISHED' in line or 'LISTENING' in line):
            print(f"  {line.strip()}")

    # Summary
    print(f"\n{'='*50}")
    print(f"SUMMARY")
    print(f"  PID: {pid}")
    print(f"  Strings: {len(strings)}")
    print(f"  JSON objects: {len(json_objs)}")
    print(f"  JWTs: {len(jwt_tokens)} (client:{len(client_jwts)} relay:{len(relay_jwts)} other:{len(other_jwts)})")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
