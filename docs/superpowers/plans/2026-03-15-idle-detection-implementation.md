# Idle Detection Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement idle segment detection within trips, fix timestamp bugs, and output rich idle data to JSON + console logs.

**Architecture:** Fix GPS timestamps by extracting date from TAR filenames, fix timedelta comparison bug in idle detection, add idle segment analysis to trip validation, output results to JSON and console logs.

**Tech Stack:** Python 3.6+ stdlib, unittest mocks, TDD

---

## File Structure

**Modified Files:**
- `src/extraction/build_database.py` — Core implementation
  - Fix `detect_idle_segments()` timedelta bug
  - Add `tar_date` parameter to `merge_gps_points()`
  - Extract date from TAR filename in `extract_gps_from_tar()`
  - Add idle detection to main trip loop
  - Remove `split_group_by_idle()` function
  - Add console logging for idle periods
  - Update JSON output to include `idle_segments`

- `src/extraction/build_database_parallel.py` — Mirror changes for parallel build

**New Files:**
- `tests/test_idle_detection.py` — Comprehensive unit tests

---

## Chunk 1: Understand Current State & Write Tests (TDD Red Phase)

### Task 1: Write comprehensive idle detection unit tests

**Files:**
- Create: `tests/test_idle_detection.py`

- [ ] **Step 1: Create test file with failing tests**

