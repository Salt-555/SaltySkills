---
name: threejs-gtk-webview
description: Build GPU-accelerated UI overlays on Raspberry Pi 5 using GTK3 + WebKit2 WebView with Three.js scenes. Covers the full pattern for animated menus, visualizations, and interactive WebGL interfaces on Wayland.
triggers:
  - gtk webkit threejs overlay
  - pi5 gpu accelerated ui
  - wayland animated menu
  - webview gtk python
  - threejs raspberry pi
  - gtk3 webgl overlay
  - chromium kiosk overlay wayland
  - http server overlay pi5
  - radial app launcher wayland
---

# Three.js + GTK WebView UI Overlays on Pi 5

Build GPU-accelerated interactive overlays (radial menus, visualizations) using GTK3 + WebKit2 WebView with embedded Three.js scenes. VideoCore VII handles WebGL natively on Pi 5.

## ⚠️ CRITICAL: Wayland Compatibility — Use HTTP+Chromium Instead

**GTK per-pixel alpha compositing does NOT work reliably on Wayland.** When you set `app_paintable(True)` + `rgba_visual`, the compositor produces horizontal banding/gaps every few pixels across the entire window. This is a fundamental Wayland compositor limitation, not a bug you can fix with sizing tweaks or transparency hacks.

**The reliable pattern for Pi 5 Wayland overlays:**
1. Python HTTP server serves the HTML/JS scene on localhost (e.g., port 8765)
2. Launch Chromium in kiosk mode pointing to `http://127.0.0.1:8765`
3. Use `--ozone-platform=wayland --kiosk` flags

This approach works because Chromium is a native Wayland compositor client — no GTK transparency layer, no per-pixel alpha issues. Three.js runs fine in Chromium's GPU pipeline on VideoCore VII.

**When to use GTK+WebKit2:** Only on X11 (Xorg) sessions where the compositor handles alpha correctly. On Wayland (labwc, sway, etc.), skip GTK entirely and use the HTTP+Chromium pattern documented in `references/http-chromium-overlay.md`.

## Architecture

```
GTK Window (POPUP + DOCK type, full-screen)
  └── WebKit2.WebView
        ├── Local HTML file with Three.js scene
        └── JS ↔ Python bridge via UserContentManager script messages
```

**Why this approach:** Pure Cairo drawing is CPU-bound and limited for complex animations. Three.js runs on the GPU, giving smooth 60fps particle systems, fog, bloom effects — even on Pi 5's VideoCore VII.

## Installation

```bash
sudo apt-get install -y gir1.2-webkit2-4.1
```

~50MB package providing GI bindings for WebKitGTK 4.1.

## CRITICAL: WebKit2 GTK3 API Quirks

The `gir1.2-webkit2-4.1` GI bindings are NOT what you'd expect from the JS/Web APIs. These gotchas will break your code:

### 1. No UserContentController — Use UserContentManager
```python
# WRONG (this class doesn't exist in gi bindings):
controller = WebKit2.UserContentController.new()

# CORRECT:
manager = WebKit2.UserContentManager.new()
manager.register_script_message_handler('allmind')  # Register BEFORE creating WebView
```

### 2. Construction Order Matters
```python
# WRONG — construct-only property error if you try to set manager after:
web_view = WebKit2.WebView.new_with_settings(settings)
web_view.set_user_content_manager(manager)  # AttributeError!

# WRONG — can't set user-content-manager property after construction:
web_view = WebKit2.WebView.new()
web_view.set_property('user-content-manager', manager)  # Warning + ignored

# CORRECT:
manager = WebKit2.UserContentManager.new()
manager.register_script_message_handler('allmind')
web_view = WebKit2.WebView.new_with_user_content_manager(manager)
settings = WebKit2.Settings.new()
settings.set_enable_javascript(True)
web_view.set_settings(settings)  # set_settings() works AFTER construction
```

