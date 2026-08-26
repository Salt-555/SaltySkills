---
name: cinematic-beats
description: Cinematic video style — short punchy TTS (one sentence max), visuals given full runtime to breathe, hard cuts, user-provided music with ducking during speech. Check-in gates after each production phase for user review before proceeding. Use when user requests this specific cinematic/punchy video style or says "cinematic beats."
version: 1.0.0
tags: [video, creative]
category: video
related_skills: [manim-video, p5js, ascii-video]
---

# Cinematic Beats Video Style

## Core Philosophy

**Visuals lead timing. Audio follows.** Animations and ASCII scenes play out at their natural runtime — they are NOT truncated, sped up, or held on final frames to match audio length. Silence between beats is intentional design, not a gap to fill.

- **TTS:** One sentence per clip. Maximum signal-to-noise. No filler narration.
- **Visuals:** Full natural runtime. Let animations breathe.
- **Cuts:** Hard cuts only. No crossfades.
- **Music:** User-provided tracks with automatic ducking during speech sections.
- **Check-ins:** After each production phase, deliver assets to user for review before proceeding.

## Project Structure

```
~/videos/[project-name]/
  project.md          # Living document — storyboard, decisions, revision notes
  beats/              # Individual beat assets
    beat-01/
      visual.mp4      # Generated visual (image with motion or animation)
      audio.mp3       # TTS clip for this beat (MP3 only — see Critical Rules)
      note.txt        # One-line description of what this beat shows
    beat-02/
      ...
  music/              # User-provided background music tracks
  output/             # Intermediate and final renders
```

## Phase 1: Beat Script

Create `project.md` with the beat breakdown. Each beat = one visual + one TTS sentence.

### Writing Beats

**TTS rules:**
- ONE sentence per beat. Period.
- Maximum signal-to-noise — every word earns its place.
- If a thought needs two sentences, it's two beats.
- Target: 5-15 words per clip. Shorter is better.
- No introductory filler ("So...", "Now let's look at..."). Start on the point.

**Visual rules:**
- Describe what the visual shows — not how long it lasts.
- The visual runtime is determined by its natural completion, NOT by TTS length.
- Image cuts: static image with Ken Burns motion (slow zoom/pan). Runtime: 4-6s minimum.
- Animated cuts (p5js/manim/ascii): full animation plays out. Whatever it takes — 8s, 12s, 15s.
- The beat duration = max(visual_duration, audio_duration) + pause.

**Beat template in project.md:**

```markdown
# [Project Name]

## Concept
[One paragraph — what this video is about and the feeling we're going for]

## Music
- Track: [filename or description of music user will provide]
- Mood: [description]

## Beats

### Beat 01
**Visual:** [type: image | p5js | manim | ascii] — [prompt/description]
**TTS:** "One punchy sentence."
**Status:** [ ] visual [ ] audio [ ] approved

### Beat 02
...

## Notes
[Running log of decisions, revisions, user feedback]
```

### Cut Types

| Type | Tool | Runtime | Best For |
|------|------|---------|----------|
| `image` | image_generate + Ken Burns | 4-6s | Photos, scenes, portraits, establishing shots |
| `p5js` | p5js skill | Natural (8-15s) | Generative art, particles, data viz, flow fields |
| `manim` | manim-video skill | Natural (8-20s) | Math animations, diagrams, technical explainers |
| `ascii` | ascii-video skill | Natural (6-12s) | Terminal aesthetic, retro computing, hacking topics |
| `caption` | ffmpeg drawtext | 4-8s | Centered TTS text on dark background — pulls focus to words |

**CRITICAL: Before producing any p5js/manim/ascii beat, load the skill with `skill_view(name)` first.** These skills contain brand palettes, font rules, and implementation patterns that must be followed exactly.

## Phase 2: Script Approval Gate

**STOP. Present project.md to user. Do not generate assets until explicitly approved.**

Update project.md Notes section with approval timestamp.

## Phase 3: Generate Visuals

Generate all visual assets per their type. Save as `beats/beat-XX/visual.mp4`.

