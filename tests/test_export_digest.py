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


# ------------------------------------------------------------------ --json
def test_to_json_has_ideas_sources_and_status():
    digest = DIGEST.replace("Write conventions once.",
                            "**Status:** ✅ Tried: works on every repo\nWrite conventions once.")
    data = ed.to_json(digest)
    assert data["title"] == "Tech: my saved reels digest" and data["date"] == "2026-11-01"
    assert data["categories"] == ["Claude Code", "Prompting"]
    assert len(data["top"]) == 2
    by_slug = {i["slug"]: i for i in data["ideas"]}
    assert by_slug["plan-mode"]["sources"] == ["https://www.instagram.com/reel/DFixAi0001/",
                                               "https://www.instagram.com/reel/DFixDev003/"]
    assert by_slug["claude-md"]["status"] == "tried"
    assert by_slug["plan-mode"]["status"] == "todo"
    assert ed.to_json(DIGEST.replace("**Notes:**", "**Status:** 🚫 Discarded: meh\n**Notes:**")
                      )["ideas"][2]["status"] == "discarded"


def test_cli_json_prints_and_writes_nothing(tmp_path):
    import json

    src = tmp_path / "digest.md"
    src.write_text(DIGEST, encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "export_digest.py"), "--json",
                        "--digest", str(src)], env={**os.environ, "SRD_HOME": str(tmp_path)},
                       capture_output=True, text=True, encoding="utf-8", check=False)
    assert r.returncode == 0, r.stderr
    assert [i["slug"] for i in json.loads(r.stdout)["ideas"]] == [
        "plan-mode", "claude-md", "give-examples-not-adjectives"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["digest.md"]


def test_cli_needs_vault_or_json(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPTS / "export_digest.py")],
                       capture_output=True, text=True, check=False)
    assert r.returncode != 0 and "--vault" in r.stderr


PORTUGUESE = """# Meus reels

## Faça isto primeiro
1. **Plano curto** → [entrada](#plano)

## Ferramentas
### Plano curto {#plano}
**Estado:** ✅ Testado: funcionou
Resumo.

### Sem marca {#sem-marca}
**Como aplicar:** ✅ siga os passos
Outro resumo.

### Descartada {#descartada}
**Estado:** 🚫 Descartado
Resumo.
"""


def test_top_list_is_found_in_any_language():
    d = ed.parse_digest(PORTUGUESE)
    assert len(d["top"]) == 1 and d["top_heading"] == "Faça isto primeiro"
    assert [i["category"] for i in d["ideas"]] == ["Ferramentas"] * 3


def test_a_first_category_of_ideas_is_not_mistaken_for_the_top_list():
    d = ed.parse_digest("# T\n\n## Tools\n### One {#one}\n1. a numbered step\n")
    assert d["top"] == [] and d["ideas"][0]["slug"] == "one"


def test_status_marks_work_in_any_language():
    ideas = {i["slug"]: i["status"] for i in ed.to_json(PORTUGUESE)["ideas"]}
    assert ideas == {"plano": "tried", "sem-marca": "todo", "descartada": "discarded"}


def test_index_keeps_the_digest_heading(tmp_path):
    ed.export(PORTUGUESE, tmp_path, today="2026-11-08")
    assert "## Faça isto primeiro" in (tmp_path / "INDEX.md").read_text("utf-8")


def _names(*titles):
    ideas = [{"title": t, "slug": f"s{n}"} for n, t in enumerate(titles)]
    ed.assign_filenames(ideas)
    return [i["file"] for i in ideas]


def test_an_idea_called_index_does_not_replace_the_index(tmp_path):
    digest = "# D\n\n## Tools\n### Index {#the-index}\nKeep an index.\n\n### Other {#other}\nText.\n"
    report = ed.export(digest, tmp_path / "out", today="2026-11-08")
    index = (tmp_path / "out" / "INDEX.md").read_text("utf-8")
    assert "](Index%20%28the-index%29.md)" in index  # still the map of content, linking to the idea
    assert (tmp_path / "out" / "Index (the-index).md").exists()
    assert not report["skipped"]


