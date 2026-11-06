"""Shared helpers: workspace paths, the local reel database and URL parsing.

Everything lives in one folder (default: ~/saved-reels-digest, override with
the SRD_HOME environment variable). Nothing is sent anywhere except the
requests to Instagram needed to read your own saved posts.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

HOME = Path(os.environ.get("SRD_HOME", Path.home() / "saved-reels-digest")).expanduser()
DB_PATH = HOME / "reels.json"
SESSION_DIR = HOME / ".session"

# instagram.com/p/<code>, /reel/<code>, /reels/<code>, /tv/<code>, optionally /<user>/reel/<code>
SHORTCODE_RE = re.compile(
    r"instagram\.com/(?:[A-Za-z0-9_.]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]{5,})"
)


def ensure_home() -> Path:
    HOME.mkdir(parents=True, exist_ok=True)
    return HOME


def shortcode_from_url(url: str) -> str | None:
    m = SHORTCODE_RE.search(url or "")
    return m.group(1) if m else None


def canonical_url(shortcode: str) -> str:
    return f"https://www.instagram.com/reel/{shortcode}/"


def load_db() -> dict:
    if not DB_PATH.exists():
        return {"version": 1, "reels": {}}
    with DB_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def save_db(db: dict) -> None:
    """Atomic write so an interrupted run never corrupts the database."""
    ensure_home()
    fd, tmp = tempfile.mkstemp(dir=HOME, prefix=".reels.", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DB_PATH)


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


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)
