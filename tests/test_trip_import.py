import unittest
from datetime import date, datetime, timezone, timedelta
from unittest.mock import patch

from src.processing.trip_import import choose_groups, parse_selection


class TestTripImport(unittest.TestCase):
    def test_day_includes_trip_crossing_local_midnight(self):
        groups = [['20261122025000_1200.git'], ['20261122060000_0600.git']]
        zone = timezone(timedelta(hours=-3))
        self.assertEqual(choose_groups(groups, date(2026, 11, 21), zone), [groups[0]])

    def test_selection_supports_all_and_multiple(self):
        self.assertEqual(parse_selection('t', 3), [0, 1, 2])
        self.assertEqual(parse_selection('3, 1', 3), [0, 2])
        with self.assertRaises(ValueError):
            parse_selection('4', 3)

    @patch('src.processing.trip_import.builder.extract_gps_from_tar')
    def test_day_uses_nmea_utc_not_camera_filename(self, extract):
        extract.return_value = [{'timestamp': datetime(2026, 11, 22, 2, 15)}]
        groups = [['20261122021500_0060.git']]
        zone = timezone(timedelta(hours=-3))
        self.assertEqual(choose_groups(groups, date(2026, 11, 21), zone), groups)
        extract.return_value = [{'timestamp': datetime(2026, 11, 22, 5, 15)}]
        self.assertEqual(choose_groups(groups, date(2026, 11, 22), zone), groups)
