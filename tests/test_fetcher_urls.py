"""Fetcher (ig.py) uses each post's own URL, and keeps instaloader for Instagram only."""
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import ig  # noqa: E402

TIKTOK = "https://www.tiktok.com/@/video/7400000000000000001"


class FakeFetcher(ig.Fetcher):
    def __init__(self, ydl_error=None):
        super().__init__(delay=0)
        self.ydl_error, self.urls, self.il_calls = ydl_error, [], 0

    def _wait(self):
        pass

    def _ydl_info(self, shortcode, download_to=None, url=None):
        self.urls.append(url or ig.canonical_url(shortcode))
        if self.ydl_error:
            raise RuntimeError(self.ydl_error)
        return {"description": "tip", "channel": "demo_creator", "duration": 30, "_file": Path("x.m4a")}

    def _il_post(self, shortcode):
        self.il_calls += 1
        raise RuntimeError("instaloader failed too")


def test_tiktok_metadata_uses_its_own_url():
    f = FakeFetcher()
    meta = f.metadata("tt7400000000000000001", TIKTOK)
    assert f.urls == [TIKTOK]
    assert meta["author"] == "demo_creator" and meta["is_video"] is True


def test_instagram_still_uses_the_shortcode_url():
    f = FakeFetcher()
    f.download_audio("DAbc123xyz", Path("."))
    assert f.urls == ["https://www.instagram.com/reel/DAbc123xyz/"]


def test_tiktok_failure_never_falls_back_to_instaloader():
    f = FakeFetcher("Video not available")
    with pytest.raises(ig.Unavailable):
        f.metadata("tt7400000000000000001", TIKTOK)
    with pytest.raises(ig.Unavailable):
        f.download_audio("tt7400000000000000001", Path("."), TIKTOK)
    assert f.il_calls == 0


def test_instagram_failure_tries_instaloader():
    f = FakeFetcher("some extractor error")
    with pytest.raises(RuntimeError):
        f.metadata("DAbc123xyz", "https://www.instagram.com/reel/DAbc123xyz/")
    assert f.il_calls == 1
