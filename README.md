# SaltySkills

A public collection of fun creative skills for the [Hermes agent](https://github.com/Salt-555/hermes-agent).

## What are skills?

Skills are modular instruction sets that extend what Hermes can do. Each skill lives in its own directory with a `SKILL.md` (the instructions/workflow) and a `references/` folder for any supporting scripts or configs.

## Skills

### threejs/threejs-game-dev

Full Three.js game development guide: project scaffolding (Vite or self-contained HTML), the r128-global-CDN vs import-map reliability rules, third-person/FPS/top-down camera patterns, AABB collision without a physics engine, procedural IK movement, FPS gun-feel (sway springs, modeled-sight ADS, substepped projectile ballistics), and headless screenshot verification.

**Tags:** `threejs` `game-dev` `fps` `collision` `camera` `ballistics`

### threejs/threejs-gtk-webview

GPU-accelerated UI overlays on Raspberry Pi 5 using GTK3 + WebKit2 WebView with embedded Three.js scenes — animated menus, visualizations, and interactive WebGL interfaces on Wayland. Covers the Chromium-kiosk HTTP overlay pattern (when per-pixel alpha fails), CSS-only fallbacks for kiosk mode's silent script skipping, resolution-aware layout, and WebGL context-loss recovery.

**Tags:** `threejs` `gtk3` `webkit2` `wayland` `raspberry-pi` `overlay`

### threejs/threejs-interactive-experiences

Interactive 3D browser experiences: character controllers with Rapier physics (KCC), walkable environments, product showrooms and virtual stores. Third-person/first-person cameras, animation pipelines (Mixamo/gltf), raycast object interaction, raw-WebGL atmosphere layers, scroll-driven camera sites, and performance budgets for low-end GPUs.

**Tags:** `threejs` `webgl` `rapier` `showroom` `scroll-sites` `interactive`

### threejs/threejs-topdown-games

Top-down / 2.5D Three.js games with vision-cone reveal gating (STALKER-style): pure-logic TDD'd core, tuned cone/proximity/LOS constants, swept-circle collision, and the proven 2D canvas overlay for drawing the beam (3D SpotLight approaches fail). Includes black-canvas debugging recipes — NaN camera positions, physically-correct light intensities on r155+, and headless smoke-scene capture contracts.

**Tags:** `threejs` `top-down` `vision-cone` `reveal-gating` `lighting` `tdd`

### video/cinematic-beats

Cinematic video style with short punchy TTS (one sentence max), visuals given full runtime to breathe, hard cuts, and user-provided music with ducking during speech. Check-in gates after each production phase for user review before proceeding. Includes VHS filter and vibey audio mixing scripts.

**Tags:** `video` `cinematic` `tts` `storyboard` `creative`

### video/deep-fry

Multi-phase ASCII video pipeline. Turns source video into glitch-art with ASCII color variants (vidcolors, bw, matrix, rainbow), YAML-driven segment stitching with slow-mo, and VHS/analog artifact post-processing.

**Tags:** `ascii` `glitch` `vhs` `ffmpeg` `pipeline`

### video/moshpit

Datamoshing and video glitch effects pipeline. Takes a video, produces multiple glitched variations via I-frame removal, P-frame duplication, FFglitch motion vectors, and FFmpeg lagfun trails. Real codec manipulation — not simulated filters.

**Tags:** `datamosh` `glitch` `ffglitch` `ffmpeg` `codec`

### video/video-clip-captions

Extract short clips from long videos with burned-in social-media captions. Downloads YouTube auto-captions (VTT) or transcribes local files via faster-whisper, deduplicates overlapping blocks, and creates vertical 9:16 clips with verbatim word-level synced subtitles for TikTok/Reels/Shorts.

**Tags:** `clips` `captions` `social-media` `whisper` `ffmpeg`
