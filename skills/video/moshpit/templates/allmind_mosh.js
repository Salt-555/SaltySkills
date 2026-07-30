// ALLMIND-themed datamosh filter — FFglitch 0.10 API
// Atmospheric haze-style glitch: subtle horizontal drift + periodic corruption bursts
// Matches the GXSC aesthetic — muted, atmospheric, not chaotic noise

export function setup(args) {
    args.features = ["mv"];
}

export function glitch_frame(frame) {
    const fwd = frame.mv?.forward;
    if (!fwd) return;

    frame.mv.overflow = "truncate";

    var cx = fwd.width / 2;
    var cy = fwd.height / 2;

    // Gentle horizontal drift — like haze moving across frame
    var drift = Math.sin(frame.index * 0.05) * 1.5;
    fwd.forEach(function(mv, y, x) {
        if (!mv) return;
        // Drift increases toward edges (vignette-style)
        var edgeDist = Math.sqrt((x - cx) * (x - cx) + (y - cy) * (y - cy));
        var maxDist = Math.sqrt(cx * cx + cy * cy);
        var vignette = edgeDist / maxDist;

        mv.add_h(drift * vignette);
        mv.add_v(Math.cos(frame.index * 0.03 + x * 0.1) * 0.5 * vignette);
    });

    // Periodic corruption burst every ~60 frames (2 seconds at 30fps)
    var cycle = frame.index % 60;
    if (cycle < 8) {
        var intensity = (1 - cycle / 8) * 12; // fades over 8 frames
        fwd.forEach(function(mv, y, x) {
            if (!mv) return;
            mv.add_h(intensity * Math.sin(y * 0.3 + frame.index));
            mv.add_v(intensity * 0.3 * Math.cos(x * 0.2));
        });
    }

    // Subtle macroblock death — randomly zero small blocks rarely
    var seed = frame.index * 48271 + 12345;
    function rand() {
        seed = (seed * 48271) % 2147483647;
        return seed / 2147483647;
    }
    // Only ~1 block per frame on average
    if (rand() < 0.15) {
        var bx = Math.floor(rand() * fwd.width);
        var by = Math.floor(rand() * fwd.height);
        var ex = Math.min(bx + 3, fwd.width);
        var ey = Math.min(by + 3, fwd.height);
        if (ex > bx && ey > by) {
            var sub = fwd.subarray([bx, by], [ex, ey]);
            sub.fill(MV(0, 0));
        }
    }
}