def test_names_windows_cannot_create_are_avoided():
    assert _names("CON", "aux", "Nul", "Com1", "Console") == [
        "CON (s0).md", "aux (s1).md", "Nul (s2).md", "Com1 (s3).md", "Console.md"]


def test_slugs_can_have_accents(tmp_path):
    digest = ("# D\n\n## Hazlo ya\n1. **Automatiza** → [entrada](#automatización)\n\n"
              "## Herramientas\n### Automatiza tus tareas {#automatización}\nMira [otra](#revisión).\n\n"
              "### Revisa antes de publicar {#revisión}\nTexto.\n")
    ideas = ed.parse_digest(digest)["ideas"]
    assert [(i["title"], i["slug"]) for i in ideas] == [
        ("Automatiza tus tareas", "automatización"), ("Revisa antes de publicar", "revisión")]
    ed.export(digest, tmp_path, today="2026-11-08")
    note = (tmp_path / "Automatiza tus tareas.md").read_text("utf-8")
    assert "](Revisa%20antes%20de%20publicar.md)" in note
    assert "](Automatiza%20tus%20tareas.md)" in (tmp_path / "INDEX.md").read_text("utf-8")


FENCED = """# D

## Tools
### Set up the hook {#hook}
Paste this:
```markdown
## Not a category
### Not an idea
```
**How to apply:** done.

### Second idea {#second}
Text.
"""


def test_headings_inside_code_blocks_stay_in_the_idea():
    d = ed.parse_digest(FENCED)
    assert [i["slug"] for i in d["ideas"]] == ["hook", "second"]
    assert [i["category"] for i in d["ideas"]] == ["Tools", "Tools"]
    assert "### Not an idea" in d["ideas"][0]["body"] and "How to apply" in d["ideas"][0]["body"]


def test_tilde_fences_count_too():
    text = FENCED.replace("```markdown", "~~~").replace("```", "~~~")
    assert [i["slug"] for i in ed.parse_digest(text)["ideas"]] == ["hook", "second"]


def test_a_fence_never_closed_does_not_swallow_the_rest():
    d = ed.parse_digest("# D\n\n## Tools\n### One {#one}\n```\ncode\n\n### Two {#two}\nText.\n")
    assert [i["slug"] for i in d["ideas"]] == ["one", "two"]


# ------------------------------------------------------------------ marks from reels.json
def _db_with_marks(home: Path, entries: dict) -> None:
    import json

    home.mkdir(parents=True, exist_ok=True)
    (home / "reels.json").write_text(json.dumps({"reels": {}, "entries": entries}), encoding="utf-8")


def test_marks_from_the_database_win_over_the_digest_text(tmp_path):
    _db_with_marks(tmp_path, {"plan-mode": {"status": "tried", "note": "saves time", "updated": 1},
                              "claude-md": {"status": "discarded"},
                              "ghost": {"status": "tried"}})
    marks = ed.load_marks(tmp_path / "reels.json")
    assert marks == {"plan-mode": {"status": "tried", "note": "saves time"},
                     "claude-md": {"status": "discarded", "note": None},
                     "ghost": {"status": "tried", "note": None}}
    digest = DIGEST.replace("Write conventions once.", "**Status:** ✅ Tried: old\nWrite conventions once.")
    by_slug = {i["slug"]: i for i in ed.to_json(digest, marks)["ideas"]}
    assert (by_slug["plan-mode"]["status"], by_slug["plan-mode"]["note"]) == ("tried", "saves time")
    assert by_slug["claude-md"]["status"] == "discarded"  # the mark beats the digest's "Tried"
    assert (by_slug["give-examples-not-adjectives"]["status"],
            by_slug["give-examples-not-adjectives"]["note"]) == ("todo", None)


