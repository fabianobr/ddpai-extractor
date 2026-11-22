"""Regression tests for stale GPS residue inside a .gpx file.

DDPAI .gpx files can carry, after the valid fixes, leftovers of an older 307200-byte
buffer: fixes whose full timestamp (date + time) goes backwards and duplicate points
that already exist, correct, in another segment. Everything from the first backwards
step (or an absurd jump) on must be dropped; a legitimate UTC midnight rollover is not.
"""
import io
import tarfile
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from src.extraction.build_database import (
    extract_gps_from_nmea, extract_gps_from_tar, merge_gps_points)


def rmc(hhmmss, ddmmyy='211126', lat='2733.9000', lon='04830.9000'):
    return '$GPRMC,{}.00,A,{},S,{},W,10.0,90.0,{},,,A*00'.format(hhmmss, lat, lon, ddmmyy)


def nmea(*sentences):
    return '\n'.join(sentences) + '\n'


def stamps(content):
    rmc_points, gga_points = extract_gps_from_nmea(content)
    merged = merge_gps_points(rmc_points, gga_points, tar_date=datetime(2026, 11, 21).date())
    return [p['timestamp'] for p in merged]


class TestStaleResidueIsDiscarded(unittest.TestCase):
    def test_drops_fixes_from_first_backwards_timestamp(self):
        valid = [rmc('1347%02d' % s) for s in range(12, 17)]
        stale = [rmc('1320%02d' % s, lat='2734.1000') for s in (6, 7, 8, 44)]
        result = stamps(nmea(*(valid + stale)))
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0], datetime(2026, 11, 21, 13, 47, 12))
        self.assertEqual(result[-1], datetime(2026, 11, 21, 13, 47, 16))

    def test_stale_residue_removed_end_to_end_from_tar(self):
        content = nmea(*([rmc('1347%02d' % s) for s in range(12, 17)] + [rmc('132006'), rmc('132044')]))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '20261121134700_0060.git'
            with tarfile.open(str(path), 'w:') as archive:
                data = content.encode()
                info = tarfile.TarInfo('20261121134712_0060_A.gpx')
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            points = extract_gps_from_tar(str(path))
        self.assertEqual(len(points), 5)
        self.assertTrue(all(p['camera_segment'] == '20261121134712' for p in points))
        self.assertEqual(set(points[0]), {'lat', 'lon', 'speed_kmh', 'altitude', 'heading',
                                          'timestamp', 'camera_segment'})

    def test_utc_midnight_rollover_is_not_truncated(self):
        content = nmea(rmc('235958', '211126'), rmc('235959', '211126'),
                       rmc('000000', '221126'), rmc('000001', '221126'))
        result = stamps(content)
        self.assertEqual(len(result), 4)
        self.assertEqual(result[-1], datetime(2026, 11, 22, 0, 0, 1))

    def test_normal_file_is_unchanged(self):
        sentences = [rmc('1347%02d' % s) for s in range(10, 40)]
        self.assertEqual(len(stamps(nmea(*sentences))), 30)

    def test_late_first_fix_and_gaps_are_kept(self):
        # A file may start late (first fix at +28 s) and skip a few seconds.
        sentences = [rmc('134728'), rmc('134729'), rmc('134735'), rmc('134736')]
        self.assertEqual(len(stamps(nmea(*sentences))), 4)

    def test_absurd_forward_jump_is_treated_as_corruption(self):
        sentences = [rmc('134712'), rmc('134713'), rmc('150000'), rmc('150001')]
        self.assertEqual(len(stamps(nmea(*sentences))), 2)

    def test_missing_rmc_date_does_not_break_midnight(self):
        content = nmea(rmc('235959', ''), rmc('000001', ''))
        rmc_points, _ = extract_gps_from_nmea(content)
        self.assertEqual(len(rmc_points), 2)


class TestParkingClassificationIgnoresResidue(unittest.TestCase):
    """An archive that only looked like driving because of stale residue is parked."""

    @staticmethod
    def parked_archive_with_residue(folder):
        parked = ['$GPRMC,1347%02d.00,A,2733.9000,S,04830.9000,W,0.0,0.0,211126,,,A*00' % s for s in range(10, 60)]
        # Stale fixes 12 km away with backwards timestamps: they would add fake distance.
        stale = ['$GPRMC,1320%02d.00,A,2740.0000,S,04830.9000,W,10.0,0.0,211126,,,A*00' % s for s in range(10, 40)]
        data = nmea(*(parked + stale)).encode()
        path = Path(folder) / '20261121134700_0060.git'
        with tarfile.open(str(path), 'w:') as archive:
            info = tarfile.TarInfo('20261121134710_0060_A.gpx')
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        return str(path)

    def test_cleaned_extraction_classifies_as_parking(self):
        from src.extraction.build_database import is_parking_file
        with tempfile.TemporaryDirectory() as folder:
            self.assertTrue(is_parking_file(self.parked_archive_with_residue(folder)))

    def test_legacy_mode_reproduces_previous_membership(self):
        # tools/refresh_video_sync.py keeps the trips that were already imported and merged.
        from src.extraction.build_database import is_parking_file, detect_trip_groups
        with tempfile.TemporaryDirectory() as folder:
            path = self.parked_archive_with_residue(folder)
            self.assertFalse(is_parking_file(path, drop_stale=False))
            self.assertEqual(detect_trip_groups([path], drop_stale=False)[0], [[path]])
            self.assertEqual(detect_trip_groups([path])[0], [])

    def test_extract_can_keep_residue_explicitly(self):
        content = nmea(rmc('134712'), rmc('132006'))
        rmc_points, _ = extract_gps_from_nmea(content, drop_stale=False)
        self.assertEqual(len(rmc_points), 2)


if __name__ == '__main__':
    unittest.main()
