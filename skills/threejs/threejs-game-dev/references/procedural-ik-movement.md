# Procedural IK Movement (Spider/Creature Legs)

From the sniper project build.

## Two-Bone IK Solver (Closed-Form, Law of Cosines)

```javascript
function solveTwoBoneIK(hip, knee0, upperLen, lowerLen, target) {
    const maxReach = upperLen + lowerLen - 0.01; // avoid straight-line singularity

    let toTarget = new THREE.Vector3().subVectors(target, hip);
    const dist = toTarget.length();
    const clampedDist = Math.min(dist, maxReach);
    if (dist > 0.001) toTarget.divideScalar(dist);

    // Pole vector: perpendicular to hip→target, toward original knee
    const poleVec = new THREE.Vector3()
        .subVectors(knee0, hip).projectOnPlane(toTarget).normalize();
    if (poleVec.length() < 0.001) {
        poleVec.crossVectors(toTarget, new THREE.Vector3(0, 1, 0)).normalize();
    }

    // Law of Cosines
    const cosTheta = clampedDist > 0.001
        ? (clampedDist*clampedDist + upperLen*upperLen - lowerLen*lowerLen) / (2 * clampedDist * upperLen) : 1;
    const theta = Math.acos(Math.max(-1, Math.min(1, cosTheta)));

    // Knee position
    const kneePos = new THREE.Vector3()
        .addScaledVector(toTarget, upperLen * Math.cos(theta))
        .addScaledVector(poleVec, upperLen * Math.sin(theta));
    kneePos.add(hip);

    const footPos = new THREE.Vector3().addScaledVector(toTarget, clampedDist).add(hip);

    // Rotations via quaternion from-to
    const upperRest = new THREE.Vector3().subVectors(knee0, hip).normalize();
    const upperSolved = new THREE.Vector3().copy(kneePos).sub(hip).normalize();
    const hipQuat = new THREE.Quaternion().setFromUnitVectors(upperRest, upperSolved);

    const lowerRestDir = new THREE.Vector3(0, -1, 0); // rest points down
    const lowerSolved = new THREE.Vector3().subVectors(footPos, kneePos).normalize();
    const lowerRestWorld = lowerRestDir.clone().applyQuaternion(hipQuat);
    const kneeQuat = new THREE.Quaternion().setFromUnitVectors(lowerRestWorld, lowerSolved);

    return { hipQuat, kneePos, kneeQuat, footPos };
}
```

## Gait System (6 Legs)

Each leg has a phase offset. Sine wave determines swing vs stance:

```javascript
class Leg {
    constructor(index, totalLegs, upperLen = 0.6, lowerLen = 0.5) {
        this.phase = (index / totalLegs) * Math.PI * 2;
        // Attach point distributed around sphere bottom
        const angle = this.phase + Math.PI * 0.25;
        this.attachOffset = new THREE.Vector3(
            Math.cos(angle) * 0.35, -0.3, Math.sin(angle) * 0.35
        );
    }

    computeFootTarget(bodyPos, time, speed, gaitRate) {
        const cycle = time * gaitRate + this.phase;
        const swingPhase = (Math.sin(cycle) + 1) / 2; // 0..1
        const isSwinging = swingPhase > 0.5;

        if (isSwinging) {
            const liftT = (swingPhase - 0.5) * 2;
            const liftHeight = Math.sin(liftT * Math.PI) * 0.3;
            // Step forward, with arc lift
            // ... compute target position
        } else {
            // Stance: keep foot planted at last ground position
            if (!this.plantedPos) this.plantedPos = /* initial ground pos */;
            return this.plantedPos;
        }
    }
}
```

**Key tuning**: `gaitRate = 2.0 + speed * 4.0` (2-6 Hz). Idle = slow crawl, fast = rapid scuttle.

## Triangle Budget

| Component | Count | Triangles | Total |
|---|---|---|---|
| Body (Icosahedron d1) | 1 | 80 | 80 |
| Upper leg (Cylinder 5-side) | 6 | 20 | 120 |
| Lower leg (Cylinder 5-side) | 6 | 20 | 120 |
| Foot (Sphere 4x3) | 6 | 24 | 144 |
| **Total** | | | **~464** |

All legs share one `MeshStandardMaterial` = 4 draw calls total.

## Sources

- threejs-procedural-spider: https://github.com/majidmanzarpour/threejs-procedural-spider (8-leg IK, closed-form)
- Two-bone IK theory: https://blog.littlepolygon.com/posts/twobone/ (Law of Cosines derivation)
- 3D two-bone IK: https://timallanwheeler.com/blog/2024/09/28/3d-2-bone-inverse-kinematics/
