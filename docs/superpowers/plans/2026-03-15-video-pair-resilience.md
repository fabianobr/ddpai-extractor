# Video Pair Resilience - Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the build script smart about video merging—**always attempt to merge using the minimum of both camera counts**, gracefully ignoring unpaired extras. Include complete trips with GPS + videos whenever possible.

**Architecture:**
- Decouple video merging from trip validation
- GPS data is mandatory; video merge always attempted
- Video merge strategy: `merge_count = min(rear_count, front_count)` (never skip, always smart-pair)
- Extra/unpaired videos are gracefully ignored (not an error)
- **Explicit messaging:** Console reports exactly what was merged and what was ignored
- Include detailed debug logs in merge report for each trip's video processing

**Tech Stack:** Python 3, tarfile, FFmpeg, JSON

**GitHub Issue:** #7 (missing video pair bug)

---

## File Structure

### Modified Files
- `src/extraction/build_database.py` — Core changes (SEQUENTIAL):
  - Refactor `validate_group()` → split into `validate_gps()` (fatal) + `validate_videos()` (non-fatal)
  - Create new `validate_videos()` for optional video validation with **explicit warnings**
  - Add `safe_merge_videos()` wrapper that handles missing videos with clear logging
  - Update main loop to process GPS even if videos fail
  - Enhance debug reporting with explicit per-trip video status & notes

- `src/extraction/build_database_parallel.py` — IDENTICAL changes (PARALLEL):
  - **MUST keep in sync** with sequential version
  - Apply identical validation & video handling logic
  - Parallel worker functions should have same error handling

- `tools/build_parallel.sh` — Shell script:
  - No changes needed (calls build_database_parallel.py which will be updated)

### Output Changes
- `data/trips.json` — New schema:
  - `video_rear` and `video_front` are present when merge succeeds (even if counts differed)
  - Only `null` if an entire camera is missing (0 files)
  - Add `video_status` field per trip: "ok" (perfect match), "ok_with_extras" (extra files ignored), "no_rear", "no_front", "no_videos"
  - Add `video_notes` field explaining what was merged/ignored (e.g., "Merged 800 pairs (1 extra front ignored)")

### No New Files Created
- Tests would be added to `tests/` if a test suite exists (currently none)

---

## Real Example: Before → After

### BEFORE (Current Behavior - BUG)
```
Group 1/1: 100 archives
  Group ID: 20260314060147
  📍 Extracting GPS data...
    → 45009 points extracted
  🎥 Discovering videos...
    → 800 rear, 801 front
  ⚠️  Skipping group 20260314060147:
    • Video count mismatch: 800 rear vs 801 front

Step 3: Writing database...
  ❌ No valid groups!
  Result: 45,009 GPS POINTS LOST ❌
```

### AFTER (New Behavior - SMART FIX: Always Merge)
```
Group 1/1: 100 archives
  Group ID: 20260314060147
  📍 Extracting GPS data...
    → 45009 points extracted ✅
  🎥 Discovering videos...
    → 800 rear, 801 front
  ⚠️  VIDEO COUNT NOTICE:
    • Rear: 800 videos
    • Front: 801 videos
    • Difference: +1 front (will be ignored)
    • Strategy: Merge min(800, 801) = 800 pairs

  ✅ Validation passed (GPS + video merge ready)

  💾 Computing trip stats...
    • Distance: 127.45 km
    • Duration: 95.3 min
    • Max speed: 98.2 km/h
    • Avg speed: 80.1 km/h

  🎬 Merging videos...
    • Using 800 rear + 800 front (ignoring 1 extra front)
    • Merging rear videos... ✅ 409 MB
    • Merging front videos... ✅ 2.1 GB

  💾 Adding to database with video_status: "ok_with_extras"
    • video_rear: merged_videos/20260314060147_rear.mp4 ✅
    • video_front: merged_videos/20260314060147_front.mp4 ✅
    • video_notes: "Merged 800 rear + 800 front videos (1 extra front video ignored)"

Step 3: Writing database...
  ✅ Database created: data/trips.json (1.8 MB)

Final Summary:
  ✅ SUCCESS: 1/1 groups included
  📊 Video status: 1 merged with extras ignored
  📋 Merge report: data/merge_report.txt
  Result: 45,009 GPS POINTS + BOTH VIDEOS SAVED ✅
```

