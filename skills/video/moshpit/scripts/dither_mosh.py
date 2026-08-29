#!/usr/bin/env python3
"""
dither_mosh.py — RetroDither-style ordered (Bayer) dithering pass, chainable
after any datamosh. The Bayer matrix quantizes each 8x8 cell to a palette,
producing the crosshatch "digital surveillance" texture that defines the
Watch Dogs look. It pairs with datamosh artifacts: dithering AFTER a mosh
texturizes the trailing blocks; dithering with --contrast-first crushes luma
before quantizing for a harder, more graphic look.

Also supports --glitch-dither: the dither threshold is re-randomized every N
frames, so the dither pattern boils/flickers over time (animated texture,
not a static overlay).

Pure numpy. Reads frames via ffmpeg pipe, writes via ffmpeg pipe — same
chaining contract as pixelsort_mosh.py.

Usage:
  python dither_mosh.py moshed.mp4 -o dithered.mp4
  python dither_mosh.py in.mp4 -o out.mp4 --levels 4 --cell 4
  python dither_mosh.py in.mp4 -o out.mp4 --mono            # black/white
  python dither_mosh.py in.mp4 -o out.mp4 --boil 3          # animated pattern
  python dither_mosh.py in.mp4 -o out.mp4 --until-frame 96  # dither only A's half
"""

import os
import sys
import argparse
import subprocess
import numpy as np

# 8x8 Bayer matrix (normalized 0..1) — the classic ordered-dither layout
BAYER8 = (np.array([
    [ 0, 32,  8, 40,  2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44,  4, 36, 14, 46,  6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [ 3, 35, 11, 43,  1, 33,  9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47,  7, 39, 13, 45,  5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21],
], dtype=np.float32) / 64.0)


def probe_dims(input_video):
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=width,height,r_frame_rate',
         '-of', 'csv=p=0', input_video],
        capture_output=True, text=True)
    w, h, fr = probe.stdout.strip().split(',')
    num, den = fr.split('/')
    return int(w), int(h), int(num) / max(int(den), 1)


def read_frames(input_video, width, height):
    cmd = ['ffmpeg', '-loglevel', 'error', '-i', input_video,
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    frame_bytes = width * height * 3
    try:
        while True:
            buf = proc.stdout.read(frame_bytes)
            if not buf or len(buf) < frame_bytes:
                break
            frame = np.frombuffer(buf, dtype=np.uint8,
                                  count=frame_bytes).reshape(height, width, 3)
            yield frame.copy()
    finally:
        proc.stdout.close()
        proc.wait()


def bayer_matrix(cell):
    """Recursively build a 2^k Bayer matrix for cell sizes 2,4,8,16."""
    if cell == 2:
        return np.array([[0, 2], [3, 1]], dtype=np.float32) / 4.0
    prev = bayer_matrix(cell // 2)
    return np.block([
        [4 * prev,     4 * prev + 2],
        [4 * prev + 3, 4 * prev + 1],
    ]) / (cell * cell)


def dither_frame(rgb, levels=6, cell=8, mono=False, contrast=1.0,
                 threshold=None):
    """Ordered-dither one frame. rgb: (H,W,3) uint8. Returns new frame.
    threshold: optional (H,W) float32 in [0,1); pass a re-randomized Bayer
    each N frames for the animated 'boil' variant."""
    h, w = rgb.shape[:2]
    f = rgb.astype(np.float32) / 255.0

    if contrast != 1.0:
        f = np.clip((f - 0.5) * contrast + 0.5, 0.0, 1.0)

    if mono:
        f = (0.299 * f[..., 0] + 0.587 * f[..., 1]
             + 0.114 * f[..., 2])[..., None].repeat(3, axis=-1)

    if threshold is None:
        b = bayer_matrix(cell) if cell != 8 else BAYER8
        thr = np.tile(b, (h // cell + 1, w // cell + 1))[:h, :w]
    else:
        thr = threshold

    if thr.ndim == 2:
        thr = thr[..., None]  # broadcast one threshold over RGB

    # quantize with the Bayer offset inside each quantization step
    q = levels - 1.0
    out = np.floor(f * q + thr) / q
    return (np.clip(out, 0, 1) * 255).astype(np.uint8)


def dither_video(input_video, output_video, levels=6, cell=8, mono=False,
                 contrast=1.0, boil=0, fps=None, until_frame=0):
    width, height, src_fps = probe_dims(input_video)
    if fps is None:
        fps = int(round(src_fps))

    encoder = subprocess.Popen(
        ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo',
         '-pix_fmt', 'rgb24', '-s', f'{width}x{height}', '-r', str(fps),
         '-i', '-', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p',
         output_video],
        stdin=subprocess.PIPE)

    rng = np.random.default_rng(1337)
    done = 0
    for frame in read_frames(input_video, width, height):
        if until_frame > 0 and done >= until_frame:
            encoder.stdin.write(frame.tobytes())
            done += 1
            continue

        thr = None
        if boil > 0:
            if done % boil == 0:
                # re-randomize the threshold: shuffle the Bayer cell ordering
                # keeps spatial dither structure but decorrelates over time
                b = bayer_matrix(cell)
                for row in b:
                    rng.shuffle(row)
                thr = np.tile(b, (height // cell + 1, width // cell + 1))
                thr = thr[:height, :width]
        out = dither_frame(frame, levels=levels, cell=cell, mono=mono,
                           contrast=contrast, threshold=thr)
        encoder.stdin.write(out.tobytes())
        done += 1
        if done % 60 == 0:
            print(f"  dithered {done} frames...")

    encoder.stdin.close()
    encoder.wait()
    print(f"✓ Dithered {done} frames → {output_video}")


def main():
    parser = argparse.ArgumentParser(
        description="Ordered (Bayer) dither pass — Watch Dogs texture, chains after datamoshing.")
    parser.add_argument("input_video")
    parser.add_argument("-o", "--output", default="dithered.mp4")
    parser.add_argument("--levels", type=int, default=6,
                        help="quantization levels per channel (2 = hard 1-bit "
                             "look, 4-8 = subtle. default 6)")
    parser.add_argument("--cell", type=int, choices=[2, 4, 8, 16], default=8,
                        help="Bayer matrix cell size (default 8)")
    parser.add_argument("--mono", action="store_true",
                        help="grayscale before dithering (hard graphic look)")
    parser.add_argument("--contrast", type=float, default=1.0,
                        help="contrast boost applied pre-quantize "
                             "(1.0 = none; 1.5-2.0 for the crushed WD look)")
    parser.add_argument("--boil", type=int, default=0,
                        help="re-randomize dither threshold every N frames — "
                             "animated 'boiling' pattern (e.g. 3 = every 3rd frame)")
    parser.add_argument("--until-frame", type=int, default=0,
                        help="dither only the first N frames; pass the rest clean")
    parser.add_argument("--fps", type=int, default=None)
    args = parser.parse_args()

    if not os.path.isfile(args.input_video):
        print(f"Error: '{args.input_video}' not found.", file=sys.stderr)
        sys.exit(1)

    dither_video(args.input_video, args.output, levels=args.levels,
                 cell=args.cell, mono=args.mono, contrast=args.contrast,
                 boil=args.boil, fps=args.fps, until_frame=args.until_frame)


if __name__ == "__main__":
    main()
