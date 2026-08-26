---
name: threejs-topdown-games
description: "Build top-down Three.js games and fix black-canvas renders."
version: 1.0.0
author: Hermes Agent (curator)
metadata:
  hermes:
    tags: [threejs, top-down, game-dev, vision-cone, reveal-gating, lighting, headless-capture, tdd]
    related_skills: [threejs-game-dev, test-driven-development]
    category: threejs
---

# Three.js Top-Down Games

Verified guidance for building top-down / 2.5D Three.js games — especially
STALKER-style games whose core mechanic is a **vision cone / reveal gating**
(entities only exist when inside the player's cone + distance + line of sight,
or within a small proximity radius). Everything below was proven in a complete
build (a STALKER-style, moon-survival game): TDD'd logic core,
136 tests, headless-verified both scenes. Full build detail:
`references/vision-cone-stalker-build.md`.

## Architecture that works

- **Pure-logic core** (`src/logic/`) with ZERO Three.js imports: geometry
  (vec2, AABB, segment/AABB, LOS), vision, player, combat, inventory, loot,
  world defs + transitions, house, save. Test with vitest/pytest — RED-GREEN
  per module. `src/main.js` orchestrates only; it never contains game rules.
- **Thin render layer** (`src/render/`): scene/env, camera, world meshes,
  entity views, input, DOM HUD.
- **Reveal pipeline**: each frame compute `revealEntities(player, entities,
  walls)` → Set of ids → `view.visible = revealed.has(id)`. Reveal gating is
  pure logic; the cone visual is cosmetic but shares the SAME cone constants
  so what you see == what is real. **Draw the cone as a 2D canvas overlay**
  (see "Vision-cone visuals" below) — the SpotLight + translucent-mesh combo
  produces a one-sided "stripe" artifact and the 3D cone mesh may never
  render at all (both verified in the reference build).

## Vision cone constants (tuned, copy-able)

- Player: halfAngle 40° (80° cone), distance 13, proximity 2.0. Proximity
  bypasses LOS — you sense things 2 steps away.
- Enemy: sight 7 units, 120° facing cone, LOS required; hearing =
  hearRadius(4.5) × movement noise (crouch 0.25 / walk 1.0 / sprint 3.0).
  Sprinting is LOUD — that is the stealth tension.

## Pitfalls (each cost real debugging time)

### Black screen, HUD fine, zero errors → probe the live renderer
Before touching lights: playwright `page.evaluate` on the game instance
(expose `window.__game`) reading `renderer.info.render.calls`,
`camera.position`, scene child counts. Classic silent killer: **camera
position.y = NaN** from a plain `{x, z}` camera-target object — `targetPos.y`
is undefined → `undefined + offset - y = NaN` → whole projection dies. Guard:
`const ty = targetPos.y ?? 0` in the follow-camera update.

### Physically-correct lights (three r155+)
SpotLight/PointLight intensity is in **candela**. Values like 2-3 are
invisible at 10-15 unit gameplay scale. A readable flashlight needed
intensity ~120-180, decay ~1.0, distance = cone distance. First exposure
lever: `renderer.toneMappingExposure` (ACES 1.15 → ~2.4). Fill light:
HemisphereLight (~1.0) + a FIXED DirectionalLight 'moon' that never follows
the player — only the cone moves.

### Smoke scenes for reveal-gated games
- Headless mouse sits at NDC (0,0) → ground raycast → noisy facing → cone
  points arbitrarily → reveal gating hides your demo. Lock facing in smoke
  mode (`lockAim` flag; skip the aim raycast) and set it explicitly.
- Walls short-circuit the beam: a player inside a walled compound facing out
  → cone terminates at the wall face → loot/enemies "ahead" are never
  revealed. Spawn smoke entities in open ground, LOS-clear, inside the cone.
- One smoke variant per world (`?smoke=1`, `?smoke=room`) proves every scene.
  Bridge: `window.Gameplay` + `[data-smoke-result]="pass"` appended to body.

### Headless capture must serve the vite PRODUCTION build
Bare specifiers (`three`) fail from raw src. `vite build --logLevel error`
then serve `dist/`. Resolve the repo root before the serveFile path guard —
a relative root makes every request 403 (`ERR_HTTP_RESPONSE_CODE_FAILURE` on
page.goto). Rebuild unminified (`vite build --minify false`) for readable
pageerror stacks.

### HUD `innerHTML` destroys the canvas
If the HUD builds itself with `root.innerHTML = ...` on the same container as
the WebGL canvas, the canvas is removed from the DOM (smoke reports
`canvas:false`; game renders to a detached canvas). Append the canvas to
`document.body`; give the HUD its own element.

### Dark-scene readability (without breaking the mood)
Emissive wall-top trim strips so walls read as structures; additive
under-glow discs under loot and the player; floor grid opacity ~0.45; one
warm accent color for enemies' eyes. Tune exposure, then re-capture, then
`vision_analyze` the PNG and iterate.

