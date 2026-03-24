# GPS Sort Fix + Timestamp-Based Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix GPS points being sorted by lat/lon instead of timestamp, eliminating the 400–800 m marker teleports that occur every 60 seconds during video playback.

**Architecture:** One-line sort fix in `merge_gps_points()` + add `time_offset_s` as 6th element to each point in both build files + replace linear index interpolation with binary search in the frontend. The parallel build inherits the sort fix via import — only the points assembly needs updating there.

**Tech Stack:** Python 3 (`src/extraction/`), Vanilla JS (`web/index.html`), pytest (static analysis tests)

---

## File Structure

| File | Change |
|------|--------|
| `tests/test_gps_sort.py` | **Create** — regression tests for sort key and 6-element points |
| `src/extraction/build_database.py` | **Modify** line 421 (sort key) + lines 1351–1354 (`points_for_db`) |
| `src/extraction/build_database_parallel.py` | **Modify** line 270 (inline points comprehension) |
| `web/index.html` | **Modify** lines 668–670 (binary search in `onVideoTimeUpdate`) + line 900 (fix `onMapClick` seek) |

---

## Task 1: Write Failing Regression Tests (TDD)

**Files:**
- Create: `tests/test_gps_sort.py`

- [ ] **Step 1: Create the test file**

```python
"""
Regression tests for GPS point ordering fix.

Verifies:
- merge_gps_points sorts by timestamp, not (lat, lon)
- points_for_db in build_database.py includes 6 elements (lat, lon, spd, alt, hdg, time_offset_s)
- Same for build_database_parallel.py
"""
import pytest
from pathlib import Path

SEQ_FILE = Path(__file__).parent.parent / 'src' / 'extraction' / 'build_database.py'
PAR_FILE = Path(__file__).parent.parent / 'src' / 'extraction' / 'build_database_parallel.py'


@pytest.fixture(scope='module')
def seq_content():
    return SEQ_FILE.read_text()


@pytest.fixture(scope='module')
def par_content():
    return PAR_FILE.read_text()


def test_sort_key_is_timestamp_not_lat_lon(seq_content):
    """merge_gps_points must sort by timestamp, not geographic coordinates."""
    assert "key=lambda p: p['timestamp']" in seq_content, \
        "merge_gps_points must sort by timestamp (not lat/lon)"


def test_sort_key_not_lat_lon(seq_content):
    """Ensure the broken lat/lon sort is gone."""
    assert "key=lambda p: (p['lat'], p['lon'])" not in seq_content, \
        "Found broken lat/lon sort key — must be removed"


def test_points_for_db_has_six_elements(seq_content):
    """points_for_db must include time_offset_s as the 6th element."""
    assert 'time_offset_s' in seq_content or 'time_offset' in seq_content, \
        "points_for_db must include time_offset_s as 6th element"


def test_parallel_points_has_six_elements(par_content):
    """Parallel build points comprehension must also include time_offset_s."""
    assert 'time_offset_s' in par_content or 'time_offset' in par_content, \
        "build_database_parallel.py points must include time_offset_s as 6th element"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_gps_sort.py -v
```

Expected output: all 4 tests FAIL.

```
FAILED tests/test_gps_sort.py::test_sort_key_is_timestamp_not_lat_lon
FAILED tests/test_gps_sort.py::test_sort_key_not_lat_lon
FAILED tests/test_gps_sort.py::test_points_for_db_has_six_elements
FAILED tests/test_gps_sort.py::test_parallel_points_has_six_elements
```

