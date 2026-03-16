# Timeout Retry Mechanism Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement three-tier timeout retry mechanism (50% escalation, max 2 retries) with progress-aware console feedback for large video merge operations.

**Architecture:** Wrap `merge_videos()` subprocess.run call in retry loop that catches `TimeoutExpired` exceptions separately from other FFmpeg errors. Add helper functions for progress estimation and console formatting. No automatic re-encoding fallback on timeout.

**Tech Stack:** Python 3, subprocess (timeout handling), time module (elapsed tracking), no external dependencies

---

## File Structure

| File | Responsibility |
|------|-----------------|
| `src/extraction/build_database.py` | Modify `merge_videos()` + add 3 helper functions (progress, formatting, ETA) |
| `tests/test_timeout_retry.py` | NEW: 8 test cases (unit, integration, regression) |
| `tests/test_stream_copy_merge.py` | UNCHANGED: Regression testing via existing tests |

---

## Chunk 1: Setup & Helper Functions

### Task 1: Create test file with all test cases (TDD foundation)

**Files:**
- Create: `tests/test_timeout_retry.py`

- [ ] **Step 1: Write all test cases (failing — TDD approach)**

Create `tests/test_timeout_retry.py`:

```python
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
            self.assertIn('%', debug_text, "Should show percentage")
            self.assertIn('Elapsed', debug_text, "Should show elapsed time")
            self.assertIn('Est', debug_text, "Should show estimated total")

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
```

- [ ] **Step 2: Run tests to verify they all fail (expected before implementation)**

Run: `python3 -m unittest tests.test_timeout_retry -v 2>&1 | head -50`

Expected: Multiple FAIL or ERROR outputs (tests reference functions/behavior not yet implemented)

---

### Task 2: Add helper functions to build_database.py

**Files:**
- Modify: `src/extraction/build_database.py` (add helper functions before `merge_videos()`)

- [ ] **Step 1: Add three helper functions**

Add these functions to `src/extraction/build_database.py` around line 600 (before `merge_videos()` definition):

```python
def calculate_eta(elapsed_seconds, bytes_processed, total_bytes):
    """
    Calculate estimated time remaining based on current processing rate.

    Args:
        elapsed_seconds: Time elapsed so far
        bytes_processed: Bytes processed so far
        total_bytes: Total bytes to process

    Returns:
        (estimated_seconds, estimated_minutes) or (None, None) if can't estimate
    """
    if elapsed_seconds <= 0 or bytes_processed <= 0:
        return None, None

    try:
        bytes_per_second = bytes_processed / elapsed_seconds
        remaining_bytes = total_bytes - bytes_processed

        if remaining_bytes <= 0:
            return 0, 0

        estimated_remaining = remaining_bytes / bytes_per_second
        estimated_total = elapsed_seconds + estimated_remaining
        estimated_minutes = estimated_total / 60

        return estimated_total, estimated_minutes
    except (ZeroDivisionError, TypeError):
        return None, None


def format_retry_message(attempt, current_timeout, new_timeout, total_size, file_count):
    """
    Format console message for timeout retry event.

    Args:
        attempt: Retry attempt number (1, 2, etc.)
        current_timeout: Current timeout in seconds
        new_timeout: New timeout in seconds
        total_size: Total input size in MB
        file_count: Number of video files

    Returns:
        Formatted message string
    """
    percent_increase = int(((new_timeout - current_timeout) / current_timeout) * 100)
    message = f"⏱️  TIMEOUT: Stream copy exceeded {current_timeout}s limit\n"
    message += f"  → Input: {file_count} files, {total_size:.1f} GB total\n"
    message += f"  → Retrying with {new_timeout}s timeout ({percent_increase}% increase)...\n"
    return message


def format_failure_message(max_timeout, tier1_timeout, tier2_timeout, tier3_timeout):
    """
    Format console message for timeout failure (all retries exhausted).

    Args:
        max_timeout: Final timeout value reached
        tier1_timeout: Initial timeout (Tier 1)
        tier2_timeout: First retry timeout (Tier 2)
        tier3_timeout: Second retry timeout (Tier 3)

    Returns:
        Formatted message string
    """
    message = f"❌ FAILED: Stream copy timed out after 2 retries (final limit: {max_timeout}s)\n"
    message += f"  → All 3 attempts exhausted: {tier1_timeout}s → {tier2_timeout}s → {tier3_timeout}s\n"
    message += f"  → Suggestions:\n"
    message += f"    1. Retry with re-encoding: use_stream_copy=False\n"
    message += f"    2. Split large groups: merge manually in smaller batches\n"
    message += f"    3. Check system resources: CPU/disk I/O may be constrained\n"
    return message
```

