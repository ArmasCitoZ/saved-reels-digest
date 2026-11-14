"""Tests for the environment checks in doctor.py."""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import doctor  # noqa: E402
import pytest  # noqa: E402

MB = 1024 * 1024


def test_python_version_gate():
    assert doctor.check_python((3, 8, 18))["status"] == "fail"
    assert doctor.check_python((3, 9, 0))["status"] == "ok"
    assert "3.13.1" in doctor.check_python((3, 13, 1))["detail"]


def test_python_newer_than_the_dependencies_is_a_warning():
    newest = doctor.MAX_PYTHON
    assert doctor.check_python((*newest, 0))["status"] == "ok"
    too_new = doctor.check_python((newest[0], newest[1] + 1, 2))
    assert too_new["status"] == "warn"
    assert f"install Python {newest[0]}.{newest[1]}" in too_new["detail"]


def test_disk_needs_more_on_first_run(tmp_path):
    free = 800 * MB
    assert doctor.check_disk(tmp_path, free)["status"] == "fail"  # no .venv yet
    (tmp_path / ".venv").mkdir()
    assert doctor.check_disk(tmp_path, free)["status"] == "ok"
    assert doctor.check_disk(tmp_path, 400 * MB)["status"] == "warn"
    assert doctor.check_disk(tmp_path, 100 * MB)["status"] == "fail"


def test_disk_works_before_workspace_exists(tmp_path):
    assert doctor.check_disk(tmp_path / "not" / "yet")["status"] in ("ok", "warn", "fail")


def test_workspace_is_created_and_writable(tmp_path):
    home = tmp_path / "srd"
    assert doctor.check_workspace(home)["status"] == "ok"
    assert home.is_dir() and not list(home.iterdir())  # probe file cleaned up


def test_workspace_that_is_a_file_fails(tmp_path):
    blocker = tmp_path / "srd"
    blocker.write_text("not a folder")
    assert doctor.check_workspace(blocker)["status"] == "fail"


def test_missing_venv_is_only_a_warning(tmp_path):
    r = doctor.check_venv(tmp_path)
    assert r["status"] == "warn" and "setup_env.py" in r["detail"]


@pytest.mark.skipif(os.name == "nt", reason="needs a symlinked interpreter")
def test_venv_reports_missing_packages(tmp_path):
    py = doctor.venv_python(tmp_path / ".venv")
    py.parent.mkdir(parents=True)
    py.symlink_to(sys.executable)
    r = doctor.check_venv(tmp_path)
    # the test interpreter does not have the plugin's heavy dependencies
    assert r["status"] == "fail" and "faster_whisper" in r["detail"]


def test_ffmpeg_is_optional():
    assert doctor.check_ffmpeg(lambda _: None)["status"] == "ok"
    assert doctor.check_ffmpeg(lambda _: "/usr/bin/ffmpeg")["detail"] == "/usr/bin/ffmpeg"


def test_cli_json_output(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPTS / "doctor.py"), "--json"],
                       env={**os.environ, "SRD_HOME": str(tmp_path)},
                       capture_output=True, text=True, check=False)
    report = json.loads(r.stdout)
    names = [c["name"] for c in report["checks"]]
    assert names == ["python", "workspace", "disk", "ram", "venv", "ffmpeg"]
    assert r.returncode == (0 if report["ok"] else 1)


def test_ram_check_recommends_a_model():
    assert doctor.check_ram(16 * 1024 * MB)["whisper_model"] == "small"
    low = doctor.check_ram(3 * 1024 * MB)
    assert low["status"] == "warn" and low["whisper_model"] == "tiny"


def test_ytdlp_release_date_from_version():
    import datetime as dt
    assert doctor.release_date("2025.10.22") == dt.date(2025, 10, 22)
    assert doctor.release_date("2025.10.22.234518") == dt.date(2025, 10, 22)  # nightly
    assert doctor.release_date("1.2") is None
    assert doctor.release_date("2025.13.40") is None


def test_ytdlp_older_than_two_months_is_a_warning():
    import datetime as dt
    today = dt.date(2026, 11, 14)
    assert doctor.check_ytdlp("2026.10.01", today)["status"] == "ok"
    old = doctor.check_ytdlp("2026.03.01", today)
    assert old["status"] == "warn"
    assert "8 months old" in old["detail"] and "--upgrade" in old["detail"]
    assert "-Upgrade" in old["detail"]


def test_ytdlp_unknown_version():
    assert doctor.check_ytdlp(None)["status"] == "warn"
    assert doctor.check_ytdlp("dev")["status"] == "ok"  # not a date: nothing to compare


def test_ytdlp_is_only_checked_with_a_complete_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(doctor, "check_venv", lambda home: {"name": "venv", "status": "warn", "detail": ""})
    assert "yt-dlp" not in [c["name"] for c in doctor.run_checks(tmp_path)]
    monkeypatch.setattr(doctor, "check_venv", lambda home: {"name": "venv", "status": "ok", "detail": ""})
    monkeypatch.setattr(doctor, "ytdlp_version", lambda home: "2000.01.01")
    names = [c["name"] for c in doctor.run_checks(tmp_path)]
    assert names.index("yt-dlp") == names.index("venv") + 1


@pytest.mark.skipif(os.name == "nt", reason="the fake venv python is a shell script")
def test_ytdlp_version_is_read_from_the_environment(tmp_path):
    assert doctor.ytdlp_version(tmp_path) is None  # no environment
    py = doctor.venv_python(tmp_path / ".venv")
    py.parent.mkdir(parents=True)
    py.write_text("#!/bin/sh\necho 2026.09.30\n")
    py.chmod(0o755)
    assert doctor.ytdlp_version(tmp_path) == "2026.09.30"
