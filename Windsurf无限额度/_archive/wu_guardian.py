#!/usr/bin/env python3
"""
WU Guardian v1.0 — 持久化守护+全链路E2E+一键修复
=================================================
功能:
  1. hosts守护: 检测+自动恢复WU MITM hosts条目
  2. CA证书守护: 检测+自动安装WU MITM CA
  3. WU进程守护: crash检测+自动重启
  4. 443端口守护: MITM代理监听检测
  5. 全链路E2E: TLS握手+DNS+后端连通+Windsurf gRPC流量
  6. 积分监控: 实时查询+告警
  7. 一键修复: 所有问题一键解决
  8. daemon模式: 持续120s巡检

用法:
  python wu_guardian.py              # 全景诊断
  python wu_guardian.py --fix        # 诊断+修复所有问题
  python wu_guardian.py --daemon     # 持续守护模式(120s)
  python wu_guardian.py --e2e        # 全链路E2E测试
  python wu_guardian.py --credits    # 积分查询
"""

import os, sys, json, subprocess, socket, ssl, time, platform
from pathlib import Path
from datetime import datetime, timezone

# ============================================================
# 常量
# ============================================================
HOSTS_FILE = r'C:\Windows\System32\drivers\etc\hosts'
WU_MITM_IP = '127.65.43.21'
WU_MITM_MARKER = '# windsurf-mitm-proxy'
MITM_DOMAINS = ['server.self-serve.windsurf.com', 'server.codeium.com']

WU_DATA = Path(os.environ.get('APPDATA', '')) / 'windsurf-unlimited'
WU_SESSION = WU_DATA / 'session.json'
WU_CERTS = WU_DATA / 'certs'
WU_CA_CRT = WU_CERTS / 'ca.crt'
WU_INSTALL = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'WindsurfUnlimited'
WU_EXE = WU_INSTALL / 'WindsurfUnlimited.exe'

WS_SETTINGS = Path(os.environ.get('APPDATA', '')) / 'Windsurf' / 'User' / 'settings.json'
WS_USER_PB = Path.home() / '.codeium' / 'windsurf' / 'user_settings.pb'

WU_API_USAGE = '/api/v1/auth/usage'
WU_API_VALIDATE = '/api/v1/auth/validate'

# ============================================================
# 诊断框架
# ============================================================
class Diag:
    def __init__(self):
        self.items = []
        self.errors = []
        self.fixes = []

    def ok(self, name, detail=''):
        self.items.append(('✅', name, detail))

    def fail(self, name, detail=''):
        self.items.append(('❌', name, detail))
        self.errors.append(f'{name}: {detail}')

    def warn(self, name, detail=''):
        self.items.append(('⚠️', name, detail))

    def fix(self, name, detail=''):
        self.fixes.append(f'{name}: {detail}')

    @property
    def score(self):
        return sum(1 for s, *_ in self.items if s == '✅')

    @property
    def total(self):
        return len(self.items)

    def summary(self):
        return f'{self.score}/{self.total} ({self.score/max(self.total,1)*100:.0f}%)'

# ============================================================
# 1. Hosts守护
# ============================================================
def check_hosts(d, fix=False):
    try:
        content = open(HOSTS_FILE, encoding='utf-8').read()
        expected_lines = [f'{WU_MITM_IP} {dom}' for dom in MITM_DOMAINS]
        missing = [l for l in expected_lines if l not in content]

        if not missing:
            d.ok('hosts', f'{WU_MITM_IP} → {len(MITM_DOMAINS)}域名')
            return True

        d.fail('hosts', f'缺失{len(missing)}条: {missing[0][:40]}...')
        if fix:
            lines_to_add = []
            if WU_MITM_MARKER not in content:
                lines_to_add.append(WU_MITM_MARKER)
            for m in missing:
                lines_to_add.append(m)
            with open(HOSTS_FILE, 'a', encoding='ascii') as f:
                f.write('\n' + '\n'.join(lines_to_add) + '\n')
            subprocess.run(['ipconfig', '/flushdns'], capture_output=True, timeout=10)
            d.fix('hosts', f'已写入{len(missing)}条+DNS刷新')
            return True
        return False
    except Exception as e:
        d.fail('hosts', str(e))
        return False

