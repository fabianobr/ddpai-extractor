#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default paths (local)
TAR_DIR="${1:-working_data/tar}"
REAR_DIR="${2:-/Users/fabianosilva/dashcam/DCIM/200video/rear}"
FRONT_DIR="${3:-/Users/fabianosilva/dashcam/DCIM/200video/front}"
OUTPUT_DIR="${4:-.}"

# Validate paths exist
if [ ! -d "$TAR_DIR" ]; then
    echo "❌ Error: TAR directory not found: $TAR_DIR"
    echo ""
    echo "Usage: ./build.sh [TAR_DIR] [REAR_DIR] [FRONT_DIR] [OUTPUT_DIR]"
    echo ""
    echo "Examples:"
    echo "  ./build.sh                           # Use defaults (local working_data/)"
    echo "  ./build.sh /Volumes/SDCard/tar       # Read from SD card"
    echo "  ./build.sh /Volumes/SDCard/tar /Volumes/SDCard/rear /Volumes/SDCard/front"
    echo ""
    exit 1
fi

echo "🔨 Building trip database..."
echo "   TAR files:    $TAR_DIR"
echo "   Rear videos:  $REAR_DIR"
echo "   Front videos: $FRONT_DIR"
echo "   Output:       $OUTPUT_DIR"
echo ""

python3 -m src.extraction.build_database "$TAR_DIR" "$REAR_DIR" "$FRONT_DIR" "$OUTPUT_DIR"
echo ""
echo "✅ Done. Start app with: ./run.sh"
