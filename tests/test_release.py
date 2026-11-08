"""The changelog and the release script must stay in step with plugin.json."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "release_notes.py"
sys.path.insert(0, str(SCRIPT.parent))
import release_notes as rn  # noqa: E402

VERSION = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text("utf-8"))["version"]
SAMPLE = ("# Changelog\n\n## [Unreleased]\n\n- soon\n\n"
          "## [1.2.0] - 2026-12-01\n\n- new\n\n## [1.1.0]\n\n- old\n")


def test_section_stops_at_the_next_version():
    assert rn.section(SAMPLE, "1.2.0") == "- new"
    assert rn.section(SAMPLE, "1.1.0") == "- old"
    assert rn.section(SAMPLE, "9.9.9") is None
    assert rn.section("## [1.0.0]\n\n## [0.9.0]\n- x\n", "1.0.0") is None  # empty is not ready


def run(tag):
    return subprocess.run([sys.executable, str(SCRIPT), tag], capture_output=True, text=True,
                          encoding="utf-8")


def test_current_version_can_be_released():
    r = run(f"v{VERSION}")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip()


def test_tag_that_does_not_match_the_manifest_is_refused():
    r = run("v99.0.0")
    assert r.returncode == 1 and "plugin.json" in r.stderr
