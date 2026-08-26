#!/usr/bin/env python3
"""
ffglitch_mosh.py — FFglitch-based datamoshing via motion vector manipulation.

Requires: ffedit (from ffglitch.org)

FFglitch 0.10 supports: MPEG-4 Part 2, MPEG-2 Video, MJPEG codecs.
H.264/HEVC inputs are transcoded to MPEG-4 ASP automatically.

Built-in presets use the FFglitch 0.10 JS API:
  export function setup(args) { args.features = ["mv"]; }
  export function glitch_frame(frame) { ... modify frame.mv.forward ... }

Usage:
  python ffglitch_mosh.py input.mp4 --preset chaos -o output.avi
  python ffglitch_mosh.py input.mp4 --script my_filter.js -o output.avi
  python ffglitch_mosh.py source.mp4 --extract vectors.json
  python ffglitch_mosh.py target.mp4 --transfer vectors.json -o result.avi

WARNING (--transfer): Applying extracted vectors to a DIFFERENT video (cross-file
transfer) segfaults ffedit 0.10.2 (exit 139, verified). Only self-apply works —
pass the SAME source video to --transfer so vectors are re-applied onto the video
they were extracted from. Cross-file transfer is unsupported; do not use it.
"""

import os
import sys
import argparse
import subprocess
import tempfile
import shutil

