"""transcribe.py --shortcodes: say which codes are unknown instead of silently doing nothing."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"))
import common  # noqa: E402
import transcribe  # noqa: E402

REELS = {
    "AAAAA1": {"shortcode": "AAAAA1"},
    "BBBBB2": {"shortcode": "BBBBB2"},
    "tt7300000000000000001": {"shortcode": "tt7300000000000000001"},
}


def codes(todo):
    return [r["shortcode"] for r in todo]


def test_known_codes_keep_their_order():
    todo, unknown = transcribe.pick_shortcodes(REELS, "BBBBB2,AAAAA1")
    assert codes(todo) == ["BBBBB2", "AAAAA1"] and unknown == []


def test_unknown_codes_are_reported():
    todo, unknown = transcribe.pick_shortcodes(REELS, "AAAAA1,ZZZZZ9,typo")
    assert codes(todo) == ["AAAAA1"] and unknown == ["ZZZZZ9", "typo"]


def test_spaces_empty_items_and_repeats_are_tolerated():
    todo, unknown = transcribe.pick_shortcodes(REELS, " AAAAA1, BBBBB2 ,,AAAAA1,")
    assert codes(todo) == ["AAAAA1", "BBBBB2"] and unknown == []


def test_pasted_links_are_accepted():
    spec = ("https://www.instagram.com/reel/AAAAA1/?igsh=xyz,"
            "https://www.tiktok.com/@someone/video/7300000000000000001")
    todo, unknown = transcribe.pick_shortcodes(REELS, spec)
    assert codes(todo) == ["AAAAA1", "tt7300000000000000001"] and unknown == []


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DB_PATH", tmp_path / "reels.json")
    monkeypatch.setattr(transcribe, "load_db", lambda: {"version": 1, "reels": dict(REELS)})
    monkeypatch.setattr(transcribe, "load_model", lambda *_: pytest.fail("no model should load"))
    return tmp_path


def test_all_unknown_stops_with_a_clear_message(home, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["transcribe.py", "--shortcodes", "ZZZZZ9"])
    with pytest.raises(SystemExit) as e:
        transcribe.main()
    assert "None of the --shortcodes" in str(e.value)
    assert "ZZZZZ9" in capsys.readouterr().err
