# Manual Video-GPS Sync Testing Guide

## Setup

1. Start web server:
   ```bash
   cd /Users/fabianosilva/Documentos/code/ddpai_extractor
   ./run.sh
   ```

2. Open browser:
   ```
   http://localhost:8000/web/
   ```

## Test Scenarios

### Scenario 1: Video → Map Sync (Linked Mode)

**Steps:**
1. Select a trip with both rear and front videos
2. Verify sync mode shows "🔗 Linked" (green button)
3. Press Play on rear video
4. Observe:
   - [ ] Map marker appears and moves along polyline
   - [ ] Marker position matches video playback (within 1-2 seconds)
   - [ ] Front video also plays automatically
   - [ ] Both videos stay synchronized

**Expected:** Smooth video playback with real-time map updates

---

### Scenario 2: Scrubbing → Map Jump (Linked Mode)

**Steps:**
1. (From Scenario 1) Stop at any point in video
2. Drag video progress bar to different time (e.g., 50% through)
3. Observe:
   - [ ] Both videos jump to same position
   - [ ] Map marker jumps to corresponding GPS point
   - [ ] No lag between video and map update

**Expected:** Instant sync when scrubbing

---

### Scenario 3: Map Click → Video Seek (Linked Mode)

**Steps:**
1. (From Scenario 1) Pause videos
2. Click a different point on the polyline (map)
3. Observe:
   - [ ] Both videos seek to corresponding time
   - [ ] Map marker appears at clicked location
   - [ ] Time indicator shows current time

**Expected:** Video seeks to clicked GPS point

---

### Scenario 4: Mode Switching (Independent vs Linked)

**Steps:**
1. Start with Linked mode, both videos playing
2. Click "🎬 Independent" button
3. Observe:
   - [ ] Videos don't stop
   - [ ] Button visual changes (color updates)
   - [ ] localStorage updated (verify in DevTools)
4. Pause rear video, continue playing front video
5. Observe:
   - [ ] Front video continues independently
   - [ ] Rear video stays paused
   - [ ] Map follows front video

**Expected:** Smooth transition between modes

---

### Scenario 5: Video Shorter Than GPS (Gap Handling)

**Steps:**
1. Find a trip with `video_duration_status = "video_shorter"`
2. Play video until it ends
3. Observe:
   - [ ] Yellow badge appears: "⚠️ Video ended at X:XX"
   - [ ] Video freezes at last frame
   - [ ] Map marker can still be clicked in GPS-only area
   - [ ] Clicking beyond video end shows position but video stays frozen

**Expected:** Graceful handling of video gap

---

### Scenario 6: Video Unavailable

**Steps:**
1. Find a trip with `video_duration_status = "no_video"`
2. Observe:
   - [ ] Video player shows: "❌ Rear video not available"
   - [ ] Sync controls disabled (grayed out) if both videos missing
   - [ ] Map remains fully interactive
   - [ ] If other video available, it syncs independently

**Expected:** Graceful degradation when video missing

---

### Scenario 7: Idle Segments in Sync

**Steps:**
1. Find a trip with idle_segments
2. Play video through an idle segment
3. Observe:
   - [ ] Idle segment appears as dashed gray line on map
   - [ ] Idle segment is not clickable (or clicking shows it's idle)
   - [ ] Video plays through idle normally
   - [ ] Option to toggle idle visibility (if implemented)

**Expected:** Idle segments handled gracefully

---

### Scenario 8: Performance & Circular Updates

**Steps:**
1. Open browser DevTools → Console
2. Play video for 30 seconds
3. Observe:
   - [ ] No error messages in console
   - [ ] No excessive console logs
   - [ ] Browser doesn't lag (FPS stays ~30+)
4. Scrub video rapidly 5 times
5. Observe:
   - [ ] No console errors
   - [ ] No frozen state
   - [ ] Sync recovers after rapid scrubbing

**Expected:** No performance issues or infinite loops

---

## Sign-Off

- [ ] All 8 scenarios pass
- [ ] No console errors
- [ ] Performance acceptable (smooth video playback + map updates)
- [ ] Sync mode persistence works (refresh page, mode stays set)

Date tested: ___________
Tester: _______________
