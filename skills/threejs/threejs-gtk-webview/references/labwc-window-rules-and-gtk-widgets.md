# labwc Window Rules & GTK3 Widget Positioning (verified labwc 0.9.8)

Session-verified findings from building the cron-timeline HUD widget on Pi 5
(labwc 0.9.8 + XWayland + GTK3 GI).

## 1. Nested `<position>`/`<size>` in windowRule are SILENTLY IGNORED

A rule written in the "conky example" style does NOT position a window:

```xml
<!-- WRONG — window stays at screen center / cascade position, no error logged -->
<windowRule identifier="my-widget" matchOnce="false">
  <position type="corner"><x>0</x><y>0</y></position>
  <size><width>40</width><height>480</height></size>
</windowRule>
```

CORRECT form — inline action attributes:

```xml
<windowRule identifier="my-widget" matchOnce="false" serverDecoration="no">
  <fixedPosition>yes</fixedPosition>
  <skipTaskbar>yes</skipTaskbar>
  <action name="MoveTo" x="0" y="0" />
  <action name="ResizeTo" width="121" height="480" />
  <action name="ToggleAlwaysOnTop"/>
</windowRule>
```

Why conky's nested rule "works": conky self-positions via its own config
(`alignment`, `gap_x`, `gap_y`). Its rc.xml rule never actually moved it.
A plain GTK3 window that CANNOT self-position stays centered until you use
inline `MoveTo`/`ResizeTo` actions.

Reload after editing rc.xml: `kill -HUP $(pidof labwc)` (labwc 0.9.8 also
supports `labwc -r` / `labwc --reconfigure`).

## 2. Identifier matching: XWayland + set_wmclass beats native Wayland

- Native Wayland GTK3 (`GDK_BACKEND=wayland`): the wrapper-name trick
  (binary filename = app_id) did NOT make `identifier=` rules match in
  testing — even with `GLib.set_prgname()` and a matching wrapper name.
- Reliable: `export GDK_BACKEND=x11` in the launcher wrapper +
  `window.set_wmclass("my-widget", "my-widget")` in Python. labwc then
  matches the rule via WM_CLASS. Verify: `DISPLAY=:0 xprop WM_CLASS`.
- gpet on this box uses exactly this pattern.
- Native Wayland is fine for POPUP/SPLASH launchers; use XWayland for
  persistent rule-positioned widgets.

## 3. Translucent floating HUD (ARGB) works on XWayland/labwc

```python
screen = window.get_screen()
rgba = screen.get_rgba_visual()
if rgba is not None:
    window.set_visual(rgba)
window.set_app_paintable(True)
# draw handler:
cr.set_source_rgba(r, g, b, 0.72)   # partial alpha, NOT set_source_rgb
cr.paint()
```

Verified with the cron-timeline widget and gpet. Note: the per-pixel alpha
banding described in the threejs-gtk-webview skill is specific to NATIVE
Wayland; XWayland renders it correctly.

## 4. pkill -f self-match kills the Hermes shell command

```bash
# WRONG — exit -15, labwc reload NEVER runs:
pkill -f my-widget.py; sleep 1; kill -HUP $(pidof labwc)
```

The Hermes terminal wrapper builds an eval string that CONTAINS
`my-widget.py`, so pkill matches the shell wrapper itself and kills the
whole command before `kill -HUP` executes.

```bash
# RIGHT — bracket regex never matches its own literal text:
pkill -f '[m]y-widget.py'
```
Or kill the widget via the Hermes process tool, then reload labwc and
relaunch as SEPARATE commands.

## 5. Passive cron-listener widget data source

`~/.hermes/cron/jobs.json` is a dict: `{"jobs": [...], "updated_at": ...}`.
Each job has `name`, `enabled`, `schedule.expr` (5-field cron) or
`schedule.kind == "interval"` + `next_run_at`, plus `state`, `last_run_at`.
Poll the file mtime every ~5s with `GLib.timeout_add` — never write to it.
The cron-timeline widget at `~/.config/cron-timeline/` is a complete
working example (48 half-hour cells, gold now-arrow, HH:MM readout,
tooltips with job names).