# ============================================================
# 2. CA证书守护
# ============================================================
def check_ca_cert(d, fix=False):
    try:
        out = subprocess.run(
            ['certutil', '-store', 'Root'],
            capture_output=True, text=True, timeout=15,
            encoding='gbk', errors='replace'
        ).stdout
        if 'MITM CA' in out or 'Local Proxy' in out:
            d.ok('CA证书', 'Windsurf MITM CA已安装')
            return True
        d.fail('CA证书', '未安装')
        if fix and WU_CA_CRT.exists():
            subprocess.run(['certutil', '-addstore', 'Root', str(WU_CA_CRT)],
                           capture_output=True, timeout=15)
            d.fix('CA证书', '已安装Windsurf MITM CA')
            return True
        return False
    except Exception as e:
        d.warn('CA证书', str(e))
        return False

# ============================================================
# 3. WU进程守护
# ============================================================
def check_wu_process(d, fix=False):
    try:
        out = subprocess.run(
            ['tasklist', '/fi', 'IMAGENAME eq WindsurfUnlimited.exe', '/fo', 'csv', '/nh'],
            capture_output=True, text=True, timeout=5, encoding='gbk', errors='replace'
        ).stdout
        count = out.count('WindsurfUnlimited')
        if count > 0:
            d.ok('WU进程', f'{count}个运行中')
            return True
        d.fail('WU进程', '未运行')
        if fix and WU_EXE.exists():
            subprocess.Popen([str(WU_EXE)], creationflags=0x00000008)
            time.sleep(8)
            d.fix('WU进程', '已重启')
            return True
        return False
    except Exception as e:
        d.fail('WU进程', str(e))
        return False

# ============================================================
# 4. 443端口守护
# ============================================================
def check_443_listen(d, fix=False):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((WU_MITM_IP, 443))
        s.close()
        d.ok('MITM:443', f'{WU_MITM_IP}:443 LISTENING')
        return True
    except Exception:
        d.fail('MITM:443', f'{WU_MITM_IP}:443 未监听')
        if fix:
            # Try restarting WU
            if WU_EXE.exists():
                subprocess.run(['taskkill', '/IM', 'WindsurfUnlimited.exe', '/F'],
                               capture_output=True, timeout=10)
                time.sleep(3)
                subprocess.Popen([str(WU_EXE)], creationflags=0x00000008)
                time.sleep(10)
                try:
                    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s2.settimeout(5)
                    s2.connect((WU_MITM_IP, 443))
                    s2.close()
                    d.fix('MITM:443', 'WU重启后恢复监听')
                    return True
                except Exception:
                    d.fail('MITM:443', 'WU重启后仍未监听')
        return False

# ============================================================
# 5. TLS握手测试
# ============================================================
def check_tls(d):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        start = time.time()
        s = ctx.wrap_socket(socket.socket(), server_hostname=MITM_DOMAINS[0])
        s.settimeout(10)
        s.connect((WU_MITM_IP, 443))
        lat = (time.time() - start) * 1000
        ver = s.version()
        s.close()
        d.ok('TLS握手', f'{ver} {lat:.0f}ms')
        return True
    except Exception as e:
        d.fail('TLS握手', str(e))
        return False

# ============================================================
# 6. DNS验证
# ============================================================
def check_dns(d):
    ok = True
    for dom in MITM_DOMAINS:
        try:
            ip = socket.gethostbyname(dom)
            if ip == WU_MITM_IP:
                d.ok(f'DNS {dom[:25]}', f'→ {ip}')
            else:
                d.fail(f'DNS {dom[:25]}', f'→ {ip} (应为{WU_MITM_IP})')
                ok = False
        except Exception:
            d.fail(f'DNS {dom[:25]}', '解析失败')
            ok = False
    return ok

