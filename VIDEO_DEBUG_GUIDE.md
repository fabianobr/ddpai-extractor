# Video Merge Debug Guide

## Overview
The build script now supports reading from SD card and includes detailed debugging output for video merging.

## Usage: Reading from SD Card

### Option 1: Read TAR files from SD card (basic)
```bash
./build.sh /Volumes/SDCard/tar
```
Uses:
- TAR files from: `/Volumes/SDCard/tar`
- Videos from: Local default locations

### Option 2: Read everything from SD card
```bash
./build.sh /Volumes/SDCard/tar /Volumes/SDCard/rear /Volumes/SDCard/front
```
Uses:
- TAR files from: `/Volumes/SDCard/tar`
- Rear videos from: `/Volumes/SDCard/rear`
- Front videos from: `/Volumes/SDCard/front`
- Output to: Current directory

### Option 3: Read from SD card, save to specific location
```bash
./build.sh /Volumes/SDCard/tar /Volumes/SDCard/rear /Volumes/SDCard/front /Users/yourname/ddpai_output
```
Uses:
- TAR files from: `/Volumes/SDCard/tar`
- Rear videos from: `/Volumes/SDCard/rear`
- Front videos from: `/Volumes/SDCard/front`
- Output to: `/Users/yourname/ddpai_output`

### Option 4: Use local defaults
```bash
./build.sh
```
Uses default paths (original configuration)

---

## Debug Output During Build

When you run `./build.sh`, you'll see detailed information about each video merge:

```
================================================================================
REAR CAMERA - Merging 9 videos:
================================================================================
  1. 20260307103136_0480_front.mp4
     → 245.3 MB | 480.0s (8 min)
  2. 20260307104736_0480_front.mp4
     → 312.5 MB | 480.0s (8 min)
  ...
  9. 20260307110936_0480_front.mp4
     → 189.2 MB | 360.0s (6 min)

Total: 9 files | 2145.6 MB | 4080.0s (68 min)

Concat list:
  1. /Users/fabianosilva/dashcam/DCIM/200video/rear/20260307103136_0480_rear.mp4
  2. /Users/fabianosilva/dashcam/DCIM/200video/rear/20260307104736_0480_rear.mp4
  ...

Running FFmpeg...
Command: ffmpeg -f concat -safe 0 -i /tmp/... -c copy -y ...

✅ Merge successful!
Output: 20260307103136_rear.mp4
  → 2100.5 MB | 4020.0s (67 min)
```

### What This Tells You

1. **Number of videos merged**: How many source files went into the merged file
2. **File sizes**: Each source video size (check if any are suspiciously small/large)
3. **Durations**: Each source video duration (check for mismatches)
4. **Concat order**: The exact order videos were concatenated
5. **Output size**: Final merged video size (should ≈ sum of inputs)
6. **Output duration**: Final merged video duration

---

## Troubleshooting: Why Merged Video Differs from Originals

### Issue 1: Merged video is much smaller than originals
**Causes:**
- Some source videos failed to include (check log for which ones)
- FFmpeg used codec copy but videos had different specs
- Videos were already compressed differently

**How to check:**
```bash
# See individual source video specs
ffprobe -v error -show_entries format=duration,size,bit_rate \
  /Volumes/SDCard/rear/20260307103136_0480_rear.mp4

# See merged video specs
ffprobe -v error -show_entries format=duration,size,bit_rate \
  merged_videos/20260307103136_rear.mp4

# Compare total size
du -h /Volumes/SDCard/rear/*.mp4 | tail -1
du -h merged_videos/20260307103136_rear.mp4
```

### Issue 2: Merged video is missing footage
**Causes:**
- Video files are corrupted (FFmpeg skipped them)
- Wrong camera directory specified
- Videos not in the expected naming format

**How to fix:**
1. Check the build output log for error messages
2. Verify video directory contains the correct files
3. Check if videos need different codec settings

### Issue 3: Merged video plays incorrectly
**Causes:**
- Source videos have different codecs/frame rates
- FFmpeg concat filter requires compatible specs

**How to fix:**
Re-encode before merging (slower but more compatible):
```bash
# Edit src/build_database.py, change merge_videos() call:
# Change: '-c', 'copy'
# To: '-c:v', 'libx264', '-crf', '18', '-c:a', 'aac'
```

