# DDpai Z50 Pro Dashcam Extractor

Extract GPS data and merge dashcam videos from a DDpai Z50 Pro dashboard camera. Automatically detects trips, validates data, and generates an interactive web dashboard with maps and real-time charts.

## Features

- **GPS Extraction** — Parse NMEA sentences ($GPRMC, $GPGGA) from TAR archives
- **Trip Detection** — Automatically group consecutive recordings by 30-minute gap threshold
- **Trip Validation** — Check speed > 0 km/h, altitude coverage, and matching video counts
- **Video Merging** — Concatenate rear/front videos with H.264 720p re-encoding (70% size reduction)
- **Interactive Dashboard** — Web UI with Leaflet.js maps, Chart.js speed/altitude graphs, and linked video players
- **Parallel Build** — Optional 2.5–3.5× speedup for long archives

## Requirements

- **Python** 3.6 or later (standard library only: `tarfile`, `json`, `subprocess`, `datetime`, `pathlib`, `collections`, `math`)
- **FFmpeg** with libx264 support:
  ```bash
  # Verify FFmpeg installation
  ffmpeg -codecs | grep h264
  ```
- **Modern browser** (Leaflet.js, Chart.js, HTML5 video)
- **~15 GB disk space** for merged videos + source files

## Quick Start

```bash
git clone https://github.com/fabianobr/ddpai-extractor.git
cd ddpai-extractor

# Build trip database (extracts GPS, detects trips, merges videos)
./build.sh

# Start web server on localhost:8000
./run.sh

# Open browser to http://localhost:8000/web/
```

## Configuration

### Video Paths
Edit `src/extraction/build_database.py` lines 18–20 to point to your dashcam directories:
```python
REAR_VIDEO_DIR = '/path/to/your/rear/videos/'
FRONT_VIDEO_DIR = '/path/to/your/front/videos/'
TAR_ARCHIVE_DIR = '/path/to/your/tar/archives/'
```

### Trip Detection
Modify `GAP_THRESHOLD` in `src/extraction/build_database.py` (line 24, default: 1800 seconds = 30 minutes):
```python
GAP_THRESHOLD = 30 * 60  # seconds between files to split trips
```

### Video Encoding
Tune quality/speed tradeoffs in `src/extraction/build_database.py` lines 51–53:
```python
OUTPUT_HEIGHT = 720        # Target resolution (default 720p)
VIDEO_CRF = 26            # Quality: 18-22 (high), 26 (default), 28+ (compressed)
VIDEO_PRESET = 'fast'     # Speed: ultrafast, fast, medium, slow
```

See [CLAUDE.md](CLAUDE.md) for detailed encoding guide.

## Architecture

```
.git TAR files (working_data/tar/)
  ↓ [parse_tar_filename]
Auto-detect trip groups (30-min gap)
  ↓ [extract_gps_from_tar]
Extract GPS from NMEA (.gpx in TAR)
  ↓ [merge_gps_points]
Merge RMC (speed/heading) + GGA (altitude)
  ↓ [validate_group]
Validate: speed > 0, altitude, video counts
  ↓ [merge_videos_ffmpeg]
Merge rear/front videos (H.264 720p)
  ↓ [Write data/trips.json]
JSON database (GPS points, stats, video paths)
  ↓ [web/index.html]
Browser: Leaflet map, Chart.js graphs, video players
```

## Data Structure

**Input:** TAR archives containing GPX NMEA sentence logs
**Processing:** Python extraction + trip grouping + FFmpeg video merging
**Output:** `data/trips.json` (static JSON) + `merged_videos/*.mp4`
**Frontend:** `web/index.html` (14 KB) fetches JSON via async fetch()

### GPS Points Format (in JSON)
```json
{
  "id": "20260306134738",
  "label": "Mar 06 13:47 → 14:04",
  "distance_km": 29.66,
  "duration_min": 16.8,
  "max_speed": 85.2,
  "avg_speed": 105.7,
  "points": [
    [lat, lon, speed_kmh, altitude_m, heading_degrees],
    ...
  ]
}
```

## Development

### Rebuild Database
```bash
./build.sh
# Regenerates data/trips.json from TAR archives (2–3 min)
```

### Parallel Build (Optional)
For faster processing on multi-core systems:
```bash
./tools/build_parallel.sh
# Same output as ./build.sh but ~2.5–3.5× faster
```

### Serve Dashboard
```bash
./run.sh
# Starts HTTP server on localhost:8000 (requires for JSON fetch)
```

### Additional Tools
```bash
./tools/debug_videos.sh       # Debug video file status and encoding
./tools/install_fftools.sh    # Install or verify FFmpeg dependencies
```

### Verify Video Encoding
```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height \
  -of csv=p=0 merged_videos/*_rear.mp4
```

## Troubleshooting

### FFmpeg: "libx264 not found"
Install FFmpeg with libx264:
```bash
# macOS
brew install ffmpeg

# Linux (Ubuntu/Debian)
sudo apt-get install ffmpeg

# Windows
choco install ffmpeg
```

### "Heatmap not loading" / "Map tiles appear blank"
Web UI requires HTTP serving (not `file://` URLs). Use `./run.sh` to start the server.

### TAR Parsing Errors
The project gracefully ignores corrupted TAR files and bad NMEA checksums. Check build output for warnings.

### Video Playback Issues
- Verify video paths in `src/extraction/build_database.py` lines 18–20 exist
- Check browser DevTools Console for path errors
- Ensure dashcam videos are in H.264/MP4 format

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for branching conventions, commit style, and release process.

## License

MIT License © 2026 Fabiano Silva. See [LICENSE](LICENSE) for details.

## Acknowledgments

- NMEA parsing for GPS data extraction
- FFmpeg for video concatenation
- [Leaflet.js](https://leafletjs.com/) for interactive maps
- [Chart.js](https://www.chartjs.org/) for speed/altitude visualization
