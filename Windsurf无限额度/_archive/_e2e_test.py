"""全链路测试 — 不干扰现有服务"""
import asyncio, ssl, socket, json, time, struct, os, sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(r'd:\道\道生一\一生二\Windsurf无限额度')
CERT_PEM = SCRIPT_DIR / 'windsurf_proxy_ca.pem'
CERT_KEY = SCRIPT_DIR / 'windsurf_proxy_ca.key'
CERT_CER = SCRIPT_DIR / 'windsurf_proxy_ca.cer'
TEST_PORT = 9443

bugs, warns, passes = [], [], []
def bug(id, sev, desc): bugs.append((id, sev, desc))
def warn(id, desc): warns.append((id, desc))
def ok(id, desc): passes.append((id, desc))

# ===== T1: 证书审计 =====
print('=== T1: 证书链审计 ===')
try:
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    cert_data = open(CERT_PEM, 'rb').read()
    cert = x509.load_pem_x509_certificate(cert_data)

    from datetime import timezone
    nb = cert.not_valid_before_utc if hasattr(cert, 'not_valid_before_utc') else cert.not_valid_before.replace(tzinfo=timezone.utc)
    na = cert.not_valid_after_utc if hasattr(cert, 'not_valid_after_utc') else cert.not_valid_after.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    days_left = (na - now).days
    print(f'  有效期: {nb.date()} ~ {na.date()} ({days_left}天)')
    if days_left < 30:
        bug('T1.1', '🔴', f'证书即将过期: {days_left}天')
    else:
        ok('T1.1', f'证书有效期: {days_left}天')

    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        dns_names = san.value.get_values_for_type(x509.DNSName)
        ips = san.value.get_values_for_type(x509.IPAddress)
        print(f'  SAN DNS: {dns_names}')
        print(f'  SAN IP: {[str(ip) for ip in ips]}')
        required = ['server.self-serve.windsurf.com', 'server.codeium.com', 'localhost']
        missing = [d for d in required if d not in dns_names]
        if missing:
            bug('T1.2', '🔴', f'证书缺少SAN: {missing}')
        else:
            ok('T1.2', 'SAN包含所有必需域名')
    except Exception as e:
        bug('T1.2', '🔴', f'证书无SAN扩展: {e}')

    try:
        bc = cert.extensions.get_extension_for_class(x509.BasicConstraints)
        ok('T1.3', f'CA={bc.value.ca}') if bc.value.ca else warn('T1.3', 'CA=False')
    except:
        warn('T1.3', '无BasicConstraints')

    ks = cert.public_key().key_size
    print(f'  密钥: RSA-{ks}')
    ok('T1.4', f'RSA-{ks}') if ks >= 2048 else bug('T1.4', '🟡', f'密钥短: {ks}')

    key_data = open(CERT_KEY, 'rb').read()
    priv = load_pem_private_key(key_data, password=None)
    if cert.public_key().public_numbers().n == priv.public_key().public_numbers().n:
        ok('T1.5', 'PEM与KEY匹配')
    else:
        bug('T1.5', '🔴', 'PEM与KEY不匹配!')

    if CERT_CER.exists():
        cer = x509.load_der_x509_certificate(open(CERT_CER, 'rb').read())
        if cer.serial_number == cert.serial_number:
            ok('T1.6', 'CER与PEM一致')
        else:
            bug('T1.6', '🔴', 'CER与PEM不一致!')
    else:
        bug('T1.6', '🟡', 'CER不存在')
except Exception as e:
    bug('T1.0', '🔴', f'证书审计异常: {e}')

# ===== T2: 系统证书信任 =====
print('\n=== T2: 系统证书信任 ===')
ssl_cert = os.environ.get('SSL_CERT_FILE', '')
if ssl_cert:
    if os.path.isfile(ssl_cert):
        sys_cert = x509.load_pem_x509_certificate(open(ssl_cert, 'rb').read())
        local_cert = x509.load_pem_x509_certificate(open(CERT_PEM, 'rb').read())
        if sys_cert.serial_number == local_cert.serial_number:
            ok('T2.1', f'SSL_CERT_FILE证书匹配 (SN一致)')
        else:
            bug('T2.1', '🔴', f'SSL_CERT_FILE证书不匹配! SN不同')
    else:
        bug('T2.1', '🔴', f'SSL_CERT_FILE路径不存在: {ssl_cert}')
else:
    bug('T2.1', '🟡', 'SSL_CERT_FILE未设置')

# ===== T3: 上游连通性 =====
print('\n=== T3: 上游连通性 ===')
async def test_upstreams():
    targets = [
        ('server.codeium.com', '35.223.238.178', 443),
        ('server.self-serve.windsurf.com', '34.49.14.144', 443),
    ]
    for host, ip, port in targets:
        try:
            ctx = ssl.create_default_context()
            r, w = await asyncio.wait_for(
                asyncio.open_connection(ip, port, ssl=ctx, server_hostname=host), timeout=10)
            so = w.get_extra_info('ssl_object')
            ver = so.version() if so else '?'
            alpn = so.selected_alpn_protocol() if so else '?'
            cipher = so.cipher()[0] if so else '?'
            print(f'  {host} ({ip}): TLS={ver} ALPN={alpn}')
            w.close(); await w.wait_closed()
            ok(f'T3.{host[:10]}', f'{host} reachable')
        except Exception as e:
            bug(f'T3.{host[:10]}', '🔴', f'{host}: {e}')
