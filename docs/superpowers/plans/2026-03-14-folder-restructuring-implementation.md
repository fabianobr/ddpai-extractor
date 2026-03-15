# Folder Restructuring Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Atomically reorganize the ddpai_extractor project structure to improve maintainability, developer experience, and distribution readiness.

**Architecture:** Single atomic git commit moving files into domain-organized folders (src/extraction/, src/processing/, src/video/), centralizing scripts (tools/) and docs (docs/), and updating all import paths. No functionality changes—pure reorganization with validation.

**Tech Stack:** Bash (file operations), Python 3 (import validation), git (atomic commit)

---

## Execution Checklist

This plan is organized into chunks. **Execute in order** (each chunk depends on previous):

- [ ] Chunk 1: Create directory structure & package markers
- [ ] Chunk 2: Move Python modules (src/extraction, src/processing, src/video)
- [ ] Chunk 3: Move scripts to tools/
- [ ] Chunk 4: Move docs to docs/
- [ ] Chunk 5: Move assets (favicons) to web/
- [ ] Chunk 6: Delete backup/ folder
- [ ] Chunk 7: Update import paths in moved files
- [ ] Chunk 8: Update shell scripts (build.sh, build_parallel.sh, etc.)
- [ ] Chunk 9: Update documentation (README.md, CLAUDE.md)
- [ ] Chunk 10: Validation & atomic commit

---

# Chunk 1: Create Directory Structure & Package Markers

**Files Created:**
- `src/__init__.py` (empty package marker)
- `src/extraction/__init__.py` (empty package marker)
- `src/processing/__init__.py` (empty package marker)
- `src/video/__init__.py` (empty package marker)
- `tools/` (directory)
- `docs/superpowers/specs/` (directory, already exists from design doc)

**Precondition:** On `main` branch, clean working tree

---

### Task 1: Create tools/ directory

- [ ] **Step 1: Create tools/ directory**

```bash
mkdir -p tools
```

- [ ] **Step 2: Verify directory created**

```bash
ls -ld tools
# Expected output: drwxr-xr-x ... tools
```

---

### Task 2: Create src/extraction/ directory

- [ ] **Step 1: Create src/extraction/ directory**

```bash
mkdir -p src/extraction
```

- [ ] **Step 2: Verify directory created**

```bash
ls -ld src/extraction
# Expected output: drwxr-xr-x ... src/extraction
```

---

### Task 3: Create src/processing/ directory

- [ ] **Step 1: Create src/processing/ directory**

```bash
mkdir -p src/processing
```

- [ ] **Step 2: Verify directory created**

```bash
ls -ld src/processing
# Expected output: drwxr-xr-x ... src/processing
```

---

### Task 4: Create src/video/ directory

- [ ] **Step 1: Create src/video/ directory**

```bash
mkdir -p src/video
```

- [ ] **Step 2: Verify directory created**

```bash
ls -ld src/video
# Expected output: drwxr-xr-x ... src/video
```

---

### Task 5: Create package marker files

- [ ] **Step 1: Create src/__init__.py**

```bash
touch src/__init__.py
```

- [ ] **Step 2: Create src/extraction/__init__.py**

```bash
touch src/extraction/__init__.py
```

- [ ] **Step 3: Create src/processing/__init__.py**

```bash
touch src/processing/__init__.py
```

- [ ] **Step 4: Create src/video/__init__.py**

```bash
touch src/video/__init__.py
```

- [ ] **Step 5: Verify all __init__.py files exist**

```bash
ls -1 src/__init__.py src/extraction/__init__.py src/processing/__init__.py src/video/__init__.py
# Expected output: all 4 files listed
```

---

### Task 6: Verify Chunk 1 complete

- [ ] **Step 1: Verify directory structure**

```bash
tree -L 2 src/
# Expected output:
# src/
# ├── __init__.py
# ├── extraction/
# │   └── __init__.py
# ├── processing/
# │   └── __init__.py
# └── video/
#     └── __init__.py
```

- [ ] **Step 2: Check git status (no commits yet)**

```bash
git status
# Expected: all new files as untracked
```

---

# Chunk 2: Move Python Modules

**Files Moved:**
- `src/build_database.py` → `src/extraction/build_database.py`
- `src/build_database_parallel.py` → `src/extraction/build_database_parallel.py`
- `src/ddpai_route_improved.py` → `src/extraction/ddpai_route_improved.py`
- `src/merge_trips.py` → `src/processing/merge_trips.py`
- `src/merge_videos.py` → `src/video/merge_videos.py`

---

### Task 1: Move extraction modules

