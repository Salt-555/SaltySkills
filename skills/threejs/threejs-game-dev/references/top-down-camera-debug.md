# Top-Down Camera Debug Log — Fantasy Roguelite Build

## Symptom

New Three.js top-down 2.5D game (Streets of Rogue style, Vite + npm three). Class-select screen worked, game state reached `playing`, canvas existed — but every screenshot showed a **horizontal, ground-level view** instead of a bird's-eye view.

## Failed Approaches (in order)

1. **Pivot Group + `pivot.rotation.x = -0.4`** — camera childed to a Group at `(0, 8, 6)`. Rendered horizontal. Increased to `-0.6`, height 15 — still horizontal.
2. **Higher pivot + steeper rotation** (`y=20`, `rotation.x = -Math.PI/2.5`) — console showed local rotation correct, but `getWorldDirection().y = -0.95` while the screenshot STILL looked horizontal. Contradiction resolved: the view WAS angled down, but so steeply and so close that the player model filled the frame and nearby building walls read as a "horizon."
3. **`camera.lookAt(0, -1, 0.5)` in constructor** — produced junk world orientation (`rotation.z ≈ -π`) because lookAt computes full basis; result worse than rotation.set.
4. **Near-vertical offset `(0, 30, 0)`** — camera directly overhead: player cylinder filled the entire screen, world invisible.

## Root Causes (compound)

- Parented-pivot rotation is fragile: local rotation on a child camera interacts with parent transforms in ways that are hard to reason about, and `lookAt` in a constructor computes against an un-updated world matrix.
- A near-vertical top-down camera at low altitude makes the player mesh dominate the frame — you need horizontal offset (Z distance) as well as height so the world around the player is visible.
- Verifying via state (`game.state === 'playing'`, canvas exists) is NOT visual verification. Only a screenshot catches "camera looks the wrong way."

## Verified Working Pattern

Position camera directly in world space every frame, `lookAt` the player every frame:

```javascript
this._offset = new THREE.Vector3(0, 15, 12); // height + distance behind
// in update():
this.camera.position.x += (targetPos.x + this._offset.x - this.camera.position.x) * delta * 5;
this.camera.position.y += (targetPos.y + this._offset.y - this.camera.position.y) * delta * 5;
this.camera.position.z += (targetPos.z + this._offset.z - this.camera.position.z) * delta * 5;
// lookahead + lookAt
this._lookAt.copy(targetPos);
this._currentLookAt.lerp(this._lookAt, delta * 3);
this.camera.lookAt(this._currentLookAt);
```

Offset `(0, 15, 12)` → ~50° downward angle, player small in frame, 6-8 buildings visible, minimap matches main view. Confirmed via screenshot.

## Diagnostics That Helped

- `camera.getWorldDirection(v).y` — must be ≤ −0.8 for top-down. If near 0, camera is horizontal no matter what local rotation claims.
- `camera.getWorldPosition(v)` vs `player.position` — confirms whether camera is actually above the player.
- Screenshot after EVERY camera change — console numbers alone misled twice (numbers said "looking down," render said "horizontal").

## Related Spawn/Lighting Fixes From the Same Build

- Random-position spawn with rejection sampling put the player inside a building → camera spawned inside geometry showing only interior walls. Fix: fixed safe-zone spawn (central plaza, radius 2-5 from origin).
- Scene unreadably dark with single dim ambient (0.4) + directional. Fix: ambient 1.2 + hemisphere light 0.6 + directional 2.0. Prototype readability > mood lighting.
