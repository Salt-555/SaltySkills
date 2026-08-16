# Animation Pipeline — Mixamo to Three.js

## Getting Character Animations from Mixamo

Mixamo (mixamo.com) is Adobe's free library of 3D character animations. All animations are ready-to-use and can be downloaded as FBX or glTF.

### Workflow

1. **Get a character model**
   - Use a Mixamo T-pose character (free), OR
   - Retarget your own Blender model to Mixamo skeleton
   
2. **Download animations**
   - Browse: https://www.mixamo.com/#/browse/animations/all
   - Essential set for storefront: Idle, Walk, Run, Jump, Crouch
   - Download as **FBX** (Mixamo's native format)

3. **Convert FBX to glTF**
   ```bash
   # Using Blender command line:
   blender --background --python convert.py -- \
     --input character_with_animations.fbx \
     --output character.glb
   
   # Or use Facebook's gltf-pipeline:
   npx @gltf-transform/cli convert input.fbx output.glb
   ```

4. **Load in Three.js**
   ```javascript
   import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
   
   const loader = new GLTFLoader();
   loader.load('/models/character.glb', (gltf) => {
     const model = gltf.scene;
     const animations = gltf.animations; // Array of AnimationClip
     
     scene.add(model);
     
     // Set up animation mixer
     const mixer = new THREE.AnimationMixer(model);
     
     // Play idle by default
     const idleClip = animations.find(c => c.name.includes('Idle'));
     if (idleClip) {
       const action = mixer.clipAction(idleClip);
       action.play();
     }
   });
   
   // In render loop:
   mixer.getDelta(); // or mixer.update(deltaTime);
   ```

## Animation State Machine Pattern

```javascript
class CharacterAnimator {
  constructor(model, animations) {
    this.mixer = new THREE.AnimationMixer(model);
    this.clips = {};
    
    // Index clips by name pattern
    for (const clip of animations) {
      if (clip.name.includes('Idle'))   this.clips.idle = clip;
      if (clip.name.includes('Walk'))   this.clips.walk = clip;
      if (clip.name.includes('Run'))    this.clips.run = clip;
      if (clip.name.includes('Jump'))   this.clips.jump = clip;
    }
    
    this.currentAction = null;
  }
  
  play(name, duration = 0.3) {
    const clip = this.clips[name];
    if (!clip || this.currentAction?.clip === clip) return;
    
    const newAction = this.mixer.clipAction(clip);
    newAction.reset();
    newAction.enabled = true;
    newAction.fadeIn(duration);
    
    if (this.currentAction) {
      this.currentAction.fadeOut(duration);
    }
    this.currentAction = newAction;
  }
  
  update(deltaTime) {
    this.mixer.update(deltaTime);
  }
}

// Usage in game loop:
const animator = new CharacterAnimator(model, gltf.animations);

function updateAnimation(state) {
  if (state.isAirborne) {
    animator.play('jump');
  } else if (state.speed > 0.5 * state.maxSpeed) {
    animator.play('run');
  } else if (state.speed > 0) {
    animator.play('walk');
  } else {
    animator.play('idle');
  }
}
```

## Blending Multiple Animations

For upper/lower body independence (e.g., character walks while waving):

```javascript
// Add weights to actions for partial blending
const walkAction = mixer.clipAction(walkClip);
const waveAction = mixer.clipAction(waveClip);

walkAction.play();
waveAction.play();

// Wave only affects upper body bones
waveAction.setEffectiveWeightOnMixedBones(0.5);
```

## Common Pitfalls

1. **Forgetting `mixer.update(deltaTime)`** — Animations won't play without calling this every frame in the render loop.

2. **Not disposing old actions** — Creating new clip actions every state change leaks memory. Reuse or properly dispose.

3. **Mixamo skeleton mismatch** — If your model isn't rigged to Mixamo's skeleton, animations won't apply correctly. Use Mixamo's auto-rigging tool or retarget in Blender.

4. **Animation scale issues** — Mixamo models are typically ~1.8 units tall. Scale your scene accordingly or rescale the glTF on import:
   ```javascript
   model.scale.set(0.5, 0.5, 0.5); // Adjust to match world scale
   ```

## Alternative: Blender-Original Animations

For custom animations not in Mixamo:
1. Animate in Blender with armature
2. Export as glTF/GLB with "Include > Armature" and "Export Animated" checked
3. Load same way — `gltf.animations` contains your clips
