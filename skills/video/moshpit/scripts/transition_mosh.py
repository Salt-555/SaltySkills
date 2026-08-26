#!/usr/bin/env python3
"""
transition_mosh.py — Datamosh A into full corruption, then melt into B.

Classic A→B datamosh transition done at the codec byte level:

  1. Encode A as MPEG-4 ASP AVI with a long GOP (single I-frame) so its
     corruption accumulates. Optionally bloom (P-frame duplication) A's
     frames so it builds trailing-square corruption.
  2. Encode B as MPEG-4 ASP AVI with a SHORT GOP so it can resolve clean.
  3. Stitch: take A's frames up to the splice, then append B's frames but
     DROP B's opening I-frame. B's first P-frames now decode against A's
     corrupted reference frame -> B melts in glitched, then clears as its
     own frames/I-frames accumulate.
  4. Re-encode the combined AVI to MP4.

Chain pixelsort_mosh.py --until-frame <splice> to pixelsort only A's half
(the corrupted section), leaving B clean.

Usage:
  python transition_mosh.py A.mp4 B.mp4 -s 175 -d 8 -o transition.mp4
  python transition_mosh.py A.mp4 B.mp4 -s 175 --bloom-start 70 -o t.mp4

Transition tuning:
  -s <frame>    output frame where B begins (default ~2/3 through A)
  -d <n>        P-frame duplication (bloom) on A; --bloom-start sets where it begins
  --a-gop       A's GOP (default 9999 = single long GOP -> corruption accumulates)
  --b-gop       B's GOP. LONGER = slower, more gradual melt into B (the dissolve
                fills B's first GOP). e.g. 96 @ 24fps = 4s melt.

Chain with pixelsort_mosh.py to corrupt A's pixels and let B unsort into view:
  --until-frame <splice>       sort only A's half, keep B clean
  --unsort-start <splice> --unsort-frames N   B arrives heavily sorted and
                               unsorts to clean over N frames
  (--unsort-start must equal -s.)
"""

import os
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


def probe_dims(path):
    p = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=width,height,r_frame_rate',
         '-of', 'csv=p=0', path], capture_output=True, text=True)
    w, h, fr = p.stdout.strip().split(',')
    num, den = fr.split('/')
    return int(w), int(h), int(num) / max(int(den), 1)


def encode_avi(input_video, out_avi, fps, gop, size=None):
    """Encode to MPEG-4 ASP AVI (Xvid), no B-frames, optional scale to size."""
    scale = f'-vf scale={size[0]}:{size[1]}' if size else ''
    run(
        f'ffmpeg -loglevel error -y -i "{input_video}" {scale} '
        f'-c:v mpeg4 -vtag xvid -qscale:v 4 -g {gop} -bf 0 -r {fps} '
        f'-an "{out_avi}"'
    )


def read_frames(avi):
    with open(avi, 'rb') as f:
        data = f.read()
    parts = data.split(MARKER)
    return parts[0], parts[1:]  # header, frames


def is_video_frame(frame):
    # VOP start-code bytes at fixed offset 5. This is muxer-specific — it works
    # with this pipeline's own ffmpeg MPEG-4 ASP muxer (we control the encode),
    # but a differently-muxed AVI would not put the start code at offset 5.
    return frame[5:8] == IFRAME or frame[5:8] == PFRAME


def bloom_frames(frames, delta, start):
    """P-frame duplication (bloom) applied from `start` onward. Returns new list."""
    out = []
    repeat = []
    ridx = 0
    for i, frame in enumerate(frames):
        if not is_video_frame(frame):
            out.append(frame)
            continue
        if frame[5:8] == IFRAME:
            out.append(frame)
            repeat, ridx = [], 0
            continue
        if i < start:
            out.append(frame)
            continue
        if len(repeat) < delta:
            repeat.append(frame)
            out.append(frame)
        else:
            out.append(repeat[ridx])
            ridx = (ridx + 1) % delta
    return out


