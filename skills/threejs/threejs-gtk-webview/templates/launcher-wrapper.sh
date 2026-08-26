#!/bin/bash
# Launcher wrapper — starts HTTP server + Chromium kiosk overlay
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCK_FILE="$HOME/.cache/allmind-launcher.lock"

if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE" 2>/dev/null)
    kill -0 "$PID" 2>/dev/null && exit 0
fi

mkdir -p "$HOME/.cache"
echo $$ > "$LOCK_FILE"

fuser -k 8765/tcp 2>/dev/null || true

# Resolve the Chromium binary at runtime (distro-dependent path)
CHROMIUM_BIN="$(command -v chromium || command -v chromium-browser || command -v google-chrome-stable)"
if [ -z "$CHROMIUM_BIN" ] && [ -x /usr/lib/chromium/chromium ]; then
    CHROMIUM_BIN=/usr/lib/chromium/chromium
fi
if [ -z "$CHROMIUM_BIN" ]; then
    echo "Chromium not found — install it or set CHROMIUM_BIN" >&2
    rm -f "$LOCK_FILE"
    exit 1
fi

# Use the active Wayland display if set, else default to wayland-0
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"

cd "$SCRIPT_DIR"
python3 overlay-server.py &
SERVER_PID=$!
sleep 0.5

env WAYLAND_DISPLAY="$WAYLAND_DISPLAY" "$CHROMIUM_BIN" \
    --ozone-platform=wayland \
    --use-angle=gles \
    --kiosk \
    --no-first-run \
    --disable-features=TranslateUI \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-popup-blocking \
    --disable-translate \
    http://127.0.0.1:8765 &

wait $SERVER_PID 2>/dev/null
rm -f "$LOCK_FILE"
