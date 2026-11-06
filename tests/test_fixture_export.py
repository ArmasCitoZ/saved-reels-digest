"""End-to-end import of the anonymized Instagram export in tests/fixtures/."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "digest" / "scripts"
FIXTURE = ROOT / "tests" / "fixtures" / "instagram_export"

SAVED = {"DFixAi0001", "DFixAi0002", "DFixDev003", "DFixFood04", "DFixTrip05"}


def run_export(home, path):
    r = subprocess.run([sys.executable, str(SCRIPTS / "collect.py"), "export", str(path)],
                       env={**os.environ, "SRD_HOME": str(home)},
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    return r.stdout, json.loads((home / "reels.json").read_text(encoding="utf-8"))["reels"]


def test_fixture_folder_imports_every_saved_post_and_nothing_else(tmp_path):
    out, reels = run_export(tmp_path, FIXTURE)
    assert set(reels) == SAVED  # the liked post DLiked0099 is not picked up
    assert "5 new" in out


def test_fixture_keeps_authors_dates_and_collections(tmp_path):
    _, reels = run_export(tmp_path, FIXTURE)
    assert reels["DFixAi0002"]["author"] == "demo_ai_tips"
    assert reels["DFixTrip05"]["saved_at"] == 1761523200
    assert reels["DFixAi0001"]["collection"] == "IA"
    assert reels["DFixDev003"]["collection"] == "IA"
    assert reels["DFixFood04"]["collection"] == "Recetas"  # Spanish-keyed export
    assert "collection" not in reels["DFixTrip05"]
    assert all(r["source"] == "export" for r in reels.values())


def test_fixture_as_zip_matches_folder(tmp_path):
    archive = shutil.make_archive(str(tmp_path / "instagram-demo"), "zip", FIXTURE)
    _, from_zip = run_export(tmp_path / "zip", archive)
    _, from_dir = run_export(tmp_path / "dir", FIXTURE)
    strip = lambda reels: {k: {f: v for f, v in r.items() if f != "added_at"}  # noqa: E731
                           for k, r in reels.items()}
    assert strip(from_zip) == strip(from_dir)
