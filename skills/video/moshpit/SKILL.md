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
- **Python 3 + numpy** — system packages (numpy 2.4.3)

Install FFglitch if missing (x86_64 build — this machine is x86_64, NOT aarch64):
```bash
curl -L -o /tmp/ffglitch.7z "https://ffglitch.org/pub/bin/linux64/ffglitch-0.10.2-linux-x86_64.7z"
cd /tmp && 7z x ffglitch.7z   # needs p7zip/7zip: sudo pacman -S 7zip
sudo cp ffglitch-0.10.2-linux-x86_64/ffedit ffglitch-0.10.2-linux-x86_64/ffgac \
        ffglitch-0.10.2-linux-x86_64/qjs ffglitch-0.10.2-linux-x86_64/fflive /usr/local/bin/
```
> **Architecture note (Salt's box):** this machine is x86_64. The binaries in the README's original `linux-aarch64` block will NOT run here — use `linux64/` → `ffglitch-0.10.2-linux-x86_64.7z` from `https://ffglitch.org/pub/bin/linux64/`. Both `ffedit` and `ffgac` are pure `shutil.which()` PATH lookups, so `/usr/local/bin` is all they need; no per-script path config.

## Scripts

All scripts live in `scripts/` relative to this skill:

| Script | Purpose | Requires FFglitch? |
|--------|---------|-------------------|
| `moshpit.py` | Main orchestrator — batch-generate all variants | Partial (only for vector effects) |
| `mosh.py` | Pure FFmpeg I-frame removal + P-frame duplication | No |
| `ffglitch_mosh.py` | Motion vector manipulation via ffedit/ffgac | Yes |
| `dual_layer.py` | Two-video reveal: FFglitch-corrupts foreground into a mask that exposes clean background | Yes |
| `pixelsort_mosh.py` | Per-frame pixelsort pass (luma or green-hue sort); chains after any datamosh | No |
| `transition_mosh.py` | A→B codec-level transition: datamosh A to collapse, melt into B | No |

## Quick Start

```bash
# Generate ALL variants from a video:
python scripts/moshpit.py input.mp4

# Specific effects only:
python scripts/moshpit.py input.mp4 --effects melt bloom chaos wave

# Custom output directory + frame range for melt/bloom:
python scripts/moshpit.py input.mp4 -o ./glitched/ --start 20 --end 80
```

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

## Named Setups

### PERSISTENT MOSH + PIXELSORT (the "clean throughout" setup)

The flagship combo: bloom datamosh that stays clean and re-moshes in waves instead of collapsing, then a luma-sort pass. This is the preserved, hand-tuned recipe.

**The mechanism that makes it work: the I-frame refresh anchor (`--gop`).** `mosh.py`'s intermediate is encoded with `-g 9999` by default (one I-frame for the whole video), so P-frame duplication compounds with no reset and collapses into a frozen glitch loop partway through. Setting a short GOP drops periodic I-frames that act as refresh anchors — in the delta loop, in-range I-frames clear the repeat buffer and reset to clean. Corruption builds, resets, rebuilds → persistent moshing without terminal collapse.

```bash
# 1) Bloom with a 0.5s refresh anchor (GOP 12 @ 24fps), heavy P-frame reuse:
#    -d 10 fills most P-frames in each half-second window for maximum intensity
#    within the refresh limit. Lower -d (e.g. 6) = lighter trails.
python scripts/mosh.py input.mp4 -d 10 -s <start> -f 24 --gop 12 -o bloom.mp4

# 2) Luma-sort the moshed output:
python scripts/pixelsort_mosh.py bloom.mp4 -o final.mp4 --axis rows --mode interval --low 50 --high 255
```

Guidance:
- `--gop` = frames between refresh anchors (in seconds × fps). 12 @ 24fps = 0.5s. Smaller = steadier/more readable; larger = heavier corruption between resets.
- `-d` = how many P-frames repeat = trail length. A half-second anchor caps trail length at ~GOP frames before the I-frame resets it.
- **Tuning the collapse point:** a single long GOP with *any* bloom delta collapses at roughly the same point regardless of delta (verified: delta 1/2/3 all hit ~50/255 mean-corruption by 7-8s). Delta changes the flavor, not the collapse timing. To control *when* it collapses, change the GOP cadence — there is no delta setting that stretches a single-I-frame collapse to the last second.

### A→B HEAVY GLITCH TRANSITION (datamosh to collapse, then melt into a new video)

Datamosh video A into full corruption, then transition into a brand-new video B. The transition is a genuine codec-level melt, not a crossfade.

**How it works (the seam):** encode A as MPEG-4 ASP with a long GOP so its corruption accumulates; encode B with a shorter GOP so it can resolve clean; stitch the frames, then **drop B's opening I-frame** so B's first P-frames decode *against A's corrupted reference frame*. B melts in glitched and only asserts itself as its motion-compensated deltas and I-frames accumulate. Chain a pixelsort pass to corrupt A's pixels and (optionally) unsort B as it arrives.

```bash
# 1) Build the codec-level transition. A corrupts; B melts in clean.
#    -s <frame>  = output frame where B begins (default ~2/3 through A)
#    -d / --bloom-start = P-frame duplication on A (trails / when corruption starts)
#    --b-gop     = frames per B GOP. LONGER = slower, more gradual melt
#                  (96 @ 24fps = 4s dissolve). Shorter = snap-clean transition.
python scripts/transition_mosh.py A.mp4 B.mp4 -s 170 -d 8 --bloom-start 60 --b-gop 96 -o transition.mp4

# 2) Pixelsort A's corrupted half, and let B arrive sorted-then-unsort into view:
#    --until-frame <splice>  = sort only A's half, keep B clean (simple version)
#    --unsort-start <splice> --unsort-frames N = B arrives HEAVILY sorted and
#        unsorts progressively to clean over N frames (the "sorted wreckage
#        resolving" look — pairs with the melt).
python scripts/pixelsort_mosh.py transition.mp4 -o final.mp4 \
    --axis rows --mode interval --low 50 --high 255 \
    --unsort-start 170 --unsort-frames 96
```

Mechanics / tuning:
- **`--unsort-start` MUST equal `-s`** (the transition splice frame). The unsort must begin exactly where B begins, or the sort/unsort will be misaligned with the melt.
- **B must be scaled to A's resolution** (transition_mosh handles this via ffmpeg `scale=`).
- **`--b-gop` governs melt duration.** The dissolve fills B's first GOP: a longer GOP = a longer, more gradual fade. There is no crossfade opacity — the melt is the decoder's accumulated motion-compensation error clearing out.
- **`--unsort-*`:** `unsort_frames` = how many frames the B-side sort takes to recede to clean. Match it to the melt length (`--b-gop`) so the sort-streaks clear at the same rate the datamosh clears. Verified decay: seam diff ~62/255 → ~19 by end; residual is the datamosh blocks that only fully re-sync at B's next I-frame.
- **Unsort works with `--mode interval`/`threshold`, not `--mode edges`** — the edges branch keys off `edge_thresh` only, so `low`/`high` (and thus the unsort ramp) have no effect there.
- **Residual melt at the tail** is expected if B is short and `b_gop` spans most of it — give B more runway (longer clip) or a smaller `--b-gop` to fully resolve to pristine.
- A's collapse point follows the single-I-frame rule above (`--a-gop` long = accumulates).

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
python scripts/ffglitch_mosh.py input.mp4 --preset chaos -o output.mpg --mp4

# Custom JS filter:
python scripts/ffglitch_mosh.py input.mp4 --script my_filter.js -o output.mpg

# Extract vectors from one video, apply to another:
python scripts/ffglitch_mosh.py source.mp4 --extract vectors.dat
python scripts/ffglitch_mosh.py target.mp4 --transfer vectors.dat -o result.mpg --mp4
```

## Workflow for Agent Use

When the user provides a video and asks for datamoshing/glitch effects:

1. **Verify input exists** — check file path, get duration/resolution via ffprobe
2. **Choose effects** based on user request, or default to `melt bloom lagfun_trail chaos wave`
3. **Run moshpit.py** with the selected effects and output directory
4. **Report results** — list generated files with sizes

For a single effect, use the individual scripts directly for faster execution.

## Tips

- Videos with **more motion** produce better datamoshing (the codec has more vectors to corrupt)
- Lower resolution inputs (720p or below) give cleaner glitch artifacts than 4K
- I-frame removal works best at scene transitions — find cuts first, then target those frame ranges
- FFglitch outputs MPEG-1 (.mpg) which some players struggle with — always convert to MP4
- Chain effects: melt → re-melt the output for deeper corruption (generational loss)
- **Use a short GOP (`--gop`) for bloom/trail effects** so the mosh persists without collapsing into a frozen loop. See the PERSISTENT MOSH setup above.
- **Chain a pixelsort pass** after any datamosh to turn trailing squares into sorted streaks.
- **A→B transitions:** drop B's opening I-frame so B decodes against A's corrupted state — the melt duration is set by `--b-gop` (no crossfade, it's real decoder error). See the A→B TRANSITION setup.
- **Progressive unsort** (`--unsort-start/--unsort-frames`) makes new content arrive heavily sorted and resolve to clean — pair its length with the melt GOP.

## Pitfalls

- **Black/green frames**: Too many I-frames deleted. The decoder has no reference data. Fix: delete fewer frames or ensure at least one I-frame per scene.
- **Collapse into a permanent glitch loop**: Long GOP (`-g 9999`) + bloom compounds corruption until the content dies. Fix: set `--gop` (e.g. 12 @ 24fps) so periodic I-frames refresh the decoder.
- **FFglitch mpg playback issues**: Most players can't seek in corrupted MPEG-1. Convert to MP4 immediately after generation.
- **Avidemux-style frame editing won't work on H.265/HEVC**: The byte-level I-frame detection only works with MPEG-4 ASP (Xvid) format, which is why the pipeline re-encodes first.
- **lagfun ghost may drop frames** if the trim offset exceeds video length — ensure input is at least 1 second long.
