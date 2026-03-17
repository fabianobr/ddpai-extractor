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
from datetime import datetime, timedelta, timezone, time, date
from collections import defaultdict
import time as time_module

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

# Idle detection configuration
IDLE_SPEED_THRESHOLD = 0.5          # km/h — speed at or below this is considered idle (0.5 tolerance for GPS noise)
IDLE_DURATION_THRESHOLD = 5 * 60    # 300 seconds (5 minutes minimum)

# ============================================================================
# Video Duration Extraction
# ============================================================================

def extract_video_duration(video_path):
    """
    Extract actual video duration using ffprobe.

    Args:
        video_path: Path to video file

    Returns:
        float: Duration in seconds, or None if extraction fails
    """
    if not os.path.exists(video_path):
        return None

    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
        return None
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return None


def validate_video_gps_duration(video_duration_s, gps_duration_s):
    """
    Validate video duration against GPS duration.

    Args:
        video_duration_s: Video duration in seconds (or None if unavailable)
        gps_duration_s: GPS data duration in seconds

    Returns:
        str: "match" | "video_shorter" | "video_longer" | "no_video"
    """
    if video_duration_s is None:
        return "no_video"

    diff_s = abs(video_duration_s - gps_duration_s)

    if diff_s <= 5:
        return "match"
    elif video_duration_s < gps_duration_s:
        return "video_shorter"
    else:
        return "video_longer"


def compute_sparse_timestamps(points, sample_interval=10):
    """
    Compute sparse timestamps at every Nth GPS point.

    Args:
        points: List of GPS points with 'timestamp' field
        sample_interval: Sample every Nth point (default: 10)

    Returns:
        List of dicts: [{"index": 0, "timestamp": "2026-03-14T13:13:46Z"}, ...]
    """
    if not points:
        return []

    sparse = []
    for i in range(0, len(points), sample_interval):
        if i < len(points):
            timestamp = points[i].get('timestamp')
            if isinstance(timestamp, datetime):
                sparse.append({
                    'index': i,
                    'timestamp': timestamp.isoformat()
                })

    return sparse

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

def detect_idle_segments(points, speed_threshold=None, duration_threshold=None):
    """
    Detect continuous idle periods (low speed) in GPS points.

    Args:
        points: List of dicts with 'speed_kmh' and 'timestamp' keys
        speed_threshold: Speed threshold in km/h (default: IDLE_SPEED_THRESHOLD)
        duration_threshold: Minimum idle duration in seconds (default: IDLE_DURATION_THRESHOLD)

    Returns:
        List of idle segment dicts: {start_index, end_index, duration_s, distance_km, points: [...]}
    """
    if speed_threshold is None:
        speed_threshold = IDLE_SPEED_THRESHOLD
    if duration_threshold is None:
        duration_threshold = IDLE_DURATION_THRESHOLD

    if not points:
        return []

    idle_segments = []
    in_idle = False
    idle_start_idx = None

    for i, point in enumerate(points):
        speed = point.get('speed_kmh', 0.0)

        if speed <= speed_threshold:
            # Point is in idle range
            if not in_idle:
                # Start of a new idle period
                in_idle = True
                idle_start_idx = i
        else:
            # Point is above idle threshold
            if in_idle:
                # End of idle period - check if duration meets threshold
                idle_end_idx = i - 1
                idle_points = points[idle_start_idx:idle_end_idx + 1]

                # Calculate duration from first and last timestamp (convert to seconds)
                end_time = idle_points[-1].get('timestamp')
                start_time = idle_points[0].get('timestamp')
                if end_time and start_time:
                    duration_s = (end_time - start_time).total_seconds()
                else:
                    duration_s = 0

                if duration_s >= duration_threshold:
                    # Calculate distance traveled during idle period
                    distance_km = sum([p.get('distance_km', 0) for p in idle_points])

                    idle_segments.append({
                        'start_index': idle_start_idx,
                        'end_index': idle_end_idx,
                        'duration_s': duration_s,
                        'distance_km': round(distance_km, 2),
                        'points': idle_points
                    })

                in_idle = False
                idle_start_idx = None

    # Handle case where trip ends while idle
    if in_idle and idle_start_idx is not None:
        idle_end_idx = len(points) - 1
        idle_points = points[idle_start_idx:idle_end_idx + 1]
        # Calculate duration from first and last timestamp (convert to seconds)
        end_time = idle_points[-1].get('timestamp')
        start_time = idle_points[0].get('timestamp')
        if end_time and start_time:
            duration_s = (end_time - start_time).total_seconds()
        else:
            duration_s = 0

        if duration_s >= duration_threshold:
            distance_km = sum([p.get('distance_km', 0) for p in idle_points])

            idle_segments.append({
                'start_index': idle_start_idx,
                'end_index': idle_end_idx,
                'duration_s': duration_s,
                'distance_km': round(distance_km, 2),
                'points': idle_points
            })

    return idle_segments

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

