import shutil
import subprocess
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from src.extraction.video_timeline import build_video_sync, estimate_clock_offset, estimate_clock_calibration

BASE = datetime(2026, 11, 21, 9, 4, 10)


def point(minute, fix_delay, skew=10752):
    """First fix of a one-minute file `minute` minutes after BASE, `fix_delay` s after file start."""
    start = BASE + timedelta(minutes=minute)
    return {'camera_segment': start.strftime('%Y%m%d%H%M%S'),
            'timestamp': start + timedelta(seconds=skew + fix_delay)}


class TestClockCalibration(unittest.TestCase):
    def test_stable_clock_is_high_confidence(self):
        pts = [point(i, 0) for i in range(8)]
        cal = estimate_clock_calibration(pts)
        self.assertEqual(cal['offset_s'], 10752)
        self.assertEqual(cal['offset_spread_s'], 0)
        self.assertEqual(cal['offset_samples'], 8)
        self.assertEqual(cal['confidence'], 'high')

    def test_late_first_fix_is_outlier_but_median_stays_and_spread_reported(self):
        pts = [point(i, 0) for i in range(7)] + [point(7, 2.5)]
        cal = estimate_clock_calibration(pts)
        self.assertEqual(cal['offset_s'], 10752)
        self.assertEqual(cal['offset_spread_s'], 2.5)
        self.assertEqual(cal['offset_typical_spread_s'], 2.5)
        self.assertEqual(cal['offset_outlier_segments'], 0)
        self.assertEqual(cal['confidence'], 'medium')

    def test_large_spread_is_low(self):
        pts = [point(i, 0) for i in range(6)] + [point(6, 12)]
        cal = estimate_clock_calibration(pts)
        self.assertEqual(cal['offset_s'], 10752)
        self.assertEqual(cal['offset_spread_s'], 12)
        self.assertEqual(cal['confidence'], 'low')

    def test_spread_exactly_at_limits(self):
        self.assertEqual(estimate_clock_calibration([point(i, 0) for i in range(6)] + [point(6, 1)])['confidence'], 'high')
        self.assertEqual(estimate_clock_calibration([point(i, 0) for i in range(6)] + [point(6, 3)])['confidence'], 'medium')

    def test_isolated_outliers_in_long_trip_do_not_lower_confidence(self):
        # Real data pattern: ~97% of segments within 1 s, a few late/misattributed ones.
        pts = [point(i, 0) for i in range(110)] + [point(110, 28), point(111, -1600), point(112, 9)]
        cal = estimate_clock_calibration(pts)
        self.assertEqual(cal['offset_s'], 10752)
        self.assertEqual(cal['offset_spread_s'], 1600)  # maximum is still reported
        self.assertEqual(cal['offset_typical_spread_s'], 0)
        self.assertEqual(cal['offset_outlier_segments'], 3)
        self.assertEqual(cal['confidence'], 'high')

    def test_many_outliers_in_long_trip_lower_confidence(self):
        pts = [point(i, 0) for i in range(80)] + [point(80 + i, 20) for i in range(20)]
        cal = estimate_clock_calibration(pts)
        self.assertEqual(cal['offset_outlier_segments'], 20)
        self.assertEqual(cal['confidence'], 'low')

    def test_few_segments_is_medium_even_with_zero_spread(self):
        cal = estimate_clock_calibration([point(0, 0), point(1, 0)])
        self.assertEqual(cal['offset_samples'], 2)
        self.assertEqual(cal['offset_spread_s'], 0)
        self.assertEqual(cal['confidence'], 'medium')

    def test_few_segments_with_large_spread_is_low(self):
        cal = estimate_clock_calibration([point(0, 0), point(1, 9)])
        self.assertEqual(cal['confidence'], 'low')

    def test_no_samples_is_low_and_none_without_exception(self):
        for pts in ([], [{'camera_segment': None, 'timestamp': None}]):
            cal = estimate_clock_calibration(pts)
            self.assertIsNone(cal['offset_s'])
            self.assertIsNone(cal['offset_spread_s'])
            self.assertIsNone(cal['offset_typical_spread_s'])
            self.assertEqual(cal['offset_outlier_segments'], 0)
            self.assertEqual(cal['offset_samples'], 0)
            self.assertEqual(cal['confidence'], 'low')
            self.assertIsNone(estimate_clock_offset(pts))

    def test_invalid_timestamps_and_segments_are_ignored(self):
        good = [point(i, 0) for i in range(5)]
        bad = [{'camera_segment': 'lixo', 'timestamp': BASE},
               {'camera_segment': '20261121100000', 'timestamp': 'nao-e-data'},
               {'camera_segment': '20261121100100', 'timestamp': None},
               {'timestamp': BASE}]
        cal = estimate_clock_calibration(good + bad)
        self.assertEqual(cal['offset_samples'], 5)
        self.assertEqual(cal['confidence'], 'high')

    def test_estimate_clock_offset_value_unchanged(self):
        pts = [point(0, 0), point(1, 0), point(2, 5)]
        self.assertEqual(estimate_clock_offset(pts), 10752)
        # Earliest fix of a segment is the one used, as before.
        extra = point(0, 0)
        later = dict(extra, timestamp=extra['timestamp'] + timedelta(seconds=30))
        self.assertEqual(estimate_clock_offset([later, extra, point(1, 0)]), 10752)

    def test_video_sync_adds_confidence_fields_without_changing_mapping(self):
        pts = [point(i, 0) for i in range(3)]
        names = [(BASE + timedelta(minutes=i)).strftime('%Y%m%d%H%M%S') + '_0060_A.mp4' for i in range(3)]
        result = build_video_sync(pts, names, names, duration_fn=lambda p: 60.0)
        self.assertEqual(result['rear'], [0.0, 60.0, 120.0])
        self.assertEqual(result['clock_offset_s'], 10752)
        self.assertEqual(result['offset_spread_s'], 0)
        self.assertEqual(result['offset_samples'], 3)
        self.assertEqual(result['offset_typical_spread_s'], 0)
        self.assertEqual(result['offset_outlier_segments'], 0)
        self.assertEqual(result['confidence'], 'medium')
        for key in ('rear', 'front', 'status', 'rear_source_duration_s', 'front_source_duration_s'):
            self.assertIn(key, result)

    def test_video_sync_without_gps_samples(self):
        result = build_video_sync([], [], [], duration_fn=lambda p: 60.0)
        self.assertIsNone(result['clock_offset_s'])
        self.assertEqual(result['confidence'], 'low')
        self.assertEqual(result['offset_samples'], 0)


