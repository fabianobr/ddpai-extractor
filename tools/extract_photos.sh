#!/usr/bin/env bash
# Copy DDpai still photos from the prepared local source without altering it.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
    echo "Usage: $0 [SOURCE_DIR] [OUTPUT_DIR] [--dry-run] [--include-tmp]  (flags may appear anywhere)" >&2
}

DRY_RUN=0
INCLUDE_TMP=0
positional=()
while (($#)); do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --include-tmp) INCLUDE_TMP=1 ;;
        -h|--help) usage; exit 0 ;;
        --) shift; positional+=("$@"); break ;;
        -*) echo "Unknown option: $1" >&2; usage; exit 2 ;;
        *) positional+=("$1") ;;
    esac
    shift
done

if ((${#positional[@]} > 2)); then
    usage
    exit 2
fi

SOURCE_DIR="${positional[0]:-$REPO_DIR/working_data/photos}"
OUTPUT_DIR="${positional[1]:-$REPO_DIR/extracted_photos}"

if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "Photo source not found: $SOURCE_DIR" >&2
    exit 1
fi

sources=(front rear)
if ((INCLUDE_TMP)); then
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
        if ((DRY_RUN)); then
            printf 'Would copy: %s -> %s/\n' "$photo" "$destination_camera_dir"
        else
            mkdir -p "$destination_camera_dir"
            # -a keeps timestamps/EXIF-relevant metadata; -n never overwrites a prior export.
            cp -an -- "$photo" "$destination_camera_dir/"
        fi
    done < <(find -L "$source_camera_dir" -maxdepth 1 -type f -iname '*.jpg' -print0)

    printf '%s: %d JPEG(s)%s\n' "$camera" "$count" \
        "$( ((DRY_RUN)) && printf ' (dry run)' || true)"
    copied=$((copied + count))
done

if ((DRY_RUN)); then
    printf 'Total available for extraction: %d JPEG(s)\n' "$copied"
else
    printf 'Extraction complete: %d JPEG(s) considered in %s\n' "$copied" "$OUTPUT_DIR"
fi