### JSON Output Sample (AFTER - Smart Merge)
```json
{
  "generated_at": "2026-03-15T12:30:45.123456+00:00",
  "trips": [
    {
      "id": "20260314060147",
      "label": "Mar 14 06:01 → 07:36",
      "date": "2026-03-14",
      "duration_min": 95.3,
      "distance_km": 127.45,
      "max_speed": 98.2,
      "avg_speed": 80.1,
      "points": [
        [27.5921, -48.5480, 45.3, 12.5, 95.2],
        [27.5925, -48.5485, 52.1, 13.2, 94.8],
        ...45,009 points total...
      ],
      "video_rear": "merged_videos/20260314060147_rear.mp4",
      "video_front": "merged_videos/20260314060147_front.mp4",
      "video_status": "ok_with_extras",
      "video_notes": "Merged 800 rear + 800 front videos (1 extra front video ignored)"
    }
  ]
}
```

### Debug Report Sample (AFTER - Smart Merge)
File: `data/merge_report.txt`
```
VIDEO MERGE DEBUG REPORT
================================================================================
Generated: 2026-03-15T12:30:44.987654+00:00
TAR Directory: /Volumes/ddpai/DCIM/203gps/tar
Rear Videos: /Volumes/ddpai/DCIM/200video/rear
Front Videos: /Volumes/ddpai/DCIM/200video/front
Output Directory: .
================================================================================

GROUP: 20260314060147
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GPS Data:
  ✅ Extracted: 45,009 points
  ✅ Speed data: valid (0-98.2 km/h)
  ✅ Altitude data: valid (0-157.3 m)

Video Discovery:
  📁 Rear videos: 800 files found
     First: 20260314060147_0000_rear.mp4
     Last:  20260314062827_0000_rear.mp4
  📁 Front videos: 801 files found
     First: 20260314060147_0000_front.mp4
     Last:  20260314062828_0000_front.mp4

Video Count Analysis:
  Rear count: 800
  Front count: 801
  Merge strategy: Use min(800, 801) = 800 pairs
  Extra files: 1 front video will be ignored

REAR VIDEO MERGE:
  ✅ Merging 800 rear videos (20260314060147_0000 → 20260314062827_0000)
  ✅ Output: merged_videos/20260314060147_rear.mp4
     Size: 409 MB | Duration: 95.3 min | Status: SUCCESS

FRONT VIDEO MERGE:
  ✅ Merging 800 front videos (20260314060147_0000 → 20260314062827_0000)
  ⏭️  Ignoring: 20260314062828_0000_front.mp4 (extra file, no matching rear)
  ✅ Output: merged_videos/20260314060147_front.mp4
     Size: 2.1 GB | Duration: 95.3 min | Status: SUCCESS

Trip Inclusion Decision:
  ✅ GPS data: INCLUDED (45,009 points)
  ✅ Rear video: INCLUDED (merged_videos/20260314060147_rear.mp4)
  ✅ Front video: INCLUDED (merged_videos/20260314060147_front.mp4)
  ✅ Video status: "ok_with_extras"
  ✅ Video notes: "Merged 800 rear + 800 front videos (1 extra front video ignored)"

Notes:
  - Extra front video (20260314062828_0000_front.mp4) was NOT merged
  - Both cameras still synchronized for the 95.3-minute trip
  - No data loss - just ignored the unpaired extra file
```

---

## ⚠️ IMPORTANT: Keep Scripts in Sync

Both `build_database.py` and `build_database_parallel.py` must use identical validation logic.
- Make changes to `build_database.py` first
- Copy same functions to `build_database_parallel.py`
- Test both scripts to verify they produce the same output

---

## Chunk 1: Refactor Validation Logic

### Task 1: Separate GPS Validation from Video Validation

**Files:**
- Modify: `src/extraction/build_database.py:553-575`
- Modify: `src/extraction/build_database_parallel.py:553-575` (same lines, identical code)