### Image beats (VHS-filtered Ken Burns)

1. Generate image via `image_generate`
2. Apply VHS filter to the image (grain, scanlines, vignette, chromatic aberration):
```bash
python3 scripts/vhs-filter.py \
  --input beat-XX-image.png \
  --output beat-XX-vhs.png \
  --seed 42 \
  --intensity 1.0
```

**Requirements:** `pip install numpy Pillow` (numpy for the array effects, Pillow for image I/O).

Intensity levels: `0.7` (subtle — grain + vignette only), `1.0` (standard — all effects), `1.5` (heavy — strong chromatic aberration, visible scanlines). Default is `1.0`.

3. Apply Ken Burns motion to the VHS-filtered image to create MP4:
```bash
ffmpeg -loop 1 -i beat-XX-vhs.png -t 5 \
  -vf "zoompan=z='min(zoom+0.001,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=1920x1080:fps=25" \
  -c:v libx264 -pix_fmt yuv420p -r 25 beats/beat-XX/visual.mp4
```

**Why VHS first, then Ken Burns?** The zoompan filter would blur out the grain and scanlines. Apply VHS to the static image first, then add motion on top. The Ken Burns movement on top of the VHS-filtered image creates a lived-in analog feel — like watching old footage through a slightly degraded CRT.

### Animated beats (p5js/manim/ascii)
Load the relevant skill first, then generate. Save output as `beats/beat-XX/visual.mp4`.

**Resolution:** All visuals must be 1920x1080 at 25fps. Scale manim outputs:
```bash
ffmpeg -y -i raw-manim.mp4 \
  -vf "scale=1920:1080:flags=lanczos,setsar=1:1,fps=25" \
  -c:v libx264 -pix_fmt yuv420p -r 25 beats/beat-XX/visual.mp4
```

**Batch image_generate calls in groups of 6. If flagged, rephrase neutrally and retry once.**

### VHS Filter Reference

The VHS filter (`scripts/vhs-filter.py`) applies these effects to a single image:

| Effect | What it does | Visual result |
|--------|-------------|---------------|
| Chromatic aberration | R/B channel offset (0-2px) | Color fringing on edges, like a misaligned CRT |
| Analog noise | ±8 grain per channel (intensity-scaled) | Film-like texture in shadows and midtones |
| Scanlines | Every 4th row darkened to 96% | CRT phosphor grid overlay |
| CRT vignette | Edge darkening (15-35% based on intensity) | Rounded screen corners, like old TV |

**For images:** All effects apply once with a single random seed. Chromatic aberration and noise are visible; jitter/tracking lines are subtle since there's only one frame.

**Note:** This filter is image-only — it does not process video input. To get motion, apply the filter to a static frame first, then add Ken Burns/zoompan on top.

## Phase 3.5: Visual Check-In Gate

**STOP. Send each visual clip to the user for review.**

Include the screenshot or MP4 with MEDIA: paths. Present them numbered:
```
Beat 01: [MEDIA path] — [brief description]
Beat 02: [MEDIA path] — [brief description]
...
```

Ask: "Any edits needed before we proceed to audio?"

**Do not generate TTS until user approves visuals.** Record feedback in project.md Notes.

If changes requested, regenerate only the affected beats and re-check-in.

## Phase 4: Generate TTS Audio

Generate ALL TTS clips — one per beat. Use `text_to_speech` tool with output_path as `.mp3`. Save as `beats/beat-XX/audio.mp3`.

**CRITICAL: Always use MP3 format for audio.** OGG has codec compatibility issues with Telegram delivery and ffmpeg concat operations. Set TTS provider to OpenAI with MP3 output.

