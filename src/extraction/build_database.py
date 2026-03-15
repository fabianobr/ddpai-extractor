#!/usr/bin/env python3
"""
DDpai Database Builder - Trip & GPS extraction to JSON
Extracts GPS, detects trip groups, validates, merges videos → data/trips.json
"""
import os
import sys
import glob
import json
import tarfile
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# Default Configuration
DEFAULT_WORKING_DIR = '/Users/fabianosilva/Documentos/code/ddpai_extractor/working_data/tar'
DEFAULT_VIDEO_DIR_REAR = '/Users/fabianosilva/dashcam/DCIM/200video/rear'
DEFAULT_VIDEO_DIR_FRONT = '/Users/fabianosilva/dashcam/DCIM/200video/front'
DEFAULT_OUTPUT_DIR = '/Users/fabianosilva/Documentos/code/ddpai_extractor'

# Parse command-line arguments
if len(sys.argv) > 1:
    WORKING_DIR = sys.argv[1]
else:
    WORKING_DIR = DEFAULT_WORKING_DIR

if len(sys.argv) > 2:
    VIDEO_DIR_REAR = sys.argv[2]
else:
    VIDEO_DIR_REAR = DEFAULT_VIDEO_DIR_REAR

if len(sys.argv) > 3:
    VIDEO_DIR_FRONT = sys.argv[3]
else:
    VIDEO_DIR_FRONT = DEFAULT_VIDEO_DIR_FRONT

if len(sys.argv) > 4:
    OUTPUT_DIR = sys.argv[4]
else:
    OUTPUT_DIR = DEFAULT_OUTPUT_DIR

MERGED_VIDEO_DIR = os.path.join(OUTPUT_DIR, 'merged_videos')
OUTPUT_JSON = os.path.join(OUTPUT_DIR, 'data', 'trips.json')

# Group detection
GAP_THRESHOLD = 30 * 60  # 30 minutes in seconds

# Video output quality (re-encoded during merge)
OUTPUT_HEIGHT = 720      # Target height in pixels; width auto-scales to maintain aspect ratio
VIDEO_CRF = 26           # H.264 quality (18=high quality/large, 28=lower quality/small)
VIDEO_PRESET = 'fast'    # Encoding speed (ultrafast, fast, medium, slow)

# ============================================================================
# NMEA Parsing (reused from ddpai_route_improved.py)
# ============================================================================

def parse_nmea_sentence(sentence):
    """Parse NMEA sentence, ignoring checksum."""
    if not sentence.startswith('$'):
        return None

    # Remove checksum part
    if '*' in sentence:
        sentence = sentence[:sentence.index('*')]

    parts = sentence[1:].split(',')
    if len(parts) < 2:
        return None

    sentence_type = parts[0]
    return {'type': sentence_type, 'data': parts[1:]}

def dms_to_decimal(coord_str, direction):
    """Convert DDMM.MMMMM format to decimal degrees."""
    if not coord_str:
        return None

    try:
        if '.' in coord_str:
            dot_pos = coord_str.index('.')
            degrees = int(coord_str[:dot_pos-2])
            minutes = float(coord_str[dot_pos-2:])
        else:
            degrees = int(coord_str[:-7])
            minutes = float(coord_str[-7:])

        decimal = degrees + minutes / 60.0

        if direction in ['S', 'W']:
            decimal = -decimal

        return decimal
    except (ValueError, IndexError):
        return None

def parse_rmc(data):
    """Parse RMC sentence with speed in knots, heading in degrees."""
    if len(data) < 11:
        return None

    try:
        time_str = data[0]
        status = data[1]  # A=active/valid, V=void/invalid
        lat_str = data[2]
        lat_dir = data[3]
        lon_str = data[4]
        lon_dir = data[5]

        if status != 'A' or not lat_str or not lon_str:
            return None

        # Convert coordinates
        lat = dms_to_decimal(lat_str, lat_dir)
        lon = dms_to_decimal(lon_str, lon_dir)

        if lat is None or lon is None:
            return None

        # Speed in knots, heading in degrees
        speed_knots = float(data[6]) if len(data) > 6 and data[6] else 0
        heading = float(data[7]) if len(data) > 7 and data[7] else 0

        return {
            'time': time_str,
            'lat': lat,
            'lon': lon,
            'speed_knots': speed_knots,
            'heading': heading
        }
    except (ValueError, IndexError):
        return None