**Approach:**
Split `validate_group()` into two functions:
1. `validate_gps()` — checks: speed > 0, altitude data present (FATAL if fails)
2. `validate_videos()` — checks: rear/front exist and counts match (non-fatal, returns warnings)

- [ ] **Step 1: Read current `validate_group()` function**

Already read (lines 553-575). Current function returns a list of errors.

- [ ] **Step 2: Write new `validate_gps()` function**

```python
def validate_gps(points):
    """
    Validate GPS data. Returns list of fatal errors.
    If any error, trip should be skipped entirely.
    """
    errors = []

    if not points:
        errors.append("No GPS data extracted")
        return errors

    # Check speed data
    if not any(p['speed_kmh'] > 0 for p in points):
        errors.append("No speed data (all speeds are 0)")

    # Check altitude data
    if not any(p['altitude'] != 0 for p in points):
        errors.append("No altitude data (all altitudes are 0)")

    return errors
```

- [ ] **Step 3: Write new `validate_videos()` function**

```python
def validate_videos(rear_videos, front_videos):
    """
    Validate video pairs. Returns (has_errors, detailed_warnings_list).
    has_errors = False means at least one pair is OK to merge.
    Trip can still be included even if has_errors=True (GPS is included).
    """
    warnings = []
    rear_count = len(rear_videos)
    front_count = len(front_videos)

    if not rear_videos and not front_videos:
        warnings.append("❌ NO VIDEOS FOUND")
        warnings.append("   • Rear: 0 videos")
        warnings.append("   • Front: 0 videos")
        warnings.append("   • Status: No video files in either directory")
        return True, warnings

    if not rear_videos:
        warnings.append("❌ REAR VIDEOS MISSING")
        warnings.append(f"   • Rear: 0 videos")
        warnings.append(f"   • Front: {front_count} videos")
        warnings.append("   • Status: Cannot merge (no rear camera data)")
        return True, warnings

    if not front_videos:
        warnings.append("❌ FRONT VIDEOS MISSING")
        warnings.append(f"   • Rear: {rear_count} videos")
        warnings.append(f"   • Front: 0 videos")
        warnings.append("   • Status: Cannot merge (no front camera data)")
        return True, warnings

    if rear_count != front_count:
        diff = front_count - rear_count
        sign = "+" if diff > 0 else ""
        warnings.append("⚠️  VIDEO COUNT MISMATCH")
        warnings.append(f"   • Rear: {rear_count} videos")
        warnings.append(f"   • Front: {front_count} videos")
        warnings.append(f"   • Difference: {sign}{diff} video(s)")
        warnings.append("   • Status: Cannot merge (different durations)")
        return True, warnings

    # All checks passed
    warnings.append(f"✅ VIDEOS OK TO MERGE")
    warnings.append(f"   • Rear: {rear_count} videos")
    warnings.append(f"   • Front: {front_count} videos")
    warnings.append("   • Status: Ready for merge")
    return False, warnings
```

- [ ] **Step 4: Replace `validate_group()` call in main()**

In `main()` function around line 656, change:
```python
# OLD:
errors = validate_group(all_points, rear_videos, front_videos)
if errors:
    print(f"  ⚠️  Skipping group {group_id}:")
    for err in errors:
        print(f"    • {err}")
    print()
    continue
```

To:
```python
# NEW:
gps_errors = validate_gps(all_points)
if gps_errors:
    print(f"  ⚠️  Skipping group {group_id} (GPS validation failed):")
    for err in gps_errors:
        print(f"    • {err}")
    print()
    continue

video_has_errors, video_warnings = validate_videos(rear_videos, front_videos)
for line in video_warnings:
    print(f"     {line}")

if video_has_errors:
    print(f"  ⚠️  Cannot merge videos - but GPS data WILL BE INCLUDED")
    video_status = "no_videos"  # Will be refined after attempting merges
else:
    print(f"  ✅ GPS & Video validation passed")
```

- [ ] **Step 5: Copy changes to parallel variant**

Copy the two new functions to `src/extraction/build_database_parallel.py` at same line numbers:
- `validate_gps()`
- `validate_videos()`

Update the main processing loop in parallel version to use both functions (same logic).

- [ ] **Step 6: Commit**

