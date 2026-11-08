"""collect.py live: when Instagram cuts the read short, what was read must survive."""
import sys
import types
from argparse import Namespace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"))
import collect  # noqa: E402


def post(code):
    return types.SimpleNamespace(shortcode=code, caption=f"caption {code}", owner_username="demo",
                                 is_video=True, video_duration=30.0)


@pytest.fixture
def live(monkeypatch):
    """Run cmd_live against a saved feed that yields posts, or raises where an exception is listed."""
    def _live(feed):
        def saved_posts():
            for item in feed:
                if isinstance(item, Exception):
                    raise item
                yield post(item)

        profile = types.SimpleNamespace(get_saved_posts=saved_posts)
        fake = types.SimpleNamespace(Profile=types.SimpleNamespace(from_username=lambda *_: profile))
        db, saves = {"reels": {}}, []
        monkeypatch.setitem(sys.modules, "instaloader", fake)
        session = (types.SimpleNamespace(context=None), "me")
        monkeypatch.setattr(collect, "_instaloader_session", lambda _a: session)
        monkeypatch.setattr(collect, "load_db", lambda: db)
        monkeypatch.setattr(collect, "save_db", lambda d: saves.append(set(d["reels"])))
        monkeypatch.setattr(collect.time, "sleep", lambda _s: None)
        args = Namespace(limit=0, stop_at_known=False)
        return args, db, saves
    return _live


def test_rate_limit_keeps_what_was_read_and_says_why(live):
    args, db, saves = live(["AAAAA1", "AAAAA2", RuntimeError("429 Too Many Requests")])
    with pytest.raises(SystemExit) as e:
        collect.cmd_live(args)
    assert set(db["reels"]) == {"AAAAA1", "AAAAA2"} and saves[-1] == {"AAAAA1", "AAAAA2"}
    assert "rate-limiting" in str(e.value) and "2 new" in str(e.value)


def test_lost_connection_is_told_apart_from_a_block(live):
    args, _, saves = live(["AAAAA1", ConnectionError("Connection reset by peer")])
    with pytest.raises(SystemExit) as e:
        collect.cmd_live(args)
    assert "no connection" in str(e.value) and saves


def test_a_complete_read_is_unchanged(live, capsys):
    args, db, _ = live(["AAAAA1", "AAAAA2"])
    collect.cmd_live(args)
    assert len(db["reels"]) == 2
    assert "Read 2 saved posts from @me, 2 new" in capsys.readouterr().out
