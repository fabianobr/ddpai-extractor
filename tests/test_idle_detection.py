# tests/test_idle_detection.py
"""
Tests for idle detection with proper GPS data structure.
Run: python3 -m pytest tests/test_idle_detection.py -v
"""
import unittest
from datetime import datetime, timedelta
from src.extraction.build_database import (
    detect_idle_segments,
    merge_gps_points
)


class TestDetectIdleSegments(unittest.TestCase):
    """Test idle detection with proper GPS data structure."""

    def test_all_moving_no_idle(self):
        """No idle segments when all points have speed > threshold."""
        points = [
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 0, 0)},
            {'speed_kmh': 55, 'timestamp': datetime(2026, 3, 14, 6, 0, 10)},
            {'speed_kmh': 60, 'timestamp': datetime(2026, 3, 14, 6, 0, 20)},
        ]

        segments = detect_idle_segments(points, speed_threshold=0.5, duration_threshold=60)
        self.assertEqual(len(segments), 0, "No idle segments expected when all speeds > threshold")

    def test_short_idle_below_threshold(self):
        """Ignore idle periods shorter than duration_threshold."""
        points = [
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 0, 0)},
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 0, 30)},
            {'speed_kmh': 0.2, 'timestamp': datetime(2026, 3, 14, 6, 1, 0)},  # Idle 10 sec
            {'speed_kmh': 0.3, 'timestamp': datetime(2026, 3, 14, 6, 1, 10)},
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 1, 20)},
        ]

        segments = detect_idle_segments(points, speed_threshold=0.5, duration_threshold=60)
        self.assertEqual(len(segments), 0, "Idle segment <60s should be ignored")

    def test_long_idle_detected(self):
        """Detect idle periods longer than duration_threshold."""
        # 5 minutes of idle (moving slow)
        from datetime import timedelta
        points = [
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 0, 0)},
        ]
        # Add 300 seconds of idle points
        start_ts = datetime(2026, 3, 14, 6, 1, 0)
        for i in range(1, 300):
            points.append({
                'speed_kmh': 0.2 + (i % 2) * 0.1,
                'timestamp': start_ts + timedelta(seconds=i)
            })
        points.append({'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 6, 0)})

        segments = detect_idle_segments(points, speed_threshold=0.5, duration_threshold=60)
        self.assertGreaterEqual(len(segments), 1, "Expected at least 1 idle segment")
        self.assertGreaterEqual(segments[0]['duration_s'], 200, "Idle duration should be ~300s")

    def test_idle_duration_is_float_seconds(self):
        """Verify idle segment duration is a number (seconds), not timedelta."""
        points = [
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 0, 0)},
            {'speed_kmh': 0.2, 'timestamp': datetime(2026, 3, 14, 6, 1, 0)},
            {'speed_kmh': 0.2, 'timestamp': datetime(2026, 3, 14, 6, 2, 0)},
            {'speed_kmh': 0.2, 'timestamp': datetime(2026, 3, 14, 6, 3, 0)},
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 4, 0)},
        ]

        segments = detect_idle_segments(points, speed_threshold=0.5, duration_threshold=60)
        self.assertEqual(len(segments), 1, "Expected 1 idle segment")

        # CRITICAL: duration_s must be a number, not timedelta
        self.assertIsInstance(segments[0]['duration_s'], (int, float),
                             "duration_s must be int or float, not timedelta")
        self.assertGreater(segments[0]['duration_s'], 100, "Duration should be > 100 seconds")

    def test_idle_segment_has_required_fields(self):
        """Idle segment must have all required fields for JSON output."""
        points = [
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 0, 0)},
            {'speed_kmh': 0.2, 'timestamp': datetime(2026, 3, 14, 6, 1, 0)},
            {'speed_kmh': 0.2, 'timestamp': datetime(2026, 3, 14, 6, 2, 0)},
            {'speed_kmh': 0.2, 'timestamp': datetime(2026, 3, 14, 6, 3, 0)},
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 4, 0)},
        ]

        segments = detect_idle_segments(points, speed_threshold=0.5, duration_threshold=60)
        self.assertGreater(len(segments), 0)

        seg = segments[0]
        required_fields = ['start_index', 'end_index', 'duration_s', 'distance_km']
        for field in required_fields:
            self.assertIn(field, seg, f"Idle segment missing required field: {field}")


class TestMergeGpsPointsTimestamp(unittest.TestCase):
    """Test GPS point merging preserves and creates proper timestamps."""

    def test_timestamp_is_datetime_object(self):
        """Timestamps should be datetime objects, not strings or placeholders."""
        rmc_points = {
            '060100': {  # 06:01:00
                'lat': 40.0,
                'lon': -74.0,
                'speed_knots': 10.0,
                'heading': 90.0
            }
        }
        gga_points = {}
        tar_date = datetime(2026, 3, 14).date()

        result = merge_gps_points(rmc_points, gga_points, tar_date=tar_date)

        self.assertGreater(len(result), 0, "Should have GPS points")
        point = result[0]
        self.assertIn('timestamp', point, "Point must have timestamp")
        self.assertIsInstance(point['timestamp'], datetime, "Timestamp must be datetime object")

        # Critical: date must be actual date, not 2000-01-01
        self.assertNotEqual(point['timestamp'].year, 2000,
                           "Timestamp should NOT have placeholder year 2000")
        self.assertEqual(point['timestamp'].year, 2026, "Should use actual year from tar_date")
        self.assertEqual(point['timestamp'].month, 3, "Should use actual month")
        self.assertEqual(point['timestamp'].day, 14, "Should use actual day")


if __name__ == '__main__':
    unittest.main()
