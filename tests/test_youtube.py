"""Tests for collecting YouTube Watch Later and playlists (collect.py youtube)."""
import json
import os
import subprocess
import sys
import types
import zipfile
from argparse import Namespace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "digest" / "scripts"
FIXTURE = ROOT / "tests" / "fixtures" / "youtube_export"
sys.path.insert(0, str(SCRIPTS))
import collect  # noqa: E402
import ig  # noqa: E402
import transcribe  # noqa: E402


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


# --------------------------------------------------------------- --url (yt-dlp)
ENTRIES = [{"id": "aaaaaaaaaa1", "title": "Cursor vs Claude", "channel": "demo_dev", "duration": 300},
           {"id": "bbbbbbbbbb2", "title": "[Private video]"},
           {"id": "cccccccccc3", "title": "[Deleted video]"},
           None,
           {"id": "PLnested", "title": "not a video id"}]


@pytest.fixture
def fake_ytdlp(monkeypatch):
    calls = {}

    class YDL:
        def __init__(self, opts):
            calls["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download):
            calls["url"], calls["download"] = url, download
            if calls.get("error"):
                raise RuntimeError(calls["error"])
            return {"title": "Watch later", "entries": ENTRIES}

    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=YDL))
    return calls


def test_url_lists_without_downloading_and_skips_gone_videos(fake_ytdlp):
    title, entries = collect.read_youtube_playlist("https://www.youtube.com/playlist?list=PLx")
    assert title == "Watch later" and [e["id"] for e in entries] == ["aaaaaaaaaa1"]
    assert fake_ytdlp["download"] is False and fake_ytdlp["opts"]["extract_flat"] == "in_playlist"
    assert "cookiesfrombrowser" not in fake_ytdlp["opts"]


def test_wl_shortcut_uses_the_browser_login(fake_ytdlp):
    collect.read_youtube_playlist("wl", "firefox")
    assert fake_ytdlp["url"].endswith("list=WL")
    assert fake_ytdlp["opts"]["cookiesfrombrowser"] == ("firefox",)


def test_url_failure_explains_login(fake_ytdlp):
    fake_ytdlp["error"] = "This playlist is private"
    with pytest.raises(SystemExit, match="--browser"):
        collect.read_youtube_playlist("WL")


def test_url_adds_videos_to_the_database(fake_ytdlp, monkeypatch, capsys):
    db = {"version": 1, "reels": {}}
    monkeypatch.setattr(collect, "load_db", lambda: db)
    monkeypatch.setattr(collect, "save_db", lambda d: None)
    collect.cmd_youtube(Namespace(path=None, url="WL", browser="chrome", playlist=None))
    r = db["reels"]["ytaaaaaaaaaa1"]
    assert r["url"] == "https://www.youtube.com/watch?v=aaaaaaaaaa1" and r["author"] == "demo_dev"
    assert r["collection"] == "Watch later" and r["duration"] == 300 and "saved_at" not in r
    assert "1 new" in capsys.readouterr().out


def test_path_and_url_are_exclusive():
    with pytest.raises(SystemExit, match="either"):
        collect.cmd_youtube(Namespace(path="x", url="WL", browser=None, playlist=None))
    with pytest.raises(SystemExit, match="either"):
        collect.cmd_youtube(Namespace(path=None, url=None, browser=None, playlist=None))


# ------------------------------------------------------------------ robustness
def test_youtube_bot_check_stops_the_run():
    assert ig.classify_error("yt-dlp: Sign in to confirm you're not a bot") == "blocked"


def test_long_videos_are_skipped_only_with_a_known_duration():
    assert transcribe.too_long({"duration": 3700}, 30)
    assert not transcribe.too_long({"duration": 1800}, 30)
    assert not transcribe.too_long({}, 30)  # no metadata yet: try it
    assert not transcribe.too_long({"duration": 3700}, 0)  # 0 turns the limit off
