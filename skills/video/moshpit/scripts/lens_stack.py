#!/usr/bin/env python3
"""
lens_stack.py — Bodycam/CRT lens look, built on ffmpeg's native lenscorrection
filter + custom edge passes layered after it.

Architecture (learned from the fisheye.py interaction bug — geometry passes
must not fight each other over the same remap):

  Single decode/encode sweep: the input is decoded ONCE, piped through ffmpeg
  WITH the native lenscorrection + vignette filters applied in-line
  (-filter_complex on the rawvideo input), and the Python edge passes
  (edge-flip ring, edge-weighted chroma, scanlines) run on the raw frames
  before the single final encode. One decode, one encode total.

  1. lenscorrection (native ffmpeg): radial distortion k1/k2, black fill for
     out-of-lens corners (fc option), bilinear interpolation. The canonical
     model: r_src = r_tgt * (1 + k1*(r/r0)^2 + k2*(r/r0)^4), r0 = half-diagonal.
     POSITIVE k1/k2 = fisheye; corners letterbox black natively.
  2. vignette (native ffmpeg): tube edge darkening.
  3. Custom numpy passes (no ffmpeg filter exists for these):
     - edge-flip ring: beyond R, image mirrors back on itself (cheap lens
       seeing its own housing)
     - edge-weighted chroma: R/B split ramping 0 center → max at rim
     - scanlines (optional CRT stack)

Usage:
  python lens_stack.py in.mp4 -o out.mp4                          # fisheye only
  python lens_stack.py in.mp4 -o out.mp4 --k1 0.25 --k2 0.15      # bodycam bulge
  python lens_stack.py in.mp4 -o out.mp4 --k1 0.25 --k2 0.15 \
      --edge-flip 0.92 --edge-chroma 10 --vignette 0.25           # full lens
  python lens_stack.py in.mp4 -o out.mp4 --k1 0.2 --scanlines 3   # + CRT rows
"""

import os
import sys
import math
import argparse
import subprocess
import tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _common import probe, open_encoder
except ImportError:
    probe_fps = open_encoder = None  # fallback if _common absent


def probe(input_video):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate",
         "-of", "csv=p=0", input_video], capture_output=True, text=True)
    w, h, fr = r.stdout.strip().split(",")
    num, den = fr.split("/")
    return int(w), int(h), f"{num}/{den}", int(num) / max(int(den), 1)


def build_flip_remap(h, w, flip_r_frac):
    """Mirror-flip ring remap: for output pixels beyond flip radius, sample the
    mirrored position inside. Content-free, computed once.

    NOTE: runs on the ALREADY-letterboxed lenscorrection output — it flips the
    visible image (including black corners) inward, like lens housing reflection.
    """
    cy, cx = h / 2.0, w / 2.0
    r0 = float(np.hypot(cy, cx))
    Y = (np.arange(h, dtype=np.float32)[:, None] - cy)
    X = (np.arange(w, dtype=np.float32)[None, :] - cx)
    r = np.sqrt(X * X + Y * Y)
    flip_r = flip_r_frac * r0
    beyond = r > flip_r
    r_flip = np.where(beyond, 2.0 * flip_r - r, r)
    with np.errstate(divide="ignore", invalid="ignore"):
        ux = np.where(r > 0.5, X / r, 0.0)
        uy = np.where(r > 0.5, Y / r, 0.0)
    sx = np.clip(cx + ux * r_flip, 0, w - 1).astype(np.int32)
    sy = np.clip(cy + uy * r_flip, 0, h - 1).astype(np.int32)
    return sy, sx


def build_chroma_remaps(h, w, max_px):
    """Edge-weighted chroma: R shifts +px, B shifts -px, ramping as r^2 from
    0 at center to max_px at corners. Two column-shift maps, computed once."""
    cy, cx = h / 2.0, w / 2.0
    r0 = float(np.hypot(cy, cx))
    Y = (np.arange(h, dtype=np.float32)[:, None] - cy)
    X = (np.arange(w, dtype=np.float32)[None, :] - cx)
    r = np.sqrt(X * X + Y * Y)
    rn = np.clip(r / r0, 0, 1)
    shift = (max_px * rn * rn).astype(np.int32)          # quadratic ramp
    col = np.arange(w, dtype=np.int32)[None, :]
    sx_r = np.clip(col + shift, 0, w - 1)
    sx_b = np.clip(col - shift, 0, w - 1)
    return sx_r, sx_b


def scanline_mask(h, period, intensity):
    m = np.ones(h, dtype=np.float32)
    m[::period] = 1.0 - intensity
    return m[:, None, None]


