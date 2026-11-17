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
    assert "nothing was renamed" in err and "Did you mean 'subagents'?" in err
    assert "Known ideas: subagents" in err
    assert "Did you mean" not in run_failing(tmp_path, "rename", "prompting", "agents")
    assert "not a valid slug" in run_failing(tmp_path, "rename", "subagents", "two words")
    assert "the same" in run_failing(tmp_path, "rename", "subagents", "subagents")
    assert (tmp_path / "reels.json").read_text(encoding="utf-8") == before


def test_accented_slugs_are_valid(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="automatizacion"))
    run(tmp_path, "rename", "automatizacion", "automatización")
    assert entry_of(tmp_path) == {"AAAAA1": "automatización"}


DIGEST = """# IA: my saved reels digest

## Do these first
1. **Subagents** → [entry](#sub-agents)

## Claude Code
### Subagents {#sub-agents}
Split big tasks. Pairs well with [hooks](#hooks).

### Hooks {#hooks}
Run commands on events. See [subagents](#sub-agents).
"""


def test_digest_flag_renames_heading_and_links(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="sub-agents"),
            reel("BBBBB2", relevant=True, entry="hooks"))
    (tmp_path / "digest.md").write_text(DIGEST, encoding="utf-8")
    out = run(tmp_path, "rename", "sub-agents", "subagents", "--digest")
    assert "renamed 1 headings and 2 links to {#subagents}" in out
    text = (tmp_path / "digest.md").read_text(encoding="utf-8")
    assert "sub-agents" not in text and "{#subagents}" in text and "(#hooks)" in text
    assert "agree (2 ideas)" in run(tmp_path, "check")


def test_digest_flag_warns_when_two_headings_now_share_the_slug(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="sub-agents"),
            reel("BBBBB2", relevant=True, entry="hooks"))
    path = tmp_path / "my-digest.md"
    path.write_text(DIGEST, encoding="utf-8")
    out = run(tmp_path, "rename", "hooks", "sub-agents", "--digest", str(path))
    assert "two {#sub-agents} ideas: merge their text" in out
    assert "{#hooks}" not in path.read_text(encoding="utf-8")


def test_digest_without_the_slug_is_left_alone(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="old"))
    (tmp_path / "digest.md").write_text(DIGEST, encoding="utf-8")
    assert "has no {#old} or (#old): left as it was" in run(tmp_path, "rename", "old", "new", "--digest")
    assert (tmp_path / "digest.md").read_text(encoding="utf-8") == DIGEST


def test_missing_digest_renames_nothing(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="old"))
    assert "Nothing was renamed" in run_failing(tmp_path, "rename", "old", "new", "--digest")
    assert entry_of(tmp_path) == {"AAAAA1": "old"}


def test_dry_run_says_what_would_change_and_writes_nothing(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="sub-agents"),
            reel("BBBBB2", relevant=True, entry="hooks"))
    run(tmp_path, "mark", "tried", "sub-agents")
    (tmp_path / "digest.md").write_text(DIGEST, encoding="utf-8")
    before = (tmp_path / "reels.json").read_text(encoding="utf-8")
    out = run(tmp_path, "rename", "sub-agents", "subagents", "--digest", "--dry-run")
    assert "Would move 1 reels from 'sub-agents' to 'subagents'." in out
    assert "Its tried mark would move too." in out
    assert "would rename 1 headings and 2 links to {#subagents}" in out
    assert "Dry run: nothing was changed" in out
    assert (tmp_path / "reels.json").read_text(encoding="utf-8") == before
    assert (tmp_path / "digest.md").read_text(encoding="utf-8") == DIGEST


def test_dry_run_of_a_merge_into_a_marked_idea(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="hooks"),
            reel("BBBBB2", relevant=True, entry="claude-hooks"))
    run(tmp_path, "mark", "discarded", "hooks")
    run(tmp_path, "mark", "tried", "claude-hooks")
    out = run(tmp_path, "rename", "hooks", "claude-hooks", "--dry-run")
    assert "Would move 1 reels" in out and "merged with the 1 already there" in out
    assert "Would keep the tried mark of 'claude-hooks' and drop the discarded mark of 'hooks'" in out
    assert entry_of(tmp_path) == {"AAAAA1": "hooks", "BBBBB2": "claude-hooks"}
    assert set(db(tmp_path)["entries"]) == {"hooks", "claude-hooks"}


def test_dry_run_still_refuses_unknown_slugs(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"))
    assert "nothing was renamed" in run_failing(tmp_path, "rename", "sub-agents", "x", "--dry-run")
