#!/usr/bin/env python3
"""
cut_mosh.py — Watch Dogs-style DELIBERATE datamoshing: corruption as
transitions and punctuation, not a full-video melt.

Two independent features, combinable:

1. CUT-TARGETED MELTS (--auto-cuts)
   ffmpeg's scene-change detection finds the shot boundaries in your source.
   The intermediate MPEG-4 encode places I-frames at those scene changes;
   we delete exactly the I-frames AT the cuts, so each shot melts in out of
   the previous shot's pixels. This is the Watch Dogs menu-transition
   mechanic: every cut is a controlled dissolve, and the melt length = frames
   from the cut to the next surviving I-frame. --gop 9999 (default) means
   I-frames exist only at detected cuts, so each melt fills the whole next
   shot (long smears).

2. RHYTHMIC BLOOM BURSTS (--bursts)
   Insert short, bounded P-frame duplication bursts at chosen frames —
   "rhythmic datamoshing" punctuation inside otherwise clean footage.
   --bursts "96:6:18,200:10" = at frame 96, bloom with delta 6 for 18 frames;
   at frame 200, delta 10 for 18 frames (default burst length 4x delta).
   Clean before, clean after, corruption only in the burst window.

Usage:
  # Long smears at every detected scene cut (the default look):
  python cut_mosh.py input.mp4 --auto-cuts --scene 0.3 -f 24 -o out.mp4

  # Melts + a couple of bloom bursts on the beat:
  python cut_mosh.py input.mp4 --auto-cuts --bursts "120:6:24,288:10:30" -o out.mp4

  # Bursts only (no melts) — pure punctuation on a clean plate:
  python cut_mosh.py input.mp4 --bursts "96:8" -o out.mp4

Frame numbers refer to the re-encoded intermediate at --fps (frames are
forced to a constant rate, so source frame N ≈ round(N_src * fps/src_fps)).
"""

import os
import re
import sys
import argparse
import subprocess
import tempfile

MARKER = bytes.fromhex("30306463")  # "00dc" AVI frame marker
IFRAME = bytes.fromhex("0001B0")
PFRAME = bytes.fromhex("0001B6")


def run(cmd, check=True):
    print(f"  ▶ {cmd}")
    r = subprocess.run(cmd, shell=True, capture_output=False)
    if check and r.returncode != 0:
        print(f"  ✗ Command failed with code {r.returncode}", file=sys.stderr)
        sys.exit(1)


def probe_fps(path):
    p = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', path],
        capture_output=True, text=True)
    num, den = p.stdout.strip().split('/')
    return int(num) / max(int(den), 1)


def detect_cuts(input_video, threshold):
    """Return sorted list of cut times (seconds) via ffmpeg scene detection."""
    proc = subprocess.run(
        ['ffmpeg', '-hide_banner', '-i', input_video,
         '-vf', f"select='gt(scene,{threshold})',metadata=print",
         '-an', '-f', 'null', '-'],
        capture_output=True, text=True)
    times = []
    for m in re.finditer(r'pts_time:([0-9.]+)', proc.stderr):
        times.append(float(m.group(1)))
    return sorted(set(times))


def is_video_frame(frame):
    return frame[5:8] == IFRAME or frame[5:8] == PFRAME


def parse_bursts(spec, default_len_factor=4):
    """'96:6:24,200:10' -> [(96, 6, 24), (200, 10, 40)]"""
    bursts = []
    for part in spec.split(','):
        bits = part.strip().split(':')
        f = int(bits[0])
        d = int(bits[1])
        ln = int(bits[2]) if len(bits) > 2 else d * default_len_factor
        bursts.append((f, d, ln))
    return sorted(bursts)