def parse_gga(data):
    """Parse GGA sentence for altitude and satellite info."""
    if len(data) < 9:
        return None

    try:
        lat_str = data[1]
        lat_dir = data[2]
        lon_str = data[3]
        lon_dir = data[4]
        fix_quality = int(data[5]) if data[5] else 0
        num_satellites = int(data[6]) if data[6] else 0
        hdop = float(data[7]) if data[7] else 0
        altitude = float(data[8]) if data[8] else 0

        if fix_quality == 0:
            return None

        lat = dms_to_decimal(lat_str, lat_dir)
        lon = dms_to_decimal(lon_str, lon_dir)

        if lat is None or lon is None:
            return None

        return {
            'lat': lat,
            'lon': lon,
            'altitude': altitude,
            'num_satellites': num_satellites,
            'hdop': hdop
        }
    except (ValueError, IndexError):
        return None

def extract_gps_from_nmea(nmea_content):
    """Extract GPS points from NMEA text."""
    rmc_points = {}  # keyed by time
    gga_points = {}  # keyed by time

    for line in nmea_content.split('\n'):
        line = line.strip()
        if not line:
            continue

        parsed = parse_nmea_sentence(line)
        if not parsed:
            continue

        sentence_type = parsed['type']

        if sentence_type in ['GPRMC', 'GNRMC']:
            point = parse_rmc(parsed['data'])
            if point:
                rmc_points[point['time']] = point

        elif sentence_type in ['GPGGA', 'GNGGA']:
            point = parse_gga(parsed['data'])
            if point:
                gga_points[point.get('lat')] = point

    return rmc_points, gga_points

def merge_gps_points(rmc_points, gga_points):
    """Merge RMC and GGA points into comprehensive records."""
    points = []

    for time_key, rmc in rmc_points.items():
        lat, lon = rmc['lat'], rmc['lon']

        # Try to find matching GGA data (rough match on coordinates)
        altitude = 0
        for gga in gga_points.values():
            if abs(gga['lat'] - lat) < 0.0001 and abs(gga['lon'] - lon) < 0.0001:
                altitude = gga['altitude']
                break

        speed_kmh = rmc['speed_knots'] * 1.852  # knots to km/h
        heading = rmc['heading']

        points.append({
            'lat': lat,
            'lon': lon,
            'speed_kmh': speed_kmh,
            'altitude': altitude,
            'heading': heading
        })

    return sorted(points, key=lambda p: (p['lat'], p['lon']))

def extract_gps_from_tar(tar_path):
    """Extract all GPS points from tar file."""
    points = []

    try:
        with tarfile.open(tar_path, 'r:') as tar:
            for member in tar.getmembers():
                if member.name.endswith('.gpx'):
                    f = tar.extractfile(member)
                    if f:
                        nmea_content = f.read().decode('utf-8', errors='ignore')
                        rmc, gga = extract_gps_from_nmea(nmea_content)
                        merged = merge_gps_points(rmc, gga)
                        points.extend(merged)
    except Exception as e:
        pass

    return points

# ============================================================================
# Trip Grouping
# ============================================================================

def parse_tar_filename(filename):
    """Parse .git filename to get start time and duration."""
    base = os.path.basename(filename).replace('.git', '')
    parts = base.split('_')

    if len(parts) != 2:
        return None, None

    try:
        timestamp_str = parts[0]  # e.g., 20260307103136
        duration_s = int(parts[1])  # e.g., 0480 = 480 seconds

        # Parse UTC timestamp
        start_utc = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
        end_utc = start_utc + timedelta(seconds=duration_s)

        return start_utc, duration_s
    except ValueError:
        return None, None

def detect_trip_groups(tar_files):
    """Detect trip groups using 30-minute gap threshold."""
    sorted_files = sorted(tar_files)
    groups = []
    current_group = []
    prev_end = None

    for tar_path in sorted_files:
        start_utc, duration_s = parse_tar_filename(tar_path)

        if start_utc is None:
            continue

        end_utc = start_utc + timedelta(seconds=duration_s)

        # Start new group if gap > threshold or first file
        if prev_end is None or (start_utc - prev_end).total_seconds() > GAP_THRESHOLD:
            if current_group:
                groups.append(current_group)
            current_group = [tar_path]
        else:
            current_group.append(tar_path)

        prev_end = end_utc

    if current_group:
        groups.append(current_group)

    return groups

