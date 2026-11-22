#!/usr/bin/env bash
# Copy DDpai still photos from the prepared local source without altering it.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_DIR="${1:-$REPO_DIR/working_data/photos}"
OUTPUT_DIR="${2:-$REPO_DIR/extracted_photos}"
MODE="${3:-}"

if [[ "$MODE" != "" && "$MODE" != "--include-tmp" && "$MODE" != "--dry-run" ]]; then
    echo "Usage: $0 [SOURCE_DIR] [OUTPUT_DIR] [--include-tmp|--dry-run]" >&2
    exit 2
fi

if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "Photo source not found: $SOURCE_DIR" >&2
    exit 1
fi

sources=(front rear)
if [[ "$MODE" == "--include-tmp" ]]; then
    sources+=(tmp)
fi

copied=0
for camera in "${sources[@]}"; do
    source_camera_dir="$SOURCE_DIR/$camera"
    [[ -d "$source_camera_dir" ]] || continue
    destination_camera_dir="$OUTPUT_DIR/$camera"
    count=0

    while IFS= read -r -d '' photo; do
        count=$((count + 1))
        if [[ "$MODE" == "--dry-run" ]]; then
            printf 'Would copy: %s -> %s/\n' "$photo" "$destination_camera_dir"
        else
            mkdir -p "$destination_camera_dir"
            # -a keeps timestamps/EXIF-relevant metadata; -n never overwrites a prior export.
            cp -an -- "$photo" "$destination_camera_dir/"
        fi
    done < <(find -L "$source_camera_dir" -maxdepth 1 -type f -iname '*.jpg' -print0)

    printf '%s: %d JPEG(s)%s\n' "$camera" "$count" \
        "$([[ "$MODE" == "--dry-run" ]] && printf ' (dry run)')"
    copied=$((copied + count))
done

if [[ "$MODE" == "--dry-run" ]]; then
    printf 'Total available for extraction: %d JPEG(s)\n' "$copied"
else
    printf 'Extraction complete: %d JPEG(s) considered in %s\n' "$copied" "$OUTPUT_DIR"
fi
