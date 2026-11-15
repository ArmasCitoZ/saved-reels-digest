"""db.py rename: move an idea's reels and mark to another slug."""
import json

from test_db import make_db, reel, run
from test_marks import run_failing


def db(home):
    return json.loads((home / "reels.json").read_text(encoding="utf-8"))


def entry_of(home):
    return {code: r.get("entry") for code, r in db(home)["reels"].items()}


def test_rename_moves_reels_and_mark(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="sub-agents"),
            reel("BBBBB2", relevant=True, entry="sub-agents"),
            reel("CCCCC3", relevant=True, entry="mcp-servers"))
    run(tmp_path, "mark", "tried", "sub-agents", "--note", "worked")
    out = run(tmp_path, "rename", "sub-agents", "subagents")
    assert "Moved 2 reels from 'sub-agents' to 'subagents'." in out and "mark moved too" in out
    assert entry_of(tmp_path) == {"AAAAA1": "subagents", "BBBBB2": "subagents", "CCCCC3": "mcp-servers"}
    marks = db(tmp_path)["entries"]
    assert list(marks) == ["subagents"] and marks["subagents"]["note"] == "worked"


def test_merging_into_a_marked_idea_keeps_its_mark(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="hooks"),
            reel("BBBBB2", relevant=True, entry="claude-hooks"))
    run(tmp_path, "mark", "discarded", "hooks")
    run(tmp_path, "mark", "tried", "claude-hooks")
    out = run(tmp_path, "rename", "hooks", "claude-hooks")
    assert "merged with the 1 already there" in out
    assert "Kept the tried mark of 'claude-hooks' and dropped the discarded mark of 'hooks'" in out
    assert set(entry_of(tmp_path).values()) == {"claude-hooks"}
    assert db(tmp_path)["entries"] == {"claude-hooks": db(tmp_path)["entries"]["claude-hooks"]}
    assert db(tmp_path)["entries"]["claude-hooks"]["status"] == "tried"


def test_a_mark_without_reels_can_still_be_renamed(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"))
    data = db(tmp_path)
    data["entries"] = {"old": {"status": "discarded", "updated": 1761600000}}
    (tmp_path / "reels.json").write_text(json.dumps(data), encoding="utf-8")
    assert "Moved 0 reels" in run(tmp_path, "rename", "old", "subagents")
    assert list(db(tmp_path)["entries"]) == ["subagents"]


def test_unknown_or_invalid_slugs_change_nothing(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"))
    before = (tmp_path / "reels.json").read_text(encoding="utf-8")
    err = run_failing(tmp_path, "rename", "sub-agents", "agents")
    assert "nothing was renamed" in err and "Known ideas: subagents" in err
    assert "not a valid slug" in run_failing(tmp_path, "rename", "subagents", "two words")
    assert "the same" in run_failing(tmp_path, "rename", "subagents", "subagents")
    assert (tmp_path / "reels.json").read_text(encoding="utf-8") == before


def test_accented_slugs_are_valid(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="automatizacion"))
    run(tmp_path, "rename", "automatizacion", "automatización")
    assert entry_of(tmp_path) == {"AAAAA1": "automatización"}