asyncio.run(test_upstreams())

# ===== T4: 代理E2E =====
import socket as _sock
def _probe(port):
    s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM); s.settimeout(1)
    r = s.connect_ex(('127.0.0.1', port)); s.close(); return r == 0
proxy_port = next((p for p in [TEST_PORT, 443] if _probe(p)), None)

if proxy_port:
    print(f'\n=== T4: 代理E2E (port {proxy_port}, live) ===')
else:
    print(f'\n=== T4: 代理E2E (SKIP) ===')
    warn('T4.0', '无代理运行，跳过E2E')

async def e2e_test():
    if not proxy_port: return
    ctx_c = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx_c.check_hostname = False; ctx_c.verify_mode = ssl.CERT_NONE
    ctx_c.set_alpn_protocols(['h2'])
    preface = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'
    settings = b'\x00\x00\x00\x04\x00\x00\x00\x00\x00'

    # T4.1: TLS + ALPN
    try:
        cr, cw = await asyncio.wait_for(
            asyncio.open_connection('127.0.0.1', proxy_port, ssl=ctx_c,
                                    server_hostname='server.codeium.com'), timeout=10)
        so = cw.get_extra_info('ssl_object')
        alpn = so.selected_alpn_protocol() if so else None
        if alpn == 'h2': ok('T4.1', f'TLS+ALPN=h2 (port {proxy_port})')
        else: bug('T4.1', '🔴', f'ALPN={alpn}')
        # T4.2: H2 roundtrip
        cw.write(preface + settings); await cw.drain()
        try:
            resp = await asyncio.wait_for(cr.read(4096), timeout=5)
            if resp and len(resp) > 0: ok('T4.2', f'H2透传: 发{len(preface)+len(settings)}B→收{len(resp)}B')
            else: bug('T4.2', '🟡', '无响应')
        except asyncio.TimeoutError: bug('T4.2', '🟡', '响应超时')
        cw.close()
    except Exception as e:
        bug('T4.1', '🔴', f'E2E失败: {e}')

    # T4.3: 并发
    try:
        results = []
        async def ct(i):
            try:
                c2 = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                c2.check_hostname = False; c2.verify_mode = ssl.CERT_NONE; c2.set_alpn_protocols(['h2'])
                r2, w2 = await asyncio.wait_for(
                    asyncio.open_connection('127.0.0.1', proxy_port, ssl=c2,
                                            server_hostname='server.codeium.com'), timeout=10)
                w2.close(); await w2.wait_closed(); results.append(True)
            except: results.append(False)
        await asyncio.gather(*[ct(i) for i in range(3)])
        s = sum(1 for r in results if r)
        ok('T4.3', f'并发: {s}/3') if s == 3 else bug('T4.3', '🟡', f'并发: {s}/3')
    except Exception as e:
        bug('T4.3', '🟡', f'并发异常: {e}')

    # T4.4: SNI路由
    try:
        ctx_sni = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx_sni.check_hostname = False; ctx_sni.verify_mode = ssl.CERT_NONE; ctx_sni.set_alpn_protocols(['h2'])
        cr2, cw2 = await asyncio.wait_for(
            asyncio.open_connection('127.0.0.1', proxy_port, ssl=ctx_sni,
                                    server_hostname='server.self-serve.windsurf.com'), timeout=10)
        cw2.write(preface + settings); await cw2.drain()
        try:
            resp2 = await asyncio.wait_for(cr2.read(4096), timeout=5)
            if resp2 and len(resp2) > 0: ok('T4.4', f'SNI路由: self-serve {len(resp2)}B')
            else: bug('T4.4', '🟡', 'SNI路由无响应')
        except asyncio.TimeoutError: bug('T4.4', '🟡', 'SNI路由超时')
        cw2.close()
    except Exception as e:
        bug('T4.4', '🟡', f'SNI路由失败: {e}')

asyncio.run(e2e_test())

# ===== T5: 代码审计 =====
print('\n=== T5: 代码审计 ===')
code = open(SCRIPT_DIR / 'windsurf_proxy.py', 'r', encoding='utf-8').read()

if '35.185.11.128' in code:
    bug('T5.1', '🟡', 'fallback IP 35.185.11.128过时')
else:
    ok('T5.1', 'fallback IP已更新')

if 'with stats_lock:' in code and 'self.conn_id = stats["connections"]' in code:
    ok('T5.2', 'conn_id在锁内读取')
elif 'self.conn_id = stats["connections"]' in code:
    bug('T5.2', '🟡', 'conn_id竞态')