def test_missing_or_damaged_database_means_no_marks(tmp_path, capsys):
    assert ed.load_marks(tmp_path / "reels.json") == {}
    (tmp_path / "reels.json").write_text("{not json", encoding="utf-8")
    assert ed.load_marks(tmp_path / "reels.json") == {}
    assert "Status lines" in capsys.readouterr().err
    _db_with_marks(tmp_path, {"x": {"status": "weird"}, "y": "tried"})
    assert ed.load_marks(tmp_path / "reels.json") == {}


def test_cli_json_uses_the_marks_in_reels_json(tmp_path):
    import json

    _db_with_marks(tmp_path, {"claude-md": {"status": "tried", "note": "works"}})
    src = tmp_path / "digest.md"
    src.write_text(DIGEST, encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "export_digest.py"), "--json",
                        "--digest", str(src)], env={**os.environ, "SRD_HOME": str(tmp_path)},
                       capture_output=True, text=True, encoding="utf-8", check=False)
    assert r.returncode == 0, r.stderr
    by_slug = {i["slug"]: i for i in json.loads(r.stdout)["ideas"]}
    assert (by_slug["claude-md"]["status"], by_slug["claude-md"]["note"]) == ("tried", "works")


def _frontmatter(note: str) -> str:
    return note.split("\n---", 1)[0]


def test_notes_have_the_status_property(tmp_path):
    digest = DIGEST.replace("**Notes:**", "**Status:** 🚫 Discarded: hype\n**Notes:**")
    ed.export(digest, tmp_path, marks={"plan-mode": {"status": "tried", "note": 'fast "and" safe\nreally'}})
    plan = _frontmatter((tmp_path / "Plan mode before big changes.md").read_text(encoding="utf-8"))
    assert "\nstatus: tried\n" in plan
    assert '\nnote: "fast \\"and\\" safe\\nreally"\n' in plan  # one YAML line, quotes escaped
    claude = _frontmatter((tmp_path / "Keep a CLAUDE.md project memory.md").read_text(encoding="utf-8"))
    assert "\nstatus: todo\n" in claude and "\nnote:" not in claude
    examples = _frontmatter((tmp_path / "Give examples, not adjectives.md").read_text(encoding="utf-8"))
    assert "\nstatus: discarded\n" in examples  # from the digest text when there is no mark


def test_cli_vault_uses_the_marks_in_reels_json(tmp_path):
    _db_with_marks(tmp_path, {"claude-md": {"status": "tried", "note": "works"}})
    src = tmp_path / "digest.md"
    src.write_text(DIGEST, encoding="utf-8")
    vault = tmp_path / "vault"
    r = subprocess.run([sys.executable, str(SCRIPTS / "export_digest.py"), "--vault", str(vault),
                        "--digest", str(src)], env={**os.environ, "SRD_HOME": str(tmp_path)},
                       capture_output=True, text=True, encoding="utf-8", check=False)
    assert r.returncode == 0, r.stderr
    note = (vault / "Saved reels" / "Keep a CLAUDE.md project memory.md").read_text(encoding="utf-8")
    assert "\nstatus: tried\n" in note and '\nnote: "works"\n' in note


