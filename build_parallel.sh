#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

TAR_DIR="${1:-working_data/tar}"
REAR_DIR="${2:-/Users/fabianosilva/dashcam/DCIM/200video/rear}"
FRONT_DIR="${3:-/Users/fabianosilva/dashcam/DCIM/200video/front}"
OUTPUT_DIR="${4:-.}"

if [ ! -d "$TAR_DIR" ]; then
    echo "❌ Error: TAR directory not found: $TAR_DIR"
    echo "Usage: ./build_parallel.sh [TAR_DIR] [REAR_DIR] [FRONT_DIR] [OUTPUT_DIR]"
    exit 1
fi

echo "🔨 Building trip database (parallel)..."
echo "   TAR files:    $TAR_DIR"
echo "   Rear videos:  $REAR_DIR"
echo "   Front videos: $FRONT_DIR"
echo "   Output:       $OUTPUT_DIR"
echo ""

python3 src/build_database_parallel.py "$TAR_DIR" "$REAR_DIR" "$FRONT_DIR" "$OUTPUT_DIR"
echo ""
echo "✅ Done. Start app with: ./run.sh"
