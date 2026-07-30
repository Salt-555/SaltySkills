// Moshpit Custom Filter Template — FFglitch 0.10 API
// Use with: python ffglitch_mosh.py input.mp4 --script custom_filters.js -o output.avi
//
// Required functions (must be exported):
//   setup(args)     — select features to process
//   glitch_frame(frame) — modify each frame's data
//
// Motion vectors accessed via:
//   frame.mv.forward  → MV2DArray of [h, v] vectors per macroblock
//   frame.index       → current frame number (0-based)
//   fwd.width / fwd.height → vector grid dimensions
//
// Each mv in forEach can be null on I-frames — always check!
// Use mv.add_h(n), mv.add_v(n) to modify, or mv.assign(h, v) to replace.

export function setup(args) {
    args.features = ["mv"];  // process motion vectors
}

export function glitch_frame(frame) {
    const fwd = frame.mv?.forward;
    if (!fwd) return;         // skip frames with no forward vectors (I-frames)

    frame.mv.overflow = "truncate";  // clamp out-of-range vectors

    // --- EXAMPLE: Combine multiple effects ---

    // 1. Horizontal wave that oscillates over time
    var waveAmp = 4 + Math.sin(frame.index * 0.1) * 3;
    fwd.forEach(function(mv, y, x) {
        if (!mv) return;      // skip null vectors on I-frames
        mv.add_h(Math.sin(y * 0.2 + frame.index * 0.3) * waveAmp);
    });

    // 2. Vertical cascade that intensifies toward bottom
    fwd.forEach(function(mv, y, x) {
        if (!mv) return;
        var intensity = y / fwd.height;  // 0 at top, 1 at bottom
        mv.add_v(intensity * 6);
    });

    // 3. Random glitch blocks (deterministic per-frame)
    var seed = frame.index * 7919 + 104729;
    function rand() {
        seed = (seed * 16807) % 2147483647;
        return seed / 2147483647;
    }
    var numBlocks = 2 + Math.floor(rand() * 3);
    for (var b = 0; b < numBlocks; b++) {
        var bx = Math.floor(rand() * fwd.width);
        var by = Math.floor(rand() * fwd.height);
        var bw = 4 + Math.floor(rand() * 8);
        var bh = 4 + Math.floor(rand() * 8);
        // Zero out vectors in a rectangular region using subarray + fill
        var ex = Math.min(bx + bw, fwd.width);
        var ey = Math.min(by + bh, fwd.height);
        var sub = fwd.subarray([bx, by], [ex, ey]);
        sub.fill(MV(0, 0));
    }
}
