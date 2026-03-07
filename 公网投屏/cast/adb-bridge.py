#!/usr/bin/env python3
"""
ADB Bridge v2.0 - 本地HTTP + 公网WebSocket双模式

用法:
  本地模式: python adb-bridge.py [--port 8085]
  公网模式: python adb-bridge.py --public [--code 123456]

本地模式: HTTP服务器 localhost:8085，setup.html通过fetch调用
公网模式: WebSocket连接 wss://aiotvr.xyz/signal/，任意浏览器通过信令中继控制

公网模式依赖: pip install websocket-client
"""
import subprocess, json, sys, os, time, argparse, shutil, random, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ═══ 配置 ═══
DEFAULT_PORT = 8085
ADB_PATH = None  # 自动检测

def find_adb():
    """自动查找adb.exe路径"""
    # 1. PATH中查找
    adb = shutil.which('adb')
    if adb: return adb
    # 2. 常见路径
    candidates = [
        r'D:\platform-tools\adb.exe',
        r'C:\platform-tools\adb.exe',
        os.path.expanduser(r'~\AppData\Local\Android\Sdk\platform-tools\adb.exe'),
        r'C:\Users\Public\platform-tools\adb.exe',
    ]
    for p in candidates:
        if os.path.exists(p): return p
    return 'adb'  # fallback

def run_adb(*args, timeout=15):
    """执行ADB命令，返回(成功, 输出)"""
    cmd = [ADB_PATH] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          creationflags=0x08000000 if sys.platform == 'win32' else 0)
        output = (r.stdout + r.stderr).strip()
        return r.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, f'超时({timeout}s)'
    except Exception as e:
        return False, str(e)

# ═══ 安全白名单 ═══
ALLOWED_COMMANDS = {
    'devices',           # 列出设备
    'install',           # 安装APK
    'shell',             # shell命令(受限)
    'forward',           # 端口转发
    'connect',           # WiFi ADB连接
    'disconnect',        # 断开连接
    'get-state',         # 获取设备状态
    'version',           # ADB版本
}

ALLOWED_SHELL_COMMANDS = {
    'pm',       # 包管理(grant/list)
    'am',       # Activity管理(start)
    'settings', # 系统设置
    'dumpsys',  # 系统信息
    'getprop',  # 属性
    'input',    # 模拟输入
    'cmd',      # 系统命令
    'wm',       # 窗口管理
    'cat',      # 读文件
    'ls',       # 列目录
}

# 危险命令黑名单
BLOCKED_PATTERNS = ['rm ', 'rm -', 'mkfs', 'format', 'dd ', 'reboot', 'shutdown',
                    'factory', 'wipe', '> /dev', '| su', 'su -c']

def is_safe_command(args):
    """检查命令安全性"""
    if not args: return False, '空命令'
    cmd = args[0]
    if cmd not in ALLOWED_COMMANDS:
        return False, f'不允许的命令: {cmd}'
    if cmd == 'shell' and len(args) > 1:
        shell_cmd = args[1]
        if shell_cmd not in ALLOWED_SHELL_COMMANDS:
            return False, f'不允许的shell命令: {shell_cmd}'
        full = ' '.join(args[1:])
        for pattern in BLOCKED_PATTERNS:
            if pattern in full:
                return False, f'危险命令被阻止: {pattern}'
    return True, 'ok'

# ═══ 预定义操作 ═══
PACKAGE_CANDIDATES = [
    'info.dvkr.screenstream.dev',   # 开发版
    'info.dvkr.screenstream',       # dvkr原版
    'info.nicedoc.screenstream',    # nicedoc版
]
ACTIVITY_MAP = {
    'info.dvkr.screenstream.dev': 'info.dvkr.screenstream.SingleActivity',
    'info.dvkr.screenstream': 'info.dvkr.screenstream.SingleActivity',
    'info.nicedoc.screenstream': '.AppActivity',
}
PACKAGE = None  # 运行时自动检测

