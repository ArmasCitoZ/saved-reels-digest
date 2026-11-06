"""Check that this computer is ready before doing any real work.

  doctor.py           human-readable report
  doctor.py --json    same checks as JSON (for Claude)

Runs with the system Python (no dependencies) so it works before setup_env.py.
Each check is OK, WARN (works, but worth knowing) or FAIL (fix it first).
Exit code is 1 when any check fails.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HOME, pick_whisper_model, total_ram_bytes  # noqa: E402

MIN_PYTHON = (3, 9)
# first run: virtualenv with deps (~600 MB) + Whisper "small" model (~460 MB)
DISK_NEEDED_FIRST_RUN_MB = 1200
DISK_NEEDED_MB = 300  # later runs: temporary audio files and the database
REQUIRED_MODULES = ("yt_dlp", "faster_whisper", "instaloader", "browser_cookie3")

OK, WARN, FAIL = "ok", "warn", "fail"


def venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def check_python(version=None) -> dict:
    v = tuple(version or sys.version_info[:3])
    shown = ".".join(map(str, v))
    if v[:2] < MIN_PYTHON:
        return {"name": "python", "status": FAIL,
                "detail": f"Python {shown}; 3.9 or newer is required (python.org/downloads)"}
    return {"name": "python", "status": OK, "detail": f"Python {shown}"}


def _existing_parent(path: Path) -> Path:
    while not path.exists() and path.parent != path:
        path = path.parent
    return path


def check_disk(home: Path = HOME, free_bytes=None) -> dict:
    first_run = not (home / ".venv").exists()
    need = DISK_NEEDED_FIRST_RUN_MB if first_run else DISK_NEEDED_MB
    if free_bytes is None:
        free_bytes = shutil.disk_usage(_existing_parent(home)).free
    free_mb = free_bytes // (1024 * 1024)
    detail = f"{free_mb / 1024:.1f} GB free in {_existing_parent(home)}"
    if free_mb < need:
        return {"name": "disk", "status": FAIL,
                "detail": f"{detail}; needs about {need} MB"
                          + (" for the first run (Python packages + Whisper model)" if first_run else "")}
    if free_mb < need * 2:
        return {"name": "disk", "status": WARN, "detail": f"{detail}; tight, about {need} MB needed"}
    return {"name": "disk", "status": OK, "detail": detail}


def check_workspace(home: Path = HOME) -> dict:
    try:
        home.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=home, prefix=".doctor-"):
            pass
    except OSError as e:
        return {"name": "workspace", "status": FAIL,
                "detail": f"cannot write to {home} ({e.strerror or e}); set SRD_HOME to another folder"}
    return {"name": "workspace", "status": OK, "detail": str(home)}


def check_venv(home: Path = HOME) -> dict:
    py = venv_python(home / ".venv")
    if not py.exists():
        return {"name": "venv", "status": WARN,
                "detail": "not created yet; run setup_env.py (one time, about a minute)"}
    code = "import importlib.util as u, sys; " \
           f"m = [n for n in {REQUIRED_MODULES!r} if u.find_spec(n) is None]; print(','.join(m))"
    try:
        out = subprocess.run([str(py), "-c", code], capture_output=True, text=True,
                             timeout=60, check=False).stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"name": "venv", "status": FAIL, "detail": f"{py} does not run ({e}); delete .venv "
                                                          "and run setup_env.py again"}
    if out:
        return {"name": "venv", "status": FAIL,
                "detail": f"missing packages: {out}; run setup_env.py again"}
    return {"name": "venv", "status": OK, "detail": str(py)}


def check_ffmpeg(which=shutil.which) -> dict:
    path = which("ffmpeg")
    if path:
        return {"name": "ffmpeg", "status": OK, "detail": path}
    return {"name": "ffmpeg", "status": OK,
            "detail": "not installed (optional: audio is decoded without it)"}


def check_ram(ram_bytes=None) -> dict:
    ram_bytes = total_ram_bytes() if ram_bytes is None else ram_bytes
    if not ram_bytes:
        return {"name": "ram", "status": WARN, "detail": "could not read; transcribe.py will use 'small'",
                "whisper_model": pick_whisper_model(None)}
    model = pick_whisper_model(ram_bytes)
    gb = ram_bytes / 1024 ** 3
    status = WARN if gb < 4 else OK
    return {"name": "ram", "status": status,
            "detail": f"{gb:.1f} GB; Whisper model on CPU: {model}", "whisper_model": model}


def run_checks(home: Path = HOME) -> list:
    return [check_python(), check_workspace(home), check_disk(home), check_ram(),
            check_venv(home), check_ffmpeg()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="print the checks as JSON")
    args = ap.parse_args(argv)
    checks = run_checks()
    failed = any(c["status"] == FAIL for c in checks)
    if args.json:
        print(json.dumps({"ok": not failed, "checks": checks}, ensure_ascii=False, indent=1))
    else:
        for c in checks:
            print(f"[{c['status'].upper():4}] {c['name']:<9} {c['detail']}")
        print("\nNot ready: fix the FAIL lines above." if failed else "\nReady.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
