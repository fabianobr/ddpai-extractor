import unittest
from datetime import datetime, timedelta
from src.extraction.build_database import parse_rmc, merge_gps_points
from src.extraction.video_timeline import build_video_sync


class TestSegmentSync(unittest.TestCase):
    def test_rmc_date_crosses_midnight(self):
        base = ['235959.00','A','2733.9','S','04830.9','W','0','0','211126','','']
        next_day = ['000001.00','A','2733.9','S','04830.9','W','0','0','221126','','']
        first, second = parse_rmc(base), parse_rmc(next_day)
        points = merge_gps_points({first['time']: first, second['time']: second}, {}, tar_date=datetime(2026, 11, 21).date())
        self.assertEqual((points[1]['timestamp'] - points[0]['timestamp']).total_seconds(), 2)

    def test_maps_discontinuous_recordings_to_concatenated_seconds(self):
        pts = [
            {'timestamp': datetime(2026,11,21,12,3,22), 'camera_segment': '20261121090410'},
            {'timestamp': datetime(2026,11,21,12,3,32), 'camera_segment': '20261121090410'},
            {'timestamp': datetime(2026,11,21,12,20,45), 'camera_segment': '20261121092133'},
            {'timestamp': datetime(2026,11,21,12,20,55), 'camera_segment': '20261121092133'},
            {'timestamp': datetime(2026,11,21,12,21,45), 'camera_segment': '20261121092233'},
        ]
        rear = ['20261121090410_0060_A.mp4', '20261121092133_0060_A.mp4', '20261121092233_0060_A.mp4']
        front = rear[:2]
        result = build_video_sync(pts, rear, front, duration_fn=lambda p: 60.0)
        self.assertEqual(result['rear'], [0.0, 10.0, 60.0, 70.0, 120.0])
        self.assertEqual(result['front'], [0.0, 10.0, 60.0, 70.0, None])
        self.assertEqual(result['status'], 'partial')

    def test_missing_media_duration_never_invents_offsets(self):
        pts = [{'timestamp': datetime(2026,11,21,12,3,22), 'camera_segment':'20261121090410'}]
        result = build_video_sync(pts, ['20261121090410_0060_A.mp4'], [], duration_fn=lambda p: None)
        self.assertEqual(result['rear'], [None])
        self.assertEqual(result['status'], 'unavailable')


class TestSingleCameraStatus(unittest.TestCase):
    """A camera that was not supplied is absent, not a coverage gap."""

    def points(self):
        return [
            {'timestamp': datetime(2026,11,21,12,3,22), 'camera_segment': '20261121090410'},
            {'timestamp': datetime(2026,11,21,12,3,32), 'camera_segment': '20261121090410'},
        ]

    def test_fully_mapped_single_camera_is_ok(self):
        rear = ['20261121090410_0060_A.mp4']
        result = build_video_sync(self.points(), rear, [], duration_fn=lambda p: 60.0)
        self.assertEqual(result['rear'], [0.0, 10.0])
        self.assertEqual(result['status'], 'ok')

    def test_single_front_camera_is_ok(self):
        front = ['20261121090410_0060_A.mp4']
        result = build_video_sync(self.points(), [], front, duration_fn=lambda p: 60.0)
        self.assertEqual(result['status'], 'ok')

    def test_single_camera_with_uncovered_point_is_partial(self):
        # Same segment, but recorded after the 60 s video ended: no footage for this point.
        pts = self.points() + [{'timestamp': datetime(2026,11,21,12,5,30), 'camera_segment': '20261121090410'}]
        result = build_video_sync(pts, ['20261121090410_0060_A.mp4'], [], duration_fn=lambda p: 60.0)
        self.assertEqual(result['status'], 'partial')

    def test_no_cameras_is_unavailable(self):
        result = build_video_sync(self.points(), [], [], duration_fn=lambda p: 60.0)
        self.assertEqual(result['status'], 'unavailable')


class TestBoundaryPointsMapByVideoWindow(unittest.TestCase):
    """GPS points attributed to the next .gpx but recorded just before its video starts."""

    def make_points(self):
        starts = ['20261121120000', '20261121120100', '20261121120200', '20261121120300']
        points = []
        for start in starts:
            base = datetime.strptime(start, '%Y%m%d%H%M%S')
            for seconds in (0, 30):
                points.append({'timestamp': base + timedelta(seconds=seconds), 'camera_segment': start})
        # Three points 3, 2 and 1 s before B's window; they lie inside A's window.
        early = [{'timestamp': datetime(2026, 11, 21, 12, 0, 57 + i), 'camera_segment': '20261121120100'}
                 for i in range(3)]
        return starts, points, early

    def test_boundary_point_maps_into_previous_video(self):
        starts, points, early = self.make_points()
        videos = [s + '_0060_A.mp4' for s in starts]
        result = build_video_sync(points + early, videos, videos, duration_fn=lambda p: 60.0)
        mapped = result['rear'][len(points):]
        self.assertEqual(mapped, [57.0, 58.0, 59.0])
        self.assertEqual(result['front'][len(points):], [57.0, 58.0, 59.0])
        # The usual points are unchanged.
        self.assertEqual(result['rear'][:8], [0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0, 210.0])

    def test_point_without_any_video_stays_null(self):
        starts, points, _ = self.make_points()
        videos = [s + '_0060_A.mp4' for s in starts]
        orphan = [{'timestamp': datetime(2026, 11, 21, 12, 10, 0), 'camera_segment': '20261121121000'}]
        result = build_video_sync(points + orphan, videos, videos, duration_fn=lambda p: 60.0)
        self.assertIsNone(result['rear'][-1])
        self.assertIsNone(result['front'][-1])

    def test_real_gap_between_videos_stays_null(self):
        # B starts 12:01:12 (a 12 s hole after A); a point at 12:01:10 has no video.
        starts = ['20261121120000', '20261121120112', '20261121120300', '20261121120400']
        points = []
        for start in starts:
            base = datetime.strptime(start, '%Y%m%d%H%M%S')
            for seconds in (0, 30):
                points.append({'timestamp': base + timedelta(seconds=seconds), 'camera_segment': start})
        gap = [{'timestamp': datetime(2026, 11, 21, 12, 1, 10), 'camera_segment': '20261121120112'},
               {'timestamp': datetime(2026, 11, 21, 12, 1, 11), 'camera_segment': '20261121120112'}]
        videos = [s + '_0060_A.mp4' for s in starts]
        result = build_video_sync(points + gap, videos, videos, duration_fn=lambda p: 60.0)
        self.assertEqual(result['rear'][len(points):], [None, None])