def detect_package():
    """自动检测已安装的ScreenStream包名"""
    global PACKAGE
    ok, out = run_adb('shell', 'pm', 'list', 'packages')
    if ok:
        for candidate in PACKAGE_CANDIDATES:
            if f'package:{candidate}' in out:
                PACKAGE = candidate
                return candidate
    PACKAGE = PACKAGE_CANDIDATES[-1]  # 默认fallback
    return None

def get_activity():
    """获取当前PACKAGE对应的Activity全名"""
    pkg = PACKAGE or PACKAGE_CANDIDATES[-1]
    act = ACTIVITY_MAP.get(pkg, '.AppActivity')
    if act.startswith('.'):
        return f'{pkg}/{act}'
    return f'{pkg}/{act}'

def get_preset_actions():
    """返回预定义的配置操作列表"""
    pkg = PACKAGE or PACKAGE_CANDIDATES[-1]
    return {
        'check_device': ['devices'],
        'check_package': ['shell', 'pm', 'list', 'packages', pkg],
        'grant_overlay': ['shell', 'appops', 'set', pkg, 'SYSTEM_ALERT_WINDOW', 'allow'],
        'grant_media_projection': ['shell', 'appops', 'set', pkg, 'PROJECT_MEDIA', 'allow'],
        'disable_battery_optimization': ['shell', 'dumpsys', 'deviceidle', 'whitelist', f'+{pkg}'],
        'check_accessibility': ['shell', 'settings', 'get', 'secure', 'enabled_accessibility_services'],
        'get_device_info': ['shell', 'getprop', 'ro.product.model'],
        'get_android_version': ['shell', 'getprop', 'ro.build.version.release'],
        'get_screen_size': ['shell', 'wm', 'size'],
        'start_app': ['shell', 'am', 'start', '-n', get_activity()],
        'force_stop': ['shell', 'am', 'force-stop', pkg],
        'check_foreground': ['shell', 'dumpsys', 'activity', 'activities'],
    }

# ═══ WebSocket命令处理（公网模式） ═══
def handle_ws_command(msg):
    """处理来自网页控制端的命令，返回结果dict"""
    cmd_type = msg.get('type', '')
    cmd_id = msg.get('id', '')

    if cmd_type == 'adb_command':
        args = msg.get('args', [])
        if isinstance(args, str): args = args.split()
        safe, reason = is_safe_command(args)
        if not safe:
            return {'type': 'adb_result', 'id': cmd_id, 'ok': False, 'error': reason}
        timeout = min(msg.get('timeout', 15), 60)
        ok, out = run_adb(*args, timeout=timeout)
        return {'type': 'adb_result', 'id': cmd_id, 'ok': ok, 'output': out}

    elif cmd_type == 'preset':
        action = msg.get('action', '')
        presets = get_preset_actions()
        if action not in presets:
            return {'type': 'preset_result', 'id': cmd_id, 'ok': False, 'error': f'未知: {action}'}
        ok, out = run_adb(*presets[action])
        return {'type': 'preset_result', 'id': cmd_id, 'ok': ok, 'action': action, 'output': out}

    elif cmd_type == 'get_status':
        ok, out = run_adb('devices')
        lines = [l for l in out.split('\n')[1:] if l.strip() and 'device' in l.split()[1:2]]
        return {'type': 'status_result', 'id': cmd_id, 'ok': True,
                'has_device': len(lines) > 0, 'device_count': len(lines), 'adb_path': ADB_PATH}

    elif cmd_type == 'get_devices':
        ok, out = run_adb('devices', '-l')
        devices = []
        if ok:
            for line in out.split('\n')[1:]:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[1] in ('device', 'unauthorized', 'offline'):
                    dev = {'id': parts[0], 'state': parts[1]}
                    for p in parts[2:]:
                        if ':' in p:
                            k, v = p.split(':', 1)
                            dev[k] = v
                    devices.append(dev)
        return {'type': 'devices_result', 'id': cmd_id, 'ok': ok, 'devices': devices}

    elif cmd_type == 'auto_config':
        return run_auto_config_ws(cmd_id)

    elif cmd_type == 'http_proxy':
        return handle_http_proxy(msg, cmd_id)

    elif cmd_type == 'phone_diag':
        return run_phone_diagnostics(cmd_id)

    elif cmd_type == 'screenshot':
        return handle_screenshot(cmd_id)

    return {'type': 'error', 'id': cmd_id, 'error': f'未知命令: {cmd_type}'}

