#!/usr/bin/env python3
"""
salt_transition.py — THE "Salt Transition" (hand-tuned, Salt-verified).

The full Watch Dogs-style deliberate mosh chain, locked after iteration:

  1. cut_mosh    — scene-detected cut melts (long smears) + frozen seam
                   holds (the outgoing shot's last smear freezes for 0.5s,
                   the next shot melts in over that frozen base)
  2. pixelsort   — luma sort (rows, interval, low 50) pass on the mosh
  3. blend       — the UNsorted mosh composited over the sorted one at 50%
                   opacity: streaks read as a translucent ghost texture
  4. dither      — barely-visible static Bayer dither (levels 12, no boil):
                   a locked crosshatch you feel more than see

Usage:
  python salt_transition.py input.mp4 -o salt.mp4
  python salt_transition.py input.mp4 -o salt.mp4 --t 0.5 --dither-levels 12
"""

import os
import sys
import argparse
import subprocess
import tempfile

SKILL_SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    print(f"  ▶ {cmd}")
    r = subprocess.run(cmd, shell=True)
    if r.returncode != 0:
        print(f"  ✗ failed (code {r.returncode})", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="The 'Salt Transition': cut melts + frozen seams + "
                    "50% pixelsort overlay + whisper of static dither.")
    parser.add_argument("input_video")
    parser.add_argument("-o", "--output", default="salt_transition.mp4")
    parser.add_argument("--scene", type=float, default=0.3,
                        help="scene-cut detection threshold (default 0.3; "
                             "lower = more sensitive)")
    parser.add_argument("--freeze", type=int, default=12,
                        help="frozen seam hold frames (default 12 = 0.5s @ 24fps)")
    parser.add_argument("--sort-low", type=int, default=50,
                        help="pixelsort luma low bound (default 50)")
    parser.add_argument("--opacity", type=float, default=0.5,
                        help="sorted-layer opacity in the composite (default 0.5)")
    parser.add_argument("--dither-levels", type=int, default=12,
                        help="dither quantization levels (default 12 = barely "
                             "visible; LOWER = MORE visible)")
    parser.add_argument("--fps", type=int, default=24)
    args = parser.parse_args()

    if not os.path.isfile(args.input_video):
        print(f"Error: '{args.input_video}' not found.", file=sys.stderr)
        sys.exit(1)

    workdir = tempfile.mkdtemp(prefix="moshpit_salt_")
    mosh = os.path.join(workdir, "mosh.mp4")
    sorted_ = os.path.join(workdir, "sorted.mp4")

    try:
        print("[1/4] Cut melts + frozen seam holds...")
        run(f'python "{os.path.join(SKILL_SCRIPTS, "cut_mosh.py")}" '
            f'"{args.input_video}" --auto-cuts --scene {args.scene} '
            f'--freeze {args.freeze} -f {args.fps} -o "{mosh}"')

        print("[2/4] Pixelsort pass...")
        run(f'python "{os.path.join(SKILL_SCRIPTS, "pixelsort_mosh.py")}" '
            f'"{mosh}" -o "{sorted_}" --axis rows --mode interval '
            f'--low {args.sort_low} --high 255')

        print("[3/4] Composite: clean mosh over sorted at "
              f"{args.opacity:.0%}...")
        run(f'ffmpeg -loglevel error -y -i "{mosh}" -i "{sorted_}" '
            f'-filter_complex "blend=all_mode=normal:'
            f'all_opacity={args.opacity}" '
            f'-c:v libx264 -crf 18 -pix_fmt yuv420p -an "{workdir}/blend.mp4"')

        print("[4/4] Static whisper-dither...")
        run(f'python "{os.path.join(SKILL_SCRIPTS, "dither_mosh.py")}" '
            f'"{workdir}/blend.mp4" -o "{args.output}" '
            f'--levels {args.dither_levels} --contrast 1.0 --boil 0')

        print(f"✓ Salt transition: {args.output}")
    finally:
        for f in [mosh, sorted_, os.path.join(workdir, "blend.mp4")]:
            if os.path.exists(f):
                os.remove(f)
        os.rmdir(workdir)


if __name__ == "__main__":
    main()
