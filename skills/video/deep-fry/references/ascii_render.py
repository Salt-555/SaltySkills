#!/usr/bin/env python3
"""Phase 1: ASCII Rendering — source video → 4 variant MP4s.

Usage:
    python3 ascii_render.py --input video.mp4 --output /tmp/out/ [--variants all|vidcolors,bw,matrix,rainbow]

Variants:
    vidcolors — source pixel colors mapped to ASCII chars (base layer)
    bw        — clean monochrome grayscale
    matrix    — green phosphor + katakana/runes + CRT barrel + scanlines + glitch bands
    rainbow   — HSV spectrum cycling + saturation boost + film grain
"""

import argparse, json, math, os, random, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

CHARS = " .`'-:;!><=+*^~?/|(){}[]#&$@%"
PAL_MATRIX = " .·~=≈∞⚡☿✦◊♦▲▼●■░▒▓█ᛠᛒᛗᛞᛏ"


def find_font(preferred=None):
    candidates = preferred or [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("No monospace font found.")


def probe_video(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
        capture_output=True, text=True)
    info = json.loads(r.stdout)
    vs = [s for s in info["streams"] if s["codec_type"] == "video"][0]
    return {
        "width": vs["width"], "height": vs["height"],
        "duration": float(info["format"]["duration"]),
        "has_audio": any(s["codec_type"] == "audio" for s in info["streams"]),
    }


def decode_frames(path, fps, n_frames):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path],
        capture_output=True, text=True)
    info = json.loads(r.stdout)
    vs = [s for s in info["streams"] if s["codec_type"] == "video"][0]
    sw, sh = int(vs["width"]), int(vs["height"])
    cmd = ["ffmpeg", "-y", "-i", path, "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{sw}x{sh}", "-r", str(fps), "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    frame_size = sw * sh * 3
    frames = []
    for _ in range(n_frames):
        raw = proc.stdout.read(frame_size)
        if len(raw) < frame_size:
            break
        frames.append(np.frombuffer(raw, dtype=np.uint8).reshape(sh, sw, 3).copy())
    proc.wait()
    return frames, sw, sh


def build_bitmaps(font, font_size, all_chars):
    font_obj = ImageFont.truetype(font, font_size)
    ascent, descent = font_obj.getmetrics()
    cw = font_obj.getbbox("M")[2] - font_obj.getbbox("M")[0]
    ch = ascent + descent
    bmp = {}
    for c in all_chars:
        if c == " ":
            continue
        img = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(img).text((0, 0), c, fill=255, font=font_obj)
        bmp[c] = np.array(img, dtype=np.float32) / 255.0
    return bmp, cw, ch


def letterbox_frame(frame, vw, vh, sw, sh):
    """Resize source to output resolution with letterbox/pillarbox padding."""
    src_aspect = sw / sh
    out_aspect = vw / vh
    if src_aspect > out_aspect:
        new_w, new_h = vw, int(vw / src_aspect)
        pad_y = (vh - new_h) // 2
        resized = np.array(Image.fromarray(frame).resize((new_w, new_h), Image.LANCZOS))
        padded = np.zeros((vh, vw, 3), dtype=np.uint8)
        padded[pad_y:pad_y+new_h, :, :] = resized
    else:
        new_h, new_w = vh, int(vh * src_aspect)
        pad_x = (vw - new_w) // 2
        resized = np.array(Image.fromarray(frame).resize((new_w, new_h), Image.LANCZOS))
        padded = np.zeros((vh, vw, 3), dtype=np.uint8)
        padded[:, pad_x:pad_x+new_w, :] = resized
    return padded


def compute_lum(padded, cols, rows):
    """Compute luminance from letterboxed frame, resize to grid dimensions."""
    lum_full = (0.299 * padded[:,:,0].astype(np.float32) +
                0.587 * padded[:,:,1].astype(np.float32) +
                0.114 * padded[:,:,2].astype(np.float32)) / 255.0
    return np.array(Image.fromarray((lum_full * 255).astype(np.uint8)).resize(
        (cols, rows), Image.LANCZOS)).astype(np.float32) / 255.0


def frame_to_ascii(idx_arr, mask, colors, bmp, palette, rows, cols, ox, oy, cw, ch, vh, vw):
    """Render a single frame from character index array + colors. Batch-scatter by char index."""
    canvas = np.zeros((vh, vw, 3), dtype=np.uint8)
    row_pos, col_pos = np.where(mask)
    if len(row_pos) == 0:
        return canvas

    char_vals = idx_arr[row_pos, col_pos]
    cr = colors[row_pos, col_pos, 0]
    cg = colors[row_pos, col_pos, 1]
    cb = colors[row_pos, col_pos, 2]

    for ci in np.unique(char_vals):
        c = palette[int(ci)]
        if c == " " or c not in bmp:
            continue
        char_bm = bmp[c]
        pm = (char_vals == ci)
        rp, cp = row_pos[pm], col_pos[pm]
        if len(rp) == 0:
            continue
        pys = oy + rp * ch
        pxs = ox + cp * cw
        ccr, ccg, ccb = cr[pm], cg[pm], cb[pm]

        # Process in chunks to avoid memory blowup
        chunk_size = 2000
        for chunk_start in range(0, len(rp), chunk_size):
            chunk_end = min(chunk_start + chunk_size, len(rp))
            cpys = pys[chunk_start:chunk_end]
            cpxs = pxs[chunk_start:chunk_end]
            ccr_c = ccr[chunk_start:chunk_end]
            ccg_c = ccg[chunk_start:chunk_end]
            ccb_c = ccb[chunk_start:chunk_end]
            for by in range(ch):
                for bx in range(cw):
                    w = float(char_bm[by, bx])
                    if w < 0.01:
                        continue
                    py = (cpys + by).astype(np.int32)
                    px = (cpxs + bx).astype(np.int32)
                    valid = (py >= 0) & (py < vh) & (px >= 0) & (px < vw)
                    if not valid.any():
                        continue
                    vpy, vpx = py[valid], px[valid]
                    canvas[vpy, vpx, 0] = np.maximum(
                        canvas[vpy, vpx, 0],
                        (ccr_c[valid].astype(np.float32) * w).astype(np.uint8))
                    canvas[vpy, vpx, 1] = np.maximum(
                        canvas[vpy, vpx, 1],
                        (ccg_c[valid].astype(np.float32) * w).astype(np.uint8))
                    canvas[vpy, vpx, 2] = np.maximum(
                        canvas[vpy, vpx, 2],
                        (ccb_c[valid].astype(np.float32) * w).astype(np.uint8))
    return canvas


def tonemap(canvas, gamma=0.72):
    """Adaptive percentile tone-mapping for dark ASCII on black."""
    f = canvas.astype(np.float32)
    sub = f[::4, ::4]
    lo, hi = np.percentile(sub, 1), np.percentile(sub, 99.5)
    if hi - lo < 10:
        hi = max(hi, lo + 10)
    f = np.clip((f - lo) / (hi - lo), 0.0, 1.0)
    np.power(f, gamma, out=f)
    return np.clip(f * 255, 0, 255).astype(np.uint8)


def render_variant(variant, out_path, frames, font_path, font_size, vw, vh, fps, pal):
    """Render a single variant (e.g. 'matrix') to MP4."""
    sw, sh = frames[0].shape[1], frames[0].shape[0]
    bmp, cw, ch = build_bitmaps(font_path, font_size, pal)
    cols, rows = vw // cw, vh // ch
    ox, oy = (vw - cols * cw) // 2, (vh - rows * ch) // 2
    n_pal = len(pal)

    stderr = open(f"/tmp/ascii_{variant}_stderr.log", "w")
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{vw}x{vh}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", "16",
           "-pix_fmt", "yuv420p", out_path]
    pipe = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=stderr)

    for fi, frame in enumerate(frames):
        if fi % 10 == 0:
            print(f"    Frame {fi}/{len(frames)}")

        padded = letterbox_frame(frame, vw, vh, sw, sh)
        lum = compute_lum(padded, cols, rows)
        lum_max = max(lum.max(), 1e-3)
        idx_arr = np.clip((lum / lum_max * (n_pal - 1)).astype(np.int32), 0, n_pal - 1)
        mask = (lum > 0.02)

        # ─── Color generation per variant ───
        if variant == "bw":
            intensity = (40 + 215 * (lum / lum_max)).astype(np.uint8)
            colors = np.stack([intensity] * 3, axis=-1)

        elif variant == "rainbow":
            t = fi / fps
            cf = np.arange(cols, dtype=np.float32)[None, :] / cols
            rf = np.arange(rows, dtype=np.float32)[:, None] / rows
            hue = (cf + rf * 0.5 + t * 0.15) % 1.0
            sat = np.full((rows, cols), 0.85, dtype=np.float32)
            val = 0.7 + 0.3 * (lum / lum_max)
            c = val * sat
            x = c * (1.0 - np.abs((hue * 6.0) % 2 - 1.0))
            m = val - c
            h6 = (hue * 6).astype(int) % 6
            r, g, b = np.zeros_like(hue), np.zeros_like(hue), np.zeros_like(hue)
            for i, mh in enumerate([h6 == j for j in range(6)]):
                rc, gc, bc = [(c,x,0),(x,c,0),(0,c,x),(0,x,c),(x,0,c),(c,0,x)][i]
                r[mh] = rc if isinstance(rc, (int, float)) else rc[mh]
                g[mh] = gc if isinstance(gc, (int, float)) else gc[mh]
                b[mh] = bc if isinstance(bc, (int, float)) else bc[mh]
            colors = np.stack([np.clip((r+m)*255,0,255).astype(np.uint8),
                               np.clip((g+m)*255,0,255).astype(np.uint8),
                               np.clip((b+m)*255,0,255).astype(np.uint8)], axis=-1)

        elif variant == "matrix":
            br = lum / lum_max
            colors = np.stack([(br*15).astype(np.uint8),
                               (50 + br*205).astype(np.uint8),
                               (br*45).astype(np.uint8)], axis=-1)

        elif variant == "vidcolors":
            boost = np.clip(lum * 1.5 + 0.3, 0.3, 1.0)
            resized = np.array(Image.fromarray(padded).resize((cols, rows), Image.LANCZOS))
            colors = np.clip(resized.astype(np.float32) * np.stack([boost]*3, axis=-1), 0, 255).astype(np.uint8)
        else:
            continue

        canvas = frame_to_ascii(idx_arr, mask, colors, bmp, pal, rows, cols, ox, oy, cw, ch, vh, vw)
        canvas = tonemap(canvas)

        # ─── Matrix-specific post-processing ───
        if variant == "matrix":
            # CRT barrel distortion
            cy_c, cx_c, str_c = vh/2, vw/2, 0.03
            Y_c = np.arange(vh, dtype=np.float32)[:, None]
            X_c = np.arange(vw, dtype=np.float32)[None, :]
            r2_c = ((X_c - cx_c) / cx_c)**2 + ((Y_c - cy_c) / cy_c)**2
            fac = 1 + str_c * r2_c
            sx_c = np.clip((X_c - cx_c) / cx_c * fac * cx_c + cx_c, 0, vw - 1).astype(np.int32)
            sy_c = np.clip((Y_c - cy_c) / cy_c * fac * cy_c + cy_c, 0, vh - 1).astype(np.int32)
            canvas = canvas[sy_c, sx_c]
            # Scanlines
            sl = np.ones(vh, dtype=np.float32)
            sl[::2] = 0.82
            canvas = np.clip(canvas * sl[:, None, None], 0, 255).astype(np.uint8)
            # Vignette
            Y_v = np.linspace(-1, 1, vh)[:, None]
            X_v = np.linspace(-1, 1, vw)[None, :]
            vig = np.clip(1.0 - np.sqrt(X_v**2 + Y_v**2) * 0.2, 0.2, 1.0).astype(np.float32)
            canvas = np.clip(canvas.astype(np.float32) * vig[:, :, None], 0, 255).astype(np.uint8)
            # Glitch bands every ~20 frames
            if fi % 20 < 2:
                for _ in range(random.randint(2, 4)):
                    y_b = random.randint(10, vh - 60)
                    h_b = random.randint(3, 15)
                    shift = random.randint(-25, 25)
                    if shift != 0:
                        canvas[y_b:y_b+h_b] = np.roll(canvas[y_b:y_b+h_b], shift, axis=1)

        pipe.stdin.write(canvas.tobytes())

    pipe.stdin.close()
    pipe.wait()
    stderr.close()
    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"  → {os.path.basename(out_path)} ({size_mb:.1f} MB)")
    return out_path


