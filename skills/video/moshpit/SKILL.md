---
name: moshpit
description: Datamoshing and video glitch effects pipeline. Takes a video, produces multiple glitched variations via I-frame removal, P-frame duplication, FFglitch motion vectors, and FFmpeg lagfun trails. Use when user wants to datamosh, glitch, or corrupt video footage artistically.
category: creative
---

# Moshpit — Video Datamoshing Pipeline

Glitch art tool that takes a source video and produces multiple corrupted/glitched variations using real codec manipulation (not simulated filters).

## Dependencies

- **FFmpeg** (system) — installed at `/usr/bin/ffmpeg` (n9.0.1 on this box)
- **FFglitch 0.10.2** (`ffedit`, `ffgac`, `qjs`) — installed at `/usr/local/bin/`
- **Python 3 + numpy** — system packages

Install FFglitch if missing (x86_64 build — this machine is x86_64, NOT aarch64):
```bash
curl -L -o /tmp/ffglitch.7z "https://ffglitch.org/pub/bin/linux64/ffglitch-0.10.2-linux-x86_64.7z"
cd /tmp && 7z x ffglitch.7z   # needs p7zip/7zip: sudo pacman -S 7zip
sudo cp ffglitch-0.10.2-linux-x86_64/ffedit ffglitch-0.10.2-linux-x86_64/ffgac \
        ffglitch-0.10.2-linux-x86_64/qjs ffglitch-0.10.2-linux-x86_64/fflive /usr/local/bin/
```
Both `ffedit` and `ffgac` are pure `shutil.which()` PATH lookups, so `/usr/local/bin` is all they need; no per-script path config.

## Scripts

All scripts live in `scripts/` relative to this skill:

| Script | Purpose | Requires FFglitch? |
|--------|---------|-------------------|
| `es_mosh.py` | **Core surgery engine** — raw MPEG-4 elementary-stream melts/bursts/freeze-seams with built-in validation. Use this for cut-targeted work | No |
| `moshpit.py` | Batch orchestrator — generate many variants from one input | Partial (only for vector effects) |
| `mosh.py` | Pure FFmpeg I-frame removal + P-frame duplication | No |
| `ffglitch_mosh.py` | Motion vector manipulation via ffedit/ffgac | Yes |
| `dual_layer.py` | Two-video reveal: FFglitch-corrupts foreground into a mask that exposes clean background | Yes |
| `pixelsort_mosh.py` | Per-frame pixelsort pass (luma or green-hue sort); chains after any datamosh | No |
| `transition_mosh.py` | LEGACY — A→B codec-level transition: datamosh A to collapse, melt into B | No |
| `cut_mosh.py` | LEGACY — cut-targeted melts + rhythmic bloom bursts (Watch Dogs style). Use es_mosh.py for new work | No |
| `dither_mosh.py` | Chainable Bayer ordered-dither pass (Watch Dogs texture) | No |
| `ca_swell.py` | Chainable chromatic-aberration pass with organic swell/recede dynamics | No |
| `flicker_sort.py` | Pixel-sort flicker: random bursts (1 frame to 1s+) of full-density sorting on an otherwise clean video | No |
| `lens_stack.py` | **Bodycam/CRT lens look** — native `lenscorrection` fisheye with black corners + vignette, then edge-flip ring, edge-weighted chroma, scanlines. THE lens-distortion tool | No |
| `salt_transition.py` | **THE "Salt Transition"** — full locked pipeline: melts + frozen seams + 50% pixelsort overlay + static whisper-dither. Stage 1 runs on the es_mosh core | No |

## Core workflow: cut-targeted melts (es_mosh.py)

The centerpiece operation: melt every shot boundary of a concatenated video at
frame-exact positions, with a frozen seam hold between shots. Works on ANY
multi-shot video where you know (or can detect) the cut frames.

```bash
# Melt at specific frames (at --fps), 0.5s freeze hold per seam:
python scripts/es_mosh.py concat.mp4 --cuts "48,172,292" --freeze 12 -f 24 -o melted.mp4

# Add bloom bursts (frame:delta:length) — corruption punctuating clean footage:
python scripts/es_mosh.py concat.mp4 --cuts "48,172" --bursts "100:8:24,180:10:36" -o out.mp4

# Bursts only, no melts:
python scripts/es_mosh.py input.mp4 --bursts "96:8" -o out.mp4
```