```python
# tests/test_idle_detection.py
"""
Tests for idle detection with proper GPS data structure.
Run: python3 -m pytest tests/test_idle_detection.py -v
"""
import unittest
from datetime import datetime, timedelta
from src.extraction.build_database import (
    detect_idle_segments,
    merge_gps_points
)


class TestDetectIdleSegments(unittest.TestCase):
    """Test idle detection with proper GPS data structure."""

    def test_all_moving_no_idle(self):
        """No idle segments when all points have speed > threshold."""
        points = [
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 0, 0)},
            {'speed_kmh': 55, 'timestamp': datetime(2026, 3, 14, 6, 0, 10)},
            {'speed_kmh': 60, 'timestamp': datetime(2026, 3, 14, 6, 0, 20)},
        ]

        segments = detect_idle_segments(points, speed_threshold=0.5, duration_threshold=60)
        self.assertEqual(len(segments), 0, "No idle segments expected when all speeds > threshold")

    def test_short_idle_below_threshold(self):
        """Ignore idle periods shorter than duration_threshold."""
        points = [
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 0, 0)},
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 0, 30)},
            {'speed_kmh': 0.2, 'timestamp': datetime(2026, 3, 14, 6, 1, 0)},  # Idle 10 sec
            {'speed_kmh': 0.3, 'timestamp': datetime(2026, 3, 14, 6, 1, 10)},
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 1, 20)},
        ]

        segments = detect_idle_segments(points, speed_threshold=0.5, duration_threshold=60)
        self.assertEqual(len(segments), 0, "Idle segment <60s should be ignored")

    def test_long_idle_detected(self):
        """Detect idle periods longer than duration_threshold."""
        # 5 minutes of idle (moving slow)
        points = [
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 0, 0)},
        ]
        # Add 300 seconds of idle points
        for i in range(1, 300):
            points.append({
                'speed_kmh': 0.2 + (i % 2) * 0.1,
                'timestamp': datetime(2026, 3, 14, 6, 1, i)
            })
        points.append({'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 6, 0)})

        segments = detect_idle_segments(points, speed_threshold=0.5, duration_threshold=60)
        self.assertGreaterEqual(len(segments), 1, "Expected at least 1 idle segment")
        self.assertGreaterEqual(segments[0]['duration_s'], 200, "Idle duration should be ~300s")

    def test_idle_duration_is_float_seconds(self):
        """Verify idle segment duration is a number (seconds), not timedelta."""
        points = [
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 0, 0)},
            {'speed_kmh': 0.2, 'timestamp': datetime(2026, 3, 14, 6, 1, 0)},
            {'speed_kmh': 0.2, 'timestamp': datetime(2026, 3, 14, 6, 2, 0)},
            {'speed_kmh': 0.2, 'timestamp': datetime(2026, 3, 14, 6, 3, 0)},
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 4, 0)},
        ]

        segments = detect_idle_segments(points, speed_threshold=0.5, duration_threshold=60)
        self.assertEqual(len(segments), 1, "Expected 1 idle segment")

        # CRITICAL: duration_s must be a number, not timedelta
        self.assertIsInstance(segments[0]['duration_s'], (int, float),
                             "duration_s must be int or float, not timedelta")
        self.assertGreater(segments[0]['duration_s'], 100, "Duration should be > 100 seconds")

    def test_idle_segment_has_required_fields(self):
        """Idle segment must have all required fields for JSON output."""
        points = [
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 0, 0)},
            {'speed_kmh': 0.2, 'timestamp': datetime(2026, 3, 14, 6, 1, 0)},
            {'speed_kmh': 0.2, 'timestamp': datetime(2026, 3, 14, 6, 2, 0)},
            {'speed_kmh': 0.2, 'timestamp': datetime(2026, 3, 14, 6, 3, 0)},
            {'speed_kmh': 50, 'timestamp': datetime(2026, 3, 14, 6, 4, 0)},
        ]

        segments = detect_idle_segments(points, speed_threshold=0.5, duration_threshold=60)
        self.assertGreater(len(segments), 0)

        seg = segments[0]
        required_fields = ['start_index', 'end_index', 'duration_s', 'distance_km']
        for field in required_fields:
            self.assertIn(field, seg, f"Idle segment missing required field: {field}")


class TestMergeGpsPointsTimestamp(unittest.TestCase):
    """Test GPS point merging preserves and creates proper timestamps."""

    def test_timestamp_is_datetime_object(self):
        """Timestamps should be datetime objects, not strings or placeholders."""
        rmc_points = {
            '060100': {  # 06:01:00
                'lat': 40.0,
                'lon': -74.0,
                'speed_knots': 10.0,
                'heading': 90.0
            }
        }
        gga_points = {}
        tar_date = datetime(2026, 3, 14).date()

        result = merge_gps_points(rmc_points, gga_points, tar_date=tar_date)

        self.assertGreater(len(result), 0, "Should have GPS points")
        point = result[0]
        self.assertIn('timestamp', point, "Point must have timestamp")
        self.assertIsInstance(point['timestamp'], datetime, "Timestamp must be datetime object")

        # Critical: date must be actual date, not 2000-01-01
        self.assertNotEqual(point['timestamp'].year, 2000,
                           "Timestamp should NOT have placeholder year 2000")
        self.assertEqual(point['timestamp'].year, 2026, "Should use actual year from tar_date")
        self.assertEqual(point['timestamp'].month, 3, "Should use actual month")
        self.assertEqual(point['timestamp'].day, 14, "Should use actual day")


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run tests to confirm they FAIL (red phase)**

```bash
cd /Users/fabianosilva/Documentos/code/ddpai_extractor/.worktrees/feature-ffmpeg-progress-visibility
python3 -m pytest tests/test_idle_detection.py -v
```

Expected output:
- `TypeError: '>=' not supported between instances of 'datetime.timedelta' and 'int'` (from test_idle_duration_is_float_seconds)
- Assertion errors about timestamp year being 2000 (from test_timestamp_is_datetime_object)

---

## Chunk 2: Fix Timestamp Bug (GPS Date Extraction)

### Task 2: Add tar_date parameter to merge_gps_points()

**Files:**
- Modify: `src/extraction/build_database.py:merge_gps_points()` (line ~280)

- [ ] **Step 1: Update merge_gps_points signature and implementation**

Find the `merge_gps_points()` function and replace:

```python
def merge_gps_points(rmc_points, gga_points):
    """Merge RMC and GGA points into comprehensive records."""
    points = []

    for time_key, rmc in rmc_points.items():
        lat, lon = rmc['lat'], rmc['lon']
        # ... existing code ...

        # OLD: Placeholder date
        timestamp = datetime(2000, 1, 1, hour, minute, second)

        points.append({
            'lat': lat,
            'lon': lon,
            'speed_kmh': speed_kmh,
            'altitude': altitude,
            'heading': heading
        })
```

With:

```python
def merge_gps_points(rmc_points, gga_points, tar_date=None):
    """Merge RMC and GGA points into comprehensive records.

    Args:
        rmc_points: Dict of RMC GPS records
        gga_points: Dict of GGA GPS records
        tar_date: datetime.date object for timestamp (e.g., from TAR filename)
    """
    if tar_date is None:
        tar_date = datetime.now().date()

    points = []

    for time_key, rmc in rmc_points.items():
        lat, lon = rmc['lat'], rmc['lon']
        # ... existing code ...

        # Parse timestamp from time_key (format: HHMMSS)
        try:
            if len(time_key) >= 6:
                hour = int(time_key[0:2])
                minute = int(time_key[2:4])
                second = int(time_key[4:6])
                # NEW: Use actual date from tar_date
                from datetime import time
                timestamp = datetime.combine(tar_date, time(hour, minute, second))
            else:
                timestamp = datetime.now()
        except (ValueError, IndexError):
            timestamp = datetime.now()

        points.append({
            'lat': lat,
            'lon': lon,
            'speed_kmh': speed_kmh,
            'altitude': altitude,
            'heading': heading,
            'timestamp': timestamp
        })
