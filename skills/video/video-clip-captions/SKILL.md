---
name: video-clip-captions
description: Extract short clips from long videos with burned-in social-media captions. Downloads YouTube auto-captions (VTT), deduplicates overlapping blocks, and creates vertical 9:16 clips with verbatim word-level synced subtitles.
triggers: ["clip video", "extract clip", "social media captions", "short from video", "video captions"]
---

# Video Clip Captions Pipeline

Extract clips from long videos with burned-in verbatim captions for social media (TikTok/Reels/Shorts).

## Pipeline Steps

### 0. For local video files (not YouTube)
Use `faster-whisper` for STT (lighter than openai-whisper, installs cleanly on Pi):
```bash
pip install --break-system-packages faster-whisper
ffmpeg -y -i input.mov -vn -acodec pcm_s16le -ar 16000 -ac 1 /tmp/audio.wav
```
Then transcribe with Python (run in background, ~30-50 min for 80 min film on Pi 5 CPU):
```python
from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8")
segments, info = model.transcribe("/tmp/audio.wav", beam_size=5, language="en")
```
NOTE: On Pi 5 (~7GB RAM), use `base` model. `small` may OOM. Run as background process with `notify_on_complete=true` since foreground terminals get interrupted by user messages.

### 1. Download video + captions (YouTube only)
```bash
cd /tmp
yt-dlp -f "bestvideo[height<=1080]+bestaudio/best[height<=1080]" --merge-output-format mp4 -o "source.%(ext)s" "VIDEO_URL"
yt-dlp --write-auto-sub --sub-lang en --skip-download --sub-format vtt -o "source" "VIDEO_URL"
```

### 2. Parse VTT and deduplicate overlapping blocks

YouTube VTT has word-level timestamps AND overlapping blocks (each block repeats previous text + new words). Must dedup both.

Dedup algorithm (tested through 6 iterations):
```python
# 1. Parse blocks, strip all HTML/timing tags
# 2. Filter blocks < 100ms (these are exact 10ms duplicates)
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

### 4. Burn captions with ffmpeg

Style: bottom-aligned, small, out of the way
```
force_style='FontName=Arial,FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,Outline=1,Shadow=0,Alignment=2,MarginV=20,BackColour=&H00000000,Bold=0'
```

For letterboxed 9:16 (DEFAULT — full frame preserved, black bars on sides):
```
-vf "scale=1080:-2,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
```

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
- ~15-20s per clip on Pi 5

## Critical Lessons Learned

0. **Don't use /tmp for long-running work** — /tmp is cleared on reboot. If Pi crashes (power issues), all work is lost. Use persistent path like `~/hermes-agent/output/` for intermediates on important jobs.
1. **Never paraphrase captions** — use exact verbatim text from transcript
2. **YouTube VTT offset is ~1s late** — always shift earlier
3. **Word-level timestamps are incomplete** — VTT only captures key words, not all. Use block-level timing instead
4. **VTT blocks overlap by design** — each block repeats previous text. Must dedup with suffix-prefix matching
5. **Short captions are disorienting** — minimum 2.5s display, split gap difference for smooth transitions
6. **Bottom placement is critical** — centered captions cover the subject, always use Alignment=2 with low MarginV
7. **Pi 5 constraints** — single-threaded only, no parallel ffmpeg. ~140s per clip for caption burn, ~15-20s per clip for batch cut+caption
8. **Crop vs Letterbox** — cropping to 9:16 trims sides and loses content. Letterboxing (pillarbox) preserves full frame in 9:16 container. User preferred letterboxing for movie content
9. **STT on Pi 5** — faster-whisper base model: ~63 min for 80 min audio. Use `int8` compute. Run as background process — foreground terminals get interrupted by user messages
10. **For local files, Whisper offset still applies** — even though not YouTube, the 1s early shift improves caption sync
