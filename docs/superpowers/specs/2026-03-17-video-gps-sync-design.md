# Video ↔ GPS Synchronization (Precise Frame Matching)
**Design Spec**
**Date:** March 17, 2026
**Status:** Approved for Implementation
**Priority:** P1 (Core Feature)
**Estimated Effort:** 4-5 hours

---

## Executive Summary

Enable bidirectional synchronization between video playback and GPS map position. Users can:
- **Play/scrub video** → map updates to show current GPS position in real-time
- **Click map** → video seeks to corresponding moment
- **Switchable modes** → independent sync (rear/front separate) or linked sync (synchronized together)
- **Handle gaps** → when video is shorter than GPS data, show visual indicator and allow map interaction beyond video end

**MVP Scope:** Second-level accuracy via linear interpolation. Frame-level accuracy framework added for future enhancement.

---

## 1. Data Schema Changes

### 1.1 Enhanced Trip JSON Schema

Add the following fields to each trip in `data/trips.json`:

```json
{
  "id": "20260314131346",
  "label": "Mar 14 13:13 → 13:14",
  "date": "2026-03-14",
  "duration_min": 10.5,
  "distance_km": 31.2,
  "max_speed": 85.0,
  "avg_speed": 45.2,
  "video_rear": "merged_videos/20260314131346_rear.mp4",
  "video_front": "merged_videos/20260314131346_front.mp4",

  // NEW FIELDS FOR SYNC
  "video_duration_s": 630.0,           // Actual video duration from ffprobe (seconds)
  "start_timestamp": "2026-03-14T13:13:46Z",  // Trip start time (ISO 8601)
  "gps_points_count": 523,             // Total GPS points in active segments (excludes idle)
  "video_duration_status": "match",    // "match" | "video_shorter" | "video_longer"

  // Sparse timestamps for validation/future frame-level sync
  "sparse_timestamps": [
    {"index": 0, "timestamp": "2026-03-14T13:13:46Z"},
    {"index": 10, "timestamp": "2026-03-14T13:14:12Z"},
    {"index": 20, "timestamp": "2026-03-14T13:14:38Z"},
    // ... every 10th GPS point
  ],

  // Existing fields
  "points": [[lat, lon, speed_kmh, altitude, distance_km], ...],
  "idle_segments": [...]
}
```

### 1.2 Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `video_duration_s` | float | Actual video duration in seconds (from ffprobe). Null if video unavailable. |
| `start_timestamp` | ISO 8601 string | Trip start time (first GPS point timestamp). Used for sparse timestamp validation. |
| `gps_points_count` | integer | Total GPS points **excluding idle segments**. Used for linear interpolation. |
| `video_duration_status` | string | Validation result: `"match"` (±5s), `"video_shorter"`, `"video_longer"`, `"no_video"` |
| `sparse_timestamps` | array | Sample timestamps at every 10th GPS point. For validation and future frame-level enhancement. |

### 1.3 Backward Compatibility

- Old code without these fields continues to work (frontend gracefully disables sync)
- New fields are optional; build process populates them
- GPS point array structure unchanged

---

## 2. Build Process Changes

### 2.1 Video Duration Extraction (build_database.py)

**During trip assembly, for each trip's video pair (rear/front):**

```python
def extract_video_duration(video_path):
    """Extract actual video duration using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1:noprint_filename=1',
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        return float(result.stdout.strip())
    return None
```

### 2.2 Duration Validation (build_database.py)

**After extracting video duration, validate against GPS data:**

```python
gps_duration_s = (all_points[-1]['timestamp'] - all_points[0]['timestamp']).total_seconds()
video_duration_s = extract_video_duration(video_path)

if video_duration_s is None:
    status = "no_video"
    print(f"  ⚠️  Video unavailable: {os.path.basename(video_path)}")
elif abs(video_duration_s - gps_duration_s) <= 5:
    status = "match"
    print(f"  ✅ Duration match: video {video_duration_s:.1f}s vs GPS {gps_duration_s:.1f}s")
elif video_duration_s < gps_duration_s:
    status = "video_shorter"
    gap_s = gps_duration_s - video_duration_s
    print(f"  ⚠️  Video shorter by {gap_s:.1f}s (video {video_duration_s:.1f}s vs GPS {gps_duration_s:.1f}s)")
else:
    status = "video_longer"
    print(f"  ⚠️  Video longer than GPS (may indicate encoding issue)")
```

**Trust GPS as source of truth** — use GPS duration for sync calculations, not video duration.

### 2.3 Sparse Timestamp Computation (build_database.py)

**Generate sample timestamps at every 10th GPS point:**

```python
sparse_timestamps = []
for i in range(0, len(all_points), 10):
    sparse_timestamps.append({
        "index": i,
        "timestamp": all_points[i]['timestamp'].isoformat()
    })
```

### 2.4 JSON Output Assembly

**Add to trip object in groups_data:**

```python
groups_data.append({
    "id": trip_id,
    "label": trip_label,
    # ... existing fields ...

    # New sync fields
    "video_duration_s": video_duration_s,
    "start_timestamp": all_points[0]['timestamp'].isoformat(),
    "gps_points_count": len(all_points),  # Excluding idle
    "video_duration_status": status,
    "sparse_timestamps": sparse_timestamps
})
```

