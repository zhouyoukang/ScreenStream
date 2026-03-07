"""双向文件共享中心 - 浏览/上传/下载/预览/剪贴板/系统信息"""
import http.server
import os
import json
import zipfile
import io
import re
import socket
import platform
import mimetypes
import urllib.parse
import shutil
import time
import threading

PORT = 9999
DESKTOP_IP = '192.168.31.141'
DESKTOP_AGENT_PORT = 9998
CLIPBOARD = {"text": "", "ts": 0}
COPY_JOBS = {}  # {job_id: {status, src, dst, copied, total, error}}
AGENT_ONLINE = False

def check_agent():
    """Check if desktop agent is running."""
    global AGENT_ONLINE
    import urllib.request
    try:
        r = urllib.request.urlopen(f'http://{DESKTOP_IP}:{DESKTOP_AGENT_PORT}/api/agent_status', timeout=2)
        data = json.loads(r.read())
        AGENT_ONLINE = data.get('ok', False)
    except:
        AGENT_ONLINE = False
    return AGENT_ONLINE

def proxy_agent(api_path):
    """Proxy a request to desktop agent, return bytes."""
    import urllib.request
    url = f'http://{DESKTOP_IP}:{DESKTOP_AGENT_PORT}{api_path}'
    r = urllib.request.urlopen(url, timeout=30)
    return r.read(), r.headers.get('Content-Type', 'application/json')

def do_pull_job(job_id, remote_path, local_path):
    """Pull a file from desktop agent to local."""
    import urllib.request
    job = COPY_JOBS[job_id]
    try:
        # First get file list if directory
        url = f'http://{DESKTOP_IP}:{DESKTOP_AGENT_PORT}/api/agent_list?path={urllib.parse.quote(remote_path)}'
        r = urllib.request.urlopen(url, timeout=10)
        data = json.loads(r.read())
        items = data.get('items', [])
        files_to_pull = []
        def collect_files(dir_path, local_dir, items_list):
            for item in items_list:
                rp = dir_path + ('\\' if not dir_path.endswith('\\') else '') + item['name']
                lp = os.path.join(local_dir, item['name'])
                if item['is_dir']:
                    try:
                        sub_url = f'http://{DESKTOP_IP}:{DESKTOP_AGENT_PORT}/api/agent_list?path={urllib.parse.quote(rp)}'
                        sub_r = urllib.request.urlopen(sub_url, timeout=10)
                        sub_data = json.loads(sub_r.read())
                        collect_files(rp, lp, sub_data.get('items', []))
                    except: pass
                else:
                    files_to_pull.append((rp, lp, item.get('size', 0)))
        if any(i['is_dir'] for i in items) or len(items) > 0:
            collect_files(remote_path, local_path, items)
        else:
            # Single file
            files_to_pull = [(remote_path, local_path, 0)]
        job['total'] = sum(f[2] for f in files_to_pull)
        job['file_count'] = len(files_to_pull)
        for i, (rp, lp, sz) in enumerate(files_to_pull):
            os.makedirs(os.path.dirname(lp), exist_ok=True)
            dl_url = f'http://{DESKTOP_IP}:{DESKTOP_AGENT_PORT}/api/agent_download?path={urllib.parse.quote(rp)}'
            urllib.request.urlretrieve(dl_url, lp)
            job['copied'] += sz if sz > 0 else os.path.getsize(lp)
            job['files_done'] = i + 1
        job['status'] = 'done'
    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e)
    print(f"[PULL] {job_id}: {job['status']} - {job['files_done']}/{job['file_count']} files")

UNLOCK_SCRIPT = """@echo off
chcp 65001 >nul
echo === Unlock Desktop Network Access ===
reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Lsa" /v LimitBlankPasswordUse /t REG_DWORD /d 0 /f
reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f
netsh advfirewall firewall set rule group="Remote Desktop" new enable=yes 2>nul
netsh advfirewall firewall set rule group="\u8fdc\u7a0b\u684c\u9762" new enable=yes 2>nul
echo [OK] Done! SMB + RDP unlocked.
pause
"""

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except:
        return '127.0.0.1'
    finally:
        s.close()

def get_sys_info():
    drives = []
    if os.name == 'nt':
        for letter in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
            p = f'{letter}:\\'
            if os.path.exists(p):
                try:
                    total, used, free = shutil.disk_usage(p)
                    drives.append({'letter': letter, 'total': total, 'free': free})
                except:
                    drives.append({'letter': letter, 'total': 0, 'free': 0})
    return {
        'hostname': socket.gethostname(),
        'ip': get_local_ip(),
        'os': f'{platform.system()} {platform.release()}',
        'machine': platform.machine(),
        'drives': drives,
    }

def list_dir(path):
    items = []
    try:
        for name in os.listdir(path):
            fp = os.path.join(path, name)
            try:
                st = os.stat(fp)
                is_dir = os.path.isdir(fp)
                items.append({
                    'name': name,
                    'is_dir': is_dir,
                    'size': st.st_size if not is_dir else 0,
                    'modified': int(st.st_mtime),
                    'ext': os.path.splitext(name)[1].lower() if not is_dir else '',
                })
            except (PermissionError, OSError):
                items.append({'name': name, 'is_dir': False, 'size': -1, 'modified': 0, 'ext': ''})
    except PermissionError:
        pass
    items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    return items

def safe_path(p):
    p = urllib.parse.unquote(p).replace('/', os.sep)
    if p.startswith('\\\\'):
        return p  # UNC path, don't normalize away the prefix
    if os.name == 'nt' and len(p) >= 2 and p[1] == ':':
        return os.path.normpath(p)
    return os.path.normpath(p)

