# CSS-Only Launcher Pattern (When Three.js Fails)

When Chromium kiosk mode on Pi 5 doesn't execute `<script>` tags, use pure CSS/HTML for launcher UIs. This is the reliable fallback for app menus with cards, grids, and icons.

## Why It Works

Chromium's `--ozone-platform=wayland --kiosk` build silently skips inline script execution even when tags appear in DOM. CSS rendering works perfectly — no JS needed for layout, styling, or transitions.

## Pattern

```html
<!DOCTYPE html>
<html lang="en">
<head>
<style>
  body { overflow: hidden; background: #050510; font-family: 'Courier New', monospace; }
  
  /* Grid container */
  #grid-container {
    position: absolute; top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    display: grid; gap: 20px 15px;
  }

  .app-card {
    width: 140px; height: 90px;
    background: rgba(74, 158, 255, 0.1);
    border: 2px solid rgba(74, 158, 255, 0.3);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; transition: all 0.3s ease;
  }

  .app-card.selected {
    background: rgba(122, 196, 255, 0.2);
    border-color: #7ac4ff;
    box-shadow: 0 0 15px rgba(122, 196, 255, 0.5), 0 0 30px rgba(122, 196, 255, 0.3);
    transform: scale(1.1);
  }

  /* Scanline overlay */
  #scanlines {
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    pointer-events: none; z-index: 50; opacity: 0.35;
    background: repeating-linear-gradient(
      0deg, transparent, transparent 2px,
      rgba(0, 0, 0, 0.4) 2px, rgba(0, 0, 0, 0.4) 4px
    );
  }

  /* Vignette */
  #vignette {
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    pointer-events: none; z-index: 49;
    background: radial-gradient(ellipse at center, transparent 40%, rgba(5,5,16,0.8) 100%);
  }
</style>
</head>
<body>
<div id="scanlines"></div>
<div id="vignette"></div>
<div id="grid-container"></div>

<script>
// Minimal JS — only for navigation and HTTP communication
const PORT = 8765;
let apps = [];
let selectedIndex = -1;

function createGrid() {
  const container = document.getElementById('grid-container');
  const cols = Math.max(3, Math.min(5, Math.floor(window.innerWidth / 180)));
  container.style.gridTemplateColumns = `repeat(${cols}, 140px)`;
  
  apps.forEach((app, i) => {
    const card = document.createElement('div');
    card.className = 'app-card' + (i === selectedIndex ? ' selected' : '');
    card.dataset.index = i;
    card.innerHTML = `<span>${app.name}</span>`;
    container.appendChild(card);
  });
  
  // Attach click handlers after creating cards
  attachCardClickHandlers();
}

function updateSelection() {
  document.querySelectorAll('.app-card').forEach((card, i) => {
    card.classList.toggle('selected', i === selectedIndex);
  });
}

// Keyboard navigation
window.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowDown') {
    selectedIndex = (selectedIndex + 1) % apps.length;
    updateSelection();
    fetch(`http://127.0.0.1:${PORT}/select?index=${selectedIndex}&name=${encodeURIComponent(apps[selectedIndex]?.name || '')}`)
      .catch(err => console.error('[Launcher] Select error:', err));
  } else if (e.key === 'Enter' && apps[selectedIndex]) {
    e.preventDefault(); // Prevent page scroll on Enter
    handleClick();
  } else if (e.key === 'Escape') {
    fetch(`http://127.0.0.1:${PORT}/close`)
      .catch(err => console.error('[Launcher] Close error:', err));
  }
});

// Click handler with event propagation control
function handleClick() {
  if (apps[selectedIndex]) {
    const app = apps[selectedIndex];
    
    // Visual flash feedback before closing
    const cards = document.querySelectorAll('.app-card');
    if (cards[selectedIndex]) {
      cards[selectedIndex].style.background = 'rgba(122, 196, 255, 0.4)';
      setTimeout(() => updateSelection(), 200);
    }
    
    fetch(`http://127.0.0.1:${PORT}/launch?name=${encodeURIComponent(app.name)}&exec=${encodeURIComponent(app.exec)}`)
      .then(r => r.text())
      .catch(error => {
        console.error('[Launcher] Launch error:', error);
        alert(`Failed to launch ${app.name}\n\nError: ${error.message}`);
      });
  }
}