def mux_audio(input_path, audio_path, output_path):
    """Add extracted audio track to video."""
    final = output_path.replace(".mp4", "_final.mp4")
    subprocess.run(["ffmpeg", "-y", "-i", input_path, "-i", audio_path,
                     "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", final],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(final):
        os.replace(final, output_path)
    return output_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Source video path")
    p.add_argument("--output", default="/tmp/ascii_output/", help="Output directory")
    p.add_argument("--font", default=None, help="Monospace font path")
    p.add_argument("--fps", type=int, default=24, help="Target FPS")
    p.add_argument("--vres", type=int, default=1920, help="Vertical resolution")
    p.add_argument("--hres", type=int, default=1080, help="Horizontal resolution")
    p.add_argument("--variants", default="all", help="Comma-separated or 'all'")
    p.add_argument("--font-size", type=int, default=14, help="ASCII font size in px")
    args = p.parse_args()

    os.makedirs(args.output, exist_ok=True)
    variants = ["vidcolors", "bw", "matrix", "rainbow"] if args.variants == "all" else args.variants.split(",")
    font = args.font or find_font()
    vw, vh, fps = args.hres, args.vres, args.fps

    vinfo = probe_video(args.input)
    n_frames = int(vinfo["duration"] * fps)
    print(f"Decoding {vinfo['width']}x{vinfo['height']} @ {n_frames} frames...")
    frames, sw, sh = decode_frames(args.input, fps, n_frames)
    print(f"Got {len(frames)} frames")

    # Extract audio once
    audio_path = None
    if vinfo["has_audio"]:
        audio_path = os.path.join(args.output, "audio.aac")
        subprocess.run(["ffmpeg", "-y", "-i", args.input, "-vn", "-c:a", "copy", audio_path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    pal_map = {"vidcolors": CHARS, "bw": CHARS, "rainbow": CHARS, "matrix": PAL_MATRIX}
    for vname in variants:
        if vname not in pal_map:
            print(f"Unknown variant: {vname}")
            continue
        pal = pal_map[vname]
        out_path = os.path.join(args.output, f"{vname}.mp4")
        render_variant(vname, out_path, frames, font, args.font_size, vw, vh, fps, pal)
        if audio_path:
            mux_audio(out_path, audio_path, out_path)
            size_mb = os.path.getsize(out_path) / 1024 / 1024
            print(f"  (with audio: {size_mb:.1f} MB)")
    print("\nPhase 1 complete.")


if __name__ == "__main__":
    main()