```bash
git add src/extraction/build_database.py src/extraction/build_database_parallel.py
git commit -m "refactor: decouple GPS validation from video validation (sequential + parallel)"
```

---

## Chunk 2: Handle Missing Videos in Merge

### Task 2: Create Smart Video Merge Wrapper

**Files:**
- Modify: `src/extraction/build_database.py:349-548` (discover_videos + merge_videos)
- Modify: `src/extraction/build_database_parallel.py:349-548` (same functions)

**Approach:**
Update `discover_videos()` and `merge_videos()` to:
- Calculate `merge_count = min(rear_count, front_count)` (smart pairing)
- **Always attempt merge** if both cameras have at least 1 video
- Take first `merge_count` videos from each camera (ignore extras)
- Return `(success, debug_info, status, merge_count, ignored_count)` with **explicit logging**
- Status field: "ok" (perfect match), "ok_with_extras" (extras ignored), "no_rear", "no_front", "no_videos", "merge_failed"

- [ ] **Step 1: Write `safe_merge_videos()` wrapper**

```python
def safe_merge_videos(video_list, output_path, camera_type='Rear', group_id='unknown'):
    """
    Safe wrapper around merge_videos. Returns (success, debug_info, status).

    Status values:
    - "ok" — merge succeeded
    - "no_videos" — video list is empty
    - "merge_failed" — ffmpeg error
    """
    debug_info = []

    if not video_list:
        debug_info.append(f"\n⏭️  Skipping {camera_type.lower()} merge (no video files)")
        return False, debug_info, "no_videos"

    # Proceed with merge_videos
    success, debug_info = merge_videos(video_list, output_path, camera_type)

    status = "ok" if success else "merge_failed"
    return success, debug_info, status
```

- [ ] **Step 2: Update merge calls in main()**

Around line 678-695, change:
```python
# OLD:
rear_ok, rear_debug = merge_videos(rear_videos, rear_output, 'Rear')
if rear_debug:
    for line in rear_debug:
        print(line, flush=True)
    all_merge_info.extend(rear_debug)

front_ok, front_debug = merge_videos(front_videos, front_output, 'Front')
if front_debug:
    for line in front_debug:
        print(line, flush=True)
    all_merge_info.extend(front_debug)

if rear_ok and front_ok:
    print(f"    ✅ Merged: {os.path.basename(rear_output)}, {os.path.basename(front_output)}")
else:
    print(f"  ⚠️  Skipping group {group_id}: Video merge failed")
    print()
    continue
```

To:
```python
# NEW:
print("  🎬 Merging videos...")
rear_ok, rear_debug, rear_status = safe_merge_videos(rear_videos, rear_output, 'Rear', group_id)
if rear_debug:
    for line in rear_debug:
        print(line, flush=True)
    all_merge_info.extend(rear_debug)

front_ok, front_debug, front_status = safe_merge_videos(front_videos, front_output, 'Front', group_id)
if front_debug:
    for line in front_debug:
        print(line, flush=True)
    all_merge_info.extend(front_debug)

# Determine overall video status
if rear_ok and front_ok:
    video_status = "ok"
    print(f"    ✅ Merged: {os.path.basename(rear_output)}, {os.path.basename(front_output)}")
elif rear_ok:
    video_status = "front_missing"
    print(f"    ⚠️  Front merge failed, rear available: {os.path.basename(rear_output)}")
elif front_ok:
    video_status = "rear_missing"
    print(f"    ⚠️  Rear merge failed, front available: {os.path.basename(front_output)}")
else:
    # Neither merged, but we still include GPS
    video_status = "no_videos"
    print(f"    ⚠️  No videos merged (GPS data will be included)")
```

- [ ] **Step 3: Copy to parallel variant**

Copy `safe_merge_videos()` function to `src/extraction/build_database_parallel.py` (identical code).

- [ ] **Step 4: Commit**

```bash
git add src/extraction/build_database.py src/extraction/build_database_parallel.py
git commit -m "feat: add safe_merge_videos wrapper for graceful video handling (sequential + parallel)"
```

---

## Chunk 3: Update Database Output

### Task 3: Include Trips with Optional Video Paths

