#!/usr/bin/env python3
"""
es_mosh.py — Elementary-stream datamoshing core. Replaces AVI byte-surgery.

WHY ES: the old pipeline split AVI files on the "00dc" chunk marker, which also
occurs inside AVI stream headers — truncating the header (grey first frame) or
corrupting chunk sizes on rebuild (green/purple desync). Raw MPEG-4 elementary
streams have NO container: bytes are just [header cluster][VOP][VOP]... Surgery
is pure frame-list manipulation and remux is a single ffmpeg read.

Pipeline:
  1. Encode source -> raw MPEG-4 ES (-f m4v), forcing I-VOPs exactly at cuts
     (-force_key_frames + -sc_threshold 0; sc_threshold alone does NOT work —
     ffmpeg's mpeg4 encoder ignores it for scene I-frames).
  2. Parse ES into frame units: each unit is a header cluster (VOS/VO/VOL/GOV,
     re-emitted before every I-VOP) plus its VOP. P-VOPs are single-startcode units.
  3. Surgery on the frame-unit list: drop I units (melt), duplicate trailing P
     (freeze hold), P-frame pooling (bloom burst).
  4. Remux modified ES -> MP4. Validate: frame count + decode error count.

Usage:
  # Melt at exact frames + Watch Dogs frozen seams (frames at --fps):
  python es_mosh.py input.mp4 --cuts 48,172,292 --freeze 12 -o out.mp4

  # Melts + a bloom burst before a weak seam:
  python es_mosh.py input.mp4 --cuts 48,172 --bursts "616:8:24" -o out.mp4

  # Bloom only:
  python es_mosh.py input.mp4 --bursts "96:8" -o out.mp4
"""

import os
import re
import sys
import json
import argparse
import subprocess
import tempfile

SC = re.compile(b"\x00\x00\x01")
VOS, GOV, VOL, UD, VOP = 0xB0, 0xB3, 0xB5, 0xB2, 0xB6


def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r


def probe_frames(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames", "-of", "csv=p=0", path],
        capture_output=True, text=True)
    try:
        return int(r.stdout.strip())
    except ValueError:
        return 0


def encode_es(src, out_es, fps, keyframe_times):
    """Encode to raw MPEG-4 ES with I-VOPs forced at the given times (seconds)."""
    kf = ",".join(f"{t:.6f}" for t in keyframe_times)
    r = run(
        f'ffmpeg -loglevel error -y -i "{src}" '
        f"-c:v mpeg4 -qscale:v 4 -g 9999 -bf 0 -sc_threshold 0 "
        f'-force_key_frames "{kf}" -an -f m4v "{out_es}"'
    )
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        sys.exit(f"ES encode failed: {src}")


def parse_es(data):
    """Return list of frame units: (byte_start, byte_end, kind). kind: 'I'/'P'.

    Each I unit includes its full header cluster (VOS through VOP-I inclusive).
    Each P unit is the single VOP start code through the next start code.
    """
    codes = [(m.start(), data[m.start() + 3]) for m in SC.finditer(data)]
    entries = []
    for i, (pos, code) in enumerate(codes):
        end = codes[i + 1][0] if i + 1 < len(codes) else len(data)
        entries.append((pos, end, code))
    units = []
    i = 0
    n = len(entries)
    while i < n:
        pos, end, code = entries[i]
        if code == VOS:
            # consume headers until this cluster's I-VOP, include it
            j = i
            while j < n and entries[j][2] != VOP:
                j += 1
            if j >= n:
                break
            units.append((entries[i][0], entries[j][1], "I"))
            i = j + 1
        elif code == VOP:
            # P-VOP. ffmpeg re-emits header clusters before every I-VOP, so a
            # headerless VOP here is always a P-frame in this pipeline.
            units.append((pos, end, "P"))
            i += 1
        else:
            i += 1
    return units


def validate(out_mp4, expected_frames=None):
    """Decode check + frame count. Returns (ok, n_frames, n_decode_errors)."""
    r = run(f'ffmpeg -v error -i "{out_mp4}" -f null -')
    errs = len([l for l in r.stderr.split("\n") if l.strip()])
    n = probe_frames(out_mp4)
    ok = errs == 0 and (expected_frames is None or n == expected_frames)
    return ok, n, errs


