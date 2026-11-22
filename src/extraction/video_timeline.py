"""Map GPS samples to the actual concatenation of dashcam segments.

GPS uses its own UTC clock; filenames use the camera clock. We estimate the
clock difference from GPS records and their containing one-minute files, then
associate each record only with the matching video segment. Missing metadata
produces nulls instead of an invented position.
"""
import math
from datetime import datetime
from collections import defaultdict
from statistics import median
from pathlib import Path


def segment_key(path):
    name = Path(path).name.split('_')[0]
    try:
        return datetime.strptime(name, '%Y%m%d%H%M%S')
    except ValueError:
        return None


# Confidence thresholds for the GPS/camera clock calibration. Spread is a deviation of
# per-segment offsets from the median. Filenames only have 1 s resolution, so about
# 1 s is rounding noise. Calibrated on real 2026-11-21 data: 95-97% of segments agree
# within 1 s, the rest are late first fixes (+5..+28 s). Earlier versions also saw
# -1400..-1600 s deviations; those were stale buffer residue (duplicated points with a
# backwards timestamp), now discarded at extraction. A few segments keep a small
# negative deviation (-1..-5 s) because their first fix is a boundary point recorded
# just before the video starts. Confidence therefore uses the typical spread, ignoring
# the worst OUTLIER_FRACTION of segments (a no-op below 20 segments); the maximum is
# still reported as offset_spread_s.
HIGH_CONFIDENCE_MAX_SPREAD_S = 1.0
MEDIUM_CONFIDENCE_MAX_SPREAD_S = 3.0
HIGH_CONFIDENCE_MIN_SAMPLES = 5
OUTLIER_FRACTION = 0.05


def classify_confidence(spread, samples):
    if not samples or spread is None or spread > MEDIUM_CONFIDENCE_MAX_SPREAD_S:
        return 'low'
    if spread <= HIGH_CONFIDENCE_MAX_SPREAD_S and samples >= HIGH_CONFIDENCE_MIN_SAMPLES:
        return 'high'
    return 'medium'


def estimate_clock_calibration(points):
    """Median clock offset plus how consistent the per-segment offsets are.

    The offset value is the median of (first GPS fix of a segment - segment start in
    the filename). The spread fields and confidence only describe how much to trust it.
    """
    starts = {}
    for p in points:
        segment = p.get('camera_segment')
        timestamp = p.get('timestamp')
        camera_start = segment_key(segment or '')
        if camera_start is None or not isinstance(timestamp, datetime):
            continue
        if segment not in starts or timestamp < starts[segment][0]:
            starts[segment] = (timestamp, camera_start)
    offsets = [(stamp - camera).total_seconds() for stamp, camera in starts.values()]
    if not offsets:
        return {'offset_s': None, 'offset_spread_s': None, 'offset_typical_spread_s': None,
                'offset_outlier_segments': 0, 'offset_samples': 0, 'confidence': 'low'}
    # Most files start with a GPS fix; a few begin late or have no fix.
    # The median resists these outliers. NMEA dates, not filename dates, handle UTC midnight.
    offset = median(offsets)
    deviations = sorted(abs(value - offset) for value in offsets)
    keep = math.ceil(len(deviations) * (1 - OUTLIER_FRACTION))
    typical = deviations[keep - 1]
    return {'offset_s': offset, 'offset_spread_s': round(deviations[-1], 3),
            'offset_typical_spread_s': round(typical, 3),
            'offset_outlier_segments': sum(d > MEDIUM_CONFIDENCE_MAX_SPREAD_S for d in deviations),
            'offset_samples': len(offsets), 'confidence': classify_confidence(typical, len(offsets))}


def estimate_clock_offset(points):
    return estimate_clock_calibration(points)['offset_s']


_EPOCH = datetime(1970, 1, 1)
# Tolerance at the START of a video window when matching a point by time. Filenames have
# 1 s resolution, so half a second absorbs rounding without covering real gaps of 1-2 s.
# The end is exclusive: the instant a video ends belongs to the next video, if any.
WINDOW_MATCH_TOLERANCE_S = 0.5


def _locate_in_windows(windows, camera_seconds):
    """Concatenated-video position for a camera-clock time, or None if no window has it."""
    for camera, start, duration in windows:
        inside = camera_seconds - (camera - _EPOCH).total_seconds()
        if inside < -WINDOW_MATCH_TOLERANCE_S:
            break  # windows are sorted by start; none of the later ones can contain it
        if inside < duration:
            return start + max(inside, 0.0)
    return None


def build_video_sync(points, rear_videos, front_videos, duration_fn):
    calibration = estimate_clock_calibration(points)
    offset = calibration['offset_s']

    def map_camera(paths):
        segments = {}
        elapsed = 0.0
        complete = True
        for path in sorted(paths):
            key = segment_key(path)
            duration = duration_fn(path)
            if key is None or duration is None or duration <= 0:
                complete = False
                # All following offsets are unknown if a segment duration is unknown.
                break
            segments[key.strftime('%Y%m%d%H%M%S')] = (elapsed, duration, key)
            elapsed += duration
        windows = sorted((camera, start, duration) for start, duration, camera in segments.values())
        values = []
        for point in points:
            stamp = point.get('timestamp')
            if offset is None or not isinstance(stamp, datetime):
                values.append(None)
                continue
            value = None
            record = segments.get(point.get('camera_segment'))
            if record is not None:
                start, duration, camera = record
                inside = (stamp - camera).total_seconds() - offset
                if 0 <= inside <= duration:
                    value = start + inside
            if value is None:
                # Boundary points can belong to the .gpx of the next video while their
                # moment is still inside the previous video: look for the window that
                # contains the camera-clock time. No window means no video coverage.
                value = _locate_in_windows(windows, (stamp - _EPOCH).total_seconds() - offset)
            values.append(None if value is None else round(value, 3))
        return values, complete, elapsed

    rear, rear_complete, rear_duration = map_camera(rear_videos)
    front, front_complete, front_duration = map_camera(front_videos)
    available = [x for x in rear + front if x is not None]
    status = 'unavailable' if not available else ('ok' if all(x is not None for x in rear + front) and rear_complete and front_complete else 'partial')
    return {'rear': rear, 'front': front, 'status': status, 'clock_offset_s': offset,
            'rear_source_duration_s': round(rear_duration, 3),
            'front_source_duration_s': round(front_duration, 3),
            'offset_spread_s': calibration['offset_spread_s'],
            'offset_typical_spread_s': calibration['offset_typical_spread_s'],
            'offset_outlier_segments': calibration['offset_outlier_segments'],
            'offset_samples': calibration['offset_samples'],
            'confidence': calibration['confidence']}
