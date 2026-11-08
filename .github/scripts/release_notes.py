"""Print the CHANGELOG section for a release tag, failing if the release is not ready.

  python .github/scripts/release_notes.py v0.2.0

Used by the release workflow: the tag must match plugin.json and have its own section.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def section(changelog: str, version: str) -> str | None:
    """The text under '## [version]', up to the next '## [' heading."""
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", changelog, re.M | re.S)
    return m.group(1).strip() if m and m.group(1).strip() else None


def main(argv: list) -> int:
    version = argv[0].lstrip("v")
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text("utf-8"))["version"]
    if manifest != version:
        print(f"Tag says {version} but plugin.json says {manifest}.", file=sys.stderr)
        return 1
    notes = section((ROOT / "CHANGELOG.md").read_text("utf-8"), version)
    if notes is None:
        print(f"CHANGELOG.md has no section for {version}.", file=sys.stderr)
        return 1
    sys.stdout.reconfigure(encoding="utf-8")
    print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