def es_mosh(src, out_mp4, fps=24, cuts=None, freeze=12, bursts=None,
            force_kf_seconds=None):
    """cuts: frame indices (at fps). bursts: [(frame, delta, len)]."""
    work = tempfile.mkdtemp(prefix="esmosh_")
    es_in = os.path.join(work, "in.m4v")
    es_out = os.path.join(work, "surg.m4v")

    # 1. keyframe times: frame 0 always, plus each cut (I goes ON the cut frame)
    cut_frames = sorted(set(cuts or []))
    kf_seconds = [0.0] + [cf / fps for cf in cut_frames]
    if force_kf_seconds:
        kf_seconds = sorted(set(kf_seconds) | set(force_kf_seconds))
    print(f"[1/4] Encoding ES with forced I-VOPs at frames {[0]+cut_frames}...")
    encode_es(src, es_in, fps, kf_seconds)

    data = open(es_in, "rb").read()
    units = parse_es(data)
    n_src = len(units)
    i_pos = [ui for ui, u in enumerate(units) if u[2] == "I"]
    print(f"      ES frames: {n_src}, I units at {i_pos}")

    # 2. map cuts -> I units (nearest within 3; encoder can shift by 1)
    drop = set()
    for cf in cut_frames:
        near = [ii for ii in i_pos if abs(ii - cf) <= 3 and ii > 0]
        if not near:
            print(f"  ! WARNING: no I unit near requested cut {cf} — seam skipped")
        drop.update(near)

    # 3. surgery
    out = bytearray()
    last_p = None
    frozen = dropped = bloomed_net = 0
    i = 0
    while i < n_src:
        s, e, k = units[i]
        hit = next(((b, d, ln) for b, d, ln in (bursts or [])
                    if b <= i < b + ln), None)
        if hit and k == "P":
            bstart, bdelta, blen = hit
            pool, w, j = [], 0, i
            while w < blen and j < n_src:
                s2, e2, k2 = units[j]
                if k2 == "I":
                    break  # anchor hit — clean burst exit
                if len(pool) < bdelta:
                    pool.append((s2, e2))
                    out += data[s2:e2]
                else:
                    ps, pe = pool[w % bdelta]
                    out += data[ps:pe]
                w += 1
                j += 1
            # the burst REPLACES its source window: net add = emitted - consumed
            bloomed_net += w - (j - i)
            i = j
            continue
        if k == "I" and i in drop:
            if freeze > 0 and last_p is not None:
                s2, e2 = last_p
                out += data[s2:e2] * freeze
                frozen += freeze
            dropped += 1
            i += 1
            continue
        out += data[s:e]
        if k == "P":
            last_p = (s, e)
        i += 1

    print(f"[2/4] Surgery: dropped {dropped} I units, froze {frozen}, "
          f"bloom net {bloomed_net}")
    expected = n_src - dropped + frozen + bloomed_net
    open(es_out, "wb").write(bytes(out))

    # 4. remux + validate
    print("[3/4] Remuxing ES -> MP4...")
    r = run(
        f'ffmpeg -loglevel warning -y -f m4v -i "{es_out}" '
        f'-crf 18 -pix_fmt yuv420p -c:v libx264 -r {fps} -an "{out_mp4}"'
    )
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        sys.exit("remux failed")

    print("[4/4] Validating...")
    ok, n_out, errs = validate(out_mp4, expected)
    print(f"      frames {n_out} (expected {expected}), decode errors {errs}")
    if not ok:
        print("  ! VALIDATION FAILED — output suspect", file=sys.stderr)
        sys.exit(1)
    print(f"OK -> {out_mp4}")


def main():
    p = argparse.ArgumentParser(description="Elementary-stream datamosh core.")
    p.add_argument("src")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--cuts", help="comma-separated frame indices to melt at")
    p.add_argument("--freeze", type=int, default=12,
                   help="frozen-seam frames before each melt (0=off)")
    p.add_argument("--bursts", help="'frame:delta[:len],...' P-frame blooms")
    p.add_argument("-f", "--fps", type=int, default=24)
    args = p.parse_args()

    cuts = [int(x) for x in args.cuts.split(",")] if args.cuts else []
    bursts = []
    if args.bursts:
        for part in args.bursts.split(","):
            b = part.strip().split(":")
            f, d = int(b[0]), int(b[1])
            ln = int(b[2]) if len(b) > 2 else d * 4
            bursts.append((f, d, ln))
    if not cuts and not bursts:
        sys.exit("nothing to do: pass --cuts and/or --bursts")
    es_mosh(args.src, args.output, fps=args.fps, cuts=cuts,
            freeze=args.freeze, bursts=bursts)


if __name__ == "__main__":
    main()