Key mechanics:
- **Cut frames are the first frame of the incoming shot.** The I-frame sits ON the cut; dropping it makes the incoming shot decode against the outgoing shot's pixels.
- **`--freeze N`** duplicates the outgoing shot's last P-frame N times before the melt (Watch Dogs seam hold). 0 = off. 12 @ 24fps = 0.5s.
- **Bursts strengthen weak seams**: if a seam barely smears (outgoing shot too static/motionless), a bloom burst on its tail or the incoming shot's head builds corruption for the melt to smear. Static footage (slow pans, stills) melts weakly — motion is the fuel.
- **Validation is built in**: after remux it decodes the output and checks exact frame count vs expected. Trust the validation output, not exit codes.

Building the concat input: normalize all shots first (`scale=W:H`, `fps=N`, `setsar=1`), then `concat` filter. Any resolution/fps mismatch breaks the melt math.

For images-as-shots: hold a PNG with `-loop 1 -t <seconds>` as an input to the concat. A still shot melts weakly (no motion) — expect subtle smears at its seams.

## Effects Reference

### Pure FFmpeg (no FFglitch needed)

**melt** — I-frame removal. Classic datamosh transition smear. Forces decoder to apply motion vectors from one shot onto pixels of another, creating a melting/blooming effect between scenes.

```bash
python scripts/mosh.py input.mp4 -s 40 -e 90 -o melt.mp4
# Removes I-frames between frames 40 and 90
```

**bloom** — P-frame duplication. Repeats a block of delta frames cyclically, creating hypnotic motion trails.

```bash
python scripts/mosh.py input.mp4 -d 8 -s 165 -o bloom.mp4
# Repeats 8 P-frames starting at frame 165
```

**lagfun_trail** — FFmpeg lagfun filter with grayscale ghost overlay. Persistent trails behind movement.

**lagfun_ghost** — RGB channel split with time offsets per channel. Chromatic aberration ghost effect.

### Pixelsort pass (chains after any datamosh)

`pixelsort_mosh.py` reorders pixels within each frame by a sort key, turning datamosh trailing squares into sorted streaks. Pure numpy, no extra deps.

```bash
# Luma sort (brightness) — the default, classic streak look:
python scripts/pixelsort_mosh.py moshed.mp4 -o sorted.mp4 --axis rows --mode interval --low 50 --high 255

# Green-hue sort — isolates a neon-green subject, bleeds it while the rest stays intact:
python scripts/pixelsort_mosh.py moshed.mp4 -o sorted.mp4 --key green --mode interval --low 40 --high 255

# Edge-aware sort — sort runs between detected edges:
python scripts/pixelsort_mosh.py moshed.mp4 -o sorted.mp4 --mode edges --edge-thresh 8

# Vertical combing instead of horizontal streaks:
python scripts/pixelsort_mosh.py moshed.mp4 -o sorted.mp4 --axis cols

# Progressive unsort: frame N sorts heaviest, weakens to clean over N frames
# (use on the B-side of an A→B transition so content unsorts into view):
python scripts/pixelsort_mosh.py transition.mp4 -o out.mp4 --unsort-start 170 --unsort-frames 96
```

Sort keys (`--key`): `luma` (brightness, default) or `green` (greenness = G − max(R,B), selects neon-green/teal subjects). Frame-range controls: `--until-frame N` (sort only the first N frames, rest clean) and `--unsort-start N --unsort-frames M` (progressive unsort).

### Dither pass (chains after any datamosh)

`dither_mosh.py` — Bayer ordered dither, the Watch Dogs crosshatch texture. Static by default; `--boil N` re-randomizes the threshold every N frames for an animated pattern (boiled dither reads "cheezy" — static is the default for a reason).

```bash
# Heavy but stable (verified look):
python scripts/dither_mosh.py moshed.mp4 -o out.mp4 --levels 5 --cell 8 --contrast 1.6
# Subtler:
python scripts/dither_mosh.py moshed.mp4 -o out.mp4 --levels 6 --cell 8 --contrast 1.4
# Hard 1-bit graphic:
python scripts/dither_mosh.py moshed.mp4 -o out.mp4 --levels 2 --mono
# Limit to A's half of a transition:
python scripts/dither_mosh.py transition.mp4 -o out.mp4 --until-frame <splice>
```

