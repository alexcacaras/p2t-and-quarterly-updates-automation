# cleanup.py
import os, time, pathlib, sys
#os for clean up and os related features, time for time related features such as file age, pathlib for simplfying path, sys for command line argument access

def cleanup_media(
    folder: pathlib.Path,
    retain_days: int = 7,
    keep_latest: int = 200,
    patterns = ("*.png", "*.webm", "*.mp4")
):
    if not folder.exists():
        print(f"[cleanup] Folder not found: {folder}")
        return

    now = time.time()

    # Collect files matching patterns
    files = []
    for pat in patterns:
        files.extend(folder.glob(pat))
    files = [f for f in files if f.is_file()]

    # Sort newest first
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    # If keep_latest == 0 and retain_days == 0 -> delete all
    delete_all = (keep_latest == 0 and retain_days == 0)

    to_keep = []
    to_delete = []

    for idx, f in enumerate(files):
        age_sec = now - f.stat().st_mtime
        age_days = age_sec / 86400.0

        if delete_all:
            to_delete.append(f)
            continue

        # Age-based rule
        if retain_days is not None and retain_days >= 0 and age_days > retain_days:
            to_delete.append(f)
            continue

        # Tentatively keep, will trim by count next
        to_keep.append(f)

    # Count-based trimming (keep only top N newest)
    if keep_latest is not None and keep_latest >= 0 and len(to_keep) > keep_latest:
        to_delete.extend(to_keep[keep_latest:])
        to_keep = to_keep[:keep_latest]

    # Delete
    deleted = 0
    for f in to_delete:
        try:
            f.unlink(missing_ok=True)
            deleted += 1
        except PermissionError:
            # file is probably open/locked in Windows; skip
            pass
        except Exception:
            pass

    print(f"[cleanup] Checked: {len(files)} | Kept: {len(to_keep)} | Deleted: {deleted} | Folder: {folder}")

def getenv_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except:
        return default

if __name__ == "__main__":
    # Anchor to the script directory so it works no matter where you run it from
    ROOT = pathlib.Path(__file__).resolve().parent
    screenshots_dir = ROOT / "screenshots"

    # Env vars (ALL CAPS, no typos)
    RETAIN_DAYS = getenv_int("RETAIN_DAYS", 7)     # set 0 to delete based on count only
    KEEP_LATEST = getenv_int("KEEP_LATEST", 200)   # set 0 to keep none (delete all by count)

    # Allow optional CLI override: cleanup.py [retain_days] [keep_latest]
    if len(sys.argv) >= 2:
        try: RETAIN_DAYS = int(sys.argv[1])
        except: pass
    if len(sys.argv) >= 3:
        try: KEEP_LATEST = int(sys.argv[2])
        except: pass

    cleanup_media(screenshots_dir, retain_days=RETAIN_DAYS, keep_latest=KEEP_LATEST)
    print("[cleanup] Screenshot cleanup complete.")