def main():
    p = argparse.ArgumentParser(description="Bodycam/CRT lens stack.")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--k1", type=float, default=0.2,
                   help="fisheye quadratic coefficient (default 0.2; "
                        "0.1 subtle, 0.45 extreme)")
    p.add_argument("--k2", type=float, default=0.1,
                   help="outer-ring coefficient — pushes distortion to the "
                        "rim (default 0.1; 0.2-0.3 bodycam)")
    p.add_argument("--i", type=int, default=1, choices=[0, 1],
                   help="lenscorrection interpolation: 0 nearest, 1 bilinear "
                        "(default 1)")
    p.add_argument("--edge-flip", type=float, default=None, metavar="R",
                   help="mirror-flip ring: beyond R (fraction of half-diagonal, "
                        "e.g. 0.92) the letterboxed image mirrors inward")
    p.add_argument("--edge-chroma", type=float, default=0.0, metavar="PX",
                   help="R/B separation ramping 0 at center to PX at corners "
                        "(e.g. 10)")
    p.add_argument("--vignette", type=float, default=0.0,
                   help="native ffmpeg vignette strength (0 = off)")
    p.add_argument("--scanlines", type=int, default=0,
                   help="scanline row period (0 = off)")
    p.add_argument("--scan-intensity", type=float, default=0.12)
    args = p.parse_args()

    if not os.path.isfile(args.input):
        sys.exit(f"not found: {args.input}")

    w, h, fps_str, fps = probe(args.input)
    print(f"{w}x{h} @ {fps_str} | k1={args.k1} k2={args.k2} "
          f"flip={args.edge_flip} chroma={args.edge_chroma}")

    # geometry for custom passes — computed once
    flip_sy = flip_sx = None
    if args.edge_flip is not None:
        flip_sy, flip_sx = build_flip_remap(h, w, args.edge_flip)
        print(f"  flip ring: beyond {args.edge_flip:.2f} of half-diagonal")
    sx_r = sx_b = None
    if args.edge_chroma > 0:
        sx_r, sx_b = build_chroma_remaps(h, w, args.edge_chroma)
        print(f"  chroma: 0 -> {args.edge_chroma:.0f}px quadratic ramp")
    smask = (scanline_mask(h, args.scanlines, args.scan_intensity)
             if args.scanlines > 0 else None)
    rows = np.arange(h, dtype=np.int32)[:, None]  # for chroma gather

    needs_custom = (flip_sy is not None or sx_r is not None
                    or smask is not None)

    # native filters as an in-line filtergraph on the decoded stream
    vf = [f"lenscorrection=cx=0.5:cy=0.5:k1={args.k1}:k2={args.k2}:i={args.i}"]
    if args.vignette > 0:
        # ffmpeg vignette angle: PI/2 = strongest sane default; weaker = larger
        angle = math.pi / max(2.0, 5.0 - min(3.0, args.vignette) * 2)
        vf.append(f"vignette=angle={angle:.3f}")

    if not needs_custom:
        # pure-native path: one decode, filters, one encode
        r = subprocess.run(
            f'ffmpeg -loglevel error -y -i "{args.input}" '
            f'-vf "{",".join(vf)}" '
            f'-c:v libx264 -crf 18 -pix_fmt yuv420p -an "{args.output}"',
            shell=True, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"native pass failed:\n{r.stderr}")
        print(f"OK -> {args.output}")
        return

    # single sweep: decode input | native filters | rawvideo out -> numpy
    # edge passes -> single encode
    workdir = tempfile.mkdtemp(prefix="lens_stack_")
    err = open(os.path.join(workdir, "enc.log"), "w")
    dec_err = open(os.path.join(workdir, "dec.log"), "w")
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", fps_str,
         "-i", "-", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
         args.output], stdin=subprocess.PIPE, stderr=err)
    dec = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-i", args.input,
         "-vf", ",".join(vf),
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE, stderr=dec_err)
    fb = w * h * 3
    done = 0
    while True:
        buf = dec.stdout.read(fb)
        if len(buf) < fb:
            break
        frame = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3)
        if flip_sy is not None:
            frame = frame[flip_sy, flip_sx]
        if sx_r is not None:
            out = np.empty_like(frame)
            out[:, :, 0] = frame[:, :, 0][rows, sx_r]
            out[:, :, 1] = frame[:, :, 1]
            out[:, :, 2] = frame[:, :, 2][rows, sx_b]
            frame = out
        if smask is not None:
            frame = (frame.astype(np.float32) * smask).astype(np.uint8)
        enc.stdin.write(frame.tobytes())
        done += 1
    dec.stdout.close()
    dec.wait()
    enc.stdin.close()
    enc.wait()
    err.close()
    dec_err.close()
    dec_failed = dec.returncode != 0
    enc_failed = enc.returncode != 0
    if enc_failed or dec_failed:
        which = []
        if enc_failed:
            which.append(f"encode: {open(err.name).read()[:500]}")
        if dec_failed:
            which.append(f"decode: {open(dec_err.name).read()[:500]}")
        for f in (err.name, dec_err.name):
            if os.path.exists(f):
                os.remove(f)
        sys.exit(f"lens_stack failed — {'; '.join(which)}")
    for f in (err.name, dec_err.name):
        if os.path.exists(f):
            os.remove(f)
    try:
        os.rmdir(workdir)
    except OSError:
        pass
    print(f"OK {done} frames -> {args.output}")


if __name__ == "__main__":
    main()
