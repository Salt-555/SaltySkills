#!/usr/bin/env python3
"""Dynamic dry/wet bitcrush + tremolo on wet + slapback delay."""
import numpy as np
from pydub import AudioSegment

def process(input_path, output_base):
    audio = AudioSegment.from_mp3(input_path)
    samples = np.array(audio.get_array_of_samples(), dtype=np.float64)
    
    max_val = 2**(audio.sample_width*8-1)
    samples /= max_val
    
    n_samples = len(samples)
    sr = audio.frame_rate
    t = np.arange(n_samples) / sr
    
    # --- Bitcrush: decimate 5x, zero-order hold upsample, quantize to 8-bit ---
    down = samples[::5]
    upsampled = np.repeat(down, 5)[:len(samples)]
    quant_levels = 2**8 - 1
    crushed = np.round(upsampled * quant_levels) / quant_levels
    
    # --- Dynamic dry/wet dips (baseline 0.80/0.20, dip to ~0.35/~0.65) ---
    baseline_dry = 0.80
    dip_dry = 0.35
    mask = np.full(n_samples, baseline_dry)
    
    interval = int(1.2 * sr)
    duration = int(0.25 * sr)
    
    for start in range(interval, n_samples - duration, interval):
        end = min(start + duration, n_samples)
        fade_len = min(int(0.04 * sr), duration // 3)
        segment = np.full(end - start, dip_dry)
        if fade_len > 0:
            segment[:fade_len] = np.linspace(baseline_dry, dip_dry, fade_len)
            segment[-fade_len:] = np.linspace(dip_dry, baseline_dry, fade_len)
        mask[start:end] = segment
    
    wet_mask = 1.0 - mask
    
    # --- Tremolo on wet signal only (4Hz triangle wave) ---
    # Triangle wave: 0→1→0 over each period
    phase = (t * 4) % 1
    tri_wave = np.where(phase < 0.5, phase * 2, 2 - phase * 2)
    
    # Wet pulses between 30% and 100% of its level
    tremolo_on_wet = 0.3 + 0.7 * tri_wave
    
    wet_trembled = wet_mask * crushed * tremolo_on_wet
    
    # --- Mix dry + trembled wet ---
    mixed = mask * samples + wet_trembled
    
    # --- Slapback delay (80ms, ~-15dB) ---
    delay_samples = int(0.08 * sr)  # 80ms
    delay_volume = 0.12  # ~-18dB — subtle but audible
    
    delayed = np.zeros(n_samples)
    for i in range(delay_samples, n_samples):
        delayed[i] = mixed[i - delay_samples] * delay_volume
    
    final = mixed + delayed
    
    # --- Prevent clipping ---
    peak = np.max(np.abs(final))
    if peak > 1.0:
        final /= peak
    
    out_samples = (final * max_val).astype(np.int16)
    out = AudioSegment(
        out_samples.tobytes(),
        frame_rate=sr,
        sample_width=2,
        channels=1
    )
    out.export(f"{output_base}.mp3", format="mp3")
    print(f"  dynamic + tremolo + slapback -> saved ({len(out)}ms)")

if __name__ == "__main__":
    import sys
    input_path = sys.argv[1] if len(sys.argv) > 1 else "test-voice-base.mp3"
    output_base = sys.argv[2] if len(sys.argv) > 2 else "test-vibey-dec5-bit8"
    print(f"Dynamic dry/wet + tremolo on wet + slapback delay:")
    process(input_path, output_base)