def transition(A, B, splice, output_video, fps=24, delta=0, bloom_start=0,
               b_gop=24, a_gop=9999):
    """Datamosh A to collapse, melt into B. splice = output frame where B begins."""
    workdir = tempfile.mkdtemp(prefix="moshpit_trans_")
    a_avi = os.path.join(workdir, "a.avi")
    b_avi = os.path.join(workdir, "b.avi")
    out_avi = os.path.join(workdir, "out.avi")

    try:
        aw, ah, afps = probe_dims(A)
        bw, bh, _ = probe_dims(B)
        fps = int(fps) if fps else int(round(afps))
        print(f"A: {aw}x{ah} {fps}fps | B: {bw}x{bh} | splice @ frame {splice}")

        # Encode A (long GOP -> corrupts), B (short GOP -> resolves clean, scaled to A)
        encode_avi(A, a_avi, fps, a_gop)
        encode_avi(B, b_avi, fps, b_gop, size=(aw, ah))

        a_hdr, a_frames = read_frames(a_avi)
        b_hdr, b_frames = read_frames(b_avi)

        # Bloom A's frames (optional) to build trailing corruption before the splice
        if delta > 0:
            print(f"  Blooming A (P-frame duplication x{delta} from frame {bloom_start})...")
            a_frames = bloom_frames(a_frames, delta, bloom_start)

        # A up to splice
        a_out = a_frames[:splice]
        print(f"  A frames included: {len(a_out)}")

        # Append B, dropping the opening I-frame so B melts into A's corrupted state
        dropped = 0
        b_out = []
        started = False
        for frame in b_frames:
            if not is_video_frame(frame):
                continue
            if not started and frame[5:8] == IFRAME:
                dropped += 1
                started = True
                continue  # drop B's first I-frame -> decode against A
            started = True
            b_out.append(frame)
        print(f"  Dropped B's first {dropped} I-frame(s); appended {len(b_out)} B frames")

        # Assemble AVI (header from A, frames from A then B)
        out_data = bytearray(a_hdr)
        for frame in a_out:
            out_data.extend(MARKER + frame)
        for frame in b_out:
            out_data.extend(MARKER + frame)
        with open(out_avi, 'wb') as f:
            f.write(out_data)

        # Re-encode to MP4
        run(
            f'ffmpeg -loglevel error -y -i "{out_avi}" '
            f'-crf 18 -pix_fmt yuv420p -c:v libx264 -c:a aac -b:a 192k -r {fps} '
            f'"{output_video}"'
        )
        print(f"✓ Output: {output_video} (total frames ~{len(a_out) + len(b_out)})")

    finally:
        for f in [a_avi, b_avi, out_avi]:
            if os.path.exists(f):
                os.remove(f)
        os.rmdir(workdir)


def main():
    parser = argparse.ArgumentParser(
        description="Datamosh A into corruption, then melt into B (codec-level transition).")
    parser.add_argument("A", help="First video (gets corrupted)")
    parser.add_argument("B", help="Second video (melts in clean)")
    parser.add_argument("-s", "--splice", type=int, default=0,
                        help="Output frame where B begins (default: 2/3 of A's frames)")
    parser.add_argument("-d", "--delta", type=int, default=8,
                        help="Bloom P-frame duplication on A (0 = none). Trail length.")
    parser.add_argument("--bloom-start", type=int, default=0,
                        help="Frame in A where bloom begins (default 0 = from the start)")
    parser.add_argument("-f", "--fps", type=int, default=0,
                        help="Output fps (0 = use A's)")
    parser.add_argument("--a-gop", type=int, default=9999,
                        help="GOP for A's intermediate (long = max corruption accumulation)")
    parser.add_argument("--b-gop", type=int, default=24,
                        help="GOP for B's intermediate (short = resolves clean fast)")
    parser.add_argument("-o", "--output", default="transition.mp4")
    args = parser.parse_args()

    for p in (args.A, args.B):
        if not os.path.isfile(p):
            print(f"Error: '{p}' not found.", file=sys.stderr)
            sys.exit(1)

    if args.splice <= 0:
        # default to ~2/3 through A
        aw, ah, afps = probe_dims(args.A)
        nb = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=nb_frames', '-of', 'csv=p=0', args.A],
            capture_output=True, text=True).stdout.strip()
        try:
            total = int(nb)
        except ValueError:
            total = int(float(subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'csv=p=0', args.A], capture_output=True, text=True
            ).stdout.strip()) * afps)
        args.splice = max(1, int(total * 2 / 3))

    transition(args.A, args.B, args.splice, args.output, fps=args.fps,
               delta=args.delta, bloom_start=args.bloom_start,
               a_gop=args.a_gop, b_gop=args.b_gop)


if __name__ == "__main__":
    main()