**Rules:**
- One sentence per call. No concatenation.
- Measure each clip duration with ffprobe after generation.
- Record durations in project.md next to each beat.

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 beats/beat-XX/audio.mp3
```

## Phase 4.5: Audio Check-In Gate

**STOP. Present audio clips to user.**

### Apply voice filter (required)

Apply the dry/wet bitcrush chain to every TTS clip — this is our signature voice. See `references/dry-wet-bitcrush.md` for full technique and pitfalls.

**Two approaches available:**

**A) Static mix (simple, consistent):**
```bash
# Step 1: Create crushed version via wav intermediate (preserves duration)
ffmpeg -y -i beats/beat-XX/audio.mp3 \
  -af "aresample=resampler=soxr:osr=2000,aformat=sample_fmts=u8,aresample=resampler=soxr,lowpass=f=2500" \
  temp-crushed.wav

# Step 2: Mix dry + wet with compression glue
ffmpeg -y -i beats/beat-XX/audio.mp3 -i temp-crushed.wav \
  -filter_complex "[0:a]volume=0.7[dry];[1:a]volume=0.3[wet];[dry][wet]amix=inputs=2:duration=first:normalize=0,acompressor=threshold=0.05:ratio=4:attack=10:release=100[out]" \
  -map "[out]" beats/beat-XX/audio-filtered.mp3

rm temp-crushed.wav
```

**B) Dynamic mix (signal degradation effect — preferred):**
Uses Python script (`scripts/vibey-mix.py`) with zero-order hold upsampling for authentic bitcrush at correct pitch.

**Requirements:** `pip install numpy pydub` (numpy for array processing, pydub for MP3 read/write).

**Locked parameters (dec5-bit8 variant):**
- **Decimation:** 5× (drops every 5th sample, then repeats via zero-order hold)
- **Quantization:** 8-bit (constant)
- **Dry/wet baseline:** 80% dry / 20% wet
- **Dip pattern:** Every ~1.2s, dry drops to ~35%, wet rises to ~65% (duration ~0.25s)
- **Tremolo on wet only:** 4Hz triangle wave, depth 70% (wet pulses between 30-100%)
- **Slapback delay:** 80ms at -18dB (~0.12 volume), applied to final mix

```bash
python3 scripts/vibey-mix.py beats/beat-XX/audio.mp3
cp beats/beat-XX/audio-dynamic.mp3 beats/beat-XX/audio-filtered.mp3
```

**Chain breakdown:** Clean dry signal layered with extreme digital artifacts (5× decimation, 8-bit quantization via zero-order hold upsampling), periodic dips raising the wet level for a "degrading transmission" effect, tremolo on wet signal for rhythmic pulsing, and slapback delay for space. Keep the chain structure intact — only adjust individual parameters if needed.

Use `audio-filtered.mp3` in all subsequent phases. Keep original `audio.mp3` for reference.

Record decisions in project.md Notes.

## Phase 5: Compose Beats

For each beat, merge visual + audio with **hard cut** (no transition). The beat duration is determined by whichever is longer — visual or audio.

### If visual >= audio:
Audio plays under the full visual. No padding needed.

```bash
ffmpeg -i beats/beat-XX/visual.mp4 -i beats/beat-XX/audio-filtered.mp3 \
  -c:v libx264 -pix_fmt yuv420p -c:a aac \
  -shortest -r 25 output/beat-XX-composed.mp4
```

### If audio > visual:
Visual holds its final frame to fill the remaining time. Use `tpad` on video:

```bash
AUDIO_DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 beats/beat-XX/audio-filtered.mp3)
ffmpeg -i beats/beat-XX/visual.mp4 -i beats/beat-XX/audio-filtered.mp3 \
  -vf "tpad=stop_mode=clone:stop_duration=$AUDIO_DUR" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac \
  -t $AUDIO_DUR -r 25 output/beat-XX-composed.mp4
```

If no audio filter applied, use `audio.mp3` instead of `audio-filtered.mp3`.

### Between-beat pause
Add a short black frame between beats for breathing room:

```bash
ffmpeg -f lavfi -i color=c=black:s=1920x1080:d=0.15:r=25 \
  -c:v libx264 -pix_fmt yuv420p output/pause-XX.mp4
