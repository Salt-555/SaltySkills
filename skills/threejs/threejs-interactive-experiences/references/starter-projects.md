# Forkable Starter Projects for Three.js Interactive Experiences

## Ranked by "Ready to Build On"

### 1. icurtis1/third-person-controller-splat ⭐ RECOMMENDED

**GitHub:** https://github.com/icurtis1/third-person-controller-splat
**Live Demo:** https://third-person-character-controller.netlify.app/
**License:** MIT
**Stack:** Three.js r180, Rapier 0.12, Vite 6, TypeScript

**What's included:**
- Third-person orbit camera with zoom (right-click drag + scroll)
- Rapier kinematic character controller (KCC) — handles stairs, slopes, ground snapping
- WASD movement + Shift sprint + Space jump
- Animation crossfading: idle → walk → air idle (auto-detects grounded state)
- Character model swapping via `CHARACTER_ASSETS` config block
- Environment/world swapping via `WORLD_ASSETS` config block
- Post-processing (bloom, vignette, brightness/contrast)
- lil-gui tuning panel for live parameter adjustment
- Single-file architecture (`src/main.ts`) — readable top to bottom

**Controls:** WASD move, Shift sprint, Space jump, 1 emote, Right-click drag orbit camera, Scroll zoom

**To adapt for storefronts:**
```typescript
// In src/main.ts, replace:
const WORLD_ASSETS = {
  splatSpz: '/your-shop.spz',     // or remove entirely for glTF scene
  colliderGlb: '/shop-collider.glb', // invisible collision mesh
  colliderGlbUniformScale: 1,
};

const CHARACTER_ASSETS = {
  glb: '/character.glb',          // your character model
};

// Animation clip names — match your model's animation names:
const CLIP_HAPPY_IDLE = 'Idle';
const CLIP_AIR_IDLE   = 'Air Idle';
const CLIP_WALK       = 'Walk';
```

**Pros:** Most complete out of the box, explicitly designed as forkable template, well-documented customization guide, actively maintained
**Cons:** Gaussian splat dependency is unnecessary for most use cases (but easily removed), pinned to Three.js r180

---

### 2. larvuz2/physics-character-controller-3d

**GitHub:** https://github.com/larvuz2/physics-character-controller-3d
**License:** MIT
**Stack:** Three.js, Rapier, Vite, JavaScript (vanilla)

**What's included:**
- Rapier physics world with capsule character collider
- WASD movement + Space jump
- Third-person camera follow
- Ground collision detection
- Clean modular file structure: `physics.js`, `character.js`, `input.js`, `scene.js`

**Pros:** Simplest to understand, every line is readable, no TypeScript overhead, good educational starting point
**Cons:** No animation system (just a capsule), basic camera without orbit controls, no post-processing, JavaScript not TypeScript

---

### 3. BeardScript/RogueThirdPersonTemplate

**GitHub:** https://github.com/BeardScript/RogueThirdPersonTemplate
**License:** Public
**Stack:** Rogue Engine, Three.js, Rapier, TypeScript

**What's included:**
- Animated third-person character with Mixamo animations
- Player controller in both code (`PlayerController.re.ts`) and visual scripting (`VCPlayerController.vc.ts`)
- Rapier physics integration
- Works within Rogue Engine desktop editor (Unity-like environment)

**Pros:** Visual editor for scene building, dual code/no-code approach, professional animation setup
**Cons:** Requires downloading Rogue Engine desktop app, adds dependency layer, smaller community, learning curve for Rogue's component system

---

### 4. THREE-BasicThirdPersonGame (matthias-schuetz)

**GitHub:** https://github.com/matthias-schuetz/THREE-BasicThirdPersonGame
**License:** MIT
**Stack:** Three.js r61, Cannon.js 0.5.0, JavaScript

**What's included:**
- Third-person follow camera with adjustable offset
- Player movement, jumping, acceleration, rotation
- Cannon.js physics (rigid bodies, friction, collision)
- Level management with reset mechanism
- Grunt build system

**Pros:** Well-documented architecture, includes demos, MIT licensed
**Cons:** OLD — Three.js r61 is from 2014, Cannon.js 0.5.0 is outdated, would need significant modernization to use as-is. Architecture patterns are still valid for reference.

---

### 5. threejs-games (threejs-games)

**GitHub:** https://github.com/threejs-games/threejs-games
**Live Demo:** https://threejs-games.github.io/
**License:** MIT

**What's included:**
- Library of reusable Three.js game components
- Third-person character controller demo (playable live)
- Platformer, simulation examples
- Modular — mix and match components

**Pros:** Playable demos, modular component library, good for learning individual systems
**Cons:** Not a cohesive starter template — more of a component showcase, would need assembly

---

## Quick Decision Guide

| If you want... | Start with... |
|---|---|
| Most complete controller, ready to fork | icurtis1/third-person-controller-splat |
| Simplest code to read and understand | larvuz2/physics-character-controller-3d |
| Visual editor + no-code option | RogueThirdPersonTemplate |
| React stack with physics | `npx r3f-template` (physics preset) |
| Reference for architecture patterns | THREE-BasicThirdPersonGame |
