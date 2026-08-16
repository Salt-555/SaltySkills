# WebGL Context Loss on Pi 5 (VideoCore VII) + WebKit2 WebView

## Symptom
Scene renders as **horizontal scanlines with background visible between them**. The canvas IS there and sized correctly, but only partial frames are rendered.

This is NOT a sizing issue or CSS problem — it's the GPU context being dropped mid-frame by VideoCore VII in the WebKit2 rendering pipeline on Wayland/labwc.

## Diagnostic
```
Background visible between scanlines  → WebGL context loss (switch to Canvas2D)
Completely black screen              → WebView not loading / JS error / no canvas created
Stretched/distorted scene            → Canvas sizing issue (not WebGL-related)
```

## Fix: Switch to Canvas2D

Canvas2D is CPU-rendered and guaranteed to work. Same PS2 memory card aesthetic achievable:

### Key differences from Three.js approach
| Three.js/WebGL | Canvas2D |
|---|---|
| GPU context (can be lost) | No GPU dependency |
| `THREE.Scene`, `THREE.Mesh` | Direct `ctx.fillRect()`, `ctx.beginPath()` |
| `requestAnimationFrame` loop | Same pattern, no changes needed |
| `shadowBlur` not available | `ctx.shadowBlur` works for glow effects |
| ~256MB VRAM shared with RAM | No VRAM constraint |

### Minimal Canvas2D scene structure
```javascript
const canvas = document.createElement('canvas');
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;
document.body.insertBefore(canvas, scanlinesOverlay);
const ctx = canvas.getContext('2d');

function animate() {
    requestAnimationFrame(animate);
    
    // Clear entire frame
    ctx.fillStyle = '#050510';
    ctx.fillRect(0, 0, w, h);
    
    // Draw scene elements
    drawGrid();
    drawParticles();
    drawIcons();
}
```

### Performance on Pi 5
- **60fps achievable** with <100 objects (icons + particles)
- Use `fillRect` for particles instead of circles (faster CPU path)
- `shadowBlur` works but is expensive — use sparingly, only on selected elements
- Avoid heavy compositing; keep draw calls minimal per frame

## Debugging Steps (in order)

1. **Kill stale processes**: `pkill -f "allmind-launcher"`
2. **Clear WebKit cache**: `rm -rf ~/.cache/WebKit*`
3. **Test in Chromium directly**: `chromium-browser file:///path/to/scene.html` — if it works there, the issue is GTK/WebView integration
4. **Check canvas sizing** in JS console: `canvas.width === window.innerWidth`
5. **Add cache-busting URL**: `file://...?v={timestamp}` to prevent stale HTML

## Why This Happens

VideoCore VII has limited VRAM (~256MB shared with system RAM). When WebKit2 creates a WebGL context and the scene exceeds available resources or triggers a context loss event, the GPU drops the context mid-frame. The canvas element persists (so you see scanlines), but rendering is incomplete.

Canvas2D avoids this entirely because it runs on the CPU — no VRAM, no GPU context to lose.
