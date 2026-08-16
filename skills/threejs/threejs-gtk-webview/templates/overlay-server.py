#!/usr/bin/env python3
"""HTTP server for CSS-only launcher or Three.js/Canvas2D overlay scenes."""
import http.server, os, json, subprocess

PORT = 8765
HTML_DIR = os.path.dirname(os.path.abspath(__file__))

class LauncherHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HTML_DIR, **kwargs)
    
    def log_message(self, format, *args): pass
    
    def translate_path(self, path):
        if path == '/' or not os.path.isfile(os.path.join(self.directory, path.lstrip('/'))):
            return os.path.join(self.directory, 'allmind-launcher.html')
        return super().translate_path(path)
    
    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        
        if self.path.startswith('/launch'):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            name = params.get('name', [''])[0]
            exec_cmd = params.get('exec', [''])[0]
            
            print(f"[Launcher] Launch request: {name} ({exec_cmd})")
            
            if name and exec_cmd:
                # CRITICAL: Use setsid + start_new_session to detach the launched app
                subprocess.Popen(
                    ['setsid', 'sh', '-c', exec_cmd],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
            # CRITICAL: Exit server to close Chromium and return to Waybar
            os._exit(0)
            
        elif self.path.startswith('/select'):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            print(f"[Launcher] Selected: {params.get('name', [''])[0]} (idx {params.get('index', [''])[0]})")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
            
        elif self.path == '/apps':
            # Return app list as JSON — customize this for your launcher
            apps = [
                {'name': 'Chromium', 'exec': 'chromium-browser'},
                {'name': 'Terminal', 'exec': 'lxterminal'},
                {'name': 'Files', 'exec': 'pcmanfm'},
                # Add more apps here
            ]
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'apps': apps}).encode())
            
        elif self.path == '/close':
            print("[Launcher] Close requested")
            os._exit(0)
            
        else:
            super().do_GET()

if __name__ == '__main__':
    server = http.server.HTTPServer(('127.0.0.1', PORT), LauncherHandler)
    print(f"[Launcher] Serving at http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