```

**Note:** Add `from datetime import time` at the top of the file if not already there.

- [ ] **Step 2: Update extract_gps_from_tar() to extract and pass tar_date**

Find `extract_gps_from_tar()` function and replace:

```python
def extract_gps_from_tar(tar_path):
    """Extract all GPS points from tar file."""
    points = []

    try:
        with tarfile.open(tar_path, 'r:') as tar:
            for member in tar.getmembers():
                if member.name.endswith('.gpx'):
                    f = tar.extractfile(member)
                    if f:
                        nmea_content = f.read().decode('utf-8', errors='ignore')
                        rmc, gga = extract_gps_from_nmea(nmea_content)
                        merged = merge_gps_points(rmc, gga)
                        points.extend(merged)
```

With:

```python
def extract_gps_from_tar(tar_path):
    """Extract all GPS points from tar file."""
    points = []

    # Extract date from TAR filename (e.g., 20260314060147 → 2026-03-14)
    tar_basename = os.path.basename(tar_path).replace('.git', '')
    tar_date = None
    try:
        if len(tar_basename) >= 8:
            date_str = tar_basename[:8]  # YYYYMMDD
            tar_date = datetime.strptime(date_str, '%Y%m%d').date()
    except ValueError:
        tar_date = None

    try:
        with tarfile.open(tar_path, 'r:') as tar:
            for member in tar.getmembers():
                if member.name.endswith('.gpx'):
                    f = tar.extractfile(member)
                    if f:
                        nmea_content = f.read().decode('utf-8', errors='ignore')
                        rmc, gga = extract_gps_from_nmea(nmea_content)
                        # NEW: Pass tar_date to merge_gps_points
                        merged = merge_gps_points(rmc, gga, tar_date=tar_date)
                        points.extend(merged)
```

- [ ] **Step 3: Run tests to verify timestamp fix**

```bash
python3 -m pytest tests/test_idle_detection.py::TestMergeGpsPointsTimestamp -v
```

Expected: Tests PASS (timestamps have correct year, month, day)

- [ ] **Step 4: Commit**

```bash
git add src/extraction/build_database.py tests/test_idle_detection.py
git commit -m "fix: extract actual date from TAR filename for GPS timestamps

- Add tar_date parameter to merge_gps_points()
- Extract YYYYMMDD from TAR basename in extract_gps_from_tar()
- GPS timestamps now use actual date, not 2000-01-01 placeholder
- Fixes TestMergeGpsPointsTimestamp tests"
```

---

## Chunk 3: Fix Timedelta Bug (Duration Calculation)

### Task 3: Fix detect_idle_segments() timedelta comparison

**Files:**
- Modify: `src/extraction/build_database.py:detect_idle_segments()` (line ~175-240)

- [ ] **Step 1: Find and fix the timedelta bug**

Locate this code in `detect_idle_segments()`:

```python
if in_idle:
    # End of idle period - check if duration meets threshold
    idle_end_idx = i - 1
    idle_points = points[idle_start_idx:idle_end_idx + 1]

    # This is wrong - duration_s is a timedelta, not seconds!
    duration_s = idle_points[-1]['timestamp'] - idle_points[0]['timestamp']

    if duration_s >= duration_threshold:  # ← TypeError here!
        # ... append segment ...
```

Replace with:

```python
if in_idle:
    # End of idle period - check if duration meets threshold
    idle_end_idx = i - 1
    idle_points = points[idle_start_idx:idle_end_idx + 1]

    # FIX: Convert timedelta to seconds
    end_time = idle_points[-1].get('timestamp', datetime.now())
    start_time = idle_points[0].get('timestamp', datetime.now())
    duration_delta = end_time - start_time
    duration_s = duration_delta.total_seconds()  # ← Now it's a number!

    if duration_s >= duration_threshold:  # ← No TypeError now
        # Calculate other segment properties
        distance_km = idle_points[-1].get('cumulative_distance_km', 0) - \
                     idle_points[0].get('cumulative_distance_km', 0)

        idle_segments.append({
            'start_index': idle_start_idx,
            'end_index': idle_end_idx,
            'duration_s': duration_s,
            'distance_km': distance_km,
            'points': idle_points
        })
