"""Tests for collect.py urls: a pasted list of links from any supported platform."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "digest" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import collect  # noqa: E402

LINKS = """Saved this week:
https://www.instagram.com/reel/DAbc123xyz/?igsh=abc
https://www.tiktok.com/@demo.creator/video/7400000000000000003?lang=es
https://youtu.be/dQw4w9WgXcQ?si=xyz and https://www.youtube.com/shorts/aBcDeFgHiJk
https://www.instagram.com/p/DAbc123xyz/   (same post again)
https://www.instagram.com/demo.creator/
https://example.com/article
"""


def run(home, *args, stdin=None):
    r = subprocess.run([sys.executable, str(SCRIPTS / "collect.py"), *args], input=stdin,
                       env={**os.environ, "SRD_HOME": str(home), "PYTHONIOENCODING": "utf-8"},
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout, json.loads((home / "reels.json").read_text(encoding="utf-8"))["reels"]


def test_parse_links_keeps_order_and_skips_repeats():
    keys = [(k, p) for k, p, _ in collect.parse_links(LINKS)]
    assert keys == [("DAbc123xyz", "instagram"), ("tt7400000000000000003", "tiktok"),
                    ("ytdQw4w9WgXcQ", "youtube"), ("ytaBcDeFgHiJk", "youtube")]


def test_every_platform_gets_its_key_and_url(tmp_path):
    (tmp_path / "links.txt").write_text(LINKS, encoding="utf-8")
    out, reels = run(tmp_path, "urls", str(tmp_path / "links.txt"))
    assert sorted(reels) == ["DAbc123xyz", "tt7400000000000000003", "ytaBcDeFgHiJk", "ytdQw4w9WgXcQ"]
    assert reels["DAbc123xyz"]["url"] == "https://www.instagram.com/reel/DAbc123xyz/"
    assert "platform" not in reels["DAbc123xyz"]  # Instagram is the default, as in the other collectors
    tt = reels["tt7400000000000000003"]
    assert tt["url"] == "https://www.tiktok.com/@/video/7400000000000000003"
    assert tt["platform"] == "tiktok" and tt["is_video"] is True and tt["source"] == "urls"
    assert reels["ytdQw4w9WgXcQ"]["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert reels["ytdQw4w9WgXcQ"]["platform"] == "youtube"
    assert "Parsed 4 links (1 Instagram, 1 TikTok, 2 YouTube), 4 new" in out


def test_other_links_are_named_not_dropped_silently(tmp_path):
    out, _ = run(tmp_path, "urls", "-", stdin=LINKS)
    assert "Skipped 2 links" in out
    assert "https://www.instagram.com/demo.creator/" in out and "https://example.com/article" in out


def test_rerun_and_other_collectors_do_not_duplicate(tmp_path):
    run(tmp_path, "urls", "-", stdin=LINKS)
    out, reels = run(tmp_path, "urls", "-", stdin="https://m.tiktok.com/v/7400000000000000003.html\n")
    assert len(reels) == 4 and "0 new" in out
    assert "Skipped" not in out
