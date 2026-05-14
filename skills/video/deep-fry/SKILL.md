---
name: deep-fry
description: "Multi-phase ASCII video pipeline: generate ASCII variants from source video, config-driven glitch editing with segment stitching, and VHS/analog artifact polish. Produces stylized glitch-art videos with controlled transitions between ASCII color styles."
tags: [deep-fry, ascii, glitch, vhs, ffmpeg, pipeline, segmentation]
---

# Deep-Fry Pipeline

Three-phase modular pipeline for creating ASCII glitch-art videos with style transitions and analog post-processing.

## Pre-Flight (always do this first)

Before starting the render, ask the user:

1. **Caption text** — "Want a caption overlay at the end? Default is none."
2. **If yes** — ask what text. If they say "ALLMIND" or something else, use that with `allmind.enabled: true`.
3. **If no / default** — set `allmind.enabled: false` and skip the overlay entirely.

## Workflow

```
Phase 1: ASCII Render     → Source video → 4 variants (vidcolors, bw, matrix, rainbow)
Phase 2: Glitch Editing   → YAML config → stitched segments with slow-mo + text overlay
Phase 3: VHS Polish       → Assembled video → analog artifact overlay
```

Each phase is independent. Skip phases 1 or 2 on re-runs to change only one part of the pipeline.

## Phase 1: ASCII Rendering

Generate all style variants in a single pass (same luminance→char mapping for all versions):
- `vidcolors` - source pixel colors on black background (main/base layer)
- `bw` - clean monochrome
- `matrix` - green phosphor terminal with katakana/runes + CRT barrel + scanlines + glitch bands
- `rainbow` - HSV cycling + saturation boost

## Phase 2: Glitch Editing

YAML-driven segment stitching. Each segment specifies which ASCII variant and percentage range:

```yaml
edit:
  name: "protocol"
  source_dir: /tmp/ascii_output          # Phase 1 output
  output_dir: /tmp/glitch_output         # Phase 2 output
  slowdown_factor: 1.0                   # 1.0 = normal, 4.0 = 0.25x
  segments:
    - source: vidcolors; start_pct: 0; end_pct: 10
    - source: matrix; start_pct: 10; end_pct: 16
    - source: vidcolors; start_pct: 16; end_pct: 25
    # ... etc
  allmind:
    enabled: true
    start_pct: 85                        # percentage of final duration
    text: ALLMIND
    font_size: 120
    color: "#C5A55A"                     # hex, not rgba
    shadow: true
```

`ffmpeg` concat for assembly. Normalizes all segments to same fps/timebase before concat.

## Phase 3: VHS Polish

Per-frame analog artifact overlay:
- Chromatic aberration (R/B channel offset)
- Analog noise (subtle grain)
- Horizontal jitter (1px micro-shift on ~15% of frames)
- Tracking lines (horizontal brightness bands on ~4% of frames)
- Scanlines (every 4th row)
- CRT vignette

## Performance Guidance (Pi 5)

Portrait video at 24fps, ~145 frames (~6s source):
| Resolution | Font Size | ~Time/Variant | Quality |
|---|---|---|---|
| 672x1008 | 9px | 4-5 min | Good |
| 896x1344 | 12px | 7-8 min | Excellent |
| 1080x1920 | 14px | 12-15 min | Best (heavy) |

Use 672x1008 (font-size 9) for fast iteration. Bump to 896x1344 for final renders. Desktop viewport (1920-wide) can handle the bigger sizes.

## Pitfalls

- **`setpts` requires video-only input** — pass `-an` during segment extraction
- **`-vsync cfr` / `-r` silently kills `setpts` slow-mo** — when using `setpts` to
  stretch segment duration, do NOT combine with `-vsync cfr` or `-r` flags. They force
  frame-rate consistency and override the timestamp manipulation. Use `fps=24` after
  setpts instead: `setpts=2.5*PTS,fps=24`. Always verify segment durations with
  `ffprobe -show_entries format=duration` after extraction.
- **ffmpeg concat silently drops segments** with different timebases — normalize fps/timebase first
`drawtext` escaping — use hex colors, use `enable='gte(t,X)'` (no backslash before comma)
- **vhs_polisher.py probes `stream=codec_type`** — make sure `show_entries=stream=codec_type,width,height,r_frame_rate` includes `codec_type` or the script crashes with KeyError
- **glitch_editor.py per-segment slow** — each segment supports `slow: N` key (overrides global `slowdown_factor`). Script patches: reads `seg.get("slow", slowdown)` and uses it in setpts filter. Removed `-vsync cfr -r 24000/1001` which negated setpts duration changes.
- **numpy frombuffer is read-only** — `.copy()` before mutation
- **Pi 5**: matrix variant has inline CRT/scanline processing, ~2s/frame. Others ~1.5s/frame.
- **Telegram delivery**: 50MB limit. Re-encode with `-crf 20-22` if exceeded.
- **User workflow**: once the render pipeline is kicked off, DO NOT kill and restart
  mid-run while tweaking parameters. Let it complete first, then iterate. The user
  prefers "wait for it" over "kill and optimize" — the original would finish faster
  than any restart attempt.
- **vhs_polisher strips audio** — Phase 3 is video-only (rawvideo pipe). After polish,
  mux the original audio back: `ffmpeg -y -i polished.mp4 -i audio.aac -c:v copy -c:a aac -shortest final.mp4`
- **vhs_polisher output dir** — script now auto-creates parent dirs (`os.makedirs`). If you see
  "No such file or directory" on the output path, verify the patch is applied.
- **Config YAML format**: use multi-line YAML for segments, NOT semicolon syntax. The
  fallback YAML parser in `glitch_editor.py` can't parse `- source: X; start_pct: 0; end_pct: 10`
  on one line. Use separate keys per line for reliable parsing.
- **Per-segment slow-mo**: `glitch_editor.py` supports `slow: 2.5` per-segment (added 2025-05-13).
  Falls back to global `slowdown_factor` if omitted.
