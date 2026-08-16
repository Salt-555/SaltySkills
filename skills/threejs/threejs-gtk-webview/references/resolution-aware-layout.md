# Resolution-Aware Layout Pattern

When building Canvas2D or Three.js scenes inside GTK+WebKit2 overlays, **never hardcode pixel coordinates** for scene elements (centerX, centerY, iconRadius, etc.). Any resolution mismatch causes misalignment and visual gaps.

## The Problem

Hardcoded coords like `centerX: 400, centerY: 220` only work at exactly 800x480. At any other resolution the scene is offset or clipped.

## The Fix

Compute all layout from actual canvas dimensions in a single function called at init time and on every resize:

```javascript
let layout = {};

function computeLayout(w, h) {
    layout.centerX = w / 2;
    layout.centerY = Math.floor(h * 0.45);       // proportional position
    layout.iconRadius = Math.min(w, h) * 0.32;   // scales with smallest dim
    layout.iconSize = Math.max(28, Math.min(44, w / 18));  // responsive size
}

// Call at init:
const w = window.innerWidth || 800;
const h = window.innerHeight || 480;
computeLayout(w, h);

// Call on resize (from Python via JS bridge):
function resizeCanvas(newW, newH) {
    canvas.width = newW;
    canvas.height = newH;
    computeLayout(newW, newH);
}
```

## Key Principles

1. **Proportional positioning** — use fractions of w/h (e.g., `w/2`, `h*0.45`) not absolute pixels
2. **Scale with smallest dimension** — for circular/radial layouts, use `Math.min(w,h)` as the base scale factor
3. **Responsive sizing** — icon/text sizes should clamp between min/max and scale proportionally
4. **Single source of truth** — all scene elements read from `layout.*` object, never hardcoded values

## Python Side Sync

In the GTK wrapper, ensure canvas dimensions are synced both ways:

```python
# On window resize signal
def on_webview_resize(self, widget, allocation):
    w = max(allocation.width, 1)
    h = max(allocation.height, 1)
    self.web_view.run_javascript(
        f"allmindLauncher.resizeCanvas({w}, {h});", None, None, None
    )

# After page loads (one-shot sync)
GLib.timeout_add_seconds(2, lambda: self._sync_canvas() or False)

def _sync_canvas(self):
    alloc = self.get_allocation()
    w = max(alloc.width, 1)
    h = max(alloc.height, 1)
    self.web_view.run_javascript(
        f"allmindLauncher.resizeCanvas({w}, {h});", None, None, None
    )
    return False
```

## Session Reference

- **Context**: Pi 5 DSI-1 @ 800x480 radial app launcher
- **Issue**: Horizontal gaps and scanline artifacts from resolution mismatch + hardcoded coords
- **Fix**: `computeLayout()` pattern + Wayland monitor geometry detection + Canvas2D resize sync