`test_sort_key_not_lat_lon` uses `not in` — it asserts the broken key is **absent**. Since the broken key is currently **present**, the assertion is false → FAIL. All 4 tests must FAIL before any fixes. Confirm this before proceeding.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_gps_sort.py
git commit -m "test: add failing regression tests for GPS sort fix (TDD)"
```

---

## Task 2: Fix Sort Key in `build_database.py`

**Files:**
- Modify: `src/extraction/build_database.py` line 421

- [ ] **Step 1: Apply the one-line fix**

Find line 421:
```python
return sorted(points, key=lambda p: (p['lat'], p['lon']))
```

Replace with:
```python
return sorted(points, key=lambda p: p['timestamp'])
```

- [ ] **Step 2: Run the sort tests**

```bash
python3 -m pytest tests/test_gps_sort.py::test_sort_key_is_timestamp_not_lat_lon tests/test_gps_sort.py::test_sort_key_not_lat_lon -v
```

Expected: both PASS.

- [ ] **Step 3: Run full test suite to check no regressions**

```bash
python3 -m pytest tests/ -v
```

Expected: all 60 pre-existing tests pass + the 2 sort key tests pass (62 total). The 2 points tests (`test_points_for_db_has_six_elements`, `test_parallel_points_has_six_elements`) still FAIL — that is expected, they are fixed in Tasks 3–4.

- [ ] **Step 4: Commit**

```bash
git add src/extraction/build_database.py
git commit -m "fix: sort GPS points by timestamp instead of lat/lon in merge_gps_points"
```

---

## Task 3: Add `time_offset_s` to `points_for_db` in `build_database.py`

**Files:**
- Modify: `src/extraction/build_database.py` lines 1351–1354

- [ ] **Step 1: Replace the points_for_db comprehension**

Find lines 1351–1354:
```python
points_for_db = [
    [p['lat'], p['lon'], p['speed_kmh'], p['altitude'], p['heading']]
    for p in all_points
]
```

Replace with:
```python
trip_start = all_points[0]['timestamp'] if all_points else None
points_for_db = [
    [p['lat'], p['lon'], p['speed_kmh'], p['altitude'], p['heading'],
     round((p['timestamp'] - trip_start).total_seconds(), 2) if trip_start else 0.0]
    for p in all_points
]
```

- [ ] **Step 2: Run the points test**

```bash
python3 -m pytest tests/test_gps_sort.py::test_points_for_db_has_six_elements -v
```

Expected: PASS.

- [ ] **Step 3: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: 63 tests pass; 1 still fails (`test_parallel_points_has_six_elements` — fixed in Task 4).

- [ ] **Step 4: Commit**

```bash
git add src/extraction/build_database.py
git commit -m "feat: add time_offset_s as 6th element to GPS points in build_database"
```

---

## Task 4: Add `time_offset_s` to `build_database_parallel.py`

**Files:**
- Modify: `src/extraction/build_database_parallel.py` line 270

Note: the sort fix is already inherited from `build_database.py` via import. Only the points assembly needs updating here.

- [ ] **Step 1: Replace the inline points comprehension**

Find line 270:
```python
'points': [[p['lat'], p['lon'], p['speed_kmh'], p['altitude'], p['heading']] for p in all_points],
```

Replace with:
```python
'points': (lambda s: [[p['lat'], p['lon'], p['speed_kmh'], p['altitude'], p['heading'],
    round((p['timestamp'] - s).total_seconds(), 2)] for p in all_points])(all_points[0]['timestamp'] if all_points else None) if all_points else [],
```

Wait — that lambda is hard to read. Use a cleaner approach with a local variable. Since this is inside a dict literal, add the variable on the line before the dict:

Find the dict that contains line 270 and add before it:
```python
_trip_start = all_points[0]['timestamp'] if all_points else None
```

Then replace line 270 with:
```python
'points': [[p['lat'], p['lon'], p['speed_kmh'], p['altitude'], p['heading'],
            round((p['timestamp'] - _trip_start).total_seconds(), 2) if _trip_start else 0.0]
           for p in all_points],
```

- [ ] **Step 2: Run the parallel test**

```bash
python3 -m pytest tests/test_gps_sort.py::test_parallel_points_has_six_elements -v
```

Expected: PASS.

- [ ] **Step 3: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: all 64 tests pass (60 pre-existing + 4 GPS sort tests).

- [ ] **Step 4: Commit**

```bash
git add src/extraction/build_database_parallel.py
git commit -m "feat: add time_offset_s as 6th element to GPS points in parallel build"
```

---

## Task 5: Fix GPS Index Lookup in Frontend (onVideoTimeUpdate + onMapClick)

**Files:**
- Modify: `web/index.html` lines 668–670 and line 900

- [ ] **Step 1: Replace index interpolation with binary search in `onVideoTimeUpdate`**

Find lines 668–670:
```javascript
                // Linear interpolation: map video time to GPS index
                const gpsIndex = Math.floor((currentTime / gps_duration_s) * points.length);
                const clampedIndex = Math.max(0, Math.min(gpsIndex, points.length - 1));
