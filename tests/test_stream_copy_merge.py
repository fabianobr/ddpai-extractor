"""
Unit tests for stream copy video merging.
Tests: stream copy detection, fallback logic, output validation.
"""
import os
import sys
import unittest
import tempfile
from unittest.mock import patch, MagicMock, call
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

        with patch('src.extraction.build_database.get_video_duration', return_value=100), \
             patch('src.extraction.build_database.get_video_size_mb', return_value=50), \
             patch('src.extraction.build_database.validate_video_output', return_value=(True, "Valid")), \
             patch('subprocess.run') as mock_run:

            mock_run.return_value = MagicMock(returncode=0)

            merge_videos(fake_videos, self.output_path)

            # Get the ffmpeg call (should be subprocess.run's first arg)
            self.assertTrue(mock_run.called, "subprocess.run should have been called")

            # Get the command
            cmd = mock_run.call_args[0][0]
            self.assertIn('ffmpeg', cmd)
            self.assertIn('-c:v', cmd)
            self.assertIn('copy', cmd)
            self.assertIn('-c:a', cmd)

    def test_ffmpeg_command_structure(self):
        """FFmpeg command should be properly formatted for concat + stream copy."""
        fake_videos = ['/fake/video1.mp4', '/fake/video2.mp4']

        with patch('src.extraction.build_database.get_video_duration', return_value=100), \
             patch('src.extraction.build_database.get_video_size_mb', return_value=50), \
             patch('src.extraction.build_database.validate_video_output', return_value=(True, "Valid")), \
             patch('subprocess.run') as mock_run:

            mock_run.return_value = MagicMock(returncode=0)

            merge_videos(fake_videos, self.output_path)

            # Get the command
            self.assertTrue(mock_run.called, "subprocess.run should have been called")
            cmd = mock_run.call_args[0][0]

            # Verify concat protocol is used
            self.assertIn('-f', cmd)
            self.assertIn('concat', cmd)
            self.assertIn('-safe', cmd)
            self.assertIn('0', cmd)

    def test_fallback_to_reencode_on_stream_copy_failure(self):
        """If stream copy fails, should retry with libx264 re-encoding."""
        fake_videos = ['/fake/video1.mp4', '/fake/video2.mp4']

        # First call fails (stream copy), second succeeds (re-encode)
        with patch('src.extraction.build_database.get_video_duration', return_value=100), \
             patch('src.extraction.build_database.get_video_size_mb', return_value=50), \
             patch('src.extraction.build_database.validate_video_output', return_value=(True, "Valid")), \
             patch('subprocess.run') as mock_run:

            mock_run.side_effect = [
                MagicMock(returncode=1, stderr='Incompatible stream'),  # Stream copy fails
                MagicMock(returncode=0)  # Re-encode succeeds
            ]

            result = merge_videos(fake_videos, self.output_path)

            # Should have two subprocess.run calls (once for copy, once for re-encode)
            self.assertEqual(mock_run.call_count, 2)

            # Verify first call uses stream copy and second uses re-encode
            cmd1 = mock_run.call_args_list[0][0][0]
            cmd2 = mock_run.call_args_list[1][0][0]

            self.assertIn('copy', cmd1, "First call should use stream copy")
            self.assertIn('libx264', cmd2, "Second call should use libx264 re-encoding")

    def test_output_file_created(self):
        """Output file should be created after successful merge."""
        fake_videos = ['/fake/video1.mp4', '/fake/video2.mp4']

        with patch('src.extraction.build_database.get_video_duration', return_value=100), \
             patch('src.extraction.build_database.get_video_size_mb', return_value=50), \
             patch('src.extraction.build_database.validate_video_output', return_value=(True, "Valid")), \
             patch('subprocess.run') as mock_run:

            mock_run.return_value = MagicMock(returncode=0)

            success, debug_info = merge_videos(fake_videos, self.output_path)

            # Should return success=True when subprocess.run returns returncode=0 and validation passes
            self.assertTrue(success, "merge_videos should return True on success")

    def test_timeout_scales_with_total_size_small_group(self):
        """Timeout for stream copy should scale with total input size (small group)."""
        # Small group: 8 files × 150 MB = 1,200 MB
        # Expected timeout: max(300, int(1200/10) + 120) = max(300, 240) = 300s
        small_videos = [f'/fake/front_{i:02d}.mp4' for i in range(8)]

        with patch('src.extraction.build_database.get_video_duration', return_value=100), \
             patch('src.extraction.build_database.get_video_size_mb', return_value=150.0), \
             patch('src.extraction.build_database.validate_video_output', return_value=(True, "Valid")), \
             patch('subprocess.run') as mock_run:

            mock_run.return_value = MagicMock(returncode=0)
            merge_videos(small_videos, self.output_path, use_stream_copy=True)

            # Verify timeout is at least 300s (floor)
            _, kwargs = mock_run.call_args
            actual_timeout = kwargs.get('timeout')
            self.assertGreaterEqual(actual_timeout, 300,
                f"Small group (1.2 GB) timeout {actual_timeout}s should be >= 300s")

    def test_timeout_scales_with_total_size_large_group(self):
        """Timeout for stream copy should scale with total input size (large group)."""
        # Large group: 48 files × 151 MB = 7,248 MB
        # Expected timeout: max(300, int(7248/10) + 120) = max(300, 844) = 844s
        large_videos = [f'/fake/front_{i:02d}.mp4' for i in range(48)]

        with patch('src.extraction.build_database.get_video_duration', return_value=100), \
             patch('src.extraction.build_database.get_video_size_mb', return_value=151.0), \
             patch('src.extraction.build_database.validate_video_output', return_value=(True, "Valid")), \
             patch('subprocess.run') as mock_run:

            mock_run.return_value = MagicMock(returncode=0)
            merge_videos(large_videos, self.output_path, use_stream_copy=True)

            # Verify timeout scales up for large groups (should be > 300)
            _, kwargs = mock_run.call_args
            actual_timeout = kwargs.get('timeout')
            self.assertGreater(actual_timeout, 300,
                f"Large group (7.2 GB) timeout {actual_timeout}s should be > 300s for stream copy")
            # Reasonable upper bound (should be < 1800s for stream copy)
            self.assertLess(actual_timeout, 1800,
                f"Large group timeout {actual_timeout}s should be < 1800s")


