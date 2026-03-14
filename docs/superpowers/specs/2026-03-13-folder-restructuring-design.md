# Folder Restructuring Design
**Date:** 2026-03-13
**Project:** DDpai Z50 Pro Dashcam Extractor
**Status:** Approved
**GitHub Issue:** #5

---

## Executive Summary

Atomic refactoring of the ddpai_extractor project structure to improve:
- **Developer Experience** — Clear folder organization, logical code grouping
- **Maintainability** — Remove clutter, eliminate obsolete files, organize by domain
- **Distribution Readiness** — Professional structure suitable for public sharing
- **Performance** — Better Python package structure for imports

---

## Current State Issues

1. **Root-level clutter** — 5 shell scripts at root (build.sh, run.sh, build_parallel.sh, debug_videos.sh, install_fftools.sh)
2. **Mixed assets** — Favicons at root instead of with web files
3. **Documentation scattered** — 5 markdown files at root level
4. **Obsolete backup folder** — Contains duplicate old build_database.py files
5. **Unclear utility organization** — Python modules in src/ lack domain grouping

---

## Proposed Structure

### New Layout

```
ddpai_extractor/
├── README.md                    # Keep at root
├── LICENSE                      # Keep at root
├── CLAUDE.md                    # Keep at root (project instructions)
├── .gitignore
├── build.sh                     # Keep at root (most-used entry point)
├── run.sh                       # Keep at root (most-used entry point)
│
├── tools/                       # ← NEW: All utility scripts
│   ├── build_parallel.sh        # Moved from root
│   ├── debug_videos.sh          # Moved from root
│   └── install_fftools.sh       # Moved from root
│
├── docs/                        # ← NEW: All documentation
│   ├── CONTRIBUTING.md          # Moved from root
│   ├── CHANGELOG.md             # Moved from root
│   ├── VIDEO_DEBUG_GUIDE.md     # Moved from root
│   └── superpowers/
│       └── specs/               # Design documents
│           └── 2026-03-13-folder-restructuring-design.md
│
├── src/
│   ├── __init__.py              # ← NEW: Package marker
│   │
│   ├── extraction/              # ← NEW: GPS extraction domain
│   │   ├── __init__.py
│   │   ├── build_database.py    # Moved from src/
│   │   ├── build_database_parallel.py  # Moved from src/
│   │   └── ddpai_route_improved.py     # Moved from src/ (reference)
│   │
│   ├── processing/              # ← NEW: Trip processing domain
│   │   ├── __init__.py
│   │   └── merge_trips.py       # Moved from src/
│   │
│   └── video/                   # ← NEW: Video handling domain
│       ├── __init__.py
│       └── merge_videos.py      # Moved from src/
│
├── web/
│   ├── index.html
│   ├── favicon.ico              # ← MOVED: from root
│   └── favicon.png              # ← MOVED: from root
│
├── data/                        # Generated (unchanged)
│   └── trips.json
│
├── merged_videos/               # Generated (unchanged)
│   └── ...
│
└── working_data/                # Source data (unchanged)
    └── tar/
```

### What Stays the Same
- `.git/`, `.github/`, `.gitignore` (version control)
- `data/`, `merged_videos/`, `working_data/` (data directories)
- `web/index.html` (frontend, moved favicons alongside it)
- `README.md`, `LICENSE`, `CLAUDE.md` (root-level docs)
- `build.sh`, `run.sh` (primary entry points)

### What Changes
- ✅ Scripts organized in `tools/` (5 files → 1 folder)
- ✅ Documentation centralized in `docs/` (5 files → 1 folder)
- ✅ Favicons moved to `web/`
- ✅ `src/` reorganized into 3 domains: `extraction/`, `processing/`, `video/`
- ✅ `backup/` folder **deleted** completely (content preserved in git history)
- ✅ Package structure: `__init__.py` files added for proper Python imports

---

## Implementation Details

### File Movements

**To tools/ (5 files):**
- `build_parallel.sh` (from root)
- `debug_videos.sh` (from root)
- `install_fftools.sh` (from root)
- Create placeholder `.gitkeep` if needed

**To docs/ (3 files):**
- `CONTRIBUTING.md` (from root)
- `CHANGELOG.md` (from root)
- `VIDEO_DEBUG_GUIDE.md` (from root)

**To src/extraction/ (3 files):**
- `build_database.py` (from src/)
- `build_database_parallel.py` (from src/)
- `ddpai_route_improved.py` (from src/)

**To src/processing/ (1 file):**
- `merge_trips.py` (from src/)

**To src/video/ (1 file):**
- `merge_videos.py` (from src/)

**To web/ (2 files):**
- `favicon.ico` (from root)
- `favicon.png` (from root)

**Delete (entire folder):**
- `backup/` and all contents

**Create new (package markers):**
- `src/__init__.py`
- `src/extraction/__init__.py`
- `src/processing/__init__.py`
- `src/video/__init__.py`

---

## Import Path Changes

### Python Module Imports

**Current (will break):**
```python
# In build.sh
python3 src/build_database.py

# In code
from merge_trips import ...
from merge_videos import ...
```

**After refactoring:**
```python
# In build.sh, run.sh
python3 -m src.extraction.build_database

# Within src/ code
from src.processing.merge_trips import ...
from src.video.merge_videos import ...
```

### Files Requiring Import Updates

1. **build.sh**
   - Line: `python3 src/build_database.py`
   - Change to: `python3 -m src.extraction.build_database`