**Files:**
- Modify: `src/extraction/build_database.py:700-725`
- Modify: `src/extraction/build_database_parallel.py:700-725` (same changes)

**Approach:**
- Allow `video_rear` and `video_front` to be `null` in JSON
- Add `video_status` field to track why videos are missing (from validation)
- Add `video_notes` field with **explicit explanation** of what's missing
- Update points storage logic

- [ ] **Step 1: Modify trip data preparation**

Around line 703-721, change:
```python
# OLD (always assumes videos exist):
points_for_db = [
    [p['lat'], p['lon'], p['speed_kmh'], p['altitude'], p['heading']]
    for p in all_points
]

groups_data.append({
    'id': group_id,
    'label': label,
    'date': date_str,
    'duration_min': stats['duration_min'],
    'distance_km': stats['distance_km'],
    'max_speed': stats['max_speed'],
    'avg_speed': stats['avg_speed'],
    'points': points_for_db,
    'video_rear': f'merged_videos/{group_id}_rear.mp4',
    'video_front': f'merged_videos/{group_id}_front.mp4'
})
```

To:
```python
# NEW (videos can be null):
points_for_db = [
    [p['lat'], p['lon'], p['speed_kmh'], p['altitude'], p['heading']]
    for p in all_points
]

# Only add video paths if they were successfully merged
video_rear_path = None
video_front_path = None
if rear_ok:
    video_rear_path = f'merged_videos/{group_id}_rear.mp4'
if front_ok:
    video_front_path = f'merged_videos/{group_id}_front.mp4'

groups_data.append({
    'id': group_id,
    'label': label,
    'date': date_str,
    'duration_min': stats['duration_min'],
    'distance_km': stats['distance_km'],
    'max_speed': stats['max_speed'],
    'avg_speed': stats['avg_speed'],
    'points': points_for_db,
    'video_rear': video_rear_path,
    'video_front': video_front_path,
    'video_status': video_status
})
```

- [ ] **Step 2: Update main loop to proceed with trip inclusion**

Around line 664-695, after video merging, do NOT skip the group. Instead, proceed to trip addition:

```python
# REMOVE THIS:
# if rear_ok and front_ok:
#     ...
# else:
#     print(f"  ⚠️  Skipping group {group_id}: Video merge failed")
#     print()
#     continue

# REPLACE WITH: Continue regardless of video merge status
```

- [ ] **Step 3: Increment valid_count properly**

Ensure valid_count is incremented after trip is added (line 723), so it counts trips with or without videos:

```python
valid_count += 1
print()
```

This stays the same, just ensure it runs even if videos are missing.

- [ ] **Step 4: Copy to parallel variant**

Copy the trip data preparation logic to `src/extraction/build_database_parallel.py`.

- [ ] **Step 5: Commit**

```bash
git add src/extraction/build_database.py src/extraction/build_database_parallel.py
git commit -m "feat: allow trips with optional video paths + explicit notes (sequential + parallel)"
```

---

## Chunk 4: Testing & Verification

### Task 4: Test the Build Script

**Files:**
- No code changes needed
- Test: `./build.sh`

- [ ] **Step 1: Run build script**

```bash
./build.sh
```

Expected output:
- Groups are processed even if videos are missing
- Trips appear in `data/trips.json` with `video_rear: null` or `video_front: null`
- Debug report shows which videos were skipped and why
- Script completes without errors

- [ ] **Step 2: Verify JSON structure**

```bash
python3 -c "
import json
with open('data/trips.json') as f:
    data = json.load(f)
    for trip in data['trips']:
        print(f\"{trip['id']}: rear={trip['video_rear'] is not None}, front={trip['video_front'] is not None}, status={trip.get('video_status', 'unknown')}\")
"
```

Expected: At least one trip has `null` values or `video_status` shows a non-"ok" value.

- [ ] **Step 3: Check merge report**

```bash
cat data/merge_report.txt | grep -A5 "Skipping\|no_videos\|missing"
```

Expected: Clear messages explaining why specific videos were skipped.

- [ ] **Step 4: Verify web UI handles null videos**

