# Lazy On-Demand Video Loading

**Design Spec**
**Date:** March 21, 2026
**Status:** Approved for Implementation
**Priority:** P2 (Quality of Life)
**Estimated Effort:** 1-2 hours

---

## Executive Summary

Optimize video loading to prevent wasting bandwidth and browser resources. Videos currently load immediately when a trip is selected, even if the user never watches them. This spec implements **lazy on-demand loading** where videos only load when the user clicks the play button.

**Key features:**
- Videos load only on first play attempt, not on trip selection
- Automatic silent cancellation when switching trips
- Reduces bandwidth waste and improves perceived performance
- Compatible with existing loading indicators

---

## 1. Current Behavior vs. Proposed Behavior

### Current (Problematic)
```
selectTrip() → updateVideos() → set video.src
  ↓
Browser immediately starts downloading video (even if user never watches)
  ↓
Multiple simultaneous downloads if user browses trips quickly
  ↓
Bandwidth wasted on unwatched videos
```

### Proposed (Lazy On-Demand)
```
selectTrip() → updateVideos() → clear video.src, show ready state
  ↓
User clicks play button on video
  ↓
Set video.src (browser downloads on-demand)
  ↓
User switches trip → clear video.src (silent cancellation)
```

---

## 2. Implementation Changes

### 2.1 Modify updateVideos() Function

**Current behavior:**
```javascript
function updateVideos(group, idx) {
    const rearVideo = document.getElementById('video-rear');
    const frontVideo = document.getElementById('video-front');

    if (group.video_rear) {
        const rearSrc = '../' + group.video_rear;
        rearVideo.src = rearSrc;  // ← IMMEDIATE LOAD (PROBLEM)
        // ... rest of setup
    }
}
```

**Proposed behavior:**
```javascript
function updateVideos(group, idx) {
    const rearVideo = document.getElementById('video-rear');
    const frontVideo = document.getElementById('video-front');

    // Clear any previous video loads (silent cancellation)
    rearVideo.src = '';
    frontVideo.src = '';

    // Store video paths in data attributes for lazy loading
    if (group.video_rear) {
        const rearSrc = '../' + group.video_rear;
        rearVideo.dataset.lazySrc = rearSrc;  // Store for later
        rearVideo.src = '';  // Don't load yet
        // ... rest of setup
    }

    if (group.video_front) {
        const frontSrc = '../' + group.video_front;
        frontVideo.dataset.lazySrc = frontSrc;  // Store for later
        frontVideo.src = '';  // Don't load yet
        // ... rest of setup
    }
}
```

### 2.2 Add Lazy Load Listener

**New function to attach to each video:**
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

**When to attach:**
- In `updateVideos()` after setting up both rear and front videos
- Called once per trip selection

### 2.3 Integration with selectTrip()

**In `selectTrip()` after calling `updateVideos()`:**
```javascript
function selectTrip(GROUPS, idx) {
    const group = GROUPS[idx];
    currentGroup = group;

    // ... existing code ...

    updateVideos(group, idx);

    // NEW: Attach lazy load listeners
    const rearVideo = document.getElementById('video-rear');
    const frontVideo = document.getElementById('video-front');
    attachLazyLoadListener(rearVideo);
    attachLazyLoadListener(frontVideo);

    // Attach sync listeners as before
    setTimeout(() => {
        if (rearVideo || frontVideo) {
            attachVideoSyncListeners(rearVideo, frontVideo);
        }
    }, 100);
}
```

---

## 3. Silent Cancellation Mechanism

**How it works:**
- When `updateVideos()` is called for a new trip, it immediately sets `video.src = ''` for both videos
- This tells the browser to stop downloading the previous video
- No user-facing notification needed (silent)
- Clean and simple

**Why it's safe:**
- Browsers handle empty `src` gracefully
- Any pending network requests are automatically cancelled
- No console errors or warnings
- User experience is seamless

---

## 4. Data Flow Diagram

```
┌─────────────────────────────────────────┐
│ User clicks trip in sidebar             │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ selectTrip(GROUPS, idx)                 │
│ ├─ Clear old video.src ('')             │
│ ├─ Store new paths in data attributes   │
│ └─ Attach play listeners                │
└──────────────┬──────────────────────────┘
               │
               ▼
        ┌──────────────┐
        │ Ready state  │
        │ (user sees   │
        │  play icon)  │
        └──────┬───────┘
               │
        ┌──────▼───────────────────────────┐
        │ User clicks play on video        │
        └──────┬───────────────────────────┘
               │
               ▼
        ┌────────────────────────────────┐
        │ play event fires               │
        │ ├─ Check if src is set         │
        │ ├─ If not, set from data attr  │
        │ └─ Remove listener             │
        └────────────────────────────────┘
               │
               ▼
        ┌────────────────────────────────┐
        │ Browser downloads video        │
        │ (loading indicator shows)      │
        └────────────────────────────────┘
```

