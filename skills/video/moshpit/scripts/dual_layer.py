#!/usr/bin/env python3
"""
dual_layer.py - Dual-layer glitch reveal effect.

Takes two videos (foreground + background) and uses FFglitch corruption
on the foreground to generate a dynamic mask. Where the foreground is
corrupted, it reveals the clean background underneath through jagged blocky holes.
"""

import os
import sys
import argparse
import subprocess
import tempfile
import shutil


def run_cmd(cmd, check=True):
    result = subprocess.run(cmd, shell=True, capture_output=False)
    if check and result.returncode != 0:
        print(f"  x Command failed with code {result.returncode}", file=sys.stderr)
        sys.exit(1)


def run_cmd_list(args_list, check=True):
    """Run command as a list (no shell quoting issues)."""
    print(f"  > {' '.join(args_list[:5])}...")
    result = subprocess.run(args_list, capture_output=False)
    if check and result.returncode != 0:
        print(f"  x Command failed with code {result.returncode}", file=sys.stderr)
        sys.exit(1)


def transcode_for_ffglitch(input_video):
    probe = subprocess.run(
        "ffprobe -v error -select_streams v:0 "
        f'-show_entries stream=codec_name -of csv=p=0 "{input_video}"',
        shell=True, capture_output=True, text=True
    )
    codec = probe.stdout.strip().lower()
    supported = {"mpeg4", "mpeg2video", "mjpeg", "msmpeg4v2", "msmpeg4"}
    if codec in supported:
        print(f"  Codec already supported: {codec}")
        return input_video, None
    workdir = tempfile.mkdtemp(prefix="moshpit_ff_")
    avi_path = os.path.join(workdir, "input.avi")
    print(f"  Transcoding {codec} to MPEG-4 ASP...")
    cmd = (
        f'ffmpeg -loglevel error -y -i "{input_video}" '
        '-c:v mpeg4 -vtag xvid -qscale:v 6 -bf 0 -an '
        f'"{avi_path}"'
    )
    run_cmd(cmd)
    return avi_path, workdir


def cleanup_ffglitch(workdir):
    if workdir and os.path.exists(workdir):
        shutil.rmtree(workdir, ignore_errors=True)


def apply_preset(input_video, preset_name, output_video, presets_dict):
    actual_input, workdir = transcode_for_ffglitch(input_video)
    js_dir = tempfile.mkdtemp(prefix="moshpit_js_")
    js_file = os.path.join(js_dir, "filter.js")
    try:
        with open(js_file, "w") as f:
            f.write(presets_dict[preset_name])
        print(f"  Applying preset {preset_name} via ffedit...")
        cmd = (
            f'ffedit -y -i "{actual_input}" '
            f'-s "{js_file}" '
            f'-o "{output_video}"'
        )
        run_cmd(cmd)
    finally:
        shutil.rmtree(js_dir, ignore_errors=True)
        cleanup_ffglitch(workdir)


def generate_mask(original_avi, glitched_avi, mask_output, threshold=30):
    print(f"  Generating reveal mask (threshold={threshold})...")
    lut_expr = f"if(gt(val,{threshold}),255,0)"
    filter_str = (
        "[0:v][1:v]blend=all_mode=difference,format=gray,"
        "lut=" + "'" + lut_expr + "'",
        "format=yuv420p[mask]"
    )
    # Actually build as one string with proper quoting for -filter_complex
    filter_str = (
        "[0:v][1:v]blend=all_mode=difference,format=gray,"
        f"lut='{lut_expr}',format=yuv420p[mask]"
    )
    run_cmd_list([
        "ffmpeg", "-y",
        "-i", original_avi,
        "-i", glitched_avi,
        "-filter_complex", filter_str,
        "-map", "[mask]",
        mask_output,
    ])


def composite_dual_layer(fg_video, bg_video, mask_video, output_path):
    print("  Compositing dual layers...")
    filter_str = (
        "[1:v][2:v]alphamerge=shortest=1[fg_alpha];"
        "[0:v][fg_alpha]overlay=format=auto:shortest=1"
    )
    run_cmd_list([
        "ffmpeg", "-y",
        "-i", bg_video,
        "-i", fg_video,
        "-i", mask_video,
        "-filter_complex", filter_str,
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
        output_path,
    ])


def dual_layer_reveal(fg_video, bg_video, preset_name, output_path,
                      threshold=30, presets_dict=None):
    if presets_dict is None:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from ffglitch_mosh import PRESETS as presets_dict
    workdir = tempfile.mkdtemp(prefix="moshpit_dual_")
    try:
        glitched_avi = os.path.join(workdir, "glitched.avi")
        apply_preset(fg_video, preset_name, glitched_avi, presets_dict)
        fg_avi = os.path.join(workdir, "fg_original.avi")
        print("  Transcoding foreground for comparison...")
        cmd = (
            f'ffmpeg -loglevel error -y -i "{fg_video}" '
            '-c:v mpeg4 -vtag xvid -qscale:v 6 -bf 0 -an '
            f'"{fg_avi}"'
        )
        run_cmd(cmd)
        mask_video = os.path.join(workdir, "mask.mp4")
        generate_mask(fg_avi, glitched_avi, mask_video, threshold=threshold)
        composite_dual_layer(bg_video, fg_video, mask_video, output_path)
        print(f"  Dual-layer reveal done: {output_path}")
    finally:
        cleanup_ffglitch(workdir)


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ffglitch_mosh import PRESETS
    parser = argparse.ArgumentParser(description="Dual-layer glitch reveal")
    parser.add_argument("foreground", help="Foreground video (gets glitched)")
    parser.add_argument("background", help="Background video (shows through holes)")
    parser.add_argument("--preset", choices=sorted(PRESETS.keys()), default="chaos")
    parser.add_argument("-o", "--output", default="dual_layer_reveal.mp4")
    parser.add_argument("--threshold", type=int, default=30)
    args = parser.parse_args()
    if not os.path.isfile(args.foreground):
        print(f"Error: foreground not found.", file=sys.stderr); sys.exit(1)
    if not os.path.isfile(args.background):
        print(f"Error: background not found.", file=sys.stderr); sys.exit(1)
    if shutil.which("ffedit") is None:
        print("Error: ffedit not found.", file=sys.stderr); sys.exit(1)
    dual_layer_reveal(args.foreground, args.background, args.preset,
                      args.output, threshold=args.threshold, presets_dict=PRESETS)


if __name__ == "__main__":
    main()
