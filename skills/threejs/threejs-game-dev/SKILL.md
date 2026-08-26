---
name: threejs-game-dev
description: Guide Three.js game development from setup through architecture.
version: 0.2.0
category: game-development
related_skills:
  - llm-wiki
  - obsidian
metadata:
  hermes:
    tags: [Three.js, Game Dev, WebGL, 3D, Architecture]
---

# Three.js Game Development Guide

Practical reference for building browser-based 3D games with Three.js — from project setup through game architecture patterns. Covers physics integration, collision detection, performance optimization, and scalable design. Focuses on *game development*, not just pretty scenes or interactive demos.

This skill does NOT replace formal courses (Three.js Journey for fundamentals, SimonDev's course for advanced techniques). It provides the canonical workflow, toolchain decisions, architecture patterns, and pitfalls encountered when building actual playable games in Three.js.

## When to Use

- "How do I set up a new Three.js game project?"
- "What physics engine should I use with Three.js?"
- "How do I implement collision detection or ECS architecture for my game?"
- "My Three.js game is running slow, what can I optimize?"
- "I need to stream an infinite world or manage heavy GPU resources"
- Comparing Three.js vs React Three Fiber for a game project

## Prerequisites

```bash
# Node.js 18+ (use nvm on Pi 5)
nvm install 20
nvm use 20

# Core package — VERSION MATTERS for API compatibility
npm i three@latest

# Physics engine (recommended: Rapier for games in 2026)
npm i @dimforge/rapier3d-compat

# Build tool — Vite is the standard choice
npm i -D vite @vitejs/plugin-basic-ssl
```

## Critical Version Compatibility

| Feature | Minimum Three.js Version | r128 Alternative |
|---------|--------------------------|------------------|
| `CapsuleGeometry` | r137+ | `CylinderGeometry(radius, radius, height, segments)` with `.translate()` |
| ES Module CDN imports | any | Use `<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js">` (global THREE) |
| Import maps (`type="importmap"`) | r152+ | Not available — use global script tag or bundler |

**Rule**: If using CDN without a build step, either pick a modern version (r160+) with import maps OR stick to r128 globals. Mixing causes silent failures.

## Project Structure (Modular Standard)

User preference: **modular from day one**, not monolithic files. Even small demos should use this structure for easy expansion:

```\nproject/\n├── index.html          # Minimal entry point + import map\n└── src/\n    ├── main.js         # Game loop — ties subsystems together, does NOT contain game logic\n    ├── Input.js        # Keyboard/mouse state only (decoupled from movement)\n    ├── SpritePlayer.js # Billboarded 2D character with walk bobbing and collision\n    ├── Camera.js       # View logic (third-person orbit, first-person, etc.)\n    ├── World.js        # Scene, lighting, obstacles, shadow management\n    ├── NPC.js          # Non-player characters with interaction radius checks\n    └── DialogueSystem.js # Camera shifts, typewriter text, choice buttons
```

Each class has ONE responsibility. `main.js` orchestrates; it never calculates movement or handles input directly. See `references/collision-resolution.md` for the modular pattern with code examples from a working third-person game.

## How to Run

1. Scaffold project with Vite — use `terminal` tool to create directory and initialize
2. Write game code in source files, reference via `read_file` when editing or reviewing
3. Iterate on architecture patterns described below using `patch` for modifications
4. Test in browser via Vite dev server

> **Templates need Vite + npm.** The provided templates use bare ESM imports (`import * as THREE from 'three'`) and a `<script type="module">` entry, so they cannot run from `file://`. Run them with Vite and install Three.js from npm first:
> ```bash
> npm init -y
> npm i three
> npm i -D vite
> npx vite --host
> ```

### Quick Start Template (Infinite Runner)

For a fast mobile-friendly 3D runner game, use the provided templates:
- `templates/infinite-runner.html` — complete HTML with UI overlay, viewport meta, touch-safe CSS
- `templates/infinite-runner.js` — full Three.js game loop with lane switching, obstacle spawning, collision detection, boost mechanic

Copy both to your project root and edit the CONFIG block at top of JS. Works on mobile out of the box.

## Quick Reference

| Concern | Recommendation |
|---------|---------------|
| Build tool | Vite (not Webpack unless legacy) |
| FPS starting point | No public template worth forking (scouted 2026-07 — all toy-grade). Adopt official `games_fps` octree+capsule controller; hand-build sway/ADS/ballistics (`references/fps-viewmodel-and-ballistics.md`) |
| Physics | @dimforge/rapier3d-compat (preferred), Ammo.js, JoltPhysics (via WASM) |
| Architecture | ECS pattern (Entity-Component-System) or simple class hierarchy |
| Asset loading | GLTFLoader + DRACO loader for compressed models |
| World streaming | Custom chunk system with spatial hashing (SimonDev course covers deeply) |
| GPU compute | GPGPU via raw WebGL shaders or Three.js RawShaderMaterial |
| React integration | @react-three/fiber (declarative, good for UI-heavy games) |
| Performance profiling | Three.js Stats plugin + browser DevTools Performance tab |

## Procedure

### 0. Template Scouting Before Scaffolding

**User preference: scout for existing open-source starters BEFORE hand-rolling a new game project.** Search GitHub directly (`gh search repos "three.js <genre>" --sort stars --json fullName,description,stargazersCount,updatedAt`), then clone the top candidate and READ the actual source — star counts and README feature lists misrepresent code quality. Decide adopt-vs-build with specific evidence (what systems exist, what's toy-grade, what's missing). Present the verdict honestly rather than defaulting to building from scratch or blindly adopting.

FPS landscape verdict (scouted): barren — best candidate (`Footprintarts/ThreeJS_FPS_2.0`) is reference-grade only. Adopt proven primitives (three-mesh-bvh octree+capsule controller, GLTF viewmodel rig pipeline, Vite modular structure); hand-build the gun-feel stack, which is the game's identity and no template has. Full evaluation + realistic FPS patterns (sway springs, ADS w/ modeled sights, lean raycasts, projectile ballistics, weapon drops, 3-player co-op netcode boundary): `references/fps-realism-and-template-scout.md`.

### 1. Project Initialization (Two Paths)

**Path A: Rapid Prototype (Single-File + CDN)** — Use for quick iterations, movement tests, simple games

```bash
mkdir my-game && cd my-game
# No npm install needed — use CDN imports directly
```

Create `index.html` with CDN import and Python server:

```html
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>My Game</title></head>
<body>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        // Your game code here — THREE is globally available (no module needed)
    </script>
</body>
</html>
```

**CRITICAL**: Do NOT use `<script type="module">` with r128 globals — wrap in an IIFE or plain script tag. Import maps (`type="importmap"`) fail silently on Pi 5 Chromium (black canvas, zero errors). r128 global CDN is the only reliable path for self-contained HTML files on this hardware.

**Path B: Full Project (Vite + npm)** — Use when you need TypeScript, build optimization, or complex dependencies

```bash
mkdir my-game && cd my-game
npm init -y
npm i three @dimforge/rapier3d-compat
npm i -D vite tsx typescript @types/three @types/node
npx tsc --init
```

Create `index.html` with canvas target and `src/main.ts`:

```html
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>My Game</title></head>
<body><canvas id="game"></canvas><script type="module" src="/src/main.ts"></script></body>
</html>
```

### 2. Delta Time (Critical)

Movement MUST be framerate-independent — always multiply speed by `delta` from `THREE.Clock`. Without it, movement is faster on high-refresh displays and slower when the Pi struggles:

```javascript
// main.js
this.clock = new THREE.Clock();

_loop() {
    requestAnimationFrame(() => this._loop());
    const delta = this.clock.getDelta(); // seconds since last frame
    
    if (locked) {
        this.player.update(this.input, this.camera.camera, this.world.obstacleBoxes, delta);
    }
}

// Player.js — speed in units/second, not per-frame
this.speed = 6; // ~6 world units per second
moveDir.normalize().multiplyScalar(this.speed * delta);
```

**User preference**: Delta time is non-negotiable for any game loop. Always implement it from the start rather than retrofitting later.

### 3. Physics Integration (Rapier)

```typescript
import * as RAPIER from '@dimforge/rapier3d-compat'

// Initialize once at startup
await RAPIER.init()
const gravity = { x: 0, y: -9.81, z: 0 }
const world = new RAPIER.World(gravity)

function physicsStep(dt: number): void {
  world.step()
}
```

### 4. ECS Architecture Pattern

Three.js has no built-in ECS. The canonical pattern from the community (and SimonDev's course):

- **Entities** = integer IDs (no data, just identifiers)
- **Components** = plain objects mapping entity ID → data (position, velocity, mesh ref)
- **Systems** = functions that iterate over entities with specific components and apply logic

```typescript
type Position = { x: number; y: number; z: number }
type Velocity = { vx: number; vy: number; vz: number }

const positionMap = new Map<number, Position>()
const velocityMap = new Map<number, Velocity>()

function addEntity(pos: Position): number {
  const id = nextId++
  positionMap.set(id, pos)
  return id
}

// MovementSystem runs every frame
for (const [id, vel] of velocityMap.entries()) {
  if (!positionMap.has(id)) continue
  const p = positionMap.get(id)!
  p.x += vel.vx * dt
  p.y += vel.vy * dt
  p.z += vel.vz * dt
}
```

### 5. Collision Detection

With Rapier, register rigid bodies with collision flags:

```typescript
const bodyDesc = RAPIER.RigidBodyDesc.fixed()
  .setTranslation(pos.x, pos.y, pos.z)
const body = world.createRigidBody(bodyDesc)

// Sensors live on the ColliderDesc, NOT the RigidBodyDesc (Rapier 0.20)
const sensorDesc = RAPIER.ColliderDesc.cuboid(x, y, z).setSensor(true) // for triggers (no physics response)
const sensorHandle = world.createCollider(sensorDesc, body)
// or: a non-sensor collider with .setRestitution/.setFriction for realistic movement
```

Now that a collider exists, use `world.colliders.forEach()` with overlap checks or raycasting for interactions.

### 6. Third-Person Movement Math (No Physics Engine)

**Standard approach: use `camera.getWorldDirection()` — NOT manual yaw math.** Deriving forward/right from the actual camera view direction is the textbook standard for third-person games and eliminates sign-flip bugs that plague manual trig approaches. Pass the camera to your player's update method:

```javascript
update(input, camera, obstacleBoxes, delta) {
    // Get camera's actual forward direction (projected onto XZ plane)
    const forward = new THREE.Vector3();
    camera.getWorldDirection(forward);
    forward.y = 0;
    forward.normalize();

    // Right vector: cross product of forward and up
    const right = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 1, 0));

    let moveDir = new THREE.Vector3(0, 0, 0);
    if (input.isDown('KeyW')) moveDir.add(forward);   // W = forward relative to camera
    if (input.isDown('KeyS')) moveDir.sub(forward);   // S = backward relative to camera
    if (input.isDown('KeyA')) moveDir.sub(right);     // A = left relative to camera
    if (input.isDown('KeyD')) moveDir.add(right);     // D = right relative to camera

    if (moveDir.lengthSq() > 0) {
        moveDir.normalize().multiplyScalar(this.speed * delta); // delta is non-negotiable
        this.group.position.add(moveDir);
    }
}
```

**Why not yaw-based?** Manual `(-sin(yaw), -cos(yaw))` vectors are fragile — sign errors cause W/S inversion and diagonal drift. `getWorldDirection()` always matches what the camera sees, so movement is guaranteed to be correct regardless of how you position the camera.

**GC optimization**: Reuse THREE.Vector3 instances as class properties instead of creating new ones each frame:
```javascript
this._forward = new THREE.Vector3();
this._right = new THREE.Vector3();
this._moveDir = new THREE.Vector3();
```

**Wall sliding**: When collision blocks full movement, try X and Z axes independently so the player slides along walls instead of hard-stopping:

```javascript
const nextPos = pos.clone().add(moveDir);
if (!collides(nextPos)) {
    pos.copy(nextPos);
} else {
    // Slide X only
    let slideX = pos.clone(); slideX.x += moveDir.x;
    if (!collides(slideX)) pos.x = slideX.x;
    // Slide Z only
    let slideZ = pos.clone(); slideZ.z += moveDir.z;
    if (!collides(slideZ)) pos.z = slideZ.z;
}
```

Pre-compute obstacle bounding boxes once at startup (`new THREE.Box3().setFromObject(mesh)`) — never recalculate per frame. See `references/collision-resolution.md` for full working implementation.

### 7. Shadow Management (Static Light + Moving Frustum)

**Standard pattern: keep the light fixed, move only the shadow camera frustum.** Moving the light position with the player makes it feel like a personal spotlight — shadows shift direction as you walk, which looks wrong. The correct approach is what every third-person game uses (Unreal, Unity):

```javascript
_createLights() {
    this.sun = new THREE.DirectionalLight(0xfff5e6, 1.2);
    this.sun.position.set(50, 80, -40); // FIXED — does not move with player
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.width = 2048;
    this.sun.shadow.mapSize.height = 2048;
}

updateShadows(playerPos) {
    const size = 35;
    this.sun.shadow.camera.left = -size;
    this.sun.shadow.camera.right = size;
    this.sun.shadow.camera.top = size;
    this.sun.shadow.camera.bottom = -size;
    // Center shadow camera over player
    this.sun.target.position.set(playerPos.x, 0, playerPos.z);

    // CRITICAL — must call after changing frustum bounds
    this.sun.shadow.camera.updateProjectionMatrix();
}
```

**Why not move the light?** Moving `sunLight.position` every frame makes shadows behave like a flashlight attached to the player. A static position gives consistent shadow direction across the entire scene. The shadow camera just needs to follow so the 2048×2048 texture is always sampling around where the player stands.

**Critical pitfall**: Forgetting `.updateProjectionMatrix()` after changing frustum bounds. Without it, Three.js keeps using the old projection — shadows appear only in the initial area and don't update as you move.

### 8. Billboarded Sprite Characters (Paper Mario / Void Bastards Style)

For 2D sprites that always face the camera in a 3D world, use `PlaneGeometry` — NOT `THREE.Sprite`:

| Approach | Pros | Cons |
|----------|------|------|
| `PlaneGeometry` + manual Y rotation | Stays upright at any camera angle, full control over bobbing/flip | Manual billboarding code needed |
| `THREE.Sprite` | Auto-billboards automatically | Tilts when camera looks up/down — looks like a floating card |

**Standard pattern:**
```javascript
// Create billboard plane with texture
const geo = new THREE.PlaneGeometry(1.0, 2.0);
const mat = new THREE.MeshBasicMaterial({
    map: texture,
    transparent: true,
    side: THREE.DoubleSide,
    depthTest: true,
    depthWrite: false // Critical: don't write to depth so sprites layer correctly
});

this.sprite = new THREE.Mesh(geo, mat);
this.sprite.position.y = 1.0; // Center at mid-height
this.group.add(this.sprite);

// In update(): face camera on Y axis only (stay upright)
const camPos = new THREE.Vector3();
camera.getWorldPosition(camPos);
const toCamera = new THREE.Vector3().subVectors(camPos, this.group.position);
toCamera.y = 0; // Project onto XZ plane

if (toCamera.lengthSq() > 0.01) {
    const targetAngle = Math.atan2(toCamera.x, toCamera.z);
    let diff = targetAngle - this.sprite.rotation.y;
    while (diff > Math.PI) diff -= Math.PI * 2; // Normalize to [-PI, PI]
    while (diff < -Math.PI) diff += Math.PI * 2;
    this.sprite.rotation.y += diff * 0.15; // Smooth lerp
}

// Walk bobbing when moving
if (isMoving) {
    bobPhase += delta * 12;
    sprite.position.y = baseY + Math.abs(Math.sin(bobPhase)) * 0.08;
} else {
    // Gentle idle breathing
    sprite.position.y = baseY + Math.sin(Date.now() * 0.002) * 0.005;
}
```

**Canvas texture placeholder:** Generate character art with `CanvasTexture` for prototyping — swap to `.png` later:
```javascript
const canvas = document.createElement('canvas');
canvas.width = 128; canvas.height = 256;
const ctx = canvas.getContext('2d');
// Draw character silhouette, face details...
const texture = new THREE.CanvasTexture(canvas);
texture.needsUpdate = true;
```

### 9. NPC Interaction System

For billboarded NPCs (always facing camera), **use pure distance checks** — not dot product facing tests:

| Approach | When to Use | Why |
|----------|-------------|-----|
| Pure distance (`< radius`) | Billboarded sprites, Paper Mario style | Sprites always face camera — "facing" concept doesn't apply visually |
| Dot product + distance | 3D models with clear front/back | Player must look at NPC's actual front side |

**Standard pattern:**
```javascript
checkInteraction(playerPos) {
    const dx = playerPos.x - this.group.position.x;
    const dz = playerPos.z - this.group.position.z;
    const dist = Math.sqrt(dx * dx + dz * dz);
    return { canInteract: dist < this.interactionRadius, distance: dist };
}
```

**Pitfall:** Using dot product facing checks with billboarded sprites causes the interaction to only trigger when the player is at a specific angle relative to the camera — feels like you need to "walk past" the NPC. For billboards, distance-only is correct.

### 10. Dialogue System with Camera Shifts and Pointer Lock

When implementing dialogue that requires mouse clicks (choice buttons), **release pointer lock** during dialogue:

```javascript
// On dialogue start
startDialogue(npc, camera) {
    if (document.pointerLockElement) document.exitPointerLock(); // Free cursor for clicking
    
    this._dialogueBox.style.display = 'block';
    // ... show UI
}

// On dialogue end / cancel
endDialogue() {
    this._dialogueBox.style.display = 'none';
    requestAnimationFrame(() => document.body.requestPointerLock()); // Re-lock for movement
}

// ESC handler — exits from any state
window.addEventListener('keydown', e => {
    if (e.code === 'Escape' && this.isActive) this.cancelDialogue();
});
```

**Camera shift pattern:** Smooth camera transitions between NPC face → player face using `lerpVectors` with smoothstep easing:
```javascript
update(delta, camera) {
    const speed = delta * 4; // ~0.25s transition
    this._progress = Math.min(1, this._progress + speed);
    const t = this._smoothStep(this._progress); // Smoothstep easing
    
    camera.position.lerpVectors(this._startPos, this._targetPos, t);
    this._currentLookAt.lerpVectors(this._startLookAt, this._targetLookAt, t);
    camera.lookAt(this._currentLookAt);
}

_smoothStep(t) { return t * t * (3 - 2 * t); }
```

**Auto-advance pattern:** Use `setTimeout` with state guards — never fire stale timers:
```javascript
// Clear on every state transition
_clearAutoAdvance() {
    if (this._timer) { clearTimeout(this._timer); this._timer = null; }
}

// Guarded advance after NPC finishes speaking
this._clearAutoAdvance();
this._autoAdvanceTimer = setTimeout(() => {
    if (this.state === 'npc_talking') this.advanceToPlayerTurn(); // State check prevents double-fire
}, 2000);
```

**Typewriter text with callback:**
```javascript
_typeText(text, onComplete) {
    this._dialogueText.textContent = '';
    let i = 0;
    const interval = setInterval(() => {
        if (i < text.length) { this._dialogueText.textContent += text[i]; i++; }
        else { clearInterval(interval); if (onComplete) onComplete(); }
    }, 35); // ~35ms per character
}
```

### 11. AABB Collision Resolution (No Physics Engine)

For simple games without Rapier, implement axis-separated penetration resolution:

**Standard pattern — single pass, no iterative loops:**
```javascript
// Reusable player box — NEVER allocate per frame
this._playerBox = new THREE.Box3();

_resolveCollision(pos, obstacleBox) {
    const pBox = this._playerBox;
    pBox.min.set(pos.x - this.radius, pos.y, pos.z - this.radius);
    pBox.max.set(pos.x + this.radius, pos.y + this.height, pos.z + this.radius);

    if (!pBox.intersectsBox(obstacleBox)) return false;

    // Overlap on each axis
    const overlapX = Math.min(pBox.max.x - obstacleBox.min.x, obstacleBox.max.x - pBox.min.x);
    const overlapY = Math.min(pBox.max.y - obstacleBox.min.y, obstacleBox.max.y - pBox.min.y);
    const overlapZ = Math.min(pBox.max.z - obstacleBox.min.z, obstacleBox.max.z - pBox.min.z);

    // Resolve along SMALLEST penetration axis
    if (overlapX < overlapY && overlapX < overlapZ) { /* push out X */ }
    else if (overlapY < overlapZ) { /* push out Y — land on top or hit ceiling */ }
    else { /* push out Z */ }

    return true;
}
```

**Unified ground check — one pass, no special cases:**
```javascript
_findStandingSurface(obstacleBoxes) {
    let surfaceY = 0; // Floor plane as default candidate

    for (const box of obstacleBoxes) {
        const xOverlap = px + radius > box.min.x && px - radius < box.max.x;
        const zOverlap = pz + radius > box.min.z && pz - radius < box.max.z;
        if (xOverlap && zOverlap) {
            const distToTop = py - box.max.y;
            if (distToTop >= -TOLERANCE && distToTop <= TOLERANCE) {
                surfaceY = Math.max(surfaceY, box.max.y); // Pick highest valid surface
            }
        }
    }

    return (py - surfaceY within tolerance) ? surfaceY : null; // null = airborne
}
```

**Why unified?** Separate checks for "on ground" vs "on box top" create divergent paths. A single `_findStandingSurface()` that scans floor + all obstacles in one pass works for any flat surface — add stairs, platforms, moving objects without changing the check.

**CRITICAL performance rules:**
1. **Single-pass resolution** — iterate obstacles once per axis, break on first hit. No `while(!resolved)` loops doing 2-3 passes over ALL obstacles per frame = O(n²) GC pressure + chunky stutters on jump/land.
2. **Reuse Box3** — pre-allocate `_playerBox` as a class property. Never create `new THREE.Box3()` during collision resolution.
3. **Pre-compute obstacle boxes** at startup: `new THREE.Box3().setFromObject(mesh)`.

See `references/collision-resolution.md` for full working implementation with jump physics integration.

## Top-Down Follow Camera (VERIFIED — prefer over parented pivot)

For top-down 2.5D games (Streets of Rogue style), do NOT parent the camera to a pivot Group and set `rotation.x` — that pattern produced persistent horizontal-view bugs in a real session (5 failed iterations: wrong sign, lookAt overridden, parent transforms interfering). Instead, position the camera directly in world space and call `lookAt()` on the player every frame:

```javascript
export class Camera {
  constructor(scene) {
    this.camera = new THREE.PerspectiveCamera(50, innerWidth/innerHeight, 0.1, 100);
    this._offset = new THREE.Vector3(0, 15, 12); // above + behind player
    this._lookAt = new THREE.Vector3();
    this._currentLookAt = new THREE.Vector3();
  }

  update(delta, targetPos, moveDir) {
    // Smooth-follow desired position (player + offset)
    this.camera.position.x += (targetPos.x + this._offset.x - this.camera.position.x) * delta * 5;
    this.camera.position.y += (targetPos.y + this._offset.y - this.camera.position.y) * delta * 5;
    this.camera.position.z += (targetPos.z + this._offset.z - this.camera.position.z) * delta * 5;

    // lookAt player with slight movement lookahead
    this._lookAt.copy(targetPos);
    if (moveDir && moveDir.lengthSq() > 0.01) {
      this._lookAt.x += moveDir.x * 2;
      this._lookAt.z += moveDir.z * 2;
    }
    this._currentLookAt.lerp(this._lookAt, delta * 3);
    this.camera.lookAt(this._currentLookAt);
  }
}
```

Offset `(0, 15, 12)` gives a readable ~50° downward angle. Diagnostic when the view looks wrong: `camera.getWorldDirection(v).y` in the console must be strongly negative (≤ −0.8); near 0 means horizontal regardless of what local rotation says. Also: near-vertical top-down views make the player model fill the screen — keep some Z offset so the world is visible. See `references/top-down-camera-debug.md` for the full failure log.

## Sniper FPS Camera Pattern

For stationary sniper games (Prop Hunt style), use `PointerLockControls` + CSS scope overlay:

```javascript
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';

const controls = new PointerLockControls(camera, renderer.domElement);
renderer.domElement.addEventListener('click', () => controls.lock());

// Scope zoom: smooth FOV transition (never snap)
scopedFOV = 12; defaultFOV = 75;
currentFOV += Math.sign(targetFOV - currentFOV) * Math.min(Math.abs(diff), zoomSpeed * dt);
camera.fov = currentFOV;
camera.updateProjectionMatrix();

// Breathing sway: sinusoidal micro-offsets on camera quaternion
pitchSway = sin(time * 1.5) * amplitude; // ~90 BPM
yawSway = cos(time * 1.05 + 1.3) * amplitude * 0.6;
swayQuat.setFromEuler(new Euler(pitchSway, yawSway, 0, 'YXZ'));
camera.quaternion.premultiply(swayQuat);

// Hold breath (Shift): reduce sway proportional to breath meter
effectiveAmplitude *= breathMeter / 100; // zero when depleted
```

**CSS scope overlay** — always use CSS overlays for HUD in Chromium kiosk mode. Kiosk silently skips `<script>` tags in injected HTML. Scope vignette, crosshair, range marks, ammo counter all via `::before`/`::after` pseudo-elements and positioned divs with `pointer-events: none`.

## Procedural IK Animation (Spider/Creature Legs)

For multi-legged creatures, use **closed-form two-bone IK** (Law of Cosines) — not iterative FABRIK or CCD. No physics engine needed.

> **Illustrative (pseudo-code):** the sketch below omits full variable definitions for brevity — `d` = clamped hip→target distance, `u` = upper segment length, `l` = lower segment length, and the vector arithmetic is abbreviated. For a complete, runnable solver (with proper `THREE.Vector3` math and clamping) see `references/procedural-ik-movement.md`.

```javascript
function solveTwoBoneIK(hip, knee0, upperLen, lowerLen, target) {
    const toTarget = new THREE.Vector3().subVectors(target, hip).normalize();
    const poleVec = new THREE.Vector3().subVectors(knee0, hip)
        .projectOnPlane(toTarget).normalize();

    // Law of Cosines: angle at hip
    const cosTheta = (d*d + u*u - l*l) / (2 * d * u);  // d=clampedDist, u=upperLen, l=lowerLen
    const theta = Math.acos(clamp(cosTheta, -1, 1));

    // Knee position
    kneePos = hip + toTarget * (u * cos(theta)) + poleVec * (u * sin(theta));

    // Rotations via quaternion from-to
    hipQuat.setFromUnitVectors(upperRestDir, upperSolvedDir);
    kneeQuat.setFromUnitVectors(lowerRestWorldDir, lowerSolvedDir);
}
```

Gait: phase-offset sine waves per leg. Stance feet stay planted (don't drift with body). Swing feet arc forward. 6 legs is the sweet spot for visual clarity. ~464 triangles total for body + 6 two-bone legs. See `references/procedural-ik-movement.md` for full implementation.

## Asymmetric Multiplayer MVP Boundary

When the product goal is online matchmaking, never silently redefine the MVP as local shared-machine multiplayer. A single-client build may temporarily expose both roles as a **mechanical test harness**, but preserve separate role modules, serializable state, and authoritative-server boundaries from day one. Explicitly label the harness so prototype convenience does not become product architecture.

For stationary-vantage games, browser verification must include the live camera view—not just a successful render. Project the intended target into NDC, visually inspect obstructions, and raycast toward it to confirm the first hit is not the sniper platform or map shell. See `references/asymmetric-online-mvp.md` for the architecture boundary and verification recipe.

## Hitscan Ballistics

For stationary sniper games, use **instant raycasting** — not simulated projectiles. Stationary player at known distances makes hitscan more satisfying than bullet drop.

```javascript
const raycaster = new THREE.Raycaster(); // reuse every frame
raycaster.setFromCamera(new THREE.Vector2(0, 0), camera);
const hits = raycaster.intersectObjects(shootableObjects, true);
```

Track shootable objects separately — don't raycast against the entire scene. Register/unregister targets as they enter/leave play. Add slight spread offset to aim point (tighter when scoped). See `references/sniper-ballistics-pattern.md` for full implementation with ammo/reload system.

## Project-Scoped LLM Wiki

For game projects, initialize a project-specific LLM Wiki vault (`games/<name>/wiki/`) using the `llm-wiki` skill. Customize SCHEMA.md tags to the domain (mechanic, animation, physics, collision, etc.). Each mechanic gets its own concept page with research-backed implementation code. This compounds knowledge across sessions and prevents re-researching solved problems.

## Session References

See `references/fps-viewmodel-and-ballistics.md` for the verified FPS gun-feel implementation: viewmodel overlay scene, layered sway springs, modeled iron-sight ADS (no crosshair), lean-with-wall-guard, capsule crouch, substepped projectile ballistics with head-sphere instakill, weapon-drop pickups, and the headless pointer-lock verification recipe.
See `references/threejs-versioning-gotchas.md` for detailed debugging logs of version-specific failures encountered during development.
See `references/collision-resolution.md` for AABB collision patterns, unified ground checks, and performance pitfalls from the third-person game build.
See `references/procedural-ik-movement.md` for full two-bone IK solver + gait system code (sniper project).
See `references/top-down-camera-debug.md` for the parented-pivot camera failure log and the verified follow-camera pattern (fantasy roguelite build).

### 12. Performance Optimization Checklist

- Use instanced meshes (`InstancedMesh`) for repeated geometry (hundreds+ copies)
- Frustum culling is on by default — verify objects outside view aren't expensive to update
- Keep draw calls low: merge geometries where possible, use texture atlases
- For infinite worlds: chunk-based streaming with distance-based spawn/despawn
- Profile with `import Stats from 'three/examples/jsm/libs/stats.module'`
- Use DRACO compression for GLTF models (`GLTFLoader` + `DRACOLoader`)

### 13. Mobile FOV Adjustment

For scenes with multiple objects in a row (card spreads, menus, etc.), narrow screens crop edges. Fix by adjusting camera FOV based on viewport width:

**CRITICAL: Wider FOV = zoomed OUT (more fits). Narrower FOV = zoomed IN.** This is the most common mistake — going from 50 to 40 makes things appear CLOSER, not further away. To fit more objects in frame on mobile, you need a WIDER angle:

```javascript
// On init — wider FOV on narrow screens so everything fits
const camera = new THREE.PerspectiveCamera(
  window.innerWidth < 700 ? 65 : 50, // WIDER on mobile = zoomed out
  window.innerWidth / window.innerHeight,
  0.1, 100
);

// On resize (handles orientation changes)
window.addEventListener('resize', function() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.fov = window.innerWidth < 700 ? 65 : 50;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});
```

Also tighten object spacing — reduce card/object width and gap multiplier for narrow viewports.

### 14. Mobile Testing & Deployment

When testing on mobile devices (phone/tablet), the Pi 5 LAN is your target:

- **Vite must bind to all interfaces**: `npx vite --host` or set in config:
  ```js
  // vite.config.js
  export default defineConfig({
    server: { host: '0.0.0.0', port: 5173 },
  })
  ```
- **Find Pi IP**: `hostname -I | awk '{print $1}'` → use as URL on phone browser
- **Pixel ratio cap** — mobile GPUs throttle at high DPR; always cap:
  ```js
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  ```
- **Viewport meta tag is mandatory** (not optional):
  ```html
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  ```
- **Touch-safe CSS**: `touch-action: none` on body to prevent scroll/zoom interfering with game input
- **Verify visually** — use browser screenshot (browser_exec) to confirm the game renders before telling the user it's ready
- **First-render checklist for new games**: (1) player spawn is NOT inside an obstacle — use a fixed safe zone (e.g. central plaza) for spawn rather than random-position rejection sampling; (2) ambient light ≥ 0.8 + hemisphere light, not one dim directional — dark screenshots are unreadable; (3) screenshot and inspect BEFORE reporting done — "canvas exists" and `game.state === 'playing'` do not mean the camera looks the right direction.

### 15. Mobile Input Patterns

For touch-first games, implement these patterns early:

```javascript
// Swipe detection (lane switching)
let touchStartX = 0, touchStartY = 0;
document.addEventListener('touchstart', e => {
  touchStartX = e.touches[0].clientX;
  touchStartY = e.touches[0].clientY;
}, { passive: true });

document.addEventListener('touchend', e => {
  const dx = e.changedTouches[0].clientX - touchStartX;
  const dy = e.changedTouches[0].clientY - touchStartY;
  if (Math.abs(dx) > Math.abs(dy)) { /* horizontal swipe */ }
  else if (dy < -40) { /* swipe up */ }
}, { passive: true });

// Prevent default browser gestures
document.body.style.touchAction = 'none';
```

### Debugging Rules (CRITICAL)

**When debugging Three.js rendering issues:**

1. **Stop after 2-3 attempts** — If you've tried 2-3 different approaches and nothing works, STOP and pivot to a working solution rather than continuing in circles.

2. **Check the environment first** — Before assuming code is wrong:
   - Is WebGL supported? (Check browser DevTools)
   - Are ES modules loading correctly? (Use HTTP server, not file:// protocol)
   - Is the canvas element actually being created?

3. **Provide a working fallback immediately** — If you can't verify rendering in your environment, provide the complete working code with clear instructions for the user to run locally. Don't keep debugging when the environment itself is the blocker.

4. **User correction = immediate pivot** — When the user says "you're overcomplicating this" or "stop doing X", immediately switch to a simpler approach and deliver the final solution.

5. **"Periodically black" vs "always black" diagnostic** — If textures render correctly sometimes but go black after several scene resets/draws, the root cause is **WebGL memory exhaustion from undisposed resources**, NOT image loading. Do not waste time fixing preload pipelines when the real issue is missing `.dispose()` calls. Check: are old geometries/materials disposed before creating new ones? Are shared textures protected from disposal by setting `material.map = null` first?

## Pitfalls

### Three.js Version Gotchas (CRITICAL)

- **CDN version traps**: When using CDN imports (`cdnjs.cloudflare.com/ajax/libs/three.js/r128/`), many newer geometries don't exist:
  - `CapsuleGeometry` — added in r137. Use `CylinderGeometry` as fallback for older versions.
  - Always check the Three.js changelog for your target version before using new features.
- **Black screen debugging**: Scene renders black but UI is visible? Check:
  1. Is `THREE` actually defined? (`typeof THREE !== 'undefined'`)
  2. Are lights added to scene AND configured correctly? (Missing `scene.add(light)` = invisible)
  3. Does the geometry constructor exist for your Three.js version?
  4. Check browser console for silent JS exceptions — they kill the render loop silently.
- **Import maps fail SILENTLY on Pi 5 Chromium** — r160+ with `<script type="importmap">` produces a completely black canvas with ZERO console errors or network failures. The module loads but the renderer never outputs to the canvas. WebGL context is active, canvas dimensions are correct, yet `getImageData()` returns all-black pixels. **Fix**: Use r128 global CDN (`<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js">`) instead of import maps for self-contained HTML files on Pi 5. This is the reliable pattern — no build step, no module loading issues.
- **BoxGeometry material face ordering** — materials array is `[+x right, -x left, +y top, -y bottom, +z front, -z back]`. The camera at positive Z looking toward origin sees the **+Z face (index 4)**. If your card/object should show its "back" initially and flip to reveal the "front", assign `materials[4] = backMaterial` and `materials[5] = frontMaterial`, then rotate Y by PI on flip. Getting this reversed means cards appear face-up from the start.

### Movement Math

- **`camera.getWorldDirection()` is the standard** — always use it for third-person movement. Manual yaw-based trig (`sin/cos`) is fragile and prone to sign errors causing W/S inversion and diagonal drift. Pass the camera to `player.update(camera)` so movement derives from actual view direction.
- **Always normalize** the final movement vector so diagonal isn't faster than straight.

### Shadow Camera Follow

- Directional light shadow cameras are fixed in world space by default. Once the player walks outside the initial frustum, shadows disappear entirely. Fix: keep `sunLight.position` FIXED (e.g., `(50, 80, -40)`), only move `sunLight.target.position` to follow the player and update shadow camera bounds (`left/right/top/bottom`) every frame. **CRITICAL**: call `.updateProjectionMatrix()` after changing frustum bounds or shadows won't actually update.

### Collision Detection Performance

- **Pre-compute bounding boxes**: Create `Box3` objects for static obstacles ONCE at startup, not every frame. Rebuilding Box3s per-frame is expensive and unnecessary for static geometry.
- **Wall sliding**: When collision blocks full movement, try X and Z axes independently so the player can slide along walls instead of hard-stopping.

- **CapsuleGeometry is r137+** — silently fails on older Three.js (r128). Use `CylinderGeometry(radius, radius, height, segments)` with `.translate()` instead. Always check the version before using newer geometries/materials.
- **Movement direction**: Use `camera.getWorldDirection()` projected onto XZ plane for forward, then cross with up vector for right. Manual yaw-based trig (`sin/cos`) is fragile — sign errors cause W/S inversion and diagonal drift. Always pass the camera to player.update() so movement derives from actual view direction.
- **Quaternion movement collapses diagonals** — applying a quaternion to WASD input vectors causes diagonal movement to collapse onto one axis and feel faster (Pythagorean error). Use `camera.getWorldDirection()` instead of any rotation-based approach.
- **Shadow camera is world-fixed** — directional light shadows only render within their initial frustum bounds. Player walks away → shadows vanish. Fix: keep `light.position` FIXED, update ONLY `light.target.position` and shadow camera bounds every frame to follow the player. Call `.updateProjectionMatrix()` after changing bounds.
- **Never move the light with the player** — this makes shadows behave like a personal spotlight. The sun stays at one position; only the shadow camera frustum follows.
- **Game loop behind pointer lock gate** — if you wrap all rendering in `if (pointerLocked) { ... }`, the scene stays black until the user clicks. Always render every frame; only gate *input* behind pointer lock.
- **Import maps require r152+** — `<script type="importmap">` with ES modules doesn't work on older Three.js versions. For r128, use global script tag: `<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>`.
- **Rapier init is async** — must `await RAPIER.init()` before creating the world, or it silently fails. This is the #1 gotcha on first try.
- **Delta time matters** — using fixed `requestAnimationFrame` timing without delta causes physics to break at different framerates. Always use elapsed seconds between frames.
- **Three.js stats plugin path** — import from `'three/examples/jsm/libs/stats.module'`, not a separate npm package.
- **ECS overkill for small games** — if you have fewer than ~20 objects, plain classes with inheritance are simpler and faster to write. ECS pays off at scale (50+ entities).
- **Infinite world streaming is hard** — most tutorials stop at static scenes. SimonDev's course is the primary source covering smooth content streaming and GPU memory management for this.
- **Vite + Three.js examples** — some Three.js addons use import paths like `'three/examples/jsm/...'`. These work with Vite via npm but require correct package resolution — make sure `three` is installed from npm and use standard ESM `import` statements (import maps or the bundler handle the resolution), not CSS-style `@import`.
- **WebGL context loss on mobile** — set `renderer.xr.enabled = true` if targeting VR/mobile, and handle context lost events gracefully.
- **FOV direction is counterintuitive** — wider FOV (higher number) = zoomed OUT = more fits in frame. Narrower FOV (lower number) = zoomed IN = tighter crop. Going from 50→40 makes things appear CLOSER, not further away. To fit more objects on mobile, increase the FOV number (e.g., 65 for phones).
- **Vite `minify: 'terser'` fails out of the box** — since Vite v3, terser is an optional dependency. `npx vite build` errors with "terser not found" unless you `npm i -D terser` or drop the minify option. Default esbuild minification is fine for prototypes.
- **User preference: standard patterns over custom solutions.** The user explicitly prefers "by the book" approaches for proven systems (camera-relative movement via `getWorldDirection()`, delta time from `THREE.Clock`). Do not reinvent math that established game engines have solved — use the canonical pattern first.
- **Pointer lock blocks UI interaction** — if dialogue has clickable buttons, release pointer lock on start (`document.exitPointerLock()`), re-acquire on end (`requestAnimationFrame(() => document.body.requestPointerLock())`). ESC should cancel from any state and also restore pointer lock.
- **Billboarded sprites don't need facing checks** — for Paper Mario style NPCs that always face the camera, interaction triggers are pure distance-based. Dot product facing tests only make sense for 3D models with a defined front/back.
- **Iterative collision loops cause stutters** — `while(!resolved)` patterns doing multiple passes over ALL obstacles per frame create O(n²) work + GC pressure from Box3 allocation. Use single-pass resolution: iterate once, resolve first hit, done. Pre-allocate `_playerBox` as a class property — never `new THREE.Box3()` during collision.
- **Unified ground check** — separate "onGround" vs "onBoxTop" checks create divergent paths that must be maintained independently. One `_findStandingSurface(obstacleBoxes)` scanning floor + all obstacles in one pass works for any flat surface (floor, boxes, stairs, platforms). Add new object types without changing the check.
- **Data URI images load ASYNCHRONOUSLY in Chromium** — Even inline data URIs (`data:image/webp;base64,...`) do NOT load synchronously when assigned to `new Image().src`. The `naturalWidth` is 0 until the `onload` event fires. This means canvas-draw approaches that check `img.naturalWidth === 0` immediately will always fall through to fallbacks (emoji/text). **Fix**: Preload all images properly before scene init — see preload pattern below.
- **Browser Image deduplication with bulk data URI preload** — When preloading many (50+) data URI images using `new Image()` in a tight `for...in` loop, some browsers collapse all loaded Image objects into the same cached instance regardless of unique keys. Symptoms: all textures show the SAME image even though source data URIs are different and verified unique on disk. **Fix**: Use individual IIFE closures capturing both key AND dataUri as parameters (see preload pattern below).
- **THREE.TextureLoader with data URIs produces intermittent black textures** — Despite being the "clean" approach, `TextureLoader.load(dataUri)` was tested extensively with 78 embedded WebP images and produced random black textures on Chrome/Chromium. Root cause: GPU-level race between pixel decoding and WebGL texture upload inside Three.js itself. **Fix**: Use sprite sheet pattern (load as `<Image>`, draw to single canvas, extract regions) — see preload pattern above.
- **Chrome `img.decode()` is NOT reliable for all data URIs** — Despite being documented as mandatory for large data URIs, `decode()` can still produce textures that render intermittently black on some browsers/GPUs. The root cause appears to be a race between pixel decoding and WebGL texture upload that `decode()` doesn't fully resolve.
- **`createImageBitmap` can fail silently on WebP data URIs** — Even when `<img>` elements load fine, `createImageBitmap(img)` may reject for certain WebP images depending on browser/GPU. Always add a fallback in the `.catch()` handler that draws directly from the original `<img>` element to canvas: `renderCardTexture(key, img)`. Without this fallback, failed images skip texture creation entirely and fall through to text-only placeholders.
- **Canvas-draw-from-dataURI produces intermittent black textures** — Even when `img.decode()` resolves successfully, drawing to canvas then wrapping in `THREE.CanvasTexture` can produce black textures on some browsers/GPUs. The image data is valid (verified with Pillow), the decode promise resolved, but the WebGL texture upload silently fails. This is an intermittent GPU-level issue that cannot be reliably fixed at the application layer. **Fix**: Use sprite sheet pattern — draw all images to one canvas during preload, then extract regions per-card from that already-rendered canvas.

### Correct Data URI Preload Pattern (78+ images) — Sprite Sheet (MOST RELIABLE)

**Load all images as `<Image>` objects, draw onto a single sprite sheet canvas, then extract regions per-card.** This is the most reliable approach for embedded data URIs — it eliminates per-texture loading race conditions entirely:

```javascript
// Global sprite sheet — populated during preload
var CARD_SPRITE_SHEET = null;
var SPRITE_COLS = 13; // 13 wide × 6 high = 78 cards
var SPRITE_CELL_W = 256;
var SPRITE_CELL_H = 512;

(function preloadAndInit() {
  var total = Object.keys(IMAGE_DATA).length;
  var started = false;
  var keys = [];
  for (var ki in IMAGE_DATA) {
    if (IMAGE_DATA.hasOwnProperty(ki)) keys.push(ki);
  }
  window.CARD_IMAGE_ORDER = keys; // For card lookup by index

  var loadedImages = {};
  var loaded = 0;

  // Load each image as a plain <Image> object
  for (var i = 0; i < keys.length; i++) {
    (function(key, dataUri) {
      var img = new Image();
      img.onload = function() {
        loadedImages[key] = img;
        loaded++;
        if (loaded >= total && !started) buildSpriteSheet();
      };
      img.onerror = function() {
        console.warn('Image load failed:', key);
        loaded++;
        if (loaded >= total && !started) buildSpriteSheet();
      };
      img.src = dataUri;
    })(keys[i], IMAGE_DATA[keys[i]].c);
  }

  // After all images loaded, draw them onto one big canvas
  function buildSpriteSheet() {
    started = true;
    var cols = SPRITE_COLS;
    var rows = Math.ceil(total / cols);
    var sheetW = cols * SPRITE_CELL_W;
    var sheetH = rows * SPRITE_CELL_H;

    var canvas = document.createElement('canvas');
    canvas.width = sheetW;
    canvas.height = sheetH;
    var ctx = canvas.getContext('2d');

    for (var i = 0; i < keys.length; i++) {
      var img = loadedImages[keys[i]];
      if (!img || !img.width) continue;

      var col = i % cols, row = Math.floor(i / cols);
      var dx = col * SPRITE_CELL_W, dy = row * SPRITE_CELL_H;

      // Scale to fit cell maintaining aspect ratio, centered
      var scale = Math.min(SPRITE_CELL_W / img.width, SPRITE_CELL_H / img.height);
      var dw = img.width * scale, dh = img.height * scale;
      ctx.drawImage(img, dx + (SPRITE_CELL_W - dw)/2, dy + (SPRITE_CELL_H - dh)/2, dw, dh);
    }

    CARD_SPRITE_SHEET = canvas;
    startScene();
  }

  setTimeout(function() {
    if (!started) buildSpriteSheet(); // Proceed even with partial load
  }, 15000);

  function startScene() { /* ... */ }
})();
```

Then extract per-card textures from the sprite sheet:

```javascript
function createCardFrontTexture(cardData) {
  if (!CARD_SPRITE_SHEET) return fallbackTexture(cardData);

  var imgKey = cardData.suit + '_' + cardData.number;
  var idx = CARD_IMAGE_ORDER.indexOf(imgKey);
  if (idx < 0) return fallbackTexture(cardData);

  var col = idx % SPRITE_COLS, row = Math.floor(idx / SPRITE_COLS);

  // Extract this card's region into a fresh canvas
  var c = document.createElement('canvas');
  c.width = SPRITE_CELL_W; c.height = SPRITE_CELL_H;
  var ctx = c.getContext('2d');
  ctx.drawImage(CARD_SPRITE_SHEET, col*SPRITE_CELL_W, row*SPRITE_CELL_H, SPRITE_CELL_W, SPRITE_CELL_H, 0, 0, SPRITE_CELL_W, SPRITE_CELL_H);

  // Add text overlay (card name) on top
  ctx.fillStyle = '#C5A55A'; ctx.font = 'bold 16px Georgia'; ctx.textAlign = 'center';
  ctx.fillText(cardData.name, SPRITE_CELL_W/2, SPRITE_CELL_H - 10);

  return new THREE.CanvasTexture(c); // Fresh texture per card — dispose on scene reset!
}
```

**Why this works**: All images are loaded as DOM `<Image>` objects first (no WebGL involved). Then drawn onto a single canvas synchronously. Card textures are created by extracting regions from that canvas — no async loading at draw time, no race conditions between decode and GPU upload. The sprite sheet is the single source of truth for all card art.

**Why NOT TextureLoader?** `THREE.TextureLoader.load(dataUri)` was tested with 78 embedded WebP images (~521KB worker) across Chrome/Firefox/Safari — it produced **intermittent black textures** on some browsers/GPUs despite valid image data. Root cause: a GPU-level race between pixel decoding and WebGL texture upload that exists inside Three.js itself, not fixable from JS. The sprite sheet approach bypasses this by doing all drawing in 2D canvas context (no GPU) before any WebGL interaction.

**Why NOT canvas-draw-per-card?** Drawing each image individually to a canvas then wrapping in `CanvasTexture` has the same intermittent black texture problem — the race condition exists at the WebGL upload layer, not the canvas draw layer. The sprite sheet works because all drawing happens during preload (synchronous, no GPU), and per-card textures are created from an already-rendered canvas region.

**CRITICAL: dispose per-card textures on scene reset** — since `createCardFrontTexture` creates a fresh `CanvasTexture` each time, these MUST be disposed when removing old cards. The standard disposal pattern (see below) handles this correctly by setting `material.map = null` before `.dispose()`.

**Legacy canvas-draw approach (fallback only)** — If you MUST use canvas (e.g., to add text overlays on top of images), preload with `new Image()` + IIFE closures + `img.decode()`:
- **Embedding large image data** — for self-contained single-file apps, convert images to base64 WebP data URIs and embed as a JS object literal (`var CARD_IMAGES = { key: { c: "data:image/webp;base64,...", t: "..." } }`). Phone-friendly sizes: 120px wide for card faces, 60px for thumbnails. Total ~930KB for 78 cards at these sizes. CF Workers accept up to ~1MB gzip upload.
- **Canvas texture from image + text overlay** — if you need text on top of images (e.g., card names), draw the RWS image onto a canvas AFTER loading via TextureLoader, then add name/meaning text below it. Set canvas height dynamically: `c.height = cardH + textArea`. Use `img.naturalWidth / img.naturalHeight` for aspect ratio preservation when scaling to fit.
- **Reversed/flipped textures** — instead of rotating via canvas (`ctx.rotate(Math.PI)`), use Three.js texture rotation: `texture.rotation = Math.PI`. Simpler, no extra canvas allocation, and works with TextureLoader output directly.
- **Geometry/texture aspect ratio mismatch** — if BoxGeometry dimensions (e.g., 1.0×1.71) don't match the texture canvas/image aspect ratio, Three.js stretches textures causing squashed or letterboxed images. Always derive canvas width from image aspect: `texW = Math.round(texH * (img.naturalWidth / img.naturalHeight))`. For RWS tarot cards this is 24:41 ≈ 0.585.
- **Intermittent black textures with embedded data URIs** — If you see random black textures despite valid image data, the root cause is almost always a race condition in the `new Image()` → `decode()` → canvas draw → `CanvasTexture` pipeline. This cannot be reliably fixed at the JS layer. **Fix**: Use `THREE.TextureLoader.load(dataUri)` which handles decode→GPU atomically with zero observed failures across Chrome/Firefox/Safari.
- **WebGL memory leak from undisposed textures/materials** — If black textures appear AFTER several scene resets (works first few times, then randomly fails), the root cause is NOT image loading — it's GPU memory exhaustion. Every time you create `new THREE.MeshStandardMaterial({ map: texture })` and `new THREE.BoxGeometry()`, WebGL allocates resources. Removing objects from the scene via `scene.remove()` does NOT free those resources. After enough cycles, the browser runs out of texture IDs and new textures silently render as black. **Fix**: Always dispose geometries, materials, AND their texture maps before creating replacements (see disposal pattern below). Share static textures (card backs, UI elements) across all instances instead of recreating per object.
- **Shared cached texture mutation** — When caching `THREE.CanvasTexture` or `THREE.Texture` objects in a shared lookup (e.g., one texture per card type), NEVER mutate properties like `.rotation`, `.offset`, or `.repeat` on the cached texture directly. Those mutations persist across all future uses of that texture. If you need per-instance transforms (e.g., reversed cards), apply them to the `THREE.MeshStandardMaterial.rotation` property instead — materials are created fresh per instance and don't affect the shared cache. **Symptom**: A card type works correctly on first draw, then appears upside-down or black on subsequent draws after being reversed once.

### WebGL Resource Disposal Pattern (CRITICAL for scene resets)

When removing objects from the scene (e.g., between game rounds), dispose ALL Three.js resources to prevent GPU memory leaks:

```javascript
// Remove old cards and dispose resources
for (var ri = cardMeshes.length - 1; ri >= 0; ri--) {
  var group = cardMeshes[ri];
  group.traverse(function(obj) {
    if (obj.geometry) obj.geometry.dispose();
    if (obj.material) {
      if (Array.isArray(obj.material)) {
        for (var mi = 0; mi < obj.material.length; mi++) {
          // Set map to null BEFORE dispose — prevents disposing shared/cached textures
          obj.material[mi].map = null;
          obj.material[mi].dispose();
        }
      } else {
        obj.material.map = null;
        obj.material.dispose();
      }
    }
  });
  scene.remove(group);
}
cardMeshes = [];
```

**CRITICAL: `obj.material.map = null` before `.dispose()`** — if your texture is shared across multiple materials (e.g., a card back used by all cards), disposing the material would dispose the shared texture too, causing black textures on subsequent draws. Setting `map = null` severs the reference so only the material wrapper is disposed, not the underlying texture.

**Share static textures** — create once, reuse everywhere:
```javascript
var SHARED_BACK_TEX = null;
function getCardBackTexture() {
  if (!SHARED_BACK_TEX) {
    SHARED_BACK_TEX = createCardBackTexture(); // or THREE.TextureLoader.load(...)
  }
  return SHARED_BACK_TEX;
}
// In card creation: var backMat = new THREE.MeshStandardMaterial({ map: getCardBackTexture() });
```

**Symptoms of this bug**: Works fine for first 3-5 draws, then random cards go black. Refreshing the page fixes it temporarily. Different from loading bugs — those fail consistently on specific images regardless of draw count.

## Verification

Run the Vite dev server and confirm no console errors:

```bash
npx vite --host
# Open http://localhost:5173 in browser, check DevTools console is clean
```

If building a physics demo, verify objects fall with gravity (9.81 m/s²) and collide correctly — if they don't move at all, the most likely cause is Rapier not being awaited during initialization.
