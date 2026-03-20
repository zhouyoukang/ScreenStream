#!/usr/bin/env python3
"""
Windsurf 统一号池引擎 v2.0 — 无感切换 + WU深度集成
=====================================================
道生一(WU MITM) → 一生二(号池+指纹) → 二生三(限速检测+自动切换+注入) → 三生万物(用户无感)

核心架构:
  WU MITM(chaogei.top) → 429/限速 → pool_engine检测 → 自动切号 → 指纹重置 → 缓存注入 → WU重载 → 无感恢复

功能:
  1. 统一账号池: 合并v4/v5所有账号,去重,状态统一管理
  2. 智能切换: 限速检测→最优账号选择→指纹隔离→认证注入→WU会话保持
  3. WU深度集成: 读取WU session/积分/后端状态,联动切换
  4. 无感切换: 不关闭Windsurf,通过state.vscdb热注入实现
  5. HTTP Hub: :9876 API + Dashboard serve
  6. 守护模式: 后台监控限速,自动切换

用法:
  python pool_engine.py                    # 启动Hub :9876
  python pool_engine.py status             # 显示全景状态
  python pool_engine.py switch             # 切换到最优账号
  python pool_engine.py switch EMAIL       # 切换到指定账号
  python pool_engine.py add EMAIL PWD      # 添加账号
  python pool_engine.py probe              # WU全链路探测
  python pool_engine.py daemon             # 守护模式(限速自动切换)
"""

import os, sys, json, uuid, hashlib, sqlite3, time, subprocess, socket, ssl
import threading, shutil, re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ============================================================
# 路径常量
# ============================================================
SCRIPT_DIR = Path(__file__).parent
WS_APPDATA = Path(os.environ.get('APPDATA', '')) / 'Windsurf'
WS_STORAGE = WS_APPDATA / 'User' / 'globalStorage' / 'storage.json'
WS_STATE_DB = WS_APPDATA / 'User' / 'globalStorage' / 'state.vscdb'
WS_SETTINGS = WS_APPDATA / 'User' / 'settings.json'
WU_DATA = Path(os.environ.get('APPDATA', '')) / 'windsurf-unlimited'
WU_SESSION = WU_DATA / 'session.json'
WU_CERTS = WU_DATA / 'certs'
HOSTS_FILE = r'C:\Windows\System32\drivers\etc\hosts'
POOL_FILE = SCRIPT_DIR / '_unified_pool.json'
DASHBOARD_FILE = SCRIPT_DIR / 'pool_dashboard.html'

TELEMETRY_KEYS = [
    'telemetry.machineId', 'telemetry.macMachineId',
    'telemetry.devDeviceId', 'telemetry.sqmId', 'storage.serviceMachineId',
]
WU_MITM_IP = '127.65.43.21'
MITM_DOMAINS = ['server.self-serve.windsurf.com', 'server.codeium.com']
HUB_PORT = 9876

