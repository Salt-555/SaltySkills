#!/usr/bin/env python3
"""VHS/analog filter for images.

Adapted from deep-fry's vhs_polisher.py into a standalone, reusable tool.
Supports single-image processing (grain/scanlines/vignette/chromatic aberration).

Usage:
  python3 scripts/vhs-filter.py --input IMG.png --output OUT.png --seed 42 --intensity 1.0

Note: This tool is image-only. It does NOT process video (MP4/AVI/MOV) input —
feed it a single static frame, then apply motion (e.g. Ken Burns zoompan) on top.

Intensity levels:
  0.7 = subtle (grain + vignette, good for clean shots)
  1.0 = standard (all effects visible — default)
  1.5 = heavy (strong chromatic aberration, deep scanlines)

Critical rule: Apply VHS BEFORE Ken Burns zoompan. The zoompan blur destroys grain and scanlines.
Motion on top of VHS-filtered frames creates lived-in analog feel.

Effects applied:
  - Chromatic aberration (RGB channel offset)
  - Analog noise (per-pixel random variation)
  - Scanlines (alternating dark/bright horizontal lines)
  - CRT vignette (darkened corners with slight curvature)

Intensity scaling: chromatic aberration offset and noise magnitude scale linearly with --intensity.
"""

import argparse
import numpy as np
from PIL import Image, ImageFilter


def apply_vhs(image_path: str, output_path: str, seed: int = 42, intensity: float = 1.0):
    """Apply VHS/analog filter to an image."""
    rng = np.random.RandomState(seed)

    img = Image.open(image_path).convert("RGB")
    arr = np.array(img, dtype=np.float32) / 255.0

    h, w = arr.shape[:2]

    # --- Chromatic aberration (scales with intensity) ---
    offset = int(2 * intensity)
    if offset > 0:
        r_channel = np.roll(arr[:, :, 0], offset, axis=1)
        b_channel = np.roll(arr[:, :, 2], -offset, axis=1)
        arr[:, :, 0] = r_channel
        arr[:, :, 2] = b_channel

    # --- Analog noise (scales with intensity) ---
    noise_mag = 0.03 * intensity
    noise = rng.normal(0, noise_mag, arr.shape)
    arr = np.clip(arr + noise, 0, 1)

    # --- Scanlines ---
    # Alternate every row between 0.92 and 1.0 brightness. Build the full-height
    # row pattern first, then tile across columns so it broadcasts against (h, w, 3).
    row_pattern = np.tile(np.array([0.92, 1.0]), (h + 1) // 2)[:h]  # (h,)
    scanline_pattern = np.tile(row_pattern[:, None], (1, w))        # (h, w)
    arr[:, :, :] *= scanline_pattern[:, :, np.newaxis]

    # --- CRT vignette ---
    y_grid, x_grid = np.ogrid[:h, :w]
    cy, cx = h / 2, w / 2
    dist = np.sqrt(((y_grid - cy) / cy) ** 2 + ((x_grid - cx) / cx) ** 2)
    vignette = 1.0 - 0.5 * (dist / np.max(dist)) ** 2
    arr[:, :, :] *= vignette[:, :, np.newaxis]

    # Clamp and convert back
    result = np.clip(arr * 255, 0, 255).astype(np.uint8)
    Image.fromarray(result).save(output_path)


def main():
    parser = argparse.ArgumentParser(description="VHS/analog filter for images")
    parser.add_argument("--input", required=True, help="Input image path")
    parser.add_argument("--output", required=True, help="Output image path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--intensity", type=float, default=1.0, choices=[0.7, 1.0, 1.5], help="Effect intensity")
    args = parser.parse_args()

    apply_vhs(args.input, args.output, seed=args.seed, intensity=args.intensity)


if __name__ == "__main__":
    main()