def run_auto_config_ws(cmd_id):
    """公网模式一键自动配置，返回全部结果"""
    results = []

    # 1: 检查设备
    ok, out = run_adb('devices', '-l')
    if 'device' not in out or out.strip().endswith('attached'):
        return {'type': 'auto_config_result', 'id': cmd_id, 'ok': False,
                'error': '未检测到设备', 'results': results}
    results.append({'step': '设备检测', 'ok': True, 'output': out})

    # 2: 设备信息
    ok, model = run_adb('shell', 'getprop', 'ro.product.model')
    ok2, ver = run_adb('shell', 'getprop', 'ro.build.version.release')
    results.append({'step': '设备信息', 'ok': ok, 'output': f'{model} Android {ver}'})

    # 3: 自动检测已安装的ScreenStream版本
    detected = detect_package()
    pkg = PACKAGE or PACKAGE_CANDIDATES[-1]
    if detected:
        results.append({'step': '应用检测', 'ok': True, 'installed': True,
                        'output': f'已安装 ({detected})'})
    else:
        results.append({'step': '应用检测', 'ok': True, 'installed': False,
                        'output': '未安装'})
        results.append({'step': 'APK安装', 'ok': False, 'output': '未安装，请先在手机安装ScreenStream'})
        return {'type': 'auto_config_result', 'id': cmd_id, 'ok': False,
                'error': '应用未安装', 'results': results}

    # 4: 授予权限（悬浮窗在部分品牌受限，降级为警告）
    ok_overlay, out_overlay = run_adb('shell', 'appops', 'set', pkg, 'SYSTEM_ALERT_WINDOW', 'allow')
    if not ok_overlay and 'SecurityException' in (out_overlay or ''):
        results.append({'step': '权限-悬浮窗', 'ok': True, 'output': '品牌限制，需手动授权（不影响投屏）', 'warn': True})
    else:
        results.append({'step': '权限-悬浮窗', 'ok': ok_overlay, 'output': out_overlay})
    ok_bat, out_bat = run_adb('shell', 'dumpsys', 'deviceidle', 'whitelist', f'+{pkg}')
    results.append({'step': '权限-电池优化白名单', 'ok': ok_bat, 'output': out_bat})

    # 5: 检查无障碍
    ok, out = run_adb('shell', 'settings', 'get', 'secure', 'enabled_accessibility_services')
    acc_ok = ok and 'screenstream' in out.lower()
    results.append({'step': '无障碍服务', 'ok': acc_ok,
                    'output': '已开启' if acc_ok else '未开启（需手动在设置中开启）'})

    # 6: 启动应用
    activity = get_activity()
    ok, out = run_adb('shell', 'am', 'start', '-n', activity)
    results.append({'step': '启动应用', 'ok': ok, 'output': out})

    # 7: 端口转发
    for port in [8080, 8081, 8084]:
        ok, out = run_adb('forward', f'tcp:{port}', f'tcp:{port}')
        results.append({'step': f'端口转发({port})', 'ok': ok, 'output': out or 'ok'})

    all_ok = all(r['ok'] for r in results)
    return {'type': 'auto_config_result', 'id': cmd_id, 'ok': all_ok, 'results': results}

ALLOWED_PROXY_PORTS = [8080, 8081, 8082, 8083, 8084]
ALLOWED_PROXY_PATHS_PREFIX = ['/', '/api/', '/status', '/tap', '/swipe', '/key', '/text',
    '/home', '/back', '/recents', '/volume', '/brightness', '/screenshot',
    '/screen/', '/viewtree', '/findclick', '/findnodes', '/command',
    '/macro/', '/files/', '/apps', '/clipboard', '/foreground', '/deviceinfo',
    '/wake', '/lock', '/notifications', '/intent', '/wait', '/dismiss',
    '/longpress', '/doubletap', '/scroll', '/pinch', '/flashlight', '/rotate',
    '/quicksettings', '/a11y/', '/input/']

