import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_group(group):
    return subprocess.run(['node', 'tests/trip_model_cases.js', group], cwd=ROOT, capture_output=True, text=True)


@unittest.skipUnless(shutil.which('node'), 'Node.js necessário para testar web/trip-model.js')
class TestTripModel(unittest.TestCase):
    def test_time(self):
        r = run_group('time'); self.assertEqual(r.returncode, 0, r.stderr)

    def test_geometry(self):
        r = run_group('geometry'); self.assertEqual(r.returncode, 0, r.stderr)

    def test_chapters(self):
        r = run_group('chapters'); self.assertEqual(r.returncode, 0, r.stderr)
