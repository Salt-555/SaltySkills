# Vision Cone Beam — 2D Canvas Overlay

Build detail behind the "Vision-cone visuals: 2D canvas overlay (PROVEN)"
section of SKILL.md. The user reported the deployed game's vision cone had
"a stripe on one side that is bright and the rest is dark."

## Symptom → reproduction

The bug only showed at some aim angles, so a static smoke capture missed it.
Build a multi-facing probe: serve `dist/`, boot `?smoke=1`, then via
`window.__game` set `lockAim = true` and `state.player.facing` to 8 compass
angles, screenshotting each (600ms settle between). This reproduced the
stripe at 90°/135° and showed the cone centerline pitch black at 0°/180°.

## Diagnosis: the tilted SpotLight's ground pool

Rig: `SpotLight(beam, 180, VISION.distance, VISION.halfAngle, 0.5, 1.0)` at
`(p.x, 2.6, p.z)`, target `11.7` units forward at ground level.

- Axis from (0,2.6,0) to (0,0,11.7) tilts ~12.5° ABOVE horizontal. The
  steepest-down cone ray is 12.5°+40° = 52.5° below horizontal → hits ground
  at `2.6/tan(52.5°) ≈ 2.0` units ahead of the player. Pool starts 2 units
  out → dark ring at the player's feet.
- Intensity 180 candela, decay 1.0 → at the pool's near boundary
  `180/2 ≈ 90` → blown-out bright arc there.
- Pool is an elongated ellipse; rays near horizontal fly past the 13-unit
  cutoff. The flat ground fan (±40° × 13u) can never match it. Depending on
  facing, the bright arc lands on one side of the visual cone = the stripe.

Numeric confirmation (pixel reads): at facing 180° the cone centerline
(2–10 units ahead) read `[0,0,0]` while brightness sat 30–150° off-axis.
The old smoke capture looked "fine" because that facing hid the worst of it.

## The 3D cone mesh never rendered

The translucent fan (`MeshBasicMaterial` additive, y=0.15, DoubleSide) had
contributed ZERO pixels all along. Proof: swapping to a solid bright-red
additive material (no map, opacity 0.9) still rendered pure black at every
sample along the cone. Material state was verified fine in-page (map present,
texture uploaded version=1, UVs present, mesh visible, frustumCulled default).
Never root-caused (fog attenuation ~29% at 13u was ruled out; depth/culling
remained suspects). Pivot — do not burn hours on this class of mystery.

## The fix: 2D canvas overlay (src/render/beamOverlay.js)

- Full-screen canvas: `position:fixed; inset:0; z-index:5; pointer-events:none`
  (WebGL canvas is z-auto, HUD z-10, vignette z-20, overlays z-30).
- Each frame after `renderer.render`:
  1. `apex = project(player.x, 0.15, player.z)`;
     `arcC/arcL/arcR = project(player + dir(facing / facing±halfAngle) * distance)`.
     `THREE.Vector3.project(camera)` — THREE is module-scoped; use the game
     instance's camera (raw matrix math also works if THREE isn't reachable).
  2. Screen angles `atan2(dx, -dy)` (0=up, clockwise). Canvas arc angles are
     screen angle − π/2.
  3. `radius = max(dist(apex, arcL/R/C))`; skip if < 4px.
  4. Path: `moveTo(apex)` → `arc(apex, radius, angL, angR, span<0)` → `closePath`
     (normalize `span = angR - angL` to (−π, π); ccw flag = span<0).
  5. Fill with radial gradient centered at apex: stops
     `0→0, 0.18→0.26, 0.42→0.52, 0.75→0.15, 1→0` alpha, seafoam rgb.
     Optional pre-pass glow wedge (angles ±0.08 rad, radius ×1.06, peak 0.10).
  6. `clearRect` at frame start.

Immune to fog, depth, culling; symmetric by construction; uses the exact
reveal constants. Rotates with facing for free (angles come from projected
points).

## Headless screenshot trap: canvas 'screen' compositing

With `globalCompositeOperation='screen'`, the beam canvas held correct pixels
(`getImageData` → seafoam), but `page.screenshot()` showed garbage:
`[254,255,254,1]` where the beam was and `[0,255,0,0]` elsewhere — headless
Chromium mangling the canvas readback. Switching to default `source-over`
fixed the in-canvas behavior; screenshots still couldn't be trusted for the
overlay (headless canvas-over-WebGL readback), so verify via the canvas's own
pixels, not the screenshot.

## Verification scripts (per-project artifacts — not shipped here)

These scripts are **not included in this skill**. They live in the original
game project and must be written per project from the math and thresholds
described above. Recreate them from this guidance rather than expecting them
in-repo.

- `facing-probe.mjs` — 8-facing capture; also reports true player screen
  position via raw matrix projection (`camera.matrixWorldInverse` +
  `projectionMatrix` elements, plain JS — THREE is not global in the bundle).
- `cone-profile.mjs` — wedge metrics: forward wedge (±40° around facing,
  radius 120–720px) vs the same wedge rotated 180° (baseline); symmetry =
  left-half vs right-half ratio. coneSignal > 2 = beam visible.
- In-page state probes (texprobe/matprobe/camprobe/beamprobe/abtest.mjs) —
  copy into the project dir so `playwright-core` resolves; read the overlay
  canvas's pixels directly for ground truth.

Key gotcha when measuring: sample the FULL cone (13u ≈ 650px at ~50px/unit).
A 320px radius only covers the dim near-field and missed the bright mid-band
entirely; static scene elements (structures, injected loot) pollute raw
sectors — the 180°-rotated back-wedge baseline subtracts them.
