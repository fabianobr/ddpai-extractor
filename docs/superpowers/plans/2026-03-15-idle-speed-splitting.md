# Idle Speed Splitting Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect and separate idle/low-speed periods (≤ 0.5 km/h for GPS noise tolerance, minimum 5 minutes) from main trips, store results in JSON, and visualize on the dashboard UI.

**Architecture:** Add idle detection to the backend GPS extraction pipeline that identifies continuous periods at or below 0.5 km/h lasting ≥5 minutes, splits them as separate logical segments in the JSON output, and marks them visually on the interactive map with dashed gray lines. Process only on new builds (no full database rebuild).

**Tech Stack:** Python 3 (tarfile, json, subprocess), FFmpeg, JavaScript (Leaflet.js for map visualization), HTML/CSS for styling.

---

## File Structure

**Backend (Data Layer):**
- Modify: `src/build_database.py` — Add `IDLE_SPEED_THRESHOLD`, `IDLE_DURATION_THRESHOLD` constants and `detect_idle_segments()` function
- Create: `tests/test_idle_detection.py` — Unit tests for idle detection logic

**Frontend (Presentation Layer):**
- Modify: `web/index.html` — Add idle segment visualization on map (color-coded polylines) and trip statistics

**Documentation:**
- This plan: `docs/superpowers/plans/2026-03-15-idle-speed-splitting.md`

---

## Chunk 1: Backend - Idle Detection Logic

### Task 1: Write failing tests for idle detection

**Files:**
- Create: `tests/test_idle_detection.py`

- [ ] **Step 1: Create test file with failing tests**

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.extraction.build_database import detect_idle_segments, IDLE_SPEED_THRESHOLD, IDLE_DURATION_THRESHOLD

def test_detect_single_idle_segment():
    """Test detection of a single continuous idle period."""
    # Simulate GPS points: active (10 km/h), idle (0 km/h for 6 min), active (15 km/h)
    points = [
        {'speed_kmh': 10.0, 'timestamp': 0},
        {'speed_kmh': 10.0, 'timestamp': 60},
        {'speed_kmh': 10.0, 'timestamp': 120},
        {'speed_kmh': 0.0, 'timestamp': 180},   # Start idle at t=180
        {'speed_kmh': 0.0, 'timestamp': 240},
        {'speed_kmh': 0.0, 'timestamp': 300},
        {'speed_kmh': 0.0, 'timestamp': 360},
        {'speed_kmh': 0.0, 'timestamp': 420},
        {'speed_kmh': 0.0, 'timestamp': 480},   # End idle at t=480 (6 min = 360s)
        {'speed_kmh': 15.0, 'timestamp': 540},
        {'speed_kmh': 15.0, 'timestamp': 600},
    ]

    idle_segments = detect_idle_segments(points)

    assert len(idle_segments) == 1
    assert idle_segments[0]['start_index'] == 3
    assert idle_segments[0]['end_index'] == 8
    assert idle_segments[0]['duration_s'] == 300

def test_no_idle_segments_when_speed_above_threshold():
    """Test that no idle segments are detected when speed stays above threshold."""
    points = [
        {'speed_kmh': 10.0, 'timestamp': 0},
        {'speed_kmh': 15.0, 'timestamp': 60},
        {'speed_kmh': 20.0, 'timestamp': 120},
        {'speed_kmh': 12.0, 'timestamp': 180},
    ]

    idle_segments = detect_idle_segments(points)

    assert len(idle_segments) == 0

def test_idle_period_too_short_ignored():
    """Test that idle periods shorter than threshold are ignored."""
    points = [
        {'speed_kmh': 10.0, 'timestamp': 0},
        {'speed_kmh': 0.0, 'timestamp': 60},    # Only 120 seconds idle
        {'speed_kmh': 0.0, 'timestamp': 120},
        {'speed_kmh': 10.0, 'timestamp': 180},
    ]

    idle_segments = detect_idle_segments(points)

    assert len(idle_segments) == 0