# ============================================================
# 7. Windsurf配置
# ============================================================
def check_ws_config(d, fix=False):
    if not WS_SETTINGS.exists():
        d.warn('WS settings', '不存在')
        return False
    try:
        settings = json.loads(WS_SETTINGS.read_text())
        changed = False
        ssl_ok = settings.get('http.proxyStrictSSL') == False
        proxy_ok = settings.get('http.proxySupport') == 'off'

        if ssl_ok and proxy_ok:
            d.ok('WS配置', 'proxyStrictSSL=false, proxySupport=off')
            return True

        if not ssl_ok:
            d.fail('WS proxyStrictSSL', 'true → 需要false')
            if fix:
                settings['http.proxyStrictSSL'] = False
                changed = True
        if not proxy_ok:
            d.warn('WS proxySupport', f'{settings.get("http.proxySupport")} → 建议off')
            if fix:
                settings['http.proxySupport'] = 'off'
                changed = True
        if changed:
            WS_SETTINGS.write_text(json.dumps(settings, indent=2, ensure_ascii=False), 'utf-8')
            d.fix('WS配置', '已修复')
        return ssl_ok and proxy_ok
    except Exception as e:
        d.warn('WS配置', str(e))
        return False

# ============================================================
# 8. WU会话状态
# ============================================================
def check_session(d):
    if not WU_SESSION.exists():
        d.fail('WU会话', '未登录')
        return None
    try:
        sess = json.loads(WU_SESSION.read_text())
        exp = datetime.fromtimestamp(sess.get('expires_at', 0))
        remaining = exp - datetime.now()
        card = sess.get('card_type_label', '?')
        server = sess.get('server_url', '?')

        if remaining.total_seconds() > 0:
            hours = remaining.total_seconds() / 3600
            d.ok('WU会话', f'{card} | {hours:.1f}h剩余 | {server}')
        else:
            d.fail('WU会话', f'{card} 已过期')
        return sess
    except Exception as e:
        d.fail('WU会话', str(e))
        return None

# ============================================================
# 9. 积分查询
# ============================================================
def query_credits(sess):
    if not sess:
        return None
    try:
        import urllib.request
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        body = json.dumps({
            'client_id': sess.get('client_id', ''),
            'session_token': sess.get('session_token', '')
        }).encode()

        req = urllib.request.Request(
            sess['server_url'] + WU_API_USAGE,
            data=body,
            headers={'Content-Type': 'application/json'}
        )
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        return json.loads(resp.read())
    except Exception:
        return None

# ============================================================
# 10. Windsurf gRPC流量验证
# ============================================================
def check_grpc_flow(d):
    try:
        out = subprocess.run(
            'netstat -ano | findstr "127.65.43.21:443" | findstr "ESTABLISHED"',
            shell=True, capture_output=True, text=True, timeout=5, encoding='gbk', errors='replace'
        ).stdout
        conns = [l for l in out.strip().split('\n') if l.strip()]
        if len(conns) >= 2:
            d.ok('gRPC流量', f'{len(conns)//2}个活跃连接通过WU代理')
            return True
        elif len(conns) > 0:
            d.warn('gRPC流量', f'{len(conns)}条(可能单向)')
            return True
        else:
            d.fail('gRPC流量', '无ESTABLISHED连接')
            return False
    except Exception:
        d.warn('gRPC流量', '检测失败')
        return False

