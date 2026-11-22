#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f "data/trips.json" ]; then
    echo "⚠️  No database found. Run: ./build.sh"
    exit 1
fi

PORT="${1:-8765}"
exec python3 -m src.processing.http_server "$PORT"
