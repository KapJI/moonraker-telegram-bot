# Known Bugs

## ~~Height notification truncated to integer (MEDIUM)~~ FIXED

## Timelapse lock file crash on empty prints (LOW)

**File:** `bot/camera.py:503-505`

`lock_file.touch()` runs before the `photo_count == 0` check at line 510.
If no frames were captured (e.g. a print with no extrusion), the lapse
directory was never created, and `touch()` fails with `FileNotFoundError`.

**Trigger:** Any print that finishes without capturing timelapse frames.

**Fix:** Move `lock_file.touch()` after the photo count check, or create
`lapse_dir` with `mkdir(parents=True, exist_ok=True)` before touching.
