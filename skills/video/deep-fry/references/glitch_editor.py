#!/usr/bin/env python3
"""Phase 2: Glitch Assembly — config-driven segment stitching from ASCII variants.

Usage:
    python3 glitch_editor.py --config /path/to/edit.yaml

Config format (YAML):
    edit:
      name: "my_edit"
      source_dir: /tmp/ascii_output
      output_dir: /tmp/glitch_output
      slowdown_factor: 1.0          # 1.0 = normal, 4.0 = 0.25x (global fallback)
      segments:
        - source: vidcolors
          start_pct: 0
          end_pct: 10
          slow: 2.5                 # optional per-segment override (replaces slowdown_factor)
        - source: matrix
          start_pct: 10
          end_pct: 16
          slow: 1.0
      allmind:
        enabled: true
        start_pct: 85
        text: ALLMIND
        font_size: 120
        color: "#C5A55A"
        shadow: true

Per-segment slowdown: the `slow` key on a segment overrides `slowdown_factor`.
ffmpeg filter: `setpts={SLOW}*PTS,fps=24` — do NOT add `-vsync cfr` or `-r`
flags, they override setpts and the duration stays unchanged.
"""

import argparse, os, subprocess
try:
    import yaml
except ImportError:
    # Fallback: parse simple YAML manually
    yaml = None


def parse_yaml(path):
    if yaml:
        with open(path) as f:
            return yaml.safe_load(f)
    # Minimal fallback YAML parser for the config format.
    # Handles BOTH segment styles:
    #   semicolon one-liner:  - source: X; start_pct: 0; end_pct: 10
    #   multi-line:           - source: X
    #                           start_pct: 0
    #                           end_pct: 10
    # (the indented sub-keys are tracked onto the current segment).
    # Values are stripped of matching quotes consistently.
    cfg = {"edit": {"segments": [], "allmind": {}}}
    edit = cfg["edit"]
    cur_seg = None
    section = None  # "edit" | "segments" | "allmind"

    def assign_segment(seg, key, val):
        if key == "source":
            seg["source"] = val
        elif key == "start_pct":
            seg["start_pct"] = float(val)
        elif key == "end_pct":
            seg["end_pct"] = float(val)
        elif key == "slow":
            seg["slow"] = float(val)

    with open(path) as f:
        for raw_line in f:
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Segment start: "- source: X" or "-" with sub-keys on later lines
            if stripped.startswith("-"):
                body = stripped[1:].strip()
                seg = {}
                for part in [p.strip() for p in body.split(";")]:
                    if ":" in part:
                        sk, sv = part.split(":", 1)
                        assign_segment(seg, sk.strip(), sv.strip().strip("'\""))
                edit["segments"].append(seg)
                cur_seg = seg
                section = "segments"
                continue

            if ":" not in stripped:
                continue

            k, v = stripped.split(":", 1)
            k, v = k.strip(), v.strip().strip("'\"")

            if k == "segments":
                section = "segments"
            elif k == "allmind":
                section = "allmind"
            elif k == "name":
                edit["name"] = v
                section = "edit"
            elif k == "source_dir":
                edit["source_dir"] = v
                section = "edit"
            elif k == "output_dir":
                edit["output_dir"] = v
                section = "edit"
            elif k == "slowdown_factor":
                edit["slowdown_factor"] = float(v)
                section = "edit"
            elif section == "allmind":
                av = v
                if k == "start_pct":
                    av = float(v)
                elif k == "font_size":
                    av = int(v)
                elif k in ("enabled", "shadow"):
                    av = v.lower() == "true"
                edit["allmind"][k] = av
            elif section == "segments" and cur_seg is not None:
                assign_segment(cur_seg, k, v)
    return cfg


