import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'extract_photos.sh'


class TestExtractPhotosCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Copy the script into a fake repo so its default paths never touch real data.
        self.repo = Path(self.tmp.name, 'repo')
        (self.repo / 'tools').mkdir(parents=True)
        shutil.copy(str(SCRIPT), str(self.repo / 'tools' / 'extract_photos.sh'))
        self.script = str(self.repo / 'tools' / 'extract_photos.sh')
        self.photos = self.repo / 'working_data' / 'photos'
        for camera, name in (('front', 'a.jpg'), ('rear', 'b.JPG'), ('tmp', 'c.jpg')):
            (self.photos / camera).mkdir(parents=True)
            (self.photos / camera / name).write_bytes(b'x')

    def run_script(self, *args):
        return subprocess.run(['bash', self.script] + list(args), cwd=self.tmp.name,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    def test_dry_run_alone_uses_default_dirs_and_copies_nothing(self):
        result = self.run_script('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Would copy', result.stdout)
        self.assertIn('Total available for extraction: 2', result.stdout)
        self.assertFalse((self.repo / 'extracted_photos').exists())

    def test_documented_positional_form_with_trailing_flag(self):
        out = Path(self.tmp.name, 'out')
        result = self.run_script(str(self.photos), str(out), '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Total available for extraction: 2', result.stdout)
        self.assertFalse(out.exists())

    def test_flag_before_positionals(self):
        out = Path(self.tmp.name, 'out')
        result = self.run_script('--dry-run', str(self.photos), str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(out.exists())

    def test_real_copy_and_include_tmp(self):
        out = Path(self.tmp.name, 'out')
        result = self.run_script(str(self.photos), str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sorted(os.listdir(str(out))), ['front', 'rear'])
        result = self.run_script('--include-tmp', str(self.photos), str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((out / 'tmp' / 'c.jpg').is_file())

    def test_paths_with_spaces(self):
        src = Path(self.tmp.name, 'my photos')
        (src / 'front').mkdir(parents=True)
        (src / 'front' / 'a.jpg').write_bytes(b'x')
        out = Path(self.tmp.name, 'my out')
        result = self.run_script(str(src), str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((out / 'front' / 'a.jpg').is_file())

    def test_unknown_option_is_usage_error(self):
        result = self.run_script('--bogus')
        self.assertEqual(result.returncode, 2)
        self.assertIn('Usage', result.stderr)

    def test_too_many_positionals_is_usage_error(self):
        result = self.run_script('a', 'b', 'c')
        self.assertEqual(result.returncode, 2)
        self.assertIn('Usage', result.stderr)

    def test_dry_run_combined_with_include_tmp(self):
        result = self.run_script('--dry-run', '--include-tmp')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Total available for extraction: 3', result.stdout)

    def test_missing_source_reports_error(self):
        result = self.run_script(str(Path(self.tmp.name, 'nope')))
        self.assertEqual(result.returncode, 1)
        self.assertIn('Photo source not found', result.stderr)


if __name__ == '__main__':
    unittest.main()