def handle_http_proxy(msg, cmd_id):
    """代理HTTP请求到手机本地API，通过WebSocket中继实现远程控制"""
    import urllib.request, urllib.error
    method = msg.get('method', 'GET').upper()
    path = msg.get('path', '/')
    port = msg.get('port', 8084)
    body = msg.get('body', None)
    timeout = min(msg.get('timeout', 10), 30)

    if port not in ALLOWED_PROXY_PORTS:
        return {'type': 'http_proxy_result', 'id': cmd_id, 'ok': False,
                'error': f'端口 {port} 不在白名单中 {ALLOWED_PROXY_PORTS}'}

    path_ok = any(path == p or path.startswith(p) for p in ALLOWED_PROXY_PATHS_PREFIX)
    if not path_ok:
        return {'type': 'http_proxy_result', 'id': cmd_id, 'ok': False,
                'error': f'路径 {path} 不在白名单中'}

    url = f'http://127.0.0.1:{port}{path}'
    try:
        data = None
        if body is not None:
            data = json.dumps(body).encode('utf-8') if isinstance(body, dict) else str(body).encode('utf-8')
        req = urllib.request.Request(url, data=data, method=method)
        if data:
            req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode('utf-8', errors='replace')
            try:
                parsed = json.loads(content)
            except:
                parsed = None
            return {'type': 'http_proxy_result', 'id': cmd_id, 'ok': True,
                    'status': resp.status, 'body': parsed if parsed is not None else content,
                    'url': url}
    except urllib.error.HTTPError as e:
        body_text = ''
        try: body_text = e.read().decode('utf-8', errors='replace')[:500]
        except: pass
        return {'type': 'http_proxy_result', 'id': cmd_id, 'ok': False,
                'status': e.code, 'error': str(e), 'body': body_text, 'url': url}
    except Exception as e:
        return {'type': 'http_proxy_result', 'id': cmd_id, 'ok': False,
                'error': str(e), 'url': url}

