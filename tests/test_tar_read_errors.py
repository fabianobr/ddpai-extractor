"""extract_gps_from_tar must not hide unreadable archives behind an empty result."""
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from src.extraction.build_database import extract_gps_from_tar, is_parking_file, detect_trip_groups


def rmc(hhmmss, lat='2733.9000'):
    return '$GPRMC,{}.00,A,{},S,04830.9000,W,40.0,90.0,211126,,,A*00'.format(hhmmss, lat)


def gpx(first_second, lat='2733.9000'):
    return ('\n'.join(rmc('1347%02d' % (first_second + i), lat) for i in range(10)) + '\n').encode()


def write_tar(path, members):
    with tarfile.open(str(path), 'w:') as archive:
        for name, data in members:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))


class TestTarReadErrors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def make_tar(self, name='20261121134700_0060.git', members=None):
        path = self.dir / name
        write_tar(path, members or [('20261121134700_0060_A.gpx', gpx(0))])
        return path

    def truncate(self, path, keep):
        path.write_bytes(path.read_bytes()[:keep])

    def test_healthy_tar_is_unchanged_and_reports_no_error(self):
        path = self.make_tar()
        errors = []
        points = extract_gps_from_tar(str(path), errors=errors)
        self.assertEqual(len(points), 10)
        self.assertEqual(errors, [])
        self.assertEqual(len(extract_gps_from_tar(str(path))), 10)

    def test_tar_without_gpx_is_not_an_error(self):
        path = self.make_tar(members=[('video.txt', b'x')])
        errors = []
        self.assertEqual(extract_gps_from_tar(str(path), errors=errors), [])
        self.assertEqual(errors, [])

    def test_corrupt_tar_logs_path_and_exception_and_reports_error(self):
        path = self.dir / '20261121134700_0060.git'
        path.write_bytes(b'not a tar archive' * 100)
        errors = []
        with self.assertLogs('src.extraction.build_database', level='WARNING') as logs:
            points = extract_gps_from_tar(str(path), errors=errors)
        self.assertEqual(points, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][0], str(path))
        self.assertIsInstance(errors[0][1], Exception)
        self.assertIn(str(path), '\n'.join(logs.output))

    def test_truncated_tar_keeps_complete_members_and_reports_error(self):
        path = self.make_tar(members=[('20261121134700_0060_A.gpx', gpx(0)),
                                      ('20261121134800_0060_A.gpx', gpx(20) * 40)])
        self.truncate(path, 512 + 1024 + 600)
        errors = []
        with self.assertLogs('src.extraction.build_database', level='WARNING') as logs:
            points = extract_gps_from_tar(str(path), errors=errors)
        self.assertEqual(len(points), 10)
        self.assertEqual({p['camera_segment'] for p in points}, {'20261121134700'})
        self.assertEqual([item[0] for item in errors], [str(path)])
        self.assertIn(str(path), '\n'.join(logs.output))

    def test_error_list_is_optional_and_failure_is_still_logged(self):
        path = self.dir / 'x.git'
        path.write_bytes(b'garbage' * 200)
        with self.assertLogs('src.extraction.build_database', level='WARNING') as logs:
            self.assertEqual(extract_gps_from_tar(str(path)), [])
        self.assertIn(str(path), '\n'.join(logs.output))

    def test_is_parking_file_records_unreadable_file(self):
        path = self.dir / '20261121134700_0060.git'
        path.write_bytes(b'garbage' * 200)
        unreadable = []
        with self.assertLogs('src.extraction.build_database', level='WARNING'):
            self.assertTrue(is_parking_file(str(path), unreadable=unreadable))
        self.assertEqual(unreadable, [str(path)])

    def test_is_parking_file_does_not_flag_readable_parked_file(self):
        path = self.make_tar(members=[('20261121134700_0060_A.gpx', b'')])
        unreadable = []
        self.assertTrue(is_parking_file(str(path), unreadable=unreadable))
        self.assertEqual(unreadable, [])

    def test_detect_trip_groups_collects_unreadable_files(self):
        bad = self.dir / '20261121134700_0060.git'
        bad.write_bytes(b'garbage' * 200)
        unreadable = []
        with self.assertLogs('src.extraction.build_database', level='WARNING'):
            groups, _, parking = detect_trip_groups([str(bad)], unreadable=unreadable)
        self.assertEqual((groups, parking), ([], [str(bad)]))
        self.assertEqual(unreadable, [str(bad)])