2. **build_parallel.sh** (moves to tools/)
   - Line: `python3 src/build_database_parallel.py`
   - Change to: `python3 -m src.extraction.build_database_parallel`

3. **src/extraction/build_database.py**
   - Old: `from merge_trips import ...`
   - New: `from src.processing.merge_trips import ...`

4. **src/extraction/build_database_parallel.py**
   - Old: `from merge_trips import ...`
   - New: `from src.processing.merge_trips import ...`
   - Old: `from merge_videos import ...`
   - New: `from src.video.merge_videos import ...`

5. **tools/debug_videos.sh**
   - Check for any hardcoded path references
   - Update if needed

6. **tools/install_fftools.sh**
   - Check for any path references (likely minimal changes)

---

## Documentation Updates

### README.md (stays at root, update Quick Start section)

**Before:**
```markdown
## Quick Start
./build.sh
./run.sh
```

**After:**
```markdown
## Quick Start
# Primary commands
./build.sh          # Rebuild trip database
./run.sh            # Start web server

# Additional tools
./tools/build_parallel.sh      # Parallel build (faster)
./tools/debug_videos.sh        # Debug video issues
./tools/install_fftools.sh     # Install FFmpeg tools
```

### CLAUDE.md (stays at root, update architecture section)

Update "Project Layout (v3)" to "Project Layout (v4)":
```markdown
### Core Modules

**src/extraction/** (GPS extraction)
- `build_database.py`: Main entry point, NMEA parsing, trip detection
- `build_database_parallel.py`: Parallel variant for faster builds
- `ddpai_route_improved.py`: Reference implementation

**src/processing/** (Trip utilities)
- `merge_trips.py`: Merge consecutive trips

**src/video/** (Video utilities)
- `merge_videos.py`: FFmpeg wrapper for video concatenation

**tools/** (Utility scripts)
- `build_parallel.sh`: Wrapper for parallel builds
- `debug_videos.sh`: Video debugging utilities
- `install_fftools.sh`: FFmpeg setup helper

**web/** (Frontend)
- `index.html`: Dashboard (loads ../data/trips.json)
- `favicon.ico`, `favicon.png`: Branding assets
```

### Move to docs/

- **docs/CONTRIBUTING.md** (from root)
  - Update any path references
  - Update development setup instructions

- **docs/CHANGELOG.md** (from root)
  - Update any path references

- **docs/VIDEO_DEBUG_GUIDE.md** (from root)
  - Update any script path references (e.g., `debug_videos.sh` → `./tools/debug_videos.sh`)

---

## Validation & Testing

### Post-Refactoring Verification

1. **Folder structure correct:**
   ```bash
   ls -R . | grep -E "^\./(src|tools|docs|web)"
   # Verify all folders exist with correct files
   ```

2. **All scripts executable:**
   ```bash
   ls -l build.sh run.sh tools/*.sh
   # Verify execution permissions
   ```

3. **Python package structure valid:**
   ```bash
   python3 -c "import src.extraction.build_database; print('Import OK')"
   python3 -c "import src.processing.merge_trips; print('Import OK')"
   python3 -c "import src.video.merge_videos; print('Import OK')"
   ```

4. **build.sh runs successfully:**
   ```bash
   ./build.sh
   # Should generate data/trips.json without errors
   ```

5. **run.sh works:**
   ```bash
   ./run.sh &
   sleep 2
   curl http://localhost:8000/web/index.html
   # Should return HTML content
   kill %1
   ```

6. **Git cleanup:**
   ```bash
   git status
   # Should show: "nothing to commit" (all tracked/moved)
   git log --oneline -5
   # Should show: one atomic commit with all changes
   ```

---

## Rollback Plan

If issues arise during implementation:
1. All changes are in a single atomic git commit
2. Revert with: `git revert <commit-hash>`
3. Original files preserved in git history
4. No data loss (data/, merged_videos/ unchanged)

---

## Benefits

| Aspect | Benefit |
|--------|---------|
| **Developer Experience** | Clear folder hierarchy, easy to find code/docs/scripts |
| **Maintainability** | Domain-organized code, reduced root clutter, obvious structure |
| **Scalability** | Easy to add more modules in future (src/ml/, src/api/) |
| **Distribution** | Professional structure suitable for PyPI/GitHub public release |
| **Import Clarity** | Explicit package imports (`from src.extraction import ...`) |
| **Documentation** | Centralized, easier to maintain and extend |

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Import paths break | Low | Test each module after move; validate in build.sh |
| Script paths fail | Low | Update all path references; test each script |
| Relative imports in Python | Low | Use absolute imports (`from src.X import ...`) |
| Git history lost | None | Only moving files, no deletions (git tracks moves) |
| Data loss | None | data/, merged_videos/, working_data/ unchanged |

---

## Timeline

- **Execution:** Single atomic commit (all changes at once)
- **Estimated execution time:** ~30 minutes
- **Testing:** ~10 minutes

---

## Success Criteria

✅ All files moved to correct locations
✅ All `__init__.py` files created
✅ All import paths updated and working
✅ All scripts execute without errors
✅ `./build.sh` runs and generates data/trips.json
✅ `./run.sh` starts HTTP server
✅ Git status clean, single atomic commit
✅ Documentation updated with new paths
✅ GitHub issue #5 updated with completion status

---

**Approval Date:** 2026-03-13
**Reviewer:** User
**Status:** ✅ APPROVED FOR IMPLEMENTATION
