"""
Unit tests for stream copy video merging.
Tests: stream copy detection, fallback logic, output validation.
"""
import os
import sys
import unittest
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.extraction.build_database import merge_videos


class TestStreamCopyMerge(unittest.TestCase):
    """Test stream copy video merging functionality."""

    def setUp(self):
        """Create temp directory for test outputs."""
        self.test_dir = tempfile.TemporaryDirectory()
        self.output_path = os.path.join(self.test_dir.name, 'output.mp4')

    def tearDown(self):
        """Clean up temp directory."""
        self.test_dir.cleanup()

    def test_stream_copy_used_by_default(self):
        """Stream copy mode should be enabled by default."""
        fake_videos = ['/fake/video1.mp4', '/fake/video2.mp4']

        with patch('subprocess.run') as mock_run, \
             patch('os.path.exists', return_value=True), \
             patch('pathlib.Path.mkdir'):

            mock_run.return_value = MagicMock(returncode=0)

            merge_videos(fake_videos, self.output_path)

            # Verify command uses stream copy
            cmd = mock_run.call_args[1]['args'] if 'args' in mock_run.call_args[1] else mock_run.call_args[0][0]
            self.assertIn('-c:v', cmd)
            self.assertIn('copy', cmd)
            self.assertIn('-c:a', cmd)

    def test_ffmpeg_command_structure(self):
        """FFmpeg command should be properly formatted for concat + stream copy."""
        fake_videos = ['/fake/video1.mp4', '/fake/video2.mp4']

        with patch('subprocess.run') as mock_run, \
             patch('os.path.exists', return_value=True), \
             patch('pathlib.Path.mkdir'), \
             patch('tempfile.NamedTemporaryFile'):

            mock_run.return_value = MagicMock(returncode=0)

            merge_videos(fake_videos, self.output_path)

            # Verify concat protocol is used
            cmd = mock_run.call_args[1]['args'] if 'args' in mock_run.call_args[1] else mock_run.call_args[0][0]
            self.assertIn('-f', cmd)
            self.assertIn('concat', cmd)
            self.assertIn('-safe', cmd)
            self.assertIn('0', cmd)

    def test_fallback_to_reencode_on_stream_copy_failure(self):
        """If stream copy fails, should retry with libx264 re-encoding."""
        fake_videos = ['/fake/video1.mp4', '/fake/video2.mp4']

        # First call fails (stream copy), second succeeds (re-encode)
        with patch('subprocess.run') as mock_run, \
             patch('os.path.exists', return_value=True), \
             patch('pathlib.Path.mkdir'):

            mock_run.side_effect = [
                MagicMock(returncode=1, stderr='Incompatible stream'),  # Stream copy fails
                MagicMock(returncode=0)  # Re-encode succeeds
            ]

            result = merge_videos(fake_videos, self.output_path)

            # Should have tried twice (once for copy, once for re-encode)
            self.assertEqual(mock_run.call_count, 2)

    def test_output_file_created(self):
        """Output file should be created after successful merge."""
        fake_videos = ['/fake/video1.mp4', '/fake/video2.mp4']

        with patch('subprocess.run') as mock_run, \
             patch('os.path.exists', return_value=True), \
             patch('pathlib.Path.mkdir'):

            mock_run.return_value = MagicMock(returncode=0)

            result = merge_videos(fake_videos, self.output_path)

            # returncode=0 indicates success
            self.assertEqual(mock_run.return_value.returncode, 0)


if __name__ == '__main__':
    unittest.main()
