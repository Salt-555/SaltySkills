#!/usr/bin/env python3
"""Phase 3: VHS Polish — analog artifact overlay on assembled video.

Usage:
    python3 vhs_polisher.py --input assembled.mp4 --output final.mp4 [--seed 42]

Effects per frame:
- Chromatic aberration (R/B channel offset 0-2px)
- Analog noise (-8 to +8 per channel)
- Horizontal jitter (1px micro-shift on ~15% of frames)
- Tracking lines (horizontal brightness bands on ~4% of frames)
- Scanlines (every 4th row darkened to 96%)
- CRT vignette (edge darkening)
"""

import argparse, json, os, random, subprocess
import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--seed", type=int, default=None)
    args = p.parse_args()

    if args.seed is not None:
        np.random.seed(args.seed)
        random.seed(args.seed)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    # Probe
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate",
         "-of", "json", args.input],
        capture_output=True, text=True, check=True)
    info = json.loads(r.stdout)
    vs = [s for s in info["streams"] if s["codec_type"] == "video"][0]
    vw, vh = int(vs["width"]), int(vs["height"])
    fps_s = vs["r_frame_rate"]
    if "/" in fps_s:
        num, _, den = fps_s.partition("/")
        fps = float(num) / float(den)
    else:
        fps = float(fps_s)

    r2 = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         args.input],
        capture_output=True, text=True, check=True)
    duration = float(r2.stdout.strip())
    n_frames = int(duration * fps) + 1
    print(f"Input: {vw}x{vh} @ {fps:.1f}fps, {n_frames} frames ({duration:.2f}s)")

    # Decode
    cmd = ["ffmpeg", "-y", "-i", args.input, "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-r", str(fps), "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    frame_size = vw * vh * 3

    # Encode
    cmd2 = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{vw}x{vh}", "-r", str(fps), "-i", "-",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", args.output]
    stderr_file = open("/tmp/vhs_stderr.log", "w")
    pipe = subprocess.Popen(cmd2, stdin=subprocess.PIPE, stderr=stderr_file)

    # Pre-computed masks (computed once, reused every frame)
    scanline_mask = np.ones(vh, dtype=np.float32)
    scanline_mask[::4] = 0.96
    Y_v = np.linspace(-1, 1, vh)[:, None]
    X_v = np.linspace(-1, 1, vw)[None, :]
    d_v = np.sqrt(X_v**2 + Y_v**2)
    vignette = np.clip(1.0 - d_v * 0.15, 0.3, 1.0).astype(np.float32)

    print("Processing frames...")
    for fi in range(n_frames):
        raw = proc.stdout.read(frame_size)
        if len(raw) < frame_size:
            break

        canvas = np.frombuffer(raw, dtype=np.uint8).reshape(vh, vw, 3).copy()
        if fi % 12 == 0:
            print(f"  Frame {fi}/{n_frames}")

        # 1. Chromatic aberration
        sr, sb = random.randint(-1, 2), random.randint(-2, 1)
        if sr:
            canvas[:, :, 0] = np.roll(canvas[:, :, 0], sr, axis=1)
        if sb:
            canvas[:, :, 2] = np.roll(canvas[:, :, 2], sb, axis=1)

        # 2. Analog noise
        noise = np.random.randint(-8, 9, (vh, vw, 3), dtype=np.int16)
        canvas = np.clip(canvas.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # 3. Horizontal jitter
        if random.random() < 0.15:
            canvas = np.roll(canvas, random.choice([-1, 1]), axis=1)

        # 4. Tracking lines
        if random.random() < 0.04:
            y_b = random.randint(0, vh - 80)
            h_b = random.randint(5, 30)
            band = canvas[y_b:y_b+h_b].astype(np.float32)
            canvas[y_b:y_b+h_b] = np.clip(band + random.uniform(5, 15), 0, 255).astype(np.uint8)

        # 5. Scanlines + 6. Vignette
        canvas = np.clip(canvas * scanline_mask[:, None, None], 0, 255).astype(np.uint8)
        canvas = np.clip(canvas.astype(np.float32) * vignette[:, :, None], 0, 255).astype(np.uint8)

        pipe.stdin.write(canvas.tobytes())

    pipe.stdin.close()
    pipe.wait()
    stderr_file.close()
    size_mb = os.path.getsize(args.output) / 1024 / 1024
    print(f"\nOutput: {args.output} ({size_mb:.1f} MB)")
    print("Phase 3 complete.")


if __name__ == "__main__":
    main()
