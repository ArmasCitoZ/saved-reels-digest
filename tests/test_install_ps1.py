"""Tests for install.ps1, the one-command Windows setup.

The static tests run everywhere. The real runs need PowerShell: pwsh (PowerShell 7, also on
GitHub's Linux and macOS runners) and, on Windows, powershell.exe (Windows PowerShell 5.1,
what a fresh Windows has). They are skipped when neither is installed.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "install.ps1"
TEXT = SCRIPT.read_text("utf-8")


def _code_lines():
    """The script without its comment-based help block and # comments."""
    text = re.sub(r"<#.*?#>", "", TEXT, flags=re.S)
    return [line.split("#", 1)[0] for line in text.splitlines()]


def test_script_is_ascii():
    # Windows PowerShell 5.1 reads a file without a BOM as ANSI, so accents would turn into garbage
    bad = [n for n, line in enumerate(TEXT.splitlines(), 1) if not line.isascii()]
    assert not bad, f"non-ASCII characters on lines {bad}"


@pytest.mark.parametrize("pattern, what", [
    (r"\?\?", "?? (null-coalescing)"),
    (r"\?\.", "?. (null-conditional)"),
    (r"&&|\|\|", "&& / || pipeline chains"),
    (r"\s\?\s[^:]+\s:\s", "ternary a ? b : c"),
])
def test_no_powershell7_only_syntax(pattern, what):
    hits = [line.strip() for line in _code_lines() if re.search(pattern, line)]
    assert not hits, f"{what} does not exist in Windows PowerShell 5.1: {hits}"


def test_exit_only_when_run_as_a_file():
    # with `irm ... | iex`, a bare exit closes the user's PowerShell window
    exits = [line.strip() for line in _code_lines() if re.search(r"\bexit\b", line)]
    assert exits == ["if ($PSCommandPath) { exit $code }"]


def test_python_range_matches_doctor():
    # install.ps1 picks a Python in the range doctor.py accepts without warnings
    sys.path.insert(0, str(SCRIPT.parent / "skills" / "digest" / "scripts"))
    import doctor

    newest = re.search(r"\$MaxPython = \[version\]'(\d+)\.(\d+)'", TEXT).groups()
    oldest = re.search(r"\$MinPython = \[version\]'(\d+)\.(\d+)'", TEXT).groups()
    assert tuple(map(int, newest)) == doctor.MAX_PYTHON
    assert tuple(map(int, oldest)) == doctor.MIN_PYTHON


def test_documents_both_ways_to_run_it():
    raw = "https://raw.githubusercontent.com/ArmasCitoZ/saved-reels-digest/main/install.ps1"
    assert f"irm {raw} | iex" in TEXT
    assert "-File install.ps1" in TEXT


def _shells():
    names = ["pwsh"] + (["powershell"] if sys.platform == "win32" else [])
    return [pytest.param(n, marks=pytest.mark.skipif(not shutil.which(n), reason=f"{n} not installed"))
            for n in names]


def _run(shell, home, *args):
    env = {**os.environ, "SRD_HOME": str(home)}
    return subprocess.run([shutil.which(shell) or shell, "-NoProfile", "-NonInteractive",
                           "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT), *args],
                          capture_output=True, text=True, env=env, timeout=300, check=False)


@pytest.mark.parametrize("shell", _shells())
def test_check_only_runs_doctor_and_installs_nothing(shell, tmp_path):
    r = _run(shell, tmp_path / "srd", "-CheckOnly")
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "Using Python 3." in out
    assert "python " in out and "Ready." in out  # doctor.py's report
    assert "nothing was installed" in out
    assert not (tmp_path / "srd" / ".venv").exists()


@pytest.mark.parametrize("shell", _shells())
def test_check_only_fails_when_doctor_fails(shell, tmp_path):
    # SRD_HOME inside a file cannot be created: doctor.py's workspace check fails
    blocker = tmp_path / "srd"
    blocker.write_text("not a folder")
    r = _run(shell, blocker / "inside", "-CheckOnly")
    out = r.stdout + r.stderr
    assert r.returncode == 1, out
    assert "FAIL" in out and "Fix the FAIL lines" in out