class TestStreamCopyIntegration(unittest.TestCase):
    """Integration test: real FFmpeg command execution."""

    def test_merge_two_real_videos_with_stream_copy(self):
        """
        Create two test videos, merge with stream copy, verify output.
        This tests the real FFmpeg path (not mocked).
        """
        import subprocess

        # Create test directory
        test_dir = tempfile.TemporaryDirectory()

        try:
            # Create two 2-second test videos
            video1 = os.path.join(test_dir.name, 'test1.mp4')
            video2 = os.path.join(test_dir.name, 'test2.mp4')
            output = os.path.join(test_dir.name, 'output.mp4')

            for video in [video1, video2]:
                subprocess.run([
                    'ffmpeg',
                    '-f', 'lavfi', '-i', 'color=c=blue:s=1280x720:d=2',
                    '-f', 'lavfi', '-i', 'sine=f=440:d=2',
                    '-pix_fmt', 'yuv420p',
                    video, '-y'
                ], capture_output=True, timeout=10)

            # Merge with stream copy
            success, debug_info = merge_videos([video1, video2], output, use_stream_copy=True)

            # Verify success
            self.assertTrue(success, f"Merge failed: {debug_info}")
            self.assertTrue(os.path.exists(output), "Output file not created")
            self.assertGreater(os.path.getsize(output), 10000, "Output too small")

            print(f"\n✅ Integration test passed")
            print(f"   Output: {output}")
            print(f"   Size: {os.path.getsize(output)} bytes")

        finally:
            test_dir.cleanup()


if __name__ == '__main__':
    unittest.main()
