#!/usr/bin/env python3
"""
ca_swell.py — Chromatic aberration with organic swell/recede dynamics.

Chainable post-pass (like dither_mosh.py): reads frames via ffmpeg pipe,
applies RGB radial/linear channel split with a time-varying amplitude, writes
via ffmpeg pipe.

The amplitude follows a sum-of-sines "breathing" curve — several slow
oscillators at incommensurate frequencies/phases so swells happen at varied
intervals and speeds, never visibly repeating. Amplitude envelope is smooth
(ease in/out per swell), and each swell can have independent random speed.

Usage:
  python ca_swell.py in.mp4 -o out.mp4
  python ca_swell.py in.mp4 -o out.mp4 --max 12 --min 1
  python ca_swell.py in.mp4 -o out.mp4 --swells 45 --dur 8
  python ca_swell.py in.mp4 -o out.mp4 --mode linear --angle 30
"""

import os
import sys
import math
import random
import argparse
import subprocess
import numpy as np


def probe(input_video):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
         "-of", "csv=p=0", input_video], capture_output=True, text=True)
    w, h, fr, nf = r.stdout.strip().split(",")
    num, den = fr.split("/")
    return int(w), int(h), int(num) / max(int(den), 1), int(nf) if nf.isdigit() else 0


def build_envelope(n_frames, fps, n_swells, min_amp, max_amp, seed):
    """Sum-of-sines envelope + explicit random swells.

    Returns per-frame amplitude array (n_frames,) in [min_amp, max_amp].
    Layered: a slow base undulation (never fully flat) plus n_swells distinct
    gaussian bumps at random times/widths/intensities.
    """
    rng = random.Random(seed)
    t = np.arange(n_frames, dtype=np.float32) / fps

    # base undulation: 3 slow sines, incommensurate rates, phase-random
    env = np.zeros(n_frames, dtype=np.float32)
    for rate, weight in [(0.07, 0.5), (0.13, 0.3), (0.023, 0.2)]:
        phase = rng.uniform(0, 2 * math.pi)
        env += weight * np.sin(t * rate * 2 * math.pi + phase) ** 2  # 0..1
    env /= env.max() + 1e-9  # normalize base to 0..1

    # explicit swells: gaussian bumps, random center/width/peak
    for _ in range(n_swells):
        center = rng.uniform(0.05, 0.95) * n_frames
        width = rng.uniform(0.4, 2.5) * fps  # 0.4s .. 2.5s wide
        peak = rng.uniform(0.5, 1.0)
        env += peak * np.exp(-0.5 * ((np.arange(n_frames) - center) / width) ** 2)

    env = np.clip(env, 0, 1)
    return min_amp + env * (max_amp - min_amp)


_remap_cache = {}

def _radial_remap(h, w, amt_key):
    """Cache the per-amplitude remap indices — geometry only, content-free."""
    key = (h, w, amt_key)
    if key in _remap_cache:
        return _remap_cache[key]
    cy, cx = h / 2.0, w / 2.0
    Y = np.arange(h, dtype=np.float32)[:, None]
    X = np.arange(w, dtype=np.float32)[None, :]
    dy = Y - cy
    dx = X - cx
    norm = np.sqrt(cy ** 2 + cx ** 2)
    inv = 1.0 / (np.abs(dy) + np.abs(dx) + 1e-6)
    uy = dy * inv
    ux = dx * inv
    edge = np.sqrt(dy ** 2 + dx ** 2) / norm
    amt = amt_key  # exact, since we quantize before calling
    shift_y = (uy * amt * edge).astype(np.int32)
    shift_x = (ux * amt * edge).astype(np.int32)
    Yi = Y.astype(np.int32)
    Xi = X.astype(np.int32)
    ys = np.clip(Yi + shift_y, 0, h - 1)
    xs = np.clip(Xi + shift_x, 0, w - 1)
    ys2 = np.clip(Yi - shift_y, 0, h - 1)
    xs2 = np.clip(Xi - shift_x, 0, w - 1)
    _remap_cache[key] = (ys, xs, ys2, xs2)
    return _remap_cache[key]


def main():
    p = argparse.ArgumentParser(description="Chromatic aberration swell pass.")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--min", type=float, default=0.5,
                   help="resting aberration in pixels (default 0.5)")
    p.add_argument("--max", type=float, default=10.0,
                   help="peak aberration in pixels (default 10)")
    p.add_argument("--swells", type=int, default=6,
                   help="number of distinct swells over the video (default 6)")
    p.add_argument("--mode", choices=["radial", "linear"], default="radial")
    p.add_argument("--angle", type=float, default=25.0,
                   help="linear-mode split angle in degrees (default 25)")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    if not os.path.isfile(args.input):
        sys.exit(f"not found: {args.input}")

    w, h, fps, nf = probe(args.input)
    if not nf:
        # count via decode
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-count_frames",
                            "-show_entries", "stream=nb_read_frames",
                            "-of", "csv=p=0", args.input],
                           capture_output=True, text=True)
        nf = int(r.stdout.strip())
    n_frames = nf
    print(f"{w}x{h} @ {fps:.0f}fps, {n_frames} frames")

    env = build_envelope(n_frames, fps, args.swells, args.min, args.max, args.seed)
    peaks = [(i / fps, round(float(env[i]), 1))
             for i in range(1, n_frames)
             if env[i] >= env[i - 1] and (i == n_frames - 1 or env[i] > env[i + 1])
             and env[i] > args.min + 0.6 * (args.max - args.min)]
    print(f"swell peaks (t, px): {peaks}")

    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(int(fps)),
         "-i", "-", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
         args.output], stdin=subprocess.PIPE)

    dec = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-i", args.input,
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE)
    fb = w * h * 3
    done = 0
    a = math.radians(args.angle)
    while True:
        buf = dec.stdout.read(fb)
        if len(buf) < fb:
            break
        frame = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3)
        amt = float(env[done])
        if args.mode == "radial":
            if amt < 0.75:
                out = frame  # below visible threshold — pass through
            else:
                amt_key = round(amt * 2) / 2.0  # quantize to 0.5px → cache hit
                ys, xs, ys2, xs2 = _radial_remap(h, w, amt_key)
                out = frame.copy()
                out[:, :, 0] = frame[ys, xs, 0]
                out[:, :, 2] = frame[ys2, xs2, 2]
        else:
            if amt < 0.75:
                out = frame
            else:
                out = frame.copy()
                sx = int(round(amt * math.cos(a)))
                sy = int(round(amt * math.sin(a)))
                if sx or sy:
                    out[:, :, 0] = np.roll(frame[:, :, 0], (sy, sx), axis=(0, 1))
                    out[:, :, 2] = np.roll(frame[:, :, 2], (-sy, -sx), axis=(0, 1))
        enc.stdin.write(out.tobytes())
        done += 1
        if done % 100 == 0:
            print(f"  {done}/{n_frames}")
    dec.stdout.close()
    dec.wait()
    enc.stdin.close()
    enc.wait()
    print(f"OK {done} frames -> {args.output}")


if __name__ == "__main__":
    main()