def test_index_shows_which_ideas_are_tried_or_discarded(tmp_path):
    ed.export(DIGEST, tmp_path, marks={"plan-mode": {"status": "tried", "note": None},
                                       "give-examples-not-adjectives": {"status": "discarded", "note": None}})
    index = (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    assert "_Exported from digest.md on 2026-11-01 · 3 ideas · ✅ 1 tried · 🚫 1 discarded_" in index
    assert "- [Plan mode before big changes](Plan%20mode%20before%20big%20changes.md) ✅\n" in index
    assert "- [Give examples, not adjectives](Give%20examples%2C%20not%20adjectives.md) 🚫\n" in index
    assert "(Keep%20a%20CLAUDE.md%20project%20memory.md)\n" in index  # pending: no mark


def test_index_without_marks_has_no_counts(tmp_path):
    ed.export(DIGEST, tmp_path)
    index = (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    assert "_Exported from digest.md on 2026-11-01 · 3 ideas_" in index
    assert "✅" not in index and "🚫" not in index


# ------------------------------------------------------------------ --prune
def test_prune_deletes_old_notes_but_keeps_my_notes_and_foreign_files(tmp_path):
    ed.export(DIGEST, tmp_path)
    examples = tmp_path / "Give examples, not adjectives.md"
    claude = tmp_path / "Keep a CLAUDE.md project memory.md"
    claude.write_text(claude.read_text(encoding="utf-8") + "\n## My notes\nKeep this.\n", encoding="utf-8")
    plan = tmp_path / "Plan mode before big changes.md"
    plan.write_text(plan.read_text(encoding="utf-8") + "\n## My notes\n\n", encoding="utf-8")  # empty
    foreign = tmp_path / "Mine.md"
    foreign.write_text("my own note\n", encoding="utf-8")
    only_index = "# T\n\n## Other\n### Something new {#new}\nText.\n"
    report = ed.export(only_index, tmp_path, prune=True)
    assert sorted(report["pruned"]) == ["Give examples, not adjectives.md", "Plan mode before big changes.md"]
    assert report["stale"] == ["Keep a CLAUDE.md project memory.md"]
    assert not examples.exists() and not plan.exists()
    assert claude.exists() and foreign.exists() and (tmp_path / "Something new.md").exists()


def test_cli_prune_says_what_it_deleted_and_kept(tmp_path):
    src = tmp_path / "digest.md"
    src.write_text(DIGEST, encoding="utf-8")
    vault = tmp_path / "vault"

    def run(*extra):
        return subprocess.run([sys.executable, str(SCRIPTS / "export_digest.py"), "--vault", str(vault),
                               "--digest", str(src), *extra], env={**os.environ, "SRD_HOME": str(tmp_path)},
                              capture_output=True, text=True, encoding="utf-8", check=False)

    assert run().returncode == 0
    src.write_text(DIGEST.split("## Prompting")[0], encoding="utf-8")
    r = run()
    assert "--prune deletes them): Give examples, not adjectives.md" in r.stdout
    assert (vault / "Saved reels" / "Give examples, not adjectives.md").exists()
    r = run("--prune")
    assert r.returncode == 0, r.stderr
    assert "Deleted, no longer in the digest: Give examples, not adjectives.md" in r.stdout
    assert not (vault / "Saved reels" / "Give examples, not adjectives.md").exists()


def test_notes_have_reels_and_last_saved_properties(tmp_path):
    import json

    reels = {"A1": {"entry": "plan-mode", "saved_at": 1761955200},  # 2025-11-01
             "A2": {"entry": "plan-mode", "saved_at": 1762300800},  # 2025-11-05
             "B1": {"entry": "claude-md", "added_at": None},       # no known date
             "C1": {"entry": None, "saved_at": 1762300800}}
    (tmp_path / "reels.json").write_text(json.dumps({"reels": reels}), encoding="utf-8")
    stats = ed.load_reel_stats(tmp_path / "reels.json")
    assert stats == {"plan-mode": {"reels": 2, "last_saved": "2025-11-05"},
                     "claude-md": {"reels": 1, "last_saved": None}}
    vault = tmp_path / "vault"
    ed.export(DIGEST, vault, stats=stats)
    plan = _frontmatter((vault / "Plan mode before big changes.md").read_text(encoding="utf-8"))
    assert "\nreels: 2\n" in plan and "\nlast_saved: 2025-11-05\n" in plan  # a YAML date, unquoted
    claude = _frontmatter((vault / "Keep a CLAUDE.md project memory.md").read_text(encoding="utf-8"))
    assert "\nreels: 1\n" in claude and "last_saved" not in claude
    examples = _frontmatter((vault / "Give examples, not adjectives.md").read_text(encoding="utf-8"))
    assert "reels:" not in examples and "last_saved" not in examples  # no reel points to it


def test_missing_or_damaged_database_means_no_stats(tmp_path):
    assert ed.load_reel_stats(tmp_path / "reels.json") == {}
    (tmp_path / "reels.json").write_text("{not json", encoding="utf-8")
    assert ed.load_reel_stats(tmp_path / "reels.json") == {}
    (tmp_path / "reels.json").write_text('{"reels": {"X": "oops", "Y": {"entry": "a", "saved_at": "bad"}}}',
                                         encoding="utf-8")
    assert ed.load_reel_stats(tmp_path / "reels.json") == {"a": {"reels": 1, "last_saved": None}}


def test_cli_vault_writes_the_reel_properties(tmp_path):
    import json

    db = {"reels": {"A1": {"entry": "claude-md", "saved_at": 1762300800}}}
    (tmp_path / "reels.json").write_text(json.dumps(db), encoding="utf-8")
    src = tmp_path / "digest.md"
    src.write_text(DIGEST, encoding="utf-8")
    vault = tmp_path / "vault"
    r = subprocess.run([sys.executable, str(SCRIPTS / "export_digest.py"), "--vault", str(vault),
                        "--digest", str(src)], env={**os.environ, "SRD_HOME": str(tmp_path)},
                       capture_output=True, text=True, encoding="utf-8", check=False)
    assert r.returncode == 0, r.stderr
    note = (vault / "Saved reels" / "Keep a CLAUDE.md project memory.md").read_text(encoding="utf-8")
    assert "\nreels: 1\n" in note and "\nlast_saved: 2025-11-05\n" in note


def test_to_json_has_reels_and_last_saved():
    stats = {"plan-mode": {"reels": 3, "last_saved": "2025-11-05"},
             "claude-md": {"reels": 1, "last_saved": None}}
    by_slug = {i["slug"]: i for i in ed.to_json(DIGEST, stats=stats)["ideas"]}
    assert (by_slug["plan-mode"]["reels"], by_slug["plan-mode"]["last_saved"]) == (3, "2025-11-05")
    assert (by_slug["claude-md"]["reels"], by_slug["claude-md"]["last_saved"]) == (1, None)
    # no reel points to it: still there, so Notion always gets the same fields
    give = by_slug["give-examples-not-adjectives"]
    assert (give["reels"], give["last_saved"]) == (0, None)
    assert all(i["reels"] == 0 and i["last_saved"] is None for i in ed.to_json(DIGEST)["ideas"])


def test_cli_json_reads_the_reel_stats_from_reels_json(tmp_path):
    import json

    db = {"reels": {"A1": {"entry": "plan-mode", "saved_at": 1761955200},
                    "A2": {"entry": "plan-mode", "saved_at": 1762300800}}}
    (tmp_path / "reels.json").write_text(json.dumps(db), encoding="utf-8")
    src = tmp_path / "digest.md"
    src.write_text(DIGEST, encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "export_digest.py"), "--json",
                        "--digest", str(src)], env={**os.environ, "SRD_HOME": str(tmp_path)},
                       capture_output=True, text=True, encoding="utf-8", check=False)
    assert r.returncode == 0, r.stderr
    by_slug = {i["slug"]: i for i in json.loads(r.stdout)["ideas"]}
    assert (by_slug["plan-mode"]["reels"], by_slug["plan-mode"]["last_saved"]) == (2, "2025-11-05")
    assert by_slug["claude-md"]["reels"] == 0