### 3. Settings Use Individual Setters, NOT set_property
```python
# WRONG:
settings.set_property('javascript-enabled', True)  # AttributeError!

# CORRECT:
settings.set_enable_javascript(True)
settings.set_enable_developer_extras(False)
```

### 4. Signal Connection for Messages
```python
manager = WebKit2.UserContentManager.new()
manager.connect('script-message-received', self.on_message)
```

The callback receives `(manager, message)` where `message` is a `JavascriptResult`. Extract the payload via:
```python
def on_message(self, manager, message):
    data = json.loads(message.get_js_value().to_string())  # NOT .get_string()!
```

**Critical**: `message.get_string()` does NOT exist on `JavascriptResult` — it raises `'JavascriptResult' object has no attribute 'get_string'`. Always use `.get_js_value().to_string()`.

## Python Wrapper Skeleton

```python
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, Gdk, WebKit2, GLib

class OverlayWindow(Gtk.Window):
    def __init__(self):
        super().__init__()  # top-level (POPUP unreliable on Wayland)
        
        # Get actual display size — Wayland-compatible
        display = Gdk.Display.get_default()
        if display:
            monitor = display.get_monitor(0)
            w, h = monitor.get_geometry().width, monitor.get_geometry().height if monitor else (800, 480)
        else:
            w, h = 800, 480
        
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_default_size(w, h)
        self.move(0, 0)
        
        # Transparent background for overlay effect
        screen_gdk = self.get_screen()
        visual = screen_gdk.get_rgba_visual()
        if visual:
            self.set_visual(visual)
        
        # WM_CLASS for labwc window rules (Wayland app_id matching)
        self.set_wmclass("my-overlay", "my-overlay")
        
        # WebKit2 setup
        self.content_manager = WebKit2.UserContentManager.new()
        self.content_manager.connect('script-message-received', self.on_message)
        self.content_manager.register_script_message_handler('bridge')
        
        self.settings = WebKit2.Settings.new()
        self.settings.set_enable_javascript(True)
        
        self.web_view = WebKit2.WebView.new_with_user_content_manager(self.content_manager)
        self.web_view.set_settings(self.settings)
        self.add(self.web_view)
        
        # Load local HTML with cache-busting (prevents stale content)
        import time
        cache_bust = int(time.time() * 1000)
        html_url = f'file://{os.path.dirname(__file__)}/scene.html?v={cache_bust}'
        self.web_view.load_uri(html_url)
    
    def on_message(self, manager, message):
        import json
        data = json.loads(message.get_js_value().to_string())  # NOT .get_string()!
        action = data.get('action')
        if action == 'do_something':
            self.handle_action(data)
```

## JavaScript Side — Message Bridge

In your Three.js HTML file:

```javascript
// Send message to Python
window.webkit.messageHandlers.bridge.postMessage(JSON.stringify({
    action: 'user_clicked',
    data: { x: 100, y: 200 }
}));

// Receive messages from Python (optional)
function pythonCallback(data) {
    // Handle updates pushed from Python
}
```

## Three.js Scene Setup for Pi 5

### Performance Constraints on Pi 5
- **VideoCore VII** handles WebGL fine but has limited VRAM (~256MB shared with RAM)
- Keep polygon counts low — use simple geometries, avoid complex shaders
- Particle systems: 500-1000 particles is comfortable; 2000+ may stutter
- Fog + additive blending = cheap depth illusion without heavy geometry
- Avoid post-processing passes (bloom, SSAO) — they're GPU-heavy on VideoCore VII

