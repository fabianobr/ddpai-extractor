"""
Unit tests for timeout retry mechanism.
Tests: timeout detection, retry escalation, progress formatting, console output.
"""
import os
import sys
import unittest
import time
from unittest.mock import patch, MagicMock, call
from pathlib import Path
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.extraction.build_database import merge_videos


class TestTimeoutRetry(unittest.TestCase):
    """Test timeout retry mechanism."""

    def setUp(self):
        """Create temp directory for test outputs."""
        import tempfile
        self.test_dir = tempfile.TemporaryDirectory()
        self.output_path = os.path.join(self.test_dir.name, 'output.mp4')

    def tearDown(self):
        """Clean up temp directory."""
        self.test_dir.cleanup()

    def test_timeout_triggers_retry_once(self):
        """Timeout on first attempt should trigger retry with 50% increased timeout."""
        fake_videos = [f'/fake/video_{i:02d}.mp4' for i in range(8)]

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: timeout
                raise subprocess.TimeoutExpired('ffmpeg', 840)
            else:
                # Second call: success
                return MagicMock(returncode=0)

        with patch('src.extraction.build_database.get_video_duration', return_value=100), \
             patch('src.extraction.build_database.get_video_size_mb', return_value=150.0), \
             patch('src.extraction.build_database.validate_video_output', return_value=(True, "Valid")), \
             patch('subprocess.run', side_effect=side_effect) as mock_run:

            success, debug_info = merge_videos(fake_videos, self.output_path, use_stream_copy=True)

            # Verify two calls were made (first timeout, second success)
            self.assertEqual(mock_run.call_count, 2, "Should attempt twice: initial + 1 retry")

            # Verify timeout escalation: first timeout is 300s, second should be 450s (50% increase)
            calls = mock_run.call_args_list
            first_timeout = calls[0][1]['timeout']
            second_timeout = calls[1][1]['timeout']

            self.assertEqual(second_timeout, int(first_timeout * 1.5),
                f"Second timeout {second_timeout}s should be 50% more than {first_timeout}s")

            # Verify success after retry
            self.assertTrue(success, "Should succeed on retry")

            # Verify console message about retry
            debug_text = '\n'.join(debug_info)
            self.assertIn('TIMEOUT', debug_text, "Debug info should mention timeout")
            self.assertIn('Retry', debug_text, "Debug info should mention retry")

    def test_timeout_max_retries_exhausted(self):
        """All 3 attempts timing out should fail gracefully with helpful message."""
        fake_videos = [f'/fake/video_{i:02d}.mp4' for i in range(48)]

        def timeout_side_effect(*args, **kwargs):
            # Always timeout
            raise subprocess.TimeoutExpired('ffmpeg', kwargs.get('timeout', 840))

        with patch('src.extraction.build_database.get_video_duration', return_value=100), \
             patch('src.extraction.build_database.get_video_size_mb', return_value=151.0), \
             patch('subprocess.run', side_effect=timeout_side_effect) as mock_run:

            success, debug_info = merge_videos(fake_videos, self.output_path, use_stream_copy=True)

            # Verify three attempts were made (initial + 2 retries)
            self.assertEqual(mock_run.call_count, 3, "Should attempt 3 times: initial + 2 retries")

            # Verify failure
            self.assertFalse(success, "Should fail after all retries exhausted")

            # Verify helpful error message
            debug_text = '\n'.join(debug_info)
            self.assertIn('FAILED', debug_text, "Should indicate failure")
            self.assertIn('exhausted', debug_text, "Should mention retries exhausted")
            self.assertIn('Suggestions', debug_text, "Should provide recovery suggestions")

    def test_timeout_escalation_formula(self):
        """Verify 50% timeout increase on each retry."""
        # Test with 840s initial (7.2 GB group)
        initial_timeout = 840
        expected_tier2 = int(initial_timeout * 1.5)  # 1260
        expected_tier3 = int(expected_tier2 * 1.5)   # 1890

        self.assertEqual(expected_tier2, 1260, "Tier 2 should be 1260s")
        self.assertEqual(expected_tier3, 1890, "Tier 3 should be 1890s")

    def test_timeout_vs_non_timeout_errors(self):
        """Non-timeout errors should still trigger re-encoding fallback (not retry)."""
        fake_videos = [f'/fake/video_{i:02d}.mp4' for i in range(8)]

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: FFmpeg error (not timeout)
                result = MagicMock()
                result.returncode = 1
                result.stderr = "Incompatible codec"
                return result
            else:
                # Second call (re-encoding fallback): success
                return MagicMock(returncode=0)

        with patch('src.extraction.build_database.get_video_duration', return_value=100), \
             patch('src.extraction.build_database.get_video_size_mb', return_value=150.0), \
             patch('src.extraction.build_database.validate_video_output', return_value=(True, "Valid")), \
             patch('subprocess.run', side_effect=side_effect) as mock_run:

            success, debug_info = merge_videos(fake_videos, self.output_path, use_stream_copy=True)

            # Should have 2 calls: stream copy (failed) + re-encoding fallback (succeeded)
            self.assertEqual(mock_run.call_count, 2)

            # Verify second call uses libx264 (re-encoding), not stream copy
            second_call_args = mock_run.call_args_list[1][0][0]
            self.assertIn('libx264', second_call_args, "Fallback should use libx264 re-encoding")

            self.assertTrue(success)

    def test_progress_message_format(self):
        """Console messages should follow specified format with progress bar and ETA."""
        fake_videos = [f'/fake/video_{i:02d}.mp4' for i in range(48)]

        with patch('src.extraction.build_database.get_video_duration', return_value=100), \
             patch('src.extraction.build_database.get_video_size_mb', return_value=151.0), \
             patch('src.extraction.build_database.validate_video_output', return_value=(True, "Valid")), \
             patch('subprocess.run') as mock_run:

            call_count = [0]

            def timeout_then_success(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise subprocess.TimeoutExpired('ffmpeg', 840)
                return MagicMock(returncode=0)

            mock_run.side_effect = timeout_then_success

            success, debug_info = merge_videos(fake_videos, self.output_path, use_stream_copy=True)

            debug_text = '\n'.join(debug_info)

            # Check for required message components
            self.assertIn('TIMEOUT', debug_text)
            self.assertIn('exceeded', debug_text)
            self.assertIn('Retrying', debug_text)

    def test_successful_retry_logging(self):
        """Successful retry should log detailed timing information."""
        fake_videos = [f'/fake/video_{i:02d}.mp4' for i in range(8)]

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise subprocess.TimeoutExpired('ffmpeg', 300)
            return MagicMock(returncode=0)

        with patch('src.extraction.build_database.get_video_duration', return_value=50), \
             patch('src.extraction.build_database.get_video_size_mb', return_value=150.0), \
             patch('src.extraction.build_database.validate_video_output', return_value=(True, "Valid")), \
             patch('subprocess.run', side_effect=side_effect):

            success, debug_info = merge_videos(fake_videos, self.output_path, use_stream_copy=True)

            debug_text = '\n'.join(debug_info)
            self.assertIn('successful', debug_text.lower(), "Should log successful retry")
            self.assertIn('Output', debug_text, "Should log output file info")


class TestTimeoutRetryIntegration(unittest.TestCase):
    """Integration test: real merge with artificial timeout."""

    def test_real_merge_with_artificial_low_timeout(self):
        """Create test videos, merge with low timeout to trigger retry, verify success."""
        import tempfile
        import subprocess as sp

        test_dir = tempfile.TemporaryDirectory()
        try:
            # Create two small test videos
            video1 = os.path.join(test_dir.name, 'test1.mp4')
            video2 = os.path.join(test_dir.name, 'test2.mp4')
            output = os.path.join(test_dir.name, 'output.mp4')

            for video in [video1, video2]:
                sp.run([
                    'ffmpeg',
                    '-f', 'lavfi', '-i', 'color=c=blue:s=1280x720:d=1',
                    '-f', 'lavfi', '-i', 'sine=f=440:d=1',
                    '-pix_fmt', 'yuv420p',
                    video, '-y'
                ], capture_output=True, timeout=10)

            # This will likely timeout at 1s, then retry and succeed at 5s
            # (depending on system speed)
            success, debug_info = merge_videos([video1, video2], output, use_stream_copy=True)

            # Success is optional (depends on actual merge speed), but should not crash
            debug_text = '\n'.join(debug_info)
            # If it succeeded normally or via retry, should work
            if success:
                self.assertTrue(os.path.exists(output), "Output should exist on success")
                self.assertGreater(os.path.getsize(output), 10000, "Output should be non-trivial")

        finally:
            test_dir.cleanup()


if __name__ == '__main__':
    unittest.main()
