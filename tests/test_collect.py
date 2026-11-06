"""Tests for reading Instagram's official data export (collect.py export)."""
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"

SAVED_POSTS = {"saved_saved_media": [
    {"title": "creator_ai", "string_map_data": {"Saved on": {
        "href": "https://www.instagram.com/reel/DAbc123xyz/", "timestamp": 1761600000}}},
    {"title": "chef", "string_map_data": {"Saved on": {
        "href": "https://www.instagram.com/p/CPasta999/", "timestamp": 1761500000}}},
]}
COLLECTIONS = {"saved_saved_collections": [
    {"title": "Collection", "string_map_data": {"Name": {"value": "Tech"}}},
    {"title": "creator_ai", "string_map_data": {"Name": {
        "href": "https://www.instagram.com/reel/DAbc123xyz/"}}},
]}


def run(home, *args):
    r = subprocess.run([sys.executable, str(SCRIPTS / "collect.py"), *args],
                       env={**os.environ, "SRD_HOME": str(home)}, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads((home / "reels.json").read_text())["reels"]


def make_export(root):
    d = root / "export" / "your_instagram_activity" / "saved"
    d.mkdir(parents=True)
    (d / "saved_posts.json").write_text(json.dumps(SAVED_POSTS))
    (d / "saved_collections.json").write_text(json.dumps(COLLECTIONS))
    return root / "export"


def test_folder_export_reads_links_authors_and_collections(tmp_path):
    reels = run(tmp_path / "home", "export", str(make_export(tmp_path)))
    assert set(reels) == {"DAbc123xyz", "CPasta999"}
    assert reels["DAbc123xyz"]["author"] == "creator_ai"
    assert reels["DAbc123xyz"]["collection"] == "Tech"
    assert reels["CPasta999"]["saved_at"] == 1761500000


def test_zip_export_and_rerun_adds_nothing_new(tmp_path):
    folder = make_export(tmp_path)
    zpath = tmp_path / "export.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        for f in folder.rglob("*.json"):
            z.write(f, f.relative_to(folder))
    home = tmp_path / "home"
    first = run(home, "export", str(zpath))
    second = run(home, "export", str(zpath))
    assert first.keys() == second.keys() and len(second) == 2


def test_html_export_falls_back_to_link_scan(tmp_path):
    page = tmp_path / "saved_posts.html"
    page.write_text('<a href="https://www.instagram.com/reel/DHtml0001/">x</a>'
                    '<a href="https://www.instagram.com/someone/p/DHtml0002/?igsh=1">y</a>')
    assert set(run(tmp_path / "home", "export", str(page))) == {"DHtml0001", "DHtml0002"}
