# Raw-WebGL Ambient Atmosphere (no library)

Use when a page needs a **living WebGL atmosphere** (haze, glow, pointer light) but a full
Three.js scene is overkill — conversion landers, product pages, brand sites where the 3D
is *background mood*, not the content. This is the pattern behind the ALLMIND storefront
Atmosphere Engine and the coven-compass moonlit sky.

## Why raw WebGL here, not Three.js

- **Size**: a frozen fullscreen fragment shader is ~9KB. Three.js r128 is ~600KB. On a
  Cloudflare Worker that inlines everything, and on first paint, that matters.
- **No scene graph needed**: ambient haze/light is a low-frequency effect — a single
  triangle + FBM fragment shader does it better than meshes + lights.
- **Graceful degradation is trivial**: if the GL context or shader fails, a CSS gradient
  fallback stays. Nothing breaks.

## The contract

1. **Markup**: a fixed `<canvas class="atmo-gl">` behind content (z-index 0) + a CSS
   gradient sibling (the fallback) + a grain overlay. Content sits at z-index 2.
   **Every content wrapper needs explicit `position:relative; z-index:2`** — direct
   body children with no positioning stack at `z-index:auto` and fall *under* the
   fixed grain/canvas (symptom: whole sections look dimmed, "behind the background").
   Don't assume a `<main>` wrap covers siblings that aren't wrapped in it. Verify
   per-section with `getComputedStyle(el).zIndex`.
2. **Progressive enhancement**: JS tries to init GL. On ANY failure (no WebGL,
   `prefers-reduced-motion`, compile/link error) it returns early and the CSS gradient
   stays visible. The canvas is only inserted/kept on success.
3. **Screen blend everywhere** (`canvas.style.mixBlendMode='screen'`): the shader can only
   LIGHTEN, never darken — so it glows on dark pages and tints on light pages without
   muddying text. (The "light-page mud" bug: additive color stacked into a dark overlay on
   cream. Screen + gain is the fix.)
4. **Dark/light adaption**: sample `body` background luminance; light pages get a
   `uGain ≈ 0.42` uniform + lower canvas opacity, dark pages full strength.
5. **Reduced internal resolution** (`SCALE = 0.5`): haze is low-frequency, looks identical
   at half-res, runs on phones. Pause the rAF loop on `visibilitychange`.
6. **Zero-config palette**: read colors from CSS custom properties via `getComputedStyle`
   (e.g. `--atmos-1/2/3`, `--atmos-glow`) so one frozen shader renders many themes by just
   changing CSS variables — no per-product JS.

## Minimal shader skeleton

```javascript
var canvas = document.createElement('canvas');           // or reuse an existing one
var gl = canvas.getContext('webgl', {alpha:true, antialias:false, depth:false,
        stencil:false, powerPreference:'low-power'});
if (!gl) { canvas.remove(); return; }                    // CSS fallback stays

var vsrc = 'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
// fragment: FBM haze + a light shaft + pointer glow, all tinted by uniforms
//   uC1/uC2/uC3 (haze colors), uCG (glow), uGain (light-page dampener)
//   uv = gl_FragCoord.xy/uRes;  col *= uGain;  gl_FragColor = vec4(col,1.);

// fullscreen triangle:  [-1,-1, 3,-1, -1,3]
// per frame: ease pointer, set uRes/uTime/uPtr/uScroll, drawArrays(TRIANGLES,0,3)
```

## GLSL building blocks that read as "premium"

- `fbm(p, 4-5 octaves)` for drifting haze volumes (slow `uTime*0.02-0.03` scroll drift).
- `exp(-pow((uv.y-c)*k, 2.))` horizontal light shafts (warm accent rising from below).
- `exp(-d*d*r)` radial glow at the pointer (`d = length((uv-uPtr)*aspect)`).
- A soft disc + halo for a moon: `smoothstep(r1,r0,md)` disc + `exp(-md*md*k)` halo.
- Twinkle stars: `hash(floor(p*N))` cell + `sin(uTime*f + h*40.)` flicker, `smoothstep(.97,1.,star)` sparse gate.

## Verification

- Console probe: canvas exists, `body` got the "live" class, blend mode = screen.
- Screenshot (browser_exec) top AND mid-scroll. Full-page captures stitch fixed
  elements (demo bar / hero repeating is a capture artifact, not a bug).
- Test ONE dark theme AND ONE light theme — they fail in opposite ways.
