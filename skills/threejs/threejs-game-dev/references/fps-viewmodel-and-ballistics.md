# FPS Viewmodel, Gun-Feel, and Projectile Ballistics (STALKER-style co-op build)

Patterns verified working in a real build: underground facility greybox, lean/crouch capsule controller, AKM viewmodel with modeled iron sights, projectile ballistics with headshot-instakill dummies. Verified visually via headless Chromium screenshots on Pi 5.

## Template scouting verdict (2026-07)

The public three.js FPS template landscape is barren. Best-starred option (Footprintarts/ThreeJS_FPS_2.0, ~42 stars, modularized official example) shoots bouncing toy balls, has no ADS/sway/lean/crouch/interact, and drives animation timing with hardcoded `setTimeout(..., 3000)` guesses. Everything below it is 2016-era demos and 0-star student projects. **Correct base: adopt the octree capsule controller from the official `games_fps` three.js example (~150 lines, proven smooth) and hand-build the gun-feel stack** — sway/ADS/ballistics is the game's identity and no template has it.

## Viewmodel overlay scene (never clips into walls)

Render the weapon in a SEPARATE scene + camera on top of the world:

```javascript
renderer.autoClear = false;
// per frame:
renderer.clear();
renderer.render(worldScene, worldCamera);
renderer.clearDepth();
renderer.render(vmScene, vmCamera); // fov ~58, near 0.01, far 5
```

Viewmodel scene needs its OWN lights (world lights don't reach it): one directional key + ambient. Set all gun meshes `frustumCulled = false` (they sit outside the vm camera's default frustum logic once swayed).

## Layered sway stack (the STALKER gun-feel)

All layers compose additively on the viewmodel root transform; each is damped by `adsEase` (smoothstepped ADS t) EXCEPT breathing, which stays readable through the sight picture:

1. **Look inertia springs** — damped spring on accumulated mouse delta (`stiffness 90, damping 13`), gun lags behind view turn and settles. Clamp ±0.05. Scaled by `(1 - adsEase*0.55)`.
2. **Breathing** — two incommensurate sinusoids (`sin(t*1.9)`, `cos(t*2.6+0.8)`), amplitude ~0.0016 hip, ~0.0009 ADS. Never fully removed — the sight picture should feel alive.
3. **Movement bob** — phase advances with horizontal speed, `bobAmp * (1 - adsEase*0.85)`.
4. **Recoil kick** — impulse on fire, exponential recovery (`+= (0-k)*min(1,dt*9)`), applied as +z push and pitch.
5. **Muzzle flash** — PointLight at muzzle, intensity spike ~5.5, fast decay (`*= pow(0.0001, dt)`).

## ADS with modeled iron sights (no crosshair)

Build the sight geometry INTO the gun model: front post + protective ears at muzzle end, rear notch plate near receiver. Sight-line height above gun root = SIGHT_HEIGHT (measure from geometry, ~0.11 for an AK pattern). Then:

```javascript
const ADS_POS = new THREE.Vector3(0, -SIGHT_HEIGHT, -0.30); // puts sight line on camera axis
// pos = lerp(HIP_POS, ADS_POS, adsEase); sway layers shrink with adsEase
// world FOV: lerp(75, 62, adsEase) — STALKER restraint, not a big zoom
```

Verify by SCREENSHOT: front post silhouette must sit framed between the rear notch wings at screen center. Tune ADS_POS.y in 0.002 steps until it reads honestly.

## Lean (Q/E) with wall guard

Camera-space, not player-rotation: lateral offset along the camera right vector (~0.36m) + roll (~0.21 rad ≈ 12°), smoothed at ~8/s. Guard against head-through-wall: raycast sideways from eye center via `octree.rayIntersect(ray)` with far = |offset| + 0.25, clamp offset to `hit.distance - 0.25`. Roll sign = -leanT (lean left rolls camera left).

## Crouch

Shrink the capsule segment length (stand 1.15 → crouch 0.48, radius 0.32), lerp a `crouchT` at ~9/s, keep feet planted by re-deriving `end` from `start` each frame. Eye height lerps 1.62 → 0.95 separately (slower, ~10/s) so the camera doesn't stair-step.

## Projectile ballistics (STALKER is NOT hitscan)

- Bullet pool (~64), each: pos, vel, tracer mesh (stretched 0.012×0.012×0.22 box, MeshBasicMaterial warm color, `frustumCulled=false`).
- Spawn ray from CAMERA (honest aiming), tracer mesh follows bullet pos.
- Spread: `lerp(hipSpread, adsSpread, adsT) + bloom`; bloom grows per shot (~0.0035), decays (~0.02/s).
- **Substep tunnel-proofing**: per frame compute travel; split into segments of ≤0.4m; per segment check `octree.rayIntersect` (world) and target raycast; resolve nearest first.
- World gravity on `vel.y` each frame; kill bullet past ~220m.
- Head hit = sphere test (r≈0.16) against head bone world position → instakill. Torso = ray transformed into box local space (`Matrix4.invert` on mesh matrixWorld, `ray.applyMatrix4`, intersect `geometry.boundingBox`), 2-hit kill.

## Headless verification recipe (pointer-lock games)

Headless Chromium can't click through pointer lock, so verify rendering/state WITHOUT it:

1. Hide the lock overlay from console: `document.getElementById('overlay').style.display='none'`.
2. Expose debug hooks in the game loop: `if (window.__forceADS != null) viewmodel.setADS(window.__forceADS);` — then set `window.__forceADS=true` from console and screenshot the sight picture.
3. Read the live stats HUD (fps/pos) from the DOM snapshot to confirm the loop runs.
4. Expect ~20fps under Pi 5 headless software rendering — that is the harness, not the game. Judge feel on real GPU.

## Reference implementation

Working M1 codebase layout: `src/game/WeaponViewModel.js` (sway/ADS/flash), `src/game/WeaponSystem.js` (ballistics/substeps/spread/bloom), `src/game/PlayerController.js` (capsule lean crouch), `src/game/DummyManager.js` (hit zones, weapon-drop pickup with MMB raycast-at-reach + `dot > 0.92` facing test).
