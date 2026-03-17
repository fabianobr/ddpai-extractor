# Timeout Retry Mechanism with Progress-Aware Console Feedback

**Date:** March 16, 2026
**Status:** Design Approved
**Author:** Claude Code (Brainstorming Session)

---

## Executive Summary

When FFmpeg merge operations timeout during video concatenation, the system will intelligently retry with 50% additional time (maximum 2 retries) while displaying progress updates and estimated time remaining. After 2 failed retries, the operation fails gracefully with a helpful error message and suggestions for recovery. No automatic fallback to re-encoding occurs.

**Problem:** Large front camera groups (48 files, 7.2 GB) timeout at the initial timeout limit, leaving no recovery path except manual intervention.

**Solution:** Conservative retry strategy (50% time increase) with progress-aware console feedback to keep users informed during extended operations.

---

## Architecture

### Three-Tier Timeout Strategy

| Tier | Scenario | Timeout Calculation | Example (7.2 GB) |
|------|----------|-------------------|------------------|
| **Tier 1** | Initial attempt | `max(300, int(total_size / 10) + 120)` | 840s (14 min) |
| **Tier 2** | Retry 1 (timeout) | Previous × 1.5 | 1,260s (21 min) |
| **Tier 3** | Retry 2 (timeout) | Previous × 1.5 | 1,890s (31.5 min) |

**Design rationale:**
- 50% increase is conservative — avoids runaway timeout escalation
- Assumes USB/SD card I/O bottleneck improves as thermal conditions stabilize
- Maximum 3 total attempts (1 initial + 2 retries) limits total wait time
- No automatic fallback to H.264 re-encoding — user maintains control

### Exception Handling Flow

```
subprocess.run(ffmpeg_cmd, timeout=timeout_seconds)
    ↓
[Completes successfully] → Validate output → Return True
    ↓
[Returns non-zero exit] → Log error → Fallback to re-encoding → Retry
    ↓
[TimeoutExpired raised] → Catch specifically → Check retry count
                              ↓
                         Retry < 2? → Increase timeout → Retry FFmpeg
                              ↓
                         Retry >= 2? → Log failure → Return False + suggestions
```

**Key distinction:** `TimeoutExpired` exceptions are handled separately from `returncode != 0` errors. Timeouts trigger retry logic; other FFmpeg errors trigger re-encoding fallback (existing behavior preserved).

### Console Feedback Format

#### Before Retry Begins
```
⏱️  TIMEOUT: Stream copy exceeded {current_timeout}s limit
  → Input: {file_count} files, {total_size:.1f} GB total
  → Retrying with {new_timeout}s timeout ({percent_increase}% increase)...
```

**Example:**
```
⏱️  TIMEOUT: Stream copy exceeded 840s limit
  → Input: 48 files, 7.2 GB total
  → Retrying with 1260s timeout (50% increase)...
```

#### During Retry (Real-time Progress)
```
  [Retry {attempt}/2] Merging... {progress_bar} {percent}% ({processed_size:.1f} GB / {total_size:.1f} GB)
  ⏱️  Elapsed: {elapsed_time}s | Est. total: {estimated_total}s (~{est_minutes} min)
```

**Example:**
```
  [Retry 1/2] Merging... ████████░░ 82% (5.9 GB / 7.2 GB)
  ⏱️  Elapsed: 850s | Est. total: 1040s (~17 min)
```

Progress updates every 5 seconds (or as data becomes available).

#### After Successful Retry
```
✅ Merge successful on retry! Completed in {actual_time}s
  → Output: {filename} ({output_size:.1f} MB)
```

#### After All Retries Exhausted
```
❌ FAILED: Stream copy timed out after 2 retries (final limit: {final_timeout}s)
  → All 3 attempts exhausted: {tier1_time}s → {tier2_time}s → {tier3_time}s
  → Suggestions:
    1. Retry with re-encoding: use_stream_copy=False
    2. Split large groups: merge manually in smaller batches
    3. Check system resources: CPU/disk I/O may be constrained
```

