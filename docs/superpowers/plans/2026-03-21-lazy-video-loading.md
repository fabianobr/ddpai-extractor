# Lazy On-Demand Video Loading Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent automatic video downloads when selecting trips; load videos only when user clicks play, with automatic silent cancellation when switching trips.

**Architecture:** Modify `updateVideos()` to store video paths in `data-lazy-src` attributes instead of immediately setting `src`. Add `attachLazyLoadListener()` to detect first play event and load video on-demand. Call this listener attachment from `selectTrip()`. Browser automatically cancels pending downloads when `src` is cleared.

**Tech Stack:** Vanilla JavaScript (no new dependencies), HTML5 video element API, browser's native HTTP request cancellation.

---

## File Structure

**Files to modify:**
- `web/index.html` - Single file with all changes (JavaScript functions only, no HTML structure changes)
  - `updateVideos()` - Modified to clear src and use data attributes
  - `attachLazyLoadListener()` - New function to add play event listener
  - `selectTrip()` - Modified to call listener attachment

**No new files created.** This is a pure behavioral change to existing function.

---

## Implementation Tasks

### Task 1: Update updateVideos() to Clear Old Videos and Store Paths

**Files:**
- Modify: `web/index.html` - `updateVideos()` function (~lines 992-1035)

- [ ] **Step 1: Locate updateVideos() function**

Open `web/index.html` and find the `updateVideos()` function. Verify it currently contains:
```javascript
function updateVideos(group, idx) {
    const rearVideo = document.getElementById('video-rear');
    const frontVideo = document.getElementById('video-front');
    // ... existing code ...
    if (group.video_rear) {
        const rearSrc = '../' + group.video_rear;
        rearVideo.src = rearSrc;  // ← THIS IS THE PROBLEM
```

- [ ] **Step 2: Add silent cancellation at function start**

Insert this code at the very beginning of `updateVideos()` after the variable declarations, before any existing logic:

```javascript
        // Silent cancellation: clear any previous video loads
        rearVideo.src = '';
        frontVideo.src = '';
        rearVideo.dataset.lazySrc = '';
        frontVideo.dataset.lazySrc = '';
```

This should come right after:
```javascript
const rearVideo = document.getElementById('video-rear');
const frontVideo = document.getElementById('video-front');
```

- [ ] **Step 3: Replace immediate src assignment with data attribute storage**

Find this block:
```javascript
            if (group.video_rear) {
                const rearSrc = '../' + group.video_rear;
                rearVideo.src = rearSrc;
```

Replace `rearVideo.src = rearSrc;` with:
```javascript
            if (group.video_rear) {
                const rearSrc = '../' + group.video_rear;
                rearVideo.dataset.lazySrc = rearSrc;  // Store for lazy loading
```

And replace the console.log if it exists:
```javascript
                console.log('📹 Rear video queued (lazy load):', rearSrc);
```

- [ ] **Step 4: Repeat for front video**

Find this block:
```javascript
            if (group.video_front) {
                frontVideo.src = '../' + group.video_front;
```

Replace with:
```javascript
            if (group.video_front) {
                const frontSrc = '../' + group.video_front;
                frontVideo.dataset.lazySrc = frontSrc;  // Store for lazy loading
```

- [ ] **Step 5: Verify updateVideos() structure**

