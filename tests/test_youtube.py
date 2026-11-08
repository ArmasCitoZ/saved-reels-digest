"""Tests for collecting YouTube Watch Later and playlists (collect.py youtube)."""
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "digest" / "scripts"
FIXTURE = ROOT / "tests" / "fixtures" / "youtube_export"
sys.path.insert(0, str(SCRIPTS))
import collect  # noqa: E402


def run(home, *args):
    r = subprocess.run([sys.executable, str(SCRIPTS / "collect.py"), *args],
                       env={**os.environ, "SRD_HOME": str(home), "PYTHONIOENCODING": "utf-8"},
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout, json.loads((home / "reels.json").read_text(encoding="utf-8"))["reels"]


def test_folder_reads_every_playlist_once_and_ignores_the_rest(tmp_path):
    out, reels = run(tmp_path, "youtube", str(FIXTURE))
    assert sorted(reels) == ["ytaaaaaaaaaa1", "ytbbbbbbbb-b2", "ytcccccccc_c3"]
    r = reels["ytaaaaaaaaaa1"]
    assert r["url"] == "https://www.youtube.com/watch?v=aaaaaaaaaa1"
    assert r["platform"] == "youtube" and r["is_video"] is True
    assert r["collection"] == "Watch later" and r["saved_at"] == 1792487700
    assert reels["ytcccccccc_c3"]["collection"] == "Ideas de IA"
    assert "Read 3 YouTube videos" in out and "3 new" in out


def test_zip_and_rerun_add_nothing_twice(tmp_path):
    z = tmp_path / "takeout.zip"
    src = FIXTURE / "playlists" / "Watch later-videos.csv"
    with zipfile.ZipFile(z, "w") as f:
        f.write(src, "Takeout/YouTube and YouTube Music/playlists/Watch later-videos.csv")
    run(tmp_path / "home", "youtube", str(z))
    out, reels = run(tmp_path / "home", "youtube", str(z))
    assert len(reels) == 2 and "0 new" in out


def test_pointing_straight_at_the_playlists_folder(tmp_path):
    _, reels = run(tmp_path, "youtube", str(FIXTURE / "playlists"))
    assert len(reels) == 3


def test_playlist_filter(tmp_path):
    _, reels = run(tmp_path, "youtube", str(FIXTURE), "--playlist", "ideas de ia")
    assert sorted(reels) == ["ytbbbbbbbb-b2", "ytcccccccc_c3"]


def test_headers_in_any_language_and_old_preamble():
    text = ("Playlist Id,Channel Id,Time Created\n"
            "PLdemo000000000000000000000000000a,UCdemo0000000000000000000,2026-01-01\n\n"
            "ID de vídeo,Marca de tiempo\n"
            "aaaaaaaaaa1,2026-10-20 09:15:00 UTC\n"
            "tooshort,2026-10-20T09:15:00+00:00\n"
            "bbbbbbbbbb2,not a date\n")
    assert collect.parse_youtube_csv(text) == [{"id": "aaaaaaaaaa1", "saved_at": 1792487700}]


def test_playlist_names_and_which_files_count():
    assert collect.playlist_name("Takeout/x/Watch later-videos.csv") == "Watch later"
    assert collect.playlist_name("Ver más tarde-vídeos.csv") == "Ver más tarde"
    assert collect.playlist_name("Watch later videos.csv") == "Watch later"
    assert collect._is_playlist_csv("Takeout/YouTube/listas de reproducción/IA-vídeos.csv")
    assert collect._is_playlist_csv("Watch later videos.csv")
    assert not collect._is_playlist_csv("Takeout/YouTube/playlists/playlists.csv")
    assert not collect._is_playlist_csv("Takeout/YouTube/subscriptions/subscriptions.csv")


def test_export_without_playlists_explains_what_to_download(tmp_path):
    (tmp_path / "empty").mkdir()
    out, reels = run(tmp_path / "home", "youtube", str(tmp_path / "empty"))
    assert reels == {} and "No playlist videos found" in out
