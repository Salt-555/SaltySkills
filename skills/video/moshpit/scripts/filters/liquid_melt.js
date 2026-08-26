// Setup A — Liquid Vector Melt
// Combines sine-wave distortion with backward self-referencing lookback
// for a flowing, hallucinatory liquid corruption of the motion vectors.
export function setup(args) { args.features = ["mv"]; }
export function glitch_frame(frame) {
    const fwd = frame.mv?.forward;
    if (!fwd) return;
    frame.mv.overflow = "truncate";
    var freq = 0.12;
    var amp = 24 + Math.sin(frame.index * 0.05) * 16;   // wave amplitude
    var lookback = 26 + Math.floor(Math.sin(frame.index * 0.08) * 16); // loop pull
    fwd.forEach(function(mv, y, x) {
        if (!mv) return;
        // wave distortion
        mv[1] += Math.sin(x * freq + frame.index * 0.3) * amp;
        mv[0] += Math.cos(y * freq + frame.index * 0.2) * amp * 0.5;
        // self-referencing lookback
        mv[0] += -lookback * Math.sin(frame.index * 0.2 + y * 0.1);
        mv[1] += -lookback * Math.cos(frame.index * 0.15 + x * 0.1);
    });
}