```

Replace with:
```javascript
                // Binary search on time_offset_s (points[i][5]); fallback to linear if old trips.json
                let clampedIndex;
                if (points.length && points[0].length >= 6) {
                    let lo = 0, hi = points.length - 1;
                    while (lo < hi) {
                        const mid = (lo + hi + 1) >> 1;
                        if (points[mid][5] <= currentTime) lo = mid;
                        else hi = mid - 1;
                    }
                    clampedIndex = lo;
                } else {
                    const gpsIndex = Math.floor((currentTime / gps_duration_s) * points.length);
                    clampedIndex = Math.max(0, Math.min(gpsIndex, points.length - 1));
                }
```

Note: `gps_duration_s` is still used on the next line for `showVideoTimeIndicator` — keep it. Only the `gpsIndex` / `clampedIndex` calculation changes.

Note on spec deviation: The spec proposes a named `findGpsIndex()` helper function. This plan uses an inline block instead to accommodate the fallback for `trips.json` files built before this fix. Functionally equivalent; no named helper is needed.

- [ ] **Step 2: Fix `onMapClick` seek at line 900**

Find line 900 (inside the map-click handler, after `closestIndex` is determined):
```javascript
                const seekTime = (closestIndex / points.length) * gps_duration_s;
```

Replace with:
```javascript
                // Use time_offset_s directly from closest point; fallback to linear for old trips.json
                const seekTime = (points[closestIndex] && points[closestIndex].length >= 6)
                    ? points[closestIndex][5]
                    : (closestIndex / points.length) * gps_duration_s;
```

- [ ] **Step 3: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: all 64 tests pass (frontend change is JS, static tests still pass).

- [ ] **Step 4: Commit**

```bash
git add web/index.html
git commit -m "feat: replace GPS index interpolation with binary search on time_offset_s"
```

---

## Task 6: Rebuild Database and Manual Verification

- [ ] **Step 1: Rebuild trips.json**

```bash
./build.sh
```

Wait for full rebuild (~15–60 min depending on video encoding). When done:

- [ ] **Step 2: Verify points have 6 elements**

```bash
python3 -c "
import json
data = json.load(open('data/trips.json'))
trip = next(t for t in data['trips'] if '20260314183347' in str(t.get('id','')))
pts = trip['points']
print('Elements per point:', len(pts[0]))
print('First point time_offset_s:', pts[0][5])
print('Point at index 60 time_offset_s:', pts[60][5])
print('Point at index 59 time_offset_s:', pts[59][5])
"
```

Expected:
```
Elements per point: 6
First point time_offset_s: 0.0
Point at index 60 time_offset_s: ~60.0   ← sequential, no jump
Point at index 59 time_offset_s: ~59.0
```

- [ ] **Step 3: Verify no 60-second teleports**

```bash
python3 -c "
import json, math

def haversine(p1, p2):
    R = 6371000
    import math
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    a = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return R * 2 * math.asin(math.sqrt(a))

data = json.load(open('data/trips.json'))
trip = next(t for t in data['trips'] if '20260314183347' in str(t.get('id','')))
pts = trip['points']

print('Distances at former chunk boundaries:')
for boundary in [60, 120, 180, 240, 300]:
    dist = haversine(pts[boundary-1], pts[boundary])
    status = '✅' if dist < 50 else '❌ JUMP'
    print(f'  [{boundary-1}] → [{boundary}]: {dist:.1f} m {status}')
"
```

Expected: all distances < 50 m (normal car motion), no ❌.

- [ ] **Step 4: Manual browser test**

```bash
./run.sh
```

Open `http://localhost:8000/web/`, select trip "Mar 14 18:33 → 19:21", play video. Verify the blue marker moves smoothly along the road with no teleports.

- [ ] **Step 5: Final commit**

```bash
git add tests/test_gps_sort.py src/extraction/build_database.py src/extraction/build_database_parallel.py web/index.html
git commit -m "test: verify GPS sort fix — smooth marker movement confirmed"
```

---

## Testing Checklist

- [ ] `python3 -m pytest tests/test_gps_sort.py -v` — 4 tests pass
- [ ] `python3 -m pytest tests/ -v` — all 64 tests pass
- [ ] `trips.json` points have 6 elements
- [ ] `points[0][5] == 0.0`
- [ ] Distances at chunk boundaries < 50 m
- [ ] Browser: smooth marker during playback of 20260314183347
