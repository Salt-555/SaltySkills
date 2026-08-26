# Vision-Cone Stalker Build — full build detail

Top-down STALKER/Road-to-Vostok moon survival stalker in Three.js with a TDD'd
pure-logic core. 136 vitest tests, both worlds headless-verified, committed.

## Shape that worked

- **Pure-logic core** in `src/logic/` with zero Three.js imports: geometry
  (vec2, AABB, segment/AABB, LOS), vision (cone+proximity+LOS reveal), player
  (movement tiers + swept collision), combat (husk AI + hitscan), inventory,
  loot tables, world definitions + door transitions, house (decoration/storage),
  save/load. RED-GREEN per module.
- **Thin render layer** (`src/render/*`) + `src/input/` + DOM HUD. `main.js`
  orchestrates only — it never contains game rules.
- **Reveal pipeline**: every frame `revealEntities(player, [...items, ...husks],
  walls)` returns a Set of ids; views set `visible` accordingly. Reveal gating
  is pure logic; lighting (cone SpotLight + translucent cone mesh) is cosmetic
  but shares the same VISION constants so what you see == what is real.

## Vision cone constants (tuned)

- Player: halfAngle 40° (80° cone), distance 13, proximity 2.0 (proximity
  bypasses LOS — you sense them that close).
- Enemy: sight 7 units, 120° facing cone, LOS required; hearing =
  hearRadius(4.5) × movement noise (crouch 0.25 / walk 1.0 / sprint 3.0).
  Sprinting is LOUD — that is the stealth tension.

## Movement/collision — swept circle vs expanded AABB

- Endpoint-only circle-vs-rect **tunnels through walls** at speed. Use a
  Liang-Barsky sweep of the move segment against each wall rect expanded by the
  player radius; clamp t at first entry (minus a small epsilon). Resolve X
  first, then Z from the clamped X → wall sliding and corner handling for free.
- Property test that caught it: 200 random deltas must never end inside a wall
  rect expanded by radius.

## Combat / AI notes

- State transitions must act the **same tick** — a husk that spots the player
  should move/attack immediately, not next frame (tests fail "closes distance
  on a chased player" otherwise; the fix is falling through, not an early
  return).
- Hitscan: ray-vs-circle (quadratic) + ray-vs-expanded-AABB; wall impact = min t.
  Test the wall-block case explicitly (impact stops at the wall face).

## Rendering — the lighting / black-screen war

- **Black scene, HUD fine, zero errors → probe the live renderer first.**
  Evaluate `renderer.info.render.calls`, `camera.position`, scene child counts
  via playwright `page.evaluate` on the game instance (expose `window.__game`).
- **ROOT CAUSE this session: camera.position.y = NaN.** The follow camera was
  given a plain `{x, z}` target object; `targetPos.y` is undefined →
  `undefined + 16 - 16 = NaN` → the whole projection dies silently. Fix:
  `const ty = targetPos.y ?? 0` in the follow-camera update. The canonical
  camera example uses a full Vector3 — guard the plain-object case anyway.
- **Physically-correct lights (three r155+)** — SpotLight/PointLight intensity
  is in candela. A value of 2.6 was invisible at 10-15 unit gameplay scale; a
  readable flashlight beam needed **intensity ~120-180, decay ~1.0**,
  distance = cone distance. First exposure lever: `renderer.toneMappingExposure`
  (ACES 1.15 → ~2.4). Fill light: HemisphereLight (~1.0) + a FIXED
  DirectionalLight 'moon' (~0.7) that never moves with the player — only the
  cone follows.
- **Readability in the dark**: emissive wall-top trim strips (faint emissive
  so walls read as structures), additive seafoam under-glow discs under loot
  and player, floor grid opacity ~0.45, one warm red (husk eyes) per palette.
  Tune loop: capture → `vision_analyze` → adjust exposure/lights → repeat.

## Smoke-scene capture contract (three traps)

1. **Aimless headless mouse**: at NDC (0,0) the ground raycast produces noisy
   facing → the cone points arbitrarily → reveal gating hides the demo. Lock
   the facing in smoke mode (`lockAim` flag; skip the aim raycast) and set it
   explicitly toward the shot.
2. **Walls short-circuit the beam**: player inside a walled compound facing out
   → the cone terminates at the wall face; loot/enemies "ahead" sit behind it
   and are never revealed. Spawn smoke entities in open ground, LOS-clear.
3. **One smoke variant per world** (`?smoke=1` colony money shot, `?smoke=room`
   hab shot) proves every scene renders. Bridge: `window.Gameplay` +
   `[data-smoke-result]="pass"` appended to body. Adapt the capture script's
   ready predicate per game (drop game-specific elements like #hud-round).
4. **Capture must serve the vite PRODUCTION build (dist/)** — bare `three`
   specifiers fail from raw src. `vite build --logLevel error && node
   scripts/capture.mjs dist ../shots/x.png`. (Note: `capture.mjs` is a
   **per-project artifact** from the original game project, not shipped with
   this skill — write your own capture probe from this guidance.) Resolve ROOT
   before the serveFile
   path guard (relative '.' → every request 403 →
   `ERR_HTTP_RESPONSE_CODE_FAILURE` on page.goto). `vite build --minify false`
   for readable pageerror stacks.

## HUD pitfalls

- HUD built with `root.innerHTML = ...` on the SAME container as the WebGL
  canvas destroys the canvas (smoke reports `canvas:false`; game renders to a
  detached canvas). Append the canvas to `document.body`; HUD gets its own
  element.

## Debugging sequence that worked

1. `capture.mjs` + pageerror stack; rebuild unminified (`vite build --minify
   false`) for readable stacks.
2. DOM dump after the error (what's in #app, does `window.__game` exist, el keys).
3. Live probe of renderer/scene/camera state.
4. Fix → recapture → `vision_analyze` the PNG → tune exposure/lighting → repeat.

## TDD fixture hygiene (learned the hard way)

- Test-world geometry bugs masquerade as implementation bugs: player spawn
  inside a wall rect, circle-vs-rect edge math off by 0.1, reusing one mutable
  fixture (a husk) across two assertions in one test (state leaks from the
  first case into the second). When RED fails for the wrong reason — the
  fixture, not the code, is usually guilty: fix the test, not the impl.
