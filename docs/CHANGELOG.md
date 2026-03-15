# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
