#!/usr/bin/env python3
"""
DDpai Database Builder — Parallel variant.
Imports all logic from build_database.py; only main() is overridden with threading.
"""
import sys
import os
import json
import glob
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Import everything from the original sequential script
sys.path.insert(0, os.path.dirname(__file__))
from build_database import (
    parse_tar_filename, detect_trip_groups, extract_gps_from_tar,
    discover_videos, validate_gps, validate_videos, compute_trip_stats,
    merge_videos, save_merge_report,
    WORKING_DIR, VIDEO_DIR_REAR, VIDEO_DIR_FRONT,
    OUTPUT_DIR, MERGED_VIDEO_DIR, OUTPUT_JSON, GAP_THRESHOLD,
    OUTPUT_HEIGHT, VIDEO_CRF, VIDEO_PRESET
)

# ============================================================================
# Thread-safe printing
# ============================================================================

_PRINT_LOCK = threading.Lock()

def locked_print(*args, **kwargs):
    """Thread-safe print using a lock."""
    with _PRINT_LOCK:
        print(*args, **kwargs)

# ============================================================================
# Per-group processing
# ============================================================================

def process_group(group_idx, group, total_groups, inner_executor):
    """
    Process one trip group in parallel.

    Args:
        group_idx: 1-based group index
        group: list of TAR file paths for this group
        total_groups: total number of groups (for progress display)
        inner_executor: ThreadPoolExecutor for rear+front video merging

    Returns:
        (group_data_dict | None, merge_debug_lines)
    """
    group_merge_info = []

    # Parse the first TAR file to get group ID
    start_utc, _ = parse_tar_filename(group[0])
    if start_utc is None:
        return None, group_merge_info

    group_id = start_utc.strftime('%Y%m%d%H%M%S')
    date_str = start_utc.strftime('%Y-%m-%d')

    locked_print(f"Group {group_idx}/{total_groups}: {len(group)} archives | ID: {group_id}")

    # ========== Extract GPS ==========
    all_points = []
    for tar_path in group:
        all_points.extend(extract_gps_from_tar(tar_path))

    if not all_points:
        locked_print(f"  [{group_id}] ⚠️  SKIP: no GPS data")
        return None, group_merge_info

    locked_print(f"  [{group_id}] 📍 {len(all_points)} GPS points")

    # ========== Discover videos ==========
    rear_videos = discover_videos(group, camera='rear')
    front_videos = discover_videos(group, camera='front')
    locked_print(f"  [{group_id}] 🎥 {len(rear_videos)} rear, {len(front_videos)} front")

    # ========== Validate GPS (mandatory) ==========
    gps_errors = validate_gps(all_points)
    if gps_errors:
        error_msg = '; '.join(gps_errors)
        locked_print(f"  [{group_id}] ❌ SKIP (GPS): {error_msg}")
        return None, group_merge_info

    # ========== Validate videos (optional) ==========
    video_has_errors, video_warnings = validate_videos(rear_videos, front_videos)
    for line in video_warnings:
        locked_print(f"  [{group_id}] {line}")

    locked_print(f"  [{group_id}] ✅ GPS validated - proceeding with video processing")

    # Initialize video merge status variables (will be updated below)
    rear_ok = False
    front_ok = False
    video_status = "no_videos"
    video_notes = "No video files found for either camera"

    # Smart video merge: implement min() count strategy
    rear_count = len(rear_videos)
    front_count = len(front_videos)

    if rear_count > 0 and front_count > 0:
        # Both cameras have videos: use min() to ensure sync
        merge_count = min(rear_count, front_count)
        if rear_count != front_count:
            ignored_count = abs(rear_count - front_count)
            locked_print(f"  [{group_id}] ⚠️  VIDEO COUNT MISMATCH: {rear_count} rear vs {front_count} front")
            locked_print(f"  [{group_id}]    Merge strategy: Using min({rear_count}, {front_count}) = {merge_count} pairs")
            locked_print(f"  [{group_id}]    Will ignore: {ignored_count} extra video(s)")

            # Rediscover with limit to get only the pairs we'll merge
            rear_videos = discover_videos(group, camera='rear', limit_count=merge_count)
            front_videos = discover_videos(group, camera='front', limit_count=merge_count)
        else:
            locked_print(f"  [{group_id}] ✅ Both cameras matched: {merge_count} pairs ready for merge")
    elif rear_count > 0:
        # Only rear videos
        locked_print(f"  [{group_id}] ⚠️  No front videos available ({rear_count} rear available)")
    elif front_count > 0:
        # Only front videos
        locked_print(f"  [{group_id}] ⚠️  No rear videos available ({front_count} front available)")
    else:
        # No videos at all
        locked_print(f"  [{group_id}] ⚠️  No videos found for either camera")

    # ========== Compute stats ==========
    stats = compute_trip_stats(all_points)
    locked_print(f"  [{group_id}] 📊 {stats['distance_km']} km | {stats['duration_min']} min | max {stats['max_speed']} km/h")

    # ========== Merge videos in parallel (rear + front) if available ==========
    if rear_count > 0 and front_count > 0:
        rear_output = os.path.join(MERGED_VIDEO_DIR, f'{group_id}_rear.mp4')
        front_output = os.path.join(MERGED_VIDEO_DIR, f'{group_id}_front.mp4')

        locked_print(f"  [{group_id}] 🎬 Merging rear + front in parallel...")

        # Submit both rear and front merges to the inner executor
        fut_rear = inner_executor.submit(merge_videos, rear_videos, rear_output, 'Rear',
                                         None, False)
        fut_front = inner_executor.submit(merge_videos, front_videos, front_output, 'Front',
                                          None, False)

        # Wait for both to complete
        rear_ok, rear_debug = fut_rear.result()
        front_ok, front_debug = fut_front.result()

        # Collect debug output with thread safety
        with _PRINT_LOCK:
            for line in rear_debug + front_debug:
                print(line, flush=True)

        group_merge_info.extend(rear_debug)
        group_merge_info.extend(front_debug)

        # Determine merge status and notes
        if rear_ok and front_ok:
            if rear_count != front_count:
                extra_count = abs(rear_count - front_count)
                video_status = "ok_with_extras"
                video_notes = f"Merged {merge_count} rear + {merge_count} front videos ({extra_count} extra video(s) ignored)"
                locked_print(f"  [{group_id}] ✅ Merged: {merge_count} pairs ({extra_count} extra video(s) ignored)")
            else:
                video_status = "ok"
                video_notes = f"Merged {merge_count} rear + {merge_count} front videos successfully"
                locked_print(f"  [{group_id}] ✅ Merged: {merge_count} pairs")
        else:
            # At least one merge failed - record what happened
            if not rear_ok and not front_ok:
                video_status = "merge_failed"
                video_notes = "Both rear and front video merges failed"
            elif not rear_ok:
                video_status = "merge_failed_rear"
                video_notes = f"Rear video merge failed ({rear_count} rear, {front_count} front files)"
            else:
                video_status = "merge_failed_front"
                video_notes = f"Front video merge failed ({rear_count} rear, {front_count} front files)"

            locked_print(f"  [{group_id}] ⚠️  Video merge failed, but GPS data is valid")
            locked_print(f"  [{group_id}]    Status: {video_status}")

    elif rear_count > 0:
        # Only rear videos
        video_status = "no_front"
        video_notes = f"Only rear videos available ({rear_count} rear, 0 front)"
        locked_print(f"  [{group_id}] ⚠️  No front videos, but GPS data is valid")

    elif front_count > 0:
        # Only front videos
        video_status = "no_rear"
        video_notes = f"Only front videos available (0 rear, {front_count} front)"
        locked_print(f"  [{group_id}] ⚠️  No rear videos, but GPS data is valid")

    else:
        # No videos at all - but GPS is valid so we include the trip
        video_status = "no_videos"
        video_notes = "No video files found for either camera"
        locked_print(f"  [{group_id}] ⚠️  No videos found, but GPS data is valid")

    # ========== Build result dict ==========
    end_date = start_utc + timedelta(minutes=stats['duration_min'])
    label = f"{start_utc.strftime('%b %d')} {start_utc.strftime('%H:%M')} → {end_date.strftime('%H:%M')}"

    locked_print(f"  [{group_id}] ✅ Done")

    # Build video paths based on merge success
    video_rear_path = f'merged_videos/{group_id}_rear.mp4' if rear_ok else None
    video_front_path = f'merged_videos/{group_id}_front.mp4' if front_ok else None

    return {
        'id': group_id,
        'label': label,
        'date': date_str,
        'duration_min': stats['duration_min'],
        'distance_km': stats['distance_km'],
        'max_speed': stats['max_speed'],
        'avg_speed': stats['avg_speed'],
        'points': [[p['lat'], p['lon'], p['speed_kmh'], p['altitude'], p['heading']] for p in all_points],
        'video_rear': video_rear_path,
        'video_front': video_front_path,
        'video_status': video_status,
        'video_notes': video_notes,
    }, group_merge_info