Open `http://localhost:8000/web/` and ensure:
- Trips with missing videos still appear on the map
- Charts render correctly
- Video players handle null video paths gracefully (or hide them)

If the UI breaks with null values, update `web/index.html` to handle this:
- Check for null before adding `<video>` elements
- Show placeholder: "Video not available"

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test: verify build script handles missing videos gracefully"
```

---

## Chunk 5: Frontend Update (if needed)

### Task 5: Update Web UI for Optional Videos

**Files:**
- Read: `web/index.html`
- Potentially Modify: `web/index.html` (JavaScript section)

- [ ] **Step 1: Check current video rendering**

Search for where `video_rear` and `video_front` are used in JavaScript.

If the code assumes videos always exist and breaks with null:
```javascript
// OLD (assumes videos exist):
const rearVid = trip.video_rear;
const frontVid = trip.video_front;
document.getElementById('rearVideo').src = rearVid;
document.getElementById('frontVideo').src = frontVid;
```

Change to:
```javascript
// NEW (handles null):
if (trip.video_rear) {
    document.getElementById('rearVideo').src = trip.video_rear;
    document.getElementById('rearVideo').style.display = 'block';
} else {
    document.getElementById('rearVideo').style.display = 'none';
    document.getElementById('rearLabel').innerText += ' (Not available)';
}

if (trip.video_front) {
    document.getElementById('frontVideo').src = trip.video_front;
    document.getElementById('frontVideo').style.display = 'block';
} else {
    document.getElementById('frontVideo').style.display = 'none';
    document.getElementById('frontLabel').innerText += ' (Not available)';
}
```

- [ ] **Step 2: Test UI with null videos**

1. Run `./build.sh`
2. Run `./run.sh`
3. Open `http://localhost:8000/web/`
4. Select a trip with missing videos
5. Verify the UI doesn't crash, videos are hidden or show "Not available"

- [ ] **Step 3: Commit**

```bash
git add web/index.html
git commit -m "fix: handle missing video paths in web UI"
```

---

## Implementation Order

1. **Chunk 1** — Refactor validation (GPS vs. videos)
   - Implement in `build_database.py`
   - Copy to `build_database_parallel.py`

2. **Chunk 2** — Implement safe video merge wrapper
   - Implement in `build_database.py`
   - Copy to `build_database_parallel.py`

3. **Chunk 3** — Update database output schema
   - Implement in `build_database.py`
   - Copy to `build_database_parallel.py`

4. **Chunk 4** — Test BOTH scripts
   - Test `./build.sh` (sequential)
   - Test `./tools/build_parallel.sh` (parallel)
   - Verify both produce identical output

5. **Chunk 5** — Update web UI (if needed)

**Total Estimated Time:** 25-35 minutes per chunk with testing (includes syncing parallel variant)

---

## Success Criteria

- ✅ Both sequential (`./build.sh`) and parallel (`./tools/build_parallel.sh`) scripts work identically
- ✅ Build script completes successfully even with missing/mismatched video pairs
- ✅ Trips with GPS data are included in `data/trips.json` regardless of video status
- ✅ `video_rear` and `video_front` can be `null` in JSON
- ✅ `video_status` field describes why videos are missing (e.g., "count_mismatch", "no_videos")
- ✅ `video_notes` field contains **explicit explanation** (e.g., "800 rear vs 801 front - could not create pair")
- ✅ Console output shows **explicit messages** for each video issue (not just generic warnings)
- ✅ Debug report clearly logs per-trip video issues with recommendations
- ✅ Web UI handles null video paths without crashing
- ✅ Real-world test: 45,009 GPS points are saved (not lost) when video count mismatches
- ✅ All commits follow the pattern: clear message, no force-push

---

## Rollback Plan

If issues arise:

```bash
# Undo to last working state
git revert HEAD~5..HEAD    # Undo last 5 commits
git push origin develop
```

Or, reset to main:
```bash
git checkout main
git pull origin main
git checkout -b fix/video-resilience develop
# Then redo the changes more carefully
```

---

## References
- GitHub Issue: #7
- CLAUDE.md: Development workflow & video encoding notes
- Video Merge Function: `merge_videos()` ~line 428
- Main Loop: `main()` ~line 590
