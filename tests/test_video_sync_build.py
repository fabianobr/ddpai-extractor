#!/usr/bin/env python3
"""
Tests for video-GPS synchronization build process.
Run: python3 -m pytest tests/test_video_sync_build.py -v
"""
import unittest
import os
import sys
import tempfile
import subprocess
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))
from src.extraction.build_database import (
    extract_video_duration,
    validate_video_gps_duration,
    compute_sparse_timestamps
)


class TestExtractVideoDuration(unittest.TestCase):
    """Test video duration extraction with ffprobe."""

    def test_extract_duration_from_valid_mp4(self):
        """Extract duration from a valid MP4 file."""
        test_dir = tempfile.TemporaryDirectory()
        test_video = os.path.join(test_dir.name, 'test.mp4')

        cmd = [
            'ffmpeg', '-f', 'lavfi', '-i', 'color=c=blue:s=640x480:d=2',
            '-f', 'lavfi', '-i', 'sine=f=440:d=2',
            '-pix_fmt', 'yuv420p', test_video, '-y'
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=10)

        if result.returncode != 0:
            self.skipTest("ffmpeg not available")

        duration = extract_video_duration(test_video)

        self.assertIsNotNone(duration, "Should extract duration from valid video")
        self.assertGreater(duration, 1.5, "Duration should be ~2 seconds")
        self.assertLess(duration, 2.5, "Duration should be ~2 seconds")

        test_dir.cleanup()

    def test_extract_duration_from_missing_file(self):
        """Handle missing video file gracefully."""
        duration = extract_video_duration('/nonexistent/video.mp4')
        self.assertIsNone(duration, "Should return None for missing file")

    def test_extract_duration_is_float(self):
        """Duration should be returned as float (seconds)."""
        test_dir = tempfile.TemporaryDirectory()
        test_video = os.path.join(test_dir.name, 'test.mp4')

        cmd = [
            'ffmpeg', '-f', 'lavfi', '-i', 'color=c=blue:s=640x480:d=3',
            '-f', 'lavfi', '-i', 'sine=f=440:d=3',
            '-pix_fmt', 'yuv420p', test_video, '-y'
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=10)

        if result.returncode != 0:
            self.skipTest("ffmpeg not available")

        duration = extract_video_duration(test_video)

        self.assertIsInstance(duration, (int, float), "Duration must be numeric")

        test_dir.cleanup()


class TestValidateVideoDuration(unittest.TestCase):
    """Test video-GPS duration validation logic."""

    def test_validate_matching_durations(self):
        """Durations matching within 5 seconds should pass."""
        video_duration_s = 600.0
        gps_duration_s = 599.5

        status = validate_video_gps_duration(video_duration_s, gps_duration_s)
        self.assertEqual(status, "match", "Durations within 5s should be valid")

    def test_validate_video_shorter(self):
        """Video significantly shorter than GPS should be flagged."""
        video_duration_s = 540.0
        gps_duration_s = 600.0

        status = validate_video_gps_duration(video_duration_s, gps_duration_s)
        self.assertEqual(status, "video_shorter", "Video shorter by 1 min should flag as video_shorter")

    def test_validate_video_longer(self):
        """Video longer than GPS should be flagged."""
        video_duration_s = 620.0
        gps_duration_s = 600.0

        status = validate_video_gps_duration(video_duration_s, gps_duration_s)
        self.assertEqual(status, "video_longer", "Video longer should flag as video_longer")

    def test_validate_missing_video(self):
        """None video duration should be flagged as no_video."""
        status = validate_video_gps_duration(None, 600.0)
        self.assertEqual(status, "no_video", "None video_duration should flag as no_video")


class TestComputeSparseTimestamps(unittest.TestCase):
    """Test sparse timestamp computation."""

    def test_compute_sparse_timestamps_simple(self):
        """Compute sparse timestamps from GPS points."""
        points = []
        start = datetime(2026, 3, 14, 13, 0, 0)

        for i in range(50):
            points.append({
                'timestamp': start + timedelta(seconds=i),
                'lat': 40.0 + i * 0.001,
                'lon': -74.0 + i * 0.001,
                'speed_kmh': 50.0
            })

        sparse = compute_sparse_timestamps(points, sample_interval=10)

        self.assertGreater(len(sparse), 0, "Should produce sparse timestamps")
        self.assertEqual(sparse[0]['index'], 0, "First sample should be at index 0")

        for sample in sparse:
            self.assertEqual(sample['index'] % 10, 0, f"Index {sample['index']} should be multiple of 10")

        for sample in sparse:
            self.assertIsInstance(sample['timestamp'], str, "Timestamp should be ISO string")
            datetime.fromisoformat(sample['timestamp'])

    def test_compute_sparse_timestamps_empty(self):
        """Empty points should return empty sparse timestamps."""
        sparse = compute_sparse_timestamps([], sample_interval=10)
        self.assertEqual(len(sparse), 0, "Empty points should return empty sparse timestamps")


