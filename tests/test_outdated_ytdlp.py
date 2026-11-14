"""When downloads stop with the errors of an outdated yt-dlp, say how to update it."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"))
import transcribe  # noqa: E402
from ig import outdated_ytdlp_hint  # noqa: E402

# what yt-dlp prints when Instagram or TikTok changed their pages
EXTRACTOR_BROKE = ("yt-dlp: ERROR: [Instagram] DAbc123: Unable to extract video url; please report "
                   "this issue on https://github.com/yt-dlp/yt-dlp/issues. Confirm you are on the "
                   "latest version using yt-dlp -U")


@pytest.mark.parametrize("msg", [
    EXTRACTOR_BROKE,
    "yt-dlp: ERROR: Unsupported URL: https://www.tiktok.com/@a/video/1",
    "yt-dlp: ERROR: [TikTok] 1: No video formats found!",
])
def test_outdated_ytdlp_errors_get_the_upgrade_hint(msg):
    assert "setup_env.py --upgrade" in outdated_ytdlp_hint(msg)


@pytest.mark.parametrize("msg", [
    "yt-dlp: no file downloaded | instaloader: not a video",
    "ffmpeg exited with code 1",
    "",
])
def test_other_errors_do_not(msg):
    assert outdated_ytdlp_hint(msg) == ""


class FailingFetcher:
    def __init__(self, *_):
        pass

    def download_audio(self, *_):
        raise RuntimeError(FailingFetcher.error)


@pytest.fixture
def run(monkeypatch):
    def _run(error):
        reels = {f"C{n}": {"shortcode": f"C{n}", "relevant": True} for n in range(8)}
        FailingFetcher.error = error
        monkeypatch.setattr(transcribe, "load_db", lambda: {"version": 1, "reels": reels})
        monkeypatch.setattr(transcribe, "save_db", lambda _db: None)
        monkeypatch.setattr(transcribe, "load_model", lambda *_: object())
        monkeypatch.setattr(transcribe, "Fetcher", FailingFetcher)
        monkeypatch.setattr(sys, "argv", ["transcribe.py"])
        with pytest.raises(SystemExit) as e:
            transcribe.main()
        return str(e.value)
    return _run


def test_transcribe_stop_suggests_upgrading_yt_dlp(run):
    out = run(EXTRACTOR_BROKE)
    assert out.startswith(f"STOPPED after {transcribe.MAX_CONSECUTIVE_FAILS} failures in a row")
    assert "setup_env.py --upgrade" in out


def test_transcribe_stop_for_other_reasons_does_not(run):
    out = run("ffmpeg exited with code 1")
    assert "STOPPED after" in out and "--upgrade" not in out
