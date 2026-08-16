# Sniper Ballistics Pattern (Hitscan)

From the sniper project build.

## Hitscan Raycasting

```javascript
class SniperBallistics {
    constructor(camera, scene) {
        this.raycaster = new THREE.Raycaster(); // reused every frame
        this.shootableObjects = []; // tracked separately from full scene

        // Ammo: 5 magazine + 10 reserve
        this.magazineSize = 5;
        this.ammoInMag = 5;
        this.reserveAmmo = 10;
        this.reloadTime = 2.0;
        this.minFireRate = 0.5; // seconds between shots

        // Spread: tight when scoped, wide without
        this.scopedSpread = 0.001;
        this.unscopedSpread = 0.02;
    }

    fire(isScoped) {
        if (this.ammoInMag <= 0 || this.isReloading || this.fireCooldown > 0) return null;

        this.ammoInMag--;
        this.fireCooldown = this.minFireRate;

        // Slight random spread
        const spread = isScoped ? this.scopedSpread : this.unscopedSpread;
        this.raycaster.setFromCamera(
            new THREE.Vector2((Math.random()-0.5)*2*spread, (Math.random()-0.5)*2*spread),
            camera
        );

        const hits = this.raycaster.intersectObjects(this.shootableObjects, true);
        return hits.length > 0 ? { hit: true, object: hits[0].object, point: hits[0].point } : null;
    }

    registerTarget(obj) {
        if (!this.shootableObjects.includes(obj)) {
            this.shootableObjects.push(obj);
            obj.userData.shootable = true;
        }
    }
}
```

## Why Hitscan Over Simulated Bullets?

- Sniper is **stationary** at fixed vantage point
- Distances are known and consistent within a level
- Bullet drop requires leading targets + distance compensation — adds complexity without adding fun when you can't reposition
- Hitscan feels snappy and responsive, critical for browser games

## Impact VFX (12-particle spark burst)

```javascript
class HitEffect {
    play(point, normal) {
        // 12 particles, random spherical velocity biased along surface normal
        const geo = new THREE.BufferGeometry();
        // ... set positions to origin, velocities from sphere distribution
        const points = new THREE.Points(geo, sharedMaterial);
        points.position.copy(point);
        scene.add(points);
        // Fade over 0.4s with gravity
    }
}
```

Zero triangle cost — uses `THREE.Points`. Shared material across all hit effects for draw call batching.