PRESETS = {
    "horizontal": """
// Horizontal smear — zero out vertical vectors, amplify horizontal displacement
export function setup(args) { args.features = ["mv"]; }
export function glitch_frame(frame) {
    const fwd = frame.mv?.forward;
    if (!fwd) return;
    frame.mv.overflow = "truncate";
    var pan = 20 + Math.sin(frame.index * 0.1) * 30;
    fwd.forEach(function(mv, y, x) {
        if (!mv) return;
        mv[1] = 0; // zero vertical — forces horizontal smear
        mv[0] += pan; // massive horizontal offset
    });
}
""",

    "vertical": """
// Vertical cascade — zero out horizontal vectors, amplify downward pull
export function setup(args) { args.features = ["mv"]; }
export function glitch_frame(frame) {
    const fwd = frame.mv?.forward;
    if (!fwd) return;
    frame.mv.overflow = "truncate";
    var pan = 20 + Math.sin(frame.index * 0.08) * 30;
    fwd.forEach(function(mv, y, x) {
        if (!mv) return;
        mv[0] = 0; // zero horizontal — forces vertical cascade
        mv[1] += pan; // massive downward offset
    });
}
""",

    "spiral": """
// Spiral distortion — rotate vectors around center with aggressive amplification
export function setup(args) { args.features = ["mv"]; }
export function glitch_frame(frame) {
    const fwd = frame.mv?.forward;
    if (!fwd) return;
    frame.mv.overflow = "truncate";
    var cx = fwd.width / 2, cy = fwd.height / 2;
    var angle = frame.index * 0.3;
    fwd.forEach(function(mv, y, x) {
        if (!mv) return;
        var dx = x - cx, dy = y - cy;
        var dist = Math.sqrt(dx*dx + dy*dy);
        var sinA = Math.sin(angle * dist / fwd.width) * 50;
        mv[0] += -dy * sinA / (dist + 1);
        mv[1] += dx * sinA / (dist + 1);
    });
}
""",

    "zoom": """
// Fake zoom — multiply vectors radially from center by large factor
export function setup(args) { args.features = ["mv"]; }
export function glitch_frame(frame) {
    const fwd = frame.mv?.forward;
    if (!fwd) return;
    frame.mv.overflow = "truncate";
    var cx = fwd.width / 2, cy = fwd.height / 2;
    var strength = 5 + Math.sin(frame.index * 0.1) * 3;
    fwd.forEach(function(mv, y, x) {
        if (!mv) return;
        mv[0] += (x - cx) * strength;
        mv[1] += (y - cy) * strength;
    });
}
""",

    "chaos": """
// Chaos — randomized vector perturbation with high intensity
export function setup(args) { args.features = ["mv"]; }
var seed = 12345;
export function glitch_frame(frame) {
    const fwd = frame.mv?.forward;
    if (!fwd) return;
    frame.mv.overflow = "truncate";
    seed = (frame.index * 7919 + 104729) % 2147483647;
    function rand() {
        seed = (seed * 16807) % 2147483647;
        return (seed / 2147483647) * 2 - 1;
    }
    var intensity = 30 + rand() * 50; // much higher range
    fwd.forEach(function(mv, y, x) {
        if (!mv) return;
        mv[0] += rand() * intensity;
        mv[1] += rand() * intensity;
    });
}
""",

    "pixelate": """
// Pixelate — zero out vectors in large blocks to create macroblock effect
export function setup(args) { args.features = ["mv"]; }
export function glitch_frame(frame) {
    const fwd = frame.mv?.forward;
    if (!fwd) return;
    frame.mv.overflow = "truncate";
    var blockSize = 16 + Math.floor(Math.sin(frame.index * 0.2) * 8); // bigger blocks
    for (var y = 0; y < fwd.height; y += blockSize) {
        for (var x = 0; x < fwd.width; x += blockSize) {
            if ((Math.floor(x / blockSize) + Math.floor(y / blockSize)) % 2 === 0) {
                var sub = fwd.subarray([x, y], [Math.min(x+blockSize, fwd.width), Math.min(y+blockSize, fwd.height)]);
                sub.fill(MV(0, 0));
            }
        }
    }
}
""",

    "rgb_split": """
// RGB channel split simulation via aggressive directional vector bias
export function setup(args) { args.features = ["mv"]; }
export function glitch_frame(frame) {
    const fwd = frame.mv?.forward;
    if (!fwd) return;
    frame.mv.overflow = "truncate";
    var split = 15 + Math.sin(frame.index * 0.15) * 20; // much larger split
    fwd.forEach(function(mv, y, x) {
        if (!mv) return;
        var edgeFactor = Math.abs(x / fwd.width - 0.5) * 2;
        mv[0] += split * edgeFactor;
        mv[1] += Math.sin(frame.index + y * 0.3) * edgeFactor * 10;
    });
}
""",

    "wave": """
// Sine wave distortion — horizontal waves that propagate over time, high amplitude
export function setup(args) { args.features = ["mv"]; }
export function glitch_frame(frame) {
    const fwd = frame.mv?.forward;
    if (!fwd) return;
    frame.mv.overflow = "truncate";
    var freq = 0.15, amp = 30 + Math.sin(frame.index * 0.05) * 20; // much higher amplitude
    fwd.forEach(function(mv, y, x) {
        if (!mv) return;
        mv[1] += Math.sin(x * freq + frame.index * 0.3) * amp;
        mv[0] += Math.cos(y * freq + frame.index * 0.2) * amp * 0.5;
    });
}
""",

    "datamosh_loop": """
// Self-referencing datamosh loop — vectors point back to earlier positions aggressively
export function setup(args) { args.features = ["mv"]; }
export function glitch_frame(frame) {
    const fwd = frame.mv?.forward;
    if (!fwd) return;
    frame.mv.overflow = "truncate";
    var lookback = 30 + Math.floor(Math.sin(frame.index * 0.1) * 20); // much larger lookback
    fwd.forEach(function(mv, y, x) {
        if (!mv) return;
        mv[0] += -lookback * Math.sin(frame.index * 0.2 + y * 0.1);
        mv[1] += -lookback * Math.cos(frame.index * 0.15 + x * 0.1);
    });
}
""",

    "block_glitch": """
// Block glitch — randomly zero out large rectangular regions of vectors
export function setup(args) { args.features = ["mv"]; }
var seed = 31337;
export function glitch_frame(frame) {
    const fwd = frame.mv?.forward;
    if (!fwd) return;
    frame.mv.overflow = "truncate";
    seed = (frame.index * 31337 + 12345) % 2147483647;
    function rand() {
        seed = (seed * 48271) % 2147483647;
        return seed / 2147483647;
    }
    var numBlocks = 5 + Math.floor(rand() * 5); // more blocks
    for (var b = 0; b < numBlocks; b++) {
        var bx = Math.floor(rand() * fwd.width);
        var by = Math.floor(rand() * fwd.height);
        var bw = 32 + Math.floor(rand() * 96); // bigger blocks
        var bh = 32 + Math.floor(rand() * 96);
        var ex = Math.min(bx + bw, fwd.width);
        var ey = Math.min(by + bh, fwd.height);
        var sub = fwd.subarray([bx, by], [ex, ey]);
        sub.fill(MV(0, 0));
    }
}
""",

    "mv_sink": """
// Sink and rise — zero out horizontal motion vectors entirely (from official tutorial)
export function setup(args) { args.features = ["mv"]; }
export function glitch_frame(frame) {
    const fwd = frame.mv?.forward;
    if (!fwd) return;
    frame.mv.overflow = "truncate";
    for (let i = 0; i < fwd.length; i++) {
        const row = fwd[i];
        for (let j = 0; j < row.length; j++) {
            var mv = row[j];
            if (!mv) continue;
            mv[0] = 0; // zero horizontal — vertical artifacts only
        }
    }
}
""",

    "mv_average": """
// Average motion vectors over previous frames (from official tutorial, adapted for ffedit)
let prev_fwd_mvs = [];
let total_sum;
var tail_length = 10;
export function setup(args) { args.features = ["mv"]; }
export function glitch_frame(frame) {
    const fwd_mvs = frame.mv?.forward;
    if (!fwd_mvs) return;
    frame.mv.overflow = "truncate";
    var deep_copy = fwd_mvs.dup();
    prev_fwd_mvs.push(deep_copy);
    if (!total_sum) total_sum = new MV2DArray(fwd_mvs.width, fwd_mvs.height);
    if (prev_fwd_mvs.length > tail_length) {
        total_sum.sub(prev_fwd_mvs[0]);
        prev_fwd_mvs = prev_fwd_mvs.slice(1);
    }
    total_sum.add(deep_copy);
    if (prev_fwd_mvs.length == tail_length) {
        fwd_mvs.assign(total_sum);
        fwd_mvs.div(MV(tail_length, tail_length));
    }
}
""",

    "mv_pan": """
// Pan — add large constant offset to all motion vectors (from official tutorial)
var pan_x = 30; // horizontal offset
var pan_y = 20; // vertical offset
export function setup(args) { args.features = ["mv"]; }
export function glitch_frame(frame) {
    const fwd_mvs = frame.mv?.forward;
    if (!fwd_mvs) return;
    frame.mv.overflow = "truncate";
    var oscillation = Math.sin(frame.index * 0.1) * 20;
    fwd_mvs.add(MV(pan_x + oscillation, pan_y));
}
"""
}


