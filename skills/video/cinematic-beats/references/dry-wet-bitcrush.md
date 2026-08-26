# Dry/Wet Bitcrush Voice Filter

## Signature Chain

Our locked-in voice filter for cinematic beats videos. Applied to every TTS clip after generation.

### Approach A: Static Mix (ffmpeg)

Simple, consistent dry/wet mix using ffmpeg's aresample roundtrip:

```bash
# Step 1: Create crushed version via wav intermediate (preserves duration)
ffmpeg -y -i input.mp3 \
  -af "aresample=resampler=soxr:osr=2000,aformat=sample_fmts=u8,aresample=resampler=soxr,lowpass=f=2500" \
  temp-crushed.wav

# Step 2: Mix dry + wet with compression glue
ffmpeg -y -i input.mp3 -i temp-crushed.wav \
  -filter_complex "[0:a]volume=0.7[dry];[1:a]volume=0.3[wet];[dry][wet]amix=inputs=2:duration=first:normalize=0,acompressor=threshold=0.05:ratio=4:attack=10:release=100[out]" \
  -map "[out]" output.mp3

rm temp-crushed.wav
```

### Approach B: Dynamic Mix (Python — preferred)

Zero-order hold upsampling for authentic bitcrush at correct pitch. Includes tremolo on wet signal and slapback delay for rhythmic texture.

```bash
python3 scripts/vibey-mix.py beats/beat-XX/audio.mp3
cp beats/beat-XX/audio-dynamic.mp3 beats/beat-XX/audio-filtered.mp3
```

**Locked parameters (dec5-bit8 variant):**
- **Decimation:** 5× (drops every 5th sample, zero-order hold upsampling)
- **Quantization:** 8-bit (constant)
- **Dry/wet baseline:** 80% dry / 20% wet
- **Dip pattern:** Every ~1.2s, dry drops to ~35%, wet rises to ~65% (duration ~0.25s)
- **Tremolo on wet only:** 4Hz triangle wave, depth 70% (wet pulses between 30-100%)
- **Slapback delay:** 80ms at -18dB (~0.12 volume), applied to final mix

**Result:** Clean voice layered with extreme digital artifacts. The dynamic dips create a "degrading transmission" effect, tremolo gives the crunch rhythmic pulsing, and slapback adds spacey depth underneath everything.

## Tunable Parameters

| Parameter | Current | Effect of Change |
|-----------|---------|------------------|
| `osr=2000` (ffmpeg) / decim=5 (python) | 2000 Hz / 5× | Lower = more extreme crunch (1000-4000 range for ffmpeg; 3-10x for python). **Current: 5×** |
| `volume=0.3` (wet static) | 30% static, 20-65% dynamic | Higher = more artifacts audible (0.15-0.40 range for static) |
| `lowpass=f=2500` | 2500 Hz | Lower = tamer harshness, higher = brighter crunch |
| `acompressor ratio` | 4:1 | Higher = more "glued" but less dynamic |
| Decimation (dynamic) | 5× | Current locked value. 3-10x range for experimentation |
| Quantization bits | 8-bit | Lower = more extreme. 6-bit/4-bit lighter, 4-bit/2-bit would be nuclear |
| Dip interval | ~1.2s | Shorter = more frequent glitches |
| Dip depth | dry→0.35, wet→0.65 | Lower dry = more aggressive glitch effect |
| Tremolo frequency (wet) | 4Hz triangle wave | Higher = faster pulsing, lower = slower throbbing |
| Tremolo depth (wet) | 70% | 0=no tremolo, 1=full on/off pulsing |
| Slapback delay time | 80ms | Shorter = tighter echo, longer = more spacey. 50-120ms range typical |
| Slapback volume | -18dB (0.12) | Higher = more audible repeat. Keep subtle — it's texture not a lead effect |

## Tremolo on Wet Signal

Tremolo modulates ONLY the crushed/wet signal, NOT the clean dry voice. Creates rhythmic pulsing that makes the bitcrush feel alive rather than static.

**Implementation:**
```python
# Triangle wave oscillating 0→1→0 at given frequency
phase = (t * freq) % 1
tri_wave = np.where(phase < 0.5, phase * 2, 2 - phase * 2)

# Scale: wet pulses between (1-depth) and 1.0 of its level
tremolo_on_wet = (1 - depth) + depth * tri_wave
wet_trembled = wet_mask * crushed_signal * tremolo_on_wet
```

**Why only on wet?** The clean dry signal stays stable for vocal intelligibility. Tremolo on the crunch underneath creates a synth-like throbbing that adds vibe without sacrificing clarity.

## Slapback Delay

A single short echo (50-120ms) mixed into the final output. Creates retro spacey quality — like hearing yourself through a degraded transmission in an empty room.

**Implementation:**
```python
delay_samples = int(delay_s * sr)  # e.g., 80ms at sample rate
delay_volume = 0.12  # ~-18dB, subtle but audible
delayed = np.zeros(n_samples)
for i in range(delay_samples, n_samples):
    delayed[i] = mixed[i - delay_samples] * delay_volume
final = mixed + delayed
```

**Why slapback (not reverb)?** Slapback is a single discrete echo — punchy and retro. Reverb creates wash that muddies the bitcrush texture. Keep it subtle; it's atmosphere not a lead effect.

## Critical Pitfalls

### Zero-Order Hold Required for Correct Pitch

**WRONG:** `samples[::N]` without upsampling — This drops samples but doesn't resample back to original rate. Audio plays N× faster with pitch shifted up by N×. Sounds like a sped-up chipmunk, not bitcrush.