### 2.5 Error Handling

| Scenario | Behavior |
|----------|----------|
| ffprobe fails | Log error, set `video_duration_s = null`, continue |
| Video missing | Set `video_duration_s = null`, `status = "no_video"` |
| GPS data empty | Skip sync fields, log error |
| Both videos missing | Set both to null, frontend disables sync |

---

## 3. Frontend Synchronization Architecture

### 3.1 Sync Timeline Calculation

**Linear interpolation (MVP approach):**

```
GPS timeline maps to video timeline:
  gps_position_ratio = currentGpsPointIndex / total_gps_points_count
  video_seek_time = gps_position_ratio * gps_duration_s
```

**Reverse calculation (map click → video seek):**

```
  clicked_point_index (from map.on('click'))
  video_seek_time = (clicked_point_index / total_gps_points_count) * gps_duration_s
  video.currentTime = video_seek_time
```

### 3.2 Event Listeners

**Video playback → Map update:**

```javascript
// Fires when video plays/scrubs
video.addEventListener('timeupdate', (e) => {
    const videoTime = e.target.currentTime;
    const gpsIndex = Math.floor((videoTime / gps_duration_s) * points.length);
    updateMapMarker(points[gpsIndex]);
});

// Fires when user scrubs video
video.addEventListener('seeking', (e) => {
    const videoTime = e.target.currentTime;
    const gpsIndex = Math.floor((videoTime / gps_duration_s) * points.length);
    updateMapMarker(points[gpsIndex]);
});
```

**Map click → Video seek:**

```javascript
map.on('click', (e) => {
    const clickedIndex = findClosestGpsPoint(e.latlng);
    const seekTime = (clickedIndex / points.length) * gps_duration_s;

    if (syncMode === 'linked') {
        rearVideo.currentTime = seekTime;
        frontVideo.currentTime = seekTime;
    } else {
        activeVideo.currentTime = seekTime;
    }

    updateMapMarker(points[clickedIndex]);
});
```

### 3.3 Sync Mode Management

**Two modes:**

| Mode | Behavior |
|------|----------|
| **Independent** | Rear and front videos sync independently to map. Scrubbing one doesn't affect the other. |
| **Linked** | Both videos stay synchronized. Scrubbing one automatically scrubs the other. Both linked to map. |

**Implementation:**

```javascript
let syncMode = 'linked';  // default

function setSyncMode(newMode) {
    syncMode = newMode;
    if (newMode === 'linked' && rearVideo.currentTime !== frontVideo.currentTime) {
        // Sync to whichever video was last interacted with
        frontVideo.currentTime = rearVideo.currentTime;
    }
}
```

### 3.4 Preventing Circular Updates

**Problem:** Video update → map update → map click → video update (infinite loop)

**Solution:** Track event source:

```javascript
let syncSource = null;  // 'video' | 'map' | null

video.addEventListener('timeupdate', () => {
    if (syncSource === 'map') return;  // Ignore if map triggered this
    syncSource = 'video';
    updateMapMarker(...);
    syncSource = null;
});

map.on('click', () => {
    if (syncSource === 'video') return;  // Ignore if video triggered this
    syncSource = 'map';
    video.currentTime = ...;
    updateMapMarker(...);
    syncSource = null;
});
```

---

## 4. UI Components

### 4.1 Sync Mode Toggle

**Location:** Above video players or in trip controls

```
[🔗 Linked] [🎬 Independent]  ← Toggle button, shows active mode
```

**Behavior:**
- Click to switch modes
- Visual feedback showing current mode
- Label explains mode (tooltip)

### 4.2 Video Status Badges

**Location:** Top-right of each video player

| Badge | Meaning | Color |
|-------|---------|-------|
| ✅ Playing | Video synced and playing | Green |
| ⏸ Paused | Video paused | Gray |
| ⚠️ Video ended at 9:00 | Video finished but GPS data continues | Yellow |
| ❌ Unavailable | Video file not found | Red |

### 4.3 Current Position Marker (Map)

**Large pulsing marker showing current playback position:**

```
📍 Current Position
├─ Time in video: 5:23
├─ Speed: 45.2 km/h
├─ Altitude: 87.3 m
├─ Distance from start: 12.5 km
└─ Distance to end: 18.7 km
```

**Visual styling:**
- Bright color (e.g., bright blue)
- Pulsing animation during playback
- Smooth movement as video plays

### 4.4 Polyline Styling (Past vs Future)

**Polyline drawn in two colors:**

```
━━━━━━━━ (bright white) ← Already played
────────  (faded gray) ← Future / not yet played
- - - - - (dashed gray) ← Idle segments (not clickable for sync)
```

**Updates in real-time as video plays.**

### 4.5 Scrubbing Feedback

**When user hovers over map polyline:**

```
Tooltip: "13:14:32 (5.2 km into trip)"
Cursor: pointer (clickable)
```

**When user hovers over video progress bar:**

```
Tooltip: "Click map to sync playback to this time"
or show time code like standard video players
```

