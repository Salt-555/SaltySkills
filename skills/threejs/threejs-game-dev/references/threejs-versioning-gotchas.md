# Three.js Version-Specific Gotchas

## CapsuleGeometry Missing (r128)

**Error**: `THREE.CapsuleGeometry is not a constructor` — causes silent black screen because the exception kills the render loop.

**Cause**: `CapsuleGeometry` was added in Three.js r137. The CDN import at `cdnjs.cloudflare.com/ajax/libs/three.js/r128/` does NOT have it.

**Fix**: Use `CylinderGeometry` as a fallback:
```javascript
// Instead of CapsuleGeometry(radius, length, capSegments, radialSegments)
const bodyGeo = new THREE.CylinderGeometry(PLAYER_RADIUS, PLAYER_RADIUS, PLAYER_HEIGHT - 0.6, 16);
bodyGeo.translate(0, PLAYER_HEIGHT / 2 + offset, 0);
```

**Debug path**: When scene is black but UI renders:
1. Check `typeof THREE !== 'undefined'` → confirms CDN loaded
2. Check `document.querySelectorAll('canvas').length` → confirms renderer created
3. Check browser console for JS exceptions → usually reveals the missing constructor
4. Check specific geometry availability: `typeof THREE.CapsuleGeometry === 'undefined'`

## Shadow Camera Disappearance

**Symptom**: Shadows render at spawn point but disappear as player moves away.

**Cause**: DirectionalLight's shadow camera is fixed in world space. The frustum only covers the area where it was initially positioned.

**Fix**: Keep the light FIXED in world space; only move the shadow camera frustum and the light's target to follow the player. Moving the light position every frame makes shadows behave like a personal spotlight (shadows shift direction as you walk). This matches the canonical rule in `SKILL.md`:
```javascript
// Light position stays FIXED (never moved with the player)
sunLight.position.set(50, 80, -40);

// Every frame — follow the player with the shadow frustum + target only
sunLight.target.position.copy(playerGroup.position);
sunLight.shadow.camera.left = -25;
sunLight.shadow.camera.right = 25;
sunLight.shadow.camera.top = 25;
sunLight.shadow.camera.bottom = -25;
sunLight.shadow.camera.updateProjectionMatrix(); // CRITICAL after changing bounds
```

> **Note:** an older variant updated `sunLight.position` alongside `target` every frame. That path works but is less correct (spotlight effect, inconsistent shadow direction) and is superseded by the fixed-light pattern above.

## Movement Axis Collapse Bug

**Symptom**: WASD movement only works on one axis at a time. Diagonal input (W+D) collapses to straight forward or straight right.

**Cause**: Using `quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), yaw).applyQuaternion(moveDir)` where `moveDir` is already built from key state as axis-aligned vectors causes the quaternion rotation to collapse diagonal input onto a single axis.

**Fix**: Build movement from explicit forward/right unit vectors derived from yaw:
```javascript
const forward = new THREE.Vector3(-Math.sin(yaw), 0, -Math.cos(yaw));
const right = new THREE.Vector3(Math.cos(yaw), 0, Math.sin(yaw));
const moveDir = new THREE.Vector3(0, 0, 0);
if (keys.w) moveDir.add(forward);
if (keys.s) moveDir.sub(forward);
if (keys.a) moveDir.sub(right);
if (keys.d) moveDir.add(right);
moveDir.normalize(); // Critical — prevents diagonal speed hack
```

> **Note:** this manual-yaw approach only applies to the narrow yaw-only quaternion-collapse bug above (where you already have an explicit `yaw` value). For general third-person movement the **standard is `camera.getWorldDirection()`** projected onto the XZ plane (see `SKILL.md` §6) — it matches what the camera actually sees and avoids the sign-flip fragility of hand-rolled `sin/cos` vectors.

## Collision Detection Performance

**Anti-pattern**: Creating `new THREE.Box3().setFromObject(mesh)` every frame for static obstacles. This allocates memory and computes bounds unnecessarily.

**Fix**: Pre-compute bounding boxes once at startup:
```javascript
const obstacleBoxes = [];
for (let i = 0; i < obstacles.length; i++) {
    obstacleBoxes.push(new THREE.Box3().setFromObject(obstacles[i]));
}
// Then in game loop, just use the pre-computed boxes directly.
```