def get_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True, help="YAML config path")
    args = p.parse_args()

    cfg = parse_yaml(args.config)
    edit = cfg["edit"]
    workdir = os.path.join(edit["output_dir"], f".{edit['name']}_work")
    os.makedirs(workdir, exist_ok=True)
    sdir = edit["source_dir"]
    slowdown = edit.get("slowdown_factor", 1.0)
    segments = edit["segments"]

    print(f"\nAssembly: {edit['name']} ({len(segments)} segments, {slowdown}x)")

    seg_files = []
    for i, seg in enumerate(segments):
        src = os.path.join(sdir, f"{seg['source']}.mp4")
        src_dur = get_duration(src)
        seg_start = src_dur * seg["start_pct"] / 100.0
        seg_dur = (src_dur * seg["end_pct"] / 100.0) - seg_start
        seg_slow = seg.get("slow", slowdown)
        adjusted_dur = seg_dur * seg_slow

        out = os.path.join(workdir, f"seg_{i:03d}.mp4")
        print(f"  [{i}] {seg['source']} {seg['start_pct']}%→{seg['end_pct']}% "
              f"({seg_dur:.2f}s → {adjusted_dur:.2f}s)")

        seg_fps = f"setpts={seg_slow}*PTS,fps=24"
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(seg_start), "-i", src, "-t", str(seg_dur),
            "-an",
            "-filter:v", seg_fps,
            "-c:v", "libx264", "-crf", "16", "-preset", "fast",
            "-pix_fmt", "yuv420p", out
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        seg_files.append(out)

    # Concat via filter_complex (more reliable than file concat)
    temp_mp4 = os.path.join(workdir, "temp.mp4")
    inputs = []
    filter_parts = []
    for i, sf in enumerate(seg_files):
        inputs.extend(["-i", sf])
        filter_parts.append(f"[{i}:v]")
    filter_str = "".join(filter_parts) + f"concat=n={len(seg_files)}:v=1:a=0[outv]"

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_str,
        "-map", "[outv]",
        "-c:v", "libx264", "-crf", "16", "-preset", "medium",
        "-pix_fmt", "yuv420p", temp_mp4
    ]
    print(f"  Concatenating {len(seg_files)} segments...")
    subprocess.run(cmd, capture_output=True, check=True)

    # ALLMIND overlay
    allmind_cfg = edit.get("allmind", {})
    if allmind_cfg and allmind_cfg.get("enabled"):
        asm_dur = get_duration(temp_mp4)
        overlay_start = asm_dur * float(allmind_cfg.get("start_pct", 85)) / 100.0
        font_path = allmind_cfg.get("font_path", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        color = allmind_cfg.get("color", "#C5A55A")
        fs = allmind_cfg.get("font_size", 120)
        shadow = allmind_cfg.get("shadow", True)
        text = allmind_cfg.get("text", "ALLMIND")

        f = (f"drawtext=text='{text}':fontcolor={color}"
             f":fontsize={fs}:fontfile='{font_path}'"
             f":x=(w-text_w)/2:y=(h-text_h)/2"
             f":enable='gte(t,{overlay_start:.2f})'")
        if shadow:
            f += ":shadowcolor=black:shadowx=5:shadowy=5"

        out_mp4 = os.path.join(workdir, "labeled.mp4")
        cmd = ["ffmpeg", "-y", "-i", temp_mp4, "-filter:v", f,
               "-c:v", "libx264", "-crf", "14", "-preset", "medium",
               "-pix_fmt", "yuv420p", out_mp4]
        print(f"  ALLMIND overlay at {overlay_start:.2f}s...")
        subprocess.run(cmd, capture_output=True, check=True)
        temp_mp4 = out_mp4

    final = os.path.join(edit["output_dir"], f"{edit['name']}_assembled.mp4")
    subprocess.run(["cp", temp_mp4, final], check=True)
    size_mb = os.path.getsize(final) / 1024 / 1024
    dur = get_duration(final)
    print(f"\n  → {final} ({size_mb:.1f} MB, {dur:.2f}s)")
    print("Phase 2 complete.")


if __name__ == "__main__":
    main()