`--levels` (lower = heavier posterize; 5-6 typical, 12 = barely-visible whisper, 2 = hard 1-bit), `--cell` (2/4/8/16 Bayer size), `--contrast` (pre-quantize luma crush, 1.4-1.6 = graphic), `--mono`, `--boil` (0 = static).

### Lens/bodycam pass (chains after anything)

`lens_stack.py` — THE lens-distortion tool. Stage 1 is ffmpeg's native
`lenscorrection` filter (canonical radial model, black fill for out-of-lens
corners — true letterboxed fisheye); stage 2 layers custom edge passes in a
single decode/encode sweep (no round-trips): mirror-flip ring, edge-weighted
chroma, scanlines.

```bash
# Subtle fisheye:
python scripts/lens_stack.py in.mp4 -o out.mp4 --k1 0.1
# Full bodycam: strong bulge, black corners, mirror ring, rim fringing, CRT rows
python scripts/lens_stack.py in.mp4 -o out.mp4 --k1 0.25 --k2 0.15 \
    --edge-flip 0.92 --edge-chroma 10 --vignette 0.25 --scanlines 3
```

`--k1` (positive = fisheye bulge), `--k2` (pushes distortion into the outer ring —
the bodycam look), `--edge-flip R` (beyond fraction R of half-diagonal the image
mirrors inward — cheap lens seeing its own housing), `--edge-chroma PX` (R/B split
ramping 0 center → PX at rim), `--vignette`, `--scanlines`.

### Chromatic aberration swell pass (chains after anything)

`ca_swell.py` — RGB channel split whose amplitude breathes: slow multi-oscillator base undulation plus N distinct gaussian swells at random times/widths/intensities (seeded, reproducible). Radial mode (lens-like, center clean) by default; linear mode for directional split.

```bash
# Default: rest ~0.5px, 5 random swells peaking ~10-12px
python scripts/ca_swell.py in.mp4 -o out.mp4 --min 0.5 --max 12 --swells 5 --seed 7
# Directional split instead of radial:
python scripts/ca_swell.py in.mp4 -o out.mp4 --mode linear --angle 30
```

Prints its swell peak table (time, px) so you can see the choreography before committing. `--seed` rerolls the pattern.

**Performance note:** the radial remap is content-free geometry — the script caches remap indices per 0.5px amplitude step and passes through frames below 0.75px. Don't "simplify" it back to per-frame index computation; that burned 4x the CPU for identical output.

### Pixel-sort flicker pass (chains after anything)

`flicker_sort.py` — pixel sorting switches ON for random bursts then OFF. Burst lengths randomize between `--minlen` and `--len` frames, placed with a refractory gap so flashes stay distinct events. Full row/column density during a burst (no row-skipping) so each flash reads unmistakably, then snaps back clean. Bursts up to ~24 frames (1s) read as "the image tears and re-resolves"; 1-3 frame bursts read as a twitch.

```bash
# Mix of short twitches and ~1s tears, 10 events:
python scripts/flicker_sort.py in.mp4 -o out.mp4 --bursts 10 --len 24 --seed 3
# Only fast twitches:
python scripts/flicker_sort.py in.mp4 -o out.mp4 --bursts 8 --len 3
# More violent sort (more pixels included):
python scripts/flicker_sort.py in.mp4 -o out.mp4 --threshold 80
# Vertical streaks, only in the last half:
python scripts/flicker_sort.py in.mp4 -o out.mp4 --axis v --window 491,983
```

Prints the burst plan (start, length) and total flicker % before rendering. `--seed` rerolls placement.

### FFglitch Motion Vector Presets (requires ffedit)

Each preset is a JavaScript function that modifies motion vectors during decode/encode:

