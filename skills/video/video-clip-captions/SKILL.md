---
name: video-clip-captions
description: Use when you need to clip long videos into 9:16 shorts with burned-in captions.
triggers: ["clip video", "extract clip", "social media captions", "short from video", "video captions"]
category: video
platforms: [linux, macos, windows]
version: 1.0.0
author: Hermes
license: MIT
metadata:
  hermes:
    tags: [video, captions, subtitles, ffmpeg, youtube, whisper, short-form]
---

# Video Clip Captions Pipeline

Extract clips from long videos with burned-in verbatim captions for social media (TikTok/Reels/Shorts).

## When to Use

Use when you need to pull one or more short vertical (9:16) clips out of a long horizontal video — a movie, podcast, interview, or YouTube video — with the spoken words burned directly into the frame so they're legible without sound. Good for social-media clips (TikTok/Reels/Shorts), trailers, and highlight reels where viewers watch muted.

Not a fit when: captions must be editable later (burned-in text can't be removed) — use sidecar `.srt`/`.vtt` files instead; or when you want to *generate* captions for a fully authored video rather than clip from an existing one.

## Prerequisites

- **ffmpeg** (with libass for the `subtitles` filter): `sudo apt install ffmpeg` (Debian/Ubuntu), `sudo pacman -S ffmpeg` (Arch), `brew install ffmpeg` (macOS)
- **yt-dlp** (YouTube source only): `pip install yt-dlp` (or `brew install yt-dlp`)
- **faster-whisper** (local files only): `pip install --break-system-packages faster-whisper`
- ~2–4 GB free disk per clip (1080p source + intermediates)
- Optional but recommended: a persistent working dir like `~/hermes-agent/output/` for intermediates (see Critical Lessons #0 — avoid `/tmp` for long-running jobs)

## Pipeline Steps

### 0. For local video files (not YouTube)
Use `faster-whisper` for STT (lighter than openai-whisper, installs cleanly on Pi):
```bash
mkdir -p ~/hermes-agent/output
pip install --break-system-packages faster-whisper
ffmpeg -y -i input.mov -vn -acodec pcm_s16le -ar 16000 -ac 1 ~/hermes-agent/output/audio.wav
```
Then transcribe with Python (run in background, ~63 min for 80 min film on Pi 5 CPU):
```python
from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8")
segments, info = model.transcribe("~/hermes-agent/output/audio.wav", beam_size=5, language="en")
```
NOTE: Pi 5 ships with 4/8/16 GB RAM; use the 8 GB (or 16 GB) model — on the 8 GB model use `base`. `small` may OOM. Run as background process with `notify_on_complete=true` since foreground terminals get interrupted by user messages.

### 1. Download video + captions (YouTube only)
```bash
cd ~/hermes-agent/output
yt-dlp -f "bestvideo[height<=1080]+bestaudio/best[height<=1080]" --merge-output-format mp4 -o "source.%(ext)s" "VIDEO_URL"
yt-dlp --write-auto-sub --sub-lang en --skip-download --sub-format vtt -o "source" "VIDEO_URL"
```

### 2. Parse VTT and deduplicate overlapping blocks

YouTube VTT has word-level timestamps AND overlapping blocks (each block repeats previous text + new words). Must dedup both.

Dedup algorithm (tested through 6 iterations):
```python
# 1. Parse blocks, strip all HTML/timing tags
# 2. Filter blocks < 100ms (sub-100ms blocks are near-instant duplicates)
filtered = [(s,e,t) for s,e,t in parsed if (e-s)*1000 >= 100]

# 3. Remove consecutive identical text
# 4. Suffix-prefix matching to find overlap between consecutive blocks
def find_overlap_suffix_prefix(prev, curr):
    prev_words = prev.split()
    curr_words = curr.split()
    for length in range(min(len(prev_words), len(curr_words)), 0, -1):
        if prev_words[-length:] == curr_words[:length]:
            return length
    return 0

# 5. Keep only new words, estimate proportional timing
overlap = find_overlap_suffix_prefix(prev_text, text)
if overlap > 0:
    new_words = text.split()[overlap:]
    new_text = ' '.join(new_words)
    new_ratio = len(new_words) / len(text.split())
    new_start = start + (end - start) * (1 - new_ratio)
```

NOTE: Do NOT use word-level timestamps (`<ts><c>word` pattern) — they drop too many words (articles, prepositions). Use block-level timing with full text and dedup.

### 3. Create SRT with proper timing

Key settings refined through 6 iterations of user feedback:

- **Caption offset: -1.0 seconds** (YouTube auto-captions are ~1s behind actual speech — this is consistent)
- **Minimum duration: 2.5 seconds** per subtitle (shorter is disorienting)
- **Split gap difference**: extend end time forward, pull start time back, meet in middle for smooth overlap. Do NOT just stretch end to meet next start — user wants the overlap handoff.
- **Use block-level timestamps** with full text, NOT word-level (word-level drops articles, prepositions, etc.)

Timing algorithm:
```python
def split_difference_overlap(subs, min_dur=2.5):
    """Extend each end forward, pull each start back, meet in middle"""
    adjusted = []
    for i, (start, end, text) in enumerate(subs):
        if i < len(subs) - 1:
            next_start = subs[i+1][0]
            gap = next_start - end
            if gap > 0:
                end = end + gap / 2
            if end - start < min_dur:
                end = start + min_dur
        else:
            if end - start < min_dur:
                end = start + min_dur
        adjusted.append((start, end, text))

    # Second pass: pull starts earlier to meet prev end in the middle
    final = []
    for i, (start, end, text) in enumerate(adjusted):
        if i > 0:
            prev_end = adjusted[i-1][1]
            gap = start - prev_end
            if gap > 0:
                start = start - gap / 2
        final.append((max(0, start), end, text))
    return final
```

Then apply offset:
```python
# Shift all timestamps 1s earlier
shifted = [(max(0, s-1.0), max(0, e-1.0), t) for s, e, t in subs]
```

Serialize the adjusted `(start, end, text)` tuples to `.srt` format:
```python
def write_srt(subs, path="clip.srt"):
    """Serialize (start, end, text) tuples to SubRip (.srt) format."""
    def fmt(sec):
        h = int(sec // 3600); m = int((sec % 3600) // 60)
        s = int(sec % 60); ms = int(round((sec - int(sec)) * 1000))
        if ms == 1000: ms = 0; s += 1
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    lines = []
    for i, (start, end, text) in enumerate(subs, 1):
        lines.append(f"{i}\n{fmt(start)} --> {fmt(end)}\n{text.strip()}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path
```
`write_srt(shifted)` produces e.g. `1\n00:00:01,000 --> 00:00:03,500\nHello world.`

### 4. Burn captions with ffmpeg

Style: bottom-aligned, small, out of the way
```
force_style='FontName=Arial,FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,Outline=1,Shadow=0,Alignment=2,MarginV=20,BackColour=&H00000000,Bold=0'
```

For letterboxed 9:16 (DEFAULT — full frame preserved, black bars on sides):
```
-vf "scale=1080:-2,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
```

Full burn command (combines scale + pad + subtitles, audio copied through):
```bash
ffmpeg -y -i clip.mp4 \
  -vf "scale=1080:-2,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,subtitles=clip.srt:force_style='FontName=Arial,FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,Outline=1,Shadow=0,Alignment=2,MarginV=20,BackColour=&H00000000,Bold=0'" \
  -c:a copy out.mp4
```
Notes: the `subtitles=clip.srt` path is relative to the current working directory (make it absolute if you run ffmpeg from elsewhere); `-c:a copy` copies the audio stream losslessly instead of re-encoding.

### 5. SRT generation from Whisper transcripts (local files)

For local files using faster-whisper, the transcript is a JSON list of `{start, end, text}` segments. Generate SRT directly:

```python
def make_srt_from_whisper(clip_start, clip_end, all_segments):
    subs = []
    for s in all_segments:
        if s["start"] >= clip_start and s["end"] <= clip_end and len(s["text"]) > 2:
            adj_start = max(0, s["start"] - clip_start - 1.0)  # 1s offset
            adj_end = max(0, s["end"] - clip_start - 1.0)
            if adj_end > adj_start:
                subs.append((adj_start, adj_end, s["text"]))

    # Extend: each sub lasts until next starts, min 2.5s
    extended = []
    for i, (start, end, text) in enumerate(subs):
        if i < len(subs) - 1:
            end = subs[i+1][0]
        if end - start < 2.5:
            end = start + 2.5
        extended.append((start, end, text))
    return extended
```

### 6. Batch processing (30+ clips)

For many clips, run as background Python script (not execute_code which times out at 300s):
- Cut each clip with ffmpeg
- Generate SRT per clip
- Burn captions per clip
- Use `crf=28` for batch (smaller files, faster encode)
- Cutting + SRT generation is quick (~15-20s per clip on Pi 5); caption burn is the slow step (~140s/clip — see Critical Lessons #7). For 30+ clips, plan for burn-bound throughput.

## Critical Lessons Learned

0. **Don't use /tmp for long-running work** — /tmp is cleared on reboot. If Pi crashes (power issues), all work is lost. Use persistent path like `~/hermes-agent/output/` for intermediates on important jobs.
1. **Never paraphrase captions** — use exact verbatim text from transcript
2. **YouTube VTT offset is ~1s late** — always shift earlier
3. **Word-level timestamps are incomplete** — VTT only captures key words, not all. Use block-level timing instead
4. **VTT blocks overlap by design** — each block repeats previous text. Must dedup with suffix-prefix matching
5. **Short captions are disorienting** — minimum 2.5s display, split gap difference for smooth transitions
6. **Bottom placement is critical** — centered captions cover the subject, always use Alignment=2 with low MarginV
7. **Pi 5 constraints** — single-threaded only, no parallel ffmpeg. ~140s per clip for caption burn; batch cut + SRT generation is quick (~15-20s per clip). Burn is the bottleneck for 30+ clips
8. **Crop vs Letterbox** — cropping to 9:16 trims sides and loses content. Letterboxing (pillarbox) preserves full frame in 9:16 container. User preferred letterboxing for movie content
9. **STT on Pi 5** — faster-whisper base model: ~63 min for 80 min audio. Use `int8` compute. Run as background process — foreground terminals get interrupted by user messages
10. **For local files, Whisper offset still applies** — even though not YouTube, the 1s early shift improves caption sync

## Verification

- **Check dimensions**: `ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 out.mp4` → expect `1080,1920` (9:16). If the value is `1080,-2`-style odd height or a different resolution, re-check the scale/pad filter.
- **Check duration/audio**: `ffprobe -v error -show_entries format=duration -of csv=p=0 out.mp4` should roughly match the clip length; confirm an audio stream is present (`ffprobe -v error -show_entries stream=codec_type -of csv=p=0 out.mp4`).
- **Spot-check sync**: play the output and verify each caption appears as the speaker says the words (esp. around hard cuts and the 1s offset) and that no caption lingers past the next one (the split-gap overlap should look smooth).
- **Sanity-check the SRT**: open `clip.srt` and confirm timestamps are sequential, non-overlapping, and formatted `HH:MM:SS,mmm --> HH:MM:SS,mmm`, and that the text is verbatim (not paraphrased).
