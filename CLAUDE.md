# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# DDpai Z50 Pro Dashcam Extractor

## Project Status: ✅ REFACTORED (v3)

Clean separation: GPS/trip extraction → JSON database, web UI loads data dynamically.

## Quick Start

```bash
# Rebuild trip database from .git archives
./build.sh

# Start the web server on localhost:8000
./run.sh

# Open browser to http://localhost:8000/web/

# Auto-watch SD card for new recordings (optional)
./watch.sh             # Sequential build (default)
./watch.sh --parallel  # Parallel build (2.5-3.5x faster)
```

## ⚠️ MUST DO: Development Workflow (Git Flow + TDD)

**🔴 ALL changes to this project MUST follow this exact workflow — NO EXCEPTIONS:**

1. **Branch:** Create a feature branch from `develop` (format: `feature/*`)
   - ✅ DO: `git checkout -b feature/video-sync-gps`
   - ❌ DON'T: Commit directly to main or develop

2. **Test:** Write tests FIRST (Test-Driven Development)
   - ✅ DO: Create `tests/` directory with test cases before implementation
   - ✅ DO: Run tests locally: `pytest` or `bash tests/test_*.sh`
   - ❌ DON'T: Write code without tests

3. **Code:** Implement changes, confirm all tests pass
   - ✅ DO: Follow commit message conventions (see CONTRIBUTING.md)
   - ✅ DO: Keep changes focused (one feature per PR)
   - ❌ DON'T: Mix multiple features in one commit

4. **PR:** Push branch and create Pull Request on GitHub
   - ✅ DO: Push with: `git push -u origin feature/your-name`
   - ✅ DO: Link PR to GitHub Projects board
   - ❌ DON'T: Merge directly without PR review