```

### ASCII caption beats (word focus)
When the narration itself is the focal point — not the visual — use an ASCII-style beat with the TTS text centered on screen. Mark these in project.md as `[caption]` type:

**Beat template:**
```markdown
### Beat 03 [caption]
**Visual:** ascii caption — center text, dark background, subtle terminal aesthetic
**TTS:** "The exact words that appear on screen."
**Status:** [ ] visual [ ] audio [ ] approved
```

Generate with ffmpeg drawtext on a black/dark background with monospace font and ALLMIND gold (#C5A55A) text:

```bash
TEXT="Your TTS sentence here"
ffmpeg -f lavfi -i color=c=black:s=1920x1080:d=6:r=25 \
  -vf "drawtext=text='${TEXT}':fontsize=42:fontcolor='#C5A55A':fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf:x=(w-text_w)/2:y=(h-text_h)/2:borderw=1:bordercolor='#8B7D3E'" \
  -c:v libx264 -pix_fmt yuv420p -r 25 beats/beat-XX/visual.mp4
```

Add subtle scanline overlay for CRT feel:
```bash
ffmpeg -i beats/beat-XX/visual.mp4 \
  -vf "geq=lum='lum(X,Y)*(1-0.15*mod(Y,2))'" \
  -c:v libx264 -pix_fmt yuv420p -r 25 beats/beat-XX/visual.mp4
```

Use caption beats sparingly — they pull focus to the words. Best for key quotes, definitions, or punchlines.

## Phase 6: Music Integration

User provides music track(s). Place in `music/` folder. See `references/music-integration.md` for Suno download workaround and sidechain ducking parameter tuning guide.

### Ducking during speech (sidechaincompress)
Use ffmpeg's `sidechaincompress` filter — music is the main signal, voice is the sidechain control. When voice is loud, music compresses down automatically:

```bash
ffmpeg -i output/beat-XX-composed.mp4 \
  -stream_loop -1 -i music/background.mp3 \
  -filter_complex "[1:a][0:a]sidechaincompress=threshold=0.02:ratio=4:attack=50:release=200:makeup=1.5[ducked_music];[0:a][ducked_music]amix=inputs=2:duration=first:weights='1 1'[mixed]" \
  -map 0:v -map "[mixed]" \
  -c:v libx264 -pix_fmt yuv420p -t $BEAT_DUR -r 25 output/beat-XX-with-music.mp4
```

**How it works:** `[1:a]` (music) is the main signal, `[0:a]` (voice) is the sidechain. When voice exceeds `threshold`, music compresses by `ratio`. `attack=50ms` and `release=200ms` give natural feel — not too snappy, not too slow. `makeup=1.5` restores compressed signal level so ducked music doesn't go silent.

**Parameters to tune:**
- `threshold`: Lower = more aggressive ducking (0.01-0.03). Higher = subtler (0.05+)
- `ratio`: 3:1 is gentle, 4:1 is standard, 6:1+ is heavy
- `attack`: How fast music ducks when voice starts. 20-50ms feels natural
- `release`: How fast music recovers after voice ends. 150-300ms prevents pumping

**Batch processing:** Loop over all beats with a script — each beat gets its own ducked output, then assemble in Phase 7. Music is looped (`-stream_loop -1`) to fill the full video duration.

### Alternative: Music only during pause frames
For maximum punch, play music ONLY between-beat pauses (black frames) and mute entirely during speech beats. Creates stark rhythmic contrast:

```bash
# Beat with speech — no music
cp output/beat-XX-composed.mp4 output/beat-XX-final.mp4

# Pause frame WITH music
ffmpeg -i output/pause-XX.mp4 -i music/background.mp3 \
  -filter_complex "[1:a]volume=0.5[a]" \
  -map 0:v -map "[a]" -c:v libx264 -pix_fmt yuv420p -c:a aac \
  -t 0.15 output/pause-XX-music.mp4
```

## Phase 7: Assembly

Concatenate all beats + pauses in order using `-c copy` (no re-encode):

1. Create concat list (`output/concat.txt`):
```
file 'beat-01-final.mp4'
file 'pause-01-music.mp4'
file 'beat-02-final.mp4'
file 'pause-02-music.mp4'
...
```

2. Concat:
```bash
ffmpeg -f concat -safe 0 -i output/concat.txt \
  -c copy output/final-raw.mp4