def check_ffglitch():
    if shutil.which("ffedit") is None:
        print("Error: 'ffedit' not found. Install FFglitch from ffglitch.org", file=sys.stderr)
        sys.exit(1)


def run_cmd(cmd, check=True):
    result = subprocess.run(cmd, shell=True, capture_output=False)
    if check and result.returncode != 0:
        print(f"  ✗ Command failed with code {result.returncode}", file=sys.stderr)
        sys.exit(1)


def transcode_for_ffglitch(input_video):
    """Transcode to MPEG-4 ASP (Xvid) that ffedit supports.

    Returns (actual_input_path, workdir_or_None).
    Caller must cleanup with cleanup_ffglitch(workdir).
    """
    probe = subprocess.run(
        f'ffprobe -v error -select_streams v:0 '
        f'-show_entries stream=codec_name -of csv=p=0 "{input_video}"',
        shell=True, capture_output=True, text=True
    )
    codec = probe.stdout.strip().lower()

    supported = {"mpeg4", "mpeg2video", "mjpeg", "msmpeg4v2", "msmpeg4"}
    if codec in supported:
        print(f"  ℹ Codec '{codec}' already supported by ffedit")
        return input_video, None

    workdir = tempfile.mkdtemp(prefix="moshpit_ff_")
    avi_path = os.path.join(workdir, "input.avi")

    print(f"  ℹ Transcoding '{codec}' → MPEG-4 ASP for ffedit...")
    cmd = (
        f'ffmpeg -loglevel error -y -i "{input_video}" '
        f'-c:v mpeg4 -vtag xvid -qscale:v 6 -bf 0 -an '
        f'"{avi_path}"'
    )
    run_cmd(cmd)
    return avi_path, workdir


def cleanup_ffglitch(workdir):
    if workdir and os.path.exists(workdir):
        shutil.rmtree(workdir, ignore_errors=True)


def apply_preset(input_video, preset_name, output_video):
    if preset_name not in PRESETS:
        print(f"Unknown preset '{preset_name}'. Available: {', '.join(sorted(PRESETS.keys()))}", file=sys.stderr)
        sys.exit(1)

    actual_input, workdir = transcode_for_ffglitch(input_video)
    js_dir = tempfile.mkdtemp(prefix="moshpit_js_")
    js_file = os.path.join(js_dir, "filter.js")

    try:
        with open(js_file, "w") as f:
            f.write(PRESETS[preset_name])

        print(f"Applying preset '{preset_name}' via ffedit...")
        cmd = (
            f'ffedit -y -i "{actual_input}" '
            f'-s "{js_file}" '
            f'-o "{output_video}"'
        )
        print(f"  ▶ {cmd}")
        run_cmd(cmd)
        print(f"✓ Output: {output_video}")

    finally:
        shutil.rmtree(js_dir, ignore_errors=True)
        cleanup_ffglitch(workdir)