def _db_with_dated_marks(tmp_path):
    import json

    marked = 1762000000  # 2025-11-01
    db = {"reels": {"A1": {"entry": "plan-mode", "saved_at": marked - 86400},
                    "A2": {"entry": "plan-mode", "saved_at": marked + 86400},
                    "A3": {"entry": "plan-mode", "added_at": None},           # no date: never new
                    "B1": {"entry": "claude-md", "saved_at": marked - 86400},
                    "C1": {"entry": "give-examples-not-adjectives", "saved_at": marked + 86400}},
          "entries": {"plan-mode": {"status": "tried", "updated": marked},
                      "claude-md": {"status": "discarded", "updated": marked, "note": "meh"},
                      "ghost": {"status": "tried", "updated": marked}}}
    (tmp_path / "reels.json").write_text(json.dumps(db), encoding="utf-8")


def test_reel_stats_count_reels_saved_after_the_mark(tmp_path):
    _db_with_dated_marks(tmp_path)
    stats = ed.load_reel_stats(tmp_path / "reels.json")
    assert stats["plan-mode"]["new_since_mark"] == 1
    assert stats["claude-md"]["new_since_mark"] == 0  # marked, nothing new: 0, not missing
    assert "new_since_mark" not in stats["give-examples-not-adjectives"]  # not marked
    assert "ghost" not in stats  # a mark with no reels gives no stats


