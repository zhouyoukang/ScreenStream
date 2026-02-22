import http.server, json, os, urllib.parse, sys

DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '文档')
VIEWER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'md-viewer.html')

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            with open(VIEWER_PATH, 'rb') as f:
                self.wfile.write(f.read())
        elif parsed.path == '/api/files':
            files = sorted([f for f in os.listdir(DOCS_DIR) if f.endswith('.md')])
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(files).encode())
        elif parsed.path == '/api/read':
            qs = urllib.parse.parse_qs(parsed.query)
            fname = qs.get('file', [''])[0]
            fpath = os.path.join(DOCS_DIR, fname)
            if os.path.isfile(fpath) and fname.endswith('.md'):
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                with open(fpath, 'r', encoding='utf-8') as f:
                    self.wfile.write(f.read().encode())
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, format, *args):
        pass

print(f"Docs viewer at http://localhost:8877", flush=True)
http.server.HTTPServer(('127.0.0.1', 8877), Handler).serve_forever()
