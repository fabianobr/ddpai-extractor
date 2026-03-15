# Contributing

Thank you for your interest in contributing! **Please read this entire guide before submitting any changes.**

---

## 🔴 MUST DO: Mandatory Requirements

**ALL contributions MUST follow these rules — NO EXCEPTIONS:**

### 1. Feature Branch (REQUIRED)
- ✅ Create a feature branch from `develop`: `git checkout -b feature/your-feature-name`
- ✅ Use branch naming: `feature/*`, `fix/*`, `docs/*`, `refactor/*`
- ❌ DO NOT commit directly to `main` or `develop`

### 2. Test-Driven Development (REQUIRED)
- ✅ Write tests FIRST before implementing features
- ✅ Place tests in `tests/` directory (e.g., `tests/test_watch.sh`)
- ✅ Run tests locally before pushing: `pytest` or `bash tests/*.sh`
- ✅ All tests MUST pass before PR submission
- ❌ DO NOT submit code without tests

### 3. Pull Request (REQUIRED)
- ✅ Push branch: `git push -u origin feature/your-feature-name`
- ✅ Create PR on GitHub (never merge directly)
- ✅ Link PR to GitHub Projects board
- ✅ Wait for code review approval
- ❌ DO NOT self-approve or force-merge
- ❌ DO NOT use `git push --force`

### 4. Code Review (REQUIRED)
- ✅ Request review from project maintainers
- ✅ Fix review comments in new commits (don't amend published commits)
- ✅ Respond to all feedback before merging
- ❌ DO NOT ignore review feedback

### 5. Merge Via GitHub (REQUIRED)
- ✅ Merge through GitHub UI only
- ✅ Delete feature branch after merge
- ✅ If merging to `main`, sync `develop` afterward (see Sync below)
- ❌ DO NOT use force-push or rebase on shared branches

### 6. Branch Sync (REQUIRED for releases)
After merging a release PR to `main`:
```bash
git checkout develop
git pull origin develop
git merge main
git push origin develop
git checkout main
```

---

## Workflow Overview

This project uses **Git Flow** branching and **Conventional Commits**.

## Git Flow Branching

We follow [Git Flow](https://nvie.com/posts/a-successful-git-branching-model/):

- **`main`** — Production-ready releases only. Protected branch.
  - Only merged from `release/` branches
  - Every commit tagged as a release (v0.1.0, v0.2.0, etc.)

- **`develop`** — Integration branch for new features. Default branch.
  - Base for all feature and release branches
  - May be unstable; always points to next release

- **`feature/*`** — New features or improvements
  - Branch from: `develop`
  - Merge back to: `develop` (via pull request)
  - Naming: `feature/trip-idle-detection`, `feature/video-heatmap`, etc.

- **`release/vX.Y.Z`** — Release candidates
  - Branch from: `develop`
  - Merge to: `main` (via pull request) and back to `develop`
  - Bumps version numbers and updates CHANGELOG.md
  - Only bug fixes, no new features

- **`hotfix/vX.Y.Z`** — Emergency patches for production issues
  - Branch from: `main`
  - Merge to: `main` and back to `develop`
  - Bumps patch version only (v0.1.0 → v0.1.1)

## Commit Conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- `feat` — New feature
- `fix` — Bug fix
- `docs` — Documentation only
- `chore` — Build scripts, dependencies, tooling
- `refactor` — Code refactoring (no feature/bug change)
- `test` — Tests (not yet automated in this project)
- `perf` — Performance improvement

### Examples
```
feat(gps): add idle-speed threshold to trip validation

fix(video): correct H.264 encoding timeout for long trips

docs(readme): update FFmpeg installation instructions

chore(ci): add Python syntax check to GitHub Actions

refactor(nmea): simplify checksum validation logic
```

## Pull Request Process

### For Feature Development
1. Create a feature branch off `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
   ```

2. Make commits following Conventional Commits format

3. Push and open a PR to `develop`:
   ```bash
   git push -u origin feature/your-feature-name
   ```

4. Wait for code review and CI checks to pass

5. Merge via PR (squash or rebase optional; keep history clean)

6. Delete feature branch after merge

### For Releases
1. Create a release branch off `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b release/v0.2.0
   ```

2. Update CHANGELOG.md and version number:
   - Update CHANGELOG.md with new features/fixes/deprecations
   - Add [Unreleased] section for next development

3. Make release commit:
   ```bash
   git commit -m "chore(release): bump to v0.2.0"
   ```

4. Open PR to `main` for review

5. Merge to `main`, tag the release, and back-merge to `develop`:
   ```bash
   # (After PR merge to main)
   git checkout main
   git pull origin main
   git tag -a v0.2.0 -m "v0.2.0 — new features"
   git push origin v0.2.0

   # Back-merge to develop
   git checkout develop
   git pull origin develop
   git merge main
   git push origin develop
   ```

## Code Review Expectations

- Follow the architecture in [CLAUDE.md](CLAUDE.md)
- Keep changes focused (one feature/bug per PR)
- Update README.md if user-facing behavior changes
- Update CHANGELOG.md for releases
- Test manually (no automated test suite yet):
  - Run `./build.sh` and verify `data/trips.json` regenerates
  - Run `./run.sh` and open http://localhost:8000/web/
  - Check browser DevTools Console for JavaScript errors

## Hardcoded Paths

**Important:** Video paths in `src/build_database.py` (lines 18–20) are currently hardcoded to the author's local directories. When contributing:
- Do not commit paths specific to your system
- Document in PR if paths need updating for your dashcam layout
- Consider opening an issue if you'd like to add configuration file support

## Dependencies

**External Tools**
- FFmpeg with libx264 (for H.264 video re-encoding)
- Python 3.6+ (standard library only)
- Git 2.0+

**No pip dependencies** — standard library only for simplicity and reproducibility.

## Testing & Validation

Until an automated test suite is added, manually validate:

1. **GPS Extraction:**
   ```bash
   ./build.sh  # Check output for trip detection and validation messages
   ```

2. **Trip Database:**
   ```bash
   python3 -c "import json; d=json.load(open('data/trips.json')); print(len(d['trips']), 'trips')"
   ```

3. **Web UI:**
   ```bash
   ./run.sh
   # Open http://localhost:8000/web/
   # Select a trip, verify map renders, play video
   ```

4. **Video Encoding:**
   ```bash
   ffprobe -v error -select_streams v:0 -show_entries stream=width,height \
     -of csv=p=0 merged_videos/*_rear.mp4
   ```

## Questions?

- Check [CLAUDE.md](CLAUDE.md) for architecture details
- Review [README.md](README.md) for usage and configuration
- Open an issue for bug reports or feature requests

Thank you for contributing! 🎥📍
