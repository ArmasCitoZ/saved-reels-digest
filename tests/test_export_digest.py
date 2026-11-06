"""Tests for exporting digest.md to an Obsidian vault (export_digest.py)."""
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import export_digest as ed  # noqa: E402

DIGEST = """# Tech: my saved reels digest
_Updated 2026-11-01 · 40 saved · 12 on topic · 3 unique ideas after merging_

## Do these first
1. **Plan mode first**: avoids rewrites → [entry](#plan-mode)
2. **Use CLAUDE.md**: context for free → [entry](#claude-md)

## Claude Code
### Plan mode before big changes {#plan-mode}
Ask for a plan, review it, then let it edit. See also [CLAUDE.md](#claude-md).
**How to apply:** press Shift+Tab twice.
**Seen in 2 reels:** [@demo_ai](https://www.instagram.com/reel/DFixAi0001/) · [@demo_dev](https://www.instagram.com/reel/DFixDev003/)

### Keep a CLAUDE.md: project memory {#claude-md}
Write conventions once.
**Seen in 1 reels:** [@demo_ai](https://www.instagram.com/reel/DFixAi0002/)

## Prompting
### Give examples, not adjectives
Show one good output.
**Notes:** mostly hype in one reel.
"""


def test_parse_digest_structure():
    d = ed.parse_digest(DIGEST)
    assert d["title"] == "Tech: my saved reels digest" and d["date"] == "2026-11-01"
    assert len(d["top"]) == 2
    assert [(i["slug"], i["category"]) for i in d["ideas"]] == [
        ("plan-mode", "Claude Code"), ("claude-md", "Claude Code"),
        ("give-examples-not-adjectives", "Prompting")]
    assert "Shift+Tab" in d["ideas"][0]["body"]


def test_one_note_per_idea_with_frontmatter_and_links(tmp_path):
    report = ed.export(DIGEST, tmp_path)
    assert sorted(report["written"]) == sorted([
        "INDEX.md", "Plan mode before big changes.md", "Keep a CLAUDE.md project memory.md",
        "Give examples, not adjectives.md"])
    note = (tmp_path / "Plan mode before big changes.md").read_text(encoding="utf-8")
    assert note.startswith('---\ntitle: "Plan mode before big changes"\ndate: 2026-11-01\n')
    assert "tags: [saved-reels, claude-code]" in note and "aliases: [plan-mode]" in note
    assert "  - https://www.instagram.com/reel/DFixDev003/" in note
    # in-digest anchor becomes a relative, URL-encoded link to the other note
    assert "[CLAUDE.md](Keep%20a%20CLAUDE.md%20project%20memory.md)" in note
    assert "Related: [Keep a CLAUDE.md: project memory](Keep%20a%20CLAUDE.md%20project%20memory.md)" in note
    assert note.rstrip().endswith("Up: [Index](INDEX.md)")


def test_index_is_a_map_of_content(tmp_path):
    ed.export(DIGEST, tmp_path)
    index = (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    assert "## Do these first" in index
    assert "→ [entry](Plan%20mode%20before%20big%20changes.md)" in index
    assert index.index("## Claude Code") < index.index("## Prompting")
    assert "- [Give examples, not adjectives](Give%20examples%2C%20not%20adjectives.md)" in index


def test_rerun_keeps_my_notes_and_never_touches_foreign_files(tmp_path):
    ed.export(DIGEST, tmp_path)
    note = tmp_path / "Plan mode before big changes.md"
    note.write_text(note.read_text(encoding="utf-8") + "\n## My notes\nTried it: works.\n",
                    encoding="utf-8")
    foreign = tmp_path / "Give examples, not adjectives.md"
    foreign.write_text("my own note, not generated\n", encoding="utf-8")
    report = ed.export(DIGEST.replace("Ask for a plan", "Always ask for a plan"), tmp_path)
    text = note.read_text(encoding="utf-8")
    assert "Always ask for a plan" in text and text.rstrip().endswith("Tried it: works.")
    assert text.count("## My notes") == 1
    assert report["skipped"] == ["Give examples, not adjectives.md"]
    assert foreign.read_text(encoding="utf-8") == "my own note, not generated\n"


def test_removed_ideas_are_reported_not_deleted(tmp_path):
    ed.export(DIGEST, tmp_path)
    shorter = DIGEST.split("## Prompting")[0]
    report = ed.export(shorter, tmp_path)
    assert report["stale"] == ["Give examples, not adjectives.md"]
    assert (tmp_path / "Give examples, not adjectives.md").exists()


def test_titles_are_made_safe_and_unique(tmp_path):
    digest = ("## A\n### What/why: a? {#one}\nx\n### What why a {#two}\ny\n")
    ed.export(digest, tmp_path)
    assert {p.name for p in tmp_path.glob("*.md")} == {
        "INDEX.md", "Whatwhy a.md", "What why a.md"}
    dup = "## A\n### Same {#s1}\nx\n## B\n### Same {#s2}\ny\n"
    ed.export(dup, tmp_path / "dup")
    assert {p.name for p in (tmp_path / "dup").glob("*.md")} == {"INDEX.md", "Same.md", "Same (s2).md"}


def test_cli_writes_into_vault_subfolder(tmp_path):
    src = tmp_path / "digest.md"
    src.write_text(DIGEST, encoding="utf-8")
    vault = tmp_path / "vault"
    r = subprocess.run([sys.executable, str(SCRIPTS / "export_digest.py"), "--vault", str(vault),
                        "--digest", str(src)], env={**os.environ, "SRD_HOME": str(tmp_path)},
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    assert (vault / "Saved reels" / "INDEX.md").exists() and "Wrote 4 notes" in r.stdout


def test_cli_rejects_a_digest_without_ideas(tmp_path):
    src = tmp_path / "digest.md"
    src.write_text("# Empty\n\nnothing yet\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "export_digest.py"), "--vault",
                        str(tmp_path / "v"), "--digest", str(src)],
                       capture_output=True, text=True, check=False)
    assert r.returncode != 0 and "no ideas found" in r.stderr