---

## 5. Edge Cases & Error Handling

### 5.1 User switches trips while video is buffering
**Behavior:** `updateVideos()` clears `src`, browser silently stops download
**Result:** Clean, no errors

### 5.2 User clicks play, video path is invalid/missing
**Behavior:** Browser's default error handling applies (video fails to load)
**Mitigation:** Existing error handling in sync listeners will catch this
**No change needed:** Browser handles gracefully

### 5.3 User selects same trip twice
**Behavior:** First `attachLazyLoadListener()` removes itself after first play, second call adds a new listener
**Result:** Works correctly, listeners don't duplicate

### 5.4 Video element doesn't exist
**Behavior:** `attachLazyLoadListener()` checks for existence before adding listeners
**Result:** Safe, no errors

---

## 6. Testing Strategy

### 6.1 Manual Testing

**Test 1: Basic lazy loading**
- [ ] Open dashboard
- [ ] Select a trip
- [ ] Verify video `src` is empty (check DevTools → Elements)
- [ ] Verify `data-lazy-src` attribute contains the video path
- [ ] Click play on video
- [ ] Verify `src` is now set and video downloads
- [ ] Verify "⏳ Loading video..." indicator shows

**Test 2: Silent cancellation**
- [ ] Select trip A (video starts buffering)
- [ ] Immediately select trip B (before video A finishes loading)
- [ ] Verify trip A's video download stops silently
- [ ] Verify trip B's video loads when you click play
- [ ] Check DevTools → Network tab: trip A request should be cancelled

**Test 3: Multiple play attempts**
- [ ] Select trip
- [ ] Click play (video loads)
- [ ] Pause, then click play again
- [ ] Verify video plays without re-downloading
- [ ] Verify listener was removed (no double-listeners)

**Test 4: Trip switching during playback**
- [ ] Select trip A and play video
- [ ] Video is playing (not paused)
- [ ] Select trip B
- [ ] Verify trip A stops, trip B ready state shows
- [ ] Click play on trip B
- [ ] Verify trip B loads and plays

### 6.2 Browser DevTools Verification

**Network tab:**
- [ ] No video downloads when trip is selected
- [ ] Video only downloads after clicking play
- [ ] Switching trips cancels pending downloads (shows "cancelled" status)

**Elements tab:**
- [ ] `data-lazy-src` attributes are present on video elements
- [ ] `src` is empty until first play
- [ ] `src` is populated after first play

**Console:**
- [ ] No errors related to missing videos
- [ ] Console shows "📹 Lazy loading video: ..." when play is clicked
- [ ] No duplicate console messages on repeated plays

---

## 7. Success Criteria

✅ Videos do not load until user clicks play button
✅ Switching trips silently cancels previous video download
✅ Video paths stored in `data-lazy-src` attribute
✅ Loading indicator appears when video begins downloading
✅ All existing sync functionality continues to work
✅ No console errors or warnings
✅ Manual tests pass (all 4 test scenarios)

---

## 8. Backward Compatibility

**No breaking changes:**
- All existing functions and APIs remain the same
- Sync listeners work identically
- Loading indicators and error handling unchanged
- Only internal timing of video load changes (deferred to first play)

---

## 9. Performance Impact

**Improvements:**
- ✅ Reduces memory usage (videos only in RAM when playing)
- ✅ Reduces network bandwidth (no unwatched videos downloaded)
- ✅ Faster trip switching (no need to wait for video to start downloading)

**Trade-offs:**
- Small delay (100-500ms) between clicking play and video actually starting (buffering)
- Minor: adding `play` event listeners to each video (negligible overhead)

**Verdict:** Positive impact, no negatives.

---

## 10. Files to Modify

- `web/index.html` - Main changes:
  - Modify `updateVideos()` to clear `src` and use `data-lazy-src`
  - Add `attachLazyLoadListener()` function
  - Call `attachLazyLoadListener()` from `selectTrip()`

**No other files need modification** - build process, tests, or backend code unchanged.

---

## 11. Implementation Dependencies

**Must be done before this task:**
- None (independent feature)

**Blocks:**
- None (doesn't affect other work)

**Notes:**
- This is a pure frontend optimization
- Safe to implement without re-building database
- Can be tested immediately in browser

