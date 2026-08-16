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

export WAYLAND_DISPLAY=wayland-0
cd "$SCRIPT_DIR"
python3 allmind-launcher-server.py &
SERVER_PID=$!
sleep 0.5

env WAYLAND_DISPLAY=wayland-0 /usr/lib/chromium/chromium \
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