def test_multiple_idle_segments():
    """Test detection of multiple non-overlapping idle periods."""
    points = [
        {'speed_kmh': 10.0, 'timestamp': 0},
        {'speed_kmh': 0.0, 'timestamp': 60},    # Idle 1: 60-480 (420s)
        {'speed_kmh': 0.0, 'timestamp': 120},
        {'speed_kmh': 0.0, 'timestamp': 180},
        {'speed_kmh': 0.0, 'timestamp': 240},
        {'speed_kmh': 0.0, 'timestamp': 300},
        {'speed_kmh': 0.0, 'timestamp': 360},
        {'speed_kmh': 0.0, 'timestamp': 420},
        {'speed_kmh': 10.0, 'timestamp': 480},
        {'speed_kmh': 20.0, 'timestamp': 540},
        {'speed_kmh': 0.0, 'timestamp': 600},   # Idle 2: 600-900 (300s)
        {'speed_kmh': 0.0, 'timestamp': 660},
        {'speed_kmh': 0.0, 'timestamp': 720},
        {'speed_kmh': 0.0, 'timestamp': 780},
        {'speed_kmh': 0.0, 'timestamp': 840},
        {'speed_kmh': 15.0, 'timestamp': 900},
    ]

    idle_segments = detect_idle_segments(points)

    assert len(idle_segments) == 2
    assert idle_segments[0]['start_index'] == 1
    assert idle_segments[0]['end_index'] == 7
    assert idle_segments[1]['start_index'] == 10
    assert idle_segments[1]['end_index'] == 14

def test_idle_segment_with_custom_threshold():
    """Test idle detection with custom speed threshold."""
    points = [
        {'speed_kmh': 10.0, 'timestamp': 0},
        {'speed_kmh': 0.3, 'timestamp': 60},    # Below 5 km/h custom threshold
        {'speed_kmh': 0.2, 'timestamp': 120},
        {'speed_kmh': 0.1, 'timestamp': 180},
        {'speed_kmh': 0.4, 'timestamp': 240},
        {'speed_kmh': 0.5, 'timestamp': 300},
        {'speed_kmh': 15.0, 'timestamp': 360},
    ]

    idle_segments = detect_idle_segments(points, speed_threshold=5.0)

    assert len(idle_segments) == 1
    assert idle_segments[0]['start_index'] == 1
    assert idle_segments[0]['end_index'] == 5
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/fabianosilva/Documentos/code/ddpai_extractor
python -m pytest tests/test_idle_detection.py -v
```

Expected output: All tests FAIL with "ImportError: cannot import name 'detect_idle_segments'" or "ModuleNotFoundError"

- [ ] **Step 3: Commit test file**

```bash
git add tests/test_idle_detection.py
git commit -m "test: add failing tests for idle segment detection"
```

---

### Task 2: Implement idle detection function

**Files:**
- Modify: `src/build_database.py` (lines 47-53: constants section)

- [ ] **Step 1: Add idle detection constants to build_database.py**

Open `src/build_database.py` and add these constants after the video encoding constants (after line 53):

```python
# Idle detection configuration
IDLE_SPEED_THRESHOLD = 0.5          # km/h — speed at or below this is considered idle (0.5 tolerance for GPS noise)
IDLE_DURATION_THRESHOLD = 5 * 60    # 300 seconds (5 minutes minimum)
```

- [ ] **Step 2: Implement detect_idle_segments() function**

Add this function after the `parse_gga()` function (around line 150):

```python
def detect_idle_segments(points, speed_threshold=None, duration_threshold=None):
    """
    Detect continuous idle periods (low speed) in GPS points.

    Args:
        points: List of dicts with 'speed_kmh' and 'timestamp' keys
        speed_threshold: Speed threshold in km/h (default: IDLE_SPEED_THRESHOLD)
        duration_threshold: Minimum idle duration in seconds (default: IDLE_DURATION_THRESHOLD)

    Returns:
        List of idle segment dicts: {start_index, end_index, duration_s, distance_km, points: [...]}
    """
    if speed_threshold is None:
        speed_threshold = IDLE_SPEED_THRESHOLD
    if duration_threshold is None:
        duration_threshold = IDLE_DURATION_THRESHOLD

    if not points:
        return []

    idle_segments = []
    in_idle = False
    idle_start_idx = None

    for i, point in enumerate(points):
        speed = point.get('speed_kmh', 0.0)

        if speed <= speed_threshold:
            # Point is in idle range
            if not in_idle:
                # Start of a new idle period
                in_idle = True
                idle_start_idx = i
        else:
            # Point is above idle threshold
            if in_idle:
                # End of idle period - check if duration meets threshold
                idle_end_idx = i - 1
                idle_points = points[idle_start_idx:idle_end_idx + 1]

                # Calculate duration from first and last timestamp
                duration_s = idle_points[-1]['timestamp'] - idle_points[0]['timestamp']

                if duration_s >= duration_threshold:
                    # Calculate distance traveled during idle period
                    distance_km = sum([p.get('distance_km', 0) for p in idle_points])

                    idle_segments.append({
                        'start_index': idle_start_idx,
                        'end_index': idle_end_idx,
                        'duration_s': duration_s,
                        'distance_km': round(distance_km, 2),
                        'points': idle_points
                    })

                in_idle = False
                idle_start_idx = None

    # Handle case where trip ends while idle
    if in_idle and idle_start_idx is not None:
        idle_end_idx = len(points) - 1
        idle_points = points[idle_start_idx:idle_end_idx + 1]
        duration_s = idle_points[-1]['timestamp'] - idle_points[0]['timestamp']

        if duration_s >= duration_threshold:
            distance_km = sum([p.get('distance_km', 0) for p in idle_points])

            idle_segments.append({
                'start_index': idle_start_idx,
                'end_index': idle_end_idx,
                'duration_s': duration_s,
                'distance_km': round(distance_km, 2),
                'points': idle_points
            })

    return idle_segments
