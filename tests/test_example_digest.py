"""The sample in examples/digest.md must keep the structure SKILL.md asks for,
so the exporters (Obsidian, --json for Notion) keep working on it. examples/reels.json is
the matching database, for the viewer demo: db.py check must find both in agreement."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "digest" / "scripts"))
import export_digest as ed  # noqa: E402

EXAMPLE = (ROOT / "examples" / "digest.md").read_text(encoding="utf-8")
EXAMPLE_DB = json.loads((ROOT / "examples" / "reels.json").read_text(encoding="utf-8"))


def test_example_parses_and_header_counts_match():
    data = ed.to_json(EXAMPLE)
    n = int(re.search(r"(\d+) ideas únicas", EXAMPLE).group(1))
    assert len(data["ideas"]) == n
    assert data["date"] == "2026-11-01"
    assert data["categories"] == ["Claude Code", "Prompting", "Herramientas de IA"]
    assert {i["status"] for i in data["ideas"]} == {"todo", "tried", "discarded"}
    assert len(data["top"]) == 4  # the translated "Haz esto primero" heading is recognized


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


def test_example_database_agrees_with_the_digest(tmp_path):
    # run on a copy: db.py writes a daily backup next to reels.json
    for name in ("digest.md", "reels.json"):
        shutil.copy(ROOT / "examples" / name, tmp_path / name)
    env = {**os.environ, "SRD_HOME": str(tmp_path), "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, str(ROOT / "skills" / "digest" / "scripts" / "db.py"), "check"],
                       env=env, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert "agree (6 ideas)" in r.stdout


def test_example_database_links_and_marks_match_the_digest():
    reels = EXAMPLE_DB["reels"].values()
    for i in ed.to_json(EXAMPLE)["ideas"]:
        urls = sorted(r["url"] for r in reels if r.get("entry") == i["slug"])
        assert urls == sorted(i["sources"]), i["slug"]
        mark = EXAMPLE_DB["entries"].get(i["slug"], {}).get("status", "todo")
        assert mark == i["status"], i["slug"]
    assert all(r["author"].startswith("demo_") for r in reels)
