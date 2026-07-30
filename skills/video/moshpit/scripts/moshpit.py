#!/usr/bin/env python3
"""
moshpit.py — One-command datamoshing orchestrator.

Takes an input video and produces multiple glitched variations using:
  - Pure FFmpeg I-frame removal (melt)
  - Pure FFmpeg P-frame duplication (bloom)
  - FFglitch motion vector presets (requires ffedit/ffgac)
  - FFmpeg lagfun trails

Usage:
  # Generate all default variants:
  python moshpit.py input.mp4

  # Specific effects only:
  python moshpit.py input.mp4 --effects melt bloom wave

  # Custom output directory:
  python moshpit.py input.mp4 -o ./moshed/

  # With frame range for melt/bloom:
  python moshpit.py input.mp4 --start 30 --end 120

Available effects:
  melt          I-frame removal — classic datamosh transition smear
  bloom         P-frame duplication — hypnotic motion trails/repeats
  lagfun_trail  FFmpeg lagfun filter — persistent ghosting trails
  lagfun_ghost  Heavy lagfun with color shift — spectral ghost effect

  horizontal    FFglitch: zero vertical, massive horizontal pan (requires ffedit)
  vertical      FFglitch: zero horizontal, massive vertical cascade (requires ffedit)
  spiral        FFglitch: aggressive spiral distortion around center (requires ffedit)
  zoom          FFglitch: radial zoom via vectors (requires ffedit)
  chaos         FFglitch: randomized vector perturbation (requires ffedit)
  pixelate      FFglitch: macroblock zeroing effect (requires ffedit)
  rgb_split     FFglitch: RGB channel split simulation (requires ffedit)
  wave          FFglitch: sine wave distortion (requires ffedit)
  datamosh_loop FFglitch: self-referencing loop vectors (requires ffedit)
  block_glitch  FFglitch: random rectangular vector blocks (requires ffedit)
  mv_sink       FFglitch: zero horizontal motion vectors entirely (requires ffedit)
  mv_average    FFglitch: average motion vectors over previous frames (requires ffedit)
  mv_pan        FFglitch: constant offset pan with oscillation (requires ffedit)

  dual_reveal   Dual-layer reveal — foreground corrupts to expose clean background
                Requires --background video and --preset flags.

  all           Generate every effect above
"""

import os
import sys
import argparse
import subprocess
import tempfile
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.absolute()

# Import the sub-scripts as modules for programmatic use
sys.path.insert(0, str(SCRIPT_DIR))


def has_ffglitch():
    """Check if ffedit is available."""
    return shutil.which("ffedit") is not None


def run(cmd, description=""):
    """Run shell command with progress indicator."""
    if description:
        print(f"  ▶ {description}")
    else:
        print(f"  ▶ {cmd[:120]}...")
    result = subprocess.run(
        cmd, shell=True, capture_output=False
    )
    return result.returncode == 0


