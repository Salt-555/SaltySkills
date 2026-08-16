# Physics Engines for Three.js — Comparison

## Rapier (`@dimforge/rapier3d-compat`) ⭐ RECOMMENDED

**Language:** Rust → WASM
**npm:** `npm install @dimforge/rapier3d-compat`
**Three.js manual status:** Officially recommended for modern projects

### Why Rapier Wins
- **Performance:** Significantly faster than Cannon-es and Ammo.js in benchmarks. WASM execution avoids JS overhead.
- **Kinematic Character Controller (KCC):** Built-in capsule-based character movement that handles stairs, slopes, ground snapping automatically. No need to roll your own character physics.
- **Active development:** Regular releases, Rust ecosystem backing.
- **Clean API:** `World`, `RigidBody`, `Collider`, `Joint` — straightforward mapping to game concepts.

### Basic Setup
```javascript
import * as RAPIER from '@dimforge/rapier3d-compat';

// Initialize physics world (async — WASM loads)
const { World, RigidBodyBuilder, ColliderBuilder } = await RAPIER.init();

const physicsWorld = new World(new Float32Array([0, 0, -9.81]));

// Create character as kinematic position-based body
const characterBody = RigidBodyBuilder.kinematicPositionBased()
  .translated(0, 2, 0)
  .built(physicsWorld);

// Add capsule collider for collision detection
ColliderBuilder.capsule(0.5, 1.0)
  .setRestitution(0.0)
  .linkedTo(characterBody)
  .built(physicsWorld);

// Ground plane
const groundBody = RigidBodyBuilder.fixed()
  .built(physicsWorld);

ColliderBuilder.cuboid Infinity, 0.5, Infinity) // half-extents
  .translated(0, -0.5, 0)
  .linkedTo(groundBody)
  .built(physicsWorld);

// In game loop:
physicsWorld.step(dt);

// Sync Three.js mesh to physics body
const pos = characterBody.translation();
mesh.position.set(pos.x, pos.y, pos.z);
```

### Character Movement Pattern
```javascript
// Apply linear velocity for WASD movement
const direction = new THREE.Vector3(input.x, 0, input.z);
direction.applyQuaternion(cameraQuaternion); // relative to camera
direction.normalize().multiplyScalar(moveSpeed);

characterBody.setLinvel({ x: direction.x, y: currentVel.y, z: direction.z }, true);

// Jump
if (isGrounded && jumpPressed) {
  characterBody.setLinvel({ x: currentVel.x, y: jumpVelocity, z: currentVel.z }, true);
}
```

---

## Cannon-es

**Language:** Pure JavaScript (fork of Cannon.js)
**npm:** `npm install cannon-es`

### When to Use
- Simple prototypes where WASM setup is overkill
- Need to debug physics in plain JS (easier to step through)
- Smaller bundle size matters and you don't need KCC

### Limitations
- No built-in character controller — you roll your own capsule movement
- Slower than Rapier for complex scenes (JS vs WASM)
- Less actively maintained than Rapier

---

## Ammo.js

**Language:** C++ Bullet Physics → WASM (Emscripten)
**npm:** `npm install ammo.js`

### When to Use
- Need vehicle physics, soft bodies, or advanced constraints
- Porting existing Bullet Physics code

### Limitations
- Most complex setup — Emscripten memory management, async loading quirks
- Largest bundle size (~3MB WASM)
- Steep learning curve for the C++-style API
- Overkill for character controllers and basic collision

---

## Decision Matrix

| Feature | Rapier | Cannon-es | Ammo.js |
|---|---|---|---|
| Character controller (KCC) | ✅ Built-in | ❌ Roll your own | ⚠️ Complex |
| Performance | ⭐⭐⭐ WASM | ⭐⭐ JS | ⭐⭐⭐ WASM |
| Bundle size | ~300KB | ~100KB | ~3MB |
| Setup complexity | Low | Lowest | High |
| Active maintenance | ✅ Yes | ⚠️ Moderate | ⚠️ Moderate |
| Three.js examples | Many | Some | Fewer |
| Best for | **Most projects** | Simple prototypes | Vehicle/soft body physics |

## Recommendation

Use Rapier unless you have a specific reason not to. The KCC alone saves days of character movement debugging, and the performance headroom matters as scenes get complex.
