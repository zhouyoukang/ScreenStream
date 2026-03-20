#!/usr/bin/env python3
"""
Windsurf 账号管理中枢 v3.0
===========================
HTTP API服务器 + Dashboard，基于switch_v2.py核心引擎。
端口: 9876

API:
  GET  /                    Dashboard页面
  GET  /api/health          健康检查
  GET  /api/status          全景状态(池+认证+计划+VIP)
  GET  /api/accounts        账号列表
  GET  /api/auth            认证详情(含指纹)
  GET  /api/history         切换历史
  GET  /api/backups         备份列表
  POST /api/switch          切换账号 {email?}
  POST /api/dry-run         模拟切换 {email?}
  POST /api/cooldown        标记冷却 {email, minutes?}
  POST /api/add             添加账号 {email, password, notes?}
  POST /api/remove          删除账号 {email}
  POST /api/update          更新状态 {email, status?, notes?}
  POST /api/reset-fp        重置指纹
  POST /api/clear-auth      清除认证 {deep?}
  POST /api/backup          备份认证 {label?}
  POST /api/restore         恢复认证 {file}
  POST /api/verify          验证认证
  POST /api/expire-fix      修复过期冷却
"""

import sys, json, os, time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from datetime import timedelta

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
import switch_v2 as engine

PORT = 9876
DASHBOARD = SCRIPT_DIR / 'pool_dashboard.html'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._cors()
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, path):
        if not path.exists():
            self.send_error(404); return
        body = path.read_text('utf-8').encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(length)) if length > 0 else {}

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/', '/dashboard'):
            self._html(DASHBOARD)
        elif path == '/api/health':
            self._json({'status': 'ok', 'version': '3.0', 'port': PORT})
        elif path == '/api/status':
            self._json(self._full_status())
        elif path == '/api/accounts':
            self._json(self._accounts_list())
        elif path == '/api/auth':
            self._json(self._auth_info())
        elif path == '/api/history':
            pool = engine.load_pool()
            self._json(pool.get('history', [])[-50:])
        elif path == '/api/backups':
            self._json(self._list_backups())
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._body()
        if path == '/api/switch':
            self._json(self._do_switch(body))
        elif path == '/api/dry-run':
            self._json(self._do_dry_run(body))
        elif path == '/api/cooldown':
            self._json(self._do_cooldown(body))
        elif path == '/api/add':
            self._json(self._do_add(body))
        elif path == '/api/remove':
            self._json(self._do_remove(body))
        elif path == '/api/update':
            self._json(self._do_update(body))
        elif path == '/api/reset-fp':
            fp, msg = engine.reset_fingerprint()
            self._json({'ok': fp is not None, 'message': msg})
        elif path == '/api/clear-auth':
            cleared = engine.clear_auth(deep=body.get('deep', False))
            self._json({'ok': True, 'cleared': cleared})
        elif path == '/api/backup':
            bp = engine.backup_auth(label=body.get('label', engine.get_current_user() or 'manual'))
            self._json({'ok': True, 'file': bp.name})
        elif path == '/api/restore':
            ok, msg = engine.restore_auth(body.get('file', ''))
            self._json({'ok': ok, 'message': msg})
        elif path == '/api/verify':
            self._json(self._verify())
        elif path == '/api/expire-fix':
            pool = engine.load_pool()
            fixed = engine.expire_fix(pool)
            self._json({'ok': True, 'fixed': fixed})
        else:
            self.send_error(404)

    # === Data assemblers ===

    def _full_status(self):
        pool = engine.load_pool()
        user = engine.get_current_user()
        auth = engine.get_auth_info()
        plan = engine.get_plan_info()
        vip = engine.get_vip_info()
        running = engine.is_windsurf_running()
        accounts = pool.get('accounts', [])
        available = sum(1 for a in accounts
                        if not engine.is_cooling(a)
                        and a.get('status') not in ('disabled', 'terminated'))
        cooling = sum(1 for a in accounts
                      if engine.is_cooling(a) and engine.cooldown_remaining(a) > 0)
        terminated = sum(1 for a in accounts
                         if a.get('status') in ('disabled', 'terminated'))
        return {
            'windsurf_running': running,
            'current_user': user,
            'auth': auth,
            'plan': plan,
            'vip': {'active': vip is not None,
                    'id': vip.get('user_identifier', '')[:30] if vip else None},
            'pool': {
                'total': len(accounts), 'available': available,
                'cooling': cooling, 'terminated': terminated,
                'current': pool.get('current'),
            },
        }

    def _accounts_list(self):
        pool = engine.load_pool()
        result = []
        for a in pool.get('accounts', []):
            is_cool = engine.is_cooling(a) and engine.cooldown_remaining(a) > 0
            result.append({
                'email': a['email'],
                'password': a.get('password', ''),
                'plan': a.get('plan', 'unknown'),
                'status': 'cooling' if is_cool else a.get('status', 'untested'),
                'cooldown_min': round(engine.cooldown_remaining(a)) if is_cool else 0,
                'last_used': a.get('last_used'),
                'messages_used': a.get('messages_used', 0),
                'notes': a.get('notes', ''),
                'is_current': a['email'] == pool.get('current'),
            })
        return result

    def _auth_info(self):
        user = engine.get_current_user()
        auth = engine.get_auth_info()
        plan = engine.get_plan_info()
        vip = engine.get_vip_info()
        fp = {}
        if engine.WS_STORAGE.exists():
            try:
                data = json.loads(engine.WS_STORAGE.read_text('utf-8'))
                for k in ['telemetry.machineId', 'telemetry.macMachineId',
                           'telemetry.devDeviceId', 'telemetry.sqmId',
                           'storage.serviceMachineId']:
                    v = data.get(k, '')
                    fp[k] = (v[:20] + '...') if v else '<not set>'
            except:
                pass
        return {'user': user, 'auth': auth, 'plan': plan, 'vip': vip, 'fingerprint': fp}

    def _list_backups(self):
        if not engine.BACKUP_DIR.exists():
            return []
        backups = []
        for f in sorted(engine.BACKUP_DIR.glob('auth_*.json'), reverse=True):
            try:
                d = json.loads(f.read_text('utf-8'))
                backups.append({'file': f.name, 'timestamp': d.get('timestamp', ''),
                                'label': d.get('label', ''), 'user': d.get('user', ''),
                                'size': f.stat().st_size})
            except:
                backups.append({'file': f.name, 'timestamp': '', 'label': '',
                                'user': '', 'size': f.stat().st_size})
        return backups

    # === Actions ===

    def _do_switch(self, body):
        pool = engine.load_pool()
        email = body.get('email')
        if email:
            target = next((a for a in pool['accounts'] if a['email'] == email), None)
            if not target:
                return {'ok': False, 'error': f'Account {email} not found'}
            if engine.is_cooling(target):
                return {'ok': False, 'error': f'Cooling, {engine.cooldown_remaining(target):.0f}m left'}
            if target.get('status') == 'terminated':
                return {'ok': False, 'error': 'Account terminated'}
        else:
            target = engine.get_next_account(pool)
            if not target:
                return {'ok': False, 'error': 'No available accounts'}

        steps = []
        user = engine.get_current_user()
        bp = engine.backup_auth(label=user or 'auto')
        steps.append(f'Backed up: {bp.name}')

        ok, msg = engine.kill_windsurf()
        steps.append(f'Windsurf: {msg}')

        fp, msg = engine.reset_fingerprint()
        steps.append(f'Fingerprint: {msg}')

        cleared = engine.clear_auth(deep=False)
        steps.append(f'Auth cleared: {cleared} keys')

        old_email = pool.get('current')
        if old_email and old_email != target['email']:
            for acc in pool['accounts']:
                if acc['email'] == old_email and acc.get('status') == 'active':
                    acc['cooldown_until'] = (engine.now_utc() + timedelta(hours=2)).isoformat()
                    acc['status'] = 'cooling'

        target['last_used'] = engine.now_utc().isoformat()
        target['status'] = 'active'
        pool['current'] = target['email']
        pool.setdefault('history', []).append({
            'action': 'switch', 'email': target['email'],
            'from': old_email, 'timestamp': engine.now_utc().isoformat(),
        })
        if len(pool.get('history', [])) > 200:
            pool['history'] = pool['history'][-200:]
        engine.save_pool(pool)
        steps.append('Pool updated')

        return {
            'ok': True, 'target': target['email'],
            'password': target['password'], 'steps': steps,
            'message': f"Switched to {target['email']}. Launch Windsurf and login.",
        }

    def _do_dry_run(self, body):
        pool = engine.load_pool()
        email = body.get('email')
        if email:
            target = next((a for a in pool['accounts'] if a['email'] == email), None)
            if not target:
                return {'ok': False, 'error': 'Not found'}
        else:
            target = engine.get_next_account(pool)
            if not target:
                return {'ok': False, 'error': 'No available accounts'}
        return {
            'ok': True, 'target': target['email'],
            'password': target['password'], 'dry_run': True,
            'message': f'Would switch to {target["email"]}',
        }

    def _do_cooldown(self, body):
        pool = engine.load_pool()
        email, mins = body.get('email', ''), body.get('minutes', 120)
        for acc in pool['accounts']:
            if acc['email'] == email:
                acc['cooldown_until'] = (engine.now_utc() + timedelta(minutes=mins)).isoformat()
                acc['status'] = 'cooling'
                engine.save_pool(pool)
                return {'ok': True}
        return {'ok': False, 'error': 'Not found'}

    def _do_add(self, body):
        pool = engine.load_pool()
        email, pwd = body.get('email', ''), body.get('password', '')
        if not email or not pwd:
            return {'ok': False, 'error': 'email and password required'}
        if any(a['email'] == email for a in pool['accounts']):
            return {'ok': False, 'error': 'Already exists'}
        pool['accounts'].append({
            'email': email, 'password': pwd, 'plan': 'unknown',
            'status': 'untested', 'cooldown_until': None,
            'last_used': None, 'last_tested': None,
            'messages_used': 0, 'notes': body.get('notes', ''),
        })
        engine.save_pool(pool)
        return {'ok': True}

    def _do_remove(self, body):
        pool = engine.load_pool()
        email = body.get('email', '')
        before = len(pool['accounts'])
        pool['accounts'] = [a for a in pool['accounts'] if a['email'] != email]
        if len(pool['accounts']) < before:
            engine.save_pool(pool)
            return {'ok': True}
        return {'ok': False, 'error': 'Not found'}

    def _do_update(self, body):
        pool = engine.load_pool()
        email = body.get('email', '')
        for acc in pool['accounts']:
            if acc['email'] == email:
                if 'status' in body:
                    acc['status'] = body['status']
                if 'notes' in body:
                    acc['notes'] = body['notes']
                if 'plan' in body:
                    acc['plan'] = body['plan']
                engine.save_pool(pool)
                return {'ok': True}
        return {'ok': False, 'error': 'Not found'}

    def _verify(self):
        checks = []
        if engine.WS_STORAGE.exists():
            data = json.loads(engine.WS_STORAGE.read_text('utf-8'))
            fp_keys = ['telemetry.machineId', 'telemetry.macMachineId',
                        'telemetry.devDeviceId', 'telemetry.sqmId',
                        'storage.serviceMachineId']
            count = sum(1 for k in fp_keys if data.get(k))
            checks.append({'name': 'Fingerprint', 'ok': count >= 3,
                           'detail': f'{count}/5 keys set'})
        else:
            checks.append({'name': 'Fingerprint', 'ok': False,
                           'detail': 'storage.json missing'})
        auth = engine.get_auth_info()
        checks.append({'name': 'Auth', 'ok': auth is not None,
                        'detail': auth['api_key'] if auth else 'Not authenticated'})
        plan = engine.get_plan_info()
        checks.append({'name': 'Plan', 'ok': plan is not None,
                        'detail': f"{plan['plan']} {plan['messages_remaining']:,} remaining"
                        if plan else 'No plan'})
        vip = engine.get_vip_info()
        checks.append({'name': 'VIP', 'ok': vip is not None,
                        'detail': (vip.get('user_identifier', '')[:25] + '...')
                        if vip else 'No VIP'})
        user = engine.get_current_user()
        checks.append({'name': 'User', 'ok': user is not None,
                        'detail': user or 'Not set'})
        checks.append({'name': 'Storage writable', 'ok': os.access(str(engine.WS_STORAGE), os.W_OK),
                        'detail': str(engine.WS_STORAGE)})
        checks.append({'name': 'DB writable', 'ok': os.access(str(engine.WS_STATE_DB), os.W_OK),
                        'detail': str(engine.WS_STATE_DB)})
        return {'checks': checks,
                'passed': sum(1 for c in checks if c['ok']),
                'total': len(checks)}


def main():
    print(f'\n  Windsurf Account Hub v3.0')
    print(f'  Dashboard: http://localhost:{PORT}/')
    print(f'  API:       http://localhost:{PORT}/api/status')
    print(f'  Press Ctrl+C to stop\n')
    server = HTTPServer(('127.0.0.1', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  Stopped.')
        server.server_close()


if __name__ == '__main__':
    main()