@unittest.skipUnless(shutil.which('node'), 'Node.js necessário para validar o JavaScript')
class TestConfidenceWarningFrontend(unittest.TestCase):
    def run_node(self, script):
        result = subprocess.run(['node', '-e', script], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_warning_text_by_confidence(self):
        self.run_node(r'''
const assert = require('assert');
const {syncConfidenceWarning} = require('./web/video-sync.js');
assert.equal(syncConfidenceWarning({confidence: 'high', offset_spread_s: 0.4}), '');
assert.equal(syncConfidenceWarning({confidence: 'medium', offset_spread_s: 2.1}), 'Sincronização aproximada (±3 s)');
assert.equal(syncConfidenceWarning({confidence: 'medium', offset_spread_s: 0}), 'Sincronização aproximada (±1 s)');
assert.equal(syncConfidenceWarning({confidence: 'medium', offset_spread_s: 1600, offset_typical_spread_s: 2.1}), 'Sincronização aproximada (±3 s)');
assert.equal(syncConfidenceWarning({confidence: 'medium', offset_spread_s: null}), 'Sincronização aproximada');
assert.equal(syncConfidenceWarning({confidence: 'low', offset_spread_s: 9}), 'A posição no mapa pode não coincidir com o vídeo.');
''')

    def test_old_or_missing_data_keeps_current_behaviour(self):
        self.run_node(r'''
const assert = require('assert');
const {syncConfidenceWarning} = require('./web/video-sync.js');
for (const value of [undefined, null, {}, {status: 'ok'}, {status: 'ok', clock_offset_s: 10752}, {confidence: 'desconhecida'}])
  assert.equal(syncConfidenceWarning(value), '');
''')
