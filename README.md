# DDpai Z50 Pro Dashcam Extractor

Extract GPS data and merge dashcam videos from a DDpai Z50 Pro dashboard camera. Automatically detects trips, validates data, and generates an interactive trip detail screen with a map, a metro-line timeline and linked dashcam videos.

## Features

- **GPS Extraction** — Parse NMEA sentences ($GPRMC, $GPGGA) from TAR archives
- **Trip Detection** — Automatically group consecutive recordings by 30-minute gap threshold
- **Trip Validation** — Check speed > 0 km/h, altitude coverage, and matching video counts
- **Video Merging** — Concatenate rear/front videos using stream copy, with H.264 re-encoding as a fallback
- **Interactive Dashboard** — Trip detail screen ("Estúdio de viagem") with Leaflet.js map, chapters, an SVG metro-line timeline for speed/altitude, single transport controls and linked front/rear video
- **Parallel Build** — Optional 2.5–3.5× speedup for long archives

## Requirements

- **Python** 3.6 or later (standard library only: `tarfile`, `json`, `subprocess`, `datetime`, `pathlib`, `collections`, `math`)
- **FFmpeg** with libx264 support:
  ```bash
  # Verify FFmpeg installation
  ffmpeg -codecs | grep h264
  ```
- **Modern browser** (Leaflet.js, inline SVG, HTML5 video)
- **~15 GB disk space** for merged videos + source files

## Quick Start

### Importar viagens do disco DDPAI

Conecte o disco e execute `python3 -m src.processing.trip_import`. O programa
procura o disco, mostra as viagens de ontem no horário local e permite escolher
uma, várias ou todas. Em seguida, gera o índice e os vídeos dianteiro e traseiro
em `data/trips.json` e `merged_videos/`. Antes de substituir o índice anterior,
salva uma cópia em `working_data/backups/`.

Para outra data ou para processar todas sem perguntar:

```bash
python3 -m src.processing.trip_import --data 2026-11-21 --todas
python3 -m src.processing.trip_import --disco /caminho/do/disco
```

Viagens que atravessam a meia-noite são incluídas inteiras. A detecção usa GPS
e descarta arquivos classificados como parados ou sem dados GPS. Depois, abra
o painel com `./run.sh` e acesse http://localhost:8765/web/.

Se a porta 8765 estiver ocupada, use outra, por exemplo `./run.sh 8766`, e
acesse http://localhost:8766/web/. O servidor aceita requisições parciais,
necessárias para avançar nos vídeos. Os vídeos unidos preservam o codec original
quando possível; a reprodução de HEVC depende do navegador e do sistema.

```bash
git clone https://github.com/fabianobr/ddpai-extractor.git
cd ddpai-extractor

# Build trip database (extracts GPS, detects trips, merges videos)
./build.sh

# Start web server on localhost:8765
./run.sh

# Open browser to http://localhost:8765/web/
```

## Configuration

### Input Paths
`./build.sh` takes the directories as positional arguments (defaults: `working_data/tar`, `working_data/videos/rear`, `working_data/videos/front`, output `.`):
```bash
./build.sh /path/to/tar /path/to/rear /path/to/front [OUTPUT_DIR]
```
The `DEFAULT_*` constants in `src/extraction/build_database.py` are only used when the module is run directly without arguments, so prefer `build.sh` (or `trip_import`).

### Trip Detection
Modify `GAP_THRESHOLD` in `src/extraction/build_database.py` (default: 1800 seconds = 30 minutes):
```python
GAP_THRESHOLD = 30 * 60  # seconds between files to split trips
```

### Video Encoding
Tune the quality/speed of the libx264 fallback (stream copy, the default, ignores these) in `src/extraction/build_database.py` (near the top of the file):
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
Merge rear/front videos (stream copy or H.264 fallback)
  ↓ [Write data/trips.json]
JSON database (GPS points, stats, video paths)
  ↓ [web/index.html]
Browser: Leaflet map, SVG timeline, video players
```

## Video-GPS Synchronization

### Features
- **Bidirectional sync:** Play/scrub video → map updates | Click map → video seeks
- **Switchable modes:** lock button "Câmeras juntas" (both videos together) or "Câmeras separadas" (only the main camera follows the map/timeline); one main camera, the other as picture-in-picture or side by side
- **Gap handling:** Cameras without footage for a GPS point show a "Sem gravação…" note and a "Sem vídeo" chapter; the map stays interactive
- **Real-time visualization:** See playback position on map with time indicator

### Usage
1. Open dashboard: `./run.sh` → http://localhost:8765/web/
2. Select a trip with video
3. Use the sync padlock in the timeline bar: "Câmeras juntas" (locked) or "Câmeras separadas" (unlocked)
4. Play video to see map follow playback
5. Click map to jump video to that GPS point

### Estúdio de viagem

A tela de detalhe abre a viagem de `#viagem-<id>` (ou a mais recente). Os capítulos ficam em lista, a linha do
tempo SVG mostra velocidade e altitude com o trecho selecionável, e o botão "Trocar" alterna a câmera principal.