def run_phone_diagnostics(cmd_id):
    """手机全面诊断 — 对标remote-agent的17步自动诊断，适配Android五感"""
    results = []

    def diag(name, *args):
        ok, out = run_adb(*args)
        results.append({'name': name, 'ok': ok, 'output': out.strip() if ok else out})
        return ok, out.strip()

    # ☰乾·视: 设备基础信息
    diag('model', 'shell', 'getprop ro.product.model')
    diag('manufacturer', 'shell', 'getprop ro.product.manufacturer')
    diag('android_version', 'shell', 'getprop ro.build.version.release')
    diag('sdk_version', 'shell', 'getprop ro.build.version.sdk')
    diag('serial', 'shell', 'getprop ro.serialno')

    # ☷坤·听: 网络与连接
    diag('wifi_ssid', 'shell', 'dumpsys wifi | grep "mWifiInfo" | head -1')
    diag('ip_address', 'shell', 'ip route | grep "src" | head -1')
    diag('connectivity', 'shell', 'ping -c 1 -W 2 8.8.8.8 2>&1 | tail -1')

    # ☵坎·触: 屏幕与显示
    diag('screen_size', 'shell', 'wm size')
    diag('screen_density', 'shell', 'wm density')
    diag('screen_state', 'shell', 'dumpsys power | grep "mWakefulness"')

    # ☲离·嗅: 资源与健康
    diag('battery', 'shell', 'dumpsys battery | grep -E "level|status|plugged|temperature"')
    diag('memory', 'shell', 'cat /proc/meminfo | head -3')
    diag('storage', 'shell', 'df -h /data | tail -1')
    diag('cpu_usage', 'shell', 'top -bn1 | head -5')

    # ☳震·味: ScreenStream生态
    pkg = detect_package()
    if pkg:
        results.append({'name': 'ss_package', 'ok': True, 'output': pkg})
        ok, out = run_adb('shell', f'pidof {pkg}')
        running = ok and out.strip().isdigit()
        results.append({'name': 'ss_running', 'ok': running, 'output': out.strip() if running else 'not running'})

        # 检查ScreenStream HTTP API
        import urllib.request
        api_status = {}
        for port, label in [(8080, 'mjpeg_api'), (8084, 'input_api')]:
            try:
                req = urllib.request.Request(f'http://127.0.0.1:{port}/status', method='GET')
                with urllib.request.urlopen(req, timeout=3) as resp:
                    content = resp.read().decode('utf-8', errors='replace')
                    api_status[label] = content[:200]
                    results.append({'name': label, 'ok': True, 'output': content[:200]})
            except Exception as e:
                results.append({'name': label, 'ok': False, 'output': str(e)})
    else:
        results.append({'name': 'ss_package', 'ok': False, 'output': 'ScreenStream not installed'})

    # 无障碍服务检查
    ok, out = run_adb('shell', 'settings get secure enabled_accessibility_services')
    a11y_ok = ok and 'screenstream' in out.lower()
    results.append({'name': 'accessibility', 'ok': a11y_ok, 'output': out.strip() if ok else 'unknown'})

    # 端口转发状态
    ok, out = run_adb('forward', '--list')
    results.append({'name': 'port_forwards', 'ok': ok, 'output': out.strip() if ok else 'none'})

    # 分析诊断结果 (Brain逻辑)
    issues = []
    fixes = []
    for r in results:
        if not r['ok']:
            if r['name'] == 'ss_package':
                issues.append('ScreenStream未安装')
                fixes.append('安装ScreenStream APK')
            elif r['name'] == 'ss_running':
                issues.append('ScreenStream未运行')
                fixes.append('启动ScreenStream: adb shell am start -n ...')
            elif r['name'] in ('mjpeg_api', 'input_api'):
                issues.append(f'{r["name"]}不可达')
                fixes.append(f'检查端口转发和ScreenStream投屏状态')
            elif r['name'] == 'accessibility':
                issues.append('无障碍服务未启用')
                fixes.append('启用ScreenStream无障碍服务')
            elif r['name'] == 'connectivity':
                issues.append('网络不通')
                fixes.append('检查WiFi连接')

    passed = sum(1 for r in results if r['ok'])
    total = len(results)
    level = 'ok' if len(issues) == 0 else ('warn' if len(issues) <= 2 else 'error')
    score = round(passed / total * 10, 1) if total > 0 else 0

    analysis = {
        'level': level, 'passed': passed, 'total': total, 'score': score,
        'issues': issues, 'fixes': fixes,
        'summary': f'诊断完成: {passed}/{total} 通过, 健康评分 {score}/10'
            + (f', {len(issues)} 个问题' if issues else ', 一切正常')
    }

    return {'type': 'phone_diag_result', 'id': cmd_id, 'ok': len(issues) == 0,
            'results': results, 'analysis': analysis}


def handle_screenshot(cmd_id):
    """截取手机屏幕并返回base64编码的PNG"""
    import base64, tempfile
    tmp = os.path.join(tempfile.gettempdir(), 'ss_screenshot.png')
    # 截屏到手机
    ok, out = run_adb('shell', 'screencap -p /sdcard/ss_screenshot.png')
    if not ok:
        return {'type': 'screenshot_result', 'id': cmd_id, 'ok': False, 'error': f'screencap failed: {out}'}
    # 拉取到本地
    ok, out = run_adb('pull', '/sdcard/ss_screenshot.png', tmp)
    if not ok:
        return {'type': 'screenshot_result', 'id': cmd_id, 'ok': False, 'error': f'pull failed: {out}'}
    # 清理手机文件
    run_adb('shell', 'rm /sdcard/ss_screenshot.png')
    try:
        with open(tmp, 'rb') as f:
            data = base64.b64encode(f.read()).decode('ascii')
        os.unlink(tmp)
        # 截断大图: 最大500KB base64
        if len(data) > 500000:
            # 缩小图片
            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(base64.b64decode(data)))
                img.thumbnail((540, 1200))
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=60)
                data = base64.b64encode(buf.getvalue()).decode('ascii')
                fmt = 'jpeg'
            except ImportError:
                data = data[:500000]
                fmt = 'png'
        else:
            fmt = 'png'
        return {'type': 'screenshot_result', 'id': cmd_id, 'ok': True,
                'image': data, 'format': fmt, 'size': len(data)}
    except Exception as e:
        return {'type': 'screenshot_result', 'id': cmd_id, 'ok': False, 'error': str(e)}


