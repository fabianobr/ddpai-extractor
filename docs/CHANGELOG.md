# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Estúdio de viagem redesign**: the trip detail screen has chapters, a Leaflet map, an SVG metro-line timeline
  for speed and altitude, a single transport bar with real clock, light/dark theme and keyboard shortcuts
- **Chart.js removed**: the speed/altitude charts are inline SVG
- **Map tiles**: OpenStreetMap with a per-theme CSS filter (CARTO dropped, it now requires an API key)

### Added
- `web/trip-model.js`: pure trip helpers, tested by `tests/test_trip_model.py`
- `tools/cdp-shot.js`: exact-viewport PNG screenshots through headless Chrome

## [0.5.0] - 2026-11-22

### Added
- **Estúdio de viagem dashboard**: wide map, rear/front cameras side by side and a shared timeline,
  with clickable speed/altitude charts and optional map follow mode
- **Per-camera video/GPS sync (`video_sync`)**: each GPS point maps to the real second of each camera's
  merged video, or `null` where a camera has no footage; the dashboard warns about missing coverage
- **Clock calibration confidence**: `offset_samples`, `offset_spread_s`, `offset_typical_spread_s`,
  `offset_outlier_segments` and `confidence` (`high`/`medium`/`low`) in `video_sync`, with a dashboard warning
  for `medium` and `low`
- **Trip importer** (`python3 -m src.processing.trip_import`): detects the mounted DDPAI disk, lists trips by
  local day and imports one, several or all; new trips are merged into the existing index
- **`tools/refresh_video_sync.py`**: recomputes points and `video_sync` for already imported trips without
  re-merging videos (backs up and replaces `data/trips.json` atomically, preserving its permissions)
- **HTTP server with Range support** (`src.processing.http_server`, port 8765) so large videos can be seeked
- **Route selection and export**: pick a start/end on the timeline and export the geometry as GPX or KML
  (not a guaranteed navigable route)
- Selected route coordinates shown in degrees/minutes/seconds (DMS)
- **`tools/extract_photos.sh`**: copies the camera's JPEGs to a local folder (`--dry-run`, `--include-tmp`)
- Accessibility and responsive layout: keyboard-operable trip list, focus outlines, ARIA labels and live
  regions, cameras stay side by side down to ~700px

### Changed
- `./run.sh` now serves the dashboard on port 8765 (was 8000) through `src.processing.http_server`
- Trip dates and labels use the NMEA RMC date and the local time zone instead of assuming UTC
- CI runner pinned to `ubuntu-24.04` so Python 3.9 stays available

### Fixed
- Stale GPS fixes left in the camera buffer at the end of some `.gpx` files are dropped (a fix whose full
  date+time goes backwards, or jumps forward more than 120 s); boundary points map by the video window that
  contains them instead of only by `camera_segment`
- Unreadable or truncated TAR archives are reported with their path instead of being silently treated as parked
- A trip with only one camera is no longer reported as `partial`
- Linked playback: one camera reaching its natural end no longer pauses the other, and a user scrub is no
  longer snapped to a GPS sample time
- Range server ignores malformed Range headers (serves the full file) and silences client aborts
- `.gitignore` rule for `*.git` TAR archives was disabled by an inline comment

### Known limitations
- The clock offset is a per-trip median estimate with ~1 s resolution (file names), not absolute accuracy
- With stale GPS fixes removed, some `.git` files are classified as parked; a fresh import excludes them from
  the trip, while `refresh_video_sync.py` keeps the composition already imported
- Point indices change when stale fixes are removed, so ranges selected or exported before a refresh no
  longer apply
- GPX export carries no timestamps or elevation

## [0.2.2] - 2026-03-15

### Added
- **watch.sh**: Polling watchdog for real-time SD card monitoring
- Auto-detection of new dashcam TAR archives on SD card (30-second poll interval)
- Automatic build triggering when new recordings detected
- Support for both sequential and parallel builds via `--parallel` flag
- Pre-build backup of `data/trips.json` for safety
- macOS Notification Center alerts on build completion and failure
- State tracking via `data/.last_tar_count` (gitignored)

## [0.1.0] - 2026-03-12

### Added
- GPS extraction from NMEA sentences ($GPRMC, $GPGGA) in .git TAR archives
- Automatic trip group detection (30-minute gap threshold)
- Trip validation (speed > 0 km/h, altitude coverage, matching video counts)
- FFmpeg video merging with H.264 720p re-encoding (CRF 26, ~70% size reduction)
- Parallel build variant (`build_parallel.sh`) for 2.5–3.5× speedup
- Interactive web dashboard (Leaflet.js maps, Chart.js speed/altitude charts)
- Rear + front video players linked to trip GPS data
- Configurable encoding parameters (resolution, quality, preset speed)
- Distance calculation using Haversine formula
- NMEA checksum validation with graceful error handling
- JSON-based trip database with automatic regeneration
