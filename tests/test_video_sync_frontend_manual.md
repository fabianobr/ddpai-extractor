# Manual Video-GPS Sync Testing Guide

## Setup

1. Start web server:
   ```bash
   cd /Users/fabianosilva/Documentos/code/ddpai_extractor
   ./run.sh
   ```

2. Open browser:
   ```
   http://localhost:8765/web/
   ```

## Test Scenarios

### Scenario 1: Video → Map Sync (Linked Mode)

**Steps:**
1. Select a trip with both rear and front videos
2. Verify the sync padlock in the timeline bar shows "Câmeras juntas" (`aria-pressed=true`)
3. Press Play (single transport control, or Space/K) on the main camera
4. Observe:
   - [ ] Map marker appears and moves along polyline
   - [ ] Marker position matches video playback (within 1-2 seconds)
   - [ ] The playhead on the SVG timeline moves with the video
   - [ ] The other camera also plays automatically
   - [ ] Both videos stay synchronized

**Expected:** Smooth video playback with real-time map updates

---

### Scenario 2: Scrubbing → Map Jump (Linked Mode)

**Steps:**
1. (From Scenario 1) Stop at any point in video
2. Drag the playhead on the timeline (or click the timeline) to a different time (e.g., 50% through)
3. Observe:
   - [ ] Both videos jump to same position
   - [ ] Map marker jumps to corresponding GPS point
   - [ ] No lag between video and map update

**Expected:** Instant sync when scrubbing

---

### Scenario 3: Map Click → Video Seek (Linked Mode)

**Steps:**
1. (From Scenario 1) Pause videos
2. Click a different point on the polyline (map), or a chapter in the list
3. Observe:
   - [ ] Both videos seek to corresponding time
   - [ ] Map marker appears at clicked location
   - [ ] Clock and elapsed time in the transport bar update

**Expected:** Video seeks to clicked GPS point

---

### Scenario 4: Mode Switching (Independent vs Linked)

**Steps:**
1. Start with Linked mode, both videos playing
2. Click the sync padlock ("Câmeras separadas", `aria-pressed=false`)
3. Observe:
   - [ ] Videos don't stop
   - [ ] Padlock visual changes (label and icon update)
   - [ ] localStorage updated (verify in DevTools)
4. Click "Trocar" (or press C) to make the other camera the main one, then pause the main camera and play the other
5. Observe:
   - [ ] The newly main camera continues independently
   - [ ] The other camera stays paused
   - [ ] Map follows the main camera

**Expected:** Smooth transition between modes

---

### Scenario 5: Video Shorter Than GPS (Gap Handling)

**Steps:**
1. Find a trip with `video_duration_status = "video_shorter"`
2. Play video until it ends
3. Observe:
   - [ ] The notice on the video (placa sobre o vídeo) appears when the camera has no footage in that stretch
   - [ ] Video freezes at last frame
   - [ ] Map marker can still be clicked in GPS-only area
   - [ ] Clicking beyond video end shows position but video stays frozen

**Expected:** Graceful handling of video gap

---

### Scenario 6: Video Unavailable

**Steps:**
1. Find a trip with `video_duration_status = "no_video"`
2. Observe:
   - [ ] Play is disabled with the text "Viagem sem vídeo"
   - [ ] Chapters, map and timeline remain navigable
   - [ ] Map remains fully interactive
   - [ ] If other video available, it syncs independently

**Expected:** Graceful degradation when video missing

---

### Scenario 7: Idle Segments in Sync

**Steps:**
1. Find a trip with idle_segments
2. Play video through an idle segment
3. Observe:
   - [ ] Idle stretch appears as dashed gray line on map
   - [ ] Idle stretch is shown as a hatched gap on the timeline
   - [ ] Video plays through idle normally

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