---

## Implementation Details

### File Modifications

**Primary file:** `src/extraction/build_database.py`

**Function to modify:** `merge_videos()` (lines 625–799)

**Changes required:**

1. **Wrap subprocess.run in retry loop:**
   ```python
   max_retries = 2
   for retry_attempt in range(max_retries + 1):  # 0, 1, 2
       try:
           result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
       except subprocess.TimeoutExpired:
           if retry_attempt < max_retries:
               # Handle retry (increase timeout, continue loop)
           else:
               # All retries exhausted (fail gracefully)
   ```

2. **Add timeout escalation logic:**
   ```python
   if retry_attempt > 0:
       timeout_seconds = int(timeout_seconds * 1.5)
   ```

3. **Add progress tracking:**
   - Call `estimate_ffmpeg_progress()` every 5 seconds during subprocess.run
   - Update console with progress bar and ETA
   - Requires parsing FFmpeg stderr or using `ffprobe` queries

4. **Add timeout-specific debug info:**
   ```python
   debug_info.append(f"Attempt {retry_attempt + 1}/3: timeout={timeout_seconds}s")
   ```

### New Helper Functions

#### `estimate_ffmpeg_progress(start_time, total_size, sample_interval=5)`
**Purpose:** Estimate progress percentage and ETA based on elapsed time and input size.

**Logic:**
- Calculate elapsed time since FFmpeg started
- Estimate bytes processed using: `(elapsed_time / estimated_total) * total_size`
- For better accuracy, query FFmpeg's output frame count via `ffprobe` (if available)
- Return: `(percent_complete, bytes_processed, estimated_total_time)`

**Fallback:** If progress cannot be determined, skip progress display (no error).

#### `format_retry_message(attempt, current_timeout, new_timeout, total_size, file_count)`
**Purpose:** Build consistent console feedback messages for retry events.

**Returns:** Formatted string with timeout info and suggestion for user action.

#### `calculate_eta(elapsed_seconds, bytes_processed, total_bytes)`
**Purpose:** Calculate estimated time remaining based on current processing rate.

**Logic:**
- Rate: `bytes_per_second = bytes_processed / elapsed_seconds`
- Remaining bytes: `total_bytes - bytes_processed`
- ETA: `remaining_bytes / rate`
- Return: `(estimated_seconds, estimated_minutes)`

### Console Output Timing

- **Timeout detected:** Print immediately (no delay)
- **Retry begins:** Print immediately before subprocess.run
- **Progress updates:** Every 5 seconds (configurable) during merge
- **Success/failure:** Print immediately upon completion

**No buffering:** All output goes directly to stdout via `print()` for real-time visibility.

---

## Testing Strategy

### Unit Tests (`tests/test_timeout_retry.py` — new file)

1. **test_timeout_triggers_retry_once**
   - Mock `subprocess.run()` to raise `TimeoutExpired` on first call, succeed on second
   - Verify retry happens with 50% increased timeout
   - Verify console message contains "Retry 1/2"

2. **test_timeout_max_retries_exhausted**
   - Mock `subprocess.run()` to raise `TimeoutExpired` on all 3 calls
   - Verify function returns `False` after all retries fail
   - Verify console message contains "all retries exhausted" and suggestions

3. **test_timeout_escalation_formula**
   - Verify timeout increases by exactly 50% on each retry
   - Example: 840s → 1260s → 1890s

4. **test_progress_message_format**
   - Mock progress tracking, verify console messages match expected format
   - Check for: progress bar, percentage, size breakdown, ETA

5. **test_successful_retry_logging**
   - Verify debug_info contains successful retry details
   - Check timing is accurately logged

### Integration Tests

6. **test_real_merge_with_artificial_low_timeout**
   - Create two real test videos
   - Set artificially low timeout to trigger timeout
   - Verify retry succeeds with higher timeout
   - Confirm output is valid

### Regression Tests

