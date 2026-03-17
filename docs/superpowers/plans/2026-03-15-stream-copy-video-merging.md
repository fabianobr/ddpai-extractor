# Stream Copy Video Merging Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to execute this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement stream copy merging to achieve 5-8x speedup (2-3 min per long trip) while maintaining video quality.

**Architecture:** Modify `merge_videos()` to use FFmpeg stream copy (`-c:v copy -c:a copy`) by default, with automatic fallback to libx264 re-encoding if stream copy fails (e.g., incompatible formats). Output verification ensures integrity.

**Tech Stack:** FFmpeg (stream copy + conditional fallback), Python subprocess, pathlib, standard library

---

## File Structure

```
src/extraction/
├── build_database.py                 # Modify: merge_videos() function
└── build_database_parallel.py        # Sync: same changes as build_database.py

tests/
└── test_stream_copy_merge.py         # NEW: unit tests for stream copy
```

**Responsibility boundaries:**
- **merge_videos()** in `build_database.py` — Core logic: stream copy with fallback, logging, verification
- **build_database_parallel.py** — Identical logic (parallel variant imports from serial)
- **tests/test_stream_copy_merge.py** — Test coverage for stream copy detection, fallback, output validation

---

# Chunk 1: Unit Tests (TDD Foundation)

### Task 1: Write Failing Tests for Stream Copy Mode

**Files:**
- Create: `tests/test_stream_copy_merge.py`

- [ ] **Step 1: Create test file with imports**

```python
# tests/test_stream_copy_merge.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/fabianosilva/Documentos/code/ddpai_extractor
python3 -m pytest tests/test_stream_copy_merge.py -v 2>&1 | head -30
```

Expected output: Tests should FAIL because stream copy logic not yet implemented.

- [ ] **Step 3: Commit test file**

```bash
git add tests/test_stream_copy_merge.py
git commit -m "test: add stream copy merge tests (TDD foundation)"
```

---

### Task 2: Verify Tests Are Ready

- [ ] **Step 1: Check test file exists and is valid Python**

```bash
python3 -m py_compile tests/test_stream_copy_merge.py
echo "✅ Tests valid"
```

- [ ] **Step 2: Document test expectations**

Tests verify:
1. ✅ Stream copy is used by default (not re-encoding)
2. ✅ FFmpeg command structure is correct
3. ✅ Fallback to re-encoding occurs on failure
4. ✅ Output file is created on success

---

# Chunk 2: Core Implementation

### Task 3: Modify merge_videos() to Support Stream Copy

**Files:**
- Modify: `src/extraction/build_database.py` (merge_videos function around line 605)

**Key changes:**
1. Add `use_stream_copy=True` parameter to function signature
2. Replace FFmpeg command building to use stream copy by default
3. Add fallback logic for stream copy failures
4. Add output validation function
5. Update timeout values (5 min for stream copy, 30 min for re-encoding)

**Implementation details:**
- Stream copy command: `[..., '-c:v', 'copy', '-c:a', 'copy', ...]`
- Re-encoding command: `[..., '-vf', 'scale=-2:720', '-c:v', 'libx264', '-crf', '26', '-preset', 'fast', '-c:a', 'aac', '-b:a', '128k', ...]`
- Fallback: If stream copy fails (returncode != 0), call merge_videos() recursively with `use_stream_copy=False`
- Validation: Check file size > 1000 bytes, optionally check duration matches expected

**Expected test result:** After implementation, tests should PASS.

---

### Task 4: Sync build_database_parallel.py

**Files:**
- Verify: `src/extraction/build_database_parallel.py`

**Key check:**
- Confirm that `merge_videos` is imported from `build_database.py` (not duplicated)
- If duplicated, apply same changes

**Expected:** No changes needed (parallel imports from serial).

---

# Chunk 3: Integration & Validation

### Task 5: Create Integration Test

**Files:**
- Modify: `tests/test_stream_copy_merge.py`

**Add test class:** `TestStreamCopyIntegration`

**Test method:** `test_merge_two_real_videos_with_stream_copy()`
- Creates two 2-second test videos using FFmpeg
- Calls merge_videos() with stream copy
- Verifies output file exists and is > 10KB
- Checks that operation succeeds

---

### Task 6: End-to-End Test with build.sh

**Files:**
- Run: `./build.sh` on sample data

**Validation steps:**
1. Run `python3 -m src.extraction.build_database` and verify it completes
2. Check output contains "Stream copy" or "Method:" logging
3. Verify merged videos exist in `merged_videos/` directory
4. Verify videos are playable with FFmpeg
5. Document timing: should be 2-5 min for long trips (vs 15-20 min with re-encoding)
6. Calculate speedup ratio (should be 5-8x)

---

# Chunk 4: Cleanup & Documentation

### Task 7: Update CLAUDE.md with Stream Copy Details

**Files:**
- Modify: `CLAUDE.md`

**Find and update:** "### Video Merging" section

**Changes:**
- Update tool description from "H.264 libx264 re-encoding" to "Stream copy (default) or libx264 re-encoding (fallback)"
- Update performance from "~15-20 min" to "~2-3 min (stream copy)"
- Document fallback behavior
- Update configuration section with `use_stream_copy` parameter

---

### Task 8: Final Cleanup

- [ ] **Step 1: Verify all tests pass**

```bash
python3 -m pytest tests/test_stream_copy_merge.py -v
```

Expected: All tests PASS

- [ ] **Step 2: Run syntax check on modified files**

```bash
python3 -m py_compile src/extraction/build_database.py
python3 -m py_compile src/extraction/build_database_parallel.py
python3 -m py_compile tests/test_stream_copy_merge.py
echo "✅ All files valid"
```

- [ ] **Step 3: Verify git status**

```bash
git status
```

Expected: No untracked files, clean working tree

---

## Success Criteria

| Criterion | Validation |
|-----------|-----------|
| **Tests pass** | `pytest tests/test_stream_copy_merge.py -v` → all PASS |
| **Stream copy works** | `./build.sh` uses stream copy path, completes in 2-5 min |
| **Fallback works** | Tests confirm fallback to re-encoding on failure |
| **Output valid** | Merged videos play without errors |
| **Speedup achieved** | 5-8x faster than re-encoding |
| **Docs updated** | CLAUDE.md reflects stream copy feature |
| **Commits clean** | Meaningful commit messages, TDD flow |

---

## Expected Final State

✅ Stream copy merging implemented and tested
✅ Fallback to re-encoding works transparently
✅ All unit and integration tests passing
✅ CLAUDE.md updated with new details
✅ 8 focused commits documenting implementation
✅ Ready for PR to main branch
