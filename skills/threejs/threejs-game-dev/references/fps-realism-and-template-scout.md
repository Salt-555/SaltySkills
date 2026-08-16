# FPS Realism Patterns & Template Scout

A co-op STALKER-Anomaly-like shooter was specced in Three.js (3-player PvE, brutal gunfights, lean/crouch, ADS w/ modeled sights + sway, 1-headshot kills, enemy gun drops, middle-click interact). Open-source FPS templates were scouted before scaffolding; verdict + reusable design decisions below.

## Template Landscape Verdict (Three.js FPS)

Barren. Searched GitHub (`gh search repos "three.js fps" --sort stars`) + web. Best candidate:

**Footprintarts/ThreeJS_FPS_2.0** (42 stars, MIT, updated 2026-06) — modularized official Three.js FPS example.
- GOOD: three-mesh-bvh Octree + Capsule player controller (the official three.js FPS example pattern — smooth collision vs arbitrary level geometry, battle-tested, ~150 lines)
- GOOD: GLTF viewmodel rig w/ AnimationMixer ("FPS Rig AKM" by J-Toastie, CC-BY via Poly Pizza) — gun w/ modeled sights + shoot/reload anims
- GOOD: Vite + modular folder structure
- BAD: toy-ball projectile spheres, no real ballistics (velocity/drop/penetration)
- BAD: no ADS, no sway, no lean, no crouch, no interaction/pickup system
- BAD: setTimeout-hardcoded timing ("reload = 3000ms"); game-feel code tangled into physics.js

Everything else found: 2016-era demos, 0–3 star student projects, Windows-95 maze "engines". No adoptable base.

**Decision pattern: adopt proven primitives as REFERENCE (octree+capsule, GLTF viewmodel pipeline, Vite structure); hand-build the gun-feel stack — it is the game's identity and no template has it. Building on someone else's tangle costs more than it saves.**

## Realistic Gun-Feel Stack (build order)

1. **Viewmodel overlay**: render gun in a separate scene/camera layered over the world — never clips into walls, independent FOV.
2. **Sway = layered springs**, not random noise: breathing sinusoid + movement-driven lag + look-inertia (gun lags behind camera turn, springs back to center).
3. **ADS**: lerp viewmodel to sight line + restrained FOV zoom (~68→55; STALKER keeps zoom subtle). Sway reduced but breathing amplified *through the sight picture*.
4. **Modeled sights, no crosshair**: real front/rear post geometry; alignment drifts with sway — player reads the sight picture, not a UI dot.
5. **Lean (Q/E)**: camera lateral offset ~0.35m + roll ~12°, raycast-checked so the head can't clip through the wall being leaned around.
6. **Crouch (Ctrl)**: capsule height shrink, sway down, quieter movement (feed noise level to AI hearing later).
7. **Ballistics = projectile, NOT hitscan**: muzzle velocity + gravity drop + material penetration. Head-bone sphere collider, ~4x damage = unarmored one-shot headshot kill.
8. **Weapon drops**: enemy death spawns pickup entity carrying serialized weapon state (ammo in mag, condition). Middle-click raycast within ~2m -> pickup/swap.

## Co-op PvE Netcode Boundary (small player count)

- 3-player PvE co-op is the tractable case: **host-authoritative** — one browser simulates AI/damage/pickups, clients send inputs, host broadcasts state ~20Hz with interpolation. No anticheat needed, lag-tolerant.
- Transport: WebRTC DataChannel mesh (P2P); needs a signaling handshake — manual copy-paste for prototype, Cloudflare Worker lobby later.
- Clients predict only their own movement; host owns everything else. Keep host/client logic separate from day one so the prototype doesn't become a trap.
- Competitive browser PvP is a death sentence (lag compensation, reconciliation, anticheat) — do not scope-creep into it.
- **Enemy AI is make-or-break for STALKER feel**: navmesh (recast-navigation JS port), vision cones + hearing (gunshots alert), cover-point evaluation, squad-level flanking/retreat, deliberately imperfect aim (reaction delay, accuracy drops when suppressed or moving). Brutality comes from terrain use, not aimbot.

## Milestone Order That Worked for Scoping

1. M1 gun feel single-player on greybox (proves the game is fun to *hold*)
2. M2 one enemy type, full combat loop (patrol/alert/cover/flank/die/drop/pickup) — the long pole
3. M3 host-authoritative co-op sync
4. M4 content: map (user chose underground facility), enemy variety, atmosphere
