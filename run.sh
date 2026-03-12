#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f "data/trips.json" ]; then
    echo "⚠️  No database found. Run: ./build.sh"
    exit 1
fi

# Kill any existing process on port 8000
if command -v lsof &> /dev/null; then
    PID=$(lsof -ti :8000 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo "🔌 Freeing port 8000 (killing PID $PID)..."
        kill -9 $PID 2>/dev/null || true
        sleep 1
    fi
fi

echo "🎬 DDpai Dashboard"
echo "   → http://localhost:8000/web/"
echo "   Press Ctrl+C to stop"
echo ""

python3 -m http.server 8000 --bind 127.0.0.1