7. **test_non_timeout_errors_still_fallback**
   - Verify FFmpeg errors (non-timeout) still trigger re-encoding fallback
   - Ensure existing fallback behavior is unchanged

8. **test_all_existing_stream_copy_tests_pass**
   - Run all existing tests from `tests/test_stream_copy_merge.py`
   - Ensure no regression in stream copy or re-encoding logic

---

## Success Criteria

- ✅ **Timeout detection:** `subprocess.TimeoutExpired` caught and handled separately
- ✅ **Retry mechanism:** Timeouts trigger up to 2 retries with 50% timeout increase
- ✅ **Console feedback:** Progress-aware messages with ETA (every 5 seconds)
- ✅ **No re-encoding fallback:** Timeouts don't automatically switch to re-encoding
- ✅ **Graceful failure:** After 2 retries, fails with helpful error message
- ✅ **Backward compatibility:** All existing tests pass; no changes to re-encoding fallback
- ✅ **Example scenario:** 7.2 GB front camera group with 840s initial timeout → retries at 1260s → succeeds within ~17 minutes
- ✅ **User visibility:** Every state change (timeout, retry, progress, success/failure) logged to console in real-time

---

## Example Run-Through

### Scenario: 48-file front camera group (7.2 GB)

**Initial attempt (Tier 1, 840s):**
```
  Running FFmpeg (stream copy)...
  Timeout: 840s (based on 7200 MB input)
  [Processing 48 files...]
  ⏱️  TIMEOUT: Stream copy exceeded 840s limit
```

**Retry 1 (Tier 2, 1260s):**
```
  → Input: 48 files, 7.2 GB total
  → Retrying with 1260s timeout (50% increase)...
  [Retry 1/2] Merging... ████████░░ 82% (5.9 GB / 7.2 GB)
  ⏱️  Elapsed: 850s | Est. total: 1040s (~17 min)
  ✅ Merge successful on retry! Completed in 1050s
    → Output: 20260307134738_front.mp4 (2.3 GB)
```

### Scenario: Persistent timeout (all retries fail)

```
  ⏱️  TIMEOUT: Stream copy exceeded 840s limit
  → Retrying with 1260s timeout (50% increase)...
  [Retry 1/2] Merging... ████████░░ 45% (3.2 GB / 7.2 GB)
  ⏱️  TIMEOUT: Stream copy exceeded 1260s limit
  → Retrying with 1890s timeout (50% increase)...
  [Retry 2/2] Merging... ██░░░░░░░░ 25% (1.8 GB / 7.2 GB)
  ⏱️  TIMEOUT: Stream copy exceeded 1890s limit
  ❌ FAILED: Stream copy timed out after 2 retries (final limit: 1890s)
    → All 3 attempts exhausted: 840s → 1260s → 1890s
    → Suggestions:
      1. Retry with re-encoding: use_stream_copy=False
      2. Split large groups: merge manually in smaller batches
      3. Check system resources: CPU/disk I/O may be constrained
```

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Retry loop adds 30–60 min total time | User perception of slowness | Clear ETA and progress feedback; document expected times in CLAUDE.md |
| Progress tracking adds CPU overhead | Reduced merge speed | Use lightweight `ffprobe` queries; cache results; fallback to silent mode if unavailable |
| Timeout values still too optimistic | Further retries fail | Monitor real-world timing data; refine formula after first production run |
| Retry logic breaks existing fallback | Re-encoding fallback fails | Separate timeout handling from returncode handling; extensive regression testing |

---

## Future Enhancements (Out of Scope)

- Adaptive timeout learning: track actual merge times and adjust formula dynamically
- Parallel retry: spawn multiple merge attempts with different methods simultaneously
- User configuration: allow timeout override via CLI flag or config file
- Metrics collection: log timeout frequencies to identify problematic file groups

---

## References

- **Previous work:** `57573ef` - Dynamic timeout formula (scales from input size)
- **Existing tests:** `tests/test_stream_copy_merge.py` - Stream copy and fallback tests
- **Related CLAUDE.md:** Section on video merging, performance notes

