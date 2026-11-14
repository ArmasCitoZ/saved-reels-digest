"""Create a private virtualenv inside the workspace and install dependencies.

Run with any Python 3.9+:  python3 setup_env.py [--upgrade]
Prints the path of the Python to use for every other script. When the environment is
already complete it changes nothing (and needs no internet); --upgrade updates the packages.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ensure_home  # noqa: E402
from doctor import MAX_PYTHON, NEWER_PYTHON_HINT, OK, check_venv  # noqa: E402

REQ = Path(__file__).resolve().parent / "requirements.txt"


def venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def install(py: Path, env_dir: Path, upgrade: bool) -> None:
    print("Installing dependencies (first time takes a minute) ...", flush=True)
    subprocess.check_call([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"])
    cmd = [str(py), "-m", "pip", "install", "-q", "-r", str(REQ)] + (["--upgrade"] if upgrade else [])
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        if sys.version_info[:2] > MAX_PYTHON:
            newest = ".".join(map(str, MAX_PYTHON))
            sys.exit(f"Installing the dependencies failed. Python {sys.version_info[0]}."
                     f"{sys.version_info[1]} is probably too new for some of them: "
                     + NEWER_PYTHON_HINT.format(max=newest)
                     + f", after deleting {env_dir}.")
        raise


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--upgrade", action="store_true",
                    help="update the packages even when the environment is complete")
    args = ap.parse_args(argv)
    if sys.version_info < (3, 9):
        sys.exit("Python 3.9 or newer is required.")
    home = ensure_home()
    env_dir = home / ".venv"
    py = venv_python(env_dir)
    if not py.exists():
        print(f"Creating virtualenv in {env_dir} ...", flush=True)
        venv.EnvBuilder(with_pip=True).create(env_dir)
    elif not args.upgrade and check_venv(home)["status"] == OK:
        # running the setup again (install.ps1, a new session) should not need pip or internet
        print("The environment is already complete (setup_env.py --upgrade updates the packages).")
        print(f"\nREADY. Use this Python for the other scripts:\n{py}")
        return
    install(py, env_dir, args.upgrade)
    print(f"\nREADY. Use this Python for the other scripts:\n{py}")


if __name__ == "__main__":
    main()