### Swept collision — endpoint checks tunnel
Endpoint-only circle-vs-rect tunnels through walls at speed. Liang-Barsky
sweep of the move segment against each wall rect expanded by the player
radius; clamp t at first entry (minus epsilon). Resolve X first, then Z from
the clamped X → wall sliding + corners for free. Property test: 200 random
deltas never end inside a wall.

### Combat/AI same-tick rule
State transitions must act the same tick — a husk that spots the player
moves/attacks immediately, not next frame.

### TDD fixture hygiene
Test-world geometry bugs masquerade as implementation bugs: player spawn
inside a wall rect, edge math off by 0.1, reusing one mutable fixture across
two assertions in one test (state leaks). When RED fails for the wrong
reason, the fixture — not the code — is usually guilty: fix the test.

## Vision-cone visuals: 2D canvas overlay (PROVEN — the way to draw a beam)

The player's vision cone should be a clean, symmetric wedge of light that
matches the reveal fan exactly. Two 3D approaches failed in the reference build;
the working one is a screen-space 2D canvas:

- **Do NOT use a SpotLight for the cone.** A spot hung over the player
  (e.g. y=2.6, target 11.7 ahead, intensity 180, angle = halfAngle) tilts
  its axis ~12.5° above horizontal. Its ground pool then starts ~2 units in
  front of the player — dark ring at the player's feet, a blown-out bright
  arc at the pool's near boundary (I ≈ 180/2), and an elongated ellipse that
  never matches the flat fan. At some aim angles the arc sits on one side of
  the cone: the classic "bright stripe on one side, rest dark" bug. A tilted
  SpotLight can NEVER light a flat ground fan cleanly.
- **Do NOT rely on a translucent 3D cone mesh either.** The MeshBasicMaterial
  additive fan at y=0.15 rendered NOTHING — even a solid bright-red additive
  material over it showed pure black in screenshots. Root cause never pinned
  (fog/depth/culling suspects); the beam look had been 100% the spot pool all
  along. Don't burn time diagnosing; pivot.
- **The proven pattern — 2D canvas overlay:** a full-screen canvas
  (`position:fixed; z-index` above the WebGL canvas, below the HUD,
  `pointer-events:none`). Each frame: project the player apex and the two
  cone-edge points (player + dir(facing ± halfAngle) × distance) through the
  camera (`THREE.Vector3.project` — the game module has THREE even though it
  isn't global in the bundle), compute screen angles (`atan2(dx,-dy)`, 0=up;
  canvas angle = screen angle − π/2), then fill a wedge path (moveTo apex →
  arc → closePath) with a radial gradient centered on the apex: transparent
  at 0 (feet), ~0.26 at 0.18, peak ~0.52 at 0.42, fading to 0 at the far
  edge. Optional wider/longer low-alpha glow wedge first. Symmetric by
  construction, immune to fog/depth/culling, and always matches the reveal
  fan because it uses the same constants.
- **CRITICAL: default `source-over` compositing only.** Drawing the overlay
  with `globalCompositeOperation='screen'` makes headless Chromium mangle the
  canvas in `page.screenshot()` (garbage readback like `[254,255,254,1]` and
  `[0,255,0,0]`) even though the canvas's own `getImageData` is correct.
  Real browsers composite either way, but the headless verification loop
  needs source-over. When a 2D beam "doesn't appear" in screenshots, read the
  overlay canvas's pixels directly with `getImageData` before trusting the
  screenshot.
- **Verifying a beam: numeric pixel analysis, not the aux vision model.**
  `vision_analyze` gives contradictory reads on near-black frames (it
  described the same image two different ways). Measure instead: sample the
  FULL cone length (13 units ≈ 650px at ~50px/unit — a 320px radius only
  covers the dim near-field), mean luma in the forward wedge (±halfAngle
  around facing, radius 120–720px) minus the same wedge rotated 180°
  (baseline scene brightness; static structures/loot pollute raw sectors).
  coneSignal > 2 = beam visible; left-vs-right half ratio ≈ 1.0 = symmetric.
  See `references/vision-cone-beam-overlay.md` for the full math, the
  multi-facing capture probe (reproduces angle-dependent artifacts by
  screenshotting at 8 facings), and the in-page state probes.

## Verification loop
> **Note:** the probe scripts named below (`capture.mjs`, `facing-probe.mjs`,
> `cone-profile.mjs`, `texprobe`/`matprobe`/`camprobe`/`beamprobe`/`abtest.mjs`)
> are **per-project artifacts, not shipped with this skill**. Write your own
> from the math, thresholds, and checklists described in this file and in
> `references/vision-cone-beam-overlay.md` (they live in the original game
> project). They are recreated per project from this guidance.

1. `capture.mjs` + pageerror stacks (unminified build if needed).
2. DOM dump after error (`window.__game`, element keys).
3. Live probe of renderer/scene/camera state.
4. Fix → recapture → `vision_analyze` → tune exposure/lighting → repeat.
5. For lighting/beam checks on dark frames, prefer numeric pixel analysis
   over `vision_analyze` (see above) — and remember screenshots can lie about
   canvas-2D overlays; read the canvas's own pixels for ground truth.
