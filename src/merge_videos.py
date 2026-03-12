#!/usr/bin/env python3
"""
Merge dashcam videos from a trip into two final files (rear + front).
Concatenates all individual segment videos into complete journey videos.
"""
import os
import glob
import subprocess
from pathlib import Path

def merge_videos(video_list, output_path, camera_type="Rear"):
    """Merge multiple video files using ffmpeg."""

    if not video_list:
        print(f"  ❌ No {camera_type} videos found")
        return False

    # Create concat file for ffmpeg
    concat_file = '/tmp/concat_list.txt'
    with open(concat_file, 'w') as f:
        for video in sorted(video_list):
            # Escape single quotes in path
            escaped_path = video.replace("'", "'\\''")
            f.write(f"file '{escaped_path}'\n")

    print(f"  📝 Processing {len(video_list)} {camera_type} videos...")

    # Merge videos using ffmpeg
    cmd = [
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_file,
        '-c', 'copy',  # Copy codec (no re-encoding, faster)
        '-y',  # Overwrite output file
        output_path
    ]

    try:
        # Run ffmpeg
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode == 0:
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"  ✅ {camera_type} merged: {file_size_mb:.1f} MB")
            return True
        else:
            print(f"  ❌ Error merging {camera_type} videos")
            print(result.stderr[-500:] if result.stderr else "")
            return False

    except subprocess.TimeoutExpired:
        print(f"  ⏱️  Timeout merging {camera_type} videos (taking too long)")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    finally:
        # Clean up concat file
        if os.path.exists(concat_file):
            os.remove(concat_file)

def main():
    """Merge videos for the trip (33-41)."""

    trip_id = "20260307"  # March 7, 2026
    rear_dir = '/Users/fabianosilva/dashcam/DCIM/200video/rear'
    front_dir = '/Users/fabianosilva/dashcam/DCIM/200video/front'
    output_dir = '/Users/fabianosilva/Documentos/code/ddpai_extractor'

    print("🎬 DDpai Video Merger - Merging Dashboard Videos")
    print("=" * 70)
    print(f"\nTrip: {trip_id} (March 7, 2026 - UTC-3)")
    print(f"Duration: 67 minutes (trips 33-41)")
    print("")

    # Find rear videos - these are the 9 videos that make up the merged trip (33-41)
    # Trip IDs: 20260307103136, 20260307103936, 20260307104736, 20260307105536,
    #           20260307110336, 20260307111136, 20260307111936, 20260307112736, 20260307113536
    rear_videos = []
    for ts in ['20260307103136', '20260307103936', '20260307104736', '20260307105536',
               '20260307110336', '20260307111136', '20260307111936', '20260307112736', '20260307113536']:
        pattern = os.path.join(rear_dir, f'{ts}*.mp4')
        matches = sorted(glob.glob(pattern))
        rear_videos.extend(matches)
    rear_videos = sorted(set(rear_videos))  # Remove duplicates and sort

    # Find front videos
    front_videos = []
    for ts in ['20260307103136', '20260307103936', '20260307104736', '20260307105536',
               '20260307110336', '20260307111136', '20260307111936', '20260307112736', '20260307113536']:
        pattern = os.path.join(front_dir, f'{ts}*.mp4')
        matches = sorted(glob.glob(pattern))
        front_videos.extend(matches)
    front_videos = sorted(set(front_videos))  # Remove duplicates and sort

    if not rear_videos and not front_videos:
        print("❌ No videos found matching the trip dates")
        return 1

    print(f"Found {len(rear_videos)} rear camera videos")
    print(f"Found {len(front_videos)} front camera videos")
    print("\n" + "=" * 70)
    print("Merging videos (this may take a few minutes)...\n")

    success_count = 0

    # Merge rear videos
    if rear_videos:
        print("🎥 Merging REAR camera videos...")
        rear_output = os.path.join(output_dir, 'merged_rear_20260307.mp4')
        if merge_videos(rear_videos, rear_output, "Rear"):
            success_count += 1

    # Merge front videos
    if front_videos:
        print("\n🎥 Merging FRONT camera videos...")
        front_output = os.path.join(output_dir, 'merged_front_20260307.mp4')
        if merge_videos(front_videos, front_output, "Front"):
            success_count += 1

    print("\n" + "=" * 70)
    if success_count == 2:
        print("✅ SUCCESS! Both videos merged!")
        print("\nOutput files:")
        print(f"  📹 merged_rear_20260307.mp4  - Full rear camera journey (67 min)")
        print(f"  📹 merged_front_20260307.mp4 - Full front camera journey (67 min)")
        print("\nNext: Update dashboard to use merged videos")
        return 0
    elif success_count == 1:
        print("⚠️  One video merged successfully")
        return 0
    else:
        print("❌ Failed to merge videos")
        return 1

if __name__ == '__main__':
    import sys
    sys.exit(main())