def get_device_info_dict():
    """获取设备信息用于公网广播"""
    ok, model = run_adb('shell', 'getprop', 'ro.product.model')
    ok2, ver = run_adb('shell', 'getprop', 'ro.build.version.release')
    ok3, out = run_adb('devices')
    lines = [l for l in out.split('\n')[1:] if l.strip() and 'device' in l.split()[1:2]]
    return {
        'model': model.strip() if ok else 'unknown',
        'android': ver.strip() if ok2 else '?',
        'devices': len(lines),
        'adb_path': ADB_PATH
    }

# ═══ HTTP服务器（本地模式） ═══
class ADBBridgeHandler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/':
            self._json(200, {
                'service': 'ADB Bridge',
                'version': '1.0',
                'adb_path': ADB_PATH,
                'presets': list(get_preset_actions().keys()),
            })
        elif path == '/devices':
            ok, out = run_adb('devices', '-l')
            devices = []
            if ok:
                for line in out.split('\n')[1:]:
                    parts = line.strip().split()
                    if len(parts) >= 2 and parts[1] in ('device', 'unauthorized', 'offline'):
                        dev = {'id': parts[0], 'state': parts[1]}
                        for p in parts[2:]:
                            if ':' in p:
                                k, v = p.split(':', 1)
                                dev[k] = v
                        devices.append(dev)
            self._json(200, {'ok': ok, 'devices': devices, 'raw': out})
        elif path == '/status':
            ok, out = run_adb('devices')
            device_lines = [l for l in out.split('\n')[1:] if l.strip() and 'device' in l.split()[1:2]]
            has_device = len(device_lines) > 0
            self._json(200, {
                'ok': True,
                'adb_path': ADB_PATH,
                'has_device': has_device,
                'device_count': len(device_lines),
                'raw': out
            })
        elif path == '/phone-diag':
            result = run_phone_diagnostics('http')
            self._json(200, result)
        elif path == '/screenshot':
            result = handle_screenshot('http')
            self._json(200, result)
        elif path.startswith('/preset/'):
            action = path.split('/preset/')[1]
            presets = get_preset_actions()
            if action not in presets:
                self._json(400, {'ok': False, 'error': f'未知操作: {action}'})
                return
            args = presets[action]
            ok, out = run_adb(*args)
            self._json(200, {'ok': ok, 'action': action, 'output': out})
        else:
            self._json(404, {'error': 'not found'})

    def do_POST(self):
        path = urlparse(self.path).path
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len).decode('utf-8') if content_len else '{}'
        try:
            data = json.loads(body)
        except:
            self._json(400, {'ok': False, 'error': '无效JSON'})
            return

        if path == '/adb':
            args = data.get('args', [])
            if isinstance(args, str):
                args = args.split()
            safe, reason = is_safe_command(args)
            if not safe:
                self._json(403, {'ok': False, 'error': reason})
                return
            timeout = min(data.get('timeout', 15), 60)
            ok, out = run_adb(*args, timeout=timeout)
            self._json(200, {'ok': ok, 'output': out})

        elif path == '/install':
            apk_url = data.get('url', '')
            apk_path = data.get('path', '')
            if apk_url:
                # 下载APK然后安装
                import tempfile, urllib.request
                try:
                    tmp = os.path.join(tempfile.gettempdir(), 'ss_install.apk')
                    self._json(200, {'ok': True, 'status': 'downloading', 'msg': '正在下载APK...'})
                    return
                except Exception as e:
                    self._json(500, {'ok': False, 'error': str(e)})
                    return
            elif apk_path and os.path.exists(apk_path):
                ok, out = run_adb('install', '-r', '-g', apk_path, timeout=60)
                self._json(200, {'ok': ok, 'output': out})
            else:
                self._json(400, {'ok': False, 'error': '需要提供url或path'})

        elif path == '/auto-config':
            # 一键自动配置流程
            results = []
            presets = get_preset_actions()

            # Step 1: 检查设备
            ok, out = run_adb('devices', '-l')
            if 'device' not in out or out.strip().endswith('attached'):
                self._json(200, {'ok': False, 'error': '未检测到设备', 'results': results})
                return
            results.append({'step': '设备检测', 'ok': True, 'output': out})

            # Step 2: 获取设备信息
            ok, model = run_adb('shell', 'getprop', 'ro.product.model')
            ok2, ver = run_adb('shell', 'getprop', 'ro.build.version.release')
            results.append({'step': '设备信息', 'ok': ok, 'output': f'{model} Android {ver}'})

            # Step 3: 自动检测已安装的ScreenStream版本
            detected = detect_package()
            pkg = PACKAGE or PACKAGE_CANDIDATES[-1]
            if detected:
                results.append({'step': '应用检测', 'ok': True, 'installed': True,
                              'output': f'已安装 ({detected})'})
            else:
                results.append({'step': '应用检测', 'ok': True, 'installed': False,
                              'output': '未安装'})
                apk_path = data.get('apk_path', '')
                if apk_path and os.path.exists(apk_path):
                    ok, out = run_adb('install', '-r', '-g', apk_path, timeout=120)
                    results.append({'step': 'APK安装', 'ok': ok, 'output': out})
                else:
                    results.append({'step': 'APK安装', 'ok': False, 'output': '需要提供APK路径'})

            # Step 5: 授予权限
            permissions = [
                ('悬浮窗', ['shell', 'appops', 'set', pkg, 'SYSTEM_ALERT_WINDOW', 'allow']),
                ('电池优化白名单', ['shell', 'dumpsys', 'deviceidle', 'whitelist', f'+{pkg}']),
            ]
            for name, cmd in permissions:
                ok, out = run_adb(*cmd)
                results.append({'step': f'权限-{name}', 'ok': ok, 'output': out})

            # Step 6: 启动应用
            activity = get_activity()
            ok, out = run_adb('shell', 'am', 'start', '-n', activity)
            results.append({'step': '启动应用', 'ok': ok, 'output': out})

            # Step 7: 端口转发
            ok, out = run_adb('forward', 'tcp:8080', 'tcp:8080')
            results.append({'step': '端口转发(8080)', 'ok': ok, 'output': out})

            self._json(200, {'ok': True, 'results': results})
        else:
            self._json(404, {'error': 'not found'})

    def log_message(self, format, *args):
        print(f'[ADB Bridge] {args[0]}' if args else '')