Your modified `updateVideos()` should now look like:
```javascript
function updateVideos(group, idx) {
    const rearVideo = document.getElementById('video-rear');
    const frontVideo = document.getElementById('video-front');
    const rearContainer = document.getElementById('rear-container');
    const frontContainer = document.getElementById('front-container');
    const rearTitle = document.getElementById('rear-title');
    const frontTitle = document.getElementById('front-title');
    const badge = `${Math.round(group.duration_min)} MIN`;

    // Silent cancellation: clear any previous video loads
    rearVideo.src = '';
    frontVideo.src = '';
    rearVideo.dataset.lazySrc = '';
    frontVideo.dataset.lazySrc = '';

    // Handle rear video
    if (group.video_rear) {
        const rearSrc = '../' + group.video_rear;
        rearVideo.dataset.lazySrc = rearSrc;  // Store for lazy loading
        console.log('📹 Rear video queued (lazy load):', rearSrc);
        document.getElementById('rear-path').textContent = group.video_rear;
        document.getElementById('rear-badge').textContent = badge;
        rearContainer.style.display = 'block';
        rearTitle.classList.remove('video-unavailable');
    } else {
        rearContainer.style.display = 'none';
        rearTitle.classList.add('video-unavailable');
    }

    // Handle front video
    if (group.video_front) {
        const frontSrc = '../' + group.video_front;
        frontVideo.dataset.lazySrc = frontSrc;  // Store for lazy loading
        document.getElementById('front-path').textContent = group.video_front;
        document.getElementById('front-badge').textContent = badge;
        frontContainer.style.display = 'block';
        frontTitle.classList.remove('video-unavailable');
    } else {
        frontContainer.style.display = 'none';
        frontTitle.classList.add('video-unavailable');
    }

    // Attach lazy load listeners (NEW - added in Task 2)
    attachLazyLoadListener(rearVideo);
    attachLazyLoadListener(frontVideo);
}
```

- [ ] **Step 6: Test in browser - verify no videos load on trip selection**

Run: `./run.sh` (server should already be running)
Open: `http://localhost:8000/web/`

1. Open DevTools (F12)
2. Go to Network tab
3. Select a trip from sidebar
4. **EXPECTED:** No video download requests appear in Network tab
5. **CHECK DevTools Elements tab:** Verify `<video id="video-rear">` has `data-lazy-src` attribute set but `src` attribute is empty

- [ ] **Step 7: Commit updateVideos changes**

```bash
git add web/index.html
git commit -m "refactor: modify updateVideos to defer video loading

- Clear previous video src on trip selection (silent cancellation)
- Store video paths in data-lazy-src attributes instead of loading immediately
- Console logs now show 'queued (lazy load)' status
- Actual video download deferred until play event (see attachLazyLoadListener)"
```

---

### Task 2: Add attachLazyLoadListener() Function

**Files:**
- Modify: `web/index.html` - Add new function before `updateVideos()` function

- [ ] **Step 1: Locate insertion point**

Find the `updateVideos()` function. We'll add `attachLazyLoadListener()` right before it.

Search for: `function updateVideos(group, idx) {`

Add the new function immediately above this line.

- [ ] **Step 2: Insert attachLazyLoadListener() function**

```javascript
        function attachLazyLoadListener(videoElement) {
            // Load video on first play attempt
            const handlePlayAttempt = () => {
                if (!videoElement.src && videoElement.dataset.lazySrc) {
                    videoElement.src = videoElement.dataset.lazySrc;
                    console.log('📹 Lazy loading video:', videoElement.dataset.lazySrc);
                }
                // Remove listener after first use (no need to re-load)
                videoElement.removeEventListener('play', handlePlayAttempt);
            };

            videoElement.addEventListener('play', handlePlayAttempt);
        }

```

**Indentation:** Match the indentation level of `updateVideos()` (should be inside the main script tag, same level as other functions).

- [ ] **Step 3: Test play event listener attachment**

Run: `./run.sh`
Open: `http://localhost:8000/web/`

1. Open DevTools Console
2. Select a trip
3. Click play button on a video
4. **EXPECTED:** Console logs `📹 Lazy loading video: ../merged_videos/...`
5. **EXPECTED:** Video begins buffering (loading indicator appears)
6. **EXPECTED:** In Network tab, you should see the video file being downloaded

- [ ] **Step 4: Test listener removal**

1. With video still playing, click pause
2. Click play again
3. **EXPECTED:** Console does NOT log `📹 Lazy loading video:...` again (listener was removed after first play)
4. **EXPECTED:** Video resumes without re-downloading

- [ ] **Step 5: Commit attachLazyLoadListener addition**

```bash
git add web/index.html
git commit -m "feat: add attachLazyLoadListener function for lazy video loading

- New function adds play event listener to video element
- On first play, loads video src from data-lazy-src attribute
- Automatically removes listener after first use (prevents re-loading)
- Console logs when lazy load triggered"
```

---