### Recommended Scene Pattern
```javascript
// Dark void with fog (cheap depth cueing)
scene.background = new THREE.Color(0x050510);
scene.fog = new THREE.Fog(0x050510, 8, 35);

// Grid floor for spatial reference
const grid = new THREE.GridHelper(60, 40, 0x1a3a5c, 0x1a3a5c);
grid.material.opacity = 0.4;
grid.material.transparent = true;

// Floating particles (additive blending = glow without post-processing)
const particleGeo = new THREE.BufferGeometry();
particleGeo.setAttribute('position', /* Float32Array */);
const particleMat = new THREE.PointsMaterial({
    size: 0.06,
    vertexColors: true,
    transparent: true,
    opacity: 0.6,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
});

// Minimal lighting — emissive materials do the work
const ambient = new THREE.AmbientLight(0x1a2a3a, 0.5);
scene.add(ambient);
```

### CSS Overlay for Scanlines/Vignette
Three.js renders to a canvas element. Add HTML overlays on top for CRT effects:

```css
#scanlines {
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    pointer-events: none; z-index: 10;
    background: repeating-linear-gradient(
        0deg, transparent, transparent 2px,
        rgba(0, 0, 0, 0.15) 2px, rgba(0, 0, 0, 0.15) 4px
    );
}

#vignette {
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    pointer-events: none; z-index: 9;
    background: radial-gradient(ellipse at center, transparent 50%, rgba(5,5,16,0.8) 100%);
}
```

## Canvas2D Fallback (When WebGL Fails)

If the scene renders as **scanlines with background visible between them**, WebGL has context loss on VideoCore VII. This is NOT a sizing issue — it's the GPU context being dropped mid-frame. The fix: switch to pure Canvas2D, which is CPU-rendered and guaranteed to work.

### Diagnostic
- ✅ Background visible between scan lines = WebGL partial render (context loss)
- ❌ Completely black screen = WebView not loading or JS error
- ❌ Stretched/distorted scene = canvas sizing issue (not WebGL)

### Canvas2D Scene Pattern
Canvas2D can achieve the same PS2 memory card aesthetic without any GPU dependency:

```javascript
// Create canvas element directly in JS
const canvas = document.createElement('canvas');
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;
document.body.insertBefore(canvas, scanlinesOverlay);
const ctx = canvas.getContext('2d');

// Draw grid floor (perspective lines)
ctx.strokeStyle = '#1a3a5c';
ctx.lineWidth = 1;
for (let y = cy; y < h; y += 30) {
    const perspective = (y - cy) / (h - cy);
    ctx.globalAlpha = 0.1 + perspective * 0.2;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
}

// Draw icon cards as rounded rectangles with glow
function drawIconCard(x, y, size, isSelected) {
    const halfSize = size / 2;
    
    // Glow via shadowBlur (CPU-drawn, no GPU context needed)
    if (isSelected) {
        ctx.shadowColor = '#7ac4ff';
        ctx.shadowBlur = 20;
    }
    
    // Card body
    ctx.fillStyle = 'rgba(5, 5, 16, 0.8)';
    drawRoundedRect(ctx, x - halfSize, y - halfSize, size, size, 4);
    ctx.fill();
    
    // Border
    ctx.strokeStyle = isSelected ? '#7ac4ff' : '#4a9eff';
    ctx.lineWidth = isSelected ? 2 : 1.5;
    drawRoundedRect(ctx, x - halfSize, y - halfSize, size, size, 4);
    ctx.stroke();
    
    ctx.shadowBlur = 0;
}

function drawRoundedRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
}

// Animation loop — same pattern as Three.js
function animate() {
    requestAnimationFrame(animate);
    
    // Clear and redraw entire frame each iteration
    ctx.fillStyle = '#050510';
    ctx.fillRect(0, 0, w, h);
    
    drawGrid(w, h);
    updateAndDrawParticles();
    drawAllIcons();
}
```

### Canvas2D Performance Notes
- **60fps is achievable** on Pi 5 for scenes with <100 objects (icons + particles)
- Use `requestAnimationFrame` — same as Three.js, but no GPU context to lose
- `shadowBlur` works in Canvas2D and provides glow effects without post-processing
- Avoid heavy compositing operations; keep draw calls minimal per frame
- For particle systems, use simple rectangles (`fillRect`) instead of circles for better CPU performance