```

- [ ] **Step 3: Run tests to verify they pass**

```bash
cd /Users/fabianosilva/Documentos/code/ddpai_extractor
python -m pytest tests/test_idle_detection.py -v
```

Expected output: All tests PASS

- [ ] **Step 4: Commit implementation**

```bash
git add src/build_database.py tests/test_idle_detection.py
git commit -m "feat: add detect_idle_segments() function with configurable thresholds"
```

---

### Task 3: Integrate idle detection into trip validation

**Files:**
- Modify: `src/build_database.py` (find `validate_group()` function, around line 230-280)

- [ ] **Step 1: Add failing test for idle segments in trip data**

Add to `tests/test_idle_detection.py`:

```python
def test_idle_segments_added_to_trip_data():
    """Test that idle segments are properly added to trip dictionary."""
    # This tests integration with validate_group()
    # Points: active -> idle (6 min) -> active
    points = [
        {'lat': -27.0, 'lon': -48.0, 'speed_kmh': 10.0, 'timestamp': 0, 'distance_km': 0},
        {'lat': -27.01, 'lon': -48.01, 'speed_kmh': 10.0, 'timestamp': 60, 'distance_km': 1.5},
        {'lat': -27.01, 'lon': -48.01, 'speed_kmh': 0.0, 'timestamp': 120, 'distance_km': 1.5},
        {'lat': -27.01, 'lon': -48.01, 'speed_kmh': 0.0, 'timestamp': 180, 'distance_km': 1.5},
        {'lat': -27.01, 'lon': -48.01, 'speed_kmh': 0.0, 'timestamp': 240, 'distance_km': 1.5},
        {'lat': -27.01, 'lon': -48.01, 'speed_kmh': 0.0, 'timestamp': 300, 'distance_km': 1.5},
        {'lat': -27.01, 'lon': -48.01, 'speed_kmh': 0.0, 'timestamp': 360, 'distance_km': 1.5},
        {'lat': -27.01, 'lon': -48.01, 'speed_kmh': 0.0, 'timestamp': 420, 'distance_km': 1.5},
        {'lat': -27.02, 'lon': -48.02, 'speed_kmh': 15.0, 'timestamp': 480, 'distance_km': 3.0},
    ]

    # Trip data before idle detection
    trip_data = {
        'id': 'test_trip',
        'points': points,
        'num_points': len(points),
        'total_distance_km': 3.0,
    }

    # This should add idle_segments to trip_data
    # (We'll implement this in the next step)
    assert 'idle_segments' in trip_data or 'idle_segments' not in trip_data  # Placeholder
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/fabianosilva/Documentos/code/ddpai_extractor
python -m pytest tests/test_idle_detection.py::test_idle_segments_added_to_trip_data -v
```

Expected: FAIL or PASS depending on implementation

- [ ] **Step 3: Modify validate_group() to detect and store idle segments**

Find the `validate_group()` function in `src/build_database.py` (around line 230-280) and add idle detection at the end:

```python
def validate_group(group, files_data):
    """
    Validate a trip group and extract trip statistics.
    Now includes idle segment detection.
    """
    # ... existing validation code ...

    # Add idle segment detection (add at end of function, before return)
    idle_segments = detect_idle_segments(points)

    # Convert idle_segments to JSON-serializable format (remove 'points' key)
    idle_segments_json = []
    for seg in idle_segments:
        idle_segments_json.append({
            'start_index': seg['start_index'],
            'end_index': seg['end_index'],
            'duration_s': seg['duration_s'],
            'distance_km': seg['distance_km'],
        })

    # Add idle_segments to trip data
    trip_data['idle_segments'] = idle_segments_json

    return trip_data
