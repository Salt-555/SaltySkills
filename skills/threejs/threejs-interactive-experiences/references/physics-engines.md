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
await RAPIER.init();

const physicsWorld = new RAPIER.World({ x: 0, y: 0, z: -9.81 });

// Create character as kinematic-position-based body
const characterBody = physicsWorld.createRigidBody(
  RAPIER.RigidBodyDesc.kinematicPositionBased().setTranslation(0, 2, 0)
);

// Add capsule collider for collision detection
const characterCollider = physicsWorld.createCollider(
  RAPIER.ColliderDesc.capsule(0.5, 1.0).setRestitution(0.0),
  characterBody
);

// Ground plane (static body + cuboid collider)
const groundBody = physicsWorld.createRigidBody(RAPIER.RigidBodyDesc.fixed());
physicsWorld.createCollider(
  RAPIER.ColliderDesc.cuboid(50.0, 0.5, 50.0).setTranslation(0, -0.5, 0), // finite half-extents
  groundBody
);

// In game loop: step() takes an optional EventQueue, not a timestep number.
// The fixed timestep is world.timestep (default 1/60).
physicsWorld.step();

// Sync Three.js mesh to physics body
const pos = characterBody.translation();
mesh.position.set(pos.x, pos.y, pos.z);
```

### Character Movement Pattern (KinematicCharacterController)

For a kinematic-position body, `setLinvel` has no effect — you must drive movement through the character controller's `setNextKinematicTranslation`.

```javascript
// Create a kinematic character controller (handles stairs, slopes, ground snapping)
const kcc = physicsWorld.createCharacterController(0.01);
kcc.setUp({ x: 0, y: 1, z: 0 });              // world "up"
kcc.enableAutostep(0.2, 0.1, true);           // step over small obstacles
kcc.enableSnapToGround(0.2);                  // snap to the ground while walking
kcc.setSlopeClimbAngle(45 * Math.PI / 180);   // max walkable slope

// Each frame (after world.step()), build a desired movement delta:
const direction = new THREE.Vector3(input.x, 0, input.z);
direction.applyQuaternion(cameraQuaternion); // relative to camera
direction.normalize().multiplyScalar(moveSpeed);

const moveVec = new RAPIER.Vector3(direction.x, 0, direction.z);
if (!isGrounded) {
  moveVec.y = currentVel.y;        // carry vertical velocity
} else if (jumpPressed) {
  moveVec.y = jumpVelocity;        // jump impulse
}

// Resolve the controller's movement against colliders, then apply the
// collision-clamped delta to the kinematic body.
kcc.computeColliderMovement(characterCollider, moveVec);
const effective = kcc.computedMovement();
const nextPos = characterBody.translation();
characterBody.setNextKinematicTranslation({
  x: nextPos.x + effective.x,
  y: nextPos.y + effective.y,
  z: nextPos.z + effective.z,
});
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
