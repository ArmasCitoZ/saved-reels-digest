"""db.py check: digest.md and reels.json must agree on which reels went into which idea."""
import os
import subprocess
import sys

from test_db import SCRIPTS, load, make_db, reel, run

DIGEST = """# IA: my saved reels digest
_Updated 2026-11-10 · 4 saved · 3 on topic · 2 unique ideas after merging_

## Do these first
1. **Subagents** → [entry](#subagents)

## Claude Code
### Subagents {#subagents}
Split big tasks.

### MCP servers {#mcp-servers}
Connect tools. See also [subagents](#subagents).
"""


def write(home, text=DIGEST):
    (home / "digest.md").write_text(text, encoding="utf-8")


def test_agreeing_digest_and_database(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp-servers"), reel("CCCCC3", relevant=False))
    write(tmp_path)
    assert "agree (2 ideas)" in run(tmp_path, "check")


def test_reports_every_kind_of_mismatch(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="sub-agents"),
            reel("DDDDD4", relevant=True, caption="new reel"))
    write(tmp_path, DIGEST.replace("[subagents](#subagents)", "[hooks](#hooks)")
          + "\n### Subagents again {#subagents}\nDuplicate.\n")
    out = run(tmp_path, "check")
    assert "2 ideas share the slug {#subagents}" in out
    assert "1 reels point to 'sub-agents', which is not in the digest" in out and "BBBBB2" in out
    assert "No reel points to {#mcp-servers}" in out and "set entry mcp-servers" in out
    assert "(#hooks)" in out
    assert "1 relevant reels are not in any idea yet" in out
    assert "agree" not in out


def test_marks_for_ideas_no_longer_in_the_digest(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp-servers"), reel("EEEEE5", relevant=True, entry="old"))
    run(tmp_path, "mark", "discarded", "old")
    run(tmp_path, "set", "entry", "mcp-servers", "EEEEE5")
    write(tmp_path)
    assert "'old' is marked discarded but is not in the digest" in run(tmp_path, "check")


def test_slugs_inside_code_blocks_are_not_ideas(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp-servers"))
    write(tmp_path, DIGEST + "```\n### Not an idea {#nope}\n```\n")
    assert "agree (2 ideas)" in run(tmp_path, "check")


def test_missing_digest(tmp_path):
    make_db(tmp_path, reel("AAAAA1"))
    r = subprocess.run([sys.executable, str(SCRIPTS / "db.py"), "check"],
                       env={**os.environ, "SRD_HOME": str(tmp_path), "PYTHONIOENCODING": "utf-8"},
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode != 0 and "Write the digest first" in r.stderr


def _check(home, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / "db.py"), "check", *args],
                          env={**os.environ, "SRD_HOME": str(home), "PYTHONIOENCODING": "utf-8"},
                          capture_output=True, text=True, encoding="utf-8")


def test_strict_fails_only_when_there_is_something_to_fix(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp-servers"))
    write(tmp_path)
    r = _check(tmp_path, "--strict")
    assert r.returncode == 0 and "agree (2 ideas)" in r.stdout
    write(tmp_path, DIGEST.replace("{#mcp-servers}", "{#mcp}"))
    r = _check(tmp_path, "--strict")
    assert r.returncode == 1 and "things to fix" in r.stdout and "'mcp-servers'" in r.stdout
    assert _check(tmp_path).returncode == 0  # without --strict it only reports


def test_suggests_the_rename_when_one_idea_lost_its_reels(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp"))
    write(tmp_path)
    out = run(tmp_path, "check")
    assert "Probably renamed to {#mcp-servers}: db.py rename mcp mcp-servers" in out
    run(tmp_path, "rename", "mcp", "mcp-servers")
    assert "agree (2 ideas)" in run(tmp_path, "check")


def test_without_a_single_candidate_the_rename_has_a_placeholder(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp-servers"),
            reel("CCCCC3", relevant=True, entry="old-one"), reel("DDDDD4", relevant=True, entry="old-two"))
    write(tmp_path)
    out = run(tmp_path, "check")
    assert "Point them to the idea they belong to: db.py rename old-one NEW-SLUG" in out
    assert "db.py rename old-two NEW-SLUG" in out and "Probably renamed" not in out


def test_fix_applies_the_rename_check_is_sure_of(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp"), reel("CCCCC3", relevant=True, entry="mcp"))
    run(tmp_path, "mark", "tried", "mcp")
    write(tmp_path)
    out = run(tmp_path, "check", "--fix")
    assert "Fixed: Moved 2 reels from 'mcp' to 'mcp-servers'. Its tried mark moved too." in out
    assert "agree (2 ideas)" in out
    reels = load(tmp_path)
    assert reels["BBBBB2"]["entry"] == reels["CCCCC3"]["entry"] == "mcp-servers"
    assert "mcp-servers" in run(tmp_path, "marks", "--status", "tried")


def test_fix_does_nothing_when_the_rename_is_a_guess(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp-servers"),
            reel("CCCCC3", relevant=True, entry="old-one"), reel("DDDDD4", relevant=True, entry="old-two"))
    write(tmp_path)
    out = run(tmp_path, "check", "--fix")
    assert "Nothing to fix automatically" in out and "Fixed" not in out
    assert "db.py rename old-one NEW-SLUG" in out
    assert load(tmp_path)["CCCCC3"]["entry"] == "old-one"


def test_fix_on_an_agreeing_digest_leaves_it_alone(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp-servers"))
    write(tmp_path)
    out = run(tmp_path, "check", "--fix", "--strict")
    assert "Nothing to fix automatically" in out and "agree (2 ideas)" in out


NEAR = DIGEST + """
### Subagent tricks {#subagent}
More on splitting tasks.

### Step 1 {#step-1}
First.

### Step 2 {#step-2}
Second.
"""


def test_hints_at_ideas_with_nearly_the_same_slug(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("AAAAA2", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp-servers"),
            reel("CCCCC3", relevant=True, entry="subagent"),
            reel("DDDDD4", relevant=True, entry="step-1"), reel("EEEEE5", relevant=True, entry="step-2"))
    write(tmp_path, NEAR)
    out = run(tmp_path, "check", "--strict")  # a hint is not a problem: --strict still passes
    assert "agree (5 ideas)" in out and "Maybe the same idea" in out
    assert "{#subagent} (1 reels) and {#subagents} (2 reels)" in out
    assert "db.py rename subagent subagents --digest" in out
    assert "step-1" not in out.split("Maybe the same idea")[1]


def test_no_hint_when_slugs_are_different_enough(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp-servers"))
    write(tmp_path)
    assert "Maybe the same idea" not in run(tmp_path, "check")


def test_separator_only_differences_are_near(tmp_path):
    make_db(tmp_path, reel("AAAAA1", relevant=True, entry="subagents"),
            reel("BBBBB2", relevant=True, entry="mcp-servers"),
            reel("CCCCC3", relevant=True, entry="mcp_servers"))
    write(tmp_path, DIGEST + "\n### MCP again {#mcp_servers}\nSame.\n")
    out = run(tmp_path, "check")
    assert "{#mcp_servers} (1 reels) and {#mcp-servers} (1 reels)" in out
    assert "db.py rename mcp_servers mcp-servers --digest" in out