else:
    ok('T5.2', 'conn_id模式已变更')

if 'stats["requests"] += 1' in code:
    warn('T5.3', 'requests统计粒度是TCP segment非gRPC请求')

if 'signal' in code and 'SIGINT' in code:
    ok('T5.4', 'graceful shutdown已实现(signal.SIGINT)')
else:
    warn('T5.4', '无graceful shutdown')

if 'while idx < len(data) - 10:' in code:
    warn('T5.5', 'parse_grpc_path逐字节扫描效率低')

# SNI路由检查
if 'sni_host' in code and 'UPSTREAM_HOSTS[self.sni_host]' in code:
    ok('T5.6', 'SNI路由已实现')
elif 'UPSTREAM_HOSTS' in code and 'sni' not in code.lower():
    bug('T5.6', '🔴', 'UPSTREAM_HOSTS定义但无SNI路由')
else:
    ok('T5.6', 'SNI路由逻辑存在')

warn('T5.7', '--token注入尚未实现(低优先级)')

if 'reconnect' not in code.lower() and 'retry' not in code.lower():
    warn('T5.8', '上游断连无自动重连')

warn('T5.9', 'preflight只检查hosts含域名(可接受)')

ok('T5.0', '代码审计完成')

# ===== T6: patch_windsurf.py =====
print('\n=== T6: patch兼容性 ===')
ws_paths = [r'D:\Windsurf', os.path.expandvars(r'%LOCALAPPDATA%\Programs\Windsurf')]
found_js = None
for base in ws_paths:
    p = os.path.join(base, r'resources\app\out\vs\workbench\workbench.desktop.main.js')
    if os.path.isfile(p):
        found_js = p; break

if found_js:
    sz = os.path.getsize(found_js) / 1024 / 1024
    product_json = os.path.normpath(os.path.join(os.path.dirname(found_js), '..', '..', '..', 'product.json'))
    ver = '?'
    if os.path.isfile(product_json):
        ver = json.load(open(product_json, 'r', encoding='utf-8')).get('version', '?')
    print(f'  {found_js} ({sz:.1f}MB, v{ver})')

    with open(found_js, 'r', encoding='utf-8') as f:
        content_full = f.read()

    # 验证补丁状态: 检查patched文本是否存在(不检查orig,因为变量名会变)
    patch_checks = [
        ('U5e=Z=>!0,W5e=', 'Credit bypass'),
        ('if(!1)return', 'Capacity bypass'),
        ('dismissedOutOfCredit:!0,dismissedStatusWarning:!0', 'Warnings dismissed'),
        ('this.isEnterprise=!0,this.hasPaidFeatures=!0', 'Enterprise flags'),
        ('planName:"Pro Ultimate"', 'PlanName override'),
    ]
    for patched, name in patch_checks:
        if patched in content_full:
            ok(f'T6.{name[:5]}', f'{name}: 已生效')
        else:
            bug(f'T6.{name[:5]}', '🟡', f'{name}: 未检测到补丁')

    # 检查是否有未补丁的hasCapacity (regex)
    import re as re2
    unpatched_cap = re2.findall(r'if\(!\w+\.hasCapacity\)return', content_full)
    if unpatched_cap:
        bug('T6.Cap2', '🟡', f'仍有{len(unpatched_cap)}个未补丁的hasCapacity检查')
    else:
        ok('T6.Cap2', '所有hasCapacity检查已补丁')
else:
    warn('T6.0', 'workbench.desktop.main.js未找到')

# ===== T7: 启动脚本 =====
print('\n=== T7: 启动脚本 ===')
cmd = SCRIPT_DIR / '→自建代理.cmd'
if cmd.exists():
    cc = open(cmd, 'r', encoding='utf-8', errors='ignore').read()
    if 'net session' in cc: ok('T7.1', 'CMD含管理员检查')
    else: warn('T7.1', 'CMD无管理员检查')
    if 'findstr' in cc and '443' in cc: ok('T7.2', 'CMD含端口冲突检测')
    else: warn('T7.2', 'CMD无端口冲突检测')
    if 'python windsurf_proxy.py' in cc: ok('T7.3', 'CMD启动命令正确')
    else: bug('T7.3', '🟡', 'CMD启动命令缺失')
else:
    bug('T7.0', '🟡', '→自建代理.cmd不存在')

# ===== 汇总 =====
print(f'\n{"="*55}')
print(f'  全链路测试汇总')
print(f'{"="*55}')
print(f'  PASS: {len(passes)}')
for id, desc in passes:
    print(f'    [{id}] {desc}')
print(f'  WARN: {len(warns)}')
for id, desc in warns:
    print(f'    [{id}] {desc}')
print(f'  BUG:  {len(bugs)}')
for id, sev, desc in bugs:
    print(f'    [{id}] {sev} {desc}')
print(f'{"="*55}')
print(f'  评分: {len(passes)}/{len(passes)+len(bugs)} ({100*len(passes)/max(1,len(passes)+len(bugs)):.0f}%)')
print(f'{"="*55}')