def verify_adb():
    """验证ADB可用性并打印设备信息"""
    ok, out = run_adb('version')
    if ok:
        ver_line = out.split('\n')[0] if out else 'unknown'
        print(f'[✓] ADB: {ver_line}')
    else:
        print(f'[✗] ADB不可用: {out}')
        print(f'    请确认adb路径，或使用 --adb 参数指定')
        return False

    ok, out = run_adb('devices')
    lines = [l for l in out.split('\n')[1:] if l.strip() and 'device' in l]
    print(f'[{"✓" if lines else "!"}] 已连接设备: {len(lines)}个')
    for line in lines:
        print(f'    {line.strip()}')
    return True

def run_public_mode(server_url, code):
    """公网模式：WebSocket连接到信令服务器"""
    try:
        import websocket
    except ImportError:
        print('\n[✗] 公网模式需要 websocket-client 库')
        print('    请运行: pip install websocket-client')
        print('    然后重新启动本程序')
        return

    ws_url = f'{server_url}?role=adb-bridge&room={code}'
    print(f'\n[公网] 正在连接信令服务器...')
    print(f'[公网] URL: {ws_url}')

    def on_open(ws):
        print(f'[公网] ✓ 已连接！')
        print(f'')
        print(f'╔══════════════════════════════════════════════╗')
        print(f'║  在网页输入连接码: {code}                    ║')
        print(f'║  网页地址: https://aiotvr.xyz/cast/setup.html║')
        print(f'╚══════════════════════════════════════════════╝')
        print(f'')
        # 发送设备信息
        info = get_device_info_dict()
        ws.send(json.dumps({'type': 'device_info', 'data': info}, ensure_ascii=False))
        print(f'[公网] 设备: {info["model"]} Android {info["android"]} ({info["devices"]}台)')
        print(f'[公网] 等待网页控制端连接...')

    def on_message(ws, message):
        try:
            msg = json.loads(message)
        except:
            return

        msg_type = msg.get('type', '')

        # 信令服务器系统消息
        if msg_type == 'adb_registered':
            return
        if msg_type == 'controller_connected':
            print(f'[公网] ● 网页控制端已连接')
            # 重新发送设备信息
            info = get_device_info_dict()
            ws.send(json.dumps({'type': 'device_info', 'data': info}, ensure_ascii=False))
            return
        if msg_type == 'controller_disconnected':
            print(f'[公网] ○ 网页控制端已断开')
            return
        if msg_type == 'error':
            print(f'[公网] 错误: {msg.get("data", {}).get("message", str(msg))}')
            return

        # ADB命令（来自网页控制端）
        print(f'[cmd] {msg_type}: {msg.get("action", msg.get("args", ""))}')
        result = handle_ws_command(msg)
        if result:
            try:
                ws.send(json.dumps(result, ensure_ascii=False))
                status = '✓' if result.get('ok') else '✗'
                print(f'[rsp] {status} {result.get("type", "")}')
            except Exception as e:
                print(f'[公网] 发送失败: {e}')

    def on_error(ws, error):
        print(f'[公网] 错误: {error}')

    def on_close(ws, code, msg):
        print(f'[公网] 连接断开 (code={code})')

    # 自动重连循环
    while True:
        try:
            ws = websocket.WebSocketApp(ws_url,
                on_open=on_open, on_message=on_message,
                on_error=on_error, on_close=on_close)
            ws.run_forever(ping_interval=25, ping_timeout=10,
                          sslopt={'cert_reqs': 0} if 'wss://' in ws_url else {})
        except KeyboardInterrupt:
            print('\n[公网] 已停止')
            break
        except Exception as e:
            print(f'[公网] 异常: {e}')
        print('[公网] 5秒后重连...')
        time.sleep(5)