def merge_gps_points(rmc_points, gga_points, tar_date=None):
    """Merge RMC and GGA points into comprehensive records.

    Args:
        rmc_points: Dict of RMC GPS records
        gga_points: Dict of GGA GPS records
        tar_date: datetime.date object for timestamp (e.g., from TAR filename)
    """
    if tar_date is None:
        tar_date = datetime.now().date()

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

        # Parse timestamp from time_key (format: HHMMSS) with actual date
        try:
            if len(time_key) >= 6:
                hour = int(time_key[0:2])
                minute = int(time_key[2:4])
                second = int(time_key[4:6])
                # Use actual date from tar_date parameter
                timestamp = datetime.combine(tar_date, time(hour, minute, second))
            else:
                timestamp = None
        except (ValueError, IndexError):
            timestamp = None

        points.append({
            'lat': lat,
            'lon': lon,
            'speed_kmh': speed_kmh,
            'altitude': altitude,
            'heading': heading,
            'timestamp': timestamp if timestamp else datetime.now()
        })

    return sorted(points, key=lambda p: (p['lat'], p['lon']))

def extract_gps_from_tar(tar_path):
    """Extract all GPS points from tar file."""
    points = []

    # Extract date from TAR filename (e.g., 20260314060147 → 2026-03-14)
    tar_basename = os.path.basename(tar_path).replace('.git', '')
    tar_date = None
    try:
        if len(tar_basename) >= 8:
            date_str = tar_basename[:8]  # YYYYMMDD
            tar_date = datetime.strptime(date_str, '%Y%m%d').date()
    except ValueError:
        tar_date = None

    try:
        with tarfile.open(tar_path, 'r:') as tar:
            for member in tar.getmembers():
                if member.name.endswith('.gpx'):
                    f = tar.extractfile(member)
                    if f:
                        nmea_content = f.read().decode('utf-8', errors='ignore')
                        rmc, gga = extract_gps_from_nmea(nmea_content)
                        # Pass tar_date to merge_gps_points for correct timestamps
                        merged = merge_gps_points(rmc, gga, tar_date=tar_date)
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

def is_parking_file(tar_path):
    """
    Hybrid parking detection: Classifies TAR file as parking or driving.
    Returns True if parking, False if driving.
    Uses: distance < 0.6 km OR avg_speed < 3.0 km/h (either indicates parked)

    Refined thresholds (from ground truth analysis):
    - Original: distance < 0.1 km OR avg_speed < 1.5 km/h
    - Issue: File 18:01 BRT (0.57 km, 3.3 km/h) was wrongly classified as DRIVING
    - Fix: Increased both thresholds to catch edge cases during parking transitions
    """
    points = extract_gps_from_tar(tar_path)
    if not points or len(points) < 2:
        return True  # Assume parking if no GPS data

    stats = compute_trip_stats(points)
    distance = stats['distance_km']
    avg_speed = stats['avg_speed']

    # Hybrid detection: parking if EITHER condition is true
    # - distance < 0.6 km: catches short-distance parking/GPS drift
    # - avg_speed < 3.0 km/h: catches stationary or crawling (parking lot speed)
    is_parking = (distance < 0.6) or (avg_speed < 3.0)
    return is_parking


