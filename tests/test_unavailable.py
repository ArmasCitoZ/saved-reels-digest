"""Deleted or private posts: error classification (ig.py) and how db.py treats them."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"))
from ig import Blocked, Unavailable, _raise_for, classify_error  # noqa: E402
from test_db import load, make_db, reel, run  # noqa: E402


@pytest.mark.parametrize("msg", [
    "yt-dlp: ERROR: [Instagram] C1: HTTP Error 404: Not Found",
    "instaloader: Post does not exist",
    "yt-dlp: This content isn't available | instaloader: Profile is private",
    "This post has been removed",
])
def test_deleted_or_private_posts_are_unavailable(msg):
    assert classify_error(msg) == "unavailable"
    with pytest.raises(Unavailable):
        _raise_for(msg)


@pytest.mark.parametrize("msg", [
    "yt-dlp: login required | instaloader: 401 Unauthorized",
    "HTTP Error 429: Too Many Requests",
    # rate limiting must stop the run even if it also says "not available"
    "Requested content is not available, rate-limit reached or login required",
])
def test_rate_limits_and_logins_still_block(msg):
    assert classify_error(msg) == "blocked"
    with pytest.raises(Blocked):
        _raise_for(msg)


def test_other_errors_are_plain_failures():
    assert classify_error("yt-dlp: Unable to extract video url | instaloader: timed out") == "failed"
    with pytest.raises(RuntimeError):
        _raise_for("connection reset")


def test_db_lists_unavailable_and_skips_them_in_triage(tmp_path):
    make_db(tmp_path, reel("AAAAA1", caption="claude tip"),
            reel("GONE01", meta="unavailable", author="ghost", collection="IA"))
    out = run(tmp_path, "unavailable")
    assert "1 saved posts are deleted or private" in out
    assert "reel/GONE01/" in out and "@ghost" in out
    nxt = run(tmp_path, "next")
    assert "1 waiting" in nxt and "GONE01" not in nxt
    status = run(tmp_path, "status")
    assert any(ln.split()[-1] == "1" for ln in status.splitlines() if "deleted or private" in ln)
    assert load(tmp_path)["GONE01"]["meta"] == "unavailable"


def test_db_unavailable_when_none(tmp_path):
    make_db(tmp_path, reel("AAAAA1"))
    assert "No deleted or private posts" in run(tmp_path, "unavailable")


def test_deleted_post_without_text_is_not_waiting_for_the_digest(tmp_path):
    make_db(tmp_path, reel("GONE01", relevant=True, meta="unavailable"),
            reel("GONE02", relevant=True, meta="unavailable", caption="read before it was deleted"),
            reel("LIVE01", relevant=True, caption="still here"))
    assert "GONE01" not in run(tmp_path, "dump")
    assert "GONE02" in run(tmp_path, "dump")
    pending = [ln for ln in run(tmp_path, "status").splitlines() if "not yet in digest" in ln][0]
    assert pending.split()[-1] == "2"