---

## 5. Edge Case Handling

### 5.1 Video Shorter Than GPS Data

**Scenario:** Trip is 10 minutes (600 GPS points), video is 9 minutes (540 seconds)

**Behavior:**
1. Yellow badge: "⚠️ Video ended at 9:00"
2. Video freezes at last frame at 9:00 mark
3. Allow clicking map points beyond 9:00 (video stays frozen, map shows position)
4. `gps_points_count` includes all points; sync calculation works correctly
5. Build logs: "Trip 123: Video 9m vs GPS 10m (+1m gap)"

**Frontend code:**

```javascript
if (videoTime >= gps_duration_s) {
    // Video ended before GPS data ended
    showBadge('Video ended at ' + formatTime(gps_duration_s));
    // Continue allowing map clicks beyond video end
}
```

### 5.2 Video Longer Than GPS Data

**Scenario:** Video is 11 minutes but GPS data is 10 minutes (shouldn't happen)

**Behavior:**
1. Use GPS duration as truth (gps_duration_s)
2. After GPS data ends, video can still play but no GPS points to sync
3. Map marker stays at last GPS point (grayed out)
4. Build logs: "Trip 123: Video longer than GPS (possible encoding issue)"

### 5.3 Video Unavailable

**Scenario:** Video file missing or corrupted

**Behavior:**
1. Set `video_duration_s = null` in JSON
2. Video player shows: "❌ Rear video not available"
3. If only one video missing: other video syncs alone
4. If both missing: disable all sync controls
5. Map remains fully interactive (no video to sync, but GPS data is valid)

### 5.4 Idle Segments in Sync

**Behavior:**
- Idle segments are **skipped from sync timeline** (gps_points_count excludes idle)
- If user clicks on an idle segment on the map:
  - Video seeks to idle segment start time
  - Map shows idle marker
  - User can interact with idle segment despite it being "collapsed"
- Optional toggle: "Show idle segments in sync" (default: off)

### 5.5 Switching Modes During Playback

**Scenario:** User is playing rear video (independent mode), switches to linked

**Behavior:**
1. Smooth transition (no video jump)
2. Front video syncs to rear video's current position
3. Both continue playing together from that point
4. No visual disruption

---

## 6. Testing Strategy

### 6.1 Unit Tests (build_database.py)

- ✅ Extract video duration correctly (ffprobe integration)
- ✅ Validate duration match/shorter/longer logic
- ✅ Compute sparse timestamps correctly
- ✅ Handle missing videos gracefully
- ✅ GPS points count excludes idle segments

### 6.2 Integration Tests (build + JSON output)

- ✅ Full trip with both videos → JSON includes video_duration_s, start_timestamp, sparse_timestamps
- ✅ Video shorter than GPS → status = "video_shorter", gap logged
- ✅ Video missing → video_duration_s = null
- ✅ Idle segments properly excluded from gps_points_count

### 6.3 Frontend Tests (web/index.html)

- ✅ Play video → map marker updates in real-time
- ✅ Scrub video → map marker jumps to new position
- ✅ Click map → both videos seek (linked mode)
- ✅ Click map → only active video seeks (independent mode)
- ✅ Switch modes during playback → smooth transition
- ✅ Video ends before GPS data → badge shows, map still interactive
- ✅ Both videos missing → sync controls disabled
- ✅ Idle segments → skipped in sync timeline
- ✅ No circular update loops (event source tracking works)

### 6.4 Manual Testing (Real Dashcam Data)

- ✅ Play a real trip video → verify map follows playback
- ✅ Click a point on map → verify video seeks to that time
- ✅ Verify timestamps are accurate (sample 5+ trips)
- ✅ Test mode switching with different video lengths
- ✅ Test gap handling (video shorter than GPS)

---

## 7. Future Enhancements (Out of Scope)

1. **Frame-level accuracy:** Add per-point timestamps, implement frame counting
2. **Reverse video sync:** Click GPS point in chart → seek video
3. **Multi-camera sync refinement:** Handle rear/front timing offsets (e.g., rear is 2 frames behind front)
4. **Video quality indicators:** Show frame drops, encoder quality on map
5. **Heatmap integration:** Color polyline by speed, temperature, or other metrics during playback

---

## 8. Success Criteria

✅ Video plays → map updates with current position
✅ Map click → video seeks to that GPS point
✅ Mode toggle works smoothly (independent ↔ linked)
✅ Idle segments properly excluded from sync timeline
✅ Video gaps handled gracefully (badge + interactive map)
✅ No circular update loops or performance issues
✅ Build process validates video durations and logs mismatches
✅ All unit + integration tests pass
✅ Manual testing on 3+ real trips successful

---

## 9. Implementation Dependencies

**Must be done before this task:**
- None (Task 1 auto-sync is independent, Task 3 idle detection already implemented)

**Blocks:**
- None (this is self-contained)

**Notes:**
- Task 2 can run in parallel with other tasks
- Idle detection (Task 3) already provides `idle_segments` in JSON, so we just skip them in sync
- Stream copy video merging (recent PR #17) means video_duration_s extraction must account for re-encoded fallback

