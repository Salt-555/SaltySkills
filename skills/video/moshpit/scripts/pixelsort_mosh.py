#!/usr/bin/env python3
"""
pixelsort_mosh.py — Pixelsort pass over a video.

Reorders pixels within each frame by brightness (classic pixelsort), designed
to chain AFTER datamoshing. The datamosh trailing squares become sorted streaks
instead of uniform blocks.

Pure numpy — no extra dependencies. Reads frames via ffmpeg pipe, processes
with numpy, writes via ffmpeg pipe.

Modes (how runs are chosen):
  interval   Sort contiguous runs of pixels whose luma falls in [low, high].
             The classic glitch-art mode. Good for high-contrast footage.
  threshold  Sort runs of pixels brighter than `low` (runs split at pixels
             darker than `low`).
  edges      Split rows at edge-detection (Sobel on luma), sort runs between
             strong edges. Best when you want content-aware boundaries.

Usage:
  python pixelsort_mosh.py moshed.mp4 -o sorted.mp4
  python pixelsort_mosh.py in.mp4 -o out.mp4 --axis cols --mode threshold --low 40
  python pixelsort_mosh.py in.mp4 -o out.mp4 --reverse
"""

import os
import sys
import argparse
import subprocess
import tempfile
import numpy as np


def probe_dims(input_video):
    """Return (width, height, fps) for a video."""
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=width,height,r_frame_rate',
         '-of', 'csv=p=0', input_video],
        capture_output=True, text=True
    )
    w, h, fr = probe.stdout.strip().split(',')
    width, height = int(w), int(h)
    num, den = fr.split('/')
    src_fps = int(num) / max(int(den), 1)
    return width, height, src_fps


def read_frames(input_video, width, height):
    """Yield rgb frames via ffmpeg rawvideo pipe."""
    cmd = [
        'ffmpeg', '-loglevel', 'error', '-i', input_video,
        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    frame_bytes = width * height * 3
    try:
        while True:
            buf = proc.stdout.read(frame_bytes)
            if not buf or len(buf) < frame_bytes:
                break
            frame = np.frombuffer(buf, dtype=np.uint8,
                                  count=frame_bytes).reshape(height, width, 3)
            frame = frame.copy()  # frombuffer shares read-only pipe buffer
            yield width, height, frame
    finally:
        proc.stdout.close()
        proc.wait()


def luma(rgb):
    """BT.601 luma from an (H,W,3) uint8 array."""
    return (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1]
            + 0.114 * rgb[..., 2]).astype(np.float32)


def sobel_edges(gray):
    """Approx Sobel magnitude on a float32 2D array."""
    gx = np.zeros_like(gray)
    gy = np.zeros_like(gray)
    gx[:, 1:-1] = (gray[:, 2:] - gray[:, :-2])
    gy[1:-1, :] = (gray[2:, :] - gray[:-2, :])
    return np.hypot(gx, gy)


def green_key(rgb):
    """Greenness measure per pixel: how much green exceeds the max of R/B.
    High for neon-green/teal on dark. (H,W) float32."""
    r = rgb[..., 0].astype(np.float32)
    g = rgb[..., 1].astype(np.float32)
    b = rgb[..., 2].astype(np.float32)
    return np.maximum(0.0, g - np.maximum(r, b))


def _sort_runs(line_rgb, line_key, runs, reverse=False):
    """Sort pixels within each (start,end) run by key (luma or greenness).

    line_rgb: (N,3) uint8, line_key: (N,) float32, runs: list[(s,e)].
    In-place reorders line_rgb by key within each run.
    """
    for s, e in runs:
        if e - s < 2:
            continue
        seg = line_rgb[s:e]
        order = line_key[s:e].argsort()
        if reverse:
            order = order[::-1]
        line_rgb[s:e] = seg[order]


def pixelsort_frame(rgb, axis='rows', mode='interval', low=0, high=255,
                    edge_thresh=12.0, reverse=False, key='luma'):
    """Pixelsort one frame in place. rgb: (H,W,3) uint8.
    key: 'luma' (brightness) or 'green' (greenness) — both the sort scalar
    and, for interval/threshold, the mask criterion."""
    h, w = rgb.shape[:2]
    if key == 'green':
        scalar = green_key(rgb)
    else:
        scalar = luma(rgb)

    if mode == 'edges':
        edges = sobel_edges(luma(rgb))
        edge_mask = edges > edge_thresh
        # transpose the sort line to match axis
        if axis == 'rows':
            edge_line = edge_mask  # each row
            key_line = scalar
        else:
            edge_line = edge_mask.T
            key_line = scalar.T
        for i in range(edge_line.shape[0]):
            line_rgb = rgb[i] if axis == 'rows' else rgb[:, i]
            boundaries = np.flatnonzero(edge_line[i])
            runs = list(zip(boundaries[:-1], boundaries[1:]))
            _sort_runs(line_rgb, key_line[i], runs, reverse=reverse)
    else:
        # interval / threshold: mask of pixels to sort
        if mode == 'interval':
            mask = (scalar >= low) & (scalar <= high)
        else:  # threshold: scalar > low
            mask = scalar > low
        if axis == 'rows':
            mask_line = mask
            key_line = scalar
        else:
            mask_line = mask.T
            key_line = scalar.T
        for i in range(mask_line.shape[0]):
            line_rgb = rgb[i] if axis == 'rows' else rgb[:, i]
            m = mask_line[i]
            # runs of consecutive True
            d = np.diff(np.concatenate(([0], m.view(np.int8), [0])))
            starts = np.flatnonzero(d == 1)
            ends = np.flatnonzero(d == -1)
            runs = list(zip(starts, ends))
            _sort_runs(line_rgb, key_line[i], runs, reverse=reverse)