def test_notes_and_json_have_new_since_mark(tmp_path):
    _db_with_dated_marks(tmp_path)
    stats = ed.load_reel_stats(tmp_path / "reels.json")
    marks = ed.load_marks(tmp_path / "reels.json")
    vault = tmp_path / "vault"
    ed.export(DIGEST, vault, marks=marks, stats=stats)
    plan = _frontmatter((vault / "Plan mode before big changes.md").read_text(encoding="utf-8"))
    assert "\nstatus: tried\n" in plan and "\nnew_since_mark: 1\n" in plan
    claude = _frontmatter((vault / "Keep a CLAUDE.md project memory.md").read_text(encoding="utf-8"))
    assert "\nnew_since_mark: 0\n" in claude
    examples = _frontmatter((vault / "Give examples, not adjectives.md").read_text(encoding="utf-8"))
    assert "new_since_mark" not in examples
    by_slug = {i["slug"]: i for i in ed.to_json(DIGEST, marks, stats)["ideas"]}
    assert by_slug["plan-mode"]["new_since_mark"] == 1
    assert by_slug["claude-md"]["new_since_mark"] == 0
    assert by_slug["give-examples-not-adjectives"]["new_since_mark"] is None


def test_marks_without_a_date_count_nothing_as_new(tmp_path):
    import json

    db = {"reels": {"A1": {"entry": "plan-mode", "saved_at": 1762300800}},
          "entries": {"plan-mode": {"status": "tried"}}}
    (tmp_path / "reels.json").write_text(json.dumps(db), encoding="utf-8")
    assert ed.load_reel_stats(tmp_path / "reels.json") == {
        "plan-mode": {"reels": 1, "last_saved": "2025-11-05"}}


def test_index_shows_new_reels_since_the_mark(tmp_path):
    _db_with_dated_marks(tmp_path)
    stats = ed.load_reel_stats(tmp_path / "reels.json")
    marks = ed.load_marks(tmp_path / "reels.json")
    ed.export(DIGEST, tmp_path / "vault", marks=marks, stats=stats)
    index = (tmp_path / "vault" / "INDEX.md").read_text(encoding="utf-8")
    assert "(Plan%20mode%20before%20big%20changes.md) ✅ +1\n" in index
    assert "(Keep%20a%20CLAUDE.md%20project%20memory.md) 🚫\n" in index  # marked, nothing new
    assert " · 1 with new reels since the mark_" in index


def test_index_has_no_new_count_for_pending_ideas_or_without_stats(tmp_path):
    marks = {"plan-mode": {"status": "tried", "note": None}}
    stats = {"plan-mode": {"reels": 2, "last_saved": None, "new_since_mark": 0},
             "claude-md": {"reels": 3, "last_saved": None, "new_since_mark": 2}}  # pending
    ed.export(DIGEST, tmp_path, marks=marks, stats=stats)
    index = (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    assert "+" not in index.split("\n---", 1)[1].replace("](", "")  # no badge anywhere
    assert "with new reels" not in index
    ed.export(DIGEST, tmp_path / "plain", marks=marks)
    assert "with new reels" not in (tmp_path / "plain" / "INDEX.md").read_text("utf-8")
