---
name: threejs-interactive-experiences
description: "Use when building interactive 3D browser experiences with Three.js — character controllers, walkable environments, product showrooms, virtual stores, or any WebGL experience where the user navigates a 3D space. Covers third-person/first-person cameras, physics integration, animation systems, raycasting for object interaction, and project scaffolding."
version: 1.0.0
author: Almi
license: MIT
metadata:
  hermes:
    tags: [threejs, webgl, three-dimensional, character-controller, interactive, storefront, browser-game]
    related_skills: [phaser-3, popular-web-designs, sketch]
---

# Three.js Interactive Experiences

## Overview

Three.js is the standard JavaScript library for WebGL 3D rendering in the browser. It abstracts raw WebGL shaders and buffers into a scene graph API (`scene.add(mesh)`). For interactive experiences — walkable environments, virtual stores, product showrooms, exploratory demos — it's the go-to toolchain because it runs everywhere without installation.

This skill covers building **interactive 3D experiences** where users navigate a space with a character controller and interact with objects. Not raw WebGL shader work (use custom shaders for that) and not 2D canvas games (use Phaser).

## When to Use

- User wants a walkable 3D environment in the browser
- Building a virtual store/showroom where users browse products in 3D space
- Creating an interactive product configurator with spatial navigation
- Any "walk around and interact" experience that runs in-browser
- Third-person or first-person character controllers
- **Non-interactive 3D renders** — rotating logos, product shots, brand animations exported as video (use Three.js + `MediaRecorder` for HTML-based capture, or fall back to Manim CE when the agent needs to deliver a file directly)

## Video Delivery Pitfalls

When building non-interactive 3D renders that need to be sent in chat:
1. **Browser canvas capture is unreliable** — `canvas.toDataURL()` often returns blank/empty data due to sandbox restrictions and timing issues
2. **File paths don't work for file delivery** — sending `/path/to/file.mp4` just shows the filesystem, not actual media content
3. **Use Manim CE instead** when you need guaranteed video output: `manim scene.py Class -pqh --disable_caching`, then copy from `media/videos/` and send via MEDIA: path
4. **For interactive demos** (where user clicks "Start Render"), use the Three.js + MediaRecorder approach in the HTML itself — let the user download the file directly

## Common Pitfalls
- Heavy multiplayer games (use Godot/Unity + export)
- VR-only experiences (use A-Frame / WebXR directly)
- Simple 3D model viewers without navigation (just use `<model-viewer>` web component)

## Architecture Stack

Every interactive 3D experience needs these layers:

| Layer | Purpose | Recommended Choice |
|---|---|---|
| **Rendering** | 3D graphics, materials, lighting | Three.js (standard) |
| **Physics** | Collision detection, gravity, rigid bodies | Rapier (`@dimforge/rapier3d-compat`) — WASM, fastest, actively maintained |
| **Animation** | Skeletal character movement | Three.js `AnimationMixer` + glTF from Mixamo or Blender |
| **Camera** | Follows player (third-person) or IS the player (first-person) | Custom lerp-based follow camera or `OrbitControls` |
| **Input** | Keyboard/mouse/gamepad | Custom event handlers + `PointerLockControls` for FPS |
| **Interaction** | Picking objects, clicking products | Three.js `Raycaster` — cast ray from camera, detect intersections |
| **Build** | Dev server, bundling, TypeScript | Vite (fast HMR) + TypeScript |

### Physics Engine Selection

- **Rapier** (`@dimforge/rapier3d-compat`) — Rust → WASM. Best performance, built-in kinematic character controller (KCC), capsule colliders. Official Three.js manual recommends it for modern projects.
- **Cannon-es** — Pure JS fork of Cannon.js. Easier to debug but slower. Good for simple prototypes.
- **Ammo.js** — Bullet Physics port to WASM. Most features, most complex setup. Only use if you need vehicle physics or soft bodies.

## Starting Points (Forkable Templates)

### Best General-Purpose: icurtis1/third-person-controller-splat