## Debugging Checklist

When the launcher shows garbage or doesn't render:

1. **Kill stale processes**: `pkill -f "allmind-launcher"` — old instances may hold locks
2. **Clear WebKit cache**: `rm -rf ~/.cache/WebKit*` — prevents serving stale HTML
3. **Check for WebGL context loss**: background visible between scanlines = switch to Canvas2D
4. **Verify canvas sizing**: check that `canvas.width === window.innerWidth` in JS console
5. **Test in Chromium first**: open the HTML file directly in Chromium (`chromium-browser file:///path/to/scene.html`) — if it works there but not in launcher, the issue is GTK/WebView integration, not the scene itself
- `webview-gtk4` — future migration path when GTK4 + WebKit6 bindings become available on Pi OS Bookworm

## Reference Files
- `references/webgl-context-loss.md` — diagnostic guide for WebGL context loss symptoms and Canvas2D fallback pattern
- `Gdk.WindowTypeHint.DOCK` — layers above system panels (best for overlays)
- `Gdk.WindowTypeHint.SPLASHSCREEN` — sits behind system bars
- Use `DOCK` for launcher menus that should cover everything

### Input Grabbing
On Wayland, popup windows don't receive input by default. WebView handles this internally since it's a full widget, but if you need custom input handling on the GTK window level:

```python
def _on_map(self, widget, event):
    gdk_window = self.get_window()
    if gdk_window:
        seat = gdk_window.get_display().get_default_seat()
        if seat:
            seat.grab(gdk_window, Gdk.SeatCapabilities.ALL_POINTING, False, None, None, None)
            seat.grab(gdk_window, Gdk.SeatCapabilities.KEYBOARD, False, None, None, None)
```

### App ID Matching for Window Rules
GTK3 on Wayland uses the **binary filename** as app_id. A wrapper script is required:

```bash
#!/bin/bash
export GDK_BACKEND=wayland
exec python3 /path/to/overlay.py "$@"
```

Name it `my-overlay`, make executable, then labwc window rules with `identifier="my-overlay"` will match.

## Reference Files
- `references/webgl-context-loss.md` — diagnostic guide for WebGL context loss symptoms and Canvas2D fallback pattern
- `references/resolution-aware-layout.md` — pattern for resolution-independent scene layout (proportional coords, computeLayout function)
- `references/http-chromium-overlay.md` — **Wayland-compatible overlay pattern**: HTTP server + Chromium kiosk mode (replaces GTK+WebKit2 on Wayland)
- `references/css-only-launcher.md` — CSS grid launcher fallback when Three.js script execution fails in Chromium kiosk mode (includes full working template, server endpoints, and CSS effects reference)