### Task 3: Call attachLazyLoadListener() from selectTrip()

**Files:**
- Modify: `web/index.html` - `selectTrip()` function (~lines 607-635)

- [ ] **Step 1: Locate selectTrip() function**

Find `function selectTrip(GROUPS, idx) {`

Verify it currently calls `updateVideos(group, idx);` somewhere in the middle.

- [ ] **Step 2: Verify updateVideos() calls listeners**

Check that `updateVideos()` already contains (from Task 1):
```javascript
    // Attach lazy load listeners
    attachLazyLoadListener(rearVideo);
    attachLazyLoadListener(frontVideo);
```

If you added this correctly in Task 1, Step 5, you're done here.

If NOT, add these two lines at the end of `updateVideos()`, right before the closing brace:

```javascript
    attachLazyLoadListener(rearVideo);
    attachLazyLoadListener(frontVideo);
```

- [ ] **Step 3: Test end-to-end flow**

Run: `./run.sh`
Open: `http://localhost:8000/web/`

1. Open DevTools Network tab
2. Select trip A from sidebar
3. **EXPECTED:** No network requests for video
4. In Network tab, right-click and select "Clear" to reset
5. Click play on video for trip A
6. **EXPECTED:** Network tab shows video file being downloaded
7. Pause video
8. Select trip B from sidebar
9. **EXPECTED:** Trip A's video download stops (check Network tab shows red X or "cancelled")
10. Click play on trip B video
11. **EXPECTED:** Trip B video downloads

- [ ] **Step 4: Commit selectTrip integration**

```bash
git add web/index.html
git commit -m "feat: integrate lazy load listeners into trip selection workflow

- selectTrip() already calls updateVideos() which now attaches listeners
- updateVideos() calls attachLazyLoadListener for both rear and front videos
- Lazy loading now fully integrated into trip selection flow"
```

---

### Task 4: Test Silent Cancellation Behavior

**Files:**
- Test: Manual testing (DevTools Network tab, no automated tests)

- [ ] **Step 1: Test scenario - Switch trips while buffering**

Run: `./run.sh`
Open: `http://localhost:8000/web/`
Open DevTools (F12) → Network tab

