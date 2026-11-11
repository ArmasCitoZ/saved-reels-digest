"""db.py check: digest.md and reels.json must agree on which reels went into which idea."""
import os
import subprocess
import sys

from test_db import SCRIPTS, make_db, reel, run

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
