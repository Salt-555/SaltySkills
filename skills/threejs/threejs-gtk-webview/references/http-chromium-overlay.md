# HTTP Server + Chromium Kiosk Overlay Pattern (Wayland)

When GTK+WebKit2 per-pixel alpha fails on Wayland (horizontal banding/gaps), use this pattern instead. Proven working on Pi 5 with labwc/Wayland at 800x480 DSI-1.

## Architecture

```
Python HTTP Server (localhost:8765)
  └── Serves allmind-launcher.html (Three.js scene + Canvas2D fallback)
  
Chromium Kiosk (--ozone-platform=wayland --kiosk)
  └── Loads http://127.0.0.1:8765
  └── Fullscreen overlay, no decorations
  
Communication via HTTP GET requests (fetch API in JS):
  - /select?index=N&name=X → selection change notification
  - /launch?name=X&exec=Y → launch app command
  - /close → close launcher
```

## Launcher Script (`allmind-launcher`)

```bash
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCK_FILE="$HOME/.cache/allmind-launcher.lock"

# Check if already running
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE" 2>/dev/null)
    kill -0 "$PID" 2>/dev/null && exit 0
fi

mkdir -p "$HOME/.cache"
echo $$ > "$LOCK_FILE"

# Kill existing server on port 8765
fuser -k 8765/tcp 2>/dev/null || true

# Start HTTP server (with Wayland env)
export WAYLAND_DISPLAY=wayland-0
cd "$SCRIPT_DIR"
python3 allmind-launcher-server.py &
SERVER_PID=$!
sleep 0.5

# Launch Chromium in kiosk mode on Wayland
env WAYLAND_DISPLAY=wayland-0 /usr/lib/chromium/chromium \
    --ozone-platform=wayland \
    --use-angle=gles \
    --kiosk \
    --no-first-run \
    --disable-features=TranslateUI \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-popup-blocking \
    --disable-translate \
    http://127.0.0.1:8765 &

wait $SERVER_PID 2>/dev/null
rm -f "$LOCK_FILE"
```

## Server (`allmind-launcher-server.py`)

Minimal HTTP server serving HTML + handling commands:

```python
import http.server, os, json, subprocess, signal

PORT = 8765
HTML_DIR = os.path.dirname(os.path.abspath(__file__))

class LauncherHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HTML_DIR, **kwargs)
    
    def log_message(self, format, *args): pass
    
    def translate_path(self, path):
        # Serve allmind-launcher.html for root/unknown paths
        if path == '/' or not os.path.isfile(os.path.join(self.directory, path.lstrip('/'))):
            return os.path.join(self.directory, 'allmind-launcher.html')
        return super().translate_path(path)
    
    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        
        if self.path == '/launch':
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            name = params.get('name', [''])[0]
            exec_cmd = params.get('exec', [''])[0]
            if name and exec_cmd:
                subprocess.Popen(['sh', '-c', exec_cmd])
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
            
        elif self.path == '/select':
            # Selection change notification (log only)
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            print(f"[Launcher] Selected: {params.get('name', [''])[0]}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
            
        elif self.path == '/close':
            os._exit(0)  # Kill server → Chromium closes
            
        else:
            super().do_GET()

if __name__ == '__main__':
    http.server.HTTPServer(('127.0.0.1', PORT), LauncherHandler).serve_forever()
```

## HTML Scene Notes

- **Three.js CDN**: `https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js` (or bundle locally)
- **Cursor visibility**: Use `cursor: default` on body, NOT `cursor: none`. Canvas should have `pointer-events: none` so cursor passes through to underlying elements.
- **Resolution-aware layout**: Compute all positions from `window.innerWidth/Height` via a `computeLayout(w, h)` function — never hardcode pixel coords.
- **HTTP communication**: Use `fetch()` for all JS→Python messages (selection, launch, close). No WebKit2 message handlers needed.

## Pitfalls

1. **Chromium reuses existing session** — if you see old content, Chromium may be loading from cache or an existing window. Kill all chromium processes before testing: `pkill -f chromium`.
2. **Wayland display socket** — Chromium needs `WAYLAND_DISPLAY=wayland-0` explicitly set in the env when launching from a script (it won't inherit from your shell session).
3. **Port conflicts** — always kill existing listeners on port 8765 before starting: `fuser -k 8765/tcp`.
4. **Three.js local copy** — for offline reliability, download Three.js to the same directory as the HTML and reference it locally instead of via CDN.
