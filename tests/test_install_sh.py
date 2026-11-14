"""Tests for install.sh, the one-command setup on macOS and Linux.

They run the script with sh (dash on Debian and Ubuntu, a strict POSIX shell) and are skipped
on Windows, which has install.ps1 instead.
"""
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "install.sh"
TEXT = SCRIPT.read_text("utf-8")

pytestmark = pytest.mark.skipif(sys.platform == "win32" or not shutil.which("sh"),
                                reason="install.sh is for macOS and Linux")


def run(home, *args, **env):
    return subprocess.run(["sh", str(SCRIPT), *args], capture_output=True, text=True, timeout=300,
                          env={**os.environ, "SRD_HOME": str(home), **env}, check=False)


def fake_python(tmp_path, major, minor):
    """A 'python' that only answers the version question, like an old or too-new install."""
    exe = tmp_path / f"python{major}.{minor}"
    exe.write_text(f"#!/bin/sh\necho {major} {minor}\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return exe


def test_check_only_runs_doctor_and_installs_nothing(tmp_path):
    r = run(tmp_path / "srd", "--check-only", SRD_PYTHON=sys.executable)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert f"Using Python {sys.version_info[0]}.{sys.version_info[1]}" in out
    assert "Ready." in out and "nothing was installed" in out
    assert not (tmp_path / "srd" / ".venv").exists()


def test_finds_a_python_by_itself(tmp_path):
    r = run(tmp_path / "srd", "--check-only")
    assert r.returncode == 0, r.stdout + r.stderr
    assert re.search(r"Using Python 3\.(9|1[0-4]) \(", r.stdout)


def test_doctor_failure_stops_the_install(tmp_path):
    blocker = tmp_path / "srd"
    blocker.write_text("not a folder")  # SRD_HOME inside a file cannot be created
    r = run(blocker / "inside", SRD_PYTHON=sys.executable)
    assert r.returncode == 1
    assert "FAIL" in r.stdout and "Fix the FAIL lines" in r.stderr
    assert "Creating the Python environment" not in r.stdout


def test_too_old_python_is_refused(tmp_path):
    r = run(tmp_path / "srd", "--check-only", SRD_PYTHON=str(fake_python(tmp_path, 3, 8)))
    assert r.returncode == 1 and "not Python 3.9 or newer" in r.stderr


def test_too_new_python_is_used_with_a_warning(tmp_path):
    r = run(tmp_path / "srd", "--check-only", SRD_PYTHON=str(fake_python(tmp_path, 3, 99)))
    assert "Using Python 3.99" in r.stdout
    assert "may be too new" in r.stderr and "install\nPython 3.14" in r.stderr


def test_unknown_option(tmp_path):
    r = run(tmp_path / "srd", "--chek-only")
    assert r.returncode == 2 and "Unknown option: --chek-only" in r.stderr


def test_python_range_matches_doctor():
    sys.path.insert(0, str(ROOT / "skills" / "digest" / "scripts"))
    import doctor

    assert int(re.search(r"^MIN_MINOR=(\d+)", TEXT, re.M).group(1)) == doctor.MIN_PYTHON[1]
    assert int(re.search(r"^MAX_MINOR=(\d+)", TEXT, re.M).group(1)) == doctor.MAX_PYTHON[1]


def test_no_bashisms():
    # dash, the sh of Debian and Ubuntu, has none of these
    code = [line.split(" #", 1)[0] for line in TEXT.splitlines() if not line.lstrip().startswith("#")]
    bashisms = (r"\[\[", r"\bfunction\b", r"\blocal\b", r"<<<", r"\$\{[^}]*//", r"\[ [^]]* == ",
                r"\bsource\b")
    for pattern in bashisms:
        assert not [ln for ln in code if re.search(pattern, ln)], pattern
