# Scroll-Driven Narrative Sites — Research & Patterns

Condensed from 2026 awwwards analysis + the ALLMIND machine-cathedral build (allmind.biz). Use when building brand/marketing sites where scroll drives a 3D camera, NOT walkable spaces.

## What Wins in 2026 (jury patterns)

- **61% of SOTD winners are immersive 3D** (up from 23% in 2024). Three.js + GSAP ScrollTrigger is the standard stack.
- **Restraint**: winners commit to ONE hard visual concept executed cleanly. Generic particle backgrounds and copy-paste templates LOSE.
- **Scroll as narrative device**: each section is a staged beat (entrance / hold / exit), camera moves through true Z-depth, not sliding 2D layers.
- **Technical craft is a hidden rubric**: 60fps on mid-range, `prefers-reduced-motion` respected, graceful mobile/no-WebGL fallback, Lighthouse mobile 90+.
- **Custom shaders** for distinctive tone (a full-viewport fragment shader behind typography = highest impact-to-effort move).
- Stable tooling only: Three.js stable, GSAP stable, glTF 2.0. No bleeding-edge in production.
- Dead trends: NFT-aligned 3D, metaverse themes, "AI-generated 3D website" tools.

## Reusable Design Briefs (steal the idea, not the site)

| Brief | One idea | When to use |
|---|---|---|
| Machine-cathedral | Camera descends a canyon of breathing monoliths, volumetric haze shader | Brand = built systems, machine ops, sovereignty |
| Single object, real weight | One hero object, inertial orbit cam, Z-depth scroll | Product launch, flagship reveal |
| Scroll-sequenced reveal | Type scatters/reforms, depth-layered panels per section | Dense changelog / feature story |
| Museum rooms | One 3D alcove per item, scroll = walking the gallery | Portfolio, product line |
| Landscape flythrough | Cinematic aerial path over terrain | Place/real-estate/travel |

For ALLMIND-class brands: the scene must invoke the copy's themes. "Empire that runs itself" → self-assembling architecture, not decorative fog. Nature integrated INTO geometry, not scattered on top.

## Code Patterns (proven on the ALLMIND build)

### Camera rail
```javascript
var path = new THREE.CatmullRomCurve3([
  new THREE.Vector3(0, 1.5, 6),
  new THREE.Vector3(0, 0.8, -30),
  new THREE.Vector3(-2.5, 0.2, -80),
  new THREE.Vector3(2.5, -0.6, -140),
  new THREE.Vector3(0, -2.5, -260)
]);
// Per frame:
path.getPointAt(smoothT, camPos);
path.getPointAt(Math.min(smoothT + 0.035, 1), camTarget);
camera.position.copy(camPos); camera.lookAt(camTarget);
// Idle sway + pointer parallax layered on top:
camPos.x += Math.sin(t*0.22)*0.35 + pointer.x*1.1;
```

### Scroll driver (double smoothing)
```javascript
ScrollTrigger.create({
  trigger: document.body, start: 'top top', end: 'bottom bottom',
  scrub: 0.6,
  onUpdate: self => { scrollState.t = self.progress; }
});
// render loop: smoothT += (scrollState.t - smoothT) * 0.07;
```

### Beat reveals
```javascript
gsap.fromTo(inner, {opacity:0, y:60, filter:'blur(8px)'},
  {opacity:1, y:0, filter:'blur(0px)', duration:1.1, ease:'power2.out',
   scrollTrigger:{trigger: beat, start:'top 62%', toggleActions:'play none none reverse'}});
```

### Background atmosphere pass (two-scene render)
Ortho quad scene rendered FIRST with FBM haze + gold light shaft + film grain; world scene second with `renderer.autoClear=false`. FogExp2 (density ~0.016) fuses geometry into the haze.

### Breathing architecture
Store `baseY`, `phase`, `breath` in mesh.userData at build; per frame `mesh.position.y = baseY + sin(t*breath + phase) * 0.22`. Cheap, makes the whole scene feel alive.

### Particles as one draw call
`THREE.Points` + custom ShaderMaterial: per-particle seed attribute, drift in vertex shader (`pos.y += sin(uTime*0.25+seed)*1.4`), alpha by distance, additive blending, size = `uSize/dist`. ~1400 particles is free.

## Fallback Contract (non-negotiable)

Trigger static mode if ANY of: `prefers-reduced-motion: reduce`, WebGL context creation fails, `THREE`/`gsap` undefined (CDN blocked). Then: `body.classList.add('no-webgl')`, remove canvas, force all `.beat-inner` opacity 1, run stat counters via IntersectionObserver, drive progress bar from a plain scroll listener. The static version must still look designed — radial seafoam gradients on the body, same panels.

## Verification

- browser_exec screenshot at top AND mid-scroll — full-page captures stitch fixed elements (hero text repeating is a capture artifact, not a bug).
- Confirm markers via console: `typeof THREE`, `body.classList.contains('no-webgl')` both as expected.
- Canvas readPixels from console fails ('no ctx') once Three owns the context — use screenshots, not pixel probes.