def do_copy_job(job_id, src, dst):
    """Server-side copy in background thread."""
    job = COPY_JOBS[job_id]
    try:
        if os.path.isfile(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            job['total'] = os.path.getsize(src)
            with open(src, 'rb') as sf, open(dst, 'wb') as df:
                while True:
                    chunk = sf.read(1024*1024)  # 1MB chunks
                    if not chunk:
                        break
                    df.write(chunk)
                    job['copied'] += len(chunk)
            job['status'] = 'done'
        elif os.path.isdir(src):
            # Count total size first
            total = 0
            file_list = []
            for dirpath, dirnames, filenames in os.walk(src):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total += os.path.getsize(fp)
                        rel = os.path.relpath(fp, src)
                        file_list.append((fp, os.path.join(dst, rel)))
                    except:
                        pass
            job['total'] = total
            job['file_count'] = len(file_list)
            for i, (sfp, dfp) in enumerate(file_list):
                os.makedirs(os.path.dirname(dfp), exist_ok=True)
                with open(sfp, 'rb') as sf, open(dfp, 'wb') as df:
                    while True:
                        chunk = sf.read(1024*1024)
                        if not chunk:
                            break
                        df.write(chunk)
                        job['copied'] += len(chunk)
                job['files_done'] = i + 1
            job['status'] = 'done'
        else:
            job['status'] = 'error'
            job['error'] = 'Source not found'
    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e)
    print(f"[COPY] {job_id}: {job['status']} - {job['copied']}/{job['total']} bytes")

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == '/' or path == '/index.html':
            self._serve_html()
        elif path == '/api/sysinfo':
            self._json(get_sys_info())
        elif path == '/api/list':
            dir_path = safe_path(qs.get('path', ['C:\\'])[0])
            self._json({'path': dir_path, 'items': list_dir(dir_path), 'parent': os.path.dirname(dir_path)})
        elif path == '/api/download':
            file_path = safe_path(qs.get('path', [''])[0])
            self._serve_file(file_path)
        elif path == '/api/preview':
            file_path = safe_path(qs.get('path', [''])[0])
            self._serve_preview(file_path)
        elif path == '/api/clipboard':
            self._json(CLIPBOARD)
        elif path == '/api/search':
            dir_path = safe_path(qs.get('path', ['C:\\'])[0])
            query = qs.get('q', [''])[0].lower()
            self._search(dir_path, query)
        elif path == '/api/mount_check':
            ip = qs.get('ip', [DESKTOP_IP])[0]
            smb_ok = os.path.exists(f'\\\\{ip}\\C$')
            agent_ok = check_agent()
            self._json({'ok': smb_ok or agent_ok, 'smb': smb_ok, 'agent': agent_ok, 'ip': ip})
        elif path == '/api/agent_check':
            ok = check_agent()
            self._json({'ok': ok, 'ip': DESKTOP_IP, 'port': DESKTOP_AGENT_PORT})
        elif path == '/api/remote_list':
            rp = qs.get('path', ['C:\\'])[0]
            try:
                data, ct = proxy_agent(f'/api/agent_list?path={urllib.parse.quote(rp)}')
                self.send_response(200)
                self.send_header('Content-Type', ct)
                self.send_header('Content-Length', len(data))
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self._json({'error': str(e), 'items': [], 'path': rp})
        elif path == '/api/remote_download':
            rp = qs.get('path', [''])[0]
            try:
                data, ct = proxy_agent(f'/api/agent_download?path={urllib.parse.quote(rp)}')
                self.send_response(200)
                self.send_header('Content-Type', ct)
                self.send_header('Content-Length', len(data))
                self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(rp)}"')
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self.send_error(502, str(e))
        elif path == '/api/remote_preview':
            rp = qs.get('path', [''])[0]
            try:
                data, ct = proxy_agent(f'/api/agent_preview?path={urllib.parse.quote(rp)}')
                self.send_response(200)
                self.send_header('Content-Type', ct)
                self.send_header('Content-Length', len(data))
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self._json({'type': 'error', 'content': str(e)})
        elif path == '/api/remote_search':
            rp = qs.get('path', ['C:\\'])[0]
            q = qs.get('q', [''])[0]
            try:
                data, ct = proxy_agent(f'/api/agent_search?path={urllib.parse.quote(rp)}&q={urllib.parse.quote(q)}')
                self.send_response(200)
                self.send_header('Content-Type', ct)
                self.send_header('Content-Length', len(data))
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self._json({'results': [], 'total': 0, 'error': str(e)})
        elif path == '/api/remote_sysinfo':
            try:
                data, ct = proxy_agent('/api/agent_sysinfo')
                self.send_response(200)
                self.send_header('Content-Type', ct)
                self.send_header('Content-Length', len(data))
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self._json({'error': str(e)})
        elif path == '/api/serve_agent':
            agent_bat = open(os.path.join(os.path.dirname(__file__), 'desktop_agent.bat'), 'rb').read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', 'attachment; filename="desktop_agent.bat"')
            self.send_header('Content-Length', len(agent_bat))
            self.end_headers()
            self.wfile.write(agent_bat)
        elif path == '/api/serve_unlock':
            data = UNLOCK_SCRIPT.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', 'attachment; filename="unlock-desktop.bat"')
            self.send_header('Content-Length', len(data))
            self.end_headers()
            self.wfile.write(data)
        elif path == '/api/copy_status':
            jid = qs.get('id', [''])[0]
            job = COPY_JOBS.get(jid, {'status': 'not_found'})
            self._json(job)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == '/api/upload':
            self._handle_upload()
        elif path == '/api/upload_zip':
            self._handle_zip_upload()
        elif path == '/api/clipboard':
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length))
            CLIPBOARD['text'] = data.get('text', '')
            CLIPBOARD['ts'] = int(time.time())
            self._json({'ok': True})
        elif path == '/api/mkdir':
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length))
            dir_path = safe_path(data['path'])
            os.makedirs(dir_path, exist_ok=True)
            self._json({'ok': True, 'path': dir_path})
        elif path == '/api/delete':
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length))
            target = safe_path(data['path'])
            if os.path.isdir(target):
                shutil.rmtree(target)
            else:
                os.remove(target)
            self._json({'ok': True})
        elif path == '/api/copy':
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length))
            src = data['src']
            dst = data['dst']
            jid = f'copy_{int(time.time()*1000)}'
            COPY_JOBS[jid] = {'status': 'running', 'src': src, 'dst': dst, 'copied': 0, 'total': 0, 'error': None, 'files_done': 0, 'file_count': 0}
            t = threading.Thread(target=do_copy_job, args=(jid, src, dst), daemon=True)
            t.start()
            self._json({'ok': True, 'job_id': jid})
        elif path == '/api/pull':
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length))
            src = data['src']  # remote path on desktop
            dst = data['dst']  # local path on laptop
            jid = f'pull_{int(time.time()*1000)}'
            COPY_JOBS[jid] = {'status': 'running', 'src': src, 'dst': dst, 'copied': 0, 'total': 0, 'error': None, 'files_done': 0, 'file_count': 0}
            t = threading.Thread(target=do_pull_job, args=(jid, src, dst), daemon=True)
            t.start()
            self._json({'ok': True, 'job_id': jid})
        else:
            self.send_error(404)

    def _json(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(data))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(data)

    def _serve_html(self):
        html = HTML.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(html))
        self.end_headers()
        self.wfile.write(html)

    def _serve_file(self, file_path):
        if not os.path.isfile(file_path):
            self.send_error(404)
            return
        mime = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        size = os.path.getsize(file_path)
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', size)
        fname = os.path.basename(file_path)
        self.send_header('Content-Disposition', f'attachment; filename="{urllib.parse.quote(fname)}"')
        self.end_headers()
        with open(file_path, 'rb') as f:
            shutil.copyfileobj(f, self.wfile)

    def _serve_preview(self, file_path):
        if not os.path.isfile(file_path):
            self._json({'type': 'error', 'content': 'File not found'})
            return
        ext = os.path.splitext(file_path)[1].lower()
        size = os.path.getsize(file_path)

        if ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg', '.ico'):
            mime = mimetypes.guess_type(file_path)[0] or 'image/png'
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', size)
            self.end_headers()
            with open(file_path, 'rb') as f:
                shutil.copyfileobj(f, self.wfile)
        elif ext in ('.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.yml', '.yaml',
                      '.kt', '.java', '.sh', '.bat', '.ps1', '.cfg', '.ini', '.toml', '.csv', '.log',
                      '.gradle', '.properties', '.kts', '.sql', '.gitignore', '.env'):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read(100_000)
                self._json({'type': 'text', 'content': content, 'size': size, 'ext': ext})
            except:
                self._json({'type': 'error', 'content': 'Cannot read file'})
        else:
            self._json({'type': 'binary', 'size': size, 'ext': ext})

    def _search(self, root, query):
        results = []
        count = 0
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if not d.startswith('.')]
                for name in filenames:
                    if query in name.lower():
                        fp = os.path.join(dirpath, name)
                        results.append({'name': name, 'path': fp, 'is_dir': False})
                        count += 1
                        if count >= 50:
                            break
                for name in dirnames:
                    if query in name.lower():
                        fp = os.path.join(dirpath, name)
                        results.append({'name': name, 'path': fp, 'is_dir': True})
                        count += 1
                if count >= 50:
                    break
        except:
            pass
        self._json({'results': results, 'total': count})

    def _handle_upload(self):
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            self.send_error(400)
            return
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        boundary = re.search(r'boundary=(.+)', content_type)
        if not boundary:
            self.send_error(400)
            return
        boundary = boundary.group(1).encode()
        parts_data = body.split(b'--' + boundary)
        file_data = None
        rel_path = ''
        target_dir = ''
        for part in parts_data:
            if b'name="file"' in part:
                idx = part.find(b'\r\n\r\n')
                if idx >= 0:
                    file_data = part[idx+4:]
                    if file_data.endswith(b'\r\n'):
                        file_data = file_data[:-2]
            elif b'name="path"' in part:
                idx = part.find(b'\r\n\r\n')
                if idx >= 0:
                    rel_path = part[idx+4:].strip().decode('utf-8').strip()
            elif b'name="targetDir"' in part:
                idx = part.find(b'\r\n\r\n')
                if idx >= 0:
                    target_dir = part[idx+4:].strip().decode('utf-8').strip()
        if file_data is None:
            self.send_error(400)
            return
        if not rel_path:
            rel_path = 'uploaded_file'
        save_dir = target_dir if target_dir else os.path.join(os.path.expanduser('~'), 'Downloads')
        save_path = os.path.join(save_dir, rel_path)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'wb') as f:
            f.write(file_data)
        self._json({'ok': True, 'path': save_path, 'size': len(file_data)})

    def _handle_zip_upload(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        target = safe_path(qs.get('target', [os.path.join(os.path.expanduser('~'), 'Downloads')])[0])
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        os.makedirs(target, exist_ok=True)
        try:
            zf = zipfile.ZipFile(io.BytesIO(body))
            count = 0
            for info in zf.infolist():
                if info.is_dir():
                    continue
                tp = os.path.join(target, info.filename)
                os.makedirs(os.path.dirname(tp), exist_ok=True)
                with open(tp, 'wb') as f:
                    f.write(zf.read(info))
                count += 1
            self._json({'ok': True, 'files': count, 'target': target})
            print(f"[ZIP] {count} files -> {target}")
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': False, 'error': str(e)}).encode())

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

# ============================================================
# HTML - 双向文件共享中心
# ============================================================
HTML = r"""<!DOCTYPE html>
<html lang="zh"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>🔄 双向共享中心</title>
<style>
:root{--bg:#0a0a0a;--card:#141414;--border:#262626;--text:#e0e0e0;--dim:#777;--accent:#4fc3f7;--green:#66bb6a;--red:#ef5350;--yellow:#ffd54f;--radius:10px}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);height:100vh;display:flex;flex-direction:column;overflow:hidden}
/* Top bar */
.topbar{display:flex;align-items:center;gap:12px;padding:8px 16px;background:#111;border-bottom:1px solid var(--border);flex-shrink:0}
.topbar h1{font-size:1.1em;white-space:nowrap}
.topbar .status{margin-left:auto;display:flex;gap:12px;font-size:.8em;color:var(--dim)}
.topbar .status span{display:flex;align-items:center;gap:4px}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.dot-g{background:var(--green)}.dot-r{background:var(--red)}.dot-y{background:var(--yellow)}
/* Tabs */
.tabs{display:flex;border-bottom:1px solid var(--border);flex-shrink:0;background:#111}
.tab{padding:8px 20px;cursor:pointer;border-bottom:2px solid transparent;color:var(--dim);font-size:.9em;transition:.2s}
.tab:hover{color:var(--text)}.tab.active{color:var(--accent);border-bottom-color:var(--accent)}
/* Main */
.main{flex:1;overflow:hidden;display:flex;flex-direction:column}
.panel{display:none;flex:1;overflow:auto;padding:16px}.panel.active{display:flex;flex-direction:column}
/* File browser */
.breadcrumb{display:flex;align-items:center;gap:4px;padding:8px 0;flex-wrap:wrap;font-size:.85em;flex-shrink:0}
.breadcrumb span{cursor:pointer;color:var(--accent);padding:2px 6px;border-radius:4px}.breadcrumb span:hover{background:#1a3040}
.breadcrumb .sep{color:var(--dim);cursor:default}
.toolbar{display:flex;gap:8px;padding:8px 0;flex-shrink:0;flex-wrap:wrap;align-items:center}
.toolbar input[type=text]{background:#1a1a1a;border:1px solid var(--border);color:var(--text);padding:6px 12px;border-radius:6px;font-size:.85em;flex:1;min-width:150px}
.toolbar button,.btn{background:#222;border:1px solid var(--border);color:var(--text);padding:6px 14px;border-radius:6px;cursor:pointer;font-size:.85em;transition:.2s;white-space:nowrap}
.toolbar button:hover,.btn:hover{background:#333;border-color:var(--accent)}
.btn-accent{background:var(--accent);color:#000;border-color:var(--accent);font-weight:600}
.btn-accent:hover{background:#81d4fa}
.btn-green{background:var(--green);color:#000;border-color:var(--green)}.btn-green:hover{background:#81c784}
.file-list{flex:1;overflow:auto}
.file-item{display:flex;align-items:center;gap:10px;padding:8px 12px;border-radius:6px;cursor:pointer;transition:.15s;border:1px solid transparent}
.file-item:hover{background:#1a1a1a;border-color:var(--border)}
.file-item.selected{background:#1a2a3a;border-color:var(--accent)}
.file-icon{font-size:1.3em;width:28px;text-align:center;flex-shrink:0}
.file-name{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.file-meta{color:var(--dim);font-size:.8em;white-space:nowrap}
.file-actions{display:flex;gap:4px;opacity:0;transition:.2s}
.file-item:hover .file-actions{opacity:1}
.file-actions button{background:none;border:none;color:var(--dim);cursor:pointer;padding:4px;font-size:1em}.file-actions button:hover{color:var(--accent)}
/* Quick access */
.quick-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;padding:12px 0}
.quick-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:16px;text-align:center;cursor:pointer;transition:.2s}
.quick-card:hover{border-color:var(--accent);transform:translateY(-2px)}
.quick-card .icon{font-size:2em;margin-bottom:6px}
.quick-card .label{font-size:.85em;color:var(--dim)}
/* Upload zone */
.upload-zone{border:2px dashed var(--border);border-radius:var(--radius);padding:40px;text-align:center;cursor:pointer;transition:.3s;margin:12px 0}
.upload-zone:hover,.upload-zone.dragover{border-color:var(--accent);background:#0d1f2d}
/* Preview */
.preview-overlay{position:fixed;inset:0;background:rgba(0,0,0,.85);display:none;z-index:100;flex-direction:column;align-items:center;justify-content:center}
.preview-overlay.show{display:flex}
.preview-close{position:absolute;top:16px;right:20px;font-size:2em;cursor:pointer;color:#fff;z-index:101}
.preview-content{max-width:90vw;max-height:85vh;overflow:auto}
.preview-content img{max-width:90vw;max-height:80vh;object-fit:contain;border-radius:8px}
.preview-content pre{background:#111;padding:20px;border-radius:8px;color:#ccc;font-size:.85em;max-height:80vh;overflow:auto;white-space:pre-wrap;word-break:break-all}
/* Clipboard */
.clip-area{width:100%;max-width:600px;margin:0 auto}
.clip-area textarea{width:100%;height:200px;background:#111;border:1px solid var(--border);color:var(--text);padding:12px;border-radius:8px;font-size:.95em;resize:vertical;font-family:inherit}
.clip-status{text-align:center;color:var(--dim);font-size:.85em;margin-top:8px}
/* Info cards */
.info-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px;padding:12px 0}
.info-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:20px}
.info-card h3{font-size:.95em;color:var(--accent);margin-bottom:12px}
.info-row{display:flex;justify-content:space-between;padding:4px 0;font-size:.85em}
.info-row .label{color:var(--dim)}.info-row .value{color:var(--text)}
.drive-bar{height:6px;background:#333;border-radius:3px;margin-top:4px;overflow:hidden}
.drive-fill{height:100%;border-radius:3px}
/* Toast */
.toast{position:fixed;bottom:20px;right:20px;background:#333;color:#fff;padding:12px 20px;border-radius:8px;z-index:200;opacity:0;transform:translateY(20px);transition:.3s;font-size:.9em;max-width:400px}
.toast.show{opacity:1;transform:translateY(0)}
/* Transfer log */
.transfer-log{max-height:200px;overflow-y:auto;background:#111;border-radius:8px;padding:8px 12px;font-family:monospace;font-size:.8em;line-height:1.6}
.tl-ok{color:var(--green)}.tl-err{color:var(--red)}.tl-info{color:var(--dim)}
</style></head>
<body>

<div class="topbar">
  <h1>🔄 双向共享中心</h1>
  <div class="status">
    <span><span class="dot dot-g" id="dotLocal"></span> 本机</span>
    <span id="connInfo"></span>
  </div>
</div>

<div class="tabs">
  <div class="tab active" data-tab="files">📂 文件浏览</div>
  <div class="tab" data-tab="upload">📤 上传</div>
  <div class="tab" data-tab="clipboard">📋 剪贴板</div>
  <div class="tab" data-tab="info">ℹ️ 系统</div>
  <div class="tab" data-tab="setup">🔧 配置</div>
</div>

<div class="main">
  <!-- ===== 文件浏览 ===== -->
  <div class="panel active" id="p-files">
    <div class="breadcrumb" id="breadcrumb"></div>
    <div class="toolbar">
      <input type="text" id="searchBox" placeholder="🔍 搜索文件..." onkeydown="if(event.key==='Enter')doSearch()">
      <button onclick="doSearch()">搜索</button>
      <button onclick="navigateTo(currentPath)">🔄</button>
      <button onclick="goUp()">⬆️ 上级</button>
      <span style="border-left:1px solid var(--border);height:24px;margin:0 4px"></span>
      <button id="modeLocal" class="btn btn-accent" onclick="switchMode('local')">🏠 本机</button>
      <button id="modeRemote" class="btn" onclick="switchMode('remote')">🖥️ 台式机</button>
    </div>
    <div id="quickAccess" class="quick-grid"></div>
    <div class="file-list" id="fileList"></div>
  </div>

  <!-- ===== 上传 ===== -->
  <div class="panel" id="p-upload">
    <h2 style="margin-bottom:12px;font-size:1.1em">📤 上传文件到本机</h2>
    <div style="margin-bottom:12px">
      <span style="color:var(--dim);font-size:.85em">目标路径：</span>
      <input type="text" id="uploadTarget" value="" style="background:#1a1a1a;border:1px solid var(--border);color:var(--text);padding:6px 12px;border-radius:6px;width:400px;font-size:.85em">
    </div>
    <div class="upload-zone" id="uploadZone" onclick="uploadInput.click()">
      <div style="font-size:2.5em;margin-bottom:8px">📁</div>
      <p>点击选择文件夹 · 或拖拽文件/ZIP到此处</p>
      <small style="color:var(--dim)">支持文件夹上传、单文件、ZIP自动解压</small>
    </div>
    <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap">
      <input type="file" id="uploadInput" webkitdirectory multiple style="display:none">
      <input type="file" id="uploadFiles" multiple style="display:none">
      <button class="btn btn-accent" onclick="uploadInput.click()">📁 选择文件夹</button>
      <button class="btn btn-green" onclick="uploadFiles.click()">📄 选择文件</button>
      <button class="btn" onclick="uploadZipInput.click()">📦 上传ZIP解压</button>
      <input type="file" id="uploadZipInput" accept=".zip" style="display:none">
    </div>
    <div style="margin-top:16px" id="uploadProgress"></div>
    <div class="transfer-log" id="uploadLog" style="margin-top:12px;display:none"></div>
  </div>

  <!-- ===== 剪贴板 ===== -->
  <div class="panel" id="p-clipboard">
    <h2 style="margin-bottom:12px;font-size:1.1em">📋 跨机剪贴板</h2>
    <p style="color:var(--dim);font-size:.85em;margin-bottom:12px">在任一端粘贴文本，另一端即可获取。实时同步。</p>
    <div class="clip-area">
      <textarea id="clipText" placeholder="在这里输入或粘贴文本..."></textarea>
      <div style="display:flex;gap:8px;margin-top:8px;justify-content:center">
        <button class="btn btn-accent" onclick="syncClip()">📤 同步到对方</button>
        <button class="btn" onclick="loadClip()">📥 获取最新</button>
        <button class="btn" onclick="copyClipToLocal()">📋 复制到本地剪贴板</button>
      </div>
      <div class="clip-status" id="clipStatus"></div>
    </div>
  </div>

  <!-- ===== 系统信息 ===== -->
  <div class="panel" id="p-info">
    <h2 style="margin-bottom:12px;font-size:1.1em">ℹ️ 系统信息</h2>
    <div class="info-grid" id="infoGrid"></div>
  </div>

  <!-- ===== 配置台式机 ===== -->
  <div class="panel" id="p-setup">
    <h2 style="margin-bottom:12px;font-size:1.1em">🔧 配置台式机连接</h2>
    <div style="max-width:600px">
      <div class="info-card" style="margin-bottom:16px">
        <h3>当前状态</h3>
        <div class="info-row"><span class="label">台式机IP</span><span class="value" id="setupIP">%%DESKTOP_IP%%</span></div>
        <div class="info-row"><span class="label">代理服务</span><span class="value" id="setupAgent">检测中...</span></div>
        <div class="info-row"><span class="label">SMB共享</span><span class="value" id="setupSMB">检测中...</span></div>
      </div>
      <div class="info-card" style="margin-bottom:16px;border-color:var(--accent)">
        <h3>⭐ 推荐：下载代理程序（一键映射）</h3>
        <p style="color:var(--dim);font-size:.85em;margin-bottom:8px">在台式机浏览器打开本页 → 下载 → 双击运行，即可远程浏览台式机所有文件</p>
        <a href="/api/serve_agent" class="btn btn-accent" style="text-decoration:none;display:inline-block;margin-right:8px">⬇️ 下载 desktop_agent.bat</a>
        <button class="btn btn-green" onclick="checkDesktopMount()">🔍 检测连接</button>
        <span id="setupResult" style="margin-left:8px"></span>
      </div>
      <div class="info-card" style="margin-bottom:16px">
        <h3>备选：SMB解锁（需管理员）</h3>
        <p style="color:var(--dim);font-size:.85em;margin-bottom:8px">解锁后可用Windows资源管理器直接访问</p>
        <a href="/api/serve_unlock" class="btn" style="text-decoration:none;display:inline-block">⬇️ 下载 unlock-desktop.bat</a>
      </div>
      <div class="info-card">
        <h3>连接后可以做什么</h3>
        <p style="color:var(--dim);font-size:.85em;line-height:1.6">
          ✅ 远程浏览台式机所有磁盘和文件<br>
          ✅ 选择性拉取精华文件到本机（服务端高速传输）<br>
          ✅ 预览台式机上的文本/图片文件<br>
          ✅ 搜索台式机文件<br>
          ✅ 去除糟粕：跳过 node_modules/.git/缓存 等垃圾
        </p>
      </div>
    </div>
  </div>
</div>

<!-- Preview overlay -->
<div class="preview-overlay" id="previewOverlay" onclick="if(event.target===this)closePreview()">
  <div class="preview-close" onclick="closePreview()">✕</div>
  <div class="preview-content" id="previewContent"></div>
</div>

<!-- Toast -->
<div class="toast" id="toast"></div>

<script>
// ===== State =====
let currentPath = '';
let sysInfo = null;
let desktopConnected = false;
let browseMode = 'local'; // 'local' or 'remote'
const DESKTOP_IP = '%%DESKTOP_IP%%';
const QUICK_PATHS = [
  {icon:'📚',label:'二手书',path:'E:\\道\\二手书',group:'local'},
  {icon:'🏠',label:'桌面',path:'%DESKTOP%',group:'local'},
  {icon:'📁',label:'下载',path:'%DOWNLOADS%',group:'local'},
  {icon:'📂',label:'文档',path:'%DOCUMENTS%',group:'local'},
  {icon:'💿',label:'C盘',path:'C:\\',group:'local'},
  {icon:'💿',label:'D盘',path:'D:\\',group:'local'},
  {icon:'💿',label:'E盘',path:'E:\\',group:'local'},
];
const DESKTOP_PATHS = [
  {icon:'�',label:'台式机C盘',path:'V:\\',group:'desktop'},
  {icon:'�',label:'台式机D盘',path:'W:\\',group:'desktop'},
  {icon:'💿',label:'台式机E盘',path:'X:\\',group:'desktop'},
  {icon:'🏠',label:'台式机桌面',path:'Y:\\Administrator\\Desktop',group:'desktop'},
  {icon:'📂',label:'台式机文档',path:'Y:\\Administrator\\Documents',group:'desktop'},
  {icon:'�',label:'台式机下载',path:'Y:\\Administrator\\Downloads',group:'desktop'},
];

// ===== Tabs =====
document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  document.getElementById('p-' + t.dataset.tab).classList.add('active');
  if (t.dataset.tab === 'clipboard') loadClip();
  if (t.dataset.tab === 'info') loadInfo();
}));

// ===== Toast =====
function toast(msg, dur=3000) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), dur);
}

// ===== File Browser =====
async function navigateTo(path) {
  try {
    // Y: drive paths use local API (mapped SMB share)
    const r = await fetch('/api/list?path=' + encodeURIComponent(path));
    const data = await r.json();
    if (data.error) { toast('❌ ' + data.error); return; }
    currentPath = data.path;
    if (browseMode === 'local') document.getElementById('uploadTarget').value = currentPath;
    renderBreadcrumb(data.path);
    renderFileList(data.items);
    document.getElementById('quickAccess').style.display = 'none';
  } catch(e) { toast('❌ 无法访问: ' + e.message); }
}

function switchMode(mode) {
  browseMode = mode;
  document.getElementById('modeLocal').className = mode === 'local' ? 'btn btn-accent' : 'btn';
  document.getElementById('modeRemote').className = mode === 'remote' ? 'btn btn-green' : 'btn';
  desktopConnected = true; // Y: drive always available
  showQuickAccess();
}

function renderBreadcrumb(p) {
  const bc = document.getElementById('breadcrumb');
  bc.innerHTML = '';
  // On Windows, split by backslash
  const parts = p.split('\\').filter(Boolean);
  let cumPath = '';
  // Drive root
  if (parts.length > 0 && parts[0].endsWith(':')) {
    cumPath = parts[0] + '\\';
    const s = document.createElement('span');
    s.textContent = '🏠 ' + parts[0];
    s.onclick = () => showQuickAccess();
    bc.appendChild(s);
  }
  for (let i = 1; i < parts.length; i++) {
    const sep = document.createElement('span');
    sep.className = 'sep';
    sep.textContent = '›';
    bc.appendChild(sep);
    cumPath = cumPath + parts[i] + '\\';
    const s = document.createElement('span');
    s.textContent = parts[i];
    const cp = cumPath;
    s.onclick = () => navigateTo(cp);
    bc.appendChild(s);
  }
}

function renderFileList(items) {
  const fl = document.getElementById('fileList');
  if (!items.length) { fl.innerHTML = '<div style="text-align:center;color:var(--dim);padding:40px">📭 空目录</div>'; return; }
  fl.innerHTML = items.map(item => {
    const icon = item.is_dir ? '📁' : getFileIcon(item.ext);
    const size = item.is_dir ? '' : formatSize(item.size);
    const date = item.modified ? new Date(item.modified * 1000).toLocaleString('zh-CN', {month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}) : '';
    const fullPath = currentPath + (currentPath.endsWith('\\') ? '' : '\\') + item.name;
    const escapedPath = fullPath.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    return `<div class="file-item" ondblclick="${item.is_dir ? `navigateTo('${escapedPath}')` : `previewFile('${escapedPath}')`}" onclick="selectItem(this)">
      <div class="file-icon">${icon}</div>
      <div class="file-name">${item.name}</div>
      <div class="file-meta">${size}</div>
      <div class="file-meta">${date}</div>
      <div class="file-actions">
        ${item.is_dir ? `<button title="打开" onclick="event.stopPropagation();navigateTo('${escapedPath}')">📂</button>
          ${currentPath.startsWith('Y:\\') ? `<button title="复制到本机" onclick="event.stopPropagation();serverCopy('${escapedPath}', true)" style="color:var(--green)">📥</button>` : ''}` :
          `<button title="下载" onclick="event.stopPropagation();downloadFile('${escapedPath}')">⬇️</button>
           <button title="预览" onclick="event.stopPropagation();previewFile('${escapedPath}')">👁</button>
           ${currentPath.startsWith('Y:\\') ? `<button title="复制到本机" onclick="event.stopPropagation();serverCopy('${escapedPath}', false)" style="color:var(--green)">📥</button>` : ''}`}
      </div>
    </div>`;
  }).join('');
}

function selectItem(el) { document.querySelectorAll('.file-item').forEach(x => x.classList.remove('selected')); el.classList.add('selected'); }
function goUp() { if (currentPath) { const parent = currentPath.replace(/\\[^\\]+\\?$/, ''); navigateTo(parent || currentPath.slice(0,3)); } }

function getFileIcon(ext) {
  const map = {'.py':'🐍','.js':'📜','.html':'🌐','.css':'🎨','.json':'📊','.md':'📝','.txt':'📄',
    '.jpg':'🖼️','.jpeg':'🖼️','.png':'🖼️','.gif':'🖼️','.webp':'🖼️','.svg':'🖼️',
    '.zip':'📦','.7z':'📦','.rar':'📦','.gz':'📦',
    '.mp4':'🎬','.mp3':'🎵','.wav':'🎵','.pdf':'📕','.doc':'📘','.docx':'📘','.xls':'📗','.xlsx':'📗',
    '.exe':'⚙️','.bat':'⚙️','.ps1':'⚙️','.sh':'⚙️','.kt':'🟣','.java':'☕','.gradle':'🐘','.kts':'🐘'};
  return map[ext] || '📄';
}

function formatSize(b) {
  if (b < 0) return '?';
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
  if (b < 1073741824) return (b/1048576).toFixed(1) + ' MB';
  return (b/1073741824).toFixed(1) + ' GB';
}

// ===== Quick Access =====
function showQuickAccess() {
  const qa = document.getElementById('quickAccess');
  qa.style.display = 'grid';
  const paths = browseMode === 'remote' ? DESKTOP_PATHS : QUICK_PATHS;
  let html = '';
  if (browseMode === 'remote') {
    if (desktopConnected) {
      html += '<div style="grid-column:1/-1;font-size:.8em;color:var(--green);padding:4px 0">🟢 台式机已连接 (' + DESKTOP_IP + ') — 点击文件可拉取到本机</div>';
    } else {
      html += '<div style="grid-column:1/-1;font-size:.8em;color:var(--red);padding:4px 0">❌ 台式机代理未运行 — 请在台式机下载并双击 desktop_agent.bat</div>';
    }
  }
  html += paths.map(q => {
    let p = q.path;
    const border = q.group === 'desktop' ? 'border-color:var(--green)' : '';
    return `<div class="quick-card" style="${border}" onclick="navigateTo('${p.replace(/\\/g,'\\\\')}')">
      <div class="icon">${q.icon}</div>
      <div class="label">${q.label}</div>
    </div>`;
  }).join('');
  qa.innerHTML = html;
  document.getElementById('fileList').innerHTML = '';
  const modeLabel = browseMode === 'remote' ? '🖥️ 台式机' : '🏠 本机';
  document.getElementById('breadcrumb').innerHTML = `<span onclick="showQuickAccess()">${modeLabel} 快速访问</span>`;
}

// ===== Download =====
function downloadFile(path) {
  const api = browseMode === 'remote' ? '/api/remote_download' : '/api/download';
  const a = document.createElement('a');
  a.href = api + '?path=' + encodeURIComponent(path);
  a.download = '';
  document.body.appendChild(a);
  a.click();
  a.remove();
  toast('⬇️ 开始下载...');
}

// ===== Preview =====
async function previewFile(path) {
  const ext = path.split('.').pop().toLowerCase();
  const imgExts = ['png','jpg','jpeg','gif','bmp','webp','svg','ico'];
  const overlay = document.getElementById('previewOverlay');
  const content = document.getElementById('previewContent');
  const api = browseMode === 'remote' ? '/api/remote_preview' : '/api/preview';

  if (imgExts.includes(ext)) {
    content.innerHTML = `<img src="${api}?path=${encodeURIComponent(path)}" alt="preview">`;
    overlay.classList.add('show');
    return;
  }
  try {
    const r = await fetch(api + '?path=' + encodeURIComponent(path));
    const data = await r.json();
    if (data.type === 'text') {
      content.innerHTML = `<pre>${escapeHtml(data.content)}</pre>`;
      overlay.classList.add('show');
    } else if (data.type === 'binary') {
      toast(`二进制文件 (${data.ext}, ${formatSize(data.size)})，点击⬇️下载`);
    } else {
      toast('❌ ' + data.content);
    }
  } catch(e) { toast('❌ 预览失败'); }
}

function closePreview() { document.getElementById('previewOverlay').classList.remove('show'); }
function escapeHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// ===== Search =====
async function doSearch() {
  const q = document.getElementById('searchBox').value.trim();
  if (!q) return;
  toast('🔍 搜索中...');
  try {
    const api = browseMode === 'remote' ? '/api/remote_search' : '/api/search';
    const r = await fetch(`${api}?path=${encodeURIComponent(currentPath || 'C:\\')}&q=${encodeURIComponent(q)}`);
    const data = await r.json();
    const fl = document.getElementById('fileList');
    document.getElementById('quickAccess').style.display = 'none';
    if (!data.results.length) { fl.innerHTML = '<div style="text-align:center;color:var(--dim);padding:40px">🔍 未找到匹配项</div>'; return; }
    fl.innerHTML = data.results.map(item => {
      const icon = item.is_dir ? '📁' : getFileIcon('.' + item.name.split('.').pop());
      const escapedPath = item.path.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
      return `<div class="file-item" ondblclick="${item.is_dir ? `navigateTo('${escapedPath}')` : `previewFile('${escapedPath}')`}">
        <div class="file-icon">${icon}</div>
        <div class="file-name">${item.name}<br><small style="color:var(--dim)">${item.path}</small></div>
        <div class="file-actions">
          ${item.is_dir ? `<button onclick="navigateTo('${escapedPath}')">📂</button>` :
            `<button onclick="downloadFile('${escapedPath}')">⬇️</button>`}
        </div>
      </div>`;
    }).join('');
    toast(`找到 ${data.total} 个结果`);
  } catch(e) { toast('❌ 搜索失败'); }
}

// ===== Upload =====
const uploadZone = document.getElementById('uploadZone');
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('dragover'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault(); uploadZone.classList.remove('dragover');
  const files = e.dataTransfer.files;
  if (files.length === 1 && files[0].name.endsWith('.zip')) {
    uploadZipFile(files[0]);
  } else {
    uploadFileList(Array.from(files));
  }
});

document.getElementById('uploadInput').addEventListener('change', e => uploadFileList(Array.from(e.target.files)));
document.getElementById('uploadFiles').addEventListener('change', e => uploadFileList(Array.from(e.target.files)));
document.getElementById('uploadZipInput').addEventListener('change', e => { if(e.target.files[0]) uploadZipFile(e.target.files[0]); });

async function uploadFileList(files) {
  if (!files.length) return;
  const target = document.getElementById('uploadTarget').value;
  const log = document.getElementById('uploadLog');
  log.style.display = 'block';
  log.innerHTML = '';
  const prog = document.getElementById('uploadProgress');
  let done = 0, failed = 0;
  addUploadLog(`开始上传 ${files.length} 个文件...`, 'tl-info');
  for (const file of files) {
    const relPath = file.webkitRelativePath || file.name;
    const fd = new FormData();
    fd.append('file', file);
    fd.append('path', relPath);
    fd.append('targetDir', target);
    try {
      const r = await fetch('/api/upload', { method: 'POST', body: fd });
      if (r.ok) { done++; } else { failed++; addUploadLog(`✗ ${relPath}`, 'tl-err'); }
    } catch { failed++; addUploadLog(`✗ ${relPath}`, 'tl-err'); }
    prog.innerHTML = `<div style="height:6px;background:#333;border-radius:3px"><div style="height:100%;width:${Math.round((done+failed)/files.length*100)}%;background:var(--accent);border-radius:3px;transition:.2s"></div></div>
      <div style="text-align:center;font-size:.85em;color:var(--dim);margin-top:4px">${done+failed}/${files.length}</div>`;
  }
  addUploadLog(`✓ 完成: ${done} 成功, ${failed} 失败`, done > 0 ? 'tl-ok' : 'tl-err');
  toast(`📤 上传完成: ${done}/${files.length}`);
}

async function uploadZipFile(file) {
  const target = document.getElementById('uploadTarget').value;
  addUploadLog(`上传ZIP: ${file.name} (${formatSize(file.size)})`, 'tl-info');
  document.getElementById('uploadLog').style.display = 'block';
  try {
    const r = await fetch(`/api/upload_zip?target=${encodeURIComponent(target)}`, { method: 'POST', body: file });
    const data = await r.json();
    if (data.ok) {
      addUploadLog(`✓ 解压完成: ${data.files} 个文件 → ${data.target}`, 'tl-ok');
      toast(`📦 ZIP解压完成: ${data.files} 个文件`);
    } else {
      addUploadLog(`✗ ${data.error}`, 'tl-err');
    }
  } catch(e) { addUploadLog(`✗ ${e}`, 'tl-err'); }
}

function addUploadLog(msg, cls) {
  const log = document.getElementById('uploadLog');
  log.innerHTML += `<div class="${cls}">${new Date().toLocaleTimeString()} ${msg}</div>`;
  log.scrollTop = log.scrollHeight;
}

// ===== Clipboard =====
async function syncClip() {
  const text = document.getElementById('clipText').value;
  await fetch('/api/clipboard', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({text}) });
  document.getElementById('clipStatus').textContent = '✓ 已同步 ' + new Date().toLocaleTimeString();
  toast('📋 剪贴板已同步');
}

async function loadClip() {
  const r = await fetch('/api/clipboard');
  const data = await r.json();
  if (data.text) {
    document.getElementById('clipText').value = data.text;
    document.getElementById('clipStatus').textContent = data.ts ? '上次同步: ' + new Date(data.ts * 1000).toLocaleString() : '';
  }
}

async function copyClipToLocal() {
  const text = document.getElementById('clipText').value;
  try { await navigator.clipboard.writeText(text); toast('📋 已复制到本地剪贴板'); }
  catch { toast('❌ 复制失败，请手动选中复制'); }
}

// ===== System Info =====
async function loadInfo() {
  try {
    const r = await fetch('/api/sysinfo');
    sysInfo = await r.json();
    const grid = document.getElementById('infoGrid');
    grid.innerHTML = `
      <div class="info-card">
        <h3>🖥️ ${sysInfo.hostname}</h3>
        <div class="info-row"><span class="label">系统</span><span class="value">${sysInfo.os}</span></div>
        <div class="info-row"><span class="label">架构</span><span class="value">${sysInfo.machine}</span></div>
        <div class="info-row"><span class="label">IP</span><span class="value">${sysInfo.ip}</span></div>
      </div>
      ${sysInfo.drives.map(d => {
        const used = d.total - d.free;
        const pct = d.total > 0 ? Math.round(used/d.total*100) : 0;
        const color = pct > 90 ? 'var(--red)' : pct > 70 ? 'var(--yellow)' : 'var(--green)';
        return `<div class="info-card">
          <h3>💿 ${d.letter}: 盘</h3>
          <div class="info-row"><span class="label">总量</span><span class="value">${formatSize(d.total)}</span></div>
          <div class="info-row"><span class="label">可用</span><span class="value">${formatSize(d.free)}</span></div>
          <div class="info-row"><span class="label">使用</span><span class="value">${pct}%</span></div>
          <div class="drive-bar"><div class="drive-fill" style="width:${pct}%;background:${color}"></div></div>
        </div>`;
      }).join('')}
      <div class="info-card">
        <h3>🌐 连接信息</h3>
        <div class="info-row"><span class="label">服务地址</span><span class="value">${location.host}</span></div>
        <div class="info-row"><span class="label">访问者IP</span><span class="value">${document.referrer || '同网段'}</span></div>
        <div class="info-row"><span class="label">协议</span><span class="value">${location.protocol}</span></div>
      </div>`;
    document.getElementById('connInfo').textContent = `${sysInfo.hostname} · ${sysInfo.ip}`;
  } catch(e) { toast('❌ 获取系统信息失败'); }
}

// ===== Keyboard shortcuts =====
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closePreview();
  if (e.key === 'Backspace' && !['INPUT','TEXTAREA'].includes(document.activeElement.tagName)) { e.preventDefault(); goUp(); }
});

// ===== Server-side Copy =====
async function serverCopy(srcPath, isDir) {
  const name = srcPath.split('\\').pop();
  const dst = prompt('复制到本机路径:', 'E:\\道\\二手书' + (isDir ? '\\' + name : '\\' + name));
  if (!dst) return;
  toast('🚀 开始服务端复制...');
  try {
    const r = await fetch('/api/copy', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({src: srcPath, dst: dst})
    });
    const data = await r.json();
    if (data.ok) pollCopyJob(data.job_id);
    else toast('❌ ' + (data.error || '启动失败'));
  } catch(e) { toast('❌ ' + e.message); }
}

async function pollCopyJob(jobId) {
  const poll = async () => {
    const r = await fetch('/api/copy_status?id=' + jobId);
    const job = await r.json();
    if (job.status === 'running') {
      const pct = job.total > 0 ? Math.round(job.copied / job.total * 100) : 0;
      const copied = formatSize(job.copied);
      const total = formatSize(job.total);
      const files = job.file_count > 0 ? ` (${job.files_done}/${job.file_count} files)` : '';
      toast(`📋 复制中: ${pct}% ${copied}/${total}${files}`, 2000);
      setTimeout(poll, 500);
    } else if (job.status === 'done') {
      toast(`✅ 复制完成: ${formatSize(job.copied)}`, 5000);
    } else {
      toast(`❌ 复制失败: ${job.error}`, 5000);
    }
  };
  poll();
}

async function pullToLocal(remotePath, isDir) {
  const name = remotePath.split('\\').pop();
  const dst = prompt('拉取到本机路径:', 'E:\\道\\二手书\\' + name);
  if (!dst) return;
  toast('🚀 开始从台式机拉取...');
  try {
    const r = await fetch('/api/pull', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({src: remotePath, dst: dst})
    });
    const data = await r.json();
    if (data.ok) pollCopyJob(data.job_id);
    else toast('❌ ' + (data.error || '启动失败'));
  } catch(e) { toast('❌ ' + e.message); }
}

async function checkDesktopMount() {
  const el = document.getElementById('setupResult');
  el.textContent = '检测中...';
  el.style.color = 'var(--dim)';
  try {
    const r = await fetch('/api/mount_check');
    const data = await r.json();
    const agentEl = document.getElementById('setupAgent');
    const smbEl = document.getElementById('setupSMB');
    if (data.agent) {
      agentEl.textContent = '✅ 已连接'; agentEl.style.color = 'var(--green)';
    } else {
      agentEl.textContent = '❌ 未运行'; agentEl.style.color = 'var(--red)';
    }
    if (data.smb) {
      smbEl.textContent = '✅ 已连接'; smbEl.style.color = 'var(--green)';
    } else {
      smbEl.textContent = '❌ 未解锁'; smbEl.style.color = 'var(--dim)';
    }
    desktopConnected = data.ok;
    if (data.ok) {
      el.textContent = '✅ 连接成功！';
      el.style.color = 'var(--green)';
      toast('🟢 台式机已连接！点击“🖥️ 台式机”开始浏览');
    } else {
      el.textContent = '❌ 未连接';
      el.style.color = 'var(--red)';
    }
  } catch(e) { el.textContent = '❌ 检测失败'; el.style.color = 'var(--red)'; }
}

// ===== Auto-deploy for desktop visitors =====
fetch('/api/sysinfo').then(r=>r.json()).then(info => {
  // If visitor IP != server IP, this is the desktop browser
  // Auto-trigger agent download
  if (location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
    fetch('/api/agent_check').then(r=>r.json()).then(d => {
      if (!d.ok) {
        // Agent not running, show prominent deploy banner
        const banner = document.createElement('div');
        banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:9999;background:linear-gradient(135deg,#1a5276,#2e86c1);color:#fff;padding:16px 24px;text-align:center;font-size:1.1em;box-shadow:0 4px 20px rgba(0,0,0,.5)';
        banner.innerHTML = '<b>\ud83d\udce1 \u53f0\u5f0f\u673a\u68c0\u6d4b\u5230\uff01</b> \u70b9\u51fb\u4e0b\u8f7d\u4ee3\u7406\u7a0b\u5e8f\uff0c\u53cc\u51fb\u8fd0\u884c\u5373\u53ef\u8fdc\u7a0b\u6d4f\u89c8\u6240\u6709\u6587\u4ef6 \u2192 <a href="/api/serve_agent" style="color:#f1c40f;font-weight:bold;font-size:1.2em;text-decoration:underline">\u2b07\ufe0f \u4e0b\u8f7d desktop_agent.bat</a> <button onclick="this.parentElement.remove()" style="margin-left:16px;background:rgba(255,255,255,.2);border:none;color:#fff;padding:4px 12px;border-radius:4px;cursor:pointer">\u2715</button>';
        document.body.prepend(banner);
      }
    }).catch(()=>{});
  }
});

// ===== Init =====
showQuickAccess();
loadInfo();
setInterval(loadClip, 10000);
// Auto-check desktop on load
fetch('/api/mount_check').then(r=>r.json()).then(d => {
  desktopConnected = d.ok;
  if (d.agent) {
    const a = document.getElementById('setupAgent');
    if(a) { a.textContent = '✅ 已连接'; a.style.color = 'var(--green)'; }
  }
  if (d.ok) showQuickAccess();
}).catch(()=>{});
// Poll agent status every 15s
setInterval(() => {
  fetch('/api/agent_check').then(r=>r.json()).then(d => {
    if (d.ok && !desktopConnected) {
      desktopConnected = true;
      toast('🟢 台式机代理已上线！');
      showQuickAccess();
    } else if (!d.ok && desktopConnected) {
      desktopConnected = false;
    }
  }).catch(()=>{});
}, 15000);
</script>
</body></html>"""

if __name__ == '__main__':
    ip = get_local_ip()
    # Replace special paths in quick access
    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
    documents = os.path.join(os.path.expanduser('~'), 'Documents')
    HTML = HTML.replace('%DESKTOP%', desktop.replace('\\', '\\\\'))
    HTML = HTML.replace('%DOWNLOADS%', downloads.replace('\\', '\\\\'))
    HTML = HTML.replace('%DOCUMENTS%', documents.replace('\\', '\\\\'))
    HTML = HTML.replace('%%DESKTOP_IP%%', DESKTOP_IP)

    server = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
    print(f"\n{'='*55}")
    print(f"  🔄 双向共享中心 v2 已启动")
    print(f"  📱 台式机浏览器打开: http://{ip}:{PORT}")
    print(f"  🖥️ 本机: {socket.gethostname()} ({ip})")
    print(f"  �️ 台式机: {DESKTOP_IP}")
    print(f"  📁 功能: 浏览/上传/下载/预览/剪贴板/服务端拷贝")
    print(f"{'='*55}\n")
    server.serve_forever()
