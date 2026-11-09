"""Shared helpers: workspace paths, the local reel database and URL parsing.

Everything lives in one folder (default: ~/saved-reels-digest, override with
the SRD_HOME environment variable). Nothing is sent anywhere except the
requests to Instagram needed to read your own saved posts.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path



def _utf8_output() -> None:
    """Captions are full of emoji, and on Windows a piped stdout is cp1252, which cannot print them."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


_utf8_output()

HOME = Path(os.environ.get("SRD_HOME", Path.home() / "saved-reels-digest")).expanduser()
DB_PATH = HOME / "reels.json"
BACKUP_PATH = HOME / "reels.backup.json"
BACKUP_EVERY = 24 * 3600  # seconds
SESSION_DIR = HOME / ".session"

# instagram.com/p/<code>, /reel/<code>, /reels/<code>, /tv/<code>, optionally /<user>/reel/<code>
SHORTCODE_RE = re.compile(
    r"instagram\.com/(?:[A-Za-z0-9_.]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]{5,})"
)

# TikTok video links: tiktok.com/@user/video/<id>, the tiktokv.com/share/video/<id>/ form
# used by TikTok's data export, and m.tiktok.com/v/<id>.html
TIKTOK_RE = re.compile(r"tiktokv?\.com/(?:@[\w.-]*/video|share/video|v)/(\d{8,})")
TIKTOK_PREFIX = "tt"

YOUTUBE_PREFIX = "yt"


def ensure_home() -> Path:
    HOME.mkdir(parents=True, exist_ok=True)
    return HOME


def shortcode_from_url(url: str) -> str | None:
    m = SHORTCODE_RE.search(url or "")
    return m.group(1) if m else None


def tiktok_id_from_url(url: str) -> str | None:
    m = TIKTOK_RE.search(url or "")
    return m.group(1) if m else None


def tiktok_key(video_id: str) -> str:
    """Database key for a TikTok video. Prefixed so it never clashes with an Instagram shortcode."""
    return f"{TIKTOK_PREFIX}{video_id}"


def tiktok_url(video_id: str) -> str:
    # "@" without a username is accepted by tiktok.com and by yt-dlp
    return f"https://www.tiktok.com/@/video/{video_id}"


def youtube_key(video_id: str) -> str:
    """Database key for a YouTube video, kept apart from Instagram shortcodes like TikTok's."""
    return f"{YOUTUBE_PREFIX}{video_id}"


def youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def canonical_url(shortcode: str) -> str:
    return f"https://www.instagram.com/reel/{shortcode}/"


def resolve_code(reels: dict, name: str) -> str | None:
    """Database key for a code or a pasted Instagram / TikTok link, or None if it is not saved."""
    name = name.strip()
    if name in reels:
        return name
    tiktok_id = tiktok_id_from_url(name)
    key = shortcode_from_url(name) or (tiktok_key(tiktok_id) if tiktok_id else None)
    return key if key in reels else None


def split_codes(items) -> list[str]:
    """Codes from command line arguments, each of which may hold several separated by commas."""
    return [c.strip() for item in items for c in item.split(",") if c.strip()]


def _damaged_db_message(why: str) -> str:
    fix = (f"Replace it with the backup: copy {BACKUP_PATH} over it (at most a day of work is lost)."
           if BACKUP_PATH.exists()
           else "There is no backup yet. Move the file aside and collect again to start over.")
    return f"{DB_PATH} is damaged ({why}), so nothing was changed. {fix}"


def load_db() -> dict:
    if not DB_PATH.exists():
        return {"version": 1, "reels": {}}
    try:
        with DB_PATH.open(encoding="utf-8") as f:
            db = json.load(f)
    except ValueError as e:  # bad JSON or bad UTF-8
        sys.exit(_damaged_db_message(str(e)))
    if not isinstance(db, dict) or not isinstance(db.get("reels"), dict):
        sys.exit(_damaged_db_message('no "reels" table'))
    return db


def _daily_backup() -> None:
    """Copy the database before overwriting it, at most once a day. Never blocks a save."""
    try:
        if not DB_PATH.exists() or not DB_PATH.stat().st_size:
            return
        if BACKUP_PATH.exists() and time.time() - BACKUP_PATH.stat().st_mtime < BACKUP_EVERY:
            return
        tmp = BACKUP_PATH.with_suffix(".tmp")
        try:
            shutil.copyfile(DB_PATH, tmp)
            os.replace(tmp, BACKUP_PATH)
        except OSError:
            _remove_quietly(tmp)
            raise
    except OSError as e:
        log(f"Could not back up {DB_PATH}: {e}")


def _remove_quietly(path) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def save_db(db: dict) -> None:
    """Atomic write so an interrupted run never corrupts the database."""
    ensure_home()
    _daily_backup()
    fd, tmp = tempfile.mkstemp(dir=HOME, prefix=".reels.", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=1)
        os.replace(tmp, DB_PATH)
    except BaseException as e:
        # A full disk (or Ctrl+C) mid-write must not leave half-written .reels.*.json files behind.
        _remove_quietly(tmp)
        if isinstance(e, OSError):
            sys.exit(f"Could not save {DB_PATH} ({e.strerror or e}). The file was not changed; "
                     "free some disk space and run the command again.")
        raise


def add_reel(db: dict, shortcode: str, **fields) -> bool:
    """Insert a reel if new. Returns True when it was added."""
    reels = db["reels"]
    if shortcode in reels:
        r = reels[shortcode]
        for k, v in fields.items():  # fill gaps, never overwrite
            if v and not r.get(k):
                r[k] = v
        return False
    reels[shortcode] = {
        "shortcode": shortcode,
        "url": canonical_url(shortcode),
        "added_at": int(time.time()),
        "relevant": None,   # None = not triaged, True / False / "maybe"
        **{k: v for k, v in fields.items() if v is not None},
    }
    return True


def total_ram_bytes() -> int | None:
    """Physical memory of this computer, or None if it cannot be read. No dependencies."""
    try:
        if sys.platform == "win32":
            import ctypes

            class MemStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            st = MemStatus()
            st.dwLength = ctypes.sizeof(MemStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return int(st.ullTotalPhys) or None
        if sys.platform == "darwin":
            import subprocess
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True,
                                 text=True, check=True).stdout
            return int(out.strip())
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except Exception:  # noqa: BLE001
        return None


# Whisper model per amount of RAM, on CPU. "small" is the sweet spot for Spanish and
# English; "medium" and larger are too slow on a laptop CPU to be worth it.
MODEL_BY_RAM_GB = ((4, "tiny"), (8, "base"))
DEFAULT_MODEL = "small"
GPU_MODEL = "medium"


def pick_whisper_model(ram_bytes: int | None, cuda: bool = False) -> str:
    """Choose a Whisper model that fits this computer."""
    if ram_bytes is None:
        return DEFAULT_MODEL
    gb = ram_bytes / 1024 ** 3
    if cuda and gb >= 8:
        return GPU_MODEL
    for limit, name in MODEL_BY_RAM_GB:
        if gb < limit:
            return name
    return DEFAULT_MODEL


def in_collection(reel: dict, name: str | None) -> bool:
    """True when no filter is given or the reel was saved in that Instagram collection.

    Case-insensitive and ignores surrounding spaces ("ia" matches "IA", " Tech " matches "tech").
    """
    if not name:
        return True
    return (reel.get("collection") or "").strip().casefold() == name.strip().casefold()


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)
