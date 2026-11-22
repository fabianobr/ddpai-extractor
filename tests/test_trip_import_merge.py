"""Importing a day must merge into the existing index, not replace it."""
import io
import json
import os
import re
import tarfile
import tempfile
import unittest
from datetime import date, timedelta, timezone
from pathlib import Path

from src.processing import trip_import
from src.processing.trip_import import (
    IndexUnreadable, import_trips, load_index, merge_index, merge_reports)


def trip(trip_id, **extra):
    data = {'id': trip_id, 'label': trip_id, 'points': [[0, 0, 0, 0, 0, 0]], 'video_rear': 'merged_videos/%s_rear.mp4' % trip_id}
    data.update(extra)
    return data


def sections(trip_id, with_marker, count=2):
    lines = []
    if with_marker:
        lines.append('TRIP: ' + trip_id)
    for camera in ('Rear', 'Front'):
        lines += ['', '=' * 80, '{} CAMERA - Merging {} videos:'.format(camera.upper(), count), '=' * 80]
        for n in range(count):
            lines += ['  {}. {}_{:02d}_{}.mp4'.format(n + 1, trip_id, n, camera[0]), '     Size: 1.0 MB | Duration: ? s']
        lines += ['', 'Total Videos: {} files'.format(count), 'Total Size: 2.0 MB']
    return lines


def report(*trip_ids, with_marker=True):
    lines = ['VIDEO MERGE DEBUG REPORT', '=' * 80, 'Generated: now', '=' * 80]
    for trip_id in trip_ids:
        lines += sections(trip_id, with_marker)
    return '\n'.join(lines)


def refresh_view(text):
    """What tools/refresh_video_sync.py sees: (camera, source names) per section, in order."""
    found = re.findall(r'(REAR|FRONT) CAMERA - Merging (\d+) videos:(.*?)Total Videos:', text, re.S)
    return [(kind, re.findall(r'^\s*\d+\. ([^\n]+\.mp4)$', body, re.M)) for kind, _, body in found]


class TestMergeIndex(unittest.TestCase):
    def test_keeps_old_trips_adds_new_in_chronological_order(self):
        old = {'generated_at': 'old', 'sync_refreshed_at': 'T', 'extra': 1, 'trips': [trip('20261121090410'), trip('20261121201845')]}
        new = {'generated_at': 'new', 'trips': [trip('20261121141815')]}
        merged = merge_index(old, new)
        self.assertEqual([t['id'] for t in merged['trips']], ['20261121090410', '20261121141815', '20261121201845'])
        self.assertEqual(merged['sync_refreshed_at'], 'T')
        self.assertEqual(merged['extra'], 1)
        self.assertEqual(merged['generated_at'], 'new')

    def test_reimported_trip_replaces_without_duplicate(self):
        old = {'trips': [trip('20261121090410', label='old'), trip('20261122090000')]}
        new = {'trips': [trip('20261121090410', label='new')]}
        merged = merge_index(old, new)
        self.assertEqual([(t['id'], t['label']) for t in merged['trips']], [('20261121090410', 'new'), ('20261122090000', '20261122090000')])

    def test_no_old_index_returns_new(self):
        new = {'generated_at': 'n', 'trips': [trip('b'), trip('a')]}
        self.assertEqual([t['id'] for t in merge_index(None, new)['trips']], ['a', 'b'])


class TestLoadIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'trips.json'

    def test_missing_is_none(self):
        self.assertIsNone(load_index(self.path))

    def test_valid(self):
        self.path.write_text(json.dumps({'trips': []}))
        self.assertEqual(load_index(self.path), {'trips': []})

    def test_corrupt_or_wrong_shape_raises(self):
        for content in ('{"trips": [', '[]', '{"trips": 3}', ''):
            self.path.write_text(content)
            with self.assertRaises(IndexUnreadable, msg=content):
                load_index(self.path)


class TestMergeReports(unittest.TestCase):
    def test_marked_old_and_new_are_ordered_like_the_index(self):
        merged = merge_reports(report('A', 'C'), ['A', 'C'], report('B'), ['B'], ['A', 'B', 'C'])
        kinds = refresh_view(merged)
        self.assertEqual([k for k, _ in kinds], ['REAR', 'FRONT'] * 3)
        self.assertEqual([names[0][0] for _, names in kinds], ['A', 'A', 'B', 'B', 'C', 'C'])

    def test_legacy_report_without_markers_is_mapped_by_index_order(self):
        merged = merge_reports(report('A', 'C', with_marker=False), ['A', 'C'], report('B'), ['B'], ['A', 'B', 'C'])
        self.assertEqual([names[0][0] for _, names in refresh_view(merged)], ['A', 'A', 'B', 'B', 'C', 'C'])
        self.assertEqual(merged.count('TRIP: '), 3)

    def test_replaced_trip_uses_new_sections_once(self):
        new = report('A').replace('A_00_R', 'A_NEW_R')
        merged = merge_reports(report('A', 'B'), ['A', 'B'], new, ['A'], ['A', 'B'])
        view = refresh_view(merged)
        self.assertEqual(len(view), 4)
        self.assertIn('A_NEW_R.mp4', view[0][1])

    def test_unmappable_legacy_report_returns_none(self):
        # 3 sections for 2 trips and no markers: cannot tell which belongs to whom.
        text = report('A', with_marker=False) + '\n' + '\n'.join(sections('B', False)[:6])
        self.assertIsNone(merge_reports(text, ['A', 'B'], report('C'), ['C'], ['A', 'B', 'C']))