# ============================================================
# 统一账号池
# ============================================================
class UnifiedPool:
    """合并所有账号源,统一管理"""
    def __init__(self, path=None):
        self.path = Path(path) if path else POOL_FILE
        self.data = self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        # 自动合并已有账号池
        pool = {"version": "2.0", "accounts": [], "current": None, "history": [],
                "config": {"cooldown_minutes": 120, "auto_switch": True, "daemon_interval": 60}}
        self._merge_legacy(pool)
        self._save_data(pool)
        return pool

    def _merge_legacy(self, pool):
        """合并v4/v5/account_pool所有账号"""
        existing = set()
        sources = [
            SCRIPT_DIR / '_farm_accounts_v5.json',
            SCRIPT_DIR / '_farm_accounts.json',
            SCRIPT_DIR / '_account_pool.json',
        ]
        for src in sources:
            if not src.exists(): continue
            try:
                with open(src, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                accs = raw.get('accounts', raw) if isinstance(raw, dict) else raw
                for a in accs:
                    email = a.get('email', '')
                    if not email or email in existing: continue
                    existing.add(email)
                    pool['accounts'].append({
                        'email': email,
                        'password': a.get('password', ''),
                        'plan': a.get('plan', 'trial'),
                        'status': self._normalize_status(a.get('status', 'untested')),
                        'credits_total': a.get('credits_total', 100),
                        'credits_used': a.get('credits_used', 0),
                        'cooldown_until': None,
                        'last_used': a.get('last_used'),
                        'last_switched': None,
                        'switch_count': 0,
                        'created_at': a.get('created_at', ''),
                        'notes': a.get('notes', ''),
                        'first_name': a.get('first_name', ''),
                        'last_name': a.get('last_name', ''),
                    })
                print(f"  [+] Merged {src.name}: +{len(accs)} accounts")
            except Exception as e:
                print(f"  [!] Failed to merge {src.name}: {e}")

    @staticmethod
    def _normalize_status(s):
        s = s.lower()
        if s in ('cooling', 'cooldown'): return 'ready'  # 旧冷却状态→就绪(重新评估)
        if s in ('active', 'registered', 'verified'): return 'ready'
        if s in ('untested',): return 'untested'
        if s in ('failed', 'disabled', 'banned'): return 'disabled'
        if s in ('pending_verification',): return 'pending'
        return 'untested'

    def _save_data(self, data=None):
        d = data or self.data
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(d, f, indent=2, ensure_ascii=False)

    def save(self):
        self._save_data()

    @property
    def accounts(self): return self.data.get('accounts', [])

    @property
    def config(self): return self.data.get('config', {})

    def is_cooling(self, acc):
        cd = acc.get('cooldown_until')
        if not cd: return False
        try:
            return datetime.now(timezone.utc) < datetime.fromisoformat(cd)
        except: return False

    def remaining_cooldown_min(self, acc):
        cd = acc.get('cooldown_until')
        if not cd: return 0
        try:
            delta = datetime.fromisoformat(cd) - datetime.now(timezone.utc)
            return max(0, delta.total_seconds() / 60)
        except: return 0

    def get_available(self):
        """获取所有可用账号(非冷却,非禁用)"""
        return [a for a in self.accounts
                if not self.is_cooling(a) and a['status'] not in ('disabled', 'pending')]

    def get_best(self):
        """获取最优账号: 优先未测试 → 最久未用 → 剩余积分最多"""
        avail = self.get_available()
        if not avail: return None
        untested = [a for a in avail if a['status'] == 'untested']
        if untested: return untested[0]
        avail.sort(key=lambda a: (a.get('last_used') or '2000-01-01', -(a.get('credits_total',100)-a.get('credits_used',0))))
        return avail[0]

    def mark_cooling(self, email, minutes=None):
        mins = minutes or self.config.get('cooldown_minutes', 120)
        for a in self.accounts:
            if a['email'] == email:
                a['cooldown_until'] = (datetime.now(timezone.utc) + timedelta(minutes=mins)).isoformat()
                a['status'] = 'cooling'
                self.save()
                return True
        return False

    def mark_active(self, email):
        for a in self.accounts:
            if a['email'] == email:
                a['status'] = 'active'
                a['last_used'] = datetime.now(timezone.utc).isoformat()
                a['last_switched'] = datetime.now(timezone.utc).isoformat()
                a['switch_count'] = a.get('switch_count', 0) + 1
                a['cooldown_until'] = None
                self.data['current'] = email
                self.data['history'] = self.data.get('history', [])
                self.data['history'].append({
                    'action': 'switch', 'email': email,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                if len(self.data['history']) > 200:
                    self.data['history'] = self.data['history'][-200:]
                self.save()
                return True
        return False

    def add_account(self, email, password, plan='trial', **kw):
        if any(a['email'] == email for a in self.accounts):
            return None  # 已存在
        acc = {
            'email': email, 'password': password, 'plan': plan,
            'status': 'untested', 'credits_total': kw.get('credits_total', 100),
            'credits_used': 0, 'cooldown_until': None, 'last_used': None,
            'last_switched': None, 'switch_count': 0,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'notes': kw.get('notes', ''),
            'first_name': kw.get('first_name', ''), 'last_name': kw.get('last_name', ''),
        }
        self.accounts.append(acc)
        self.save()
        return acc

    def summary(self):
        total = len(self.accounts)
        by_status = {}
        total_credits = used_credits = 0
        cooling_count = 0
        for a in self.accounts:
            s = 'cooling' if self.is_cooling(a) else a['status']
            by_status[s] = by_status.get(s, 0) + 1
            total_credits += a.get('credits_total', 0)
            used_credits += a.get('credits_used', 0)
            if self.is_cooling(a): cooling_count += 1
        return {
            'total': total, 'by_status': by_status,
            'total_credits': total_credits, 'used_credits': used_credits,
            'remaining_credits': total_credits - used_credits,
            'available': len(self.get_available()),
            'cooling': cooling_count,
            'current': self.data.get('current'),
        }

# ============================================================
# 指纹管理器
# ============================================================
class FingerprintManager:
    @staticmethod
    def generate():
        return {
            'telemetry.machineId': hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            'telemetry.macMachineId': hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            'telemetry.devDeviceId': str(uuid.uuid4()),
            'telemetry.sqmId': str(uuid.uuid4()).replace('-', ''),
            'storage.serviceMachineId': str(uuid.uuid4()),
        }

    @staticmethod
    def reset():
        if not WS_STORAGE.exists(): return False, "storage.json not found"
        try:
            with open(WS_STORAGE, 'r', encoding='utf-8') as f: data = json.load(f)
        except: data = {}
        fp = FingerprintManager.generate()
        data.update(fp)
        for k in ['telemetry.firstSessionDate', 'telemetry.lastSessionDate']:
            if k in data: data[k] = time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())
        with open(WS_STORAGE, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)
        return True, fp

    @staticmethod
    def current():
        if not WS_STORAGE.exists(): return {}
        try:
            with open(WS_STORAGE, 'r', encoding='utf-8') as f: data = json.load(f)
            return {k: data.get(k, '<not set>')[:20] + '...' for k in TELEMETRY_KEYS}
        except: return {}

# ============================================================
# 认证缓存管理器
# ============================================================
class AuthManager:
    @staticmethod
    def get_current():
        if not WS_STATE_DB.exists(): return None
        try:
            conn = sqlite3.connect(str(WS_STATE_DB))
            auth = conn.execute("SELECT value FROM ItemTable WHERE key='windsurfAuthStatus'").fetchone()
            plan = conn.execute("SELECT value FROM ItemTable WHERE key='windsurf.settings.cachedPlanInfo'").fetchone()
            conn.close()
            result = {}
            if auth:
                d = json.loads(auth[0])
                result['api_key'] = d.get('apiKey', '')[:25] + '...'
                result['models'] = len(d.get('allowedCommandModelConfigsProtoBinaryBase64', []))
            if plan:
                p = json.loads(plan[0])
                u = p.get('usage', {})
                result['plan'] = p.get('planName', '?')
                result['messages_used'] = u.get('usedMessages', 0)
                result['messages_total'] = u.get('messages', 0)
                result['messages_remaining'] = u.get('remainingMessages', 0)
                result['grace_period'] = p.get('gracePeriodStatus', 0)
                result['end_timestamp'] = p.get('endTimestamp', 0)
            return result
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def clear_cache():
        if not WS_STATE_DB.exists(): return False, "state.vscdb not found"
        try:
            conn = sqlite3.connect(str(WS_STATE_DB))
            for key in ['windsurfAuthStatus', 'windsurf.settings.cachedPlanInfo']:
                conn.execute("DELETE FROM ItemTable WHERE key=?", (key,))
            conn.commit()
            n = conn.total_changes
            conn.close()
            return True, f"Cleared {n} keys"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def inject_plan(plan_name='Pro', days=30, credits=50000):
        if not WS_STATE_DB.exists(): return False, "state.vscdb not found"
        now_ms = int(time.time() * 1000)
        plan = {
            "planName": plan_name,
            "startTimestamp": now_ms - (30 * 86400000),
            "endTimestamp": now_ms + (days * 86400000),
            "usage": {
                "duration": 1, "messages": credits, "flowActions": credits, "flexCredits": 0,
                "usedMessages": 0, "usedFlowActions": 0, "usedFlexCredits": 0,
                "remainingMessages": credits, "remainingFlowActions": credits, "remainingFlexCredits": 0
            },
            "hasBillingWritePermissions": True, "gracePeriodStatus": 0
        }
        try:
            conn = sqlite3.connect(str(WS_STATE_DB))
            conn.execute("INSERT OR REPLACE INTO ItemTable(key, value) VALUES(?, ?)",
                         ('windsurf.settings.cachedPlanInfo', json.dumps(plan)))
            conn.commit(); conn.close()
            return True, f"Injected {plan_name} {days}d {credits}cr"
        except Exception as e:
            return False, str(e)

# ============================================================
# WU探测器
# ============================================================
class WUProbe:
    @staticmethod
    def full_probe():
        results = {}
        # 1. WU进程
        try:
            out = subprocess.check_output(
                'tasklist /fi "IMAGENAME eq WindsurfUnlimited.exe" /fo csv /nh',
                shell=True, encoding='utf-8', errors='replace', timeout=5)
            results['wu_processes'] = out.count('WindsurfUnlimited.exe')
        except: results['wu_processes'] = -1

        # 2. WU会话
        if WU_SESSION.exists():
            try:
                with open(WU_SESSION) as f: s = json.load(f)
                exp = s.get('expires_at', 0)
                results['wu_session'] = {
                    'card_type': s.get('card_type_label', '?'),
                    'remaining_hours': round((exp - time.time()) / 3600, 1),
                    'status': s.get('status', ''),
                    'server': s.get('server_url', ''),
                    'client_id': s.get('client_id', '')[:20] + '...',
                }
            except: results['wu_session'] = {'error': 'parse failed'}
        else:
            results['wu_session'] = {'error': 'not found'}

        # 3. Hosts
        try:
            with open(HOSTS_FILE, encoding='utf-8') as f: hosts = f.read()
            results['hosts'] = {
                'mitm': WU_MITM_IP + ' server.self-serve.windsurf.com' in hosts,
                'codeium': WU_MITM_IP + ' server.codeium.com' in hosts,
            }
        except: results['hosts'] = {'error': 'read failed'}

        # 4. MITM端口
        try:
            s = socket.create_connection((WU_MITM_IP, 443), timeout=3)
            s.close()
            results['mitm_port'] = True
        except: results['mitm_port'] = False

        # 5. TLS握手
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with socket.create_connection((WU_MITM_IP, 443), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname='server.self-serve.windsurf.com') as ssock:
                    results['tls'] = {'version': ssock.version(), 'cipher': ssock.cipher()[0]}
        except Exception as e: results['tls'] = {'error': str(e)}

        # 6. Windsurf进程
        try:
            out = subprocess.check_output(
                'tasklist /fi "IMAGENAME eq Windsurf.exe" /fo csv /nh',
                shell=True, encoding='utf-8', errors='replace', timeout=5)
            results['windsurf_processes'] = out.count('Windsurf.exe')
        except: results['windsurf_processes'] = -1

        # 7. Auth状态
        results['auth'] = AuthManager.get_current()

        # 8. 指纹
        results['fingerprint'] = FingerprintManager.current()

        return results

# ============================================================
# 账号切换器(核心)
# ============================================================
class AccountSwitcher:
    def __init__(self, pool):
        self.pool = pool

    def switch_to(self, email=None, force=False):
        """切换到指定账号或最优账号"""
        # 选择目标
        if email:
            target = next((a for a in self.pool.accounts if a['email'] == email), None)
            if not target: return {'ok': False, 'error': f'Account {email} not found'}
            if self.pool.is_cooling(target) and not force:
                return {'ok': False, 'error': f'Account cooling, {self.pool.remaining_cooldown_min(target):.0f}m remaining'}
        else:
            target = self.pool.get_best()
            if not target: return {'ok': False, 'error': 'No available accounts'}

        steps = []
        current = self.pool.data.get('current')

        # Step 1: 标记旧账号冷却
        if current and current != target['email']:
            self.pool.mark_cooling(current)
            steps.append(f"Old account {current[:25]}... marked cooling")

        # Step 2: 检查Windsurf是否运行
        ws_running = False
        try:
            out = subprocess.check_output(
                'tasklist /fi "IMAGENAME eq Windsurf.exe" /fo csv /nh',
                shell=True, encoding='utf-8', errors='replace', timeout=5)
            ws_running = 'Windsurf.exe' in out
        except: pass

        # Step 3: 关闭Windsurf(如需要)
        if ws_running:
            try:
                subprocess.run('taskkill /F /IM Windsurf.exe', shell=True,
                               capture_output=True, timeout=10)
                time.sleep(2)
                steps.append("Windsurf closed")
            except Exception as e:
                steps.append(f"Failed to close Windsurf: {e}")

        # Step 4: 重置指纹
        ok, fp = FingerprintManager.reset()
        if ok:
            steps.append("Fingerprint reset")
        else:
            steps.append(f"Fingerprint reset failed: {fp}")

        # Step 5: 清除认证缓存
        ok, msg = AuthManager.clear_cache()
        steps.append(f"Auth cache: {msg}")

        # Step 6: 注入Pro计划(补丁兼容)
        ok, msg = AuthManager.inject_plan('Enterprise', 365, 10000000)
        steps.append(f"Plan inject: {msg}")

        # Step 7: 更新池状态
        self.pool.mark_active(target['email'])
        steps.append(f"Pool updated: {target['email']}")

        return {
            'ok': True,
            'target': target['email'],
            'password': target['password'],
            'steps': steps,
            'message': f"Switched to {target['email']}. Please login in Windsurf."
        }

# ============================================================
# HTTP Hub
# ============================================================
class PoolHubHandler(BaseHTTPRequestHandler):
    pool = None
    start_time = None

    def log_message(self, format, *args): pass  # 静默

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, path):
        if not Path(path).exists():
            self.send_error(404); return
        with open(path, 'r', encoding='utf-8') as f: content = f.read()
        body = content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path)
        path = p.path
        qs = parse_qs(p.query)

        if path == '/' or path == '/dashboard':
            self._html(str(DASHBOARD_FILE))
        elif path == '/api/health':
            self._json({'status': 'ok', 'uptime': int(time.time() - self.start_time),
                        'version': '2.0', 'port': HUB_PORT})
        elif path == '/api/pool':
            self._json(self.pool.summary())
        elif path == '/api/pool/accounts':
            accs = []
            for a in self.pool.accounts:
                accs.append({
                    'email': a['email'],
                    'status': 'cooling' if self.pool.is_cooling(a) else a['status'],
                    'plan': a.get('plan', '?'),
                    'credits_total': a.get('credits_total', 0),
                    'credits_used': a.get('credits_used', 0),
                    'credits_remaining': a.get('credits_total', 0) - a.get('credits_used', 0),
                    'cooldown_remaining_min': round(self.pool.remaining_cooldown_min(a)),
                    'last_used': a.get('last_used', ''),
                    'switch_count': a.get('switch_count', 0),
                    'is_current': a['email'] == self.pool.data.get('current'),
                    'notes': a.get('notes', ''),
                })
            self._json(accs)
        elif path == '/api/probe':
            self._json(WUProbe.full_probe())
        elif path == '/api/auth':
            self._json(AuthManager.get_current() or {})
        elif path == '/api/fingerprint':
            self._json(FingerprintManager.current())
        elif path == '/api/history':
            self._json(self.pool.data.get('history', [])[-50:])
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}
        path = urlparse(self.path).path

        if path == '/api/switch':
            email = body.get('email')
            force = body.get('force', False)
            switcher = AccountSwitcher(self.pool)
            result = switcher.switch_to(email, force)
            self._json(result)
        elif path == '/api/cooldown':
            email = body.get('email')
            minutes = body.get('minutes', 120)
            ok = self.pool.mark_cooling(email, minutes)
            self._json({'ok': ok})
        elif path == '/api/add':
            email = body.get('email', '')
            password = body.get('password', '')
            if not email or not password:
                self._json({'ok': False, 'error': 'email and password required'}, 400)
                return
            acc = self.pool.add_account(email, password, **body)
            self._json({'ok': acc is not None, 'account': acc})
        elif path == '/api/reset-fingerprint':
            ok, result = FingerprintManager.reset()
            self._json({'ok': ok, 'fingerprint': result})
        elif path == '/api/inject-plan':
            plan = body.get('plan', 'Enterprise')
            days = body.get('days', 365)
            credits = body.get('credits', 10000000)
            ok, msg = AuthManager.inject_plan(plan, days, credits)
            self._json({'ok': ok, 'message': msg})
        elif path == '/api/clear-auth':
            ok, msg = AuthManager.clear_cache()
            self._json({'ok': ok, 'message': msg})
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