# ============================================================================
# Main (parallel version)
# ============================================================================

def main():
    print("=" * 80)
    print("🎬 DDpai Database Builder (PARALLEL)")
    print("=" * 80)
    print()

    # Step 1: Find all .git files
    print("Step 1: Discovering .git archives...")
    tar_files = sorted(glob.glob(os.path.join(WORKING_DIR, '*.git')))
    print(f"  Found {len(tar_files)} archives")
    if tar_files:
        first_name = os.path.basename(tar_files[0])
        last_name = os.path.basename(tar_files[-1])
        first_start, first_dur = parse_tar_filename(tar_files[0])
        last_start, last_dur = parse_tar_filename(tar_files[-1])

        if first_start and last_start:
            print(f"  First: {first_name}")
            print(f"         → {first_start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"  Last:  {last_name}")
            print(f"         → {last_start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()

    # Step 2: Detect trip groups
    print("Step 2: Detecting trip groups (30-min gap threshold)...")
    groups, gaps = detect_trip_groups(tar_files)
    print(f"  Detected {len(groups)} trip groups")

    # Show chronological range for each group
    for group_idx, group in enumerate(groups, 1):
        first_start, first_dur = parse_tar_filename(group[0])
        last_tar = group[-1]
        last_start, last_dur = parse_tar_filename(last_tar)

        if first_start and last_start and last_dur:
            last_end = last_start + timedelta(seconds=last_dur)
            print(f"  Group {group_idx}: {first_start.strftime('%Y-%m-%d %H:%M:%S')} → {last_end.strftime('%H:%M:%S UTC')} ({len(group)} files)")

    # Show gap information if any
    if gaps:
        print(f"\n  ⏱️  Gaps detected (>30min threshold):")
        for gap in gaps:
            print(f"     • {gap['gap_minutes']} min gap: {gap['between']}")
    else:
        print(f"\n  ℹ️  No gaps >30min detected — all {len(tar_files)} files in continuous sequence")
    print()

    # Step 3: Process groups in parallel
    print("Step 3: Processing groups in parallel...")
    print()

    MAX_OUTER_WORKERS = min(len(groups), 4)  # Cap at 4 concurrent groups
    MAX_INNER_WORKERS = 2                    # Always 2 (rear + front per group)

    groups_data = [None] * len(groups)       # Pre-sized to preserve order
    all_merge_info = []
    valid_count = 0

    report_file = os.path.join(OUTPUT_DIR, 'data', 'merge_report.txt')
    report_lines = [
        "VIDEO MERGE DEBUG REPORT (PARALLEL)",
        "=" * 80,
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"TAR Directory: {WORKING_DIR}",
        f"Rear Videos: {VIDEO_DIR_REAR}",
        f"Front Videos: {VIDEO_DIR_FRONT}",
        f"Output Directory: {OUTPUT_DIR}",
        f"Workers: outer={MAX_OUTER_WORKERS}, inner={MAX_INNER_WORKERS}",
        "=" * 80,
    ]

    # Create nested executors: outer for groups, inner for rear+front per group
    with ThreadPoolExecutor(max_workers=MAX_INNER_WORKERS, thread_name_prefix='merge') as inner_ex:
        with ThreadPoolExecutor(max_workers=MAX_OUTER_WORKERS, thread_name_prefix='group') as outer_ex:

            # Submit all groups to the outer executor
            future_to_idx = {
                outer_ex.submit(process_group, idx + 1, group, len(groups), inner_ex): idx
                for idx, group in enumerate(groups)
            }

            # Collect results as they complete (not necessarily in order)
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    group_data, merge_info = future.result()
                except Exception as exc:
                    locked_print(f"  Group {idx + 1} error: {exc}")
                    group_data, merge_info = None, []

                all_merge_info.extend(merge_info)
                if group_data is not None:
                    groups_data[idx] = group_data
                    valid_count += 1

    # Remove None slots to get final list in original order
    groups_data = [g for g in groups_data if g is not None]

    print()
    print("Step 4: Writing database...")

    if not groups_data:
        print("  ❌ No valid groups!")
        return 1

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, 'w') as f:
        json.dump({
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'trips': groups_data
        }, f)

    file_size_kb = os.path.getsize(OUTPUT_JSON) / 1024
    print(f"  ✅ Database created: {OUTPUT_JSON} ({file_size_kb:.1f} KB)")
    print()

    # Save merge report
    report_lines.extend(all_merge_info)
    save_merge_report(report_file, report_lines)
    print(f"  📋 Merge report saved: {report_file}")
    print()

    # Summary
    print("=" * 80)
    print(f"✅ SUCCESS: {valid_count}/{len(groups)} groups included")
    print(f"   Workers: outer={MAX_OUTER_WORKERS}, inner={MAX_INNER_WORKERS}")
    print()
    print("Next: Run ./run.sh to start the app")
    print("=" * 80)

    return 0

if __name__ == '__main__':
    sys.exit(main())
