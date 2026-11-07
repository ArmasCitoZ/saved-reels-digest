"""The sample in examples/digest.md must keep the structure SKILL.md asks for,
so the exporters (Obsidian, --json for Notion) keep working on it."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "digest" / "scripts"))
import export_digest as ed  # noqa: E402

EXAMPLE = (ROOT / "examples" / "digest.md").read_text(encoding="utf-8")


def test_example_parses_and_header_counts_match():
    data = ed.to_json(EXAMPLE)
    n = int(re.search(r"(\d+) ideas únicas", EXAMPLE).group(1))
    assert len(data["ideas"]) == n
    assert data["date"] == "2026-11-01"
    assert data["categories"] == ["Claude Code", "Prompting", "Herramientas de IA"]
    assert {i["status"] for i in data["ideas"]} == {"todo", "tried", "discarded"}


def test_every_anchor_points_to_an_idea_and_every_idea_has_sources():
    data = ed.to_json(EXAMPLE)
    slugs = {i["slug"] for i in data["ideas"]}
    assert set(re.findall(r"\]\(#([\w-]+)\)", EXAMPLE)) <= slugs
    for i in data["ideas"]:
        count = int(re.search(r"\*\*Visto en (\d+) reels?\*\*", i["body"]).group(1))
        assert len(i["sources"]) == count, i["slug"]


def test_example_uses_only_invented_accounts():
    handles = set(re.findall(r"\[@([\w.]+)\]", EXAMPLE))
    assert handles and all(h.startswith("demo_") for h in handles)


def test_example_exports_to_obsidian(tmp_path):
    report = ed.export(EXAMPLE, tmp_path)
    assert "INDEX.md" in report["written"] and not report["skipped"]