def detect_trip_groups(tar_files, verbose=False):
    """
    Detect trip groups using 30-minute gap threshold.
    Pre-filters parking files via is_parking_file() (distance < 0.6 km OR avg_speed < 3.0 km/h) before grouping.
    Returns (groups, gap_info, parking_files).
    """
    sorted_files = sorted(tar_files)
    groups = []
    current_group = []
    prev_end = None
    gaps = []  # Track gaps between groups
    parking_files = []  # Track filtered parking files

    for tar_path in sorted_files:
        start_utc, duration_s = parse_tar_filename(tar_path)

        if start_utc is None:
            continue

        # Pre-filter: Skip parking files
        if is_parking_file(tar_path):
            parking_files.append(tar_path)
            continue

        end_utc = start_utc + timedelta(seconds=duration_s)

        # Start new group if gap > threshold or first file
        gap_seconds = (start_utc - prev_end).total_seconds() if prev_end else None
        if prev_end is None or gap_seconds > GAP_THRESHOLD:
            if current_group:
                groups.append(current_group)
                if gap_seconds:
                    gaps.append({
                        'gap_minutes': round(gap_seconds / 60, 1),
                        'between': f"{os.path.basename(current_group[-1])} → {os.path.basename(tar_path)}"
                    })
            current_group = [tar_path]
        else:
            current_group.append(tar_path)

        prev_end = end_utc

    if current_group:
        groups.append(current_group)

    return groups, gaps, parking_files


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

