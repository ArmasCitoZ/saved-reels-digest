"""Marking digest ideas as tried / discarded (db.py mark / marks)."""
import json

import os
import subprocess
import sys

from test_db import SCRIPTS, make_db, reel, run


def run_failing(home, *args):
    env = {**os.environ, "SRD_HOME": str(home), "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, str(SCRIPTS / "db.py"), *args], env=env,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode != 0
    return r.stderr


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


def test_mark_todo_clears_and_unknown_slug_is_skipped(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"))
    run(tmp_path, "mark", "tried", "subagents")
    run(tmp_path, "mark", "todo", "subagents")
    assert entries(tmp_path) == {}
    out = run(tmp_path, "mark", "discarded", "subagents", "sub-agents")
    assert "Marked 1 entries" in out and "not linked to any reel (typo?): sub-agents" in out
    assert list(entries(tmp_path)) == ["subagents"]


def test_mark_with_only_unknown_slugs_changes_nothing(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"))
    r = run_failing(tmp_path, "mark", "tried", "sub-agents")
    assert "nothing was marked" in r and "sub-agents" in r and "Known ideas: subagents" in r
    assert entries(tmp_path) == {}


def test_mark_with_no_entries_yet_explains_the_order(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True))
    assert "db.py set entry" in run_failing(tmp_path, "mark", "tried", "subagents")


def test_todo_clears_a_mark_whose_reels_moved_to_another_idea(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"))
    run(tmp_path, "mark", "tried", "subagents")
    run(tmp_path, "set", "entry", "agents", "AAAAA1")
    run(tmp_path, "mark", "todo", "subagents")
    assert entries(tmp_path) == {}


def test_marks_when_empty(tmp_path):
    make_db(tmp_path, reel("AAAAA1"))
    assert "No ideas marked" in run(tmp_path, "marks")
