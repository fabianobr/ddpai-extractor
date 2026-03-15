#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Configuration ────────────────────────────────────────────────────────────
SD_TAR_DIR="/Volumes/ddpai/DCIM/203gps/tar"
SD_REAR_DIR="/Volumes/ddpai/DCIM/200video/rear"
SD_FRONT_DIR="/Volumes/ddpai/DCIM/200video/front"
POLL_INTERVAL=30  # seconds between checks
STATE_FILE="data/.last_tar_count"
BACKUP_FILE="data/trips.json.bak"

# ── Parse flags ───────────────────────────────────────────────────────────────
USE_PARALLEL=false
for arg in "$@"; do
  case "$arg" in
    --parallel) USE_PARALLEL=true ;;
  esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────
notify() {
  local title="$1" msg="$2"
  osascript -e "display notification \"$msg\" with title \"$title\"" 2>/dev/null || true
}

count_tars() {
  ls "$SD_TAR_DIR"/*.git 2>/dev/null | wc -l | tr -d ' '
}

# ── Entry ─────────────────────────────────────────────────────────────────────
BUILD_CMD="./build.sh"
if [ "$USE_PARALLEL" = "true" ]; then
  BUILD_CMD="./tools/build_parallel.sh"
fi

echo "👁  DDpai Watchdog started"
echo "   SD card:  $SD_TAR_DIR"
echo "   Build:    $BUILD_CMD"
echo "   Interval: ${POLL_INTERVAL}s"
echo "   Press Ctrl+C to stop"
echo ""

mkdir -p data

# Read last known count (default 0 on first run)
LAST_COUNT=0
if [ -f "$STATE_FILE" ]; then
  LAST_COUNT=$(cat "$STATE_FILE")
fi

# ── Poll loop ─────────────────────────────────────────────────────────────────
while true; do
  # Check SD card is mounted
  if [ ! -d "$SD_TAR_DIR" ]; then
    echo "⏳ $(date '+%H:%M:%S')  SD card not found at /Volumes/ddpai — waiting..."
    sleep "$POLL_INTERVAL"
    continue
  fi

  CURRENT_COUNT=$(count_tars)

  if [ "$CURRENT_COUNT" != "$LAST_COUNT" ]; then
    echo "🆕 $(date '+%H:%M:%S')  Change detected: $LAST_COUNT → $CURRENT_COUNT TAR files"

    # Backup existing database
    if [ -f "data/trips.json" ]; then
      cp "data/trips.json" "$BACKUP_FILE"
      echo "   💾 Backed up trips.json → trips.json.bak"
    fi

    # Run build
    echo "   🔨 Running $BUILD_CMD ..."
    if $BUILD_CMD "$SD_TAR_DIR" "$SD_REAR_DIR" "$SD_FRONT_DIR"; then
      echo "   ✅ Build succeeded"
      notify "DDpai ✅" "Build complete — $CURRENT_COUNT archives processed"
      echo "$CURRENT_COUNT" > "$STATE_FILE"
      LAST_COUNT=$CURRENT_COUNT
    else
      echo "   ❌ Build failed — keeping last_count unchanged"
      notify "DDpai ❌" "Build failed — check terminal for details"
    fi
    echo ""
  else
    echo "✔  $(date '+%H:%M:%S')  No change ($CURRENT_COUNT TAR files)"
  fi

  sleep "$POLL_INTERVAL"
done