def get_video_info(video_path):
    """Get video duration in frames and FPS using ffprobe."""
    cmd = (
        f'ffprobe -v error -select_streams v:0 '
        f'-show_entries stream=width,height,r_frame_rate,nb_frames,avg_frame_rate '
        f'-of json "{video_path}"'
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        return {"fps": 30, "frames": -1, "width": 1920, "height": 1080}

    import json
    data = json.loads(result.stdout)
    stream = data.get("streams", [{}])[0]

    # Parse frame rate
    fps_str = stream.get("avg_frame_rate", "30/1")
    if "/" in fps_str:
        num, den = fps_str.split("/")
        fps = int(num) / max(int(den), 1)
    else:
        fps = float(fps_str)

    frames = int(stream.get("nb_frames", 0))
    width = int(stream.get("width", 1920))
    height = int(stream.get("height", 1080))

    # If nb_frames is 0, estimate from duration
    if frames == 0:
        dur_cmd = (
            f'ffprobe -v error -show_entries format=duration '
            f'-of csv=p=0 "{video_path}"'
        )
        dur_result = subprocess.run(dur_cmd, shell=True, capture_output=True, text=True)
        if dur_result.returncode == 0:
            duration = float(dur_result.stdout.strip())
            frames = int(duration * fps)

    return {"fps": round(fps), "frames": frames, "width": width, "height": height}


def effect_melt(input_video, output_path, start=0, end=-1, fps=30):
    """I-frame removal — classic datamosh melt."""
    from mosh import mosh as do_mosh
    print(f"\n{'='*60}")
    print(f"  MELT — I-frame removal (frames {start}→{end})")
    print(f"{'='*60}")
    do_mosh(input_video, start_frame=start, end_frame=end, fps=fps, delta=0, output_video=str(output_path))


def effect_bloom(input_video, output_path, start=30, end=-1, fps=30, delta=8):
    """P-frame duplication — bloom/trail effect."""
    from mosh import mosh as do_mosh
    print(f"\n{'='*60}")
    print(f"  BLOOM — P-frame duplication x{delta} (frames {start}→{end})")
    print(f"{'='*60}")
    do_mosh(input_video, start_frame=start, end_frame=end, fps=fps, delta=delta, output_video=str(output_path))


def effect_lagfun_trail(input_video, output_path):
    """FFmpeg — persistent motion trails via frame blending.

    Blends each frame with a delayed grayscale version of itself
    to create ghosting trails behind movement.
    """
    print(f"\n{'='*60}")
    print(f"  LAGFUN TRAIL — persistent ghosting behind movement")
    print(f"{'='*60}")

    # Split → grayscale trail with reduced brightness → overlay on original
    cmd = (
        f'ffmpeg -y -i "{input_video}" '
        f'-vf "split[main][trail];'
        f'[trail]format=gray,lut=val*0.5,format=yuv420p[ghost];'
        f'[main][ghost]overlay=format=auto" '
        f'-c:v libx264 -crf 18 "{output_path}"'
    )

    run(cmd, "Applying trail effect...")
    print(f"✓ Output: {output_path}")


def effect_lagfun_ghost(input_video, output_path):
    """FFmpeg — RGB channel separation with time offsets.

    Splits the video into R/G/B channels, applies different time offsets
    to each, then recombines for a chromatic aberration ghost effect.
    """
    print(f"\n{'='*60}")
    print(f"  LAGFUN GHOST — spectral ghost with color separation")
    print(f"{'='*60}")

    # RGB split: extract each channel, offset in time, recombine via mergeplanes
    cmd = (
        f'ffmpeg -y -i "{input_video}" '
        f'-vf "split[r][g][b];'
        f'[r]colorchannelmixer=1*0+0*1+0*2:0*0+0*1+0*2:0*0+0*1+0*2,'
        f'trim=start=0.1,setpts=PTS-STARTPTS[r_ch];'
        f'[g]colorchannelmixer=0*0+1*1+0*2:0*0+0*1+0*2:0*0+0*1+0*2,'
        f'trim=start=0.05,setpts=PTS-STARTPTS[g_ch];'
        f'[b]colorchannelmixer=0*0+0*1+0*2:0*0+0*1+0*2:0*0+0*1+0*2[b_ch];'
        f'[r_ch][g_ch][b_ch]mergeplanes='
        f'0*0+3*1+6*2,1*0+4*1+7*2,2*0+5*1+8*2:format=yuv420p" '
        f'-c:v libx264 -crf 18 "{output_path}"'
    )

    run(cmd, "Applying ghost effect...")
    print(f"✓ Output: {output_path}")


def effect_ffglitch(input_video, output_path, preset_name):
    """Apply an FFglitch motion vector preset.

    ffedit only supports MPEG-4 Part 2 / MPEG-2 / MJPEG codecs.
    H.264 inputs are auto-transcoded to MPEG-4 ASP first.
    """
    if not has_ffglitch():
        print(f"\n  ⚠ Skipping '{preset_name}' — ffedit not found. Install from ffglitch.org")
        return False

    sys.path.insert(0, str(SCRIPT_DIR))
    from ffglitch_mosh import apply_preset, convert_to_mp4

    print(f"\n{'='*60}")
    print(f"  {preset_name.upper()} — FFglitch motion vector manipulation")
    print(f"{'='*60}")

    # ffedit preserves input file extension (MPEG-4 ASP → .avi)
    intermediate = str(output_path).replace(".mp4", ".avi")
    apply_preset(input_video, preset_name, intermediate)

    # Convert to MP4
    convert_to_mp4(intermediate, str(output_path))

    # Remove the intermediate if mp4 succeeded
    if os.path.exists(str(output_path)):
        if os.path.exists(intermediate):
            os.remove(intermediate)
        print(f"✓ Output: {output_path}")
        return True
    return True


def effect_dual_reveal(fg_video, bg_video, output_path, preset_name="chaos", threshold=30):
    """Dual-layer glitch reveal.

    Glitches the foreground via ffedit, generates a per-pixel difference mask
    between original and glitched frames, then composites: where the mask shows
    corruption (white), the clean background video shows through; where intact
    (black), the original foreground remains.

    The result is jagged blocky holes in the foreground revealing the background.
    """
    if not has_ffglitch():
        print(f"\n  ⚠ Skipping 'dual_reveal' — ffedit not found.")
        return False

    sys.path.insert(0, str(SCRIPT_DIR))
    from dual_layer import dual_layer_reveal
    from ffglitch_mosh import PRESETS

    print(f"\n{'='*60}")
    print(f"  DUAL REVEAL — foreground corrupts to expose background")
    print(f"  Preset: {preset_name} | Threshold: {threshold}")
    print(f"{'='*60}")

    dual_layer_reveal(
        fg_video, bg_video, preset_name, str(output_path),
        threshold=threshold, presets_dict=PRESETS
    )
    return True


def batch_generate(input_video, output_dir, effects=None, start=0, end=-1,
                   background=None, preset="chaos", threshold=30):
    """Generate multiple glitched variants."""
    info = get_video_info(input_video)
    fps = info["fps"]
    total_frames = info["frames"]

    print(f"\n{'#'*60}")
    print(f"  MOSHPIT — Datamoshing Pipeline")
    print(f"{'#'*60}")
    print(f"  Input: {input_video}")
    if background:
        print(f"  Background: {background}")
    print(f"  Resolution: {info['width']}x{info['height']}")
    print(f"  FPS: {fps} | Frames: {total_frames}")
    print(f"  Output dir: {output_dir}")

    if effects is None or "all" in effects:
        effects = [
            "melt", "bloom", "lagfun_trail", "lagfun_ghost",
            "horizontal", "vertical", "spiral", "zoom",
            "chaos", "pixelate", "rgb_split", "wave",
            "datamosh_loop", "block_glitch",
            "mv_sink", "mv_average", "mv_pan"
        ]

    # Adjust frame ranges if not specified
    if total_frames > 0:
        if start == 0 and end == -1:
            # Default melt starts a bit in to avoid the first I-frame
            start = max(1, int(total_frames * 0.05))
            bloom_start = max(10, int(total_frames * 0.3))

    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = Path(input_video).stem

    success_count = 0
    skip_count = 0

    for effect in effects:
        out_file = output_dir / f"{base_name}_{effect}.mp4"

        try:
            if effect == "dual_reveal":
                if not background:
                    print(f"\n  ⚠ Skipping 'dual_reveal' — no --background video provided.")
                    skip_count += 1
                    continue
                if effect_dual_reveal(input_video, background, out_file,
                                     preset_name=preset, threshold=threshold):
                    success_count += 1
            elif effect == "melt":
                effect_melt(input_video, out_file, start=start, end=end, fps=fps)
                success_count += 1
            elif effect == "bloom":
                bloom_start = max(10, int(total_frames * 0.3)) if total_frames > 0 else 30
                effect_bloom(input_video, out_file, start=bloom_start, end=end, fps=fps, delta=8)
                success_count += 1
            elif effect == "lagfun_trail":
                effect_lagfun_trail(input_video, out_file)
                success_count += 1
            elif effect == "lagfun_ghost":
                effect_lagfun_ghost(input_video, out_file)
                success_count += 1
            else:
                # FFglitch presets — effect_ffglitch handles transcoding internally
                if effect_ffglitch(input_video, out_file, effect):
                    success_count += 1
        except Exception as e:
            print(f"  ✗ Effect '{effect}' failed: {e}")
            skip_count += 1

    print(f"\n{'#'*60}")
    print(f"  Done! Generated {success_count} variants, skipped {skip_count}")
    print(f"  Output directory: {output_dir}/")
    if success_count > 0:
        for f in sorted(output_dir.glob("*.mp4")):
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"    📁 {f.name} ({size_mb:.1f} MB)")
    print(f"{'#'*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Moshpit — one-command datamoshing pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all variants:
  python moshpit.py input.mp4

  # Just melt and bloom:
  python moshpit.py input.mp4 --effects melt bloom

  # Custom output folder + specific frame range for melt/bloom:
  python moshpit.py input.mp4 -o ./glitched/ --start 20 --end 80

  # FFglitch effects only (requires ffedit):
  python moshpit.py input.mp4 --effects chaos wave spiral zoom

  # Dual-layer reveal — foreground corrupts to expose background:
  python moshpit.py foreground.mp4 --background dark_version.mp4 --effects dual_reveal --preset chaos
        """
    )
    parser.add_argument("input_video", help="Input video file")
    parser.add_argument("-o", "--output_dir", default="./moshpit_output",
                        help="Output directory (default: ./moshpit_output)")
    parser.add_argument("--effects", nargs="+", default=None,
                        help="Effects to generate. Default = all. Use 'all' explicitly.")
    parser.add_argument("--start", type=int, default=0,
                        help="Start frame for melt/bloom effects (default: auto)")
    parser.add_argument("--end", type=int, default=-1,
                        help="End frame (-1 = end of video)")
    parser.add_argument("--background", "-b", default=None,
                        help="Background video for dual_reveal effect")
    parser.add_argument("--preset", default="chaos",
                        help="FFglitch preset for dual_reveal (default: chaos)")
    parser.add_argument("--threshold", type=int, default=30,
                        help="Pixel difference threshold for dual_reveal mask (0-255)")

    args = parser.parse_args()

    if not os.path.isfile(args.input_video):
        print(f"Error: '{args.input_video}' not found.", file=sys.stderr)
        sys.exit(1)

    batch_generate(
        input_video=args.input_video,
        output_dir=Path(args.output_dir),
        effects=args.effects,
        start=args.start,
        end=args.end,
        background=args.background,
        preset=args.preset,
        threshold=args.threshold,
    )


if __name__ == "__main__":
    main()