**CORRECT (Python):** Zero-order hold upsampling — Downsample by dropping every Nth sample, then repeat each remaining sample N times:
```python
down = samples[::N]          # Drop samples → creates aliasing potential
upsampled = np.repeat(down, N)[:len(samples)]  # Repeat each sample → preserves pitch
quantized = np.round(upsampled * (2**bits-1)) / (2**bits-1)  # Bit depth reduction
```

**CORRECT (ffmpeg):** `aresample` roundtrip — Downsample to X Hz then resample back to original rate:
```bash
aresample=resampler=soxr:osr=X,aresample=resampler=soxr
```
The first aresample creates aliasing artifacts; the second restores playback speed.

### Duration Preservation Requires WAV Intermediate

Direct MP3 output from complex filter chains loses samples:
- `aresample` roundtrip can eat ~10% of duration when encoding directly to MP3
- Solution: encode crushed signal to `.wav` first (lossless, preserves exact duration), then mix in second pass

**Working pattern:**
```bash
# Pass 1: crush → wav (preserves duration)
ffmpeg -i input.mp3 -af "aresample=...,aformat=u8,aresample=..." temp.wav

# Pass 2: mix dry+wav → mp3 
ffmpeg -i input.mp3 -i temp.wav -filter_complex "[0:a]volume=X[dry];[1:a]volume=Y[wet];[dry][wet]amix=...[out]" -map "[out]" output.mp3
```

### `apad` Creates Infinite Files

**NEVER use `apad` without explicit duration bounds.** It pads audio forever — creates 8GB+ files in seconds and fills disk.

**Safe alternatives:**
- Use `-t DURATION` to limit output length
- Use `atrim=start:end` with explicit end time
- For padding: `tpad=stop_mode=clone:stop_duration=X` (video) or calculate exact needed duration first

### Complex Filter Chains Timeout on Pi 5

Multi-input filter chains (`asplit`, `acrossfade`, `sidechaincompress`) can exceed the 30s terminal timeout.

**Fix:** Two-pass approach — split to temp files, process separately, then merge:
```bash
# Instead of one massive filter_complex call:
ffmpeg -i input.mp3 -t 0.5 -c copy part1.mp3
ffmpeg -i input.mp3 -ss 0.5 -c copy part2.mp3
# Process each part...
ffmpeg -i processed1.mp3 -i processed2.mp3 -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1[out]" -map "[out]" output.mp3
```

### MP3 Encoder Queue Warnings

`[libmp3lame] Trying to remove 576 samples, but the queue is empty` — harmless warning that appears when filter chain produces slightly fewer samples than expected. Does not affect output quality but indicates duration mismatch in filter graph.

**Fix:** Ensure all filter branches produce matching sample counts by using `duration=first` in amix and avoiding filters that change sample rate without compensation.

## Dynamic Mixing Technique

The dynamic mix creates a "degrading transmission" effect rather than static bitcrush:

1. **Baseline state (80% dry / 20% wet):** Clean voice with subtle crunch underneath
2. **Dip event (~0.25s every ~1.2s):** Dry drops to ~35%, wet rises to ~65% — signal briefly degrades noticeably then returns to clean
3. **Smooth transitions:** Fade in/out of dips (40ms each) to avoid clicks

This creates rhythmic texture — the voice is mostly clear but periodically "glitches" like a degraded digital transmission. More interesting than static mix without being overwhelming.

## Alternative Approaches (Tested, Rejected)

| Approach | Why Rejected |
|----------|--------------|
| `asetrate` alone | Changes speed, not bitcrush |
| Single-pass filter_complex to MP3 | Loses duration (~10% truncation) |
| `rubberband=pitch=X` for formant shift | Too subtle at low values (<5%), obvious chipmunk at high values |
| Modulating pitch via segment splitting | Works but adds complexity; user preferred static/dynamic filter |
| `afftnr` for noise floor | Actually a noise REDUCER, not adder — fails on OGG input |

## Session Notes

- **May 28, 2026:** Initial discovery session. Tested bitcrush, radio filters, pitch modulation, dry/wet mixing. Locked in: dry/wet at 70/30 with 2kHz crush + lowpass + compression glue.
- **User preference:** "light" artifacts — heavy crunch mixed low under clean signal rather than crushing the whole signal.
- **May 28 (later):** Discovered zero-order hold upsampling for correct-pitch bitcrush. User liked dec5-bit8 texture. Added dynamic mixing with periodic dips revealing more crunch underneath.
- **Final iteration:** User wanted "more vibey" → added tremolo on wet signal (4Hz triangle wave) and slapback delay (80ms, -18dB). Locked in the shipped `dec5-bit8` chain: 5× decimation with 8-bit quantization, plus dynamic dips raising the wet level during the mix.
- **Script consolidation:** Moved `vibey-mix.py` from scattered `audio_cache/` into skill's own `scripts/` directory for self-containment.

## Discovery Log — What Didn't Work

The path to zero-order hold required eliminating wrong approaches:

1. **Simple decimation (`samples[::N]`)** → Pitch shifted up N×, sounded like sped-up chipmunk. Wrong because dropping samples without upsampling changes playback rate.
2. **Pure bit-depth reduction** (quantize without sample-rate change) → No aliasing texture, just quiet quantization noise. Wrong because true bitcrush needs the sample-rate artifact to create audible distortion.
3. **ffmpeg `aresample` roundtrip** → Works but applies soxr anti-aliasing filters that smooth out harsh artifacts. Good for "tame" crunch, bad for authentic bitcrush texture.
4. **Zero-order hold upsampling (`np.repeat(down, N)`)** → CORRECT. Drops samples (creates aliasing potential), then repeats each sample to restore original rate without pitch shift. Produces authentic stair-step waveform with real digital artifacts.