5. **Review:** Get approval from project owner before merging
   - ✅ DO: Wait for code review feedback
   - ✅ DO: Fix review comments in new commits (don't amend)
   - ✅ DO: Use `/verify-before-completion` skill to confirm work is ready
   - ❌ DON'T: Self-approve or force-merge

6. **Merge:** Merge via GitHub UI (squash or rebase to keep history clean)
   - ✅ DO: Merge through GitHub interface
   - ✅ DO: Delete feature branch after merge
   - ❌ DON'T: Use force-push (`git push --force`)
   - ❌ DON'T: Merge to main directly (use develop first)

7. **Sync:** After merge to main, sync develop branch
   ```bash
   git checkout develop
   git pull origin develop
   git merge main
   git push origin develop
   git checkout main
   ```

**Why This Matters:**
- ✅ Code quality & test coverage before production
- ✅ Clean git history (easy to revert if needed)
- ✅ Prevents conflicts between main/develop
- ✅ Every commit is deployable
- ✅ Easy code review & knowledge sharing

**For Claude Code Users:**
- 🔴 **MUST** use `/verify-before-completion` skill before marking work done
- 🔴 **MUST** follow TDD: tests first, then code
- 🔴 **MUST** create feature branches (never commit to main/develop directly)
- 🔴 **MUST** use Conventional Commits for clear history

## Architecture & Workflow

```
.git TAR files (working_data/tar/)
    ↓ [parse_tar_filename + detect_trip_groups]
Auto-detect trip groups (30-min gap threshold)
    ↓ [extract_gps_from_tar]
Extract GPS from NMEA (.gpx files in TAR)
    ↓ [merge_gps_points]
Merge RMC (speed/heading) + GGA (altitude) data
    ↓ [validate groups]
Validate: speed > 0, altitude data, video counts match
    ↓ [merge_videos_ffmpeg]
Merge rear/front videos using FFmpeg (H.264 720p re-encoding)
    ↓ [Write data/trips.json]
Generate JSON database (GPS points, trip stats, video paths)
    ↓ [web/index.html]
Browser fetches JSON, renders map/charts/videos (Leaflet + Chart.js)
```

### Core Modules

**src/extraction/build_database.py** (Main)
- `parse_nmea_sentence()` / `parse_rmc()` / `parse_gga()`: NMEA sentence parsing
- `extract_gps_from_tar()`: Reads .gpx NMEA data from TAR members
- `detect_trip_groups()`: Groups consecutive .git files by 30-min gaps
- `validate_group()`: Checks speed > 0, altitude coverage, video availability
- `merge_videos()`: Concatenates rear/front videos with H.264 720p re-encoding (~70% size reduction)
- Outputs: `data/trips.json` (GPS points, trip stats, video references)

**src/extraction/build_database_parallel.py** (Parallel variant)
- Same functions as build_database.py, parallel video encoding (2.5-3.5× speedup)

**web/index.html** (Frontend)
- Fetches `data/trips.json` dynamically at page load
- Renders interactive map (Leaflet.js), speed/altitude charts (Chart.js)
- Displays trip selector, linked rear+front video players
- All UI logic is client-side JavaScript

**Utilities**
- **src/processing/merge_trips.py**: Standalone trip merging (rarely used)
- **src/video/merge_videos.py**: Standalone FFmpeg wrapper (rarely used)
- **src/extraction/ddpai_route_improved.py**: Original GPS extraction code (reference)
- **tools/build_parallel.sh**: Parallel build entry point
- **tools/debug_videos.sh**: Video debugging
- **tools/install_fftools.sh**: FFmpeg helper

### Data Sources

**Input Paths** (configured in src/extraction/build_database.py)
- `.git TAR files`: `working_data/tar/` (100 files, ~30 MB each)
- Rear videos: `/Users/fabianosilva/dashcam/DCIM/200video/rear/`
- Front videos: `/Users/fabianosilva/dashcam/DCIM/200video/front/`

**Output Paths**
- Database: `data/trips.json` (1.4 MB, auto-generated by ./build.sh)
- Dashboard: `web/index.html` (14 KB static)
- Merged videos: `merged_videos/` + `{trip_id}_rear.mp4` / `{trip_id}_front.mp4`

## Data Processing Details

### Trip Detection
- **GAP_THRESHOLD**: 30 minutes (seconds = 1800)
- Parses `.git` filename format: `YYYYMMDDHHMMSS_DURATION_SECONDS.git`
- Groups files chronologically; splits on gaps > threshold

### GPS Extraction
- **NMEA Sentence Types**: `$GPRMC` (speed/heading), `$GPGGA` (altitude/satellites)
- **Coordinate Format**: DDMM.MMMMM (degrees-minutes) → decimal degrees
- **Speed**: Knots → km/h (×1.852)
- **Timezone**: UTC (parsed from TAR filenames)
- **Validation**: Requires valid fix quality + matching lat/lon across RMC/GGA

### Video Merging
- **Tool**: FFmpeg with stream copy (default) or H.264 libx264 re-encoding (fallback)
- **Default Method**: Stream copy (`-c:v copy -c:a copy`) — lossless, instant
- **Original Resolution**: Preserved (1920x1080 typical dashcam), no scaling
- **Performance**: ~2-3 min per long trip (I/O bound, just muxing)
- **File Size**: Original dashcam size (~30 MB/min), no compression
- **Fallback**: If stream copy fails (incompatible formats), automatically retries with libx264 re-encoding
- **Fallback Performance**: ~15-20 min per trip, 720p output, ~70% size reduction, CRF 26

**Configuration (in build_database.py):**
- `merge_videos(..., use_stream_copy=True)` — Use stream copy by default
- Set `use_stream_copy=False` to force re-encoding (useful for archive/storage-constrained)

### Dashboard Output
- **Format**: Static HTML (web/index.html) + external JSON (data/trips.json)
- **Data Loading**: Async fetch() at page load, error handling for missing data
- **Map**: Leaflet.js (requires HTTP serving for tiles)
- **Charts**: Chart.js (speed + altitude profiles)
- **Videos**: <video> elements with relative paths (../merged_videos/*.mp4)

## Development & Modification

### Common Tasks

**Rebuild the trip database** (entry point)
```bash
./build.sh
# Runs: python3 -m src.extraction.build_database
# Output: data/trips.json
```

**Serve the dashboard locally**
```bash
./run.sh
# Starts: python3 -m http.server 8000
# Access: http://localhost:8000/web/
```

**Watch for new SD card recordings** (watch.sh)
- Run: `./watch.sh [--parallel]`
- Polls `/Volumes/ddpai/DCIM/203gps/tar` every 30s for new TAR files
- Auto-triggers build when new archives detected
- Backs up `data/trips.json` before each rebuild
- Sends macOS Notification Center alerts on build complete/failure
- State file `data/.last_tar_count` tracks TAR file count (gitignored)

**Change trip grouping threshold** (src/extraction/build_database.py)
- Modify `GAP_THRESHOLD` (line 24): default 30*60 seconds
- Re-run `./build.sh`

**Change idle detection settings** (src/extraction/build_database.py)
- Modify `IDLE_SPEED_THRESHOLD` (line 56): default 0.5 km/h — speeds at or below this are "idle"
- Modify `IDLE_DURATION_THRESHOLD` (line 57): default 300 seconds (5 min) — minimum idle period duration
- Re-run `./build.sh`
- Idle segments appear in `data/trips.json` as `idle_segments` array per trip
- Each segment includes: start_index, end_index, duration_s, distance_km
- UI visualizes idle periods as dashed gray lines on the map

**Modify video encoding parameters** (src/extraction/build_database.py & src/extraction/build_database_parallel.py)
- Modify encoding constants at module level (lines 51-53):
  - `OUTPUT_HEIGHT` (default 720) — target resolution
  - `VIDEO_CRF` (default 26) — quality, range 18-28 (lower = higher quality, larger file)
  - `VIDEO_PRESET` (default 'fast') — speed, options: ultrafast, fast, medium, slow
- **Important**: Both `src/extraction/build_database.py` AND `src/extraction/build_database_parallel.py` must be kept in sync (parallel imports from sequential)
- Verify output resolution: `ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 merged_videos/*_rear.mp4`

**Modify video merging function** (advanced)
- Edit `merge_videos()` function (~line 423) to adjust FFmpeg command
- Timeout is set to 1800s (30 min) for long trips; adjust if needed

### Video Encoding Tuning Guide

**Quality vs. File Size Trade-offs:**

| CRF Value | Quality | File Size | Use Case |
|-----------|---------|-----------|----------|
| 18-22 | High (near-lossless) | ~15-20 MB/min | Archive, detailed review |
| **26** | **Good (dashcam default)** | **~8 MB/min** | Standard dashcam review |
| 28+ | Lower (compressed) | ~5-6 MB/min | Storage-constrained |

**Speed vs. Encoding Time Trade-offs:**

| Preset | Speed | Encoding Time | Use Case |
|--------|-------|----------------|----------|
| ultrafast | Very fast | ~2-3 min/10min video | Quick testing, real-time |
| **fast** | **Moderate** | **~3-4 min/10min video** | Balanced (default) |
| medium | Slower | ~5-8 min/10min video | Better quality needed |
| slow | Slowest | ~10-15 min/10min video | Maximum compression |

**Common Tuning Scenarios:**

- **Storage constrained**: Set `VIDEO_CRF = 28` and `VIDEO_PRESET = 'ultrafast'` (fastest encoding, smallest files)
- **High-quality archive**: Set `VIDEO_CRF = 20` and `VIDEO_PRESET = 'slow'` (best quality, larger files, slower)
- **Default (balanced)**: `VIDEO_CRF = 26` and `VIDEO_PRESET = 'fast'` (recommended)

**Performance Notes:**
- Stream copy (old method): ~5-10 min per group, no CPU usage, full resolution
- H.264 re-encoding (current): ~15-20 min for 200+ min long trips, CPU-intensive, 70-75% size reduction
- FFmpeg timeout (1800s = 30 min) is sufficient for trips up to 206 min; longer trips may need adjustment

**Customize dashboard UI** (web/index.html)
- Edit CSS (lines 11-170) for styling changes
- Modify JavaScript functions (renderApp, updateMap, updateCharts, updateVideos)
- Update Leaflet map center/zoom, Chart.js colors, etc.

**Add new trip metadata to JSON**
- Edit `groups_data.append()` section in src/extraction/build_database.py
- Add fields to the dictionary, they'll auto-appear in web/index.html if accessed

### Testing & Validation

No automated test suite. Manual validation:

1. **Check trip detection**: `./build.sh` prints detected groups + validation results
2. **Verify database**: `python3 -c "import json; d=json.load(open('data/trips.json')); print(len(d['trips']), 'trips')"`
3. **Test UI**: `./run.sh` → open http://localhost:8000/web/ → select trip, play video
4. **Check DevTools**: Browser Console for JavaScript errors, Network tab for JSON fetch
5. **Validate maps**: Ensure Leaflet polyline renders for each trip (requires HTTP server)

**FFmpeg Build Time Expectations:**
- Short trips (10-20 min): ~5-10 min encode time
- Medium trips (60 min): ~15-20 min encode time
- Long trips (200+ min): ~40-60 min encode time (timeout set to 1800s = 30 min per video)
- If build times exceed timeout, increase `timeout` parameter in `merge_videos()` or reduce `VIDEO_CRF` for faster encoding

### Dependencies

**External Tools**
- FFmpeg with libx264 support (for video re-encoding) — verify with: `ffmpeg -codecs | grep h264`
- Python 3.6+ (standard library only: tarfile, json, subprocess, datetime, pathlib, collections, math)
- Web browser (Leaflet.js + Chart.js loaded from CDN in HTML)

**System Requirements**
- Sufficient disk space: ~15 GB for merged videos + source files
- Video paths must be accessible (currently hardcoded—adjust if relocating dashcam footage)

## Known Limitations & Quirks

- **Hardcoded paths**: Video directories are absolute paths in src/extraction/build_database.py (lines 18-20)
- **NMEA parsing**: Gracefully ignores bad checksums and malformed sentences
- **Timezone**: Assumes UTC, converts via TAR filename timestamp (no local timezone detection)
- **Video validation**: Matches rear/front count per trip but doesn't verify frame counts
- **Heatmap rendering**: Not available on file:// URLs (requires HTTP server for security)
- **22 TAR files**: Known to fail parsing (corrupted or incomplete)
- **Dynamic data loading**: web/index.html requires HTTP server (not file:// URLs) to fetch data/trips.json
- **Relative paths**: Videos must exist at merged_videos/*.mp4; check paths if videos moved

## Data Summary (Current Rebuild Results)

- **Archives**: 100 .git files → 11 groups detected → 7 valid groups
- **GPS Points**: 24,170 total extracted (real NMEA data, no interpolation)
- **Videos**: 7 groups with rear+front merged (14.9 GB total)
- **Coverage**: Mar 6-8, 2026, Florianópolis, Brazil (UTC timezone)

## Trip Groups (Valid)

1. Mar 06 13:47 → 14:04 (29.66 km, 16.8 min)
2. Mar 06 15:19 → 15:26 (20.44 km, 7.0 min)
3. Mar 06 16:17 → 16:43 (31.2 km, 25.6 min)
4. Mar 07 10:31 → 11:38 (113.34 km, 66.8 min) — Longest journey
5. Mar 07 13:00 → 13:19 (24.76 km, 18.8 min)
6. Mar 07 15:22 → 18:48 (336.93 km, 206.1 min) — Full day drive
7. Mar 08 07:13 → 07:25 (0.46 km, 12.1 min)

## Project Layout (v4)

```
ddpai_extractor/
├── build.sh              # Build entry point (calls src.extraction.build_database)
├── run.sh               # Run entry point (starts HTTP server on port 8000)
├── watch.sh             # Watchdog script (polls SD card for new TAR files)
├── CLAUDE.md            # This file
├── README.md            # User documentation
├── LICENSE              # MIT license
│
├── src/                 # Python package
│   ├── __init__.py
│   ├── extraction/      # GPS extraction & trip detection
│   │   ├── __init__.py
│   │   ├── build_database.py           # Main: GPS extraction + trip detection
│   │   ├── build_database_parallel.py  # Parallel variant
│   │   └── ddpai_route_improved.py     # Reference: original code
│   ├── processing/      # Trip utilities
│   │   ├── __init__.py
│   │   └── merge_trips.py              # Standalone trip merging
│   └── video/           # Video handling
│       ├── __init__.py
│       └── merge_videos.py             # FFmpeg wrapper
│
├── tools/               # Build & debug scripts
│   ├── build_parallel.sh       # Parallel build (2.5-3.5× speedup)
│   ├── debug_videos.sh         # Video debugging utility
│   └── install_fftools.sh      # FFmpeg installation helper
│
├── docs/                # Documentation
│   ├── CONTRIBUTING.md         # Contribution guidelines
│   ├── CHANGELOG.md            # Release history
│   ├── VIDEO_DEBUG_GUIDE.md    # Debugging guide
│   └── superpowers/            # Extended docs
│
├── web/                 # Web frontend
│   ├── index.html              # Dashboard: fetches data/trips.json, renders UI
│   ├── favicon.ico             # Icon
│   └── favicon.png             # Icon
│
├── data/                # Generated data (do not commit)
│   └── trips.json       # Auto-generated by ./build.sh
│
├── merged_videos/       # Generated videos (do not commit)
│   ├── 20260306134738_rear.mp4
│   ├── 20260306134738_front.mp4
│   └── ... (7 trip pairs)
│
└── working_data/        # Source data
    └── tar/             # 100 .git TAR archives (~3 GB)
```

## Migration Notes (v3)

This project was refactored from monolithic `build_dashboard.py` (single 30KB script generating 1.4 MB HTML with embedded JSON) to a **modular architecture**:

**Changes:**
- **Decoupled build**: `src/extraction/build_database.py` → generates JSON only, no HTML
- **Decoupled frontend**: `web/index.html` → static 14 KB, loads data via fetch()
- **Clean entry points**: `./build.sh` and `./run.sh` for common tasks
- **Organized code**: Python modules in `src/`, web assets in `web/`
- **Simplified data**: `data/trips.json` can be version-controlled, re-generated independently

**Benefits:**
- Smaller files (index.html 14 KB vs 1.4 MB dashboard.html)
- Faster data updates (rebuild JSON in ~2 min vs 6+ min for full HTML)
- Easier to modify UI (HTML/JS separate from Python build logic)
- Better separation of concerns (data layer vs presentation layer)