| Preset | Effect |
|--------|--------|
| `horizontal` | Horizontal smear biased by frame position |
| `vertical` | Vertical cascade with noise |
| `spiral` | Spiral distortion around center point |
| `zoom` | Radial expansion from center (fake zoom) |
| `chaos` | Randomized vector perturbation |
| `pixelate` | Macroblock zeroing — creates blocky artifacts |
| `rgb_split` | RGB channel split simulation via directional bias |
| `wave` | Sine wave distortion propagating over time |
| `datamosh_loop` | Self-referencing vectors pointing backward in time |
| `block_glitch` | Random rectangular regions of zeroed vectors |

```bash
# Single preset:
python scripts/ffglitch_mosh.py input.mp4 --preset chaos -o output.avi --mp4

# Custom JS filter (shipped templates: templates/custom_filters.js,
# templates/allmind_mosh.js; scripts/filters/liquid_melt.js):
python scripts/ffglitch_mosh.py input.mp4 --script templates/custom_filters.js -o output.avi

# Extract vectors from a video and re-apply to the SAME video:
python scripts/ffglitch_mosh.py source.mp4 --extract vectors.json
python scripts/ffglitch_mosh.py source.mp4 --transfer vectors.json -o result.avi --mp4
# WARNING: cross-file --transfer (extract from A, transfer onto B) SEGFAULTS
# ffedit 0.10.2 (verified, exit 139) — do not use it across different videos.
```

## Named Setups

### THE "SALT TRANSITION" (hand-tuned, Salt-verified — the locked recipe)

The flagship deliberate-mosh pipeline, iterated on real footage and locked.
One command runs the whole chain:

```bash
python scripts/salt_transition.py input.mp4 -o salt.mp4
```

The four stages (each hand-verified; do NOT "improve" the defaults — they
were tuned by eye across 7+ iterations, including rejected variants):

1. **Cut melts + frozen seam holds** (es_mosh core with auto scene detection):
   long smears at every detected cut; the outgoing shot's last smear freezes
   for 0.5s and the next shot melts in over that frozen base.
2. **Pixelsort** (`pixelsort_mosh.py --axis rows --mode interval --low 50`):
   luma sort on the moshed output.
3. **50% composite** (`ffmpeg blend=all_opacity=0.5`): the UNSORTED mosh
   overlayed ON TOP of the sorted one. The streaks become a translucent
   ghost texture instead of dominating — this is the trick that makes it.
4. **Static whisper-dither** (`dither_mosh.py --levels 12 --contrast 1.0
   --boil 0`): barely-visible locked Bayer crosshatch. Static is critical —
   animated/boil dither flashes (rejected).

**Locked recipe:** all tuning dials are salt_transition.py flags — it drives
the melt stage internally on the es_mosh core. Do not swap other surgery
scripts into it; the look is tuned to this exact chain.

Tuning dials (rarely needed): `--opacity` (sorted-layer weight, default 0.5),
`--dither-levels` (lower = more visible dither, default 12),
`--scene` (cut sensitivity), `--freeze` (seam hold length).

### WATCH DOGS MENU STYLE (deliberate moshing — transitions + punctuation + texture)

How Ubisoft's Watch Dogs menus work: not full-video collapse, but
corruption used *deliberately* — melts at cut points as transitions, short
bloom bursts as rhythmic punctuation, dithering as the unifying texture.
(Verified via aescripts: WD2 used AE Pixel Sorter, RetroDither, and Data
Glitch on trailers and in-game UI; the menu backgrounds are pre-rendered
video authored with these treatments.)

Three independent passes, any combination (NOTE: prefer `es_mosh.py` over the
legacy `cut_mosh.py` for the melts/bursts — same operations, robust pipeline):

**1. Cut-targeted melts.** Delete the I-frame at each shot boundary so each
shot melts in from the previous shot's pixels. Long GOP = long smears.
**Frozen seam holds (`--freeze`)** duplicate the outgoing shot's last smeared
P-frame N times so the incoming shot melts against a still base — the WD
"freeze the last frame of one smeared video, use it as the base for the next
smear" look.

```bash
python scripts/es_mosh.py concat.mp4 --cuts <frame,list> --freeze 12 -f 24 -o out.mp4
```

**2. Rhythmic bloom bursts** — short bounded P-frame duplication inside
otherwise clean footage. Bursts end early if they hit an I-frame (clean exit).

```bash
python scripts/es_mosh.py input.mp4 --bursts "96:8,240:6" -o out.mp4
```

