"""
Unit tests for is_parking_file() hybrid parking detection.
Ground truth validated against video playback on 2026-03-14.
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.extraction.build_database import is_parking_file


def _make_stats(distance_km, avg_speed):
    return {'distance_km': distance_km, 'avg_speed': avg_speed,
            'max_speed': avg_speed * 2, 'duration_min': 8.0}


class TestIsParkingFile(unittest.TestCase):

    def _run(self, distance, avg_speed):
        """Helper: mock GPS extraction and return is_parking_file result."""
        fake_points = [{'lat': 0, 'lon': 0, 'speed_kmh': avg_speed}] * 10
        with patch('src.extraction.build_database.extract_gps_from_tar', return_value=fake_points), \
             patch('src.extraction.build_database.compute_trip_stats', return_value=_make_stats(distance, avg_speed)):
            return is_parking_file('/fake/file.git')

    # --- Clear parking cases ---

    def test_zero_distance_is_parking(self):
        """0.01 km, 0.10 km/h → PARKING (clear stationary)."""
        self.assertTrue(self._run(0.01, 0.10))

    def test_low_speed_only_is_parking(self):
        """0.55 km, 1.10 km/h → PARKING (speed below 3.0 threshold)."""
        self.assertTrue(self._run(0.55, 1.10))

    def test_transition_file_is_parking(self):
        """0.57 km, 3.30 km/h → PARKING (distance below 0.6 threshold).
        This is the ground-truth edge case from 18:01 BRT on 2026-03-14."""
        self.assertTrue(self._run(0.57, 3.30))

    # --- Clear driving cases ---

    def test_highway_speed_is_driving(self):
        """24.17 km, 67.70 km/h → DRIVING."""
        self.assertFalse(self._run(24.17, 67.70))

    def test_city_driving_is_driving(self):
        """10.40 km, 27.20 km/h → DRIVING."""
        self.assertFalse(self._run(10.40, 27.20))

    def test_start_of_driving_is_driving(self):
        """10.40 km, 27.20 km/h at 18:33 BRT → DRIVING (ground truth)."""
        self.assertFalse(self._run(10.40, 27.20))

    # --- No GPS data ---

    def test_no_points_is_parking(self):
        """No GPS data → assume PARKING."""
        with patch('src.extraction.build_database.extract_gps_from_tar', return_value=[]):
            self.assertTrue(is_parking_file('/fake/empty.git'))


if __name__ == '__main__':
    unittest.main()
