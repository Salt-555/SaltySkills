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

**Fix**: Update light position AND target every frame:
```javascript
sunLight.position.set(
    playerGroup.position.x + 10,
    20,
    playerGroup.position.z + 10
);
sunLight.target.position.copy(playerGroup.position);
// Also widen the shadow camera bounds to cover a reasonable area
sunLight.shadow.camera.left = -25;
sunLight.shadow.camera.right = 25;
sunLight.shadow.camera.top = 25;
sunLight.shadow.camera.bottom = -25;
```

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