**3. Dither texture** — optional. The WD menu does NOT use visible Bayer
dithering; if wanted at all keep it very light (levels 8+, barely visible).

**The default WD look:** melts + frozen seams alone. Iterated past this
(anchor bursts, clear ramps, ghost-plate dissolves) and rolled back:
bitstream I-frame clears are inherently abrupt; pixel-space dissolve passes
over-engineer the fix and read as cheezy. The abrupt clear is part of the
aesthetic.

### PERSISTENT MOSH + PIXELSORT (the "clean throughout" setup)

Bloom datamosh that stays clean and re-moshes in waves instead of collapsing, then a luma-sort pass.

**The mechanism: the I-frame refresh anchor (`--gop`).** With `-g 9999` (one I-frame for the whole video), P-frame duplication compounds with no reset and collapses into a frozen glitch loop. A short GOP drops periodic I-frames that act as refresh anchors — corruption builds, resets, rebuilds → persistent moshing without terminal collapse.

```bash
# 1) Bloom with a 0.5s refresh anchor (GOP 12 @ 24fps):
python scripts/mosh.py input.mp4 -d 10 -s <start> -f 24 --gop 12 -o bloom.mp4

# 2) Luma-sort the moshed output:
python scripts/pixelsort_mosh.py bloom.mp4 -o final.mp4 --axis rows --mode interval --low 50 --high 255
```

Guidance:
- `--gop` = frames between refresh anchors (seconds × fps). Smaller = steadier; larger = heavier corruption between resets.
- `-d` = how many P-frames repeat = trail length.
- **Collapse timing is GOP-controlled, not delta-controlled:** a single long GOP collapses at roughly the same point regardless of delta (verified: delta 1/2/3 all hit ~50/255 mean-corruption by 7-8s). To control *when* it collapses, change GOP cadence.

### A→B HEAVY GLITCH TRANSITION (datamosh to collapse, then melt into a new video)

Datamosh video A into full corruption, then transition into a brand-new video B — a genuine codec-level melt, not a crossfade.

**The seam:** encode A with a long GOP so corruption accumulates; B with a shorter GOP so it resolves clean; stitch frames; **drop B's opening I-frame** so B's first P-frames decode against A's corrupted reference. B melts in glitched and asserts itself as its deltas accumulate.

```bash
python scripts/transition_mosh.py A.mp4 B.mp4 -s 170 -d 8 --bloom-start 60 --b-gop 96 -o transition.mp4

# Pixelsort A's corrupted half, B arrives sorted-then-unsorts into view:
python scripts/pixelsort_mosh.py transition.mp4 -o final.mp4 \
    --axis rows --mode interval --low 50 --high 255 \
    --unsort-start 170 --unsort-frames 96
```

Mechanics / tuning:
- **`--unsort-start` MUST equal `-s`** (the splice frame) or sort/unsort misaligns with the melt.
- **`--b-gop` governs melt duration** — the dissolve fills B's first GOP; longer = more gradual. No crossfade opacity involved; it's decoder error clearing.
- **Residual melt at the tail** is expected if B is short and b_gop spans most of it — give B more runway or a smaller `--b-gop`.
- **Unsort works with `--mode interval`/`threshold`, not `--mode edges`** (edges branch keys off `edge_thresh` only).

### Compositing one shot over another's last frame (shot-level alpha)

For seams where the incoming shot has large flat/static regions (e.g. a
graphic on black) and you want the outgoing frame to persist underneath and
get progressively wiped: composite the incoming shot over the outgoing
shot's last frame using the incoming shot's luminance as alpha, BEFORE the
concat/melt. Why it works: mpeg4 P-frames only overwrite blocks their motion
vectors touch — black/flat areas of the incoming shot encode as "changed"
unless they match the reference. Pre-compositing makes flat areas literally
match the reference, so they preserve it; bright areas (the wiping element)
carry the motion vectors and progressively clear the frame.

```bash
# 1) Extract outgoing shot's last frame at concat resolution:
ffmpeg -sseof -0.1 -i shotA.mp4 -frames:v 1 -vf scale=W:H lastA.png

# 2) Composite (numpy): alpha = luminance of shotB, base = lastA.
#    comp = shotB * alpha + lastA * (1 - alpha), per frame; encode as shotB_composited.mp4

# 3) Use shotB_composited in the concat in place of shotB; melts as usual.
```