[GitHub](https://github.com/icurtis1/third-person-controller-splat) · [Live Demo](https://third-person-character-controller.netlify.app/)

**What you get:** Third-person orbit camera, Rapier KCC physics, WASD + sprint + jump, animation crossfading (idle→walk→air), character model swapping, TypeScript + Vite, post-processing, tunable GUI.

**Why it wins:** Explicitly designed as a "ready-to-fork template for building 3D games." Single `main.ts` file — readable top to bottom. Environment is swappable (Gaussian splats are just one option; replace with any glTF scene).

**To adapt for storefronts:**
1. Replace Gaussian splat environment with your shop glTF scene
2. Replace character model with your own or keep the default
3. Add `Raycaster` for product interaction on top of existing controller
4. Cart/checkout as HTML overlay — no 3D needed

### Simplest to Understand: larvuz2/physics-character-controller-3d

[GitHub](https://github.com/larvuz2/physics-character-controller-3d)

**What you get:** Rapier physics, WASD movement, jump, third-person camera follow, capsule collider. Clean file separation (`physics.js`, `character.js`, `input.js`, `scene.js`). Vanilla JS.

**Use when:** You want to read every line and understand the full pipeline before adding features. Less polished than icurtis1 but more educational.

### For React Stacks: r3f-template CLI

```bash
npx r3f-template
```

Choose "physics" preset → gets you player controls + Rapier pre-configured with React Three Fiber. Good if your storefront already uses React.

## Core Patterns

### Third-Person Camera (lerp-based follow)

```javascript
// In render loop, after physics step:
const character = rigidBody;  // from Rapier
const position = character.translation();
const rotation = character.rotation();

// Offset behind and above character
const cameraOffset = new THREE.Vector3(0, 3, 5);
cameraOffset.applyQuaternion(rotation);
cameraOffset.add(position);

// Target slightly above feet (avoids ground clipping)
const targetOffset = new THREE.Vector3(0, 1, 0);
targetOffset.applyQuaternion(rotation);
targetOffset.add(position);

// Smooth follow — adjust lerp factor for responsiveness
camera.position.lerp(cameraOffset, 0.05);
controls.target.lerp(targetOffset, 0.1);
```

### Raycasting for Object Interaction

```javascript
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2(0, 0); // center of screen

// Every frame or on key press:
raycaster.setFromCamera(mouse, camera);
const intersects = raycaster.intersectObjects(pickableItems, true);

if (intersects.length > 0 && intersects[0].distance < INTERACT_RANGE) {
  const item = intersects[0].object;
  showInteractPrompt(item.userData.productName);
}
```

### Animation State Machine

```javascript
const mixer = new THREE.AnimationMixer(characterMesh);
const clips = {
  idle: THREE.AnimationClip.findByName(animations, 'Idle'),
  walk: THREE.AnimationClip.findByName(animations, 'Walk'),
  run:  THREE.AnimationClip.findByName(animations, 'Run'),
};

function setAnimation(name, duration = 0.3) {
  const clip = clips[name];
  if (!clip || currentAction?.clip === clip) return;
  
  const newAction = mixer.clipAction(clip);
  newAction.reset();
  newAction.enabled = true;
  newAction.fadeIn(duration);
  
  if (currentAction) currentAction.fadeOut(duration);
  currentAction = newAction;
}
```

### glTF Model Loading

```javascript
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const loader = new GLTFLoader();
loader.load('/models/character.glb', (gltf) => {
  const model = gltf.scene;
  const animations = gltf.animations; // AnimationClip[]
  
  model.traverse((child) => {
    if (child.isMesh) {
      child.castShadow = true;
      child.receiveShadow = true;
    }
  });
  
  scene.add(model);
});
```

## Building a Virtual Storefront

### Architecture

```
3D Scene (Three.js canvas)          HTML Overlay (position: fixed)
┌─────────────────────────┐        ┌──────────────────────┐
│                         │        │  🛒 Cart (3 items)   │
│    Shop environment     │        │                      │
│    Shelves + products   │        │  [E] Pick up Widget  │
│    Character walking    │        │                      │
│    Checkout counter     │        └──────────────────────┘
└─────────────────────────┘        
         ↓ raycast
   Product detected → add to cart state
         ↓ walk to zone
   Checkout counter → Stripe modal
```

### Implementation Steps

1. **Fork** `icurtis1/third-person-controller-splat` or start from `larvuz2/physics-character-controller-3d`
2. **Model shop** in Blender: floor, walls, shelves, product placeholders, checkout counter → export as glTF
3. **Replace environment**: Swap the default scene for your shop glTF + Rapier collision trimesh
4. **Tag products** with `userData`: Each shelf item gets `{ productId, name, price, pickable: true }`
5. **Raycast on "E" key**: Cast from camera center, check distance < 3 units, show HTML prompt
6. **Cart state**: Plain JavaScript object or Zustand store — items array with product data
7. **Checkout zone**: Distance check to checkout counter position → show payment modal (Stripe Elements)
8. **Deploy**: Vite build → static hosting (Netlify, Cloudflare Pages, your own server)

### Performance Considerations

- **Pi 5 / mobile**: Reduce polygon count, use baked lighting instead of real-time shadows, limit draw calls with instancing for repeated items (shelves, products)
- **Desktop**: Real-time shadows + post-processing are fine
- **Always**: Use `dispose()` on geometries/materials when unloading scenes to prevent memory leaks

## Scroll-Driven Narrative Sites (no character controller)

A distinct class from walkable spaces: **brand/marketing sites where scroll position drives a camera along a spline** and content reveals as staged "beats." This is the dominant awwwards-winning pattern (61% of 2026 SOTD) and needs NO physics, raycasting, or controllers — just a camera path + GSAP ScrollTrigger + one strong shader.

**Architecture (works in a single-file static site, no bundler):**
1. Global CDN builds: `three.min.js` r128 + `gsap.min.js` 3.12 + `ScrollTrigger.min.js` (same pattern as Self-Contained HTML — NO import maps).
2. `THREE.CatmullRomCurve3` through the scene; each frame `curve.getPointAt(scrollT)` positions the camera, `getPointAt(scrollT + 0.035)` is the lookAt target.
3. ScrollTrigger with `scrub: 0.6` maps `self.progress` (0..1) to the curve parameter; add a second lerp layer (`smoothT += (target - smoothT) * 0.07`) for butter-smooth motion.
4. Content beats: HTML sections over the fixed canvas, each revealed with `gsap.fromTo(..., {opacity, y, filter: blur}, {scrollTrigger: {trigger, start: 'top 62%'}})`.
5. One full-screen background shader quad (separate ortho scene rendered first with `renderer.autoClear` toggling) for atmospheric FBM gradient + grain — highest impact-to-effort visual.
6. **Always build the fallback**: `prefers-reduced-motion` OR no WebGL OR CDN failure → static CSS version, all content visible, no canvas. Detect in JS, add `body.no-webgl` class, drive reveals with IntersectionObserver instead of GSAP.
7. **The design rule that wins**: commit to ONE hard visual idea executed cleanly (a volumetric fog volume, a monolith canyon, one orbiting object). Restraint beats stacked effects. Generic particle backgrounds are saturated/losing territory — custom shaders + deliberate camera choreography are what read as "frontier."

**Performance budget**: DPR clamp ≤1.5, FogExp2 to fade far geometry, flat-shaded low-poly forms, FBM capped at 4 octaves, particles as one Points draw call with a custom shader. Target 60fps on Pi 5 Chromium.

See `references/scroll-driven-sites.md` for the 2026 awwwards pattern research, the full camera-path/shader/beat-reveal code patterns, and the design briefs that win.

## Ambient Atmosphere Without a Scene (raw WebGL, no library)

Sometimes you want a *living background* — haze, glow, a moon, pointer light — but no 3D content. Don't pull in Three.js for that. A frozen **~9KB fullscreen fragment shader** (raw WebGL, one triangle, FBM) delivers it with graceful CSS fallback, at a fraction of the size, and can read its palette from CSS variables so one shader serves many themes. Key rules: **screen-blend only** (lighten, never darken), **adapt gain to page luminance** (light pages ≈0.42), **render at 0.5 internal resolution**, and **fall back to a CSS gradient** on any failure. Use this for conversion landers and brand pages where atmosphere is mood, not content — and reserve the full scroll-driven 3D scene for when the brand IS the spectacle. See `references/raw-webgl-atmosphere.md` for the contract, shader skeleton, and GLSL building blocks.

## Self-Contained HTML Applications

For single-file HTML apps served from Cloudflare Workers or static hosting (no bundler):

**Use global CDN script tag, NOT ES module import maps.** On Pi 5 Chromium and some mobile browsers, ES module imports via `<script type="importmap">` silently fail — the canvas renders completely black with zero console errors. The reliable pattern:

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
  // THREE is available as a global
  const renderer = new THREE.WebGLRenderer({ ... });
</script>
```

Use r128 (stable, well-tested) rather than bleeding-edge versions. If you need addons (OrbitControls, GLTFLoader), load them from the same CDN version:
```html
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
```

**Wrap in an IIFE** to avoid polluting global scope: `(function() { 'use strict'; ... })();`

### BoxGeometry Material Face Ordering

Three.js `BoxGeometry` materials are ordered: `[+x right, -x left, +y top, -y bottom, +z front, -z back]`. The camera at positive Z looking toward origin sees the **+Z face** (index 4). For cards where you want the BACK facing the camera initially and the FRONT revealed after a Y-axis flip:

```javascript
// materials[4] = back design (facing camera), materials[5] = front design (hidden)
var materials = [edgeMat, edgeMat, edgeMat, edgeMat, backMat, frontMat];
```

A 180° Y rotation (`rotation.y = Math.PI`) swaps which face is visible.

### Canvas Texture Generation for Cards

Generate card faces procedurally with `<canvas>` → `CanvasTexture`:
- Card back: dark gradient + gold borders + geometric pattern (star, circles)
- Card front: suit-colored symbol + name + meaning text
- For reversed cards: rotate the canvas 180° before creating the texture
- Always set `texture.colorSpace = THREE.SRGBColorSpace` for correct colors

### Raycasting for Click-to-Interact

```javascript
raycaster.setFromCamera(mouse, camera);
var hits = raycaster.intersectObjects(cardGroup.children, true);
if (hits.length > 0 && !cardGroup.userData.flipped) { flipCard(cardGroup); }
```

Track mouse position via `pointermove` events, converting screen coords to NDC:
```javascript
mouse.x = ((clientX - rect.left) / rect.width) * 2 - 1;
mouse.y = -((clientY - rect.top) / rect.height) * 2 + 1;
```

### Mobile FOV Adjustment

Narrower screens need WIDER FOV to fit more in frame (counterintuitive):
- Desktop: 50° FOV
- Mobile (<700px): 65° FOV
- Update on resize for orientation changes

## Common Pitfalls

1. **ES module import maps silently failing** — see Self-Contained HTML section above. Black canvas with no errors = almost always an import map issue. Use global CDN script tag instead.

2. **Forking a project that's too complex.** The icurtis1 template is intentionally minimal (single file). Avoid projects with 50+ files and custom frameworks — you'll spend more time reverse-engineering than building.

3. **Not using Rapier for character movement.** Rolling your own physics for walking/jumping/collision is a rabbit hole. Rapier's KCC handles stairs, slopes, ground snapping automatically.

4. **Forgetting animation crossfading.** Instant animation switches look robotic. Always use `fadeIn()`/`fadeOut()` with 0.2-0.5s duration on the AnimationMixer.

5. **Raycasting against everything.** Tag only interactive objects and pass a filtered array to `intersectObjects()`. Raycasting against the entire scene is slow.

6. **Mixing physics and visual transforms.** The Rapier rigid body owns the position; sync the Three.js mesh to it every frame. Never move the mesh directly — always apply forces/velocities to the physics body.

7. **Camera clipping through walls.** Use a capsule or sphere cast from camera position toward target to detect obstruction, then offset the camera forward when blocked.

8. **Over-engineering before prototyping.** Build walk + look at shelf + press E first. Everything else (inventory UI, payment, animations) comes after the core loop works.

9. **Shared texture mutation corrupts cached textures.** When you cache `THREE.CanvasTexture` or `THREE.Texture` objects in a shared lookup (e.g., one texture per card type), NEVER mutate properties like `.rotation`, `.offset`, or `.repeat` on the cached object — it affects ALL future uses of that texture. Instead, rotate at the material level (`material.rotation`) or mesh level (`mesh.rotation.z = Math.PI`). The cached texture stays pristine; each instance gets its own transform.

10. **`createImageBitmap` can fail silently on WebP data URIs.** Some browsers reject `createImageBitmap(img)` when the source `<img>` was loaded from a base64 data URI, especially for WebP format. Always add a fallback in the `.catch()` handler that draws directly from the original `<img>` element: `renderCardTexture(key, img)`.

11. **Fixed atmosphere layers + unpositioned content sections = content falls BEHIND the background.** When you inject fixed `z-index:0/1` atmosphere layers (gradient veil, film grain, WebGL canvas) at the top of `<body>`, every content section that is a direct body child with no positioning stacks at `z-index:auto` (0) and ends up *under* the grain/canvas. Symptom: sections of the page look washed-out, dimmed, or "behind the background." The fix: set `position:relative; z-index:2` on EVERY content wrapper explicitly (`.hero, .section, .panel, footer`, etc.) — do NOT assume wrapping in `<main>` covers siblings that aren't actually wrapped in it. Verify per-section with `getComputedStyle(el).zIndex`, not just a visual glance (the bug is subtle at low grain opacity). Applies to both the raw-WebGL atmosphere pattern and any fixed-canvas scroll site.

12. **Grid-based wall rendering: geometry must match tile spacing.** When building walls/floors from a grid where each cell is spaced `ts` units apart (e.g., `wx = (x - width/2) * ts`), the BoxGeometry dimensions MUST equal `ts`, not hardcoded to 1. A `BoxGeometry(1, h, 1)` with `ts=2` leaves visible gaps between adjacent wall cubes — NPCs can see through walls and the structure looks like disconnected blocks. **Fix**: Declare `const ts = N;` BEFORE geometry creation, then use `new THREE.BoxGeometry(ts, height, ts)`. Also scale floor planes (`PlaneGeometry(ts, ts)`) and door widths proportionally (`0.9 * ts`). Worked example: changed `BoxGeometry(1, 2.5, 1)` to `BoxGeometry(ts, 2.5, ts)` where `ts=2`.

13. **Inline vs module code duplication.** Hybrid projects often have logic in two places: an ES module (`src/ai.js`) AND an inline copy inside `index.html` (e.g., map generation). Tests only cover the module — leaving the inline copy stale and untested. Symptom: tests all pass, but runtime fails with `undefined` on a property your new code depends on. **Fix**: Before declaring work complete, search for duplicate definitions of any function you modified (`grep -rn "function name"` across ALL files including HTML). If the integration point uses an inline copy, update both or consolidate to a single source. Worked example: `generateMap()` existed in both `src/mapgen.js` and inline in `index.html`; only the module was updated with waypoint generation, causing black screen on game load.

## Verification Checklist

- [ ] Character moves with WASD and responds to physics
- [ ] Third-person camera follows smoothly without clipping
- [ ] Animation transitions are crossfaded (not instant)
- [ ] Raycaster detects interactive objects within range
- [ ] HTML overlay shows/hides based on interaction state
- [ ] Cart state updates when items are picked up
- [ ] Scene loads under 3 seconds on target device
- [ ] Memory doesn't grow over time (no leaks from undisposed objects)

## Reference Files

See `references/` for:
- `starter-projects.md` — Detailed comparison of forkable templates with pros/cons
- `physics-engines.md` — Rapier vs Cannon-es vs Ammo.js deep comparison
- `animation-pipeline.md` — Mixamo to glTF workflow, bone retargeting, AnimationMixer patterns
- `scroll-driven-sites.md` — 2026 awwwards patterns, camera-spline + shader + beat-reveal code, winning design briefs
- `raw-webgl-atmosphere.md` — no-library fragment-shader atmosphere: screen-blend contract, dark/light gain, CSS-variable palette, GLSL building blocks
