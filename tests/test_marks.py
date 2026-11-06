"""Marking digest ideas as tried / discarded (db.py mark / marks)."""
import json

from test_db import make_db, reel, run


def entries(home):
    return json.loads((home / "reels.json").read_text(encoding="utf-8")).get("entries", {})


def test_mark_records_status_and_note_and_keeps_reels(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp-servers"))
    out = run(tmp_path, "mark", "tried", "subagents", "--note", "worked for refactors")
    assert "Marked 1 entries as tried." in out and "typo" not in out
    run(tmp_path, "mark", "discarded", "mcp-servers")
    e = entries(tmp_path)
    assert e["subagents"]["status"] == "tried" and e["subagents"]["note"] == "worked for refactors"
    assert e["mcp-servers"]["status"] == "discarded" and "note" not in e["mcp-servers"]
    listing = run(tmp_path, "marks")
    assert "tried" in listing and "subagents" in listing and "worked for refactors" in listing
    assert listing.index("discarded") < listing.index("tried")  # grouped by status
    # reels themselves are untouched, so new reels still merge into the same entry
    assert '"entry": "subagents"' in run(tmp_path, "show", "AAAAA1")


def test_mark_todo_clears_and_unknown_slug_warns(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"))
    run(tmp_path, "mark", "tried", "subagents")
    run(tmp_path, "mark", "todo", "subagents")
    assert entries(tmp_path) == {}
    out = run(tmp_path, "mark", "discarded", "sub-agents")
    assert "Not linked to any reel yet (typo?): sub-agents" in out
    assert entries(tmp_path)["sub-agents"]["status"] == "discarded"


def test_marks_when_empty(tmp_path):
    make_db(tmp_path, reel("AAAAA1"))
    assert "No ideas marked" in run(tmp_path, "marks")