# ============================================================
# 全景诊断
# ============================================================
def full_diag(fix=False):
    d = Diag()
    print(f'\n{"="*60}')
    print(f'WU Guardian v1.0 — {"诊断+修复" if fix else "全景诊断"}')
    print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'{"="*60}')

    check_hosts(d, fix)
    check_ca_cert(d, fix)
    check_wu_process(d, fix)
    check_443_listen(d, fix)
    check_tls(d)
    check_dns(d)
    check_ws_config(d, fix)
    sess = check_session(d)
    check_grpc_flow(d)

    # 汇总
    print(f'\n{"="*60}')
    for status, name, detail in d.items:
        print(f'  {status} {name}: {detail}')

    if d.fixes:
        print(f'\n🔧 修复:')
        for f in d.fixes:
            print(f'  - {f}')

    print(f'\n评分: {d.summary()}')
    if d.errors:
        print(f'❌ 错误({len(d.errors)}):')
        for e in d.errors:
            print(f'  - {e}')

    return d, sess

# ============================================================
# E2E全链路测试
# ============================================================
def e2e_test():
    print(f'\n{"="*60}')
    print('WU 全链路E2E测试')
    print(f'{"="*60}')

    results = []
    total = 0
    passed = 0

    def check(name, fn):
        nonlocal total, passed
        total += 1
        try:
            ok, detail = fn()
            status = '✅' if ok else '❌'
            if ok:
                passed += 1
            results.append((status, name, detail))
            print(f'  {status} {name}: {detail}')
        except Exception as e:
            results.append(('❌', name, str(e)))
            print(f'  ❌ {name}: {e}')

    # T1: hosts
    def t_hosts():
        content = open(HOSTS_FILE, encoding='utf-8').read()
        for dom in MITM_DOMAINS:
            if f'{WU_MITM_IP} {dom}' not in content:
                return False, f'{dom} 缺失'
        return True, f'{len(MITM_DOMAINS)}域名OK'
    check('T1-hosts', t_hosts)

    # T2: DNS
    def t_dns():
        for dom in MITM_DOMAINS:
            ip = socket.gethostbyname(dom)
            if ip != WU_MITM_IP:
                return False, f'{dom}→{ip}'
        return True, f'全部→{WU_MITM_IP}'
    check('T2-DNS', t_dns)

    # T3: WU进程
    def t_proc():
        out = subprocess.run(['tasklist', '/fi', 'IMAGENAME eq WindsurfUnlimited.exe', '/fo', 'csv', '/nh'],
                             capture_output=True, text=True, timeout=5, encoding='gbk', errors='replace').stdout
        c = out.count('WindsurfUnlimited')
        return c > 0, f'{c}个进程'
    check('T3-WU进程', t_proc)

    # T4: TCP:443
    def t_tcp():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((WU_MITM_IP, 443))
        s.close()
        return True, 'LISTENING'
    check('T4-TCP:443', t_tcp)

    # T5: TLS
    def t_tls():
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        start = time.time()
        s = ctx.wrap_socket(socket.socket(), server_hostname=MITM_DOMAINS[0])
        s.settimeout(10)
        s.connect((WU_MITM_IP, 443))
        lat = (time.time() - start) * 1000
        ver = s.version()
        s.close()
        return True, f'{ver} {lat:.0f}ms'
    check('T5-TLS握手', t_tls)

    # T6: CA证书
    def t_cert():
        out = subprocess.run(['certutil', '-store', 'Root'], capture_output=True, text=True,
                             timeout=15, encoding='gbk', errors='replace').stdout
        ok = 'MITM CA' in out or 'Local Proxy' in out
        return ok, 'MITM CA已安装' if ok else '未安装'
    check('T6-CA证书', t_cert)

    # T7: WU会话
    def t_session():
        if not WU_SESSION.exists():
            return False, '未登录'
        sess = json.loads(WU_SESSION.read_text())
        exp = datetime.fromtimestamp(sess.get('expires_at', 0))
        remaining = exp - datetime.now()
        if remaining.total_seconds() <= 0:
            return False, '已过期'
        return True, f'{sess.get("card_type_label","?")} {remaining.total_seconds()/3600:.1f}h'
    check('T7-WU会话', t_session)

    # T8: WS配置
    def t_ws_config():
        if not WS_SETTINGS.exists():
            return False, '不存在'
        s = json.loads(WS_SETTINGS.read_text())
        ssl_ok = s.get('http.proxyStrictSSL') == False
        proxy_ok = s.get('http.proxySupport') == 'off'
        return ssl_ok and proxy_ok, f'SSL={not ssl_ok and "true!" or "false"} Proxy={s.get("http.proxySupport","?")}'
    check('T8-WS配置', t_ws_config)

    # T9: gRPC流量
    def t_grpc():
        out = subprocess.run(
            'netstat -ano | findstr "127.65.43.21:443" | findstr "ESTABLISHED"',
            shell=True, capture_output=True, text=True, timeout=5, encoding='gbk', errors='replace'
        ).stdout
        conns = [l for l in out.strip().split('\n') if l.strip() and 'ESTABLISHED' in l]
        return len(conns) >= 2, f'{len(conns)}条ESTABLISHED'
    check('T9-gRPC流量', t_grpc)

    # T10: Windsurf进程
    def t_ws_proc():
        out = subprocess.run(['tasklist', '/fi', 'IMAGENAME eq Windsurf.exe', '/fo', 'csv', '/nh'],
                             capture_output=True, text=True, timeout=5, encoding='gbk', errors='replace').stdout
        c = out.count('Windsurf.exe')
        return c > 0, f'{c}个进程'
    check('T10-Windsurf', t_ws_proc)

    print(f'\n{"="*60}')
    print(f'E2E结果: {passed}/{total} PASS ({passed/max(total,1)*100:.0f}%)')
    return passed, total