This is a prep step, not a skill script — adapt the numpy composite per project
(the alpha source can be luminance, a mask, or a real alpha channel if the
incoming render has one).

## Workflow for Agent Use

When the user provides footage and asks for datamoshing/glitch effects:

1. **Verify input** — ffprobe duration/resolution/fps; count shots and find cut frames (user may supply them; else scene-detect or infer from concat structure)
2. **Normalize** — all shots to one resolution/fps/SAR before any surgery
3. **Choose the operation** — melts at cuts (es_mosh), persistent bloom (mosh), A→B (transition_mosh), or polish passes (dither/CA/pixelsort/flicker)
4. **Run, then validate** — es_mosh.py prints frame-count/decode validation itself; for other scripts run your own check: `ffmpeg -v error -i out.mp4 -f null -` (expect no output) plus `ffprobe nb_frames` vs expected
5. **Report results** — files, sizes, frame counts, and any validation warnings

Chain polish passes AFTER codec surgery; each is MP4-in/MP4-out and survives re-encode quantization.

## Tips

- Videos with **more motion** produce better datamoshing (the codec has more vectors to corrupt). Static footage melts weakly.
- Lower resolution inputs (720p or below) give cleaner glitch artifacts than 4K
- I-frame removal works best at scene transitions — find cuts first, then target those frame ranges
- FFglitch outputs MPEG-4 ASP in an AVI container — pass `--mp4` or convert immediately; corrupted MPEG-4 ASP still plays poorly in many players
- Chain effects: melt → re-melt the output for deeper corruption (generational loss)
- **Use a short GOP (`--gop`) for bloom/trail effects** so the mosh persists without collapsing into a frozen loop.
- **Chain a pixelsort pass** after any datamosh to turn trailing squares into sorted streaks.
- **A→B transitions:** drop B's opening I-frame so B decodes against A's corrupted state — melt duration is set by `--b-gop`.
- **Progressive unsort** makes new content arrive heavily sorted and resolve to clean — pair its length with the melt GOP.
- **Full polish chain:** melts → dither → CA swell → flicker sort. Each pass is independent; re-run only the stage you're tuning.

## Pitfalls

- **Black/green frames**: Too many I-frames deleted. The decoder has no reference data. Fix: delete fewer frames or ensure at least one I-frame per scene.
- **Collapse into a permanent glitch loop**: Long GOP (`-g 9999`) + bloom compounds corruption until the content dies. Fix: set `--gop` (e.g. 12 @ 24fps) so periodic I-frames refresh the decoder.
- **FFglitch AVI playback issues**: Most players struggle with corrupted MPEG-4 ASP in AVI. Pass `--mp4` to ffglitch_mosh.py or convert to MP4 immediately after generation.
- **Avidemux-style frame editing won't work on H.265/HEVC**: The byte-level I-frame detection only works with MPEG-4 ASP (Xvid) format, which is why the pipeline re-encodes first.
- **lagfun ghost may drop frames** if the trim offset exceeds video length — ensure input is at least 1 second long.
- **NEVER do byte-surgery on AVI containers** (the legacy `cut_mosh`/`transition_mosh` path): the `00dc` chunk marker appears inside AVI stream headers too, so splitting on it truncates the header → grey first frame; hand-rebuilding `movi` chunk sizes → green/purple chroma desync that decodes "clean" but renders garbage. Use `es_mosh.py` (raw MPEG-4 elementary stream) instead — no container, no chunk sizes to corrupt.
- **`sc_threshold 0` does NOT stop ffmpeg's mpeg4 encoder inserting scene I-frames.** Only `-force_key_frames` gives deterministic I placement. The encoder also emits duplicate I-clusters (adjacent +1 frame indices) at some keyframes — drop whole clusters (headers AND VOPs) when melting.
- **A bloom burst REPLACES its source window**, it doesn't append: net frame add = emitted − consumed, not the burst length. Account for this or validation frame counts won't match.
- **Always validate after remux**: decode-error count (`ffmpeg -v error -f null -`) + exact frame count vs expected. Exit code 0 proves nothing about content — a chroma-desynced file decoded with zero errors.
