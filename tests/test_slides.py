"""Tests for reading photo and carousel posts (slides.py and Fetcher.download_images)."""
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import ig  # noqa: E402
import slides  # noqa: E402


def reel(code, **fields):
    return {"shortcode": code, "url": f"https://www.instagram.com/reel/{code}/",
            "relevant": True, "is_video": False, "author": "ana", **fields}


def run(home, *args, stdin=None):
    r = subprocess.run([sys.executable, str(SCRIPTS / "slides.py"), *args], input=stdin,
                       env={**os.environ, "SRD_HOME": str(home), "PYTHONIOENCODING": "utf-8"},
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout


def make_db(home, *reels):
    home.mkdir(parents=True, exist_ok=True)
    (home / "reels.json").write_text(
        json.dumps({"version": 1, "reels": {r["shortcode"]: r for r in reels}}), encoding="utf-8")


def load(home):
    return json.loads((home / "reels.json").read_text(encoding="utf-8"))["reels"]


class FakeFetcher:
    def __init__(self, result):
        self.result, self.calls = result, []

    def download_images(self, shortcode, folder, max_images):
        self.calls.append(shortcode)
        if isinstance(self.result, Exception):
            raise self.result
        folder.mkdir(parents=True)
        paths = [folder / f"{n:02d}.jpg" for n in range(1, self.result + 1)]
        for p in paths:
            p.write_bytes(b"img")
        return paths


@pytest.fixture(autouse=True)
def no_db_write(monkeypatch):
    monkeypatch.setattr(slides, "save_db", lambda db: None)


def test_only_relevant_image_posts_need_reading():
    assert slides.needs_reading(reel("A"))
    assert slides.needs_reading(reel("A", relevant="maybe"))
    assert not slides.needs_reading(reel("A", relevant=False))
    assert not slides.needs_reading(reel("A", relevant=None))
    assert not slides.needs_reading(reel("A", is_video=True))
    assert not slides.needs_reading(reel("A", is_video=None))  # metadata not fetched yet
    assert not slides.needs_reading(reel("A", slides_text="ya leído"))
    assert not slides.needs_reading(reel("A", slides="failed"))
    assert not slides.needs_reading(reel("A", meta="unavailable"))
    assert not slides.needs_reading(reel("tt1", url="https://www.tiktok.com/@/video/1"))
    assert not slides.needs_reading(reel("A", collection="IA"), "Otra")


def test_fetch_downloads_and_reuses_what_is_already_there(tmp_path):
    r = reel("AAAAA1")
    db = {"reels": {"AAAAA1": r}}
    f = FakeFetcher(2)
    out = slides.fetch_all(db, [r], f, tmp_path, 10)
    assert [p.name for p in out[0][1]] == ["01.jpg", "02.jpg"]
    again = slides.fetch_all(db, [r], f, tmp_path, 10)
    assert f.calls == ["AAAAA1"] and len(again[0][1]) == 2


def test_post_without_images_is_not_asked_for_again(tmp_path):
    r = reel("AAAAA1")
    assert slides.fetch_all({"reels": {}}, [r], FakeFetcher(0), tmp_path, 10) == []
    assert r["slides_text"] == "" and not slides.needs_reading(r)


def test_blocked_stops_the_run_at_once(tmp_path):
    rs = [reel("AAAAA1"), reel("BBBBB2")]
    f = FakeFetcher(ig.Blocked("429"))
    with pytest.raises(SystemExit, match="STOPPED"):
        slides.fetch_all({"reels": {}}, rs, f, tmp_path, 10)
    assert f.calls == ["AAAAA1"]


def test_network_drop_leaves_the_post_pending(tmp_path):
    r = reel("AAAAA1")
    with pytest.raises(SystemExit, match="no connection"):
        slides.fetch_all({"reels": {}}, [r], FakeFetcher(ig.NetworkError("timed out")), tmp_path, 10)
    assert slides.needs_reading(r)


def test_deleted_post_is_marked_and_repeated_failures_stop(tmp_path):
    r = reel("AAAAA1")
    assert slides.fetch_all({"reels": {}}, [r], FakeFetcher(ig.Unavailable("404")), tmp_path, 10) == []
    assert r["meta"] == "unavailable"
    rs = [reel(f"CODE{i}") for i in range(8)]
    f = FakeFetcher(RuntimeError("boom"))
    with pytest.raises(SystemExit, match="5 failures"):
        slides.fetch_all({"reels": {}}, rs, f, tmp_path, 10)
    assert len(f.calls) == 5 and rs[0]["slides"] == "failed"


def test_save_stores_text_and_deletes_images(tmp_path):
    make_db(tmp_path, reel("AAAAA1", slides="failed", slides_error="x"))
    folder = tmp_path / ".slides" / "AAAAA1"
    folder.mkdir(parents=True)
    (folder / "01.jpg").write_bytes(b"img")
    assert "Saved 4 characters" in run(tmp_path, "save", "AAAAA1", "  hola\n")
    r = load(tmp_path)["AAAAA1"]
    assert r["slides_text"] == "hola" and "slides" not in r and "slides_error" not in r
    assert not folder.exists()


def test_save_reads_stdin_and_pending_shrinks(tmp_path):
    make_db(tmp_path, reel("AAAAA1"), reel("BBBBB2"))
    assert "2 image posts" in run(tmp_path, "pending")
    run(tmp_path, "save", "AAAAA1", stdin="Paso 1\nPaso 2\n")
    assert load(tmp_path)["AAAAA1"]["slides_text"] == "Paso 1\nPaso 2"
    out = run(tmp_path, "pending")
    assert "1 image posts" in out and "BBBBB2" in out and "AAAAA1" not in out


def run_failing(home, *args, stdin=""):
    r = subprocess.run([sys.executable, str(SCRIPTS / "slides.py"), *args], input=stdin,
                       env={**os.environ, "SRD_HOME": str(home), "PYTHONIOENCODING": "utf-8"},
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode != 0
    return r.stderr


def post_with_images(home):
    make_db(home, reel("AAAAA1"))
    folder = home / ".slides" / "AAAAA1"
    folder.mkdir(parents=True)
    (folder / "01.jpg").write_bytes(b"img")
    return folder


@pytest.mark.parametrize("stdin", ["", "  \n\n"])
def test_empty_stdin_keeps_the_images_and_saves_nothing(tmp_path, stdin):
    folder = post_with_images(tmp_path)
    err = run_failing(tmp_path, "save", "AAAAA1", stdin=stdin)
    assert "--empty" in err and "kept" in err
    assert (folder / "01.jpg").exists()
    assert "slides_text" not in load(tmp_path)["AAAAA1"]


def test_empty_flag_marks_the_post_as_read(tmp_path):
    folder = post_with_images(tmp_path)
    assert "Saved 0 characters" in run(tmp_path, "save", "AAAAA1", "--empty")
    assert load(tmp_path)["AAAAA1"]["slides_text"] == ""
    assert not folder.exists()
    assert "0 image posts" in run(tmp_path, "pending")


def test_text_and_empty_flag_together_are_refused(tmp_path):
    folder = post_with_images(tmp_path)
    assert "not both" in run_failing(tmp_path, "save", "AAAAA1", "hola", "--empty")
    assert folder.exists()


@pytest.mark.parametrize("link", ["https://www.instagram.com/p/AAAAA1/?img_index=2",
                                  " https://instagram.com/ana/reel/AAAAA1 "])
def test_save_accepts_a_pasted_link(tmp_path, link):
    folder = post_with_images(tmp_path)
    assert "for AAAAA1" in run(tmp_path, "save", link, "hola")
    assert load(tmp_path)["AAAAA1"]["slides_text"] == "hola"
    assert not folder.exists()


def test_save_unknown_post_changes_nothing(tmp_path):
    folder = post_with_images(tmp_path)
    err = run_failing(tmp_path, "save", "https://www.instagram.com/p/ZZZZZ9/", "hola")
    assert "Unknown post" in err and "no images were deleted" in err
    assert folder.exists() and "slides_text" not in load(tmp_path)["AAAAA1"]


def test_download_images_handles_carousels_and_cleans_up(tmp_path, monkeypatch):
    nodes = [SimpleNamespace(is_video=False, display_url="u1"),
             SimpleNamespace(is_video=True, display_url="v"),
             SimpleNamespace(is_video=False, display_url="u2"),
             SimpleNamespace(is_video=False, display_url="u3")]
    post = SimpleNamespace(typename="GraphSidecar", is_video=False, get_sidecar_nodes=lambda: nodes)
    f = ig.Fetcher(delay=0)
    monkeypatch.setattr(f, "_il_post", lambda sc: post)
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)
    got = []

    def fetch(url, dest):
        got.append(url)
        Path(dest).write_bytes(b"img")

    monkeypatch.setattr(ig.urllib.request, "urlretrieve", fetch)
    paths = f.download_images("AAAAA1", tmp_path / "AAAAA1", max_images=2)
    assert got == ["u1", "u2"] and [p.name for p in paths] == ["01.jpg", "02.jpg"]

    def boom(url, dest):
        raise OSError("timed out")

    monkeypatch.setattr(ig.urllib.request, "urlretrieve", boom)
    with pytest.raises(ig.NetworkError):
        f.download_images("BBBBB2", tmp_path / "BBBBB2")
    assert not (tmp_path / "BBBBB2").exists()


def test_single_photo_post(monkeypatch):
    f = ig.Fetcher(delay=0)
    post = SimpleNamespace(typename="GraphImage", is_video=False, url="u")
    monkeypatch.setattr(f, "_il_post", lambda sc: post)
    assert f.image_urls("AAAAA1") == ["u"]


# ------------------------------------------------------------- db.py integration
def run_db(home, *args):
    r = subprocess.run([sys.executable, str(SCRIPTS / "db.py"), *args],
                       env={**os.environ, "SRD_HOME": str(home), "PYTHONIOENCODING": "utf-8"},
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_dump_and_maybe_triage_show_the_text_of_the_images(tmp_path):
    make_db(tmp_path, reel("AAAAA1", caption="desliza", slides_text="Paso 1: instala uv"),
            reel("BBBBB2", relevant="maybe", slides_text="Cinco atajos de Claude Code"))
    assert "IMAGES: Paso 1: instala uv" in run_db(tmp_path, "dump")
    assert "IMAGES: Cinco atajos" in run_db(tmp_path, "next", "--maybe")


def test_similar_compares_image_text_and_status_counts_it(tmp_path):
    text = "instala uv para gestionar entornos python rapido sin complicaciones"
    make_db(tmp_path, reel("AAAAA1", slides_text=text), reel("BBBBB2", transcript=text),
            reel("CCCCC3", caption="receta de lentejas con chorizo y pimentón"))
    out = run_db(tmp_path, "similar")
    assert "AAAAA1" in out and "BBBBB2" in out and "CCCCC3" not in out
    assert any(line.split() == ["images", "read", "1"] for line in run_db(tmp_path, "status").splitlines())