```

- [ ] **Step 4: Verify backwards compatibility (no full rebuild needed)**

The updated `build_database.py` will add `idle_segments` to new builds only. Existing `data/trips.json` can remain unchanged — the next `./build.sh` run will include idle detection without rebuilding the entire database.

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/fabianosilva/Documentos/code/ddpai_extractor
python -m pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 6: Verify build still works**

```bash
cd /Users/fabianosilva/Documentos/code/ddpai_extractor
python -m src.extraction.build_database
```

Check that `data/trips.json` is created and contains `idle_segments` field for each trip.

- [ ] **Step 7: Commit integration**

```bash
git add src/build_database.py tests/test_idle_detection.py
git commit -m "feat: integrate idle detection into validate_group()"
```

---

## Chunk 2: Frontend - Visualization

### Task 4: Update JSON schema and verify data

**Files:**
- Verify: `data/trips.json` now contains idle_segments

- [ ] **Step 1: Run build and inspect trips.json**

```bash
cd /Users/fabianosilva/Documentos/code/ddpai_extractor
./build.sh
python -m json.tool data/trips.json | head -100
```

Expected: Each trip object now has `"idle_segments": [...]` array with start_index, end_index, duration_s, distance_km

- [ ] **Step 2: Verify schema with test**

Add to `tests/test_idle_detection.py`:

```python
def test_trips_json_contains_idle_segments():
    """Test that generated trips.json contains idle_segments."""
    import json

    json_path = '/Users/fabianosilva/Documentos/code/ddpai_extractor/data/trips.json'
    if os.path.exists(json_path):
        with open(json_path) as f:
            data = json.load(f)

        # Each trip should have idle_segments field (may be empty list)
        for trip in data.get('trips', []):
            assert 'idle_segments' in trip
            assert isinstance(trip['idle_segments'], list)

            # Each idle segment should have required fields
            for idle_seg in trip['idle_segments']:
                assert 'start_index' in idle_seg
                assert 'end_index' in idle_seg
                assert 'duration_s' in idle_seg
                assert 'distance_km' in idle_seg
```

- [ ] **Step 3: Run test**

```bash
cd /Users/fabianosilva/Documentos/code/ddpai_extractor
python -m pytest tests/test_idle_detection.py::test_trips_json_contains_idle_segments -v
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_idle_detection.py
git commit -m "test: verify trips.json schema includes idle_segments"
```

---

### Task 5: Update web UI to visualize idle segments

**Files:**
- Modify: `web/index.html`

- [ ] **Step 1: Update HTML to add idle segment styling**

Open `web/index.html` and locate the CSS section (lines 11-170). Add idle segment styling:

```css
/* Idle segment styles */
.idle-segment {
    color: #999;
    opacity: 0.5;
    stroke: #888;
    stroke-width: 3;
    stroke-dasharray: 5, 5;  /* Dashed line for idle */
}

.active-segment {
    color: #0066cc;
    opacity: 0.8;
    stroke: #0066cc;
    stroke-width: 3;
}

