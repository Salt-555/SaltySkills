#!/usr/bin/env python3
"""
flicker_sort.py — Pixel-sort flicker: pixel sorting flashes on for random
1-3 frame bursts, then off. Chainable after anything (MP4 in/out).

The flicker reads as digital tearing — the sort runs at full row density
(every row, not row-skipped) during a burst so each flash is unmistakable,
then the video snaps back clean. Bursts never land within N frames of each
other (refractory gap), so flashes stay distinct events.

Usage:
  python flicker_sort.py in.mp4 -o out.mp4                       # defaults
  python flicker_sort.py in.mp4 -o out.mp4 --bursts 8 --len 2    # denser, shorter
  python flicker_sort.py in.mp4 -o out.mp4 --threshold 80        # more violent
  python flicker_sort.py in.mp4 -o out.mp4 --axis v --seed 9
  python flicker_sort.py in.mp4 -o out.mp4 --window 700,983     # only act in range
"""

import os
import sys
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
    fps = int(num) / max(int(den), 1)
    n = int(nf) if nf.isdigit() else 0
    return int(w), int(h), fps, n


def count_frames(input_video):
    w, h, fps, n = probe(input_video)
    if n:
        return n
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-count_frames", "-show_entries", "stream=nb_read_frames",
                        "-of", "csv=p=0", input_video], capture_output=True, text=True)
    return int(r.stdout.strip())


def plan_bursts(n_frames, n_bursts, max_len, min_gap, seed, window=None):
    """Random non-overlapping bursts of length 1..max_len with a refractory gap."""
    rng = random.Random(seed)
    lo, hi = window if window else (0, n_frames)
    bursts = []
    tries = 0
    while len(bursts) < n_bursts and tries < n_bursts * 50:
        tries += 1
        start = rng.randint(lo, max(lo, hi - max_len - 1))
        length = rng.randint(1, max_len)
        if any(abs(start - b0) < min_gap or abs(start + length - (b0 + b1)) < min_gap
               or (b0 <= start <= b0 + b1) or (start <= b0 <= start + length)
               for b0, b1 in bursts):
            continue
        bursts.append((start, length))
        tries = 0
    return sorted(bursts)


def sort_burst(frame, threshold, axis):
    """Full-density pixel sort: bright runs in each row (or column) get sorted."""
    gray = frame.astype(np.float32).mean(axis=2)
    out = frame.copy()
    if axis == "h":
        for y in range(frame.shape[0]):
            mask = gray[y] > threshold
            if not mask.any():
                continue
            d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
            for s, e in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
                if e - s > 2:
                    idx = np.argsort(gray[y, s:e], kind="stable")
                    out[y, s:e] = frame[y, s:e][idx]
    else:
        for x in range(frame.shape[1]):
            mask = gray[:, x] > threshold
            if not mask.any():
                continue
            d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
            for s, e in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
                if e - s > 2:
                    idx = np.argsort(gray[s:e, x], kind="stable")
                    out[s:e, x] = frame[s:e, x][idx]
    return out


def main():
    p = argparse.ArgumentParser(description="Pixel-sort flicker pass.")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--bursts", type=int, default=6,
                   help="number of flicker events (default 6)")
    p.add_argument("--len", type=int, default=3, dest="max_len",
                   help="max burst length in frames (default 3; use ~24 for 1s)")
    p.add_argument("--minlen", type=int, default=1,
                   help="min burst length in frames (default 1)")
    p.add_argument("--gap", type=int, default=None,
                   help="min frames between bursts (default: 1 second)")
    p.add_argument("--threshold", type=int, default=100,
                   help="luma threshold for sorting (default 100; lower = more)")
    p.add_argument("--axis", choices=["h", "v"], default="h")
    p.add_argument("--window", help="only flicker within 'start,end' frames")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    if not os.path.isfile(args.input):
        sys.exit(f"not found: {args.input}")
    if not (1 <= args.minlen <= args.max_len):
        sys.exit("--minlen must be >= 1 and <= --len")

    w, h, fps, _ = probe(args.input)
    n = count_frames(args.input)
    window = None
    if args.window:
        a, b = args.window.split(",")
        window = (max(0, int(a)), min(n, int(b)))
    min_gap = args.gap if args.gap is not None else int(fps)

    bursts = []
    rng = random.Random(args.seed)
    lo, hi = window if window else (0, n)
    tries = 0
    while len(bursts) < args.bursts and tries < args.bursts * 50:
        tries += 1
        length = rng.randint(args.minlen, args.max_len)
        start = rng.randint(lo, max(lo, hi - length - 1))
        if any(abs(start - b0) < min_gap or (b0 <= start <= b0 + b1)
               or (start <= b0 <= start + length) for b0, b1 in bursts):
            continue
        bursts.append((start, length))
        tries = 0
    burst_map = {}
    for start, length in bursts:
        for i in range(start, start + length):
            burst_map[i] = True
    print(f"{n} frames @ {fps:.0f}fps | {len(bursts)} bursts: "
          f"{[(s, l) for s, l in bursts]}")
    print(f"total flicker frames: {len(burst_map)} "
          f"({len(burst_map)/n*100:.1f}% of video)")

    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(int(fps)),
         "-i", "-", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
         args.output], stdin=subprocess.PIPE)
    dec = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-i", args.input,
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    fb = w * h * 3
    done = 0
    while True:
        buf = dec.stdout.read(fb)
        if len(buf) < fb:
            break
        frame = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3)
        if done in burst_map:
            frame = sort_burst(frame, args.threshold, args.axis)
        enc.stdin.write(frame.tobytes())
        done += 1
    dec.stdout.close()
    dec.wait()
    enc.stdin.close()
    enc.wait()
    print(f"OK {done} frames -> {args.output}")


if __name__ == "__main__":
    main()
