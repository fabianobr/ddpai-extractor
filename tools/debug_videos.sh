#!/usr/bin/env bash
# Debug script to inspect merged videos and compare with source videos

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================================================
📊 VIDEO MERGE DEBUG REPORT
================================================================================"
echo ""

if [ ! -d "merged_videos" ]; then
    echo "❌ No merged_videos directory found"
    exit 1
fi

# Function to get video info using ffprobe
get_video_info() {
    local video=$1
    if command -v ffprobe &> /dev/null; then
        echo "Using ffprobe:"
        ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1:nokey=1:csv=p=0 "$video" 2>/dev/null | {
            read duration
            read size
            if [ ! -z "$duration" ]; then
                min=$(echo "$duration / 60" | bc)
                echo "  Duration: ${min}m (${duration}s)"
            fi
            if [ ! -z "$size" ]; then
                size_mb=$(echo "scale=1; $size / 1024 / 1024" | bc)
                echo "  Size: ${size_mb} MB"
            fi
        }
    fi
}

echo "📁 MERGED VIDEO FILES:"
echo "================================================================================"
ls -lh merged_videos/*.mp4 2>/dev/null | awk '{print $9, "→", $5}' | while read file size; do
    if [ ! -z "$file" ]; then
        echo ""
        echo "📹 $(basename $file) ($size)"
        get_video_info "$file"
    fi
done

echo ""
echo "================================================================================"
echo "🔍 ORIGINAL VIDEO LOCATIONS:"
echo "================================================================================"

echo ""
echo "Rear videos:"
REAR_DIR="/Users/fabianosilva/dashcam/DCIM/200video/rear"
if [ -d "$REAR_DIR" ]; then
    count=$(ls -1 "$REAR_DIR"/*.mp4 2>/dev/null | wc -l)
    echo "  📂 $REAR_DIR"
    echo "  Count: $count videos"
    ls -1 "$REAR_DIR"/*.mp4 2>/dev/null | head -5 | while read f; do
        echo "    • $(basename $f) ($(ls -lh $f | awk '{print $5}'))"
    done
    if [ $count -gt 5 ]; then
        echo "    ... and $((count - 5)) more"
    fi
else
    echo "  ❌ Not found: $REAR_DIR"
fi

echo ""
echo "Front videos:"
FRONT_DIR="/Users/fabianosilva/dashcam/DCIM/200video/front"
if [ -d "$FRONT_DIR" ]; then
    count=$(ls -1 "$FRONT_DIR"/*.mp4 2>/dev/null | wc -l)
    echo "  📂 $FRONT_DIR"
    echo "  Count: $count videos"
    ls -1 "$FRONT_DIR"/*.mp4 2>/dev/null | head -5 | while read f; do
        echo "    • $(basename $f) ($(ls -lh $f | awk '{print $5}'))"
    done
    if [ $count -gt 5 ]; then
        echo "    ... and $((count - 5)) more"
    fi
else
    echo "  ❌ Not found: $FRONT_DIR"
fi

echo ""
echo "================================================================================"
echo "💡 TROUBLESHOOTING:"
echo "================================================================================"
echo ""
echo "1. Compare file sizes:"
echo "   Total merged size should ≈ sum of source video sizes"
echo ""
echo "2. Check duration:"
echo "   ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 merged_videos/*.mp4"
echo ""
echo "3. Verify concat order in build output:"
echo "   Check the build log above for video merge order"
echo ""
echo "4. Test playback:"
echo "   ffplay merged_videos/[trip_id]_rear.mp4"
echo ""
echo "5. Re-run build with debug:"
echo "   ./build.sh"
echo ""
echo "================================================================================"