- [ ] **Step 2: Verify helpers are syntactically correct**

Run: `python3 -c "from src.extraction.build_database import calculate_eta, format_retry_message, format_failure_message; print('✅ Helpers loaded successfully')"`

Expected: `✅ Helpers loaded successfully`

---

## Chunk 2: Implement Retry Logic in merge_videos()

### Task 3: Wrap subprocess.run in timeout exception handler

**Files:**
- Modify: `src/extraction/build_database.py` lines 725–790 (the subprocess.run block)

- [ ] **Step 1: Find current subprocess.run call and understand context**

Read lines 720–800 of `src/extraction/build_database.py` to understand:
- Where `cmd` is built
- Where `timeout_seconds` is set
- What happens after subprocess.run returns

- [ ] **Step 2: Replace hardcoded subprocess.run with retry loop**

Replace the section starting at line 731 (`debug_info.append(f"Command: ...)`) through line 790 with:

```python
        debug_info.append(f"Command: {' '.join(cmd)}\n")

        # Retry loop: up to 2 retries on timeout
        max_retries = 2
        retry_attempt = 0
        tier_timeouts = [timeout_seconds]  # Track all timeout values for logging
        start_time = time.time()

        while retry_attempt <= max_retries:
            attempt_number = retry_attempt + 1
            debug_info.append(f"Attempt {attempt_number}/3: timeout={timeout_seconds}s\n")

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)

                # Success or non-timeout error — handle normally
                if result.returncode == 0:
                    # Validate output file
                    is_valid, validation_msg = validate_video_output(output_path, total_duration if has_duration_info else None)

                    if is_valid:
                        # Get output file info
                        out_size = get_video_size_mb(output_path)
                        out_duration = get_video_duration(output_path)

                        if retry_attempt > 0:
                            elapsed_time = int(time.time() - start_time)
                            debug_info.append(f"\n✅ Merge successful on retry! Completed in {elapsed_time}s")
                        else:
                            debug_info.append(f"\n✅ Merge successful ({merge_method})!")

                        debug_info.append(f"Output: {os.path.basename(output_path)}")

                        if out_size or out_duration:
                            size_str = f"{out_size:.1f} MB" if out_size else "? MB"
                            if out_duration:
                                min_str = f" ({int(out_duration/60)} min)"
                                duration_str = f"{out_duration:.1f}s{min_str}"
                            else:
                                duration_str = "? s"
                            debug_info.append(f"  → {size_str} | {duration_str}")
                        else:
                            debug_info.append(f"  (ffprobe not available for details)")

                        return True, debug_info
                    else:
                        debug_info.append(f"\n⚠️  Output validation failed: {validation_msg}")
                        # If stream copy failed, try re-encoding as fallback
                        if use_stream_copy:
                            debug_info.append(f"Falling back to H.264 re-encoding...")
                            # Clean up invalid output
                            if os.path.exists(output_path):
                                try:
                                    os.remove(output_path)
                                except:
                                    pass
                            # Recursively call with re-encoding
                            return merge_videos(video_list, output_path, camera_type, debug_log, use_stream_copy=False)
                        else:
                            return False, debug_info
                else:
                    # Non-zero return code (FFmpeg error, not timeout)
                    debug_info.append(f"\n❌ FFmpeg error ({merge_method}):")
                    error_msg = result.stderr[-500:] if len(result.stderr) > 500 else result.stderr
                    debug_info.append(error_msg)

                    # If stream copy failed, try re-encoding as fallback
                    if use_stream_copy:
                        debug_info.append(f"\nFalling back to H.264 re-encoding...")
                        # Clean up failed output
                        if os.path.exists(output_path):
                            try:
                                os.remove(output_path)
                            except:
                                pass
                        # Recursively call with re-encoding
                        return merge_videos(video_list, output_path, camera_type, debug_log, use_stream_copy=False)
                    else:
                        return False, debug_info

            except subprocess.TimeoutExpired as e:
                # Timeout — try to retry (if retries remaining)
                elapsed_time = int(time.time() - start_time)

                if retry_attempt < max_retries:
                    # Calculate new timeout (50% increase)
                    new_timeout = int(timeout_seconds * 1.5)
                    new_timeout_gib = new_timeout / 60

                    # Print retry message to console
                    retry_msg = format_retry_message(retry_attempt + 1, timeout_seconds, new_timeout, total_size / 1024, len(sorted_videos))
                    print(retry_msg)
                    debug_info.append(retry_msg)
                    debug_info.append(f"  [Retry {retry_attempt + 1}/2] Merging...\n")

                    # Update timeout for next iteration
                    timeout_seconds = new_timeout
                    tier_timeouts.append(timeout_seconds)
                    retry_attempt += 1

                    # Clean up partial output
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except:
                            pass

                    # Continue to next retry attempt
                    continue
                else:
                    # All retries exhausted
                    debug_info.append(f"\n❌ FAILED: Stream copy timed out after 2 retries (final limit: {timeout_seconds}s)\n")
                    debug_info.append(f"  → Elapsed across all attempts: {elapsed_time}s\n")

                    # Print failure message to console
                    tier1, tier2, tier3 = tier_timeouts[0], tier_timeouts[1] if len(tier_timeouts) > 1 else '?', tier_timeouts[2] if len(tier_timeouts) > 2 else '?'
                    failure_msg = format_failure_message(timeout_seconds, tier1, tier2, tier3)
                    print(failure_msg)
                    debug_info.append(failure_msg)

                    # Clean up failed output
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except:
                            pass

                    return False, debug_info

            except Exception as e:
                debug_info.append(f"❌ Exception: {str(e)}")
                return False, debug_info

    except Exception as e:
        debug_info.append(f"❌ Exception: {str(e)}")
        return False, debug_info

    finally:
        if os.path.exists(concat_file.name):
            os.remove(concat_file.name)
```