Atalhos de teclado (ignorados quando o foco está em campo de texto):

| Tecla | Ação |
|---|---|
| Espaço / K | Reproduzir / pausar |
| ← / → | Voltar / avançar 10 s |
| Shift + ← / → | Voltar / avançar 60 s |
| J / L | Voltar / avançar 10 s |
| I / O | Marcar início / fim do trecho |
| M | Ampliar o mapa (troca mapa e vídeo de lugar) |
| C | Trocar a câmera principal |
| Esc | Fechar popovers |

### Video Duration Validation
During build, the system:
- Extracts actual video duration using ffprobe
- Compares with GPS duration
- Logs mismatches (video shorter/longer than GPS)
- Trusts GPS data as source of truth

If `video_duration_status = "video_shorter"`:
- Yellow badge appears showing when video ended
- Map remains clickable for GPS points beyond video end
- Video freezes at last frame

### Architecture
- **Backend:** ffprobe extracts duration, build process validates and adds to JSON
- **Frontend:** Event listeners sync video ↔ map; linear interpolation maps time to GPS index
- **Data:** JSON schema includes `video_duration_s`, `start_timestamp`, `sparse_timestamps`

### Per-camera mapping (`video_sync`)
Each trip carries `video_sync` with one vector per camera (`rear`, `front`): for each GPS point, the second
inside the merged video, or `null` when that camera has no footage for the point. The frontend uses these
vectors instead of linear interpolation; trips without `video_sync` (older JSON) fall back to the old behaviour.

- **Clock offset:** the GPS (UTC) and the camera clock differ (about 10 752 s in the Nov/2026 import). It is
  estimated as the **median** of the per-segment offsets (first GPS fix of each file minus the file-name time).
  This is an estimate, not a guarantee of absolute accuracy; resolution is limited to about 1 s by file names.
- **Confidence:** `video_sync` also stores `offset_samples`, `offset_spread_s`, `offset_typical_spread_s`,
  `offset_outlier_segments` and `confidence` (`high` / `medium` / `low`). `medium` and `low` show a warning in
  the dashboard. The classification uses the typical spread (it ignores the worst 5 % of segments, set by
  `OUTLIER_FRACTION` in `src/extraction/video_timeline.py`); set it to 0 for the strict max-deviation rule.
  Confidence describes the clock calibration only, not footage coverage (see `status`: `ok` / `partial`).
- **Stale GPS residue:** some `.gpx` files (the last short file of a recording) end with old fixes left in the
  camera buffer. `extract_gps_from_nmea` stops at the first fix whose full date+time goes backwards or jumps
  forward more than 120 s. Consequence: those fixes no longer count as driving, so a few `.git` files can be
  classified as parked; `tools/refresh_video_sync.py` keeps the trip composition that was already imported and
  merged, but a fresh import would leave them out. Point indices change when residue is removed, so ranges
  selected or exported before a refresh no longer apply.
- **GPX/KML export:** exports the geometry of the selected points only (no timestamps or elevation); it is not
  a guaranteed navigable route in mapping apps.
- **Refreshing without re-merging video:** `python3 tools/refresh_video_sync.py --disco <mount> [--dry-run]`
  recomputes points and `video_sync` for the trips already imported; it backs up `data/trips.json` first and does
  not touch `merged_videos/`.

### Testing
- Unit tests: `python3 -m unittest discover -s tests -v`
- Unit tests (legacy): `pytest tests/test_video_sync_build.py`
- Manual testing: Follow guide in `tests/test_video_sync_frontend_manual.md`

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
# Starts HTTP server on localhost:8765 (requires for JSON fetch)
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
- Verify the video directories passed to `./build.sh` exist and that `data/trips.json` references `merged_videos/*.mp4` files that exist
- Check browser DevTools Console for path errors
- Ensure dashcam videos are in H.264/MP4 format

## Contributing

**Before submitting any changes, read the [CONTRIBUTING.md](docs/CONTRIBUTING.md) guide carefully.**

### 🔴 MUST DO Requirements

**ALL contributions MUST follow these rules:**

1. ✅ **Create a feature branch** from `develop` (never commit to main directly)
2. ✅ **Write tests FIRST** (Test-Driven Development) before implementing features
3. ✅ **Create a Pull Request** on GitHub (never merge directly)
4. ✅ **Get code review approval** before merging
5. ✅ **Merge via GitHub UI** (use squash/rebase to keep history clean)
6. ✅ **Sync develop with main** after releasing to main
7. ✅ **Follow Conventional Commits** for clear commit messages

**See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for detailed workflow, branching conventions, and commit style.**

## License

MIT License © 2026 Fabiano Silva. See [LICENSE](LICENSE) for details.

## Acknowledgments

- NMEA parsing for GPS data extraction
- FFmpeg for video concatenation
- [Leaflet.js](https://leafletjs.com/) for interactive maps
- [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors for map tiles
