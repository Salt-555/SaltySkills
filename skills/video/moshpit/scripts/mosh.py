#!/usr/bin/env python3
"""
mosh.py — Pure FFmpeg I-frame removal and P-frame duplication datamoshing.

Adapted from tiberiuiancu/datamoshing (Unlicense).
Works with system ffmpeg — no ffglitch needed for these two effects.

Modes:
  Default (no -d): Remove all I-frames between start/end frames → melt effect.
  With -d N: Repeat a block of N P-frames cyclically within the range → bloom/trail effect.

Usage:
  python mosh.py input.mp4 -s 40 -e 90 -o output.mp4        # I-frame removal (melt)
  python mosh.py input.mp4 -d 5 -s 165 -o output.mp4         # P-frame duplication (bloom)
"""

import os
import sys
import argparse
import subprocess
import tempfile

def run(cmd, check=True):
    """Run a shell command, show progress."""
    print(f"  ▶ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=False)
    if check and result.returncode != 0:
        print(f"  ✗ Command failed with code {result.returncode}", file=sys.stderr)
        sys.exit(1)

def mosh(input_video, start_frame=0, end_frame=-1, fps=30, delta=0, output_video="moshed.mp4", gop=9999):
    """Core datamoshing pipeline.

    gop: frames between I-frames in the intermediate MPEG-4 encode.
         Default 9999 (single GOP — classic long-GOP datamosh, maximum melt).
         For bloom/trail effects that must NOT collapse into a permanent
         glitch loop, set a smaller gop (e.g. 48) so in-range I-frames act
         as periodic refresh anchors: corruption builds, resets to clean,
         re-builds — persistent moshing instead of terminal corruption.
    """
    workdir = tempfile.mkdtemp(prefix="moshpit_")
    input_avifile = os.path.join(workdir, "input.avi")
    output_avifile = os.path.join(workdir, "output.avi")

    try:
        # Step 1: Convert to MPEG-4 ASP AVI with configurable GOP, no B-frames
        print(f"[1/3] Encoding intermediate AVI (GOP={gop}, no B-frames)...")
        run(
            f'ffmpeg -loglevel error -y -i "{input_video}" '
            f'-c:v mpeg4 -vtag xvid -qscale:v 4 -g {gop} -bf 0 -r {fps} '
            f'-an "{input_avifile}"'
        )

        # Step 2: Read AVI, manipulate frames at byte level
        print(f"[2/3] Manipulating frames (start={start_frame}, end={end_frame}, delta={delta})...")

        with open(input_avifile, "rb") as inf:
            in_bytes = inf.read()

        # 0x30306463 = ASCII "00dc" — MPEG frame boundary marker
        frame_start_marker = bytes.fromhex("30306463")
        frames = in_bytes.split(frame_start_marker)

        out_data = bytearray(frames[0])  # write header
        frames = frames[1:]

        iframe_sig = bytes.fromhex("0001B0")
        pframe_sig = bytes.fromhex("0001B6")

        def is_video_frame(frame):
            return frame[5:8] == iframe_sig or frame[5:8] == pframe_sig

        n_frames = sum(1 for f in frames if is_video_frame(f))
        actual_end = end_frame if end_frame >= 0 else n_frames

        def write_frame(frame):
            out_data.extend(frame_start_marker + frame)

        if delta > 0:
            # P-frame duplication (bloom)
            repeat_frames = []
            repeat_idx = 0
            for i, frame in enumerate(frames):
                if not is_video_frame(frame) or not (start_frame <= i < actual_end):
                    write_frame(frame)
                    continue
                if frame[5:8] == iframe_sig:
                    # I-frame inside range — must keep it as anchor
                    write_frame(frame)
                    repeat_frames.clear()
                    repeat_idx = 0
                    continue
                if len(repeat_frames) < delta:
                    repeat_frames.append(frame)
                    write_frame(frame)
                else:
                    write_frame(repeat_frames[repeat_idx])
                    repeat_idx = (repeat_idx + 1) % delta
        else:
            # I-frame removal (melt)
            for i, frame in enumerate(frames):
                if i < start_frame or i >= actual_end or frame[5:8] != iframe_sig:
                    write_frame(frame)
                # else: skip the I-frame → decoder uses previous reference

        with open(output_avifile, "wb") as outf:
            outf.write(out_data)

        print(f"[3/3] Re-encoding to MP4...")
        run(
            f'ffmpeg -loglevel error -y -i "{output_avifile}" '
            f'-crf 18 -pix_fmt yuv420p -c:v libx264 -c:a aac -b:a 192k -r {fps} '
            f'"{output_video}"'
        )

        print(f"✓ Output: {output_video}")

    finally:
        # Cleanup temp files
        for f in [input_avifile, output_avifile]:
            if os.path.exists(f):
                os.remove(f)
        os.rmdir(workdir)


def main():
    parser = argparse.ArgumentParser(
        description="Datamosh video via I-frame removal or P-frame duplication.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Melt transition between frames 40-90 (I-frame removal):
  python mosh.py clip.mp4 -s 40 -e 90

  # Bloom effect from frame 165 onward, repeating 8 P-frames:
  python mosh.py clip.mp4 -d 8 -s 165

  # Melt entire video (no clean keyframes after first):
  python mosh.py clip.mp4 -s 1
        """
    )
    parser.add_argument("input_video", help="Input video file")
    parser.add_argument("-s", "--start_frame", type=int, default=0,
                        help="Start frame of the mosh (default: 0)")
    parser.add_argument("-e", "--end_frame", type=int, default=-1,
                        help="End frame (-1 = end of video, default: -1)")
    parser.add_argument("-f", "--fps", type=int, default=30,
                        help="FPS for intermediate encode (default: 30)")
    parser.add_argument("-o", "--output", dest="output_video", default="moshed.mp4",
                        help="Output file (default: moshed.mp4)")
    parser.add_argument("-d", "--delta", type=int, default=0,
                        help="P-frame duplication count. 0 = I-frame removal mode.")
    parser.add_argument("--gop", type=int, default=9999,
                        help="Frames between I-frames in intermediate (default: 9999 = "
                             "single long GOP). Smaller (e.g. 48) = periodic refresh "
                             "anchors so bloom doesn't collapse into a permanent loop.")

    args = parser.parse_args()

    if not os.path.isfile(args.input_video):
        print(f"Error: '{args.input_video}' not found.", file=sys.stderr)
        sys.exit(1)

    mosh(
        input_video=args.input_video,
        start_frame=args.start_frame,
        end_frame=args.end_frame,
        fps=args.fps,
        delta=args.delta,
        output_video=args.output_video,
        gop=args.gop,
    )


if __name__ == "__main__":
    main()
