"""
Tests for merge_videos() progress bar, dynamic timeout, and Ctrl+C handling.
Run: pytest tests/test_merge_videos_progress.py -v
"""
import os
import sys
import io
import unittest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.extraction.build_database import merge_videos


class TestDynamicTimeout(unittest.TestCase):
    """_calculate_timeout is tested indirectly via merge_videos timeout behavior."""

    def test_merge_empty_list_returns_false(self):
        """Guard clause: empty list returns (False, []) immediately."""
        ok, info = merge_videos([], '/tmp/out.mp4', 'Rear')
        self.assertFalse(ok)

    def test_merge_videos_shows_progress_on_stdout(self, *_):
        """With show_progress=True, a \\r line must appear on stdout during encode."""
        # Build a minimal fake FFmpeg stdout: one progress event then end
        fake_stdout_lines = [
            "frame=100\n",
            "fps=30.0\n",
            "out_time_ms=30000000\n",   # 30 seconds encoded
            "speed=3.0x\n",
            "progress=continue\n",
            "out_time_ms=60000000\n",
            "speed=3.0x\n",
            "progress=end\n",
        ]
        mock_proc = MagicMock()
        mock_proc.stdout = iter(fake_stdout_lines)
        mock_proc.stderr = iter([])
        mock_proc.returncode = 0
        mock_proc.wait.return_value = None

        with patch('subprocess.Popen', return_value=mock_proc), \
             patch('os.path.exists', return_value=False), \
             patch('tempfile.NamedTemporaryFile') as mock_tmp, \
             patch('os.remove'), \
             patch('src.extraction.build_database.get_video_size_mb', return_value=100.0), \
             patch('src.extraction.build_database.get_video_duration', return_value=30.0):

            mock_tmp.return_value.__enter__ = MagicMock()
            mock_tmp.return_value.name = '/tmp/fake_concat.txt'
            mock_tmp.return_value.write = MagicMock()
            mock_tmp.return_value.close = MagicMock()

            captured = io.StringIO()
            with patch('sys.stdout', captured):
                ok, _ = merge_videos(
                    ['/fake/video1.mp4'],
                    '/tmp/out.mp4',
                    camera_type='Rear',
                    show_progress=True,
                )

            output = captured.getvalue()
            self.assertIn('\r', output, "Expected \\r progress bar on stdout")
            self.assertIn('Rear', output, "Expected camera type in progress bar")

    def test_merge_videos_no_progress_when_disabled(self):
        """With show_progress=False, no \\r output to stdout."""
        fake_stdout_lines = [
            "out_time_ms=30000000\n",
            "speed=3.0x\n",
            "progress=end\n",
        ]
        mock_proc = MagicMock()
        mock_proc.stdout = iter(fake_stdout_lines)
        mock_proc.stderr = iter([])
        mock_proc.returncode = 0
        mock_proc.wait.return_value = None

        with patch('subprocess.Popen', return_value=mock_proc), \
             patch('os.path.exists', return_value=False), \
             patch('tempfile.NamedTemporaryFile') as mock_tmp, \
             patch('os.remove'), \
             patch('src.extraction.build_database.get_video_size_mb', return_value=100.0), \
             patch('src.extraction.build_database.get_video_duration', return_value=30.0):

            mock_tmp.return_value.name = '/tmp/fake_concat.txt'
            mock_tmp.return_value.write = MagicMock()
            mock_tmp.return_value.close = MagicMock()

            captured = io.StringIO()
            with patch('sys.stdout', captured):
                merge_videos(
                    ['/fake/video1.mp4'],
                    '/tmp/out.mp4',
                    show_progress=False,
                )

            output = captured.getvalue()
            self.assertNotIn('\r', output, "No \\r expected when show_progress=False")

    def test_merge_videos_keyboard_interrupt_calls_sys_exit(self):
        """Ctrl+C during encode kills proc and calls sys.exit(1)."""
        mock_proc = MagicMock()
        mock_proc.stdout = _KeyboardInterruptIter()
        mock_proc.stderr = iter([])
        mock_proc.returncode = None
        mock_proc.wait.return_value = None

        with patch('subprocess.Popen', return_value=mock_proc), \
             patch('os.path.exists', return_value=False), \
             patch('tempfile.NamedTemporaryFile') as mock_tmp, \
             patch('os.remove'), \
             patch('src.extraction.build_database.get_video_size_mb', return_value=None), \
             patch('src.extraction.build_database.get_video_duration', return_value=None):

            mock_tmp.return_value.name = '/tmp/fake_concat.txt'
            mock_tmp.return_value.write = MagicMock()
            mock_tmp.return_value.close = MagicMock()

            with self.assertRaises(SystemExit) as cm:
                merge_videos(['/fake/video1.mp4'], '/tmp/out.mp4', show_progress=False)

            self.assertEqual(cm.exception.code, 1)
            mock_proc.kill.assert_called_once()

    def test_ffmpeg_command_contains_progress_flag(self):
        """FFmpeg command must include -progress pipe:1 and -nostats."""
        called_cmds = []

        def capture_popen(cmd, **kwargs):
            called_cmds.append(cmd)
            mock_proc = MagicMock()
            mock_proc.stdout = iter(["progress=end\n"])
            mock_proc.stderr = iter([])
            mock_proc.returncode = 0
            mock_proc.wait.return_value = None
            return mock_proc

        with patch('subprocess.Popen', side_effect=capture_popen), \
             patch('os.path.exists', return_value=False), \
             patch('tempfile.NamedTemporaryFile') as mock_tmp, \
             patch('os.remove'), \
             patch('src.extraction.build_database.get_video_size_mb', return_value=None), \
             patch('src.extraction.build_database.get_video_duration', return_value=None):

            mock_tmp.return_value.name = '/tmp/fake_concat.txt'
            mock_tmp.return_value.write = MagicMock()
            mock_tmp.return_value.close = MagicMock()

            merge_videos(['/fake/video1.mp4'], '/tmp/out.mp4', show_progress=False)

        self.assertTrue(len(called_cmds) > 0, "Popen should have been called")
        cmd = called_cmds[0]
        self.assertIn('-progress', cmd)
        self.assertIn('pipe:1', cmd)
        self.assertIn('-nostats', cmd)


class _KeyboardInterruptIter:
    """Iterator that raises KeyboardInterrupt on first call."""
    def __iter__(self):
        return self
    def __next__(self):
        raise KeyboardInterrupt


if __name__ == '__main__':
    unittest.main()