---

## Debug Tools

### 1. Debug Video Information Script
```bash
./debug_videos.sh
```
Shows:
- All merged video files and sizes
- Original video locations
- Basic troubleshooting steps

### 2. FFprobe (Video Inspector)
```bash
# Get all video details
ffprobe merged_videos/20260307103136_rear.mp4

# Get specific info (faster)
ffprobe -v error -show_format -show_streams merged_videos/20260307103136_rear.mp4

# Get just duration and size
ffprobe -v error -show_entries format=duration,size \
  merged_videos/20260307103136_rear.mp4
```

### 3. FFplay (Video Player)
```bash
# Play merged video
ffplay merged_videos/20260307103136_rear.mp4

# Play side-by-side (in separate windows)
ffplay /Volumes/SDCard/rear/20260307103136_0480_rear.mp4 &
ffplay merged_videos/20260307103136_rear.mp4
```

### 4. Merge Report
```bash
# Detailed merge report (auto-generated)
cat data/merge_report.txt

# Check size of all files
ls -lh merged_videos/
ls -lh data/
```

---

## Understanding the Merge Report

The build script creates `data/merge_report.txt` with full details:

```
VIDEO MERGE DEBUG REPORT
================================================================================
Generated: 2026-03-11T18:30:45.123456
TAR Directory: /Volumes/SDCard/tar
Rear Videos: /Volumes/SDCard/rear
Front Videos: /Volumes/SDCard/front
Output Directory: .
================================================================================

REAR CAMERA - Merging 9 videos:
================================================================================
  1. 20260307103136_0480_rear.mp4
     → 245.3 MB | 480.0s
  ...
```

Each video listed shows:
- **Order**: How it appears in the merge
- **Filename**: Source file name
- **Size**: In megabytes (MB)
- **Duration**: In seconds (s)

---

## Step-by-Step Verification

### 1. Before Building
```bash
# Check source directories exist
ls /Volumes/SDCard/tar/*.git | wc -l
ls /Volumes/SDCard/rear/*.mp4 | wc -l
ls /Volumes/SDCard/front/*.mp4 | wc -l
```

### 2. During Building
```bash
# Start the build and watch the merge output
./build.sh /Volumes/SDCard/tar /Volumes/SDCard/rear /Volumes/SDCard/front

# Note:
# - Which videos got merged
# - Total sizes and durations
# - Any merge errors
```

### 3. After Building
```bash
# Check merge report
cat data/merge_report.txt

# Compare file counts
ls /Volumes/SDCard/rear/*.mp4 | wc -l
ls merged_videos/*_rear.mp4 | wc -l

# Compare total sizes
du -sh /Volumes/SDCard/rear
du -sh merged_videos
```

---

## Common Video Naming Patterns

The script looks for videos matching the TAR file timestamps:

**TAR file**: `20260307103136_0480.git`
- Timestamp: 2026-03-07 10:31:36
- Duration: 480 seconds

**Rear video** (must exist):
- `/Volumes/SDCard/rear/20260307103136_0480_rear.mp4`
- `/Volumes/SDCard/rear/20260307103136*_rear.mp4`

**Front video** (must exist):
- `/Volumes/SDCard/front/20260307103136_0480_front.mp4`
- `/Volumes/SDCard/front/20260307103136*_front.mp4`

If naming doesn't match, videos won't be found. Check with:
```bash
ls /Volumes/SDCard/rear/20260307103136*
ls /Volumes/SDCard/front/20260307103136*
```

---

## Command Reference

```bash
# Show help
./build.sh /nonexistent/path

# Build with defaults
./build.sh

# Build from SD card
./build.sh /Volumes/SDCard/tar /Volumes/SDCard/rear /Volumes/SDCard/front

# View debug info
./debug_videos.sh

# View merge report
cat data/merge_report.txt

# Inspect video details
ffprobe merged_videos/*.mp4

# Play merged video
ffplay merged_videos/20260307103136_rear.mp4

# Check file sizes
ls -lh merged_videos/
```

---

## Contact/Issues

If merged videos still don't match originals:
1. Save the `data/merge_report.txt` file
2. Check which videos were actually merged
3. Compare file sizes and durations using ffprobe
4. Verify source videos are in correct locations
5. Check for FFmpeg error messages in the build log