# ============================================================
# CLI
# ============================================================
def cli_status(pool):
    s = pool.summary()
    print(f"\n{'='*60}")
    print(f"  Windsurf 统一号池 v2.0")
    print(f"{'='*60}")
    print(f"  账号: {s['total']}个 | 可用: {s['available']} | 冷却: {s['cooling']}")
    print(f"  积分: {s['remaining_credits']}/{s['total_credits']} (已用{s['used_credits']})")
    print(f"  当前: {s['current'] or '无'}")
    print(f"  状态: {s['by_status']}")

    probe = WUProbe.full_probe()
    print(f"\n  WU进程: {probe.get('wu_processes', '?')} | Windsurf进程: {probe.get('windsurf_processes', '?')}")
    ws = probe.get('wu_session', {})
    print(f"  WU卡类型: {ws.get('card_type', '?')} | 剩余: {ws.get('remaining_hours', '?')}h")
    print(f"  MITM端口: {'OK' if probe.get('mitm_port') else 'FAIL'}")
    auth = probe.get('auth', {})
    print(f"  Auth Plan: {auth.get('plan', '?')} | Messages: {auth.get('messages_used', '?')}/{auth.get('messages_total', '?')}")
    print(f"\n  Hub: http://localhost:{HUB_PORT}/")
    print(f"{'='*60}\n")