def main():
    global ADB_PATH
    parser = argparse.ArgumentParser(description='ADB Bridge v2.0')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='本地HTTP端口')
    parser.add_argument('--adb', type=str, default=None, help='ADB路径')
    parser.add_argument('--public', action='store_true', help='启用公网模式')
    parser.add_argument('--code', type=str, default=None, help='公网连接码(默认随机6位)')
    parser.add_argument('--server', type=str, default='wss://aiotvr.xyz/signal/',
                        help='信令服务器URL')
    args = parser.parse_args()

    ADB_PATH = args.adb or find_adb()

    if args.public:
        # ═══ 公网模式 ═══
        code = args.code or str(random.randint(100000, 999999))
        print(f'╔══════════════════════════════════════════════╗')
        print(f'║      ADB Bridge v2.0 — 公网模式              ║')
        print(f'╠══════════════════════════════════════════════╣')
        print(f'║ ADB路径: {ADB_PATH}')
        print(f'║ 信令服务器: {args.server}')
        print(f'║ 连接码: {code}')
        print(f'╚══════════════════════════════════════════════╝')
        verify_adb()
        run_public_mode(args.server, code)
    else:
        # ═══ 本地模式 ═══
        print(f'╔══════════════════════════════════════════════╗')
        print(f'║      ADB Bridge v2.0 — 本地模式              ║')
        print(f'╠══════════════════════════════════════════════╣')
        print(f'║ ADB路径: {ADB_PATH}')
        print(f'║ 监听端口: http://localhost:{args.port}')
        print(f'║ 网页端: https://aiotvr.xyz/cast/setup.html')
        print(f'║ 提示: 使用 --public 启用公网模式')
        print(f'╚══════════════════════════════════════════════╝')
        verify_adb()
        print(f'\n等待网页端连接...\n')

        server = HTTPServer(('0.0.0.0', args.port), ADBBridgeHandler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print('\n[ADB Bridge] 已停止')
            server.server_close()

if __name__ == '__main__':
    main()