def discover_videos(tar_paths, camera='rear', limit_count=None):
    """
    Discover ALL video files that fall within the time range of the TAR group.

    If limit_count is provided, return only the first limit_count videos.

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

    videos = sorted(videos)  # Return in chronological order

    if limit_count is not None and len(videos) > limit_count:
        return videos[:limit_count]

    return videos

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

def validate_video_output(output_path, expected_duration=None):
    """Validate video output file. Returns (success: bool, message: str)."""
    # Check file exists and has content
    if not os.path.exists(output_path):
        return False, f"Output file not created: {output_path}"

    file_size = os.path.getsize(output_path)
    if file_size < 1000:
        return False, f"Output file too small ({file_size} bytes): {output_path}"

    # Optional: check duration if expected_duration provided
    if expected_duration is not None:
        actual_duration = get_video_duration(output_path)
        if actual_duration is not None:
            # Allow 5% tolerance
            tolerance = expected_duration * 0.05
            if abs(actual_duration - expected_duration) > tolerance:
                return False, (f"Duration mismatch: expected {expected_duration:.1f}s, "
                             f"got {actual_duration:.1f}s (> 5% tolerance)")

    return True, f"Output file valid: {os.path.basename(output_path)} ({file_size / (1024*1024):.1f} MB)"

def calculate_eta(elapsed_seconds, bytes_processed, total_bytes):
    """
    Calculate estimated time remaining based on current processing rate.

    Args:
        elapsed_seconds: Time elapsed so far
        bytes_processed: Bytes processed so far
        total_bytes: Total bytes to process

    Returns:
        (estimated_seconds, estimated_minutes) or (None, None) if can't estimate
    """
    if elapsed_seconds <= 0 or bytes_processed <= 0:
        return None, None

    try:
        bytes_per_second = bytes_processed / elapsed_seconds
        remaining_bytes = total_bytes - bytes_processed

        if remaining_bytes <= 0:
            return 0, 0

        estimated_remaining = remaining_bytes / bytes_per_second
        estimated_total = elapsed_seconds + estimated_remaining
        estimated_minutes = estimated_total / 60

        return estimated_total, estimated_minutes
    except (ZeroDivisionError, TypeError):
        return None, None


def format_retry_message(attempt, current_timeout, new_timeout, total_size, file_count):
    """
    Format console message for timeout retry event.

    Args:
        attempt: Retry attempt number (1, 2, etc.)
        current_timeout: Current timeout in seconds
        new_timeout: New timeout in seconds
        total_size: Total input size in MB
        file_count: Number of video files

    Returns:
        Formatted message string
    """
    percent_increase = int(((new_timeout - current_timeout) / current_timeout) * 100)
    message = f"⏱️  TIMEOUT: Stream copy exceeded {current_timeout}s limit\n"
    message += f"  → Input: {file_count} files, {total_size:.1f} GB total\n"
    message += f"  → Retrying with {new_timeout}s timeout ({percent_increase}% increase)...\n"
    return message


def format_failure_message(max_timeout, tier1_timeout, tier2_timeout, tier3_timeout):
    """
    Format console message for timeout failure (all retries exhausted).

    Args:
        max_timeout: Final timeout value reached
        tier1_timeout: Initial timeout (Tier 1)
        tier2_timeout: First retry timeout (Tier 2)
        tier3_timeout: Second retry timeout (Tier 3)

    Returns:
        Formatted message string
    """
    message = f"❌ FAILED: Stream copy timed out after 2 retries (final limit: {max_timeout}s)\n"
    message += f"  → All 3 attempts exhausted: {tier1_timeout}s → {tier2_timeout}s → {tier3_timeout}s\n"
    message += f"  → Suggestions:\n"
    message += f"    1. Retry with re-encoding: use_stream_copy=False\n"
    message += f"    2. Split large groups: merge manually in smaller batches\n"
    message += f"    3. Check system resources: CPU/disk I/O may be constrained\n"
    return message

def merge_videos(video_list, output_path, camera_type='Rear', debug_log=None, use_stream_copy=True):
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

        # Run ffmpeg with stream copy or re-encoding
        merge_method = "stream copy" if use_stream_copy else "H.264 re-encoding"

        # Dynamic timeout: 1 second per 10 MB of input (≈10 MB/s conservative USB read speed)
        # Min 300s for small groups; no cap — front camera 48-file groups reach 7+ GB
        if use_stream_copy:
            timeout_seconds = max(300, int(total_size / 10) + 120) if has_size_info else 1800
        else:
            timeout_seconds = 1800

        debug_info.append(f"\nRunning FFmpeg ({merge_method})...")
        debug_info.append(f"Timeout: {timeout_seconds}s (based on {total_size:.0f} MB input)")

        # Build FFmpeg command
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file.name,
        ]

        if use_stream_copy:
            # Stream copy: fast, no re-encoding
            cmd.extend(['-c:v', 'copy', '-c:a', 'copy', '-y', output_path])
        else:
            # H.264 re-encoding: slower, compressed
            cmd.extend([
                '-vf', f'scale=-2:{OUTPUT_HEIGHT}',
                '-c:v', 'libx264',
                '-crf', str(VIDEO_CRF),
                '-preset', VIDEO_PRESET,
                '-c:a', 'aac',
                '-b:a', '128k',
                '-y',
                output_path
            ])

        debug_info.append(f"Command: {' '.join(cmd)}\n")

        # Retry loop: up to 2 retries on timeout
        max_retries = 2
        retry_attempt = 0
        tier_timeouts = [timeout_seconds]  # Track all timeout values for logging
        start_time = time_module.time()

        while retry_attempt <= max_retries:
            attempt_number = retry_attempt + 1
            debug_info.append(f"Attempt {attempt_number}/3: timeout={timeout_seconds}s\n")

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)

                # Success or non-timeout error — handle normally
                if result.returncode == 0:
                    # Validate output file
                    is_valid, validation_msg = validate_video_output(output_path, total_duration if has_duration_info else None)

                    if is_valid:
                        # Get output file info
                        out_size = get_video_size_mb(output_path)
                        out_duration = get_video_duration(output_path)

                        if retry_attempt > 0:
                            elapsed_time = int(time_module.time() - start_time)
                            debug_info.append(f"\n✅ Merge successful on retry! Completed in {elapsed_time}s")
                        else:
                            debug_info.append(f"\n✅ Merge successful ({merge_method})!")

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
                        debug_info.append(f"\n⚠️  Output validation failed: {validation_msg}")
                        # If stream copy failed, try re-encoding as fallback
                        if use_stream_copy:
                            debug_info.append(f"Falling back to H.264 re-encoding...")
                            # Clean up invalid output
                            if os.path.exists(output_path):
                                try:
                                    os.remove(output_path)
                                except:
                                    pass
                            # Recursively call with re-encoding
                            return merge_videos(video_list, output_path, camera_type, debug_log, use_stream_copy=False)
                        else:
                            return False, debug_info
                else:
                    # Non-zero return code (FFmpeg error, not timeout)
                    debug_info.append(f"\n❌ FFmpeg error ({merge_method}):")
                    error_msg = result.stderr[-500:] if len(result.stderr) > 500 else result.stderr
                    debug_info.append(error_msg)

                    # If stream copy failed, try re-encoding as fallback
                    if use_stream_copy:
                        debug_info.append(f"\nFalling back to H.264 re-encoding...")
                        # Clean up failed output
                        if os.path.exists(output_path):
                            try:
                                os.remove(output_path)
                            except:
                                pass
                        # Recursively call with re-encoding
                        return merge_videos(video_list, output_path, camera_type, debug_log, use_stream_copy=False)
                    else:
                        return False, debug_info

            except subprocess.TimeoutExpired as e:
                # Timeout — try to retry (if retries remaining)
                elapsed_time = int(time_module.time() - start_time)

                if retry_attempt < max_retries:
                    # Calculate new timeout (50% increase)
                    new_timeout = int(timeout_seconds * 1.5)

                    # Print retry message to console
                    retry_msg = format_retry_message(retry_attempt + 1, timeout_seconds, new_timeout, total_size / 1024, len(sorted_videos))
                    print(retry_msg)
                    debug_info.append(retry_msg)
                    debug_info.append(f"  [Retry {retry_attempt + 1}/2] Merging...\n")

                    # Update timeout for next iteration
                    timeout_seconds = new_timeout
                    tier_timeouts.append(timeout_seconds)
                    retry_attempt += 1

                    # Clean up partial output
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except:
                            pass

                    # Continue to next retry attempt
                    continue
                else:
                    # All retries exhausted
                    debug_info.append(f"\n❌ FAILED: Stream copy timed out after 2 retries (final limit: {timeout_seconds}s)\n")
                    debug_info.append(f"  → Elapsed across all attempts: {elapsed_time}s\n")

                    # Print failure message to console
                    tier1 = tier_timeouts[0] if len(tier_timeouts) > 0 else '?'
                    tier2 = tier_timeouts[1] if len(tier_timeouts) > 1 else '?'
                    tier3 = tier_timeouts[2] if len(tier_timeouts) > 2 else '?'
                    failure_msg = format_failure_message(timeout_seconds, tier1, tier2, tier3)
                    print(failure_msg)
                    debug_info.append(failure_msg)

                    # Clean up failed output
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except:
                            pass

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
    print("Step 2: Detecting trip groups (30-min gap threshold + hybrid parking detection)...")
    groups, gaps, parking_files = detect_trip_groups(tar_files)
    print(f"  Detected {len(groups)} driving trip groups by time gap")
    print(f"  Filtered {len(parking_files)} parking TAR files (distance < 0.6km OR avg_speed < 3.0 km/h)")
    print()

    # Show detailed info for each driving group
    print(f"  📊 DRIVING TRIP GROUPS (Time gaps indicate parking periods):")
    print(f"  {'Grp':<4} {'Start Time':<20} {'End Time':<20} {'Files':<6} {'Distance':<12} {'Duration':<12} {'Max Speed':<12} {'Mode':<12}")
    print(f"  {'-'*124}")

    for group_idx, group in enumerate(groups, 1):
        first_start, first_dur = parse_tar_filename(group[0])
        last_tar = group[-1]
        last_start, last_dur = parse_tar_filename(last_tar)

        if first_start and last_start and last_dur:
            last_end = last_start + timedelta(seconds=last_dur)

            # Extract GPS to get stats
            all_group_points = []
            for tar_path in group:
                points = extract_gps_from_tar(tar_path)
                all_group_points.extend(points)

            if all_group_points:
                stats = compute_trip_stats(all_group_points)
                distance = stats['distance_km']
                duration = stats['duration_min']
                max_speed = stats['max_speed']
            else:
                distance = 0
                duration = 0
                max_speed = 0

            start_str = first_start.strftime('%Y-%m-%d %H:%M:%S')
            end_str = last_end.strftime('%H:%M:%S')
            mode = "🚗 DRIVING"

            print(f"  {group_idx:<4} {start_str:<20} {end_str:<20} {len(group):<6} {distance:>10.2f}km {duration:>10.1f}min {max_speed:>10.1f}km/h {mode:<12}")

    # Show parking periods (time gaps)
    if gaps:
        print(f"\n  ⏱️  PARKING PERIODS (Time gaps >30min between driving groups):")
        print(f"  {'#':<4} {'Between Files':<50} {'Duration':<12} {'Mode':<12}")
        print(f"  {'-'*90}")

        for gap_idx, gap in enumerate(gaps, 1):
            gap_minutes = gap['gap_minutes']
            between_str = gap['between']
            print(f"  {gap_idx:<4} {between_str:<50} {gap_minutes:>10.0f}min 🅿️ PARKING")
    else:
        print(f"\n  ℹ️  No time gaps >30min detected")

    print(f"\n  📊 Result: {len(groups)} driving trip groups ({len(parking_files)} parking files excluded from processing)")
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

        print(f"  ✅ GPS validation passed - proceeding with video merge")

        # Compute stats
        stats = compute_trip_stats(all_points)
        print(f"    • Distance: {stats['distance_km']} km")
        print(f"    • Duration: {stats['duration_min']} min")
        print(f"    • Max speed: {stats['max_speed']} km/h")
        print(f"    • Avg speed: {stats['avg_speed']} km/h")

        # Initialize video merge status variables (will be updated below)
        rear_ok = False
        front_ok = False
        video_status = "no_videos"
        video_notes = "No video files found for either camera"

        # Smart video merge: implement min() count strategy
        print("  🎬 Smart merge strategy...")
        rear_count = len(rear_videos)
        front_count = len(front_videos)

        if rear_count > 0 and front_count > 0:
            # Both cameras have videos: use min() to ensure sync
            merge_count = min(rear_count, front_count)

            if rear_count != front_count:
                # Count mismatch - log explicitly
                ignored_count = abs(rear_count - front_count)
                print(f"    ⚠️  VIDEO COUNT MISMATCH: {rear_count} rear vs {front_count} front")
                print(f"       Merge strategy: Using min({rear_count}, {front_count}) = {merge_count} pairs")
                print(f"       Will ignore: {ignored_count} extra video(s)")

                # Rediscover with limit to get only the pairs we'll merge
                rear_videos = discover_videos(group, camera='rear', limit_count=merge_count)
                front_videos = discover_videos(group, camera='front', limit_count=merge_count)
            else:
                print(f"    ✅ Both cameras matched: {merge_count} pairs ready for merge")

            # Merge the limited video lists
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

            # Determine merge status and notes
            if rear_ok and front_ok:
                if rear_count != front_count:
                    extra_count = abs(rear_count - front_count)
                    video_status = "ok_with_extras"
                    video_notes = f"Merged {merge_count} rear + {merge_count} front videos ({extra_count} extra video(s) ignored)"
                    print(f"    ✅ Merged: {os.path.basename(rear_output)}, {os.path.basename(front_output)}")
                    print(f"       ({merge_count} pairs, {extra_count} extra video(s) ignored)")
                else:
                    video_status = "ok"
                    video_notes = f"Merged {merge_count} rear + {merge_count} front videos successfully"
                    print(f"    ✅ Merged: {os.path.basename(rear_output)}, {os.path.basename(front_output)}")
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

                print(f"  ⚠️  Video merge failed for group {group_id}, but GPS data is valid")
                print(f"     Status: {video_status}")
                print(f"     Note: {video_notes}")

        elif rear_count > 0 and front_count == 0:
            # Only rear videos - record as partial
            video_status = "no_front"
            video_notes = f"Only rear videos available ({rear_count} rear, 0 front)"
            print(f"  ⚠️  No front videos for group {group_id} ({rear_count} rear available), but GPS data is valid")

        elif front_count > 0 and rear_count == 0:
            # Only front videos - record as partial
            video_status = "no_rear"
            video_notes = f"Only front videos available (0 rear, {front_count} front)"
            print(f"  ⚠️  No rear videos for group {group_id} ({front_count} front available), but GPS data is valid")

        else:
            # No videos at all - but GPS is valid so we include the trip
            video_status = "no_videos"
            video_notes = "No video files found for either camera"
            print(f"  ⚠️  No videos for group {group_id}, but GPS data is valid")

        # Calculate time range
        start_date = datetime.strptime(group_id, '%Y%m%d%H%M%S')
        end_date = start_date + timedelta(minutes=stats['duration_min'])

        label = f"{start_date.strftime('%b %d')} {start_date.strftime('%H:%M')} → {end_date.strftime('%H:%M')}"

        # Prepare points for database (simplified format)
        points_for_db = [
            [p['lat'], p['lon'], p['speed_kmh'], p['altitude'], p['heading']]
            for p in all_points
        ]

        # Build video paths based on merge success
        video_rear_path = f'merged_videos/{group_id}_rear.mp4' if rear_ok else None
        video_front_path = f'merged_videos/{group_id}_front.mp4' if front_ok else None

        # Add idle segment detection
        idle_segments = detect_idle_segments(all_points)

        # Convert idle_segments to JSON-serializable format (remove 'points' key for output)
        idle_segments_json = []
        for seg in idle_segments:
            idle_segments_json.append({
                'start_index': seg['start_index'],
                'end_index': seg['end_index'],
                'duration_s': seg['duration_s'],
                'distance_km': seg['distance_km'],
            })

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
            'video_rear': video_rear_path,
            'video_front': video_front_path,
            'video_status': video_status,
            'video_notes': video_notes,
            'idle_segments': idle_segments_json
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
