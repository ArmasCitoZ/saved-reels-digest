"""Create a private virtualenv inside the workspace and install dependencies.

Run with any Python 3.9+:  python3 setup_env.py
Prints the path of the Python to use for every other script.
"""
from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ensure_home  # noqa: E402

REQ = Path(__file__).resolve().parent / "requirements.txt"


def venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main() -> None:
    if sys.version_info < (3, 9):
        sys.exit("Python 3.9 or newer is required.")
    home = ensure_home()
    env_dir = home / ".venv"
    py = venv_python(env_dir)
    if not py.exists():
        print(f"Creating virtualenv in {env_dir} ...", flush=True)
        venv.EnvBuilder(with_pip=True).create(env_dir)
    print("Installing dependencies (first time takes a minute) ...", flush=True)
    subprocess.check_call([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"])
    subprocess.check_call([str(py), "-m", "pip", "install", "-q", "-r", str(REQ)])
    print(f"\nREADY. Use this Python for the other scripts:\n{py}")


if __name__ == "__main__":
    main()
