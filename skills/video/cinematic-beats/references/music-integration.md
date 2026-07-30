# Music Integration Reference

## Downloading Suno Tracks from URLs

Suno share links (`https://suno.com/s/<id>`) don't provide direct download. Workaround:

1. **Fetch the HTML page:**
   ```bash
   curl -L "https://suno.com/s/<track-id>" -o suno-track.html
   ```

2. **Extract CDN URL from HTML:**
   ```bash
   grep -oiE 'https?://[^"'"'"' ]+\.(mp3|ogg|m4a)[^"'"'"' ]*' suno-track.html | head -1
   ```
   Look for the actual audio file URL (not `sil-100.mp3` which is a placeholder).

3. **Download:**
   ```bash
   curl -L "https://cdn1.suno.ai/<track-id>.mp3" -o music/background.mp3
   ```

4. **Verify duration:**
   ```bash
   ffprobe -v error -show_entries format=duration -of csv=p=0 music/background.mp3
   ```

## Sidechain Ducking Parameters

| Parameter | Range | Effect | Default in pipeline |
|-----------|-------|--------|---------------------|
| `threshold` | 0.01-0.1 | Lower = more aggressive ducking | 0.02 |
| `ratio` | 2:1 to 10:1 | Higher = stronger compression | 4:1 |
| `attack` | 5-100ms | How fast music ducks when voice starts | 50ms |
| `release` | 50-500ms | How fast music recovers after voice ends | 200ms |
| `makeup` | 0.5-3.0 | Restores level after compression | 1.5 |

**Tuning guide:**
- Music too loud during speech → lower threshold (0.01) or increase ratio (6:1)
- Music ducks too abruptly → increase attack (80ms+)
- Music pumps/breathes unnaturally between beats → increase release (300ms+)
- Ducking doesn't feel noticeable → raise makeup (2.0+)

## FFprobe Duration Parsing

**Pi 5 compatibility:** Use `-of csv=p=0` for reliable duration extraction:
```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 file.mp4
# Returns: 4.880000\n
```

Do NOT use `-of default=noprint_wrappers=1` — it returns `duration=4.880000` which fails `float()` parsing on some Pi 5 ffprobe versions.

## Music Looping for Video Assembly

When mixing music into beats of varying lengths, loop the music track to fill each beat:
```bash
ffmpeg -i video.mp4 -stream_loop -1 -i music.mp3 \
  -filter_complex "[1:a][0:a]sidechaincompress=..." \
  -t $BEAT_DUR output.mp4
```

`-stream_loop -1` loops the audio infinitely; `-t $BEAT_DUR` trims to exact beat length. This avoids generating per-beat music segments.