```

- [ ] **Step 2: Verify duration_s is used correctly elsewhere**

Search for all references to `duration_s` in the function to ensure they treat it as a number:

```bash
grep -n "duration_s" src/extraction/build_database.py | grep -A2 -B2 "detect_idle"
```

All uses should be: `duration_s / 60` (convert to minutes) or `duration_s >= threshold` comparisons.

- [ ] **Step 3: Run tests to verify timedelta fix**

```bash
python3 -m pytest tests/test_idle_detection.py::TestDetectIdleSegments -v
```

Expected: Tests PASS (no TypeError, duration_s is float/int, not timedelta)

- [ ] **Step 4: Commit**

```bash
git add src/extraction/build_database.py
git commit -m "fix: convert timedelta to seconds in detect_idle_segments()

- Calculate duration_s as (end_time - start_time).total_seconds()
- Fixes TypeError: '>=' not supported between timedelta and int
- All idle detection tests now passing"
```

---

## Chunk 4: Add Idle Detection to Main Flow

### Task 4: Integrate idle detection into trip validation

**Files:**
- Modify: `src/extraction/build_database.py:main()` trip loop (line ~950+)

- [ ] **Step 1: Create helper function to build rich idle segment data**

Add this function before `main()`:

```python
def build_idle_segment_data(idle_segment, all_points):
    """Build rich idle segment data for JSON output.

    Args:
        idle_segment: Dict from detect_idle_segments()
        all_points: All GPS points in the trip

    Returns:
        Dict with rich idle segment data
    """
    start_idx = idle_segment['start_index']
    end_idx = idle_segment['end_index']
    idle_points = idle_segment.get('points', all_points[start_idx:end_idx+1])

    if not idle_points:
        return None

    start_point = idle_points[0]
    end_point = idle_points[-1]

    # Calculate speed statistics
    speeds = [p.get('speed_kmh', 0) for p in idle_points]
    avg_speed = sum(speeds) / len(speeds) if speeds else 0

    return {
        'start_index': start_idx,
        'end_index': end_idx,
        'duration_seconds': idle_segment['duration_s'],
        'distance_km': idle_segment['distance_km'],
        'start_time': start_point['timestamp'].strftime('%H:%M:%S'),
        'end_time': end_point['timestamp'].strftime('%H:%M:%S'),
        'start_location': {
            'lat': start_point['lat'],
            'lon': start_point['lon']
        },
        'end_location': {
            'lat': end_point['lat'],
            'lon': end_point['lon']
        },
        'avg_speed_kmh': round(avg_speed, 2),
        'min_speed_kmh': round(min(speeds), 2) if speeds else 0,
        'max_speed_kmh': round(max(speeds), 2) if speeds else 0
    }
```

- [ ] **Step 2: Add idle detection to group validation loop**

Find where groups are processed in `main()` and add this after extracting GPS:

```python
# In the trip processing loop, after extracting GPS points:
all_points = []
for tar_path in group:
    points = extract_gps_from_tar(tar_path)
    all_points.extend(points)

# NEW: Detect idle segments
print("  🛑 Analyzing idle periods...")
idle_segments = detect_idle_segments(all_points,
                                     speed_threshold=IDLE_SPEED_THRESHOLD,
                                     duration_threshold=IDLE_DURATION_THRESHOLD)

# Build rich idle segment data
rich_idle_segments = []
for seg in idle_segments:
    rich_seg = build_idle_segment_data(seg, all_points)
    if rich_seg:
        rich_idle_segments.append(rich_seg)
        # Console log
        print(f"    • {seg['start_index']}-{seg['end_index']}: "
              f"{seg['duration_s']:.0f}s idle, {seg['distance_km']:.2f} km")

# Store in group data
group_data['idle_segments'] = rich_idle_segments

print(f"  Found {len(rich_idle_segments)} idle periods")
```

- [ ] **Step 3: Run build to verify integration**

```bash
./build.sh /Volumes/ddpai/DCIM/203gps/tar /Volumes/ddpai/DCIM/200video/rear /Volumes/ddpai/DCIM/200video/front
```

Expected:
- No TypeError
- Console shows "Found X idle periods" for each group
- Idle periods logged with indices and duration

- [ ] **Step 4: Commit**

```bash
git add src/extraction/build_database.py
git commit -m "feat: integrate idle detection into trip validation loop

