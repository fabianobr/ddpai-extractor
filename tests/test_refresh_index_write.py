import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('refresh_video_sync', str(ROOT / 'tools/refresh_video_sync.py'))
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)


class TestWriteIndexAtomic(unittest.TestCase):
    def test_preserves_existing_file_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, 'trips.json')
            database.write_text('{}')
            os.chmod(str(database), 0o640)
            refresh.write_index_atomic({'trips': [1]}, database)
            self.assertEqual(stat.S_IMODE(os.stat(str(database)).st_mode), 0o640)
            self.assertEqual(json.loads(database.read_text()), {'trips': [1]})

    def test_missing_original_uses_sensible_default_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, 'trips.json')
            old_umask = os.umask(0o022)
            try:
                refresh.write_index_atomic({'a': 1}, database)
            finally:
                os.umask(old_umask)
            self.assertEqual(stat.S_IMODE(os.stat(str(database)).st_mode), 0o644)

    def test_no_temporary_files_left_behind(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, 'trips.json')
            database.write_text('{}')
            refresh.write_index_atomic({'a': 1}, database)
            self.assertEqual(os.listdir(directory), ['trips.json'])

    def test_failed_serialisation_keeps_original_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory, 'trips.json')
            database.write_text('{"keep": true}')
            with self.assertRaises(TypeError):
                refresh.write_index_atomic({'a': object()}, database)
            self.assertEqual(json.loads(database.read_text()), {'keep': True})
            self.assertEqual(os.listdir(directory), ['trips.json'])


if __name__ == '__main__':
    unittest.main()