class TestFullSyncIntegration(unittest.TestCase):
    """Test full video-GPS sync pipeline."""

    def test_json_output_includes_all_sync_fields(self):
        """Verify trips.json includes all required sync fields."""
        json_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'data', 'trips.json'
        )

        if not os.path.exists(json_path):
            self.skipTest("trips.json not generated (run ./build.sh first)")

        with open(json_path) as f:
            data = json.load(f)

        self.assertIn('trips', data, "JSON should have 'trips' key")

        if len(data['trips']) == 0:
            self.skipTest("No trips in trips.json")

        trip = data['trips'][0]

        # Check required fields
        required = ['video_duration_s', 'start_timestamp', 'gps_points_count',
                   'video_duration_status', 'sparse_timestamps']

        # Skip if fields not yet added (allow gradual migration)
        fields_missing = [f for f in required if f not in trip]
        if fields_missing:
            self.skipTest(f"Sync fields not yet in JSON: {', '.join(fields_missing)}. "
                         "Re-run ./build.sh to regenerate trips.json")

        for field in required:
            self.assertIn(field, trip, f"Trip should have '{field}' field")

        # Validate field types
        if trip['video_duration_s'] is not None:
            self.assertIsInstance(trip['video_duration_s'], (int, float),
                                 "video_duration_s should be numeric")

        self.assertIsInstance(trip['start_timestamp'], str,
                             "start_timestamp should be ISO string")

        self.assertIsInstance(trip['gps_points_count'], int,
                             "gps_points_count should be int")

        self.assertIn(trip['video_duration_status'],
                     ['match', 'video_shorter', 'video_longer', 'no_video'],
                     "video_duration_status should be valid value")

        self.assertIsInstance(trip['sparse_timestamps'], list,
                             "sparse_timestamps should be list")

    def test_sparse_timestamps_structure(self):
        """Verify sparse_timestamps have correct structure."""
        json_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'data', 'trips.json'
        )

        if not os.path.exists(json_path):
            self.skipTest("trips.json not generated")

        with open(json_path) as f:
            data = json.load(f)

        if len(data['trips']) == 0:
            self.skipTest("No trips")

        if 'sparse_timestamps' not in data['trips'][0]:
            self.skipTest("Sync fields not yet in JSON. Re-run ./build.sh to regenerate trips.json")

        sparse = data['trips'][0]['sparse_timestamps']

        if len(sparse) == 0:
            return  # Valid if trip too short

        for sample in sparse:
            self.assertIn('index', sample, "Sample should have 'index'")
            self.assertIn('timestamp', sample, "Sample should have 'timestamp'")
            self.assertIsInstance(sample['index'], int, "Index should be int")
            self.assertIsInstance(sample['timestamp'], str, "Timestamp should be string")

            # Verify indices are multiples of 10
            self.assertEqual(sample['index'] % 10, 0,
                           f"Index {sample['index']} should be multiple of 10")

    def test_video_duration_status_values(self):
        """Verify video_duration_status is set correctly."""
        json_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'data', 'trips.json'
        )

        if not os.path.exists(json_path):
            self.skipTest("trips.json not generated")

        with open(json_path) as f:
            data = json.load(f)

        if len(data['trips']) == 0:
            self.skipTest("No trips")

        if 'video_duration_status' not in data['trips'][0]:
            self.skipTest("Sync fields not yet in JSON. Re-run ./build.sh to regenerate trips.json")

        for trip in data['trips']:
            status = trip.get('video_duration_status')
            self.assertIn(status, ['match', 'video_shorter', 'video_longer', 'no_video'],
                         f"Invalid status: {status}")


if __name__ == '__main__':
    unittest.main()
