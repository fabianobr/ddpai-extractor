import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from datetime import date, datetime, timezone, timedelta
from unittest.mock import patch

from src.processing.trip_import import choose_groups, discover_groups, parse_selection, warn_unreadable


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


def driving_gpx():
    rows = ['$GPRMC,1347{:02d}.00,A,{:09.4f},S,04830.9000,W,40.0,90.0,211126,,,A*00'.format(i, 2733.9 + i * 0.1)
            for i in range(10)]
    return ('\n'.join(rows) + '\n').encode()


class TestUnreadableArchives(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.zone = timezone(timedelta(hours=-3))
        self.good = self.dir / '20261121134700_0060.git'
        with tarfile.open(str(self.good), 'w:') as archive:
            data = driving_gpx()
            info = tarfile.TarInfo('20261121134700_0060_A.gpx')
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        self.bad = self.dir / '20261121150000_0060.git'
        self.bad.write_bytes(b'garbage' * 300)

    def test_corrupt_archive_is_reported_not_silently_parked(self):
        with self.assertLogs('src.extraction.build_database', level='WARNING'):
            groups, parking, unreadable = discover_groups([str(self.good), str(self.bad)], date(2026, 11, 21), self.zone)
        self.assertEqual(groups, [[str(self.good)]])
        self.assertEqual(unreadable, [str(self.bad)])
        self.assertIn(str(self.bad), parking)

    def test_healthy_archives_have_no_unreadable(self):
        groups, _, unreadable = discover_groups([str(self.good)], date(2026, 11, 21), self.zone)
        self.assertEqual((groups, unreadable), ([[str(self.good)]], []))

    def test_warning_names_each_file_and_explains_it_is_not_parked(self):
        out = io.StringIO()
        warn_unreadable([str(self.bad), str(self.bad), '/x/y.git'], out)
        text = out.getvalue()
        self.assertEqual(text.count(str(self.bad)), 1)
        self.assertIn('/x/y.git', text)
        self.assertIn('ilegíve', text)

    def test_no_warning_when_nothing_unreadable(self):
        out = io.StringIO()
        warn_unreadable([], out)
        self.assertEqual(out.getvalue(), '')