def apply_script(input_video, script_path, output_video):
    if not os.path.isfile(script_path):
        print(f"Error: Script '{script_path}' not found.", file=sys.stderr)
        sys.exit(1)

    actual_input, workdir = transcode_for_ffglitch(input_video)

    try:
        print(f"Applying custom script '{script_path}' via ffedit...")
        cmd = (
            f'ffedit -y -i "{actual_input}" '
            f'-s "{script_path}" '
            f'-o "{output_video}"'
        )
        print(f"  ▶ {cmd}")
        run_cmd(cmd)
        print(f"✓ Output: {output_video}")

    finally:
        cleanup_ffglitch(workdir)


def extract_vectors(input_video, output_json):
    actual_input, workdir = transcode_for_ffglitch(input_video)

    try:
        print(f"Extracting motion vectors from '{input_video}'...")
        cmd = f'ffedit -y -i "{actual_input}" -f mv -e "{output_json}"'
        run_cmd(cmd)
        print(f"✓ Vectors saved: {output_json}")

    finally:
        cleanup_ffglitch(workdir)


def transfer_vectors(input_video, vectors_file, output_video):
    """Re-apply extracted motion vectors onto a video via ffedit.

    WARNING: ffedit 0.10.2 segfaults (exit 139) when vectors are transferred to a
    DIFFERENT video (cross-file transfer). Only SELF-APPLY works reliably: pass the
    same source video the vectors were extracted from.
    """
    if not os.path.isfile(vectors_file):
        print(f"Error: Vectors file '{vectors_file}' not found.", file=sys.stderr)
        sys.exit(1)

    actual_input, workdir = transcode_for_ffglitch(input_video)

    try:
        print(f"Transferring vectors from '{vectors_file}' to '{input_video}'...")
        cmd = (
            f'ffedit -y -i "{actual_input}" '
            f'-f mv -a "{vectors_file}" '
            f'-o "{output_video}"'
        )
        run_cmd(cmd)
        print(f"✓ Output: {output_video}")

    finally:
        cleanup_ffglitch(workdir)


def convert_to_mp4(src, output_mp4=None):
    if output_mp4 is None:
        base = os.path.splitext(src)[0]
        output_mp4 = base + ".mp4"

    print(f"Converting '{src}' → '{output_mp4}'...")
    cmd = (
        f'ffmpeg -loglevel error -y -i "{src}" '
        f'-c:v libx264 -crf 18 -pix_fmt yuv420p '
        f'-c:a aac "{output_mp4}"'
    )
    run_cmd(cmd)
    print(f"✓ MP4: {output_mp4}")


def main():
    parser = argparse.ArgumentParser(
        description="FFglitch-based datamoshing via motion vector manipulation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Presets: {', '.join(sorted(PRESETS.keys()))}

Examples:
  python ffglitch_mosh.py input.mp4 --preset chaos -o output.avi
  python ffglitch_mosh.py input.mp4 --script my_filter.js -o output.avi
  python ffglitch_mosh.py source.mp4 --extract vectors.json
  python ffglitch_mosh.py target.mp4 --transfer vectors.json -o result.avi
        """
    )
    parser.add_argument("input_video", help="Input video file")
    parser.add_argument("--preset", choices=sorted(PRESETS.keys()), help="Built-in preset")
    parser.add_argument("--script", "-s", help="Custom JS filter (FFglitch 0.10 API)")
    parser.add_argument("-o", "--output", default="ffglitch_output.avi", help="Output file")
    parser.add_argument("--extract", metavar="JSON_FILE", help="Extract motion vectors to JSON")
    parser.add_argument("--transfer", metavar="VECTORS_FILE", help="Transfer vectors onto input")
    parser.add_argument("--mp4", action="store_true", help="Also convert output to MP4")

    args = parser.parse_args()

    if not os.path.isfile(args.input_video):
        print(f"Error: '{args.input_video}' not found.", file=sys.stderr)
        sys.exit(1)

    check_ffglitch()

    if args.extract:
        extract_vectors(args.input_video, args.extract)
    elif args.transfer:
        transfer_vectors(args.input_video, args.transfer, args.output)
        if args.mp4:
            convert_to_mp4(args.output)
    elif args.preset:
        apply_preset(args.input_video, args.preset, args.output)
        if args.mp4:
            convert_to_mp4(args.output)
    elif args.script:
        apply_script(args.input_video, args.script, args.output)
        if args.mp4:
            convert_to_mp4(args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