# ============================================================
# Daemon模式
# ============================================================
def daemon_mode():
    print(f'\n🔄 WU Guardian daemon启动 (120s间隔, Ctrl+C退出)')
    cycle = 0
    try:
        while True:
            cycle += 1
            print(f'\n--- 巡检#{cycle} {datetime.now().strftime("%H:%M:%S")} ---')
            d = Diag()
            hosts_ok = check_hosts(d, fix=True)
            cert_ok = check_ca_cert(d, fix=True)
            proc_ok = check_wu_process(d, fix=True)
            listen_ok = check_443_listen(d, fix=True)

            issues = []
            if not hosts_ok: issues.append('hosts')
            if not cert_ok: issues.append('cert')
            if not proc_ok: issues.append('proc')
            if not listen_ok: issues.append('listen')

            if issues:
                print(f'  ⚠️ 修复: {", ".join(issues)}')
            else:
                print(f'  ✅ 全部正常 ({d.summary()})')

            if d.fixes:
                for f in d.fixes:
                    print(f'  🔧 {f}')

            time.sleep(120)
    except KeyboardInterrupt:
        print('\n🛑 Guardian已停止')

# ============================================================
# Main
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description='WU Guardian v1.0')
    parser.add_argument('--fix', action='store_true', help='诊断+修复所有问题')
    parser.add_argument('--daemon', action='store_true', help='持续守护模式')
    parser.add_argument('--e2e', action='store_true', help='全链路E2E测试')
    parser.add_argument('--credits', action='store_true', help='积分查询')
    args = parser.parse_args()

    if args.daemon:
        # First fix everything, then daemon
        full_diag(fix=True)
        daemon_mode()
        return 0

    if args.e2e:
        passed, total = e2e_test()
        return 0 if passed == total else 1

    d, sess = full_diag(fix=args.fix)

    if args.credits and sess:
        print(f'\n📊 积分查询...')
        data = query_credits(sess)
        if data:
            used = data.get('total_credits_used', 0)
            limit = data.get('credit_limit', 0)
            print(f'  已用: {used}/{limit}')
            print(f'  剩余: {limit - used}')
        else:
            print('  查询失败(可能需要WU代理运行)')

    return 0 if not d.errors else 1


if __name__ == '__main__':
    sys.exit(main())
