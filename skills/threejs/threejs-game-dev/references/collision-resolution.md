# AABB Collision Resolution — Three.js Without Physics Engine

Third-person game build on Pi 5.

## Problem

Player could land *inside* boxes instead of on top. Y-overlap hack allowed clipping through obstacles. Iterative `while(!resolved)` loops caused chunky stutters (0.5s freeze) on jump/land due to O(n²) work + GC pressure from Box3 allocation per frame.

## Solution: Axis-Separated Penetration Resolution

### Single-Pass Collision Resolver

> **Illustrative:** the resolver below references a few assumed values — `obstacleCenter` = the obstacle box center (`obstacleBox.getCenter(...)`), `playerBottom` = the player's foot Y (`pos.y`), and `boxTop` = `obstacleBox.max.y`. Treat them as defined where this is shown; the surrounding project wires them in.

```javascript
// Pre-allocated — NEVER allocate during collision
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

    // Resolve along SMALLEST penetration axis (standard AABB approach)
    if (overlapX < overlapY && overlapX < overlapZ) {
        // Push out on X — slide along wall
        pos.x += (pos.x < obstacleCenter.x) ? -overlapX : overlapX;
    } else if (overlapY < overlapZ) {
        // Push out on Y
        if (playerBottom <= boxTop && velocityY <= 0) {
            pos.y = obstacleBox.max.y; // Land on top
            this.velocityY = 0;
        } else {
            pos.y -= overlapY; // Hit ceiling
        }
    } else {
        // Push out on Z — slide along wall
        pos.z += (pos.z < obstacleCenter.z) ? -overlapZ : overlapZ;
    }
    return true;
}
```

### Unified Ground Check

Scans floor plane AND all obstacles in one pass. Returns surface Y or null if airborne:

```javascript
_findStandingSurface(obstacleBoxes) {
    let surfaceY = 0; // Floor as default candidate

    for (const box of obstacleBoxes) {
        const xOverlap = px + radius > box.min.x && px - radius < box.max.x;
        const zOverlap = pz + radius > box.min.z && pz - radius < box.max.z;
        if (xOverlap && zOverlap) {
            const distToTop = py - box.max.y;
            if (distToTop >= -TOLERANCE && distToTop <= TOLERANCE) {
                surfaceY = Math.max(surfaceY, box.max.y); // Highest valid surface wins
            }
        }
    }

    return (Math.abs(py - surfaceY) <= tolerance) ? surfaceY : null;
}
```

### Integration Order in Game Loop

1. **Gravity** → apply `velocityY += gravity * delta`, update Y position
2. **Ground check** → `_findStandingSurface()` returns surface or null
3. **If standing** → snap to surface, zero velocity, allow jump
4. **Horizontal movement** → single pass through obstacles, resolve first hit
5. **No iterative loops** — one collision check per axis per frame

## Pitfalls Encountered

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| 0.5s stutter on jump/land | `while(!resolved)` doing 2-3 passes over ALL obstacles + new Box3() each call | Single-pass resolution, pre-allocated Box3 |
| Player lands inside boxes | Y-overlap check only blocked horizontal movement, didn't resolve onto top face | Axis-separated penetration: smallest overlap wins, Y push-up = landing |
| Two ground checks (`isOnGround` + `isOnBoxTop`) | Divergent paths for floor vs box surfaces | Unified `_findStandingSurface()` — one pass covers everything |

## Key Numbers

- Gravity: `-25 m/s²` (feels right for platformer)
- Jump force: `9 m/s` (~1.6m peak height)
- Ground tolerance: `0.15 units` (prevents micro-bouncing on surfaces)
- Air control factor: `0.4x` when airborne (steerable but not floaty)
