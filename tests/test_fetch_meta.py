"""fetch_meta.py must stop before a throttled session marks the whole list as deleted."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"))
import fetch_meta  # noqa: E402
from ig import Unavailable  # noqa: E402


class FakeFetcher:
    """Answers each post in order: an exception to raise, or the metadata to return."""
    answers: list = []
    calls: list = []

    def __init__(self, *_):
        pass

    def metadata(self, shortcode, _url=None):
        FakeFetcher.calls.append(shortcode)
        answer = FakeFetcher.answers[len(FakeFetcher.calls) - 1]
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def run(monkeypatch):
    def _run(answers, *argv):
        db = {"reels": {f"C{n}": {"shortcode": f"C{n}", "url": None} for n in range(len(answers))}}
        FakeFetcher.answers, FakeFetcher.calls = answers, []
        monkeypatch.setattr(fetch_meta, "Fetcher", FakeFetcher)
        monkeypatch.setattr(fetch_meta, "load_db", lambda: db)
        monkeypatch.setattr(fetch_meta, "save_db", lambda _db: None)
        monkeypatch.setattr(sys, "argv", ["fetch_meta.py", *argv])
        return db
    return _run


GONE = Unavailable("yt-dlp: This content isn't available")
OK = {"caption": "a tip", "author": "someone"}


def test_a_long_run_of_deleted_posts_stops_the_run(run):
    run([GONE] * 12)
    with pytest.raises(SystemExit) as e:
        fetch_meta.main()
    assert len(FakeFetcher.calls) == fetch_meta.MAX_CONSECUTIVE_FAILS
    assert "in a row" in str(e.value) and "--retry-failed" in str(e.value)


def test_the_posts_before_the_stop_are_kept_for_the_next_run(run):
    db = run([GONE] * 12)
    with pytest.raises(SystemExit):
        fetch_meta.main()
    marked = [r for r in db["reels"].values() if r.get("meta") == "unavailable"]
    assert len(marked) == fetch_meta.MAX_CONSECUTIVE_FAILS  # the next run moves past them


def test_deleted_posts_mixed_with_good_ones_do_not_stop_it(run, capsys):
    db = run(([GONE] * 4 + [OK]) * 3)
    fetch_meta.main()
    assert len(FakeFetcher.calls) == 15
    assert db["reels"]["C4"]["meta"] == "ok"
    assert "3 ok, 12 deleted or private" in capsys.readouterr().out