- [ ] **Step 1: Move build_database.py to extraction/**

```bash
mv src/build_database.py src/extraction/build_database.py
```

- [ ] **Step 2: Move build_database_parallel.py to extraction/**

```bash
mv src/build_database_parallel.py src/extraction/build_database_parallel.py
```

- [ ] **Step 3: Move ddpai_route_improved.py to extraction/**

```bash
mv src/ddpai_route_improved.py src/extraction/ddpai_route_improved.py
```

- [ ] **Step 4: Verify extraction/ has 3 files**

```bash
ls -1 src/extraction/*.py
# Expected output: 3 files (build_database.py, build_database_parallel.py, ddpai_route_improved.py)
```

---

### Task 2: Move processing modules

- [ ] **Step 1: Move merge_trips.py to processing/**

```bash
mv src/merge_trips.py src/processing/merge_trips.py
```

- [ ] **Step 2: Verify processing/ has 1 file**

```bash
ls -1 src/processing/*.py
# Expected output: 1 file (merge_trips.py)
```

---

### Task 3: Move video modules

- [ ] **Step 1: Move merge_videos.py to video/**

```bash
mv src/merge_videos.py src/video/merge_videos.py
```

- [ ] **Step 2: Verify video/ has 1 file**

```bash
ls -1 src/video/*.py
# Expected output: 1 file (merge_videos.py)
```

---

### Task 4: Verify src/ is clean

- [ ] **Step 1: Verify only __init__.py files remain in src/ root**

```bash
ls src/*.py
# Expected output: -rw-r--r--  ... src/__init__.py (no other .py files in src/)
```

- [ ] **Step 2: Verify no subdirectories left behind**

```bash
ls -d src/*/
# Expected output: extraction/ processing/ video/
```

---

# Chunk 3: Move Scripts to tools/

**Files Moved:**
- `build_parallel.sh` → `tools/build_parallel.sh`
- `debug_videos.sh` → `tools/debug_videos.sh`
- `install_fftools.sh` → `tools/install_fftools.sh`

---

### Task 1: Move shell scripts

- [ ] **Step 1: Move build_parallel.sh**

```bash
mv build_parallel.sh tools/build_parallel.sh
```

- [ ] **Step 2: Move debug_videos.sh**

```bash
mv debug_videos.sh tools/debug_videos.sh
```

- [ ] **Step 3: Move install_fftools.sh**

```bash
mv install_fftools.sh tools/install_fftools.sh
```

- [ ] **Step 4: Verify tools/ has 3 shell scripts**

```bash
ls -1 tools/*.sh
# Expected output: 3 files (build_parallel.sh, debug_videos.sh, install_fftools.sh)
```

---

### Task 2: Verify permissions preserved

- [ ] **Step 1: Check all scripts are executable**

```bash
ls -l tools/*.sh
# Expected: all have -rwxr-xr-x permissions
```

---

# Chunk 4: Move Documentation to docs/

**Files Moved:**
- `CONTRIBUTING.md` → `docs/CONTRIBUTING.md`
- `CHANGELOG.md` → `docs/CHANGELOG.md`
- `VIDEO_DEBUG_GUIDE.md` → `docs/VIDEO_DEBUG_GUIDE.md`

---

### Task 1: Move documentation files

- [ ] **Step 1: Move CONTRIBUTING.md**

```bash
mv CONTRIBUTING.md docs/CONTRIBUTING.md
```

- [ ] **Step 2: Move CHANGELOG.md**

```bash
mv CHANGELOG.md docs/CHANGELOG.md
```

- [ ] **Step 3: Move VIDEO_DEBUG_GUIDE.md**

```bash
mv VIDEO_DEBUG_GUIDE.md docs/VIDEO_DEBUG_GUIDE.md
```

- [ ] **Step 4: Verify docs/ has 3 markdown files**

```bash
ls -1 docs/*.md
# Expected output: 3 files (CONTRIBUTING.md, CHANGELOG.md, VIDEO_DEBUG_GUIDE.md)
# Note: 2026-03-13-folder-restructuring-design.md should also be there (from earlier commit)
```

---

# Chunk 5: Move Assets (Favicons) to web/

**Files Moved:**
- `favicon.ico` → `web/favicon.ico`
- `favicon.png` → `web/favicon.png`

---

### Task 1: Move favicon files

- [ ] **Step 1: Move favicon.ico**

```bash
mv favicon.ico web/favicon.ico
```

- [ ] **Step 2: Move favicon.png**

```bash
mv favicon.png web/favicon.png
```

- [ ] **Step 3: Verify web/ has 3 files**

```bash
ls -1 web/
# Expected output: favicon.ico, favicon.png, index.html
```

---

# Chunk 6: Delete backup/ Folder

**Files Deleted:**
- `backup/` (entire directory)

---

### Task 1: Delete backup folder

- [ ] **Step 1: Remove backup/ directory**

```bash
rm -rf backup/
```

- [ ] **Step 2: Verify backup/ is gone**

```bash
ls backup/ 2>&1
# Expected: "cannot access 'backup/': No such file or directory"
```

---

# Chunk 7: Update Import Paths in Moved Files

**Files Modified:**
- `src/extraction/build_database.py`
- `src/extraction/build_database_parallel.py`
- (Check if merge_trips.py and merge_videos.py have relative imports)

---

### Task 1: Update imports in build_database.py

- [ ] **Step 1: Read current file to identify imports**

```bash
grep -n "^from merge_\|^import merge_" src/extraction/build_database.py
# Expected: lines showing imports of merge_trips and/or merge_videos
```

- [ ] **Step 2: Update imports in build_database.py**

If the file has lines like:
```python
from merge_trips import ...
from merge_videos import ...
```

Change them to:
```python
from src.processing.merge_trips import ...
from src.video.merge_videos import ...
```

**Exact edit:** Use Read tool to view current file, identify exact import lines, then use Edit tool to update them.

- [ ] **Step 3: Verify imports are updated**

```bash
grep -n "^from src\." src/extraction/build_database.py
# Expected: lines showing updated imports
```

---

### Task 2: Update imports in build_database_parallel.py

- [ ] **Step 1: Read current file to identify imports**

```bash
grep -n "^from merge_\|^import merge_" src/extraction/build_database_parallel.py
# Expected: lines showing imports
```

- [ ] **Step 2: Update imports in build_database_parallel.py**

Same as build_database.py:
```python
from src.processing.merge_trips import ...
from src.video.merge_videos import ...
```

- [ ] **Step 3: Verify imports are updated**

```bash
grep -n "^from src\." src/extraction/build_database_parallel.py
# Expected: lines showing updated imports
```

---

### Task 3: Check merge_trips.py and merge_videos.py for internal imports

- [ ] **Step 1: Check merge_trips.py for imports**

```bash
grep -n "^from \|^import " src/processing/merge_trips.py
# Expected: list any internal imports (likely none or standard library)
```

- [ ] **Step 2: Check merge_videos.py for imports**

```bash
grep -n "^from \|^import " src/video/merge_videos.py
# Expected: list any internal imports (likely none or standard library)
```

- [ ] **Step 3: Update if needed**

If either file imports from each other or from build_database, update to use `src.` prefixed paths.

---

# Chunk 8: Update Shell Scripts

**Files Modified:**
- `build.sh`
- `tools/build_parallel.sh`
- `tools/debug_videos.sh` (if it has Python imports)
- `tools/install_fftools.sh` (if it has path references)

---

### Task 1: Update build.sh

- [ ] **Step 1: Read build.sh to see current command**

```bash
cat build.sh
# Expected: contains "python3 src/build_database.py"
```

- [ ] **Step 2: Update build.sh to use module import**

Change from:
```bash
python3 src/build_database.py
```

To:
```bash
python3 -m src.extraction.build_database
```

**Use Edit tool to make this change.**

- [ ] **Step 3: Verify change**

```bash
grep "python3" build.sh
# Expected: line showing "python3 -m src.extraction.build_database"
```

---

### Task 2: Update tools/build_parallel.sh

- [ ] **Step 1: Read tools/build_parallel.sh**

```bash
cat tools/build_parallel.sh
# Expected: contains "python3 src/build_database_parallel.py"
```

- [ ] **Step 2: Update to use module import**

Change from:
```bash
python3 src/build_database_parallel.py
```

To:
```bash
python3 -m src.extraction.build_database_parallel
```

**Use Edit tool to make this change.**

- [ ] **Step 3: Verify change**

```bash
grep "python3" tools/build_parallel.sh
# Expected: line showing "python3 -m src.extraction.build_database_parallel"
```

---

### Task 3: Check tools/debug_videos.sh for updates

- [ ] **Step 1: Read tools/debug_videos.sh**

```bash
cat tools/debug_videos.sh
# Check for any Python calls or hardcoded paths
```

- [ ] **Step 2: Update if needed**

If file contains:
- `python3 src/...` → update to `python3 -m src.X.Y`
- Hardcoded paths to `src/` → update to match new structure

**Use Edit tool if changes needed.**

---

### Task 4: Check tools/install_fftools.sh for updates

- [ ] **Step 1: Read tools/install_fftools.sh**

```bash
cat tools/install_fftools.sh
# Check for any Python calls or hardcoded src/ references
```

- [ ] **Step 2: Update if needed**

If file contains paths to `src/`, update them.

---

# Chunk 9: Update Documentation

**Files Modified:**
- `README.md`
- `CLAUDE.md`
- `docs/CONTRIBUTING.md`
- `docs/VIDEO_DEBUG_GUIDE.md`

---

### Task 1: Update README.md

- [ ] **Step 1: Read README.md**

```bash
cat README.md
# Look for references to build.sh, run.sh, and other scripts
```

- [ ] **Step 2: Update Quick Start section**

Find the "Quick Start" section and add information about additional tools:

```markdown
## Quick Start

# Primary commands
./build.sh          # Rebuild trip database
./run.sh            # Start web server on localhost:8000

# Additional tools
./tools/build_parallel.sh      # Parallel build (faster)
./tools/debug_videos.sh        # Debug video issues
./tools/install_fftools.sh     # Install FFmpeg tools
```

**Use Edit tool to make these changes.**

- [ ] **Step 3: Verify changes**

```bash
grep -A 5 "Quick Start" README.md
# Expected: updated instructions with tools/ references
```

---

### Task 2: Update CLAUDE.md

- [ ] **Step 1: Read CLAUDE.md to find Project Layout section**

```bash
grep -n "Project Layout" CLAUDE.md
# Expected: line number of the Project Layout section
```

- [ ] **Step 2: Update Project Layout section (change v3 to v4)**

Update the architecture and core modules section to reflect:
```markdown
## Project Layout (v4)

### Core Modules

**src/extraction/** (GPS extraction & trip detection)
- `build_database.py`: Main entry point, NMEA parsing, trip detection
- `build_database_parallel.py`: Parallel variant for faster builds
- `ddpai_route_improved.py`: Reference implementation

**src/processing/** (Trip utilities)
- `merge_trips.py`: Merge consecutive trips

**src/video/** (Video handling)
- `merge_videos.py`: FFmpeg wrapper for video concatenation

**tools/** (Utility scripts)
- `build_parallel.sh`: Wrapper for parallel builds
- `debug_videos.sh`: Video debugging utilities
- `install_fftools.sh`: FFmpeg setup helper

**web/** (Frontend)
- `index.html`: Dashboard (loads ../data/trips.json)
- `favicon.ico`, `favicon.png`: Branding assets

**docs/** (Documentation)
- `CONTRIBUTING.md`: Contribution guidelines
- `CHANGELOG.md`: Release history
- `VIDEO_DEBUG_GUIDE.md`: Video debugging guide
```

**Use Edit tool to make these changes.**

- [ ] **Step 3: Verify changes**

```bash
grep -A 30 "Project Layout (v4)" CLAUDE.md
# Expected: updated section with new structure
```

---

### Task 3: Update docs/CONTRIBUTING.md

- [ ] **Step 1: Read docs/CONTRIBUTING.md**

```bash
cat docs/CONTRIBUTING.md
# Check for any path references or setup instructions
```

- [ ] **Step 2: Update any path references**

If file mentions:
- `src/build_database.py` → change to `src/extraction/build_database.py`
- `./build_parallel.sh` → change to `./tools/build_parallel.sh`
- Development setup instructions

**Use Edit tool if changes needed.**

---

### Task 4: Update docs/VIDEO_DEBUG_GUIDE.md

- [ ] **Step 1: Read docs/VIDEO_DEBUG_GUIDE.md**

```bash
cat docs/VIDEO_DEBUG_GUIDE.md
# Check for script path references
```

- [ ] **Step 2: Update script references**

If file mentions:
- `./debug_videos.sh` → change to `./tools/debug_videos.sh`
- Any path references to src/ utilities

**Use Edit tool if changes needed.**

---

# Chunk 10: Validation & Atomic Commit

---

### Task 1: Validate Python imports work

- [ ] **Step 1: Test src.extraction.build_database import**

```bash
python3 -c "import src.extraction.build_database; print('✓ src.extraction.build_database OK')"
# Expected: ✓ src.extraction.build_database OK
```

- [ ] **Step 2: Test src.extraction.build_database_parallel import**

```bash
python3 -c "import src.extraction.build_database_parallel; print('✓ src.extraction.build_database_parallel OK')"
# Expected: ✓ src.extraction.build_database_parallel OK
```

- [ ] **Step 3: Test src.processing.merge_trips import**

```bash
python3 -c "import src.processing.merge_trips; print('✓ src.processing.merge_trips OK')"
# Expected: ✓ src.processing.merge_trips OK
```

- [ ] **Step 4: Test src.video.merge_videos import**

```bash
python3 -c "import src.video.merge_videos; print('✓ src.video.merge_videos OK')"
# Expected: ✓ src.video.merge_videos OK
```

---

### Task 2: Validate shell scripts

- [ ] **Step 1: Verify build.sh is executable**

```bash
ls -l build.sh
# Expected: -rwxr-xr-x ... build.sh
```

- [ ] **Step 2: Verify tools/ scripts are executable**

```bash
ls -l tools/*.sh
# Expected: all have -rwxr-xr-x permissions
```

- [ ] **Step 3: Test build.sh syntax (dry run, don't execute)**

```bash
bash -n build.sh
# Expected: no output (syntax OK)
```

- [ ] **Step 4: Test tools/build_parallel.sh syntax**

```bash
bash -n tools/build_parallel.sh
# Expected: no output (syntax OK)
```

---

### Task 3: Validate folder structure

- [ ] **Step 1: Verify new structure**

```bash
tree -L 2 -I '__pycache__|*.pyc' .
# Expected output shows:
# - src/extraction/, src/processing/, src/video/ with .py files
# - tools/ with .sh files
# - docs/ with .md files
# - web/ with .html and favicon files
# - NO backup/ directory
```

- [ ] **Step 2: Verify no orphaned files in src/ root**

```bash
ls src/*.py
# Expected: only __init__.py (no other .py files)
```

- [ ] **Step 3: Verify no scripts in root (except build.sh, run.sh)**

```bash
ls -1 *.sh
# Expected: build.sh, run.sh only
```

---

### Task 4: Verify git status

- [ ] **Step 1: Check git status**

```bash
git status
# Expected: shows deleted files, new files, modified files (no untracked clutter)
```

- [ ] **Step 2: Review what's being committed**

```bash
git status --short
# Expected: M for modified files, D for deleted files, A for added files
```

- [ ] **Step 3: Verify no unintended deletions**

```bash
git status | grep "deleted:"
# Verify only backup/ folder is deleted, nothing else
```

---

### Task 5: Atomic commit

- [ ] **Step 1: Stage all changes**

```bash
git add -A
```

- [ ] **Step 2: Verify staging**

```bash
git status
# Expected: all changes staged (no "Changes not staged" section)
```

- [ ] **Step 3: Create atomic commit**

```bash
git commit -m "refactor: reorganize folder structure for v4

- Move scripts to tools/ (build_parallel.sh, debug_videos.sh, install_fftools.sh)
- Move docs to docs/ (CONTRIBUTING.md, CHANGELOG.md, VIDEO_DEBUG_GUIDE.md)
- Reorganize src/ into domains: extraction/, processing/, video/
- Move favicons to web/
- Delete backup/ folder (content preserved in git history)
- Add __init__.py package markers for proper Python imports
- Update all import paths to use src.X.Y format
- Update shell scripts and documentation for new structure

No functionality changes—pure reorganization for maintainability and distribution.

Closes: #5

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Verify commit created**

```bash
git log --oneline -1
# Expected: shows the refactor commit message
```

---

### Task 6: Post-commit validation

- [ ] **Step 1: Verify data/ folder untouched**

```bash
ls data/
# Expected: trips.json (unchanged from before refactor)
```

- [ ] **Step 2: Verify merged_videos/ untouched**

```bash
ls merged_videos/ 2>&1 | head -5
# Expected: video files (unchanged from before refactor)
```

- [ ] **Step 3: Verify working_data/ untouched**

```bash
ls working_data/
# Expected: tar/ folder with source data (unchanged)
```

- [ ] **Step 4: Final git log check**

```bash
git log --oneline -3
# Expected: latest commit is the refactor commit
```

---

## Success Criteria

✅ All files moved to correct locations
✅ All `__init__.py` files exist in src/ and subfolders
✅ All import paths updated and validated
✅ All shell scripts executable and syntax-checked
✅ All documentation updated with new structure
✅ Single atomic commit created
✅ Git history shows no data loss
✅ Python modules importable from command line
✅ data/, merged_videos/, working_data/ untouched
✅ GitHub issue #5 updated with completion

---

## Rollback

If anything fails, revert with:
```bash
git revert <commit-hash>
# All files restored to original locations
```

Or (nuclear option):
```bash
git reset --hard HEAD~1
# Back to state before refactor commit
```

---

**Plan Status:** Ready for execution
**Estimated Time:** 45-60 minutes (including validation)
**Created:** 2026-03-14
**Spec Reference:** docs/superpowers/specs/2026-03-13-folder-restructuring-design.md