# ============================================================================
# GPS Utilities
# ============================================================================

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in kilometers."""
    from math import radians, cos, sin, asin, sqrt

    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r

def compute_trip_stats(points):
    """Compute distance, duration, speed stats."""
    if len(points) < 2:
        return {
            'distance_km': 0,
            'duration_min': 0,
            'max_speed': 0,
            'avg_speed': 0
        }

    # Distance
    total_distance = 0
    for i in range(len(points) - 1):
        p1, p2 = points[i], points[i+1]
        dist = haversine_distance(p1['lat'], p1['lon'], p2['lat'], p2['lon'])
        total_distance += dist

    # Speed stats
    speeds = [p['speed_kmh'] for p in points if p['speed_kmh'] > 0]
    max_speed = max(speeds) if speeds else 0
    avg_speed = sum(speeds) / len(speeds) if speeds else 0

    # Assume ~1 second between points (rough estimate for duration)
    duration_min = len(points) / 60.0

    return {
        'distance_km': round(total_distance, 2),
        'duration_min': round(duration_min, 1),
        'max_speed': round(max_speed, 1),
        'avg_speed': round(avg_speed, 1)
    }

# ============================================================================
# Video Discovery & Merging
# ============================================================================

def discover_videos(tar_paths, camera='rear'):
    """
    Discover ALL video files that fall within the time range of the TAR group.

    CORRECTED LOGIC:
    1. Get START time from first TAR file
    2. Get END time from last TAR file
    3. Collect ALL videos between START and END
    (Since dashcam creates 1 video per minute, we need to capture the full range)
    """
    video_dir = VIDEO_DIR_REAR if camera == 'rear' else VIDEO_DIR_FRONT
    videos = []
    seen = set()

    if not tar_paths:
        return videos

    # Get START time from first TAR file
    first_start_utc, _ = parse_tar_filename(tar_paths[0])
    if first_start_utc is None:
        return videos

    # Get END time from last TAR file
    last_start_utc, last_duration_s = parse_tar_filename(tar_paths[-1])
    if last_start_utc is None:
        return videos

    last_end_utc = last_start_utc + timedelta(seconds=last_duration_s)

    # Collect ALL video files in the directory
    all_videos = sorted(glob.glob(os.path.join(video_dir, '*_*.mp4')))

    # Filter: keep only videos where timestamp falls within [first_start, last_end]
    for video_path in all_videos:
        filename = os.path.basename(video_path)
        # Extract timestamp: YYYYMMDDHHMMSS from filename
        timestamp_str = filename.split('_')[0]

        try:
            video_utc = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')

            # Include if video timestamp is within trip time range
            if first_start_utc <= video_utc <= last_end_utc:
                if video_path not in seen:
                    videos.append(video_path)
                    seen.add(video_path)
        except ValueError:
            # Skip files with unparseable timestamps
            pass

    return sorted(videos)  # Return in chronological order

def get_video_duration(video_path):
    """Get video duration in seconds using ffprobe (with timeout)."""
    try:
        # Try ffprobe first (faster and more reliable)
        # Use short timeout and don't wait for full probe
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
               '-of', 'default=noprint_wrappers=1:nokey=1:csv=p=0', video_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except subprocess.TimeoutExpired:
        pass  # ffprobe took too long, skip
    except (FileNotFoundError, ValueError):
        pass  # ffprobe not found or invalid output
    except:
        pass

    return None

def get_video_size_mb(video_path):
    """Get video file size in MB."""
    try:
        size_bytes = os.path.getsize(video_path)
        return size_bytes / (1024 * 1024)
    except:
        return None

def merge_videos(video_list, output_path, camera_type='Rear', debug_log=None):
    """Merge multiple video files using ffmpeg with detailed logging."""
    debug_info = []

    if not video_list:
        return False, debug_info

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    sorted_videos = sorted(video_list)

    # Log video details
    debug_info.append(f"\n{'='*80}")
    debug_info.append(f"{camera_type.upper()} CAMERA - Merging {len(sorted_videos)} videos:")
    debug_info.append(f"{'='*80}")

    total_duration = 0
    total_size = 0
    has_duration_info = False
    has_size_info = False

    for idx, video in enumerate(sorted_videos, 1):
        filename = os.path.basename(video)
        size = get_video_size_mb(video)
        duration = get_video_duration(video)

        size_str = f"{size:.1f} MB" if size is not None else "? MB"
        duration_str = f"{duration:.1f}s" if duration is not None else "? s"

        debug_info.append(f"  {idx}. {filename}")
        debug_info.append(f"     Size: {size_str} | Duration: {duration_str}")

        if size is not None:
            total_size += size
            has_size_info = True
        if duration is not None:
            total_duration += duration
            has_duration_info = True

    # Summary line
    debug_info.append(f"\nTotal Videos: {len(sorted_videos)} files")
    if has_size_info:
        debug_info.append(f"Total Size: {total_size:.1f} MB")
    if has_duration_info:
        total_min = int(total_duration / 60)
        debug_info.append(f"Total Duration: {total_duration:.1f}s ({total_min} min)")

    # Remove existing file if it exists (regenerate)
    if os.path.exists(output_path):
        try:
            os.remove(output_path)
            debug_info.append(f"\nRemoving existing file: {os.path.basename(output_path)}")
        except Exception as e:
            debug_info.append(f"\n⚠️  Could not remove existing file: {str(e)}")
            return False, debug_info

    # Create concat file
    concat_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
    try:
        debug_info.append(f"\nConcat list:")
        for idx, video in enumerate(sorted_videos, 1):
            escaped_path = video.replace("'", "'\\''")
            concat_file.write(f"file '{escaped_path}'\n")
            debug_info.append(f"  {idx}. {video}")
        concat_file.close()

        # Run ffmpeg
        debug_info.append(f"\nRunning FFmpeg...")
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file.name,
            '-vf', f'scale=-2:{OUTPUT_HEIGHT}',
            '-c:v', 'libx264',
            '-crf', str(VIDEO_CRF),
            '-preset', VIDEO_PRESET,
            '-c:a', 'aac',
            '-b:a', '128k',
            '-y',
            output_path
        ]

        debug_info.append(f"Command: {' '.join(cmd)}\n")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)

        if result.returncode == 0:
            # Get output file info
            out_size = get_video_size_mb(output_path)
            out_duration = get_video_duration(output_path)

            debug_info.append(f"\n✅ Merge successful!")
            debug_info.append(f"Output: {os.path.basename(output_path)}")

            if out_size or out_duration:
                size_str = f"{out_size:.1f} MB" if out_size else "? MB"
                if out_duration:
                    min_str = f" ({int(out_duration/60)} min)"
                    duration_str = f"{out_duration:.1f}s{min_str}"
                else:
                    duration_str = "? s"
                debug_info.append(f"  → {size_str} | {duration_str}")
            else:
                debug_info.append(f"  (ffprobe not available for details)")

            return True, debug_info
        else:
            debug_info.append(f"\n❌ FFmpeg error:")
            error_msg = result.stderr[-500:] if len(result.stderr) > 500 else result.stderr
            debug_info.append(error_msg)
            return False, debug_info

    except Exception as e:
        debug_info.append(f"❌ Exception: {str(e)}")
        return False, debug_info

    finally:
        if os.path.exists(concat_file.name):
            os.remove(concat_file.name)

# ============================================================================
# Validation
# ============================================================================

def validate_gps(points):
    """Validate GPS data. Returns list of fatal errors."""
    errors = []
    if not points:
        errors.append("No GPS data extracted")
        return errors
    if not any(p['speed_kmh'] > 0 for p in points):
        errors.append("No speed data (all speeds are 0)")
    if not any(p['altitude'] != 0 for p in points):
        errors.append("No altitude data (all altitudes are 0)")
    return errors

def validate_videos(rear_videos, front_videos):
    """Validate video pairs. Returns (has_errors, detailed_warnings_list)."""
    warnings = []
    rear_count = len(rear_videos)
    front_count = len(front_videos)

    if not rear_videos and not front_videos:
        warnings.append("❌ NO VIDEOS FOUND")
        warnings.append("   • Rear: 0 videos")
        warnings.append("   • Front: 0 videos")
        warnings.append("   • Status: No video files in either directory")
        return True, warnings

    if not rear_videos:
        warnings.append("❌ REAR VIDEOS MISSING")
        warnings.append(f"   • Rear: 0 videos")
        warnings.append(f"   • Front: {front_count} videos")
        warnings.append("   • Status: Cannot merge (no rear camera data)")
        return True, warnings

    if not front_videos:
        warnings.append("❌ FRONT VIDEOS MISSING")
        warnings.append(f"   • Rear: {rear_count} videos")
        warnings.append(f"   • Front: 0 videos")
        warnings.append("   • Status: Cannot merge (no front camera data)")
        return True, warnings

    if rear_count != front_count:
        diff = front_count - rear_count
        sign = "+" if diff > 0 else ""
        warnings.append("⚠️  VIDEO COUNT MISMATCH")
        warnings.append(f"   • Rear: {rear_count} videos")
        warnings.append(f"   • Front: {front_count} videos")
        warnings.append(f"   • Difference: {sign}{diff} video(s)")
        warnings.append(f"   • Strategy: Will merge min({rear_count}, {front_count}) = {min(rear_count, front_count)} pairs")
        return True, warnings  # Not fatal - will still merge

    warnings.append(f"✅ VIDEOS OK TO MERGE")
    warnings.append(f"   • Rear: {rear_count} videos")
    warnings.append(f"   • Front: {front_count} videos")
    warnings.append("   • Status: Perfect match, ready for merge")
    return False, warnings

# ============================================================================
# Main
# ============================================================================

def save_merge_report(report_file, report_lines):
    """Save merge report to file."""
    try:
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        with open(report_file, 'w') as f:
            f.write('\n'.join(report_lines))
    except:
        pass

def main():
    print("=" * 80)
    print("🎬 DDpai Database Builder")
    print("=" * 80)
    print()

    # Initialize report
    report_file = os.path.join(OUTPUT_DIR, 'data', 'merge_report.txt')
    report_lines = []
    report_lines.append("VIDEO MERGE DEBUG REPORT")
    report_lines.append("=" * 80)
    report_lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    report_lines.append(f"TAR Directory: {WORKING_DIR}")
    report_lines.append(f"Rear Videos: {VIDEO_DIR_REAR}")
    report_lines.append(f"Front Videos: {VIDEO_DIR_FRONT}")
    report_lines.append(f"Output Directory: {OUTPUT_DIR}")
    report_lines.append("=" * 80)

    # Step 1: Find all .git files
    print("Step 1: Discovering .git archives...")
    tar_files = sorted(glob.glob(os.path.join(WORKING_DIR, '*.git')))
    print(f"  Found {len(tar_files)} archives")
    print()

    # Step 2: Detect trip groups
    print("Step 2: Detecting trip groups (30-min gap threshold)...")
    groups = detect_trip_groups(tar_files)
    print(f"  Detected {len(groups)} trip groups")
    print()

    # Step 3: Process each group
    groups_data = []
    valid_count = 0
    all_merge_info = []

    for group_idx, group in enumerate(groups, 1):
        print(f"Group {group_idx}/{len(groups)}: {len(group)} archives")

        # Get group ID from first archive
        start_utc, _ = parse_tar_filename(group[0])
        group_id = start_utc.strftime('%Y%m%d%H%M%S')
        date_str = start_utc.strftime('%Y-%m-%d')

        print(f"  Group ID: {group_id}")

        # Extract GPS
        print("  📍 Extracting GPS data...")
        all_points = []
        for tar_path in group:
            points = extract_gps_from_tar(tar_path)
            all_points.extend(points)

        if not all_points:
            print(f"  ⚠️  Skipping group {group_id}: No GPS data extracted")
            print()
            continue

        print(f"    → {len(all_points)} points extracted")

        # Discover videos
        print("  🎥 Discovering videos...")
        rear_videos = discover_videos(group, camera='rear')
        front_videos = discover_videos(group, camera='front')
        print(f"    → {len(rear_videos)} rear, {len(front_videos)} front")

        # Validate GPS (mandatory)
        gps_errors = validate_gps(all_points)
        if gps_errors:
            print(f"  ❌ Skipping group {group_id} (GPS validation failed):")
            for err in gps_errors:
                print(f"    • {err}")
            print()
            report_lines.append(f"\nGROUP: {group_id} - SKIPPED (GPS validation failed)")
            for err in gps_errors:
                report_lines.append(f"  • {err}")
            continue

        # Validate videos (optional - warn but continue)
        video_has_errors, video_warnings = validate_videos(rear_videos, front_videos)
        print(f"  🎥 Video Check:")
        for line in video_warnings:
            print(f"     {line}")

        if video_has_errors and not rear_videos and not front_videos:
            print(f"  ⚠️  Skipping group {group_id} (no videos available)")
            print()
            report_lines.append(f"\nGROUP: {group_id} - SKIPPED (no videos)")
            for line in video_warnings:
                report_lines.append(f"  {line}")
            continue

        if video_has_errors and (not rear_videos or not front_videos):
            print(f"  ⚠️  Skipping group {group_id} (missing rear or front videos)")
            print()
            report_lines.append(f"\nGROUP: {group_id} - SKIPPED (missing rear/front)")
            for line in video_warnings:
                report_lines.append(f"  {line}")
            continue

        print(f"  ✅ GPS validation passed - proceeding with video merge")

        # Compute stats
        stats = compute_trip_stats(all_points)
        print(f"    • Distance: {stats['distance_km']} km")
        print(f"    • Duration: {stats['duration_min']} min")
        print(f"    • Max speed: {stats['max_speed']} km/h")
        print(f"    • Avg speed: {stats['avg_speed']} km/h")

        # Merge videos
        print("  🎬 Merging videos...")
        rear_output = os.path.join(MERGED_VIDEO_DIR, f'{group_id}_rear.mp4')
        front_output = os.path.join(MERGED_VIDEO_DIR, f'{group_id}_front.mp4')

        rear_ok, rear_debug = merge_videos(rear_videos, rear_output, 'Rear')
        if rear_debug:
            for line in rear_debug:
                print(line, flush=True)
            all_merge_info.extend(rear_debug)

        front_ok, front_debug = merge_videos(front_videos, front_output, 'Front')
        if front_debug:
            for line in front_debug:
                print(line, flush=True)
            all_merge_info.extend(front_debug)

        if rear_ok and front_ok:
            print(f"    ✅ Merged: {os.path.basename(rear_output)}, {os.path.basename(front_output)}")
        else:
            print(f"  ⚠️  Skipping group {group_id}: Video merge failed")
            print()
            continue

        # Calculate time range
        start_date = datetime.strptime(group_id, '%Y%m%d%H%M%S')
        end_date = start_date + timedelta(minutes=stats['duration_min'])

        label = f"{start_date.strftime('%b %d')} {start_date.strftime('%H:%M')} → {end_date.strftime('%H:%M')}"

        # Prepare points for database (simplified format)
        points_for_db = [
            [p['lat'], p['lon'], p['speed_kmh'], p['altitude'], p['heading']]
            for p in all_points
        ]

        # Add to groups data
        groups_data.append({
            'id': group_id,
            'label': label,
            'date': date_str,
            'duration_min': stats['duration_min'],
            'distance_km': stats['distance_km'],
            'max_speed': stats['max_speed'],
            'avg_speed': stats['avg_speed'],
            'points': points_for_db,
            'video_rear': f'merged_videos/{group_id}_rear.mp4',
            'video_front': f'merged_videos/{group_id}_front.mp4'
        })

        valid_count += 1
        print()

    # Step 4: Write database
    print("Step 3: Writing database...")
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
    print()
    print("📊 Debug Information:")
    print(f"   📋 Merge report: {report_file}")
    print(f"   🎬 Debug script: ./debug_videos.sh")
    print(f"   📊 Video info: ffprobe merged_videos/*.mp4")
    print(f"   📂 File listing: ls -lh merged_videos/")
    print()
    print("Next: Run ./run.sh to start the app")
    print("=" * 80)

    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())