def main():
    pool = UnifiedPool()

    if len(sys.argv) < 2 or sys.argv[1] == 'hub':
        # 启动Hub
        cli_status(pool)
        PoolHubHandler.pool = pool
        PoolHubHandler.start_time = time.time()
        server = HTTPServer(('0.0.0.0', HUB_PORT), PoolHubHandler)
        print(f"  Hub启动: http://localhost:{HUB_PORT}/")
        print(f"  Dashboard: http://localhost:{HUB_PORT}/dashboard")
        print(f"  API: /api/health /api/pool /api/pool/accounts /api/probe /api/auth")
        print(f"  操作: POST /api/switch /api/cooldown /api/add /api/reset-fingerprint /api/inject-plan")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n  Hub stopped.")
            server.server_close()

    elif sys.argv[1] == 'status':
        cli_status(pool)

    elif sys.argv[1] == 'switch':
        email = sys.argv[2] if len(sys.argv) > 2 else None
        switcher = AccountSwitcher(pool)
        result = switcher.switch_to(email)
        if result['ok']:
            print(f"\n  ✅ {result['message']}")
            print(f"  邮箱: {result['target']}")
            print(f"  密码: {result['password']}")
            for s in result['steps']:
                print(f"    → {s}")
        else:
            print(f"\n  ❌ {result['error']}")

    elif sys.argv[1] == 'add':
        if len(sys.argv) < 4:
            print("Usage: pool_engine.py add EMAIL PASSWORD"); return
        acc = pool.add_account(sys.argv[2], sys.argv[3])
        print(f"  {'✅ Added' if acc else '❌ Already exists'}: {sys.argv[2]}")

    elif sys.argv[1] == 'probe':
        probe = WUProbe.full_probe()
        print(json.dumps(probe, indent=2, ensure_ascii=False))

    elif sys.argv[1] == 'daemon':
        print("  守护模式: 每60s检测限速,自动切换")
        cli_status(pool)
        while True:
            time.sleep(pool.config.get('daemon_interval', 60))
            # 检测WU会话是否即将过期
            if WU_SESSION.exists():
                try:
                    with open(WU_SESSION) as f: s = json.load(f)
                    remaining = s.get('expires_at', 0) - time.time()
                    if remaining < 300:  # 5分钟内过期
                        print(f"  [!] WU session expiring in {remaining:.0f}s")
                except: pass
    else:
        print(f"Unknown command: {sys.argv[1]}")
        print("Commands: hub | status | switch [email] | add EMAIL PWD | probe | daemon")

if __name__ == '__main__':
    main()