## Templates
- `templates/launcher-wrapper.sh` — bash wrapper that starts the HTTP server and launches Chromium in kiosk mode
- `templates/overlay-server.py` — minimal Python HTTP server for serving overlay HTML with /launch, /select, /close endpoints
- **WebKit2 GI bindings are NOT the same as browser APIs** — no `UserContentController`, different method names (`set_enable_*` not `set_property`)
- **Construction order is strict** — register handler → create WebView with manager → set settings after
- **Three.js r128+ recommended** — older versions may have WebGL compatibility issues on VideoCore VII
- **CDN vs bundled Three.js** — CDN loads are fine for development but add latency. For production, bundle a local copy or use a CDN that caches well
- **WebView doesn't auto-hide cursor** — if you want a clean overlay, hide the cursor via CSS `cursor: none` on the body
- **Memory leaks on repeated open/close** — if the overlay is opened/closed frequently, ensure proper cleanup of Three.js objects (dispose geometries, materials, textures) before destroying the WebView
- **GTK WebView produces blank screens with zero errors** — When the GTK+WebKit2 approach renders a completely black screen, there may be NO console output and NO JS errors. This is a known failure mode on Wayland where the compositor drops the window entirely. If you see a black screen from the GTK launcher: (1) check that `Gdk.Display.get_default()` returns a valid display, (2) verify the HTML file loads correctly in Chromium first (`chromium-browser file:///path/to/scene.html`), (3) if it works in Chromium but not GTK, switch to the HTTP+Chromium pattern instead. **Diagnostic**: completely black = WebView not rendering; background visible between scan lines = WebGL context loss (different issue).
- **Waybar `on-click` needs `setsid` for detached processes** — On Wayland, running a launcher script from Waybar's `on-click` with just `&` does NOT properly detach the process. The child inherits the Waybar session and may not launch correctly. Always use `setsid /path/to/launcher &` in the config. Without `setsid`, the launcher silently fails to open.
- **GTK caches HTML aggressively** — after changing the HTML file, old content may still be served. Always add a cache-busting query string: `f'file://{HTML_FILE}?v={int(time.time()*1000)}'`. Also kill stale launcher processes and clear WebKit cache (`rm -rf ~/.cache/WebKit*`) before retesting after file changes.
- **Chromium kiosk mode may not execute `<script>` tags** — In some Chromium builds (especially `--ozone-platform=wayland --kiosk`), script tags in HTML do NOT execute even though they appear in the DOM. Three.js loaded via CDN silently fails to initialize. Workarounds: (1) dynamically inject scripts via JS DOM manipulation (`document.createElement('script')`), or (2) abandon Three.js entirely for CSS-only UIs when the scene is simple (cards, grids, icons). For launcher menus with app cards, pure CSS grid + emoji/icons is more reliable than WebGL on this platform. **Diagnostic**: if `typeof THREE === 'undefined'` after page load but the `<script>` tag exists in DOM, scripts are being skipped entirely — switch to CSS-only or dynamic injection.
- **HTTP server must exit after /launch** — The launcher's HTTP server MUST call `os._exit(0)` after handling a `/launch` request. This closes Chromium and returns control to Waybar. Without this, the launcher stays open forever after launching an app. Also use `setsid` when spawning launched apps so they don't inherit the server's process group.
- **Click handlers need explicit event propagation control** — CSS `cursor: pointer` alone doesn't bind JS events. Always call `e.preventDefault()` and `e.stopPropagation()` in click handlers. Use both document-level delegation AND direct card listeners for reliability on Chromium kiosk mode. Add a 100ms delay before launching to show selection feedback.
- **POPUP window type is unreliable on Wayland** — use a top-level `Gtk.Window()` with `set_decorated(False)` instead. POPUP windows can fail to position correctly or not receive input.
- **`Gdk.Screen.get_width()/height()` returns 0 on Wayland** — always use `Gdk.Display.get_default().get_monitor(0).get_geometry()` for the actual display size. Fallback to hardcoded default if monitor query fails.
- **Hardcoded pixel coords in JS cause misalignment at wrong resolutions** — never hardcode centerX, centerY, iconRadius as fixed numbers. Compute all layout from actual canvas dimensions via a `computeLayout(w, h)` function that derives positions relative to the canvas size. This ensures correct alignment on any resolution (800x480, 1920x1080, etc.).
- **Canvas resize must be explicitly synced** — GTK window and JS canvas can drift apart. Connect `size-allocate` signal on the WebView AND use timeout-based sync after page load to call a JS function that resizes the canvas to match.
- **Cursor hidden behind WebGL canvas** — if using `cursor: none` on body, the cursor disappears entirely. For overlays where you want cursor visibility (navigation), use `cursor: default` on body and add `pointer-events: none` to the canvas element so mouse events pass through to underlying HTML elements.
- `webview-gtk4` — future migration path when GTK4 + WebKit6 bindings become available on Pi OS Bookworm

## Reference Files
- `references/webgl-context-loss.md` — diagnostic guide for WebGL context loss symptoms and Canvas2D fallback pattern
