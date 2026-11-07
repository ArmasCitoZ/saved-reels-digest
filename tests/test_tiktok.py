"""Tests for reading TikTok's official data export (collect.py tiktok)."""
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "digest" / "scripts"
FIXTURE = ROOT / "tests" / "fixtures" / "tiktok_export"
sys.path.insert(0, str(SCRIPTS))
import collect  # noqa: E402
from common import shortcode_from_url, tiktok_id_from_url  # noqa: E402


def run(home, *args):
    r = subprocess.run([sys.executable, str(SCRIPTS / "collect.py"), *args],
                       env={**os.environ, "SRD_HOME": str(home), "PYTHONIOENCODING": "utf-8"},
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout, json.loads((home / "reels.json").read_text(encoding="utf-8"))["reels"]


def test_link_forms():
    for url in ("https://www.tiktok.com/@demo.creator/video/7400000000000000003?lang=es",
                "https://www.tiktokv.com/share/video/7400000000000000003/",
                "https://m.tiktok.com/v/7400000000000000003.html"):
        assert tiktok_id_from_url(url) == "7400000000000000003", url
    assert tiktok_id_from_url("https://www.instagram.com/reel/DAbc123xyz/") is None
    # TikTok links are not mistaken for Instagram shortcodes
    assert shortcode_from_url("https://www.tiktok.com/@a/video/7400000000000000003") is None


def test_folder_reads_only_favorites_with_dates(tmp_path):
    out, reels = run(tmp_path, "tiktok", str(FIXTURE))
    assert sorted(reels) == ["tt7400000000000000001", "tt7400000000000000002",
                             "tt7400000000000000003"]
    r = reels["tt7400000000000000001"]
    assert r["url"] == "https://www.tiktok.com/@/video/7400000000000000001"
    assert r["platform"] == "tiktok" and r["source"] == "tiktok" and r["is_video"] is True
    assert r["saved_at"] == 1793383451  # 2026-10-30 18:04:11 UTC
    assert "saved_at" not in reels["tt7400000000000000003"]  # bad date is dropped, not guessed
    assert "Read 3 TikTok favorites" in out and "3 new" in out


def test_zip_and_rerun_add_nothing_twice(tmp_path):
    z = tmp_path / "tiktok.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.write(FIXTURE / "user_data_tiktok.json", "TikTok_Data/user_data_tiktok.json")
    run(tmp_path / "home", "tiktok", str(z))
    out, reels = run(tmp_path / "home", "tiktok", str(z))
    assert len(reels) == 3 and "0 new" in out


def test_txt_export():
    text = ("Date: 2026-10-30 18:04:11\nLink: https://www.tiktokv.com/share/video/7400000000000000001/\n\n"
            "Date: 2026-10-31 08:00:00\nLink: https://www.tiktokv.com/share/video/7400000000000000002/\n")
    assert collect.parse_tiktok("Activity/Favorite Videos.txt", text) == [
        {"id": "7400000000000000001", "saved_at": 1793383451},
        {"id": "7400000000000000002", "saved_at": 1793433600}]


def test_mixes_with_instagram_in_one_database(tmp_path):
    (tmp_path / "links.txt").write_text("https://www.instagram.com/reel/DAbc123xyz/\n")
    run(tmp_path, "urls", str(tmp_path / "links.txt"))
    _, reels = run(tmp_path, "tiktok", str(FIXTURE))
    assert "DAbc123xyz" in reels and len(reels) == 4
    assert "platform" not in reels["DAbc123xyz"]


def test_export_without_favorites_explains_what_to_download(tmp_path):
    f = tmp_path / "user_data_tiktok.json"
    f.write_text('{"Your Activity": {"Like List": {"ItemFavoriteList": []}}}')
    out, reels = run(tmp_path / "home", "tiktok", str(f))
    assert reels == {} and "No favorite videos found" in out
