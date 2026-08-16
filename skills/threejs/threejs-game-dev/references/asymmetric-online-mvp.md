# Asymmetric Online Game MVP Boundary

## Product goal vs mechanical harness

When the intended product is online matchmaking, do not redefine the MVP as local shared-machine multiplayer merely because a single-client prototype is faster.

Use a **single-client mechanical harness** only to validate mechanics:
- Expose both role controls temporarily.
- Label it clearly as a test harness, not the target multiplayer design.
- Keep role logic in separate classes/modules.
- Keep round state deterministic and serializable.
- Avoid assumptions that both roles share a camera, input device, or process.

Target architecture for two-player asymmetric play:
- Separate Sniper and Mimic clients.
- Authoritative room server over WebSockets.
- Server owns timer, round transitions, ammo, transformations, and shot validation.
- Mimic client predicts its own movement; server reconciles snapshots.
- Sniper client sends aim/shot intent; server resolves against authoritative state.
- Matchmaking/lobby service assigns role and room before gameplay.

## Vantage-camera verification

A numerically plausible camera can still face the wrong side of the arena or be blocked by its own platform.

Before declaring the MVP playable:
1. Start the actual round in a browser.
2. Project the target position into NDC; the target should have `x/y` near `[-1,1]` and `z` in the visible clip range.
3. Visually inspect the view from the real vantage point.
4. Confirm the platform/railing does not cover the reticle or lower half of the useful field.
5. Raycast from camera toward the target and verify the first hit is the intended target, not the platform or map shell.
6. Re-run after changing camera position, pitch, or arena orientation.

Do not trust `camera.lookAt` intuition or coordinate-sign assumptions without this check.