#!/usr/bin/env python3
"""
_common.py — Shared helpers for moshpit chainable passes.

Every chainable pass (pixelsort, dither, ca_swell, flicker, lens_stack) does
the same thing: decode input via ffmpeg pipe, transform raw RGB frames in
numpy, encode via ffmpeg pipe. This module centralizes:

  - probe(): dimensions + EXACT frame rate as a Fraction string. Never
    int()-truncate fps — 29.97 must stay 30000/1001 or output duration and
    A/V sync drift ~3%.
  - read_frames(): rawvideo decoder generator.
  - open_encoder(): rawvideo H.264 encoder process (stderr to file — never
    PIPE, it deadlocks at 64KB).
"""

import os
import subprocess
from fractions import Fraction


def probe(path):
    """Returns (width, height, fps_str, fps_float). fps_str is exact, e.g.
    '30000/1001' — pass it verbatim to ffmpeg -r flags."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate",
         "-of", "csv=p=0", path], capture_output=True, text=True)
    w, h, fr = r.stdout.strip().split(",")
    num, den = fr.split("/")
    frac = Fraction(int(num), int(den))
    fps_str = str(frac) if frac.denominator != 1 else str(frac.numerator)
    return int(w), int(h), fps_str, float(frac)


def count_frames(path):
    """Frame count without a full decode (falls back to -count_frames)."""
    _, _, _, fps = probe(path)
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames", "-of", "csv=p=0", path],
        capture_output=True, text=True)
    s = r.stdout.strip()
    if s.isdigit():
        return int(s)
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-count_frames", "-show_entries", "stream=nb_read_frames",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    return int(r.stdout.strip())


def read_frames(path, width, height):
    """Yield (H,W,3) uint8 frames from ffmpeg rawvideo decode."""
    cmd = ["ffmpeg", "-loglevel", "error", "-i", path,
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    fb = width * height * 3
    try:
        while True:
            buf = proc.stdout.read(fb)
            if len(buf) < fb:
                break
            yield np_frame(buf, width, height)
    finally:
        proc.stdout.close()
        proc.wait()


def np_frame(buf, width, height):
    import numpy as np
    return np.frombuffer(buf, dtype=np.uint8).reshape(height, width, 3)


def open_encoder(output_path, width, height, fps_str, crf=18):
    """Rawvideo H.264 encoder. Returns Popen; caller writes frame.tobytes().
    stderr goes to a temp file (PIPE deadlocks at 64KB). Caller must
    close stdin, wait(), and should check returncode."""
    import tempfile
    err_path = tempfile.mktemp(prefix="moshpit_enc_", suffix=".log")
    err = open(err_path, "w")
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", fps_str,
         "-i", "-", "-c:v", "libx264", "-crf", str(crf),
         "-pix_fmt", "yuv420p", output_path],
        stdin=subprocess.PIPE, stderr=err)
    proc._moshpit_err = (err, err_path)  # caller: close+remove after wait()
    return proc


def close_encoder(proc):
    """Close and wait; returns (returncode, stderr_text_on_failure)."""
    proc.stdin.close()
    proc.wait()
    err, err_path = proc._moshpit_err
    err.close()
    if proc.returncode != 0:
        text = open(err_path).read()
        os.remove(err_path)
        return proc.returncode, text
    os.remove(err_path)
    return proc.returncode, None
