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


def fails(home, *args):
    r = subprocess.run([sys.executable, str(SCRIPTS / "collect.py"), *args],
                       env={**os.environ, "SRD_HOME": str(home)}, capture_output=True, text=True)
    assert r.returncode != 0
    return r.stderr


def test_half_downloaded_zip_is_explained(tmp_path):
    good = tmp_path / "good.zip"
    with zipfile.ZipFile(good, "w") as z:
        z.writestr("your_instagram_activity/saved/saved_posts.json", json.dumps(SAVED_POSTS))
    cut = tmp_path / "instagram.zip"
    cut.write_bytes(good.read_bytes()[:40])
    for command in ("export", "tiktok", "youtube"):
        err = fails(tmp_path / "home", command, str(cut))
        assert "not a complete zip" in err and "download it again" in err and "Traceback" not in err
    assert not (tmp_path / "home" / "reels.json").exists()


def test_export_without_saved_posts_says_what_to_request(tmp_path):
    empty = tmp_path / "export"
    empty.mkdir()
    r = subprocess.run([sys.executable, str(SCRIPTS / "collect.py"), "export", str(empty)],
                       env={**os.environ, "SRD_HOME": str(tmp_path / "home")}, capture_output=True, text=True)
    assert r.returncode == 0 and "No saved posts found" in r.stdout


def test_collections_are_found_in_any_export_language(tmp_path):
    d = tmp_path / "export" / "saved"
    d.mkdir(parents=True)
    (d / "saved_collections.json").write_text(json.dumps({"saved_saved_collections": [
        {"title": "Coleção", "string_map_data": {"Nome": {"value": "Ideias"},
                                                 "Hora de criação": {"timestamp": 1750000000}}},
        {"title": "criador", "string_map_data": {"Nome": {
            "value": "criador", "href": "https://www.instagram.com/reel/DPort0001/"}}},
        {"title": "Sammlung", "string_map_data": {"Name": {"value": "Küche"}}},
        {"title": "koch", "string_map_data": {"Name": {
            "value": "koch", "href": "https://www.instagram.com/p/DGerm0002/"}}},
    ]}))
    reels = run(tmp_path / "home", "export", str(tmp_path / "export"))
    assert reels["DPort0001"]["collection"] == "Ideias" and reels["DPort0001"]["author"] == "criador"
    assert reels["DGerm0002"]["collection"] == "Küche"