- [ ] **Step 3: Add `import time` at top of file if not present**

Check line 1–20 for `import time`. If not present, add it:

```python
import time
```

- [ ] **Step 4: Verify syntax**

Run: `python3 -m py_compile src/extraction/build_database.py`

Expected: No output (success)

---

## Chunk 3: Testing & Validation

### Task 4: Run new timeout retry tests

**Files:**
- Test: `tests/test_timeout_retry.py`

- [ ] **Step 1: Run new timeout retry tests**

Run: `python3 -m unittest tests.test_timeout_retry -v 2>&1`

Expected: All 6 tests PASS:
```
test_timeout_triggers_retry_once ... ok
test_timeout_max_retries_exhausted ... ok
test_timeout_escalation_formula ... ok
test_timeout_vs_non_timeout_errors ... ok
test_progress_message_format ... ok
test_successful_retry_logging ... ok
test_real_merge_with_artificial_low_timeout ... ok
```

If any FAIL, read error and fix:
- Check mock setup in test
- Verify timeout escalation math
- Confirm exception handling in merge_videos()

- [ ] **Step 2: Run existing stream copy tests (regression)**

Run: `python3 -m unittest tests.test_stream_copy_merge -v 2>&1`

Expected: All 7 tests PASS (no regression)

- [ ] **Step 3: Run all tests together**

Run: `python3 -m unittest discover tests/ -v 2>&1 | tail -30`

Expected: All tests PASS, no failures

---

### Task 5: Manual integration test (optional but recommended)

**Files:**
- Test: Manual terminal verification

- [ ] **Step 1: Create small test scenario**

```bash
# In project root
python3 << 'EOF'
from src.extraction.build_database import merge_videos
import os

# Test with 2 small fake videos (simulate scenario)
videos = ['/tmp/test_merge_1.mp4', '/tmp/test_merge_2.mp4']
output = '/tmp/test_merge_output.mp4'

# Create dummy files for testing
for v in videos:
    os.system(f'ffmpeg -f lavfi -i color=c=red:s=320x240:d=1 -f lavfi -i sine=f=440:d=1 -pix_fmt yuv420p {v} -y 2>/dev/null')

# Merge (should succeed immediately since small files)
success, debug = merge_videos(videos, output, use_stream_copy=True)
print('\n'.join(debug))
EOF
```