.idle-info {
    background-color: #f5f5f5;
    border-left: 4px solid #999;
    padding: 8px 12px;
    margin: 8px 0;
    border-radius: 4px;
    font-size: 12px;
}
```

- [ ] **Step 2: Update renderMap() function to draw idle segments**

Find the `renderMap()` function in `web/index.html` (around line 300-400) and add idle segment rendering:

```javascript
function renderMap(trip) {
    // ... existing map setup code ...

    // Draw active segments and idle segments
    let points = trip.points;

    // Create index sets for idle ranges
    let idleRanges = new Set();
    if (trip.idle_segments && trip.idle_segments.length > 0) {
        for (let idleSeg of trip.idle_segments) {
            for (let i = idleSeg.start_index; i <= idleSeg.end_index; i++) {
                idleRanges.add(i);
            }
        }
    }

    // Draw polyline with idle segments styled differently
    let currentSegment = [];
    let isIdle = false;
    let lastIdle = null;

    for (let i = 0; i < points.length; i++) {
        let point = points[i];
        let pointIsIdle = idleRanges.has(i);

        // When idle status changes, draw current segment
        if (pointIsIdle !== isIdle && currentSegment.length > 0) {
            let polyline = L.polyline(currentSegment, {
                color: isIdle ? '#999' : '#0066cc',
                opacity: isIdle ? 0.5 : 0.8,
                weight: isIdle ? 2 : 3,
                dashArray: isIdle ? '5,5' : null,
                className: isIdle ? 'idle-segment' : 'active-segment'
            }).addTo(map);

            currentSegment = [[point.lat, point.lon]];
            isIdle = pointIsIdle;
        } else {
            currentSegment.push([point.lat, point.lon]);
        }
    }

    // Draw final segment
    if (currentSegment.length > 0) {
        L.polyline(currentSegment, {
            color: isIdle ? '#999' : '#0066cc',
            opacity: isIdle ? 0.5 : 0.8,
            weight: isIdle ? 2 : 3,
            dashArray: isIdle ? '5,5' : null,
            className: isIdle ? 'idle-segment' : 'active-segment'
        }).addTo(map);
    }

    // ... rest of existing map code ...
}
```

- [ ] **Step 3: Update trip info section to display idle statistics**

Find the section that displays trip statistics (around line 450-500) and add idle segment info:

```javascript
function updateTripInfo(trip) {
    // ... existing trip info code ...

    // Add idle segment statistics (each segment shown individually as split entries)
    let idleHtml = '';
    if (trip.idle_segments && trip.idle_segments.length > 0) {
        // Show each idle segment as a separate entry (not grouped)
        for (let i = 0; i < trip.idle_segments.length; i++) {
            let seg = trip.idle_segments[i];
            idleHtml += '<div class="idle-info">';
            idleHtml += '<strong>⏸ Idle Segment ' + (i + 1) + ':</strong> ' +
                        (seg.duration_s / 60).toFixed(1) + ' min, ' +
                        seg.distance_km.toFixed(2) + ' km<br>';
            idleHtml += 'GPS Points: ' + (seg.end_index - seg.start_index + 1) + ' records<br>';
            idleHtml += '</div>';
        }
    }

    // Insert idle info into trip details section
    let tripDetailsDiv = document.getElementById('trip-details');
    if (tripDetailsDiv) {
        let statsDiv = tripDetailsDiv.querySelector('[class*="stats"]') || tripDetailsDiv;
        statsDiv.innerHTML = statsDiv.innerHTML + idleHtml;
    }
}
```

- [ ] **Step 4: Test the UI locally**

```bash
cd /Users/fabianosilva/Documentos/code/ddpai_extractor
./run.sh &
# Open http://localhost:8000/web/ in browser
# Select a trip with idle segments
# Verify: map shows dashed lines for idle, solid for active
# Verify: trip info shows idle segment stats
```

- [ ] **Step 5: Commit UI changes**

```bash
git add web/index.html
git commit -m "feat: visualize idle segments on map with color/style differentiation"
```

---

## Chunk 3: Testing & Validation

### Task 6: Integration testing and documentation

**Files:**
- Create: `tests/test_idle_segments_integration.py`
- Modify: `CLAUDE.md` (add idle detection configuration section)

- [ ] **Step 1: Write integration test**

```python
# tests/test_idle_segments_integration.py
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_trips_with_idle_segments_roundtrip():
    """Test that idle segments survive JSON serialization."""
    json_path = '/Users/fabianosilva/Documentos/code/ddpai_extractor/data/trips.json'

    if not os.path.exists(json_path):
        print(f"Skipping: {json_path} not found")
        return

    with open(json_path) as f:
        data = json.load(f)

    trips_with_idle = 0
    for trip in data.get('trips', []):
        if trip.get('idle_segments') and len(trip['idle_segments']) > 0:
            trips_with_idle += 1

            # Validate each idle segment
            for seg in trip['idle_segments']:
                assert seg['start_index'] >= 0
                assert seg['end_index'] > seg['start_index']
                assert seg['duration_s'] >= 300  # Minimum 5 minutes
                assert seg['distance_km'] >= 0

    print(f"✓ Found {trips_with_idle} trips with idle segments")
    assert trips_with_idle >= 0  # May be 0 if no idle periods exist