```

3. Normalize to consistent fps:
```bash
ffmpeg -i output/final-raw.mp4 \
  -r 25 -c:v libx264 -pix_fmt yuv420p -c:a aac \
  output/[project-name].mp4
```

## Phase 7.5: Final Review Gate

**STOP. Deliver the assembled video to user.**

Include MEDIA:/home/salt/videos/[project-name]/output/[project-name].mp4

Ask for final feedback. If changes needed, note them in project.md and iterate on specific beats rather than rebuilding everything.

## Updating project.md

After each phase completion, update `project.md`:
- Mark beat statuses as completed
- Add measured durations
- Log user decisions and revision notes in the Notes section
- Record final output path and timestamp

This file is the single source of truth for returning to the project later.

## Critical Rules

- **ONE sentence per TTS clip.** No exceptions. If it needs two sentences, it's two beats.
- **Visuals breathe at natural runtime.** Never truncate or speed up animations to match audio.
- **Hard cuts only.** No crossfades between beats.
- **Check-in after every phase.** Visual review → Audio review → Final review. Do not proceed without explicit approval.
- **project.md is the source of truth.** Update it after every phase and decision.
- **Music ducking during speech.** User-provided tracks only — never generate music automatically. Use sidechaincompress filter.
- **Between-beat pauses: 0.15s black frames.** Short, breath-like gaps — not dramatic pauses.
- **Caption beats for word focus.** Use `[caption]` type when the text itself is the message. Gold monospace on dark background with scanlines.
- **Audio filter is mandatory.** Apply dry/wet bitcrush chain to every TTS clip. Two approaches: static (ffmpeg aresample roundtrip, 70/30) or dynamic (Python zero-order hold with periodic dips revealing more crunch — preferred). Consistent voice across all beats — don't mix filtered and unfiltered voices in one video. See `references/dry-wet-bitcrush.md` for full technique.
- **VHS filter on all image beats.** Every generated image gets VHS post-processing before Ken Burns motion: grain, scanlines, vignette, chromatic aberration. This is the default visual texture — no exceptions. Use `python3 scripts/vhs-filter.py --input IMG.png --output OUT.png --seed 42 --intensity 1.0`. Intensity 0.7 = subtle, 1.0 = standard, 1.5 = heavy.
- **VHS first, then Ken Burns.** Apply VHS filter to the static image BEFORE zoompan motion. The zoompan blur would destroy grain and scanlines. Motion on top of VHS-filtered images creates lived-in analog feel — like watching old footage through a degraded CRT.
- **VHS filter is image-only.** `scripts/vhs-filter.py` processes a single image frame. For animated beats, keep the p5js/manim/ascii output as-is (or render a still frame for VHS treatment).
- **MP3 only for audio.** Never use OGG — codec compatibility issues with Telegram delivery and ffmpeg concat operations. TTS output, filters, and music tracks all MP3.

## Pi 5 Notes

- Use background=true for long ffmpeg renders with notify_on_complete=true
- Split batch operations — don't run all zoompan calls in one execute_code block (300s timeout)
- Use absolute paths (`/home/salt/`), not `~/`
- After crash: check which files exist, ffprobe for corrupt files, rebuild only what's needed
- **ffmpeg filter chain timeouts:** Complex multi-input filter chains (acrossfade, asplit+sidechaincompress) can exceed 30s timeout. Use two-pass approach: split audio to temp files first, then concat/merge in second pass
- **`apad` creates infinite files:** Never use `apad` without explicit duration — it pads forever and fills disk (8GB+ file in seconds). Always specify `-t` or use `atrim` with explicit end time instead
- **sidechaincompress syntax:** The filter takes `[main_audio][sidechain]sidechaincompress=...[output]`. Do NOT use `link=` parameter — it doesn't exist and causes parse errors. Output label goes directly after parameters: `...makeup=1.5[ducked_music]`
