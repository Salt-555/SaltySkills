---
name: moshpit
description: Datamoshing and video glitch effects pipeline. Takes a video, produces multiple glitched variations via I-frame removal, P-frame duplication, FFglitch motion vectors, and FFmpeg lagfun trails. Use when user wants to datamosh, glitch, or corrupt video footage artistically.
category: creative
---

# Moshpit — Video Datamoshing Pipeline

Glitch art tool that takes a source video and produces multiple corrupted/glitched variations using real codec manipulation (not simulated filters).

## Dependencies

- **FFmpeg** (system) — always available on Pi 5
- **FFglitch 0.10.2** (`ffedit`, `ffgac`) — installed at `/usr/local/bin/`
- **Python 3 + numpy** — system packages

Install FFglitch if missing:
```bash
curl -L -o /tmp/ffglitch.7z "https://ffglitch.org/pub/bin/linux-aarch64/ffglitch-0.10.2-linux-aarch64.7z"
cd /tmp && 7z x ffglitch.7z
sudo cp ffglitch-extract/*/ffedit ffglitch-extract/*/ffgac ffglitch-extract/*/qjs /usr/local/bin/
```

## Scripts

All scripts live in `scripts/` relative to this skill:

| Script | Purpose | Requires FFglitch? |
|--------|---------|-------------------|
| `moshpit.py` | Main orchestrator — batch-generate all variants | Partial (only for vector effects) |
| `mosh.py` | Pure FFmpeg I-frame removal + P-frame duplication | No |
| `ffglitch_mosh.py` | Motion vector manipulation via ffedit/ffgac | Yes |

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

## Pitfalls

- **Black/green frames**: Too many I-frames deleted. The decoder has no reference data. Fix: delete fewer frames or ensure at least one I-frame per scene.
- **FFglitch mpg playback issues**: Most players can't seek in corrupted MPEG-1. Convert to MP4 immediately after generation.
- **Avidemux-style frame editing won't work on H.265/HEVC**: The byte-level I-frame detection only works with MPEG-4 ASP (Xvid) format, which is why the pipeline re-encodes first.
- **lagfun ghost may drop frames** if the trim offset exceeds video length — ensure input is at least 1 second long.
