"""Tests for setup_env.py: create the environment once, skip pip when it is complete."""
import re
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import doctor  # noqa: E402
import setup_env  # noqa: E402


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_env, "ensure_home", lambda: tmp_path)
    py = setup_env.venv_python(tmp_path / ".venv")
    py.parent.mkdir(parents=True)
    py.write_text("")  # an existing environment; its packages are decided by check_venv below
    calls = []
    monkeypatch.setattr(setup_env.subprocess, "check_call", lambda cmd: calls.append(cmd))
    return calls, monkeypatch


def _venv_status(monkeypatch, status):
    monkeypatch.setattr(setup_env, "check_venv", lambda h: {"name": "venv", "status": status, "detail": ""})


def test_complete_environment_runs_no_pip(home, capsys):
    calls, monkeypatch = home
    _venv_status(monkeypatch, doctor.OK)
    setup_env.main([])
    assert calls == []
    assert "already complete" in capsys.readouterr().out


def test_missing_packages_are_installed(home, capsys):
    calls, monkeypatch = home
    _venv_status(monkeypatch, doctor.FAIL)
    setup_env.main([])
    assert any("-r" in c and "--upgrade" not in c for c in calls)
    assert "READY" in capsys.readouterr().out


def test_upgrade_updates_a_complete_environment(home):
    calls, monkeypatch = home
    _venv_status(monkeypatch, doctor.OK)
    setup_env.main(["--upgrade"])
    assert any("-r" in c and "--upgrade" in c for c in calls)


def test_doctor_checks_every_requirement():
    # "complete" means every package in requirements.txt imports; keep the two lists together
    names = {re.split(r"[<>=!~\[;\s]", line.strip(), maxsplit=1)[0].lower().replace("-", "_")
             for line in setup_env.REQ.read_text().splitlines()
             if line.strip() and not line.startswith("#")}
    assert names == set(doctor.REQUIRED_MODULES)


def test_upgrade_reports_the_yt_dlp_versions(home, capsys):
    calls, monkeypatch = home
    _venv_status(monkeypatch, doctor.OK)
    versions = iter(["2026.03.01", "2026.11.10"])
    monkeypatch.setattr(setup_env, "ytdlp_version", lambda h: next(versions))
    setup_env.main(["--upgrade"])
    assert "yt-dlp updated: 2026.03.01 -> 2026.11.10" in capsys.readouterr().out


def test_plain_install_does_not_read_yt_dlp(home):
    calls, monkeypatch = home
    _venv_status(monkeypatch, doctor.FAIL)
    monkeypatch.setattr(setup_env, "ytdlp_version", lambda h: pytest.fail("not needed"))
    setup_env.main([])


@pytest.mark.parametrize("before, after, expected", [
    ("2026.03.01", "2026.11.10", "updated: 2026.03.01 -> 2026.11.10"),
    ("2026.11.10", "2026.11.10", "already the newest release (2026.11.10)"),
    (None, "2026.11.10", "yt-dlp 2026.11.10"),
    ("2026.03.01", None, ""),
])
def test_ytdlp_change(before, after, expected):
    line = setup_env.ytdlp_change(before, after)
    assert expected in line if expected else line == ""