- Add build_idle_segment_data() helper for rich segment data
- Detect idle periods for each validated trip
- Console logging shows idle periods with duration/distance
- Idle segments ready for JSON output"
```

---

## Chunk 5: Remove Dead Code & Update JSON Output

### Task 5: Remove split_group_by_idle() and add JSON output

**Files:**
- Modify: `src/extraction/build_database.py` main flow

- [ ] **Step 1: Find and delete split_group_by_idle() function**

Search for:

```bash
grep -n "def split_group_by_idle" src/extraction/build_database.py
```

Delete the entire function (typically ~100+ lines).

- [ ] **Step 2: Remove any calls to split_group_by_idle()**

Search:

```bash
grep -n "split_group_by_idle" src/extraction/build_database.py
```

Should be zero results after deletion.

- [ ] **Step 3: Verify trips.json includes idle_segments**

The `idle_segments` array should already be in the trip data from Step 4. Just verify the JSON write includes it:

```bash
python3 -c "import json; d=json.load(open('data/trips.json')); print(d['trips'][0].get('idle_segments', 'NOT FOUND'))"
```

Expected: Array of idle segment objects (or empty array if no idles detected).

- [ ] **Step 4: Run full test suite**

```bash
python3 -m pytest tests/test_idle_detection.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/extraction/build_database.py
git commit -m "refactor: remove split_group_by_idle() - not needed for marking feature

- split_group_by_idle() was solving the wrong problem (splitting, not marking)
- Idle detection now purely for visualization within trips
- All tests passing, build verified working"
```

---

## Chunk 6: Mirror Changes to Parallel Build

### Task 6: Apply same fixes to build_database_parallel.py

**Files:**
- Modify: `src/extraction/build_database_parallel.py`

- [ ] **Step 1: Update merge_gps_points call in parallel build**

Find `merge_gps_points()` calls and add `tar_date` parameter:

```bash
grep -n "merge_gps_points" src/extraction/build_database_parallel.py
```

Update to pass `tar_date` just like in sequential build.

- [ ] **Step 2: Remove any split_group_by_idle calls**

```bash
grep -n "split_group_by_idle" src/extraction/build_database_parallel.py
```

Delete if found.

- [ ] **Step 3: Verify imports are correct**

Both files should import from build_database:

```bash
grep "^from src.extraction.build_database import" src/extraction/build_database_parallel.py
```

Should include: `detect_idle_segments`, `merge_gps_points`, `extract_gps_from_tar`

- [ ] **Step 4: Run parallel build test**

```bash
./tools/build_parallel.sh /Volumes/ddpai/DCIM/203gps/tar /Volumes/ddpai/DCIM/200video/rear /Volumes/ddpai/DCIM/200video/front
```

Expected: Same output as sequential build, with idle detection working

- [ ] **Step 5: Commit**

```bash
git add src/extraction/build_database_parallel.py
git commit -m "fix: apply idle detection fixes to parallel build

- Mirror timestamp and idle detection fixes
- Remove split_group_by_idle calls
- Parallel build now supports rich idle segment data"
```

---

## Verification Checklist

```bash
# 1. All unit tests pass
python3 -m pytest tests/test_idle_detection.py -v

# 2. No TypeError in code
grep -n "duration_s >=" src/extraction/build_database.py  # Should show fix with .total_seconds()

# 3. merge_gps_points has tar_date parameter
grep -n "def merge_gps_points" src/extraction/build_database.py

# 4. split_group_by_idle is removed
grep -n "def split_group_by_idle" src/extraction/build_database.py  # Should return nothing

# 5. Build completes without errors
./build.sh /Volumes/ddpai/DCIM/203gps/tar /Volumes/ddpai/DCIM/200video/rear /Volumes/ddpai/DCIM/200video/front

# 6. JSON has idle_segments
python3 -c "import json; print('idle_segments' in json.load(open('data/trips.json'))['trips'][0])"

# 7. Parallel build works
./tools/build_parallel.sh /Volumes/ddpai/DCIM/203gps/tar /Volumes/ddpai/DCIM/200video/rear /Volumes/ddpai/DCIM/200video/front
```

---

## Testing Strategy

**Unit Tests:** `tests/test_idle_detection.py`
- Idle detection with various speed profiles
- Duration calculation correctness (not timedelta)
- Timestamp with proper date

**Integration Tests:**
- Full build with actual SD card data
- Verify idle_segments in JSON output
- Verify console logging

**Manual Verification:**
- Run `./watch.sh`
- Confirm no errors, idle detection working
- Inspect `data/trips.json` for idle_segments array