class FakeBuild:
    """Stands in for build.sh: writes a fresh index/report holding only the requested trips."""

    def __init__(self, trip_ids, rc=0):
        self.trip_ids, self.rc, self.calls = trip_ids, rc, []

    def __call__(self, cmd, cwd=None, env=None):
        self.calls.append(cmd)
        out = Path(cmd[4])
        (out / 'data').mkdir(parents=True, exist_ok=True)
        if self.rc == 0:
            (out / 'data/trips.json').write_text(json.dumps({'generated_at': 'new', 'trips': [trip(i) for i in self.trip_ids]}))
            (out / 'data/merge_report.txt').write_text(report(*self.trip_ids))
            for i in self.trip_ids:  # videos are written through the merged_videos link
                (out / 'merged_videos' / (i + '_rear.mp4')).write_bytes(b'v')
        return self.rc


class TestImportTrips(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'data').mkdir()
        self.tar = self.root / 'src' / '20261121090410_0060.git'
        self.tar.parent.mkdir()
        self.tar.write_bytes(b'x')

    def run_import(self, ids, rc=0, **kwargs):
        runner = FakeBuild(ids, rc)
        kwargs.setdefault('notify', lambda message: None)
        result = import_trips([str(self.tar)], '/rear', '/front', root=self.root, runner=runner, **kwargs)
        return result, runner

    def index_ids(self):
        return [t['id'] for t in json.loads((self.root / 'data/trips.json').read_text())['trips']]

    def test_day_a_then_day_b_keeps_both(self):
        self.assertEqual(self.run_import(['A1', 'A2'])[0], 0)
        self.assertEqual(self.run_import(['B1'])[0], 0)
        self.assertEqual(self.index_ids(), ['A1', 'A2', 'B1'])
        view = refresh_view((self.root / 'data/merge_report.txt').read_text())
        self.assertEqual([names[0][:2] for _, names in view], ['A1', 'A1', 'A2', 'A2', 'B1', 'B1'])

    def test_reimport_replaces_without_duplicates(self):
        self.run_import(['A1', 'B1'])
        self.run_import(['A1'])
        self.assertEqual(self.index_ids(), ['A1', 'B1'])
        self.assertEqual(len(refresh_view((self.root / 'data/merge_report.txt').read_text())), 4)

    def test_missing_index_works_and_real_output_dir_is_not_the_temp_one(self):
        result, runner = self.run_import(['A1'])
        self.assertEqual(result, 0)
        self.assertEqual(self.index_ids(), ['A1'])
        self.assertNotEqual(Path(runner.calls[0][4]), self.root)

    def test_sync_refreshed_at_survives(self):
        self.run_import(['A1'])
        path = self.root / 'data/trips.json'
        data = json.loads(path.read_text())
        data['sync_refreshed_at'] = 'T'
        path.write_text(json.dumps(data))
        self.run_import(['B1'])
        self.assertEqual(json.loads(path.read_text())['sync_refreshed_at'], 'T')

    def test_backup_of_previous_index_is_kept(self):
        self.run_import(['A1'])
        self.run_import(['B1'])
        backups = list((self.root / 'working_data/backups').glob('trips-*.json'))
        self.assertEqual(len(backups), 1)
        self.assertEqual([t['id'] for t in json.loads(backups[0].read_text())['trips']], ['A1'])

    def test_corrupt_index_is_not_overwritten_and_build_is_not_run(self):
        path = self.root / 'data/trips.json'
        path.write_text('{"trips": [')
        result, runner = self.run_import(['B1'])
        self.assertNotEqual(result, 0)
        self.assertEqual(runner.calls, [])
        self.assertEqual(path.read_text(), '{"trips": [')

    def test_corrupt_index_can_be_replaced_explicitly_after_preserving_a_copy(self):
        path = self.root / 'data/trips.json'
        path.write_text('{"trips": [')
        result, _ = self.run_import(['B1'], replace_unreadable_index=True)
        self.assertEqual(result, 0)
        self.assertEqual(self.index_ids(), ['B1'])
        saved = list((self.root / 'working_data/backups').glob('trips-*.json'))
        self.assertEqual([p.read_text() for p in saved], ['{"trips": ['])

    def test_failed_build_leaves_index_and_report_untouched(self):
        self.run_import(['A1'])
        before = [(self.root / 'data' / n).read_text() for n in ('trips.json', 'merge_report.txt')]
        result, _ = self.run_import(['B1'], rc=1)
        self.assertEqual(result, 1)
        self.assertEqual(before, [(self.root / 'data' / n).read_text() for n in ('trips.json', 'merge_report.txt')])

    def test_unmappable_old_report_warns_but_index_is_merged(self):
        self.run_import(['A1'])
        (self.root / 'data/merge_report.txt').write_text('VIDEO MERGE DEBUG REPORT\n')
        messages = []
        result, _ = self.run_import(['B1'], notify=messages.append)
        self.assertEqual(result, 0)
        self.assertEqual(self.index_ids(), ['A1', 'B1'])
        self.assertTrue(any('relat' in m.lower() for m in messages), messages)
        self.assertTrue(list((self.root / 'working_data/backups').glob('merge_report-*.txt')))
