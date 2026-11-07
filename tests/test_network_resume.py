"""Network drops: classified apart, retried, and never mark a reel as permanently failed."""
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import transcribe  # noqa: E402
from ig import NetworkError, _raise_for, classify_error  # noqa: E402


@pytest.mark.parametrize("msg", [
    "yt-dlp: <urlopen error [Errno -3] Temporary failure in name resolution> | "
    "instaloader: HTTPSConnectionPool: Max retries exceeded",
    "yt-dlp: The read operation timed out",
    "yt-dlp: [Errno 101] Network is unreachable",
    "yt-dlp: Connection reset by peer | instaloader: Connection aborted",
])
def test_connection_problems_are_network(msg):
    assert classify_error(msg) == "network"
    with pytest.raises(NetworkError):
        _raise_for(msg)


def test_one_real_answer_means_it_is_not_the_network():
    # instaloader timed out, but yt-dlp reached the server and got a real error
    assert classify_error("yt-dlp: Unable to extract video url | instaloader: timed out") == "failed"
    assert classify_error("yt-dlp: HTTP Error 404: Not Found | instaloader: timed out") == "unavailable"
    assert classify_error("yt-dlp: timed out | instaloader: 429 Too Many Requests") == "blocked"


class FlakyFetcher:
    def __init__(self, drops):
        self.drops, self.calls = drops, 0

    def download_audio(self, shortcode, folder, url=None):
        self.calls += 1
        if self.calls <= self.drops:
            raise NetworkError("Network is unreachable")
        return folder / f"{shortcode}.m4a"


def test_short_drop_is_waited_out():
    waited = []
    f = FlakyFetcher(drops=2)
    got = transcribe.fetch_with_retry(f, {"shortcode": "AAAAA1"}, Path("tmp"),
                                      waits=(1, 2, 3), sleep=waited.append)
    assert got == Path("tmp") / "AAAAA1.m4a"
    assert f.calls == 3 and waited == [1, 2]


def test_long_outage_gives_up_after_the_last_wait():
    waited = []
    f = FlakyFetcher(drops=99)
    with pytest.raises(NetworkError):
        transcribe.fetch_with_retry(f, {"shortcode": "AAAAA1"}, Path("tmp"),
                                    waits=(1, 2), sleep=waited.append)
    assert f.calls == 3 and waited == [1, 2]


def test_resume_selects_only_unfinished_reels():
    base = {"relevant": True, "is_video": True}
    reels = {
        "done": {**base, "transcript": "hola", "transcribe": "ok"},
        "pending": dict(base),
        "old_network_fail": {**base, "transcribe": "failed",
                             "transcribe_error": "yt-dlp: Temporary failure in name resolution"},
        "real_fail": {**base, "transcribe": "failed", "transcribe_error": "Unable to extract"},
        "photo": {**base, "is_video": False},
        "gone": {**base, "meta": "unavailable"},
        "off_topic": {"relevant": False, "is_video": True},
    }
    todo = [k for k, r in reels.items() if transcribe.needs_transcript(r)]
    assert todo == ["pending", "old_network_fail"]
    assert "off_topic" in [k for k, r in reels.items() if transcribe.needs_transcript(r, everything=True)]