1. Select a trip with a large video (e.g., Trip 4: 67 min)
2. Click play button
3. **Video starts buffering** (you'll see network request in Network tab)
4. **Immediately select a different trip** (don't wait for buffering to complete)
5. **EXPECTED:**
   - Previous video's network request shows red X or "cancelled" status
   - Previous video's `src` is cleared
   - New trip's video `src` is still empty (waiting for play click)
6. Click play on new trip's video
7. **EXPECTED:** New video downloads cleanly without interference

- [ ] **Step 2: Test scenario - Multiple rapid trip switches**

1. Rapidly click through 4-5 different trips in sidebar
2. Don't click play, just select them
3. **EXPECTED:** No network activity, no downloads happening
4. Open DevTools Console
5. **EXPECTED:** No errors, no warnings
6. Now click play on the last trip you selected
7. **EXPECTED:** Only that trip's video downloads

- [ ] **Step 3: Test scenario - Switching during active playback**

1. Select trip A, click play, wait for video to start playing smoothly
2. Select trip B (while trip A is still playing)
3. **EXPECTED:**
   - Trip A video stops (audio cuts out)
   - Trip A's `src` is cleared
   - Loading indicator for trip B appears if you click play
4. Trip B is now ready to play
5. Click play on trip B
6. **EXPECTED:** Trip B video loads and plays

- [ ] **Step 4: Verify console logs show correct flow**

1. Open DevTools Console
2. Select trip, click play
3. **EXPECTED:** Logs show:
   ```
   🔄 Sync mode changed to: linked  (or current mode)
   📹 Lazy loading video: ../merged_videos/XXXXXXXX_rear.mp4
   📹 Lazy loading video: ../merged_videos/XXXXXXXX_front.mp4
   ```
4. Switch trip
5. **EXPECTED:** No new "Lazy loading" logs yet (videos not loaded)
6. Click play on new trip
7. **EXPECTED:** "Lazy loading" logs appear for new trip only

- [ ] **Step 5: Document manual test results**

Create a checklist in your notes (or comment in code) showing:
- ✅ Videos don't download on trip selection
- ✅ Videos load on first play click
- ✅ Switching trips silently cancels previous download
- ✅ No console errors
- ✅ Loading indicator appears/disappears correctly
- ✅ Sync listeners still work (map updates, charts update)

- [ ] **Step 6: Commit test verification**

```bash
git add -A  # (nothing to commit unless you added comments)
git commit -m "test: verify lazy loading and silent cancellation behavior

Manual testing completed:
- Videos don't download until play is clicked ✓
- Switching trips silently cancels previous downloads ✓
- No console errors or warnings ✓
- All sync features continue to work ✓
- See docs/superpowers/specs/2026-03-21-lazy-video-loading-design.md section 6.1 for full test scenarios"
```

---

### Task 5: Verify All Tests Pass and No Regressions

**Files:**
- Test: `tests/test_*.py` (existing test suite)

- [ ] **Step 1: Run existing test suite**

```bash
pytest tests/ -v
```

**EXPECTED:** All tests pass (same as before, this change is frontend-only)

- [ ] **Step 2: Check for console errors in DevTools**

Run: `./run.sh`
Open: `http://localhost:8000/web/`
Open DevTools Console (F12)

1. Select multiple trips
2. Click play on different videos
3. Switch trips during playback
4. **EXPECTED:** No red console errors
5. Warnings are OK (if any come from external libraries)

- [ ] **Step 3: Test all existing features still work**

**Video Sync:**
- Select trip with video
- Play video
- Click on map point
- **EXPECTED:** Video seeks to that position ✓

**Map Updates:**
- Play video
- **EXPECTED:** Blue marker moves on map in real-time ✓

**Charts:**
- Play video
- **EXPECTED:** Orange playhead line moves across speed/altitude charts ✓

**Mode Switching:**
- Click "🔗 Linked" and "🎬 Independent" buttons
- **EXPECTED:** Buttons change color, localStorage saves preference ✓
- Play video in independent mode
- **EXPECTED:** Rear and front videos sync independently ✓

- [ ] **Step 4: Commit verification**

```bash
git add -A
git commit -m "test: verify no regressions in existing features

- All pytest tests pass
- No console errors in browser
- Video sync functionality works ✓
- Map marker updates correctly ✓
- Chart playhead visualization works ✓
- Sync mode switching works ✓
- All features verified as regression-free"
```

---

## Testing Checklist

**Manual Testing (no automated tests needed for this change):**

- [ ] Test 1: Lazy loading on trip selection
  - Select trip → verify `src` is empty → click play → verify download starts

- [ ] Test 2: Silent cancellation
  - Select trip A → click play → immediately select trip B → verify A's download stops

- [ ] Test 3: Multiple rapid switches
  - Click through 5 trips without playing → verify no downloads → click play → only one downloads

- [ ] Test 4: Playback switching
  - Play trip A → select trip B → verify A stops, B queued → click play B → works

- [ ] Test 5: No regressions
  - Video sync, map updates, charts, sync modes all work as before

**Browser DevTools Verification:**

- [ ] Network tab shows no video downloads on trip selection
- [ ] Network tab shows download starting only on play click
- [ ] Network shows "cancelled" for previous video when switching trips
- [ ] Elements tab shows `data-lazy-src` attributes populated, `src` attribute empty
- [ ] Console shows "📹 Lazy loading video:" logs only on play click

---

## Success Criteria

✅ Videos do not download until user clicks play button
✅ Switching trips cancels previous video download silently
✅ Video paths stored in `data-lazy-src` attributes
✅ No console errors or warnings
✅ All existing features (sync, maps, charts) continue to work
✅ Manual tests pass (all 5 scenarios)
✅ No regressions in existing functionality

---

## Files Modified Summary

| File | Changes | Lines |
|------|---------|-------|
| `web/index.html` | Clear src in `updateVideos()`, add `attachLazyLoadListener()`, integrate into `selectTrip()` | ~50 lines |

**Total effort:** ~50 lines of code across 1 file, ~4 commits, ~30 minutes execution.