// Document-level event delegation
document.addEventListener('click', (e) => {
  const card = e.target.closest('.app-card');
  if (card) {
    e.preventDefault();
    e.stopPropagation();
    
    selectedIndex = parseInt(card.dataset.index);
    updateSelection();
    
    // Small delay to show selection before launching
    setTimeout(() => handleClick(), 100);
  }
});

// Direct card listeners for reliability (redundant but safe)
function attachCardClickHandlers() {
  document.querySelectorAll('.app-card').forEach((card, index) => {
    card.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      
      selectedIndex = index;
      updateSelection();
      setTimeout(() => handleClick(), 100);
    });
    
    // Hover feedback
    card.addEventListener('mouseenter', () => {
      if (index !== selectedIndex) card.style.background = 'rgba(74, 158, 255, 0.2)';
    });
    card.addEventListener('mouseleave', () => {
      if (index !== selectedIndex) card.style.background = '';
    });
  });
}

// Fetch app list from server
fetch(`http://127.0.0.1:${PORT}/apps`)
  .then(r => r.json())
  .then(data => { apps = data.apps; createGrid(); })
  .catch(error => setTimeout(() => fetch(`http://127.0.0.1:${PORT}/apps`), 2000));
</script>
</body>
</html>
```

## When to Use This Pattern

- **Launcher menus** with app cards, icons, and grid layouts
- **Simple UIs** that don't need complex 3D rendering
- **When Three.js script tags fail** in Chromium kiosk mode
- **Performance-critical overlays** where JS overhead matters on Pi 5

## Limitations

- No WebGL effects (particles, fog, bloom) — use CSS `box-shadow` for glow instead
- No Canvas2D animations — stick to CSS transitions and transforms
- Limited interactivity beyond click/keyboard navigation

## Server Endpoints Required

The HTTP server must provide:

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `/apps` | Return app list as JSON `{"apps": [...]}` | 200 + JSON |
| `/select?index=N&name=X` | Selection change notification | 200 + "OK" |
| `/launch?name=X&exec=Y` | Launch an application | 200 + "OK", then **exit** |
| `/close` | Close the launcher | Kills server process |

### ⚠️ CRITICAL: Server Must Exit After Launch

The HTTP server MUST call `os._exit(0)` after handling a `/launch` request. This closes Chromium and returns control to Waybar. Without this, the launcher stays open forever after launching an app.

```python
# In your handler's do_GET for /launch:
if name and exec_cmd:
    subprocess.Popen(['setsid', 'sh', '-c', exec_cmd], start_new_session=True)
    
self.send_response(200)
self.end_headers()
self.wfile.write(b'OK')
os._exit(0)  # ← REQUIRED — closes the launcher window
```

### ⚠️ CRITICAL: Detach Launch Process with setsid

Use `setsid` when launching apps from the server so they don't inherit the server's process group. Without it, the launched app may be killed when the server exits.

```python
subprocess.Popen(
    ['setsid', 'sh', '-c', exec_cmd],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True  # Also required for proper detachment
)
```

## Click Handler Pattern (Reliable Event Handling)

CSS-only launchers need explicit click handlers — CSS `cursor: pointer` alone doesn't trigger JS. Use both document-level delegation AND direct card listeners for reliability:

### ⚠️ Click Handler Pitfalls

- **Don't rely on CSS `cursor: pointer` alone** — it only changes the cursor, doesn't bind JS events
- **Always call `e.preventDefault()` and `e.stopPropagation()`** in click handlers to prevent event bubbling conflicts with Wayland input handling
- **Use a 100ms delay before launching** — gives visual feedback (selection highlight) time to render before the window closes
- **Add both document delegation AND direct listeners** — Chromium's kiosk mode can sometimes drop delegated events; direct listeners are more reliable

## CSS-Only Effects Reference

**Glow effect:** `box-shadow: 0 0 15px rgba(122, 196, 255, 0.5), 0 0 30px rgba(122, 196, 255, 0.3);`

**Fade transition:** `transition: opacity 0.3s ease;`

**Scale on hover/selected:** `transform: scale(1.1);` (use `scale()` not `zoom`)

**Scanlines:** `repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.4) 2px, rgba(0,0,0,0.4) 4px)`

**Vignette:** `radial-gradient(ellipse at center, transparent 40%, rgba(5,5,16,0.8) 100%)`