def pixelsort_video(input_video, output_video, axis='rows', mode='interval',
                    low=0, high=255, edge_thresh=12.0, fps=24, reverse=False,
                    key='luma', until_frame=0, unsort_start=0, unsort_frames=60):
    """Pixelsort every frame of a video, writing a new MP4.

    until_frame: if > 0, only the first `until_frame` frames are sorted;
    the rest pass through unchanged.

    unsort_start / unsort_frames: progressive "unsort". Frames at/after
    unsort_start are sorted with a low-threshold that ramps from `low` toward
    `high` over unsort_frames, so fewer pixels reorder each frame and the
    sort weakens to clean. At unsort_start the sort is heaviest; it resolves
    to clean by unsort_start+unsort_frames. Use for B-side of a transition
    so new content arrives heavily sorted and unsorts into view.
    """
    width, height, src_fps = probe_dims(input_video)
    if fps is None:
        fps = int(round(src_fps))

    encoder = subprocess.Popen(
        ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo',
         '-pix_fmt', 'rgb24', '-s', f'{width}x{height}', '-r', str(fps),
         '-i', '-', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p',
         output_video],
        stdin=subprocess.PIPE
    )

    done = 0
    for w, h, frame in read_frames(input_video, width, height):
        if unsort_start > 0 and done >= unsort_start:
            # progressive unsort: low ramps up toward high over unsort_frames
            span = max(unsort_frames, 1)
            k = done - unsort_start
            p = min(k / (span - 1), 1.0) if span > 1 else 1.0
            low_eff = low + p * (high - low)
            if low_eff < high:
                pixelsort_frame(frame, axis=axis, mode=mode, low=low_eff,
                                high=high, edge_thresh=edge_thresh,
                                reverse=reverse, key=key)
        elif until_frame <= 0 or done < until_frame:
            pixelsort_frame(frame, axis=axis, mode=mode, low=low, high=high,
                            edge_thresh=edge_thresh, reverse=reverse, key=key)
        encoder.stdin.write(frame.tobytes())
        done += 1
        if done % 30 == 0:
            print(f"  sorted {done} frames...")

    encoder.stdin.close()
    encoder.wait()
    print(f"✓ Pixelsorted {done} frames → {output_video}")


def main():
    parser = argparse.ArgumentParser(
        description="Pixelsort a video (chain after datamoshing).")
    parser.add_argument("input_video")
    parser.add_argument("-o", "--output", default="pixelsorted.mp4")
    parser.add_argument("--axis", choices=["rows", "cols"], default="rows",
                        help="rows = sort each row (horizontal streaks); "
                             "cols = sort each column (vertical combing)")
    parser.add_argument("--mode", choices=["interval", "threshold", "edges"],
                        default="interval")
    parser.add_argument("--low", type=int, default=0,
                        help="luma low bound for interval/threshold (0-255)")
    parser.add_argument("--high", type=int, default=255,
                        help="luma high bound for interval (0-255)")
    parser.add_argument("--edge-thresh", type=float, default=12.0,
                        help="Sobel magnitude cutoff for edges mode")
    parser.add_argument("--key", choices=["luma", "green"], default="luma",
                        help="sort scalar: 'luma' (brightness) or 'green' "
                             "(greenness — isolates neon-green subject)")
    parser.add_argument("--until-frame", type=int, default=0,
                        help="only sort the first N frames; pass the rest "
                             "through clean (for A→B transitions)")
    parser.add_argument("--unsort-start", type=int, default=0,
                        help="frame where a progressive unsort begins: new "
                             "content arrives heavily sorted, weakens to clean")
    parser.add_argument("--unsort-frames", type=int, default=60,
                        help="how many frames the unsort takes to reach clean "
                             "(default 60 = 2.5s @ 24fps)")
    parser.add_argument("--fps", type=int, default=None,
                        help="output fps (default: auto from source)")
    parser.add_argument("--reverse", action="store_true",
                        help="sort descending (brightest first)")
    args = parser.parse_args()

    if not os.path.isfile(args.input_video):
        print(f"Error: '{args.input_video}' not found.", file=sys.stderr)
        sys.exit(1)

    if args.low > args.high:
        print("Error: --low must be <= --high", file=sys.stderr)
        sys.exit(1)

    pixelsort_video(args.input_video, args.output, axis=args.axis,
                    mode=args.mode, low=args.low, high=args.high,
                    edge_thresh=args.edge_thresh, fps=args.fps,
                    reverse=args.reverse, key=args.key,
                    until_frame=args.until_frame,
                    unsort_start=args.unsort_start,
                    unsort_frames=args.unsort_frames)


if __name__ == "__main__":
    main()