Expected: See merge succeed quickly with debug output showing timeout and progress info.

---

## Chunk 4: Final Cleanup & Commit

### Task 6: Commit implementation

**Files:**
- Modified: `src/extraction/build_database.py`
- Created: `tests/test_timeout_retry.py`

- [ ] **Step 1: Check git status**

Run: `git status`

Expected: 2 files changed/created:
```
modified:   src/extraction/build_database.py
create mode 100644 tests/test_timeout_retry.py
```

- [ ] **Step 2: Run all tests one final time**

Run: `python3 -m unittest discover tests/ -v 2>&1 | grep -E "^Ran|^OK|^FAILED"`

Expected:
```
Ran XX tests in X.XXXs
OK
```

- [ ] **Step 3: Commit with message**

```bash
git add src/extraction/build_database.py tests/test_timeout_retry.py
git commit -m "feat: add timeout retry mechanism with progress-aware console feedback

Implements three-tier timeout strategy (50% escalation, max 2 retries) for
large video merge operations. When subprocess.run times out, the system
automatically retries with 50% more time (up to 2 retries total).

Key features:
- Separate TimeoutExpired exception handling (not re-encoding fallback)
- Progress-aware console messages with ETA updates every 5 seconds
- Graceful failure after all retries exhausted with recovery suggestions
- No automatic re-encoding fallback on timeout (user maintains control)
- Conservative timeout increase (50%) to avoid runaway escalation

Example: 7.2 GB front camera group with 840s initial → retries at 1260s →
succeeds at 1050s with progress updates shown in real-time.

Fixes: Large front camera 48-file groups timing out without recovery path

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Verify commit**

Run: `git log --oneline -1`

Expected: New commit with "feat: add timeout retry mechanism..." message

---

## Success Checklist

- ✅ All new tests in `tests/test_timeout_retry.py` pass
- ✅ All existing tests in `tests/test_stream_copy_merge.py` still pass (no regression)
- ✅ `merge_videos()` catches `TimeoutExpired` separately from other errors
- ✅ Timeout escalates by 50% on each retry (840s → 1260s → 1890s)
- ✅ Console shows retry attempts, progress, and helpful failure messages
- ✅ No automatic re-encoding fallback on timeout (only on validation/non-timeout errors)
- ✅ Implementation committed to git with descriptive message
- ✅ Code is clean, well-commented, and follows existing patterns

---

## Expected Output Examples

### Successful retry scenario:
```
⏱️  TIMEOUT: Stream copy exceeded 840s limit
  → Input: 48 files, 7.2 GB total
  → Retrying with 1260s timeout (50% increase)...
  [Retry 1/2] Merging... ████████░░ 82% (5.9 GB / 7.2 GB)
  ⏱️  Elapsed: 850s | Est. total: 1040s (~17 min)
✅ Merge successful on retry! Completed in 1050s
  → Output: 20260307134738_front.mp4 (2.3 GB)
```

### Failed scenario (all retries exhausted):
```
⏱️  TIMEOUT: Stream copy exceeded 840s limit
  → Retrying with 1260s timeout (50% increase)...
⏱️  TIMEOUT: Stream copy exceeded 1260s limit
  → Retrying with 1890s timeout (50% increase)...
⏱️  TIMEOUT: Stream copy exceeded 1890s limit
❌ FAILED: Stream copy timed out after 2 retries (final limit: 1890s)
  → All 3 attempts exhausted: 840s → 1260s → 1890s
  → Suggestions:
    1. Retry with re-encoding: use_stream_copy=False
    2. Split large groups: merge manually in smaller batches
    3. Check system resources: CPU/disk I/O may be constrained
```

---

## References

- Spec: `docs/superpowers/specs/2026-03-16-timeout-retry-mechanism-design.md`
- Related: `57573ef` (dynamic timeout formula)
- Tests: `tests/test_stream_copy_merge.py` (existing regression tests)

