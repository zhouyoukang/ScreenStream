@echo off
chcp 65001 >nul
title 文件共享代理 - 台式机端
echo ============================================
echo   台式机文件共享代理
echo   双击即可，笔记本自动连接
echo ============================================
echo.

:: Check if Python is available
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [!] Python未安装，使用PowerShell方案...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$port=9998; $listener=[System.Net.HttpListener]::new(); $listener.Prefixes.Add('http://+:$port/'); $listener.Start(); Write-Host '代理已启动: http://localhost:$port'; while($listener.IsListening){$ctx=$listener.GetContext(); $req=$ctx.Request; $resp=$ctx.Response; $path=$req.Url.AbsolutePath; try{ if($path -eq '/api/agent_status'){$j='{\"ok\":true,\"hostname\":\"'+$env:COMPUTERNAME+'\"}'; $b=[Text.Encoding]::UTF8.GetBytes($j); $resp.ContentType='application/json'; $resp.OutputStream.Write($b,0,$b.Length)} elseif($path -eq '/api/agent_list'){$q=[Web.HttpUtility]::ParseQueryString($req.Url.Query); $dir=$q['path']; if(!$dir){$dir='C:\'}; $items=@(); Get-ChildItem $dir -ErrorAction SilentlyContinue|ForEach-Object{$items+=@{name=$_.Name;is_dir=$_.PSIsContainer;size=if($_.PSIsContainer){0}else{$_.Length};modified=[int](Get-Date $_.LastWriteTime -UFormat '%%s');ext=$_.Extension.ToLower()}}; $j=ConvertTo-Json @{path=$dir;items=$items;parent=Split-Path $dir} -Compress; $b=[Text.Encoding]::UTF8.GetBytes($j); $resp.ContentType='application/json'; $resp.OutputStream.Write($b,0,$b.Length)} elseif($path -eq '/api/agent_download'){$q=[Web.HttpUtility]::ParseQueryString($req.Url.Query); $f=$q['path']; $b=[IO.File]::ReadAllBytes($f); $resp.ContentType='application/octet-stream'; $resp.Headers.Add('Content-Disposition','attachment'); $resp.OutputStream.Write($b,0,$b.Length)} }catch{$e='{\"error\":\"'+$_.Exception.Message+'\"}'; $b=[Text.Encoding]::UTF8.GetBytes($e); $resp.StatusCode=500; $resp.OutputStream.Write($b,0,$b.Length)} finally{$resp.Close()}}"
    goto :end
)

:: Python version (cleaner, more robust)
python -c "
import http.server, os, json, urllib.parse, socket, shutil, mimetypes

PORT = 9998

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        path = p.path
        qs = urllib.parse.parse_qs(p.query)
        if path == '/api/agent_status':
            self._j({'ok': True, 'hostname': socket.gethostname(), 'ip': self._ip()})
        elif path == '/api/agent_list':
            dp = qs.get('path', ['C:\\\\'])[0]
            items = []
            try:
                for n in os.listdir(dp):
                    fp = os.path.join(dp, n)
                    try:
                        st = os.stat(fp)
                        items.append({'name':n,'is_dir':os.path.isdir(fp),'size':st.st_size if not os.path.isdir(fp) else 0,'modified':int(st.st_mtime),'ext':os.path.splitext(n)[1].lower() if not os.path.isdir(fp) else ''})
                    except: items.append({'name':n,'is_dir':False,'size':-1,'modified':0,'ext':''})
            except: pass
            items.sort(key=lambda x:(not x['is_dir'],x['name'].lower()))
            self._j({'path':dp,'items':items,'parent':os.path.dirname(dp)})
        elif path == '/api/agent_download':
            fp = qs.get('path',[''])[0]
            if os.path.isfile(fp):
                sz = os.path.getsize(fp)
                mime = mimetypes.guess_type(fp)[0] or 'application/octet-stream'
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', sz)
                self.send_header('Content-Disposition', 'attachment; filename=\"'+os.path.basename(fp)+'\"')
                self.send_header('Access-Control-Allow-Origin','*')
                self.end_headers()
                with open(fp,'rb') as f: shutil.copyfileobj(f, self.wfile)
            else: self.send_error(404)
        elif path == '/api/agent_preview':
            fp = qs.get('path',[''])[0]
            ext = os.path.splitext(fp)[1].lower()
            txt_exts = {'.txt','.md','.py','.js','.html','.css','.json','.xml','.yml','.yaml','.kt','.java','.sh','.bat','.ps1','.cfg','.ini','.toml','.csv','.log','.kts','.sql','.gitignore'}
            if ext in txt_exts:
                try:
                    with open(fp,'r',encoding='utf-8',errors='replace') as f: content=f.read(100000)
                    self._j({'type':'text','content':content,'size':os.path.getsize(fp),'ext':ext})
                except: self._j({'type':'error','content':'Cannot read'})
            else: self._j({'type':'binary','size':os.path.getsize(fp) if os.path.isfile(fp) else 0,'ext':ext})
        elif path == '/api/agent_search':
            dp = qs.get('path',['C:\\\\'])[0]
            q = qs.get('q',[''])[0].lower()
            results = []; count = 0
            try:
                for dirpath, dirnames, filenames in os.walk(dp):
                    dirnames[:] = [d for d in dirnames if d not in ('.git','node_modules','__pycache__','.cache')]
                    for n in filenames:
                        if q in n.lower():
                            results.append({'name':n,'path':os.path.join(dirpath,n),'is_dir':False})
                            count += 1
                            if count >= 50: break
                    if count >= 50: break
            except: pass
            self._j({'results':results,'total':count})
        elif path == '/api/agent_sysinfo':
            drives = []
            for letter in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
                p2 = f'{letter}:\\\\'
                if os.path.exists(p2):
                    try:
                        t,u,f2 = shutil.disk_usage(p2)
                        drives.append({'letter':letter,'total':t,'free':f2})
                    except: pass
            self._j({'hostname':socket.gethostname(),'ip':self._ip(),'drives':drives})
        else: self.send_error(404)
    def _j(self, obj):
        d = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',len(d))
        self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers()
        self.wfile.write(d)
    def _ip(self):
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try: s.connect(('8.8.8.8',80)); return s.getsockname()[0]
        except: return '127.0.0.1'
        finally: s.close()
    def log_message(self,fmt,*a): pass

srv = http.server.HTTPServer(('0.0.0.0', PORT), H)
ip = H(None,None,None)._ip() if False else socket.gethostname()
print(f'台式机代理已启动: http://0.0.0.0:{PORT}')
print(f'笔记本将自动发现此服务')
print(f'关闭此窗口即可停止')
srv.serve_forever()
"

:end
echo.
echo 代理已停止
pause