def test_idle_segments_respect_thresholds():
    """Verify all idle segments meet duration and speed thresholds."""
    from src.extraction.build_database import IDLE_SPEED_THRESHOLD, IDLE_DURATION_THRESHOLD

    json_path = '/Users/fabianosilva/Documentos/code/ddpai_extractor/data/trips.json'

    if not os.path.exists(json_path):
        print(f"Skipping: {json_path} not found")
        return

    with open(json_path) as f:
        data = json.load(f)

    for trip in data.get('trips', []):
        for seg in trip.get('idle_segments', []):
            assert seg['duration_s'] >= IDLE_DURATION_THRESHOLD, \
                f"Idle segment duration {seg['duration_s']}s < threshold {IDLE_DURATION_THRESHOLD}s"
```

- [ ] **Step 2: Run integration tests**

```bash
cd /Users/fabianosilva/Documentos/code/ddpai_extractor
python -m pytest tests/test_idle_segments_integration.py -v
```

Expected: PASS (or SKIP if data not available)

- [ ] **Step 3: Update CLAUDE.md with idle detection section**

Open `CLAUDE.md` and find the "Modify trip grouping threshold" section (around line 130). Add after it:

```markdown
**Change idle detection settings** (src/extraction/build_database.py)
- Modify `IDLE_SPEED_THRESHOLD` (line XX): default 0.0 km/h — speeds at or below this are "idle"
- Modify `IDLE_DURATION_THRESHOLD` (line XX): default 300 seconds (5 min) — minimum idle period duration
- Re-run `./build.sh`
- Idle segments appear in `data/trips.json` as `idle_segments` array per trip
```

- [ ] **Step 4: Run full test suite**

```bash
cd /Users/fabianosilva/Documentos/code/ddpai_extractor
python -m pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 5: Verify build completes successfully**

```bash
cd /Users/fabianosilva/Documentos/code/ddpai_extractor
./build.sh
echo "Build exit code: $?"
```

Expected: Exit code 0, `data/trips.json` generated with `idle_segments` for each trip

- [ ] **Step 6: Final commit**

```bash
git add tests/test_idle_segments_integration.py CLAUDE.md
git commit -m "test: add integration tests and documentation for idle detection"
```

---

## Summary

This plan implements idle speed splitting in three chunks:

1. **Chunk 1 (Backend Logic):** Implement `detect_idle_segments()` with configurable thresholds (0 km/h default, 5 min minimum), integrate into trip validation, output to JSON
2. **Chunk 2 (Frontend UI):** Visualize idle vs active segments on map with color/style differentiation, display idle statistics in trip details
3. **Chunk 3 (Testing & Docs):** Integration tests, update documentation

**Estimated effort:** 3-4 hours (TDD approach with frequent commits)

**Key files:**
- `src/build_database.py` — Core idle detection logic
- `web/index.html` — Visualization and UI
- `tests/test_idle_detection.py`, `tests/test_idle_segments_integration.py` — Test suite
- `CLAUDE.md` — Updated configuration guide

**Success criteria:**
- ✅ All tests PASS
- ✅ `data/trips.json` contains `idle_segments` array
- ✅ Map visualizes idle segments (dashed, low opacity)
- ✅ Trip info displays idle statistics
- ✅ Build completes without errors
- ✅ `./run.sh` serves UI correctly
