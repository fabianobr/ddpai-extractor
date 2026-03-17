# Idle Detection Feature — Design Specification

**Date:** 2026-03-15
**Status:** Design Approved
**Approach:** Approach B — Detect Idle Segments Within Trips (Not Split)

---

## Executive Summary

Add idle period detection to trip data so the web dashboard can visualize when the dashcam was recording but the car wasn't moving (parking, traffic, stops). This is a **marking feature**, not a splitting feature — idle periods stay within their trip.

**Goal:** Fix broken idle detection code and complete the feature so each trip includes rich idle segment data in JSON output + console logs during build.

---

## Problem Statement

### Current State
- Idle detection code exists but is broken: `TypeError` when comparing `timedelta` with `int`
- Code attempts to *split* trips by idle (wrong goal)
- GPS timestamps use placeholder date `2000-01-01` instead of actual date
- No output to JSON, no visualization support

### Desired State
- Idle detection runs without errors
- Identifies periods where speed ≤ 0.5 km/h for ≥5 minutes
- Marks idle segments **within** each trip (no splitting)
- Outputs rich idle segment data to JSON
- Logs idle periods to console during build

---

## Architecture

### High-Level Flow

```
Trip Group
  ↓ [Extract all GPS points from TAR files in group]
  ↓ [Fix timestamps with actual date from TAR filename]
  ↓ [Call detect_idle_segments() on points]
  ↓ [Build rich idle segment data]
  ↓ [Store in trip['idle_segments']]
  ↓ [Log to console + JSON output]
```

### Key Design Decisions

**1. Idle Detection = Marking, Not Splitting**
- Idle detection identifies low-speed periods for visualization
- Does NOT create separate trips or split group boundaries
- Current `split_group_by_idle()` function will be **removed** — it was solving the wrong problem

**2. Detect Per Trip (Not Per Group)**
- Each validated trip gets idle analysis
- Simpler than trying to split during grouping
- Clear responsibility: groups are for time-based batching, idle is for visualization

**3. Rich Data for Dashboard Context**
- Include GPS coordinates, speed ranges, timestamps
- Enables map highlighting, info popups, timeline visualization
- Not just duration/indices

---

## Data Structures

### Idle Segment (Output to JSON)

```python
{
    # Position in trip data
    'start_index': 150,
    'end_index': 280,

    # Duration & distance
    'duration_seconds': 520,
    'distance_km': 0.012,

    # Timing
    'start_time': '06:15:30',
    'end_time': '06:24:10',

    # Locations (for map visualization)
    'start_location': {
        'lat': 40.7128,
        'lon': -74.0060
    },
    'end_location': {
        'lat': 40.7130,
        'lon': -74.0058
    },

    # Speed profile
    'avg_speed_kmh': 0.15,
    'min_speed_kmh': 0.0,
    'max_speed_kmh': 0.45
}
```

### GPS Point (Internal)

Must include timestamp with actual date (not placeholder):

```python
{
    'lat': 40.7128,
    'lon': -74.0060,
    'speed_kmh': 0.2,
    'altitude': 10.5,
    'heading': 90.0,
    'timestamp': datetime(2026, 3, 14, 6, 15, 30)  # ← Actual date!
}
```

### Trip JSON Output

```json
{
  "id": "20260314060147",
  "date": "2026-03-14",
  "start_time": "06:01:47",
  "end_time": "19:21:47",
  "distance_km": 195.64,
  "duration_minutes": 750.1,
  "points": [...],
  "idle_segments": [
    {
      "start_index": 150,
      "end_index": 280,
      "duration_seconds": 520,
      ...
    }
  ]
}
```

---

## Implementation Details

### Bug Fixes Required

**Bug #1: Timedelta vs Int Comparison**
- **Location:** `detect_idle_segments()` line ~218
- **Problem:** `duration_s = idle_points[-1]['timestamp'] - idle_points[0]['timestamp']` returns `timedelta` object, then compared with int threshold
- **Fix:** `duration_s = (end_time - start_time).total_seconds()` converts to float

**Bug #2: GPS Timestamps Use Placeholder Date**
- **Location:** `merge_gps_points()` line ~297-303
- **Problem:** Timestamps hardcoded to `datetime(2000, 1, 1, HH, MM, SS)`
- **Fix:**
  - Extract date from TAR filename: `20260314060147` → `2026-03-14`
  - Pass `tar_date` to `merge_gps_points()`
  - Build timestamp: `datetime.combine(tar_date, time(HH, MM, SS))`

### Code Changes Summary

| File | Change | Reason |
|------|--------|--------|
| `src/extraction/build_database.py` | Fix `detect_idle_segments()` timedelta bug | TypeError fix |
| `src/extraction/build_database.py` | Add `tar_date` param to `merge_gps_points()` | Proper timestamps |
| `src/extraction/build_database.py` | Add idle detection to trip validation loop | Detect & store idle segments |
| `src/extraction/build_database.py` | **Remove** `split_group_by_idle()` | Not needed; wrong approach |
| `src/extraction/build_database.py` | Update JSON output to include `idle_segments` | Dashboard support |
| `src/extraction/build_database.py` | Add console logging for idle periods | Build-time visibility |
| `tests/test_idle_detection.py` | **NEW** unit tests | TDD coverage |

---

## Configuration

**Idle Detection Thresholds (Already Defined):**
- `IDLE_SPEED_THRESHOLD = 0.5 km/h` — speed at or below considered idle
- `IDLE_DURATION_THRESHOLD = 300 seconds` (5 min) — minimum idle period duration

**These can be adjusted in `src/extraction/build_database.py` if needed.**

---

## Testing Strategy

### Unit Tests
- `test_idle_detection.py` — Idle detection with mock GPS data
  - All moving (no idle)
  - Short idle (below threshold)
  - Long idle (detected)
  - Multiple idle periods
  - Duration calculation correctness

### Integration Tests
- Build with actual dashcam data
- Verify Step 2 output shows idle detection
- Check JSON has `idle_segments` array
- Verify timestamps are correct (not 2000-01-01)

### Manual Verification
- Run `./watch.sh` or `./build.sh`
- Confirm no TypeError
- Check console shows idle periods
- Inspect generated JSON in `data/trips.json`

---

## Success Criteria

✅ **Code Quality**
- All unit tests passing
- No TypeError on timedelta
- GPS timestamps have correct dates

✅ **Functionality**
- Idle segments detected and stored in JSON
- Console logs show idle periods during build
- Rich data (locations, speed ranges) available

✅ **Integration**
- Build completes without errors
- Web dashboard can access idle_segments
- No regression in other features

---

## Dependencies & Constraints

**No New Dependencies:** Uses only Python stdlib (`datetime`, `collections`)

**Backward Compatibility:** Adding `idle_segments` to JSON is additive; won't break existing code that doesn't use it

**Performance:** Idle detection runs once per trip during build (not real-time), negligible overhead

---

## Future Enhancements (Out of Scope)

- Cluster idle periods (merge very short breaks)
- Estimate activity type (parking, traffic, stops)
- Alert on unusually long idles
- Filter out GPS noise near traffic lights

---

## Approval Sign-Off

- **Design:** ✅ Approved by Fabian
- **Approach:** ✅ Approach B (Detect Within Trips, Don't Split)
- **Ready for:** Implementation Plan (writing-plans skill)
