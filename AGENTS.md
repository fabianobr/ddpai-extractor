# Repository Guidelines

## Project Structure & Module Organization

`src/extraction/` contains NMEA/GPS parsing, trip grouping, and database builders;
`src/video/` and `src/processing/` hold video merge and trip-processing helpers.
The browser dashboard is the static `web/index.html`. Put Python tests in `tests/`
using the `test_*.py` convention. Shell utilities live in `tools/`; `build.sh` and
`run.sh` are the primary entry points. Keep personal camera inputs and generated
media under ignored paths such as `working_data/`, `merged_videos/`, `data/`, and
`extracted_photos/`.

## Build, Test, and Development Commands

```bash
python3 -m unittest discover -s tests -v  # Run the Python test suite
./build.sh                                # Build data/trips.json from camera inputs
./tools/build_parallel.sh                 # Parallel database build
./run.sh                                  # Serve dashboard at http://localhost:8000/web/
./tools/extract_photos.sh                 # Copy prepared DDpai JPEGs locally
```

`build.sh` defaults to `working_data/{tar,videos/rear,videos/front}`. It requires
Python 3.6+ and FFmpeg with `libx264`; no Python packages need installation. Run
`./tools/extract_photos.sh … --dry-run` before a large photo export.

## Coding Style & Naming Conventions

Use four spaces for Python indentation, `snake_case` for functions and variables,
and `UPPER_SNAKE_CASE` for module constants. Keep functions narrow and use
standard-library modules unless a dependency is justified. Write executable Bash
with `#!/usr/bin/env bash`, quote paths, and validate inputs. Preserve the existing
JSON schema consumed by `web/index.html`; changing it requires matching frontend
updates. There is no configured formatter or linter, so follow the surrounding
code and run relevant tests.

## Testing Guidelines

Write or update a focused `unittest` test before implementation. Name test classes
and methods descriptively, e.g. `TestValidateVideoDuration.test_validate_missing_video`.
Mock FFmpeg for unit cases; retain a small real-media integration test only where
it adds value. For dashboard-impacting work, rebuild data, run `./run.sh`, and
check the map, charts, and video controls in a browser.

## Commit & Pull Request Guidelines

Follow Git Flow: branch from `develop` using `feature/*`, `fix/*`, `docs/*`, or
`refactor/*`; never commit directly to `main` or `develop`. Use Conventional
Commits, such as `fix(video): correct merge timeout`. Keep each PR focused, explain
the user-visible effect and validation, link the project/issue when applicable,
request review, and merge only through GitHub after checks and approval. Do not
force-push shared branches or commit local media paths/data.