def cut_mosh(input_video, output_video, fps=24, auto_cuts=False,
             scene_threshold=0.3, bursts=None, gop=9999, freeze=12,
             manual_cuts=None):
    workdir = tempfile.mkdtemp(prefix="moshpit_cut_")
    in_avi = os.path.join(workdir, "in.avi")
    out_avi = os.path.join(workdir, "out.avi")

    try:
        cut_frames = list(manual_cuts) if manual_cuts else []
        if not cut_frames and auto_cuts:
            times = detect_cuts(input_video, scene_threshold)
            cut_frames = [round(t * fps) for t in times]
        if cut_frames:
            print(f"Cut(s) at frames {sorted(set(cut_frames))}")
        cut_frames = set(cut_frames)

        print(f"[1/3] Encoding intermediate AVI (GOP={gop}, no B-frames)...")
        run(
            f'ffmpeg -loglevel error -y -i "{input_video}" '
            f'-c:v mpeg4 -vtag xvid -qscale:v 4 -g {gop} -bf 0 -r {fps} '
            f'-sc_threshold 40 -an "{in_avi}"'
        )

        print("[2/3] Byte-level frame surgery...")
        with open(in_avi, "rb") as f:
            data = f.read()
        parts = data.split(MARKER)
        header = parts[0]
        frames = [fr for fr in parts[1:] if is_video_frame(fr)]

        burst_map = {}
        for start, delta, length in (bursts or []):
            burst_map[start] = (delta, length)

        out = bytearray(header)
        n = len(frames)
        removed_iframes = 0
        frozen = 0
        last_p = None

        # If manual/auto cuts were given by index, map each to the ACTUAL
        # I-frame nearest it (fps conversion + encoder scene-I placement can
        # shift indices by a few frames). Match within a ±12-frame window.
        cut_iframes = set()
        if cut_frames:
            iframe_indices = [i for i in range(n) if frames[i][5:8] == IFRAME]
            for cf in cut_frames:
                near = [ii for ii in iframe_indices
                        if abs(ii - cf) <= 12 and ii > 0]
                if near:
                    cut_iframes.add(min(near, key=lambda ii: abs(ii - cf)))
                else:
                    print(f"  ! no I-frame near requested cut frame {cf}")
            print(f"  Removing I-frames at {sorted(cut_iframes)}")

        i = 0
        while i < n:
            frame = frames[i]
            sig = frame[5:8]

            # --- cut-targeted melt: drop the I-frame sitting on a cut ---
            if (auto_cuts or manual_cuts) and sig == IFRAME and i in cut_iframes and i > 0:
                # Watch Dogs seam overlap: freeze the last smeared frame of
                # the outgoing shot by duplicating its final P-frame N times,
                # THEN let the next shot melt in against that frozen base.
                if freeze > 0 and last_p is not None:
                    for _ in range(freeze):
                        out.extend(MARKER + last_p)
                    frozen += freeze
                removed_iframes += 1
                i += 1
                continue  # next shot decodes against previous shot's pixels

            out.extend(MARKER + frame)
            if sig == PFRAME:
                last_p = frame

            # --- rhythmic burst: bloom P-frames for a bounded window ---
            if sig == PFRAME and i in burst_map:
                delta, length = burst_map.pop(i)
                written = 0
                pool = []
                ridx = 0
                j = i + 1
                while written < length and j < n:
                    nf = frames[j]
                    if not is_video_frame(nf):
                        j += 1
                        continue
                    if nf[5:8] == IFRAME:
                        break  # anchor hit — end the burst cleanly
                    if len(pool) < delta:
                        pool.append(nf)
                        out.extend(MARKER + nf)
                    else:
                        out.extend(MARKER + pool[ridx])
                        ridx = (ridx + 1) % delta
                    written += 1
                    j += 1
                i = j
                continue

            i += 1

        if burst_map:
            print(f"  ! bursts never triggered (frames past video end?): {sorted(burst_map)}")
        if removed_iframes:
            print(f"  Removed {removed_iframes} cut I-frame(s) → melts")
        if frozen:
            print(f"  Frozen {frozen} smeared frame(s) at seams (freeze={freeze})")

        with open(out_avi, "wb") as f:
            f.write(out)

        print("[3/3] Re-encoding to MP4...")
        run(
            f'ffmpeg -loglevel error -y -i "{out_avi}" '
            f'-crf 18 -pix_fmt yuv420p -c:v libx264 -c:a aac -b:a 192k -r {fps} '
            f'"{output_video}"'
        )
        print(f"✓ Output: {output_video} ({n} source frames)")

    finally:
        for f in [in_avi, out_avi]:
            if os.path.exists(f):
                os.remove(f)
        os.rmdir(workdir)


def main():
    parser = argparse.ArgumentParser(
        description="Deliberate datamoshing: cut-targeted melts + rhythmic bloom bursts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Melt at every scene cut, long smears + frozen seam holds (default):
  python cut_mosh.py clip.mp4 --auto-cuts --scene 0.3 -o out.mp4

  # Cut melts + bloom bursts at frames 96 and 288:
  python cut_mosh.py clip.mp4 --auto-cuts --bursts "96:6:24,288:10:30" -o out.mp4

  # Bursts only — punctuation on otherwise clean footage:
  python cut_mosh.py clip.mp4 --bursts "96:8" -o out.mp4
        """)
    parser.add_argument("input_video")
    parser.add_argument("-o", "--output", default="cutmoshed.mp4")
    parser.add_argument("--auto-cuts", action="store_true",
                        help="detect scene cuts and remove the I-frame at each "
                             "cut, so every shot melts in from the previous one")
    parser.add_argument("--scene", type=float, default=0.3,
                        help="scene-change detection threshold 0-1 "
                             "(default 0.3; lower = more sensitive)")
    parser.add_argument("--cuts", default=None,
                        help="manual cut frames (comma-separated, at --fps): "
                             "'119,136,148'. Overrides --auto-cuts. Use when "
                             "scene detection can't distinguish cuts from motion.")
    parser.add_argument("--bursts", default=None,
                        help="rhythmic bloom bursts: 'frame:delta[:len],...' "
                             "(len default 4x delta)")
    parser.add_argument("-f", "--fps", type=int, default=24,
                        help="fps for intermediate/output (default 24)")
    parser.add_argument("--gop", type=int, default=9999,
                        help="frames between anchor I-frames. Default 9999 = "
                             "long smears: I-frames only at detected cuts. "
                             "Shorter (e.g. 96) = corruption clears mid-shot.")
    parser.add_argument("--freeze", type=int, default=12,
                        help="Watch Dogs seam overlap: at each cut, duplicate "
                             "the last smeared P-frame N times before the melt, "
                             "so the outgoing shot freezes and the next shot "
                             "smears IN over that frozen base. 0 = off. "
                             "(default 12 = 0.5s hold @ 24fps)")

    args = parser.parse_args()

    if not os.path.isfile(args.input_video):
        print(f"Error: '{args.input_video}' not found.", file=sys.stderr)
        sys.exit(1)

    cuts_arg = [int(x) for x in args.cuts.split(',')] if args.cuts else None

    if not args.auto_cuts and not args.bursts and cuts_arg is None:
        print("Error: nothing to do — pass --auto-cuts, --cuts, and/or --bursts.",
              file=sys.stderr)
        sys.exit(1)

    bursts = parse_bursts(args.bursts) if args.bursts else None
    cut_mosh(args.input_video, args.output, fps=args.fps,
             auto_cuts=args.auto_cuts, scene_threshold=args.scene,
             bursts=bursts, gop=args.gop, freeze=args.freeze,
             manual_cuts=cuts_arg)


if __name__ == "__main__":
    main()
